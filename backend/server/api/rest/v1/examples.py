from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from server.api.rest.dependencies import get_example_store

router = APIRouter(prefix="/api/v1", tags=["examples"])


@router.get("/examples", response_model=List[str])
async def list_examples(
    store=Depends(get_example_store),
) -> List[str]:
    """获取推荐的示例问题列表。"""
    return await store.list_examples()
