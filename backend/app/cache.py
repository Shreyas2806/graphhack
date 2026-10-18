"""
app/cache.py — Thread-safe bounded TTL in-memory cache for GraphMind.

Features:
- Bounded capacity with LRU eviction.
- Per-entry TTL expiration.
- Namespace and scope-based invalidation (invalidates on write).
- Scoped cache keys (tenant / request params).
- Zero external dependencies (avoids introducing Redis).
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TTLCache:
    """Thread-safe bounded in-memory cache with TTL and LRU eviction."""

    def __init__(self, maxsize: int = 256, default_ttl_sec: float = 60.0, enabled: bool = True):
        self._maxsize = maxsize
        self._default_ttl = default_ttl_sec
        self._enabled = enabled
        self._cache: collections.OrderedDict[str, tuple[float, Any]] = collections.OrderedDict()
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        """Check whether caching is enabled."""
        if not self._enabled:
            return False
        try:
            from app.config import settings
            return getattr(settings, "ENABLE_CACHE", True)
        except Exception:
            return True

    def _make_key(self, namespace: str, scope: str, params: Any) -> str:
        """Create a deterministic SHA-256 scoped cache key."""
        param_repr = json.dumps(params, sort_keys=True, default=str)
        hash_digest = hashlib.sha256(param_repr.encode()).hexdigest()[:16]
        return f"{namespace}:{scope}:{hash_digest}"

    def get(self, namespace: str, scope: str, params: Any) -> Optional[Any]:
        """Retrieve value if present and not expired."""
        if not self.enabled:
            return None

        key = self._make_key(namespace, scope, params)
        now = time.time()
        with self._lock:
            if key not in self._cache:
                return None
            expire_at, value = self._cache[key]
            if now > expire_at:
                del self._cache[key]
                return None
            # Move to most-recently used
            self._cache.move_to_end(key)
            return value

    def set(
        self,
        namespace: str,
        scope: str,
        params: Any,
        value: Any,
        ttl_sec: Optional[float] = None,
    ) -> None:
        """Store value with expiration and LRU bounding."""
        if not self.enabled:
            return
        key = self._make_key(namespace, scope, params)
        ttl = ttl_sec if ttl_sec is not None else self._default_ttl
        expire_at = time.time() + ttl
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (expire_at, value)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)  # pop oldest LRU entry

    def invalidate_namespace(self, namespace: str) -> int:
        """Remove all entries belonging to a specific namespace."""
        prefix = f"{namespace}:"
        count = 0
        with self._lock:
            keys_to_del = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_del:
                del self._cache[k]
                count += 1
        return count

    def invalidate_scope(self, scope: str) -> int:
        """Remove all entries belonging to a specific user/tenant scope."""
        needle = f":{scope}:"
        count = 0
        with self._lock:
            keys_to_del = [k for k in self._cache if needle in k]
            for k in keys_to_del:
                del self._cache[k]
                count += 1
        return count

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Return current number of entries."""
        with self._lock:
            return len(self._cache)


# Global singleton instance
cache = TTLCache(maxsize=256, default_ttl_sec=60.0)
