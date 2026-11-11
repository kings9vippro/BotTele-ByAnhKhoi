"""Observable cooperative cancellation and normalized task registry.

The application has two deliberately different task engines:

* legacy Zalo automation tasks are cooperative, process-local workers mirrored
  into the ``tasks`` table; and
* Discord webhook notifications are durable SQLite queue records.

They must not be conflated into one scheduler, but callers need one read model
to display and safely route controls for both.  This module owns that read
model.  It never claims a process-local task can survive a restart.
"""
import time


_DURABLE_STATUS = {
    "CREATED": "created", "QUEUED": "queued", "RUNNING": "running",
    "PAUSED": "paused", "RETRYING": "retrying", "COMPLETED": "completed",
    "FAILED": "failed", "CANCELLED": "cancelled", "CANCELLING": "stopping",
    "UNKNOWN": "unknown",
}


def task_reference(engine, task_id):
    """Return an unambiguous public task reference without changing raw IDs."""
    return f"{engine}:{str(task_id)}"


def parse_task_reference(reference):
    """Parse an engine-qualified reference; reject ambiguous legacy raw IDs."""
    engine, separator, task_id = str(reference or "").partition(":")
    if not separator or engine not in {"legacy", "durable"} or not task_id:
        raise ValueError("Mã tác vụ không hợp lệ")
    return engine, task_id


def _actions(engine, status):
    if engine == "durable":
        return {
            "queued": ["pause", "stop"],
            "retrying": ["pause", "stop"],
            "paused": ["resume", "stop"],
            "running": ["stop"],
            "failed": ["retry"],
        }.get(status, [])
    return ["stop"] if status == "running" else []


def _legacy_persistence(saved):
    """Describe, rather than overstate, legacy task recovery capabilities."""
    if saved.get("persisted"):
        return "snapshot_only"
    return "process_local"


def legacy_recovery_state(persisted_status):
    """Return an honest legacy status after a process restart.

    The legacy engine has no durable executable worker.  A row that was
    ``running`` or ``stopping`` when the process disappeared therefore has an
    unknown outcome, not a successful stop and not a resumable task.
    """
    status = str(persisted_status or "stopped").strip().lower() or "stopped"
    return "interrupted" if status in {"running", "stopping"} else status


def task_state(active, saved):
    # A process-local worker cannot resume after a process restart.  Startup
    # recovery may retain its persisted snapshot for diagnostics, but must not
    # render that snapshot as a clean completion.
    if saved.get("recovered_after_restart"):
        return "interrupted"
    event = active.get("stop")
    thread = active.get("thread")
    if event is not None and event.is_set():
        return "stopping" if thread is not None and thread.is_alive() else "stopped"
    if active:
        return "running"
    return legacy_recovery_state(saved.get("status"))


def cancel_one(task_id, active_tasks, saved_tasks, lock):
    with lock:
        active = active_tasks.get(task_id) or {}
        saved = saved_tasks.get(task_id)
        if not active and saved is None:
            return None
        event = active.get("stop")
        if event is not None:
            event.set()
        if saved is None:
            saved = {"id": task_id, "meta": {}, "persisted": False}
            saved_tasks[task_id] = saved
        state = task_state(active, saved) if active else "stopped"
        saved.update(status=state, running=False, dirty=True)
        saved.setdefault("stop_requested_at", time.time())
        if state == "stopped":
            saved.setdefault("finished_at", time.time())
        return state


def task_snapshots(active_tasks, saved_tasks, accounts, lock):
    """Return legacy task snapshots with explicit execution/persistence facts.

    ``status`` remains the existing lower-case legacy status for backwards
    compatibility. New consumers should use ``engine``, ``task_ref``,
    ``available_actions`` and ``persistence`` instead of inferring behavior
    from the task ID or a decorative UI control.
    """
    now = time.time()
    names = {str(account["id"]): account.get("name") or f"#{account['id']}" for account in accounts}
    with lock:
        keys = set(active_tasks) | set(saved_tasks)
        snapshots = []
        for task_id in keys:
            active = active_tasks.get(task_id) or {}
            saved = saved_tasks.get(task_id) or {}
            meta = saved.get("meta") or {}
            mode = saved.get("type") or active.get("mode") or (active.get("opts") or {}).get("mode") or active.get("source") or "task"
            targets = list(meta.get("targets") or active.get("targets") or [])
            target_names = list(meta.get("target_names") or targets)
            ids = list(meta.get("account_ids") or ([active["acc_id"]] if active.get("acc_id") else []))
            started_at = float(saved.get("started_at") or active.get("started_at") or now)
            state = task_state(active, saved)
            if saved and saved.get("status") != state:
                saved.update(status=state, dirty=True)
            if state == "stopped" and saved.get("stop_requested_at") and not saved.get("finished_at"):
                saved.update(finished_at=now, dirty=True)
            snapshots.append({"id": str(task_id), "task_ref": task_reference("legacy", task_id),
                "engine": "legacy", "execution_source": str(meta.get("source") or active.get("source") or "legacy"),
                "persistence": _legacy_persistence(saved), "persistent": False,
                "mode": str(mode), "name": str(meta.get("trigger_cmd") or mode),
                "status": state, "raw_status": state, "available_actions": _actions("legacy", state),
                "can_stop": state == "running",
                "targets": [str(target) for target in targets], "target_names": [str(name) for name in target_names],
                "target_label": ", ".join(str(name) for name in target_names) or "Chưa có đích",
                "account_names": [names.get(str(account_id), f"#{account_id}") for account_id in ids],
                "uptime_s": int(max(0, float(saved.get("finished_at") or now) - started_at)), "started_at": started_at,
                "last_updated": float(saved.get("updated_at") or saved.get("finished_at") or started_at),
                "sent": int(saved.get("sent") or 0), "failed": int(saved.get("fail") or 0),
                "error": str(saved.get("error") or "")})
        return sorted(snapshots, key=lambda item: item["started_at"], reverse=True)[:100]


def durable_task_snapshots(queue, owner):
    """Normalize durable notification records without exposing their payloads.

    ``queue.list`` is owner-scoped by design. The caller must pass the
    authenticated Telegram owner, never an ID supplied by the browser.
    """
    if queue is None or owner is None:
        return []
    snapshots = []
    try:
        rows = queue.list(str(owner))
    except Exception as error:
        # A configured database may legitimately be a new empty SQLite file
        # after an explicit storage migration.  Initialize only the durable
        # queue schema and retry once; propagate every other storage failure so
        # the API reports degradation instead of showing a fake empty queue.
        if "no such table" not in str(error).lower() or not callable(getattr(queue, "ensure_schema", None)):
            raise
        queue.ensure_schema()
        rows = queue.list(str(owner))
    for row in rows:
        raw_status = str(row.get("status") or "UNKNOWN").upper()
        status = _DURABLE_STATUS.get(raw_status, "unknown")
        created = float(row.get("created") or 0)
        updated = float(row.get("updated") or created)
        completed = row.get("completed")
        endpoint = str(row.get("channel") or "")
        snapshots.append({
            "id": str(row.get("id") or ""),
            "task_ref": task_reference("durable", row.get("id") or ""),
            "engine": "durable",
            "execution_source": "discord_webhook_queue",
            "persistence": "durable",
            "persistent": True,
            "mode": "notification",
            "name": "Discord webhook notification",
            "platform": "discord",
            "status": status,
            "raw_status": raw_status,
            "available_actions": _actions("durable", status),
            "can_stop": "stop" in _actions("durable", status),
            "targets": [endpoint] if endpoint else [],
            "target_names": [endpoint[-8:]] if endpoint else [],
            "target_label": endpoint[-8:] if endpoint else "Kênh không xác định",
            "account_names": [],
            "started_at": created,
            "last_updated": updated,
            "completed_at": completed,
            "uptime_s": int(max(0, (float(completed) if completed else time.time()) - created)),
            "sent": 1 if status == "completed" else 0,
            "failed": 1 if status in ("failed", "unknown") else 0,
            "attempts": int(row.get("attempts") or 0),
            "error": str(row.get("error") or ""),
            "latency": float(row.get("latency") or 0),
        })
    return snapshots


def unified_task_snapshots(active_tasks, saved_tasks, accounts, lock, *, queue=None,
                           owner=None, include_legacy=True, limit=200):
    """Aggregate independent engines into a stable, honest read contract.

    Legacy tasks are intentionally included only when the caller has already
    established permission to view them. Durable tasks are scoped by ``owner``
    inside :class:`durable_tasks.TaskQueue`.
    """
    items = []
    if include_legacy:
        items.extend(task_snapshots(active_tasks, saved_tasks, accounts, lock))
    items.extend(durable_task_snapshots(queue, owner))
    return sorted(items, key=lambda item: (float(item.get("last_updated") or item.get("started_at") or 0), item["task_ref"]), reverse=True)[:max(1, min(int(limit), 500))]


def control_unified_task(reference, action, active_tasks, saved_tasks, lock, *, queue=None,
                         owner=None):
    """Route an action to the engine that owns the task.

    Only controls actually supported by an engine are advertised and accepted.
    Process-local legacy tasks support cooperative ``stop`` only; they cannot
    honestly promise pause/resume/retry semantics. Durable queue controls are
    delegated to their owner-scoped transaction.
    """
    engine, task_id = parse_task_reference(reference)
    action = str(action or "").strip().lower()
    if engine == "durable":
        if queue is None or owner is None:
            raise ValueError("Hàng đợi tác vụ không sẵn sàng")
        if action not in {"pause", "resume", "stop", "retry"}:
            raise ValueError("Thao tác tác vụ không hợp lệ")
        return queue.control(str(owner), task_id, action)
    if action != "stop":
        raise ValueError("Tác vụ đang chạy chỉ hỗ trợ dừng an toàn")
    state = cancel_one(task_id, active_tasks, saved_tasks, lock)
    if state is None:
        raise ValueError("Không tìm thấy tác vụ")
    return state
