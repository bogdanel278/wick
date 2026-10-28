import threading
import time
from collections import deque

WINDOW = 3600.0
MAX_KEYS = 10000


class SlidingWindowLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self._hits.clear()

    def check(self, key: str, limit: int, now: float | None = None) -> int | None:
        """Record a hit. Returns None if allowed, else seconds to wait (Retry-After)."""
        if limit <= 0:
            return None
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > MAX_KEYS:
                for k in [k for k, d in self._hits.items() if not d or now - d[-1] >= WINDOW]:
                    del self._hits[k]
            dq = self._hits.setdefault(key, deque())
            while dq and now - dq[0] >= WINDOW:
                dq.popleft()
            if len(dq) >= limit:
                return max(1, int(WINDOW - (now - dq[0])) + 1)
            dq.append(now)
            return None
