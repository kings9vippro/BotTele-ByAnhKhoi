"""Static Mini App contract checks. Author: Dev Anh Khôi. Version: 1.0.0."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_spotify_catalog_is_small_curated_and_safe_to_render(self):
        payload = json.loads((ROOT / "static" / "viet_hits.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload["tracks"]), 10)
        self.assertEqual(len({track["url"] for track in payload["tracks"]}), 10)
        self.assertTrue(payload["playlist_url"].startswith("https://open.spotify.com/playlist/"))
        for track in payload["tracks"]:
            self.assertTrue(track["name"].strip())
            self.assertTrue(track["artist"].strip())
            self.assertTrue(track["url"].startswith("https://open.spotify.com/track/"))

    def test_miniapp_contains_account_box_task_and_music_surfaces(self):
        html = (ROOT / "templates" / "miniapp.html").read_text(encoding="utf-8")
        for marker in ("launch-account", "launch-boxes", "task-list", "music-tracks", "music-player"):
            self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main()
