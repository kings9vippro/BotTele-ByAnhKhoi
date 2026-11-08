"""Telegram configuration: exactly one bot token from a host secret.

Set TELEGRAM_BOT_TOKEN in the service environment. Never paste a real
Telegram bot token into a source file tracked by GitHub.
"""
import os


class BotSecretConfigurationError(RuntimeError):
    """Safe startup configuration error without credential contents."""


def load_bot_token(environment=None):
    env = environment if environment is not None else os.environ
    if not hasattr(env, "get"):
        raise BotSecretConfigurationError(
            "load_bot_token requires an environment mapping. Set TELEGRAM_BOT_TOKEN in hosting secrets."
        )
    return str(env.get("TELEGRAM_BOT_TOKEN") or "").strip()


TELEGRAM_BOT_TOKEN = load_bot_token()
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "8827605973").strip()