"""Shared Telegram settings. Author: Dev Anh Khôi. Version: 1.3.0."""
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8825276987:AAHFXQbdoTofAGKkM0zMN3a19xPMd5sxE8Y").strip()
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "8827605973").strip()
