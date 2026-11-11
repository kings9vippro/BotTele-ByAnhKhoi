"""V7 Zalo watcher and paginated box browser regression tests.

Uses synthetic data; never contacts Zalo or Telegram.
"""
import os
import time
import unittest
from unittest.mock import patch, Mock

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "v7-test")
import app
from zalo_group_checker import activity_clock, paginate_groups, validate_timeout, vietnam_time

class ZaloWatcherV7Tests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True

    def test_clock_marks_exact_stop_time_after_ninety_seconds(self):
        result = activity_clock(1000,90,now=1091)
        self.assertEqual(result["inactive_since"],1090)
        self.assertEqual(result["silence_seconds"],91)
        self.assertEqual(result["status"],"silent")

    def test_clock_does_not_pretend_unseen_member_has_stopped(self):
        self.assertIsNone(activity_clock(0,90,now=999,has_message=False)["inactive_since"])

    def test_timeout_rejects_nan_negative_and_excessive(self):
        for value in ("nan", "inf", 1, -1, 999999, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_timeout(value)
        self.assertEqual(validate_timeout("90"),90)

    def test_page_split_over_eighty_boxes(self):
        groups = [{"id":str(i),"name":"Nhóm %03d"%i,"account_id":7} for i in range(105)]
        self.assertEqual(paginate_groups(groups,1)["total"],105)
        self.assertEqual(paginate_groups(groups,1)["total_pages"],6)
        self.assertEqual(len(paginate_groups(groups,5)["boxes"]),20)
        self.assertEqual(len(paginate_groups(groups,6)["boxes"]),5)
        self.assertFalse(paginate_groups(groups,6)["has_more"])

    def test_duplicate_groups_do_not_duplicate_pages(self):
        data=[{"id":"42","name":"B"},{"id":"42","name":"B"},{"id":"12","name":"A"}]
        self.assertEqual([x["id"] for x in paginate_groups(data)["boxes"]],["12","42"])

    def test_admin_box_api_has_all_pages(self):
        groups=[{"id":str(i),"name":"Nhóm %03d"%i,"account_id":7} for i in range(105)]
        with patch.object(app,"_cached_miniapp_boxes",return_value=groups) as cache:
            r=self.client.get("/api/miniapp/boxes?account_id=7&page=6")
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json["total"],105)
        self.assertEqual(len(r.json["boxes"]),5)
        cache.assert_called_with("7")

    def test_box_api_invalid_page_returns_400(self):
        r=self.client.get("/api/miniapp/boxes?page=0")
        self.assertEqual(r.status_code,400)

    def test_explicit_scan_uses_only_saved_cookie_account(self):
        account={"id":7,"platform":"zalo","imei":"fixture-imei","cookies":{"fixture":"not-a-cookie"},"uid":"1234"}
        client=Mock()
        client.get_groups.return_value=[{"id":"42","name":"Box"}]
        app._BOX_SCAN_LAST.clear()
        with patch.object(app,"get_all_accounts_from_ram",return_value=[account]),patch.object(
            app.Zalo,"get_pooled_client",return_value=client
        ) as pooled:
            r=self.client.post("/api/miniapp/scan_boxes",json={"account_id":"7"})
            r2=self.client.post("/api/miniapp/scan_boxes",json={"account_id":"7"})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json["total"],1)
        self.assertEqual(r2.status_code,429)
        pooled.assert_called_once()
        self.assertNotIn("fixture-imei",r.get_data(as_text=True))

    def test_unregistered_scan_refused(self):
        with patch.object(app,"get_all_accounts_from_ram",return_value=[]):
            r=self.client.post("/api/miniapp/scan_boxes",json={"account_id":"999"})
        self.assertEqual(r.status_code,404)

    def test_watch_start_requires_group_on_account(self):
        with patch.object(app,"_cached_miniapp_boxes",return_value=[]):
            r=self.client.post("/api/miniapp/zalo_watch",json={
                "action":"start","account_id":"7","box_id":"not-owned"})
        self.assertEqual(r.status_code,403)

    def test_watch_start_uses_existing_shared_engine(self):
        match={"id":"42","name":"Tên nhóm","account_id":7}
        enabled={"box_id":"42","timeout_sec":90}
        with patch.object(app,"_cached_miniapp_boxes",return_value=[match]),patch.object(
            app.CanhTreoWatchdogEngine,"get_watched_boxes",return_value=[]
        ),patch.object(app.CanhTreoWatchdogEngine,"enable_watch",return_value=enabled) as start:
            r=self.client.post("/api/miniapp/zalo_watch",json={
                "action":"start","account_id":"7","box_id":"42","timeout_sec":90})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json["persistence"],"process_local")
        start.assert_called_once()

    def test_alert_once_per_last_message_without_reset(self):
        watcher=app.CanhTreoWatchdogEngine
        state={"box_id":"42","enabled":True,"last_msg_id":"mid","last_activity_ts":1000.,
               "timeout_sec":90,"alerted_for_activity_ts":0,"alerts_sent":0}
        with patch.object(watcher,"_WATCHED_BOXES",{"42":state}):
            self.assertEqual(watcher.collect_due_alerts(now=1089),[])
            self.assertEqual(len(watcher.collect_due_alerts(now=1090)),1)
            self.assertEqual(watcher.collect_due_alerts(now=2000),[])
            self.assertEqual(state["last_activity_ts"],1000.)
            self.assertEqual(state["alerts_sent"],1)
            state["last_activity_ts"]=2001.
            state["last_msg_id"]="new"
            state["alerted_for_activity_ts"]=0
            self.assertEqual(len(watcher.collect_due_alerts(now=2092)),1)

    def test_status_never_exposes_participant_dictionary(self):
        watcher=app.CanhTreoWatchdogEngine
        state={"enabled":True,"box_id":"42","box_name":"Fixture","acc_id":7,
               "platform":"zalo","last_msg_id":"mid","last_activity_ts":1000.,
               "timeout_sec":90,"last_msg_text":"safe sample",
               "participants":{"private-id":{"name":"Secret"}}}
        with patch.object(watcher,"_WATCHED_BOXES",{"42":state}):
            rows=watcher.get_watched_boxes()
        self.assertEqual(rows[0]["inactive_since"],1090)
        self.assertNotIn("participants",rows[0])
        self.assertIn("GMT+7",rows[0]["inactive_since_label"])

    def test_alert_escapes_untrusted_group_text(self):
        import sys
        from types import SimpleNamespace
        telegram = Mock()
        watcher = app.CanhTreoWatchdogEngine
        now = time.time()
        snap = {"box_id":"42","box_name":"<script>alert(1)</script>",
                "last_activity_ts":now-92,"timeout_sec":90,
                "last_sender_name":"<admin>","last_sender_uid":"123",
                "last_msg_text":"<bad>tag</bad>","last_msg_id":"one",
                "participants":{"33":{"name":"<person>","last_ts":now-91,
                                      "last_msg":"<button>ignore</button>"}}}
        with patch.dict(sys.modules, {"get_ck_im_zalo":SimpleNamespace(_BOT_INSTANCE=telegram)}):
            watcher._send_telegram_inactivity_alert(snap)
        telegram.send_text.assert_called_once()
        body = telegram.send_text.call_args.args[1]
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;person&gt;", body)
        self.assertIn("&lt;bad&gt;", body)
        self.assertIn("Ngừng nhắn từ:", body)
        self.assertNotIn("\\n",body)

    def test_unauthenticated_group_scan_is_denied(self):
        client=app.app.test_client()
        self.assertEqual(client.post("/api/miniapp/scan_boxes",json={"account_id":"7"}).status_code,401)

if __name__=="__main__":unittest.main()