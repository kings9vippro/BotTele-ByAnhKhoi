"""V13 synthetic regressions: separate IMEI caches and credential-free listener health.

All test sessions are synthetic; no provider credentials or network calls.
"""
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "v13-synthetic-test-key")

import app


class PerDeviceGroupCacheTests(unittest.TestCase):
    def _client(self, imei):
        obj = app.Zalo.__new__(app.Zalo)
        obj.imei = imei
        obj.uid = "same-owner-uid"
        return obj

    def test_two_devices_with_same_uid_use_different_cached_groups(self):
        now = time.time()
        groups = {
            "synthetic-device-one": {"ts": now, "data": [{"id": "group-one"}]},
            "synthetic-device-two": {"ts": now, "data": [{"id": "group-two"}]},
        }
        with patch.object(app.Zalo, "_GROUPS_CACHE", groups):
            self.assertEqual(self._client("synthetic-device-one").groups(), [{"id": "group-one"}])
            self.assertEqual(self._client("synthetic-device-two").groups(), [{"id": "group-two"}])

    def test_miniapp_boxes_are_scoped_by_imei_even_with_shared_uid(self):
        accs = [
            {"id": 1, "name": "One", "uid": "same-owner-uid", "imei": "device-one", "platform": "zalo", "enabled": 1},
            {"id": 2, "name": "Two", "uid": "same-owner-uid", "imei": "device-two", "platform": "zalo", "enabled": 1},
        ]
        cache = {
            "device-one": {"ts": time.time(), "data": [{"id": "box-one", "name": "Group One"}]},
            "device-two": {"ts": time.time(), "data": [{"id": "box-two", "name": "Group Two"}]},
        }
        with patch.object(app, "get_all_accounts_from_ram", return_value=accs), \
             patch.object(app.Zalo, "_GROUPS_CACHE", cache), \
             patch.object(app, "KNOWN_GROUPS_BY_ACC", {}):
            a = app._cached_miniapp_boxes("1")
            b = app._cached_miniapp_boxes("2")
        self.assertEqual({r["id"] for r in a}, {"box-one"})
        self.assertEqual({r["id"] for r in b}, {"box-two"})


class ListenerHealthTests(unittest.TestCase):
    def test_health_response_contains_no_cookie_or_session_secret(self):
        accounts = [
            {"id": 7, "name": "Test Zalo", "platform": "zalo",
             "enabled": 1, "chat_cmd_enabled": 1,
             "cookies": {"zpsid": "PRIVATE-MUST-NOT-LEAK"},
             "zpw_enk": "PRIVATE-KEY"}
        ]
        with app.app.test_request_context("/api/miniapp/account_health"), \
             patch.object(app, "get_all_accounts_from_ram", return_value=accounts), \
             patch.object(app, "zalo_listener_status", return_value={"code": "worker_unavailable"}):
            response = app.api_miniapp_account_health()
            payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["accounts"][0]["listener_health"]["code"], "worker_unavailable")
        self.assertNotIn("cookies", str(payload).lower())
        self.assertNotIn("zpw_enk", str(payload).lower())
        self.assertNotIn("PRIVATE", str(payload))

    def test_health_does_not_claim_authenticated_without_provider_evidence(self):
        fake = type("Listener", (), {})()
        fake.thread = type("Thread", (), {"is_alive": lambda self: True})()
        fake.poller_thread = type("Thread", (), {"is_alive": lambda self: True})()
        fake.stop_ev = type("Stop", (), {"is_set": lambda self: False})()
        fake.ws_status = "Cần cập nhật lại Cookie Zalo"
        fake.last_event_ts = 0
        with patch.object(app, "ACTIVE_LISTENERS", {8: fake}), \
             patch.object(app, "_ZALO_LISTENER_FAILURES", {}):
            status = app.zalo_listener_status(8)
        self.assertEqual(status["session_hint"], "relogin_required")
        self.assertEqual(status["last_event_at"], 0)


class UIContractTests(unittest.TestCase):
    def test_mobile_tabs_have_icons_and_labels(self):
        js = Path("static/control.js").read_text(encoding="utf-8")
        css = Path("static/v11.css").read_text(encoding="utf-8")
        self.assertIn("b.append(svg,element('span',names[key],'nav-caption'))", js)
        self.assertIn("grid-template-columns:repeat(5,minmax(0,1fr))", css)

    def test_live_health_and_account_scoped_tasks(self):
        js = Path("static/control.js").read_text(encoding="utf-8")
        self.assertIn("refreshAccountHealth", js)
        self.assertIn("Xem task ACC", js)
        self.assertIn("account_health", js)
        self.assertNotIn("document.cookie", js)


    def test_qr_success_exports_imei_without_session_cookie(self):
        status = {
            "ok": True, "status": "success", "message": "Saved",
            "imei": "complete-synthetic-imei", "uid": "919191919",
            "display_name": "Synthetic Test", "cookies": {"zpsid": "SENSITIVE-NOT-IN-JSON"},
        }
        class FakeConnection:
            def execute(self, *args):
                return self
            def fetchone(self):
                return {"id": 42, "name": "Synthetic Test"}
            def close(self):
                pass

        with app.app.test_request_context("/api/miniapp/qr_status/example"), \
             patch.object(app.ZaloQRLoginManager, "get_session_status", return_value=status), \
             patch.object(app, "db", return_value=FakeConnection()):
            response = app.api_miniapp_qr_status("example")
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["imei"], "complete-synthetic-imei")
        self.assertEqual(data["account_handle"], "ACC-42")
        self.assertNotIn("cookies", data)
        self.assertNotIn("SENSITIVE", str(data))
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_qr_auto_save_matches_imei_before_uid(self):
        source = Path("glaze_app.py").read_text(encoding="utf-8")
        section = source.split("        saved_acc_id = 0", 1)[1].split("        st[\"status\"] = \"success\"", 1)[0]
        self.assertLess(section.index("AND imei=?"), section.index("AND uid=?"))
        self.assertIn("if not str(row[\"imei\"] or \"\").strip()", section)



if __name__ == "__main__":
    unittest.main()
