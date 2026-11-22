"""Real transport contracts for QR Zalo and Discord linkage, using safe fixtures."""
import os
import unittest
from unittest.mock import Mock, patch

import requests
import test_data_consistency as fixtures

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "transport-fixture-only")

import app
from zalo_login import VietnamSingaporeGeoRouter


class ProviderConnectionTests(unittest.TestCase):
    def setUp(self):
        fixtures.DataConsistencyTests.setUp(self)

    def test_health_is_authenticated_and_does_not_call_provider_without_login(self):
        anonymous = app.app.test_client()
        with patch.object(app.requests, "get") as get:
            response = anonymous.get("/api/miniapp/provider_health/discord")
        self.assertEqual(response.status_code, 401)
        get.assert_not_called()

    def test_provider_health_distinguishes_reachability_from_upstream_denial(self):
        response = Mock(status_code=200)
        with patch.object(app.requests, "get", return_value=response) as get:
            result = self.client.get("/api/miniapp/provider_health/discord")
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json["reachable"])
        self.assertIn("/api/v10/gateway", get.call_args.args[0])
        response.close.assert_called_once()

        rejected = Mock(status_code=403)
        with patch.object(app.requests, "get", return_value=rejected):
            result = self.client.get("/api/miniapp/provider_health/zalo")
        self.assertTrue(result.json["ok"])
        self.assertFalse(result.json["reachable"])
        self.assertEqual(result.json["http_status"], 403)

    def test_provider_timeout_reports_its_class_without_secrets(self):
        with patch.object(app.requests, "get", side_effect=requests.ConnectTimeout("private network path")):
            result = self.client.get("/api/miniapp/provider_health/zalo")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["code"], "provider_transport_unavailable")
        self.assertNotIn("private network path", result.text)

    def test_discord_bot_and_oauth2_headers_are_distinct(self):
        profile = Mock(status_code=200)
        profile.json.return_value = {"id": "123456789", "username": "Verified", "bot": True}
        for kind, authorization in (
            ("bot", "Bot fixture-bot-token"), ("oauth2", "Bearer fixture-oauth-access-token")
        ):
            with self.subTest(kind=kind), patch("credential_links.requests.get", return_value=profile) as get:
                credential = "fixture-bot-token" if kind == "bot" else "fixture-oauth-access-token"
                result = self.client.post("/api/miniapp/credential_links",
                                          json={"platform": "discord", "kind": kind, "credential": credential})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json["link"]["kind"], kind)
                self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], authorization)
                self.assertNotIn(credential, result.text)

    def test_discord_invalid_token_is_not_saved(self):
        response = Mock(status_code=401)
        with patch("credential_links.requests.get", return_value=response):
            result = self.client.post("/api/miniapp/credential_links",
                                      json={"platform": "discord", "kind": "bot", "credential": "invalid-fixture"})
        self.assertEqual(result.status_code, 400)
        self.assertIn("401", result.json["error"])

    def test_qr_start_failure_returns_http_503_not_fake_success(self):
        with patch.object(app.ZaloQRLoginManager, "start_qr_session",
                          return_value={"ok": False, "message": "QR unavailable"}):
            result = self.client.post("/api/miniapp/start_qr", json={})
        self.assertEqual(result.status_code, 503)
        self.assertFalse(result.json["ok"])
        self.assertEqual(result.json["code"], "qr_start_failed")

    def test_route_does_not_fabricate_singapore_ip(self):
        session = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "ip": "203.0.113.10", "country_code": "US",
            "country_name": "United States", "city": "Example", "org": "Example ISP",
        }
        session.get.return_value = response
        with patch("zalo_login.requests.Session", return_value=session):
            result = VietnamSingaporeGeoRouter.inspect_outbound_ip_geo()
        self.assertTrue(result["ok"])
        self.assertEqual(result["country_code"], "US")
        self.assertEqual(result["ip"], "203.0.113.10")
        self.assertFalse(result["is_vn_or_sg"])
        session.close.assert_called_once()

    def test_route_failure_reports_unverified_instead_of_fake_geo(self):
        session = Mock()
        session.get.side_effect = requests.ConnectTimeout("test only")
        with patch("zalo_login.requests.Session", return_value=session):
            result = VietnamSingaporeGeoRouter.inspect_outbound_ip_geo()
        self.assertFalse(result["ok"])
        self.assertEqual(result["ip"], "")
        self.assertEqual(result["country_code"], "")
        self.assertEqual(result["route_mode"], "direct_unverified")


if __name__ == "__main__":
    unittest.main()
