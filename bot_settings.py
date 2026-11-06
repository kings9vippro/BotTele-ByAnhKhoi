"""Shared Telegram settings. Author: Dev Anh Khôi. Version: 1.3.0."""
import os

# Secrets must be supplied by the deployment environment.  Never ship a
# fallback token in source control: even a revoked token can be replayed from
# an old commit or build artifact.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "").strip()