"""Provider integration boundary regression checks."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class IntegrationContractTests(unittest.TestCase):
    def test_removed_music_does_not_leave_preview_asset_or_embed(self):
        html = (ROOT / "templates" / "miniapp.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "control.js").read_text(encoding="utf-8")
        self.assertFalse((ROOT / "static" / "viet_hits.json").exists())
        self.assertNotIn("open.spotify.com/embed/", js)
        self.assertNotIn("id=\"music-play\"", html)

    def test_zalo_login_has_no_third_party_credential_fallback(self):
        source = (ROOT / "glaze_app.py").read_text(encoding="utf-8")
        self.assertNotIn("lengocanh.vercel.app", source)
        self.assertNotIn("3app_vip/bot.py", source)


if __name__ == "__main__":
    unittest.main()
