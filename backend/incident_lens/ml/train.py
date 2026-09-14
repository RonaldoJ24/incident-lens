"""Deterministic Phase 3 training CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifacts import write_artifact
from .data import ManifestPolicyError, assert_disjoint_groups, load_manifest, source_hash
from .ranking import feature_vector


MIN_TRAIN_ROWS = 8


def fit_from_manifest(manifest_path: Path, validation_path: Optional[Path] = None, output_path: Optional[Path] = None) -> Dict[str, Any]:
    document, rows = load_manifest(Path(manifest_path), "training")
    validation_rows: List[Dict[str, Any]] = []
    if validation_path is not None:
        _, validation_rows = load_manifest(Path(validation_path), "validation")
        assert_disjoint_groups(rows, validation_rows)
    # An unsupervised model with fewer than eight independent windows is not
    # evidence for model selection.  Keep the explicit rules baseline instead.
    model = None
    method = "rules"
    reason = "not measured: fewer than %d independent training windows or no validation windows" % MIN_TRAIN_ROWS
    if len(rows) >= MIN_TRAIN_ROWS and validation_rows:
        try:
            from sklearn.ensemble import IsolationForest

            model = IsolationForest(
                n_estimators=100,
                contamination="auto",
                random_state=42,
                n_jobs=1,
            )
            model.fit([feature_vector(row) for row in rows])
            method = "isolation_forest"
            reason = "candidate fit is deterministic; validation must still justify retaining it"
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
    )
    result["training_manifest"] = str(Path(manifest_path))
    result["validation_manifest"] = str(Path(validation_path)) if validation_path else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the deterministic unusual service/window ranker")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--validation-manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/model-manifest.json"))
    args = parser.parse_args()
    try:
        document = fit_from_manifest(args.manifest, args.validation_manifest, args.output)
    except (ManifestPolicyError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print("trained %s artifact: method=%s training_rows=%d validation_rows=%d" % (args.output, document["method"], document["training_rows"], document["validation_rows"]))


if __name__ == "__main__":
    main()
