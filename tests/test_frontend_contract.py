"""Static Mini App contracts for GLAZE control and realtime navigation."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_music_feature_is_fully_removed_from_ui(self):
        html = (ROOT / "templates" / "miniapp.html").read_text(encoding="utf-8")
        source = (ROOT / "static" / "control.js").read_text(encoding="utf-8")
        self.assertNotIn('id="music"', html)
        self.assertNotIn('home-open-music', html)
        self.assertNotIn("loadMusic", source)
        self.assertNotIn("music-player", html)
        self.assertNotIn("spotify", source.lower())
        self.assertFalse((ROOT / "static" / "viet_hits.json").exists())

    def test_miniapp_preserves_operational_sections(self):
        html = (ROOT / "templates" / "miniapp.html").read_text(encoding="utf-8")
        for marker in ("launch-account", "launch-boxes", "task-list", "event-list", "channels", "auth-gate"):
            self.assertIn(marker, html)

    def test_realtime_transport_has_bounded_recovery_contract(self):
        source = (ROOT / "static" / "control.js").read_text(encoding="utf-8")
        for marker in (
            "AbortController",
            "MiniAppError",
            "X-Request-ID",
            "STREAM_MAX_DELAY_MS",
            "STREAM_STALE_MS",
            "SDK_BOOT_WAIT_MS",
            "navigator.onLine",
            "RECONNECTING",
            "AUTH_REQUIRED",
            "SERVER_CONFIG",
            "Retry-After",
            "bootstrap",
            "checkStreamHealth",
        ):
            self.assertIn(marker, source)
        self.assertIn("Math.min(STREAM_MAX_DELAY_MS", source)
        self.assertIn("refreshController?.abort()", source)
        self.assertIn("terminalAuth", source)


if __name__ == "__main__":
    unittest.main()
