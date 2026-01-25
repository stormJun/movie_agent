from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


def _jsonb_dumps(value: Any) -> str:
    # Keep encoding consistent with other Postgres JSONB stores.
    return json.dumps(value, ensure_ascii=False)


class InMemoryFeedbackStore:
    """In-memory feedback store for dev/tests when Postgres is not configured."""

    def __init__(self) -> None:
        # Keep a single "current" feedback per (thread_id, message_id).
        self._by_key: dict[tuple[str, str], dict[str, Any]] = {}

    async def insert_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Toggle-style insert.

        - If no feedback exists: create it.
        - If same feedback exists: clear it (cancel).
        - If opposite feedback exists: update it.
        """
        key = (str(thread_id), str(message_id))
        existing = self._by_key.get(key)
        if existing is not None and bool(existing.get("is_positive")) == bool(is_positive):
            del self._by_key[key]
            return ("cleared", "none")

        fid = uuid4()
        self._by_key[key] = {
            "id": fid,
            "message_id": message_id,
            "query": query,
            "is_positive": bool(is_positive),
            "thread_id": thread_id,
            "agent_type": agent_type,
            "created_at": existing.get("created_at") if existing else datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "metadata": metadata,
        }
        return ("updated" if existing else "created", "positive" if is_positive else "negative")

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

    async def _ensure_schema(self) -> None:
        pool = self._pool
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    message_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    is_positive BOOLEAN NOT NULL,
                    thread_id TEXT NOT NULL,
                    agent_type TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    metadata JSONB
                );
                """
            )
            # For existing DBs created with older init scripts.
            await conn.execute(
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();"
            )
            # Ensure single feedback per (thread_id, message_id) so the UI can toggle.
            #
            # Older deployments stored feedback as an append-only log, so duplicates
            # may exist. We keep the latest row per (thread_id, message_id) and
            # delete the rest before creating the unique index.
            try:
                await conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_thread_message_id ON feedback(thread_id, message_id);"
                )
            except Exception as exc:
                # asyncpg exception types aren't imported at module level.
                if exc.__class__.__name__ in {"UniqueViolationError"}:
                    await conn.execute(
                        """
                        DELETE FROM feedback f
                        USING feedback f2
                        WHERE f.thread_id = f2.thread_id
                          AND f.message_id = f2.message_id
                          AND (
                            f.created_at < f2.created_at
                            OR (f.created_at = f2.created_at AND f.ctid < f2.ctid)
                          );
                        """
                    )
                    await conn.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_thread_message_id ON feedback(thread_id, message_id);"
                    )
                else:
                    # Best-effort: don't block the app if we can't enforce uniqueness.
                    logger.warning("feedback schema: could not create unique index: %s", exc)

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
            await self._ensure_schema()
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
    ) -> Tuple[str, str]:
        """Toggle-style upsert.

        Requires unique constraint/index on (thread_id, message_id).
        """
        pool = await self._get_pool()
        metadata_json = _jsonb_dumps(metadata) if metadata is not None else None
        async with pool.acquire() as conn:
            current = await conn.fetchrow(
                """
                SELECT is_positive
                FROM feedback
                WHERE thread_id = $1 AND message_id = $2
                """,
                thread_id,
                message_id,
            )
            if current is not None and bool(current["is_positive"]) == bool(is_positive):
                await conn.execute(
                    "DELETE FROM feedback WHERE thread_id = $1 AND message_id = $2",
                    thread_id,
                    message_id,
                )
                return ("cleared", "none")

            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO feedback (message_id, query, is_positive, thread_id, agent_type, metadata, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW())
                    ON CONFLICT (thread_id, message_id)
                    DO UPDATE SET
                        query = EXCLUDED.query,
                        is_positive = EXCLUDED.is_positive,
                        agent_type = EXCLUDED.agent_type,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING is_positive
                    """,
                    message_id,
                    query,
                    bool(is_positive),
                    thread_id,
                    agent_type,
                    metadata_json,
                )
            except Exception as exc:
                # If uniqueness isn't enforced (older DB), emulate upsert by delete+insert.
                if exc.__class__.__name__ in {"InvalidColumnReferenceError"}:
                    await conn.execute(
                        "DELETE FROM feedback WHERE thread_id = $1 AND message_id = $2",
                        thread_id,
                        message_id,
                    )
                    row = await conn.fetchrow(
                        """
                        INSERT INTO feedback (message_id, query, is_positive, thread_id, agent_type, metadata, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW())
                        RETURNING is_positive
                        """,
                        message_id,
                        query,
                        bool(is_positive),
                        thread_id,
                        agent_type,
                        metadata_json,
                    )
                else:
                    raise
            if not row:
                raise RuntimeError("failed to upsert feedback")
            return (
                ("updated" if current is not None else "created"),
                ("positive" if bool(row["is_positive"]) else "negative"),
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL feedback store pool closed")
