"""Regression coverage for the runtime's HTTP authorization boundary."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

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

    def test_retired_integrations_are_inaccessible_even_with_session(self):
        with self.client.session_transaction() as s:s['logged_in']=True
        for path in ['/api/discord/reg_login','/api/messenger/login_credentials','/integrations/facebook','/oauth/callback/facebook']:
            self.assertEqual(self.client.post(path,json={}).status_code,410)

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
