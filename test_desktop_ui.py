"""Exercise native widgets when a display is available, without microphone use."""

import json
from pathlib import Path
import shutil
import socket
import tempfile
import time
import unittest
from unittest.mock import patch
import tkinter as tk

from jarvis_desktop import DesktopApp


class DesktopUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: %s" % exc)
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        project = Path(self.directory.name)
        for name in ("jarvis_launcher.py", "native_file_manager.py"):
            shutil.copyfile(Path(__file__).parent / name, project / name)
        self.app = DesktopApp(self.root, project)
        self.addCleanup(self.app.service.stop)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.app.service.port = listener.getsockname()[1]
        self.errors = []
        errors = patch("jarvis_desktop.messagebox.showerror", side_effect=lambda *a, **k: self.errors.append(a))
        errors.start()
        self.addCleanup(errors.stop)

    def pump_until(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if predicate():
                self.assertEqual(self.errors, [])
                return
            time.sleep(0.01)
        self.fail("Desktop operation timed out; errors=%r" % self.errors)

    def test_buttons_save_start_schedule_cancel_and_stop(self):
        self.app.voice.set(False)
        self.app.values["CAMP_ID"].set("desktop-test")
        self.app.buttons[0].invoke()
        self.pump_until(lambda: not self.app.busy and self.app.service.ready.is_set())
        saved = json.loads(Path(self.directory.name, "config.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["CAMP_ID"], "desktop-test")
        self.assertFalse(saved["VOICE_ENABLED"])
        self.app.schedule_url.set("https://example.com")
        self.app.delay.set("3600")
        self.app.schedule()
        self.pump_until(lambda: not self.app.busy and bool(self.app.events.get_children()))
        item = self.app.events.get_children()[0]
        self.app.events.selection_set(item)
        self.app.cancel_event()
        self.pump_until(lambda: not self.app.busy and self.app.events.item(item)["values"][-1] == "cancelled")
        self.app.buttons[1].invoke()
        self.pump_until(lambda: not self.app.busy and not self.app.service.running)

    def test_invalid_schedule_shows_error_without_starting_any_service(self):
        self.app.schedule_url.set("file:///tmp/example")
        self.app.schedule()
        self.assertEqual(len(self.errors), 1)
        self.assertFalse(self.app.service.running)
        self.assertFalse(self.app.busy)


if __name__ == "__main__":
    unittest.main()
