from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from application.ports.conversation_episode_store_port import ConversationEpisodeStorePort

logger = logging.getLogger(__name__)


def _l2_normalize(vec: list[float]) -> list[float]:
    s = 0.0
    for v in vec:
        s += float(v) * float(v)
    if s <= 0.0:
        return vec
    inv = (s**0.5)
    if inv == 0.0:
        return vec
    return [float(v) / inv for v in vec]


@dataclass(frozen=True)
class _Hit:
    assistant_message_id: str
    similarity: float
    fields: Dict[str, Any]


class MilvusConversationEpisodeStore(ConversationEpisodeStorePort):
    """Milvus-backed episodic memory store.

    We store only message ids + embeddings in Milvus. Full message content is
    hydrated from the conversation store (Postgres) at recall time to avoid
    Milvus VARCHAR length limits and reduce duplication.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        collection: str,
        embedding_dim: Optional[int] = None,
    ) -> None:
        self._host = host
        self._port = int(port)
        self._collection_name = collection
        self._embedding_dim = embedding_dim
        self._collection: Any | None = None
        self._has_text_fields: bool | None = None
        self._lock = asyncio.Lock()

    def _require(self):
        try:
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "pymilvus is required for episodic memory with Milvus. Install with: pip install pymilvus"
            ) from exc
        return Collection, CollectionSchema, DataType, FieldSchema, connections, utility

    def _connect_sync(self) -> None:
        Collection, _CollectionSchema, _DataType, _FieldSchema, connections, _utility = self._require()
        connections.connect(alias="default", host=self._host, port=self._port)
        if self._collection is not None:
            return
        try:
            self._collection = Collection(self._collection_name)
            self._collection.load()
            self._has_text_fields = {f.name for f in self._collection.schema.fields}.issuperset(
                {"user_message", "assistant_message"}
            )
        except Exception:
            self._collection = None
            self._has_text_fields = None

    def _ensure_collection_sync(self, *, dim: int) -> None:
        Collection, CollectionSchema, DataType, FieldSchema, _connections, utility = self._require()
        if self._collection is not None:
            return
        if utility.has_collection(self._collection_name):
            c = Collection(self._collection_name)
            c.load()
            emb_field = next((f for f in c.schema.fields if f.name == "embedding"), None)
            if emb_field is not None and getattr(emb_field, "params", {}).get("dim") not in {None, dim}:
                raise RuntimeError(
                    f"Milvus collection {self._collection_name} exists but embedding dim mismatch."
                )
            self._collection = c
            self._has_text_fields = {f.name for f in c.schema.fields}.issuperset(
                {"user_message", "assistant_message"}
            )
            return

        # v2 schema: store only message ids + embedding. Full message content is
        # hydrated from Postgres via ConversationStore at recall time.
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=64),
            FieldSchema(name="conversation_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="user_message_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="created_at", dtype=DataType.INT64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=int(dim)),
        ]
        schema = CollectionSchema(fields, description="conversation episodic memories (GraphRAG Phase 2, ids only)")
        c = Collection(self._collection_name, schema=schema)
        c.create_index(
            field_name="embedding",
            index_params={
                "index_type": "HNSW",
                "metric_type": "IP",
                "params": {"M": 16, "efConstruction": 200},
            },
        )
        c.load()
        self._collection = c
        self._has_text_fields = False

    def _delete_sync(self, *, assistant_message_id: str) -> None:
        if self._collection is None:
            return
        expr = f'id == "{assistant_message_id}"'
        self._collection.delete(expr)

    def _upsert_sync(
        self,
        *,
        conversation_id: str,
        user_message_id: str,
        assistant_message_id: str,
        user_message: str,
        assistant_message: str,
        embedding: list[float],
        created_at: datetime,
    ) -> None:
        self._connect_sync()
        dim = self._embedding_dim or len(embedding)
        self._ensure_collection_sync(dim=dim)
        assert self._collection is not None
        if self._has_text_fields is None:
            self._has_text_fields = {f.name for f in self._collection.schema.fields}.issuperset(
                {"user_message", "assistant_message"}
            )

        # Milvus does not support in-place update; do delete+insert.
        self._delete_sync(assistant_message_id=assistant_message_id)

        vec = _l2_normalize(list(embedding))
        created = int(created_at.timestamp()) if isinstance(created_at, datetime) else int(time.time())
        # Backward-compat: if an older collection schema has text fields, insert
        # empty strings to avoid storing large payloads (and avoid 4096 limit issues).
        if self._has_text_fields:
            self._collection.insert(
                [
                    [assistant_message_id],
                    [conversation_id],
                    [user_message_id],
                    [""],
                    [""],
                    [created],
                    [vec],
                ]
            )
        else:
            self._collection.insert(
                [
                    [assistant_message_id],
                    [conversation_id],
                    [user_message_id],
                    [created],
                    [vec],
                ]
            )
        self._collection.flush()

    def _search_sync(
        self,
        *,
        conversation_id: str,
        query_embedding: list[float],
        limit: int,
        exclude_ids: list[str],
    ) -> list[_Hit]:
        self._connect_sync()
        if self._collection is None:
            return []
        if self._has_text_fields is None:
            self._has_text_fields = {f.name for f in self._collection.schema.fields}.issuperset(
                {"user_message", "assistant_message"}
            )
        vec = _l2_normalize(list(query_embedding))
        expr = f'conversation_id == "{conversation_id}"'
        if exclude_ids:
            joined = ", ".join([f'"{x}"' for x in exclude_ids])
            expr = f'{expr} && id not in [{joined}]'

        results = self._collection.search(
            data=[vec],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"ef": 64}},
            limit=int(limit),
            expr=expr,
            output_fields=["id", "conversation_id", "user_message_id", "created_at"],
        )
        hits: list[_Hit] = []
        if not results:
            return hits
        for hit in results[0]:
            hid = getattr(hit, "id", None) or (hit.entity.get("id") if hasattr(hit, "entity") else None)
            if not hid:
                continue
            entity = getattr(hit, "entity", None)
            # `hit.entity` is not a plain dict; extract only the fields we need.
            fields: Dict[str, Any] = {}
            if entity is not None:
                for k in (
                    "conversation_id",
                    "user_message_id",
                    "created_at",
                ):
                    try:
                        fields[k] = entity.get(k)  # type: ignore[attr-defined]
                    except Exception:
                        try:
                            fields[k] = getattr(entity, k)
                        except Exception:
                            fields[k] = None
            # For IP + normalized vectors, distance is cosine similarity.
            sim = float(getattr(hit, "distance", 0.0))
            hits.append(_Hit(assistant_message_id=str(hid), similarity=sim, fields=fields))
        return hits

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
        async with self._lock:
            await asyncio.to_thread(
                self._upsert_sync,
                conversation_id=str(conversation_id),
                user_message_id=str(user_message_id),
                assistant_message_id=str(assistant_message_id),
                user_message=str(user_message),
                assistant_message=str(assistant_message),
                embedding=list(embedding),
                created_at=created_at,
            )
        return True

    async def list_episodes(self, *, conversation_id: UUID, limit: int = 200) -> List[Dict[str, Any]]:
        # Best-effort: Milvus query API has no ordering; we sort by created_at locally.
        def _list_sync() -> List[Dict[str, Any]]:
            self._connect_sync()
            if self._collection is None:
                return []
            try:
                rows = self._collection.query(
                    expr=f'conversation_id == "{str(conversation_id)}"',
                    output_fields=["id", "conversation_id", "user_message_id", "created_at"],
                    limit=max(int(limit), 0),
                )
            except Exception:
                return []
            out: List[Dict[str, Any]] = []
            for r in rows or []:
                if not isinstance(r, dict):
                    continue
                out.append(
                    {
                        "assistant_message_id": r.get("id"),
                        "conversation_id": r.get("conversation_id"),
                        "user_message_id": r.get("user_message_id"),
                        "created_at": r.get("created_at"),
                    }
                )
            out.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
            return out

        return await asyncio.to_thread(_list_sync)

    async def search_episodes(
        self,
        *,
        conversation_id: UUID,
        query_embedding: List[float],
        limit: int,
        scan_limit: int = 200,
        exclude_assistant_message_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        _ = scan_limit  # Milvus does ANN search; scan_limit is not applicable.
        exclude = [str(x) for x in (exclude_assistant_message_ids or [])]
        hits = await asyncio.to_thread(
            self._search_sync,
            conversation_id=str(conversation_id),
            query_embedding=list(query_embedding),
            limit=int(limit),
            exclude_ids=exclude,
        )
        out: List[Dict[str, Any]] = []
        for h in hits:
            row = {
                "assistant_message_id": h.assistant_message_id,
                "user_message_id": h.fields.get("user_message_id"),
                "user_message": h.fields.get("user_message"),
                "assistant_message": h.fields.get("assistant_message"),
                "created_at": h.fields.get("created_at"),
                "similarity": h.similarity,
            }
            out.append(row)
        return out

    async def close(self) -> None:
        # pymilvus connections are global; best-effort noop.
        self._collection = None
