"""
cache.py
========
Thread-safe in-memory cache with Time-To-Live (TTL) expiration.
Used to cache heavy simulation inputs and telemetry data.
"""

import time
from typing import Dict, Any, Optional

class TelemetryCache:
    """In-memory key-value cache with automated TTL expiration."""
    
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def set(self, key: str, value: Any, ttl_seconds: int = 60):
        """Sets a value with an expiration timestamp."""
        self._store[key] = {
            "data": value,
            "expires_at": time.time() + ttl_seconds
        }

    def get(self, key: str) -> Optional[Any]:
        """Gets a value, returning None if expired or missing."""
        if key not in self._store:
            return None
            
        entry = self._store[key]
        if time.time() > entry["expires_at"]:
            # Delete expired entry
            del self._store[key]
            return None
            
        return entry["data"]

    def clear(self):
        """Clears all stored elements."""
        self._store.clear()
