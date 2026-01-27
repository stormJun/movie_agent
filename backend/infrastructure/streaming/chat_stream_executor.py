"""
ChatStreamExecutor：流式 RAG 执行器

核心功能：
1. 并发执行多个检索策略（RagRunSpec[]），超时控制，取消传播
2. 可选的 Query-time Enrichment（movie KB 专用 TMDB 补全）
3. 基于 combined_context 流式生成 RAG 答案
4. 完整的 observability 集成（Langfuse span + execution_log）

关键特性：
- Fanout 并行：多个 agent_type 同时检索，as_completed 完成一个推送一个
- 超时保护：overall_timeout_s = max(spec.timeout_s) + RAG_ANSWER_TIMEOUT_S
- 取消传播：客户端断连时取消所有检索任务
- Debug 事件：execution_log / combined_context / rag_runs 用于 DebugDrawer
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator

from infrastructure.config.settings import RAG_ANSWER_TIMEOUT_S
from infrastructure.llm.completion import (
    generate_general_answer_stream,
    generate_rag_answer_stream,
)
from infrastructure.rag.answer_generator import build_context_from_runs
from infrastructure.config.settings import DEBUG_COMBINED_CONTEXT_MAX_CHARS
from infrastructure.rag.rag_manager import RagManager
from infrastructure.rag.specs import RagRunSpec

logger = logging.getLogger(__name__)

# Debug 预览配置（避免 dumping 完整检索结果）
_DEBUG_RETRIEVAL_PREVIEW_N = 3  # 只预览前 3 条结果
_DEBUG_EVIDENCE_PREVIEW_CHARS = 240  # 每条证据预览 240 字符
_DEBUG_TOP_SOURCE_IDS_N = 8  # 展示前 8 个 source_id 统计


def _truncate_text(value: str, limit: int) -> str:
    """截断文本到指定长度（避免 debug payload 过大）"""
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + "…"


def _summarize_retrieval_results(results: Any) -> dict[str, Any]:
    """
    汇总检索结果用于 debug 日志（避免 dumping 完整 payload）

    返回：
    - retrieval_count: 总检索结果数
    - granularity_counts: 粒度分布（entity/community/chunk）
    - top_source_ids: 出现最多的前 N 个 source_id
    - sample_results: 前 N 条结果的预览（score/evidence/metadata）
    """
    if not isinstance(results, list):
        return {
            "retrieval_count": 0,
            "granularity_counts": {},
            "top_source_ids": [],
            "sample_results": [],
        }

    granularity_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    sample_results: list[dict[str, Any]] = []

    for idx, item in enumerate(results):
        if not isinstance(item, dict):
            continue

        granularity = str(item.get("granularity") or "").strip() or "unknown"
        granularity_counts[granularity] = granularity_counts.get(granularity, 0) + 1

        metadata = item.get("metadata")
        source_id = None
        if isinstance(metadata, dict):
            raw_source_id = metadata.get("source_id")
            if isinstance(raw_source_id, str) and raw_source_id.strip():
                source_id = raw_source_id.strip()
                source_counts[source_id] = source_counts.get(source_id, 0) + 1

        if idx < _DEBUG_RETRIEVAL_PREVIEW_N:
            evidence = item.get("evidence")
            evidence_preview = (
                _truncate_text(evidence, _DEBUG_EVIDENCE_PREVIEW_CHARS)
                if isinstance(evidence, str) and evidence
                else ""
            )
            meta_preview: dict[str, Any] = {}
            if isinstance(metadata, dict):
                # Only surface a small, commonly useful subset.
                for k in (
                    "source_id",
                    "chunk_id",
                    "doc_id",
                    "file_name",
                    "title",
                    "url",
                    "page",
                    "page_number",
                ):
                    if k in metadata:
                        meta_preview[k] = metadata.get(k)

            sample_results.append(
                {
                    "score": item.get("score"),
                    "granularity": granularity,
                    "source_id": source_id,
                    "metadata": meta_preview,
                    "evidence_preview": evidence_preview,
                }
            )

    top_source_ids = sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[
        :_DEBUG_TOP_SOURCE_IDS_N
    ]

    return {
        "retrieval_count": len(results),
        "granularity_counts": granularity_counts,
        "top_source_ids": [{"source_id": k, "count": v} for k, v in top_source_ids],
        "sample_results": sample_results,
    }


class ChatStreamExecutor:
    """
    流式 RAG 执行器：支持并发检索、超时控制、取消传播

    核心流程：
    1. 非 RAG 模式（plan 为空）→ 直接生成通用答案
    2. RAG 模式：
       a. Fanout 并行检索（多个 agent_type 同时执行）
       b. Query-time Enrichment（movie KB 专用 TMDB 补全）
       c. 基于 combined_context 流式生成答案
    """

    def __init__(self, *, rag_manager: RagManager) -> None:
        self._rag_manager = rag_manager

    async def stream(
        self,
        *,
        plan: list[RagRunSpec],  # 检索计划（可包含多个 agent_type）
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        user_id: str | None = None,
        request_id: str | None = None,
        conversation_id: Any | None = None,
        user_message_id: Any | None = None,
        incognito: bool = False,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
        extracted_entities: dict[str, Any] | None = None,  # 用于 enrichment 触发判断
        query_intent: str | None = None,
        media_type_hint: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        # ===== 模式判断：是否需要检索 =====
        use_retrieval = bool(plan) and (kb_prefix or "").strip() not in {"", "general"}

        # ===== 模式 1：非 RAG 模式（通用闲聊）=====
        if not use_retrieval:
            generation_start = time.monotonic()
            generated_chars = 0
            chunk_count = 0
            stage_span = None
            use_client_cm = None
            try:
                from infrastructure.observability import (
                    get_current_langfuse_stateful_client,
                    use_langfuse_stateful_client,
                )

                parent = get_current_langfuse_stateful_client()
                if parent is not None:
                    stage_span = parent.span(
                        name="generation",
                        input={"kb_prefix": kb_prefix, "message_preview": (message or "")[:200]},
                    )
                    use_client_cm = use_langfuse_stateful_client
            except Exception:
                stage_span = None
            yield {
                "status": "progress",
                "content": {
                    "stage": "generation",
                    "completed": 0,
                    "total": 0,
                    "error": None,
                    "agent_type": "",
                    "retrieval_count": None,
                },
            }
            try:
                if stage_span is not None and use_client_cm is not None:
                    with use_client_cm(stage_span):
                        async for chunk in generate_general_answer_stream(
                            question=message,
                            memory_context=memory_context,
                            summary=summary,
                            episodic_context=episodic_context,
                            history=history,
                        ):
                            if chunk:
                                generated_chars += len(chunk)
                                chunk_count += 1
                                yield {"status": "token", "content": chunk}
                else:
                    async for chunk in generate_general_answer_stream(
                        question=message,
                        memory_context=memory_context,
                        summary=summary,
                        episodic_context=episodic_context,
                        history=history,
                    ):
                        if chunk:
                            generated_chars += len(chunk)
                            chunk_count += 1
                            yield {"status": "token", "content": chunk}
            except Exception as e:
                # Protocol: errors are not tokens; callers should distinguish them.
                yield {"status": "error", "message": f"生成答案失败: {e}"}
                if debug:
                    yield {
                        "execution_log": {
                            "node": "answer_error",
                            "node_type": "generation",
                            "duration_ms": int((time.monotonic() - generation_start) * 1000),
                            "input": {"message": message, "kb_prefix": kb_prefix},
                            "output": {"error": str(e)},
                        }
                    }
                if stage_span is not None:
                    stage_span.end(level="ERROR", status_message=str(e), output={"error": str(e)})
            else:
                if debug:
                    yield {
                        "execution_log": {
                            "node": "answer_done",
                            "node_type": "generation",
                            "duration_ms": int((time.monotonic() - generation_start) * 1000),
                            "input": {"message": message, "kb_prefix": kb_prefix},
                            "output": {
                                "generated_chars": generated_chars,
                                "chunk_count": chunk_count,
                            },
                        }
                    }
                if stage_span is not None:
                    stage_span.end(
                        output={"generated_chars": generated_chars, "chunk_count": chunk_count},
                        metadata={"duration_ms": int((time.monotonic() - generation_start) * 1000)},
                    )
            yield {"status": "done"}
            return

        # ===== 模式 2：RAG 模式（检索 + 生成）=====

        # ---- 阶段 2.1：Debug 日志（plan 概览）----
        if debug:
            yield {
                "execution_log": {
                    "node": "rag_plan",
                    "node_type": "routing",
                    "input": {"message": message, "kb_prefix": kb_prefix},
                    "output": {"plan": [spec.agent_type for spec in plan]},
                }
            }

        # ---- 阶段 2.2：Fanout 并行检索（多个 agent_type 同时执行）----
        # 超时配置：所有 spec 的最大超时 + 答案生成超时
        overall_timeout_s = max(spec.timeout_s for spec in plan) + RAG_ANSWER_TIMEOUT_S
        start_time = time.monotonic()
        runs = []
        total_runs = len(plan)

        # 创建 Langfuse span 用于 observability
        retrieval_stage_start = time.monotonic()
        retrieval_run_elapsed_ms: dict[str, int] = {}
        retrieval_stage_span = None
        try:
            from infrastructure.observability import get_current_langfuse_stateful_client

            parent = get_current_langfuse_stateful_client()
            if parent is not None:
                retrieval_stage_span = parent.span(
                    name="rag_retrieval",
                    input={
                        "kb_prefix": kb_prefix,
                        "message_preview": (message or "")[:200],
                        "plan": [getattr(spec, "agent_type", "") for spec in plan],
                    },
                )
        except Exception:
            retrieval_stage_span = None

        yield {
            "status": "progress",
            "content": {
                "stage": "retrieval",
                "completed": 0,
                "total": total_runs,
                "error": None,
                "agent_type": "",
                "retrieval_count": None,
            },
        }

        # 创建并发检索任务（每个 agent_type 一个 task）
        retrieval_tasks: list[asyncio.Task] = []
        task_started_at: dict[asyncio.Task, float] = {}  # 记录每个任务的启动时间
        task_span: dict[asyncio.Task, Any] = {}  # 记录每个任务的 Langfuse span
        for spec in plan:
            span = None
            if retrieval_stage_span is not None:
                try:
                    span = retrieval_stage_span.span(
                        name="rag_retrieval_spec",
                        input={
                            "agent_type": getattr(spec, "agent_type", None),
                            "worker_name": getattr(spec, "worker_name", None),
                            "timeout_s": getattr(spec, "timeout_s", None),
                        },
                    )
                except Exception:
                    span = None
            task = asyncio.create_task(
                self._rag_manager.run_retrieval_for_spec(
                    spec=spec,
                    message=message,
                    session_id=session_id,
                    kb_prefix=kb_prefix,
                    debug=debug,
                )
            )
            retrieval_tasks.append(task)
            task_started_at[task] = time.monotonic()
            if span is not None:
                task_span[task] = span

        # 使用 as_completed 并发执行（完成一个推送一个）
        try:
            for task in asyncio.as_completed(retrieval_tasks, timeout=overall_timeout_s):
                run = await task
                runs.append(run)
                started_at = task_started_at.get(task)
                if started_at is not None:
                    retrieval_run_elapsed_ms[run.agent_type] = int(
                        (time.monotonic() - started_at) * 1000
                    )
                span = task_span.get(task)
                if span is not None:
                    summary = _summarize_retrieval_results(run.retrieval_results or [])
                    if run.error:
                        span.end(
                            level="ERROR",
                            status_message=str(run.error),
                            output={"error": run.error},
                            metadata={
                                "elapsed_ms": retrieval_run_elapsed_ms.get(run.agent_type, 0),
                                "retrieval_count": summary.get("retrieval_count", 0),
                            },
                        )
                    else:
                        span.end(
                            output={
                                "retrieval_count": summary.get("retrieval_count", 0),
                                "granularity_counts": summary.get("granularity_counts", {}),
                                "top_source_ids": summary.get("top_source_ids", []),
                            },
                            metadata={"elapsed_ms": retrieval_run_elapsed_ms.get(run.agent_type, 0)},
                        )
                yield {
                    "status": "progress",
                    "content": {
                        "stage": "retrieval",
                        "agent_type": run.agent_type,
                        "retrieval_count": len(run.retrieval_results or []),
                        "completed": len(runs),
                        "total": total_runs,
                        "error": run.error,
                    },
                }
                if debug:
                    summary = _summarize_retrieval_results(run.retrieval_results or [])

                    # Include sub-step execution_log from the agent
                    agent_execution_log = run.execution_log if run.execution_log else []

                    yield {
                        "execution_log": {
                            "node": "rag_retrieval_done",
                            "node_type": "retrieval",
                            "input": {"agent_type": run.agent_type},
                            "output": {
                                "error": run.error,
                                "retrieval_count": summary.get("retrieval_count", 0),
                                "elapsed_ms": retrieval_run_elapsed_ms.get(run.agent_type, 0),
                                "granularity_counts": summary.get("granularity_counts", {}),
                                "top_source_ids": summary.get("top_source_ids", []),
                                "sample_results": summary.get("sample_results", []),
                            },
                            "sub_steps": agent_execution_log,
                        }
                    }
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            if debug:
                yield {
                    "execution_log": {
                        "node": "rag_timeout",
                        "node_type": "retrieval",
                        "duration_ms": int((time.monotonic() - retrieval_stage_start) * 1000),
                        "input": {"message": message, "kb_prefix": kb_prefix},
                        "output": {"timeout_s": overall_timeout_s},
                    }
                }
            yield {"status": "error", "message": f"RAG 执行超时: {overall_timeout_s}s"}
            if retrieval_stage_span is not None:
                retrieval_stage_span.end(
                    level="ERROR",
                    status_message=f"timeout after {overall_timeout_s}s",
                    output={"timeout_s": overall_timeout_s},
                )
            yield {"status": "done"}
            return
        finally:
            # ===== 取消传播：客户端断连时取消所有检索任务 =====
            # If the client disconnects, the outer SSE generator cancels us; make sure
            # fanout retrieval tasks are cancelled so they don't keep running.
            pending = [t for t in retrieval_tasks if not t.done()]
            for t in pending:
                t.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for t in pending:
                span = task_span.get(t)
                if span is not None:
                    span.end(level="ERROR", status_message="cancelled", output={"cancelled": True})

        if debug:
            # Wall-clock retrieval stage time (not sum of per-agent times).
            yield {
                "execution_log": {
                    "node": "rag_retrieval_stage_done",
                    "node_type": "retrieval",
                    "duration_ms": int((time.monotonic() - retrieval_stage_start) * 1000),
                    "input": {"total_runs": total_runs},
                    "output": {
                        "completed_runs": len(runs),
                        "errors": {r.agent_type: r.error for r in runs if r.error},
                        "elapsed_ms_by_agent_type": retrieval_run_elapsed_ms,
                    },
                }
            }

        if retrieval_stage_span is not None:
            retrieval_stage_span.end(
                output={
                    "completed_runs": len(runs),
                    "total_runs": total_runs,
                    "errors": {r.agent_type: r.error for r in runs if r.error},
                },
                metadata={"duration_ms": int((time.monotonic() - retrieval_stage_start) * 1000)},
            )

        # ---- 阶段 2.3：合并检索结果（build combined_context）----
        combined_context = build_context_from_runs(
            runs=[
                {"agent_type": r.agent_type, "context": r.context or ""}
                for r in runs
                if not r.error
            ]
        )
        enrichment_appended = False
        generation_question = message
        generation_history = history

        # ---- 阶段 2.4：Query-time Enrichment（movie KB 专用 TMDB 补全）----
        # 查询时增强（Query-time Enrichment，movie KB 专用）：
        # 当 GraphRAG 检索上下文疑似缺少关键实体（例如 KB 未收录《喜宴》/实体抽取失败），
        # 尝试用 TMDB 构建临时图（transient graph），再把结构化证据拼到 combined_context，
        # 让生成阶段"有证据可答"，而不是依赖常识猜。
        if (kb_prefix or "").strip() == "movie":
            try:
                if _should_enrich_by_entity_matching(
                    query=message,
                    graphrag_context=combined_context,
                    extracted_entities=extracted_entities,
                    query_intent=query_intent,
                    media_type_hint=media_type_hint,
                    filters=filters,
                ):
                    logger.debug("Enrichment triggered for movie KB", extra={"kb_prefix": kb_prefix, "message_preview": message[:200]})

                    # Use the canonical import path to avoid duplicate module instances
                    # (e.g., `backend.infrastructure.*` vs `infrastructure.*`).
                    from infrastructure.enrichment import get_tmdb_enrichment_service

                    svc = get_tmdb_enrichment_service()
                    logger.debug(f"Enrichment service retrieved: {svc is not None}")

                    if svc is None:
                        if debug:
                            yield {
                                "execution_log": {
                                    "node": "enrichment_skip",
                                    "node_type": "enrichment",
                                    "input": {"kb_prefix": kb_prefix, "message_preview": (message or "")[:200]},
                                    "output": {"reason": "tmdb enrichment service not configured"},
                                }
                            }
                    else:
                        if debug:
                            # 记录“开始触发 enrichment”的调试节点（不会直接在 SSE 输出，前端用 /debug 拉取）。
                            yield {
                                "execution_log": {
                                    "node": "enrichment_start",
                                    "node_type": "enrichment",
                                    "input": {
                                        "kb_prefix": kb_prefix,
                                        "message_preview": (message or "")[:200],
                                        "extracted_entities": extracted_entities,
                                    },
                                    "output": {"triggered": True},
                                }
                            }

                        t0 = time.monotonic()
                        result = await svc.enrich_query(
                            message=message,
                            kb_prefix=kb_prefix,
                            extracted_entities=extracted_entities,
                            query_intent=query_intent,
                            media_type_hint=media_type_hint,
                            filters=filters,
                            user_id=user_id,
                            session_id=session_id,
                            request_id=request_id,
                            conversation_id=conversation_id,
                            user_message_id=user_message_id,
                            incognito=incognito,
                        )
                        duration_ms = int((time.monotonic() - t0) * 1000)

                        if result.success and result.transient_graph and not result.transient_graph.is_empty():
                            enriched_context = result.transient_graph.to_context_text().strip()
                            if enriched_context:
                                combined_context = f"{combined_context}\n\n{enriched_context}".strip()
                                enrichment_appended = True
                            # 向前端推一个轻量事件（实体候选/选中项/耗时等），便于在调试时间线可视化；
                            # 具体 combined_context 文本仍通过 debug cache 拉取，避免污染 token 流。
                            yield {
                                "status": "enrichment",
                                "content": {
                                    "entities": list(result.extracted_entities or []),
                                    "selected": (result.transient_graph.metadata.get("tmdb_disambiguation") or [])[:1],
                                    "node_count": len(result.transient_graph.nodes),
                                    "edge_count": len(result.transient_graph.edges),
                                    "cached": bool(result.cached),
                                    "duration_ms": float(result.duration_ms or duration_ms),
                                },
                            }
                            if debug:
                                yield {
                                    "execution_log": {
                                        "node": "enrichment_done",
                                        "node_type": "enrichment",
                                        "duration_ms": duration_ms,
                                        "input": {"entities": list(result.extracted_entities or [])},
                                        "output": {
                                            "node_count": len(result.transient_graph.nodes),
                                            "edge_count": len(result.transient_graph.edges),
                                        },
                                    }
                                }
                        else:
                            if debug:
                                yield {
                                    "execution_log": {
                                        "node": "enrichment_noop",
                                        "node_type": "enrichment",
                                        "duration_ms": duration_ms,
                                        "input": {"entities": list(result.extracted_entities or [])},
                                        "output": {
                                            "success": bool(result.success),
                                            "api_errors": list(result.api_errors or []),
                                        },
                                    }
                                }
            except Exception as e:
                logger.debug("query-time enrichment failed: %s", e, exc_info=True)
                if debug:
                    yield {
                        "execution_log": {
                            "node": "enrichment_error",
                            "node_type": "enrichment",
                            "input": {"kb_prefix": kb_prefix, "message_preview": (message or "")[:200]},
                            "output": {"error": str(e)},
                        }
                    }

        # ---- 阶段 2.5：Debug 事件（combined_context + rag_runs）----
        if debug:
            # Cache-only: show the exact retrieval context that will be fed into the
            # generation step (GraphRAG runs + optional enrichment). Truncate to keep
            # debug payloads bounded and UI responsive.
            max_chars = int(DEBUG_COMBINED_CONTEXT_MAX_CHARS or 0) or 20000
            full = str(combined_context or "")
            preview = full if max_chars <= 0 else full[:max_chars]
            yield {
                "status": "combined_context",
                "content": {
                    # 最终喂给 LLM 的上下文（GraphRAG + enrichment 拼接结果）
                    "text": preview,
                    "total_chars": len(full),
                    "max_chars": max_chars,
                    "truncated": len(full) > len(preview),
                    "has_enrichment": bool(enrichment_appended),
                },
            }

        # Cache-only debug event (not required for streaming UX).
        if debug:
            yield {
                "status": "rag_runs",
                "content": [
                    {
                        "agent_type": r.agent_type,
                        "retrieval_count": len(r.retrieval_results or []),
                        "error": str(r.error) if r.error else None,
                        "context_length": len(r.context or ""),
                    }
                    for r in runs
                ],
            }

        # ---- 阶段 2.6：生成阶段（基于 combined_context 流式生成答案）----
        yield {
            "status": "progress",
            "content": {
                "stage": "generation",
                "completed": len(runs),
                "total": total_runs,
                "error": None,
                "agent_type": "",
                "retrieval_count": None,
            },
        }

        # Debug 日志：fanout 完成总结
        if debug:
            yield {
                "execution_log": {
                    "node": "rag_fanout_done",
                    "node_type": "retrieval",
                    "input": {"plan": [r.agent_type for r in runs]},
                    "output": {
                        "errors": {r.agent_type: r.error for r in runs if r.error},
                        "retrieval_counts": {
                            r.agent_type: len(r.retrieval_results or []) for r in runs
                        },
                    },
                }
            }

        # ---- 内部函数：带超时的流式生成器 ----
        async def _stream_with_timeout(
            stream: AsyncGenerator[str, None], timeout_s: float
        ) -> AsyncGenerator[str, None]:
            deadline = time.monotonic() + timeout_s
            iterator = stream.__aiter__()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                try:
                    chunk = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    break
                yield chunk

        generation_started_at: float | None = None
        generated_chars = 0
        chunk_count = 0
        generation_stage_span = None
        use_client_cm = None
        try:
            from infrastructure.observability import (
                get_current_langfuse_stateful_client,
                use_langfuse_stateful_client,
            )

            parent = get_current_langfuse_stateful_client()
            if parent is not None:
                generation_stage_span = parent.span(
                    name="generation",
                    input={
                        "kb_prefix": kb_prefix,
                        "message_preview": (message or "")[:200],
                        "context_chars": len(combined_context or ""),
                    },
                )
                use_client_cm = use_langfuse_stateful_client
        except Exception:
            generation_stage_span = None
        try:
            elapsed = time.monotonic() - start_time
            remaining = max(overall_timeout_s - elapsed, 0.0)
            if remaining <= 0:
                raise asyncio.TimeoutError

            timeout_budget = min(RAG_ANSWER_TIMEOUT_S, remaining)
            generation_started_at = time.monotonic()
            rag_stream = generate_rag_answer_stream(
                question=generation_question,
                context=combined_context,
                memory_context=memory_context,
                summary=summary,
                episodic_context=episodic_context,
                history=generation_history,
            )
            if generation_stage_span is not None and use_client_cm is not None:
                with use_client_cm(generation_stage_span):
                    async for chunk in _stream_with_timeout(rag_stream, timeout_budget):
                        if chunk:
                            generated_chars += len(chunk)
                            chunk_count += 1
                            # SSE token：前端实时拼接 assistant_message.content
                            yield {"status": "token", "content": chunk}
            else:
                async for chunk in _stream_with_timeout(rag_stream, timeout_budget):
                    if chunk:
                        generated_chars += len(chunk)
                        chunk_count += 1
                        # SSE token：前端实时拼接 assistant_message.content
                        yield {"status": "token", "content": chunk}
            if debug:
                yield {
                    "execution_log": {
                        "node": "answer_done",
                        "node_type": "generation",
                        "duration_ms": int(
                            (time.monotonic() - (generation_started_at or time.monotonic()))
                            * 1000
                        ),
                        "input": {"message": message, "kb_prefix": kb_prefix},
                        "output": {
                            "generated_chars": generated_chars,
                            "chunk_count": chunk_count,
                        },
                    }
                }
            if generation_stage_span is not None:
                generation_stage_span.end(
                    output={"generated_chars": generated_chars, "chunk_count": chunk_count},
                    metadata={
                        "duration_ms": int(
                            (time.monotonic() - (generation_started_at or time.monotonic())) * 1000
                        )
                    },
                )
        except asyncio.TimeoutError:
            if debug:
                yield {
                    "execution_log": {
                        "node": "answer_timeout",
                        "node_type": "generation",
                        "duration_ms": int(
                            (time.monotonic() - (generation_started_at or time.monotonic()))
                            * 1000
                        ),
                        "input": {"message": message, "kb_prefix": kb_prefix},
                        "output": {"timeout_s": RAG_ANSWER_TIMEOUT_S},
                    }
                }
            yield {"status": "error", "message": f"生成答案超时: {RAG_ANSWER_TIMEOUT_S}s"}
            if generation_stage_span is not None:
                generation_stage_span.end(
                    level="ERROR",
                    status_message=f"timeout after {RAG_ANSWER_TIMEOUT_S}s",
                    output={"timeout_s": RAG_ANSWER_TIMEOUT_S},
                )
        except Exception as e:
            if debug:
                yield {
                    "execution_log": {
                        "node": "answer_error",
                        "node_type": "generation",
                        "duration_ms": int(
                            (time.monotonic() - (generation_started_at or time.monotonic()))
                            * 1000
                        ),
                        "input": {"message": message, "kb_prefix": kb_prefix},
                        "output": {"error": str(e)},
                    }
                }
            yield {"status": "error", "message": f"生成答案失败: {e}"}
            if generation_stage_span is not None:
                generation_stage_span.end(level="ERROR", status_message=str(e), output={"error": str(e)})

        yield {"status": "done"}

def _should_enrich_by_entity_matching(
    *,
    query: str,
    graphrag_context: str,
    extracted_entities: dict[str, Any] | None,
    query_intent: str | None,
    media_type_hint: str | None,
    filters: dict[str, Any] | None,
) -> bool:
    """
    判断是否需要进行 Query-time Enrichment（保守策略）

    触发条件：
    1. TV 推荐（Router 直接路由到 TMDB /discover/tv）
    2. Movie 推荐 + 有明确筛选条件（year/origin_country等）
    3. GraphRAG context 中没有包含抽取到的实体（疑似缺失）

    返回：True = 需要 enrichment，False = 不需要
    """
    from infrastructure.enrichment.entity_extractor import EntityExtractor

    if (query_intent or "").strip().lower() == "recommend" and (media_type_hint or "").strip().lower() == "tv":
        # Router-directed path: TV recommendations should use TMDB /discover/tv.
        return True
    if (query_intent or "").strip().lower() == "recommend" and (media_type_hint or "").strip().lower() == "movie":
        # For movies, only do discover when the user gave explicit filter constraints.
        if isinstance(filters, dict) and any(k in filters for k in ("year", "origin_country", "original_language", "region", "date_range")):
            return True

    names: list[str] = []
    if isinstance(extracted_entities, dict):
        low = extracted_entities.get("low_level")
        if isinstance(low, list):
            names = [str(x).strip() for x in low if str(x).strip()]

    if not names:
        names = EntityExtractor.extract_movie_entities(query)

    if not names:
        # No detectable entity => if the user is in movie KB, enrichment might still help.
        return True

    ctx = (graphrag_context or "").lower()
    for name in names:
        n = name.lower().strip()
        if n and n in ctx:
            return False
    return True
