"""Mini App regressions. Author: Dev Anh Khôi. Version: 1.2.0."""
import io
import os
import tempfile
import unittest
import threading
import zlib
from concurrent.futures import Future
from unittest.mock import patch
from unittest.mock import Mock

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "test-only")
import app


class MiniAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def test_compact_menu_is_platform_appropriate(self):
        menu = app.build_compact_inchat_menu("zalo", 2)
        self.assertIn("Tài khoản đang bật: 2", menu)
        self.assertIn(".sticker", menu)
        for unsafe in (".lagbox", ".kickall", ".floodbox", ".giaitan"):
            self.assertNotIn(unsafe, menu)
        self.assertNotIn(".sticker", app.build_compact_inchat_menu("discord", 1))

    def test_telegram_keyboard_does_not_advertise_destructive_functions(self):
        import get_ck_im_zalo as telegram
        keyboard = telegram.DirectTelegramBotRunner.build_tabbed_keyboard("func", user_id=telegram.ROOT_ADMIN_ID)
        callbacks = [button.get("callback_data", "") for row in keyboard["inline_keyboard"] for button in row]
        for token in ("fn_lag_sys_all", "fn_kickall", "fn_floodbox", "fn_nhay_giaitan"):
            self.assertFalse(any(token in callback for callback in callbacks))

    def test_qr_start_and_status_use_manager_without_leaking_credentials(self):
        with patch.object(app.ZaloQRLoginManager, "start_qr_session", return_value={"ok": True, "session_id": "abc", "status": "generating", "cookies": {"secret": "private"}}):
            result = self.client.post("/api/miniapp/start_qr")
        self.assertEqual(result.json["session_id"], "abc")
        self.assertNotIn("cookies", result.json)
        with patch.object(app.ZaloQRLoginManager, "get_session_status", return_value={"ok": True, "status": "waiting_scan", "qr_base64": "image", "cookies": {"secret": "private"}}):
            result = self.client.get("/api/miniapp/qr_status/abc")
        self.assertEqual(result.json["qr_base64"], "image")
        self.assertNotIn("cookies", result.json)

    def test_qr_does_not_report_success_when_account_save_fails(self):
        from zalo_login import ZaloPCSessionKeeper
        state = {"auto_save": True, "status": "confirmed"}
        fake_zalo = Mock(uid="123456", secret_key="key", display_name="User", cookies_dict={})
        with patch.object(app.Zalo, "get_pooled_client", return_value=fake_zalo), patch.object(ZaloPCSessionKeeper, "register_and_keep_alive"), patch.object(app.ZaloCookieVaultEngine, "save_zalo_vault_record"), patch.object(app.ZaloQRLoginManager, "_persist_qr_state_to_db"), patch.object(app, "db", side_effect=app.sqlite3.OperationalError("write failure")):
            app.ZaloQRLoginManager._finalize_zalo_credentials(state, "device", {"zpsid": "abcdefghijklmnop"}, user_info_dict={"uid": "123456", "zpw_enk": "key", "_groups_count": 1})
        self.assertEqual(state["status"], "error")
        self.assertIn("không lưu", state["message"])

    def test_qr_reports_success_only_after_commit(self):
        from zalo_login import ZaloPCSessionKeeper
        state = {"auto_save": True, "status": "confirmed"}
        fake_zalo = Mock(uid="123456", secret_key="key", display_name="User", cookies_dict={})
        connection = Mock()
        connection.execute.side_effect = [Mock(fetchone=Mock(return_value=None)), Mock(fetchone=Mock(return_value=None)), Mock(lastrowid=7)]
        statuses = []
        with patch.object(app.Zalo, "get_pooled_client", return_value=fake_zalo), patch.object(ZaloPCSessionKeeper, "register_and_keep_alive"), patch.object(app.ZaloCookieVaultEngine, "save_zalo_vault_record"), patch.object(app.ZaloQRLoginManager, "_persist_qr_state_to_db", side_effect=lambda st, **kw: statuses.append(st["status"])), patch.object(app, "db", return_value=connection), patch.object(app, "refresh_accounts_ram_cache"), patch.object(app, "sync_all_zalo_listeners"), patch.object(app, "log_system_command"):
            app.ZaloQRLoginManager._finalize_zalo_credentials(state, "device", {"zpsid": "abcdefghijklmnop"}, user_info_dict={"uid": "123456", "zpw_enk": "key", "_groups_count": 1})
        connection.commit.assert_called_once()
        self.assertEqual(statuses, ["confirmed", "success"])

    def test_oversized_upload_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "UPLOAD_DIR", folder):
            path = os.path.join(folder, "existing.txt")
            with open(path, "wb") as output:
                output.write(b"original")
            response = self.client.post("/api/miniapp/upload_file", data={"file": (io.BytesIO(b"x" * (app.MAX_MINIAPP_TEXT_BYTES + 1)), "existing.txt")})
            self.addCleanup(response.request.environ["wsgi.input"].close)
            self.assertEqual(response.status_code, 413)
            with open(path, "rb") as existing:
                self.assertEqual(existing.read(), b"original")

    def test_miniapp_api_requires_authentication(self):
        client = app.app.test_client()
        self.assertEqual(client.get("/api/miniapp/qr_status/abc").status_code, 401)

    def test_websocket_json_decompression_has_bounded_output(self):
        listener = app.ZaloRealtimeListener(1)
        self.assertEqual(listener._try_decompress_or_json(zlib.compress(b'{"event":1}')), {"event": 1})
        self.assertIsNone(listener._try_decompress_or_json(zlib.compress(b'"' + b'x' * (8 * 1024 * 1024) + b'"')))
        self.assertIsNone(listener._try_decompress_or_json(b'x' * (2 * 1024 * 1024 + 1)))

    def test_telegram_inflight_limit_releases_after_completion(self):
        import get_ck_im_zalo as telegram
        runner = telegram.DirectTelegramBotRunner.__new__(telegram.DirectTelegramBotRunner)
        runner._update_slots = threading.BoundedSemaphore(1)
        runner._interactive_update_slots = threading.BoundedSemaphore(1)
        pending = Future()
        runner.executor = Mock()
        runner.interactive_executor = Mock()
        runner.executor.submit.return_value = pending
        update = {"message": {"text": "hello"}}
        self.assertTrue(runner._submit_update(update))
        self.assertFalse(runner._submit_update(update))
        pending.set_result(None)
        runner.executor.submit.return_value = Future()
        self.assertTrue(runner._submit_update(update))

    def test_telegram_import_reports_save_failure_and_hides_session_key(self):
        import get_ck_im_zalo as telegram
        runner = telegram.DirectTelegramBotRunner.__new__(telegram.DirectTelegramBotRunner)
        runner.send_text = Mock(return_value={"result": {"message_id": 10}})
        runner.delete_msg = Mock()
        runner._cached_boxes_by_user = {}
        check = {"alive": True, "zpw_enk": "sensitive-session-key", "uid": "123456"}
        with patch.object(telegram, "check_zalo_cookie_imei_live", return_value=check), patch.object(telegram, "sync_zalo_account_to_web_db", return_value=None):
            runner.handle_import_zalo_cookie_imei(1, 2, "device-id", {"zpsid": "cookie"})
        self.assertIn("Không lưu được", runner.send_text.call_args.args[1])
        runner.send_text.reset_mock()
        with patch.object(telegram, "check_zalo_cookie_imei_live", return_value=check), patch.object(telegram, "sync_zalo_account_to_web_db", return_value=5):
            runner.handle_import_zalo_cookie_imei(1, 2, "device-id", {"zpsid": "cookie"})
        text = runner.send_text.call_args.args[1]
        self.assertIn("#5", text)
        self.assertNotIn("sensitive-session-key", text)
        self.assertNotIn("device-id", text)

    def test_telemetry_distinguishes_total_and_enabled_accounts(self):
        with patch.object(app, "refresh_accounts_ram_cache", return_value=[{"id": 1, "enabled": 1}, {"id": 2, "enabled": 0}]):
            response = self.client.get("/api/miniapp/telemetry")
        self.assertEqual((response.json["total_accs"], response.json["live_accs"]), (2, 1))

    def test_telemetry_counts_platforms_without_exposing_credentials(self):
        accounts = [{"id": 1, "platform": "zalo", "enabled": 1, "token": "private"}, {"id": 2, "platform": "discord", "enabled": 0}, {"id": 3, "platform": "custom"}, {"id": 4, "platform": None}]
        with patch.object(app, "refresh_accounts_ram_cache", return_value=accounts):
            response = self.client.get("/api/miniapp/telemetry")
        self.assertEqual(response.json["account_platforms"], {"zalo": 2, "discord": 1, "messenger": 0, "other": 1})
        self.assertNotIn("private", response.get_data(as_text=True))

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

    def test_legacy_account_remains_visible_in_telegram(self):
        import sqlite3
        import get_ck_im_zalo as telegram
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE accounts(id INTEGER, name TEXT, platform TEXT)")
        conn.execute("INSERT INTO accounts VALUES(1, 'Existing', 'zalo')")
        with patch.object(telegram, "_open_db", return_value=conn), patch.object(telegram, "_ACCOUNT_OWNER_SCHEMA_READY", False):
            accounts = telegram.get_user_visible_accounts(telegram.ROOT_ADMIN_ID)
        self.assertEqual([account["name"] for account in accounts], ["Existing"])

    def test_import_cannot_report_success_when_save_fails(self):
        import get_ck_im_zalo as telegram
        with patch.object(telegram, "parse_imei_and_cookie_from_text", return_value=("imei", {"zpsid": "cookie"}, {})), patch.object(telegram, "check_zalo_cookie_imei_live", return_value={}), patch.object(telegram, "sync_zalo_account_to_web_db", return_value=None):
            response = self.client.post("/api/miniapp/add_cookie", json={"raw_input": "example"})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json["ok"])

    def test_sticker_upload_decodes_json_and_encrypted_envelopes(self):
        client = app.Zalo.__new__(app.Zalo)
        media = {"normalUrl": "https://example/sticker.gif", "photoId": "123"}
        self.assertEqual(client._decode_sticker_upload({"error_code": 0, "data": media}), media)
        with patch.object(client, "_dec", return_value=app.json.dumps({"data": media})):
            self.assertEqual(client._decode_sticker_upload({"error_code": 0, "data": "encrypted"}), media)
        self.assertEqual(client._decode_sticker_upload({"error_code": 5, "data": media}), {})

    def test_miniapp_has_fresh_build_header(self):
        response = self.client.get("/miniapp")
        self.assertEqual(response.headers["X-Glaze-UI-Version"], "miniapp-1.2.0")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_custom_sticker_upload_plain_response_reaches_send(self):
        client = app.Zalo.__new__(app.Zalo)
        client.secret_key = "test"
        client.imei = "test-device"
        client.prio_s = Mock()
        client._sync_cookie_headers = Mock()
        client._enc = Mock(return_value="encrypted")
        upload = Mock(status_code=200, content=b"json")
        upload.json.return_value = {"error_code": 0, "data": {"normalUrl": "https://example/sticker.gif", "photoId": "123"}}
        delivered = Mock(status_code=200, content=b"json")
        delivered.json.return_value = {"error_code": 0, "data": {"msgId": "456"}}
        client.prio_s.post.side_effect = [upload, delivered]
        self.assertTrue(client.send_custom_sticker_media("123", b"GIF89a", is_group=False, gif_bytes=b"GIF89a"))
        self.assertEqual(client.prio_s.post.call_count, 2)
        for call in client.prio_s.post.call_args_list:
            self.assertIn("/message/", call.args[0])


if __name__ == "__main__":
    unittest.main()
