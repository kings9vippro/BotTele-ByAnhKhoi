"""Root-owned account links supplied through the control panel.

Credentials remain encrypted in SQLite and never appear in list responses.
Linking verifies the current session; it does not launch a chat worker.
"""
import base64
import hashlib
import html
import json
import re
import time
from urllib.parse import urljoin, urlsplit

import requests
from cryptography.fernet import Fernet, InvalidToken


class CredentialRejected(ValueError):
    """The provider rejected a credential or the input is malformed."""


class CredentialUnavailable(ValueError):
    """The provider did not give a conclusive answer."""


def ensure_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS credential_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        platform TEXT NOT NULL,
        uid TEXT NOT NULL,
        name TEXT NOT NULL,
        encrypted TEXT NOT NULL,
        updated REAL NOT NULL,
        checked_at REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'unknown',
        kind TEXT NOT NULL DEFAULT '',
        last_error TEXT NOT NULL DEFAULT '',
        UNIQUE(owner, platform, uid)
    )""")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(credential_links)")}
    for column, definition in {
        "checked_at": "REAL NOT NULL DEFAULT 0",
        "status": "TEXT NOT NULL DEFAULT 'unknown'",
        "kind": "TEXT NOT NULL DEFAULT ''",
        "last_error": "TEXT NOT NULL DEFAULT ''",
    }.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE credential_links ADD COLUMN {column} {definition}")
    connection.execute("CREATE INDEX IF NOT EXISTS credential_links_owner ON credential_links(owner, platform)")


def _cipher(secret_key):
    if not secret_key:
        raise CredentialUnavailable("Máy chủ thiếu SECRET_KEY cố định")
    digest = hashlib.sha256(("credential-links:" + secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _discord_authorization(token, kind):
    raw = str(token or "").strip()
    selected = str(kind or "user").strip().lower()
    if raw.lower().startswith("authorization:"):
        raw = raw.partition(":")[2].strip()
    if raw.startswith("Bot "):
        raw, selected = raw[4:].strip(), "bot"
    if selected not in ("user", "bot") or not raw or len(raw) > 500 or any(char.isspace() for char in raw):
        raise CredentialRejected("Token Discord không hợp lệ")
    return ("Bot " if selected == "bot" else "") + raw, selected


def verify_discord(token, *, kind="user", http=requests):
    authorization, kind = _discord_authorization(token, kind)
    try:
        response = http.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": authorization, "Accept": "application/json"},
            timeout=(3, 8), allow_redirects=False,
        )
    except requests.RequestException as error:
        raise CredentialUnavailable("Không kết nối được Discord để kiểm tra token") from error
    if response.status_code in (401, 403):
        raise CredentialRejected("Discord không chấp nhận token này")
    if response.status_code == 429 or response.status_code >= 500:
        raise CredentialUnavailable("Discord tạm thời chưa thể kiểm tra token")
    if response.status_code != 200:
        raise CredentialRejected("Discord không chấp nhận token này")
    try:
        profile = response.json()
    except ValueError as error:
        raise CredentialUnavailable("Discord trả về hồ sơ không hợp lệ") from error
    if not isinstance(profile, dict):
        raise CredentialUnavailable("Discord trả về hồ sơ không hợp lệ")
    uid = str(profile.get("id") or "")
    if not uid.isdigit():
        raise CredentialUnavailable("Discord không trả về ID tài khoản")
    name = str(profile.get("global_name") or profile.get("username") or "Discord")[:100]
    return uid, name, authorization, kind


def normalize_facebook_cookie(raw_cookie):
    """Accept a Cookie header, a JSON map/list, or a Netscape cookie export."""
    raw = str(raw_cookie or "").strip()
    if not raw or len(raw) > 32000 or "\r" in raw:
        raise CredentialRejected("Cookie Facebook không hợp lệ")
    if raw.lower().startswith("cookie:"):
        raw = raw.partition(":")[2].strip()
    pairs = {}
    if raw.startswith(("{", "[")):
        try:
            data = json.loads(raw)
        except ValueError as error:
            raise CredentialRejected("Cookie JSON không hợp lệ") from error
        if isinstance(data, dict):
            entries = data.items()
        elif isinstance(data, list):
            entries = ((item.get("name"), item.get("value")) for item in data if isinstance(item, dict))
        else:
            raise CredentialRejected("Cookie JSON không hợp lệ")
        for name, value in entries:
            if isinstance(name, str) and isinstance(value, (str, int)):
                pairs[name] = str(value)
    elif "\t" in raw and "# Netscape" in raw:
        for line in raw.splitlines():
            columns = line.split("\t")
            domain = columns[0].removeprefix("#HttpOnly_").lstrip(".").lower() if columns else ""
            if len(columns) >= 7 and (domain == "facebook.com" or domain.endswith(".facebook.com")):
                pairs[columns[5]] = columns[6]
    else:
        for part in re.split(r"[;\n]+", raw):
            name, sep, value = part.strip().partition("=")
            if sep:
                pairs[name.strip()] = value.strip()
    valid = {key: value for key, value in pairs.items()
             if isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_]+", key)
             and value and not any(char in value for char in "\r\n;")}
    uid = valid.get("c_user", "")
    if not uid.isdigit() or not valid.get("xs"):
        raise CredentialRejected("Cookie cần có c_user và xs")
    return uid, "; ".join(f"{key}={value}" for key, value in valid.items())


def _facebook_profile(cookie, http):
    """Never forward the Cookie header to a redirect outside Facebook."""
    url = "https://mbasic.facebook.com/profile.php"
    allowed = {"facebook.com", "www.facebook.com", "mbasic.facebook.com", "m.facebook.com"}
    for _ in range(3):
        try:
            response = http.get(url, headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0"},
                                timeout=(2, 4), allow_redirects=False)
        except requests.RequestException as error:
            raise CredentialUnavailable("Không kết nối được Facebook để kiểm tra cookie") from error
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location", "")
            if not location:
                raise CredentialUnavailable("Facebook chưa trả về kết quả kiểm tra")
            url = urljoin(url, location)
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname not in allowed:
                raise CredentialRejected("Facebook chuyển phiên tới trang không hợp lệ")
            if any(part in parsed.path.lower() for part in ("login", "checkpoint", "recover")):
                raise CredentialRejected("Facebook yêu cầu đăng nhập lại")
            continue
        reported_url = getattr(response, "url", None)
        return response, reported_url if isinstance(reported_url, str) else url
    raise CredentialUnavailable("Facebook chuyển hướng quá nhiều lần")


def verify_facebook(cookie, *, http=requests):
    uid, normalized = normalize_facebook_cookie(cookie)
    response, url = _facebook_profile(normalized, http)
    parsed = urlsplit(url)
    if response.status_code in (429, 500, 502, 503, 504):
        raise CredentialUnavailable("Facebook tạm thời chưa thể kiểm tra cookie")
    if (response.status_code != 200 or parsed.scheme != "https" or parsed.hostname not in
            ("facebook.com", "www.facebook.com", "mbasic.facebook.com", "m.facebook.com") or
            any(part in parsed.path.lower() for part in ("login", "checkpoint", "recover"))):
        raise CredentialRejected("Facebook chưa xác nhận phiên cookie này")
    page = response.text[:200000]
    if re.search(r'<form[^>]+(?:id=["\']login|action=["\'][^"\']*/login)', page, re.I):
        raise CredentialRejected("Facebook yêu cầu đăng nhập lại")
    match = re.search(r"<title[^>]*>([^<]+)</title>", page, re.I)
    name = html.unescape(match.group(1).strip())[:100] if match else "Facebook"
    return uid, name, normalized, "cookie"


def _verify(platform, secret, kind, http):
    if platform == "discord":
        return verify_discord(secret, kind=kind, http=http)
    if platform == "facebook":
        return verify_facebook(secret, http=http)
    raise CredentialRejected("Nền tảng không được hỗ trợ")


def save(connection, owner, platform, secret, secret_key, *, kind="user", http=requests):
    uid, name, normalized, credential_kind = _verify(platform, secret, kind, http)
    encrypted = _cipher(secret_key).encrypt(normalized.encode()).decode()
    now = time.time()
    connection.execute("""INSERT INTO credential_links(owner,platform,uid,name,encrypted,updated)
        VALUES(?,?,?,?,?,?) ON CONFLICT(owner,platform,uid)
        DO UPDATE SET name=excluded.name,encrypted=excluded.encrypted,updated=excluded.updated""",
        (str(owner), platform, uid, name, encrypted, now))
    connection.execute("UPDATE credential_links SET checked_at=?,status='verified',kind=?,last_error='' "
                       "WHERE owner=? AND platform=? AND uid=?",
                       (now, credential_kind, str(owner), platform, uid))
    connection.commit()
    return {"platform": platform, "uid": uid, "name": name, "status": "verified", "kind": credential_kind}


def list_links(connection, owner):
    return [dict(row) for row in connection.execute(
        "SELECT id,platform,uid,name,updated,checked_at,status,kind,last_error "
        "FROM credential_links WHERE owner=? ORDER BY updated DESC",
        (str(owner),),
    )]


def recheck(connection, owner, link_id, secret_key, *, http=requests):
    row = connection.execute("SELECT id,platform,uid,encrypted,kind FROM credential_links "
                             "WHERE id=? AND owner=?", (int(link_id), str(owner))).fetchone()
    if row is None:
        raise CredentialRejected("Không tìm thấy tài khoản")
    try:
        secret = _cipher(secret_key).decrypt(row["encrypted"].encode()).decode()
    except (InvalidToken, UnicodeError) as error:
        raise CredentialUnavailable("Không giải mã được phiên; kiểm tra SECRET_KEY") from error
    try:
        uid, name, _, kind = _verify(row["platform"], secret, row["kind"] or "user", http)
        if uid != row["uid"]:
            raise CredentialRejected("Phiên đã chuyển sang tài khoản khác; hãy thêm lại")
    except (CredentialRejected, CredentialUnavailable) as error:
        status = "invalid" if isinstance(error, CredentialRejected) else "unknown"
        connection.execute("UPDATE credential_links SET status=?,checked_at=?,last_error=? WHERE id=?",
                           (status, time.time(), str(error), row["id"]))
        connection.commit()
        return {"id": row["id"], "status": status, "error": str(error)}
    connection.execute("UPDATE credential_links SET name=?,kind=?,status='verified',checked_at=?,last_error='' WHERE id=?",
                       (name, kind, time.time(), row["id"]))
    connection.commit()
    return {"id": row["id"], "status": "verified", "name": name}


def delete(connection, owner, link_id):
    result = connection.execute(
        "DELETE FROM credential_links WHERE id=? AND owner=?", (int(link_id), str(owner)),
    )
    connection.commit()
    return bool(result.rowcount)
