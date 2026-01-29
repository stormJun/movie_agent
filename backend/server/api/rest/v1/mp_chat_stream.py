from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic import ConfigDict

from application.chat.handlers.stream_handler import StreamHandler
from application.ports.conversation_store_port import ConversationStorePort
from config.settings import SSE_HEARTBEAT_S
from infrastructure.streaming.sse import format_sse
from server.api.rest.dependencies import get_stream_handler
from server.api.rest.dependencies import get_conversation_store
from server.models.stream_events import normalize_stream_event

router = APIRouter(prefix="/api/v1/mp", tags=["mp-v1"])


class MiniProgramChatRequest(BaseModel):
    """MiniProgram streaming chat request (no user-selected agent_type)."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    session_id: str
    message: str
    kb_prefix: Optional[str] = None
    debug: bool = False
    incognito: Optional[bool] = False
    watchlist_auto_capture: Optional[bool] = None
    # Keep these for forward-compat (MiniProgram reference project may send them).
    use_deeper_tool: Optional[bool] = True
    show_thinking: Optional[bool] = False


def _map_web_event_to_mp(payload: dict[str, Any], *, request_id: str) -> dict[str, Any] | None:
    """Map the existing Web SSE contract to the MiniProgram SSE contract.

    MiniProgram reference client consumes:
      - generate_start
      - chunk
      - complete
    """

    status = str(payload.get("status") or "")
    if status == "start":
        return {"type": "generate_start", "content": {"request_id": payload.get("request_id") or request_id}}
    if status == "token" or status == "answer":
        return {"type": "chunk", "content": str(payload.get("content") or "")}
    if status == "done":
        # IMPORTANT: keep `content` falsy so MiniProgram controller doesn't render "[object Object]".
        return {"type": "complete", "content": None, "request_id": payload.get("request_id") or request_id}
    if status == "error":
        msg = payload.get("message") if isinstance(payload.get("message"), str) else None
        return {"type": "error", "content": {"message": msg or "unknown error"}}
    if status == "recommendations":
        content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
        return {"type": "recommendations", "content": content}

    if status == "progress":
        # Forward lightweight progress updates so the MiniProgram UI can show
        # "routing / retrieval / generation" instead of silence before first token.
        content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
        return {"type": "status", "content": content}

    if status == "route_decision":
        # When debug=true, the router emits a route_decision payload; surface it as a
        # status update so UI can show the selected agent early.
        content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
        return {"type": "status", "content": {"stage": "routing", **content}}

    # Ignore debug-only noise for MiniProgram.
    return None


@router.post("/chat/stream")
async def mp_chat_stream(
    raw_request: Request,
    request: MiniProgramChatRequest,
    handler: StreamHandler = Depends(get_stream_handler),
    conversation_store: ConversationStorePort = Depends(get_conversation_store),
) -> StreamingResponse:
    """MiniProgram streaming chat endpoint (SSE over chunked HTTP)."""

    async def event_generator():
        sent_complete = False
        client_disconnected = False

        # Align with Web endpoint: prefer Langfuse trace id when enabled.
        from infrastructure.observability.langfuse_handler import LANGFUSE_ENABLED, _get_langfuse_client

        langfuse_trace = None
        if LANGFUSE_ENABLED:
            langfuse = _get_langfuse_client()
            if langfuse:
                langfuse_trace = langfuse.trace(
                    name="mp_chat_stream",
                    user_id=request.user_id,
                    session_id=request.session_id,
                    input=request.message,
                    metadata={
                        "kb_prefix": request.kb_prefix,
                        "debug": request.debug,
                        "incognito": bool(request.incognito),
                        "watchlist_auto_capture": request.watchlist_auto_capture,
                    },
                )
                request_id = langfuse_trace.id
            else:
                request_id = str(uuid.uuid4())
        else:
            request_id = str(uuid.uuid4())

        # First frame: request_id
        yield format_sse({"type": "generate_start", "content": {"request_id": request_id}})

        # Resolve conversation_id once so we can attach message ids to the final frame
        # (MiniProgram needs message_id/thread_id for per-message feedback UI).
        try:
            conversation_id = await conversation_store.get_or_create_conversation_id(
                user_id=request.user_id,
                session_id=request.session_id,
            )
        except Exception:
            conversation_id = None

        # Bind downstream spans to the same Langfuse trace (best-effort).
        from infrastructure.observability import use_langfuse_request_context

        iterator = None
        scoped = use_langfuse_request_context(
            stateful_client=langfuse_trace,
            user_id=request.user_id,
            session_id=request.session_id,
        )
        scoped.__enter__()
        try:
            iterator = handler.handle(
                user_id=request.user_id,
                message=request.message,
                session_id=request.session_id,
                kb_prefix=request.kb_prefix,
                debug=bool(request.debug),
                incognito=bool(request.incognito),
                watchlist_auto_capture=request.watchlist_auto_capture,
                request_id=request_id,
            ).__aiter__()
        except Exception:
            scoped.__exit__(None, None, None)
            raise

        full_response: list[str] = []
        route_selected_agent: str | None = None
        pending_reco_ids: list[int] = []
        pending_reco_title: str | None = None

        next_event_task: asyncio.Task | None = None
        try:
            # See `chat_stream.py`: avoid cancelling the generator on heartbeat timeouts.
            next_event_task = asyncio.create_task(iterator.__anext__())
            while True:
                if await raw_request.is_disconnected():
                    client_disconnected = True
                    break

                timeout_s = max(float(SSE_HEARTBEAT_S), 1.0)
                done, _pending = await asyncio.wait(
                    {next_event_task},
                    timeout=timeout_s,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    yield ": ping\n\n"
                    continue

                try:
                    event = next_event_task.result()
                except StopAsyncIteration:
                    break

                next_event_task = asyncio.create_task(iterator.__anext__())

                web_payload = normalize_stream_event(event)
                status = str(web_payload.get("status") or "")

                if status == "route_decision":
                    content = web_payload.get("content")
                    if isinstance(content, dict):
                        sel = content.get("selected_agent")
                        if isinstance(sel, str) and sel.strip():
                            route_selected_agent = sel.strip()

                if status == "recommendations":
                    content = web_payload.get("content")
                    if isinstance(content, dict):
                        mode = content.get("mode")
                        ids = content.get("tmdb_ids")
                        if mode is None or str(mode) == "tmdb_recommendations":
                            if isinstance(ids, list):
                                # Keep ints only (MiniProgram expects id list).
                                pending_reco_ids = [
                                    int(x) for x in ids if isinstance(x, (int, str)) and str(x).isdigit()
                                ]
                            t = content.get("title")
                            if isinstance(t, str) and t.strip():
                                pending_reco_title = t.strip()

                if status in {"token", "answer"}:
                    content = web_payload.get("content", "")
                    if content:
                        full_response.append(str(content))

                if status == "done":
                    sent_complete = True
                    answer_text = "".join(full_response)
                    meta: dict[str, Any] = {
                        "request_id": request_id,
                        "query": request.message,
                    }
                    if conversation_id is not None:
                        meta["thread_id"] = str(conversation_id)
                        # Best-effort: attach the latest assistant message id.
                        try:
                            rows = await conversation_store.list_messages(
                                conversation_id=conversation_id,
                                limit=10,
                                desc=True,
                            )
                            assistant_id = None
                            user_id = None
                            for r in rows:
                                if assistant_id is None and r.get("role") == "assistant":
                                    assistant_id = r.get("id")
                                if user_id is None and r.get("role") == "user":
                                    user_id = r.get("id")
                                if assistant_id is not None and user_id is not None:
                                    break
                            if assistant_id is not None:
                                meta["message_id"] = str(assistant_id)
                            if user_id is not None:
                                meta["user_message_id"] = str(user_id)
                        except Exception:
                            pass

                    # Prefer router-selected agent when available (debug mode).
                    meta["agent_type"] = route_selected_agent or "hybrid_agent"

                    yield format_sse(
                        {
                            "type": "complete",
                            "content": None,
                            "request_id": request_id,
                            "answer": answer_text,
                            # Align with the reference MiniProgram: ids are carried in the final frame.
                            "response": {
                                "extracted_info": {
                                    "recommendation_ids": pending_reco_ids,
                                    "recommendation_title": pending_reco_title,
                                }
                            },
                            "meta": meta,
                        }
                    )
                    continue

                mp_payload = _map_web_event_to_mp(web_payload, request_id=request_id)
                if mp_payload is not None:
                    yield format_sse(mp_payload)
        finally:
            if next_event_task is not None and not next_event_task.done():
                next_event_task.cancel()
            aclose = getattr(iterator, "aclose", None)
            if callable(aclose):
                await aclose()
            scoped.__exit__(None, None, None)

        if langfuse_trace is not None and not client_disconnected:
            langfuse_trace.update(output="".join(full_response))
            langfuse = _get_langfuse_client()
            if langfuse:
                langfuse.flush()

        if not sent_complete and not client_disconnected:
            yield format_sse(
                {
                    "type": "complete",
                    "content": None,
                    "request_id": request_id,
                    "answer": "".join(full_response),
                    "response": {
                        "extracted_info": {
                            "recommendation_ids": pending_reco_ids,
                            "recommendation_title": pending_reco_title,
                        }
                    },
                    "meta": {
                        "request_id": request_id,
                        "query": request.message,
                        "thread_id": str(conversation_id) if conversation_id is not None else None,
                        "agent_type": route_selected_agent or "hybrid_agent",
                    },
                }
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router", "MiniProgramChatRequest", "_map_web_event_to_mp"]
