"""Read-only task registry across durable notifications and process-local legacy tasks.

This module does not merge executors, storage, permissions or delivery semantics.
"""
from __future__ import annotations

ACTIVE = frozenset({"QUEUED", "RETRYING", "RUNNING", "PAUSED", "CANCELLING"})
ACTIONS = {
    "QUEUED": ("pause", "stop"),
    "RETRYING": ("pause", "stop"),
    "RUNNING": ("stop",),
    "PAUSED": ("resume", "stop"),
    "FAILED": ("retry",),
}
LEGACY_STATES = {
    "running": "RUNNING",
    "stopping": "CANCELLING",
    "stopped": "STOPPED",
    "interrupted": "INTERRUPTED",
}


def aggregate_tasks(notification_rows, legacy_rows, *, owner, include_legacy=False,
                    include_all_notifications=False):
    """Produce owner-scoped snapshots; do not fabricate progress or persistence."""
    principal = str(owner)
    tasks = []
    for record in notification_rows:
        if not include_all_notifications and str(record.get("owner") or "") != principal:
            continue
        status = str(record.get("status") or "UNKNOWN").upper()
        actions = list(ACTIONS.get(status, ()))
        tasks.append({
            "id": "notification:" + str(record["id"]),
            "source_id": str(record["id"]), "execution_source": "durable_notifications",
            "task_type": "notification", "owner": str(record.get("owner") or principal), "platform": "discord",
            "target": str(record.get("channel") or ""), "status": status,
            "created": record.get("created"), "started": record.get("started"),
            "updated": record.get("updated"), "progress": None,
            "error": str(record.get("error") or ""), "actions": actions,
            "persistence": "sqlite_host_dependent", "attempts": record.get("attempts") or 0,
        })
    if include_legacy:
        for record in legacy_rows:
            raw_id = str(record.get("id") or "")
            if not raw_id:
                continue
            status = LEGACY_STATES.get(str(record.get("status") or "").lower(), "UNKNOWN")
            account_ids = [str(x) for x in record.get("account_ids", [])]
            shared_execution = len(set(account_ids)) > 1
            can_stop = bool(record.get("can_stop")) and not shared_execution and status in ("RUNNING", "CANCELLING")
            tasks.append({
                "id": "legacy:" + raw_id, "source_id": raw_id,
                "execution_source": "legacy_process", "task_type": str(record.get("mode") or "legacy"),
                "owner": principal, "platform": "zalo", "target": str(record.get("target_label") or ""),
                "account_ids": account_ids,
                "shared_execution": shared_execution,
                "account_names": list(record.get("account_names", [])),
                "status": status, "created": record.get("started_at"),
                "started": record.get("started_at"), "updated": None,
                "progress": None, "error": str(record.get("error") or ""),
                "actions": ["stop"] if can_stop else [],
                "persistence": "process_local",
                "attempts": None,
            })
    tasks.sort(key=lambda task: float(task.get("started") or task.get("created") or 0), reverse=True)
    return tasks