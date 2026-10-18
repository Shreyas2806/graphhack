"""
tests/test_cache.py — Unit tests for thread-safe bounded TTLCache.
"""

from __future__ import annotations

import time
from app.cache import TTLCache


def test_cache_set_and_get():
    c = TTLCache(maxsize=10, default_ttl_sec=5.0)
    c.set("test", "user1", {"key": "val"}, "stored_value")
    assert c.get("test", "user1", {"key": "val"}) == "stored_value"
    assert c.get("test", "user1", {"key": "other"}) is None
    assert c.get("test", "user2", {"key": "val"}) is None


def test_cache_ttl_expiration():
    c = TTLCache(maxsize=10, default_ttl_sec=0.1)
    c.set("test", "user1", {"id": 1}, "temp_value")
    assert c.get("test", "user1", {"id": 1}) == "temp_value"
    time.sleep(0.15)
    assert c.get("test", "user1", {"id": 1}) is None


def test_cache_lru_eviction():
    c = TTLCache(maxsize=3, default_ttl_sec=10.0)
    c.set("test", "u", {"k": 1}, "v1")
    c.set("test", "u", {"k": 2}, "v2")
    c.set("test", "u", {"k": 3}, "v3")
    assert c.size() == 3

    # Adding a 4th entry should evict the oldest (k: 1)
    c.set("test", "u", {"k": 4}, "v4")
    assert c.size() == 3
    assert c.get("test", "u", {"k": 1}) is None
    assert c.get("test", "u", {"k": 2}) == "v2"
    assert c.get("test", "u", {"k": 4}) == "v4"


def test_cache_invalidate_namespace():
    c = TTLCache(maxsize=10, default_ttl_sec=10.0)
    c.set("graph", "u", {"k": 1}, "g1")
    c.set("graph", "u", {"k": 2}, "g2")
    c.set("memory", "u", {"k": 1}, "m1")

    assert c.size() == 3
    invalidated = c.invalidate_namespace("graph")
    assert invalidated == 2
    assert c.get("graph", "u", {"k": 1}) is None
    assert c.get("memory", "u", {"k": 1}) == "m1"


def test_cache_disabled_mode():
    c = TTLCache(maxsize=10, default_ttl_sec=10.0, enabled=False)
    c.set("test", "u", {"k": 1}, "val")
    assert c.get("test", "u", {"k": 1}) is None
    assert c.size() == 0
