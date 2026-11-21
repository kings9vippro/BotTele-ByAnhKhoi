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

    def test_web_session_filters_tasks_by_zalo_account_without_telegram(self):
        with self.client.session_transaction() as browser_session:
            browser_session["logged_in"] = True
        accounts = [{"id": 7}, {"id": 8}]
        tasks = [
            {"id": "task-7", "status": "running", "account_ids": [7]},
            {"id": "task-8", "status": "running", "account_ids": [8]},
        ]
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_ID": "", "ADMIN_PRINCIPAL_ID": "web-owner"}), \
                patch.object(app, "get_all_accounts_from_ram", return_value=accounts), \
                patch.object(app, "task_snapshots", return_value=tasks):
            response = self.client.get("/api/miniapp/task_registry?account_id=7")
            denied = self.client.get("/api/miniapp/task_registry?account_id=9")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([task["id"] for task in response.json["tasks"]], ["legacy:task-7"])
        self.assertEqual(denied.status_code, 403)

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

    def test_repository_password_hash_authenticates_without_render_password(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            password = "local fixture password"
            hashed = app.hash_password_secure(password)
            path = Path(directory) / "admin_password.hash"
            path.write_text(hashed + "\n", encoding="ascii")
            with patch.object(app, "ADMIN_PASSWORD_HASH_PATH", str(path)), \
                    patch.object(app, "ACCESS_KEY", ""), \
                    patch.object(app, "DEFAULT_ADMIN_PASS", ""):
                denied = self.client.post("/login", data={"password": "wrong"})
                accepted = self.client.post("/login", data={"password": password})
        self.assertEqual(denied.status_code, 200)
        self.assertEqual(accepted.status_code, 302)
        with self.client.session_transaction() as browser_session:
            self.assertTrue(browser_session.get("logged_in"))

    def test_empty_password_never_authenticates_seeded_legacy_admin(self):
        with patch.object(app, "ACCESS_KEY", ""), patch.object(app, "DEFAULT_ADMIN_PASS", ""):
            response = self.client.post("/login", data={"password": ""})
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as browser_session:
            self.assertFalse(browser_session.get("logged_in"))


if __name__ == "__main__":
    unittest.main()
