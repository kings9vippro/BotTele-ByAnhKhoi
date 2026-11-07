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

    def test_host_secret_is_loaded_without_code_fallback(self):
        self.assertEqual(load_bot_token({"TELEGRAM_BOT_TOKEN": "test-value"}), "test-value")
        self.assertEqual(load_bot_token({}), "")


if __name__ == "__main__":
    unittest.main()
