import io
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("SECRET_KEY", "test-only")
import app


class MiniAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def test_qr_start_and_status_use_manager_without_leaking_credentials(self):
        with patch.object(app.ZaloQRLoginManager, "start_qr_session", return_value={"ok": True, "session_id": "abc", "status": "generating", "cookies": {"secret": "private"}}):
            result = self.client.post("/api/miniapp/start_qr")
        self.assertEqual(result.json["session_id"], "abc")
        self.assertNotIn("cookies", result.json)
        with patch.object(app.ZaloQRLoginManager, "get_session_status", return_value={"ok": True, "status": "waiting_scan", "qr_base64": "image", "cookies": {"secret": "private"}}):
            result = self.client.get("/api/miniapp/qr_status/abc")
        self.assertEqual(result.json["qr_base64"], "image")
        self.assertNotIn("cookies", result.json)

    def test_oversized_upload_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "UPLOAD_DIR", folder):
            path = os.path.join(folder, "existing.txt")
            with open(path, "wb") as output:
                output.write(b"original")
            response = self.client.post("/api/miniapp/upload_file", data={"file": (io.BytesIO(b"x" * (app.MAX_MINIAPP_TEXT_BYTES + 1)), "existing.txt")})
            self.assertEqual(response.status_code, 413)
            with open(path, "rb") as existing:
                self.assertEqual(existing.read(), b"original")

    def test_miniapp_api_requires_authentication(self):
        client = app.app.test_client()
        self.assertEqual(client.get("/api/miniapp/qr_status/abc").status_code, 401)

    def test_sticker_wait_is_scoped_and_expires(self):
        engine = app.ZaloStickerMakerEngine
        with engine._PENDING_LOCK:
            engine._PENDING_IMAGES.clear()
        with patch.object(app.time, "monotonic", return_value=100):
            engine.wait_for_image(1, "group", "owner")
            self.assertFalse(engine.consume_image_wait(1, "group", "other"))
            self.assertFalse(engine.consume_image_wait(2, "group", "owner"))
            self.assertFalse(engine.consume_image_wait(1, "other", "owner"))
            self.assertTrue(engine.consume_image_wait(1, "group", "owner"))
            self.assertFalse(engine.consume_image_wait(1, "group", "owner"))
            engine.wait_for_image(1, "group", "owner")
        with patch.object(app.time, "monotonic", return_value=221):
            self.assertFalse(engine.consume_image_wait(1, "group", "owner"))


if __name__ == "__main__":
    unittest.main()
