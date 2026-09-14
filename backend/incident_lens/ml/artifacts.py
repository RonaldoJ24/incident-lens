"""Versioned model artifact writing, loading, and integrity checks."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from .ranking import ARTIFACT_VERSION, ERROR_RATE_THRESHOLD, FEATURE_NAMES, FEATURE_SCHEMA_VERSION, LATENCY_THRESHOLD_MS

# ``joblib`` is a scikit-learn dependency.  Import lazily so manifest
# validation and rule-only operation remain usable before optional installation.


class ArtifactError(ValueError):
    """Raised for invalid, unsigned, or unsafe ranking artifacts."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RELATIVE = re.compile(r"^[A-Za-z0-9._/-]+$")
_LEAK = re.compile(
    r"(?:root.?cause|ground.?truth|hidden.?label|fault.?type|inject(?:ion)?_?time|"
    r"source.?filename|file.?name|answer|solution|re[123](?:ob|ss|tt)_[a-z0-9_-]+)",
    re.IGNORECASE,
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def manifest_digest(document: Mapping[str, Any]) -> str:
    without = dict(document)
    without.pop("artifact_sha256", None)
    return hashlib.sha256(_canonical(without).encode("utf-8")).hexdigest()


def _safe_artifact_path(path: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or not _RELATIVE.fullmatch(value) or value.startswith("/"):
        raise ArtifactError("artifact model path must be relative")
    candidate = (path.parent / value).resolve()
    try:
        candidate.relative_to(path.parent.resolve())
    except ValueError as exc:
        raise ArtifactError("artifact model path escapes its manifest directory") from exc
    return candidate


def _assert_no_private_fields(value: Any, path: str = "artifact") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "ranking_semantics":
                continue
            if _LEAK.search(str(key)):
                raise ArtifactError("artifact contains prohibited private field(s)")
            _assert_no_private_fields(child, "%s.%s" % (path, key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_no_private_fields(child, "%s[%d]" % (path, index))
    elif isinstance(value, str) and _LEAK.search(value):
        raise ArtifactError("artifact contains prohibited private value(s)")


def verify_artifact(path: Path) -> Dict[str, Any]:
    """Verify manifest shape, digest, and optional serialized model bytes."""

    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError("cannot read artifact manifest") from exc
    if not isinstance(document, dict):
        raise ArtifactError("artifact manifest must be an object")
    _assert_no_private_fields(document)
    required = ("artifact_version", "feature_schema_version", "method", "source_manifest_hash", "artifact_sha256")
    missing = [key for key in required if key not in document]
    if missing:
        raise ArtifactError("artifact manifest missing %s" % ", ".join(missing))
    if document["artifact_version"] != ARTIFACT_VERSION or document["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
        raise ArtifactError("unsupported artifact or feature schema version")
    digest = document.get("artifact_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest) or manifest_digest(document) != digest:
        raise ArtifactError("artifact manifest digest mismatch")
    source_hash = document["source_manifest_hash"]
    if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
        raise ArtifactError("source manifest hash is required")
    if document["method"] not in {"rules", "isolation_forest"}:
        raise ArtifactError("unsupported ranking method")
    model_path = document.get("model_path")
    if document["method"] == "isolation_forest":
        if not isinstance(model_path, str):
            raise ArtifactError("model path is required for an Isolation Forest artifact")
        model_file = _safe_artifact_path(path, model_path)
        if not model_file.is_file():
            raise ArtifactError("serialized model is missing")
        model_hash = document.get("model_sha256")
        if not isinstance(model_hash, str) or not _SHA256.fullmatch(model_hash):
            raise ArtifactError("serialized model hash is required")
        actual = hashlib.sha256(model_file.read_bytes()).hexdigest()
        if actual != model_hash:
            raise ArtifactError("serialized model digest mismatch")
    elif model_path is not None:
        raise ArtifactError("rules artifact cannot include model bytes")
    return document


def load_model(path: Path) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Verify and load a model, or return ``None`` for a rules artifact."""

    document = verify_artifact(path)
    if document["method"] == "rules":
        return document, None
    try:
        import joblib

        model_file = _safe_artifact_path(Path(path), document["model_path"])
        model = joblib.load(model_file)
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ArtifactError("serialized model could not be loaded") from exc
    if not hasattr(model, "score_samples"):
        raise ArtifactError("serialized artifact is not a supported ranking model")
    return document, model


def write_artifact(
    output: Path,
    *,
    source_manifest_hash: str,
    source_metadata: Mapping[str, Any],
    method: str,
    training_rows: int,
    validation_rows: int,
    reason: str,
    model: Optional[Any] = None,
) -> Dict[str, Any]:
    """Write a deterministic artifact manifest and optional model bytes."""

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not _SHA256.fullmatch(source_manifest_hash):
        raise ArtifactError("source manifest hash must be SHA-256")
    if method not in {"rules", "isolation_forest"}:
        raise ArtifactError("unsupported artifact method")
    if method == "isolation_forest" and model is None:
        raise ArtifactError("Isolation Forest method requires a fitted model")
    model_path: Optional[str] = None
    model_hash: Optional[str] = None
    if model is not None:
        # Keep weights beside the manifest, in an explicitly generated path.
        model_path = output.stem + ".joblib"
        model_file = output.parent / model_path
        try:
            import joblib

            joblib.dump(model, model_file, compress=3)
        except Exception as exc:  # pragma: no cover - environment failure
            raise ArtifactError("could not serialize ranking model") from exc
        model_hash = hashlib.sha256(model_file.read_bytes()).hexdigest()
    document: Dict[str, Any] = {
        "artifact_version": ARTIFACT_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "method": method,
        "training_rows": int(training_rows),
        "validation_rows": int(validation_rows),
        "selection_reason": reason,
        "source_manifest_hash": source_manifest_hash,
        "source": dict(source_metadata),
        "feature_names": list(FEATURE_NAMES),
        "baseline": {
            "method": "error-rate-latency-rules-v1",
            "error_rate_threshold": ERROR_RATE_THRESHOLD,
            "latency_threshold_ms": LATENCY_THRESHOLD_MS,
        },
        "ranking_semantics": "unusual service/window ranking; not a root-cause probability",
    }
    if model_path is not None:
        document["model_path"] = model_path
        document["model_sha256"] = model_hash
    document["artifact_sha256"] = manifest_digest(document)
    output.write_text(_canonical(document) + "\n", encoding="utf-8")
    verify_artifact(output)
    return document


__all__ = ["ArtifactError", "load_model", "manifest_digest", "verify_artifact", "write_artifact"]
