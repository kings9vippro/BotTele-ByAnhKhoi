"""Provider integration boundary regressions. Author: Dev Anh Khôi. Version: 1.0.0."""
import json
from pathlib import Path
from urllib.parse import urlsplit
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAYLIST_ID = "37i9dQZF1E8LGuRBNXhjWF"


class IntegrationContractTests(unittest.TestCase):
    def test_spotify_catalog_targets_verified_official_playlist(self):
        payload = json.loads((ROOT / "static" / "viet_hits.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["playlist_id"], PLAYLIST_ID)
        self.assertEqual(urlsplit(payload["playlist_url"]).netloc, "open.spotify.com")
        self.assertEqual(urlsplit(payload["playlist_url"]).path, f"/playlist/{PLAYLIST_ID}")
        self.assertEqual(urlsplit(payload["embed_url"]).path, f"/embed/playlist/{PLAYLIST_ID}")
        self.assertEqual(payload["playlist_status"], "READY")
        self.assertEqual(payload["total_items"], 50)
        self.assertGreaterEqual(len(payload["tracks"]), 10)
        for track in payload["tracks"]:
            parsed = urlsplit(track["url"])
            self.assertEqual(parsed.netloc, "open.spotify.com")
            self.assertTrue(parsed.path.startswith("/track/"))

    def test_zalo_login_has_no_third_party_credential_fallback(self):
        source = (ROOT / "glaze_app.py").read_text(encoding="utf-8")
        self.assertNotIn("lengocanh.vercel.app", source)
        self.assertNotIn("3app_vip/bot.py", source)


if __name__ == "__main__":
    unittest.main()
