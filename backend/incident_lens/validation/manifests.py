"""Validation for audited, neutral manifests with no raw telemetry."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


class ManifestError(ValueError):
    """Raised when a manifest is not safe to use for selection or evaluation."""


_SPLITS = {"development", "public_demo", "controlled_failure", "validation", "training", "final_held_out"}
_NEUTRAL_CASE_ID = re.compile(r"^dev-re2ob-\d{3}$")
_LEAK_KEYS = re.compile(r"(?:root.?cause|ground.?truth|hidden.?label|filename|file.?name|answer|solution|fault.?type|inject(?:ion)?_?time|source.?case)", re.I)
_LEAK_TEXT = re.compile(r"(?:root.?cause|ground.?truth|hidden.?label|fault.?type|inject(?:ion)?_?time|/root_cause\.txt)", re.I)


def _timestamp(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise ManifestError("%s must be an ISO-8601 timestamp" % label)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError("%s must be an ISO-8601 timestamp" % label) from exc


def _walk_for_leakage(value: Any, path: str = "manifest") -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if _LEAK_KEYS.search(str(key)):
                yield "%s.%s" % (path, key)
            yield from _walk_for_leakage(child, "%s.%s" % (path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_for_leakage(child, "%s[%d]" % (path, index))
    elif isinstance(value, str) and _LEAK_TEXT.search(value):
        yield path


def validate_manifest(path: Path) -> Dict[str, Any]:
    """Validate a manifest and return parsed data.

    Source audit manifests may have no case list. Development manifests must
    use neutral IDs and carry completeness notes for every selected case.
    """

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError("cannot read JSON manifest %s" % path) from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest must be an object")
    required = ("manifest_version", "manifest_id", "generated_at", "source", "split", "license", "attribution", "raw_data_in_repo")
    missing = [field for field in required if field not in data]
    if missing:
        raise ManifestError("missing required manifest fields: %s" % ", ".join(missing))
    _timestamp(data["generated_at"], "generated_at")
    if data["split"] not in _SPLITS:
        raise ManifestError("invalid split")
    if data["raw_data_in_repo"] is not False:
        raise ManifestError("raw_data_in_repo must be false")
    if not isinstance(data["license"], dict) or not data["license"].get("name") or not data["license"].get("url"):
        raise ManifestError("license name and URL are required")
    if not isinstance(data["attribution"], str) or not data["attribution"].strip():
        raise ManifestError("attribution is required")
    if not isinstance(data["source"], dict) or not data["source"].get("source_version"):
        raise ManifestError("source_version is required")

    cases = data.get("cases", [])
    if not isinstance(cases, list):
        raise ManifestError("cases must be a list")
    if data["split"] == "development":
        if not 10 <= len(cases) <= 20:
            raise ManifestError("development manifest must select 10–20 cases")
        for case in cases:
            if not isinstance(case, dict):
                raise ManifestError("each case must be an object")
            for field in ("case_id", "audited_at", "source_version", "signal_completeness", "interval_status"):
                if field not in case:
                    raise ManifestError("case missing %s" % field)
            if not isinstance(case["case_id"], str) or not _NEUTRAL_CASE_ID.fullmatch(case["case_id"]):
                raise ManifestError("case IDs must be neutral dev-re2ob-NNN values")
            _timestamp(case["audited_at"], "case.audited_at")
            completeness = case["signal_completeness"]
            if not isinstance(completeness, dict) or set(completeness) != {"logs", "metrics", "traces"}:
                raise ManifestError("case signal_completeness must list logs, metrics, traces")
            if any(value not in {"available", "missing", "partial", "unknown"} for value in completeness.values()):
                raise ManifestError("invalid signal completeness")
            if case["interval_status"] not in {"pending_per_case_fetch", "audited"}:
                raise ManifestError("invalid interval_status")
        ids = [case["case_id"] for case in cases]
        if len(ids) != len(set(ids)):
            raise ManifestError("case IDs must be unique")
        if data.get("selected_case_count") != len(cases):
            raise ManifestError("selected_case_count does not match cases")
    leakage = list(_walk_for_leakage(data.get("cases", []), "cases"))
    if leakage:
        raise ManifestError("possible hidden-label or filename leakage at %s" % ", ".join(leakage))
    return data


def validate_directory(directory: Path) -> List[Path]:
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ManifestError("no JSON manifests found in %s" % directory)
    for path in paths:
        validate_manifest(path)
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Incident Lens audit manifests")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    paths = [args.path] if args.path.is_file() else validate_directory(args.path)
    if args.path.is_file():
        validate_manifest(args.path)
    print("validated %d manifest(s)" % len(paths))
