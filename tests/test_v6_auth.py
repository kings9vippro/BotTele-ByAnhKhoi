"""V6 Telegram Mini App authentication and security regressions."""
import hashlib
import hmac
import json
import os
import time
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from urllib.parse import urlencode

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "v6-test-only")
import app


def signed_launch(uid=321, timestamp=None, token="v6-fixture-token"):
    fields = {
        "auth_date": str(int(time.time()) if timestamp is None else timestamp),
        "user": json.dumps({"id": uid}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class TelegramAuthV6Tests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "v6-fixture-token", "TELEGRAM_ADMIN_ID": "321"
        }))
        self.stack.enter_context(patch.object(app, "TELEGRAM_BOT_TOKEN", "v6-fixture-token"))
        self.stack.enter_context(patch.object(app, "TELEGRAM_ADMIN_ID", "321"))
        self.client = app.app.test_client()

    def request(self, launch):
        return self.client.get("/api/miniapp/session", headers={"X-Telegram-Init-Data": launch})

    def test_valid_signed_admin_launch_returns_admin_role(self):
        response = self.request(signed_launch())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["role"], "admin")
        self.assertEqual(response.json["owner"], "321")

    def test_modified_signature_is_rejected(self):
        launch = signed_launch().replace("321", "322", 1)
        response = self.request(launch)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "invalid_signature")

    def test_expired_launch_is_rejected(self):
        response = self.request(signed_launch(timestamp=int(time.time())-86500))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "expired_init_data")

    def test_future_launch_is_rejected(self):
        response = self.request(signed_launch(timestamp=int(time.time())+3600))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "invalid_init_data")

    def test_missing_init_data_requires_fresh_telegram_launch(self):
        response = self.client.get("/api/miniapp/session")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "missing_init_data")

    def test_missing_bot_token_is_configuration_error(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}), patch.object(app, "TELEGRAM_BOT_TOKEN", ""):
            response = self.request(signed_launch())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["code"], "server_configuration")
        self.assertNotIn("v6-fixture-token", response.get_data(as_text=True))

    def test_non_admin_without_delegation_is_forbidden(self):
        with patch.object(app, "db") as get_db:
            get_db.return_value.execute.return_value.fetchone.return_value = None
            response = self.request(signed_launch(uid=654))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json["code"], "unauthorized_account")

    def test_duplicate_init_data_fields_are_rejected(self):
        response = self.request(signed_launch()+"&auth_date=1")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "invalid_init_data")

    def test_unverified_request_cannot_read_protected_tasks(self):
        response = self.client.get("/api/miniapp/control")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("tasks", response.get_data(as_text=True))

    def test_bot_start_failure_is_logged_without_exception_message(self):
        with patch.dict(os.environ, {"DISABLE_TELEGRAM_BOT":"0"}), patch.object(
            app, "TELEGRAM_BOT_TOKEN", "v6-fixture-token"
        ), patch.object(app, "_TELEGRAM_BOT_RUNNER", None), patch(
            "get_ck_im_zalo.start_background_telegram_bot", side_effect=RuntimeError("sensitive-query-material")
        ):
            with self.assertLogs("glaze_app", level="ERROR") as recorded:
                app.ensure_telegram_bot_started()
        output = " ".join(recorded.output)
        self.assertIn("RuntimeError", output)
        self.assertNotIn("sensitive-query-material", output)


if __name__ == "__main__":
    unittest.main()