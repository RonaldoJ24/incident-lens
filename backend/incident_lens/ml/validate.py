"""Validation and aggregate error analysis for Phase 3."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .artifacts import ArtifactError, load_model
from .data import ManifestPolicyError, assert_disjoint_groups, load_manifest, source_hash
from .metrics import ranking_metrics
from .ranking import RANKING_SEMANTICS, rank_rows
from .targets import ReviewTargetError, load_review_targets


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_manifest(
    manifest_path: Path,
    artifact_path: Path,
    *,
    train_manifest_path: Optional[Path] = None,
    report_path: Optional[Path] = None,
    review_targets_path: Optional[Path] = None,
) -> Dict[str, Any]:
    document, rows = load_manifest(Path(manifest_path), "validation")
    if train_manifest_path is None:
        candidate = Path(manifest_path).with_name("train.json")
        train_manifest_path = candidate if candidate.exists() else None
    train_document: Optional[Mapping[str, Any]] = None
    train_rows: List[Dict[str, Any]] = []
    if train_manifest_path is not None:
        train_document, train_rows = load_manifest(Path(train_manifest_path), "training")
        assert_disjoint_groups(train_rows, rows)
    artifact, model = load_model(Path(artifact_path))
    model_rank = rank_rows(rows, model)
    baseline_rank = rank_rows(rows)
    targets = load_review_targets(review_targets_path) if review_targets_path is not None else load_review_targets()
    selected_metrics = ranking_metrics(model_rank, targets) if targets is not None else None
    baseline_metrics = ranking_metrics(baseline_rank, targets) if targets is not None else None
    missing = Counter()
    conflict_count = 0
    for row in rows:
        features = row["features"]
        for signal in ("logs", "metrics", "traces"):
            if features["missing_" + signal] is not None and features["missing_" + signal] >= 1:
                missing[signal] += 1
        if features["conflict_count"] is not None and features["conflict_count"] > 0:
            conflict_count += 1
    known_services = {row["service_id"] for row in train_rows}
    unseen_services = sorted({row["service_id"] for row in rows if row["service_id"] not in known_services}) if train_rows else []
    model_method = artifact["method"]
    comparison_status = "not measured"
    comparison_reason = (
        "No public event target is present; false alarms and ranking quality remain not measured. "
        "The rules baseline remains the honest comparison."
    )
    if model_method == "isolation_forest":
        comparison_reason = "Model scores and rule scores are emitted for comparison; no target labels were opened."
    if selected_metrics is not None:
        comparison_status = "measured"
        comparison_reason = "Private reviewer targets identify event windows only; they do not identify a failing service or root cause."
    model_scores = [item["unusual_score"] for item in model_rank]
    baseline_scores = [item["unusual_score"] for item in baseline_rank]
    report: Dict[str, Any] = {
        "report_version": "incident-lens-phase3-evaluation-v1",
        "status": "not_measured" if not rows else "measured_without_targets",
        "ranking_semantics": RANKING_SEMANTICS,
        "split": "validation",
        "case_counts": {
            "training_rows": len(train_rows),
            "validation_rows": len(rows),
            "training_cases": len({row.get("case_id") for row in train_rows if row.get("case_id")}),
            "validation_cases": len({row.get("case_id") for row in rows if row.get("case_id")}),
            "independent_training_groups": len({row["run_group"] for row in train_rows}),
            "independent_validation_groups": len({row["run_group"] for row in rows}),
        },
        "workload": {"validation_rows": len(rows), "runtime": "not measured"},
        "versions": {
            "artifact_version": artifact["artifact_version"],
            "feature_schema_version": artifact["feature_schema_version"],
            "source": artifact.get("source", {}),
            "artifact_sha256": artifact["artifact_sha256"],
            "validation_manifest_sha256": source_hash(document),
        },
        "metrics": {
            "event_detection": "not measured",
            "false_alarm_rate": "not measured",
            "ranking": {"event_window_ndcg_at_5": "not measured", "event_window_mrr": "not measured"},
            "anomaly": {
                "event_detection": "not measured",
                "false_alarm_rate": "not measured",
                "ranking": {"event_window_ndcg_at_5": "not measured", "event_window_mrr": "not measured"},
            },
            "complete_investigation": {
                "failing_service_identification": "not measured",
                "useful_next_check": "not measured",
                "evidence_support": "not measured",
                "uncertainty_under_missing_or_conflicting_signals": "not measured",
            },
        },
        "comparison": {
            "model": model_method,
            "error_rate_latency_rules": "error-rate-latency-rules-v1",
            "status": comparison_status,
            "rationale": comparison_reason,
            "model_rank_count": len(model_rank),
            "baseline_rank_count": len(baseline_rank),
            "score_summary": {
                "model_mean": round(sum(model_scores) / len(model_scores), 12) if model_scores else "not measured",
                "rules_mean": round(sum(baseline_scores) / len(baseline_scores), 12) if baseline_scores else "not measured",
                "score_disagreement_count": sum(
                    1
                    for model_item, baseline_item in zip(model_rank, baseline_rank)
                    if model_item["sample_id"] != baseline_item["sample_id"]
                )
                if rows
                else "not measured",
            },
        },
        "error_analysis": {
            "false_alarms": selected_metrics["event_detection"]["false_positive"] if selected_metrics and selected_metrics.get("status") == "measured" else "not measured: no reviewed event-window targets",
            "missing_signals": dict(sorted(missing.items())),
            "conflicting_signals": conflict_count,
            "unseen_services": len(unseen_services),
            "unseen_service_ids": unseen_services,
            "insufficient_evidence": sum(1 for row in rows if not any(row["features"].get(name) is not None for name in ("error_rate", "latency_ms", "latency_p95_ms"))),
        },
        "limitations": [
            "Public manifests intentionally contain no hidden labels, source filenames, injection times, or per-case ground truth.",
            "Reviewer targets identify event windows only; failing-service identification and root-cause quality are not measured.",
            "Final held-out data is sealed and was not opened by this phase.",
            "Complete-investigation quality and statistical significance are not measured.",
        ],
    }
    if train_document is not None:
        report["versions"]["train_manifest_sha256"] = source_hash(train_document)
    if selected_metrics is not None and selected_metrics.get("status") == "measured":
        report["status"] = "measured_event_window_only"
        report["metrics"]["event_detection"] = selected_metrics["event_detection"]
        report["metrics"]["false_alarm_rate"] = selected_metrics["false_alarm_rate"]
        report["metrics"]["ranking"] = selected_metrics["ranking"]
        report["metrics"]["anomaly"] = {
            "event_detection": selected_metrics["event_detection"],
            "false_alarm_rate": selected_metrics["false_alarm_rate"],
            "ranking": selected_metrics["ranking"],
        }
        report["comparison"]["model_metrics"] = selected_metrics if model_method == "isolation_forest" else baseline_metrics
        report["comparison"]["selected_method_metrics"] = selected_metrics
        report["comparison"]["rules_metrics"] = baseline_metrics
        if artifact.get("selection_metrics") is not None:
            report["comparison"]["selection_metrics"] = artifact["selection_metrics"]
        report["comparison"]["target_semantics"] = "reviewed event-window target; not a failing-service or root-cause label"
    elif artifact.get("selection_metrics") is not None:
        report["comparison"]["selection_metrics"] = artifact["selection_metrics"]
    if report_path is not None:
        _write_report(Path(report_path), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and report on unusual service/window rankings")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, default=Path("docs/evaluation/phase3-artifact-manifest.json"))
    parser.add_argument("--train-manifest", type=Path)
    parser.add_argument("--report", type=Path, default=Path("reports/generated/phase3-validation.json"))
    parser.add_argument("--review-targets", type=Path)
    args = parser.parse_args()
    try:
        report = validate_manifest(args.manifest, args.artifact, train_manifest_path=args.train_manifest, report_path=args.report, review_targets_path=args.review_targets)
    except (ManifestPolicyError, ArtifactError, ReviewTargetError, ValueError) as exc:
        parser.error(str(exc))
    print("validated %s: status=%s rows=%d report=%s" % (args.manifest, report["status"], report["case_counts"]["validation_rows"], args.report))


if __name__ == "__main__":
    main()
