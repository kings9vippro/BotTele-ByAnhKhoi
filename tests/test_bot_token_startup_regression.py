"""Telegram startup must use exactly one environment-backed token setting."""
import ast
import re
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

    def test_single_secret_is_read_and_trimmed(self):
        self.assertEqual(load_bot_token({"TELEGRAM_BOT_TOKEN": "  synthetic-only  "}), "synthetic-only")

    def test_obsolete_secondary_fields_are_ignored(self):
        env = {"TELEGRAM_BOT_TOKEN_ENCRYPTED": "unused",
               "TELEGRAM_BOT_TOKEN_KEY": "unused"}
        self.assertEqual(load_bot_token(env), "")

    def test_single_secret_wins_even_if_obsolete_keys_exist(self):
        env = {"TELEGRAM_BOT_TOKEN": "only-fixture",
               "TELEGRAM_BOT_TOKEN_ENCRYPTED": "invalid-ciphertext"}
        self.assertEqual(load_bot_token(env), "only-fixture")

    def test_no_literal_token_in_source_and_one_lookup(self):
        source = (Path(__file__).resolve().parents[1] / "bot_settings.py").read_text()
        self.assertIsNone(re.search(r"\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b", source))
        self.assertEqual(source.count('env.get("TELEGRAM_BOT_TOKEN")'), 1)
        self.assertNotIn('env.get("TELEGRAM_BOT_TOKEN_ENCRYPTED")', source)
        self.assertNotIn('env.get("TELEGRAM_BOT_TOKEN_KEY")', source)

    def test_empty_secret_does_not_fabricate_bot_credential(self):
        self.assertEqual(load_bot_token({}), "")


if __name__ == "__main__":
    unittest.main()
