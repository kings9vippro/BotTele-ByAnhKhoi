"""Web-only production authentication regressions."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "web-only-test-secret")

import app


class WebOnlyAuthTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_web_session_does_not_require_telegram_configuration(self):
        with self.client.session_transaction() as browser_session:
            browser_session["logged_in"] = True
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_ADMIN_ID": "", "ADMIN_PRINCIPAL_ID": "web-owner"}), \
                patch.object(app, "TELEGRAM_BOT_TOKEN", ""), patch.object(app, "TELEGRAM_ADMIN_ID", ""):
            response = self.client.get("/api/miniapp/session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["role"], "admin")
        self.assertEqual(response.json["owner"], "web-owner")
        self.assertEqual(response.json["auth_mode"], "web_session")
        self.assertTrue(response.json["csrf_token"])

    def test_production_web_session_requires_csrf_for_mutation(self):
        with patch.dict(os.environ, {"REQUIRE_WEB_CSRF": "1"}):
            with self.client.session_transaction() as browser_session:
                browser_session["logged_in"] = True
            rejected = self.client.post("/api/miniapp/oauth/start", json={"provider": "discord"})
            self.assertEqual(rejected.status_code, 403)
            self.assertEqual(rejected.json["code"], "csrf_invalid")
            session_response = self.client.get("/api/miniapp/session")
            accepted_by_boundary = self.client.post(
                "/api/miniapp/oauth/start",
                json={"provider": "discord"},
                headers={"X-CSRF-Token": session_response.json["csrf_token"]},
            )
            self.assertNotEqual(accepted_by_boundary.status_code, 403)

    def test_empty_password_never_authenticates_seeded_legacy_admin(self):
        with patch.object(app, "ACCESS_KEY", ""), patch.object(app, "DEFAULT_ADMIN_PASS", ""):
            response = self.client.post("/login", data={"password": ""})
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as browser_session:
            self.assertFalse(browser_session.get("logged_in"))


if __name__ == "__main__":
    unittest.main()
