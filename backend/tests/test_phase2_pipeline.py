import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.adapters.otel import ControlledFailureError, ControlledFailureQuery, ControlledFailureRecord, result_from_records
from incident_lens.adapters.rcaeval import RCAEvalAdapter, RCAEvalDatasetRevision, RCAEvalSourceRevision, RawCase, RawFile, SourceAdapterError, SourceArtifactNotFound, SourceLocator
from incident_lens.adapters import rcaeval
from incident_lens.pipeline.artifacts import ArtifactAccessError, ArtifactReference, derived_key, raw_key, validate_private_key
from incident_lens.pipeline.generate_quality import build_quality_report, generate_quality_report
from incident_lens.pipeline.normalization import DuplicateEventError, LeakageError, NormalizationError, SplitError, TimestampError, canonical_timestamp, normalize_case, normalize_events, parse_timestamp
from incident_lens.pipeline.normalize import normalize_manifest


class Phase2NormalizationTests(unittest.TestCase):
    def test_epoch_units_and_subsecond_precision_remain_distinct(self):
        values = [
            1700000000,
            1700000000123,
            1700000000123456,
            1700000000123456789,
        ]
        rendered = [canonical_timestamp(value) for value in values]
        self.assertEqual(rendered, [
            "2023-11-14T22:13:20Z",
            "2023-11-14T22:13:20.123000000Z",
            "2023-11-14T22:13:20.123456000Z",
            "2023-11-14T22:13:20.123456789Z",
        ])
        self.assertEqual(parse_timestamp(values[2]).microsecond, 123456)
        events, quality = normalize_events("logs", [{"time": values[2], "message": "a"}, {"time": values[3], "message": "a"}])
        self.assertEqual(quality.output_count, 2)
        self.assertNotEqual(events[0].event_id, events[1].event_id)

    def test_normalization_is_deterministic_and_timezone_normalized(self):
        records = {
            "logs": [{"timestamp": "2024-01-01T00:00:01-05:00", "message": "ok"}],
            "metrics": [{"time": 1704067200, "value": 1.0}],
            "traces": [],
        }
        first = normalize_case("dev-re2ob-001", "development", "source-v1", "dataset-v1", records)
        second = normalize_case("dev-re2ob-001", "development", "source-v1", "dataset-v1", records)
        self.assertEqual(first.manifest_hash, second.manifest_hash)
        self.assertEqual(first.manifest(), second.manifest())
        self.assertEqual(first.window_start, "2024-01-01T00:00:00Z")

    def test_malformed_timestamp_and_duplicate_are_rejected(self):
        with self.assertRaises(TimestampError):
            normalize_events("logs", [{"timestamp": "2024-01-01", "message": "bad"}])
        duplicate = [{"timestamp": "2024-01-01T00:00:00Z", "message": "same"}] * 2
        with self.assertRaises(DuplicateEventError):
            normalize_events("logs", duplicate)
        _, quality = normalize_events("logs", duplicate, strict=False)
        self.assertEqual(quality.duplicate_count, 1)
        self.assertEqual(quality.output_count, 1)

    def test_hidden_fields_filename_text_and_split_are_rejected(self):
        with self.assertRaises(LeakageError):
            normalize_events("logs", [{"timestamp": "2024-01-01T00:00:00Z", "root_cause": "x"}])
        with self.assertRaises(LeakageError):
            normalize_events("logs", [{"timestamp": "2024-01-01T00:00:00Z", "message": "re2ob_checkoutservice_cpu_1/logs.csv"}])
        with self.assertRaises(SplitError):
            normalize_case("dev-re2ob-001", "final_held_out", "source-v1", "dataset-v1", {})


class Phase2IsolationTests(unittest.TestCase):
    def test_normalize_manifest_rejects_case_not_in_public_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selection = root / "development.json"
            selection.write_text(json.dumps({
                "split": "development",
                "source": {"source_version": "source-v1", "dataset_revision": "dataset-v1"},
                "cases": [{"case_id": "dev-re2ob-001"}],
            }), encoding="utf-8")
            with self.assertRaisesRegex(NormalizationError, "not selected"):
                normalize_manifest(selection, raw_root=root / "raw", output_root=root / "derived", case_id="dev-re2ob-999")

    def test_artifact_keys_are_neutral_and_scoped(self):
        digest = "a" * 64
        key = raw_key("b" * 40, "dev-re2ob-001", "metrics.parquet")
        self.assertTrue(key.endswith("dev-re2ob-001/metrics.parquet"))
        validate_private_key(key, case_id="dev-re2ob-001")
        with self.assertRaises(ArtifactAccessError):
            validate_private_key(key, case_id="dev-re2ob-002")
        with self.assertRaises(ArtifactAccessError):
            validate_private_key("raw/rcaeval/%s/dev-re2ob-001/../../secret" % ("b" * 40), case_id="dev-re2ob-001")
        derived = derived_key("quality", "v1", "dev-re2ob-001", digest)
        reference = ArtifactReference.new("artifact-1", "dev-re2ob-001", "quality", "private-bucket", derived, b"{}", "source-v1")
        self.assertEqual(reference.byte_size, 2)

    def test_rcaeval_locator_rejects_out_of_split(self):
        with self.assertRaises(SourceAdapterError):
            SourceLocator("dev-re2ob-001", "re2ob_checkoutservice_cpu_1", split="final_held_out")

    def test_rcaeval_locator_and_fetch_boundary_reject_bad_revision_and_downloads(self):
        with self.assertRaises(SourceAdapterError):
            SourceLocator("re2ob-001", "re2ob_checkoutservice_cpu_1")
        with self.assertRaises(SourceAdapterError):
            SourceLocator("dev-re2ob-001", "re2ob_checkoutservice_cpu_1", source_revision="not-pinned")
        with self.assertRaises(SourceAdapterError):
            RCAEvalAdapter(source_revision="a" * 40).fetch_case(SourceLocator("dev-re2ob-001", "re2ob_checkoutservice_cpu_1"))
        with self.assertRaises(SourceAdapterError):
            SourceLocator(case_id="dev-re2ob-001", remote_case="re3ob_checkoutservice_cpu_1")
        locator = SourceLocator("dev-re2ob-001", "re2ob_checkoutservice_cpu_1")
        with tempfile.TemporaryDirectory() as directory:
            def fetch(url, timeout, max_bytes):
                if url.endswith("logs.parquet"):
                    raise SourceArtifactNotFound("absent")
                return b"metric-or-trace"

            with patch("incident_lens.adapters.rcaeval._download", side_effect=fetch):
                result = RCAEvalAdapter(Path(directory)).fetch_case(locator)
            self.assertEqual(set(result.available_signals), {"metrics", "traces"})
            with patch("incident_lens.adapters.rcaeval._download", side_effect=SourceAdapterError("upstream failed")):
                with self.assertRaises(SourceAdapterError):
                    RCAEvalAdapter(Path(directory)).fetch_case(locator)
            with patch("incident_lens.adapters.rcaeval._download", return_value=b"x"):
                with self.assertRaises(SourceAdapterError):
                    RCAEvalAdapter(Path(directory), max_file_bytes=0).fetch_case(locator)

    def test_download_size_limit_is_enforced_before_bytes_are_written(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, size):
                return b"x" * size

        with patch.object(rcaeval, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(SourceAdapterError, "size limit"):
                rcaeval._download("https://example.invalid", 1, 10, retries=0)

    def test_locator_file_cannot_be_loaded_from_a_tracked_project_path(self):
        with self.assertRaisesRegex(SourceAdapterError, "under ignored"):
            rcaeval.load_source_locators(Path("backend/tests/locators.json"))

    def test_quality_report_is_derived_without_injection_metadata(self):
        normalized = normalize_case(
            "dev-re2ob-001",
            "development",
            "RCAEval@bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90",
            "RCAEval-HF@afeacb11bcc94dadfd1c8f483ee4377b2b8b614e",
            {"logs": [{"timestamp": "2024-01-01T00:00:00.123456789Z", "message": "ok"}], "metrics": [], "traces": []},
        )
        report = build_quality_report(normalized)
        self.assertEqual(report["manifest_hash"], normalized.manifest_hash)
        self.assertEqual(report["signals"]["logs"]["output_count"], 1)
        self.assertNotIn("inject_time", repr(report))
        self.assertNotIn("root_cause", repr(report))

    def test_quality_generation_is_deterministic_and_cleans_only_requested_case(self):
        case_id = "dev-re2ob-001"
        locator = SourceLocator(case_id, "re2ob_checkoutservice_cpu_1")
        records = {
            "logs": [{"timestamp": "2024-01-01T00:00:00.123456789Z", "message": "ok"}],
            "metrics": [{"time": 1704067200123456789, "value": 1.0}],
            "traces": [{"time": 1704067200123, "span": "a"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_root = root / "raw"
            sibling = raw_root / "dev-re2ob-002"
            sibling.mkdir(parents=True)
            (sibling / "keep.txt").write_text("keep", encoding="utf-8")
            output_one = root / "quality-one.json"
            output_two = root / "quality-two.json"

            def fetch(_locator):
                case_root = raw_root / case_id
                case_root.mkdir(parents=True, exist_ok=True)
                for signal in records:
                    (case_root / (signal + ".parquet")).write_bytes(b"mock")
                return RawCase(
                    case_id=case_id,
                    source_revision=RCAEvalSourceRevision,
                    dataset_revision=RCAEvalDatasetRevision,
                    files=tuple(RawFile(signal, "a" * 64, 4, "raw/mock/%s/%s.parquet" % (case_id, signal)) for signal in records),
                    raw_root=case_root,
                )

            def read_records(path):
                return records[path.stem]

            with patch("incident_lens.pipeline.generate_quality.load_source_locators", return_value={case_id: locator}), \
                    patch("incident_lens.pipeline.generate_quality.RCAEvalAdapter") as adapter_class, \
                    patch("incident_lens.pipeline.generate_quality.read_parquet_records", side_effect=read_records):
                adapter_class.return_value.fetch_case.side_effect = fetch
                first = generate_quality_report(Path("data/manifests/development.json"), case_id, raw_root=raw_root, output_path=output_one)
                second = generate_quality_report(Path("data/manifests/development.json"), case_id, raw_root=raw_root, output_path=output_two)

            self.assertEqual(first, second)
            self.assertEqual(output_one.read_text(encoding="utf-8"), output_two.read_text(encoding="utf-8"))
            self.assertFalse((raw_root / case_id).exists())
            self.assertTrue((sibling / "keep.txt").exists())

    def test_quality_generation_rejects_revision_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selection = json.loads(Path("data/manifests/development.json").read_text(encoding="utf-8"))
            selection["source"]["dataset_revision"] = "RCAEval-HF@" + ("a" * 40)
            path = root / "development.json"
            path.write_text(json.dumps(selection), encoding="utf-8")
            with self.assertRaisesRegex(NormalizationError, "do not match"):
                generate_quality_report(path, "dev-re2ob-001", raw_root=root / "raw", output_path=root / "quality.json")

    def test_controlled_runtime_has_separate_result_schema(self):
        query = ControlledFailureQuery("feature_flag_evaluation", "checkoutservice", "2024-01-01T00:00:00Z", "2024-01-01T00:10:00Z")
        result = result_from_records(query, [ControlledFailureRecord("feature_flag_evaluation", "otel-v1", "2024-01-01T00:01:00Z", ("logs",))])
        self.assertEqual(result.signal_completeness["metrics"], "missing")
        with self.assertRaises(ControlledFailureError):
            result_from_records(ControlledFailureQuery("x", "y", "2024-01-01T00:00:00", "2024-01-01T00:10:00Z"), [])


if __name__ == "__main__":
    unittest.main()
