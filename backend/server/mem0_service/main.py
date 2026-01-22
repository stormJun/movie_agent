from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from server.mem0_service.auth import read_user_id_header, require_auth, resolve_user_id
from server.mem0_service.schemas import (
    MemoryAddRequest,
    MemoryAddResponse,
    ForgetRequest,
    MemoryListResponse,
    MemoryOut,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryUpdateRequest,
)
from server.mem0_service.settings import (
    MEM0_DEFAULT_LIMIT,
    MEM0_EMBEDDING_DIM,
    MEM0_MAX_LIMIT,
    MEM0_MAX_TEXT_CHARS,
    MEM0_MILVUS_COLLECTION,
    MEM0_MILVUS_HOST,
    MEM0_MILVUS_PORT,
    MEM0_PG_DSN,
    MEM0_STRICT_EMBEDDINGS,
    MEM0_VECTOR_BACKEND,
)
from server.mem0_service.storage_postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)


def _embed_text(text: str) -> list[float]:
    """Generate an embedding using an OpenAI-compatible endpoint.

    We keep the mem0 Docker image lean by avoiding the full app dependency set.
    The service reads the same env vars as the main backend:
      - OPENAI_API_KEY
      - OPENAI_BASE_URL (optional; e.g. DashScope compatible-mode)
      - OPENAI_EMBEDDINGS_MODEL
    """
    import os

    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("openai python client is required for embeddings (pip install openai)") from exc

    # Prefer mem0-scoped env vars to avoid collisions with other local stacks.
    # Compose/CI often has OPENAI_* set globally for unrelated services.
    api_key = (os.getenv("MEM0_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip().strip("'\"")
    base_url = (os.getenv("MEM0_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip().strip("'\"") or None
    model = (os.getenv("MEM0_OPENAI_EMBEDDINGS_MODEL") or os.getenv("OPENAI_EMBEDDINGS_MODEL") or "").strip().strip("'\"")
    if not api_key or not model:
        raise RuntimeError("Missing OPENAI_API_KEY / OPENAI_EMBEDDINGS_MODEL for embeddings")

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.embeddings.create(model=model, input=text)
    vec = resp.data[0].embedding if resp.data else []
    return [float(x) for x in vec]


def _cap_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) <= int(MEM0_MAX_TEXT_CHARS):
        return t
    return t[: int(MEM0_MAX_TEXT_CHARS)].rstrip()


def _cap_limit(limit: int) -> int:
    try:
        limit = int(limit)
    except Exception:
        limit = int(MEM0_DEFAULT_LIMIT)
    if limit <= 0:
        limit = int(MEM0_DEFAULT_LIMIT)
    return min(limit, int(MEM0_MAX_LIMIT))


def create_app() -> FastAPI:
    app = FastAPI(title="mem0 (self-hosted, compat)", version="0.1.0")
    app.state.pg = PostgresMemoryStore(dsn=MEM0_PG_DSN)
    app.state.vector = None

    @app.on_event("startup")
    async def _startup() -> None:
        await app.state.pg.open()
        if MEM0_VECTOR_BACKEND == "milvus":
            from server.mem0_service.vector_milvus import MilvusVectorIndex

            index = MilvusVectorIndex(
                host=MEM0_MILVUS_HOST,
                port=MEM0_MILVUS_PORT,
                collection=MEM0_MILVUS_COLLECTION,
                embedding_dim=MEM0_EMBEDDING_DIM,
            )
            index.connect()
            app.state.vector = index
        elif MEM0_VECTOR_BACKEND == "none":
            app.state.vector = None
        else:
            raise RuntimeError(f"Unsupported MEM0_VECTOR_BACKEND={MEM0_VECTOR_BACKEND}")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await app.state.pg.close()

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True, "vector_backend": MEM0_VECTOR_BACKEND}

    @app.post("/v1/memories", response_model=MemoryAddResponse, dependencies=[Depends(require_auth)])
    async def add_memory(
        req: MemoryAddRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> MemoryAddResponse:
        text = _cap_text(req.text)
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        user_id = resolve_user_id(
            authorization=authorization,
            header_user_id=read_user_id_header(dict(request.headers)),
            request_user_id=req.user_id,
        )
        mid = await app.state.pg.add(
            user_id=user_id,
            text=text,
            tags=req.tags,
            metadata=req.metadata,
        )

        if app.state.vector is None:
            return MemoryAddResponse(id=mid)

        try:
            emb = _embed_text(text)
            app.state.vector.add(memory_id=mid, user_id=user_id, embedding=emb)
        except Exception as exc:
            if MEM0_STRICT_EMBEDDINGS:
                raise HTTPException(status_code=500, detail=f"embedding/indexing failed: {exc}") from exc
            logger.warning("mem0 indexing failed (best-effort): %s", exc)

        return MemoryAddResponse(id=mid)

    @app.post("/v1/memories/search", response_model=MemorySearchResponse, dependencies=[Depends(require_auth)])
    async def search_memories(
        req: MemorySearchRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> MemorySearchResponse:
        limit = _cap_limit(req.limit)
        if app.state.vector is None:
            return MemorySearchResponse(memories=[])

        user_id = resolve_user_id(
            authorization=authorization,
            header_user_id=read_user_id_header(dict(request.headers)),
            request_user_id=req.user_id,
        )
        try:
            emb = _embed_text(req.query)
        except Exception as exc:
            if MEM0_STRICT_EMBEDDINGS:
                raise HTTPException(status_code=500, detail=f"embedding failed: {exc}") from exc
            return MemorySearchResponse(memories=[])

        hits = app.state.vector.search(user_id=user_id, embedding=emb, limit=limit)
        ids = [h.memory_id for h in hits]
        meta = await app.state.pg.get_many(ids=ids, user_id=user_id)

        memories: list[MemoryOut] = []
        for h in hits:
            row = meta.get(h.memory_id)
            if not row:
                continue
            memories.append(
                MemoryOut(
                    id=h.memory_id,
                    text=str(row.get("text") or ""),
                    score=float(h.score),
                    tags=list(row.get("tags") or []),
                    created_at=row.get("created_at"),
                )
            )
        return MemorySearchResponse(memories=memories)

    @app.get("/v1/memories", response_model=MemoryListResponse, dependencies=[Depends(require_auth)])
    async def list_memories(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        limit: int = 20,
        offset: int = 0,
        tags: Optional[str] = None,
    ) -> MemoryListResponse:
        user_id = resolve_user_id(
            authorization=authorization,
            header_user_id=read_user_id_header(dict(request.headers)),
            request_user_id=None,
        )
        tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()] or None
        rows = await app.state.pg.list_by_user(user_id=user_id, limit=limit, offset=offset, tags=tag_list)
        memories = [
            MemoryOut(
                id=str(r.get("id")),
                text=str(r.get("text") or ""),
                score=0.0,
                tags=list(r.get("tags") or []),
                created_at=r.get("created_at"),
            )
            for r in rows
        ]
        return MemoryListResponse(memories=memories, total=len(memories))

    @app.put("/v1/memories/{memory_id}", response_model=MemoryOut, dependencies=[Depends(require_auth)])
    async def update_memory(
        memory_id: str,
        req: MemoryUpdateRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> MemoryOut:
        user_id = resolve_user_id(
            authorization=authorization,
            header_user_id=read_user_id_header(dict(request.headers)),
            request_user_id=None,
        )
        new_text = _cap_text(req.text)
        row = await app.state.pg.update(
            memory_id=memory_id,
            user_id=user_id,
            text=new_text,
            tags=req.tags,
            metadata=req.metadata,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Memory not found")

        # Sync vector index with new embedding
        if app.state.vector is not None and new_text:
            try:
                emb = _embed_text(new_text)
                app.state.vector.update(memory_id=memory_id, user_id=user_id, embedding=emb)
            except Exception as exc:
                if MEM0_STRICT_EMBEDDINGS:
                    raise HTTPException(status_code=500, detail=f"vector update failed: {exc}") from exc
                logger.warning("mem0 vector update failed: %s", exc)

        return MemoryOut(
            id=str(row.get("id")),
            text=str(row.get("text") or ""),
            score=0.0,
            tags=list(row.get("tags") or []),
            created_at=row.get("created_at"),
        )

    @app.delete("/v1/memories/{memory_id}", dependencies=[Depends(require_auth)])
    async def delete_memory(
        memory_id: str,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        user_id = resolve_user_id(
            authorization=authorization,
            header_user_id=read_user_id_header(dict(request.headers)),
            request_user_id=None,
        )
        ok = await app.state.pg.soft_delete(memory_id=memory_id, user_id=user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Memory not found")

        # Remove from vector index
        if app.state.vector is not None:
            try:
                app.state.vector.delete(memory_id=memory_id)
            except Exception as exc:
                logger.warning("mem0 vector delete failed: %s", exc)

        return {"deleted": True, "memory_id": memory_id}

    @app.post("/v1/memories/{memory_id}/restore", dependencies=[Depends(require_auth)])
    async def restore_memory(
        memory_id: str,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        user_id = resolve_user_id(
            authorization=authorization,
            header_user_id=read_user_id_header(dict(request.headers)),
            request_user_id=None,
        )
        ok = await app.state.pg.restore(memory_id=memory_id, user_id=user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"restored": True, "memory_id": memory_id}

    @app.post("/v1/memories/forget", dependencies=[Depends(require_auth)])
    async def forget_memory(
        req: ForgetRequest,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        user_id = resolve_user_id(
            authorization=authorization,
            header_user_id=read_user_id_header(dict(request.headers)),
            request_user_id=None,
        )
        limit = _cap_limit(req.limit)
        if app.state.vector is None:
            return {"candidates": [], "total": 0, "message": "vector backend disabled"}

        try:
            emb = _embed_text(req.query)
        except Exception as exc:
            if MEM0_STRICT_EMBEDDINGS:
                raise HTTPException(status_code=500, detail=f"embedding failed: {exc}") from exc
            return {"candidates": [], "total": 0, "message": "embedding failed"}

        hits = app.state.vector.search(user_id=user_id, embedding=emb, limit=limit)
        ids = [h.memory_id for h in hits]
        meta = await app.state.pg.get_many(ids=ids, user_id=user_id)

        candidates: list[dict[str, Any]] = []
        for h in hits:
            row = meta.get(h.memory_id)
            if not row:
                continue
            candidates.append(
                {
                    "id": h.memory_id,
                    "text": row.get("text") or "",
                    "score": float(h.score),
                    "tags": list(row.get("tags") or []),
                    "created_at": row.get("created_at"),
                }
            )

        if req.require_confirmation and not req.confirm:
            return {
                "candidates": candidates,
                "total": len(candidates),
                "message": "Confirm deletion by calling again with confirm=true",
            }

        deleted = 0
        for c in candidates:
            mid = str(c.get("id") or "")
            if not mid:
                continue
            if await app.state.pg.soft_delete(memory_id=mid, user_id=user_id):
                # Remove from vector index
                if app.state.vector is not None:
                    try:
                        app.state.vector.delete(memory_id=mid)
                    except Exception as exc:
                        logger.warning("mem0 vector delete failed for %s: %s", mid, exc)
                deleted += 1

        return {"deleted": True, "count": deleted}

    return app


app = create_app()
