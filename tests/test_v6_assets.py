"""Frontend cache invalidation after deployment."""
import hashlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "test-v6")
import app


class AssetRevisionTests(unittest.TestCase):
    def test_frontend_assets_versioned_by_content_hash(self):
        digest = hashlib.sha256()
        for name in ("control.js", "control.css", "compact-nav.css", "v11.css", "yanbi.css", "yanbi-logo.webp", "yanbi-background.webp"):
            digest.update(name.encode("utf-8"))
            digest.update((Path(app.BASE_DIR) / "static" / name).read_bytes())
        expected = digest.hexdigest()[:16]
        self.assertEqual(app.miniapp_asset_revision(), expected)
        response = app.app.test_client().get("/miniapp")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        body = response.get_data(as_text=True)
        for name in ("control.js", "control.css", "compact-nav.css", "v11.css", "yanbi.css", "yanbi-logo.webp"):
            self.assertIn("/static/" + name + "?v=" + expected, body)
        self.assertNotIn("/static/control.js?v=2.0.0", body)

    def test_dashboard_and_login_shells_render_without_runtime_data(self):
        client = app.app.test_client()
        with patch.object(app, "get_all_accounts_from_ram", side_effect=AssertionError("account lock")), \
                patch.object(app, "get_setting", side_effect=AssertionError("database access")), \
                patch.object(app.CanhTreoWatchdogEngine, "get_watched_boxes", side_effect=AssertionError("watch lock")):
            for route in ("/", "/miniapp", "/login"):
                with self.subTest(route=route):
                    response = client.get(route)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('/static/yanbi-logo.webp?v=', response.text)
                    self.assertIn('/static/yanbi.css?v=', response.text)
            self.assertIn('id="startup-panel"', client.get("/").text)
            self.assertIn('href="/login"', client.get("/").text)


if __name__ == "__main__":
    unittest.main()