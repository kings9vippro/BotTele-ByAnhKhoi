"""Small deployment entry point. Author: Dev Anh Khôi. Version: 1.3.0."""
import os
import sys
from importlib import import_module

runtime = import_module("glaze_app")
for required in ("ensure_telegram_bot_started", "file_create", "api_miniapp_accounts", "stop_tasks_for_thread"):
    if not callable(getattr(runtime, required, None)):
        raise RuntimeError("glaze_app.py chưa đầy đủ: thiếu " + required + ". Triển khai lại từ commit đầy đủ trên GitHub.")
sys.modules[__name__] = runtime

if __name__ == "__main__":
    runtime.app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=True)
