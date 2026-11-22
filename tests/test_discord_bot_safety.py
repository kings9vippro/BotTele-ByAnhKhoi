"""Discord bot token transport and safe send integration contracts."""
import os
import unittest
from unittest.mock import Mock, patch

import requests
import test_data_consistency as fixtures

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "discord-bot-fixtures-only")

import app


class DiscordBotSafetyTests(unittest.TestCase):
    def setUp(self):
        fixtures.DataConsistencyTests.setUp(self)

    def test_user_session_token_rejected_without_request(self):
        with patch("credential_links.requests.get") as request:
            response = self.client.post("/api/miniapp/credential_links", json={
                "platform": "discord", "kind": "user", "credential": "fixture-user-token"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["code"], "discord_invalid")
        self.assertIn("Bot token", response.json["error"])
        request.assert_not_called()

    def test_discord_transport_timeout_is_504_and_does_not_lock_database(self):
        with patch("credential_links.requests.get", side_effect=requests.ReadTimeout("secret-bearing-url")), \
             patch.object(app, "db", side_effect=AssertionError("DB must stay closed before provider verification")):
            response = self.client.post("/api/miniapp/credential_links", json={
                "platform": "discord", "kind": "bot", "credential": "fixture-bot-token"})
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json["code"], "discord_timeout")
        self.assertNotIn("secret-bearing-url", response.text)

    def test_discord_bot_verification_has_bounded_deadline(self):
        fake = Mock(status_code=200)
        fake.json.return_value = {"id": "123456789", "username": "Test Bot", "bot": True}
        with patch("credential_links.requests.get", return_value=fake) as get:
            response = self.client.post("/api/miniapp/credential_links", json={
                "platform": "discord", "kind": "bot", "credential": "fixture-bot-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_args.kwargs["timeout"], (2, 6))
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        fake.close.assert_called_once()

    def test_oauth2_token_can_verify_identity_but_cannot_send_message(self):
        fake = Mock(status_code=200)
        fake.json.return_value = {"id": "123456789", "username": "OAuth fixture"}
        with patch("credential_links.requests.get", return_value=fake):
            link = self.client.post("/api/miniapp/credential_links", json={
                "platform": "discord", "kind": "oauth2", "credential": "fixture-oauth-access"}).json["link"]
        with patch("credential_links.requests.post") as send:
            response = self.client.post("/api/miniapp/credential_links/send_discord", json={
                "id": link["id"], "channel_id": "123456789012345678", "content": "hello"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Bot token", response.json["error"])
        send.assert_not_called()

    def test_invalid_token_is_not_saved_or_retried(self):
        fake = Mock(status_code=401)
        with patch("credential_links.requests.get", return_value=fake) as get:
            response = self.client.post("/api/miniapp/credential_links", json={
                "platform": "discord", "kind": "bot", "credential": "fixture-invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(self.client.get("/api/miniapp/credential_links").json["links"], [])


if __name__ == "__main__":
    unittest.main()
