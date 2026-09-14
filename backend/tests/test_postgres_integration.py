"""Required PostgreSQL integration coverage; skipped for SQLite-only checkouts."""

import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient

from incident_lens.api.app import create_app
from incident_lens.api.store import PostgresStateStore
from incident_lens.fixtures.loader import load_cases


DATABASE_URL = os.getenv("INCIDENT_LENS_DATABASE_URL") or os.getenv("DATABASE_URL")


@unittest.skipUnless(DATABASE_URL, "INCIDENT_LENS_DATABASE_URL is not configured")
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.url = DATABASE_URL
        self.store = PostgresStateStore(self.url)
        self.store.seed_cases(load_cases())

    def tearDown(self):
        self.store.close()

    def test_migrations_are_ordered_and_api_flow_survives_reload(self):
        rows = self.store.connection.execute(
            "SELECT version, name FROM incident_lens_schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual([row["version"] for row in rows], [1, 2])

        with patch.dict(os.environ, {"INCIDENT_LENS_DATABASE_URL": self.url}):
            selected = create_app()
        self.assertIsInstance(selected.state.store, PostgresStateStore)
        selected.state.store.close()

        app = create_app(database_url=self.url)
        client = TestClient(app)
        session = client.post("/v1/sessions")
        self.assertEqual(session.status_code, 201)
        session_id = session.json()["session_id"]
        headers = {"X-Session-ID": session_id}
        run_response = client.post(
            "/v1/runs",
            headers={**headers, "Idempotency-Key": "pg-flow-run"},
            json={"session_id": session_id, "case_id": "checkout-failure", "service": "checkoutservice"},
        )
        self.assertEqual(run_response.status_code, 202)
        run_id = run_response.json()["run_id"]
        report_response = client.post(
            "/v1/reports",
            headers={**headers, "Idempotency-Key": "pg-flow-report"},
            json={"session_id": session_id, "run_id": run_id},
        )
        self.assertEqual(report_response.status_code, 201)
        report_id = report_response.json()["report_id"]
        client.close()
        app.state.store.close()

        reloaded = create_app(database_url=self.url)
        reloaded_client = TestClient(reloaded)
        try:
            persisted = reloaded_client.get("/v1/reports/%s" % report_id, headers=headers)
            self.assertEqual(persisted.status_code, 200)
            self.assertEqual(persisted.json()["run_id"], run_id)
        finally:
            reloaded_client.close()
            reloaded.state.store.close()

    def test_failed_write_rolls_back_and_concurrent_idempotency_is_single_row(self):
        session_id = self.store.create_session()["session_id"]
        provenance = {"execution": "new_analysis"}
        run = self.store.create_run(session_id, "checkout-failure", provenance, "concurrent-run")
        evidence = {
            "evidence_id": "pg-rollback-evidence-" + run["run_id"],
            "source_type": "log",
            "source": {"source_id": "fixture", "version": "v1"},
        }
        self.store.insert_evidence(run["run_id"], evidence)
        with self.assertRaises(Exception):
            self.store.insert_evidence(run["run_id"], evidence)
        self.assertEqual(self.store.list_evidence(run["run_id"]), [evidence])

        def create_from_new_connection():
            store = PostgresStateStore(self.url)
            try:
                return store.create_run(session_id, "checkout-failure", provenance, "race-key")["run_id"]
            finally:
                store.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            run_ids = list(pool.map(lambda _: create_from_new_connection(), range(4)))
        self.assertEqual(len(set(run_ids)), 1)

    def test_store_rejects_report_for_non_owner_session(self):
        owner = self.store.create_session()["session_id"]
        other = self.store.create_session()["session_id"]
        run = self.store.create_run(owner, "checkout-failure", {"execution": "new_analysis"}, "ownership-run")
        with self.assertRaisesRegex(ValueError, "does not own"):
            self.store.save_report(other, run["run_id"], {"execution": "new_analysis"}, [], "ownership-report")


if __name__ == "__main__":
    unittest.main()
