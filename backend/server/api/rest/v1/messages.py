"""Messages list API endpoint."""
from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from server.api.rest.dependencies import get_conversation_store

router = APIRouter(prefix="/api/v1", tags=["messages"])


@router.get("/messages", response_model=List[Dict[str, Any]])
async def list_messages(
    conversation_id: str = Query(..., description="会话ID (UUID)"),
    limit: int = Query(100, ge=1, le=500, description="返回数量限制"),
    store=Depends(get_conversation_store),
) -> List[Dict[str, Any]]:
    """获取指定会话的历史消息列表。"""
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        return []
    return await store.list_messages(conversation_id=conv_uuid, limit=limit)
