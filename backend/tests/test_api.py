import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient

from incident_lens.api.app import create_app


class ApiFlowTests(unittest.TestCase):
    def setUp(self):
        self.database = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.database.close()
        self.app = create_app(self.database.name)
        self.client = TestClient(self.app)
        response = self.client.post("/v1/sessions")
        self.assertEqual(response.status_code, 201)
        self.session_id = response.json()["session_id"]
        self.headers = {"X-Session-ID": self.session_id}

    def tearDown(self):
        self.client.close()
        self.app.state.store.close()
        Path(self.database.name).unlink(missing_ok=True)

    def test_investigation_flow_persists_evidence_review_and_idempotent_report(self):
        cases = self.client.get("/v1/cases")
        self.assertEqual(cases.status_code, 200)
        self.assertEqual({case["case_id"] for case in cases.json()["cases"]}, {"checkout-failure", "degraded-performance", "insufficient-evidence"})

        run_response = self.client.post(
            "/v1/runs",
            headers={**self.headers, "Idempotency-Key": "flow-run"},
            json={"session_id": self.session_id, "case_id": "checkout-failure", "service": "checkoutservice"},
        )
        self.assertEqual(run_response.status_code, 202)
        run = self.client.get("/v1/runs/%s" % run_response.json()["run_id"], headers=self.headers).json()
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["provenance"]["telemetry_origin"], "controlled_runtime")
        self.assertEqual(run["provenance"]["execution"], "new_analysis")

        evidence = self.client.get("/v1/runs/%s/evidence" % run["run_id"], headers=self.headers)
        findings = self.client.get("/v1/runs/%s/findings" % run["run_id"], headers=self.headers)
        timeline = self.client.get("/v1/runs/%s/timeline" % run["run_id"], headers=self.headers)
        self.assertEqual(evidence.status_code, findings.status_code)
        self.assertEqual(findings.status_code, timeline.status_code)
        self.assertEqual(len(evidence.json()["evidence"]), 3)
        self.assertEqual(len(findings.json()["findings"]), 1)
        timeline_events = timeline.json()["events"]
        self.assertEqual(len(timeline_events), 1)
        self.assertEqual(timeline_events[0]["state"], "succeeded")
        self.assertIsNotNone(timeline_events[0]["started_at"])
        self.assertIsNotNone(timeline_events[0]["ended_at"])
        self.assertGreaterEqual(timeline_events[0]["duration_ms"], 1)
        self.assertEqual(timeline_events[0]["scope"]["parameters"]["max_events"], 100)
        self.assertEqual(len(timeline_events[0]["evidence_ids"]), 3)
        self.assertTrue(timeline_events[0]["scope"]["read_only"])

        review = self.client.post("/v1/runs/%s/review" % run["run_id"], headers=self.headers, json={"action": "challenge", "note": "Keep the competing explanation visible."})
        self.assertEqual(review.status_code, 202)
        self.assertTrue(review.json()["context_preserved"])
        self.assertEqual(len(self.client.get("/v1/runs/%s/findings" % run["run_id"], headers=self.headers).json()["findings"]), 1)
        withholding = self.client.post("/v1/runs/%s/review" % run["run_id"], headers=self.headers, json={"action": "withhold_source"})
        self.assertEqual(withholding.status_code, 409)

        report_payload = {"session_id": self.session_id, "run_id": run["run_id"]}
        first_report = self.client.post("/v1/reports", headers={**self.headers, "Idempotency-Key": "flow-report"}, json=report_payload)
        duplicate_report = self.client.post("/v1/reports", headers={**self.headers, "Idempotency-Key": "flow-report"}, json=report_payload)
        self.assertEqual(first_report.status_code, 201)
        self.assertEqual(duplicate_report.status_code, 201)
        self.assertEqual(first_report.json()["report_id"], duplicate_report.json()["report_id"])
        self.assertEqual(first_report.json()["revision"], 1)
        exported = self.client.post("/v1/reports/%s/export" % first_report.json()["report_id"], headers=self.headers)
        self.assertEqual(exported.status_code, 200)
        self.assertIn("attachment", exported.headers["content-disposition"])
        export_document = exported.json()
        self.assertEqual(export_document["provenance"]["run_version"], "phase1-fixture-v1")
        self.assertEqual(export_document["report"]["report_id"], first_report.json()["report_id"])
        self.assertEqual(len(export_document["findings"]), 1)
        self.assertEqual(len(export_document["evidence"]), 3)
        self.assertEqual(len(export_document["timeline"]), 2)

        reloaded_app = create_app(self.database.name)
        reloaded = TestClient(reloaded_app)
        self.assertEqual(reloaded.get("/v1/reports/%s" % first_report.json()["report_id"], headers=self.headers).status_code, 200)
        reloaded.close()
        reloaded_app.state.store.close()

    def test_three_authored_cases_have_distinct_deterministic_outcomes(self):
        expected = {
            "checkout-failure": "succeeded",
            "degraded-performance": "succeeded",
            "insufficient-evidence": "partial",
        }
        for case_id, expected_status in expected.items():
            response = self.client.post("/v1/runs", json={"session_id": self.session_id, "case_id": case_id, "service": "checkoutservice"})
            self.assertEqual(response.status_code, 202)
            run = self.client.get("/v1/runs/%s" % response.json()["run_id"], headers=self.headers).json()
            self.assertEqual(run["status"], expected_status)
            findings = self.client.get("/v1/runs/%s/findings" % run["run_id"], headers=self.headers).json()["findings"]
            self.assertEqual(len(findings), 1)
            if case_id == "degraded-performance":
                self.assertEqual(findings[0]["certainty"], "uncertain")
                self.assertIn("latency", findings[0]["assessment"].lower())
            if case_id == "insufficient-evidence":
                self.assertEqual(findings[0]["certainty"], "insufficient_evidence")

    def test_explicit_utc_window_preserves_default_fixture_interval(self):
        response = self.client.post(
            "/v1/runs",
            json={
                "session_id": self.session_id,
                "case_id": "checkout-failure",
                "service": "checkoutservice",
                "window_start": "2026-09-13T08:00:00+00:00",
                "window_end": "2026-09-13T08:10:00+00:00",
            },
        )
        self.assertEqual(response.status_code, 202)
        run_id = response.json()["run_id"]
        run = self.client.get("/v1/runs/%s" % run_id, headers=self.headers).json()
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["provenance"]["source_interval"]["start"], "2026-09-13T08:00:00Z")
        self.assertEqual(run["provenance"]["source_interval"]["end"], "2026-09-13T08:10:00Z")
        evidence = self.client.get("/v1/runs/%s/evidence" % run_id, headers=self.headers).json()["evidence"]
        self.assertEqual({item["source_type"] for item in evidence}, {"log", "metric", "trace"})
        self.assertTrue(all("missing" not in item["quality_flags"] for item in evidence))

    def test_guest_isolation_cancel_retry_and_partial_state(self):
        second_session = self.client.post("/v1/sessions").json()["session_id"]
        run_response = self.client.post(
            "/v1/runs",
            json={"session_id": self.session_id, "case_id": "insufficient-evidence", "service": "checkoutservice", "defer": True},
        )
        run_id = run_response.json()["run_id"]
        self.assertEqual(self.client.get("/v1/runs/%s" % run_id, headers={"X-Session-ID": second_session}).status_code, 404)
        cancelled = self.client.delete("/v1/runs/%s" % run_id, headers=self.headers)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        retried = self.client.post("/v1/runs/%s/retry" % run_id, headers=self.headers)
        self.assertEqual(retried.status_code, 202)
        final = self.client.get("/v1/runs/%s" % run_id, headers=self.headers).json()
        self.assertEqual(final["attempt"], 2)
        self.assertEqual(final["status"], "partial")
        self.assertEqual(self.client.get("/v1/runs/%s/evidence" % run_id, headers={"X-Session-ID": second_session}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
