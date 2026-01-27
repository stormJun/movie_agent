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
    # 非流式接口：最佳努力写入 Langfuse（不影响主链路返回）。
    from infrastructure.observability.langfuse_handler import LANGFUSE_ENABLED, _get_langfuse_client
    from infrastructure.observability import use_langfuse_request_context

    langfuse_trace = None
    request_id = None
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
                        "incognito": bool(request.incognito),
                        "watchlist_auto_capture": request.watchlist_auto_capture,
                    },
                )
                request_id = langfuse_trace.id

    if request_id is None:
        import uuid

        # 未启用 Langfuse 或 client 不可用时，用 uuid 作为 request_id（同样可用于 debug 关联）。
        request_id = str(uuid.uuid4())

    with use_langfuse_request_context(
        stateful_client=langfuse_trace,
        user_id=request.user_id,
        session_id=request.session_id,
    ):
        # ChatHandler 会负责：路由 -> recall -> retrieval -> (optional) enrichment -> generation -> side effects
        result = await handler.handle(
            user_id=request.user_id,
            message=request.message,
            session_id=request.session_id,
            kb_prefix=request.kb_prefix,
            debug=request.debug,
            incognito=bool(request.incognito),
            watchlist_auto_capture=request.watchlist_auto_capture,
            agent_type=request.agent_type,
            request_id=request_id,
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
