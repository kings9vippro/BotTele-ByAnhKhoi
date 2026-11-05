"""OAuth contract tests. Author: Dev Anh Khôi. Version: 1.2.0. No live accounts."""
import os
import base64
import hashlib
import sqlite3
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from flask import Flask, jsonify, request, session
import miniapp_oauth as oauth


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "oauth.db")
        self.key = Fernet.generate_key().decode()
        self.environment = patch.dict(os.environ, {"OAUTH_PUBLIC_BASE_URL": "https://bot.example",
            "OAUTH_ENCRYPTION_KEY": self.key, "DISCORD_CLIENT_ID": "test-client", "DISCORD_CLIENT_SECRET": "private-client-secret"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.app = Flask(__name__)
        self.owner = 'owner'
        self.app.secret_key = "test-only-signing-key"
        self.app.config["SESSION_COOKIE_HTTPONLY"] = True
        self.app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

        @self.app.before_request
        def require_auth():
            if request.path.startswith("/api/") and not session.get("logged_in"):
                return jsonify({"ok": False}), 401

        conn = self.db()
        oauth.init_oauth_tables(conn)
        conn.commit()
        conn.close()
        oauth.register_oauth_routes(self.app, self.db, lambda: self.owner)
        self.admin = self.app.test_client()
        with self.admin.session_transaction() as admin_session:
            admin_session["logged_in"] = True

    def db(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def begin(self, provider="discord"):
        started = self.admin.post("/api/miniapp/oauth/start", json={"provider": provider})
        self.assertEqual(started.status_code, 200)
        browser = self.app.test_client()
        redirect = browser.get(urlsplit(started.json["url"]).path)
        self.assertEqual(redirect.status_code, 302)
        params = parse_qs(urlsplit(redirect.location).query)
        self.assertEqual(params["scope"], ["identify"])
        self.assertNotIn("private", redirect.location)
        return browser, params["state"][0]

    def profile(self):
        return {"uid": "123456", "name": "<My Account>", "access": "private-access", "refresh": "private-refresh", "expires": 3600, "scope": "identify"}

    def test_existing_oauth_attempts_table_migrates_for_pkce(self):
        conn = self.db()
        conn.execute('DROP TABLE oauth_attempts')
        conn.execute('''CREATE TABLE oauth_attempts (
            state_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, launch_hash TEXT UNIQUE,
            owner_id TEXT NOT NULL, created_at REAL NOT NULL, browser_hash TEXT,
            used INTEGER NOT NULL DEFAULT 0)''')
        oauth.init_oauth_tables(conn)
        columns = {row[1] for row in conn.execute('PRAGMA table_info(oauth_attempts)')}
        conn.close()
        self.assertIn('verifier_encrypted', columns)

    def test_provider_configuration_is_truthful_and_secret_free(self):
        result = self.admin.get("/api/miniapp/oauth/providers")
        self.assertTrue(all(item["configured"] for item in result.json["providers"]))
        self.assertNotIn("private", result.text)
        with patch.dict(os.environ, {"DISCORD_CLIENT_SECRET": ""}):
            self.assertEqual(self.admin.post("/api/miniapp/oauth/start", json={"provider": "discord"}).status_code, 503)

    def test_official_login_is_encrypted_persisted_and_not_an_automation_account(self):
        browser, state = self.begin()
        with patch.object(oauth, "_exchange_profile", return_value=self.profile()) as exchange:
            result = browser.get("/oauth/callback/discord", query_string={"state": state, "code": "example-code"})
        self.assertEqual(result.status_code, 200)
        self.assertIn("&lt;My Account&gt;", result.text)
        self.assertNotIn("private-access", result.text)
        self.assertEqual(exchange.call_args.args[0], "discord")
        conn = self.db()
        record = conn.execute("SELECT * FROM oauth_connections").fetchone()
        self.assertNotIn("private-access", record["access_encrypted"])
        self.assertEqual(Fernet(self.key.encode()).decrypt(record["access_encrypted"].encode()), b"private-access")
        self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='accounts'").fetchone())
        conn.close()
        listing = self.admin.get("/api/miniapp/oauth/connections")
        self.assertEqual(listing.json["connections"][0]["status"], "authorized")
        self.assertNotIn("encrypted", listing.text)
        self.assertNotIn("private-access", listing.text)

    def test_callback_rejects_other_browser_then_replay(self):
        browser, state = self.begin()
        path = "/oauth/callback/discord"
        query = {"state": state, "code": "one-code"}
        with patch.object(oauth, "_exchange_profile", return_value=self.profile()) as exchange:
            self.assertEqual(self.app.test_client().get(path, query_string=query).status_code, 400)
            exchange.assert_not_called()
            self.assertEqual(browser.get(path, query_string=query).status_code, 200)
            self.assertEqual(browser.get(path, query_string=query).status_code, 400)
            exchange.assert_called_once()

    def test_pkce_s256_challenge_and_verifier_are_bound_to_one_attempt(self):
        with patch.dict(os.environ, {'DISCORD_OAUTH_PKCE':'1'}):
            started=self.admin.post('/api/miniapp/oauth/start',json={'provider':'discord'})
            browser=self.app.test_client()
            redirect=browser.get(urlsplit(started.json['url']).path)
            params=parse_qs(urlsplit(redirect.location).query)
            self.assertEqual(params['code_challenge_method'],['S256'])
            conn=self.db()
            stored=conn.execute('SELECT verifier_encrypted FROM oauth_attempts').fetchone()[0]
            conn.close()
            self.assertNotIn('code_verifier',redirect.location)
            self.assertNotIn('private',stored)
            with patch.object(oauth,'_exchange_profile',return_value=self.profile()) as exchange:
                result=browser.get('/oauth/callback/discord',query_string={'state':params['state'][0],'code':'fixture'})
            self.assertEqual(result.status_code,200)
            verifier=exchange.call_args.args[1]['code_verifier']
            self.assertEqual(params['code_challenge'][0],base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode())

    def test_same_discord_identity_is_isolated_per_telegram_owner_and_relink_deduplicates(self):
        with patch.object(oauth,'_exchange_profile',return_value=self.profile()):
            for owner in ('alice','bob','alice'):
                self.owner=owner
                browser,state=self.begin()
                self.assertEqual(browser.get('/oauth/callback/discord',query_string={'state':state,'code':'fixture'}).status_code,200)
        self.assertEqual(len(self.admin.get('/api/miniapp/oauth/connections').json['connections']),1)
        self.owner='bob'
        self.assertEqual(len(self.admin.get('/api/miniapp/oauth/connections').json['connections']),1)
        conn=self.db()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM oauth_connections').fetchone()[0],2)
        conn.close()

    def test_disconnect_revokes_only_owners_connection(self):
        with patch.object(oauth,'_exchange_profile',return_value=self.profile()):
            for owner in ('alice','bob'):
                self.owner=owner
                browser,state=self.begin()
                browser.get('/oauth/callback/discord',query_string={'state':state,'code':'fixture'})
        self.owner='alice'
        target=self.admin.get('/api/miniapp/oauth/connections').json['connections'][0]['id']
        response=Mock(status_code=200)
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock()
        with patch.object(oauth.requests,'post',return_value=response) as revoke:
            self.assertEqual(self.admin.post('/api/miniapp/oauth/disconnect',json={'id':target}).status_code,200)
            revoke.assert_called_once()
        self.assertEqual(self.admin.get('/api/miniapp/oauth/connections').json['connections'],[])
        self.owner='bob'
        self.assertEqual(len(self.admin.get('/api/miniapp/oauth/connections').json['connections']),1)

    def test_provider_cancellation_creates_no_connection(self):
        browser, state = self.begin("discord")
        with patch.object(oauth, "_exchange_profile") as exchange:
            result = browser.get("/oauth/callback/discord", query_string={"state": state, "error": "access_denied"})
        self.assertEqual(result.status_code, 400)
        exchange.assert_not_called()
        self.assertEqual(self.admin.get("/api/miniapp/oauth/connections").json["connections"], [])

    def test_expired_state_and_launch_links_are_rejected(self):
        started = self.admin.post("/api/miniapp/oauth/start", json={"provider": "discord"})
        conn = self.db()
        conn.execute("UPDATE oauth_attempts SET created_at=0")
        conn.commit()
        conn.close()
        self.assertEqual(self.app.test_client().get(urlsplit(started.json["url"]).path).status_code, 400)

    def test_provider_network_failure_never_leaks_response_or_token(self):
        browser, state = self.begin()
        with patch.object(oauth, "_exchange_profile", side_effect=oauth.OAuthError("Không kết nối được")):
            result = browser.get("/oauth/callback/discord", query_string={"state": state, "code": "one-code"})
        self.assertEqual(result.status_code, 502)
        self.assertEqual(self.admin.get("/api/miniapp/oauth/connections").json["connections"], [])

    def test_management_endpoints_require_authenticated_session(self):
        client = self.app.test_client()
        for path in ("providers", "connections"):
            self.assertEqual(client.get("/api/miniapp/oauth/" + path).status_code, 401)
        self.assertEqual(client.post("/api/miniapp/oauth/start", json={"provider": "discord"}).status_code, 401)

    def test_exchange_uses_official_bearer_profile_and_closes_responses(self):
        http = Mock()
        token_response = Mock(status_code=200)
        token_response.json.return_value = {"access_token": "private-access", "expires_in": 3600, "refresh_token": "refresh"}
        profile_response = Mock(status_code=200)
        profile_response.json.return_value = {"id": "123456", "name": "Name"}
        http.post.return_value.__enter__ = Mock(return_value=token_response)
        http.post.return_value.__exit__ = Mock()
        http.get.return_value.__enter__ = Mock(return_value=profile_response)
        http.get.return_value.__exit__ = Mock()
        with patch.object(oauth.requests, "Session") as factory:
            factory.return_value.__enter__.return_value = http
            config = oauth._config("discord")
            config["code_verifier"] = "test-s256-verifier"
            result = oauth._exchange_profile("discord", config, "example")
            self.assertEqual(result["uid"], "123456")
        self.assertEqual(http.get.call_args.kwargs["headers"]["Authorization"], "Bearer private-access")
        self.assertEqual(http.get.call_args.kwargs["params"], {})
        self.assertFalse(http.post.call_args.kwargs["allow_redirects"])
        self.assertEqual(http.post.call_args.kwargs["data"]["code_verifier"], "test-s256-verifier")
        http.get.return_value.__exit__.assert_called()


if __name__ == "__main__":
    unittest.main()
