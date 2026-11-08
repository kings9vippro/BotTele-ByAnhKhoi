"""QR sessions for different device logins must not invalidate each other."""
import os
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("DISABLE_TELEGRAM_BOT", "1")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
os.environ.setdefault("SECRET_KEY", "qr-concurrency-synthetic-only")
import app


class ConcurrentQRTests(unittest.TestCase):
    def test_starting_second_qr_does_not_cancel_first_pending_session(self):
        manager = app.ZaloQRLoginManager
        first_stop = threading.Event()
        previous = {
            "session_id": "first-account",
            "status": "waiting_scan",
            "created_at": time.time(),
            "stop_ev": first_stop,
            "qr_base64": "existing-qr-image",
        }
        states = {"first-account": previous}
        device = {
            "pc_name": "Synthetic Computer",
            "imei": "synthetic-device-id",
            "ua": "Synthetic User Agent",
        }

        def mark_new_qr_ready():
            for key, state in states.items():
                if key != "first-account":
                    state["qr_base64"] = "new-qr-image"
                    state["status"] = "waiting_scan"

        with patch.object(manager, "SESSIONS", states), \\
             patch.object(manager, "_LAST_START_TS", 0.0), \\
             patch.object(manager, "_LAST_START_SESSION_ID", ""), \\
             patch.object(manager, "_persist_qr_state_to_db"), \\
             patch.object(app.ZaloWebIDGenerator, "create_random_pc_device", return_value=device), \\
             patch.object(app.threading, "Thread") as thread_ctor:
            thread_ctor.return_value.start.side_effect = mark_new_qr_ready
            status = manager.start_qr_session()
            self.assertTrue(status["ok"])
            self.assertEqual(len(states), 2)
            self.assertNotEqual(status["session_id"], "first-account")
            self.assertFalse(first_stop.is_set())
            self.assertIn("first-account", states)


if __name__ == "__main__":
    unittest.main()
