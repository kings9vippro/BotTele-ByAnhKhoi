"""Validate deployment sources without starting clients or DB. Author: Dev Anh Khôi. Version: 1.3.0."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"ensure_telegram_bot_started", "file_create", "api_miniapp_accounts", "stop_tasks_for_thread"}


def check_runtime(source, filename="glaze_app.py"):
    tree = ast.parse(source, filename=filename, feature_version=(3, 11))
    names = {item.name for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
    missing = REQUIRED - names
    if missing:
        raise ValueError("Runtime chưa đầy đủ; thiếu: " + ", ".join(sorted(missing)))


def check_entry(source):
    tree = ast.parse(source, filename="app.py", feature_version=(3, 11))
    loads_shared = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id == "import_module" and node.args
                       and isinstance(node.args[0], ast.Constant) and node.args[0].value == "glaze_app"
                       for node in ast.walk(tree))
    if not loads_shared:
        raise ValueError("app.py phải nạp runtime glaze_app; không ghi đè bằng bản app.py cũ bị rút ngắn")


def main():
    paths = ("app.py", "glaze_app.py", "bot_settings.py", "task_control.py", "official_integrations.py",
             "app_storage.py", "miniapp_oauth.py", "command_metrics.py", "command_catalog.py", "get_ck_im_zalo.py", "zalo_login.py", "gunicorn.conf.py", "durable_tasks.py", "control_plane.py", "task_registry.py", "account_views.py", "zalo_group_checker.py", "zalo_lag_engine.py")
    for name in paths:
        source = (ROOT / name).read_text(encoding="utf-8")
        if name == "app.py":
            check_entry(source)
        elif name == "glaze_app.py":
            check_runtime(source, name)
        else:
            ast.parse(source, filename=name, feature_version=(3, 11))
    ast.parse((ROOT / "scripts" / "encrypt_bot_token.py").read_text(encoding="utf-8"),
              filename="scripts/encrypt_bot_token.py", feature_version=(3, 11))
    print("Deployment sources: Python 3.11 syntax and runtime entry points verified")


if __name__ == "__main__":
    try:
        main()
    except SyntaxError as error:
        print(f"Deployment syntax error: {error.filename}:{error.lineno}: {error.msg}", file=sys.stderr)
        raise SystemExit(1) from None
    except (OSError, ValueError) as error:
        print(f"Deployment check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None