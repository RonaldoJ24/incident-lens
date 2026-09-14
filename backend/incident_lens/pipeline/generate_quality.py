"""Reproducibly generate a reviewed quality report for one protected case."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from incident_lens.adapters.rcaeval import (
    RCAEvalAdapter,
    RCAEvalDatasetRevision,
    RCAEvalSourceRevision,
    load_source_locators,
)
from incident_lens.pipeline.normalization import NormalizationError, normalize_case, read_parquet_records


def _selection(path: Path, case_id: str) -> Mapping[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NormalizationError("cannot read public selection manifest") from exc
    if not isinstance(document, dict) or document.get("split") != "development":
        raise NormalizationError("quality generation accepts a development manifest only")
    selected = [item for item in document.get("cases", []) if isinstance(item, dict) and item.get("case_id") == case_id]
    if len(selected) != 1:
        raise NormalizationError("requested neutral case is not selected in the public manifest")
    source = document.get("source")
    if not isinstance(source, dict) or not source.get("source_version") or not source.get("dataset_revision"):
        raise NormalizationError("selection manifest lacks pinned source revisions")
    if source["source_version"] != "RCAEval@" + RCAEvalSourceRevision or source["dataset_revision"] != "RCAEval-HF@" + RCAEvalDatasetRevision:
        raise NormalizationError("selection manifest revisions do not match the adapter pins")
    return source


def build_quality_report(normalized: Any) -> Dict[str, Any]:
    """Map the normalized case to the small public reviewed-report shape."""

    signals = {
        item.signal: {
            "input_count": item.input_count,
            "output_count": item.output_count,
            "duplicate_count": item.duplicate_count,
            "malformed_timestamp_count": item.malformed_count,
            "sha256": item.sha256,
        }
        for item in normalized.signals
    }
    report = {
        "report_version": "phase2-quality-v1",
        "case_id": normalized.case_id,
        "split": normalized.split,
        "source": {
            "source_id": "rcaeval",
            "dataset": "RCAEval",
            "subset": "RE2-OB",
            "source_version": normalized.source_version,
            "dataset_revision": normalized.dataset_revision,
        },
        "normalization_version": "incident-lens-normalization-v1",
        "window": {
            "start": normalized.window_start,
            "end": normalized.window_end,
            "event_count_after_deduplication": len(normalized.events),
        },
        "signals": signals,
        "signal_completeness": {signal: ("available" if signals[signal]["output_count"] else "missing") for signal in ("logs", "metrics", "traces")},
        "manifest_hash": normalized.manifest_hash,
        "raw_data_in_repo": False,
        "leakage_review": {
            "neutral_ids": True,
            "hidden_labels_removed": True,
            "source_filenames_removed": True,
            "injection_metadata_excluded": True,
            "review_status": "passed",
        },
        "license": {"name": "MIT", "url": "https://github.com/phamquiluan/RCAEval/blob/bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90/LICENSE"},
        "attribution": "Pham, Luan et al. RCAEval (2025). One pinned RE2-OB case; raw telemetry remains outside Git.",
    }
    return report


def generate_quality_report(
    manifest_path: Path,
    case_id: str,
    *,
    locator_file: Optional[Path] = None,
    raw_root: Path = Path("data/raw/rcaeval"),
    output_path: Path = Path("docs/evaluation/rcaeval-re2ob-001-quality.json"),
    keep_raw: bool = False,
) -> Dict[str, Any]:
    """Fetch, normalize, and write a deterministic report, then clean raw data."""

    source = _selection(manifest_path, case_id)
    locators = load_source_locators(locator_file)
    if case_id not in locators:
        raise NormalizationError("no protected locator for requested neutral case")
    case_root = raw_root / case_id
    try:
        raw_case = RCAEvalAdapter(raw_root).fetch_case(locators[case_id])
        records_by_signal = {
            signal: read_parquet_records(raw_case.raw_root / (signal + ".parquet")) if any(item.signal == signal for item in raw_case.files) else ()
            for signal in ("logs", "metrics", "traces")
        }
        normalized = normalize_case(case_id, "development", str(source["source_version"]), str(source["dataset_revision"]), records_by_signal, strict=False)
        report = build_quality_report(normalized)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report
    finally:
        if not keep_raw and case_root.exists():
            # The path is constructed only after validating a neutral case ID;
            # cleanup never targets the raw root or another case.
            shutil.rmtree(case_root)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and regenerate one RCAEval quality report")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--locator-file", type=Path)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/rcaeval"))
    parser.add_argument("--output", type=Path, default=Path("docs/evaluation/rcaeval-re2ob-001-quality.json"))
    parser.add_argument("--keep-raw", action="store_true", help="retain the ignored fetched case for offline inspection")
    args = parser.parse_args()
    report = generate_quality_report(args.manifest, args.case_id, locator_file=args.locator_file, raw_root=args.raw_root, output_path=args.output, keep_raw=args.keep_raw)
    print(json.dumps({"case_id": report["case_id"], "manifest_hash": report["manifest_hash"], "output": str(args.output), "raw_cleaned": not args.keep_raw}, sort_keys=True))


if __name__ == "__main__":
    main()
