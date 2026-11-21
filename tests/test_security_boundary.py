"""Regression coverage for the runtime's HTTP authorization boundary."""
import os
import hashlib
import hmac
import json
import time
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

os.environ.setdefault('DISABLE_TELEGRAM_BOT', '1')
os.environ.setdefault('DISABLE_BACKGROUND_WORKERS', '1')
import app


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_sensitive_routes_require_auth_before_handler(self):
        for path, method in [('/api/proxies','get'),('/task/stop_all','post'),
                             ('/account/add','post'),('/file/create','post'),
                             ('/api/miniapp/control','get'),('/api/miniapp/events','get')]:
            with self.subTest(path=path):
                self.assertIn(getattr(self.client,method)(path).status_code,(401,403))

    def test_health_probe_is_public_and_minimal(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body.get('ok'), True)
        self.assertNotIn('admin_id', body)

    def test_watchdog_uses_public_health_probe(self):
        source = (Path(__file__).resolve().parents[1] / 'glaze_app.py').read_text()
        self.assertIn('requests.get(f"{ext_url}/healthz", timeout=5)', source)
        self.assertNotIn('requests.get(f"{ext_url}/api/network/gateways", timeout=5)', source)

    def test_retired_integrations_are_inaccessible_even_with_session(self):
        with self.client.session_transaction() as s:s['logged_in']=True
        for path in ['/api/discord/reg_login','/api/messenger/login_credentials','/integrations/facebook']:
            self.assertEqual(self.client.post(path,json={}).status_code,410)
        self.assertEqual(self.client.post('/oauth/callback/facebook',json={}).status_code,410)
        self.assertEqual(self.client.get('/oauth/callback/facebook').status_code,410)

    def test_legacy_account_credentials_are_rejected(self):
        with self.client.session_transaction() as s:s['logged_in']=True
        self.assertEqual(self.client.post('/account/add', data={'platform':'messenger','cookies':'legacy'}).status_code,410)
        self.assertEqual(self.client.post('/account/add', data={'platform':'discord','reg_email':'a@example.test','reg_password':'not-a-password'}).status_code,410)

    def test_cross_origin_cannot_mutate(self):
        with self.client.session_transaction() as s:s['logged_in']=True
        response=self.client.post('/api/miniapp/notifications/stop_all',headers={'Origin':'https://evil.example'})
        self.assertEqual(response.status_code,403)
        response=self.client.post('/file/create',headers={'Sec-Fetch-Site':'cross-site'})
        self.assertEqual(response.status_code,403)

    def test_webhook_uses_its_own_signature_not_browser_auth(self):
        response=self.client.post('/integrations/discord',json={})
        self.assertNotEqual(response.status_code,401)

    def test_rate_limiter_reaches_threshold(self):
        with patch.object(app,'get_client_ip',return_value='rate-test-only'):
            with app.SECURITY_LOCK:app.API_RATE_BUCKETS.pop('rate-test-only',None)
            for _ in range(320):self.assertNotEqual(self.client.get('/api/logo').status_code,429)
            self.assertEqual(self.client.get('/api/logo').status_code,429)

    def test_zalo_credentials_never_export_or_leave_process_for_totp(self):
        root = Path(__file__).resolve().parents[1]
        bot_source = (root / 'get_ck_im_zalo.py').read_text()
        web_source = (root / 'glaze_app.py').read_text()
        self.assertNotIn('API_2FA', bot_source)
        self.assertNotIn('API_2FA', web_source)
        self.assertNotIn('export_acc_token:', bot_source)
        self.assertIn('show_acc_details:', bot_source)
        self.assertNotIn('TRỌN BỘ TOKEN & COOKIE', bot_source)
        self.assertIn('browser-safe inventory', web_source)
        self.assertIn('public_keys =', web_source)

    def test_zalo_vault_and_qr_endpoints_redact_session_material(self):
        class FakeConn:
            def execute(self, *_args, **_kwargs):
                return self
            def fetchall(self):
                return [{
                    'uid': 'uid-1', 'display_name': 'Zalo Test',
                    'imei': 'imei-secret', 'cookies_json': '{"zpw_sek":"cookie-secret"}',
                    'zpw_enk': 'enk-secret', 'updated_at': 1,
                }]
            def close(self):
                return None

        with patch.object(app, 'db', return_value=FakeConn()):
            inventory = app.ZaloCookieVaultEngine.list_vault_records()
        self.assertEqual(inventory[0]['uid'], 'uid-1')
        self.assertNotIn('cookies', inventory[0])
        self.assertNotIn('cookies_str', inventory[0])
        self.assertNotIn('imei', inventory[0])

        with self.client.session_transaction() as s:
            s['logged_in'] = True
        with patch.object(app.ZaloQRLoginManager, 'start_qr_session', return_value={
            'ok': True, 'session_id': 's1', 'status': 'waiting_scan',
            'message': 'ready', 'qr_base64': 'qr', 'cookies': {'zpw_sek': 'secret'},
            'file_content': 'Cookie: secret', 'zpw_enk': 'secret',
        }):
            response = self.client.post('/api/zalo/qr_start', json={})
        body = response.get_json()
        self.assertEqual(body['session_id'], 's1')
        self.assertNotIn('cookies', body)
        self.assertNotIn('file_content', body)
        self.assertNotIn('zpw_enk', body)

    def test_zalo_login_uses_first_party_endpoints_only(self):
        source = (Path(__file__).resolve().parents[1] / 'zalo_login.py').read_text()
        self.assertNotIn('lengocanh.vercel.app', source)
        self.assertNotIn('3app_vip/bot.py', source)

    def test_telegram_bot_token_is_environment_only(self):
        source = (Path(__file__).resolve().parents[1] / 'bot_settings.py').read_text()
        self.assertIn("def load_bot_token(", source)
        self.assertIn('env.get("TELEGRAM_BOT_TOKEN")', source)
        self.assertNotRegex(source, r'TELEGRAM_BOT_TOKEN\s*=\s*[^\n]*:[A-Za-z0-9_-]{20,}')
        self.assertIn('os.environ.get("TELEGRAM_ADMIN_ID", "")', source)
        self.assertNotRegex(source, r'TELEGRAM_ADMIN_ID\s*=\s*[^\n]*"[0-9]{6,}"')

    @staticmethod
    def _signed_launch(user_id, *, auth_date=None):
        values = {
            "auth_date": str(int(time.time() if auth_date is None else auth_date)),
            "user": json.dumps({"id": int(user_id), "first_name": "Fixture"}, separators=(",", ":")),
        }
        key = hmac.new(b"WebAppData", os.environ["TELEGRAM_BOT_TOKEN"].encode(), hashlib.sha256).digest()
        check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        values["hash"] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
        return urlencode(values)

    def test_miniapp_auth_errors_are_classified_without_disclosing_launch_data(self):
        missing = self.client.get('/api/miniapp/session')
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.json['code'], 'missing_init_data')

        invalid = self.client.get('/api/miniapp/session', headers={'X-Telegram-Init-Data': 'auth_date=1&hash=' + '0' * 64})
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json['code'], 'expired_init_data')

        expired = self.client.get('/api/miniapp/session', headers={
            'X-Telegram-Init-Data': self._signed_launch(987654321, auth_date=time.time() - 86401)
        })
        self.assertEqual(expired.status_code, 401)
        self.assertEqual(expired.json['code'], 'expired_init_data')

        denied = self.client.get('/api/miniapp/session', headers={
            'X-Telegram-Init-Data': self._signed_launch(987654321)
        })
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json['code'], 'unauthorized_account')
        self.assertNotIn('tgWebAppData', denied.text)

        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': ''}):
            misconfigured = self.client.get('/api/miniapp/session')
        self.assertEqual(misconfigured.status_code, 503)
        self.assertEqual(misconfigured.json['code'], 'server_configuration')
