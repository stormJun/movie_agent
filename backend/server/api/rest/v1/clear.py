from __future__ import annotations

from fastapi import APIRouter, Depends

from infrastructure.chat import AgentHistoryService
from server.api.rest.dependencies import get_clear_history_service
from server.models.schemas import ClearRequest, ClearResponse


router = APIRouter(prefix="/api/v1", tags=["chat-v1"])


@router.post("/clear", response_model=ClearResponse)
async def clear(
    request: ClearRequest,
    service: AgentHistoryService = Depends(get_clear_history_service),
) -> ClearResponse:
    return await service.clear_history(
        user_id=request.user_id,
        session_id=request.session_id,
        kb_prefix=request.kb_prefix,
    )
