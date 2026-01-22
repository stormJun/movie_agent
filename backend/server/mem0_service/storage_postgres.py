from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncpg

from server.mem0_service.settings import MEM0_DEFAULT_TTL_DAYS, MEM0_ENABLE_TTL

class PostgresMemoryStore:
    """Postgres metadata store for mem0-like memories.

    We store text/tags/metadata in Postgres and keep vector indexing separate
    (e.g. Milvus). This avoids relying on pgvector and keeps dimension flexible.
    """

    def __init__(self, *, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def open(self) -> None:
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(dsn=self._dsn, min_size=1, max_size=5)
        await self._ensure_schema()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
        self._pool = None

    async def _ensure_schema(self) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE SCHEMA IF NOT EXISTS mem0;")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mem0.memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    tags TEXT[] NOT NULL DEFAULT '{}'::text[],
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            # Schema evolution (best-effort, idempotent).
            await conn.execute("ALTER TABLE mem0.memories ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;")
            await conn.execute("ALTER TABLE mem0.memories ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;")
            await conn.execute("ALTER TABLE mem0.memories ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;")
            await conn.execute("ALTER TABLE mem0.memories ADD COLUMN IF NOT EXISTS ttl_days INT;")
            # Backfill updated_at for existing rows and enforce default.
            await conn.execute("UPDATE mem0.memories SET updated_at = created_at WHERE updated_at IS NULL;")
            await conn.execute("ALTER TABLE mem0.memories ALTER COLUMN updated_at SET DEFAULT NOW();")
            await conn.execute("ALTER TABLE mem0.memories ALTER COLUMN updated_at SET NOT NULL;")
            await conn.execute("CREATE INDEX IF NOT EXISTS mem0_memories_user_id_idx ON mem0.memories(user_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS mem0_memories_created_at_idx ON mem0.memories(created_at);")
            await conn.execute("CREATE INDEX IF NOT EXISTS mem0_memories_deleted_at_idx ON mem0.memories(deleted_at);")
            await conn.execute("CREATE INDEX IF NOT EXISTS mem0_memories_expires_at_idx ON mem0.memories(expires_at);")

    @staticmethod
    def _compute_ttl(*, tags: list[str]) -> Optional[int]:
        """Compute TTL days based on tags (doc-aligned defaults).

        Returns None for "never expire".
        """
        normalized = {str(t).strip().lower() for t in (tags or []) if t}
        if "identity" in normalized:
            return None
        if "fact" in normalized:
            return 365
        if "constraint" in normalized:
            return 180
        if "preference" in normalized:
            return 90
        return int(MEM0_DEFAULT_TTL_DAYS)

    async def add(
        self,
        *,
        user_id: str,
        text: str,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        assert self._pool is not None
        mid = str(uuid.uuid4())
        tags = tags or []
        metadata = metadata or {}
        now = datetime.now(timezone.utc)
        expires_at = None
        ttl_days = None
        if MEM0_ENABLE_TTL:
            ttl_days = self._compute_ttl(tags=list(tags))
            if ttl_days is not None:
                expires_at = now + timedelta(days=int(ttl_days))
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO mem0.memories (id, user_id, text, tags, metadata, created_at, updated_at, expires_at, ttl_days)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9);
                """,
                mid,
                user_id,
                text,
                tags,
                json.dumps(metadata),
                now,
                now,
                expires_at,
                ttl_days,
            )
        return mid

    async def get_many(self, *, ids: list[str], user_id: str) -> dict[str, dict[str, Any]]:
        """Fetch memories by ids for a single user_id.

        Returns mapping id -> {text, tags, created_at}.
        """
        if not ids:
            return {}
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, text, tags, created_at, updated_at
                FROM mem0.memories
                WHERE user_id = $1
                  AND id = ANY($2::text[])
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW());
                """,
                user_id,
                ids,
            )
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            out[str(r["id"])] = {
                "text": str(r["text"]),
                "tags": list(r["tags"] or []),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        return out

    async def get_by_id(self, *, memory_id: str) -> Optional[dict[str, Any]]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, text, tags, metadata, created_at, updated_at, deleted_at, expires_at, ttl_days
                FROM mem0.memories
                WHERE id = $1;
                """,
                memory_id,
            )
        if not row:
            return None
        return dict(row)

    async def list_by_user(
        self,
        *,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        tags: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        assert self._pool is not None
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        tags = [str(t) for t in (tags or []) if t]
        async with self._pool.acquire() as conn:
            if tags:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, text, tags, metadata, created_at, updated_at
                    FROM mem0.memories
                    WHERE user_id = $1
                      AND deleted_at IS NULL
                      AND (expires_at IS NULL OR expires_at > NOW())
                      AND tags && $2::text[]
                    ORDER BY created_at DESC
                    LIMIT $3 OFFSET $4;
                    """,
                    user_id,
                    tags,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, text, tags, metadata, created_at, updated_at
                    FROM mem0.memories
                    WHERE user_id = $1
                      AND deleted_at IS NULL
                      AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3;
                    """,
                    user_id,
                    limit,
                    offset,
                )
        return [dict(r) for r in rows]

    async def update(
        self,
        *,
        memory_id: str,
        user_id: str,
        text: str,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        assert self._pool is not None
        tags = tags or []
        metadata = metadata or {}
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE mem0.memories
                SET text = $3,
                    tags = $4,
                    metadata = $5::jsonb,
                    updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2
                RETURNING id, user_id, text, tags, metadata, created_at, updated_at;
                """,
                memory_id,
                user_id,
                text,
                tags,
                json.dumps(metadata),
            )
        return dict(row) if row else None

    async def soft_delete(self, *, memory_id: str, user_id: str) -> bool:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            res = await conn.execute(
                """
                UPDATE mem0.memories
                SET deleted_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2
                  AND deleted_at IS NULL;
                """,
                memory_id,
                user_id,
            )
        # asyncpg returns "UPDATE <n>"
        return res.split()[-1].isdigit() and int(res.split()[-1]) > 0

    async def restore(self, *, memory_id: str, user_id: str) -> bool:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            res = await conn.execute(
                """
                UPDATE mem0.memories
                SET deleted_at = NULL,
                    updated_at = NOW()
                WHERE id = $1
                  AND user_id = $2
                  AND deleted_at IS NOT NULL;
                """,
                memory_id,
                user_id,
            )
        return res.split()[-1].isdigit() and int(res.split()[-1]) > 0
