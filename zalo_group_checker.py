"""Zalo group-checker core integrated with GLAZE.

Adapted from the user-provided Zalo watcher: no second login listener, no
credential files, no unsolicited group joins, and no background thread spawn.
Use the existing account-scoped client and CanhTreoWatchdogEngine instead.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta

VIETNAM = timezone(timedelta(hours=7))
MIN_TIMEOUT_SEC = 30
MAX_TIMEOUT_SEC = 86400
DEFAULT_TIMEOUT_SEC = 90
PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def validate_timeout(value):
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Thời gian canh không hợp lệ") from exc
    if not math.isfinite(timeout) or not MIN_TIMEOUT_SEC <= timeout <= MAX_TIMEOUT_SEC:
        raise ValueError("Thời gian canh phải từ 30 giây đến 24 giờ")
    return timeout


def activity_clock(last_activity, timeout=DEFAULT_TIMEOUT_SEC, now=None, has_message=True):
    """Keep the original last-message timestamp, even after an alert."""
    now = datetime.now(timezone.utc).timestamp() if now is None else float(now)
    timeout = validate_timeout(timeout)
    if not has_message or last_activity is None:
        return {"status": "awaiting_message", "last_message_at": None,
                "silence_seconds": None, "remaining_seconds": None, "inactive_since": None}
    last = float(last_activity)
    elapsed = max(0., now - last)
    return {"status": "silent" if elapsed >= timeout else "monitoring",
            "last_message_at": last, "silence_seconds": round(elapsed, 1),
            "remaining_seconds": max(0., round(timeout - elapsed, 1)),
            "inactive_since": last + timeout if elapsed >= timeout else None}


def vietnam_time(timestamp):
    if timestamp is None:
        return "Chưa có tin nhắn"
    return datetime.fromtimestamp(float(timestamp), tz=VIETNAM).strftime("%H:%M:%S %d/%m/%Y (GMT+7)")


def paginate_groups(groups, page=1, page_size=PAGE_SIZE):
    try:
        page = int(page)
        size = int(page_size)
    except (ValueError, TypeError) as exc:
        raise ValueError("Trang không hợp lệ") from exc
    if page < 1 or not 1 <= size <= MAX_PAGE_SIZE:
        raise ValueError("Giới hạn trang không hợp lệ")
    cleaned = []
    seen = set()
    for item in groups:
        if not isinstance(item, dict):
            continue
        uid = str(item.get("id") or "").strip()
        if not uid or uid in seen:
            continue
        seen.add(uid)
        cleaned.append({k: item[k] for k in ("id", "name", "platform", "account_id", "members") if k in item})
    cleaned.sort(key=lambda x: (str(x.get("name") or "").casefold(), str(x["id"])))
    total = len(cleaned)
    page_count = max(1, math.ceil(total / size))
    if page > page_count:
        return {"boxes": [], "page": page, "page_size": size, "total": total, "total_pages": page_count, "has_more": False}
    start = (page-1)*size
    return {"boxes": cleaned[start:start+size], "page": page, "page_size": size,
            "total": total, "total_pages": page_count, "has_more": page < page_count}