"""Offline normalization CLI.

The command intentionally reads raw telemetry only from an ignored directory.
It never accepts an upstream source path on the command line and never loads
the hidden injection-time file into a manifest or prompt-facing result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

from incident_lens.pipeline.normalization import NormalizationError, normalize_case, read_parquet_records, write_manifest


def _load_manifest(path: Path) -> Mapping[str, object]:
    if not path.exists() and path.name == "dev.json":
        # The plan's short command remains convenient without maintaining a
        # duplicate public manifest that could drift from development.json.
        path = path.with_name("development.json")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NormalizationError("cannot read selection manifest") from exc
    if not isinstance(document, dict) or document.get("split") != "development":
        raise NormalizationError("normalization accepts a development manifest only")
    return document


def _case_ids(document: Mapping[str, object], requested: Optional[str]) -> List[str]:
    values = document.get("cases", [])
    if not isinstance(values, list):
        raise NormalizationError("manifest cases must be a list")
    selected = [str(item["case_id"]) for item in values if isinstance(item, dict) and item.get("case_id")]
    if requested:
        if requested not in selected:
            raise NormalizationError("requested case is not selected in the public manifest")
        return [requested]
    return selected


def normalize_manifest(
    manifest_path: Path,
    *,
    raw_root: Path = Path("data/raw/rcaeval"),
    output_root: Path = Path("data/derived"),
    case_id: Optional[str] = None,
) -> List[Path]:
    """Normalize available neutral cases and return generated manifest paths.

    Cases selected in the public manifest but not fetched are reported as
    skipped, never synthesized.  This makes a partial offline run honest.
    """

    document = _load_manifest(manifest_path)
    source = document.get("source")
    if not isinstance(source, dict):
        raise NormalizationError("manifest source metadata is required")
    source_version = str(source.get("source_version", ""))
    dataset_revision = str(source.get("dataset_revision", ""))
    if not source_version or not dataset_revision:
        raise NormalizationError("manifest source revisions are required")
    result: List[Path] = []
    for selected_id in _case_ids(document, case_id):
        case_root = raw_root / selected_id
        if not case_root.is_dir():
            if case_id:
                raise NormalizationError("raw telemetry for %s has not been fetched" % selected_id)
            continue
        records_by_signal: Dict[str, Iterable[Mapping[str, object]]] = {}
        for signal in ("logs", "metrics", "traces"):
            parquet_path = case_root / (signal + ".parquet")
            records_by_signal[signal] = read_parquet_records(parquet_path) if parquet_path.exists() else ()
        normalized = normalize_case(
            selected_id,
            "development",
            source_version,
            dataset_revision,
            records_by_signal,
            strict=False,
        )
        destination = output_root / "manifests" / "development" / (selected_id + ".json")
        write_manifest(normalized, destination)
        result.append(destination)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize fetched RCAEval cases offline")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/rcaeval"))
    parser.add_argument("--output-root", type=Path, default=Path("data/derived"))
    args = parser.parse_args()
    paths = normalize_manifest(args.manifest, raw_root=args.raw_root, output_root=args.output_root, case_id=args.case_id)
    print("normalized %d case(s)" % len(paths))


if __name__ == "__main__":
    main()
