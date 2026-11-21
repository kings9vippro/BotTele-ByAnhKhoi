"""Regression contracts for the Yanbi Studio UI and Spotify preview handoff."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class YanbiStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "templates" / "miniapp.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "yanbi.css").read_text(encoding="utf-8")
        cls.js = (ROOT / "static" / "control.js").read_text(encoding="utf-8")

    def test_owner_is_visible_on_header_and_settings(self):
        self.assertIn('Owner · Yanbi', self.html)
        self.assertIn('class="brand-owner"', self.html)
        self.assertIn('class="owner-credit"', self.html)

    def test_all_quick_links_keep_native_page_routes(self):
        for identifier in ('home-open-accounts', 'home-open-tasks',
                           'home-open-zalo', 'home-open-discord',
                           'home-open-music', 'home-open-activity'):
            self.assertIn('id="' + identifier + '"', self.html)
            self.assertIn("'" + identifier + "'", self.js)

    def test_spotify_embed_preserves_drm_and_uses_full_track_links(self):
        self.assertIn("encrypted-media", self.js)
        self.assertIn("track.url", self.js)
        self.assertIn("track-open", self.js)
        self.assertIn("Nghe đầy đủ", self.js)
        self.assertIn("Nghe trọn playlist trên Spotify", self.html)
        self.assertIn("khoảng 30 giây", self.html)
        self.assertIn("music-actions > [hidden]{display:none!important}", self.css)

    def test_login_retry_supports_web_cookie_sessions(self):
        self.assertIn("Web sessions authenticate using cookies", self.js)
        self.assertNotIn("if(!(tg?.initData||launch)){showAuthGate", self.js)

    def test_motion_and_mobile_accessibility_are_present(self):
        for marker in ("prefers-reduced-motion:reduce", "focus-visible",
                       "max-width:520px", "yanbi-reveal", "backdrop-filter"):
            self.assertIn(marker, self.css)


if __name__ == "__main__":
    unittest.main()
