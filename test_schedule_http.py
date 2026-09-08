"""Exercise scheduling errors through the real HTTP request handler."""

from contextlib import ExitStack
import http.client
from http.server import HTTPServer
import io
import json
import unittest
from unittest.mock import patch

import jarvis_launcher


class ScheduleHTTPTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        servers = []

        class CapturedServer(HTTPServer):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                servers.append(self)

        self.stack.enter_context(patch("http.server.HTTPServer", CapturedServer))
        # Reverse-DNS startup is covered separately by the desktop-controls PR.
        self.stack.enter_context(patch("socket.getfqdn", return_value="localhost"))
        self.stack.enter_context(patch.object(jarvis_launcher, "HTTP_PORT", 0))
        self.stack.enter_context(patch.object(jarvis_launcher, "_http_started", False))
        self.stack.enter_context(patch.object(jarvis_launcher, "_kill_port"))
        self.stack.enter_context(patch.object(jarvis_launcher, "start_scheduler"))
        self.stack.enter_context(patch.object(jarvis_launcher, "_scheduled_actions", {}))
        self.stack.enter_context(patch("sys.stdout", io.StringIO()))
        jarvis_launcher.start_http_server()
        self.server = servers[0]
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, payload, raw=False):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            body = payload if raw else json.dumps(payload)
            connection.request("POST", path, body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            self.assertEqual(response.getheader("Content-Type"), "application/json")
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_invalid_delay_returns_complete_400_response(self):
        status, body = self.request("/schedule_action", {
            "trigger": {"delay_seconds": "tomorrow"},
            "actions": [{"type": "open_url", "url": "https://example.com"}],
        })
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertIn("error", body)
        self.assertEqual(jarvis_launcher.list_scheduled_actions(), [])

    def test_malformed_json_returns_400_for_both_routes(self):
        for path in ("/schedule_action", "/cancel_scheduled_action"):
            with self.subTest(path=path):
                status, body = self.request(path, "{", raw=True)
                self.assertEqual(status, 400)
                self.assertFalse(body["ok"])

    def test_non_object_payload_returns_400_for_both_routes(self):
        for path in ("/schedule_action", "/cancel_scheduled_action"):
            with self.subTest(path=path):
                status, body = self.request(path, [])
                self.assertEqual(status, 400)
                self.assertIn("error", body)

    def test_success_and_unknown_id_keep_existing_status_codes(self):
        status, body = self.request("/schedule_action", {
            "name": "later", "trigger": {"delay_seconds": 3600},
            "actions": [{"type": "open_url", "url": "https://example.com"}],
        })
        self.assertEqual(status, 201)
        action_id = body["item"]["id"]
        self.assertEqual(self.request("/cancel_scheduled_action", {"id": action_id}), (200, {"ok": True}))
        self.assertEqual(self.request("/cancel_scheduled_action", {"id": "unknown"}), (404, {"ok": False}))


if __name__ == "__main__":
    unittest.main()
