"""Shared Telegram settings. Author: Dev Anh Khôi. Version: 1.3.0."""
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8917587021:AAGnf2uUmNLI1r747luw8BVGi_hr3jBzWpw").strip()
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "8827605973").strip()