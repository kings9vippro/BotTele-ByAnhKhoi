"""Bounded, privacy-preserving Telegram command handler measurements."""
from collections import deque
import threading

_LOCK = threading.Lock()
_SAMPLES = deque(maxlen=256)


def record_command(command, handler_ms, *, ok=True):
    # Never store usernames, chat IDs, arguments, message bodies or credentials.
    safe = str(command).split("@")[0][:40]
    if not safe or safe[0] not in ("/", ".") or not safe[1:].replace("_", "").isalnum():
        safe = "/callback" if safe == "/callback" else "/other"
    try:
        elapsed = max(0.0, min(float(handler_ms), 60000.0))
    except (ValueError, TypeError):
        return
    with _LOCK:
        _SAMPLES.append((safe, elapsed, bool(ok)))


def snapshot():
    with _LOCK:
        values = list(_SAMPLES)
    times = sorted(x[1] for x in values)
    def percentile(p):
        if not times:
            return None
        return round(times[max(0, min(len(times)-1, int((len(times)-1)*p+0.5)))], 1)
    def platform(prefix):
        latencies = sorted(ms for label,ms,_ in values if label.startswith(prefix))
        def quantile(factor):
            if not latencies:
                return None
            return round(latencies[min(len(latencies)-1,int((len(latencies)-1)*factor+.5))],1)
        return {"count":len(latencies),
                "p50_ms":quantile(.5),
                "p95_ms":quantile(.95) if len(latencies)>=20 else None}
    return {
        "sample_count": len(times),
        "p50_handler_ms": percentile(.50),
        "p95_handler_ms": percentile(.95) if len(times) >= 20 else None,
        "failed_handlers": sum(not ok for _,_,ok in values),
        "telegram": platform("/"),
        "zalo": platform("."),
        "sample_window": "last 256 Telegram and Zalo command handlers",
        "measurement_scope": "handler wall time, not provider delivery or network p95",
    }