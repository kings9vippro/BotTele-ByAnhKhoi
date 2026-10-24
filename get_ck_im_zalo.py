import os
import re
import io
import time
import uuid
import json
import hmac
import zlib
import base64
import struct
import sqlite3
import hashlib
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from urllib.parse import urlencode
import requests
from requests.adapters import HTTPAdapter

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from zalo_login import (
    login_qr_with_unique_imei,
    LoginQRCallbackEventType,
    ZaloPCSessionKeeper,
    check_zalo_cookie_imei_live,
    parse_cookies_input_flexible,
    extract_imei_and_metadata_flexible,
    _is_valid_cookie_val,
)

# CẤU HÌNH BOT TELEGRAM TRUNG TÂM (BOT TREO 4APP 🇻🇳)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8917587021:AAGnf2uUmNLI1r747luw8BVGi_hr3jBzWpw")
ROOT_ADMIN_ID = str(os.environ.get("TELEGRAM_ADMIN_ID", "8827605973")).strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
WELCOME_VIDEO_PATH = os.path.join(BASE_DIR, "welcome.mp4")
MENU_BANNER_PATH = os.path.join(BASE_DIR, "menu_banner.png")

API_2FA = "https://keyherlyswar.x10.mx/Apidocs/tien_ich/2fa.php?secret={}"

DISCORD_TOKEN_RE = re.compile(
    r"((?:mfa\.[A-Za-z0-9_\-]{50,160})|(?:[A-Za-z0-9_\-]{18,44}\.[A-Za-z0-9_\-]{5,14}\.[A-Za-z0-9_\-]{20,140}))"
)

# DANH SÁCH 32 CHỨC NĂNG VIP CHIA 4 TRANG (8 MỤC / TRANG, 2 CỘT / HÀNG GIỐNG Y HỆT ẢNH MẪU)
FUNCTION_ITEMS_32 = [
    # Trang 1/4
    {"id": "fn_treo_do",       "label": "🥀 Treo Ngôn Đỏ",       "mode": "treo_ngon",   "color_mode": "fixed",        "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Treo ngôn chữ Đỏ Rực (db342e) toàn tập"},
    {"id": "fn_treo_damau",    "label": "🌈 Treo Đa Màu",        "mode": "treo_ngon",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Treo ngôn đổi màu rực rỡ từng chữ"},
    {"id": "fn_treo_gif",      "label": "🎬 Treo Ngôn GIF",      "mode": "treo_ngon",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Treo ngôn kèm hiệu ứng chuyển động VIP"},
    {"id": "fn_word_rainbow",  "label": "✨ Chữ Đổi Từng Màu",   "mode": "treo_nhay",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Mỗi từ/chữ đổi 1 màu (Đỏ-Cam-Vàng-Xanh), 0% chữ trắng"},
    {"id": "fn_treo_nhay",     "label": "💬 Treo Nhây",          "mode": "treo_nhay",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Nhây từng dòng liên hoàn đổi màu từng chữ"},
    {"id": "fn_nhay_tag",      "label": "🏷️ Nhây Tag Tên",      "mode": "treo_nhay",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Nhây kèm Tag nhắc tên mục tiêu thật 100%", "hide_tag_name": False},
    {"id": "fn_anall",         "label": "📢 Nhây Tag All Ẩn",    "mode": "anall",       "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Báo chuông @All cả nhóm nhưng ẩn hoàn toàn chữ @All", "tag_all": True, "hide_tag_all": True},
    {"id": "fn_antan",         "label": "👻 Nhây Tag Tên Ẩn",    "mode": "antan",       "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Tag tên thật báo chuông nhưng ẩn chữ @Tên trên khung chat", "hide_tag_name": True},

    # Trang 2/4
    {"id": "fn_sieu_xa",       "label": "🚀 Siêu Xả Đa Box",     "mode": "fast",        "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Siêu xả đồng loạt đa nhóm tốc độ cao chống cấm chat"},
    {"id": "fn_combo3",        "label": "⚡ Combo 3 Câu/Nhịp",   "mode": "combo3",      "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Xả liên thanh 3 câu mỗi nhịp đổi màu từng từ"},
    {"id": "fn_nhay_2c",       "label": "🔥 Nhây Gộp 2 Câu",     "mode": "nhay2c",      "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "2c.txt",          "desc": "Nhây gộp 2 câu liên hoàn (2c.txt) đổi màu từng chữ"},
    {"id": "fn_treo_so",       "label": "🔢 Treo Số Liên Hoàn",  "mode": "treo_so",     "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "so.txt",          "desc": "Treo đếm số liên hoàn (so.txt) đổi màu từng chữ"},
    {"id": "fn_so_tag",        "label": "🎯 Số Kèm Tag",         "mode": "so_tag",      "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "so.txt",          "desc": "Treo số kèm Tag thẳng tên mục tiêu"},
    {"id": "fn_faketen",       "label": "👑 Số Fake Tên",        "mode": "faketen",     "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "so.txt",          "desc": "Treo số giả danh tên đối phương"},
    {"id": "fn_nhay_icon",     "label": "🌪️ Bão Icon VIP",      "mode": "nhayicon",    "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhayicon.txt",    "desc": "Xả bão ký hiệu & icon VIP (nhayicon.txt)"},
    {"id": "fn_chui",          "label": "💥 Nhây Sát Thương",    "mode": "chui",        "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "chui.txt",        "desc": "Nhây sát thương cực mạnh (chui.txt) đổi màu từng từ"},

    # Trang 3/4
    {"id": "fn_nhay_poll",     "label": "📊 Tạo Poll Tự Động",   "mode": "nhay_poll",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Tạo bình chọn (Poll) tự động liên hoàn trong Box"},
    {"id": "fn_typing",        "label": "⌨️ Hiệu Ứng Typing",    "mode": "typing_loop", "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Giả lập đang soạn tin nhắn liên tục chống khóa chat"},
    {"id": "fn_tenbox",        "label": "✏️ Đổi Tên Box",        "mode": "nhay_tenbox", "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhaynamebox.txt", "desc": "Đổi tên nhóm liên hoàn theo kịch bản (nhaynamebox.txt)"},
    {"id": "fn_todo",          "label": "📋 Giao Việc To-Do",    "mode": "zalo_todo",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Giao việc Zalo To-Do nhắc nhở thẳng mục tiêu"},
    {"id": "fn_bankcard",      "label": "🏦 Thẻ Ngân Hàng",      "mode": "zalo_bank",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Gửi thẻ ngân hàng VietQR tự động vào nhóm"},
    {"id": "fn_sharecontact",  "label": "🪪 Gửi Danh Thiếp",     "mode": "share_contact","color_mode": "word_rainbow","fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Chia sẻ danh thiếp (Contact Card) vào nhóm"},
    {"id": "fn_theme",         "label": "🎨 Đổi Nền MQTT",       "mode": "nen_mqtt",    "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Đổi chủ đề nền nhóm tự động"},
    {"id": "fn_sharelink",     "label": "🔗 Chia Sẻ Link",       "mode": "share_link",  "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Treo chia sẻ liên kết kèm tiêu đề nổi bật"},

    # Trang 4/4
    {"id": "fn_setname",       "label": "🏷️ Đổi Biệt Danh",      "mode": "set_nickname","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhaynamebox.txt", "desc": "Đổi biệt danh thành viên trong nhóm liên hoàn"},
    {"id": "fn_chan",          "label": "🛡️ Chặn & Bám Sát",    "mode": "special_chan","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Tự động vả lại đối thủ 0ms ngay khi họ vừa nhắn (.chan)"},
    {"id": "fn_proxy",         "label": "🌐 Xoay Vòng Proxy",    "mode": "special_prx", "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "",                "desc": "Quản lý & kiểm tra dàn Proxy chống nghẽn đường truyền"},
    {"id": "fn_antiban_box",   "label": "🛡️ Anti Cấm Chat Box",  "mode": "special_anti","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "",                "desc": "Cấu hình Lá Chắn Chống Zalo Cấm Chat Box (Typing + Pacing)"},
    {"id": "fn_delay",         "label": "⏱️ Chỉnh Tốc Độ Delay", "mode": "special_delay","color_mode": "word_rainbow","fixed_color": "red",    "file_hint": "",                "desc": "Chỉnh tốc độ gửi tin (0s, 0.3s, 0.5s, 1s, 2s, 5s)"},
    {"id": "fn_colormode",     "label": "🎨 Chế Độ Màu Chữ",     "mode": "special_color","color_mode": "word_rainbow","fixed_color": "red",    "file_hint": "",                "desc": "Chọn chế độ Đổi Màu Từng Chữ hoặc Màu Cố Định"},
    {"id": "fn_fontstyle",     "label": "🔤 Cỡ & Kiểu Chữ",      "mode": "special_font","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "",                "desc": "Chọn cỡ chữ To Đậm (f_18), Vừa Đậm (f_15), Xen Kẽ"},
    {"id": "fn_stop_all",      "label": "🛑 Dừng Tất Cả (.ta)",  "mode": "special_stop","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "",                "desc": "Dừng khẩn cấp toàn bộ các chiến dịch đang chạy"},
]

FUNCTION_MAP_BY_ID = {item["id"]: item for item in FUNCTION_ITEMS_32}


def add_border_to_qr(image_data: bytes) -> bytes:
    """Thêm viền trắng chuẩn xung quanh mã QR để camera điện thoại nhận diện ngay trong 0.1s!"""
    if not HAS_PIL or not image_data:
        return image_data
    try:
        img = Image.open(BytesIO(image_data))
        if img.mode == "RGBA":
            bg_w = Image.new("RGB", img.size, (255, 255, 255))
            bg_w.paste(img, mask=img.split()[3])
            img = bg_w
        elif img.mode != "RGB":
            img = img.convert("RGB")
        pad = 24
        out_im = Image.new("RGB", (img.width + pad * 2, img.height + pad * 2), (255, 255, 255))
        out_im.paste(img, (pad, pad))
        buf = BytesIO()
        out_im.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return image_data


def generate_totp_local(secret_key, time_step=30, digits=6):
    if not secret_key:
        return None, 0
    clean_sec = re.sub(r"[^A-Za-z2-7]", "", str(secret_key)).upper()
    now_int = int(time.time())
    rem_sec = time_step - (now_int % time_step)
    if clean_sec:
        pad_len = (8 - (len(clean_sec) % 8)) % 8
        try:
            key_bytes = base64.b32decode(clean_sec + ("=" * pad_len), casefold=True)
            counter = now_int // time_step
            msg = struct.pack(">Q", counter)
            digest = hmac.new(key_bytes, msg, hashlib.sha1).digest()
            offset = digest[-1] & 0x0F
            code_int = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
            return str(code_int).zfill(digits), rem_sec
        except Exception:
            pass
    try:
        r = requests.get(API_2FA.format(str(secret_key).replace(" ", "")), timeout=6).json()
        if r.get("token"):
            return str(r["token"]), rem_sec
    except Exception:
        pass
    return None, 0


# HỆ THỐNG PHÂN QUYỀN CHẶT CHẼ (ROOT ADMIN 8827605973 + THÊM / XOÁ ID NGƯỜI DÙNG ĐẦY ĐỦ)
_TG_AUTH_LOCK = threading.RLock()
_TG_AUTH_JSON_PATH = os.path.join(BASE_DIR, "uploads", "tg_authorized_users.json")
_TG_AUTH_RAM_CACHE = {
    ROOT_ADMIN_ID: {"uid": ROOT_ADMIN_ID, "name": "Admin Chính", "role": "Admin", "added_at": int(time.time())}
}
_TG_AUTH_LOADED = False


def _open_db():
    conn = _open_db()
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
    except Exception:
        pass
    return conn


def _load_auth_ram_cache():
    global _TG_AUTH_LOADED
    if _TG_AUTH_LOADED:
        return
    with _TG_AUTH_LOCK:
        if _TG_AUTH_LOADED:
            return
        _TG_AUTH_LOADED = True
        if os.path.exists(_TG_AUTH_JSON_PATH):
            try:
                with open(_TG_AUTH_JSON_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if k and isinstance(v, dict):
                            _TG_AUTH_RAM_CACHE[str(k)] = v
            except Exception:
                pass
        try:
            conn = _open_db()
            _ensure_auth_tables(conn)
            for r in conn.execute("SELECT uid, name, role, added_at FROM tg_authorized_users").fetchall():
                u = str(r[0]).strip()
                if u:
                    _TG_AUTH_RAM_CACHE[u] = {"uid": u, "name": r[1] or f"VIP_{u[-4:]}", "role": r[2] or "VIP", "added_at": r[3] or int(time.time())}
            conn.close()
        except Exception:
            pass
        _TG_AUTH_RAM_CACHE[ROOT_ADMIN_ID] = {"uid": ROOT_ADMIN_ID, "name": "Admin Chính", "role": "Admin", "added_at": int(time.time())}


def _save_auth_json_cache():
    try:
        os.makedirs(os.path.dirname(_TG_AUTH_JSON_PATH), exist_ok=True)
        with open(_TG_AUTH_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(_TG_AUTH_RAM_CACHE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _ensure_auth_tables(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS authorized_users (
            uid TEXT PRIMARY KEY,
            name TEXT,
            added_at INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tg_authorized_users (
            uid TEXT PRIMARY KEY,
            name TEXT,
            role TEXT DEFAULT 'VIP',
            added_at INTEGER
        )"""
    )
    # Luôn đảm bảo Root Admin 8827605973 có mặt trong bảng phân quyền
    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('tg_owner_id', ?)",
        (ROOT_ADMIN_ID,)
    )
    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('allow_all_cmd', '0')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO tg_authorized_users (uid, name, role, added_at) VALUES (?, ?, 'Admin', ?)",
        (ROOT_ADMIN_ID, "Admin Chính", int(time.time()))
    )
    conn.execute(
        "INSERT OR IGNORE INTO authorized_users (uid, name, added_at) VALUES (?, ?, ?)",
        (ROOT_ADMIN_ID, "Admin Chính", int(time.time()))
    )


def is_root_admin(user_id) -> bool:
    return str(user_id or "").strip() == ROOT_ADMIN_ID


def is_telegram_user_authorized(user_id, username="", auto_claim_first_owner=False) -> bool:
    """Kiểm tra quyền sử dụng Bot Telegram:
    - Chỉ Admin gốc (8827605973) và các ID được Admin thêm mới được phép sử dụng Bot.
    - Tất cả ID khác hoặc đã bị xoá quyền đều bị chặn 100%!"""
    uid_str = str(user_id or "").strip()
    if not uid_str:
        return False
    if uid_str == ROOT_ADMIN_ID:
        return True
    _load_auth_ram_cache()
    with _TG_AUTH_LOCK:
        if uid_str in _TG_AUTH_RAM_CACHE:
            return True
    try:
        import app as _main_app
        if hasattr(_main_app, "AUTHORIZED_USERS_RAM_CACHE") and uid_str in _main_app.AUTHORIZED_USERS_RAM_CACHE:
            return True
    except Exception:
        pass
    return False


def get_user_role_label(user_id) -> str:
    uid_str = str(user_id or "").strip()
    if uid_str == ROOT_ADMIN_ID:
        return "Admin"
    if is_telegram_user_authorized(uid_str):
        return "Thành viên VIP"
    return "Chưa cấp quyền"


def grant_telegram_permission(target_uid, target_name=""):
    """Thêm ID người dùng được phép sử dụng Bot Telegram & lệnh hệ thống."""
    uid_str = str(target_uid or "").strip().lstrip("@")
    if not uid_str:
        return False
    name_str = (target_name or f"VIP_{uid_str[-4:]}").strip()
    now_ts = int(time.time())
    role_val = "Admin" if uid_str == ROOT_ADMIN_ID else "VIP"
    _load_auth_ram_cache()
    with _TG_AUTH_LOCK:
        _TG_AUTH_RAM_CACHE[uid_str] = {
            "uid": uid_str,
            "name": name_str,
            "role": role_val,
            "added_at": now_ts,
        }
        _save_auth_json_cache()
        try:
            conn = _open_db()
            _ensure_auth_tables(conn)
            conn.execute(
                "INSERT OR REPLACE INTO tg_authorized_users (uid, name, role, added_at) VALUES (?, ?, ?, ?)",
                (uid_str, name_str, role_val, now_ts)
            )
            conn.execute(
                "INSERT OR REPLACE INTO authorized_users (uid, name, added_at) VALUES (?, ?, ?)",
                (uid_str, name_str, now_ts)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
    try:
        import app as _main_app
        if hasattr(_main_app, "add_authorized_user"):
            _main_app.add_authorized_user(uid_str, name_str)
    except Exception:
        pass
    return True


def revoke_telegram_permission(target_uid):
    """Xoá ID người dùng khỏi danh sách được phép sử dụng Bot (thu hồi quyền ngay lập tức)."""
    uid_str = str(target_uid or "").strip().lstrip("@")
    if not uid_str or uid_str == ROOT_ADMIN_ID:
        return False
    removed = False
    _load_auth_ram_cache()
    with _TG_AUTH_LOCK:
        if uid_str in _TG_AUTH_RAM_CACHE:
            _TG_AUTH_RAM_CACHE.pop(uid_str, None)
            removed = True
        else:
            for k in list(_TG_AUTH_RAM_CACHE.keys()):
                if k != ROOT_ADMIN_ID and (k.lower() == uid_str.lower() or _TG_AUTH_RAM_CACHE[k].get("name", "").lower() == uid_str.lower()):
                    _TG_AUTH_RAM_CACHE.pop(k, None)
                    removed = True
        _save_auth_json_cache()
        try:
            conn = _open_db()
            _ensure_auth_tables(conn)
            c1 = conn.execute(
                "DELETE FROM tg_authorized_users WHERE uid = ? OR lower(name) = ?",
                (uid_str, uid_str.lower())
            )
            c2 = conn.execute(
                "DELETE FROM authorized_users WHERE uid = ? OR lower(name) = ?",
                (uid_str, uid_str.lower())
            )
            if (c1.rowcount > 0) or (c2.rowcount > 0):
                removed = True
            conn.commit()
            conn.close()
        except Exception:
            pass
    try:
        import app as _main_app
        if hasattr(_main_app, "remove_authorized_user"):
            if _main_app.remove_authorized_user(uid_str):
                removed = True
    except Exception:
        pass
    return removed


def clear_all_secondary_permissions():
    """Xoá toàn bộ ID phụ, chỉ giữ lại duy nhất Admin gốc 8827605973."""
    _load_auth_ram_cache()
    count = 0
    with _TG_AUTH_LOCK:
        for k in list(_TG_AUTH_RAM_CACHE.keys()):
            if k != ROOT_ADMIN_ID:
                _TG_AUTH_RAM_CACHE.pop(k, None)
                count += 1
        _save_auth_json_cache()
        try:
            conn = _open_db()
            _ensure_auth_tables(conn)
            conn.execute("DELETE FROM tg_authorized_users WHERE uid != ?", (ROOT_ADMIN_ID,))
            conn.execute("DELETE FROM authorized_users WHERE uid != ?", (ROOT_ADMIN_ID,))
            conn.commit()
            conn.close()
        except Exception:
            pass
    try:
        import app as _main_app
        if hasattr(_main_app, "remove_authorized_user"):
            _main_app.remove_authorized_user("__all__")
    except Exception:
        pass
    return count


def list_telegram_permissions():
    """Lấy danh sách đầy đủ các ID được phép sử dụng Bot."""
    _load_auth_ram_cache()
    out = [{"uid": ROOT_ADMIN_ID, "name": "Admin Chính", "role": "Admin", "is_root": True}]
    seen = {ROOT_ADMIN_ID}
    with _TG_AUTH_LOCK:
        for u, info in _TG_AUTH_RAM_CACHE.items():
            if u and u not in seen:
                seen.add(u)
                out.append({
                    "uid": u,
                    "name": info.get("name") or f"VIP_{u[-4:]}",
                    "role": info.get("role") or "VIP",
                    "is_root": False,
                })
    return out


def _get_db_setting(key, default=""):
    try:
        conn = _open_db()
        _ensure_auth_tables(conn)
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row[0] if row and row[0] is not None else default
    except Exception:
        return default


def _set_db_setting(key, value):
    try:
        conn = _open_db()
        _ensure_auth_tables(conn)
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
    except Exception:
        pass


def sync_zalo_account_to_web_db(uid, display_name, imei, cookies_dict, zpw_enk="", user_agent="", pc_name=""):
    """Lưu tài khoản Zalo vừa quét QR vào SQLite database.db & kích hoạt luồng lắng nghe đa nhóm."""
    try:
        clean_ck = {
            str(k): str(v)
            for k, v in (cookies_dict or {}).items()
            if _is_valid_cookie_val(v)
        }
        cookies_json = json.dumps(clean_ck, ensure_ascii=False)
        ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        conn = _open_db()
        conn.execute(
            """CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                imei TEXT,
                cookies TEXT,
                platform TEXT DEFAULT 'zalo',
                token TEXT DEFAULT '',
                is_bot INTEGER DEFAULT 0,
                uid TEXT DEFAULT '',
                zpw_enk TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1
            )"""
        )
        cur = conn.cursor()
        existing = None
        if uid:
            existing = cur.execute(
                "SELECT id FROM accounts WHERE platform='zalo' AND uid=?", (str(uid),)
            ).fetchone()
        if not existing and imei:
            existing = cur.execute(
                "SELECT id FROM accounts WHERE platform='zalo' AND imei=?", (str(imei),)
            ).fetchone()

        acc_label = display_name or f"Zalo_{str(uid)[-4:]}"
        if existing:
            acc_id = existing[0]
            cur.execute(
                """UPDATE accounts
                   SET name=?, imei=?, cookies=?, uid=?, zpw_enk=CASE WHEN ? != '' THEN ? ELSE zpw_enk END,
                       user_agent=?, enabled=1
                   WHERE id=?""",
                (acc_label, imei, cookies_json, str(uid or ""), str(zpw_enk or ""), str(zpw_enk or ""), ua, acc_id),
            )
        else:
            cur.execute(
                """INSERT INTO accounts (name, imei, cookies, platform, token, is_bot, uid, zpw_enk, user_agent, enabled)
                   VALUES (?, ?, ?, 'zalo', '', 0, ?, ?, ?, 1)""",
                (acc_label, imei, cookies_json, str(uid or ""), str(zpw_enk or ""), ua),
            )
            acc_id = cur.lastrowid

        conn.commit()
        conn.close()

        try:
            import app as _main_app
            if hasattr(_main_app, "reload_accounts_to_ram"):
                _main_app.reload_accounts_to_ram()
            if hasattr(_main_app, "ensure_account_listener"):
                acc_row = {
                    "id": acc_id,
                    "name": acc_label,
                    "imei": imei,
                    "cookies": cookies_json,
                    "platform": "zalo",
                    "uid": str(uid or ""),
                    "zpw_enk": str(zpw_enk or ""),
                    "user_agent": ua,
                    "enabled": 1,
                }
                _main_app.ensure_account_listener(acc_row)
        except Exception:
            pass
        return acc_id
    except Exception:
        return None


def parse_imei_and_cookie_from_text(raw_text):
    meta = extract_imei_and_metadata_flexible(raw_text)
    cookies_dict = parse_cookies_input_flexible(raw_text)
    imei = meta.get("imei") or cookies_dict.get("imei") or cookies_dict.get("_zlang") or ""
    cookies_dict.pop("imei", None)
    return imei, cookies_dict, meta


def sync_and_keepalive_tokens_to_db(raw_text):
    saved_items = []
    if not raw_text:
        return saved_items

    for m in DISCORD_TOKEN_RE.finditer(raw_text):
        tok = m.group(1).strip()
        try:
            r = requests.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": tok, "User-Agent": "Mozilla/5.0"},
                timeout=6,
            )
            if r.status_code != 200:
                r = requests.get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": f"Bot {tok}", "User-Agent": "Mozilla/5.0"},
                    timeout=6,
                )
                is_bot = 1 if r.status_code == 200 else 0
            else:
                is_bot = 0

            if r.status_code == 200:
                u = r.json()
                uid = str(u.get("id") or "")
                uname = u.get("global_name") or u.get("username") or f"Discord_{uid[-4:]}"
                conn = _open_db()
                cur = conn.cursor()
                ex = cur.execute(
                    "SELECT id FROM accounts WHERE platform='discord' AND (token=? OR uid=?)",
                    (tok, uid),
                ).fetchone()
                if ex:
                    acc_id = ex[0]
                    cur.execute(
                        "UPDATE accounts SET name=?, token=?, is_bot=?, uid=?, enabled=1 WHERE id=?",
                        (uname, tok, is_bot, uid, acc_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO accounts (name, imei, cookies, platform, token, is_bot, uid, enabled) VALUES (?, '', '{}', 'discord', ?, ?, ?, 1)",
                        (uname, tok, is_bot, uid),
                    )
                    acc_id = cur.lastrowid
                conn.commit()
                conn.close()
                saved_items.append({"platform": "Discord", "name": uname, "uid": uid, "id": acc_id})
        except Exception:
            pass

    if "c_user=" in raw_text and "xs=" in raw_text:
        uid_m = re.search(r"c_user=(\d+)", raw_text)
        uid = uid_m.group(1) if uid_m else ""
        fb_name = f"FB_{uid[-4:]}" if uid else "Messenger_Acc"
        try:
            conn = _open_db()
            cur = conn.cursor()
            ex = cur.execute(
                "SELECT id FROM accounts WHERE platform='messenger' AND uid=?", (uid,)
            ).fetchone()
            if ex:
                acc_id = ex[0]
                cur.execute(
                    "UPDATE accounts SET cookies=?, enabled=1 WHERE id=?", (raw_text.strip(), acc_id)
                )
            else:
                cur.execute(
                    "INSERT INTO accounts (name, imei, cookies, platform, token, is_bot, uid, enabled) VALUES (?, '', ?, 'messenger', '', 0, ?, 1)",
                    (fb_name, raw_text.strip(), uid),
                )
                acc_id = cur.lastrowid
            conn.commit()
            conn.close()
            saved_items.append({"platform": "Messenger", "name": fb_name, "uid": uid, "id": acc_id})
        except Exception:
            pass

    try:
        import app as _main_app
        if saved_items and hasattr(_main_app, "reload_accounts_to_ram"):
            _main_app.reload_accounts_to_ram()
    except Exception:
        pass
    return saved_items


class MetaAIAssistant:
    """Trợ lý AI đa năng tích hợp trực tiếp."""
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
            "Origin": "https://www.meta.ai",
            "Referer": "https://www.meta.ai/",
        }
        self.lsd = None
        self.fb_dtsg = None
        self.initialized = False

    @staticmethod
    def _extract_val(text, start_s, end_s):
        try:
            s = text.index(start_s) + len(start_s)
            e = text.index(end_s, s)
            return text[s:e]
        except Exception:
            return ""

    def initialize_session(self):
        try:
            resp = self.session.get("https://www.meta.ai/", headers=self.headers, timeout=8)
            raw = resp.text
            self.lsd = self._extract_val(raw, '"LSD",[],{"token":"', '"}')
            self.fb_dtsg = self._extract_val(raw, 'DTSGInitData",[],{"token":"', '"')
            self.initialized = bool(self.lsd)
            return self.initialized
        except Exception:
            return False

    def ask(self, question):
        if not question:
            return "Vui lòng nhập câu hỏi."
        try:
            r = requests.get(
                "https://text.pollinations.ai/" + requests.utils.quote(f"Trả lời ngắn gọn bằng tiếng Việt: {question}"),
                timeout=12,
            )
            if r.status_code == 200 and r.text.strip():
                return r.text.strip()
        except Exception:
            pass
        return f"🤖 [AI Assistant]: Đã ghi nhận yêu cầu: '{question}'."


class DiscordTokenGetter:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/login",
        }

    def login_discord(self, email, password, twofa_code="", twofa_type="totp"):
        try:
            r = self.session.post(
                "https://discord.com/api/v9/auth/login",
                headers=self.headers,
                json={"login": email, "password": password, "undelete": False},
                timeout=12,
            )
            data = r.json()
            if "token" in data and data["token"]:
                return {"status": "SUCCESS", "token": data["token"]}
            if data.get("mfa") and "ticket" in data:
                ticket = data["ticket"]
                if not twofa_code:
                    return {"status": "2FA_REQUIRED", "ticket": ticket, "message": "Tài khoản bật 2FA, hãy kèm mã 6 số hoặc Secret 2FA."}
                code_use = str(twofa_code).strip()
                if len(code_use) > 8:
                    totp_c, _ = generate_totp_local(code_use)
                    if totp_c:
                        code_use = totp_c
                ep = "totp" if twofa_type != "sms" else "sms"
                r2 = self.session.post(
                    f"https://discord.com/api/v9/auth/mfa/{ep}",
                    headers=self.headers,
                    json={"code": code_use, "ticket": ticket},
                    timeout=12,
                )
                d2 = r2.json()
                if "token" in d2 and d2["token"]:
                    return {"status": "SUCCESS", "token": d2["token"]}
                return {"status": "ERROR", "message": f"Lỗi xác thực 2FA: {d2.get('message', d2)}"}
            return {"status": "ERROR", "message": data.get("message") or str(data)}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}


class FacebookCookieGetter:
    def __init__(self):
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"

    def login_facebook(self, email, password, twofa_code=""):
        try:
            headers = {
                "User-Agent": self.ua,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://m.facebook.com",
                "Referer": "https://m.facebook.com/login/",
            }
            self.session.get("https://m.facebook.com/login/", headers=headers, timeout=10)
            payload = {"email": email, "pass": password, "login": "Log In"}
            self.session.post("https://m.facebook.com/login/device-based/regular/login/", headers=headers, data=payload, timeout=12)
            ck_dict = self.session.cookies.get_dict()
            if "c_user" in ck_dict and "xs" in ck_dict:
                ck_str = "; ".join(f"{k}={v}" for k, v in ck_dict.items())
                return {"status": "SUCCESS", "cookies": ck_str, "uid": ck_dict["c_user"], "access_token": ""}
            if "checkpoint" in ck_dict:
                return {"status": "CHECKPOINT", "message": "Tài khoản yêu cầu xác minh Checkpoint / 2FA trên thiết bị."}
            return {"status": "ERROR", "message": "Sai mật khẩu hoặc Facebook chặn đăng nhập trực tiếp. Hãy dán trực tiếp chuỗi Cookie c_user=...; xs=... vào Bot!"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}


class DirectTelegramBotRunner:
    """Bộ điều khiển trung tâm BOT TREO 4APP 🇻🇳 qua Telegram (Giao diện Video + 3 Tab 32 Item + Phân quyền ID + Anti-Ban Box)."""

    def __init__(self, token=TELEGRAM_BOT_TOKEN):
        self.token = (token or TELEGRAM_BOT_TOKEN).strip()
        self.api_base = f"https://api.telegram.org/bot{self.token}"
        self.running = False
        self.offset = 0
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=40)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.user_states = {}
        self.wizard_selections = {}
        self.active_qr_locks = set()
        self.bot_username = ""
        self.bot_id = None
        self.last_error = ""
        self.started_at = time.time()
        self.executor = ThreadPoolExecutor(max_workers=20)
        self._cached_welcome_file_id = _get_db_setting("tg_welcome_file_id", "")
        self._cached_welcome_kind = _get_db_setting("tg_welcome_kind", "animation")

    def api_call(self, method, data=None, files=None, timeout=25):
        url = f"{self.api_base}/{method}"
        try:
            if files:
                r = self.session.post(url, data=data, files=files, timeout=timeout)
            else:
                r = self.session.post(url, json=data, timeout=timeout)
            return r.json()
        except Exception as e:
            self.last_error = str(e)
            return {"ok": False, "description": str(e)}

    def clear_webhook_and_init(self):
        try:
            self.api_call("deleteWebhook", {"drop_pending_updates": False}, timeout=10)
            me = self.api_call("getMe", timeout=10)
            if me.get("ok") and me.get("result"):
                self.bot_username = me["result"].get("username") or ""
                self.bot_id = me["result"].get("id")
                self.api_call(
                    "setMyCommands",
                    {
                        "commands": [
                            {"command": "start", "description": "🎬 Mở bảng điều khiển BOT TREO 4APP 🇻🇳"},
                            {"command": "menu", "description": "📋 Mở nhanh Menu 32 Chức Năng VIP"},
                            {"command": "qr", "description": "📲 Quét mã QR Zalo PC tự nạp Cookie & IMEI"},
                            {"command": "addid", "description": "➕ Thêm ID người dùng được phép sài Bot"},
                            {"command": "delid", "description": "➖ Xoá ID người dùng khỏi Bot"},
                            {"command": "listid", "description": "📋 Xem danh sách ID được phép sài Bot"},
                            {"command": "checkzalo", "description": "🔍 Kiểm tra & Cứu Cookie Zalo Live/Die"},
                            {"command": "status", "description": "📊 Xem trạng thái Acc & Chiến dịch đang chạy"},
                            {"command": "stopall", "description": "🛑 Dừng khẩn cấp toàn bộ chiến dịch (.ta)"},
                        ]
                    },
                    timeout=10,
                )
                return True
        except Exception as e:
            self.last_error = str(e)
        return False

    def send_text(self, chat_id, text, reply_to=None, parse_mode="HTML", reply_markup=None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.api_call("sendMessage", payload, timeout=15)

    def send_welcome_video_menu(self, chat_id, caption_html, reply_to=None, reply_markup=None):
        """Gửi bảng điều khiển kèm Video chào (welcome.mp4) giống hệt ảnh mẫu, tự động cache file_id để phản hồi 0.05s!"""
        # 1. Thử dùng file_id đã cache để gửi tức thì không tốn băng thông
        if self._cached_welcome_file_id:
            method = "sendAnimation" if self._cached_welcome_kind == "animation" else "sendVideo"
            media_key = "animation" if self._cached_welcome_kind == "animation" else "video"
            payload = {
                "chat_id": chat_id,
                media_key: self._cached_welcome_file_id,
                "caption": caption_html,
                "parse_mode": "HTML",
            }
            if reply_to:
                payload["reply_to_message_id"] = reply_to
            if reply_markup:
                payload["reply_markup"] = reply_markup
            res = self.api_call(method, payload, timeout=15)
            if res.get("ok"):
                return res
            # Nếu token đổi làm file_id cũ hết hạn, xóa cache để upload lại
            self._cached_welcome_file_id = ""

        # 2. Tải trực tiếp file welcome.mp4 lên Telegram lần đầu và lưu file_id
        if os.path.exists(WELCOME_VIDEO_PATH):
            try:
                with open(WELCOME_VIDEO_PATH, "rb") as vf:
                    video_bytes = vf.read()
                data = {
                    "chat_id": str(chat_id),
                    "caption": caption_html,
                    "parse_mode": "HTML",
                }
                if reply_to:
                    data["reply_to_message_id"] = str(reply_to)
                if reply_markup:
                    data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

                res = self.api_call(
                    "sendAnimation",
                    data=data,
                    files={"animation": ("welcome.mp4", video_bytes, "video/mp4")},
                    timeout=35,
                )
                if res.get("ok") and res.get("result"):
                    r_obj = res["result"]
                    fid = (
                        (r_obj.get("animation") or {}).get("file_id")
                        or (r_obj.get("video") or {}).get("file_id")
                        or (r_obj.get("document") or {}).get("file_id")
                    )
                    kind = "animation" if r_obj.get("animation") else "video"
                    if fid:
                        self._cached_welcome_file_id = fid
                        self._cached_welcome_kind = kind
                        _set_db_setting("tg_welcome_file_id", fid)
                        _set_db_setting("tg_welcome_kind", kind)
                    return res

                # Fallback sang sendVideo nếu sendAnimation bị từ chối
                res2 = self.api_call(
                    "sendVideo",
                    data=data,
                    files={"video": ("welcome.mp4", video_bytes, "video/mp4")},
                    timeout=35,
                )
                if res2.get("ok") and res2.get("result"):
                    r_obj = res2["result"]
                    fid = (r_obj.get("video") or {}).get("file_id") or (r_obj.get("animation") or {}).get("file_id")
                    if fid:
                        self._cached_welcome_file_id = fid
                        self._cached_welcome_kind = "video"
                        _set_db_setting("tg_welcome_file_id", fid)
                        _set_db_setting("tg_welcome_kind", "video")
                    return res2
            except Exception:
                pass

        return self.send_text(chat_id, caption_html, reply_to=reply_to, reply_markup=reply_markup)

    def edit_menu_message(self, chat_id, message_id, caption_html, reply_markup=None):
        """Cập nhật mượt mà nội dung & nút bấm ngay dưới Video chào (giống 'đã sửa' trong ảnh mẫu)."""
        payload_cap = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": caption_html,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload_cap["reply_markup"] = reply_markup
        res = self.api_call("editMessageCaption", payload_cap, timeout=12)
        if res.get("ok") or "message is not modified" in str(res.get("description", "")).lower():
            return res

        payload_txt = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": caption_html,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload_txt["reply_markup"] = reply_markup
        res2 = self.api_call("editMessageText", payload_txt, timeout=12)
        if res2.get("ok") or "message is not modified" in str(res2.get("description", "")).lower():
            return res2
        return self.send_welcome_video_menu(chat_id, caption_html, reply_markup=reply_markup)

    def answer_callback(self, callback_query_id, text="", show_alert=False):
        payload = {"callback_query_id": callback_query_id, "show_alert": bool(show_alert)}
        if text:
            payload["text"] = text[:190]
        return self.api_call("answerCallbackQuery", payload, timeout=8)

    def send_photo_bytes(self, chat_id, png_bytes, caption="", reply_to=None, reply_markup=None):
        data = {"chat_id": str(chat_id), "parse_mode": "HTML"}
        if caption:
            data["caption"] = caption
        if reply_to:
            data["reply_to_message_id"] = str(reply_to)
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        files = {"photo": ("zalo_qr.png", png_bytes, "image/png")}
        return self.api_call("sendPhoto", data=data, files=files, timeout=20)

    def send_doc_bytes(self, chat_id, content_bytes, filename, caption="", reply_to=None):
        data = {"chat_id": str(chat_id), "parse_mode": "HTML"}
        if caption:
            data["caption"] = caption
        if reply_to:
            data["reply_to_message_id"] = str(reply_to)
        files = {"document": (filename, content_bytes, "text/plain")}
        return self.api_call("sendDocument", data=data, files=files, timeout=20)

    def delete_msg(self, chat_id, message_id):
        if not message_id:
            return
        self.api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id}, timeout=8)

    # XÂY DỰNG GIAO DIỆN 3 TAB & 4 TRANG GIỐNG HỆT ẢNH MẪU (image.png)
    @staticmethod
    def _get_live_runtime_summary():
        acc_cnt = 0
        running_cnt = 0
        color_label = "Đổi Từng Màu"
        delay_val = 0.0
        try:
            import app as _main_app
            accs = _main_app.get_all_accounts_from_ram(enabled_only=True)
            acc_cnt = len(accs)
            with _main_app.TASKS_LOCK:
                running_cnt = sum(1 for t in _main_app.TASKS.values() if t.get("running"))
            with _main_app.SYSTEM_CFG_LOCK:
                cm = _main_app.SYSTEM_RUNTIME_CONFIG.get("color_mode", "word_rainbow")
                delay_val = _main_app.SYSTEM_RUNTIME_CONFIG.get("delay", 0.0)
                color_label = "Đổi Từng Màu" if cm != "fixed" and cm != "none" else ("Đỏ Rực" if cm == "fixed" else "Mặc Định")
        except Exception:
            pass
        return acc_cnt, running_cnt, color_label, delay_val

    @classmethod
    def build_tabbed_caption(cls, user_first_name="Anh", user_id=ROOT_ADMIN_ID, active_tab="func", page=1, extra_notice=""):
        now_vn = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
        time_str = now_vn.strftime("%H:%M %d/%m/%Y")
        role_str = get_user_role_label(user_id)
        name_clean = str(user_first_name or "Anh").replace("<", "").replace(">", "").strip() or "Anh"

        if active_tab == "func":
            sec_title = f"CHỨC NĂNG – trang {page}/4"
        elif active_tab == "mgmt":
            sec_title = "QUẢN LÝ HỆ THỐNG & PHÂN QUYỀN ID"
        else:
            sec_title = "TIỆN ÍCH MỞ RỘNG VIP"

        acc_cnt, running_cnt, color_label, delay_val = cls._get_live_runtime_summary()
        status_bar = f"\n📡 Acc: <b>{acc_cnt}</b> • Đang chạy: <b>{running_cnt}</b> • Màu: <b>{color_label}</b> ({delay_val}s)"
        notice_block = f"\n\n{extra_notice}" if extra_notice else ""

        return (
            f"👋 Xin chào, {name_clean}!\n\n"
            f"<b>BOT TREO 4APP 🇻🇳</b>\n"
            f"👾 Chức năng: 32 item\n"
            f"💼 Quản lý: 6 mục\n"
            f"🔧 Tiện ích: 6 mục\n"
            f"────────────────────\n"
            f"🕒 {time_str}\n"
            f"🥷 Vai trò: {role_str}\n"
            f"👤 Admin: <a href=\"tg://user?id={ROOT_ADMIN_ID}\">Bấm vào đây ↗️</a>"
            f"{status_bar}"
            f"{notice_block}\n\n"
            f"⚙️ <b>{sec_title}</b>"
        )

    @classmethod
    def build_tabbed_keyboard(cls, active_tab="func", page=1):
        page = max(1, min(4, int(page or 1)))
        tab_row = [
            {
                "text": f"{'🔘' if active_tab == 'func' else '⚪'} Chức Năng",
                "callback_data": "tab_func_1"
            },
            {
                "text": f"{'🔘' if active_tab == 'mgmt' else '⚪'} Quản Lý",
                "callback_data": "tab_mgmt"
            },
            {
                "text": f"{'🔘' if active_tab == 'util' else '⚪'} Tiện Ích",
                "callback_data": "tab_util"
            },
        ]
        sep_row = [{"text": "────────────────────────", "callback_data": "noop"}]
        rows = [tab_row, sep_row]

        if active_tab == "func":
            start_idx = (page - 1) * 8
            page_items = FUNCTION_ITEMS_32[start_idx:start_idx + 8]
            for i in range(0, len(page_items), 2):
                pair = page_items[i:i + 2]
                row = [{"text": item["label"], "callback_data": f"pickfn:{item['id']}"} for item in pair]
                rows.append(row)

            prev_p = 4 if page <= 1 else page - 1
            next_p = 1 if page >= 4 else page + 1
            rows.append([
                {"text": "⬅️ Trang trước", "callback_data": f"tab_func_{prev_p}"},
                {"text": f"📄 {page}/4", "callback_data": "noop"},
                {"text": "Trang sau ➡️", "callback_data": f"tab_func_{next_p}"},
            ])

        elif active_tab == "mgmt":
            rows.extend([
                [
                    {"text": "➕ Thêm ID Người Dùng", "callback_data": "mgmt_add_id"},
                    {"text": "➖ Xoá ID Người Dùng", "callback_data": "mgmt_del_id_menu"},
                ],
                [
                    {"text": "📋 Danh Sách ID VIP", "callback_data": "mgmt_list_ids"},
                    {"text": "📲 Quét QR Zalo PC", "callback_data": "cmd_qr_sg"},
                ],
                [
                    {"text": "🔍 Check & Cứu Cookie", "callback_data": "cmd_checkzalo"},
                    {"text": "🗂️ Quản Lý Acc & File", "callback_data": "mgmt_acc_files"},
                ],
            ])

        else:  # util
            rows.extend([
                [
                    {"text": "🔐 Tạo Mã 2FA OTP", "callback_data": "prompt_2fa"},
                    {"text": "🤖 Trợ Lý Meta AI", "callback_data": "prompt_ai"},
                ],
                [
                    {"text": "🎯 Lấy Token Discord", "callback_data": "prompt_gettoken"},
                    {"text": "🍪 Lấy Cookie FB", "callback_data": "prompt_getcookie"},
                ],
                [
                    {"text": "✨ Đổi Font Chữ VIP", "callback_data": "pickfn:fn_fontstyle"},
                    {"text": "📊 Trạng Thái Hệ Thống", "callback_data": "cmd_status"},
                ],
            ])

        return {"inline_keyboard": rows}

    # BẢNG CHỌN CHIẾN DỊCH TƯƠNG TÁC (CHỌN BOX + CHỌN FILE + CHẠY NGAY TRÊN TELEGRAM)
    def _discover_all_boxes(self):
        boxes = []
        seen = set()
        try:
            import app as _main_app
            accs = _main_app.get_all_accounts_from_ram(enabled_only=True)
            for a in accs:
                plat = a.get("platform") or "zalo"
                if plat == "zalo":
                    try:
                        zc = _main_app.Zalo.get_pooled_client(
                            a["imei"], a["cookies"],
                            user_agent=a.get("user_agent") or "",
                            zpw_enk_hint=a.get("zpw_enk") or "",
                            uid_hint=a.get("uid") or ""
                        )
                        for g in (zc.get_groups() or []):
                            gid = str(g.get("id") or "").strip()
                            if gid and gid not in seen and gid != "null":
                                seen.add(gid)
                                boxes.append({
                                    "id": gid,
                                    "name": g.get("name") or f"Nhóm {gid[-4:]}",
                                    "platform": "zalo",
                                    "acc_id": a["id"],
                                })
                    except Exception:
                        pass
                elif plat == "discord":
                    for cid in _main_app.DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS.get(a["id"], set()):
                        if cid and cid not in seen:
                            seen.add(cid)
                            boxes.append({
                                "id": str(cid),
                                "name": f"Kênh Discord {str(cid)[-4:]}",
                                "platform": "discord",
                                "acc_id": a["id"],
                            })
        except Exception:
            pass
        return boxes

    def _get_available_txt_files(self):
        try:
            import app as _main_app
            return _main_app.get_ordered_files_with_display_num()
        except Exception:
            up_dir = os.path.join(BASE_DIR, "uploads")
            out = []
            if os.path.exists(up_dir):
                for idx, fn in enumerate(sorted(os.listdir(up_dir)), 1):
                    if fn.endswith(".txt"):
                        out.append({"num": idx, "filename": fn})
            return out

    def render_function_wizard(self, chat_id, message_id, user_id, fn_id):
        fn_meta = FUNCTION_MAP_BY_ID.get(fn_id)
        if not fn_meta:
            return

        mode = fn_meta["mode"]
        # Các chức năng cấu hình nhanh
        if mode == "special_stop":
            try:
                import app as _main_app
                stopped = _main_app.stop_tasks_for_thread(None)
            except Exception:
                stopped = 0
            cap = self.build_tabbed_caption(
                user_id=user_id, active_tab="func", page=4,
                extra_notice=f"🛑 <b>ĐÃ DỪNG TẤT CẢ ({stopped} chiến dịch)!</b>"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4))
            return

        if mode == "special_delay":
            kb = {
                "inline_keyboard": [
                    [
                        {"text": "⚡ 0.0s (Siêu tốc)", "callback_data": "setdelay:0"},
                        {"text": "🚀 0.3s (Chuẩn VIP)", "callback_data": "setdelay:0.3"},
                    ],
                    [
                        {"text": "🔥 0.5s (Mượt)", "callback_data": "setdelay:0.5"},
                        {"text": "🛡️ 1.0s (An toàn)", "callback_data": "setdelay:1.0"},
                    ],
                    [
                        {"text": "🐢 2.0s (Chậm chắc)", "callback_data": "setdelay:2.0"},
                        {"text": "⏱️ 5.0s (Treo bền)", "callback_data": "setdelay:5.0"},
                    ],
                    [{"text": "🔙 Quay lại Chức Năng", "callback_data": "tab_func_4"}],
                ]
            }
            cap = (
                "⏱️ <b>CHỈNH TỐC ĐỘ DELAY HỆ THỐNG</b>\n"
                "────────────────────\n"
                "• Chọn tốc độ gửi tin bên dưới (áp dụng tức thì cho cả các chiến dịch đang chạy):\n"
                "• <i>Khuyên dùng 0.3s - 0.5s kết hợp Anti Cấm Chat Box để treo bền xuyên đêm!</i>"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        if mode == "special_color":
            kb = {
                "inline_keyboard": [
                    [{"text": "✨ Chữ Đổi Từng Màu (VIP - Mặc định)", "callback_data": "setcolor:word_rainbow:red"}],
                    [
                        {"text": "🥀 Đỏ Rực (db342e)", "callback_data": "setcolor:fixed:red"},
                        {"text": "🔥 Cam Lửa (f27806)", "callback_data": "setcolor:fixed:orange"},
                    ],
                    [
                        {"text": "👑 Vàng Kim (f7b503)", "callback_data": "setcolor:fixed:yellow"},
                        {"text": "🍀 Xanh Ngọc (15a85f)", "callback_data": "setcolor:fixed:green"},
                    ],
                    [{"text": "🔙 Quay lại Chức Năng", "callback_data": "tab_func_4"}],
                ]
            }
            cap = (
                "🎨 <b>CHẾ ĐỘ MÀU CHỮ ZALO VIP (0% CHỮ TRẮNG)</b>\n"
                "────────────────────\n"
                "• <b>Chữ Đổi Từng Màu</b>: Từng từ/chữ cái tự động đổi qua 4 mã màu gốc rực rỡ của Zalo (Đỏ - Cam - Vàng - Xanh Lá).\n"
                "• Tuyệt đối không dùng màu trắng cho câu treo/nhây (chỉ để màu trắng cho tin nhắn chức năng hệ thống)."
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        if mode == "special_font":
            kb = {
                "inline_keyboard": [
                    [
                        {"text": "🔥 Chữ To Đậm (f_18)", "callback_data": "setfont:big_bold"},
                        {"text": "⚡ Chữ Vừa Đậm (f_15)", "callback_data": "setfont:normal_bold"},
                    ],
                    [
                        {"text": "✨ Xen Kẽ To/Nhỏ", "callback_data": "setfont:alternating_bold"},
                        {"text": "💎 Nghiêng Đậm VIP", "callback_data": "setfont:italic_bold"},
                    ],
                    [{"text": "🔙 Quay lại Chức Năng", "callback_data": "tab_func_4"}],
                ]
            }
            cap = (
                "🔤 <b>CHỈNH CỠ & KIỂU CHỮ ZALO</b>\n"
                "────────────────────\n"
                "• Chọn kiểu hiển thị chữ kết hợp cùng bộ đổi màu từng từ:"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        if mode == "special_anti":
            kb = {
                "inline_keyboard": [
                    [{"text": "🛡️ Bật Full Anti Cấm Chat Box (Khuyên dùng)", "callback_data": "setanti:1"}],
                    [{"text": "⚡ Chế Độ Xả Thẳng Tốc Độ Cao", "callback_data": "setanti:0"}],
                    [{"text": "🔙 Quay lại Chức Năng", "callback_data": "tab_func_4"}],
                ]
            }
            cap = (
                "🛡️ <b>LÁ CHẮN CHỐNG ZALO CẤM CHAT BOX (VIP ANTI-BAN)</b>\n"
                "────────────────────\n"
                "✅ <b>Sliding-Window Box Pacing</b>: Tự động điều tiết khi bắn dồn dập vào 1 Box, chặn đứng mã phạt <code>-112</code>, <code>-114</code>, <code>300</code>, <code>301</code>.\n"
                "✅ <b>Typing Pulse Simulation</b>: Giả lập trạng thái đang gõ phím (<code>/api/group/typing</code>) định kỳ như người thật.\n"
                "✅ <b>Dynamic Polymorphic Tail</b>: Gắn đuôi tàng hình biến thiên 4-10 ký tự giúp mỗi câu có mã băm độc nhất.\n"
                "✅ <b>Multi-Gateway Rotation</b>: Tự động xoay vòng giữa <code>tt-group-wpa</code> và <code>wpa.chat.zalo.me</code>."
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        if mode == "special_prx":
            snap = {}
            try:
                import app as _main_app
                snap = _main_app.ProxyPoolEngine.get_snapshot()
            except Exception:
                pass
            kb = {
                "inline_keyboard": [
                    [{"text": "➕ Nạp Thêm Proxy Mới", "callback_data": "prx_add_prompt"}],
                    [
                        {"text": "🔄 Test Ping Proxy", "callback_data": "prx_test_now"},
                        {"text": "🗑️ Xoá Sạch Proxy", "callback_data": "prx_clear_now"},
                    ],
                    [{"text": "🔙 Quay lại Chức Năng", "callback_data": "tab_func_4"}],
                ]
            }
            cap = (
                "🌐 <b>QUẢN LÝ HỒ PROXY SIÊU TỐC</b>\n"
                "────────────────────\n"
                f"• Tổng Proxy: <b>{snap.get('total', 0)}</b> (Khỏe: <b>{snap.get('healthy', 0)}</b>)\n"
                f"• Ping nhanh nhất: <b>{snap.get('fastest_ms', 0)} ms</b>\n"
                f"• Đã định tuyến: <b>{snap.get('routed_ok', 0)} gói tin</b>"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        # Khởi tạo lựa chọn Wizard cho chiến dịch
        wiz = self.wizard_selections.get(user_id) or {}
        wiz["fn_id"] = fn_id
        wiz.setdefault("box_id", "ALL")
        wiz.setdefault("box_name", "Tất Cả Các Box (All)")
        wiz.setdefault("file_name", fn_meta.get("file_hint") or "nhay.txt")
        wiz.setdefault("custom_text", "")
        wiz.setdefault("tag_query", "")
        self.wizard_selections[user_id] = wiz

        boxes = self._discover_all_boxes()
        files = self._get_available_txt_files()

        kb_rows = [
            [{"text": f"🚀 BẮT ĐẦU CHẠY: {fn_meta['label']}", "callback_data": f"runfn:{fn_id}"}],
            [{"text": f"📦 Chọn Box: {wiz['box_name'][:24]}", "callback_data": f"wiz_pickbox:{fn_id}"}],
        ]
        # Hiển thị nhanh 4 file kịch bản phổ biến
        file_btns = []
        for f_item in files[:6]:
            fn_s = f_item["filename"]
            mark = "✅ " if wiz.get("file_name") == fn_s and not wiz.get("custom_text") else "📄 "
            file_btns.append({"text": f"{mark}{fn_s}", "callback_data": f"wiz_setfile:{fn_id}:{fn_s}"})
        for i in range(0, len(file_btns), 2):
            kb_rows.append(file_btns[i:i + 2])

        kb_rows.append([
            {"text": "✍️ Nhập Nội Dung / @Tag", "callback_data": f"wiz_customtxt:{fn_id}"},
            {"text": "🛑 Dừng Chiến Dịch Này", "callback_data": "fn_stop_all_quick"},
        ])
        kb_rows.append([{"text": "🔙 Quay lại Bảng Chức Năng", "callback_data": "tab_func_1"}])

        content_preview = (
            f"Văn bản tự nhập ({len(wiz['custom_text'])} ký tự)"
            if wiz.get("custom_text")
            else f"File kịch bản <code>{wiz.get('file_name')}</code>"
        )
        tag_info = f"\n🏷️ Tag mục tiêu: <code>{wiz['tag_query']}</code>" if wiz.get("tag_query") else ""

        cap = (
            f"⚙️ <b>CẤU HÌNH: {fn_meta['label'].upper()}</b>\n"
            f"<i>{fn_meta['desc']}</i>\n"
            f"────────────────────\n"
            f"📦 Mục tiêu: <b>{wiz['box_name']}</b> (Hiện có {len(boxes)} Box)\n"
            f"📄 Nội dung: {content_preview}"
            f"{tag_info}\n"
            f"🎨 Màu chữ: <b>{'Đỏ Rực (db342e)' if fn_meta['color_mode'] == 'fixed' else 'Chữ Đổi Từng Màu (0% Trắng)'}</b>\n"
            f"🛡️ Anti-Ban Box: <b>Đang Bật (Chống Zalo Cấm Chat)</b>\n\n"
            f"👉 Bấm <b>🚀 BẮT ĐẦU CHẠY</b> để phang ngay hoặc đổi Box/File bên dưới:"
        )
        self.edit_menu_message(chat_id, message_id, cap, reply_markup={"inline_keyboard": kb_rows})

    def launch_wizard_campaign(self, chat_id, message_id, user_id, fn_id):
        fn_meta = FUNCTION_MAP_BY_ID.get(fn_id)
        if not fn_meta:
            return
        wiz = self.wizard_selections.get(user_id) or {}
        box_id = wiz.get("box_id") or "ALL"
        file_name = wiz.get("file_name") or fn_meta.get("file_hint") or "nhay.txt"
        custom_text = (wiz.get("custom_text") or "").strip()
        tag_query = (wiz.get("tag_query") or "").strip()

        try:
            import app as _main_app
            boxes = self._discover_all_boxes()
            if box_id == "ALL":
                target_boxes = boxes
            else:
                target_boxes = [b for b in boxes if str(b["id"]) == str(box_id)]
                if not target_boxes:
                    # Nếu người dùng nhập thẳng ID Box thủ công
                    accs = _main_app.get_all_accounts_from_ram(enabled_only=True)
                    if accs:
                        target_boxes = [{
                            "id": str(box_id),
                            "name": f"Box {str(box_id)[-6:]}",
                            "platform": accs[0].get("platform") or "zalo",
                            "acc_id": accs[0]["id"],
                        }]

            if not target_boxes:
                self.send_text(
                    chat_id,
                    "⚠️ <b>Chưa tìm thấy Box Zalo/Discord nào!</b>\n"
                    "• Hãy quét QR Zalo PC (trong tab <b>Quản Lý -> 📲 Quét QR Zalo PC</b>) hoặc gõ lệnh <code>.menu</code> trong nhóm Zalo trước, hoặc bấm <b>📦 Chọn Box</b> để nhập ID nhóm.",
                )
                return

            # Đọc nội dung từ file hoặc custom_text
            raw_content = custom_text
            if not raw_content:
                fpath = os.path.join(BASE_DIR, "uploads", os.path.basename(file_name))
                if os.path.exists(fpath):
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        raw_content = f.read()
                else:
                    raw_content = "Sủa mạnh lên con chó ngu"

            mode = fn_meta["mode"]
            if mode == "treo_ngon":
                blocks = [raw_content.strip()] if raw_content.strip() else ["Treo ngôn VIP"]
            else:
                blocks = [ln.strip() for ln in raw_content.splitlines() if ln.strip()] or [raw_content.strip()]

            if tag_query:
                blocks = [f"{b} {tag_query}" for b in blocks]

            with _main_app.SYSTEM_CFG_LOCK:
                cur_delay = float(_main_app.SYSTEM_RUNTIME_CONFIG.get("delay", 0.0))
                cur_font = _main_app.SYSTEM_RUNTIME_CONFIG.get("font_style", "big_bold")

            targets_payload = []
            for b in target_boxes:
                targets_payload.append({
                    "acc_id": b["acc_id"],
                    "thread_id": str(b["id"]),
                    "type": "group",
                    "platform": b.get("platform") or "zalo",
                    "mentions": [],
                    "tag_all": bool(fn_meta.get("tag_all", False)),
                })

            tid = _main_app.start_task_programmatic(
                targets=targets_payload,
                blocks=blocks,
                delay=cur_delay,
                use_emoji=False,
                icon_count=0,
                mode=mode if mode != "special_chan" else "treo_nhay",
                color_mode=fn_meta.get("color_mode", "word_rainbow"),
                fixed_color=fn_meta.get("fixed_color", "red"),
                is_heading=True,
                antiband=True,
                strip_line_num=True,
                hide_tag_all=bool(fn_meta.get("hide_tag_all", True)),
                hide_tag_name=bool(fn_meta.get("hide_tag_name", True)),
                font_style=cur_font,
            )

            cap = self.build_tabbed_caption(
                user_id=user_id,
                active_tab="func",
                page=1,
                extra_notice=(
                    f"✅ <b>ĐÃ KHỞI CHẠY {fn_meta['label'].upper()}!</b>\n"
                    f"• Mã Task: <code>#{tid}</code> • Số Box: <b>{len(targets_payload)}</b>\n"
                    f"• Kịch bản: <code>{file_name if not custom_text else 'Tự nhập'}</code> ({len(blocks)} câu)\n"
                    f"• Màu chữ: <b>{'Đỏ Rực' if fn_meta.get('color_mode') == 'fixed' else 'Đổi Từng Màu (0% Trắng)'}</b>"
                ),
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=self.build_tabbed_keyboard("func", 1))
        except Exception as e:
            self.send_text(chat_id, f"❌ Lỗi khởi chạy chiến dịch: <code>{str(e)[:200]}</code>")

    # KIỂM TRA & TỰ ĐỘNG CỨU SỐNG COOKIE ZALO
    def handle_check_all_stored_zalo_cookies(self, chat_id, reply_to=None):
        wait_res = self.send_text(
            chat_id,
            "🔍 <b>Đang kiểm tra trạng thái Live/Die & tự động làm mới khóa phiên cho toàn bộ tài khoản Zalo...</b>",
            reply_to=reply_to,
        )
        wait_mid = (wait_res.get("result") or {}).get("message_id")
        try:
            conn = _open_db()
            rows = conn.execute(
                "SELECT id, name, uid, imei, cookies, user_agent FROM accounts WHERE platform='zalo'"
            ).fetchall()
            conn.close()
        except Exception as e:
            self.delete_msg(chat_id, wait_mid)
            self.send_text(chat_id, f"❌ Lỗi truy vấn DB: <code>{e}</code>", reply_to=reply_to)
            return

        if not rows:
            self.delete_msg(chat_id, wait_mid)
            self.send_text(
                chat_id,
                "📭 <b>Chưa có tài khoản Zalo nào trong hệ thống!</b>\n"
                "👉 Hãy bấm <b>📲 Quét QR Zalo PC</b> trong tab <b>Quản Lý</b> để đăng nhập.",
                reply_to=reply_to,
            )
            return

        lines = [f"📊 <b>KẾT QUẢ KIỂM TRA {len(rows)} TÀI KHOẢN ZALO:</b>\n"]
        live_cnt = 0
        healed_cnt = 0
        for r in rows:
            acc_id, name, uid, imei, ck_raw, ua = r
            chk = check_zalo_cookie_imei_live(ck_raw, imei, user_agent=ua or "")
            if chk.get("alive"):
                live_cnt += 1
                if chk.get("refreshed_cookies") or chk.get("secret_key"):
                    healed_cnt += 1
                    sync_zalo_account_to_web_db(
                        chk.get("uid") or uid,
                        chk.get("name") or name,
                        imei,
                        chk.get("refreshed_cookies") or parse_cookies_input_flexible(ck_raw),
                        zpw_enk=chk.get("secret_key") or "",
                        user_agent=ua or "",
                    )
                st_badge = "🟢 <b>LIVE (Đã làm mới zpw_sek)</b>" if chk.get("refreshed_cookies") else "🟢 <b>LIVE KHỎE</b>"
                lines.append(
                    f"• <b>#{acc_id} {chk.get('name') or name}</b> (UID: <code>{chk.get('uid') or uid}</code>)\n"
                    f"  └ Trạng thái: {st_badge}"
                )
            else:
                lines.append(
                    f"• <b>#{acc_id} {name}</b> (UID: <code>{uid}</code>)\n"
                    f"  └ Trạng thái: 🔴 <b>DIE</b> (<i>{chk.get('reason') or 'Hết hạn phiên'}</i>)"
                )

        lines.append(
            f"\n✅ Tổng kết: <b>{live_cnt}/{len(rows)} Acc LIVE</b> (Tự động cứu sống: <b>{healed_cnt}</b> Acc)."
        )
        self.delete_msg(chat_id, wait_mid)
        self.send_text(chat_id, "\n".join(lines), reply_to=reply_to)

    # QUÉT QR ZALO PC TRỰC TIẾP TRÊN TELEGRAM (SỐNG TRONG ACC 24/7)
    def handle_zalo_qr_command(self, chat_id, user_id, msg_id=None, region_code="sg_vip", custom_pc_name=""):
        if user_id in self.active_qr_locks:
            self.send_text(
                chat_id,
                "⏳ <b>Bạn đang có 1 phiên tạo mã QR đang chờ quét!</b> Vui lòng quét mã QR hiện tại hoặc đợi hết hạn.",
                reply_to=msg_id,
            )
            return

        self.active_qr_locks.add(user_id)

        def _qr_worker():
            wait_msg_id = None
            qr_msg_id = None
            qr_file_path = None
            try:
                w_res = self.send_text(
                    chat_id,
                    "⏳ <b>Đang khởi tạo mã QR Zalo PC chuẩn (zalo.me/pc -> chat.zalo.me)...</b>",
                    reply_to=msg_id,
                )
                if w_res.get("ok") and w_res.get("result"):
                    wait_msg_id = w_res["result"].get("message_id")

                import asyncio

                async def qr_callback(event):
                    nonlocal wait_msg_id, qr_msg_id
                    ev_type = event.get("type")
                    data = event.get("data") or {}

                    if ev_type == LoginQRCallbackEventType.QRCodeGenerated:
                        b64_img = data.get("image") or ""
                        if b64_img.startswith("data:image"):
                            b64_img = b64_img.split(",", 1)[-1]
                        raw_png = base64.b64decode(b64_img)
                        bordered_png = add_border_to_qr(raw_png)

                        if wait_msg_id:
                            self.delete_msg(chat_id, wait_msg_id)
                            wait_msg_id = None

                        caption = (
                            "📲 <b>MÃ QR ĐĂNG NHẬP ZALO PC</b>\n"
                            "────────────────────\n"
                            "1️⃣ Mở ứng dụng <b>Zalo</b> trên điện thoại.\n"
                            "2️⃣ Quét mã QR bên trên và bấm <b>Đăng nhập</b>.\n"
                            "⏱️ <i>Mã có hiệu lực trong 100 giây. Sau khi quét, máy chủ sẽ tự động nạp Cookie + IMEI và sống trực tiếp trong Acc Zalo 24/7!</i>"
                        )
                        p_res = self.send_photo_bytes(chat_id, bordered_png, caption=caption, reply_to=msg_id)
                        if p_res.get("ok") and p_res.get("result"):
                            qr_msg_id = p_res["result"].get("message_id")

                    elif ev_type == LoginQRCallbackEventType.QRCodeScanned:
                        dname = data.get("display_name") or "Zalo User"
                        self.send_text(
                            chat_id,
                            f"📱 <b>Đã nhận diện quét QR bởi: {dname}!</b>\n👉 Vui lòng bấm <b>Xác nhận đăng nhập</b> trên màn hình điện thoại của bạn...",
                            reply_to=qr_msg_id or msg_id,
                        )

                    elif ev_type == LoginQRCallbackEventType.QRCodeExpired:
                        if qr_msg_id:
                            self.delete_msg(chat_id, qr_msg_id)
                        self.send_text(
                            chat_id,
                            "⌛ <b>Mã QR Zalo đã hết hạn!</b> Bấm <b>📲 Quét QR Zalo PC</b> hoặc gõ <code>/qr</code> để lấy mã mới.",
                            reply_to=msg_id,
                        )

                    elif ev_type == LoginQRCallbackEventType.QRCodeDeclined:
                        if qr_msg_id:
                            self.delete_msg(chat_id, qr_msg_id)
                        self.send_text(
                            chat_id,
                            "❌ <b>Bạn đã từ chối xác nhận đăng nhập trên điện thoại.</b>",
                            reply_to=msg_id,
                        )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(login_qr_with_unique_imei(callback=qr_callback))
                finally:
                    loop.close()

                if not result:
                    return

                cookies = result.get("cookies") or {}
                imei = result.get("imei") or ""
                uinfo = result.get("user_info") or {}
                uid = str(uinfo.get("uid") or uinfo.get("id") or "")
                dname = uinfo.get("name") or uinfo.get("display_name") or f"Zalo_{uid[-4:]}"
                ua = result.get("user_agent") or ""
                zpw_enk = result.get("secret_key") or ""

                qr_file_path = f"qr_{imei}.png"

                acc_id = sync_zalo_account_to_web_db(
                    uid=uid,
                    display_name=dname,
                    imei=imei,
                    cookies_dict=cookies,
                    zpw_enk=zpw_enk,
                    user_agent=ua,
                )
                try:
                    ZaloPCSessionKeeper.register_session(
                        uid=uid or imei,
                        imei=imei,
                        cookies_dict=cookies,
                        user_agent=ua,
                        secret_key=zpw_enk,
                    )
                except Exception:
                    pass

                if qr_msg_id:
                    self.delete_msg(chat_id, qr_msg_id)

                cookies_str = json.dumps(cookies, ensure_ascii=False)
                msg_success = (
                    f"✅ <b>ĐĂNG NHẬP & SỐNG TRONG ACC ZALO THÀNH CÔNG!</b>\n"
                    f"────────────────────\n"
                    f"👤 Tên tài khoản: <b>{dname}</b>\n"
                    f"🆔 UID Zalo: <code>{uid}</code> (Mã Acc: <b>#{acc_id}</b>)\n"
                    f"🔑 Khóa AES (zpw_enk): <b>{'Đã nạp chuẩn 100%' if zpw_enk else 'Tự động đồng bộ'}</b>\n"
                    f"📡 Trạng thái: <b>🟢 Đang duy trì kết nối sống 24/7 trong Acc & lắng nghe lệnh đa nhóm</b>\n\n"
                    f"📱 <b>IMEI:</b>\n<pre>{imei}</pre>\n\n"
                    f"🍪 <b>Cookies:</b>\n<pre>{cookies_str[:3200]}</pre>"
                )
                self.send_text(chat_id, msg_success, reply_to=msg_id)

            except Exception as e:
                if wait_msg_id:
                    self.delete_msg(chat_id, wait_msg_id)
                self.send_text(
                    chat_id,
                    f"❌ <b>Lỗi khi tạo phiên QR Zalo:</b> <code>{str(e)[:300]}</code>",
                    reply_to=msg_id,
                )
            finally:
                self.active_qr_locks.discard(user_id)
                if qr_file_path and os.path.exists(qr_file_path):
                    try:
                        os.remove(qr_file_path)
                    except Exception:
                        pass

        self.executor.submit(_qr_worker)

    # XỬ LÝ NÚT BẤM INLINE TRÊN TELEGRAM BOT
    def process_callback_query(self, cb):
        cb_id = cb.get("id")
        from_u = cb.get("from") or {}
        user_id = from_u.get("id")
        first_name = from_u.get("first_name") or from_u.get("username") or "Anh"
        msg = cb.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        msg_id = msg.get("message_id")
        data = (cb.get("data") or "").strip()

        if not chat_id or not data:
            return

        # KIỂM TRA QUYỀN NGHIÊM NGẶT (CHẶN 100% NGƯỜI LẠ HOẶC ID ĐÃ BỊ XOÁ)
        if not is_telegram_user_authorized(user_id, first_name):
            self.answer_callback(cb_id, "⛔ Bạn không có quyền sử dụng bot này!", show_alert=True)
            self.send_text(
                chat_id,
                f"⛔ <b>Bạn không có quyền sử dụng bot này.</b>\n"
                f"🆔 ID của bạn: <code>{user_id}</code>\n"
                f"👤 Liên hệ Admin để cấp quyền: <a href=\"tg://user?id={ROOT_ADMIN_ID}\">Bấm vào đây ↗️</a>",
            )
            return

        if data == "noop":
            self.answer_callback(cb_id)
            return

        # Chuyển đổi giữa 3 Tab chính & phân trang 1..4
        if data.startswith("tab_func_"):
            page = int(data.split("_")[-1] or 1)
            self.answer_callback(cb_id, f"Chức năng - Trang {page}/4")
            cap = self.build_tabbed_caption(first_name, user_id, active_tab="func", page=page)
            kb = self.build_tabbed_keyboard(active_tab="func", page=page)
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=kb)
            return

        if data == "tab_mgmt":
            self.answer_callback(cb_id, "Mở Tab Quản Lý")
            cap = self.build_tabbed_caption(first_name, user_id, active_tab="mgmt")
            kb = self.build_tabbed_keyboard(active_tab="mgmt")
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=kb)
            return

        if data == "tab_util":
            self.answer_callback(cb_id, "Mở Tab Tiện Ích")
            cap = self.build_tabbed_caption(first_name, user_id, active_tab="util")
            kb = self.build_tabbed_keyboard(active_tab="util")
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=kb)
            return

        # Chọn 1 trong 32 chức năng
        if data.startswith("pickfn:"):
            fn_id = data.split(":", 1)[1]
            self.answer_callback(cb_id, "Đang mở cấu hình chức năng...")
            self.render_function_wizard(chat_id, msg_id, user_id, fn_id)
            return

        if data.startswith("runfn:"):
            fn_id = data.split(":", 1)[1]
            self.answer_callback(cb_id, "🚀 Đang khởi chạy chiến dịch...")
            self.launch_wizard_campaign(chat_id, msg_id, user_id, fn_id)
            return

        if data.startswith("wiz_setfile:"):
            parts = data.split(":", 2)
            fn_id, file_s = parts[1], parts[2]
            wiz = self.wizard_selections.setdefault(user_id, {})
            wiz["file_name"] = file_s
            wiz["custom_text"] = ""
            self.answer_callback(cb_id, f"Đã chọn file {file_s}")
            self.render_function_wizard(chat_id, msg_id, user_id, fn_id)
            return

        if data.startswith("wiz_pickbox:"):
            fn_id = data.split(":", 1)[1]
            self.answer_callback(cb_id, "Chọn Box mục tiêu")
            boxes = self._discover_all_boxes()
            rows = [[{"text": "📦 Tất Cả Các Box (All)", "callback_data": f"wiz_setbox:{fn_id}:ALL"}]]
            for b in boxes[:14]:
                b_label = f"💬 {b['name'][:26]} ({b['id'][-4:]})"
                rows.append([{"text": b_label, "callback_data": f"wiz_setbox:{fn_id}:{b['id']}"}])
            rows.append([{"text": "✍️ Nhập ID Box Thủ Công", "callback_data": f"wiz_manualbox:{fn_id}"}])
            rows.append([{"text": "🔙 Quay lại", "callback_data": f"pickfn:{fn_id}"}])
            cap = (
                f"📦 <b>CHỌN BOX MỤC TIÊU ({len(boxes)} Box hiện có)</b>\n"
                "────────────────────\n"
                "• Bấm vào 1 nhóm bên dưới hoặc chọn <b>Tất Cả Các Box</b>:"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup={"inline_keyboard": rows})
            return

        if data.startswith("wiz_setbox:"):
            _, fn_id, bid = data.split(":", 2)
            wiz = self.wizard_selections.setdefault(user_id, {})
            wiz["box_id"] = bid
            if bid == "ALL":
                wiz["box_name"] = "Tất Cả Các Box (All)"
            else:
                boxes = self._discover_all_boxes()
                matched = next((x for x in boxes if str(x["id"]) == str(bid)), None)
                wiz["box_name"] = matched["name"] if matched else f"Box {bid}"
            self.answer_callback(cb_id, f"Đã chọn: {wiz['box_name'][:24]}")
            self.render_function_wizard(chat_id, msg_id, user_id, fn_id)
            return

        if data.startswith("wiz_manualbox:"):
            fn_id = data.split(":", 1)[1]
            self.user_states[user_id] = {"mode": "wiz_input_box", "fn_id": fn_id, "menu_msg_id": msg_id}
            self.answer_callback(cb_id)
            self.send_text(
                chat_id,
                "✍️ <b>Hãy gửi ID Box (nhóm Zalo / kênh Discord) mà bạn muốn nhắm tới:</b>",
                reply_to=msg_id,
            )
            return

        if data.startswith("wiz_customtxt:"):
            fn_id = data.split(":", 1)[1]
            self.user_states[user_id] = {"mode": "wiz_input_text", "fn_id": fn_id, "menu_msg_id": msg_id}
            self.answer_callback(cb_id)
            self.send_text(
                chat_id,
                "✍️ <b>Hãy gửi nội dung muốn treo/nhây (kèm <code>@Tên</code> hoặc <code>@All</code> nếu muốn tag):</b>",
                reply_to=msg_id,
            )
            return

        if data == "fn_stop_all_quick":
            try:
                import app as _main_app
                stopped = _main_app.stop_tasks_for_thread(None)
            except Exception:
                stopped = 0
            self.answer_callback(cb_id, f"🛑 Đã dừng {stopped} chiến dịch!", show_alert=True)
            cap = self.build_tabbed_caption(
                first_name, user_id, active_tab="func", page=1,
                extra_notice=f"🛑 <b>Đã dừng tất cả ({stopped} chiến dịch)!</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 1))
            return

        # Cài đặt nhanh Delay / Màu chữ / Font / Anti-Ban
        if data.startswith("setdelay:"):
            d_val = float(data.split(":", 1)[1])
            try:
                import app as _main_app
                with _main_app.SYSTEM_CFG_LOCK:
                    _main_app.SYSTEM_RUNTIME_CONFIG["delay"] = d_val
                _main_app.update_running_tasks_config(thread_id=None, delay=d_val)
            except Exception:
                pass
            self.answer_callback(cb_id, f"⏱️ Đã chỉnh Delay = {d_val}s!", show_alert=True)
            cap = self.build_tabbed_caption(
                first_name, user_id, active_tab="func", page=4,
                extra_notice=f"✅ <b>Đã cập nhật tốc độ Delay = {d_val}s trên toàn hệ thống!</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4))
            return

        if data.startswith("setcolor:"):
            _, c_mode, f_col = data.split(":", 2)
            try:
                import app as _main_app
                with _main_app.SYSTEM_CFG_LOCK:
                    _main_app.SYSTEM_RUNTIME_CONFIG["color_mode"] = c_mode
                    _main_app.SYSTEM_RUNTIME_CONFIG["fixed_color"] = f_col
                _main_app.update_running_tasks_config(thread_id=None, color_mode=c_mode, fixed_color=f_col)
            except Exception:
                pass
            label_c = "Đổi Từng Màu (0% Trắng)" if c_mode == "word_rainbow" else f"Màu {f_col.upper()}"
            self.answer_callback(cb_id, f"🎨 Đã bật: {label_c}!", show_alert=True)
            cap = self.build_tabbed_caption(
                first_name, user_id, active_tab="func", page=4,
                extra_notice=f"🎨 <b>Đã kích hoạt chế độ màu: {label_c}!</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4))
            return

        if data.startswith("setfont:"):
            f_style = data.split(":", 1)[1]
            try:
                import app as _main_app
                with _main_app.SYSTEM_CFG_LOCK:
                    _main_app.SYSTEM_RUNTIME_CONFIG["font_style"] = f_style
                _main_app.update_running_tasks_config(thread_id=None, font_style=f_style)
            except Exception:
                pass
            self.answer_callback(cb_id, f"🔤 Đã đổi kiểu chữ: {f_style}!", show_alert=True)
            cap = self.build_tabbed_caption(
                first_name, user_id, active_tab="func", page=4,
                extra_notice=f"🔤 <b>Đã cập nhật kiểu chữ: {f_style}!</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4))
            return

        if data.startswith("setanti:"):
            anti_on = data.split(":", 1)[1] == "1"
            try:
                import app as _main_app
                with _main_app.SYSTEM_CFG_LOCK:
                    _main_app.SYSTEM_RUNTIME_CONFIG["antiband"] = anti_on
            except Exception:
                pass
            st_lbl = "BẬT (Chống Zalo Cấm Chat Box)" if anti_on else "TẮT (Xả thẳng)"
            self.answer_callback(cb_id, f"🛡️ Anti-Ban Box: {st_lbl}", show_alert=True)
            cap = self.build_tabbed_caption(
                first_name, user_id, active_tab="func", page=4,
                extra_notice=f"🛡️ <b>Trạng thái Anti Cấm Chat Box: {st_lbl}</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4))
            return

        # QUẢN LÝ THÊM / XOÁ / XEM ID NGƯỜI DÙNG ĐƯỢC PHÉP SÀI BOT
        if data == "mgmt_add_id":
            if not is_root_admin(user_id):
                self.answer_callback(cb_id, "⛔ Chỉ Admin chính (8827605973) mới có quyền thêm ID!", show_alert=True)
                return
            self.user_states[user_id] = {"mode": "add_user_id", "menu_msg_id": msg_id}
            self.answer_callback(cb_id, "Nhập ID người dùng cần cấp quyền")
            self.send_text(
                chat_id,
                "➕ <b>THÊM ID NGƯỜI DÙNG ĐƯỢC PHÉP SÀI BOT</b>\n"
                "────────────────────\n"
                "• Hãy gửi <b>ID Telegram / Zalo</b> kèm tên (tùy chọn) theo cú pháp:\n"
                "  <code>123456789 Tên Người Dùng</code>\n"
                "• Hoặc gửi nhiều ID (mỗi dòng 1 ID) để cấp quyền hàng loạt!",
                reply_to=msg_id,
            )
            return

        if data == "mgmt_del_id_menu":
            if not is_root_admin(user_id):
                self.answer_callback(cb_id, "⛔ Chỉ Admin chính (8827605973) mới có quyền xoá ID!", show_alert=True)
                return
            self.answer_callback(cb_id, "Chọn ID cần xoá quyền sài Bot")
            self._render_delete_user_id_menu(chat_id, msg_id)
            return

        if data.startswith("del_uid_now:"):
            if not is_root_admin(user_id):
                self.answer_callback(cb_id, "⛔ Chỉ Admin chính mới có quyền xoá ID!", show_alert=True)
                return
            target_uid = data.split(":", 1)[1].strip()
            if target_uid == ROOT_ADMIN_ID:
                self.answer_callback(cb_id, "Không thể xoá Admin gốc!", show_alert=True)
                return
            revoke_telegram_permission(target_uid)
            self.answer_callback(cb_id, f"🗑️ Đã xoá quyền sài Bot của ID {target_uid}!", show_alert=True)
            self._render_delete_user_id_menu(
                chat_id, msg_id,
                notice=f"✅ <b>Đã xoá hoàn toàn quyền sử dụng Bot của ID <code>{target_uid}</code>!</b>"
            )
            return

        if data == "del_all_sub_uids":
            if not is_root_admin(user_id):
                self.answer_callback(cb_id, "⛔ Chỉ Admin chính mới có quyền này!", show_alert=True)
                return
            cnt = clear_all_secondary_permissions()
            self.answer_callback(cb_id, f"🗑️ Đã xoá sạch {cnt} ID phụ!", show_alert=True)
            self._render_delete_user_id_menu(
                chat_id, msg_id,
                notice=f"✅ <b>Đã thu hồi quyền của toàn bộ {cnt} ID phụ! Chỉ còn Admin gốc ({ROOT_ADMIN_ID}) được dùng Bot.</b>"
            )
            return

        if data == "mgmt_list_ids":
            self.answer_callback(cb_id, "Danh sách ID được phép sài Bot")
            perms = list_telegram_permissions()
            lines = ["📋 <b>DANH SÁCH ID ĐƯỢC PHÉP SỬ DỤNG BOT:</b>\n────────────────────"]
            for idx, p in enumerate(perms, 1):
                badge = "👑 <b>Admin Gốc</b>" if p.get("is_root") else "🥷 <b>Thành Viên VIP</b>"
                lines.append(f"{idx}. {badge}: <b>{p['name']}</b> — ID: <code>{p['uid']}</code>")
            lines.append("\n🔒 <i>Tất cả người dùng ngoài danh sách này đều bị chặn 100%!</i>")
            kb = {
                "inline_keyboard": [
                    [
                        {"text": "➕ Thêm ID Mới", "callback_data": "mgmt_add_id"},
                        {"text": "➖ Xoá ID Người Dùng", "callback_data": "mgmt_del_id_menu"},
                    ],
                    [{"text": "🔙 Quay lại Quản Lý", "callback_data": "tab_mgmt"}],
                ]
            }
            self.edit_menu_message(chat_id, msg_id, "\n".join(lines), reply_markup=kb)
            return

        if data == "mgmt_acc_files":
            self.answer_callback(cb_id, "Mở quản lý Acc & Kho File")
            self._render_accounts_and_files_menu(chat_id, msg_id)
            return

        if data.startswith("del_acc_now:"):
            acc_id = int(data.split(":", 1)[1])
            try:
                conn = _open_db()
                conn.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
                conn.commit()
                conn.close()
                import app as _main_app
                if hasattr(_main_app, "reload_accounts_to_ram"):
                    _main_app.reload_accounts_to_ram()
            except Exception:
                pass
            self.answer_callback(cb_id, f"🗑️ Đã xoá tài khoản #{acc_id}!", show_alert=True)
            self._render_accounts_and_files_menu(chat_id, msg_id, notice=f"✅ Đã xoá tài khoản <b>#{acc_id}</b>!")
            return

        if data == "cmd_qr_sg":
            self.answer_callback(cb_id, "Đang tạo mã QR Zalo PC...")
            self.handle_zalo_qr_command(chat_id, user_id, msg_id=msg_id)
            return

        if data == "cmd_checkzalo":
            self.answer_callback(cb_id, "Đang kiểm tra toàn bộ Cookie Zalo...")
            self.executor.submit(self.handle_check_all_stored_zalo_cookies, chat_id, msg_id)
            return

        if data == "cmd_status":
            self.answer_callback(cb_id, "Đang tải trạng thái...")
            self.send_status_report(chat_id, reply_to=msg_id)
            return

        if data == "prx_add_prompt":
            self.user_states[user_id] = {"mode": "input_proxies"}
            self.answer_callback(cb_id)
            self.send_text(
                chat_id,
                "🌐 <b>NẠP PROXY VÀO HỆ THỐNG</b>\n"
                "• Hãy dán danh sách Proxy (<code>ip:port</code> hoặc <code>ip:port:user:pass</code>) hoặc gửi file <code>.txt</code> chứa Proxy vào đây:",
                reply_to=msg_id,
            )
            return

        if data == "prx_test_now":
            self.answer_callback(cb_id, "Đang kiểm tra tốc độ dàn Proxy...")
            try:
                import app as _main_app
                _main_app.ProxyPoolEngine.trigger_background_benchmark()
            except Exception:
                pass
            self.render_function_wizard(chat_id, msg_id, user_id, "fn_proxy")
            return

        if data == "prx_clear_now":
            try:
                import app as _main_app
                _main_app.ProxyPoolEngine.clear_all()
            except Exception:
                pass
            self.answer_callback(cb_id, "🗑️ Đã xoá sạch Proxy Pool!", show_alert=True)
            self.render_function_wizard(chat_id, msg_id, user_id, "fn_proxy")
            return

        if data == "prompt_2fa":
            self.user_states[user_id] = {"mode": "2fa"}
            self.answer_callback(cb_id)
            self.send_text(chat_id, "🔐 <b>Hãy gửi chuỗi Secret Key 2FA của bạn để lấy mã OTP 6 số:</b>", reply_to=msg_id)
            return

        if data == "prompt_ai":
            self.user_states[user_id] = {"mode": "ai"}
            self.answer_callback(cb_id)
            self.send_text(chat_id, "🤖 <b>Hãy nhập câu hỏi cho Trợ lý Meta AI:</b>", reply_to=msg_id)
            return

        if data == "prompt_gettoken":
            self.user_states[user_id] = {"mode": "gettoken"}
            self.answer_callback(cb_id)
            self.send_text(
                chat_id,
                "🎯 <b>Gửi tài khoản Discord theo cú pháp:</b>\n<code>email|password</code> hoặc dán trực tiếp Token Discord vào đây:",
                reply_to=msg_id,
            )
            return

        if data == "prompt_getcookie":
            self.user_states[user_id] = {"mode": "getcookie"}
            self.answer_callback(cb_id)
            self.send_text(
                chat_id,
                "🍪 <b>Gửi tài khoản Facebook theo cú pháp:</b>\n<code>email|password</code> hoặc dán trực tiếp Cookie <code>c_user=...; xs=...</code> vào đây:",
                reply_to=msg_id,
            )
            return

    def _render_delete_user_id_menu(self, chat_id, msg_id, notice=""):
        perms = list_telegram_permissions()
        sub_users = [p for p in perms if not p.get("is_root")]
        rows = []
        for p in sub_users[:16]:
            rows.append([
                {
                    "text": f"🗑️ Xoá ID: {p['name']} ({p['uid']})",
                    "callback_data": f"del_uid_now:{p['uid']}"
                }
            ])
        if sub_users:
            rows.append([{"text": "🔥 Xoá Sạch Tất Cả ID Phụ", "callback_data": "del_all_sub_uids"}])
        rows.append([
            {"text": "➕ Thêm ID Mới", "callback_data": "mgmt_add_id"},
            {"text": "🔙 Quay lại Quản Lý", "callback_data": "tab_mgmt"},
        ])
        notice_str = f"\n{notice}\n" if notice else ""
        if sub_users:
            body = (
                f"➖ <b>XOÁ ID NGƯỜI DÙNG KHỎI BOT ({len(sub_users)} ID phụ)</b>\n"
                f"────────────────────{notice_str}\n"
                "• Bấm vào bất kỳ ID nào bên dưới để <b>xoá ngay lập tức</b> quyền sử dụng Bot của ID đó.\n"
                "• Hoặc gõ lệnh: <code>/delid &lt;ID&gt;</code>"
            )
        else:
            body = (
                f"➖ <b>XOÁ ID NGƯỜI DÙNG KHỎI BOT</b>\n"
                f"────────────────────{notice_str}\n"
                f"🔒 Hiện tại <b>chỉ có duy nhất Admin gốc (<code>{ROOT_ADMIN_ID}</code>)</b> có quyền sử dụng Bot (chưa có ID phụ nào)."
            )
        self.edit_menu_message(chat_id, msg_id, body, reply_markup={"inline_keyboard": rows})

    def _render_accounts_and_files_menu(self, chat_id, msg_id, notice=""):
        accs = []
        try:
            conn = _open_db()
            accs = conn.execute("SELECT id, name, platform, uid FROM accounts ORDER BY id DESC").fetchall()
            conn.close()
        except Exception:
            pass
        files = self._get_available_txt_files()
        rows = []
        for a in accs[:10]:
            aid, aname, aplat, auid = a
            rows.append([
                {
                    "text": f"🗑️ Xoá Acc #{aid}: [{str(aplat).upper()}] {aname}",
                    "callback_data": f"del_acc_now:{aid}"
                }
            ])
        rows.append([
            {"text": "📲 Quét QR Thêm Acc Zalo", "callback_data": "cmd_qr_sg"},
            {"text": "🔙 Quay lại Quản Lý", "callback_data": "tab_mgmt"},
        ])
        f_names = ", ".join(f"<code>{x['filename']}</code>" for x in files[:10]) or "Chưa có file"
        notice_s = f"\n{notice}\n" if notice else ""
        cap = (
            f"🗂️ <b>QUẢN LÝ TÀI KHOẢN ({len(accs)}) & KHO FILE ({len(files)})</b>\n"
            f"────────────────────{notice_s}\n"
            f"📄 <b>Kho file .txt sẵn sàng:</b> {f_names}\n"
            f"💡 <i>Mẹo: Bạn có thể gửi trực tiếp bất kỳ file <code>.txt</code> nào vào khung chat Bot này để nạp thêm vào kho kịch bản!</i>\n\n"
            f"👇 Bấm vào tài khoản bên dưới nếu muốn xoá khỏi hệ thống:"
        )
        self.edit_menu_message(chat_id, msg_id, cap, reply_markup={"inline_keyboard": rows})

    def send_status_report(self, chat_id, reply_to=None):
        try:
            conn = _open_db()
            accs = conn.execute("SELECT id, name, platform, uid, enabled FROM accounts").fetchall()
            conn.close()
        except Exception:
            accs = []

        acc_cnt, running_cnt, color_label, delay_val = self._get_live_runtime_summary()
        perms = list_telegram_permissions()
        lines = [
            "📊 <b>TRẠNG THÁI HỆ THỐNG BOT TREO 4APP 🇻🇳</b>",
            "────────────────────",
            f"👑 Admin Gốc: <code>{ROOT_ADMIN_ID}</code>",
            f"🔐 Số ID được phép dùng Bot: <b>{len(perms)} ID</b> (Chặn 100% người lạ)",
            f"📡 Tài khoản đang kết nối: <b>{len(accs)} Acc</b>",
            f"🚀 Chiến dịch đang chạy: <b>{running_cnt} luồng</b>",
            f"🎨 Chế độ màu chữ: <b>{color_label} (0% Chữ Trắng)</b> • Delay: <b>{delay_val}s</b>",
            "🛡️ Anti Cấm Chat Box Zalo: <b>ĐANG BẬT (Typing Pulse + Box Pacing)</b>",
            "",
        ]
        if accs:
            lines.append("<b>Danh sách Tài khoản:</b>")
            for a in accs[:15]:
                st = "🟢" if a[4] else "⚪"
                lines.append(f"• {st} <b>#{a[0]} [{str(a[2]).upper()}] {a[1]}</b> (<code>{a[3] or '-'}</code>)")
        else:
            lines.append("• <i>Chưa có tài khoản nào. Gõ /qr để quét mã QR Zalo PC!</i>")
        self.send_text(chat_id, "\n".join(lines), reply_to=reply_to)

    def handle_interactive_state(self, chat_id, user_id, text, msg_id):
        st = self.user_states.get(user_id)
        if not st:
            return False
        mode = st.get("mode")

        if mode == "add_user_id":
            self.user_states.pop(user_id, None)
            if not is_root_admin(user_id):
                self.send_text(chat_id, "⛔ Chỉ Admin gốc mới có quyền thêm ID!", reply_to=msg_id)
                return True
            added_list = []
            for ln in text.splitlines():
                ln_s = ln.strip()
                if not ln_s:
                    continue
                parts = ln_s.split(None, 1)
                uid_cand = parts[0].strip()
                name_cand = parts[1].strip() if len(parts) > 1 else f"VIP_{uid_cand[-4:]}"
                if grant_telegram_permission(uid_cand, name_cand):
                    added_list.append(f"<code>{uid_cand}</code> ({name_cand})")
            if added_list:
                self.send_text(
                    chat_id,
                    f"✅ <b>ĐÃ THÊM QUYỀN SỬ DỤNG BOT CHO {len(added_list)} ID:</b>\n• " + "\n• ".join(added_list),
                    reply_to=msg_id,
                )
            else:
                self.send_text(chat_id, "⚠️ ID không hợp lệ. Vui lòng thử lại!", reply_to=msg_id)
            return True

        if mode == "wiz_input_box":
            self.user_states.pop(user_id, None)
            fn_id = st.get("fn_id") or "fn_treo_nhay"
            bid = text.strip()
            wiz = self.wizard_selections.setdefault(user_id, {})
            wiz["box_id"] = bid
            wiz["box_name"] = f"Box {bid}"
            self.send_text(chat_id, f"✅ Đã chọn Box mục tiêu: <code>{bid}</code>! Đang mở lại bảng cấu hình...", reply_to=msg_id)
            self.render_function_wizard(chat_id, st.get("menu_msg_id") or msg_id, user_id, fn_id)
            return True

        if mode == "wiz_input_text":
            self.user_states.pop(user_id, None)
            fn_id = st.get("fn_id") or "fn_treo_nhay"
            wiz = self.wizard_selections.setdefault(user_id, {})
            wiz["custom_text"] = text.strip()
            self.send_text(chat_id, "✅ Đã lưu nội dung tự chọn! Bấm <b>🚀 BẮT ĐẦU CHẠY</b> trên bảng điều khiển để phang ngay.", reply_to=msg_id)
            if st.get("menu_msg_id"):
                self.render_function_wizard(chat_id, st["menu_msg_id"], user_id, fn_id)
            return True

        if mode == "input_proxies":
            self.user_states.pop(user_id, None)
            try:
                import app as _main_app
                added, total = _main_app.ProxyPoolEngine.add_proxies_incremental(text, auto_start=True)
                self.send_text(chat_id, f"✅ Đã nạp thêm <b>{added} Proxy</b> (Tổng: <b>{total} Proxy</b>) và tự động đo tốc độ Ping!", reply_to=msg_id)
            except Exception as e:
                self.send_text(chat_id, f"❌ Lỗi nạp Proxy: <code>{e}</code>", reply_to=msg_id)
            return True

        if mode == "2fa":
            self.user_states.pop(user_id, None)
            code, rem = generate_totp_local(text)
            if code:
                self.send_text(chat_id, f"🔐 Mã 2FA OTP: <code>{code}</code> (Còn hiệu lực: {rem}s)", reply_to=msg_id)
            else:
                self.send_text(chat_id, "❌ Chuỗi Secret 2FA không hợp lệ!", reply_to=msg_id)
            return True

        if mode == "ai":
            self.user_states.pop(user_id, None)
            ans = MetaAIAssistant().ask(text)
            self.send_text(chat_id, f"🤖 <b>Meta AI:</b>\n{ans}", reply_to=msg_id)
            return True

        if mode == "gettoken":
            self.user_states.pop(user_id, None)
            if "|" in text:
                parts = [p.strip() for p in text.split("|")]
                res = DiscordTokenGetter().login_discord(parts[0], parts[1], parts[2] if len(parts) > 2 else "")
                if res.get("status") == "SUCCESS":
                    tok = res["token"]
                    sync_and_keepalive_tokens_to_db(tok)
                    self.send_text(chat_id, f"✅ <b>Lấy Token Discord thành công & đã nạp vào Bot:</b>\n<pre>{tok}</pre>", reply_to=msg_id)
                else:
                    self.send_text(chat_id, f"❌ {res.get('message')}", reply_to=msg_id)
            else:
                saved = sync_and_keepalive_tokens_to_db(text)
                if saved:
                    self.send_text(chat_id, f"✅ Đã nạp <b>{len(saved)} Token Discord</b> vào hệ thống!", reply_to=msg_id)
                else:
                    self.send_text(chat_id, "⚠️ Không tìm thấy Token hợp lệ!", reply_to=msg_id)
            return True

        if mode == "getcookie":
            self.user_states.pop(user_id, None)
            if "c_user=" in text and "xs=" in text:
                saved = sync_and_keepalive_tokens_to_db(text)
                self.send_text(chat_id, f"✅ Đã lưu Cookie Messenger/FB ({len(saved)} Acc) vào hệ thống!", reply_to=msg_id)
            elif "|" in text:
                parts = [p.strip() for p in text.split("|")]
                res = FacebookCookieGetter().login_facebook(parts[0], parts[1], parts[2] if len(parts) > 2 else "")
                if res.get("status") == "SUCCESS":
                    sync_and_keepalive_tokens_to_db(res["cookies"])
                    self.send_text(chat_id, f"✅ <b>Lấy Cookie FB thành công:</b>\n<pre>{res['cookies']}</pre>", reply_to=msg_id)
                else:
                    self.send_text(chat_id, f"❌ {res.get('message')}", reply_to=msg_id)
            else:
                self.send_text(chat_id, "⚠️ Vui lòng gửi đúng định dạng <code>email|pass</code> hoặc chuỗi Cookie <code>c_user=...; xs=...</code>", reply_to=msg_id)
            return True

        return False

    def _handle_uploaded_document(self, chat_id, user_id, doc_obj, msg_id):
        fname = doc_obj.get("file_name") or "script.txt"
        fid = doc_obj.get("file_id")
        if not fid:
            return
        try:
            f_info = self.api_call("getFile", {"file_id": fid}, timeout=10)
            fpath = (f_info.get("result") or {}).get("file_path")
            if not fpath:
                return
            dl_url = f"https://api.telegram.org/file/bot{self.token}/{fpath}"
            raw_bytes = self.session.get(dl_url, timeout=20).content
            up_dir = os.path.join(BASE_DIR, "uploads")
            os.makedirs(up_dir, exist_ok=True)
            safe_fn = re.sub(r"[^a-zA-Z0-9_.\-]", "_", fname)
            if not safe_fn.endswith(".txt"):
                safe_fn += ".txt"
            dest = os.path.join(up_dir, safe_fn)
            with open(dest, "wb") as f:
                f.write(raw_bytes)
            lines_cnt = len(raw_bytes.decode("utf-8", errors="ignore").splitlines())
            self.send_text(
                chat_id,
                f"✅ <b>Đã nạp file kịch bản <code>{safe_fn}</code> ({lines_cnt} dòng) vào Kho File!</b>\n"
                f"👉 Mở <code>/menu</code> để chọn file này và chạy ngay.",
                reply_to=msg_id,
            )
        except Exception as e:
            self.send_text(chat_id, f"❌ Lỗi tải file: <code>{e}</code>", reply_to=msg_id)

    def process_update(self, upd):
        if "callback_query" in upd:
            self.process_callback_query(upd["callback_query"])
            return

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return

        chat_id = (msg.get("chat") or {}).get("id")
        from_u = msg.get("from") or {}
        user_id = from_u.get("id")
        first_name = from_u.get("first_name") or from_u.get("username") or "Anh"
        msg_id = msg.get("message_id")
        text = (msg.get("text") or "").strip()

        if not chat_id:
            return

        # KIỂM TRA QUYỀN TRUY CẬP NGHIÊM NGẶT (CHỈ ADMIN 8827605973 VÀ CÁC ID ĐƯỢC THÊM MỚI SÀI ĐƯỢC BOT)
        if not is_telegram_user_authorized(user_id, first_name):
            self.send_text(
                chat_id,
                f"⛔ <b>Bạn không có quyền sử dụng bot này.</b>\n"
                f"🆔 ID của bạn: <code>{user_id}</code>\n"
                f"👤 Liên hệ Admin: <a href=\"tg://user?id={ROOT_ADMIN_ID}\">Bấm vào đây ↗️</a>",
                reply_to=msg_id,
            )
            return

        if "document" in msg:
            self._handle_uploaded_document(chat_id, user_id, msg["document"], msg_id)
            return

        if not text:
            return

        if not text.startswith("/") and self.handle_interactive_state(chat_id, user_id, text, msg_id):
            return

        # Tự động nhận diện nếu người dùng dán trực tiếp Cookie Zalo / Token Discord vào Bot
        if not text.startswith("/") and ("zpw_sek=" in text or "zpsid=" in text or DISCORD_TOKEN_RE.search(text)):
            imei_extracted, ck_dict, meta = parse_imei_and_cookie_from_text(text)
            if ck_dict and ("zpw_sek" in ck_dict or "zpsid" in ck_dict):
                chk = check_zalo_cookie_imei_live(ck_dict, imei_extracted)
                uid = chk.get("uid") or meta.get("uid") or ""
                dname = chk.get("name") or meta.get("name") or f"Zalo_{str(uid)[-4:]}"
                acc_id = sync_zalo_account_to_web_db(
                    uid=uid,
                    display_name=dname,
                    imei=imei_extracted,
                    cookies_dict=chk.get("refreshed_cookies") or ck_dict,
                    zpw_enk=chk.get("secret_key") or meta.get("zpw_enk") or "",
                )
                self.send_text(
                    chat_id,
                    f"✅ <b>Đã nạp trực tiếp tài khoản Zalo #{acc_id}: {dname} (UID: <code>{uid}</code>)!</b>\n"
                    f"• Trạng thái: {'🟢 LIVE KHỎE' if chk.get('alive') else '⚠️ Đã lưu & đang tự động làm mới phiên'}",
                    reply_to=msg_id,
                )
                return
            saved_dc = sync_and_keepalive_tokens_to_db(text)
            if saved_dc:
                self.send_text(chat_id, f"✅ Đã tự động nạp <b>{len(saved_dc)} tài khoản</b> vào Bot!", reply_to=msg_id)
                return

        parts = text.split(None, 1)
        cmd_raw = parts[0].lower().split("@")[0]
        arg_str = parts[1].strip() if len(parts) > 1 else ""

        if cmd_raw in ("/start", "/menu", "/help", "/bot"):
            self.user_states.pop(user_id, None)
            cap = self.build_tabbed_caption(first_name, user_id, active_tab="func", page=1)
            kb = self.build_tabbed_keyboard(active_tab="func", page=1)
            self.send_welcome_video_menu(chat_id, cap, reply_to=msg_id, reply_markup=kb)
            return

        if cmd_raw in ("/qr", "/zaloqr", "/scan"):
            self.handle_zalo_qr_command(chat_id, user_id, msg_id=msg_id)
            return

        if cmd_raw in ("/addid", "/cp", "/them"):
            if not is_root_admin(user_id):
                self.send_text(chat_id, "⛔ Chỉ Admin chính (8827605973) mới có quyền thêm ID người dùng!", reply_to=msg_id)
                return
            if not arg_str:
                self.send_text(
                    chat_id,
                    "➕ <b>Cú pháp thêm ID người dùng:</b>\n<code>/addid &lt;ID_Người_Dùng&gt; [Tên]</code>\nVí dụ: <code>/addid 123456789 Anh Ba</code>",
                    reply_to=msg_id,
                )
                return
            sub_p = arg_str.split(None, 1)
            t_uid = sub_p[0].strip()
            t_name = sub_p[1].strip() if len(sub_p) > 1 else f"VIP_{t_uid[-4:]}"
            grant_telegram_permission(t_uid, t_name)
            self.send_text(
                chat_id,
                f"✅ <b>Đã thêm quyền sử dụng Bot cho ID:</b> <code>{t_uid}</code> (<b>{t_name}</b>)!",
                reply_to=msg_id,
            )
            return

        if cmd_raw in ("/delid", "/xq", "/xoa", "/xoaid"):
            if not is_root_admin(user_id):
                self.send_text(chat_id, "⛔ Chỉ Admin chính (8827605973) mới có quyền xoá ID người dùng!", reply_to=msg_id)
                return
            if not arg_str:
                cap = self.build_tabbed_caption(first_name, user_id, active_tab="mgmt")
                msg_sent = self.send_welcome_video_menu(chat_id, cap, reply_to=msg_id, reply_markup=self.build_tabbed_keyboard("mgmt"))
                mid_new = (msg_sent.get("result") or {}).get("message_id")
                if mid_new:
                    self._render_delete_user_id_menu(chat_id, mid_new)
                return
            t_uid = arg_str.split()[0].strip()
            if t_uid == ROOT_ADMIN_ID:
                self.send_text(chat_id, "⚠️ Không thể xoá Admin gốc!", reply_to=msg_id)
                return
            revoke_telegram_permission(t_uid)
            self.send_text(
                chat_id,
                f"🗑️ <b>Đã xoá hoàn toàn quyền sử dụng Bot của ID:</b> <code>{t_uid}</code>!\n"
                f"🔒 Người dùng mang ID <code>{t_uid}</code> hiện không thể sử dụng bất kỳ lệnh hay nút bấm nào của Bot nữa.",
                reply_to=msg_id,
            )
            return

        if cmd_raw in ("/listid", "/dsq"):
            perms = list_telegram_permissions()
            lines = ["📋 <b>DANH SÁCH ID ĐƯỢC PHÉP SỬ DỤNG BOT:</b>\n────────────────────"]
            for i, p in enumerate(perms, 1):
                role_b = "👑 Admin Gốc" if p.get("is_root") else "🥷 Thành Viên VIP"
                lines.append(f"{i}. {role_b}: <b>{p['name']}</b> — <code>{p['uid']}</code>")
            self.send_text(chat_id, "\n".join(lines), reply_to=msg_id)
            return

        if cmd_raw in ("/checkzalo", "/check"):
            self.executor.submit(self.handle_check_all_stored_zalo_cookies, chat_id, msg_id)
            return

        if cmd_raw in ("/status", "/ping"):
            self.send_status_report(chat_id, reply_to=msg_id)
            return

        if cmd_raw in ("/stopall", "/ta", "/stop"):
            try:
                import app as _main_app
                stopped = _main_app.stop_tasks_for_thread(None)
            except Exception:
                stopped = 0
            self.send_text(chat_id, f"🛑 <b>Đã dừng khẩn cấp toàn bộ ({stopped} chiến dịch)!</b>", reply_to=msg_id)
            return

        # Mặc định hiển thị bảng điều khiển Video
        cap = self.build_tabbed_caption(first_name, user_id, active_tab="func", page=1)
        kb = self.build_tabbed_keyboard(active_tab="func", page=1)
        self.send_welcome_video_menu(chat_id, cap, reply_to=msg_id, reply_markup=kb)

    def _safe_process_update(self, upd):
        try:
            self.process_update(upd)
        except Exception as e:
            self.last_error = str(e)

    def run_forever(self):
        self.running = True
        self.clear_webhook_and_init()
        while self.running:
            try:
                res = self.api_call(
                    "getUpdates",
                    {
                        "offset": self.offset,
                        "timeout": 20,
                        "allowed_updates": ["message", "edited_message", "callback_query"],
                    },
                    timeout=28,
                )
                if res.get("ok") and isinstance(res.get("result"), list):
                    for upd in res["result"]:
                        uid_upd = upd.get("update_id", 0)
                        if uid_upd >= self.offset:
                            self.offset = uid_upd + 1
                        self.executor.submit(self._safe_process_update, upd)
                else:
                    time.sleep(1.5)
            except Exception as e:
                self.last_error = str(e)
                time.sleep(2.0)


_BOT_INSTANCE = None
_BOT_LOCK = threading.RLock()


def start_background_telegram_bot(token=TELEGRAM_BOT_TOKEN, force_restart=False):
    global _BOT_INSTANCE
    with _BOT_LOCK:
        if _BOT_INSTANCE is not None and _BOT_INSTANCE.running and not force_restart:
            return _BOT_INSTANCE
        if _BOT_INSTANCE is not None:
            _BOT_INSTANCE.running = False
        runner = DirectTelegramBotRunner(token=token or TELEGRAM_BOT_TOKEN)
        t = threading.Thread(target=runner.run_forever, daemon=True, name="TelegramBot4AppRunner")
        t.start()
        _BOT_INSTANCE = runner
        return runner


def get_telegram_bot_status():
    if _BOT_INSTANCE is None:
        return {"running": False, "bot_username": "", "admin_id": ROOT_ADMIN_ID}
    return {
        "running": bool(_BOT_INSTANCE.running),
        "bot_username": _BOT_INSTANCE.bot_username,
        "bot_id": _BOT_INSTANCE.bot_id,
        "admin_id": ROOT_ADMIN_ID,
        "last_error": _BOT_INSTANCE.last_error,
    }


def main():
    print(f"🚀 Đang khởi chạy BOT TREO 4APP 🇻🇳 (Admin ID: {ROOT_ADMIN_ID})...")
    runner = DirectTelegramBotRunner(TELEGRAM_BOT_TOKEN)
    runner.run_forever()


if __name__ == "__main__":
    main()