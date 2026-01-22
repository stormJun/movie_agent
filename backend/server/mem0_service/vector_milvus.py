from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional


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
class VectorHit:
    memory_id: str
    score: float


class MilvusVectorIndex:
    """Milvus vector index for mem0-like memory search (per-user filtering)."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        collection: str,
        embedding_dim: Optional[int],
    ) -> None:
        self._host = host
        self._port = int(port)
        self._collection_name = collection
        self._embedding_dim = embedding_dim
        self._collection: Any | None = None

    def _require(self):
        try:
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "pymilvus is required for MEM0_VECTOR_BACKEND=milvus. "
                "Install with: pip install pymilvus"
            ) from exc
        return Collection, CollectionSchema, DataType, FieldSchema, connections, utility

    def connect(self) -> None:
        Collection, _CollectionSchema, _DataType, _FieldSchema, connections, _utility = self._require()
        connections.connect(alias="default", host=self._host, port=self._port)
        # Do not create collection here; we may not know dim until first embed().
        if self._collection is not None:
            return
        try:
            self._collection = Collection(self._collection_name)
            self._collection.load()
        except Exception:
            self._collection = None

    def ensure_collection(self, *, dim: int) -> None:
        Collection, CollectionSchema, DataType, FieldSchema, _connections, utility = self._require()
        if self._collection is not None:
            return
        if utility.has_collection(self._collection_name):
            c = Collection(self._collection_name)
            c.load()
            # Best-effort sanity check.
            emb_field = next((f for f in c.schema.fields if f.name == "embedding"), None)
            if emb_field is not None and getattr(emb_field, "params", {}).get("dim") not in {None, dim}:
                raise RuntimeError(
                    f"Milvus collection {self._collection_name} exists but embedding dim mismatch."
                )
            self._collection = c
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=64),
            FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=int(dim)),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]
        schema = CollectionSchema(fields, description="mem0 memories (GraphRAG self-hosted)")
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

    def add(self, *, memory_id: str, user_id: str, embedding: list[float]) -> None:
        if self._collection is None:
            dim = self._embedding_dim or len(embedding)
            self.ensure_collection(dim=dim)
        assert self._collection is not None
        created_at = int(time.time())
        vec = _l2_normalize(list(embedding))
        self._collection.insert([[memory_id], [user_id], [vec], [created_at]])
        self._collection.flush()

    def search(self, *, user_id: str, embedding: list[float], limit: int) -> list[VectorHit]:
        if self._collection is None:
            # No collection yet => nothing indexed.
            return []
        vec = _l2_normalize(list(embedding))
        # Filter by user_id to avoid cross-user leakage.
        expr = f'user_id == "{user_id}"'
        results = self._collection.search(
            data=[vec],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"ef": 64}},
            limit=int(limit),
            expr=expr,
            output_fields=["id", "user_id", "created_at"],
        )
        hits: list[VectorHit] = []
        if not results:
            return hits
        for hit in results[0]:
            mid = getattr(hit, "id", None) or (hit.entity.get("id") if hasattr(hit, "entity") else None)
            if not mid:
                continue
            hits.append(VectorHit(memory_id=str(mid), score=float(getattr(hit, "distance", 0.0))))
        return hits

    def delete(self, *, memory_id: str) -> bool:
        """Delete vector by primary key."""
        if self._collection is None:
            return False
        expr = f'id == "{memory_id}"'
        self._collection.delete(expr)
        self._collection.flush()
        return True

    def update(self, *, memory_id: str, user_id: str, embedding: list[float]) -> None:
        """Update vector by delete + insert (Milvus does not support in-place update)."""
        self.delete(memory_id=memory_id)
        self.add(memory_id=memory_id, user_id=user_id, embedding=embedding)

