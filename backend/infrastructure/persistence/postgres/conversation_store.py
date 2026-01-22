from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from application.ports.conversation_store_port import ConversationStorePort

logger = logging.getLogger(__name__)


def _sanitize_for_jsonb(data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Sanitize dict for asyncpg JSONB serialization.

    Handles non-JSON-serializable types like numpy.int64, numpy.float64, etc.
    Returns a JSON string that asyncpg can directly use for JSONB columns.
    """
    if data is None:
        return None
    try:
        # Round-trip through JSON to convert numpy types to Python native types
        return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to serialize data for JSONB: {e}")
        return None


class InMemoryConversationStore(ConversationStorePort):
    """In-memory conversation store for dev/tests when Postgres is not configured."""

    def __init__(self) -> None:
        self._conversations: Dict[Tuple[str, str], UUID] = {}
        self._messages: Dict[UUID, List[Dict[str, Any]]] = {}

    async def get_or_create_conversation_id(self, *, user_id: str, session_id: str) -> UUID:
        key = (str(user_id), str(session_id))
        if key not in self._conversations:
            self._conversations[key] = uuid4()
        return self._conversations[key]

    async def append_message(
        self,
        *,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: Optional[Dict[str, Any]] = None,
        debug: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        msg_id = uuid4()
        self._messages.setdefault(conversation_id, []).append(
            {
                "id": msg_id,
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "created_at": datetime.utcnow(),
                "citations": citations,
                "debug": debug,
            }
        )
        return msg_id

    async def list_messages(
        self,
        *,
        conversation_id: UUID,
        limit: Optional[int] = None,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        rows = list(self._messages.get(conversation_id, []))
        if before is not None:
            rows = [r for r in rows if isinstance(r.get("created_at"), datetime) and r["created_at"] < before]
        rows.sort(key=lambda r: r.get("created_at") or datetime.min)
        if limit is not None:
            rows = rows[: int(limit)]
        return rows

    async def clear_messages(self, *, conversation_id: UUID) -> int:
        existing = self._messages.get(conversation_id, [])
        count = len(existing)
        self._messages[conversation_id] = []
        return count

    async def list_conversations(
        self, *, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出用户的历史会话列表，按更新时间倒序。"""
        results = []
        for (uid, sid), conv_id in self._conversations.items():
            if uid == user_id:
                msgs = self._messages.get(conv_id, [])
                first_msg = msgs[0]["content"] if msgs else None
                results.append({
                    "id": conv_id,
                    "session_id": sid,
                    "created_at": msgs[0]["created_at"] if msgs else datetime.utcnow(),
                    "updated_at": msgs[-1]["created_at"] if msgs else datetime.utcnow(),
                    "first_message": first_msg,
                })
        results.sort(key=lambda x: x["updated_at"], reverse=True)
        return results[offset : offset + limit]

    async def close(self) -> None:
        return None


class PostgresConversationStore(ConversationStorePort):
    """PostgreSQL conversation store (asyncpg).

    Tables:
      - conversations(id uuid pk, user_id text, session_id text, created_at, updated_at, unique(user_id, session_id))
      - messages(id uuid pk, conversation_id fk, role, content, created_at, citations jsonb, debug jsonb)
    """

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
            # Lazy import so unit tests can run without asyncpg installed if not used.
            import asyncpg  # type: ignore

            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
            )
            logger.info("PostgreSQL conversation store pool initialized")
            return self._pool

    async def get_or_create_conversation_id(self, *, user_id: str, session_id: str) -> UUID:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (user_id, session_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, session_id)
                DO UPDATE SET updated_at = NOW()
                RETURNING id
                """,
                user_id,
                session_id,
            )
            if not row:
                raise RuntimeError("failed to get or create conversation_id")
            return row["id"]

    async def append_message(
        self,
        *,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: Optional[Dict[str, Any]] = None,
        debug: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        # Sanitize JSONB fields to handle numpy types and other non-serializable objects
        citations_json = _sanitize_for_jsonb(citations)
        debug_json = _sanitize_for_jsonb(debug)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO messages (conversation_id, role, content, citations, debug)
                VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
                RETURNING id
                """,
                conversation_id,
                role,
                content,
                citations_json,
                debug_json,
            )
            if not row:
                raise RuntimeError("failed to append message")
            return row["id"]

    async def list_messages(
        self,
        *,
        conversation_id: UUID,
        limit: Optional[int] = None,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            params: List[Any] = [conversation_id]
            sql = "SELECT * FROM messages WHERE conversation_id = $1"
            if before is not None:
                sql += " AND created_at < $2"
                params.append(before)
            sql += " ORDER BY created_at ASC"
            if limit is not None:
                sql += f" LIMIT ${len(params) + 1}"
                params.append(int(limit))
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]

    async def clear_messages(self, *, conversation_id: UUID) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM messages WHERE conversation_id = $1",
                conversation_id,
            )
            # asyncpg returns: "DELETE <n>"
            try:
                return int(str(result).split()[-1])
            except Exception:
                return 0

    async def list_conversations(
        self, *, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出用户的历史会话列表，按更新时间倒序。"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT c.id, c.session_id, c.created_at, c.updated_at,
                       (SELECT content FROM messages m
                        WHERE m.conversation_id = c.id
                        ORDER BY m.created_at LIMIT 1) as first_message
                FROM conversations c
                WHERE c.user_id = $1
                ORDER BY c.updated_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )
            return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL conversation store pool closed")
