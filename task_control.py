"""Observable cooperative cancellation. Author: Dev Anh Khôi. Version: 1.3.0."""
import time


def task_state(active, saved):
    event = active.get("stop")
    thread = active.get("thread")
    if event is not None and event.is_set():
        return "stopping" if thread is not None and thread.is_alive() else "stopped"
    if active:
        return "running"
    previous = saved.get("status") or "stopped"
    return "interrupted" if previous == "running" else previous


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
            snapshots.append({"id": str(task_id), "mode": str(mode), "name": str(meta.get("trigger_cmd") or mode),
                "status": state, "can_stop": state in ("running", "stopping"),
                "targets": [str(target) for target in targets], "target_names": [str(name) for name in target_names],
                "target_label": ", ".join(str(name) for name in target_names) or "Chưa có đích",
                "account_names": [names.get(str(account_id), f"#{account_id}") for account_id in ids],
                "uptime_s": int(max(0, float(saved.get("finished_at") or now) - started_at)), "started_at": started_at,
                "sent": int(saved.get("sent") or 0), "failed": int(saved.get("fail") or 0)})
        return sorted(snapshots, key=lambda item: item["started_at"], reverse=True)[:100]
