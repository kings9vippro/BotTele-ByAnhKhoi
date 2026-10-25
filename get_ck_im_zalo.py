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

import sys

# ==============================================================================
# BỘ ICON ĐỘNG TELEGRAM PREMIUM (TELEGRAM ANIMATED CUSTOM EMOJI ENGINE <tg-emoji>)
# Tự động hiển thị Icon Động 60fps Lottie trên Telegram iOS/Android/Desktop
# kèm cơ chế Auto-Fallback 0ms trong api_call nếu Bot Token chưa bật Fragment
# ==============================================================================
TG_ANIM_EMOJI_MAP = {
    "crown":   ("5219805704906270925", "👑"),
    "fire":    ("5424972470023104089", "🔥"),
    "bolt":    ("5431449001532594346", "⚡"),
    "rocket":  ("5445284980978621387", "🚀"),
    "sparkle": ("5368324170671202286", "✨"),
    "diamond": ("5472164874886846699", "💎"),
    "shield":  ("5373141891321699086", "🛡️"),
    "star":    ("5438496463044752972", "🌟"),
    "radar":   ("5397782960512444700", "📡"),
    "check":   ("5206607081334906820", "✅"),
    "cross":   ("5210952531676504517", "❌"),
    "warn":    ("5447644880824181073", "⚠️"),
    "gear":    ("5341715473882955310", "⚙️"),
    "king":    ("5386367538735104399", "🥷"),
    "target":  ("5350351256923673521", "🎯"),
    "magic":   ("5359785904535774578", "🌈"),
    "heart":   ("5465665476971471368", "❤️‍🔥"),
    "qr":      ("5427009714745517609", "📲"),
    "key":     ("5438496463044752972", "🔑"),
    "bot":     ("5373141891321699086", "👾"),
    "stop":    ("5210952531676504517", "🛑"),
    "folder":  ("5472164874886846699", "🗂️"),
}

_TG_CUSTOM_EMOJI_RE = re.compile(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", re.DOTALL)


TG_ANIM_EMOJI_MAP.update({
    "zzz":     ("5368324170671202286", "💤"),
    "mega":    ("5397782960512444700", "📢"),
    "user":    ("5373141891321699086", "👤"),
    "cart":    ("5445284980978621387", "🛒"),
    "chart":   ("5438496463044752972", "📊"),
    "down":    ("5427009714745517609", "📥"),
    "send":    ("5431449001532594346", "✈️"),
    "cookie":  ("5465665476971471368", "🍪"),
    "lock":    ("5373141891321699086", "🔐"),
})


def tg_anim(key: str, fallback: str = "") -> str:
    """Trả về thẻ HTML <tg-emoji emoji-id="...">...</tg-emoji> chuẩn Telegram Animated Emoji."""
    em_id, def_fb = TG_ANIM_EMOJI_MAP.get(key, ("5431449001532594346", fallback or "⚡"))
    fb_use = fallback or def_fb
    return f'<tg-emoji emoji-id="{em_id}">{fb_use}</tg-emoji>'


def tg_btn(text: str, callback_data: str = None, url: str = None, emoji_key: str = None, emoji_id: str = None) -> dict:
    """Tạo nút bấm InlineKeyboardButton kèm icon_custom_emoji_id (giống Tphat Store bot 83b86043.jpeg)."""
    btn = {"text": str(text)}
    if callback_data is not None:
        btn["callback_data"] = str(callback_data)
    if url is not None:
        btn["url"] = str(url)
    eff_eid = emoji_id
    if not eff_eid and emoji_key and emoji_key in TG_ANIM_EMOJI_MAP:
        eff_eid = TG_ANIM_EMOJI_MAP[emoji_key][0]
    if eff_eid:
        btn["icon_custom_emoji_id"] = str(eff_eid)
    return btn


def strip_tg_anim_tags(html_text: str) -> str:
    if not html_text or "<tg-emoji" not in html_text:
        return html_text
    return _TG_CUSTOM_EMOJI_RE.sub(r"\1", html_text)


def strip_button_custom_emojis(reply_markup):
    """Gỡ bỏ icon_custom_emoji_id khỏi inline_keyboard nếu môi trường Bot trả mã 400 BUTTON_CUSTOM_EMOJI_INVALID."""
    if not reply_markup:
        return reply_markup
    is_json_str = isinstance(reply_markup, str)
    try:
        rm_obj = json.loads(reply_markup) if is_json_str else dict(reply_markup)
        if isinstance(rm_obj, dict) and "inline_keyboard" in rm_obj:
            new_kb = []
            for row in rm_obj["inline_keyboard"]:
                new_row = []
                for btn in row:
                    if isinstance(btn, dict):
                        b_copy = {k: v for k, v in btn.items() if k != "icon_custom_emoji_id"}
                        new_row.append(b_copy)
                    else:
                        new_row.append(btn)
                new_kb.append(new_row)
            rm_obj["inline_keyboard"] = new_kb
        return json.dumps(rm_obj, ensure_ascii=False) if is_json_str else rm_obj
    except Exception:
        return reply_markup

# DANH SÁCH 32 CHỨC NĂNG VIP CHIA 4 TRANG (8 MỤC / TRANG, 2 CỘT / HÀNG GIỐNG Y HỆT ẢNH MẪU)
FUNCTION_ITEMS_32 = [
    # Trang 1/4
    {"id": "fn_treo_do",       "label": "❤️‍🔥 Treo Ngôn Đỏ",      "mode": "treo_ngon",   "color_mode": "fixed",        "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Treo ngôn chữ Đỏ Rực (db342e) toàn tập", "emoji_id": "5465665476971471368"},
    {"id": "fn_treo_damau",    "label": "🌈 Treo Đa Màu",        "mode": "treo_ngon",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Treo ngôn đổi màu rực rỡ từng chữ", "emoji_id": "5359785904535774578"},
    {"id": "fn_treo_gif",      "label": "⚡ Treo Ngôn GIF",      "mode": "treo_ngon",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Treo ngôn kèm hiệu ứng chuyển động VIP", "emoji_id": "5431449001532594346"},
    {"id": "fn_word_rainbow",  "label": "✨ Chữ Đổi Từng Màu",   "mode": "treo_nhay",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Mỗi từ/chữ đổi 1 màu (Đỏ-Cam-Vàng-Xanh), 0% chữ trắng", "emoji_id": "5368324170671202286"},
    {"id": "fn_treo_nhay",     "label": "🔥 Treo Nhây VIP",      "mode": "treo_nhay",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Nhây từng dòng liên hoàn đổi màu từng chữ", "emoji_id": "5424972470023104089"},
    {"id": "fn_nhay_tag",      "label": "🎯 Nhây Tag Tên",       "mode": "treo_nhay",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Nhây kèm Tag nhắc tên mục tiêu thật 100%", "hide_tag_name": False, "emoji_id": "5350351256923673521"},
    {"id": "fn_anall",         "label": "🚀 Nhây Tag All Ẩn",    "mode": "anall",       "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Báo chuông @All cả nhóm nhưng ẩn hoàn toàn chữ @All", "tag_all": True, "hide_tag_all": True, "emoji_id": "5445284980978621387"},
    {"id": "fn_antan",         "label": "💎 Nhây Tag Tên Ẩn",    "mode": "antan",       "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Tag tên thật báo chuông nhưng ẩn chữ @Tên trên khung chat", "hide_tag_name": True, "emoji_id": "5472164874886846699"},

    # Trang 2/4
    {"id": "fn_sieu_xa",       "label": "🚀 Siêu Xả Đa Box",     "mode": "fast",        "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Siêu xả đồng loạt đa nhóm tốc độ cao chống cấm chat (.xa)", "emoji_id": "5445284980978621387"},
    {"id": "fn_combo3",        "label": "⚡ Combo 3 Câu/Nhịp",   "mode": "combo3",      "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Xả liên thanh 3 câu mỗi nhịp đổi màu từng từ (.combo)", "emoji_id": "5431449001532594346"},
    {"id": "fn_nhay_2c",       "label": "🔥 Nhây Gộp 2 Câu",     "mode": "nhay2c",      "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "2c.txt",          "desc": "Nhây gộp 2 câu liên hoàn (2c.txt) đổi màu từng chữ (.2c)", "emoji_id": "5424972470023104089"},
    {"id": "fn_treo_so",       "label": "🔢 Treo Số Liên Hoàn",  "mode": "treo_so",     "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "so.txt",          "desc": "Treo đếm số liên hoàn (so.txt) đổi màu từng chữ (.so)", "emoji_id": "5438496463044752972"},
    {"id": "fn_so_tag",        "label": "🎯 Số Kèm Tag",         "mode": "so_tag",      "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "so.txt",          "desc": "Treo số kèm Tag thẳng tên mục tiêu (.sotag)", "emoji_id": "5350351256923673521"},
    {"id": "fn_faketen",       "label": "👑 Số Fake Tên",        "mode": "faketen",     "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "so.txt",          "desc": "Treo số giả danh tên đối phương (.faketen)", "emoji_id": "5219805704906270925"},
    {"id": "fn_nhay_icon",     "label": "🌪️ Bão Icon VIP",      "mode": "nhayicon",    "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhayicon.txt",    "desc": "Xả bão ký hiệu & icon VIP (.nhayicon)", "emoji_id": "5368324170671202286"},
    {"id": "fn_chui",          "label": "💥 Nhây Sát Thương",    "mode": "chui",        "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "chui.txt",        "desc": "Nhây sát thương cực mạnh (chui.txt) đổi màu từng từ (.chui)", "emoji_id": "5424972470023104089"},

    # Trang 3/4
    {"id": "fn_nhay_poll",     "label": "📊 Treo Poll 0s (Không Nghỉ)", "mode": "nhay_poll", "color_mode": "word_rainbow", "fixed_color": "red", "file_hint": "nhay.txt",        "desc": "Tạo bình chọn (Poll) tự động liên hoàn 0.0s KHÔNG CÓ THỜI GIAN NGHỈ (.nhaypoll)", "emoji_id": "5438496463044752972"},
    {"id": "fn_typing",        "label": "⌨️ Hiệu Ứng Typing",    "mode": "typing_loop", "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Giả lập đang soạn tin nhắn liên tục chống khóa chat (.nhaytyping)", "emoji_id": "5431449001532594346"},
    {"id": "fn_tenbox",        "label": "✏️ Đổi Tên Box Zalo",   "mode": "nhay_tenbox", "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhaynamebox.txt", "desc": "Đổi tên Box Zalo & Messenger liên hoàn 0s (.tenbox / .nhaynamebox)", "emoji_id": "5368324170671202286"},
    {"id": "fn_todo",          "label": "📋 Giao Việc To-Do",    "mode": "zalo_todo",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Giao việc Zalo To-Do nhắc nhở thẳng mục tiêu (.todo)", "emoji_id": "5206607081334906820"},
    {"id": "fn_bankcard",      "label": "🏦 Thẻ Ngân Hàng",      "mode": "zalo_bank",   "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Gửi thẻ ngân hàng VietQR tự động vào nhóm (.bank)", "emoji_id": "5472164874886846699"},
    {"id": "fn_sharecontact",  "label": "🪪 Gửi Danh Thiếp",     "mode": "share_contact","color_mode": "word_rainbow","fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Chia sẻ danh thiếp (Contact Card) vào nhóm (.card)", "emoji_id": "5427009714745517609"},
    {"id": "fn_theme",         "label": "🎨 Đổi Nền Box Zalo",   "mode": "nen_mqtt",    "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Đổi nền trò chuyện Box Zalo & Messenger liên hoàn (.theme / .nen)", "emoji_id": "5359785904535774578"},
    {"id": "fn_sharelink",     "label": "🔗 Chia Sẻ Link",       "mode": "share_link",  "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "ngon.txt",        "desc": "Treo chia sẻ liên kết kèm tiêu đề nổi bật (.sharelink)", "emoji_id": "5397782960512444700"},

    # Trang 4/4
    {"id": "fn_setname",       "label": "🏷️ Đổi Biệt Danh",      "mode": "set_nickname","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhaynamebox.txt", "desc": "Đổi biệt danh thành viên trong nhóm liên hoàn (.setname)", "emoji_id": "5386367538735104399"},
    {"id": "fn_chan",          "label": "🛡️ Chặn & Bám Sát",    "mode": "special_chan","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "nhay.txt",        "desc": "Tự động vả lại đối thủ 0ms ngay khi họ vừa nhắn (.chan)", "emoji_id": "5373141891321699086"},
    {"id": "fn_proxy",         "label": "🌐 Xoay Vòng Proxy",    "mode": "special_prx", "color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "",                "desc": "Quản lý & kiểm tra dàn Proxy chống nghẽn đường truyền (.prx)", "emoji_id": "5397782960512444700"},
    {"id": "fn_antiban_box",   "label": "🛡️ Anti Cấm Chat Box",  "mode": "special_anti","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "",                "desc": "Cấu hình Lá Chắn Chống Zalo Cấm Chat Box (.ab)", "emoji_id": "5373141891321699086"},
    {"id": "fn_delay",         "label": "⏱️ Chỉnh Tốc Độ Delay", "mode": "special_delay","color_mode": "word_rainbow","fixed_color": "red",    "file_hint": "",                "desc": "Chỉnh tốc độ gửi tin (0.0s, 0.05s, 0.1s, 0.2s, 0.5s, 1s) (.d)", "emoji_id": "5431449001532594346"},
    {"id": "fn_colormode",     "label": "🎨 Chế Độ Màu Chữ",     "mode": "special_color","color_mode": "word_rainbow","fixed_color": "red",    "file_hint": "",                "desc": "Chọn chế độ Đổi Màu Từng Chữ hoặc Màu Cố Định (.mau)", "emoji_id": "5359785904535774578"},
    {"id": "fn_fontstyle",     "label": "🔤 Cỡ & Kiểu Chữ",      "mode": "special_font","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "",                "desc": "Chọn cỡ chữ To Đậm (f_18), Vừa Đậm (f_15), Xen Kẽ (.font)", "emoji_id": "5368324170671202286"},
    {"id": "fn_stop_all",      "label": "🛑 Dừng Tất Cả (.ta)",  "mode": "special_stop","color_mode": "word_rainbow", "fixed_color": "red",    "file_hint": "",                "desc": "Dừng khẩn cấp toàn bộ các chiến dịch đang chạy (.ta)", "emoji_id": "5210952531676504517"},
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
    eff_path = DB_PATH
    try:
        if "app" in sys.modules and getattr(sys.modules["app"], "_ACTIVE_DB_PATH", None):
            eff_path = sys.modules["app"]._ACTIVE_DB_PATH
    except Exception:
        pass
    conn = sqlite3.connect(eff_path, timeout=15)
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


def can_user_access_account(user_id, owner_tg_id) -> bool:
    """Phân quyền Cookie/Acc nghiêm ngặt:
    - Admin chính (8827605973) có quyền tối cao: xem, kiểm tra, lấy token và điều khiển TẤT CẢ Cookie/Acc trên hệ thống!
    - Người được Admin thêm vào Bot: CHỈ xem, kiểm tra, lấy token và điều khiển được đúng các Cookie/Acc do chính họ quét hoặc nạp vào (owner_tg_id == user_id)!"""
    if is_root_admin(user_id):
        return True
    u_s = str(user_id or "").strip()
    o_s = str(owner_tg_id or "").strip()
    return bool(u_s and o_s and u_s == o_s)


def get_user_visible_accounts(user_id, enabled_only=False, platform=None):
    """Trả về danh sách tài khoản mà user_id được phép nhìn thấy và sử dụng."""
    out = []
    try:
        conn = _open_db()
        try:
            conn.execute("ALTER TABLE accounts ADD COLUMN owner_tg_id TEXT DEFAULT ''")
        except Exception:
            pass
        rows = conn.execute(
            "SELECT id, name, platform, uid, imei, cookies, user_agent, zpw_enk, chat_cmd_enabled, enabled, token, is_bot, owner_tg_id FROM accounts ORDER BY id DESC"
        ).fetchall()
        conn.close()
        for r in rows:
            aid, aname, aplat, auid, aimei, ack, aua, aenk, cmd_on, en_on, atok, is_b, owner_id = r
            if enabled_only and not (en_on is None or int(en_on)):
                continue
            if platform and str(aplat or "zalo").lower() != str(platform).lower():
                continue
            if not can_user_access_account(user_id, owner_id):
                continue
            out.append({
                "id": aid,
                "name": aname or f"Acc #{aid}",
                "platform": (aplat or "zalo").lower(),
                "uid": auid or "",
                "imei": aimei or "",
                "cookies": ack or "{}",
                "user_agent": aua or "",
                "zpw_enk": aenk or "",
                "chat_cmd_enabled": 1 if (cmd_on is None or int(cmd_on)) else 0,
                "enabled": 1 if (en_on is None or int(en_on)) else 0,
                "token": atok or "",
                "is_bot": int(is_b or 0),
                "owner_tg_id": str(owner_id or ""),
            })
    except Exception:
        pass
    return out


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


def sync_zalo_account_to_web_db(uid, display_name, imei, cookies_dict, zpw_enk="", user_agent="", pc_name="", owner_tg_id=""):
    """Lưu tài khoản Zalo (quét QR hoặc nhập Cookie + IMEI) vào SQLite database.db, gắn quyền sở hữu owner_tg_id & kích hoạt luồng lắng nghe 32 lệnh in-chat (.menu, .n, .g, .nhaypoll, .t...) 24/7 trên Đa Acc."""
    try:
        clean_ck = {
            str(k): str(v)
            for k, v in (cookies_dict or {}).items()
            if _is_valid_cookie_val(v)
        }
        imei_str = str(imei or clean_ck.get("z_uuid") or clean_ck.get("imei") or "").strip()
        if imei_str:
            clean_ck["z_uuid"] = imei_str
        clean_ck.setdefault("_zlang", "vn")
        ua = (user_agent or "").strip() or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

        raw_uid_in = str(uid or "").strip()
        uid_str = raw_uid_in if (raw_uid_in.isdigit() and len(raw_uid_in) >= 6 and raw_uid_in != imei_str) else ""
        if not uid_str:
            for ck_v in clean_ck.values():
                m_u = re.match(r"^(\d{8,22})\.", str(ck_v or "").strip())
                if m_u:
                    uid_str = m_u.group(1)
                    break
        enk_str = str(zpw_enk or "").strip()
        dname_str = str(display_name or "").strip()
        owner_str = str(owner_tg_id or "").strip()

        # 1. Nếu nhập Cookie + IMEI mà chưa có zpw_enk hoặc uid -> tự động lấy khóa phiên zpw_enk & UID thật ngay lập tức
        if imei_str and clean_ck and (not enk_str or not uid_str):
            try:
                chk = check_zalo_cookie_imei_live(imei_str, clean_ck, zpw_enk=enk_str, user_agent=ua, uid=uid_str, db_path=DB_PATH)
                if chk.get("cookies"):
                    for k_c, v_c in chk["cookies"].items():
                        if _is_valid_cookie_val(v_c):
                            clean_ck[str(k_c)] = str(v_c)
                if chk.get("zpw_enk"):
                    enk_str = str(chk["zpw_enk"]).strip()
                if chk.get("uid"):
                    uid_str = str(chk["uid"]).strip()
                if chk.get("display_name") and (not dname_str or dname_str.startswith("Zalo_")):
                    dname_str = str(chk["display_name"]).strip()
            except Exception:
                pass

        # 2. Dự phòng trích xuất trực tiếp qua Zalo.get_pooled_client để đảm bảo 100% có UID + zpw_enk khi thêm Cookie + IMEI
        if imei_str and clean_ck and (not enk_str or not uid_str):
            try:
                import app as _main_app
                zc_init = _main_app.Zalo.get_pooled_client(
                    imei_str, clean_ck, user_agent=ua, zpw_enk_hint=enk_str, uid_hint=uid_str
                )
                if getattr(zc_init, "uid", None) and not uid_str:
                    uid_str = str(zc_init.uid).strip()
                if getattr(zc_init, "secret_key", None) and not enk_str:
                    enk_str = str(zc_init.secret_key).strip()
            except Exception:
                pass

        cookies_json = json.dumps(clean_ck, ensure_ascii=False)
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
                chat_cmd_enabled INTEGER DEFAULT 1,
                cmd_prefix TEXT DEFAULT '.',
                allow_all_cmd INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                uid TEXT DEFAULT '',
                zpw_enk TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                owner_tg_id TEXT DEFAULT ''
            )"""
        )
        for col_sql in (
            "ALTER TABLE accounts ADD COLUMN chat_cmd_enabled INTEGER DEFAULT 1",
            "ALTER TABLE accounts ADD COLUMN cmd_prefix TEXT DEFAULT '.'",
            "ALTER TABLE accounts ADD COLUMN allow_all_cmd INTEGER DEFAULT 0",
            "ALTER TABLE accounts ADD COLUMN enabled INTEGER DEFAULT 1",
            "ALTER TABLE accounts ADD COLUMN uid TEXT DEFAULT ''",
            "ALTER TABLE accounts ADD COLUMN zpw_enk TEXT DEFAULT ''",
            "ALTER TABLE accounts ADD COLUMN user_agent TEXT DEFAULT ''",
            "ALTER TABLE accounts ADD COLUMN owner_tg_id TEXT DEFAULT ''",
        ):
            try:
                conn.execute(col_sql)
            except Exception:
                pass

        cur = conn.cursor()
        existing = None
        if uid_str:
            existing = cur.execute(
                "SELECT id, owner_tg_id FROM accounts WHERE platform='zalo' AND uid=?", (uid_str,)
            ).fetchone()
        if not existing and imei_str:
            existing = cur.execute(
                "SELECT id, owner_tg_id FROM accounts WHERE platform='zalo' AND imei=?", (imei_str,)
            ).fetchone()

        acc_label = dname_str or f"Zalo_{(uid_str or imei_str)[-4:]}"
        if existing:
            acc_id = existing[0]
            old_owner = str(existing[1] or "").strip()
            eff_owner = owner_str if owner_str else (old_owner or ROOT_ADMIN_ID)
            cur.execute(
                """UPDATE accounts
                   SET name=?, imei=?, cookies=?, uid=CASE WHEN ? != '' THEN ? ELSE uid END,
                       zpw_enk=CASE WHEN ? != '' THEN ? ELSE zpw_enk END,
                       user_agent=?, chat_cmd_enabled=1, cmd_prefix='.', allow_all_cmd=0, enabled=1,
                       owner_tg_id=?
                   WHERE id=?""",
                (acc_label, imei_str, cookies_json, uid_str, uid_str, enk_str, enk_str, ua, eff_owner, acc_id),
            )
        else:
            eff_owner = owner_str or ROOT_ADMIN_ID
            cur.execute(
                """INSERT INTO accounts (name, imei, cookies, platform, token, is_bot, chat_cmd_enabled, cmd_prefix, allow_all_cmd, enabled, uid, zpw_enk, user_agent, owner_tg_id)
                   VALUES (?, ?, ?, 'zalo', '', 0, 1, '.', 0, 1, ?, ?, ?, ?)""",
                (acc_label, imei_str, cookies_json, uid_str, enk_str, ua, eff_owner),
            )
            acc_id = cur.lastrowid

        conn.commit()
        conn.close()

        # Đồng bộ ngay vào Vault, ZaloPCSessionKeeper, OWNER_UIDS_CACHE & ZaloRealtimeListener để acc sài được trọn bộ 32 lệnh (.menu, .treodo, .damau, .nhaypoll, .n, .g, .t...) ngay lập tức!
        try:
            ZaloPCSessionKeeper.register_and_keep_alive(
                uid=uid_str,
                imei=imei_str,
                cookies_dict=clean_ck,
                zpw_enk=enk_str,
                user_agent=ua,
                pc_name=pc_name or "Windows 11 Pro (Singapore)",
                display_name=acc_label,
                db_path=DB_PATH,
            )
        except Exception:
            pass

        try:
            import app as _main_app
            if hasattr(_main_app, "ZaloCookieVaultEngine"):
                _main_app.ZaloCookieVaultEngine.save_zalo_vault_record(
                    uid=uid_str or imei_str,
                    display_name=acc_label,
                    imei=imei_str,
                    cookies_dict=clean_ck,
                    zpw_enk=enk_str,
                    user_agent=ua,
                    owner_tg_id=eff_owner,
                )
            if uid_str:
                _main_app.OWNER_UIDS_CACHE.add(uid_str)
                if hasattr(_main_app, "add_authorized_user"):
                    _main_app.add_authorized_user(uid_str, acc_label)
            if hasattr(_main_app, "refresh_accounts_ram_cache"):
                _main_app.refresh_accounts_ram_cache()
            if hasattr(_main_app, "refresh_owner_uids"):
                _main_app.refresh_owner_uids()
            if hasattr(_main_app, "sync_all_zalo_listeners"):
                _main_app.sync_all_zalo_listeners()

            # Khởi động ấm (pre-warm) danh sách nhóm & phiên Zalo.get_pooled_client trong luồng nền để gõ 32 lệnh ở bất kỳ Box nào cũng ăn ngay 0ms
            def _warm_acc_groups():
                try:
                    zc = _main_app.Zalo.get_pooled_client(
                        imei_str, clean_ck, user_agent=ua, zpw_enk_hint=enk_str, uid_hint=uid_str
                    )
                    resolved_u = str(getattr(zc, "uid", "") or uid_str).strip()
                    resolved_enk = str(getattr(zc, "secret_key", "") or enk_str).strip()
                    if resolved_u:
                        _main_app.OWNER_UIDS_CACHE.add(resolved_u)
                        if hasattr(_main_app, "add_authorized_user"):
                            _main_app.add_authorized_user(resolved_u, acc_label)
                        if not uid_str or (resolved_enk and not enk_str):
                            try:
                                c_up = _open_db()
                                c_up.execute(
                                    "UPDATE accounts SET uid=CASE WHEN uid='' THEN ? ELSE uid END, zpw_enk=CASE WHEN zpw_enk='' THEN ? ELSE zpw_enk END WHERE id=?",
                                    (resolved_u, resolved_enk, acc_id)
                                )
                                c_up.commit()
                                c_up.close()
                                if hasattr(_main_app, "refresh_accounts_ram_cache"):
                                    _main_app.refresh_accounts_ram_cache()
                                if hasattr(_main_app, "sync_all_zalo_listeners"):
                                    _main_app.sync_all_zalo_listeners()
                            except Exception:
                                pass
                        gmap = zc.get_grid_ver_map() or {}
                        for gk in gmap.keys():
                            gs = str(gk).split("_")[0].strip()
                            if gs and gs != resolved_u:
                                _main_app.KNOWN_GROUPS_BY_ACC[resolved_u].add(gs)
                                _main_app.ALL_KNOWN_ZALO_GROUP_IDS.add(gs)
                except Exception:
                    pass
            threading.Thread(target=_warm_acc_groups, daemon=True).start()
        except Exception:
            pass
        return acc_id
    except Exception:
        return None


def parse_imei_and_cookie_from_text(raw_text, extra_cookies_text=""):
    """Trích xuất linh hoạt IMEI, Cookie Dict và Metadata từ mọi định dạng văn bản người dùng gửi vào."""
    imei_clean, cookies_dict, zpw_enk, ua = extract_imei_and_metadata_flexible(raw_text, extra_cookies_text)
    if not cookies_dict:
        cookies_dict = parse_cookies_input_flexible(f"{raw_text or ''}\n{extra_cookies_text or ''}")
    if not imei_clean:
        imei_clean = str(cookies_dict.get("z_uuid") or cookies_dict.get("imei") or "").strip()
    uid_found = str(cookies_dict.get("uid") or "").strip()
    if not uid_found:
        m_uid = re.search(r"(?:UID|uid|userId)\s*[:=]\s*([0-9]{8,22})", f"{raw_text or ''}\n{extra_cookies_text or ''}")
        if m_uid:
            uid_found = m_uid.group(1).strip()
    cookies_dict.pop("imei", None)
    meta = {
        "imei": imei_clean,
        "zpw_enk": zpw_enk,
        "user_agent": ua,
        "uid": uid_found,
        "name": "",
    }
    return imei_clean, cookies_dict, meta


def sync_and_keepalive_tokens_to_db(raw_text, owner_tg_id=""):
    saved_items = []
    if not raw_text:
        return saved_items
    owner_str = str(owner_tg_id or ROOT_ADMIN_ID).strip()

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
                try:
                    conn.execute("ALTER TABLE accounts ADD COLUMN owner_tg_id TEXT DEFAULT ''")
                except Exception:
                    pass
                cur = conn.cursor()
                ex = cur.execute(
                    "SELECT id FROM accounts WHERE platform='discord' AND (token=? OR uid=?)",
                    (tok, uid),
                ).fetchone()
                if ex:
                    acc_id = ex[0]
                    cur.execute(
                        "UPDATE accounts SET name=?, token=?, is_bot=?, uid=?, enabled=1, owner_tg_id=? WHERE id=?",
                        (uname, tok, is_bot, uid, owner_str, acc_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO accounts (name, imei, cookies, platform, token, is_bot, uid, enabled, owner_tg_id) VALUES (?, '', '{}', 'discord', ?, ?, ?, 1, ?)",
                        (uname, tok, is_bot, uid, owner_str),
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
            try:
                conn.execute("ALTER TABLE accounts ADD COLUMN owner_tg_id TEXT DEFAULT ''")
            except Exception:
                pass
            cur = conn.cursor()
            ex = cur.execute(
                "SELECT id FROM accounts WHERE platform='messenger' AND uid=?", (uid,)
            ).fetchone()
            if ex:
                acc_id = ex[0]
                cur.execute(
                    "UPDATE accounts SET cookies=?, enabled=1, owner_tg_id=? WHERE id=?", (raw_text.strip(), owner_str, acc_id)
                )
            else:
                cur.execute(
                    "INSERT INTO accounts (name, imei, cookies, platform, token, is_bot, uid, enabled, owner_tg_id) VALUES (?, '', ?, 'messenger', '', 0, ?, 1, ?)",
                    (fb_name, raw_text.strip(), uid, owner_str),
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
    """Bộ điều khiển trung tâm BOT TREO 4APP 🇻🇳 qua Telegram (Giao diện Card Quote + Custom Emoji giống Tphat Store + Phân quyền Admin/User độc lập + Treo Poll 0s)."""

    @staticmethod
    def _create_isolated_session():
        s = requests.Session()
        adapter = HTTPAdapter(pool_connections=48, pool_maxsize=96, max_retries=1)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s

    def __init__(self, token=TELEGRAM_BOT_TOKEN):
        self.token = (token or TELEGRAM_BOT_TOKEN).strip()
        self.api_base = f"https://api.telegram.org/bot{self.token}"
        self.running = False
        self.offset = 0
        self._tls = threading.local()
        self.poll_session = self._create_isolated_session()
        self.session = self._create_isolated_session()
        self.user_states = {}
        self.wizard_selections = {}
        self.active_qr_locks = set()
        self.active_qr_stop_events = {}
        self.bot_username = ""
        self.bot_id = None
        self.last_error = ""
        self.started_at = time.time()
        self.last_poll_ok_ts = time.time()
        self.poll_thread = None
        self.executor = ThreadPoolExecutor(max_workers=32, thread_name_prefix="TgFastWorker")
        self._cached_welcome_file_id = _get_db_setting("tg_welcome_file_id", "")
        self._cached_welcome_kind = _get_db_setting("tg_welcome_kind", "animation")
        self._cached_boxes_by_user = {}
        self._boxes_refreshing_users = set()

    def _get_worker_session(self):
        sess = getattr(self._tls, "session", None)
        if sess is None:
            sess = self._create_isolated_session()
            self._tls.session = sess
        return sess

    def api_call(self, method, data=None, files=None, timeout=15, use_poll_session=False):
        url = f"{self.api_base}/{method}"
        sess = self.poll_session if use_poll_session else self._get_worker_session()
        eff_timeout = (5.0, float(timeout)) if isinstance(timeout, (int, float)) else timeout
        try:
            if files:
                r = sess.post(url, data=data, files=files, timeout=eff_timeout)
            else:
                r = sess.post(url, json=data, timeout=eff_timeout)
            res = r.json() if r.content else {"ok": False, "description": f"HTTP {r.status_code}"}
            # Tự động fallback 0ms nếu Telegram báo lỗi BUTTON_CUSTOM_EMOJI_INVALID hoặc thẻ <tg-emoji>
            if not res.get("ok") and isinstance(data, dict):
                desc_up = str(res.get("description") or "").upper()
                if any(k in desc_up for k in ("EMOJI", "ENTITY", "ENTITIES", "PARSE", "BUTTON", "DOCUMENT_INVALID", "BAD REQUEST")):
                    fallback_data = dict(data)
                    changed = False
                    if "reply_markup" in fallback_data and fallback_data["reply_markup"]:
                        rm_raw = fallback_data["reply_markup"]
                        if isinstance(rm_raw, str):
                            try:
                                rm_obj = json.loads(rm_raw)
                                fallback_data["reply_markup"] = json.dumps(strip_button_custom_emojis(rm_obj), ensure_ascii=False)
                                changed = True
                            except Exception:
                                pass
                        elif isinstance(rm_raw, dict):
                            fallback_data["reply_markup"] = strip_button_custom_emojis(rm_raw)
                            changed = True
                    # Nếu lỗi do parse entity trong text/caption thì mới lược bỏ <tg-emoji>
                    if any(k in desc_up for k in ("ENTITY", "ENTITIES", "PARSE", "DOCUMENT_INVALID")) or not changed:
                        if "text" in fallback_data and isinstance(fallback_data["text"], str) and "<tg-emoji" in fallback_data["text"]:
                            fallback_data["text"] = strip_tg_anim_tags(fallback_data["text"])
                            changed = True
                        if "caption" in fallback_data and isinstance(fallback_data["caption"], str) and "<tg-emoji" in fallback_data["caption"]:
                            fallback_data["caption"] = strip_tg_anim_tags(fallback_data["caption"])
                            changed = True
                    if changed:
                        if files:
                            r2 = sess.post(url, data=fallback_data, files=files, timeout=eff_timeout)
                        else:
                            r2 = sess.post(url, json=fallback_data, timeout=eff_timeout)
                        res2 = r2.json() if r2.content else res
                        if not res2.get("ok") and (
                            ("<tg-emoji" in str(fallback_data.get("text") or ""))
                            or ("<tg-emoji" in str(fallback_data.get("caption") or ""))
                        ):
                            if "text" in fallback_data and isinstance(fallback_data["text"], str):
                                fallback_data["text"] = strip_tg_anim_tags(fallback_data["text"])
                            if "caption" in fallback_data and isinstance(fallback_data["caption"], str):
                                fallback_data["caption"] = strip_tg_anim_tags(fallback_data["caption"])
                            if files:
                                r3 = sess.post(url, data=fallback_data, files=files, timeout=eff_timeout)
                            else:
                                r3 = sess.post(url, json=fallback_data, timeout=eff_timeout)
                            return r3.json() if r3.content else res2
                        return res2
            return res
        except Exception as e:
            self.last_error = str(e)
            if not use_poll_session:
                try:
                    self._tls.session = self._create_isolated_session()
                except Exception:
                    pass
            return {"ok": False, "description": str(e)}

    def clear_webhook_and_init(self):
        try:
            self.api_call("deleteWebhook", {"drop_pending_updates": False}, timeout=8)
            me = self.api_call("getMe", timeout=8)
            if me.get("ok") and me.get("result"):
                self.bot_username = me["result"].get("username") or ""
                self.bot_id = me["result"].get("id")
                self.api_call(
                    "setMyCommands",
                    {
                        "commands": [
                            {"command": "start", "description": "🎬 Mở bảng điều khiển BOT TREO 4APP 🇻🇳"},
                            {"command": "menu", "description": "📋 Mở nhanh Menu 32 Chức Năng VIP"},
                            {"command": "qr", "description": "📲 Quét mã QR Zalo PC lấy Token & Sống Đa Acc"},
                            {"command": "addck", "description": "🍪 Nhập Cookie + IMEI Zalo (Sài 32 lệnh trên Acc)"},
                            {"command": "addid", "description": "➕ [Admin] Thêm ID người dùng được phép sài Bot"},
                            {"command": "delid", "description": "➖ [Admin] Xoá quyền sài Bot của ID người dùng"},
                            {"command": "listid", "description": "📋 [Admin] Xem danh sách ID được phép sài Bot"},
                            {"command": "checkzalo", "description": "🔍 Kiểm tra & Cứu Cookie Zalo Live/Die"},
                            {"command": "status", "description": "📊 Xem trạng thái Acc & Chiến dịch đang chạy"},
                            {"command": "stopall", "description": "🛑 Dừng khẩn cấp toàn bộ chiến dịch (.ta)"},
                        ]
                    },
                    timeout=8,
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
        return self.api_call("sendMessage", payload, timeout=12)

    def send_welcome_video_menu(self, chat_id, caption_html, reply_to=None, reply_markup=None):
        """Gửi bảng điều khiển kèm Video chào (welcome.mp4), tự động cache file_id để phản hồi 0.02s!"""
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
            res = self.api_call(method, payload, timeout=12)
            if res.get("ok"):
                return res
            self._cached_welcome_file_id = ""

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
                    timeout=30,
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

                res2 = self.api_call(
                    "sendVideo",
                    data=data,
                    files={"video": ("welcome.mp4", video_bytes, "video/mp4")},
                    timeout=30,
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
        """Cập nhật tức thì nội dung & nút bấm dưới Video chào (0ms perceived latency)."""
        payload_cap = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": caption_html,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload_cap["reply_markup"] = reply_markup
        res = self.api_call("editMessageCaption", payload_cap, timeout=10)
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
        res2 = self.api_call("editMessageText", payload_txt, timeout=10)
        if res2.get("ok") or "message is not modified" in str(res2.get("description", "")).lower():
            return res2
        return self.send_welcome_video_menu(chat_id, caption_html, reply_markup=reply_markup)

    def answer_callback(self, callback_query_id, text="", show_alert=False, async_mode=True):
        if not callback_query_id:
            return
        payload = {"callback_query_id": callback_query_id, "show_alert": bool(show_alert)}
        if text:
            payload["text"] = text[:190]
        if async_mode and not show_alert:
            self.executor.submit(self.api_call, "answerCallbackQuery", payload, None, 6, False)
            return {"ok": True}
        return self.api_call("answerCallbackQuery", payload, timeout=6)

    def send_photo_bytes(self, chat_id, png_bytes, caption="", reply_to=None, reply_markup=None):
        data = {"chat_id": str(chat_id), "parse_mode": "HTML"}
        if caption:
            data["caption"] = caption
        if reply_to:
            data["reply_to_message_id"] = str(reply_to)
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        files = {"photo": ("zalo_qr.png", png_bytes, "image/png")}
        return self.api_call("sendPhoto", data=data, files=files, timeout=18)

    def send_doc_bytes(self, chat_id, content_bytes, filename, caption="", reply_to=None):
        data = {"chat_id": str(chat_id), "parse_mode": "HTML"}
        if caption:
            data["caption"] = caption
        if reply_to:
            data["reply_to_message_id"] = str(reply_to)
        files = {"document": (filename, content_bytes, "text/plain")}
        return self.api_call("sendDocument", data=data, files=files, timeout=18)

    def delete_msg(self, chat_id, message_id):
        if not message_id:
            return
        self.executor.submit(self.api_call, "deleteMessage", {"chat_id": chat_id, "message_id": message_id}, None, 6, False)

    # XÂY DỰNG GIAO DIỆN BLOCKQUOTE CARD + ICON ĐỘNG GIỐNG HỆT TPHAT STORE BOT (83b86043.jpeg)
    @staticmethod
    def _get_live_runtime_summary(user_id=ROOT_ADMIN_ID):
        acc_cnt = 0
        running_cnt = 0
        color_label = "Đổi Từng Màu"
        delay_val = 0.0
        try:
            vis_accs = get_user_visible_accounts(user_id, enabled_only=True)
            acc_cnt = len(vis_accs)
            import app as _main_app
            with _main_app.TASKS_LOCK:
                running_cnt = sum(1 for t in _main_app.TASKS.values() if t.get("status") == "running" or t.get("running"))
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
        is_admin = is_root_admin(user_id)
        role_str = "Admin Chính (Toàn Quyền)" if is_admin else "Thành Viên VIP (Kho Acc Riêng)"
        name_clean = str(user_first_name or "Anh").replace("<", "").replace(">", "").strip() or "Anh"

        if active_tab == "func":
            sec_title = f"CHỨC NĂNG VIP – TRANG {page}/4"
        elif active_tab == "mgmt":
            sec_title = "QUẢN LÝ ĐA ACC & PHÂN QUYỀN VIP" if is_admin else "QUẢN LÝ COOKIE & ACC CỦA BẠN"
        else:
            sec_title = "TIỆN ÍCH MỞ RỘNG SIÊU CẤP"

        acc_cnt, running_cnt, color_label, delay_val = cls._get_live_runtime_summary(user_id=user_id)
        scope_lbl = "Tổng Acc hệ thống" if is_admin else "Acc bạn đã quét/nạp"
        notice_block = f"\n<blockquote>{extra_notice}</blockquote>" if extra_notice else ""

        # Giao diện chuẩn Tphat Store bot (83b86043.jpeg): Tiêu đề chào + khung <blockquote> bo góc có dấu ngoặc kép ” & gạch đứt — — — — — — — — — —
        return (
            f"<b>CHÀO MỪNG {name_clean.upper()} ĐẾN VỚI BOT TREO 4APP 🇻🇳</b> {tg_anim('sparkle', '✨')}\n\n"
            f"<blockquote>"
            f"{tg_anim('bell', '📢')} Hệ thống: <b>32 Chức Năng VIP • Đa Acc 24/7</b>\n"
            f"{tg_anim('king', '👑')} Admin Chính: <a href=\"tg://user?id={ROOT_ADMIN_ID}\">@{ROOT_ADMIN_ID} ↗️</a>\n"
            f"— — — — — — — — — —\n"
            f"{tg_anim('party', '🎉')} Vai trò: <b>{role_str}</b>\n"
            f"{tg_anim('users', '👥')} {scope_lbl}: <b>{acc_cnt} Acc Live</b> • Đang chạy: <b>{running_cnt} luồng</b>\n"
            f"{tg_anim('money', '💸')} Chế độ: <b>{color_label}</b> • Delay: <b>{delay_val}s</b> (Poll: <b>0.0s</b>)\n"
            f"{tg_anim('clock', '🕒')} Thời gian: <b>{time_str}</b>"
            f"</blockquote>"
            f"{notice_block}\n\n"
            f"{tg_anim('gear', '⚙️')} <b>{sec_title}</b>"
        )

    @classmethod
    def build_tabbed_keyboard(cls, active_tab="func", page=1, user_id=ROOT_ADMIN_ID):
        page = max(1, min(4, int(page or 1)))
        is_admin = is_root_admin(user_id)
        tab_row = [
            tg_btn("Chức Năng", "tab_func_1", emoji_key="fire" if active_tab == "func" else "diamond"),
            tg_btn("Quản Lý", "tab_mgmt", emoji_key="crown" if active_tab == "mgmt" else "folder"),
            tg_btn("Tiện Ích", "tab_util", emoji_key="bolt" if active_tab == "util" else "gear"),
        ]
        rows = [tab_row]

        if active_tab == "func":
            start_idx = (page - 1) * 8
            page_items = FUNCTION_ITEMS_32[start_idx:start_idx + 8]
            for i in range(0, len(page_items), 2):
                pair = page_items[i:i + 2]
                row = [
                    tg_btn(item["label"], f"pickfn:{item['id']}", emoji_id=item.get("emoji_id"))
                    for item in pair
                ]
                rows.append(row)

            prev_p = 4 if page <= 1 else page - 1
            next_p = 1 if page >= 4 else page + 1
            rows.append([
                tg_btn("Trang trước", f"tab_func_{prev_p}", emoji_key="back"),
                tg_btn(f"Trang {page}/4", "noop", emoji_key="chart"),
                tg_btn("Trang sau", f"tab_func_{next_p}", emoji_key="next"),
            ])

        elif active_tab == "mgmt":
            rows.append([
                tg_btn("Quét QR Lấy Token", "cmd_qr_sg", emoji_key="qr"),
                tg_btn("Nhập Cookie + IMEI", "mgmt_input_ck_im", emoji_key="cookie"),
            ])
            # CHỈ ADMIN CHÍNH (8827605973) MỚI ĐƯỢC THÊM / XOÁ / XEM DANH SÁCH ID SÀI BOT
            if is_admin:
                rows.append([
                    tg_btn("Thêm ID Sài Bot", "mgmt_add_id", emoji_key="plus"),
                    tg_btn("Xoá Quyền Sài Bot", "mgmt_del_id_menu", emoji_key="minus"),
                ])
                rows.append([
                    tg_btn("Danh Sách ID VIP", "mgmt_list_ids", emoji_key="list"),
                    tg_btn("Check Tất Cả Cookie", "cmd_checkzalo", emoji_key="search"),
                ])
                rows.append([
                    tg_btn("Tất Cả Cookie & Kho File (Admin)", "mgmt_acc_files", emoji_key="cat"),
                ])
            else:
                rows.append([
                    tg_btn("Cookie & Acc Của Tôi", "mgmt_acc_files", emoji_key="cat"),
                    tg_btn("Check Cookie Của Tôi", "cmd_checkzalo", emoji_key="search"),
                ])

        else:  # util
            rows.extend([
                [
                    tg_btn("Tạo Mã 2FA OTP", "prompt_2fa", emoji_key="lock"),
                    tg_btn("Trợ Lý Meta AI", "prompt_ai", emoji_key="bot"),
                ],
                [
                    tg_btn("Lấy Token Discord", "prompt_gettoken", emoji_key="target"),
                    tg_btn("Lấy Cookie FB", "prompt_getcookie", emoji_key="cookie"),
                ],
                [
                    tg_btn("Đổi Font Chữ VIP", "pickfn:fn_fontstyle", emoji_key="sparkle"),
                    tg_btn("Trạng Thái Hệ Thống", "cmd_status", emoji_key="chart"),
                ],
            ])

        return {"inline_keyboard": rows}

    # BẢNG CHỌN CHIẾN DỊCH TƯƠNG TÁC SIÊU TỐC (PHÂN TÁCH THEO USER_ID & TRẢ VỀ TỨC THÌ TỪ RAM 0MS)
    def _discover_all_boxes(self, user_id=ROOT_ADMIN_ID, force_refresh=False):
        uid_key = "ADMIN" if is_root_admin(user_id) else str(user_id or "")
        now = time.time()
        cached_entry = self._cached_boxes_by_user.get(uid_key)
        if not force_refresh and cached_entry and (now - cached_entry[0] < 25.0):
            return list(cached_entry[1])

        def _collect_fast_from_ram():
            boxes = []
            seen = set()
            try:
                import app as _main_app
                vis_accs = get_user_visible_accounts(user_id, enabled_only=True)
                for a in vis_accs:
                    plat = (a.get("platform") or "zalo").lower()
                    if plat == "zalo":
                        auid_s = str(a.get("uid") or "").strip()
                        # 1. Lấy tức thì từ _GROUPS_CACHE trong RAM nếu đã có
                        if auid_s and hasattr(_main_app.Zalo, "_GROUPS_CACHE"):
                            g_cached = _main_app.Zalo._GROUPS_CACHE.get(auid_s)
                            if g_cached:
                                for g in (g_cached[1] or []):
                                    gid = str(g.get("id") or "").strip()
                                    if gid and gid not in seen and gid != "null":
                                        seen.add(gid)
                                        boxes.append({
                                            "id": gid,
                                            "name": g.get("name") or f"Nhóm {gid[-6:]}",
                                            "platform": "zalo",
                                            "acc_id": a["id"],
                                        })
                        # 2. Bổ sung tức thì từ KNOWN_GROUPS_BY_ACC trong RAM
                        for gid_k in _main_app.KNOWN_GROUPS_BY_ACC.get(auid_s, set()):
                            gid_s = str(gid_k).strip()
                            if gid_s and gid_s not in seen and gid_s != "null":
                                seen.add(gid_s)
                                boxes.append({
                                    "id": gid_s,
                                    "name": f"Box Zalo {gid_s[-6:]}",
                                    "platform": "zalo",
                                    "acc_id": a["id"],
                                })
                    elif plat == "discord":
                        for cid in _main_app.DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS.get(a["id"], set()):
                            if cid and str(cid) not in seen:
                                seen.add(str(cid))
                                boxes.append({
                                    "id": str(cid),
                                    "name": f"Kênh Discord {str(cid)[-4:]}",
                                    "platform": "discord",
                                    "acc_id": a["id"],
                                })
            except Exception:
                pass
            return boxes

        def _deep_refresh_worker():
            if uid_key in self._boxes_refreshing_users and not force_refresh:
                return
            self._boxes_refreshing_users.add(uid_key)
            try:
                boxes = []
                seen = set()
                import app as _main_app
                vis_accs = get_user_visible_accounts(user_id, enabled_only=True)
                for a in vis_accs:
                    plat = (a.get("platform") or "zalo").lower()
                    if plat == "zalo":
                        try:
                            zc = _main_app.Zalo.get_pooled_client(
                                a["imei"], a["cookies"],
                                user_agent=a.get("user_agent") or "",
                                zpw_enk_hint=a.get("zpw_enk") or "",
                                uid_hint=a.get("uid") or ""
                            )
                            for g in (zc.groups(use_cache=not force_refresh) or []):
                                gid = str(g.get("id") or "").strip()
                                if gid and gid not in seen and gid != "null":
                                    seen.add(gid)
                                    boxes.append({
                                        "id": gid,
                                        "name": g.get("name") or f"Nhóm {gid[-6:]}",
                                        "platform": "zalo",
                                        "acc_id": a["id"],
                                    })
                            for gid_k in _main_app.KNOWN_GROUPS_BY_ACC.get(str(zc.uid or a.get("uid") or ""), set()):
                                gid_s = str(gid_k).strip()
                                if gid_s and gid_s not in seen and gid_s != "null":
                                    seen.add(gid_s)
                                    boxes.append({
                                        "id": gid_s,
                                        "name": f"Box Zalo {gid_s[-6:]}",
                                        "platform": "zalo",
                                        "acc_id": a["id"],
                                    })
                        except Exception:
                            pass
                    elif plat == "discord":
                        for cid in _main_app.DiscordStealthAntiBanEngine.ACTIVE_DISCORD_POLL_CHANNELS.get(a["id"], set()):
                            if cid and str(cid) not in seen:
                                seen.add(str(cid))
                                boxes.append({
                                    "id": str(cid),
                                    "name": f"Kênh Discord {str(cid)[-4:]}",
                                    "platform": "discord",
                                    "acc_id": a["id"],
                                })
                self._cached_boxes_by_user[uid_key] = (time.time(), list(boxes))
            except Exception:
                pass
            finally:
                self._boxes_refreshing_users.discard(uid_key)

        if force_refresh:
            _deep_refresh_worker()
            return list((self._cached_boxes_by_user.get(uid_key) or (0, []))[1])

        fast_boxes = _collect_fast_from_ram()
        if fast_boxes:
            self._cached_boxes_by_user[uid_key] = (now, list(fast_boxes))
            self.executor.submit(_deep_refresh_worker)
            return fast_boxes

        # Nếu RAM chưa có mới quét đồng bộ 1 lần
        _deep_refresh_worker()
        return list((self._cached_boxes_by_user.get(uid_key) or (0, []))[1])

    def _get_available_txt_files(self):
        try:
            import app as _main_app
            files = _main_app.get_ordered_files_with_display_num()
            if files:
                return files
        except Exception:
            pass
        out = []
        seen = set()
        for folder in (os.path.join(BASE_DIR, "presets"), os.path.join(BASE_DIR, "uploads")):
            if os.path.isdir(folder):
                for fn in sorted(os.listdir(folder)):
                    if fn.endswith(".txt"):
                        clean_fn = fn[7:] if fn.startswith("preset_") else fn
                        if clean_fn.lower() not in seen:
                            seen.add(clean_fn.lower())
                            fp = os.path.join(folder, fn)
                            try:
                                with open(fp, "r", encoding="utf-8", errors="ignore") as rf:
                                    l_cnt = sum(1 for ln in rf if ln.strip())
                            except Exception:
                                l_cnt = 1
                            out.append({
                                "display_num": len(out) + 1,
                                "num": len(out) + 1,
                                "filename": clean_fn,
                                "filepath": fp,
                                "lines_count": max(1, l_cnt),
                            })
        return out

    def _read_txt_file_blocks(self, file_name, mode="treo_nhay"):
        try:
            import app as _main_app
            blocks = _main_app.get_blocks_from_file_query(file_name, mode=mode)
            if blocks:
                return blocks
        except Exception:
            pass
        base_fn = os.path.basename(str(file_name or "nhay.txt"))
        candidates = [
            os.path.join(BASE_DIR, "uploads", base_fn),
            os.path.join(BASE_DIR, "uploads", f"preset_{base_fn}"),
            os.path.join(BASE_DIR, "presets", base_fn),
        ]
        for fpath in candidates:
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as rf:
                        raw_c = rf.read()
                    if mode == "treo_ngon":
                        return [raw_c.strip()] if raw_c.strip() else []
                    return [ln.strip() for ln in raw_c.splitlines() if ln.strip()]
                except Exception:
                    continue
        return []

    def render_function_wizard(self, chat_id, message_id, user_id, fn_id):
        fn_meta = FUNCTION_MAP_BY_ID.get(fn_id)
        if not fn_meta:
            return

        mode = fn_meta["mode"]
        if mode == "special_stop":
            try:
                import app as _main_app
                stopped = _main_app.stop_tasks_for_thread(None)
            except Exception:
                stopped = 0
            cap = self.build_tabbed_caption(
                user_id=user_id, active_tab="func", page=4,
                extra_notice=f"{tg_anim('stop', '🛑')} <b>ĐÃ DỪNG TẤT CẢ ({stopped} chiến dịch)!</b>"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4, user_id=user_id))
            return

        if mode == "special_delay":
            kb = {
                "inline_keyboard": [
                    [
                        tg_btn("0.0s (Không Nghỉ / Poll)", "setdelay:0", emoji_key="bolt"),
                        tg_btn("0.1s (Siêu Tốc Đa Acc)", "setdelay:0.1", emoji_key="rocket"),
                    ],
                    [
                        tg_btn("0.3s (Chuẩn VIP)", "setdelay:0.3", emoji_key="fire"),
                        tg_btn("0.5s (Mượt Bền)", "setdelay:0.5", emoji_key="shield"),
                    ],
                    [
                        tg_btn("1.0s (An Toàn)", "setdelay:1.0", emoji_key="check"),
                        tg_btn("2.0s (Treo Đêm)", "setdelay:2.0", emoji_key="clock"),
                    ],
                    [tg_btn("Quay lại Chức Năng", "tab_func_4", emoji_key="back")],
                ]
            }
            cap = (
                f"{tg_anim('bolt', '⚡')} <b>CHỈNH TỐC ĐỘ DELAY HỆ THỐNG (KHÔNG LAG ĐA ACC)</b>\n\n"
                "<blockquote>"
                "• Chọn tốc độ gửi tin bên dưới (áp dụng tức thì cho cả các chiến dịch đang chạy).\n"
                "• Riêng chế độ <b>📊 Treo Poll 0s</b> luôn luôn chạy <b>0.0s Không Nghỉ</b> bất kể Delay chung!"
                "</blockquote>"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        if mode == "special_color":
            kb = {
                "inline_keyboard": [
                    [tg_btn("Chữ Đổi Từng Màu (VIP - Mặc định)", "setcolor:word_rainbow:red", emoji_key="magic")],
                    [
                        tg_btn("Đỏ Rực (db342e)", "setcolor:fixed:red", emoji_key="fire"),
                        tg_btn("Cam Lửa (f27806)", "setcolor:fixed:orange", emoji_key="bolt"),
                    ],
                    [
                        tg_btn("Vàng Kim (f7b503)", "setcolor:fixed:yellow", emoji_key="crown"),
                        tg_btn("Xanh Ngọc (15a85f)", "setcolor:fixed:green", emoji_key="sparkle"),
                    ],
                    [tg_btn("Quay lại Chức Năng", "tab_func_4", emoji_key="back")],
                ]
            }
            cap = (
                f"{tg_anim('magic', '🌈')} <b>CHẾ ĐỘ MÀU CHỮ ZALO VIP (0% CHỮ TRẮNG)</b>\n\n"
                "<blockquote>"
                "• <b>Chữ Đổi Từng Màu</b>: Từng từ/chữ cái tự động đổi qua 4 mã màu gốc rực rỡ của Zalo (Đỏ - Cam - Vàng - Xanh Lá).\n"
                "• Tuyệt đối không dùng màu trắng cho câu treo/nhây."
                "</blockquote>"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        if mode == "special_font":
            kb = {
                "inline_keyboard": [
                    [
                        tg_btn("Chữ To Đậm (f_18)", "setfont:big_bold", emoji_key="fire"),
                        tg_btn("Chữ Vừa Đậm (f_15)", "setfont:normal_bold", emoji_key="bolt"),
                    ],
                    [
                        tg_btn("Xen Kẽ To/Nhỏ", "setfont:alternating_bold", emoji_key="sparkle"),
                        tg_btn("Nghiêng Đậm VIP", "setfont:italic_bold", emoji_key="diamond"),
                    ],
                    [tg_btn("Quay lại Chức Năng", "tab_func_4", emoji_key="back")],
                ]
            }
            cap = (
                f"{tg_anim('sparkle', '🔤')} <b>CHỈNH CỠ & KIỂU CHỮ ZALO VIP</b>\n\n"
                "<blockquote>• Chọn kiểu hiển thị chữ kết hợp cùng bộ đổi màu từng từ:</blockquote>"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        if mode == "special_anti":
            kb = {
                "inline_keyboard": [
                    [tg_btn("Bật Full Anti Cấm Chat Box (0ms Delay)", "setanti:1", emoji_key="shield")],
                    [tg_btn("Chế Độ Xả Thẳng Tốc Độ Cao", "setanti:0", emoji_key="bolt")],
                    [tg_btn("Quay lại Chức Năng", "tab_func_4", emoji_key="back")],
                ]
            }
            cap = (
                f"{tg_anim('shield', '🛡️')} <b>LÁ CHẮN CHỐNG ZALO CẤM CHAT BOX (VIP ANTI-BAN)</b>\n\n"
                "<blockquote>"
                "✅ <b>Zero-Wait Adaptive Backoff</b>: Không bao giờ tự delay khi nhóm đang thông suốt; chỉ giảm nhịp thông minh khi Zalo trả mã cảnh báo.\n"
                "✅ <b>Isolated Typing ThreadPool</b>: Giả lập gõ phím trên luồng nền riêng biệt, không làm nghẽn tin nhắn.\n"
                "✅ <b>Dynamic Polymorphic Tail</b>: Gắn đuôi tàng hình biến thiên giúp mỗi câu có mã băm độc nhất.\n"
                "✅ <b>Multi-Gateway Rotation</b>: Xoay vòng giữa <code>tt-group-wpa</code> và <code>wpa.chat.zalo.me</code>."
                "</blockquote>"
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
                    [tg_btn("Nạp Thêm Proxy Mới", "prx_add_prompt", emoji_key="plus")],
                    [
                        tg_btn("Test Ping Proxy", "prx_test_now", emoji_key="bolt"),
                        tg_btn("Xoá Sạch Proxy", "prx_clear_now", emoji_key="trash"),
                    ],
                    [tg_btn("Quay lại Chức Năng", "tab_func_4", emoji_key="back")],
                ]
            }
            cap = (
                f"{tg_anim('radar', '🌐')} <b>QUẢN LÝ HỒ PROXY SIÊU TỐC</b>\n\n"
                "<blockquote>"
                f"• Tổng Proxy: <b>{snap.get('total', 0)}</b> (Khỏe: <b>{snap.get('healthy', 0)}</b>)\n"
                f"• Ping nhanh nhất: <b>{snap.get('fastest_ms', 0)} ms</b>\n"
                f"• Đã định tuyến: <b>{snap.get('routed_ok', 0)} gói tin</b>"
                "</blockquote>"
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=kb)
            return

        # Khởi tạo lựa chọn Wizard cho chiến dịch (Bắt buộc chọn File tệp .txt trước khi chạy)
        wiz = self.wizard_selections.get(user_id) or {}
        wiz["fn_id"] = fn_id
        wiz.setdefault("box_id", "ALL")
        wiz.setdefault("box_name", "Tất Cả Các Box (All)")
        wiz.setdefault("acc_id", "ALL")
        wiz.setdefault("acc_name", "Tất Cả Acc Của Bạn (Đa Acc)")
        wiz.setdefault("file_name", "")
        wiz.setdefault("file_selected", False)
        wiz.setdefault("custom_text", "")
        wiz.setdefault("tag_query", "")
        self.wizard_selections[user_id] = wiz

        boxes = self._discover_all_boxes(user_id=user_id, force_refresh=False)
        files = self._get_available_txt_files()
        vis_accs = get_user_visible_accounts(user_id, enabled_only=True)
        acc_cnt = len(vis_accs)
        has_file_ready = bool((wiz.get("file_selected") and wiz.get("file_name")) or wiz.get("custom_text"))

        kb_rows = []
        if has_file_ready:
            kb_rows.append([tg_btn(f"BẮT ĐẦU CHẠY: {fn_meta['label']}", f"runfn:{fn_id}", emoji_key="rocket")])
        else:
            kb_rows.append([tg_btn("⚠️ BƯỚC 1: HÃY CHỌN FILE (.TXT) BÊN DƯỚI TRƯỚC", f"runfn:{fn_id}", emoji_key="warn")])

        file_btns = []
        for idx_f, f_item in enumerate(files[:10], 1):
            fn_s = f_item["filename"]
            d_num = f_item.get("display_num") or f_item.get("num") or idx_f
            is_sel = bool(wiz.get("file_selected") and wiz.get("file_name") == fn_s and not wiz.get("custom_text"))
            btn_lbl = f"#{d_num}: {fn_s} (Đã Chọn)" if is_sel else f"Chọn #{d_num}: {fn_s}"
            file_btns.append(
                tg_btn(btn_lbl, f"wiz_setfile:{fn_id}:{fn_s}", emoji_key="check" if is_sel else "download")
            )
        for i in range(0, len(file_btns), 2):
            kb_rows.append(file_btns[i:i + 2])

        kb_rows.append([
            tg_btn(f"Box: {wiz['box_name'][:18]}", f"wiz_pickbox:{fn_id}", emoji_key="folder"),
            tg_btn(f"Acc: {wiz['acc_name'][:18]}", f"wiz_pickacc:{fn_id}", emoji_key="users"),
        ])
        kb_rows.append([
            tg_btn("Nhập Nội Dung / @Tag", f"wiz_customtxt:{fn_id}", emoji_key="sparkle"),
            tg_btn("Dừng Tất Cả Lệnh Ngầm (.ta)", "fn_stop_all_quick", emoji_key="stop"),
        ])
        kb_rows.append([tg_btn("Quay lại Bảng Chức Năng", "tab_func_1", emoji_key="back")])

        if wiz.get("custom_text"):
            content_preview = f"✅ Văn bản tự nhập ({len(wiz['custom_text'])} ký tự)"
        elif wiz.get("file_selected") and wiz.get("file_name"):
            content_preview = f"✅ Đã chọn File: <code>{wiz.get('file_name')}</code>"
        else:
            content_preview = "⚠️ <b>Chưa chọn File .txt (Bắt buộc chọn 1 File bên dưới trước!)</b>"

        tag_info = f"\n🏷️ Tag mục tiêu: <code>{wiz['tag_query']}</code>" if wiz.get("tag_query") else ""
        poll_speed_note = "\n⚡ Tốc độ Poll: <b>0.0s KHÔNG NGHỈ (Non-Stop Liên Tục)</b>" if mode == "nhay_poll" else ""
        step_guide = (
            f"{tg_anim('rocket', '👉')} <b>Đã chọn File kịch bản!</b> Bấm <b>BẮT ĐẦU CHẠY</b> để phang ngay:"
            if has_file_ready
            else f"{tg_anim('warn', '📂')} <b>BƯỚC 1 (BẮT BUỘC):</b> Hãy bấm chọn 1 <b>File tệp (.txt)</b> bên dưới trước khi bấm Bắt Đầu Chạy:"
        )

        cap = (
            f"{tg_anim('gear', '⚙️')} <b>CẤU HÌNH: {fn_meta['label'].upper()}</b>\n"
            f"<i>{fn_meta['desc']}</i>\n\n"
            f"<blockquote>"
            f"{tg_anim('download', '📂')} File tệp (.txt): {content_preview}\n"
            f"{tg_anim('users', '👥')} Tài khoản chạy: <b>{wiz['acc_name']}</b> ({acc_cnt} Acc khả dụng)\n"
            f"{tg_anim('folder', '📦')} Mục tiêu: <b>{wiz['box_name']}</b> ({len(boxes)} Box)"
            f"{tag_info}"
            f"{poll_speed_note}\n"
            f"{tg_anim('magic', '🎨')} Màu chữ: <b>{'Đỏ Rực (db342e)' if fn_meta['color_mode'] == 'fixed' else 'Chữ Đổi Từng Màu Cầu Vồng (0% Trắng)'}</b>"
            f"</blockquote>\n\n"
            f"{step_guide}"
        )
        self.edit_menu_message(chat_id, message_id, cap, reply_markup={"inline_keyboard": kb_rows})

    def launch_wizard_campaign(self, chat_id, message_id, user_id, fn_id, cb_id=None):
        fn_meta = FUNCTION_MAP_BY_ID.get(fn_id)
        if not fn_meta:
            return
        wiz = self.wizard_selections.get(user_id) or {}
        custom_text = (wiz.get("custom_text") or "").strip()
        file_selected = bool(wiz.get("file_selected") and wiz.get("file_name"))
        if not file_selected and not custom_text:
            if cb_id:
                self.answer_callback(
                    cb_id,
                    "⚠️ Bắt buộc chọn trước 1 File tệp (.txt) bên dưới trước khi bấm Bắt Đầu Chạy!",
                    show_alert=True,
                )
            self.render_function_wizard(chat_id, message_id, user_id, fn_id)
            return

        if cb_id:
            self.answer_callback(cb_id, "🚀 Đang khởi chạy chiến dịch...")

        box_id = wiz.get("box_id") or "ALL"
        acc_sel = str(wiz.get("acc_id") or "ALL")
        file_name = wiz.get("file_name") or fn_meta.get("file_hint") or "nhay.txt"
        tag_query = (wiz.get("tag_query") or "").strip()

        try:
            import app as _main_app
            vis_accs = get_user_visible_accounts(user_id, enabled_only=True)
            vis_acc_ids = [int(a["id"]) for a in vis_accs]
            if not vis_accs:
                self.send_text(
                    chat_id,
                    f"{tg_anim('warn', '⚠️')} <b>Bạn chưa có tài khoản Zalo/Discord nào đang sống!</b>\n"
                    "• Hãy vào tab <b>Quản Lý</b> ➡️ bấm <b>Quét QR Lấy Token</b> hoặc <b>Nhập Cookie + IMEI</b> để thêm tài khoản của bạn.",
                )
                return

            boxes = self._discover_all_boxes(user_id=user_id, force_refresh=False)
            if box_id == "ALL":
                target_boxes = boxes
            else:
                target_boxes = [b for b in boxes if str(b["id"]) == str(box_id)]
                if not target_boxes:
                    target_boxes = [{
                        "id": str(box_id),
                        "name": f"Box {str(box_id)[-6:]}",
                        "platform": vis_accs[0].get("platform") or "zalo",
                        "acc_id": vis_accs[0]["id"],
                    }]

            if not target_boxes:
                self.send_text(
                    chat_id,
                    f"{tg_anim('warn', '⚠️')} <b>Chưa tìm thấy Box Zalo/Discord nào!</b>\n"
                    "• Hãy bấm nút <b>Box</b> trong bảng cấu hình ➡️ chọn <b>Nhập ID Box</b> hoặc <b>Làm Mới Box</b>.",
                )
                return

            mode = fn_meta["mode"]
            if custom_text:
                if mode == "treo_ngon":
                    blocks = [custom_text]
                else:
                    blocks = [ln.strip() for ln in custom_text.splitlines() if ln.strip()] or [custom_text]
            else:
                blocks = self._read_txt_file_blocks(file_name, mode=mode)
                if not blocks:
                    self.send_text(chat_id, f"⚠️ File <code>{file_name}</code> đang trống! Hãy chọn file khác.")
                    return

            # Dừng các tiến trình cũ đang chạy ngầm trước khi khởi chạy chiến dịch mới
            _main_app.stop_tasks_for_thread(None)
            with _main_app.SYSTEM_CFG_LOCK:
                _main_app.SYSTEM_RUNTIME_CONFIG["selected_file"] = file_name

            if tag_query:
                blocks = [f"{b} {tag_query}" for b in blocks]

            with _main_app.SYSTEM_CFG_LOCK:
                cur_delay = float(_main_app.SYSTEM_RUNTIME_CONFIG.get("delay", 0.0))
                cur_font = _main_app.SYSTEM_RUNTIME_CONFIG.get("font_style", "big_bold")

            # NÂNG CẤP TREO POLL: KHÔNG CÓ THỜI GIAN NGHỈ (DELAY = 0.0S TUYỆT ĐỐI)
            if mode == "nhay_poll":
                cur_delay = 0.0

            targets_payload = []
            for b in target_boxes:
                bid_s = str(b["id"])
                targets_payload.append({
                    "id": bid_s,
                    "thread_id": bid_s,
                    "name": b.get("name") or f"Box {bid_s[-6:]}",
                    "acc_id": b.get("acc_id"),
                    "type": "discord_channel" if (b.get("platform") == "discord") else "group",
                    "platform": b.get("platform") or "zalo",
                    "mentions": [],
                    "tag_all": bool(fn_meta.get("tag_all", False)),
                })

            if acc_sel != "ALL" and acc_sel.isdigit() and int(acc_sel) in vis_acc_ids:
                is_multi_acc = False
                sel_acc_ids = [int(acc_sel)]
                spec_aid = int(acc_sel)
            else:
                # Chỉ chạy trên các tài khoản thuộc quyền sở hữu của user_id (Admin thì chạy toàn bộ)
                is_multi_acc = len(vis_acc_ids) > 1
                sel_acc_ids = vis_acc_ids
                spec_aid = vis_acc_ids[0] if len(vis_acc_ids) == 1 else None

            tid = _main_app.start_task_programmatic(
                targets=targets_payload,
                blocks=blocks,
                delay=cur_delay,
                use_emoji=False,
                icon_count=0,
                multi_acc=is_multi_acc,
                specific_acc_id=spec_aid,
                account_ids=sel_acc_ids,
                mode=mode if mode != "special_chan" else "treo_nhay",
                color_mode=fn_meta.get("color_mode", "word_rainbow"),
                fixed_color=fn_meta.get("fixed_color", "red"),
                is_heading=True,
                antiband=(mode != "nhay_poll"),
                strip_line_num=True,
                hide_tag_all=bool(fn_meta.get("hide_tag_all", True)),
                hide_tag_name=bool(fn_meta.get("hide_tag_name", False)),
                font_style=cur_font,
            )

            speed_badge = "0.0s Không Nghỉ" if mode == "nhay_poll" else f"{cur_delay}s"
            cap = self.build_tabbed_caption(
                user_id=user_id,
                active_tab="func",
                page=1,
                extra_notice=(
                    f"{tg_anim('rocket', '🚀')} <b>ĐÃ KHỞI CHẠY {fn_meta['label'].upper()}!</b>\n"
                    f"• Mã Task: <code>#{tid}</code> • Số Acc tham gia: <b>{len(sel_acc_ids)} Acc</b>\n"
                    f"• Số Box: <b>{len(targets_payload)}</b> • Tốc độ: <b>{speed_badge}</b>\n"
                    f"• Kịch bản: <code>{file_name if not custom_text else 'Tự nhập'}</code> ({len(blocks)} câu)"
                ),
            )
            self.edit_menu_message(chat_id, message_id, cap, reply_markup=self.build_tabbed_keyboard("func", 1, user_id=user_id))
        except Exception as e:
            self.send_text(chat_id, f"❌ Lỗi khởi chạy chiến dịch: <code>{str(e)[:200]}</code>")

    # NẠP TRỰC TIẾP COOKIE + IMEI ZALO, GẮN CHỦ SỞ HỮU OWNER_TG_ID & BẬT TRỌN BỘ 32 LỆNH TRÊN ACC (.menu, .treodo, .damau, .nhaypoll, .n, .g, .t...)
    def handle_import_zalo_cookie_imei(self, chat_id, user_id, imei_str, ck_dict, meta=None, reply_to=None):
        meta = meta or {}
        wait_res = self.send_text(
            chat_id,
            f"{tg_anim('bolt', '⏳')} <b>Đang kiểm tra Cookie + IMEI, đồng bộ khóa phiên (zpw_enk) & kích hoạt 32 lệnh trực tiếp trên Acc Zalo...</b>",
            reply_to=reply_to,
        )
        wait_mid = (wait_res.get("result") or {}).get("message_id")
        try:
            chk = check_zalo_cookie_imei_live(
                imei=imei_str,
                cookies_input=ck_dict,
                zpw_enk=meta.get("zpw_enk") or "",
                user_agent=meta.get("user_agent") or "",
                uid=meta.get("uid") or "",
                db_path=DB_PATH,
            )
            eff_ck = chk.get("cookies") or ck_dict
            eff_enk = chk.get("zpw_enk") or meta.get("zpw_enk") or ""
            eff_uid = chk.get("uid") or meta.get("uid") or ""
            eff_name = chk.get("display_name") or meta.get("name") or (f"Zalo_{eff_uid[-4:]}" if eff_uid else f"Zalo_{imei_str[-4:]}")
            eff_ua = chk.get("user_agent") or meta.get("user_agent") or ""
            grp_cnt = int(chk.get("groups_count") or 0)

            acc_id = sync_zalo_account_to_web_db(
                uid=eff_uid,
                display_name=eff_name,
                imei=imei_str,
                cookies_dict=eff_ck,
                zpw_enk=eff_enk,
                user_agent=eff_ua,
                owner_tg_id=str(user_id),
            )
            self._cached_boxes_by_user.clear()

            if wait_mid:
                self.delete_msg(chat_id, wait_mid)

            st_text = (
                f"🟢 <b>SỐNG TRONG ACC 24/7 ({grp_cnt} nhóm)</b>"
                if chk.get("alive")
                else "🟡 <b>Đã lưu vào hệ thống & đang tự động đồng bộ phiên</b>"
            )
            enk_preview = eff_enk if eff_enk else "Tự động lấy khi chạy"
            msg_out = (
                f"{tg_anim('check', '✅')} <b>ĐÃ NẠP COOKIE + IMEI & KÍCH HOẠT 32 LỆNH TRÊN ACC ZALO!</b>\n\n"
                f"<blockquote>"
                f"👤 Tài khoản: <b>#{acc_id} — {eff_name}</b>\n"
                f"🆔 UID Zalo: <code>{eff_uid or 'Tự động nhận diện'}</code>\n"
                f"📡 Trạng thái: {st_text}\n"
                f"🔒 Quyền quản lý Cookie: <b>Chỉ bạn & Admin chính xem được</b>\n"
                f"💬 Lệnh trên Acc Zalo: <b>🟢 ĐÃ BẬT TRỌN BỘ 32 LỆNH</b>\n"
                f"• Gõ trực tiếp trong bất kỳ Box Zalo nào: <code>.menu</code>, <code>.treodo</code>, <code>.damau</code>, <code>.gif</code>, <code>.word</code>, <code>.nhay</code>, <code>.ngon</code>, <code>.nhaytag</code>, <code>.anall</code>, <code>.xa</code>, <code>.combo</code>, <code>.2c</code>, <code>.so</code>, <code>.nhaypoll</code> (0s không nghỉ), <code>.nhaytyping</code>, <code>.tenbox</code>, <code>.todo</code>, <code>.bank</code>, <code>.card</code>, <code>.d</code>, <code>.mau</code>, <code>.t</code>, <code>.ta</code>!"
                f"</blockquote>\n\n"
                f"🔑 <b>Token Khóa Phiên (zpw_enk):</b>\n<pre>{enk_preview}</pre>\n\n"
                f"📱 <b>IMEI (z_uuid):</b>\n<pre>{imei_str}</pre>"
            )
            self.send_text(chat_id, msg_out, reply_to=reply_to)
        except Exception as e:
            if wait_mid:
                self.delete_msg(chat_id, wait_mid)
            self.send_text(chat_id, f"❌ Lỗi khi nạp Cookie + IMEI: <code>{str(e)[:250]}</code>", reply_to=reply_to)

    # KIỂM TRA & TỰ ĐỘNG CỨU SỐNG COOKIE ZALO (ADMIN XEM TẤT CẢ, USER CHỈ XEM ACC CỦA MÌNH)
    def handle_check_all_stored_zalo_cookies(self, chat_id, user_id=ROOT_ADMIN_ID, reply_to=None):
        is_admin = is_root_admin(user_id)
        scope_title = "TOÀN BỘ HỆ THỐNG (ADMIN)" if is_admin else "CỦA BẠN"
        wait_res = self.send_text(
            chat_id,
            f"{tg_anim('search', '🔍')} <b>Đang kiểm tra trạng thái Live/Die & làm mới khóa phiên cho dàn tài khoản Zalo {scope_title}...</b>",
            reply_to=reply_to,
        )
        wait_mid = (wait_res.get("result") or {}).get("message_id")
        vis_accs = get_user_visible_accounts(user_id, enabled_only=False, platform="zalo")

        if not vis_accs:
            self.delete_msg(chat_id, wait_mid)
            self.send_text(
                chat_id,
                f"📭 <b>Chưa có tài khoản Zalo nào thuộc phạm vi {scope_title}!</b>\n"
                "👉 Hãy bấm <b>📲 Quét QR Lấy Token</b> hoặc <b>🍪 Nhập Cookie + IMEI</b> trong tab <b>Quản Lý</b>.",
                reply_to=reply_to,
            )
            return

        lines = [f"{tg_anim('chart', '📊')} <b>KẾT QUẢ KIỂM TRA {len(vis_accs)} TÀI KHOẢN ZALO {scope_title}:</b>\n<blockquote>"]
        live_cnt = 0
        for a in vis_accs:
            acc_id = a["id"]
            name = a["name"]
            uid = a["uid"]
            imei = a["imei"]
            ck_raw = a["cookies"]
            ua = a["user_agent"]
            zpw_enk_db = a["zpw_enk"]
            cmd_on = a["chat_cmd_enabled"]
            owner_id = a.get("owner_tg_id") or ROOT_ADMIN_ID

            chk = check_zalo_cookie_imei_live(
                imei=imei,
                cookies_input=ck_raw,
                zpw_enk=zpw_enk_db or "",
                user_agent=ua or "",
                uid=uid or "",
                db_path=DB_PATH,
            )
            owner_badge = f" [Owner: <code>{owner_id}</code>]" if is_admin else ""
            if chk.get("alive"):
                live_cnt += 1
                sync_zalo_account_to_web_db(
                    uid=chk.get("uid") or uid,
                    display_name=chk.get("display_name") or name,
                    imei=imei,
                    cookies_dict=chk.get("cookies") or parse_cookies_input_flexible(ck_raw),
                    zpw_enk=chk.get("zpw_enk") or zpw_enk_db or "",
                    user_agent=chk.get("user_agent") or ua or "",
                    owner_tg_id=owner_id,
                )
                grp_n = int(chk.get("groups_count") or 0)
                cmd_lbl = "💬32 Lệnh:BẬT" if cmd_on else "🔇Lệnh:TẮT"
                lines.append(
                    f"• 🟢 <b>#{acc_id} {chk.get('display_name') or name}</b> (<code>{chk.get('uid') or uid}</code>){owner_badge}\n"
                    f"  └ <b>LIVE 24/7</b> ({grp_n} nhóm) • {cmd_lbl}"
                )
            else:
                lines.append(
                    f"• 🔴 <b>#{acc_id} {name}</b> (<code>{uid}</code>){owner_badge}\n"
                    f"  └ <b>DIE</b> (<i>{chk.get('reason') or 'Hết hạn phiên'}</i>)"
                )

        lines.append("</blockquote>")
        lines.append(
            f"\n{tg_anim('check', '✅')} Tổng kết: <b>{live_cnt}/{len(vis_accs)} Acc LIVE KHỎE</b> • Đã đồng bộ chống die Cookie/IMEI & sẵn sàng chạy Đa Acc!"
        )
        self.delete_msg(chat_id, wait_mid)
        self.send_text(chat_id, "\n".join(lines), reply_to=reply_to)

    # QUÉT QR ZALO PC TRỰC TIẾP TRÊN TELEGRAM (GẮN OWNER_TG_ID RIÊNG CHO NGƯỜI QUÉT)
    def handle_zalo_qr_command(self, chat_id, user_id, msg_id=None, region_code="sg_vip", custom_pc_name=""):
        prev_stop = self.active_qr_stop_events.get(user_id)
        if prev_stop is not None:
            try:
                prev_stop.set()
            except Exception:
                pass
        my_stop_ev = threading.Event()
        self.active_qr_stop_events[user_id] = my_stop_ev
        self.active_qr_locks.add(user_id)

        def _qr_worker():
            wait_msg_id = None
            qr_msg_id = None
            qr_file_path = None
            try:
                w_res = self.send_text(
                    chat_id,
                    f"{tg_anim('bolt', '⚡')} <b>Đang khởi tạo mã QR Zalo PC độc lập (hỗ trợ quét nối tiếp Đa Acc Zalo 24/7)...</b>",
                    reply_to=msg_id,
                )
                if w_res.get("ok") and w_res.get("result"):
                    wait_msg_id = w_res["result"].get("message_id")

                def qr_callback(event):
                    nonlocal wait_msg_id, qr_msg_id
                    if my_stop_ev.is_set():
                        return
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
                            f"{tg_anim('qr', '📲')} <b>MÃ QR ĐĂNG NHẬP ZALO PC (LẤY TOKEN & SỐNG ĐA ACC)</b>\n\n"
                            f"<blockquote>"
                            f"{tg_anim('sparkle', '1️⃣')} Mở ứng dụng <b>Zalo</b> trên điện thoại.\n"
                            f"{tg_anim('target', '2️⃣')} Quét mã QR bên trên và bấm <b>Đăng nhập</b>.\n"
                            f"{tg_anim('shield', '🛡️')} Cookie quét được sẽ thuộc <b>kho riêng của bạn</b> và tự động bật 32 lệnh in-chat!"
                            f"</blockquote>"
                        )
                        p_res = self.send_photo_bytes(chat_id, bordered_png, caption=caption, reply_to=msg_id)
                        if p_res.get("ok") and p_res.get("result"):
                            qr_msg_id = p_res["result"].get("message_id")

                    elif ev_type == LoginQRCallbackEventType.QRCodeScanned:
                        dname = data.get("display_name") or "Zalo User"
                        self.send_text(
                            chat_id,
                            f"{tg_anim('radar', '📱')} <b>Đã nhận diện quét QR bởi: {dname}!</b>\n"
                            f"{tg_anim('bolt', '👉')} Vui lòng bấm <b>Đăng nhập</b> trên điện thoại để hoàn tất lấy Token...",
                            reply_to=qr_msg_id or msg_id,
                        )

                    elif ev_type == LoginQRCallbackEventType.QRCodeExpired:
                        if qr_msg_id:
                            self.delete_msg(chat_id, qr_msg_id)
                        if not my_stop_ev.is_set():
                            self.send_text(
                                chat_id,
                                f"{tg_anim('warn', '⌛')} <b>Mã QR Zalo đã hết hạn!</b> Bấm <b>Quét QR Lấy Token</b> hoặc gõ <code>/qr</code> để lấy mã mới.",
                                reply_to=msg_id,
                            )

                    elif ev_type == LoginQRCallbackEventType.QRCodeDeclined:
                        if qr_msg_id:
                            self.delete_msg(chat_id, qr_msg_id)
                        self.send_text(
                            chat_id,
                            f"{tg_anim('cross', '❌')} <b>Bạn đã từ chối xác nhận đăng nhập trên điện thoại.</b>",
                            reply_to=msg_id,
                        )

                result = login_qr_with_unique_imei(callback=qr_callback, stop_ev=my_stop_ev)

                if not result or my_stop_ev.is_set():
                    if wait_msg_id:
                        self.delete_msg(chat_id, wait_msg_id)
                    if qr_msg_id and my_stop_ev.is_set():
                        self.delete_msg(chat_id, qr_msg_id)
                    return

                cookies = result.get("cookies") or {}
                imei = result.get("imei") or ""
                uinfo = result.get("user_info") or {}
                uid = str(result.get("uid") or uinfo.get("uid") or uinfo.get("id") or "")
                dname = result.get("display_name") or uinfo.get("name") or uinfo.get("display_name") or f"Zalo_{uid[-4:]}"
                ua = result.get("user_agent") or ""
                zpw_enk = result.get("zpw_enk") or result.get("secret_key") or ""
                grp_cnt = int(result.get("groups_count") or 0)

                qr_file_path = f"qr_{imei}.png"

                acc_id = sync_zalo_account_to_web_db(
                    uid=uid,
                    display_name=dname,
                    imei=imei,
                    cookies_dict=cookies,
                    zpw_enk=zpw_enk,
                    user_agent=ua,
                    owner_tg_id=str(user_id),
                )
                self._cached_boxes_by_user.clear()

                if qr_msg_id:
                    self.delete_msg(chat_id, qr_msg_id)

                cookies_str = json.dumps(cookies, ensure_ascii=False)
                my_accs, _, _, _ = self._get_live_runtime_summary(user_id=user_id)
                msg_success = (
                    f"{tg_anim('crown', '👑')} <b>QUÉT QR LẤY TOKEN & NẠP ĐA ACC THÀNH CÔNG!</b>\n\n"
                    f"<blockquote>"
                    f"👤 Tài khoản: <b>#{acc_id} — {dname}</b>\n"
                    f"🆔 UID Zalo: <code>{uid}</code> • Nhóm: <b>{grp_cnt} Box</b>\n"
                    f"📡 Số Acc của bạn đang chạy: <b>{my_accs} Acc song song</b>\n"
                    f"💬 Lệnh trên Acc Zalo: <b>🟢 ĐÃ BẬT 32 LỆNH (.menu, .treodo, .damau, .nhaypoll, .n, .g, .t, .ta)</b>"
                    f"</blockquote>\n\n"
                    f"🔑 <b>Token Khóa Phiên (zpw_enk):</b>\n<pre>{zpw_enk or 'Đã đồng bộ tự động'}</pre>\n\n"
                    f"📱 <b>IMEI (z_uuid):</b>\n<pre>{imei}</pre>\n\n"
                    f"🍪 <b>Cookies JSON:</b>\n<pre>{cookies_str[:2600]}</pre>"
                )
                self.send_text(chat_id, msg_success, reply_to=msg_id)

                backup_txt = (
                    f"=== THONG TIN TOKEN & COOKIE ZALO PC ===\n"
                    f"Ten_Acc: {dname}\n"
                    f"UID: {uid}\n"
                    f"IMEI: {imei}\n"
                    f"Zpw_Enk: {zpw_enk}\n"
                    f"User_Agent: {ua}\n"
                    f"Cookies_JSON: {cookies_str}\n"
                    f"Nhap_Nhanh_1_Dong: {imei}|{cookies_str}\n"
                ).encode("utf-8")
                self.send_doc_bytes(
                    chat_id,
                    backup_txt,
                    filename=f"zalo_token_{uid or acc_id}.txt",
                    caption=f"📂 File sao lưu Token + Cookie + IMEI của <b>{dname}</b> (Chỉ hiển thị cho bạn & Admin chính!)",
                    reply_to=msg_id,
                )

            except Exception as e:
                if wait_msg_id:
                    self.delete_msg(chat_id, wait_msg_id)
                self.send_text(
                    chat_id,
                    f"❌ <b>Lỗi khi tạo phiên QR Zalo:</b> <code>{str(e)[:300]}</code>",
                    reply_to=msg_id,
                )
            finally:
                if self.active_qr_stop_events.get(user_id) is my_stop_ev:
                    self.active_qr_stop_events.pop(user_id, None)
                self.active_qr_locks.discard(user_id)
                if qr_file_path and os.path.exists(qr_file_path):
                    try:
                        os.remove(qr_file_path)
                    except Exception:
                        pass

        self.executor.submit(_qr_worker)

    # XỬ LÝ NÚT BẤM INLINE TRÊN TELEGRAM BOT (PHẢN HỒI TỨC THÌ 0MS & PHÂN QUYỀN ADMIN/USER NGHIÊM NGẶT)
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

        # 1. KIỂM TRA QUYỀN SỬ DỤNG BOT (CHẶN 100% NGƯỜI LẠ HOẶC ID ĐÃ BỊ ADMIN XOÁ)
        if not is_telegram_user_authorized(user_id, first_name):
            self.answer_callback(cb_id, "⛔ Bạn không có quyền sử dụng bot này!", show_alert=True)
            self.send_text(
                chat_id,
                f"⛔ <b>Bạn không có quyền sử dụng bot này.</b>\n"
                f"🆔 ID của bạn: <code>{user_id}</code>\n"
                f"👤 Liên hệ Admin chính để cấp quyền: <a href=\"tg://user?id={ROOT_ADMIN_ID}\">Bấm vào đây ↗️</a>",
            )
            return

        if data == "noop":
            self.answer_callback(cb_id)
            return

        # 2. Chuyển đổi giữa 3 Tab chính & phân trang 1..4 (Async answer_callback để edit_menu_message chạy 0ms!)
        if data.startswith("tab_func_"):
            page = int(data.split("_")[-1] or 1)
            self.answer_callback(cb_id, f"Chức năng - Trang {page}/4")
            cap = self.build_tabbed_caption(first_name, user_id, active_tab="func", page=page)
            kb = self.build_tabbed_keyboard(active_tab="func", page=page, user_id=user_id)
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=kb)
            return

        if data == "tab_mgmt":
            self.answer_callback(cb_id, "Mở Tab Quản Lý")
            cap = self.build_tabbed_caption(first_name, user_id, active_tab="mgmt")
            kb = self.build_tabbed_keyboard(active_tab="mgmt", user_id=user_id)
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=kb)
            return

        if data == "tab_util":
            self.answer_callback(cb_id, "Mở Tab Tiện Ích")
            cap = self.build_tabbed_caption(first_name, user_id, active_tab="util")
            kb = self.build_tabbed_keyboard(active_tab="util", user_id=user_id)
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=kb)
            return

        # 3. Chọn 1 trong 32 chức năng
        if data.startswith("pickfn:"):
            fn_id = data.split(":", 1)[1]
            self.answer_callback(cb_id, "Mở cấu hình chức năng...")
            self.render_function_wizard(chat_id, msg_id, user_id, fn_id)
            return

        if data.startswith("runfn:"):
            fn_id = data.split(":", 1)[1]
            self.launch_wizard_campaign(chat_id, msg_id, user_id, fn_id, cb_id=cb_id)
            return

        if data.startswith("wiz_setfile:"):
            parts = data.split(":", 2)
            fn_id, file_s = parts[1], parts[2]
            wiz = self.wizard_selections.setdefault(user_id, {})
            wiz["file_name"] = file_s
            wiz["file_selected"] = True
            wiz["custom_text"] = ""
            try:
                import app as _main_app
                with _main_app.SYSTEM_CFG_LOCK:
                    _main_app.SYSTEM_RUNTIME_CONFIG["selected_file"] = file_s
            except Exception:
                pass
            self.answer_callback(cb_id, f"✅ Đã chọn file: {file_s}")
            self.render_function_wizard(chat_id, msg_id, user_id, fn_id)
            return

        if data.startswith("wiz_pickbox:") or data.startswith("wiz_refresh_boxes:"):
            force_ref = data.startswith("wiz_refresh_boxes:")
            fn_id = data.split(":", 1)[1]
            self.answer_callback(cb_id, "🔄 Đang làm mới danh sách Box..." if force_ref else "Chọn Box mục tiêu")
            boxes = self._discover_all_boxes(user_id=user_id, force_refresh=force_ref)
            rows = [[tg_btn("Tất Cả Các Box (All)", f"wiz_setbox:{fn_id}:ALL", emoji_key="folder")]]
            for b in boxes[:14]:
                b_label = f"{b['name'][:26]} ({b['id'][-4:]})"
                rows.append([tg_btn(b_label, f"wiz_setbox:{fn_id}:{b['id']}", emoji_key="chat")])
            rows.append([
                tg_btn("Làm Mới Box", f"wiz_refresh_boxes:{fn_id}", emoji_key="bolt"),
                tg_btn("Nhập ID Box", f"wiz_manualbox:{fn_id}", emoji_key="sparkle"),
            ])
            rows.append([tg_btn("Quay lại", f"pickfn:{fn_id}", emoji_key="back")])
            cap = (
                f"{tg_anim('folder', '📦')} <b>CHỌN BOX MỤC TIÊU ({len(boxes)} Box hiện có)</b>\n\n"
                "<blockquote>• Bấm vào 1 nhóm bên dưới hoặc chọn <b>Tất Cả Các Box</b>:</blockquote>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup={"inline_keyboard": rows})
            return

        if data.startswith("wiz_pickacc:"):
            fn_id = data.split(":", 1)[1]
            self.answer_callback(cb_id, "Chọn chế độ Tài khoản chạy")
            vis_accs = get_user_visible_accounts(user_id, enabled_only=True)
            rows = [[tg_btn(f"Tất Cả Acc Của Bạn ({len(vis_accs)} Acc - Đa Acc)", f"wiz_setacc:{fn_id}:ALL", emoji_key="users")]]
            for a in vis_accs[:14]:
                aid = a["id"]
                aname = a["name"]
                aplat = a["platform"]
                rows.append([tg_btn(f"Acc #{aid}: [{str(aplat).upper()}] {aname[:22]}", f"wiz_setacc:{fn_id}:{aid}", emoji_key="cat")])
            rows.append([tg_btn("Quay lại", f"pickfn:{fn_id}", emoji_key="back")])
            cap = (
                f"{tg_anim('users', '👥')} <b>CHỌN TÀI KHOẢN CHẠY ({len(vis_accs)} Acc khả dụng)</b>\n\n"
                "<blockquote>• Chọn <b>Tất Cả Acc Của Bạn (Đa Acc)</b> để toàn bộ dàn Acc Zalo cùng xả sóng lệch pha siêu mượt (không lag, không die Cookie), hoặc chọn riêng 1 Acc:</blockquote>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup={"inline_keyboard": rows})
            return

        if data.startswith("wiz_setacc:"):
            _, fn_id, aid_str = data.split(":", 2)
            wiz = self.wizard_selections.setdefault(user_id, {})
            if aid_str == "ALL":
                wiz["acc_id"] = "ALL"
                wiz["acc_name"] = "Tất Cả Acc Của Bạn (Đa Acc)"
            else:
                vis_accs = get_user_visible_accounts(user_id, enabled_only=False)
                matched_a = next((a for a in vis_accs if str(a["id"]) == str(aid_str)), None)
                if not matched_a:
                    self.answer_callback(cb_id, "⛔ Bạn không có quyền sử dụng tài khoản này!", show_alert=True)
                    return
                wiz["acc_id"] = aid_str
                wiz["acc_name"] = f"#{aid_str} {matched_a['name']}"
            self.answer_callback(cb_id, f"Đã chọn: {wiz['acc_name']}")
            self.render_function_wizard(chat_id, msg_id, user_id, fn_id)
            return

        if data.startswith("wiz_setbox:"):
            _, fn_id, bid = data.split(":", 2)
            wiz = self.wizard_selections.setdefault(user_id, {})
            wiz["box_id"] = bid
            if bid == "ALL":
                wiz["box_name"] = "Tất Cả Các Box (All)"
            else:
                boxes = self._discover_all_boxes(user_id=user_id, force_refresh=False)
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
                extra_notice=f"{tg_anim('stop', '🛑')} <b>Đã dừng tất cả ({stopped} chiến dịch)!</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 1, user_id=user_id))
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
                extra_notice=f"{tg_anim('check', '✅')} <b>Đã cập nhật tốc độ Delay = {d_val}s trên toàn hệ thống! (Treo Poll luôn giữ 0.0s Không Nghỉ)</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4, user_id=user_id))
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
                extra_notice=f"{tg_anim('magic', '🎨')} <b>Đã kích hoạt chế độ màu: {label_c}!</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4, user_id=user_id))
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
                extra_notice=f"{tg_anim('sparkle', '🔤')} <b>Đã cập nhật kiểu chữ: {f_style}!</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4, user_id=user_id))
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
                extra_notice=f"{tg_anim('shield', '🛡️')} <b>Trạng thái Anti Cấm Chat Box: {st_lbl}</b>"
            )
            self.edit_menu_message(chat_id, msg_id, cap, reply_markup=self.build_tabbed_keyboard("func", 4, user_id=user_id))
            return

        # 4. QUẢN LÝ THÊM / XOÁ / XEM ID NGƯỜI DÙNG (CHỈ ADMIN CHÍNH 8827605973 MỚI CÓ QUYỀN CAO NHẤT)
        if data == "mgmt_add_id":
            if not is_root_admin(user_id):
                self.answer_callback(cb_id, "⛔ Quyền Admin là cao nhất! Chỉ Admin chính mới được thêm người dùng sài Bot!", show_alert=True)
                return
            self.user_states[user_id] = {"mode": "add_user_id", "menu_msg_id": msg_id}
            self.answer_callback(cb_id, "Nhập ID người dùng cần cấp quyền")
            self.send_text(
                chat_id,
                f"{tg_anim('plus', '➕')} <b>THÊM ID NGƯỜI DÙNG ĐƯỢC PHÉP SÀI BOT (CHỈ ADMIN CHÍNH)</b>\n\n"
                "<blockquote>"
                "• Hãy gửi <b>ID Telegram</b> kèm tên (tùy chọn) theo cú pháp:\n"
                "  <code>123456789 Tên Người Dùng</code>\n"
                "• Lưu ý: Người được thêm chỉ xem và dùng được Cookie do chính họ quét/nạp, không thể xem tất cả Cookie của hệ thống và không thể thêm người khác!"
                "</blockquote>",
                reply_to=msg_id,
            )
            return

        if data == "mgmt_del_id_menu":
            if not is_root_admin(user_id):
                self.answer_callback(cb_id, "⛔ Chỉ Admin chính mới có quyền xoá người dùng khỏi Bot!", show_alert=True)
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
            if not is_root_admin(user_id):
                self.answer_callback(cb_id, "⛔ Chỉ Admin chính mới xem được danh sách ID toàn hệ thống!", show_alert=True)
                return
            self.answer_callback(cb_id, "Danh sách ID được phép sài Bot")
            perms = list_telegram_permissions()
            lines = [f"{tg_anim('list', '📋')} <b>DANH SÁCH ID ĐƯỢP PHÉP SỬ DỤNG BOT:</b>\n<blockquote>"]
            for idx, p in enumerate(perms, 1):
                badge = "👑 <b>Admin Chính</b>" if p.get("is_root") else "🥷 <b>Thành Viên VIP (Chỉ xem Cookie riêng)</b>"
                lines.append(f"{idx}. {badge}: <b>{p['name']}</b> — ID: <code>{p['uid']}</code>")
            lines.append("</blockquote>\n🔒 <i>Chỉ Admin chính mới có quyền cấp/xoá quyền sài Bot!</i>")
            kb = {
                "inline_keyboard": [
                    [
                        tg_btn("Thêm ID Mới", "mgmt_add_id", emoji_key="plus"),
                        tg_btn("Xoá Quyền Sài Bot", "mgmt_del_id_menu", emoji_key="minus"),
                    ],
                    [tg_btn("Quay lại Quản Lý", "tab_mgmt", emoji_key="back")],
                ]
            }
            self.edit_menu_message(chat_id, msg_id, "\n".join(lines), reply_markup=kb)
            return

        if data == "mgmt_input_ck_im":
            self.user_states[user_id] = {"mode": "input_zalo_ck_im", "menu_msg_id": msg_id}
            self.answer_callback(cb_id, "Nhập Cookie + IMEI Zalo")
            self.send_text(
                chat_id,
                f"{tg_anim('cookie', '🍪')} <b>NHẬP COOKIE + IMEI ZALO (SÀI TRỌN BỘ 32 LỆNH TRÊN ACC)</b>\n\n"
                "<blockquote>"
                "1️⃣ <b>Cách 1 (1 dòng):</b> Dán <code>IMEI | Cookie</code> (hoặc JSON có cả Cookie & IMEI).\n"
                "2️⃣ <b>Cách 2 (2 bước):</b> Dán <b>Cookie</b> (<code>zpw_sek=...</code> hoặc <code>zpsid=...</code>) trước ➡️ Bot sẽ hỏi tiếp <b>IMEI</b>!\n"
                "✨ <i>Ngay sau khi nạp, Acc sẽ tự động lấy khóa phiên (zpw_enk) và gõ được đầy đủ 32 lệnh (<code>.menu</code>, <code>.treodo</code>, <code>.damau</code>, <code>.nhaypoll</code>, <code>.n</code>, <code>.g</code>, <code>.t</code>...) trực tiếp trên Zalo!</i>"
                "</blockquote>",
                reply_to=msg_id,
            )
            return

        if data == "mgmt_acc_files":
            self.answer_callback(cb_id, "Mở quản lý Cookie & Kho File")
            self._render_accounts_and_files_menu(chat_id, msg_id, user_id=user_id)
            return

        if data.startswith("toggle_acc_cmd:"):
            acc_id = int(data.split(":", 1)[1])
            vis_accs = get_user_visible_accounts(user_id, enabled_only=False)
            if not any(int(a["id"]) == acc_id for a in vis_accs):
                self.answer_callback(cb_id, "⛔ Bạn chỉ được chỉnh tài khoản do chính bạn quét/nạp!", show_alert=True)
                return
            new_st = 1
            try:
                conn = _open_db()
                row = conn.execute("SELECT chat_cmd_enabled FROM accounts WHERE id=?", (acc_id,)).fetchone()
                cur_st = int(row[0]) if (row and row[0] is not None) else 1
                new_st = 0 if cur_st else 1
                conn.execute("UPDATE accounts SET chat_cmd_enabled=? WHERE id=?", (new_st, acc_id))
                conn.commit()
                conn.close()
                import app as _main_app
                if hasattr(_main_app, "sync_all_zalo_listeners"):
                    _main_app.sync_all_zalo_listeners()
            except Exception:
                pass
            lbl = "🟢 BẬT nhận 32 lệnh (.menu)" if new_st else "🔇 TẮT nhận lệnh"
            self.answer_callback(cb_id, f"Acc #{acc_id}: {lbl}!", show_alert=True)
            self._render_accounts_and_files_menu(chat_id, msg_id, user_id=user_id, notice=f"✅ Đã chỉnh Acc <b>#{acc_id}</b>: <b>{lbl}</b>!")
            return

        if data.startswith("export_acc_token:"):
            acc_id = int(data.split(":", 1)[1])
            vis_accs = get_user_visible_accounts(user_id, enabled_only=False)
            target_a = next((a for a in vis_accs if int(a["id"]) == acc_id), None)
            if not target_a:
                self.answer_callback(cb_id, "⛔ Bạn chỉ được xem Cookie do chính bạn quét! Chỉ Admin chính mới xem được tất cả Cookie.", show_alert=True)
                return
            self.answer_callback(cb_id, f"Đang trích xuất Token/Cookie Acc #{acc_id}...")
            aid = target_a["id"]
            aname = target_a["name"]
            aplat = target_a["platform"]
            auid = target_a["uid"]
            aimei = target_a["imei"]
            ack = target_a["cookies"]
            aenk = target_a["zpw_enk"]
            atok = target_a["token"]
            if str(aplat).lower() == "discord":
                self.send_text(
                    chat_id,
                    f"🔑 <b>TOKEN DISCORD ACC #{aid} ({aname}):</b>\n<pre>{atok}</pre>",
                    reply_to=msg_id,
                )
            else:
                self.send_text(
                    chat_id,
                    f"{tg_anim('key', '🔑')} <b>TRỌN BỘ TOKEN & COOKIE + IMEI ZALO ACC #{aid} ({aname})</b>\n\n"
                    f"<blockquote>"
                    f"🆔 UID: <code>{auid}</code>\n"
                    f"👤 Chủ sở hữu ID: <code>{target_a.get('owner_tg_id') or ROOT_ADMIN_ID}</code>"
                    f"</blockquote>\n\n"
                    f"🔑 <b>Token (zpw_enk):</b>\n<pre>{aenk or 'Đang đồng bộ'}</pre>\n"
                    f"📱 <b>IMEI (z_uuid):</b>\n<pre>{aimei}</pre>\n"
                    f"🍪 <b>Cookies:</b>\n<pre>{str(ack or '')[:2600]}</pre>\n\n"
                    f"📋 <b>Cú pháp nạp nhanh 1 dòng:</b>\n<pre>{aimei}|{str(ack or '')[:1200]}</pre>",
                    reply_to=msg_id,
                )
            return

        if data.startswith("del_acc_now:"):
            acc_id = int(data.split(":", 1)[1])
            vis_accs = get_user_visible_accounts(user_id, enabled_only=False)
            if not any(int(a["id"]) == acc_id for a in vis_accs):
                self.answer_callback(cb_id, "⛔ Bạn không có quyền xoá tài khoản của người khác!", show_alert=True)
                return
            try:
                conn = _open_db()
                conn.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
                conn.commit()
                conn.close()
                import app as _main_app
                if hasattr(_main_app, "sync_all_zalo_listeners"):
                    _main_app.sync_all_zalo_listeners()
                elif hasattr(_main_app, "reload_accounts_to_ram"):
                    _main_app.reload_accounts_to_ram()
            except Exception:
                pass
            self._cached_boxes_by_user.clear()
            self.answer_callback(cb_id, f"🗑️ Đã xoá tài khoản #{acc_id}!", show_alert=True)
            self._render_accounts_and_files_menu(chat_id, msg_id, user_id=user_id, notice=f"✅ Đã xoá tài khoản <b>#{acc_id}</b>!")
            return

        if data == "cmd_qr_sg":
            self.answer_callback(cb_id, "Đang tạo mã QR Zalo PC...")
            self.handle_zalo_qr_command(chat_id, user_id, msg_id=msg_id)
            return

        if data == "cmd_checkzalo":
            self.answer_callback(cb_id, "Đang kiểm tra Cookie Zalo...")
            self.executor.submit(self.handle_check_all_stored_zalo_cookies, chat_id, user_id, msg_id)
            return

        if data == "cmd_status":
            self.answer_callback(cb_id, "Đang tải trạng thái...")
            self.send_status_report(chat_id, user_id=user_id, reply_to=msg_id)
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
                tg_btn(f"Xoá Quyền Sài Bot: {p['name']} ({p['uid']})", f"del_uid_now:{p['uid']}", emoji_key="trash")
            ])
        if sub_users:
            rows.append([tg_btn("Thu Hồi Toàn Bộ ID Phụ", "del_all_sub_uids", emoji_key="fire")])
        rows.append([
            tg_btn("Thêm ID Mới", "mgmt_add_id", emoji_key="plus"),
            tg_btn("Quay lại Quản Lý", "tab_mgmt", emoji_key="back"),
        ])
        notice_str = f"\n{notice}\n" if notice else ""
        if sub_users:
            body = (
                f"{tg_anim('minus', '➖')} <b>XOÁ QUYỀN SÀI BOT CỦA NGƯỜNG DÙNG ({len(sub_users)} ID phụ)</b>\n\n"
                f"<blockquote>{notice_str}"
                "• Bấm vào bất kỳ ID nào bên dưới để <b>thu hồi ngay lập tức</b> quyền sử dụng Bot của ID đó.\n"
                "• Hoặc gõ lệnh: <code>/delid &lt;ID&gt;</code>"
                "</blockquote>"
            )
        else:
            body = (
                f"{tg_anim('minus', '➖')} <b>XOÁ QUYỀN SÀI BOT CỦA NGƯỜI DÙNG</b>\n\n"
                f"<blockquote>{notice_str}"
                f"🔒 Hiện tại <b>chỉ có duy nhất Admin chính (<code>{ROOT_ADMIN_ID}</code>)</b> có quyền sử dụng Bot (chưa có ID phụ nào)."
                "</blockquote>"
            )
        self.edit_menu_message(chat_id, msg_id, body, reply_markup={"inline_keyboard": rows})

    def _render_accounts_and_files_menu(self, chat_id, msg_id, user_id=ROOT_ADMIN_ID, notice=""):
        is_admin = is_root_admin(user_id)
        vis_accs = get_user_visible_accounts(user_id, enabled_only=False)
        files = self._get_available_txt_files()
        rows = [
            [
                tg_btn("Quét QR Thêm Acc", "cmd_qr_sg", emoji_key="qr"),
                tg_btn("Nhập Cookie + IMEI", "mgmt_input_ck_im", emoji_key="cookie"),
            ]
        ]
        acc_lines = []
        for a in vis_accs[:10]:
            aid = a["id"]
            aname = a["name"]
            aplat = a["platform"]
            auid = a["uid"]
            cmd_flag = bool(a.get("chat_cmd_enabled", 1))
            owner_id = a.get("owner_tg_id") or ROOT_ADMIN_ID
            cmd_badge = "💬32 Lệnh:ON" if cmd_flag else "🔇Lệnh:OFF"
            owner_tag = f" | Owner:<code>{owner_id}</code>" if is_admin else ""
            acc_lines.append(
                f"• 🟢 <b>#{aid} [{str(aplat).upper()}] {aname}</b> (<code>{auid or '-'}</code> | {cmd_badge}{owner_tag})"
            )
            rows.append([
                tg_btn(f"Cookie #{aid} ({aname[:8]})", f"export_acc_token:{aid}", emoji_key="key"),
                tg_btn(f"{'Bật' if cmd_flag else 'Tắt'} Lệnh #{aid}", f"toggle_acc_cmd:{aid}", emoji_key="chat"),
                tg_btn(f"Xoá #{aid}", f"del_acc_now:{aid}", emoji_key="trash"),
            ])
        rows.append([
            tg_btn("Check Toàn Bộ Cookie" if is_admin else "Check Cookie Của Tôi", "cmd_checkzalo", emoji_key="search"),
            tg_btn("Quay lại Quản Lý", "tab_mgmt", emoji_key="back"),
        ])
        f_names = ", ".join(f"<code>{x['filename']}</code>" for x in files[:10]) or "Chưa có file"
        notice_s = f"\n{notice}\n" if notice else ""
        acc_summary = "\n".join(acc_lines) if acc_lines else "• <i>Bạn chưa có Cookie/Acc nào. Hãy bấm Quét QR hoặc Nhập Cookie + IMEI!</i>"
        scope_hdr = f"TẤT CẢ COOKIE HỆ THỐNG ({len(vis_accs)} Acc - Admin)" if is_admin else f"COOKIE & ACC CỦA BẠN ({len(vis_accs)} Acc)"
        cap = (
            f"{tg_anim('cat', '🗂️')} <b>{scope_hdr} & KHO FILE ({len(files)} File)</b>\n\n"
            f"<blockquote>{notice_s}"
            f"{acc_summary}"
            f"</blockquote>\n\n"
            f"📄 <b>Kho file .txt:</b> {f_names}\n"
            f"🔒 <i>{'Quyền Admin Chính: Xem & quản lý toàn bộ Cookie của mọi thành viên.' if is_admin else 'Bảo mật: Bạn chỉ xem & sử dụng được các Cookie do chính bạn quét/nạp.'}</i>"
        )
        self.edit_menu_message(chat_id, msg_id, cap, reply_markup={"inline_keyboard": rows})

    def send_status_report(self, chat_id, user_id=ROOT_ADMIN_ID, reply_to=None):
        is_admin = is_root_admin(user_id)
        vis_accs = get_user_visible_accounts(user_id, enabled_only=False)
        acc_cnt, running_cnt, color_label, delay_val = self._get_live_runtime_summary(user_id=user_id)
        perms = list_telegram_permissions()
        scope_lbl = "Tất cả Acc toàn hệ thống (Admin)" if is_admin else "Acc riêng của bạn"
        lines = [
            f"{tg_anim('radar', '📡')} <b>TRẠNG THÁI HỆ THỐNG BOT TREO 4APP 🇻🇳</b>\n",
            "<blockquote>",
            f"👑 Admin Chính: <code>{ROOT_ADMIN_ID}</code>",
            f"🔐 Số ID được phép dùng Bot: <b>{len(perms)} ID</b>" if is_admin else "🔐 Quyền hạn: <b>Thành Viên VIP (Kho Cookie độc lập)</b>",
            f"📡 {scope_lbl}: <b>{len(vis_accs)} Acc</b> ({acc_cnt} Acc bật)",
            f"🚀 Chiến dịch đang chạy: <b>{running_cnt} luồng</b>",
            f"🎨 Chế độ màu chữ: <b>{color_label}</b> • Delay: <b>{delay_val}s</b> (Poll: <b>0.0s</b>)",
            "🛡️ Anti Cấm Chat Box Zalo: <b>ĐANG BẬT (Zero-Lag Multi-Acc)</b>",
            "</blockquote>",
        ]
        if vis_accs:
            lines.append("<b>Danh sách Tài khoản hiển thị cho bạn:</b>")
            for a in vis_accs[:15]:
                st = "🟢" if a.get("enabled", 1) else "⚪"
                owner_info = f" [Owner: <code>{a.get('owner_tg_id') or ROOT_ADMIN_ID}</code>]" if is_admin else ""
                lines.append(f"• {st} <b>#{a['id']} [{str(a['platform']).upper()}] {a['name']}</b> (<code>{a['uid'] or '-'}</code>){owner_info}")
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
                self.send_text(chat_id, "⛔ Chỉ Admin chính (8827605973) mới có quyền thêm ID sài Bot!", reply_to=msg_id)
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
                    f"✅ <b>ĐÃ CẤP QUYỀN SỬ DỤNG BOT CHO {len(added_list)} ID:</b>\n• " + "\n• ".join(added_list)
                    + "\n\n🔒 <i>Người được thêm chỉ xem được Cookie họ tự quét, không xem được tất cả Cookie của hệ thống!</i>",
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
            self.send_text(chat_id, "✅ Đã lưu nội dung tự chọn! Bấm <b>BẮT ĐẦU CHẠY</b> trên bảng điều khiển để phang ngay.", reply_to=msg_id)
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
                    sync_and_keepalive_tokens_to_db(tok, owner_tg_id=str(user_id))
                    self.send_text(chat_id, f"✅ <b>Lấy Token Discord thành công & đã nạp vào kho riêng của bạn:</b>\n<pre>{tok}</pre>", reply_to=msg_id)
                else:
                    self.send_text(chat_id, f"❌ {res.get('message')}", reply_to=msg_id)
            else:
                saved = sync_and_keepalive_tokens_to_db(text, owner_tg_id=str(user_id))
                if saved:
                    self.send_text(chat_id, f"✅ Đã nạp <b>{len(saved)} Token Discord</b> vào kho riêng của bạn!", reply_to=msg_id)
                else:
                    self.send_text(chat_id, "⚠️ Không tìm thấy Token hợp lệ!", reply_to=msg_id)
            return True

        if mode == "input_zalo_ck_im":
            imei_ex, ck_dict, meta = parse_imei_and_cookie_from_text(text)
            has_ck = bool(ck_dict and ("zpw_sek" in ck_dict or "zpsid" in ck_dict))
            if has_ck and imei_ex:
                self.user_states.pop(user_id, None)
                self.executor.submit(self.handle_import_zalo_cookie_imei, chat_id, user_id, imei_ex, ck_dict, meta, msg_id)
                return True
            elif has_ck and not imei_ex:
                self.user_states[user_id] = {"mode": "input_zalo_imei_step2", "ck_dict": ck_dict, "meta": meta}
                self.send_text(
                    chat_id,
                    "🍪 <b>Đã nhận Cookie Zalo hợp lệ!</b>\n"
                    "👉 Bây giờ hãy gửi tiếp mã <b>IMEI (z_uuid)</b> của tài khoản này để hoàn tất kích hoạt 32 lệnh trong Acc:",
                    reply_to=msg_id,
                )
                return True
            elif imei_ex and not has_ck:
                self.user_states[user_id] = {"mode": "input_zalo_ck_step2", "imei": imei_ex, "meta": meta}
                self.send_text(
                    chat_id,
                    f"📱 <b>Đã nhận IMEI:</b> <code>{imei_ex}</code>\n"
                    "👉 Bây giờ hãy dán tiếp <b>Cookie Zalo</b> (<code>zpw_sek=...</code> hoặc <code>zpsid=...</code> hoặc JSON) vào đây:",
                    reply_to=msg_id,
                )
                return True
            else:
                self.user_states.pop(user_id, None)
                self.send_text(
                    chat_id,
                    "⚠️ Không tìm thấy Cookie Zalo (<code>zpw_sek</code> / <code>zpsid</code>) hoặc IMEI hợp lệ! Hãy bấm <b>Nhập Cookie + IMEI</b> để thử lại.",
                    reply_to=msg_id,
                )
                return True

        if mode == "input_zalo_imei_step2":
            saved_ck = st.get("ck_dict") or {}
            saved_meta = st.get("meta") or {}
            self.user_states.pop(user_id, None)
            imei_cand, extra_ck, extra_meta = parse_imei_and_cookie_from_text(text)
            if not imei_cand:
                imei_cand = text.strip()
            saved_ck.update(extra_ck or {})
            for k_m, v_m in (extra_meta or {}).items():
                if v_m and not saved_meta.get(k_m):
                    saved_meta[k_m] = v_m
            if len(imei_cand) >= 8:
                self.executor.submit(self.handle_import_zalo_cookie_imei, chat_id, user_id, imei_cand, saved_ck, saved_meta, msg_id)
            else:
                self.send_text(chat_id, "❌ Mã IMEI không hợp lệ! Vui lòng gửi lại Cookie + IMEI.", reply_to=msg_id)
            return True

        if mode == "input_zalo_ck_step2":
            saved_imei = st.get("imei") or ""
            saved_meta = st.get("meta") or {}
            self.user_states.pop(user_id, None)
            _, ck_dict, extra_meta = parse_imei_and_cookie_from_text(text)
            for k_m, v_m in (extra_meta or {}).items():
                if v_m and not saved_meta.get(k_m):
                    saved_meta[k_m] = v_m
            if ck_dict and ("zpw_sek" in ck_dict or "zpsid" in ck_dict):
                self.executor.submit(self.handle_import_zalo_cookie_imei, chat_id, user_id, saved_imei, ck_dict, saved_meta, msg_id)
            else:
                self.send_text(chat_id, "❌ Cookie Zalo không hợp lệ (thiếu zpw_sek hoặc zpsid)!", reply_to=msg_id)
            return True

        if mode == "getcookie":
            self.user_states.pop(user_id, None)
            if "c_user=" in text and "xs=" in text:
                saved = sync_and_keepalive_tokens_to_db(text, owner_tg_id=str(user_id))
                self.send_text(chat_id, f"✅ Đã lưu Cookie Messenger/FB ({len(saved)} Acc) vào kho của bạn!", reply_to=msg_id)
            elif "|" in text:
                parts = [p.strip() for p in text.split("|")]
                res = FacebookCookieGetter().login_facebook(parts[0], parts[1], parts[2] if len(parts) > 2 else "")
                if res.get("status") == "SUCCESS":
                    sync_and_keepalive_tokens_to_db(res["cookies"], owner_tg_id=str(user_id))
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
            lines_cnt = max(1, sum(1 for ln in raw_bytes.decode("utf-8", errors="ignore").splitlines() if ln.strip()))
            try:
                conn = _open_db()
                existing_f = conn.execute("SELECT id FROM files WHERE filename=?", (safe_fn,)).fetchone()
                if existing_f:
                    conn.execute("UPDATE files SET filepath=?, lines_count=?, created_at=? WHERE id=?", (dest, lines_cnt, time.time(), existing_f[0]))
                else:
                    conn.execute("INSERT INTO files (filename, filepath, lines_count, created_at) VALUES (?, ?, ?, ?)", (safe_fn, dest, lines_cnt, time.time()))
                conn.commit()
                conn.close()
            except Exception:
                pass
            wiz = self.wizard_selections.setdefault(user_id, {})
            wiz["file_name"] = safe_fn
            wiz["file_selected"] = True
            wiz["custom_text"] = ""
            try:
                import app as _main_app
                with _main_app.SYSTEM_CFG_LOCK:
                    _main_app.SYSTEM_RUNTIME_CONFIG["selected_file"] = safe_fn
            except Exception:
                pass
            self.send_text(
                chat_id,
                f"✅ <b>Đã nạp & tự động chọn trước file kịch bản <code>{safe_fn}</code> ({lines_cnt} dòng)!</b>\n"
                f"👉 Mở <code>/menu</code> để bấm chạy ngay.",
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

        # KIỂM TRA QUYỀN TRUY CẬP NGHIÊM NGẶT (CHỈ ADMIN 8827605973 VÀ CÁC ID ĐƯỢC ADMIN THÊM MỚI SÀI ĐƯỢC BOT)
        if not is_telegram_user_authorized(user_id, first_name):
            self.send_text(
                chat_id,
                f"⛔ <b>Bạn không có quyền sử dụng bot này.</b>\n"
                f"🆔 ID của bạn: <code>{user_id}</code>\n"
                f"👤 Liên hệ Admin chính: <a href=\"tg://user?id={ROOT_ADMIN_ID}\">Bấm vào đây ↗️</a>",
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

        # Tự động nhận diện nếu người dùng dán trực tiếp Cookie + IMEI Zalo / Token Discord vào Bot
        if not text.startswith("/") and ("zpw_sek" in text or "zpsid" in text or DISCORD_TOKEN_RE.search(text)):
            imei_extracted, ck_dict, meta = parse_imei_and_cookie_from_text(text)
            if ck_dict and ("zpw_sek" in ck_dict or "zpsid" in ck_dict):
                if imei_extracted:
                    self.executor.submit(self.handle_import_zalo_cookie_imei, chat_id, user_id, imei_extracted, ck_dict, meta, msg_id)
                else:
                    self.user_states[user_id] = {"mode": "input_zalo_imei_step2", "ck_dict": ck_dict, "meta": meta}
                    self.send_text(
                        chat_id,
                        "🍪 <b>Đã nhận diện Cookie Zalo!</b>\n"
                        "👉 Hãy gửi tiếp mã <b>IMEI (z_uuid)</b> của tài khoản này để Bot đăng nhập thẳng vào Acc và bật 32 lệnh (<code>.menu</code>, <code>.treodo</code>, <code>.nhaypoll</code>, <code>.n</code>, <code>.g</code>):",
                        reply_to=msg_id,
                    )
                return
            saved_dc = sync_and_keepalive_tokens_to_db(text, owner_tg_id=str(user_id))
            if saved_dc:
                self.send_text(chat_id, f"✅ Đã tự động nạp <b>{len(saved_dc)} tài khoản</b> vào kho riêng của bạn!", reply_to=msg_id)
                return

        parts = text.split(None, 1)
        cmd_raw = parts[0].lower().split("@")[0]
        arg_str = parts[1].strip() if len(parts) > 1 else ""

        if cmd_raw in ("/start", "/menu", "/help", "/bot"):
            self.user_states.pop(user_id, None)
            cap = self.build_tabbed_caption(first_name, user_id, active_tab="func", page=1)
            kb = self.build_tabbed_keyboard(active_tab="func", page=1, user_id=user_id)
            self.send_welcome_video_menu(chat_id, cap, reply_to=msg_id, reply_markup=kb)
            return

        if cmd_raw in ("/qr", "/zaloqr", "/scan"):
            self.handle_zalo_qr_command(chat_id, user_id, msg_id=msg_id)
            return

        if cmd_raw in ("/addck", "/cookie", "/nhapck", "/ck"):
            if arg_str:
                imei_ex, ck_dict, meta = parse_imei_and_cookie_from_text(arg_str)
                if ck_dict and ("zpw_sek" in ck_dict or "zpsid" in ck_dict) and imei_ex:
                    self.executor.submit(self.handle_import_zalo_cookie_imei, chat_id, user_id, imei_ex, ck_dict, meta, msg_id)
                    return
                elif ck_dict and ("zpw_sek" in ck_dict or "zpsid" in ck_dict) and not imei_ex:
                    self.user_states[user_id] = {"mode": "input_zalo_imei_step2", "ck_dict": ck_dict, "meta": meta}
                    self.send_text(chat_id, "🍪 <b>Đã nhận Cookie Zalo!</b> Hãy gửi tiếp mã <b>IMEI (z_uuid)</b>:", reply_to=msg_id)
                    return
            self.user_states[user_id] = {"mode": "input_zalo_ck_im"}
            self.send_text(
                chat_id,
                f"{tg_anim('cookie', '🍪')} <b>NHẬP COOKIE + IMEI ZALO (SÀI 32 LỆNH TRỰC TIẾP TRÊN ACC)</b>\n\n"
                "<blockquote>"
                "• Hãy dán <code>IMEI | Cookie</code> (hoặc dán <b>Cookie</b> trước, sau đó dán <b>IMEI</b>):\n"
                "• Sau khi nạp, tài khoản sẽ sống 24/7 trong Acc và gõ được mọi lệnh <code>.menu</code>, <code>.treodo</code>, <code>.nhaypoll</code>, <code>.n</code>, <code>.g</code>, <code>.t</code> trên Zalo!"
                "</blockquote>",
                reply_to=msg_id,
            )
            return

        if cmd_raw in ("/addid", "/cp", "/them"):
            if not is_root_admin(user_id):
                self.send_text(chat_id, "⛔ Quyền Admin là cao nhất! Chỉ Admin chính (8827605973) mới được thêm người dùng sử dụng Bot!", reply_to=msg_id)
                return
            if not arg_str:
                self.send_text(
                    chat_id,
                    "➕ <b>Cú pháp thêm ID người dùng (Chỉ Admin chính):</b>\n<code>/addid &lt;ID_Người_Dùng&gt; [Tên]</code>\nVí dụ: <code>/addid 123456789 Anh Ba</code>",
                    reply_to=msg_id,
                )
                return
            sub_p = arg_str.split(None, 1)
            t_uid = sub_p[0].strip()
            t_name = sub_p[1].strip() if len(sub_p) > 1 else f"VIP_{t_uid[-4:]}"
            grant_telegram_permission(t_uid, t_name)
            self.send_text(
                chat_id,
                f"✅ <b>Đã cấp quyền sử dụng Bot cho ID:</b> <code>{t_uid}</code> (<b>{t_name}</b>)!\n"
                "🔒 <i>Thành viên này chỉ xem và sử dụng được Cookie do chính họ quét/nạp.</i>",
                reply_to=msg_id,
            )
            return

        if cmd_raw in ("/delid", "/xq", "/xoa", "/xoaid"):
            if not is_root_admin(user_id):
                self.send_text(chat_id, "⛔ Chỉ Admin chính (8827605973) mới có quyền xoá quyền sử dụng Bot!", reply_to=msg_id)
                return
            if not arg_str:
                cap = self.build_tabbed_caption(first_name, user_id, active_tab="mgmt")
                msg_sent = self.send_welcome_video_menu(chat_id, cap, reply_to=msg_id, reply_markup=self.build_tabbed_keyboard("mgmt", user_id=user_id))
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
            if not is_root_admin(user_id):
                self.send_text(chat_id, "⛔ Chỉ Admin chính (8827605973) mới được xem danh sách ID toàn hệ thống!", reply_to=msg_id)
                return
            perms = list_telegram_permissions()
            lines = [f"{tg_anim('list', '📋')} <b>DANH SÁCH ID ĐƯỢC PHÉP SỬ DỤNG BOT:</b>\n<blockquote>"]
            for i, p in enumerate(perms, 1):
                role_b = "👑 Admin Chính" if p.get("is_root") else "🥷 Thành Viên VIP (Kho riêng)"
                lines.append(f"{i}. {role_b}: <b>{p['name']}</b> — <code>{p['uid']}</code>")
            lines.append("</blockquote>")
            self.send_text(chat_id, "\n".join(lines), reply_to=msg_id)
            return

        if cmd_raw in ("/checkzalo", "/check"):
            self.executor.submit(self.handle_check_all_stored_zalo_cookies, chat_id, user_id, msg_id)
            return

        if cmd_raw in ("/status", "/ping"):
            self.send_status_report(chat_id, user_id=user_id, reply_to=msg_id)
            return

        if cmd_raw in ("/stopall", "/ta", "/stop"):
            try:
                import app as _main_app
                stopped = _main_app.stop_tasks_for_thread(None)
            except Exception:
                stopped = 0
            self.send_text(chat_id, f"{tg_anim('stop', '🛑')} <b>Đã dừng khẩn cấp toàn bộ ({stopped} chiến dịch)!</b>", reply_to=msg_id)
            return

        # Mặc định hiển thị bảng điều khiển Video
        cap = self.build_tabbed_caption(first_name, user_id, active_tab="func", page=1)
        kb = self.build_tabbed_keyboard(active_tab="func", page=1, user_id=user_id)
        self.send_welcome_video_menu(chat_id, cap, reply_to=msg_id, reply_markup=kb)

    def _safe_process_update(self, upd):
        try:
            self.process_update(upd)
        except Exception as e:
            self.last_error = str(e)

    def run_forever(self):
        self.running = True
        self.last_poll_ok_ts = time.time()
        self.clear_webhook_and_init()
        fail_streak = 0
        while self.running:
            try:
                self.last_poll_ok_ts = time.time()
                res = self.api_call(
                    "getUpdates",
                    {
                        "offset": self.offset,
                        "timeout": 15,
                        "allowed_updates": ["message", "edited_message", "callback_query"],
                    },
                    timeout=(5.0, 20.0),
                    use_poll_session=True,
                )
                self.last_poll_ok_ts = time.time()
                if res.get("ok") and isinstance(res.get("result"), list):
                    fail_streak = 0
                    for upd in res["result"]:
                        uid_upd = upd.get("update_id", 0)
                        if uid_upd >= self.offset:
                            self.offset = uid_upd + 1
                        self.executor.submit(self._safe_process_update, upd)
                else:
                    fail_streak += 1
                    desc_err = str(res.get("description") or "").lower()
                    if "conflict" in desc_err or "webhook" in desc_err:
                        try:
                            self.api_call("deleteWebhook", {"drop_pending_updates": False}, timeout=6, use_poll_session=True)
                        except Exception:
                            pass
                    if fail_streak >= 3:
                        try:
                            self.poll_session.close()
                        except Exception:
                            pass
                        self.poll_session = self._create_isolated_session()
                        fail_streak = 0
                    time.sleep(0.5)
            except Exception as e:
                self.last_error = str(e)
                fail_streak += 1
                try:
                    self.poll_session.close()
                except Exception:
                    pass
                self.poll_session = self._create_isolated_session()
                time.sleep(0.8)


_BOT_INSTANCE = None
_BOT_LOCK = threading.RLock()
_BOT_WATCHDOG_STARTED = False


def _ensure_internal_bot_watchdog():
    global _BOT_WATCHDOG_STARTED, _BOT_INSTANCE
    if _BOT_WATCHDOG_STARTED:
        return
    _BOT_WATCHDOG_STARTED = True

    def _watchdog():
        time.sleep(8.0)
        while True:
            try:
                inst = _BOT_INSTANCE
                if inst is not None and inst.running:
                    age = time.time() - float(getattr(inst, "last_poll_ok_ts", time.time()))
                    pt = getattr(inst, "poll_thread", None)
                    if age > 35.0 or (pt is not None and not pt.is_alive()):
                        start_background_telegram_bot(inst.token, force_restart=True)
            except Exception:
                pass
            time.sleep(8.0)

    threading.Thread(target=_watchdog, daemon=True, name="TelegramBotWatchdog").start()


def start_background_telegram_bot(token=TELEGRAM_BOT_TOKEN, force_restart=False):
    global _BOT_INSTANCE
    _ensure_internal_bot_watchdog()
    with _BOT_LOCK:
        if _BOT_INSTANCE is not None and _BOT_INSTANCE.running and not force_restart:
            pt = getattr(_BOT_INSTANCE, "poll_thread", None)
            age = time.time() - float(getattr(_BOT_INSTANCE, "last_poll_ok_ts", time.time()))
            if (pt is None or pt.is_alive()) and age <= 35.0:
                return _BOT_INSTANCE
        if _BOT_INSTANCE is not None:
            _BOT_INSTANCE.running = False
            try:
                _BOT_INSTANCE.poll_session.close()
            except Exception:
                pass
        runner = DirectTelegramBotRunner(token=token or TELEGRAM_BOT_TOKEN)
        t = threading.Thread(target=runner.run_forever, daemon=True, name="TelegramBot4AppRunner")
        runner.poll_thread = t
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
