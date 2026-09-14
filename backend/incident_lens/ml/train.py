"""Deterministic Phase 3 training CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifacts import write_artifact
from .data import ManifestPolicyError, assert_disjoint_groups, load_manifest, source_hash
from .metrics import better_model, ranking_metrics
from .ranking import feature_vector, rank_rows
from .targets import ReviewTargetError, load_review_targets


MIN_TRAIN_GROUPS = 8
MIN_VALIDATION_GROUPS = 2


def fit_from_manifest(manifest_path: Path, validation_path: Optional[Path] = None, output_path: Optional[Path] = None, review_targets_path: Optional[Path] = None) -> Dict[str, Any]:
    document, rows = load_manifest(Path(manifest_path), "training")
    validation_rows: List[Dict[str, Any]] = []
    if validation_path is not None:
        _, validation_rows = load_manifest(Path(validation_path), "validation")
        assert_disjoint_groups(rows, validation_rows)
    train_groups = {row["run_group"] for row in rows}
    validation_groups = {row["run_group"] for row in validation_rows}
    # Fit a candidate only after the independent-group gate.  Selection still
    # requires private reviewer targets; without them the rules remain chosen.
    model = None
    candidate_model = None
    method = "rules"
    selection_metrics: Dict[str, Any] = {"status": "not measured", "target_semantics": "reviewed event-window target; not a failing-service or root-cause label", "candidate_training_rows": 0, "candidate_training_groups": 0}
    reason = "not measured: independent training/validation group gate or reviewer targets unavailable; rules retained"
    if len(train_groups) >= MIN_TRAIN_GROUPS and len(validation_groups) >= MIN_VALIDATION_GROUPS and validation_rows:
        try:
            from sklearn.ensemble import IsolationForest

            candidate_model = IsolationForest(
                n_estimators=100,
                contamination="auto",
                random_state=42,
                n_jobs=1,
            )
            candidate_model.fit([feature_vector(row) for row in rows])
            targets = load_review_targets(review_targets_path)
            if targets:
                candidate_metrics = ranking_metrics(rank_rows(validation_rows, candidate_model), targets)
                baseline_metrics = ranking_metrics(rank_rows(validation_rows), targets)
                selected = "isolation_forest" if better_model(candidate_metrics, baseline_metrics) else "rules"
                if selected == "isolation_forest":
                    model = candidate_model
                    method = selected
                    reason = "Isolation Forest strictly improved event-window validation ranking over rules"
                else:
                    reason = "rules strictly matched or exceeded Isolation Forest on event-window validation evidence"
                selection_metrics = {
                    "status": "measured",
                    "target_semantics": "reviewed event-window target; not a failing-service or root-cause label",
                    "candidate_training_rows": len(rows),
                    "candidate_training_groups": len(train_groups),
                    "selected": selected,
                    "isolation_forest": candidate_metrics,
                    "rules": baseline_metrics,
                }
            else:
                reason = "candidate fitted on training only, but reviewer targets unavailable; rules retained"
        except ReviewTargetError:
            raise
        except ImportError as exc:  # pragma: no cover - dependency check
            raise RuntimeError("scikit-learn is required for the Phase 3 training CLI") from exc
    if output_path is None:
        output_path = Path("artifacts/model-manifest.json")
    result = write_artifact(
        Path(output_path),
        source_manifest_hash=source_hash(document),
        source_metadata=document["source"],
        method=method,
        training_rows=len(rows),
        validation_rows=len(validation_rows),
        reason=reason,
        model=model,
        selection_metrics=selection_metrics,
    )
    result["training_manifest"] = str(Path(manifest_path))
    result["validation_manifest"] = str(Path(validation_path)) if validation_path else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the deterministic unusual service/window ranker")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--validation-manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/model-manifest.json"))
    parser.add_argument("--review-targets", type=Path)
    args = parser.parse_args()
    try:
        document = fit_from_manifest(args.manifest, args.validation_manifest, args.output, args.review_targets)
    except (ManifestPolicyError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print("trained %s artifact: method=%s training_rows=%d validation_rows=%d" % (args.output, document["method"], document["training_rows"], document["validation_rows"]))


if __name__ == "__main__":
    main()
