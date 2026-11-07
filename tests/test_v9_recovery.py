"""V9 secure token, Telegram command feedback, multi-cookie Zalo monitor regressions."""
import os
import time
import unittest
from concurrent.futures import Future
from unittest.mock import Mock, patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "v9-regression-test")
import app
from bot_settings import load_bot_token, BotSecretConfigurationError
from command_metrics import record_command, snapshot as command_snapshot
from control_plane import telegram_command


class TokenSecretTests(unittest.TestCase):
    def test_secret_environment_preserves_single_supported_setup(self):
        fake = "only-a-synthetic-token"
        self.assertEqual(load_bot_token({"TELEGRAM_BOT_TOKEN": fake}), fake)

    def test_old_encrypted_only_configuration_does_not_create_a_second_token(self):
        self.assertEqual(load_bot_token({
            "TELEGRAM_BOT_TOKEN_ENCRYPTED": "obsolete-placeholder",
            "TELEGRAM_BOT_TOKEN_KEY": "obsolete-placeholder",
        }), "")

    def test_primary_env_token_is_used_when_legacy_keys_remain(self):
        actual = load_bot_token({
            "TELEGRAM_BOT_TOKEN": "fixture",
            "TELEGRAM_BOT_TOKEN_ENCRYPTED": "legacy",
            "TELEGRAM_BOT_TOKEN_KEY": "legacy",
        })
        self.assertEqual(actual, "fixture")



class TelegramResponseTests(unittest.TestCase):
    def test_tasks_use_actual_linebreaks_not_backslash_n(self):
        bot = Mock()
        with patch.dict(app.app.extensions, {"unified_tasks": Mock(return_value=[])}):
            self.assertTrue(telegram_command(bot, "321", "chat", "tasks", ""))
        msg = bot.send_text.call_args.args[1]
        self.assertIn("\n", msg)
        self.assertNotIn("\\n", msg)
        self.assertIn("RAM", msg)

    def test_performance_is_readable_and_distinguishes_no_samples(self):
        bot = Mock()
        data = {"workers": 5, "counts": {}, "api_latency_seconds": None}
        with patch.dict(app.app.extensions, {"control_snapshot": Mock(return_value=data)}):
            self.assertTrue(telegram_command(bot, "321", "chat", "performance", ""))
        msg = bot.send_text.call_args.args[1]
        self.assertIn("HIỆU SUẤT", msg)
        self.assertIn("Chưa có mẫu", msg)
        self.assertNotIn('"workers"', msg)
        self.assertNotIn("\\n", msg)

    def test_missing_send_multi_arguments_return_exact_usage(self):
        bot = Mock()
        queue = app.app.extensions["notification_queue"]
        with patch.object(queue, "submit_many") as submit:
            self.assertTrue(telegram_command(bot, "321", "chat", "send_multi", ""))
        self.assertIn("/send_multi", bot.send_text.call_args.args[1])
        submit.assert_not_called()

    def test_watch_status_never_mixes_selected_cookie(self):
        bot = Mock()
        watches = [
            {"acc_id": 7,"box_id": "42","box_name": "Cookie Seven",
             "last_message_at_label": "22:03","status":"monitoring",
             "silence_seconds":5.0, "timeout_sec":90.0, "last_sync_at":None},
            {"acc_id": 8,"box_id": "42","box_name": "Cookie Eight",
             "last_message_at_label": "22:01","status":"silent",
             "silence_seconds":100.0, "timeout_sec":90.0, "last_sync_at":None},
        ]
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_ID": "321"}), patch.object(
            app.CanhTreoWatchdogEngine,"get_watched_boxes", return_value=watches
        ):
            self.assertTrue(telegram_command(bot,"321","chat","watch_status","7"))
        response=bot.send_text.call_args.args[1]
        self.assertIn("Cookie Seven",response)
        self.assertNotIn("Cookie Eight",response)

    def test_watch_status_rejects_non_admin(self):
        bot=Mock()
        with patch.dict(os.environ,{"TELEGRAM_ADMIN_ID":"321"}):
            telegram_command(bot,"999","chat","watch_status","7")
        self.assertIn("Chỉ quản trị viên",bot.send_text.call_args.args[1])

    def test_command_metrics_exclude_sensitive_values(self):
        record_command("/performance", 65.22)
        record_command("/menu", 12.0)
        record_command(".menu", 15.0)
        result=command_snapshot()
        self.assertGreaterEqual(result["sample_count"],2)
        self.assertIn("p50_handler_ms",result)
        self.assertGreaterEqual(result["zalo"]["count"],1)
        self.assertNotIn("user",result)
        self.assertNotIn("token",str(result).lower())


class ZaloWatchIsolationTests(unittest.TestCase):
    def test_two_cookies_same_group_do_not_overwrite(self):
        watcher=app.CanhTreoWatchdogEngine
        with patch.object(watcher,"_WATCHED_BOXES",{}), patch.object(
            watcher,"ensure_daemon_started"
        ), patch.object(watcher,"_schedule_sync",return_value=True):
            one=watcher.enable_watch("42",box_name="Group 7",acc_id=7)
            two=watcher.enable_watch("42",box_name="Group 8",acc_id=8)
            self.assertEqual(len(watcher._WATCHED_BOXES),2)
            self.assertEqual({str(w["acc_id"]) for w in watcher.get_watched_boxes()},{"7","8"})
            watcher.record_incoming_message("42","a","Alice","message A",
                msg_id="m1", account_id=7)
            record_7=watcher._WATCHED_BOXES["7:42"]
            record_8=watcher._WATCHED_BOXES["8:42"]
            self.assertEqual(record_7["last_msg_id"],"m1")
            self.assertEqual(record_8["last_msg_id"],"")
            self.assertEqual(watcher.disable_watch("42",acc_id=7),1)
            self.assertIn("8:42",watcher._WATCHED_BOXES)

    def test_ambiguous_legacy_stop_cannot_delete_all_cookies(self):
        watcher=app.CanhTreoWatchdogEngine
        with patch.object(watcher,"_WATCHED_BOXES",{
            "7:42":{"acc_id":7,"box_id":"42"},
            "8:42":{"acc_id":8,"box_id":"42"}
        }):
            self.assertEqual(watcher.disable_watch("42"),0)
            self.assertEqual(len(watcher._WATCHED_BOXES),2)

    def test_restarting_same_watch_keeps_last_real_message_time(self):
        watcher=app.CanhTreoWatchdogEngine
        with patch.object(watcher,"_WATCHED_BOXES",{}),patch.object(
            watcher,"ensure_daemon_started"
        ),patch.object(watcher,"_schedule_sync",return_value=True):
            watcher.enable_watch("42",acc_id=7)
            watcher.record_incoming_message("42","u","User","hello",
                msg_id="m1",account_id=7)
            old=watcher._WATCHED_BOXES["7:42"]["last_activity_ts"]
            watcher.enable_watch("42",acc_id=7)
            state=watcher._WATCHED_BOXES["7:42"]
            self.assertEqual(state["last_msg_id"],"m1")
            self.assertEqual(state["last_activity_ts"],old)

    def test_watch_status_exposes_sync_freshness_not_participants(self):
        watcher=app.CanhTreoWatchdogEngine
        row={"box_id":"42","acc_id":7,"platform":"zalo","enabled":True,
             "last_msg_id":"m","last_activity_ts":time.time()-120,
             "timeout_sec":90,"last_sync_at":time.time()-75,
             "last_sync_ok":False,"participants":{"secret-user":"do-not-leak"}}
        with patch.object(watcher,"_WATCHED_BOXES",{"7:42":row}):
            result=watcher.get_watched_boxes()[0]
        self.assertFalse(result["last_sync_ok"])
        self.assertGreater(result["last_sync_age_seconds"],70)
        self.assertNotIn("participants",result)


if __name__=="__main__": unittest.main()