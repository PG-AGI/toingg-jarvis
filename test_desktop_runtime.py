import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from desktop_runtime import ConfigStore, LauncherService


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "config.json"
        self.store = ConfigStore(self.path)

    def test_save_preserves_unknown_settings_and_unicode(self):
        self.path.write_text(json.dumps({"future_setting": {"enabled": True}}), encoding="utf-8")
        self.store.save({"CAMP_ID": "日本語", "TOKEN": "test-only", "BROWSER_HEADLESS": True})
        saved = self.store.load()
        self.assertEqual(saved["CAMP_ID"], "日本語")
        self.assertEqual(saved["future_setting"], {"enabled": True})
        self.assertTrue(saved["BROWSER_HEADLESS"])

    def test_invalid_url_keeps_existing_configuration(self):
        self.store.save({"TOKEN": "original"})
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.store.save({"WS_URL": "https://example.com"})
        self.assertEqual(self.path.read_bytes(), before)

    def test_malformed_configuration_is_not_overwritten(self):
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.save({"TOKEN": "new"})
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{broken")

    def test_failed_replace_preserves_original_and_removes_temporary_file(self):
        self.store.save({"TOKEN": "original"})
        before = self.path.read_bytes()
        with patch("desktop_runtime.os.replace", side_effect=PermissionError("read-only")):
            with self.assertRaises(PermissionError):
                self.store.save({"TOKEN": "new"})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(".config-*.json")), [])


class LauncherServiceIntegrationTests(unittest.TestCase):
    """Exercise the real launcher using only loopback, with voice disabled."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        for name in ("jarvis_launcher.py", "native_file_manager.py"):
            shutil.copyfile(Path(__file__).parent / name, self.project / name)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.port = listener.getsockname()[1]
        self.service = LauncherService(self.project, self.port)
        self.addCleanup(self.service.stop)

    def start(self):
        self.service.start({"VOICE_ENABLED": False})
        ready = self.service.ready.wait(timeout=8)
        self.assertTrue(ready, "Launcher did not become ready; output=%r" % list(self.service.logs.queue))
        self.assertTrue(self.service.running)

    def test_start_schedule_cancel_stop_and_restart(self):
        self.start()
        self.assertIn("status", self.service.request("/state"))
        with self.assertRaises(RuntimeError):
            self.service.start({"VOICE_ENABLED": False})
        item = self.service.request("/schedule_action", {
            "name": "test action", "trigger": {"delay_seconds": 3600},
            "actions": [{"type": "open_url", "url": "https://example.com"}],
        })["item"]
        self.assertEqual(self.service.request("/scheduled_actions")["items"][0]["id"], item["id"])
        self.assertTrue(self.service.request("/cancel_scheduled_action", {"id": item["id"]})["ok"])
        self.assertEqual(self.service.request("/scheduled_actions")["items"][0]["status"], "cancelled")
        self.service.stop()
        self.assertFalse(self.service.running)
        self.assertEqual(self.service.process.returncode, 0)
        with self.assertRaises(RuntimeError):
            self.service.request("/state")
        self.start()
        self.assertEqual(self.service.request("/scheduled_actions")["items"], [])

    def test_occupied_port_fails_without_killing_its_owner(self):
        with socket.socket() as listener:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(("127.0.0.1", self.port))
            listener.listen()
            self.service.start({"VOICE_ENABLED": False})
            self.assertNotEqual(self.service.process.wait(timeout=8), 0)
            self.assertFalse(self.service.ready.is_set())
            # The occupied listening socket remains intact after the failed start.
            self.assertEqual(listener.getsockname()[1], self.port)
            with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                connection, _ = listener.accept()
                connection.close()

    def test_stdin_eof_stops_owned_launcher(self):
        self.start()
        self.service.process.stdin.close()
        self.assertEqual(self.service.process.wait(timeout=8), 0)

    def test_log_reader_redacts_configured_token(self):
        (self.project / "jarvis_launcher.py").write_text(
            'print("example-secret-value", flush=True)\n', encoding="utf-8")
        self.service.start({"VOICE_ENABLED": False, "TOKEN": "example-secret-value"})
        self.service.process.wait(timeout=8)
        self.service._reader.join(timeout=2)
        self.assertEqual(self.service.logs.get_nowait(), "[redacted]")


class BrowserSettingsTests(unittest.TestCase):
    def test_loopback_server_does_not_require_reverse_dns(self):
        import jarvis_launcher
        with patch.object(jarvis_launcher, "HTTP_PORT", 0), \
                patch.object(jarvis_launcher, "_http_started", False), \
                patch.object(jarvis_launcher, "start_scheduler"), \
                patch.object(socket, "getfqdn", side_effect=AssertionError("DNS must not run")), \
                redirect_stdout(io.StringIO()):
            server = jarvis_launcher.start_http_server(reclaim_port=False)
            try:
                self.assertEqual(server.server_name, "localhost")
                self.assertGreater(server.server_port, 0)
            finally:
                server.shutdown()
                server.server_close()

    def test_headless_setting_is_passed_to_real_browser_command(self):
        import jarvis_launcher
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "config.json").write_text('{"BROWSER_HEADLESS": true}', encoding="utf-8")
            with patch.object(jarvis_launcher, "_DIR", temporary), \
                    patch.object(jarvis_launcher, "_browser_client_proc", None), \
                    patch.object(jarvis_launcher.subprocess, "Popen") as spawn:
                with redirect_stdout(io.StringIO()):
                    jarvis_launcher.start_browser_client()
                self.assertIn("--headless", spawn.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
