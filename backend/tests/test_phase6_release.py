import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient

from incident_lens.api.app import create_app
from incident_lens.validation.performance import percentile


ROOT = Path(__file__).parents[2]


class Phase6ReleaseTests(unittest.TestCase):
    def test_cors_allows_only_explicit_pages_and_local_frontend_origins(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database:
            app = create_app(database.name)
            client = TestClient(app)
            try:
                preflight = client.options(
                    "/v1/sessions",
                    headers={
                        "Origin": "https://ronaldoj24.github.io",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type,x-session-id,idempotency-key",
                    },
                )
                self.assertEqual(preflight.status_code, 200)
                self.assertEqual(preflight.headers.get("access-control-allow-origin"), "https://ronaldoj24.github.io")
                self.assertEqual(preflight.headers.get("access-control-allow-credentials"), None)

                denied = client.options(
                    "/v1/sessions",
                    headers={
                        "Origin": "https://example.invalid",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(denied.status_code, 400)
                self.assertEqual(denied.headers.get("access-control-allow-origin"), None)
            finally:
                client.close()
                app.state.store.close()

    def test_cors_environment_replaces_default_allowlist(self):
        with patch.dict(os.environ, {"INCIDENT_LENS_CORS_ALLOWED_ORIGINS": "https://only.example"}, clear=False):
            with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database:
                app = create_app(database.name)
                client = TestClient(app)
                try:
                    allowed = client.get("/health", headers={"Origin": "https://only.example"})
                    self.assertEqual(allowed.headers.get("access-control-allow-origin"), "https://only.example")
                    denied = client.get("/health", headers={"Origin": "https://ronaldoj24.github.io"})
                    self.assertEqual(denied.headers.get("access-control-allow-origin"), None)
                finally:
                    client.close()
                    app.state.store.close()

    def test_readiness_and_metrics_are_safe_and_observable(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database:
            app = create_app(database.name)
            client = TestClient(app)
            try:
                ready = client.get("/health/ready")
                self.assertEqual(ready.status_code, 200)
                self.assertEqual(ready.json()["database_backend"], "StateStore")
                self.assertEqual(client.get("/v1/cases").status_code, 200)
                metrics = client.get("/metrics")
                self.assertEqual(metrics.status_code, 200)
                self.assertIn("incident_lens_http_requests_total", metrics.text)
                self.assertNotIn("password", metrics.text.lower())
            finally:
                client.close()
                app.state.store.close()

    def test_runtime_workflow_path_uses_bundled_knowledge(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database:
            app = create_app(database.name)
            client = TestClient(app)
            try:
                session_id = client.post("/v1/sessions").json()["session_id"]
                headers = {"X-Session-ID": session_id}
                run = client.post(
                    "/v1/runs",
                    json={"session_id": session_id, "case_id": "checkout-failure", "service": "checkoutservice"},
                )
                self.assertEqual(run.status_code, 202)
                run_id = run.json()["run_id"]
                workflow = client.post(
                    "/v1/runs/%s/workflow" % run_id,
                    headers=headers,
                    json={"query": "feature flag telemetry"},
                )
                self.assertEqual(workflow.status_code, 202)
                self.assertEqual(workflow.json()["status"], "completed")
                self.assertTrue(workflow.json()["retrieval_hits"])
            finally:
                client.close()
                app.state.store.close()

    def test_percentiles_are_deterministic(self):
        self.assertEqual(percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(percentile([1, 2, 3, 4], 0.95), 3.85)

    def test_container_and_release_contracts_enforce_boundaries(self):
        dockerfile = (ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
        release = (ROOT / "deploy/compose.release.yml").read_text(encoding="utf-8")
        render = (ROOT / "render.yaml").read_text(encoding="utf-8")
        render_start = (ROOT / "deploy/render-start.sh").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/phase6-release.yml").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("uv sync --frozen --no-dev", dockerfile)
        self.assertIn("COPY data/knowledge /data/knowledge", dockerfile)
        self.assertIn('ARG UV_VERSION=0.11.27', dockerfile)
        self.assertIn('version: "0.11.27"', workflow)
        self.assertIn("provisional and blocked from release acceptance", makefile)
        self.assertNotRegex(dockerfile, r"ENV\s+\S*(?:PASSWORD|API_KEY|TOKEN)\s*=")
        self.assertIn("POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?", compose)
        self.assertNotIn("incident_lens_local", compose)
        self.assertIn("INCIDENT_LENS_IMAGE:?", release)
        self.assertIn("INCIDENT_LENS_DATABASE_URL:?", release)
        self.assertIn("read_only: true", release)
        self.assertIn("cap_drop:", release)
        self.assertIn("region: ohio", render)
        self.assertIn("plan: free", render)
        self.assertIn("healthCheckPath: /health/ready", render)
        self.assertIn("uv sync --project backend --frozen --no-dev", render)
        self.assertIn("/etc/secrets/neon.env", render_start)
        self.assertIn("/etc/secrets/deepseek.env", render_start)
        self.assertIn("DATABASE_URL_UNPOOLED", render_start)
        self.assertIn('"$DATABASE_URL"', render_start)
        self.assertNotIn("INCIDENT_LENS_MIGRATION_DATABASE_URL", render_start)
        self.assertNotIn("INCIDENT_LENS_RUNTIME_DATABASE_URL", render_start)
        self.assertIn('"${PORT:-10000}"', render_start)
        self.assertNotIn("postgresql://", render)
        self.assertNotIn("api_key=", render_start.lower())


if __name__ == "__main__":
    unittest.main()
