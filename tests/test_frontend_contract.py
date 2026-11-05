"""Static Mini App contract checks. Author: Dev Anh Khôi. Version: 1.0.0."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_spotify_catalog_is_small_curated_and_safe_to_render(self):
        payload = json.loads((ROOT / "static" / "viet_hits.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["playlist_id"], "37i9dQZF1E8LGuRBNXhjWF")
        self.assertEqual(payload["playlist_status"], "READY")
        self.assertEqual(payload["total_items"], 50)
        self.assertEqual(len(payload["tracks"]), 20)
        self.assertEqual(len({track["url"] for track in payload["tracks"]}), 20)
        self.assertTrue(payload["playlist_url"].startswith("https://open.spotify.com/playlist/"))
        self.assertTrue(payload["embed_url"].startswith("https://open.spotify.com/embed/playlist/"))
        for track in payload["tracks"]:
            self.assertTrue(track["name"].strip())
            self.assertTrue(track["artist"].strip())
            self.assertTrue(track["url"].startswith("https://open.spotify.com/track/"))

    def test_miniapp_contains_account_box_task_and_music_surfaces(self):
        html = (ROOT / "templates" / "miniapp.html").read_text(encoding="utf-8")
        for marker in ("launch-account", "launch-boxes", "task-list", "music-tracks", "music-player"):
            self.assertIn(marker, html)

    def test_realtime_transport_has_bounded_recovery_contract(self):
        source = (ROOT / "static" / "control.js").read_text(encoding="utf-8")
        for marker in (
            "AbortController",
            "X-Request-ID",
            "STREAM_MAX_DELAY_MS",
            "STREAM_STALE_MS",
            "navigator.onLine",
            "RECONNECTING",
            "checkStreamHealth",
        ):
            self.assertIn(marker, source)
        self.assertIn("Math.min(STREAM_MAX_DELAY_MS", source)
        self.assertIn("refreshController?.abort()", source)


if __name__ == "__main__":
    unittest.main()
