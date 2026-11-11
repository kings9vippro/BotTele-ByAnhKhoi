"""Frontend cache invalidation after deployment."""
import hashlib
import os
import unittest
from pathlib import Path

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "test-v6")
import app


class AssetRevisionTests(unittest.TestCase):
    def test_frontend_assets_versioned_by_content_hash(self):
        digest = hashlib.sha256()
        for name in ("control.js", "control.css", "compact-nav.css", "v11.css"):
            digest.update(name.encode("utf-8"))
            digest.update((Path(app.BASE_DIR) / "static" / name).read_bytes())
        expected = digest.hexdigest()[:16]
        self.assertEqual(app.miniapp_asset_revision(), expected)
        response = app.app.test_client().get("/miniapp")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        body = response.get_data(as_text=True)
        for name in ("control.js", "control.css", "compact-nav.css", "v11.css"):
            self.assertIn("/static/" + name + "?v=" + expected, body)
        self.assertNotIn("/static/control.js?v=2.0.0", body)


if __name__ == "__main__":
    unittest.main()