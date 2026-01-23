from __future__ import annotations

import json
from typing import Any, Dict, Optional

from infrastructure.debug.debug_collector import DebugDataCollector


class RedisDebugDataCache:
    """Redis-backed debug cache for multi-worker deployments.

    Notes:
    - Stores `collector.to_dict()` as JSON.
    - Retrieval returns a dict (read-only); callers should not assume collector methods.
    """

    def __init__(self, *, redis_url: str, ttl_minutes: int = 30) -> None:
        try:
            import redis  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "Redis debug cache requires the 'redis' package. "
                "Install it via: pip install redis"
            ) from e

        self._client = redis.from_url(
            redis_url,
            decode_responses=True,  # return str, not bytes
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self._ttl_seconds = max(int(ttl_minutes), 1) * 60

    def _key(self, request_id: str) -> str:
        return f"debug:{request_id}"

    def set(self, request_id: str, collector: DebugDataCollector) -> None:
        data = json.dumps(collector.to_dict(), ensure_ascii=True)
        self._client.setex(self._key(request_id), self._ttl_seconds, data)

    def get(self, request_id: str) -> Optional[Dict[str, Any]]:
        raw = self._client.get(self._key(request_id))
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    def delete(self, request_id: str) -> bool:
        return bool(self._client.delete(self._key(request_id)))

    def cleanup_expired(self) -> int:
        # Redis handles TTL expiry server-side.
        return 0

