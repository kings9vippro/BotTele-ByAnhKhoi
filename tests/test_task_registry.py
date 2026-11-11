"""Regression coverage for the cross-engine task read/control contract."""
import threading
import time
import unittest

from task_control import (
    control_unified_task,
    legacy_recovery_state,
    parse_task_reference,
    unified_task_snapshots,
)


class _Queue:
    def __init__(self):
        self.owners = []
        self.controls = []
        self.rows = [{
            "id": "notice-1", "owner": "alice", "channel": "1234567890",
            "status": "PAUSED", "created": 10, "updated": 20,
            "completed": None, "attempts": 1, "error": "", "latency": 0,
        }]

    def list(self, owner):
        self.owners.append(owner)
        return [dict(row) for row in self.rows if row["owner"] == owner]

    def control(self, owner, task_id, action):
        self.controls.append((owner, task_id, action))
        return "QUEUED"


class UnifiedTaskRegistryTests(unittest.TestCase):
    def setUp(self):
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.active = {
            "legacy-1": {"stop": self.stop, "targets": ["group-1"], "source": "chat"},
        }
        self.saved = {
            "legacy-1": {
                "id": "legacy-1", "type": "treo_ngon", "status": "running",
                "started_at": 10, "persisted": True, "sent": 3,
                "meta": {"source": "chat", "targets": ["group-1"], "target_names": ["Nhóm thử"]},
            },
        }
        self.accounts = [{"id": 1, "name": "Zalo thử"}]
        self.queue = _Queue()

    def test_registry_keeps_task_engines_and_persistence_capabilities_distinct(self):
        tasks = unified_task_snapshots(
            self.active, self.saved, self.accounts, self.lock,
            queue=self.queue, owner="alice", include_legacy=True,
        )
        by_ref = {item["task_ref"]: item for item in tasks}
        legacy = by_ref["legacy:legacy-1"]
        durable = by_ref["durable:notice-1"]

        self.assertEqual(self.queue.owners, ["alice"])
        self.assertEqual(legacy["engine"], "legacy")
        self.assertEqual(legacy["persistence"], "snapshot_only")
        self.assertFalse(legacy["persistent"])
        self.assertEqual(legacy["available_actions"], ["stop"])
        self.assertEqual(durable["engine"], "durable")
        self.assertEqual(durable["persistence"], "durable")
        self.assertTrue(durable["persistent"])
        self.assertEqual(durable["status"], "paused")
        self.assertEqual(durable["available_actions"], ["resume", "stop"])

    def test_registry_can_hide_legacy_tasks_for_non_admin_scopes(self):
        tasks = unified_task_snapshots(
            self.active, self.saved, self.accounts, self.lock,
            queue=self.queue, owner="alice", include_legacy=False,
        )
        self.assertEqual([item["task_ref"] for item in tasks], ["durable:notice-1"])

    def test_recovered_legacy_snapshot_is_honest_about_restart_interruption(self):
        """A persisted legacy record is evidence, not a resumable worker."""
        self.active.clear()
        self.saved["legacy-1"]["recovered_after_restart"] = True
        task = unified_task_snapshots(
            self.active, self.saved, self.accounts, self.lock,
            include_legacy=True,
        )[0]
        self.assertEqual(task["task_ref"], "legacy:legacy-1")
        self.assertEqual(task["status"], "interrupted")
        self.assertEqual(task["available_actions"], [])
        self.assertEqual(task["persistence"], "snapshot_only")

    def test_restart_recovery_never_relabels_inflight_legacy_work_as_stopped(self):
        self.assertEqual(legacy_recovery_state("running"), "interrupted")
        self.assertEqual(legacy_recovery_state("stopping"), "interrupted")
        self.assertEqual(legacy_recovery_state("failed"), "failed")
        self.assertEqual(legacy_recovery_state(None), "stopped")

    def test_controls_route_to_real_owner_engine_only(self):
        self.assertEqual(
            control_unified_task("durable:notice-1", "resume", self.active, self.saved, self.lock,
                                 queue=self.queue, owner="alice"),
            "QUEUED",
        )
        self.assertEqual(self.queue.controls, [("alice", "notice-1", "resume")])

        self.assertEqual(
            control_unified_task("legacy:legacy-1", "stop", self.active, self.saved, self.lock),
            "stopped",
        )
        self.assertTrue(self.stop.is_set())
        self.assertEqual(self.saved["legacy-1"]["status"], "stopped")
        with self.assertRaisesRegex(ValueError, "chỉ hỗ trợ"):
            control_unified_task("legacy:legacy-1", "pause", self.active, self.saved, self.lock)

    def test_rejects_unqualified_or_unknown_task_references(self):
        for value in ("notice-1", "other:notice-1", "durable:", ""):
            with self.assertRaises(ValueError):
                parse_task_reference(value)
        with self.assertRaisesRegex(ValueError, "không sẵn sàng"):
            control_unified_task("durable:notice-1", "stop", self.active, self.saved, self.lock)


if __name__ == "__main__":
    unittest.main()
