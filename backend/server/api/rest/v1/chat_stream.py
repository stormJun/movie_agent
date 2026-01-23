from __future__ import annotations

import asyncio
import uuid

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

# Cache-only debug events (NOT forwarded to client).
CACHE_ONLY_EVENT_TYPES = {"execution_log", "route_decision", "rag_runs"}
# Debug events to both cache and forward (useful to inspect post-hoc).
CACHE_AND_FORWARD_TYPES = {"progress", "error"}
DEBUG_EVENT_TYPES = CACHE_ONLY_EVENT_TYPES | CACHE_AND_FORWARD_TYPES


@router.post("/chat/stream")
async def chat_stream(
    raw_request: Request,
    request: ChatRequest,
    handler: StreamHandler = Depends(get_stream_handler),
) -> StreamingResponse:
    async def event_generator():
        sent_done = False
        client_disconnected = False

        request_id = str(uuid.uuid4())

        collector = None
        if request.debug:
            from infrastructure.debug.debug_collector import DebugDataCollector

            collector = DebugDataCollector(
                request_id=request_id,
                user_id=request.user_id,
                session_id=request.session_id,
            )

        yield format_sse({"status": "start", "request_id": request_id})

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
                    client_disconnected = True
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

                status = payload.get("status") if isinstance(payload, dict) else None

                # Inject request_id into done events so clients can fetch debug payloads.
                if status == "done":
                    if "request_id" not in payload:
                        payload["request_id"] = request_id
                    sent_done = True

                    # Set cache BEFORE forwarding done to avoid a race where the client
                    # fetches debug data immediately after receiving done.
                    if collector is not None and request.debug and not client_disconnected:
                        from infrastructure.debug.debug_cache import debug_cache

                        debug_cache.set(request_id, collector)
                        collector = None  # avoid double-set in finally

                # Cache debug events (some are not forwarded to the client).
                if collector is not None and request.debug and status in DEBUG_EVENT_TYPES:
                    if status == "error":
                        collector.add_event(status, {"message": payload.get("message", "")})
                    else:
                        collector.add_event(status, payload.get("content", {}))

                # Forward everything except cache-only debug events.
                if status not in CACHE_ONLY_EVENT_TYPES:
                    yield format_sse(payload)
        finally:
            # Propagate cancellation/close to the underlying async generator so
            # it can cancel fanout tasks (retrieval) and release resources.
            aclose = getattr(iterator, "aclose", None)
            if callable(aclose):
                await aclose()

        # Store cached debug data if we didn't already store it on done.
        if collector is not None and request.debug and not client_disconnected:
            from infrastructure.debug.debug_cache import debug_cache

            debug_cache.set(request_id, collector)

        if not sent_done:
            yield format_sse({"status": "done", "request_id": request_id})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
