"""Regression tests: Render can be healthy while Telegram polling is stopped.

All credentials here are synthetic; provider calls are fully mocked.
"""
import os
import unittest
from unittest.mock import patch, Mock

os.environ.setdefault("DISABLE_TELEGRAM_BOT","1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS","1")
os.environ.setdefault("SECRET_KEY","test-diagnostics-only")
import app
from get_ck_im_zalo import DirectTelegramBotRunner


class TelegramBootDiagnostics(unittest.TestCase):
    def test_missing_token_is_explicit(self):
        with patch.object(app, "TELEGRAM_BOT_TOKEN", ""):
            with patch.dict(os.environ, {"DISABLE_TELEGRAM_BOT":"0","TELEGRAM_ADMIN_ID":"321"}):
                self.assertEqual(app.telegram_boot_readiness(), "missing_token")

    def test_disabled_bot_is_not_reported_as_running(self):
        with patch.object(app, "TELEGRAM_BOT_TOKEN", "not-a-real-token"):
            with patch.dict(os.environ, {"DISABLE_TELEGRAM_BOT":"1"}):
                self.assertEqual(app.telegram_boot_readiness(), "disabled")

    def test_boot_gate_requires_administrator_id(self):
        with patch.object(app, "TELEGRAM_BOT_TOKEN", "not-a-real-token"):
            with patch.object(app, "TELEGRAM_ADMIN_ID", ""):
                with patch.dict(os.environ, {"DISABLE_TELEGRAM_BOT":"0"}):
                    self.assertEqual(app.telegram_boot_readiness(), "missing_admin_id")

    def test_getme_401_is_classified_without_echoing_message(self):
        bot=object.__new__(DirectTelegramBotRunner)
        bot.last_error=""
        bot.api_call=Mock(side_effect=[
            {"ok":True}, {"ok":False,"error_code":401,"description":"THIS_COULD_CONTAIN_A_SECRET"}
        ])
        with self.assertLogs("get_ck_im_zalo",level="ERROR") as logs:
            self.assertFalse(bot.clear_webhook_and_init())
        self.assertEqual(bot.last_error, "telegram_getme_auth_rejected")
        self.assertNotIn("THIS_COULD_CONTAIN_A_SECRET", "\\n".join(logs.output))

if __name__=="__main__":
    unittest.main()