import io
import os
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock

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

    def test_sticker_preserves_signed_url_and_closes_download(self):
        response = Mock(status_code=200, headers={"Content-Type": "image/png"})
        response.iter_content.return_value = [b"image-data"]
        session = Mock()
        session.get.return_value = response
        url = "https://cdn.example/photo?signature=abc&part=1&"
        with patch.object(app.requests, "Session") as factory:
            factory.return_value.__enter__.return_value = session
            data, _ = app.ZaloStickerMakerEngine.fetch_media_from_url_or_path(url)
        self.assertEqual(data, b"image-data")
        self.assertEqual(session.get.call_args.args[0], url)
        response.close.assert_called_once()

    def test_sticker_conversion_and_delivery_are_separate(self):
        from PIL import Image
        buffer = io.BytesIO()
        Image.new("RGB", (100, 120), "red").save(buffer, format="PNG")
        client = Mock()
        client.send_custom_sticker_media.return_value = True
        engine = app.ZaloStickerMakerEngine
        with patch.object(engine, "fetch_media_from_url_or_path", return_value=(buffer.getvalue(), "image.png")):
            result = engine.create_and_send_waiting_image(client, "123", False, {"url": "https://example/image"})
        self.assertTrue(result["ok"])
        self.assertFalse(client.send_custom_sticker_media.call_args.kwargs["is_group"])
        self.assertTrue(client.send_custom_sticker_media.call_args.kwargs["png_bytes"].startswith(b"\x89PNG"))
        with patch.object(engine, "create_sharp_image_sticker", return_value={"ok": False}):
            result = engine.create_and_send_waiting_image(client, "123", False, {"url": "https://example/image"})
        self.assertEqual(result["stage"], "convert")

    def test_telegram_menu_schema_migration_runs_once(self):
        import sqlite3
        import get_ck_im_zalo as telegram
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE accounts (id INTEGER)")
        queries = []
        conn.set_trace_callback(queries.append)
        with patch.object(telegram, "_ACCOUNT_OWNER_SCHEMA_READY", False):
            telegram._ensure_account_owner_schema(conn)
            first_count = len(queries)
            telegram._ensure_account_owner_schema(conn)
            self.assertEqual(len(queries), first_count)
        self.assertIn("owner_tg_id", {row[1] for row in conn.execute("PRAGMA table_info(accounts)")})


if __name__ == "__main__":
    unittest.main()
