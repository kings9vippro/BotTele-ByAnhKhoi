"""Prevent a direct-string Telegram credential from breaking Gunicorn import."""
import ast
import unittest
from pathlib import Path

from bot_settings import BotSecretConfigurationError, load_bot_token


class TelegramTokenBootstrapRegressionTests(unittest.TestCase):
    def test_settings_use_zero_arg_environment_loader(self):
        source = (Path(__file__).resolve().parents[1] / "bot_settings.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "TELEGRAM_BOT_TOKEN"
                               for target in node.targets)]
        self.assertEqual(len(assignments), 1)
        call = assignments[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "load_bot_token")
        self.assertEqual(call.args, [])
        self.assertEqual(call.keywords, [])

    def test_direct_string_argument_is_rejected_without_echo(self):
        candidate = "invalid-direct-credential"
        with self.assertRaises(BotSecretConfigurationError) as raised:
            load_bot_token(candidate)
        self.assertNotIn(candidate, str(raised.exception))
        self.assertIn("environment", str(raised.exception).lower())

    def test_both_secrets_use_direct_and_emit_safe_warning(self):
        env = {"TELEGRAM_BOT_TOKEN": "ci-direct-token",
               "TELEGRAM_BOT_TOKEN_ENCRYPTED": "invalid-ciphertext"}
        with self.assertLogs("bot_settings", level="WARNING") as logs:
            token = load_bot_token(env)
        self.assertEqual(token, "ci-direct-token")
        self.assertNotIn("ci-direct-token", "\n".join(logs.output))
        self.assertNotIn("invalid-ciphertext", "\n".join(logs.output))

    def test_encrypted_only_fails_safely_without_key(self):
        with self.assertRaises(BotSecretConfigurationError) as raised:
            load_bot_token({"TELEGRAM_BOT_TOKEN_ENCRYPTED": "some-ciphertext"})
        self.assertIn("TELEGRAM_BOT_TOKEN_KEY", str(raised.exception))
        self.assertNotIn("some-ciphertext", str(raised.exception))

    def test_encrypted_only_supports_real_fernet_token(self):
        from cryptography.fernet import Fernet
        secret = Fernet.generate_key()
        ciphertext = Fernet(secret).encrypt(b"ci-encrypted-token")
        actual = load_bot_token({"TELEGRAM_BOT_TOKEN_ENCRYPTED": ciphertext.decode("ascii"),
                                 "TELEGRAM_BOT_TOKEN_KEY": secret.decode("ascii")})
        self.assertEqual(actual, "ci-encrypted-token")

    def test_neither_secret_is_loaded_from_source(self):
        self.assertEqual(load_bot_token({}), "")
        source = (Path(__file__).resolve().parents[1] / "bot_settings.py").read_text()
        import re
        self.assertIsNone(re.search(r"\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b", source))
        self.assertIn('env.get("TELEGRAM_BOT_TOKEN") or ""', source)

    def test_host_secret_is_loaded_without_code_fallback(self):
        self.assertEqual(load_bot_token({"TELEGRAM_BOT_TOKEN": "test-value"}), "test-value")
        self.assertEqual(load_bot_token({}), "")


if __name__ == "__main__":
    unittest.main()