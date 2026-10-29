"""Minimal in-process rate limiter (R51). Good enough for the offline slice;
production would use Redis keyed per client + IP."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def allow(key: str, limit: int, window_seconds: float = 60.0) -> bool:
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and q[0] <= now - window_seconds:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True
