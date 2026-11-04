"""Access-control regressions for existing dashboard and Mini App routes."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('DISABLE_TELEGRAM_BOT', '1')
os.environ.setdefault('DISABLE_BACKGROUND_WORKERS', '1')
import app


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_sensitive_routes_require_authorization_before_handler(self):
        paths = [('/api/discord/reg_login', 'post'), ('/api/messenger/login_credentials', 'post'),
                 ('/api/proxies', 'get'), ('/task/stop_all', 'post'),
                 ('/account/add', 'post'), ('/file/create', 'post')]
        for path, method in paths:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertIn(response.status_code, (401, 403))

    def test_authenticated_dashboard_can_reach_existing_handler(self):
        with self.client.session_transaction() as session:
            session['logged_in'] = True
        with patch.object(app, 'login_discord_reg_session', return_value={'ok': False, 'error': 'fixture'}) as handler:
            response = self.client.post('/api/discord/reg_login', json={})
        self.assertEqual(response.status_code, 400)
        handler.assert_called_once()

    def test_cross_origin_mutation_rejected_for_cookie_session(self):
        with self.client.session_transaction() as session:
            session['logged_in'] = True
        with patch.object(app, 'login_discord_reg_session') as handler:
            response = self.client.post('/api/discord/reg_login', json={}, headers={'Origin': 'https://other.example'})
        self.assertEqual(response.status_code, 403)
        handler.assert_not_called()

    def test_provider_webhooks_remain_independently_authenticated(self):
        # Webhook verifies its own signature; it must not require dashboard login.
        response = self.client.post('/integrations/discord', json={})
        self.assertNotEqual(response.status_code, 401)

    def test_rate_limiter_reaches_limit(self):
        with patch.object(app, 'get_client_ip', return_value='rate-test-isolated'):
            with app.SECURITY_LOCK:
                app.API_RATE_BUCKETS.pop('rate-test-isolated', None)
            for _ in range(320):
                self.assertNotEqual(self.client.get('/api/logo').status_code, 429)
            self.assertEqual(self.client.get('/api/logo').status_code, 429)
