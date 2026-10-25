"""
cache.py
========
Thread-safe in-memory LRU cache with Time-To-Live (TTL) expiration.

v1 claimed thread safety but had no lock and no size bound; both are fixed here.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional, Tuple


def stable_key(namespace: str, payload: Any) -> str:
    """Process-independent key (v1 used ``hash(str(...))``, which is salted per process)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"{namespace}:{hashlib.sha256(blob.encode()).hexdigest()}"


class TelemetryCache:
    """Key-value cache with per-entry TTL, LRU eviction and hit/miss counters."""

    def __init__(self, max_entries: int = 1024, clock: Callable[[], float] = time.monotonic):
        self._store: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._clock = clock
        self.max_entries = max_entries
        self.hits = 0
        self.misses = 0

    def set(self, key: str, value: Any, ttl_seconds: float = 60) -> None:
        with self._lock:
            self._store[key] = (value, self._clock() + ttl_seconds)
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    def get(self, key: str) -> Optional[Any]:
        """Return the value, or None if missing/expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            value, expires_at = entry
            if self._clock() > expires_at:
                del self._store[key]
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
            return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"entries": len(self._store), "hits": self.hits, "misses": self.misses}
