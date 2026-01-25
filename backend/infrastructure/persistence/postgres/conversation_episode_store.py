from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from application.ports.conversation_episode_store_port import ConversationEpisodeStorePort

logger = logging.getLogger(__name__)


def _jsonb_dumps(value: Any) -> str:
    # Ensure numpy types are converted to native Python numbers.
    return json.dumps(value, default=float, ensure_ascii=False)


class InMemoryConversationEpisodeStore(ConversationEpisodeStorePort):
    """In-memory episode store for dev/tests."""

    def __init__(self) -> None:
        # assistant_message_id is the natural idempotency key.
        self._rows: dict[UUID, dict[UUID, dict[str, Any]]] = {}

    async def upsert_episode(
        self,
        *,
        conversation_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        user_message: str,
        assistant_message: str,
        embedding: List[float],
        created_at: datetime,
    ) -> bool:
        conv = self._rows.setdefault(conversation_id, {})
        conv[assistant_message_id] = {
            "conversation_id": conversation_id,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
            "user_message": str(user_message),
            "assistant_message": str(assistant_message),
            "embedding": list(embedding),
            "created_at": created_at,
        }
        return True

    async def list_episodes(self, *, conversation_id: UUID, limit: int = 200) -> List[Dict[str, Any]]:
        conv = self._rows.get(conversation_id, {})
        rows = list(conv.values())
        rows.sort(key=lambda r: r.get("created_at") or datetime.min, reverse=True)
        return [dict(r) for r in rows[: int(limit)]]

    async def search_episodes(
        self,
        *,
        conversation_id: UUID,
        query_embedding: List[float],
        limit: int,
        scan_limit: int = 200,
        exclude_assistant_message_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        # Brute-force cosine similarity in memory.
        import numpy as np

        exclude = set(exclude_assistant_message_ids or [])
        q = np.asarray(list(query_embedding), dtype=np.float32)
        denom = float(np.linalg.norm(q))
        if denom > 0:
            q = q / denom

        rows = await self.list_episodes(conversation_id=conversation_id, limit=max(int(scan_limit), 0))
        scored: List[Dict[str, Any]] = []
        for r in rows:
            aid = r.get("assistant_message_id")
            if isinstance(aid, UUID) and aid in exclude:
                continue
            v = np.asarray(r.get("embedding") or [], dtype=np.float32)
            if v.size == 0:
                continue
            denom_v = float(np.linalg.norm(v))
            if denom_v > 0:
                v = v / denom_v
            sim = float(np.dot(q, v))
            item = dict(r)
            item["similarity"] = sim
            scored.append(item)

        scored.sort(key=lambda x: float(x.get("similarity") or 0.0), reverse=True)
        return scored[: max(int(limit), 0)]

    async def close(self) -> None:
        return None


class PostgresConversationEpisodeStore(ConversationEpisodeStorePort):
    """PostgreSQL episode store (asyncpg).

    Notes:
    - We store embeddings in JSONB for a minimal baseline (no pgvector required).
      Recall does similarity in Python; for production scale, consider pgvector/Milvus.
    """

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
            logger.info("PostgreSQL conversation episode store pool initialized")
            return self._pool

    async def _ensure_schema(self) -> None:
        pool = self._pool
        if pool is None:
            return
        async with pool.acquire() as conn:
            # Episodes table: per-conversation semantic recall materialized per completed turn.
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_episodes (
                    assistant_message_id uuid PRIMARY KEY,
                    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    user_message_id uuid NOT NULL,
                    user_message text NOT NULL,
                    assistant_message text NOT NULL,
                    embedding jsonb NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT NOW()
                );
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_episodes_conversation_created
                ON conversation_episodes(conversation_id, created_at DESC);
                """
            )

    async def upsert_episode(
        self,
        *,
        conversation_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        user_message: str,
        assistant_message: str,
        embedding: List[float],
        created_at: datetime,
    ) -> bool:
        pool = await self._get_pool()
        emb_json = _jsonb_dumps(list(embedding))
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversation_episodes (
                    assistant_message_id,
                    conversation_id,
                    user_message_id,
                    user_message,
                    assistant_message,
                    embedding,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                ON CONFLICT (assistant_message_id)
                DO UPDATE SET
                    conversation_id = EXCLUDED.conversation_id,
                    user_message_id = EXCLUDED.user_message_id,
                    user_message = EXCLUDED.user_message,
                    assistant_message = EXCLUDED.assistant_message,
                    embedding = EXCLUDED.embedding,
                    created_at = EXCLUDED.created_at
                RETURNING assistant_message_id
                """,
                assistant_message_id,
                conversation_id,
                user_message_id,
                str(user_message),
                str(assistant_message),
                emb_json,
                created_at,
            )
            return row is not None

    async def list_episodes(self, *, conversation_id: UUID, limit: int = 200) -> List[Dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT assistant_message_id, conversation_id, user_message_id,
                       user_message, assistant_message, embedding, created_at
                FROM conversation_episodes
                WHERE conversation_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                conversation_id,
                int(limit),
            )
            return [dict(r) for r in rows]

    async def search_episodes(
        self,
        *,
        conversation_id: UUID,
        query_embedding: List[float],
        limit: int,
        scan_limit: int = 200,
        exclude_assistant_message_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        # Minimal baseline: load recent episodes and score in Python.
        import numpy as np

        exclude = set(exclude_assistant_message_ids or [])
        q = np.asarray(list(query_embedding), dtype=np.float32)
        denom = float(np.linalg.norm(q))
        if denom > 0:
            q = q / denom

        rows = await self.list_episodes(conversation_id=conversation_id, limit=max(int(scan_limit), 0))
        scored: List[Dict[str, Any]] = []
        for r in rows:
            aid = r.get("assistant_message_id")
            if isinstance(aid, UUID) and aid in exclude:
                continue
            emb = r.get("embedding")
            if isinstance(emb, str):
                import json

                emb = json.loads(emb)
            if not isinstance(emb, list) or not emb:
                continue
            v = np.asarray(emb, dtype=np.float32)
            denom_v = float(np.linalg.norm(v))
            if denom_v > 0:
                v = v / denom_v
            sim = float(np.dot(q, v))
            item = dict(r)
            item["similarity"] = sim
            scored.append(item)

        scored.sort(key=lambda x: float(x.get("similarity") or 0.0), reverse=True)
        return scored[: max(int(limit), 0)]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL conversation episode store pool closed")
