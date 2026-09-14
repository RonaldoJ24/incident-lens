import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.connectors import ConnectorError, ReadOnlyConnector, connector_status


class ControlledConnectorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
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
            require_https=False,
        )
        result = connector.get_json("events")
        self.assertEqual(result.payload["events"][0]["signal"], "log")
        self.assertEqual(result.source_id, "controlled-test-app")
        self.assertEqual(result.source_version, "test-v1")
        self.assertEqual(result.access_scope, "connected_app")
        self.assertTrue(result.accessed_at.endswith("Z"))
        self.assertFalse(hasattr(connector, "post"))

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
                "INCIDENT_LENS_CONNECTOR_ALLOW_HTTP": "1",
            },
            clear=True,
        ):
            status = connector_status()
        self.assertEqual(status.status, "blocked")
        self.assertTrue(status.configured)
        self.assertIn("no live", status.reason)


if __name__ == "__main__":
    unittest.main()
