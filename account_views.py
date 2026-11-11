"""Read-only, cookie-scoped Zalo group views for Mini App and Telegram.

Only the selected account's cached groups and known-group map are considered.
No live network calls are made on the Telegram interactive command path.
"""
from __future__ import annotations

import math


def groups_for_account(account, cache, known):
    aid = str(account.get("id") or "")
    uid = str(account.get("uid") or "")
    imei = str(account.get("imei") or "")
    record = cache.get(uid) or cache.get(imei)
    cached = record.get("data") if isinstance(record, dict) else (
        record[1] if isinstance(record, (list, tuple)) and len(record) > 1 else []
    )
    rows = {}
    for item in cached or []:
        if not isinstance(item, dict):
            continue
        gid = str(item.get("id") or "").strip()
        if gid:
            rows[gid] = {"id":gid,"name":str(item.get("name") or f"Box {gid[-6:]}"),
                         "account_id":aid,"platform":"zalo"}
    for gid in known.get(uid, set()) | known.get(imei, set()):
        key = str(gid or "").strip()
        if key and key not in rows:
            rows[key] = {"id":key,"name":f"Box Zalo {key[-6:]}",
                         "account_id":aid,"platform":"zalo"}
    return sorted(rows.values(),key=lambda x:(x["name"].casefold(),x["id"]))


def paginate(rows,page=1,size=12):
    try:
        p=int(page);s=int(size)
    except (TypeError, ValueError) as exc:
        raise ValueError("Trang không hợp lệ") from exc
    if p < 1 or s < 1 or s > 40:
        raise ValueError("Trang không hợp lệ")
    total=len(rows);pages=max(1,math.ceil(total/s))
    if p>pages:
        raise ValueError("Trang vượt phạm vi")
    offset=(p-1)*s
    return {"page":p,"total_pages":pages,"total":total,
            "rows":rows[offset:offset+s],"has_next":p<pages,"has_previous":p>1}


def task_belongs_to_account(task, account_id):
    wanted=str(account_id)
    return wanted in {str(x) for x in task.get("account_ids",[])}


# Explicit refresh requests never block the interactive Telegram/Zalo update loop.
from concurrent.futures import ThreadPoolExecutor
import threading
import time
_REFRESH_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ZaloGroupDiscovery")
_REFRESH_LOCK = threading.Lock()
_REFRESH_LAST = {}
_REFRESH_SLOTS = threading.BoundedSemaphore(2)


def request_group_refresh(account_id, work, done=None, cooldown=35):
    """Debounced, bounded background refresh for exactly one cookie."""
    key = str(account_id)
    with _REFRESH_LOCK:
        now = time.monotonic()
        if now - _REFRESH_LAST.get(key, 0) < cooldown:
            return False
        if not _REFRESH_SLOTS.acquire(blocking=False):
            return False
        _REFRESH_LAST[key] = now

    def worker():
        ok = False
        try:
            work()
            ok = True
        except Exception:
            # Credential-bearing provider exceptions must not reach chat or logs.
            pass
        finally:
            _REFRESH_SLOTS.release()
            if done:
                try:
                    done(ok)
                except Exception:
                    pass
    try:
        _REFRESH_POOL.submit(worker)
    except RuntimeError:
        _REFRESH_SLOTS.release()
        return False
    return True