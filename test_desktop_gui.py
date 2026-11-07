import json
import tempfile
import unittest
from pathlib import Path

from desktop_gui import (
    DesktopGuiConfigError,
    DesktopGuiController,
)


class FakeProcess:
    def __init__(self, cmd, cwd=None, stdout=None, stderr=None, pid=4242):
        self.cmd = cmd
        self.cwd = cwd
        self.pid = pid
        self._terminated = False

    def poll(self):
        return 0 if self._terminated else None

    def terminate(self):
        self._terminated = True


class DesktopGuiControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.config_path = self.root / "config.json"
        self.sample_file = self.root / "report.txt"
        self.sample_file.write_text("generated output", encoding="utf-8")

        self.spawned = []

        def factory(cmd, **kwargs):
            proc = FakeProcess(cmd, pid=1000 + len(self.spawned), **kwargs)
            self.spawned.append(proc)
            return proc

        self.scheduled_store = {}

        def create_sched(payload):
            item = {
                "id": "sched_1",
                "name": payload.get("name", "test_job"),
                "status": "scheduled",
            }
            self.scheduled_store[item["id"]] = item
            return item

        def list_sched():
            return list(self.scheduled_store.values())

        def cancel_sched(action_id):
            if action_id in self.scheduled_store:
                self.scheduled_store[action_id]["status"] = "cancelled"
                return True
            return False

        self.controller = DesktopGuiController(
            config_path=self.config_path,
            project_dir=self.root,
            process_factory=factory,
            schedule_handlers={
                "create": create_sched,
                "list": list_sched,
                "cancel": cancel_sched,
            },
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_provider_selection_and_persistence(self):
        self.assertEqual(self.controller.config["PROVIDER"], "toingg")

        updated = self.controller.set_provider("pipecat")
        self.assertEqual(updated["PROVIDER"], "pipecat")

        saved_disk = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved_disk["PROVIDER"], "pipecat")

        with self.assertRaises(DesktopGuiConfigError):
            self.controller.set_provider("unsupported_provider")

    def test_api_keys_and_model_settings_update(self):
        cfg = self.controller.update_api_keys(
            toingg_token="tg_live_1234567890abcdef",
            gemini_api_key="AIzaSyTestKey12345",
            model="gemini-2.5-pro",
        )
        self.assertEqual(cfg["TOKEN"], "tg_live_1234567890abcdef")
        self.assertEqual(cfg["GEMINI_API_KEY"], "AIzaSyTestKey12345")
        self.assertEqual(cfg["MODEL"], "gemini-2.5-pro")

        with self.assertRaises(DesktopGuiConfigError):
            self.controller.update_api_keys(model="   ")

    def test_browser_automation_settings_validation(self):
        cfg = self.controller.update_browser_settings(
            headless=True,
            window_width=1440,
            window_height=900,
            ws_url="wss://example.com/ws",
        )
        b_cfg = cfg["BROWSER_SETTINGS"]
        self.assertTrue(b_cfg["headless"])
        self.assertEqual(b_cfg["window_width"], 1440)
        self.assertEqual(b_cfg["window_height"], 900)
        self.assertEqual(b_cfg["ws_url"], "wss://example.com/ws")

        with self.assertRaises(DesktopGuiConfigError):
            self.controller.update_browser_settings(window_width=100)
        with self.assertRaises(DesktopGuiConfigError):
            self.controller.update_browser_settings(ws_url="http://not-websocket")

    def test_start_stop_and_restart_services(self):
        summary0 = self.controller.get_status_summary()
        self.assertEqual(summary0["overall"], "idle")

        res = self.controller.start_service("launcher")
        self.assertEqual(res["status"], "running")
        self.assertEqual(
            self.controller.get_service_statuses()["launcher"], "running"
        )
        self.assertEqual(self.controller.get_status_summary()["overall"], "online")

        restarted = self.controller.restart_service("launcher")
        self.assertEqual(restarted["status"], "running")
        self.assertEqual(len(self.spawned), 2)

        stopped = self.controller.stop_service("launcher")
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(
            self.controller.get_service_statuses()["launcher"], "stopped"
        )

    def test_scheduled_events_and_file_actions(self):
        created = self.controller.schedule_event({"name": "morning_briefing"})
        self.assertEqual(created["id"], "sched_1")
        self.assertEqual(len(self.controller.list_scheduled_events()), 1)

        self.assertTrue(self.controller.cancel_scheduled_event("sched_1"))
        self.assertEqual(
            self.controller.list_scheduled_events()[0]["status"], "cancelled"
        )

        dir_plan = self.controller.open_project_directory(dry_run=True)
        self.assertEqual(dir_plan["action"], "open_directory")
        self.assertEqual(dir_plan["path"], str(self.root.resolve()))

        file_plan = self.controller.open_generated_file(
            self.sample_file, reveal=True, dry_run=True
        )
        self.assertEqual(file_plan["action"], "reveal_file")
        self.assertEqual(file_plan["path"], str(self.sample_file.resolve()))


if __name__ == "__main__":
    unittest.main()
