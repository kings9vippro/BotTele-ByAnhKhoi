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

    def test_single_dock_and_more_menu_without_music(self):
        self.assertNotIn('id="tabs"', self.html)
        self.assertIn('id="more-menu"', self.html)
        self.assertIn("for(const key of ['home','accounts','tasks','more'])", self.js)
        self.assertIn("for(const key of ['discord','zalo','activity','settings'])", self.js)
        self.assertIn("activity:'Nhật ký'", self.js)
        self.assertNotIn("music:'Âm nhạc'", self.js)
        self.assertIn("grid-template-columns:repeat(4,minmax(0,1fr))!important", self.css)
        self.assertIn("body.yanbi #more-menu[hidden]", self.css)

    def test_authentication_does_not_wait_for_every_service(self):
        self.assertIn("sessionValidated=true", self.js)
        self.assertIn("hideAuthGate();", self.js)
        self.assertIn("Promise.allSettled(jobs.map(job=>loadDashboardJob(job,options)))", self.js)
        self.assertIn("setConnection('PARTIAL')", self.js)
        self.assertIn("csrfToken=viewer.csrf_token", self.js)

    def test_remove_oversized_tiles_and_keep_compact_portrait(self):
        self.assertNotIn('class="auth-icon"', self.html)
        self.assertIn('class="brand-avatar"', self.html)
        self.assertIn('width="38" height="38"', self.html)
        self.assertIn('flex:0 0 38px', self.css)
        self.assertIn('.login-card .login-mark{display:none!important}', self.css)
        self.assertIn("auth-led", self.html)

    def test_effects_and_mobile_accessibility(self):
        for marker in ("prefers-reduced-motion:reduce", "focus-visible",
                       "max-width:520px", "aurora-enter", "aurora-drift",
                       "backdrop-filter", "scroll-snap-type:x mandatory", "scroll-reveal"):
            self.assertIn(marker, self.css)
        self.assertIn("IntersectionObserver", self.js)

    def test_kinetic_letters_and_flowers_are_visual_only(self):
        self.assertIn('id="motion"', self.html)
        self.assertIn('id="motion-note"', self.html)
        self.assertIn("function buildKineticTitle(", self.js)
        self.assertIn("function buildFlowerField(", self.js)
        self.assertIn("function replayKineticTitle(", self.js)
        self.assertIn("glaze-kinetic-letter", self.css)
        self.assertIn("glaze-flower-field", self.css)
        self.assertIn("@keyframes glaze-character-pop", self.css)
        self.assertIn("@keyframes glaze-petal-float", self.css)
        self.assertIn('pointer-events:none', self.css)
        self.assertIn("prefers-reduced-motion:reduce", self.css)

    def test_previous_zalo_qr_contract_is_restored(self):
        self.assertIn("api('start_qr',{})", self.js)
        self.assertIn("api('qr_status/'+encodeURIComponent(result.session_id))", self.js)
        self.assertIn('id="qr-image"', self.html)
        self.assertNotIn("api('cancel_qr'", self.js)
        self.assertNotIn('id="qr-cancel"', self.html)

    def test_unauthenticated_user_sees_no_navigation_or_private_pages(self):
        self.assertIn("body.yanbi.auth-locked #pages", self.css)
        self.assertIn("body.yanbi.auth-locked #more-menu", self.css)
        self.assertIn("body.yanbi.auth-locked #bottom", self.css)
        self.assertIn("body.yanbi.auth-locked #error{display:none!important}", self.css)

    def test_login_retry_supports_cookie_sessions(self):
        self.assertIn("Web sessions authenticate using cookies", self.js)
        self.assertNotIn("if(!(tg?.initData||launch)){showAuthGate", self.js)


if __name__ == "__main__":
    unittest.main()
