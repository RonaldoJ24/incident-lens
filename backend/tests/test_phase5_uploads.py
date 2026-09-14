import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient

from incident_lens.api.app import create_app
from incident_lens.provider_policy import resolve_provider_outcome
from incident_lens.uploads import CostQuota, UploadManager, inspect_bytes


ROOT = Path(__file__).parent / "fixtures" / "uploads"


def fixture(name: str) -> bytes:
    return (ROOT / name).read_bytes()


class UploadValidationTests(unittest.TestCase):
    def test_all_phase5_fixtures_are_present(self):
        expected = {
            "valid.jsonl",
            "malformed.jsonl",
            "incomplete.jsonl",
            "oversized.jsonl",
            "duplicate.jsonl",
            "conflicting.jsonl",
            "prompt-injection.jsonl",
        }
        self.assertEqual({path.name for path in ROOT.glob("*.jsonl")}, expected)

    def test_required_fixture_outcomes(self):
        self.assertEqual(asyncio.run(inspect_bytes(fixture("valid.jsonl"))).validation, "accepted")
        self.assertEqual(asyncio.run(inspect_bytes(fixture("malformed.jsonl"))).validation, "invalid")
        incomplete = asyncio.run(inspect_bytes(fixture("incomplete.jsonl")))
        self.assertEqual(incomplete.validation, "incomplete")
        self.assertIn("metric", incomplete.missing_signals)
        self.assertEqual(asyncio.run(inspect_bytes(fixture("duplicate.jsonl"))).validation, "duplicate")
        self.assertEqual(asyncio.run(inspect_bytes(fixture("conflicting.jsonl"))).validation, "conflicting")

    def test_schema_rejects_unknown_fields(self):
        body = b'{"event_id":"strict-1","timestamp":"2026-09-14T08:00:00Z","signal":"log","service":"checkoutservice","message":"ok","extra":"reject"}\n'
        result = asyncio.run(inspect_bytes(body))
        self.assertEqual(result.validation, "invalid")

    def test_oversized_and_prompt_injection_are_bounded_and_untrusted(self):
        oversized = fixture("oversized.jsonl") * ((10 * 1024 * 1024 // len(fixture("oversized.jsonl"))) + 1)
        result = asyncio.run(inspect_bytes(oversized))
        self.assertEqual(result.validation, "invalid")
        self.assertIn("10 MiB", " ".join(result.messages))
        injection = asyncio.run(inspect_bytes(fixture("prompt-injection.jsonl")))
        self.assertEqual(injection.validation, "incomplete")
        self.assertEqual(injection.untrusted_record_count, 1)
        self.assertTrue(any("untrusted data" in message for message in injection.messages))

    def test_manager_isolates_sessions_cleans_and_enforces_budget(self):
        manager = UploadManager(retention_seconds=1, quota=CostQuota(max_bytes=1, max_records=1, max_cost_units=1))
        upload_id = manager.begin("sess-a")
        cancelled = manager.cancel("sess-a", upload_id)
        self.assertTrue(cancelled)
        self.assertIsNone(manager.get("sess-b", upload_id))
        manager.retention_seconds = 0
        self.assertIsNone(manager.get("sess-a", upload_id))
        manager = UploadManager(quota=CostQuota(max_bytes=1_000_000, max_records=0, max_cost_units=1))
        upload_id = manager.begin("sess-a")
        result = asyncio.run(manager.validate("sess-a", upload_id, "application/jsonl", self._chunks(fixture("incomplete.jsonl"))))
        self.assertEqual(result.validation, "invalid")
        self.assertIn("budget exceeded", " ".join(result.messages))

    def test_manager_cancels_while_stream_validation_is_active(self):
        manager = UploadManager()
        upload_id = manager.begin("sess-active")

        async def slow_chunks():
            body = fixture("valid.jsonl")
            split = body.index(b"\n") + 1
            yield body[:split]
            await asyncio.sleep(0.05)
            yield body[split:]

        async def exercise():
            task = asyncio.create_task(manager.validate("sess-active", upload_id, "application/jsonl", slow_chunks()))
            await asyncio.sleep(0.01)
            self.assertTrue(manager.cancel("sess-active", upload_id))
            return await task

        result = asyncio.run(exercise())
        self.assertEqual(result.validation, "incomplete")
        self.assertTrue(any("cancel" in message for message in result.messages))

    @staticmethod
    async def _chunks(body: bytes):
        yield body[:20]
        await asyncio.sleep(0)
        yield body[20:]

    def test_api_sample_upload_status_cancellation_and_isolation(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database:
            app = create_app(database.name)
            client = TestClient(app)
            try:
                session = client.post("/v1/sessions").json()["session_id"]
                other = client.post("/v1/sessions").json()["session_id"]
                headers = {"X-Session-ID": session}
                sample = client.get("/v1/uploads/sample")
                self.assertEqual(sample.status_code, 200)
                self.assertEqual(sample.headers["content-type"].split(";", 1)[0], "application/jsonl")
                initiated = client.post("/v1/uploads/initiate", headers=headers)
                self.assertEqual(initiated.status_code, 201)
                initiated_id = initiated.json()["upload_id"]
                streamed = client.put(
                    "/v1/uploads/%s" % initiated_id,
                    headers={**headers, "Content-Type": "application/jsonl"},
                    content=fixture("valid.jsonl"),
                )
                self.assertEqual(streamed.status_code, 200)
                self.assertEqual(streamed.json()["validation"], "accepted")
                upload = client.post(
                    "/v1/uploads", headers={**headers, "Content-Type": "application/jsonl"}, content=fixture("valid.jsonl")
                )
                self.assertEqual(upload.status_code, 200)
                self.assertEqual(upload.json()["validation"], "accepted")
                self.assertEqual(upload.json()["record_count"], 3)
                self.assertEqual(upload.json()["duplicate_count"], 0)
                self.assertEqual(upload.json()["missing_signal_count"], 0)
                upload_id = upload.json()["upload_id"]
                self.assertEqual(client.get("/v1/uploads/%s" % upload_id, headers=headers).status_code, 200)
                self.assertEqual(client.get("/v1/uploads/%s" % upload_id, headers={"X-Session-ID": other}).status_code, 404)
                self.assertEqual(client.delete("/v1/uploads/%s" % upload_id, headers=headers).json()["validation"], "accepted")
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(client.get("/v1/connectors/status").json()["status"], "blocked")
            finally:
                client.close()
                app.state.store.close()


class ProviderPolicyTests(unittest.TestCase):
    def test_provider_failure_never_silently_replays(self):
        failed = resolve_provider_outcome(provider_succeeded=False, choice="retry", replay_run_id="run-old", provider_error="timeout")
        self.assertEqual(failed.execution, "new_analysis")
        self.assertEqual(failed.outcome, "provider_failed")
        replay = resolve_provider_outcome(provider_succeeded=False, choice="replay", replay_run_id="run-old", provider_error="timeout")
        self.assertEqual(replay.execution, "stored_result")
        self.assertEqual(replay.prior_run_id, "run-old")
        success = resolve_provider_outcome(provider_succeeded=True, choice="replay", replay_run_id="run-old")
        self.assertEqual(success.execution, "new_analysis")


if __name__ == "__main__":
    unittest.main()
