"""Conversations list API endpoint."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from server.api.rest.dependencies import get_conversation_store

router = APIRouter(prefix="/api/v1", tags=["conversations"])


@router.get("/conversations", response_model=List[Dict[str, Any]])
async def list_conversations(
    user_id: str = Query(..., description="用户ID"),
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="分页偏移量"),
    store=Depends(get_conversation_store),
) -> List[Dict[str, Any]]:
    """列出用户的历史会话列表，按更新时间倒序。"""
    return await store.list_conversations(user_id=user_id, limit=limit, offset=offset)
