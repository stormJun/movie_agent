from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from application.ports.conversation_store_port import ConversationStorePort
from application.ports.conversation_summary_store_port import ConversationSummaryStorePort

logger = logging.getLogger(__name__)


class InMemoryConversationSummaryStore(ConversationSummaryStorePort):
    """In-memory summary store for dev/tests (uses the in-memory conversation store as source)."""

    def __init__(self, *, conversation_store: ConversationStorePort) -> None:
        self._conversation_store = conversation_store
        self._rows: dict[UUID, dict[str, Any]] = {}

    async def get_summary(self, *, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        row = self._rows.get(conversation_id)
        return dict(row) if row else None

    async def save_summary_upsert(
        self,
        *,
        conversation_id: UUID,
        summary: str,
        covered_through_created_at: datetime,
        covered_through_message_id: UUID,
        covered_message_count: int,
        expected_version: int | None = None,
    ) -> bool:
        current = self._rows.get(conversation_id)
        current_version = int(current.get("summary_version", 1)) if current else 1
        if expected_version is not None and current is not None and current_version != int(expected_version):
            return False

        # Monotonic cursor advance: (created_at, id) lexicographic.
        if current:
            cur_at = current.get("covered_through_created_at")
            cur_id = current.get("covered_through_message_id")
            if isinstance(cur_at, datetime) and isinstance(cur_id, UUID):
                if (covered_through_created_at, covered_through_message_id) <= (cur_at, cur_id):
                    return False

        next_version = (current_version + 1) if current else 1
        now = datetime.utcnow()
        self._rows[conversation_id] = {
            "conversation_id": conversation_id,
            "summary": str(summary),
            "summary_version": next_version,
            "covered_through_created_at": covered_through_created_at,
            "covered_through_message_id": covered_through_message_id,
            "covered_message_count": int(covered_message_count),
            "created_at": current.get("created_at") if current else now,
            "updated_at": now,
        }
        return True

    async def count_completed_messages(self, *, conversation_id: UUID) -> int:
        msgs = await self._conversation_store.list_messages(conversation_id=conversation_id)
        count = 0
        for m in msgs:
            if m.get("completed", True):
                count += 1
        return count

    async def list_messages_since(
        self,
        *,
        conversation_id: UUID,
        since_created_at: datetime | None,
        since_message_id: UUID | None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        msgs = await self._conversation_store.list_messages(conversation_id=conversation_id, desc=False)
        completed = [m for m in msgs if m.get("completed", True)]
        completed.sort(key=lambda m: (m.get("created_at") or datetime.min, m.get("id") or UUID(int=0)))

        if since_created_at is None:
            start = 0
        else:
            start = 0
            since_id = since_message_id or UUID(int=0)
            for i, m in enumerate(completed):
                cur = (m.get("created_at") or datetime.min, m.get("id"))
                if cur[0] > since_created_at or (
                    cur[0] == since_created_at and isinstance(m.get("id"), UUID) and m.get("id") > since_id
                ):
                    start = i
                    break
            else:
                start = len(completed)

        return [dict(m) for m in completed[start : start + int(limit)]]

    async def list_recent_messages(self, *, conversation_id: UUID, limit: int = 6) -> List[Dict[str, Any]]:
        msgs = await self._conversation_store.list_messages(conversation_id=conversation_id, desc=True, limit=int(limit))
        return [dict(m) for m in msgs if m.get("completed", True)]

    async def close(self) -> None:
        return None


class PostgresConversationSummaryStore(ConversationSummaryStorePort):
    """PostgreSQL summary store (asyncpg)."""

    def __init__(
        self,
        *,
        dsn: str,
        min_size: int = 1,
        max_size: int = 5,
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
                ssl=False,
            )
            await self._ensure_schema()
            logger.info("PostgreSQL conversation summary store pool initialized")
            return self._pool

    async def _ensure_schema(self) -> None:
        pool = self._pool
        if pool is None:
            return
        async with pool.acquire() as conn:
            try:
                await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
            except Exception as e:
                logger.warning("Failed to ensure pgcrypto extension: %s", e)

            # Summary table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    summary text NOT NULL,
                    summary_version int NOT NULL DEFAULT 1,
                    covered_through_message_id uuid,
                    covered_through_created_at timestamptz,
                    covered_message_count int NOT NULL DEFAULT 0,
                    created_at timestamptz NOT NULL DEFAULT NOW(),
                    updated_at timestamptz NOT NULL DEFAULT NOW(),
                    UNIQUE(conversation_id)
                );
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_summaries_conversation_id
                ON conversation_summaries(conversation_id);
                """
            )

            # Ensure messages.completed exists (Phase 1 needs it to filter partial answers).
            try:
                await conn.execute(
                    """
                    ALTER TABLE messages
                    ADD COLUMN IF NOT EXISTS completed boolean NOT NULL DEFAULT true;
                    """
                )
            except Exception as e:
                logger.warning("Failed to ensure messages.completed column: %s", e)

            # Cursor pagination index.
            try:
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_id
                    ON messages(conversation_id, created_at, id);
                    """
                )
            except Exception as e:
                logger.warning("Failed to ensure messages cursor index: %s", e)

    async def get_summary(self, *, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT conversation_id, summary, summary_version,
                       covered_through_message_id, covered_through_created_at,
                       covered_message_count, created_at, updated_at
                FROM conversation_summaries
                WHERE conversation_id = $1
                """,
                conversation_id,
            )
            return dict(row) if row else None

    async def save_summary_upsert(
        self,
        *,
        conversation_id: UUID,
        summary: str,
        covered_through_created_at: datetime,
        covered_through_message_id: UUID,
        covered_message_count: int,
        expected_version: int | None = None,
    ) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversation_summaries (
                    conversation_id,
                    summary,
                    summary_version,
                    covered_through_message_id,
                    covered_through_created_at,
                    covered_message_count
                )
                VALUES ($1, $2, 1, $3, $4, $5)
                ON CONFLICT (conversation_id)
                DO UPDATE SET
                    summary = EXCLUDED.summary,
                    covered_through_message_id = EXCLUDED.covered_through_message_id,
                    covered_through_created_at = EXCLUDED.covered_through_created_at,
                    covered_message_count = EXCLUDED.covered_message_count,
                    summary_version = conversation_summaries.summary_version + 1,
                    updated_at = NOW()
                WHERE
                    -- Cursor monotonicity: (created_at, id)
                    (
                        conversation_summaries.covered_through_created_at IS NULL
                        OR conversation_summaries.covered_through_created_at < EXCLUDED.covered_through_created_at
                        OR (
                            conversation_summaries.covered_through_created_at = EXCLUDED.covered_through_created_at
                            AND conversation_summaries.covered_through_message_id < EXCLUDED.covered_through_message_id
                        )
                    )
                    AND ($6::int IS NULL OR conversation_summaries.summary_version = $6::int)
                RETURNING summary_version
                """,
                conversation_id,
                str(summary),
                covered_through_message_id,
                covered_through_created_at,
                int(covered_message_count),
                expected_version,
            )
            return row is not None

    async def count_completed_messages(self, *, conversation_id: UUID) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = $1 AND completed = TRUE",
                conversation_id,
            )
            return int(row["n"] or 0) if row else 0

    async def list_messages_since(
        self,
        *,
        conversation_id: UUID,
        since_created_at: datetime | None,
        since_message_id: UUID | None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if since_created_at is None:
                rows = await conn.fetch(
                    """
                    SELECT id, role, content, created_at, citations, debug, completed
                    FROM messages
                    WHERE conversation_id = $1 AND completed = TRUE
                    ORDER BY created_at ASC, id ASC
                    LIMIT $2
                    """,
                    conversation_id,
                    int(limit),
                )
                return [dict(r) for r in rows]

            rows = await conn.fetch(
                """
                SELECT id, role, content, created_at, citations, debug, completed
                FROM messages
                WHERE conversation_id = $1 AND completed = TRUE
                  AND (
                      created_at > $2
                      OR (created_at = $2 AND id > $3)
                  )
                ORDER BY created_at ASC, id ASC
                LIMIT $4
                """,
                conversation_id,
                since_created_at,
                since_message_id or UUID(int=0),
                int(limit),
            )
            return [dict(r) for r in rows]

    async def list_recent_messages(self, *, conversation_id: UUID, limit: int = 6) -> List[Dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, content, created_at, citations, debug, completed
                FROM messages
                WHERE conversation_id = $1 AND completed = TRUE
                ORDER BY created_at DESC, id DESC
                LIMIT $2
                """,
                conversation_id,
                int(limit),
            )
            return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL conversation summary store pool closed")
