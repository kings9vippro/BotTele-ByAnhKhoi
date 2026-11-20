"""Official, admin-initiated OAuth connections. Author: Dev Anh Khôi. Version: 1.3.0.

OAuth identities are deliberately separate from legacy chat automation accounts.
No passwords, browser cookies, self-bot tokens or device impersonation are used.
"""
import hashlib
import base64
import json
import hmac
import os
import re
import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import Response, jsonify, render_template_string, request, session

PROVIDERS = {"discord": "Discord", "facebook": "Facebook"}
PROVIDER_SPECS = {
    "discord": {
        "client_id": "DISCORD_CLIENT_ID", "client_secret": "DISCORD_CLIENT_SECRET",
        "authorize": "https://discord.com/oauth2/authorize", "scope": "identify",
    },
    "facebook": {
        "client_id": "FACEBOOK_APP_ID", "client_secret": "FACEBOOK_APP_SECRET",
        "authorize": "https://www.facebook.com/v21.0/dialog/oauth", "scope": "public_profile",
    },
}
ATTEMPT_TTL = 300
TELEGRAM_INIT_DATA_MAX_AGE = 24 * 60 * 60
TELEGRAM_INIT_DATA_CLOCK_SKEW = 30


class OAuthError(ValueError):
    pass


class TelegramInitDataError(ValueError):
    """A safe, machine-readable Mini App launch validation failure.

    The public ``code`` is intentionally descriptive enough for a recovery UI
    but never includes raw initData, a bot token, or a computed signature.
    """

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def validate_telegram_webapp_init_data(
    init_data,
    bot_token,
    *,
    now=None,
    max_age=TELEGRAM_INIT_DATA_MAX_AGE,
    clock_skew=TELEGRAM_INIT_DATA_CLOCK_SKEW,
):
    """Validate the official Telegram Web App initData HMAC contract.

    It is deliberately framework-independent so Flask routes, command-line
    smoke tests and future transports share the exact same security boundary.
    ``auth_date`` must be recent; a small future allowance avoids rejecting
    legitimate launches when a device clock is marginally ahead.
    """
    token = str(bot_token or "").strip()
    if not token:
        raise TelegramInitDataError("server_misconfigured")
    raw = str(init_data or "").strip()
    if not raw:
        raise TelegramInitDataError("missing_init_data")
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    except ValueError as error:
        raise TelegramInitDataError("malformed_init_data") from error
    values = {}
    for key, value in pairs:
        if key in values:
            raise TelegramInitDataError("malformed_init_data")
        values[key] = value
    received_hash = values.pop("hash", "")
    if not received_hash or len(received_hash) != 64:
        raise TelegramInitDataError("invalid_signature")
    try:
        auth_date = int(values.get("auth_date") or "")
    except (TypeError, ValueError) as error:
        raise TelegramInitDataError("malformed_init_data") from error
    current = float(time.time() if now is None else now)
    if auth_date <= 0:
        raise TelegramInitDataError("malformed_init_data")
    if auth_date > current + max(0, int(clock_skew)):
        raise TelegramInitDataError("clock_skew")
    if current - auth_date > max(0, int(max_age)):
        raise TelegramInitDataError("expired_init_data")
    data_check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        raise TelegramInitDataError("invalid_signature")
    try:
        user = json.loads(values.get("user") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise TelegramInitDataError("malformed_init_data") from error
    if not isinstance(user, dict) or not str(user.get("id") or "").isdigit():
        raise TelegramInitDataError("malformed_init_data")
    return {"user": user, "auth_date": auth_date, "values": values}


def init_oauth_tables(connection):
    connection.execute("CREATE TABLE IF NOT EXISTS oauth_configuration (provider TEXT PRIMARY KEY, encrypted TEXT NOT NULL)")
    connection.execute("""CREATE TABLE IF NOT EXISTS oauth_attempts (
        state_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, launch_hash TEXT UNIQUE,
        owner_id TEXT NOT NULL, created_at REAL NOT NULL, browser_hash TEXT,
        used INTEGER NOT NULL DEFAULT 0, verifier_encrypted TEXT NOT NULL DEFAULT ''
    )""")
    if 'verifier_encrypted' not in {row[1] for row in connection.execute('PRAGMA table_info(oauth_attempts)')}:
        connection.execute("ALTER TABLE oauth_attempts ADD COLUMN verifier_encrypted TEXT NOT NULL DEFAULT ''")
    connection.execute("""CREATE TABLE IF NOT EXISTS oauth_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
        provider_uid TEXT NOT NULL, owner_id TEXT NOT NULL, display_name TEXT NOT NULL,
        access_encrypted TEXT NOT NULL, refresh_encrypted TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL, expires_at REAL NOT NULL, connected_at REAL NOT NULL,
        UNIQUE(provider, provider_uid, owner_id)
    )""")


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _config(provider, overrides=None):
    if provider not in PROVIDERS:
        raise OAuthError("Nền tảng không được hỗ trợ")
    def setting(key):
        return str((overrides or {}).get(key, os.environ.get(key, ""))).strip()
    base = setting("OAUTH_PUBLIC_BASE_URL").rstrip("/")
    parsed = urlsplit(base)
    missing = []
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        missing.append("OAUTH_PUBLIC_BASE_URL (HTTPS, không có đường dẫn)")
    spec = PROVIDER_SPECS[provider]
    id_key = spec["client_id"]
    secret_key = spec["client_secret"]
    client_id, client_secret = setting(id_key), setting(secret_key)
    for key, value in ((id_key, client_id), (secret_key, client_secret)):
        if not value:
            missing.append(key)
    encryption_key = setting("OAUTH_ENCRYPTION_KEY")
    try:
        cipher = Fernet(encryption_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        cipher = None
        missing.append("OAUTH_ENCRYPTION_KEY (Fernet)")
    return {"missing": missing, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": base + "/oauth/callback/" + provider, "cipher": cipher,
            "base": base, "scope": spec["scope"], "authorize": spec["authorize"]}


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
    if provider == "discord":
        token_url = "https://discord.com/api/v10/oauth2/token"
        profile_url = "https://discord.com/api/v10/users/@me"
        token_form = {"client_id": config["client_id"], "client_secret": config["client_secret"],
                      "grant_type": "authorization_code", "code": code, "redirect_uri": config["redirect_uri"]}
        token_params, profile_params = None, {}
    elif provider == "facebook":
        token_url = "https://graph.facebook.com/v21.0/oauth/access_token"
        profile_url = "https://graph.facebook.com/v21.0/me"
        token_form = None
        token_params = {"client_id": config["client_id"], "client_secret": config["client_secret"],
                        "code": code, "redirect_uri": config["redirect_uri"]}
        profile_params = {"fields": "id,name"}
    else:
        raise OAuthError('Nền tảng không được hỗ trợ')
    if config.get('code_verifier'):
        token_form['code_verifier'] = config['code_verifier']
    try:
        with requests.Session() as http:
            with http.post(token_url, data=token_form, params=token_params, timeout=(5, 15), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise OAuthError("Nhà cung cấp từ chối mã đăng nhập. Hãy kết nối lại.")
                token = response.json()
            access = token.get("access_token")
            if not isinstance(access, str) or not access:
                raise OAuthError("Nhà cung cấp không trả về phiên OAuth hợp lệ")
            with http.get(profile_url, headers={"Authorization": "Bearer " + access}, params=profile_params, timeout=(5, 15), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise OAuthError("Không xác minh được hồ sơ từ nhà cung cấp")
                profile = response.json()
        uid = str(profile.get("id") or "")
        if not uid.isdigit():
            raise OAuthError("Hồ sơ OAuth không có ID hợp lệ")
        display_name = str(profile.get("global_name") or profile.get("name") or profile.get("username") or uid)[:150]
        # Facebook may omit expires_in for a long-lived user token. Keep a
        # conservative local re-authorization horizon instead of claiming it
        # can never expire or survive revocation.
        expires = max(1, int(token.get("expires_in") or 3600))
        return {"uid": uid, "name": display_name, "access": access,
                "refresh": str(token.get("refresh_token") or ""), "expires": expires,
                "scope": config["scope"]}
    except (requests.RequestException, TypeError, KeyError, ValueError) as error:
        if isinstance(error, OAuthError):
            raise
        raise OAuthError("Kết nối nhà cung cấp thất bại. Hãy thử lại, không cần gửi mật khẩu vào bot.") from None


def register_oauth_routes(app, db, owner_id):
    def configuration_cipher(purpose="configuration"):
        key = hashlib.sha256(("glaze-oauth-" + purpose + str(app.secret_key)).encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key))

    def configuration(provider):
        conn = db()
        try:
            row = conn.execute("SELECT encrypted FROM oauth_configuration WHERE provider=?", (provider,)).fetchone()
        finally:
            conn.close()
        values = None
        if row:
            from cryptography.fernet import InvalidToken
            try:
                values = json.loads(configuration_cipher().decrypt(row[0].encode()).decode())
            except (InvalidToken, ValueError):
                raise OAuthError("SECRET_KEY đã thay đổi. Cần lưu lại cấu hình OAuth.") from None
            values["OAUTH_ENCRYPTION_KEY"] = os.environ.get("OAUTH_ENCRYPTION_KEY") or base64.urlsafe_b64encode(hashlib.sha256(("glaze-oauth-tokens" + str(app.secret_key)).encode()).digest()).decode()
        return _config(provider, values)

    @app.post("/api/miniapp/oauth/configure")
    def oauth_configure():
        data = request.get_json(silent=True) or {}
        provider = str(data.get("provider") or "")
        if provider not in PROVIDERS:
            return jsonify({"ok": False, "error": "Nền tảng không hợp lệ"}), 400
        if not os.environ.get("SECRET_KEY"):
            return jsonify({"ok": False, "error": "Máy chủ cần SECRET_KEY cố định trước khi lưu cấu hình"}), 503
        client_id, secret = str(data.get("client_id") or "").strip(), str(data.get("client_secret") or "").strip()
        if not client_id.isdigit() or not secret:
            return jsonify({"ok": False, "error": "Cần App/Client ID dạng số và secret ứng dụng"}), 400
        spec = PROVIDER_SPECS[provider]
        values = {"OAUTH_PUBLIC_BASE_URL": str(data.get("public_base_url") or "").strip().rstrip("/"),
                  spec["client_id"]: client_id,
                  spec["client_secret"]: secret,
                  "OAUTH_ENCRYPTION_KEY": base64.urlsafe_b64encode(hashlib.sha256(b"validation-only").digest()).decode()}
        try:
            validated = _config(provider, values)
        except ValueError:
            return jsonify({"ok": False, "error": "URL HTTPS không hợp lệ"}), 400
        if validated["missing"]:
            return jsonify({"ok": False, "error": "Cấu hình chưa hợp lệ: " + ", ".join(validated["missing"])}), 400
        values.pop("OAUTH_ENCRYPTION_KEY")
        encrypted = configuration_cipher().encrypt(json.dumps(values).encode()).decode()
        conn = db()
        try:
            conn.execute("INSERT OR REPLACE INTO oauth_configuration(provider, encrypted) VALUES(?, ?)", (provider, encrypted))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        app.config["SESSION_COOKIE_SECURE"] = True
        return jsonify({"ok": True, "message": "Đã lưu cấu hình được mã hóa. Đăng ký callback này trong ứng dụng của bạn.", "redirect_uri": validated["redirect_uri"]})

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
            config = configuration(provider)
            providers.append({"id": provider, "label": label, "configured": not config["missing"],
                              "missing": config["missing"], "redirect_uri": config["redirect_uri"] if config["base"] else None,
                              "scope": config["scope"]})
        return jsonify({"ok": True, "providers": providers})

    @app.get("/api/miniapp/oauth/connections")
    def oauth_connections():
        return jsonify({"ok": True, "connections": _public_connections(db, str(owner_id()))})

    @app.post("/api/miniapp/oauth/start")
    def oauth_start():
        provider = str((request.get_json(silent=True) or {}).get("provider") or "")
        try:
            return jsonify(start_for_owner(str(owner_id()), provider))
        except OAuthError as error:
            return jsonify(ok=False, error=str(error)), 503

    def start_for_owner(user, provider='discord'):
        try:
            config = configuration(provider)
        except OAuthError as error:
            raise
        if config["missing"]:
            raise OAuthError("Chưa cấu hình: " + ", ".join(config["missing"]))
        # Opening this same-origin one-time link in the external browser binds
        # OAuth to that browser's HttpOnly session, not the Telegram webview.
        launch = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48) if provider == 'discord' and os.environ.get('DISCORD_OAUTH_PKCE') == '1' else ''
        encrypted_verifier = config['cipher'].encrypt(verifier.encode()).decode() if verifier else ''
        conn = db()
        try:
            conn.execute("DELETE FROM oauth_attempts WHERE created_at < ?", (time.time() - ATTEMPT_TTL,))
            conn.execute("INSERT INTO oauth_attempts(state_hash, provider, launch_hash, owner_id, created_at, verifier_encrypted) VALUES (?, ?, ?, ?, ?, ?)",
                         (_digest(state), provider, _digest(launch), str(user), time.time(), encrypted_verifier))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        # The signed launch payload is short-lived and contains no credentials.
        from itsdangerous import URLSafeTimedSerializer
        payload = URLSafeTimedSerializer(app.secret_key, salt="oauth-launch").dumps({"launch": launch, "state": state})
        return {"ok": True, "url": config["base"] + "/oauth/begin/" + payload, "expires_in": ATTEMPT_TTL}

    app.extensions['oauth_start'] = start_for_owner
    app.extensions['discord_oauth_start'] = start_for_owner

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
            config = configuration(row["provider"])
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
            endpoint = config["authorize"]
            params = {"client_id": config["client_id"], "redirect_uri": config["redirect_uri"], "response_type": "code",
                      "scope": config["scope"], "state": values["state"]}
            if provider == "discord":
                params["prompt"] = "consent"
            if row['verifier_encrypted']:
                try:
                    verifier = config['cipher'].decrypt(row['verifier_encrypted'].encode())
                except InvalidToken:
                    return result_page('Khóa mã hóa OAuth đã thay đổi. Hãy đăng nhập lại.', 503)
                params['code_challenge'] = base64.urlsafe_b64encode(hashlib.sha256(verifier).digest()).rstrip(b'=').decode()
                params['code_challenge_method'] = 'S256'
            return Response(status=302, headers={"Location": endpoint + "?" + urlencode(params), "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        finally:
            conn.close()

    @app.get("/oauth/callback/<provider>")
    def oauth_callback(provider):
        issuer = request.args.get('iss')
        expected_issuers = {"discord": {"https://discord.com"}, "facebook": {"https://www.facebook.com", "https://facebook.com"}}
        if issuer and issuer not in expected_issuers.get(provider, set()):
            return result_page('Nhà phát hành OAuth không hợp lệ.', 400)
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
            config = configuration(provider)
            if config["missing"]:
                return result_page("Cấu hình OAuth đã thay đổi. Hãy kiểm tra cấu hình máy chủ.", 503)
            if row['verifier_encrypted']:
                try:
                    config['code_verifier'] = config['cipher'].decrypt(row['verifier_encrypted'].encode()).decode()
                except InvalidToken:
                    return result_page('Khóa mã hóa OAuth đã thay đổi. Hãy đăng nhập lại.', 503)
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
            notify = app.extensions.get('oauth_notice')
            if notify:
                try:
                    notify(row['owner_id'], profile['name'])
                except Exception:
                    app.logger.warning('OAuth saved; Telegram notification unavailable')
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
        try:
            return jsonify(ok=True, message=disconnect_for_owner(str(owner_id()), connection_id))
        except OAuthError as error:
            return jsonify(ok=False, error=str(error)), 502

    def disconnect_for_owner(user, connection_id):
        conn = db()
        try:
            row = conn.execute("SELECT * FROM oauth_connections WHERE id=? AND owner_id=?", (connection_id, user)).fetchone()
            if row:
                provider = row['provider']
                config = configuration(provider)
                if config['missing']:
                    raise OAuthError('Thiếu cấu hình để thu hồi; dữ liệu liên kết chưa bị xóa')
                try:
                    token = config['cipher'].decrypt(row['access_encrypted'].encode()).decode()
                    if provider == 'discord':
                        response = requests.post('https://discord.com/api/v10/oauth2/token/revoke', data={'client_id':config['client_id'],'client_secret':config['client_secret'],'token':token},timeout=(4,10),allow_redirects=False)
                    else:
                        response = requests.delete('https://graph.facebook.com/v21.0/me/permissions', params={'access_token': token}, timeout=(4,10), allow_redirects=False)
                    with response:
                        if response.status_code not in (200,204):
                            raise OAuthError(f'{PROVIDERS[provider]} chưa xác nhận thu hồi; liên kết vẫn được giữ để thử lại')
                except requests.RequestException:
                    raise OAuthError(f'Không kết nối được {PROVIDERS[provider]} để thu hồi quyền') from None
                except InvalidToken:
                    raise OAuthError('Khóa mã hóa đã thay đổi; khôi phục khóa cũ hoặc thu hồi trong Discord trước') from None
            conn.execute("DELETE FROM oauth_connections WHERE id=? AND owner_id=?", (connection_id, user))
            conn.commit()
        finally:
            conn.close()
        return 'Đã thu hồi quyền và ngắt liên kết OAuth'

    app.extensions['discord_oauth_disconnect'] = disconnect_for_owner
