"""Encrypt an existing bot token without printing its plaintext.

Input: TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN_KEY in this process environment.
Output: Fernet ciphertext only, to be stored in a secure deployment secret.
Never store the decryption key next to ciphertext in source control.
"""
import os
import sys
from cryptography.fernet import Fernet


def main():
    token = str(os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    key = str(os.environ.get("TELEGRAM_BOT_TOKEN_KEY") or "").strip()
    if not token or not key:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN_KEY in your private environment.", file=sys.stderr)
        return 2
    try:
        encrypted = Fernet(key.encode("ascii")).encrypt(token.encode("utf-8")).decode("ascii")
    except (ValueError, UnicodeError):
        print("The encryption key must be a valid Fernet key.", file=sys.stderr)
        return 2
    print(encrypted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())