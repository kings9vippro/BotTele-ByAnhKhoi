"""Telegram configuration: secrets come from the host secret store, never source.

Supports direct secret environment variables, or optional Fernet-encrypted
ciphertext with a *separate* key secret. Credential values are never logged.
"""
import os
from cryptography.fernet import Fernet, InvalidToken


class BotSecretConfigurationError(RuntimeError):
    """A safe, non-credential-bearing deployment configuration error."""


def load_bot_token(environment=None):
    env = environment if environment is not None else os.environ
    if not hasattr(env, "get"):
        raise BotSecretConfigurationError(
            "load_bot_token requires an environment mapping. Set TELEGRAM_BOT_TOKEN in hosting secrets."
        )
    # Direct env secrets take precedence for backward-compatible hosting setup.
    # A second encrypted value must never prevent the web process from booting.
    direct = str(env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    encrypted = str(env.get("TELEGRAM_BOT_TOKEN_ENCRYPTED") or "").strip()
    key = str(env.get("TELEGRAM_BOT_TOKEN_KEY") or "").strip()
    if direct:
        if encrypted:
            import logging
            logging.getLogger(__name__).warning(
                "Both Telegram token settings exist; using TELEGRAM_BOT_TOKEN. "
                "Remove TELEGRAM_BOT_TOKEN_ENCRYPTED to avoid ambiguity."
            )
        return direct
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
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "8827605973").strip()