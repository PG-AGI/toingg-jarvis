import threading
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

    def _running_item(self, actions, recurring=False):
        trigger = {"type": "daily", "time": "09:00"} if recurring else {"delay_seconds": 0}
        item = jarvis_launcher.create_scheduled_action({"trigger": trigger, "actions": actions})
        item["status"] = "running"
        return item

    def test_cancel_before_worker_starts_skips_actions(self):
        item = self._running_item([{"type": "open_url", "url": "https://example.com"}])
        self.assertTrue(jarvis_launcher.cancel_scheduled_action(item["id"]))
        with patch.object(jarvis_launcher, "open_url_in_slot") as open_url:
            jarvis_launcher._execute_scheduled_actions(item)
        open_url.assert_not_called()
        self.assertEqual(item["status"], "cancelled")

    def test_cancel_running_daily_job_stops_later_actions_and_rearming(self):
        item = self._running_item([
            {"type": "open_url", "url": "https://example.com/first"},
            {"type": "open_url", "url": "https://example.com/second"},
        ], recurring=True)
        scheduled_for = item["scheduled_for"]
        with patch.object(jarvis_launcher, "open_url_in_slot",
                          side_effect=lambda *args: jarvis_launcher.cancel_scheduled_action(item["id"])) as open_url:
            jarvis_launcher._execute_scheduled_actions(item)
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(item["status"], "cancelled")
        self.assertEqual(item["scheduled_for"], scheduled_for)

    def test_cancel_during_tab_batch_skips_remaining_tabs(self):
        item = self._running_item([{
            "type": "open_tabs",
            "urls": ["https://example.com/first", "https://example.com/second"],
        }])
        with patch.object(jarvis_launcher, "open_url_in_slot",
                          side_effect=lambda *args: jarvis_launcher.cancel_scheduled_action(item["id"])) as open_url, \
                patch.object(jarvis_launcher, "close_all_url_windows"), \
                patch.object(jarvis_launcher.time, "sleep"):
            jarvis_launcher._execute_scheduled_actions(item)
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(item["status"], "cancelled")

    def test_cancel_is_preserved_if_in_flight_action_fails(self):
        item = self._running_item([{"type": "open_url", "url": "https://example.com"}], recurring=True)

        def cancel_then_fail(*args):
            jarvis_launcher.cancel_scheduled_action(item["id"])
            raise RuntimeError("in-flight action failed")

        with patch.object(jarvis_launcher, "open_url_in_slot", side_effect=cancel_then_fail):
            jarvis_launcher._execute_scheduled_actions(item)
        self.assertEqual(item["status"], "cancelled")

    def test_cancel_on_last_action_is_not_overwritten_by_completion(self):
        item = self._running_item([{"type": "open_url", "url": "https://example.com"}])
        with patch.object(jarvis_launcher, "open_url_in_slot",
                          side_effect=lambda *args: jarvis_launcher.cancel_scheduled_action(item["id"])):
            jarvis_launcher._execute_scheduled_actions(item)
        self.assertEqual(item["status"], "cancelled")

    def test_normal_daily_job_still_rearms(self):
        item = self._running_item([{"type": "open_url", "url": "https://example.com"}], recurring=True)
        tomorrow = datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc)
        with patch.object(jarvis_launcher, "open_url_in_slot") as open_url, \
                patch.object(jarvis_launcher, "_next_schedule_time", return_value=tomorrow):
            jarvis_launcher._execute_scheduled_actions(item)
        open_url.assert_called_once()
        self.assertEqual(item["status"], "scheduled")
        self.assertEqual(item["scheduled_for"], tomorrow.isoformat())

    def test_cancel_interrupts_a_running_wait(self):
        item = self._running_item([{"type": "wait", "seconds": 30}])
        waiting = threading.Event()
        condition = jarvis_launcher._scheduled_actions_changed
        wait_for = condition.wait_for

        def observed_wait(*args, **kwargs):
            waiting.set()
            return wait_for(*args, **kwargs)

        worker = threading.Thread(target=jarvis_launcher._execute_scheduled_actions,
                                  args=(item,), daemon=True)
        with patch.object(condition, "wait_for", side_effect=observed_wait):
            worker.start()
            try:
                self.assertTrue(waiting.wait(1), "worker never reached the wait")
                self.assertTrue(jarvis_launcher.cancel_scheduled_action(item["id"]))
                worker.join(1)
                self.assertFalse(worker.is_alive(), "cancel did not interrupt the wait")
                self.assertEqual(item["status"], "cancelled")
            finally:
                jarvis_launcher.cancel_scheduled_action(item["id"])
                worker.join(1)


if __name__ == "__main__":
    unittest.main()
