from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from fastapi import Request
from fastapi.responses import StreamingResponse

from server.api.rest.dependencies import get_stream_handler
from application.chat.handlers.stream_handler import StreamHandler
from infrastructure.streaming.sse import format_sse
from config.settings import SSE_HEARTBEAT_S
from server.models.schemas import ChatRequest
from server.models.stream_events import normalize_stream_event

router = APIRouter(prefix="/api/v1", tags=["chat-v1"])


@router.post("/chat/stream")
async def chat_stream(
    raw_request: Request,
    request: ChatRequest,
    handler: StreamHandler = Depends(get_stream_handler),
) -> StreamingResponse:
    async def event_generator():
        sent_done = False
        yield format_sse({"status": "start"})

        iterator = handler.handle(
            user_id=request.user_id,
            message=request.message,
            session_id=request.session_id,
            kb_prefix=request.kb_prefix,
            debug=request.debug,
            agent_type=request.agent_type,
        ).__aiter__()

        try:
            while True:
                if await raw_request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        iterator.__anext__(),
                        timeout=max(float(SSE_HEARTBEAT_S), 1.0),
                    )
                except asyncio.TimeoutError:
                    # SSE comment frames: ignored by EventSource/clients, but keep
                    # the connection alive through proxies.
                    yield ": ping\n\n"
                    continue
                except StopAsyncIteration:
                    break

                payload = normalize_stream_event(event)

                if isinstance(payload, dict) and payload.get("status") == "done":
                    sent_done = True
                yield format_sse(payload)
        finally:
            # Propagate cancellation/close to the underlying async generator so
            # it can cancel fanout tasks (retrieval) and release resources.
            aclose = getattr(iterator, "aclose", None)
            if callable(aclose):
                await aclose()

        if not sent_done:
            yield format_sse({"status": "done"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
