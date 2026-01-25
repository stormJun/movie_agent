from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from application.memory_center.memory_facade_service import MemoryFacadeService
from server.api.rest.dependencies import (
    get_conversation_store,
    get_memory_facade_service,
    get_watchlist_store,
)
from application.ports.watchlist_store_port import WatchlistStorePort

router = APIRouter(prefix="/api/v1", tags=["memory-center-v1"])


@router.get("/memory/dashboard")
async def get_memory_dashboard(
    conversation_id: str = Query(..., description="会话ID (UUID)"),
    user_id: str = Query(..., description="用户ID"),
    service: MemoryFacadeService = Depends(get_memory_facade_service),
    conversation_store=Depends(get_conversation_store),
) -> Dict[str, Any]:
    """Memory Center dashboard (MVP): summary + long-term memory."""
    try:
        conv_uuid = UUID(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid conversation_id (expected UUID)")

    # Basic ownership check (best-effort). We only expose the dashboard for the
    # current user's conversations.
    try:
        conversations = await conversation_store.list_conversations(user_id=user_id, limit=2000, offset=0)
        if not any(str(c.get("id")) == str(conv_uuid) for c in (conversations or [])):
            raise HTTPException(status_code=404, detail="conversation not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to validate conversation ownership: {e}")

    return await service.get_dashboard(conversation_id=conv_uuid, user_id=user_id)


@router.delete("/memory/items/{memory_id}", status_code=204, response_class=Response)
async def delete_memory_item(
    memory_id: str,
    user_id: str = Query(..., description="用户ID（用于权限校验/审计）"),
    service: MemoryFacadeService = Depends(get_memory_facade_service),
) -> Response:
    ok = await service.delete_memory_item(user_id=user_id, memory_id=memory_id)
    if not ok:
        # Best-effort deletion: treat as not found.
        raise HTTPException(status_code=404, detail="memory not found")
    return Response(status_code=204)


class WatchlistAddRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    title: str = Field(..., description="电影标题")
    year: Optional[int] = Field(default=None, description="上映年份（可选）")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="扩展信息（可选）")

class WatchlistUpdateRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    title: Optional[str] = Field(default=None, description="电影标题（可选）")
    year: Optional[int] = Field(default=None, description="上映年份（可选）")
    status: Optional[Literal["to_watch", "watched", "dismissed"]] = Field(
        default=None,
        description="状态：to_watch=待看, watched=已看, dismissed=不想看",
    )
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="扩展信息（可选，merge）")


@router.get("/memory/watchlist")
async def list_watchlist(
    user_id: str = Query(..., description="用户ID"),
    status: Optional[str] = Query(default=None, description="过滤状态：to_watch/watched/dismissed（可选）"),
    query: Optional[str] = Query(default=None, description="标题搜索（可选）"),
    include_deleted: bool = Query(False, description="是否包含已删除（软删除）条目"),
    only_deleted: bool = Query(False, description="仅返回已删除条目（会隐式 include_deleted=true）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    store: WatchlistStorePort = Depends(get_watchlist_store),
) -> List[Dict[str, Any]]:
    include_deleted = bool(include_deleted) or bool(only_deleted)
    items = await store.list_items(
        user_id=user_id,
        status=status,
        query=query,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
    )
    if only_deleted:
        items = [i for i in (items or []) if getattr(i, "deleted_at", None) is not None]
    return [
        {
            "id": str(i.id),
            "title": i.title,
            "year": i.year,
            "status": getattr(i, "status", "to_watch"),
            "created_at": i.created_at,
            "updated_at": getattr(i, "updated_at", None),
            "deleted_at": getattr(i, "deleted_at", None),
            "source": (i.metadata or {}).get("source") if isinstance(i.metadata, dict) else None,
            "metadata": i.metadata or {},
        }
        for i in (items or [])
    ]


@router.post("/memory/watchlist")
async def add_watchlist_item(
    req: WatchlistAddRequest,
    store: WatchlistStorePort = Depends(get_watchlist_store),
) -> Dict[str, Any]:
    try:
        metadata = dict(req.metadata or {})
        metadata.setdefault("source", "manual")
        item = await store.add_item(
            user_id=req.user_id,
            title=req.title,
            year=req.year,
            metadata=metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": str(item.id),
        "title": item.title,
        "year": item.year,
        "status": getattr(item, "status", "to_watch"),
        "created_at": item.created_at,
        "updated_at": getattr(item, "updated_at", None),
        "deleted_at": getattr(item, "deleted_at", None),
        "source": (item.metadata or {}).get("source") if isinstance(item.metadata, dict) else None,
        "metadata": item.metadata or {},
    }

@router.patch("/memory/watchlist/{item_id}")
async def update_watchlist_item(
    item_id: str,
    req: WatchlistUpdateRequest,
    store: WatchlistStorePort = Depends(get_watchlist_store),
) -> Dict[str, Any]:
    try:
        uuid = UUID(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid item_id (expected UUID)")
    try:
        updated = await store.update_item(
            user_id=req.user_id,
            item_id=uuid,
            title=req.title,
            year=req.year,
            status=req.status,
            metadata=req.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail="watchlist item not found")
    return {
        "id": str(updated.id),
        "title": updated.title,
        "year": updated.year,
        "status": getattr(updated, "status", "to_watch"),
        "created_at": updated.created_at,
        "updated_at": getattr(updated, "updated_at", None),
        "deleted_at": getattr(updated, "deleted_at", None),
        "source": (updated.metadata or {}).get("source") if isinstance(updated.metadata, dict) else None,
        "metadata": updated.metadata or {},
    }


@router.delete("/memory/watchlist/{item_id}", status_code=204, response_class=Response)
async def delete_watchlist_item(
    item_id: str,
    user_id: str = Query(..., description="用户ID（用于权限校验/审计）"),
    store: WatchlistStorePort = Depends(get_watchlist_store),
) -> Response:
    try:
        uuid = UUID(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid item_id (expected UUID)")
    ok = await store.delete_item(user_id=user_id, item_id=uuid)
    if not ok:
        raise HTTPException(status_code=404, detail="watchlist item not found")
    return Response(status_code=204)


@router.post("/memory/watchlist/{item_id}/restore")
async def restore_watchlist_item(
    item_id: str,
    user_id: str = Query(..., description="用户ID（用于权限校验/审计）"),
    store: WatchlistStorePort = Depends(get_watchlist_store),
) -> Dict[str, Any]:
    try:
        uuid = UUID(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid item_id (expected UUID)")
    restored = await store.restore_item(user_id=user_id, item_id=uuid)
    if restored is None:
        raise HTTPException(status_code=404, detail="watchlist item not found")
    return {
        "id": str(restored.id),
        "title": restored.title,
        "year": restored.year,
        "status": getattr(restored, "status", "to_watch"),
        "created_at": restored.created_at,
        "updated_at": getattr(restored, "updated_at", None),
        "deleted_at": getattr(restored, "deleted_at", None),
        "source": (restored.metadata or {}).get("source") if isinstance(restored.metadata, dict) else None,
        "metadata": restored.metadata or {},
    }


@router.post("/memory/watchlist/dedup_merge")
async def dedup_merge_watchlist(
    user_id: str = Query(..., description="用户ID"),
    store: WatchlistStorePort = Depends(get_watchlist_store),
) -> Dict[str, Any]:
    result = await store.dedup_merge(user_id=user_id)
    return {"result": result or {}}
