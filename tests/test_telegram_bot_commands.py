"""Telegram command-routing and lifecycle regressions. Version: 1.0.0."""
import os
import threading
import time
import unittest
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "test-only")

import app
import get_ck_im_zalo as telegram


class TelegramBotCommandTests(unittest.TestCase):
    @staticmethod
    def runner_shell():
        runner = telegram.DirectTelegramBotRunner.__new__(telegram.DirectTelegramBotRunner)
        runner.user_states = {}
        runner._sticker_states = {}
        runner.last_error = ""
        runner.send_text = Mock(return_value={"ok": True})
        return runner

    def test_task_retry_keeps_reserved_interactive_capacity(self):
        runner = self.runner_shell()
        runner._update_slots = threading.BoundedSemaphore(1)
        runner._interactive_update_slots = threading.BoundedSemaphore(1)
        runner.executor = Mock()
        runner.interactive_executor = Mock()
        runner.executor.submit.return_value = Future()
        runner.interactive_executor.submit.return_value = Future()

        self.assertTrue(runner._submit_update({"message": {"text": "slow work"}}))
        self.assertTrue(runner._submit_update({"message": {"text": "/task_retry task-1"}}))
        runner.interactive_executor.submit.assert_called_once()

    def test_menu_uses_one_text_request_without_welcome_media(self):
        runner = self.runner_shell()
        result = runner.send_welcome_video_menu(77, "<b>Menu</b>", reply_markup={"inline_keyboard": []})
        self.assertEqual(result, {"ok": True})
        runner.send_text.assert_called_once_with(
            77, "<b>Menu</b>", reply_to=None, reply_markup={"inline_keyboard": []}
        )

    def test_stopall_reports_failure_instead_of_fake_success(self):
        runner = self.runner_shell()
        update = {"message": {"chat": {"id": 1}, "from": {"id": 123, "first_name": "Fixture"}, "message_id": 2, "text": "/stopall"}}
        with patch.object(telegram, "is_telegram_user_authorized", return_value=True), \
             patch.object(telegram, "is_root_admin", return_value=True), \
             patch("control_plane.telegram_command", return_value=False), \
             patch.object(app, "stop_tasks_for_thread", side_effect=RuntimeError("fixture failure")):
            runner.process_update(update)

        response = runner.send_text.call_args.args[1]
        self.assertIn("Không thể xác nhận", response)
        self.assertNotIn("Đã dừng khẩn cấp", response)
        self.assertEqual(runner.last_error, "Telegram stop-all failed (RuntimeError)")

    def test_task_commands_are_forwarded_to_shared_control_plane(self):
        runner = self.runner_shell()
        update = {"message": {"chat": {"id": 77}, "from": {"id": 123, "first_name": "Fixture"}, "message_id": 4, "text": "/task_stop task-7"}}
        with patch.object(telegram, "is_telegram_user_authorized", return_value=True), \
             patch("control_plane.telegram_command", return_value=True) as command:
            runner.process_update(update)

        command.assert_called_once_with(runner, 123, 77, "task_stop", "task-7")
        runner.send_text.assert_not_called()

    def test_status_marks_stale_polling_as_degraded(self):
        worker = SimpleNamespace(is_alive=lambda: True)
        instance = SimpleNamespace(
            running=True,
            poll_thread=worker,
            last_poll_ok_ts=time.time() - 36,
            bot_username="fixture_bot",
            bot_id=1,
            last_error="Telegram polling rejected",
            consecutive_poll_failures=3,
            initialized=False,
        )
        with patch.object(telegram, "_BOT_INSTANCE", instance):
            status = telegram.get_telegram_bot_status()
        self.assertEqual(status["state"], "DEGRADED")
        self.assertGreater(status["last_poll_age_seconds"], 35)
        self.assertEqual(status["consecutive_poll_failures"], 3)

    def test_failed_initialization_has_a_safe_status(self):
        runner = self.runner_shell()
        runner.api_call = Mock(side_effect=[{"ok": True}, {"ok": False, "description": "private failure"}])
        self.assertFalse(runner.clear_webhook_and_init())
        self.assertEqual(runner.last_error, "telegram_getme_unavailable")

    def test_legacy_discord_token_import_is_not_reintroduced(self):
        source = (Path(__file__).resolve().parents[1] / "get_ck_im_zalo.py").read_text(encoding="utf-8")
        self.assertNotIn("saved_dc = sync_and_keepalive_tokens_to_db", source)


if __name__ == "__main__":
    unittest.main()
