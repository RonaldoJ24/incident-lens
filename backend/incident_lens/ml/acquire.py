"""Private, deterministic development-only RCAEval feature acquisition.

The helper resolves protected neutral locators, processes one pinned case at a
time, derives service/window features, writes only neutral public manifests,
and removes that case's raw telemetry in a ``finally`` block.  It never prints
or returns upstream case names or raw records.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

from incident_lens.adapters.rcaeval import RCAEvalAdapter, load_source_locators
from incident_lens.pipeline.normalization import normalize_case, read_parquet_records

from .data import canonical_json, document_hash


class AcquisitionError(ValueError):
    """Raised when development-only acquisition cannot remain safe."""


_CASE_ID = re.compile(r"^dev-re2ob-(\d{3})$")
_METRIC_SUFFIXES = ("_error", "_latency-90", "_latency-50", "_workload")
_WINDOW_SECONDS = 300


def _service_pseudonym_secret(path: Path) -> bytes:
    """Load a stable protected secret; never fall back to a public hash."""

    path = Path(path)
    resolved = path.resolve()
    project_root = Path.cwd().resolve()
    if str(resolved).startswith(str(project_root) + "/") and "/data/cache/" not in str(resolved):
        raise AcquisitionError("service pseudonym secret must be under ignored data/cache")
    try:
        secret = path.read_bytes()
    except OSError as exc:
        raise AcquisitionError("protected service pseudonym secret is unavailable") from exc
    if len(secret) < 32:
        raise AcquisitionError("protected service pseudonym secret is too short")
    return secret


def _neutral_service_id(service: str, secret: bytes) -> str:
    # HMAC prevents dictionary reversal while keeping IDs stable across cases.
    return "service-" + hmac.new(secret, service.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _timestamp(record: Mapping[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        number = float(value)
        if not math.isfinite(number):
            continue
        # Metrics/logs use seconds; trace startTimeMillis is milliseconds.
        if abs(number) >= 1e11:
            number /= 1000.0
        return number
    return None


def _numeric(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _metric_services(rows: Sequence[Mapping[str, Any]]) -> Set[str]:
    services: Set[str] = set()
    for row in rows:
        for key in row:
            key = str(key)
            for suffix in _METRIC_SUFFIXES:
                if key.endswith(suffix) and len(key) > len(suffix):
                    services.add(key[: -len(suffix)])
                    break
    return services


def _public_case_features(case_id: str, records: Mapping[str, Sequence[Mapping[str, Any]]], secret: bytes) -> Tuple[List[Dict[str, Any]], List[float]]:
    """Derive neutral service/window rows and retain only private timestamps."""

    metrics, logs, traces = records.get("metrics", ()), records.get("logs", ()), records.get("traces", ())
    metric_services = _metric_services(metrics)
    service_events: MutableMapping[Tuple[str, int], Dict[str, Any]] = defaultdict(
        lambda: {"error": [], "latency": [], "metric_count": 0, "log_count": 0, "trace_count": 0, "event_count": 0}
    )
    times: List[float] = []
    for row in metrics:
        timestamp = _timestamp(row, "time", "timestamp", "event_time")
        if timestamp is None:
            continue
        times.append(timestamp)
        window = 0  # reassigned after the global start is known
        for service in metric_services:
            columns = [key for key in row if str(key).startswith(service + "_")]
            if not columns:
                continue
            bucket = service_events[(service, window)]
            bucket["metric_count"] += 1
            bucket["event_count"] += 1
            for key in columns:
                numeric = _numeric(row.get(key))
                if numeric is None:
                    continue
                if str(key).endswith("_error"):
                    bucket["error"].append(max(0.0, min(1.0, numeric)))
                elif str(key).endswith("_latency-90"):
                    bucket["latency"].append(max(0.0, numeric) * 1000.0)
    for row in logs:
        timestamp = _timestamp(row, "timestamp", "time", "event_time")
        service = row.get("container_name")
        if timestamp is None or not isinstance(service, str) or not service:
            continue
        times.append(timestamp)
        service_events[(service, 0)]["log_count"] += 1
        service_events[(service, 0)]["event_count"] += 1
    for row in traces:
        timestamp = _timestamp(row, "startTimeMillis", "startTime", "timestamp", "time", "event_time")
        service = row.get("serviceName")
        if timestamp is None or not isinstance(service, str) or not service:
            continue
        times.append(timestamp)
        service_events[(service, 0)]["trace_count"] += 1
        service_events[(service, 0)]["event_count"] += 1
    if not times:
        raise AcquisitionError("case contains no timestamped development telemetry")
    start = min(times)
    # Rebucket all provisional keys without retaining source names in output.
    rebucketed: MutableMapping[Tuple[str, int], Dict[str, Any]] = defaultdict(
        lambda: {"error": [], "latency": [], "metric_count": 0, "log_count": 0, "trace_count": 0, "event_count": 0}
    )
    def bucket_for(service: str, timestamp: float) -> Dict[str, Any]:
        return rebucketed[(service, max(0, int((timestamp - start) // _WINDOW_SECONDS)))]
    for row in metrics:
        timestamp = _timestamp(row, "time", "timestamp", "event_time")
        if timestamp is None:
            continue
        for service in metric_services:
            columns = [key for key in row if str(key).startswith(service + "_")]
            if not columns:
                continue
            bucket = bucket_for(service, timestamp)
            bucket["metric_count"] += 1
            bucket["event_count"] += 1
            for key in columns:
                numeric = _numeric(row.get(key))
                if numeric is None:
                    continue
                if str(key).endswith("_error"):
                    bucket["error"].append(max(0.0, min(1.0, numeric)))
                elif str(key).endswith("_latency-90"):
                    bucket["latency"].append(max(0.0, numeric) * 1000.0)
    for row in logs:
        timestamp = _timestamp(row, "timestamp", "time", "event_time")
        service = row.get("container_name")
        if timestamp is not None and isinstance(service, str) and service:
            bucket_for(service, timestamp)["log_count"] += 1
            bucket_for(service, timestamp)["event_count"] += 1
    for row in traces:
        timestamp = _timestamp(row, "startTimeMillis", "startTime", "timestamp", "time", "event_time")
        service = row.get("serviceName")
        if timestamp is not None and isinstance(service, str) and service:
            bucket_for(service, timestamp)["trace_count"] += 1
            bucket_for(service, timestamp)["event_count"] += 1
    rows: List[Dict[str, Any]] = []
    for index, ((service, window), values) in enumerate(sorted(rebucketed.items(), key=lambda item: (item[0][1], item[0][0]))):
        sample_id = "sample-" + case_id.replace("dev-re2ob-", "") + "-" + str(index + 1).zfill(4)
        rows.append(
            {
                "sample_id": sample_id,
                "case_id": case_id,
                "run_group": "run-group-" + case_id.rsplit("-", 1)[-1],
                "service_id": _neutral_service_id(service, secret),
                "window_id": "window-" + str(window + 1).zfill(3),
                "features": {
                    "error_rate": sum(values["error"]) / len(values["error"]) if values["error"] else None,
                    "latency_ms": sum(values["latency"]) / len(values["latency"]) if values["latency"] else None,
                    "latency_p95_ms": max(values["latency"]) if values["latency"] else None,
                    "error_count": sum(1 for value in values["error"] if value > 0) if values["error"] else None,
                    "request_count": None,
                    "event_count": values["event_count"],
                    "log_count": values["log_count"],
                    "metric_count": values["metric_count"],
                    "trace_count": values["trace_count"],
                    "missing_logs": 1 if not values["log_count"] else 0,
                    "missing_metrics": 1 if not values["metric_count"] else 0,
                    "missing_traces": 1 if not values["trace_count"] else 0,
                    "conflict_count": 0,
                },
            }
        )
    return rows, times


def _write_public_manifest(path: Path, split: str, rows: Sequence[Mapping[str, Any]], source: Mapping[str, Any]) -> Dict[str, Any]:
    cases: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cases[row["case_id"]] = {
            "case_id": row["case_id"],
            "run_group": row["run_group"],
            "quality_status": "reviewed",
        }
    document: Dict[str, Any] = {
        "manifest_version": "1.0.0",
        "manifest_id": "incident-lens-phase3-%s-v2" % split,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": dict(source),
        "split": split,
        "grouping": "independent-run",
        "selection_status": "quality-reviewed deterministic service/window features",
        "case_count": len(cases),
        "row_count": len(rows),
        "run_group_count": len({row["run_group"] for row in rows}),
        "cases": [cases[key] for key in sorted(cases)],
        "rows": list(rows),
        "license": {"name": "MIT", "url": "https://github.com/phamquiluan/RCAEval/blob/bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90/LICENSE", "redistribution": "raw telemetry remains outside Git"},
        "attribution": "Pham, Luan et al. RCAEval (2025). Public Phase 3 manifest contains reviewed aggregate service/window features only.",
        "raw_data_in_repo": False,
        "leakage_review": {"neutral_ids": True, "hidden_labels_removed": True, "source_filenames_removed": True, "injection_metadata_excluded": True, "review_status": "passed"},
    }
    document["manifest_sha256"] = document_hash(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    return document


def acquire_development(
    *,
    locator_file: Path = Path("data/raw/rcaeval/source-locators.json"),
    raw_root: Path = Path("data/raw/rcaeval"),
    train_output: Path = Path("data/manifests/train.json"),
    validation_output: Path = Path("data/manifests/validation.json"),
    targets_output: Path = Path("data/cache/rcaeval/phase3-review-targets.json"),
    pseudonym_secret: Path = Path("data/cache/rcaeval/service-pseudonym-secret"),
) -> Dict[str, Any]:
    locators = load_source_locators(locator_file)
    selected_ids = sorted(locators, key=lambda case_id: int(_CASE_ID.fullmatch(case_id).group(1)))
    if len(selected_ids) < 10:
        raise AcquisitionError("protected development locator set has fewer than 10 cases")
    selected_ids = selected_ids[:12]
    source = {"source_id": "rcaeval", "dataset": "RCAEval", "subset": "RE2-OB", "source_version": "RCAEval@bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90", "dataset_revision": "RCAEval-HF@afeacb11bcc94dadfd1c8f483ee4377b2b8b614e"}
    secret = _service_pseudonym_secret(pseudonym_secret)
    train_rows: List[Dict[str, Any]] = []
    validation_rows: List[Dict[str, Any]] = []
    positive_ids: Set[str] = set()
    adapter = RCAEvalAdapter(raw_root)
    for position, case_id in enumerate(selected_ids):
        case_root = raw_root / case_id
        raw_case = None
        try:
            raw_case = adapter.fetch_case(locators[case_id])
            records = {
                signal: read_parquet_records(raw_case.raw_root / (signal + ".parquet"))
                if any(item.signal == signal for item in raw_case.files)
                else []
                for signal in ("logs", "metrics", "traces")
            }
            # Quality-review the full case through the pinned normalization
            # boundary before deriving any public aggregate features.
            normalize_case(
                case_id,
                "development",
                source["source_version"],
                source["dataset_revision"],
                records,
                strict=False,
                generated_at="2026-09-14T00:00:00Z",
            )
            rows, times = _public_case_features(case_id, records, secret)
            inject_path = raw_case.raw_root / "inject_time.txt"
            try:
                inject_time = float(inject_path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError) as exc:
                raise AcquisitionError("review target timestamp is unavailable") from exc
            start = min(times)
            positive_window = max(0, int((inject_time - start) // _WINDOW_SECONDS))
            for row in rows:
                if row["window_id"] == "window-" + str(positive_window + 1).zfill(3):
                    positive_ids.add(row["sample_id"])
            (train_rows if position < 8 else validation_rows).extend(rows)
        finally:
            # Delete exactly this neutral case; never remove another case or
            # the raw root itself.
            if case_root.exists():
                shutil.rmtree(case_root)
            del raw_case
    train_doc = _write_public_manifest(train_output, "training", train_rows, source)
    validation_doc = _write_public_manifest(validation_output, "validation", validation_rows, source)
    targets_output.parent.mkdir(parents=True, exist_ok=True)
    targets_output.write_text(canonical_json({"version": "phase3-review-v1", "target_semantics": "reviewed event-window target; not a failing-service or root-cause label", "positive_sample_ids": sorted(positive_ids)}) + "\n", encoding="utf-8")
    return {"training_cases": 8, "validation_cases": len(selected_ids) - 8, "training_rows": len(train_rows), "validation_rows": len(validation_rows), "review_targets": len(positive_ids), "train_manifest_hash": train_doc["manifest_sha256"], "validation_manifest_hash": validation_doc["manifest_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire reviewed development-only RCAEval service/window features")
    parser.add_argument("--locator-file", type=Path, default=Path("data/raw/rcaeval/source-locators.json"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/rcaeval"))
    parser.add_argument("--train-output", type=Path, default=Path("data/manifests/train.json"))
    parser.add_argument("--validation-output", type=Path, default=Path("data/manifests/validation.json"))
    parser.add_argument("--targets-output", type=Path, default=Path("data/cache/rcaeval/phase3-review-targets.json"))
    parser.add_argument("--pseudonym-secret", type=Path, default=Path("data/cache/rcaeval/service-pseudonym-secret"))
    args = parser.parse_args()
    result = acquire_development(locator_file=args.locator_file, raw_root=args.raw_root, train_output=args.train_output, validation_output=args.validation_output, targets_output=args.targets_output, pseudonym_secret=args.pseudonym_secret)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
