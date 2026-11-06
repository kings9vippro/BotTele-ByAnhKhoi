"""Unified task registry and command scope regressions."""
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "v6-tests")
import app
from task_registry import aggregate_tasks
from control_plane import telegram_command


def durable(owner="321", task_id="d1", status="RUNNING"):
    return {"id": task_id, "owner": owner, "channel": "c1", "status": status,
        "created": 10.0, "started": 20.0, "updated": 25.0, "attempts": 1,
        "error": "", "latency": 0.0}


def legacy(task_id="l1", status="running", can_stop=True):
    return {"id": task_id, "mode": "zalo", "status": status,
        "started_at": 23.0, "target_label": "test-group",
        "can_stop": can_stop}


class TaskRegistryV6Tests(unittest.TestCase):
    def test_aggregate_scopes_durable_records(self):
        result = aggregate_tasks([durable(), durable("other", "d2")], [legacy()],
            owner="321", include_legacy=False)
        self.assertEqual([x["id"] for x in result], ["notification:d1"])
        self.assertEqual(result[0]["actions"], ["stop"])

    def test_legacy_not_claimed_durable(self):
        result = aggregate_tasks([], [legacy()], owner="321", include_legacy=True)
        self.assertEqual(result[0]["status"], "RUNNING")
        self.assertEqual(result[0]["actions"], ["stop"])
        self.assertEqual(result[0]["persistence"], "process_local")
        self.assertIsNone(result[0]["progress"])

    def test_unsupported_legacy_actions_not_advertised(self):
        result = aggregate_tasks([], [legacy(status="interrupted", can_stop=False)],
            owner="321", include_legacy=True)
        self.assertEqual(result[0]["status"], "INTERRUPTED")
        self.assertEqual(result[0]["actions"], [])

    def test_authenticated_admin_api_lists_both_engines(self):
        client = app.app.test_client()
        with client.session_transaction() as session:
            session["logged_in"] = True
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_ID": "321"}), patch.object(
            app, "TELEGRAM_ADMIN_ID", "321"
        ), patch.object(app, "task_snapshots", return_value=[legacy()]), patch.object(
            app.app.extensions["notification_queue"], "list", return_value=[durable()]
        ):
            response = client.get("/api/miniapp/task_registry")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(x["id"] for x in response.json["tasks"]),
            {"notification:d1", "legacy:l1"})

    def test_anonymous_task_registry_is_denied(self):
        client = app.app.test_client()
        self.assertEqual(client.get("/api/miniapp/task_registry").status_code, 401)

    def test_telegram_tasks_uses_registry_with_source_specific_controls(self):
        bot = Mock()
        rows = aggregate_tasks([durable()], [legacy()], owner="321", include_legacy=True)
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_ID": "321"}), patch.dict(
            app.app.extensions, {"unified_tasks": Mock(return_value=rows)}
        ):
            self.assertTrue(telegram_command(bot, "321", "chat-1", "tasks", ""))
        self.assertIn("legacy:l1", bot.send_text.call_args.args[1])
        buttons = bot.send_text.call_args.kwargs["reply_markup"]["inline_keyboard"]
        self.assertTrue(all("legacy:" not in b["callback_data"] for row in buttons for b in row))

    def test_admin_can_request_legacy_stop_but_not_pause(self):
        bot = Mock()
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_ID": "321"}), patch.object(
            app, "cancel_one", return_value="stopping"
        ) as cancel:
            self.assertTrue(telegram_command(bot, "321", "chat-1", "task_stop", "legacy:l1"))
            cancel.assert_called_once()
            self.assertIn("stopping", bot.send_text.call_args.args[1])
            bot.reset_mock()
            self.assertTrue(telegram_command(bot, "321", "chat-1", "task_pause", "legacy:l1"))
            self.assertIn("không hỗ trợ", bot.send_text.call_args.args[1])
            self.assertEqual(cancel.call_count, 1)

    def test_non_admin_cannot_stop_legacy_task(self):
        bot = Mock()
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_ID": "321"}), patch.object(
            app, "cancel_one"
        ) as cancel:
            telegram_command(bot, "other", "chat-1", "task_stop", "legacy:l1")
            cancel.assert_not_called()
            self.assertIn("Không đủ quyền", bot.send_text.call_args.args[1])


if __name__ == "__main__":
    unittest.main()