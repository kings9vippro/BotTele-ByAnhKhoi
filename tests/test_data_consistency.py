"""Shared data regressions. Author: Dev Anh Khôi. Version: 1.2.0."""
import copy
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "test-only")
import app
import app_storage


class DataConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        for name, value in (("_ACTIVE_DB_PATH", os.path.join(self.folder.name, "test.db")),
                            ("_DB_TLS", threading.local()),
                            ("ACCOUNTS_RAM_CACHE", {}),
                            ("_LAST_ACCOUNTS_SYNC_TS", 0),
                            ("UPLOAD_DIR", self.folder.name),
                            ("SYSTEM_RUNTIME_CONFIG", copy.deepcopy(app.SYSTEM_RUNTIME_CONFIG))):
            patcher = patch.object(app, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        app.init_db()
        self.addCleanup(lambda: app.db()._conn.close())
        self.client = app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def test_exact_filename_wins_over_preset_substring(self):
        rows = [{"filename": "preset_story.txt", "id": 1}, {"filename": "story.txt", "id": 2}]
        with patch.object(app, "get_ordered_files_with_display_num", return_value=rows):
            self.assertEqual(app.resolve_file_record("story.txt")["id"], 2)

    def test_legacy_timestamped_upload_wins_over_unrelated_default_file(self):
        original = os.path.join(self.folder.name, "story.txt")
        uploaded = os.path.join(self.folder.name, "123_story.txt")
        for path, content in ((original, "old default"), (uploaded, "new upload")):
            with open(path, "w") as output:
                output.write(content)
        records = [{"id": 1, "filename": "story.txt", "filepath": uploaded}]
        with patch.object(app, "get_ordered_files_with_display_num", return_value=records):
            self.assertEqual(app.get_blocks_from_file_query("story.txt", mode="treo_ngon"), ["new upload"])

    def test_miniapp_real_filename_cannot_be_shadowed_by_legacy_alias(self):
        for filename, content in (("story.txt", "default"), ("123_story.txt", "uploaded")):
            with open(os.path.join(self.folder.name, filename), "w") as output:
                output.write(content)
        conn = app.db()
        conn.execute("INSERT INTO files(filename, filepath) VALUES('story.txt', ?)", (os.path.join(self.folder.name, "123_story.txt"),))
        conn.commit()
        response = self.client.post("/api/miniapp/select_file", json={"filename": "story.txt", "target": "ngon"})
        self.assertTrue(response.json["ok"])
        self.assertEqual(response.json["filename"], "story.txt")
        record = app.select_script_file("story.txt", "ngon")
        self.assertEqual(record["filename"], "123_story.txt")
        self.assertEqual(app.SYSTEM_RUNTIME_CONFIG["selected_ngon_file"], "123_story.txt")

    def test_legacy_file_metadata_is_relocated_without_changing_id_or_content(self):
        uploaded = os.path.join(self.folder.name, "123_custom.txt")
        with open(uploaded, "w") as output:
            output.write("custom content")
        conn = app.db()
        account_file = conn.execute("INSERT INTO files(filename, filepath, lines_count) VALUES('custom.txt', '/old/deploy/uploads/123_custom.txt', 1)").lastrowid
        conn.execute("INSERT OR REPLACE INTO app_settings VALUES('selected_ngon_file', 'custom.txt')")
        conn.commit()
        app.init_db()
        record = dict(conn.execute("SELECT * FROM files WHERE id=?", (account_file,)).fetchone())
        self.assertEqual(record["filename"], "123_custom.txt")
        self.assertEqual(record["filepath"], uploaded)
        app.refresh_script_selections()
        self.assertEqual(app.SYSTEM_RUNTIME_CONFIG["selected_ngon_file"], "123_custom.txt")
        self.assertEqual(app.get_blocks_from_file_query("123_custom.txt", mode="treo_ngon"), ["custom content"])

    def test_direct_uploaded_file_resolves_without_database_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "story.txt")
            with open(path, "w") as output:
                output.write("new text")
            with patch.object(app, "UPLOAD_DIR", folder), patch.object(app, "get_ordered_files_with_display_num", return_value=[]):
                record = app.resolve_file_record("story.txt")
            self.assertIsNotNone(record)
            self.assertEqual(record["filepath"], path)

    def test_database_error_never_changes_database_path(self):
        original = app._ACTIVE_DB_PATH
        try:
            with patch.object(app.sqlite3, "connect", side_effect=app.sqlite3.OperationalError("database is locked")):
                with self.assertRaises(app.sqlite3.OperationalError):
                    app._create_raw_sqlite_conn()
            self.assertEqual(app._ACTIVE_DB_PATH, original)
        finally:
            app._ACTIVE_DB_PATH = original

    def test_nonexistent_selection_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "UPLOAD_DIR", folder):
            response = self.client.post("/api/miniapp/select_file", json={"filename": "missing.txt", "target": "nhay"})
        self.assertFalse(response.json["ok"])

    def test_new_selection_clears_stale_account_override(self):
        config = copy.deepcopy(app.SYSTEM_RUNTIME_CONFIG)
        config["selected_file_by_acc"] = {"7": "old.txt"}
        config["selected_nhay_by_acc"] = {"7": "old.txt"}
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "new.txt"), "w") as output:
                output.write("new")
            with patch.object(app, "UPLOAD_DIR", folder), patch.object(app, "SYSTEM_RUNTIME_CONFIG", config):
                response = self.client.post("/api/miniapp/select_file", json={"filename": "new.txt", "target": "nhay"})
        self.assertTrue(response.json["ok"])
        self.assertEqual(config["selected_file_by_acc"], {})
        self.assertEqual(config["selected_nhay_file"], "new.txt")

    def test_file_selection_survives_new_runtime(self):
        response = self.client.post("/api/miniapp/add_file", json={"filename": "custom.txt", "content": "chosen content", "target": "ngon"})
        self.assertTrue(response.json["ok"])
        app.SYSTEM_RUNTIME_CONFIG["selected_ngon_file"] = "old-default.txt"
        app.SYSTEM_RUNTIME_CONFIG["selected_file_by_acc"] = {"1": "old.txt"}
        response = self.client.get("/api/miniapp/files")
        self.assertEqual(response.json["selected_ngon"], "custom.txt")
        self.assertEqual(app.SYSTEM_RUNTIME_CONFIG["selected_file_by_acc"], {})
        self.assertEqual(app.get_blocks_from_file_query("custom.txt", mode="treo_ngon"), ["chosen content"])

    def test_storage_failure_is_not_reported_as_zero_accounts(self):
        with patch.object(app, "db", side_effect=app.sqlite3.OperationalError("database is locked")):
            for path in ("accounts", "telemetry"):
                response = self.client.get("/api/miniapp/" + path)
                self.assertEqual(response.status_code, 503)
                self.assertFalse(response.json["ok"])
                self.assertNotIn("total_accs", response.json)

    def test_miniapp_reads_persisted_account_even_with_empty_ram_cache(self):
        conn = app.db()
        conn.execute("INSERT INTO accounts(name, platform, uid, enabled, chat_cmd_enabled) VALUES('Stored', 'zalo', '1234567', 1, 1)")
        conn.commit()
        with patch.object(app, "ACCOUNTS_RAM_CACHE", {}), patch.object(app, "_LAST_ACCOUNTS_SYNC_TS", app.time.time()):
            response = self.client.get("/api/miniapp/accounts")
            telemetry = self.client.post("/api/miniapp/sync", json={})
        self.assertEqual(response.json["accounts"][0]["name"], "Stored")
        self.assertTrue(response.json["accounts"][0]["saved"])
        self.assertEqual(telemetry.json["total_accs"], 1)

    def test_legacy_null_enabled_means_enabled_in_both_channels(self):
        import get_ck_im_zalo as telegram
        conn = app.db()
        conn.execute("INSERT INTO accounts(name, platform, uid, enabled, owner_tg_id) VALUES('Legacy', 'zalo', '9000001', NULL, ?)", (telegram.ROOT_ADMIN_ID,))
        conn.commit()
        web = self.client.get("/api/miniapp/telemetry")
        self.assertEqual(web.json["live_accs"], 1)
        self.assertEqual(len(telegram.get_user_visible_accounts(telegram.ROOT_ADMIN_ID, enabled_only=True)), 1)

    def test_upload_failure_preserves_previous_file(self):
        path = os.path.join(self.folder.name, "saved.txt")
        with open(path, "wb") as output:
            output.write(b"previous")
        connection = app.db()
        with patch.object(connection, "commit", side_effect=app.sqlite3.OperationalError("commit failed")):
            with self.assertRaises(app.sqlite3.OperationalError):
                app.save_text_file(app.db, self.folder.name, "saved.txt", b"new", "nhay")
        with open(path, "rb") as saved:
            self.assertEqual(saved.read(), b"previous")

    def test_failed_backup_rename_cannot_replace_original_with_empty_backup(self):
        path = os.path.join(self.folder.name, "protected.txt")
        with open(path, "wb") as output:
            output.write(b"original")
        replace = os.replace

        def checked_replace(source, destination):
            if source == path:
                raise PermissionError("cannot move original")
            return replace(source, destination)

        with patch.object(app_storage.os, "replace", side_effect=checked_replace):
            with self.assertRaises(PermissionError):
                app.save_text_file(app.db, self.folder.name, "protected.txt", b"new", "nhay")
        with open(path, "rb") as output:
            self.assertEqual(output.read(), b"original")

    def test_telegram_upload_selection_is_visible_in_miniapp(self):
        import get_ck_im_zalo as telegram
        telegram.save_telegram_text_file("shared.txt", b"shared content", "ngon")
        response = self.client.get("/api/miniapp/files")
        self.assertEqual(response.json["selected_ngon"], "shared.txt")
        self.assertIn("shared.txt", [item["filename"] for item in response.json["files"]])

    def test_telegram_and_miniapp_read_same_50_stored_accounts(self):
        import get_ck_im_zalo as telegram
        connection = app.db()
        connection.executemany("INSERT INTO accounts(name, platform, uid, enabled, owner_tg_id) VALUES(?, 'zalo', ?, 1, ?)",
                               [(f"Stored {index}", str(9000000 + index), str(telegram.ROOT_ADMIN_ID)) for index in range(50)])
        connection.commit()
        telegram_ids = {item["id"] for item in telegram.get_user_visible_accounts(telegram.ROOT_ADMIN_ID)}
        web_ids = {item["id"] for item in self.client.get("/api/miniapp/accounts").json["accounts"]}
        self.assertEqual(len(web_ids), 50)
        self.assertEqual(telegram_ids, web_ids)

    def test_selected_file_cannot_be_deleted_and_deleted_index_is_removed(self):
        self.client.post("/api/miniapp/add_file", json={"filename": "first.txt", "content": "first", "target": "nhay"})
        self.assertEqual(self.client.post("/api/miniapp/delete_file", json={"filename": "first.txt"}).status_code, 409)
        self.client.post("/api/miniapp/add_file", json={"filename": "second.txt", "content": "second", "target": "nhay"})
        self.assertTrue(self.client.post("/api/miniapp/delete_file", json={"filename": "first.txt"}).json["ok"])
        self.assertIsNone(app.resolve_file_record("first.txt"))

    def test_supported_command_catalog_matches_inchat_menu(self):
        response = self.client.get("/api/miniapp/commands")
        commands = response.json["commands"]
        self.assertGreaterEqual(len(commands), 14)
        menu = app.build_compact_inchat_menu("zalo", 1)
        for command in commands:
            self.assertIn(command["usage"], menu)
        self.assertNotIn(".lagbox", str(commands))

    def test_telegram_menu_reports_storage_error_instead_of_zero(self):
        import get_ck_im_zalo as telegram
        with patch.object(telegram, "_open_db", side_effect=app.sqlite3.OperationalError("locked")):
            caption = telegram.DirectTelegramBotRunner.build_tabbed_caption()
        self.assertIn("Chưa đồng bộ", caption)
        self.assertNotIn("<b>0 Acc", caption)

    def test_invalid_account_mutations_are_rejected(self):
        for path in ("toggle_acc_cmd", "delete_acc"):
            for account_id in ("invalid", "", -1):
                response = self.client.post("/api/miniapp/" + path, json={"acc_id": account_id})
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json["ok"])

    def test_text_size_limit_includes_the_final_newline(self):
        response = self.client.post("/api/miniapp/add_file", json={"filename": "boundary.txt", "content": "x" * app.MAX_MINIAPP_TEXT_BYTES})
        self.assertEqual(response.status_code, 413)
        self.assertFalse(os.path.exists(os.path.join(self.folder.name, "boundary.txt")))


if __name__ == "__main__":
    unittest.main()
