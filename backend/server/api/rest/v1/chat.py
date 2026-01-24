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
    # Best-effort Langfuse trace for non-streaming endpoint.
    from infrastructure.observability.langfuse_handler import LANGFUSE_ENABLED, _get_langfuse_client
    from infrastructure.observability import use_langfuse_request_context

    langfuse_trace = None
    if LANGFUSE_ENABLED:
        langfuse = _get_langfuse_client()
        if langfuse:
            langfuse_trace = langfuse.trace(
                name="chat",
                user_id=request.user_id,
                session_id=request.session_id,
                input=request.message,
                metadata={
                    "kb_prefix": request.kb_prefix,
                    "agent_type": request.agent_type,
                    "debug": request.debug,
                },
            )

    with use_langfuse_request_context(
        stateful_client=langfuse_trace,
        user_id=request.user_id,
        session_id=request.session_id,
    ):
        result = await handler.handle(
            user_id=request.user_id,
            message=request.message,
            session_id=request.session_id,
            kb_prefix=request.kb_prefix,
            debug=request.debug,
            agent_type=request.agent_type,
        )

    if langfuse_trace is not None:
        try:
            langfuse_trace.update(output=result.get("answer"))
            langfuse = _get_langfuse_client()
            if langfuse:
                langfuse.flush()
        except Exception:
            pass
    return result
