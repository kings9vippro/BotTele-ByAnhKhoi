"""Telegram Mini App initData validation regressions."""
import hashlib
import hmac
import json
from urllib.parse import urlencode
import unittest

from miniapp_oauth import TelegramInitDataError, validate_telegram_webapp_init_data


TOKEN = "fixture-telegram-token"
NOW = 1_700_000_000


def signed_payload(*, user_id=123, auth_date=NOW, extra=None):
    values = {
        "auth_date": str(auth_date),
        "user": json.dumps({"id": user_id, "first_name": "Fixture"}, separators=(",", ":")),
    }
    values.update(extra or {})
    data_check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


class TelegramInitDataTests(unittest.TestCase):
    def test_accepts_current_correctly_signed_payload(self):
        result = validate_telegram_webapp_init_data(signed_payload(), TOKEN, now=NOW)
        self.assertEqual(result["user"]["id"], 123)
        self.assertEqual(result["auth_date"], NOW)

    def test_rejects_invalid_signature(self):
        # Preserve the payload shape and hash length: this must exercise the
        # cryptographic comparison rather than a superficial parser check.
        raw = signed_payload().replace("Fixture", "Fjxture", 1)
        with self.assertRaisesRegex(TelegramInitDataError, "invalid_signature"):
            validate_telegram_webapp_init_data(raw, TOKEN, now=NOW)

    def test_rejects_expired_and_future_launches(self):
        with self.assertRaisesRegex(TelegramInitDataError, "expired_init_data"):
            validate_telegram_webapp_init_data(signed_payload(auth_date=NOW - 86401), TOKEN, now=NOW)
        with self.assertRaisesRegex(TelegramInitDataError, "clock_skew"):
            validate_telegram_webapp_init_data(signed_payload(auth_date=NOW + 31), TOKEN, now=NOW)

    def test_rejects_missing_server_token_and_missing_launch_data(self):
        with self.assertRaisesRegex(TelegramInitDataError, "server_misconfigured"):
            validate_telegram_webapp_init_data(signed_payload(), "", now=NOW)
        with self.assertRaisesRegex(TelegramInitDataError, "missing_init_data"):
            validate_telegram_webapp_init_data("", TOKEN, now=NOW)

    def test_rejects_duplicate_pairs_before_signature_validation(self):
        duplicate = signed_payload() + "&auth_date=" + str(NOW)
        with self.assertRaisesRegex(TelegramInitDataError, "malformed_init_data"):
            validate_telegram_webapp_init_data(duplicate, TOKEN, now=NOW)


if __name__ == "__main__":
    unittest.main()
