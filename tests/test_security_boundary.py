"""Regression coverage for the runtime's HTTP authorization boundary."""
import os
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
