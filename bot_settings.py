"""Telegram configuration: secrets come from the host secret store, never source.

Supports direct secret environment variables, or optional Fernet-encrypted
ciphertext with a *separate* key secret. Nothing is printed or logged.
"""
import os
from cryptography.fernet import Fernet, InvalidToken


class BotSecretConfigurationError(RuntimeError):
    """A safe, non-credential-bearing deployment configuration error."""


def load_bot_token(environment=None):
    env = environment if environment is not None else os.environ
    direct = str(env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    encrypted = str(env.get("TELEGRAM_BOT_TOKEN_ENCRYPTED") or "").strip()
    key = str(env.get("TELEGRAM_BOT_TOKEN_KEY") or "").strip()
    if direct and encrypted:
        raise BotSecretConfigurationError(
            "Configure either TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN_ENCRYPTED, not both."
        )
    if not encrypted:
        return direct
    if not key:
        raise BotSecretConfigurationError("Missing TELEGRAM_BOT_TOKEN_KEY for encrypted token.")
    try:
        result = Fernet(key.encode("ascii")).decrypt(encrypted.encode("ascii")).decode("utf-8").strip()
    except (InvalidToken, ValueError, TypeError, UnicodeError) as exc:
        raise BotSecretConfigurationError("Encrypted Telegram token configuration is invalid.") from None
    if not result:
        raise BotSecretConfigurationError("Decrypted Telegram token is empty.")
    return result


TELEGRAM_BOT_TOKEN = load_bot_token()
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "").strip()