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
CACHE_ONLY_EVENT_TYPES = {
    "execution_log",
    "route_decision",
    "rag_runs",
    "combined_context",
    "episodic_memory",
    "conversation_summary",
}
# Debug events to both cache and forward (useful to inspect post-hoc).
CACHE_AND_FORWARD_TYPES = {"progress", "error"}
DEBUG_EVENT_TYPES = CACHE_ONLY_EVENT_TYPES | CACHE_AND_FORWARD_TYPES


@router.post("/chat/stream")
async def chat_stream(
    raw_request: Request,
    request: ChatRequest,
    handler: StreamHandler = Depends(get_stream_handler),
) -> StreamingResponse:
    """流式对话接口：SSE 事件流 + Debug 缓存分离"""

    async def event_generator():
        sent_done = False
        client_disconnected = False

        # ===== 阶段 1：生成 request_id（优先复用 Langfuse trace id）=====
        from infrastructure.observability.langfuse_handler import (
            LANGFUSE_ENABLED,
            _get_langfuse_client,
        )

        langfuse_trace = None
        if LANGFUSE_ENABLED:
            langfuse = _get_langfuse_client()
            if langfuse:
                langfuse_trace = langfuse.trace(
                    name="chat_stream",
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

        # ===== 阶段 2：创建 DebugCollector（debug=True 时）=====
        collector = None
        if request.debug:
            from infrastructure.debug.debug_collector import DebugDataCollector

            # debug=true 时创建 per-request 的调试收集器；它不会直接推送到 SSE，
            # 而是缓存起来，供前端用 request_id 拉取 /api/v1/debug/{request_id}。
            collector = DebugDataCollector(
                request_id=request_id,
                user_id=request.user_id,
                session_id=request.session_id,
            )

        # ===== 阶段 3：发送 SSE 第一帧（告知前端 request_id）=====
        yield format_sse({"status": "start", "request_id": request_id})

        # ===== 阶段 4：建立 Langfuse 上下文（绑定下游 LangChain/LangGraph span）=====
        # 将下游 LangChain/LangGraph 的 span/callback 绑定到该 root trace，
        # 避免出现"HTTP trace 和 LLM trace 分裂"的情况。
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
                debug=request.debug,
                incognito=bool(request.incognito),
                watchlist_auto_capture=request.watchlist_auto_capture,
                request_id=request_id,
            ).__aiter__()
        except Exception:
            scoped.__exit__(None, None, None)
            raise

        # Langfuse trace 需要最终完整文本；流式阶段逐 token 累积。
        full_response = []

        # ===== 阶段 5：主循环（遍历 StreamHandler 事件 + SSE/Debug 分离）=====
        try:
            while True:
                # 客户端断连：停止向外写 SSE，并让下游生成器尽快取消/释放资源。
                if await raw_request.is_disconnected():
                    client_disconnected = True
                    break

                try:
                    event = await asyncio.wait_for(
                        iterator.__anext__(),
                        timeout=max(float(SSE_HEARTBEAT_S), 1.0),
                    )
                except asyncio.TimeoutError:
                    # SSE keep-alive：EventSource 会忽略 comment 帧，但能避免中间代理超时断开。
                    yield ": ping\n\n"
                    continue
                except StopAsyncIteration:
                    break

                payload = normalize_stream_event(event)
                status = payload.get("status") if isinstance(payload, dict) else None

                # ----- 5.1 累积 token 到 Langfuse trace（方便后续在 Langfuse UI 中查看）-----
                if status == "answer" or status == "token":
                    content = payload.get("content", "")
                    if content:
                        full_response.append(str(content))
                # Handle progress events that might contain content chunks if schema changes
                elif status == "progress":
                     # Usually progress doesn't have the main answer text, but just in case
                     pass

                # ----- 5.2 处理 done 事件（写入 DebugCache）-----
                # done 事件必须带 request_id：前端据此拉取 debug cache。
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

                # ----- 5.3 Debug 事件分流（cache-only vs cache-and-forward）-----
                # debug 事件分两类：
                # - cache-only：只写入 debug_cache，不推给前端（避免污染 SSE token 流）
                # - cache-and-forward：既缓存也推送（例如 progress / error）
                if collector is not None and request.debug and status in DEBUG_EVENT_TYPES:
                    if status == "error":
                        collector.add_event(status, {"message": payload.get("message", "")})
                    else:
                        collector.add_event(status, payload.get("content", {}))

                # ----- 5.4 SSE 转发（除 cache-only 事件外）-----
                # 除 cache-only 事件外，其余事件都通过 SSE 发送给前端。
                if status not in CACHE_ONLY_EVENT_TYPES:
                    yield format_sse(payload)
        finally:
            # Propagate cancellation/close to the underlying async generator so
            # it can cancel fanout tasks (retrieval) and release resources.
            aclose = getattr(iterator, "aclose", None)
            if callable(aclose):
                await aclose()
            scoped.__exit__(None, None, None)

        # ===== 阶段 6：后处理（DebugCache 回写 / Langfuse trace 更新）=====
        # Store cached debug data if we didn't already store it on done.
        if collector is not None and request.debug and not client_disconnected:
            from infrastructure.debug.debug_cache import debug_cache

            debug_cache.set(request_id, collector)

        # ----- 6.1 更新 Langfuse trace output（最佳努力）-----
        # 更新 Langfuse trace 的 output（最佳努力；不影响主链路返回）。
        if langfuse_trace is not None:
            final_output = "".join(full_response)
            langfuse_trace.update(
                output=final_output
            )
            # Flush to ensure data is sent to Langfuse server
            langfuse = _get_langfuse_client()
            if langfuse:
                langfuse.flush()

        # ----- 6.2 发送兜底 done 事件（如果之前未发送）-----
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
