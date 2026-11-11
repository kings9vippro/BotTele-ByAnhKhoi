"""V11 regression: per-cookie task isolation and smaller read footprint."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "v11-test-only")
import app


class CompactV11Tests(unittest.TestCase):
    def test_compact_ui_preserves_all_functional_pages(self):
        template=(Path(__file__).resolve().parents[1] / "templates" / "miniapp.html").read_text()
        for section in ("home","accounts","discord","zalo","tasks","activity","music","settings"):
            self.assertIn('id="'+section+'"', template)
        self.assertIn('id="auth-gate"',template)
        self.assertIn('id="account-open-zalo"',template)
        self.assertIn('id="account-open-discord"',template)
        self.assertIn('id="task-account-filter"',template)

    def test_asset_fingerprint_includes_v11_stylesheet(self):
        import hashlib
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        self.assertIn('"v11.css"',(root/"glaze_app.py").read_text())
        self.assertIn('/static/v11.css', (root/"templates/miniapp.html").read_text())

    def test_source_never_hardcodes_a_bot_token(self):
        source=(Path(__file__).resolve().parents[1] / "bot_settings.py").read_text()
        self.assertIn("TELEGRAM_BOT_TOKEN = load_bot_token()",source)
        self.assertNotIn("load_bot_token(\"",source)

    def test_telegram_auth_recovery_blocks_private_dashboard(self):
        js=(Path(__file__).resolve().parents[1] / "static" / "control.js").read_text()
        self.assertIn("showAuthGate('AUTH_REQUIRED','missing')",js)
        self.assertIn("document.body.classList.add('auth-locked')",js)

    def test_account_scoped_registry_does_not_read_unrelated_discord_tasks(self):
        from control_plane import register
        from flask import Flask
        import sqlite3, tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{"TELEGRAM_ADMIN_ID":"321"}):
            path=Path(d)/"tasks.sqlite"
            webapp=Flask(__name__)
            webapp.secret_key="v11-local"
            def db():
                c=sqlite3.connect(str(path));c.row_factory=sqlite3.Row;return c
            register(webapp,db,lambda:"321")
            q=webapp.extensions["notification_queue"]
            try:
                with patch.object(q,"list_all_for_root",side_effect=AssertionError("unrelated notification scan")):
                    with patch("get_ck_im_zalo.get_user_visible_accounts",return_value=[{"id":1}]):
                        with patch.object(app,"task_snapshots",return_value=[]):
                            response=webapp.test_client().get("/api/miniapp/task_registry?account_id=1")
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json["tasks"],[])
            finally:q.close()