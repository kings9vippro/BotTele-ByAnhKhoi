"""Aurora UI regression: consistent navigation, owner identity and accessibility."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class YanbiStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "templates" / "miniapp.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "yanbi.css").read_text(encoding="utf-8")
        cls.js = (ROOT / "static" / "control.js").read_text(encoding="utf-8")

    def test_owner_on_header_and_settings(self):
        self.assertIn("YANBI", self.html)
        self.assertIn("Owner · Yanbi", self.html)
        self.assertIn('class="brand-owner"', self.html)
        self.assertIn('class="owner-credit"', self.html)
        self.assertIn('class="brand-wordmark"', self.html)

    def test_quick_links_keep_all_existing_routes(self):
        for identifier in ('home-open-accounts', 'home-open-tasks',
                           'home-open-zalo', 'home-open-discord',
                           'home-open-activity'):
            self.assertIn('id="' + identifier + '"', self.html)
            self.assertIn("'" + identifier + "'", self.js)

    def test_top_tabs_and_bottom_nav_without_music(self):
        self.assertIn('role="tablist"', self.html)
        self.assertIn("for(const key of ['home','accounts','discord','tasks','settings'])", self.js)
        self.assertIn("activity:'Nhật ký'", self.js)
        self.assertNotIn("music:'Âm nhạc'", self.js)
        self.assertIn("body.yanbi #tabs", self.css)
        self.assertIn("clip-path:none!important", self.css)

    def test_remove_oversized_diamond_and_logo_tiles(self):
        self.assertNotIn('class="auth-icon"', self.html)
        self.assertNotIn('<div class="brand"><img', self.html)
        self.assertIn('.login-card .login-mark{display:none!important}', self.css)
        self.assertIn("auth-led", self.html)

    def test_effects_and_mobile_accessibility(self):
        for marker in ("prefers-reduced-motion:reduce", "focus-visible",
                       "max-width:520px", "aurora-enter", "aurora-drift",
                       "backdrop-filter", "scroll-snap-type:x mandatory"):
            self.assertIn(marker, self.css)

    def test_login_retry_supports_cookie_sessions(self):
        self.assertIn("Web sessions authenticate using cookies", self.js)
        self.assertNotIn("if(!(tg?.initData||launch)){showAuthGate", self.js)


if __name__ == "__main__":
    unittest.main()
