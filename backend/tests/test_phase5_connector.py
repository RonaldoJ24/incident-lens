import json
import hashlib
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.api.app import create_app
from incident_lens.connectors import ConnectorError, ReadOnlyConnector, connector_status


class ControlledConnectorHandler(BaseHTTPRequestHandler):
    paths = []

    def do_GET(self):
        type(self).paths.append(self.path)
        if self.path == "/events":
            body = json.dumps({"events": [{"signal": "log"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/large":
            body = b"{" + b'"payload":"' + b"x" * 128 + b'"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "http://example.invalid/events")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        return


class ConnectorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ControlledConnectorHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = "http://127.0.0.1:%d" % self.server.server_port
        ControlledConnectorHandler.paths = []

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_local_controlled_http_result_contains_source_and_access_metadata(self):
        connector = ReadOnlyConnector(
            self.base_url,
            ["127.0.0.1"],
            source_id="controlled-test-app",
            source_version="test-v1",
            path="events",
            require_https=False,
        )
        result = connector.verify()
        self.assertEqual(result.payload["events"][0]["signal"], "log")
        self.assertEqual(result.source_id, "controlled-test-app")
        self.assertEqual(result.source_version, "test-v1")
        self.assertEqual(result.access_scope, "connected_app")
        self.assertTrue(result.accessed_at.endswith("Z"))
        self.assertEqual(result.payload_sha256, hashlib.sha256(json.dumps({"events": [{"signal": "log"}]}).encode("utf-8")).hexdigest())
        self.assertEqual(result.as_metadata()["top_level_keys"], ["events"])
        self.assertFalse(hasattr(connector, "post"))

    def test_configured_path_cannot_be_selected_by_caller(self):
        connector = ReadOnlyConnector(self.base_url, ["127.0.0.1"], path="events", require_https=False)
        with self.assertRaisesRegex(ConnectorError, "fixed by configuration"):
            connector.get_json("large")
        connector.verify()
        self.assertEqual(ControlledConnectorHandler.paths, ["/events"])

    def test_host_redirect_and_response_bounds_are_rejected(self):
        with self.assertRaises(ConnectorError):
            ReadOnlyConnector(self.base_url, ["example.invalid"], require_https=False)
        connector = ReadOnlyConnector(self.base_url, ["127.0.0.1"], require_https=False, max_bytes=16)
        with self.assertRaises(ConnectorError):
            connector.get_json("large")
        with self.assertRaises(ConnectorError):
            connector.get_json("redirect")

    def test_status_is_explicitly_blocked_without_owned_endpoint(self):
        with patch.dict(os.environ, {}, clear=True):
            status = connector_status()
        self.assertEqual(status.status, "blocked")
        self.assertFalse(status.configured)
        self.assertIn("not configured", status.reason)

    def test_status_stays_blocked_until_live_owned_access_is_verified(self):
        with patch.dict(
            os.environ,
            {
                "INCIDENT_LENS_CONNECTOR_BASE_URL": self.base_url,
                "INCIDENT_LENS_CONNECTOR_ALLOWED_HOSTS": "127.0.0.1",
                "INCIDENT_LENS_CONNECTOR_PATH": "events",
                "INCIDENT_LENS_CONNECTOR_ALLOW_HTTP": "1",
            },
            clear=True,
        ):
            status = connector_status()
        self.assertEqual(status.status, "blocked")
        self.assertTrue(status.configured)
        self.assertIn("no live", status.reason)

    def test_api_verification_returns_metadata_without_payload_and_ignores_selectors(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database, patch.dict(
            os.environ,
            {
                "INCIDENT_LENS_CONNECTOR_BASE_URL": self.base_url,
                "INCIDENT_LENS_CONNECTOR_ALLOWED_HOSTS": "127.0.0.1",
                "INCIDENT_LENS_CONNECTOR_PATH": "events",
                "INCIDENT_LENS_CONNECTOR_SOURCE_ID": "github-actions:RonaldoJ24/cadencia-ai",
                "INCIDENT_LENS_CONNECTOR_SOURCE_VERSION": "github-actions-v3",
                "INCIDENT_LENS_CONNECTOR_ALLOW_HTTP": "1",
            },
            clear=True,
        ):
            app = create_app(database.name)
            client = TestClient(app)
            try:
                self.assertEqual(client.get("/v1/connectors/status").json()["status"], "blocked")
                response = client.get("/v1/connectors/verify?path=large&method=POST")
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["status"], "verified")
                self.assertEqual(body["source_id"], "github-actions:RonaldoJ24/cadencia-ai")
                self.assertEqual(body["source_version"], "github-actions-v3")
                self.assertEqual(body["endpoint"], self.base_url + "/events")
                self.assertNotIn("payload", body)
                self.assertEqual(ControlledConnectorHandler.paths[-1], "/events")
                self.assertEqual(client.post("/v1/connectors/verify").status_code, 405)
            finally:
                client.close()
                app.state.store.close()

    def test_api_verification_failure_is_not_verified(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database, patch.dict(
            os.environ,
            {
                "INCIDENT_LENS_CONNECTOR_BASE_URL": self.base_url,
                "INCIDENT_LENS_CONNECTOR_ALLOWED_HOSTS": "127.0.0.1",
                "INCIDENT_LENS_CONNECTOR_PATH": "missing",
                "INCIDENT_LENS_CONNECTOR_ALLOW_HTTP": "1",
            },
            clear=True,
        ):
            app = create_app(database.name)
            client = TestClient(app)
            try:
                response = client.get("/v1/connectors/verify")
                self.assertEqual(response.status_code, 502)
                self.assertNotEqual(response.json().get("status"), "verified")
                self.assertEqual(client.get("/v1/connectors/status").json()["status"], "blocked")
            finally:
                client.close()
                app.state.store.close()


if __name__ == "__main__":
    unittest.main()
