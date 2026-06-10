import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import jarvis_launcher


class ScheduledActionsTest(unittest.TestCase):
    def setUp(self):
        jarvis_launcher._scheduled_actions.clear()
        jarvis_launcher._url_slot = 0

    def test_delay_trigger_creates_future_schedule(self):
        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)

        item = jarvis_launcher.create_scheduled_action(
            {
                "name": "open docs",
                "trigger": {"delay_seconds": 30},
                "actions": [{"type": "open_url", "url": "https://example.com"}],
            },
            now=now,
        )

        self.assertEqual(item["status"], "scheduled")
        self.assertEqual(item["scheduled_for"], "2026-06-03T12:00:30+00:00")
        self.assertEqual(jarvis_launcher.list_scheduled_actions()[0]["id"], item["id"])

    def test_daily_trigger_rolls_to_tomorrow_when_time_passed(self):
        now = datetime(2026, 6, 3, 12, 15, tzinfo=timezone.utc)

        next_run = jarvis_launcher._next_schedule_time(
            {"type": "daily", "time": "09:00"},
            now=now,
        )

        self.assertEqual(next_run.isoformat(), "2026-06-04T09:00:00+00:00")

    def test_execute_open_url_and_close_tabs_without_launching_browser(self):
        item = {
            "id": "test",
            "trigger": {"delay_seconds": 0},
            "actions": [
                {"type": "open_url", "url": "https://example.com"},
                {"type": "close_tabs", "auto": True},
            ],
            "status": "running",
            "scheduled_for": "2026-06-03T12:00:00+00:00",
        }

        with patch.object(jarvis_launcher, "open_url_in_slot") as open_url, \
                patch.object(jarvis_launcher, "close_all_url_windows") as close_tabs:
            jarvis_launcher._execute_scheduled_actions(item)

        open_url.assert_called_once()
        self.assertEqual(open_url.call_args.args[0], "https://example.com")
        self.assertEqual(open_url.call_args.args[1], 0)
        close_tabs.assert_called_once_with(auto=True)
        self.assertEqual(item["status"], "completed")

    def test_cancel_scheduled_action(self):
        item = jarvis_launcher.create_scheduled_action(
            {
                "id": "cancel-me",
                "trigger": {"delay_seconds": 10},
                "actions": [{"type": "open_url", "url": "https://example.com"}],
            }
        )

        self.assertTrue(jarvis_launcher.cancel_scheduled_action(item["id"]))
        self.assertEqual(jarvis_launcher.list_scheduled_actions()[0]["status"], "cancelled")

    def test_playwright_action_uses_immediate_schedule(self):
        now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)

        item = jarvis_launcher.create_playwright_action(
            {"action": "navigate", "params": {"url": "https://example.com"}},
            now=now,
        )

        self.assertEqual(item["name"], "playwright: navigate")
        self.assertEqual(item["scheduled_for"], "2026-06-03T12:00:00+00:00")
        self.assertEqual(item["actions"], [{"type": "open_url", "url": "https://example.com"}])


if __name__ == "__main__":
    unittest.main()
