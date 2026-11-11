"""V10 checks owner-only QR export, root tasks, Mini App and typed files."""
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "v10-suite-local")
from flask import Flask

import control_plane
from miniapp_url import public_miniapp_url
from get_ck_im_zalo import DirectTelegramBotRunner
import glaze_app as app


class MiniappUrlTests(unittest.TestCase):
    def test_render_hostname_is_usable(self):
        self.assertEqual(public_miniapp_url({"RENDER_EXTERNAL_URL":"https://sample.onrender.com"}),
                         "https://sample.onrender.com/miniapp")

    def test_explicit_custom_url_precedence(self):
        self.assertEqual(public_miniapp_url({
            "MINIAPP_PUBLIC_URL":"https://example.org/miniapp",
            "RENDER_EXTERNAL_URL":"https://sample.onrender.com"}),
            "https://example.org/miniapp")

    def test_invalid_schemes_and_user_info_rejected(self):
        self.assertIsNone(public_miniapp_url({"MINIAPP_PUBLIC_URL":"http://localhost:5000",
                                               "RENDER_EXTERNAL_URL":"https://attacker@evil.example",
                                               "PUBLIC_WEB_URL":"javascript:alert(1)"}))

    def test_missing_domain_never_fabricated(self):
        self.assertIsNone(public_miniapp_url({}))


class PrivateQRExportTests(unittest.TestCase):
    def setUp(self):
        self.bot=object.__new__(DirectTelegramBotRunner)
        self.bot._qr_export_pending={}
        self.bot._qr_export_lock=threading.RLock()
        self.bot.send_text=Mock(return_value={"ok":True})
        self.bot.answer_callback=Mock()

    def test_owner_private_dm_one_time_protected(self):
        nonce=self.bot._queue_private_qr_export(321,321,"synthetic-imei",
                                                 {"zpsid":"not-real-credential"})
        self.assertIsInstance(nonce,str)
        self.assertTrue(self.bot._confirm_private_qr_export(321,321,nonce))
        message=self.bot.send_text.call_args.args[1]
        self.assertIn("synthetic-imei",message)
        self.assertIn("not-real-credential",message)
        self.assertTrue(self.bot.send_text.call_args.kwargs["protect_content"])
        self.bot.send_text.reset_mock()
        self.assertFalse(self.bot._confirm_private_qr_export(321,321,nonce))
        self.bot.send_text.assert_not_called()

    def test_group_qr_reveal_never_available(self):
        self.assertIsNone(self.bot._queue_private_qr_export(-1001,321,
                          "imei",{"zpsid":"private"}))
        self.assertFalse(self.bot._confirm_private_qr_export(-1001,321,"nonce"))
        self.bot.send_text.assert_not_called()

    def test_other_admin_cannot_access_owner_qr_cookie(self):
        nonce=self.bot._queue_private_qr_export(321,321,"imei",{"zpsid":"private"})
        self.assertFalse(self.bot._confirm_private_qr_export(999,999,nonce))
        self.assertTrue(self.bot._confirm_private_qr_export(321,321,nonce))

    def test_tampered_or_expired_nonce_rejected(self):
        nonce=self.bot._queue_private_qr_export(321,321,"imei",{"zpsid":"private"})
        self.assertFalse(self.bot._confirm_private_qr_export(321,321,nonce+"x"))
        entry=self.bot._qr_export_pending[("321","321",nonce)]
        self.bot._qr_export_pending[("321","321",nonce)]=(time.time()-1,entry[1],entry[2])
        self.assertFalse(self.bot._confirm_private_qr_export(321,321,nonce))

    def test_html_sensitive_cookie_escaped(self):
        nonce=self.bot._queue_private_qr_export(321,321,"<imei>",{"zpsid":"<tag>"})
        self.assertTrue(self.bot._confirm_private_qr_export(321,321,nonce))
        raw=self.bot.send_text.call_args.args[1]
        self.assertIn("&lt;imei&gt;",raw)
        self.assertNotIn("<tag>",raw)


class AllOwnerTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=os.path.join(self.temp.name,"tasks.sqlite")
        self.principal="321"
        self.env=patch.dict(os.environ,{"TELEGRAM_ADMIN_ID":"321",
                        "SECRET_KEY":"test-secret","DISABLE_BACKGROUND_WORKERS":"1"})
        self.env.start();self.addCleanup(self.env.stop)
        self.api=Flask(__name__);self.api.secret_key="test-secret"
        control_plane.register(self.api,self.db,lambda:self.principal)
        self.queue=self.api.extensions['notification_queue'];self.addCleanup(self.queue.close)
        self.client=self.api.test_client()

    def db(self):
        c=sqlite3.connect(self.path)
        c.row_factory=sqlite3.Row
        return c

    def test_root_sees_and_manages_other_user(self):
        tid=self.queue.submit("222","channel","dummy")
        with patch.object(app,"task_snapshots",return_value=[]):
            r=self.client.get("/api/miniapp/task_registry")
        self.assertEqual(r.status_code,200)
        record=next(t for t in r.json["tasks"] if t["source_id"]==tid)
        self.assertEqual(record["owner"],"222")
        res=self.client.post("/api/miniapp/notification_control",json={
            "id":tid,"action":"pause"})
        self.assertEqual(res.status_code,200)
        self.assertEqual(self.queue.list("222")[0]["status"],"PAUSED")

    def test_root_snapshot_sees_all_owner_events_and_counts(self):
        self.queue.submit("222","channel","dummy")
        snap=self.client.get("/api/miniapp/control").json
        self.assertEqual(snap["counts"]["QUEUED"],1)
        self.assertTrue(any(e["owner"]=="222" for e in snap["events"]))
        self.principal="333"
        delegated=self.client.get("/api/miniapp/control").json
        self.assertEqual(delegated["counts"],{})
        self.assertEqual(delegated["events"],[])

    def test_delegate_cannot_list_or_stop_other_user_task(self):
        tid=self.queue.submit("222","channel","dummy")
        self.principal="333"
        self.assertEqual(self.client.get("/api/miniapp/task_registry").json["tasks"],[])
        r=self.client.post("/api/miniapp/notification_control",json={
            "id":tid,"action":"stop"})
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.queue.list("222")[0]["status"],"QUEUED")


class FileAndCommandTests(unittest.TestCase):
    def test_all_zalo_dot_commands_have_reserved_lane(self):
        self.assertIs(app._zalo_input_executor(".g"),app._ZALO_COMMAND_INPUT_EXECUTOR)
        self.assertIs(app._zalo_input_executor(".n"),app._ZALO_COMMAND_INPUT_EXECUTOR)
        self.assertIs(app._zalo_input_executor(".menu"),app._INTERACTIVE_INPUT_EXECUTOR)
        self.assertIs(app._zalo_input_executor("hello"),app._PRIORITY_CMD_EXECUTOR)

    def test_functions_have_actual_interactive_telegram_buttons(self):
        from control_plane import telegram_command
        bot=Mock()
        self.assertTrue(telegram_command(bot,321,321,"functions",""))
        markup=bot.send_text.call_args.kwargs.get("reply_markup")
        self.assertIsInstance(markup,dict)
        actions=[button["callback_data"] for row in markup["inline_keyboard"] for button in row]
        self.assertIn("pickfn:fn_treo_damau",actions)
        self.assertIn("pickfn:fn_treo_nhay",actions)

    def test_menu_falls_through_to_interactive_media_menu(self):
        from control_plane import telegram_command
        bot=Mock()
        self.assertFalse(telegram_command(bot,321,321,"menu",""))
        bot.send_text.assert_not_called()

    def test_separate_file_selector_buttons(self):
        runner=object.__new__(DirectTelegramBotRunner)
        runner._get_available_txt_files=Mock(return_value=[
            {"filename":"nhay.txt","file_type":"nhay","lines_count":3},
            {"filename":"ngon.txt","file_type":"ngon","lines_count":1}])
        runner.edit_menu_message=Mock()
        runner._render_file_selector_menu("chat","message",target="nhay")
        text=runner.edit_menu_message.call_args.args[2]
        self.assertIn("nhay.txt",text)
        self.assertNotIn("ngon.txt",text)


if __name__=="__main__":unittest.main()