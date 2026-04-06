"""
app/middleware/rate_limit.py
----------------------------
Simple in-memory sliding-window rate limiter per IP.
In production you'd back this with Redis.

Config via env vars:
  RATE_LIMIT_WINDOW   seconds (default 60)
  RATE_LIMIT_MAX      requests per window (default 100)
  RATE_LIMIT_DISABLE  set to "1" to disable (used in tests)
"""

import time
import os
import threading
from collections import defaultdict, deque
from app.utils.helpers import error

WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW", 60))
MAX_REQUESTS   = int(os.environ.get("RATE_LIMIT_MAX",    100))
DISABLED       = os.environ.get("RATE_LIMIT_DISABLE", "0") == "1"

_lock    = threading.Lock()
_windows = defaultdict(deque)


def check_rate_limit(ip: str) -> tuple[bool, dict]:
    """Returns (allowed, headers_dict)."""
    if DISABLED:
        return True, {}

    now    = time.time()
    cutoff = now - WINDOW_SECONDS

    with _lock:
        window = _windows[ip]
        while window and window[0] < cutoff:
            window.popleft()

        remaining = MAX_REQUESTS - len(window)

        if remaining <= 0:
            reset_at = int(window[0] + WINDOW_SECONDS)
            return False, {
                "X-RateLimit-Limit":     str(MAX_REQUESTS),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset":     str(reset_at),
                "Retry-After":           str(reset_at - int(now)),
            }

        window.append(now)
        return True, {
            "X-RateLimit-Limit":     str(MAX_REQUESTS),
            "X-RateLimit-Remaining": str(remaining - 1),
            "X-RateLimit-Reset":     str(int(now + WINDOW_SECONDS)),
        }
