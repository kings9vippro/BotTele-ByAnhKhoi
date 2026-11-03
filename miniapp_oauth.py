"""Official, admin-initiated OAuth connections. Author: Dev Anh Khôi. Version: 1.2.0.

OAuth identities are deliberately separate from legacy chat automation accounts.
No passwords, browser cookies, self-bot tokens or device impersonation are used.
"""
import hashlib
import hmac
import os
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

import requests
from cryptography.fernet import Fernet
from flask import Response, jsonify, render_template_string, request, session

PROVIDERS = {"discord": "Discord", "facebook": "Facebook"}
ATTEMPT_TTL = 300


class OAuthError(ValueError):
    pass


def init_oauth_tables(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS oauth_attempts (
        state_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, launch_hash TEXT UNIQUE,
        owner_id TEXT NOT NULL, created_at REAL NOT NULL, browser_hash TEXT,
        used INTEGER NOT NULL DEFAULT 0
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS oauth_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
        provider_uid TEXT NOT NULL, owner_id TEXT NOT NULL, display_name TEXT NOT NULL,
        access_encrypted TEXT NOT NULL, refresh_encrypted TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL, expires_at REAL NOT NULL, connected_at REAL NOT NULL,
        UNIQUE(provider, provider_uid, owner_id)
    )""")


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _config(provider):
    if provider not in PROVIDERS:
        raise OAuthError("Nền tảng không được hỗ trợ")
    base = (os.environ.get("OAUTH_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    parsed = urlsplit(base)
    missing = []
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        missing.append("OAUTH_PUBLIC_BASE_URL (HTTPS, không có đường dẫn)")
    prefix = "DISCORD" if provider == "discord" else "FACEBOOK"
    id_key = prefix + ("_CLIENT_ID" if provider == "discord" else "_APP_ID")
    secret_key = prefix + ("_CLIENT_SECRET" if provider == "discord" else "_APP_SECRET")
    client_id, client_secret = os.environ.get(id_key, "").strip(), os.environ.get(secret_key, "").strip()
    for key, value in ((id_key, client_id), (secret_key, client_secret)):
        if not value:
            missing.append(key)
    encryption_key = os.environ.get("OAUTH_ENCRYPTION_KEY", "").strip()
    try:
        cipher = Fernet(encryption_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        cipher = None
        missing.append("OAUTH_ENCRYPTION_KEY (Fernet)")
    version = os.environ.get("FACEBOOK_GRAPH_VERSION", "").strip()
    if provider == "facebook" and not re.fullmatch(r"v\d+\.\d+", version):
        missing.append("FACEBOOK_GRAPH_VERSION (phiên bản Meta app đang dùng)")
    return {"missing": missing, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": base + "/oauth/callback/" + provider, "cipher": cipher,
            "version": version, "base": base}


def _public_connections(db, owner_id):
    connection = db()
    try:
        rows = connection.execute(
            "SELECT id, provider, provider_uid, display_name, scope, expires_at, connected_at FROM oauth_connections WHERE owner_id=? ORDER BY connected_at DESC",
            (owner_id,),
        ).fetchall()
    finally:
        connection.close()
    now = time.time()
    return [{**dict(row), "status": "authorized" if row["expires_at"] > now else "reconnect_required"} for row in rows]


def _exchange_profile(provider, config, code):
    """Short bounded requests; provider response bodies/errors never go to logs/UI."""
    token_url = "https://discord.com/api/v10/oauth2/token" if provider == "discord" else f"https://graph.facebook.com/{config['version']}/oauth/access_token"
    token_form = {"client_id": config["client_id"], "client_secret": config["client_secret"],
                  "grant_type": "authorization_code", "code": code, "redirect_uri": config["redirect_uri"]}
    try:
        with requests.Session() as http:
            with http.post(token_url, data=token_form, timeout=(5, 15), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise OAuthError("Nhà cung cấp từ chối mã đăng nhập. Hãy kết nối lại.")
                token = response.json()
            access = token.get("access_token")
            if not isinstance(access, str) or not access or not token.get("expires_in"):
                raise OAuthError("Nhà cung cấp không trả về phiên OAuth hợp lệ")
            params = {}
            if provider == "discord":
                profile_url = "https://discord.com/api/v10/users/@me"
            else:
                profile_url = f"https://graph.facebook.com/{config['version']}/me"
                params = {"fields": "id,name", "appsecret_proof": hmac.new(config["client_secret"].encode(), access.encode(), hashlib.sha256).hexdigest()}
            with http.get(profile_url, headers={"Authorization": "Bearer " + access}, params=params, timeout=(5, 15), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise OAuthError("Không xác minh được hồ sơ từ nhà cung cấp")
                profile = response.json()
        uid = str(profile.get("id") or "")
        if not uid.isdigit():
            raise OAuthError("Hồ sơ OAuth không có ID hợp lệ")
        display_name = str(profile.get("global_name") or profile.get("name") or profile.get("username") or uid)[:150]
        expires = max(1, int(token["expires_in"]))
        return {"uid": uid, "name": display_name, "access": access,
                "refresh": str(token.get("refresh_token") or ""), "expires": expires,
                "scope": "identify" if provider == "discord" else "public_profile"}
    except (requests.RequestException, TypeError, KeyError, ValueError) as error:
        if isinstance(error, OAuthError):
            raise
        raise OAuthError("Kết nối nhà cung cấp thất bại. Hãy thử lại, không cần gửi mật khẩu vào bot.") from None


def register_oauth_routes(app, db, owner_id):
    def result_page(message, status=200):
        body = render_template_string("""<!doctype html><html lang="vi"><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1"><title>Kết nối GLAZE</title>
        <body style="background:#101a24;color:#edf6ff;font:16px/1.7 system-ui;padding:12vh 8vw;max-width:600px;margin:auto">
        <h1>Kết nối GLAZE</h1><p>{{ message }}</p><p>Bạn có thể đóng trang này và trở lại Mini App → Tài khoản → Đồng bộ.</p></body></html>""", message=message)
        return Response(body, status=status, mimetype="text/html", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @app.get("/api/miniapp/oauth/providers")
    def oauth_providers():
        providers = []
        for provider, label in PROVIDERS.items():
            config = _config(provider)
            providers.append({"id": provider, "label": label, "configured": not config["missing"],
                              "missing": config["missing"], "redirect_uri": config["redirect_uri"] if config["base"] else None,
                              "scope": "identify" if provider == "discord" else "public_profile"})
        return jsonify({"ok": True, "providers": providers})

    @app.get("/api/miniapp/oauth/connections")
    def oauth_connections():
        return jsonify({"ok": True, "connections": _public_connections(db, str(owner_id()))})

    @app.post("/api/miniapp/oauth/start")
    def oauth_start():
        provider = str((request.get_json(silent=True) or {}).get("provider") or "")
        try:
            config = _config(provider)
        except OAuthError as error:
            return jsonify({"ok": False, "error": str(error)}), 400
        if config["missing"]:
            return jsonify({"ok": False, "error": "Chưa cấu hình: " + ", ".join(config["missing"])}), 503
        # Opening this same-origin one-time link in the external browser binds
        # OAuth to that browser's HttpOnly session, not the Telegram webview.
        launch = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        conn = db()
        try:
            conn.execute("DELETE FROM oauth_attempts WHERE created_at < ?", (time.time() - ATTEMPT_TTL,))
            conn.execute("INSERT INTO oauth_attempts(state_hash, provider, launch_hash, owner_id, created_at) VALUES (?, ?, ?, ?, ?)",
                         (_digest(state), provider, _digest(launch), str(owner_id()), time.time()))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        # The signed launch payload is short-lived and contains no credentials.
        from itsdangerous import URLSafeTimedSerializer
        payload = URLSafeTimedSerializer(app.secret_key, salt="oauth-launch").dumps({"launch": launch, "state": state})
        return jsonify({"ok": True, "url": config["base"] + "/oauth/begin/" + payload, "expires_in": ATTEMPT_TTL})

    @app.get("/oauth/begin/<payload>")
    def oauth_begin(payload):
        from itsdangerous import BadSignature, URLSafeTimedSerializer
        try:
            values = URLSafeTimedSerializer(app.secret_key, salt="oauth-launch").loads(payload, max_age=ATTEMPT_TTL)
        except BadSignature:
            return result_page("Liên kết hết hạn hoặc không hợp lệ. Hãy bắt đầu lại từ Mini App.", 400)
        conn = db()
        try:
            row = conn.execute("SELECT * FROM oauth_attempts WHERE state_hash=? AND launch_hash=? AND used=0 AND created_at>=?", (_digest(values["state"]), _digest(values["launch"]), time.time() - ATTEMPT_TTL)).fetchone()
            if not row:
                return result_page("Liên kết đã dùng hoặc đã hết hạn.", 400)
            config = _config(row["provider"])
            if config["missing"]:
                return result_page("Máy chủ chưa cấu hình đăng nhập OAuth.", 503)
            binding = secrets.token_urlsafe(32)
            changed = conn.execute("UPDATE oauth_attempts SET browser_hash=?, launch_hash=NULL WHERE state_hash=? AND launch_hash=? AND used=0", (_digest(binding), row["state_hash"], _digest(values["launch"]))).rowcount
            conn.commit()
            if changed != 1:
                return result_page("Liên kết đã dùng. Hãy bắt đầu lại.", 400)
            bindings = dict(session.get("oauth_bindings") or {})
            bindings[row["state_hash"]] = binding
            session["oauth_bindings"] = dict(list(bindings.items())[-5:])
            provider = row["provider"]
            endpoint = "https://discord.com/oauth2/authorize" if provider == "discord" else f"https://www.facebook.com/{config['version']}/dialog/oauth"
            params = {"client_id": config["client_id"], "redirect_uri": config["redirect_uri"], "response_type": "code",
                      "scope": "identify" if provider == "discord" else "public_profile", "state": values["state"]}
            return Response(status=302, headers={"Location": endpoint + "?" + urlencode(params), "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        finally:
            conn.close()

    @app.get("/oauth/callback/<provider>")
    def oauth_callback(provider):
        state = request.args.get("state", "")
        state_hash = _digest(state)
        bindings = dict(session.get("oauth_bindings") or {})
        binding = bindings.pop(state_hash, "")
        session["oauth_bindings"] = bindings
        if not state or not binding or provider not in PROVIDERS:
            return result_page("Không xác minh được phiên đăng nhập. Hãy bắt đầu từ Mini App.", 400)
        conn = db()
        try:
            row = conn.execute("SELECT * FROM oauth_attempts WHERE state_hash=? AND provider=? AND used=0 AND created_at>=?", (state_hash, provider, time.time() - ATTEMPT_TTL)).fetchone()
            if not row or not hmac.compare_digest(row["browser_hash"] or "", _digest(binding)):
                return result_page("Phiên OAuth không hợp lệ hoặc đã hết hạn.", 400)
            changed = conn.execute("UPDATE oauth_attempts SET used=1 WHERE state_hash=? AND used=0", (state_hash,)).rowcount
            conn.commit()
            if changed != 1:
                return result_page("Mã đăng nhập đã được sử dụng.", 400)
            if request.args.get("error") or not request.args.get("code"):
                return result_page("Bạn chưa cấp quyền. Không có tài khoản nào được thêm.", 400)
            config = _config(provider)
            if config["missing"]:
                return result_page("Cấu hình OAuth đã thay đổi. Hãy kiểm tra cấu hình máy chủ.", 503)
            try:
                profile = _exchange_profile(provider, config, request.args["code"])
            except OAuthError as error:
                return result_page(str(error), 502)
            cipher = config["cipher"]
            conn.execute("""INSERT INTO oauth_connections(provider, provider_uid, owner_id, display_name, access_encrypted, refresh_encrypted, scope, expires_at, connected_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, provider_uid, owner_id) DO UPDATE SET
                display_name=excluded.display_name, access_encrypted=excluded.access_encrypted,
                refresh_encrypted=excluded.refresh_encrypted, scope=excluded.scope,
                expires_at=excluded.expires_at, connected_at=excluded.connected_at""",
                (provider, profile["uid"], row["owner_id"], profile["name"], cipher.encrypt(profile["access"].encode()).decode(),
                 cipher.encrypt(profile["refresh"].encode()).decode() if profile["refresh"] else "", profile["scope"], time.time() + profile["expires"], time.time()))
            conn.commit()
            return result_page(f"Đã xác minh và lưu kết nối {PROVIDERS[provider]}: {profile['name']}. Quyền hồ sơ không phải quyền tự động gửi tin nhắn.")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.post("/api/miniapp/oauth/disconnect")
    def oauth_disconnect():
        data = request.get_json(silent=True) or {}
        try:
            connection_id = int(data.get("id"))
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "ID kết nối không hợp lệ"}), 400
        conn = db()
        try:
            conn.execute("DELETE FROM oauth_connections WHERE id=? AND owner_id=?", (connection_id, str(owner_id())))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True, "message": "Đã xóa kết nối và khóa OAuth lưu tại bot. Có thể thu hồi quyền tại cài đặt Discord/Facebook."})
