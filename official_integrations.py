"""Discord Interactions / Messenger Page commands. Author: Dev Anh Khôi. Version: 1.3.0."""
import base64
import hashlib
import hmac
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from flask import jsonify, request, Response

COMMANDS = ("menu", "status", "tasks", "stopall")


def init_tables(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS official_integrations(provider TEXT PRIMARY KEY, credentials TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS official_events(event_id TEXT PRIMARY KEY, created_at REAL NOT NULL)")


def register(app, db, snapshot, stop_all):
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="OfficialPage")
    slots = threading.BoundedSemaphore(16)

    def cipher():
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("glaze-official-" + str(app.secret_key)).encode()).digest()))

    def integration_rows(provider):
        conn = db()
        try:
            return conn.execute("SELECT provider, credentials FROM official_integrations WHERE provider=? OR provider LIKE ? ORDER BY provider", (provider, provider + ':%')).fetchall()
        finally:
            conn.close()
    def decode(row):
        settings = json.loads(cipher().decrypt(row[1].encode()))
        settings['_storage_key'] = row[0]
        return settings

    def config(provider, connection_id=None):
        rows = integration_rows(provider)
        if connection_id is not None:
            if not str(connection_id).isdigit():
                return None
            selected = next((row for row in rows if row[0] == provider + ':' + str(connection_id)), None)
            if selected:
                return decode(selected)
            legacy = next((row for row in rows if row[0] == provider), None)
            value = decode(legacy) if legacy else None
            return value if value and value['id'] == str(connection_id) else None
        return decode(rows[0]) if len(rows) == 1 else None

    def response_text(command):
        if command == "menu":
            return "GLAZE · Quản lý\n/menu — Bảng lệnh\n/status — Trạng thái\n/tasks — Các tác vụ\n/stopall — Gửi yêu cầu dừng tất cả tác vụ"
        if command == "stopall":
            count = stop_all()
            return f"Đã gửi yêu cầu dừng {count} tác vụ. Kiểm tra trạng thái Đang dừng/Đã dừng trong Mini App."
        data = snapshot()
        if command == "status":
            return f"GLAZE · {data['total_accs']} tài khoản đã lưu · {data['running_tasks']} tác vụ chạy · kho {data['storage_id'][:12]}"
        tasks = data["tasks"]
        return "\n".join(f"{item['name']} · {item['target_label']} · {item['status']}" for item in tasks[:15]) or "Chưa có tác vụ."

    @app.get("/api/miniapp/integrations")
    def integration_status():
        result = []
        for provider in ("discord",):
            rows = integration_rows(provider)
            if not rows:
                result.append({"provider": provider, "configured": False, "id": "", "name": ""})
            for row in rows:
                try:
                    settings = decode(row)
                    result.append({"provider": provider, "configured": True, "name": settings["name"], "id": settings["id"],
                        "callback_path": "/integrations/" + provider + '/' + settings['id'], "commands": list(COMMANDS)})
                except Exception:
                    result.append({"provider": provider, "id": row[0].partition(':')[2], "configured": False, "error": "Cần lưu lại cấu hình sau khi đổi SECRET_KEY"})
        return jsonify({"ok": True, "integrations": result})

    @app.post("/api/miniapp/integrations/configure")
    def configure():
        data = request.get_json(silent=True) or {}
        provider = data.get("provider")
        if provider != "discord":
            return jsonify({"ok": False, "error": "Nền tảng không hợp lệ"}), 400
        import os
        if not os.environ.get("SECRET_KEY"):
            return jsonify({"ok": False, "error": "Cần SECRET_KEY cố định trên máy chủ"}), 503
        token = str(data.get("token") or "").strip()
        owners = [value.strip() for value in str(data.get("owner_ids") or "").split(",") if value.strip()]
        if not token or not owners or not all(value.isdigit() for value in owners):
            return jsonify({"ok": False, "error": "Cần token ứng dụng và ID người quản lý dạng số, phân cách dấu phẩy"}), 400
        settings = {"token": token, "owners": owners}
        public_key = str(data.get("public_key") or "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{64}", public_key):
            return jsonify({"ok": False, "error": "Public Key Discord phải gồm 64 ký tự hex"}), 400
        settings["public_key"] = public_key
        url, headers = "https://discord.com/api/v10/users/@me", {"Authorization": "Bot " + token}
        try:
            with requests.get(url, headers=headers, params={}, timeout=(5, 10), allow_redirects=False) as upstream:
                if upstream.status_code != 200:
                    raise ValueError()
                profile = upstream.json()
            if not str(profile.get("id") or "").isdigit():
                raise ValueError()
            if provider == "discord" and not profile.get("bot"):
                raise ValueError()
        except (requests.RequestException, ValueError, TypeError):
            return jsonify({"ok": False, "error": "Không xác minh được Bot/Page token chính thức"}), 422
        settings.update(id=str(profile["id"]), name=str(profile.get("name") or profile.get("username") or profile["id"]))
        connection = db()
        try:
            connection.execute("INSERT OR REPLACE INTO official_integrations(provider, credentials) VALUES(?, ?)", (provider + ':' + settings['id'], cipher().encrypt(json.dumps(settings).encode()).decode()))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return jsonify({"ok": True, "message": "Đã xác minh và lưu cấu hình mã hóa. Cần đăng ký callback trong trang quản lý ứng dụng.", "callback_path": "/integrations/" + provider + '/' + settings['id']})

    @app.post("/api/miniapp/integrations/discord/commands")
    def register_discord_commands():
        settings = config("discord", (request.get_json(silent=True) or {}).get('id'))
        if not settings:
            return jsonify({"ok": False, "error": "Chưa cấu hình Discord Bot"}), 400
        commands = [{"name": name, "description": description} for name, description in zip(COMMANDS, ("Bảng lệnh GLAZE", "Trạng thái GLAZE", "Danh sách tác vụ", "Gửi yêu cầu dừng toàn bộ tác vụ"))]
        try:
            for command in commands:
                with requests.post(f"https://discord.com/api/v10/applications/{settings['id']}/commands", headers={"Authorization": "Bot " + settings["token"]}, json=command, timeout=(5, 10), allow_redirects=False) as result:
                    if result.status_code not in (200, 201):
                        raise ValueError()
        except (ValueError, requests.RequestException):
            return jsonify({"ok": False, "error": "Discord chưa chấp nhận đăng ký lệnh"}), 502
        return jsonify({"ok": True, "message": "Đã đăng ký /menu, /status, /tasks, /stopall với Discord"})

    @app.post("/api/miniapp/integrations/disconnect")
    def disconnect():
        provider = (request.get_json(silent=True) or {}).get("provider")
        if provider != "discord":
            return jsonify({"ok": False, "error": "Nền tảng không hợp lệ"}), 400
        connection_id = (request.get_json(silent=True) or {}).get('id')
        if connection_id is not None and not str(connection_id).isdigit():
            return jsonify({"ok": False, "error": "ID kết nối không hợp lệ"}), 400
        settings = config(provider) if connection_id is None else None
        if connection_id is None and not settings:
            return jsonify({"ok": False, "error": "Cần chọn đúng ID kết nối muốn xóa"}), 400
        storage_key = provider + ':' + str(connection_id) if connection_id is not None else settings['_storage_key']
        conn = db()
        try:
            conn.execute("DELETE FROM official_integrations WHERE provider=?", (storage_key,))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True, "message": "Đã xóa cấu hình lưu tại bot. Quyền ứng dụng bên nhà cung cấp có thể thu hồi trong trang quản lý ứng dụng."})

    @app.post("/integrations/discord")
    @app.post("/integrations/discord/<connection_id>")
    def discord_interaction(connection_id=None):
        raw = request.stream.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            return Response(status=413)
        try:
            data = json.loads(raw)
        except ValueError:
            return Response(status=400)
        if not isinstance(data, dict):
            return Response(status=400)
        settings = config("discord", connection_id or data.get('application_id'))
        if not settings:
            return Response(status=503)
        timestamp = request.headers.get("X-Signature-Timestamp", "")
        try:
            if abs(time.time() - int(timestamp)) > 300:
                raise ValueError()
            signature = bytes.fromhex(request.headers.get("X-Signature-Ed25519", ""))
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(settings["public_key"])).verify(signature, timestamp.encode() + raw)
        except (ValueError, InvalidSignature):
            return Response(status=401)
        if data.get("type") == 1:
            return jsonify({"type": 1})
        if data.get("type") != 2 or not str(data.get("id") or "").isdigit():
            return Response(status=400)
        user_id = str(((data.get("member") or {}).get("user") or data.get("user") or {}).get("id") or "")
        command = str((data.get("data") or {}).get("name") or "")
        if user_id not in settings["owners"] or command not in COMMANDS:
            return jsonify({"type": 4, "data": {"content": "Bạn chưa được cấp quyền cho lệnh này.", "flags": 64}})
        # An interaction ID is used once, including across process restarts.
        if not claim_event("discord:" + str(data.get("id") or "")):
            return jsonify({"type": 4, "data": {"content": "Yêu cầu đã được tiếp nhận.", "flags": 64}})
        return jsonify({"type": 4, "data": {"content": response_text(command)[:1900], "flags": 64, "allowed_mentions": {"parse": []}}})

    def claim_event(event_id):
        conn = db()
        try:
            changed = conn.execute("INSERT OR IGNORE INTO official_events VALUES(?, ?)", (event_id, time.time())).rowcount
            conn.commit()
            return changed == 1
        finally:
            conn.close()
