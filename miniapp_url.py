"""Resolve one explicit HTTPS Mini App origin; do not invent a domain."""
import os
from urllib.parse import urlsplit


def public_miniapp_url(environment=None):
    env = environment if environment is not None else os.environ
    for key in ("MINIAPP_PUBLIC_URL", "RENDER_EXTERNAL_URL", "PUBLIC_WEB_URL"):
        candidate = str(env.get(key) or "").strip().rstrip("/")
        if not candidate:
            continue
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            continue
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            continue
        # Only the origin is trusted; the application endpoint is always /miniapp.
        if parsed.path not in ("", "/","/miniapp"):
            continue
        return f"https://{parsed.netloc}/miniapp"
    return None