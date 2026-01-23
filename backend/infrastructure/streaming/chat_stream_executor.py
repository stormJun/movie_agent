from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator

from infrastructure.config.settings import RAG_ANSWER_TIMEOUT_S
from infrastructure.llm.completion import (
    generate_general_answer_stream,
    generate_rag_answer_stream,
)
from infrastructure.rag.answer_generator import build_context_from_runs
from infrastructure.rag.rag_manager import RagManager
from infrastructure.rag.specs import RagRunSpec


_DEBUG_RETRIEVAL_PREVIEW_N = 3
_DEBUG_EVIDENCE_PREVIEW_CHARS = 240
_DEBUG_TOP_SOURCE_IDS_N = 8


def _truncate_text(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + "…"


def _summarize_retrieval_results(results: Any) -> dict[str, Any]:
    """Summarize retrieval results for debug logs without dumping full payloads."""
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
    def __init__(self, *, rag_manager: RagManager) -> None:
        self._rag_manager = rag_manager

    async def stream(
        self,
        *,
        plan: list[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        memory_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        use_retrieval = bool(plan) and (kb_prefix or "").strip() not in {"", "general"}
        if not use_retrieval:
            generation_start = time.monotonic()
            generated_chars = 0
            chunk_count = 0
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
                async for chunk in generate_general_answer_stream(
                    question=message,
                    memory_context=memory_context,
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
            yield {"status": "done"}
            return

        if debug:
            yield {
                "execution_log": {
                    "node": "rag_plan",
                    "node_type": "routing",
                    "input": {"message": message, "kb_prefix": kb_prefix},
                    "output": {"plan": [spec.agent_type for spec in plan]},
                }
            }

        overall_timeout_s = max(spec.timeout_s for spec in plan) + RAG_ANSWER_TIMEOUT_S
        start_time = time.monotonic()
        runs = []
        total_runs = len(plan)

        retrieval_stage_start = time.monotonic()
        retrieval_run_elapsed_ms: dict[str, int] = {}

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

        retrieval_tasks: list[asyncio.Task] = []
        task_started_at: dict[asyncio.Task, float] = {}
        for spec in plan:
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

        try:
            for task in asyncio.as_completed(retrieval_tasks, timeout=overall_timeout_s):
                run = await task
                runs.append(run)
                started_at = task_started_at.get(task)
                if started_at is not None:
                    retrieval_run_elapsed_ms[run.agent_type] = int(
                        (time.monotonic() - started_at) * 1000
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
            yield {"status": "done"}
            return
        finally:
            # If the client disconnects, the outer SSE generator cancels us; make sure
            # fanout retrieval tasks are cancelled so they don't keep running.
            pending = [t for t in retrieval_tasks if not t.done()]
            for t in pending:
                t.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

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

        combined_context = build_context_from_runs(
            runs=[
                {"agent_type": r.agent_type, "context": r.context or ""}
                for r in runs
                if not r.error
            ]
        )

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
        try:
            elapsed = time.monotonic() - start_time
            remaining = max(overall_timeout_s - elapsed, 0.0)
            if remaining <= 0:
                raise asyncio.TimeoutError

            timeout_budget = min(RAG_ANSWER_TIMEOUT_S, remaining)
            generation_started_at = time.monotonic()
            async for chunk in _stream_with_timeout(
                generate_rag_answer_stream(
                    question=message,
                    context=combined_context,
                    memory_context=memory_context,
                    history=history,
                ),
                timeout_budget,
            ):
                if chunk:
                    generated_chars += len(chunk)
                    chunk_count += 1
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

        yield {"status": "done"}
