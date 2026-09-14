"""Leakage and split checks for public selection/derived manifests."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from incident_lens.pipeline.normalization import LeakageError, assert_no_leakage
from incident_lens.validation.manifests import ManifestError, validate_manifest


class LeakageCheckError(ManifestError):
    """Raised when a public manifest could disclose benchmark answers."""


_UPSTREAM_CASE = re.compile(r"(?:re[123](?:ob|ss|tt)_[a-z0-9-]+_(?:cpu|mem|disk|delay|loss|socket|f[1-5])_\d+)", re.IGNORECASE)
_RAW_PATH = re.compile(r"(?:data/raw|rawdata|\.parquet(?:/|$)|inject_time)", re.IGNORECASE)


def _walk(value: Any, path: str = "manifest") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, "%s.%s" % (path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, "%s[%d]" % (path, index))


def check_public_manifest(path: Path) -> Dict[str, Any]:
    """Validate one public manifest without exposing offending content."""

    document = validate_manifest(path)
    try:
        cases = document.get("cases", [])
        rows = document.get("rows", [])
        for location, value in _walk(cases, "cases"):
            if isinstance(value, str) and (_UPSTREAM_CASE.search(value) or _RAW_PATH.search(value)):
                raise LeakageCheckError("source locator or raw path leakage at %s" % location)
        for location, value in _walk(rows, "rows"):
            if isinstance(value, str) and (_UPSTREAM_CASE.search(value) or _RAW_PATH.search(value)):
                raise LeakageCheckError("source locator or raw path leakage at %s" % location)
        assert_no_leakage(cases)
        assert_no_leakage(rows)
        if document.get("case_id") is not None:
            case_id = document.get("case_id")
            if not isinstance(case_id, str) or not re.fullmatch(r"dev-re2ob-\d{3}", case_id):
                raise LeakageCheckError("derived case ID must be neutral")
            if document.get("split") != "development":
                raise LeakageCheckError("derived case is outside the development split")
            # The review metadata intentionally says that hidden fields were
            # removed; inspect all other fields for accidental leakage.
            assert_no_leakage({key: value for key, value in document.items() if key != "leakage_review"})
    except LeakageError as exc:
        raise LeakageCheckError(str(exc)) from exc
    split = document.get("split")
    if split == "development":
        for case in cases:
            if isinstance(case, Mapping) and case.get("split") not in (None, split):
                raise LeakageCheckError("case %s is outside manifest split" % case.get("case_id", "unknown"))
    return document


def check_directory(directory: Path) -> List[Path]:
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise LeakageCheckError("no manifests found")
    for path in paths:
        check_public_manifest(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Incident Lens manifest leakage and split isolation")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    paths = [args.path] if args.path.is_file() else check_directory(args.path)
    print("checked %d manifest(s)" % len(paths))


if __name__ == "__main__":
    main()
