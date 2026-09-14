"""Public Phase 3 manifest loading and split/sealing policy."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from .ranking import RankingInputError, validate_row


class ManifestPolicyError(ValueError):
    """Raised when a manifest is not safe for Phase 3 development use."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN = re.compile(
    r"(?:root.?cause|ground.?truth|hidden.?label|fault.?type|inject(?:ion)?_?time|"
    r"source.?filename|file.?name|answer|solution|re[123](?:ob|ss|tt)_[a-z0-9_-]+)",
    re.IGNORECASE,
)
_FORBIDDEN_PATH = re.compile(r"(?:final|held.?out|test)", re.IGNORECASE)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def document_hash(document: Mapping[str, Any]) -> str:
    without = dict(document)
    without.pop("manifest_sha256", None)
    # Execution time is provenance, not deterministic content identity.
    without.pop("generated_at", None)
    return hashlib.sha256(canonical_json(without).encode("utf-8")).hexdigest()


def _walk_forbidden(value: Any, path: str = "manifest") -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            # The public audit attestation necessarily names the controls it
            # checked.  It does not contain any hidden values or locators.
            if path.endswith(".leakage_review"):
                continue
            if _FORBIDDEN.search(str(key)):
                yield "%s.%s" % (path, key)
            yield from _walk_forbidden(child, "%s.%s" % (path, key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _walk_forbidden(child, "%s[%d]" % (path, index))
    elif isinstance(value, str) and _FORBIDDEN.search(value):
        yield path


def _read(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if _FORBIDDEN_PATH.search(path.name):
        raise ManifestPolicyError("Phase 3 cannot read a sealed final/test manifest")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestPolicyError("cannot read Phase 3 manifest") from exc
    if not isinstance(document, dict):
        raise ManifestPolicyError("manifest must be an object")
    if document.get("sealed") is True or document.get("split") in {"final_held_out", "test", "held_out"}:
        raise ManifestPolicyError("final held-out manifest is sealed and unavailable to Phase 3")
    forbidden = list(_walk_forbidden(document))
    if forbidden:
        raise ManifestPolicyError("manifest contains prohibited private field(s)")
    return document


def load_manifest(path: Path, expected_split: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Load and validate one train/validation manifest without opening held-out data."""

    document = _read(Path(path))
    if document.get("manifest_version") != "1.0.0":
        raise ManifestPolicyError("unsupported Phase 3 manifest version")
    if document.get("split") != expected_split:
        raise ManifestPolicyError("expected %s manifest" % expected_split)
    if document.get("raw_data_in_repo") is not False:
        raise ManifestPolicyError("raw telemetry cannot be in a public manifest")
    source = document.get("source")
    if not isinstance(source, Mapping) or not source.get("source_version"):
        raise ManifestPolicyError("source version metadata is required")
    rows_value = document.get("rows", [])
    if not isinstance(rows_value, list):
        raise ManifestPolicyError("rows must be a list")
    rows: List[Dict[str, Any]] = []
    ids = set()
    groups = set()
    for raw in rows_value:
        try:
            row = validate_row(raw)
        except RankingInputError as exc:
            raise ManifestPolicyError(str(exc)) from exc
        if row["sample_id"] in ids:
            raise ManifestPolicyError("sample IDs must be unique")
        ids.add(row["sample_id"])
        groups.add(row["run_group"])
        # Public rows can optionally link to a neutral case ID only.
        if "case_id" in raw:
            case_id = raw["case_id"]
            if not isinstance(case_id, str) or not re.fullmatch(r"dev-re2ob-\d{3}", case_id):
                raise ManifestPolicyError("case IDs must be neutral")
            row["case_id"] = case_id
        rows.append(row)
    declared = document.get("row_count")
    if declared is not None and declared != len(rows):
        raise ManifestPolicyError("row_count does not match rows")
    declared_groups = document.get("run_group_count")
    if declared_groups is not None and declared_groups != len(groups):
        raise ManifestPolicyError("run_group_count does not match rows")
    expected_hash = document.get("manifest_sha256")
    if expected_hash is not None:
        if not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash) or document_hash(document) != expected_hash:
            raise ManifestPolicyError("manifest digest mismatch")
    return document, rows


def assert_disjoint_groups(train_rows: Sequence[Mapping[str, Any]], validation_rows: Sequence[Mapping[str, Any]]) -> None:
    training = {row["run_group"] for row in train_rows}
    validation = {row["run_group"] for row in validation_rows}
    overlap = training & validation
    if overlap:
        raise ManifestPolicyError("independent-run groups overlap between training and validation")


def source_hash(document: Mapping[str, Any]) -> str:
    return document_hash(document)


__all__ = [
    "ManifestPolicyError",
    "assert_disjoint_groups",
    "canonical_json",
    "document_hash",
    "load_manifest",
    "source_hash",
]
