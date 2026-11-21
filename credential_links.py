"""Root-owned account links supplied through the control panel.

Credentials remain encrypted in SQLite and never appear in list responses.
Linking verifies the current session; it does not launch a chat worker.
"""
import base64
import hashlib
import html
import re
import time
from urllib.parse import urlsplit

import requests
from cryptography.fernet import Fernet


def ensure_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS credential_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        platform TEXT NOT NULL,
        uid TEXT NOT NULL,
        name TEXT NOT NULL,
        encrypted TEXT NOT NULL,
        updated REAL NOT NULL,
        UNIQUE(owner, platform, uid)
    )""")
    connection.execute("CREATE INDEX IF NOT EXISTS credential_links_owner ON credential_links(owner, platform)")


def _cipher(secret_key):
    if not secret_key:
        raise ValueError("Máy chủ thiếu SECRET_KEY cố định")
    digest = hashlib.sha256(("credential-links:" + secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def verify_discord(token, *, http=requests):
    raw = str(token or "").strip()
    if not raw or len(raw) > 500 or any(char.isspace() for char in raw):
        raise ValueError("Token Discord không hợp lệ")
    try:
        response = http.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": raw, "Accept": "application/json"},
            timeout=(3, 8), allow_redirects=False,
        )
        if response.status_code != 200:
            raise ValueError("Discord không xác nhận token này")
        profile = response.json()
    except requests.RequestException as error:
        raise ValueError("Không kết nối được Discord để kiểm tra token") from error
    except ValueError as error:
        raise ValueError("Discord trả về hồ sơ không hợp lệ") from error
    if not isinstance(profile, dict):
        raise ValueError("Discord trả về hồ sơ không hợp lệ")
    uid = str(profile.get("id") or "")
    if not uid.isdigit():
        raise ValueError("Discord không trả về ID tài khoản")
    name = str(profile.get("global_name") or profile.get("username") or "Discord")[:100]
    return uid, name, raw


def verify_facebook(cookie, *, http=requests):
    raw = str(cookie or "").strip()
    if len(raw) > 16000 or "\n" in raw or "\r" in raw:
        raise ValueError("Cookie Facebook không hợp lệ")
    pairs = {}
    for part in raw.split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and re.fullmatch(r"[A-Za-z0-9_]+", name) and value:
            pairs[name] = value
    uid = pairs.get("c_user", "")
    if not uid.isdigit() or not pairs.get("xs"):
        raise ValueError("Cookie cần có c_user và xs")
    normalized = "; ".join(f"{key}={value}" for key, value in pairs.items())
    try:
        response = http.get(
            "https://mbasic.facebook.com/profile.php",
            headers={"Cookie": normalized, "User-Agent": "Mozilla/5.0"},
            timeout=(3, 8), allow_redirects=True,
        )
    except requests.RequestException as error:
        raise ValueError("Không kết nối được Facebook để kiểm tra cookie") from error
    final = urlsplit(response.url)
    if (response.status_code != 200 or final.scheme != "https" or
            final.hostname not in ("facebook.com", "www.facebook.com", "mbasic.facebook.com") or
            any(segment in final.path.lower() for segment in ("login", "checkpoint", "recover"))):
        raise ValueError("Facebook chưa xác nhận phiên cookie này")
    match = re.search(r"<title[^>]*>([^<]+)</title>", response.text[:200000], re.I)
    name = html.unescape(match.group(1).strip())[:100] if match else "Facebook"
    return uid, name, normalized


def save(connection, owner, platform, secret, secret_key, *, http=requests):
    if platform == "discord":
        uid, name, normalized = verify_discord(secret, http=http)
    elif platform == "facebook":
        uid, name, normalized = verify_facebook(secret, http=http)
    else:
        raise ValueError("Nền tảng không được hỗ trợ")
    encrypted = _cipher(secret_key).encrypt(normalized.encode()).decode()
    connection.execute("""INSERT INTO credential_links(owner,platform,uid,name,encrypted,updated)
        VALUES(?,?,?,?,?,?) ON CONFLICT(owner,platform,uid)
        DO UPDATE SET name=excluded.name,encrypted=excluded.encrypted,updated=excluded.updated""",
        (str(owner), platform, uid, name, encrypted, time.time()))
    connection.commit()
    return {"platform": platform, "uid": uid, "name": name}


def list_links(connection, owner):
    return [dict(row) for row in connection.execute(
        "SELECT id,platform,uid,name,updated FROM credential_links WHERE owner=? ORDER BY updated DESC",
        (str(owner),),
    )]


def delete(connection, owner, link_id):
    result = connection.execute(
        "DELETE FROM credential_links WHERE id=? AND owner=?", (int(link_id), str(owner)),
    )
    connection.commit()
    return bool(result.rowcount)
