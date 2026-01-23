from __future__ import annotations

import os
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional, Protocol, runtime_checkable

from infrastructure.debug.debug_collector import DebugDataCollector


def _get_env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_env_str(key: str, default: str) -> str:
    raw = os.getenv(key)
    return default if raw is None or raw.strip() == "" else raw.strip()


@runtime_checkable
class DebugCache(Protocol):
    def set(self, request_id: str, collector: DebugDataCollector) -> None: ...

    def get(self, request_id: str): ...  # returns DebugDataCollector | dict | None

    def delete(self, request_id: str) -> bool: ...

    def cleanup_expired(self) -> int: ...


class DebugDataCache:
    """In-memory LRU+TTL cache for per-request debug data.

    Limitation: per-process only. For multi-worker/multi-instance production,
    replace this with a Redis-backed implementation (see docs).
    """

    def __init__(self, *, ttl_minutes: int = 30, max_size: int = 1000) -> None:
        self._ttl = timedelta(minutes=max(ttl_minutes, 1))
        self._max_size = max(max_size, 1)
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, DebugDataCollector] = OrderedDict()

    def set(self, request_id: str, collector: DebugDataCollector) -> None:
        with self._lock:
            # Only evict when adding a new key that would exceed capacity.
            if request_id not in self._cache and len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[request_id] = collector
            self._cache.move_to_end(request_id)

    def get(self, request_id: str) -> Optional[DebugDataCollector]:
        with self._lock:
            collector = self._cache.get(request_id)
            if collector is None:
                return None
            if datetime.now() - collector.timestamp > self._ttl:
                del self._cache[request_id]
                return None
            self._cache.move_to_end(request_id)
            return collector

    def delete(self, request_id: str) -> bool:
        with self._lock:
            if request_id in self._cache:
                del self._cache[request_id]
                return True
            return False

    def cleanup_expired(self) -> int:
        with self._lock:
            now = datetime.now()
            expired = [k for k, v in self._cache.items() if now - v.timestamp > self._ttl]
            for k in expired:
                del self._cache[k]
            return len(expired)


def _build_debug_cache() -> DebugCache:
    backend = _get_env_str("DEBUG_CACHE_BACKEND", "memory").lower()
    ttl_minutes = _get_env_int("DEBUG_CACHE_TTL", 30)

    if backend in {"memory", "in-memory", "in_memory"}:
        return DebugDataCache(
            ttl_minutes=ttl_minutes,
            max_size=_get_env_int("DEBUG_CACHE_MAX_SIZE", 1000),
        )

    if backend == "redis":
        redis_url = _get_env_str("DEBUG_REDIS_URL", "redis://localhost:6379/0")
        from infrastructure.debug.debug_cache_redis import RedisDebugDataCache

        return RedisDebugDataCache(redis_url=redis_url, ttl_minutes=ttl_minutes)

    raise ValueError(f"Unsupported DEBUG_CACHE_BACKEND='{backend}' (expected memory|redis)")


debug_cache: DebugCache = _build_debug_cache()
