import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.ml.artifacts import ArtifactError, verify_artifact
from incident_lens.ml.data import ManifestPolicyError, assert_disjoint_groups, load_manifest
from incident_lens.ml.ranking import RANKING_SEMANTICS, RankingInputError, rank_rows, rule_scores
from incident_lens.ml.serve import RankingService
from incident_lens.ml.train import fit_from_manifest
from incident_lens.ml.validate import validate_manifest


def _row(sample, group, service="service-a", *, latency=100.0, error=0.01):
    return {
        "sample_id": sample,
        "run_group": group,
        "service_id": service,
        "window_id": "window-" + sample,
        "features": {
            "error_rate": error,
            "latency_ms": latency,
            "latency_p95_ms": latency,
            "error_count": 1,
            "request_count": 100,
            "event_count": 10,
            "log_count": 3,
            "metric_count": 4,
            "trace_count": 3,
            "missing_logs": 0,
            "missing_metrics": 0,
            "missing_traces": 0,
            "conflict_count": 0,
        },
    }


def _manifest(path, split, rows):
    document = {
        "manifest_version": "1.0.0",
        "manifest_id": "test-%s" % split,
        "generated_at": "2026-09-14T00:00:00Z",
        "source": {"source_id": "test", "source_version": "test-v1"},
        "split": split,
        "grouping": "independent-run",
        "row_count": len(rows),
        "run_group_count": len({row["run_group"] for row in rows}),
        "rows": rows,
        "license": {"name": "MIT", "url": "https://example.invalid/license"},
        "attribution": "reviewed test fixture",
        "raw_data_in_repo": False,
        "leakage_review": {"hidden_labels_removed": True, "source_filenames_removed": True},
    }
    path.write_text(json.dumps(document), encoding="utf-8")


class Phase3RankingTests(unittest.TestCase):
    def test_rules_are_explicit_and_not_probability(self):
        result = rule_scores(_row("sample-1", "run-1", latency=1000, error=0.2))
        self.assertEqual(result["method"], "error-rate-latency-rules-v1")
        self.assertGreater(result["score"], 0.9)
        self.assertEqual(result["ranking_semantics"], RANKING_SEMANTICS)
        self.assertNotIn("probability", result)

    def test_missing_signals_and_unseen_service_are_explicit(self):
        row = _row("sample-1", "run-1", service="service-unseen")
        row["features"]["error_rate"] = None
        row["features"]["latency_ms"] = None
        row["features"]["latency_p95_ms"] = None
        row["features"]["missing_metrics"] = 1
        ranked = rank_rows([row])
        self.assertEqual(ranked[0]["missing_signals"], ["metrics"])
        self.assertEqual(ranked[0]["service_id"], "service-unseen")
        self.assertEqual(ranked[0]["unusual_score"], 0.0)

    def test_hidden_fields_and_source_names_are_rejected(self):
        row = _row("sample-1", "run-1")
        row["root_cause"] = "private"
        with self.assertRaises(RankingInputError):
            rank_rows([row])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.json"
            row = _row("sample-1", "run-1")
            row["features"]["source_filename"] = "private"
            _manifest(path, "training", [row])
            with self.assertRaises(ManifestPolicyError):
                load_manifest(path, "training")

    def test_sealed_final_manifest_is_never_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "final-held-out.json"
            _manifest(path, "final_held_out", [])
            with self.assertRaises(ManifestPolicyError):
                load_manifest(path, "validation")

    def test_group_assignments_must_be_disjoint(self):
        row = _row("sample-1", "same-run")
        with self.assertRaises(ManifestPolicyError):
            assert_disjoint_groups([row], [row])

    def test_model_fit_uses_train_only_and_serialization_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train = root / "train.json"
            validation = root / "validation.json"
            rows = [_row("sample-%02d" % i, "train-%02d" % i, latency=100 + i * 5) for i in range(8)]
            val_rows = [_row("val-%02d" % i, "validation-%02d" % i, latency=900 + i * 5) for i in range(2)]
            _manifest(train, "training", rows)
            _manifest(validation, "validation", val_rows)
            artifact_path = root / "model-manifest.json"
            artifact = fit_from_manifest(train, validation, artifact_path)
            self.assertEqual(artifact["training_rows"], 8)
            self.assertEqual(artifact["validation_rows"], 2)
            self.assertEqual(artifact["method"], "isolation_forest")
            verify_artifact(artifact_path)
            service = RankingService(artifact_path)
            response = service.rank(val_rows)
            self.assertEqual(len(response["ranking"]), 2)
            self.assertEqual(response["ranking_semantics"], RANKING_SEMANTICS)
            self.assertNotIn("root_cause_probability", json.dumps(response))

    def test_tampered_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train = root / "train.json"
            _manifest(train, "training", [_row("sample-1", "run-1")])
            artifact_path = root / "model-manifest.json"
            fit_from_manifest(train, None, artifact_path)
            doc = json.loads(artifact_path.read_text())
            doc["method"] = "isolation_forest"
            artifact_path.write_text(json.dumps(doc))
            with self.assertRaises(ArtifactError):
                verify_artifact(artifact_path)

    def test_aggregate_report_is_honest_without_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train = root / "train.json"
            validation = root / "validation.json"
            _manifest(train, "training", [_row("sample-1", "run-1")])
            _manifest(validation, "validation", [])
            artifact = root / "model-manifest.json"
            fit_from_manifest(train, validation, artifact)
            report = validate_manifest(validation, artifact, train_manifest_path=train)
            self.assertEqual(report["status"], "not_measured")
            self.assertEqual(report["metrics"]["false_alarm_rate"], "not measured")
            self.assertIn("Final held-out", " ".join(report["limitations"]))


if __name__ == "__main__":
    unittest.main()
