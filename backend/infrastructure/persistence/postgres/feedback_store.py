from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


def _jsonb_dumps(value: Any) -> str:
    # Keep encoding consistent with other Postgres JSONB stores.
    return json.dumps(value, ensure_ascii=False)


class InMemoryFeedbackStore:
    """In-memory feedback store for dev/tests when Postgres is not configured."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []

    async def insert_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        fid = uuid4()
        self._rows.append(
            {
                "id": fid,
                "message_id": message_id,
                "query": query,
                "is_positive": bool(is_positive),
                "thread_id": thread_id,
                "agent_type": agent_type,
                "created_at": datetime.utcnow(),
                "metadata": metadata,
            }
        )
        return fid

    async def close(self) -> None:
        return None


class PostgresFeedbackStore:
    """PostgreSQL feedback store (asyncpg)."""

    def __init__(
        self,
        *,
        dsn: str,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool = None
        self._pool_lock = asyncio.Lock()

    async def _get_pool(self):
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is not None:
                return self._pool
            import asyncpg  # type: ignore

            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
            )
            logger.info("PostgreSQL feedback store pool initialized")
            return self._pool

    async def insert_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        pool = await self._get_pool()
        metadata_json = _jsonb_dumps(metadata) if metadata is not None else None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO feedback (message_id, query, is_positive, thread_id, agent_type, metadata)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                RETURNING id
                """,
                message_id,
                query,
                bool(is_positive),
                thread_id,
                agent_type,
                metadata_json,
            )
            if not row:
                raise RuntimeError("failed to insert feedback")
            return row["id"]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL feedback store pool closed")
