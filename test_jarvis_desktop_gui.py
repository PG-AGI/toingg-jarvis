import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jarvis_desktop_gui import (
    JarvisDesktopController,
    JarvisGuiConfigError,
)


class FakeProcess:
    def __init__(self, pid: int = 4321):
        self.pid = pid
        self._terminated = False
        self.stdout = ["service booted\n"]

    def poll(self):
        return 0 if self._terminated else None

    def terminate(self):
        self._terminated = True

    def wait(self, timeout=None):
        return 0


class JarvisDesktopGuiControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.cfg_path = self.root / "config.json"
        self.sample_file = self.root / "report.txt"
        self.sample_file.write_text("generated output", encoding="utf-8")

        self.spawned: list[tuple[list[str], dict]] = []

        def fake_popen(cmd, **kwargs):
            proc = FakeProcess(pid=1000 + len(self.spawned))
            self.spawned.append((cmd, kwargs))
            return proc

        self.http_calls: list[tuple[str, str, dict | None]] = []

        def fake_http(method, path, payload):
            self.http_calls.append((method, path, payload))
            if path == "/state":
                return {"state": "ready", "status": "LISTENING"}
            if path == "/scheduled_actions":
                return {"ok": True, "items": [{"id": "sched-1", "name": "Daily Sync"}]}
            if path == "/schedule_action":
                return {"ok": True, "item": {"id": "sched-2", **payload}}
            if path == "/cancel_scheduled_action":
                return {"ok": True}
            return {"ok": True}

        self.controller = JarvisDesktopController(
            base_dir=self.root,
            config_path=self.cfg_path,
            popen_factory=fake_popen,
            http_requester=fake_http,
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_and_load_config_with_provider_api_keys_and_browser_settings(self):
        saved = self.controller.save_config(
            {
                "PROVIDER": "pipecat_gemini",
                "TOKEN": "toingg-secret-key-1234567890",
                "GEMINI_API_KEY": "AIzaSyMockKey123456",
                "MODEL": "gemini-2.5-pro",
                "browser": {
                    "headless": True,
                    "preferred_monitor": "1",
                    "window_size": "1280x800",
                    "position": "center",
                },
            }
        )
        self.assertEqual(saved["PROVIDER"], "pipecat_gemini")
        self.assertEqual(saved["MODEL"], "gemini-2.5-pro")
        self.assertTrue(saved["browser"]["headless"])
        self.assertEqual(saved["browser"]["window_size"], "1280x800")

        reloaded = self.controller.load_config()
        self.assertEqual(reloaded["PROVIDER"], "pipecat_gemini")
        self.assertEqual(reloaded["GEMINI_API_KEY"], "AIzaSyMockKey123456")

        with self.assertRaises(JarvisGuiConfigError):
            self.controller.save_config({"PROVIDER": "invalid_provider"})

    def test_start_stop_and_restart_services_and_stream_logs(self):
        self.controller.save_config({"browser": {"headless": True, "user_data_dir": ".custom-prof"}})
        started = self.controller.start_service("browser_client")
        self.assertEqual(started["status"], "running")
        self.assertIn("--headless", started["command"])
        self.assertIn(".custom-prof", started["command"])
        self.assertTrue(self.controller.is_service_running("browser_client"))

        restarted = self.controller.restart_service("browser_client")
        self.assertEqual(restarted["status"], "running")

        stopped = self.controller.stop_service("browser_client")
        self.assertEqual(stopped["status"], "stopped")
        self.assertFalse(self.controller.is_service_running("browser_client"))

        status = self.controller.get_service_status()
        self.assertEqual(status["launcher_state"]["status"], "LISTENING")
        self.assertTrue(any("Started browser_client" in line for line in self.controller.get_logs()))

    def test_scheduled_events_and_native_file_actions(self):
        items = self.controller.list_scheduled_events()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "sched-1")

        created = self.controller.schedule_event(
            {
                "name": "Morning Report",
                "trigger": {"delay_seconds": 15},
                "actions": [{"type": "open_url", "url": "https://example.com"}],
            }
        )
        self.assertTrue(created["ok"])

        cancelled = self.controller.cancel_scheduled_event("sched-1")
        self.assertTrue(cancelled["ok"])

        file_res = self.controller.trigger_file_action(
            "open_file",
            str(self.sample_file),
            dry_run=True,
            system="Windows",
        )
        self.assertEqual(file_res["action"], "open_file")
        self.assertEqual(Path(file_res["path"]), self.sample_file.resolve())


if __name__ == "__main__":
    unittest.main()
