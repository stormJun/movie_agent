from __future__ import annotations

from fastapi import APIRouter, Depends

from server.api.rest.dependencies import get_chat_handler
from application.chat.handlers.chat_handler import ChatHandler
from server.models.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/api/v1", tags=["chat-v1"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    handler: ChatHandler = Depends(get_chat_handler),
) -> ChatResponse:
    result = await handler.handle(
        user_id=request.user_id,
        message=request.message,
        session_id=request.session_id,
        kb_prefix=request.kb_prefix,
        debug=request.debug,
        agent_type=request.agent_type,
    )
    return result
