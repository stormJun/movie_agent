from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.constants import CONF, CONFIG_KEY_STREAM_WRITER
from langgraph.graph import END, StateGraph

from domain.chat.entities.rag_run import RagRunResult, RagRunSpec
from domain.chat.entities.route_decision import RouteDecision
from infrastructure.config.settings import DEBUG_COMBINED_CONTEXT_MAX_CHARS
from infrastructure.rag.aggregator import aggregate_run_results
from infrastructure.rag.answer_generator import build_context_from_runs
from infrastructure.rag.rag_manager import RagManager, _should_enrich_by_entity_matching

logger = logging.getLogger(__name__)


def _get_stream_writer(config: RunnableConfig) -> Callable[[Any], None]:
    """Access LangGraph StreamWriter from config (Python 3.10 safe)."""
    try:
        writer = config.get(CONF, {}).get(CONFIG_KEY_STREAM_WRITER)
    except Exception:
        writer = None
    return writer if callable(writer) else (lambda _chunk: None)


def _iso_now() -> str:
    return datetime.now().isoformat()


def _truncate_text(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + "…"


# ==================== Plan / Execution Models ====================


@dataclass(frozen=True)
class PlanBudget:
    timeout_s: float = 15.0
    top_k: int = 50
    max_evidence_count: int = 100
    max_retries: int = 1


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    objective: str
    tool: str
    tool_input: Dict[str, Any]
    depends_on: Optional[List[str]]
    budget: PlanBudget
    priority: int = 1


@dataclass(frozen=True)
class ExecutionRecord:
    step_id: str
    tool: str
    started_at: str
    duration_ms: int
    input_summary: Dict[str, Any]
    output_summary: Dict[str, Any]
    raw_input: Dict[str, Any]
    raw_output: Dict[str, Any]
    status: Literal["success", "failed", "timeout", "partial"]
    error: Optional[str] = None
    sub_steps: List[Dict[str, Any]] = dataclasses.field(default_factory=list)


@dataclass(frozen=True)
class Reflection:
    should_continue: bool
    next_steps: List[PlanStep]
    rewrite_query: Optional[str] = None
    stop_reason: Optional[str] = None
    reasoning: str = ""
    current_iteration: int = 0
    max_iterations: int = 3
    remaining_budget: float = 0.0


@dataclass(frozen=True)
class MergedOutput:
    context: str
    retrieval_results: List[Dict[str, Any]]
    reference: Dict[str, Any]
    statistics: Optional[Dict[str, Any]] = None


class RetrievalState(TypedDict, total=False):
    # Inputs.
    query: str
    kb_prefix: str
    route_decision: RouteDecision
    debug: bool
    session_id: str
    # Request context for enrichment persistence.
    user_id: str | None
    request_id: str | None
    conversation_id: Any | None
    user_message_id: Any | None
    incognito: bool

    # Planner hints.
    resolved_agent_type: str | None

    # Plan/execute/reflect outputs.
    plan: List[PlanStep]
    records: List[ExecutionRecord]
    runs: List[RagRunResult]
    reflection: Optional[Reflection]
    iterations: int
    max_iterations: int

    # Final merged output.
    merged: Optional[MergedOutput]
    stop_reason: Optional[str]


# ==================== Planner ====================


def _normalize_query_intent(route_decision: RouteDecision | None) -> str:
    if not route_decision:
        return "unknown"
    return str(getattr(route_decision, "query_intent", "unknown") or "unknown").strip().lower()


def _normalize_media_type(route_decision: RouteDecision | None) -> str:
    if not route_decision:
        return "unknown"
    return str(getattr(route_decision, "media_type_hint", "unknown") or "unknown").strip().lower()


def _tool_to_agent_type(tool: str) -> str | None:
    """Map PlanStep.tool to a concrete agent_type for RagManager execution."""
    t = (tool or "").strip().lower()
    if not t:
        return None
    if t in {"hybrid", "hybrid_agent", "hybrid_search"}:
        return "hybrid_agent"
    if t in {"graph", "graph_agent", "local_search", "global_search"}:
        # GraphAgent covers local+global; we don't have a dedicated global-only agent today.
        return "graph_agent"
    if t in {"naive", "naive_rag_agent", "naive_search"}:
        return "naive_rag_agent"
    if t in {"deep", "deep_research_agent"}:
        return "deep_research_agent"
    # Explicit agent_type passthrough.
    if t in {"fusion_agent"}:
        # fusion_agent is intentionally not executed as a single tool; it is replaced
        # by the Plan→Execute→Reflect loop. Planner should not emit it here.
        return None
    return t


async def _plan_node(state: RetrievalState, config: RunnableConfig) -> dict[str, Any]:
    t0 = time.monotonic()
    query = str(state.get("query") or "")
    kb_prefix = str(state.get("kb_prefix") or "general")
    route_decision = state.get("route_decision")
    debug = bool(state.get("debug"))

    query_intent = _normalize_query_intent(route_decision)
    media_type_hint = _normalize_media_type(route_decision)
    filters = getattr(route_decision, "filters", None) if isinstance(route_decision, RouteDecision) else None
    extracted_entities = (
        getattr(route_decision, "extracted_entities", None) if isinstance(route_decision, RouteDecision) else None
    )

    resolved_agent_type = (state.get("resolved_agent_type") or "").strip() or None

    # Minimal deterministic planner (MVP):
    # - QA: 1-step using resolved_agent_type (router recommendation) with a naive fallback.
    # - Recommend/List/Compare: 2-step (hybrid candidates -> graph evidence) plus naive fallback.
    plan: list[PlanStep] = []

    if query_intent == "qa":
        primary = resolved_agent_type if resolved_agent_type and resolved_agent_type != "fusion_agent" else "hybrid_agent"
        plan.append(
            PlanStep(
                step_id="step_0_primary",
                objective="检索相关信息（主路）",
                tool=primary,
                tool_input={"query": query, "kb_prefix": kb_prefix, "top_k": 50},
                depends_on=[],
                budget=PlanBudget(timeout_s=15.0, top_k=50),
                priority=1,
            )
        )
        plan.append(
            PlanStep(
                step_id="step_1_fallback",
                objective="兜底检索（纯向量）",
                tool="naive_rag_agent",
                tool_input={"query": query, "kb_prefix": kb_prefix, "top_k": 30},
                depends_on=["step_0_primary"],
                budget=PlanBudget(timeout_s=10.0, top_k=30),
                priority=2,
            )
        )
    elif query_intent in {"recommend", "compare", "list"}:
        # If router indicates person, bias first step to graph_agent for disambiguation.
        if media_type_hint == "person":
            person_name = ""
            if isinstance(extracted_entities, dict):
                low = extracted_entities.get("low_level")
                if isinstance(low, list) and low:
                    person_name = str(low[0] or "").strip()
            person_name = person_name or query
            plan.append(
                PlanStep(
                    step_id="step_0_resolve_person",
                    objective=f"解析人物 {person_name}",
                    tool="graph_agent",
                    tool_input={"query": f"{person_name} 是谁？", "kb_prefix": kb_prefix, "top_k": 20},
                    depends_on=[],
                    budget=PlanBudget(timeout_s=10.0, top_k=20),
                    priority=1,
                )
            )
            plan.append(
                PlanStep(
                    step_id="step_1_person_works",
                    objective=f"获取 {person_name} 的作品信息",
                    tool="hybrid_agent",
                    tool_input={"query": query, "kb_prefix": kb_prefix, "top_k": 60},
                    depends_on=["step_0_resolve_person"],
                    budget=PlanBudget(timeout_s=15.0, top_k=60),
                    priority=2,
                )
            )
        else:
            # Candidate-first approach.
            plan.append(
                PlanStep(
                    step_id="step_0_candidates",
                    objective="拉取候选集合",
                    tool="hybrid_agent",
                    tool_input={"query": query, "kb_prefix": kb_prefix, "top_k": 80},
                    depends_on=[],
                    budget=PlanBudget(timeout_s=18.0, top_k=80),
                    priority=1,
                )
            )
            plan.append(
                PlanStep(
                    step_id="step_1_evidence",
                    objective="补充候选的详细信息（全局/关系）",
                    tool="graph_agent",
                    tool_input={"query": query, "kb_prefix": kb_prefix, "top_k": 50},
                    depends_on=["step_0_candidates"],
                    budget=PlanBudget(timeout_s=18.0, top_k=50),
                    priority=2,
                )
            )

        # If router provided explicit filters, we still rely on TMDB enrichment during merge.
        if isinstance(filters, dict) and filters:
            plan.append(
                PlanStep(
                    step_id="step_2_filters_hint",
                    objective="（可选）根据筛选条件做外部补全（TMDB enrichment 在 merge 阶段执行）",
                    tool="enrichment",
                    tool_input={"filters": filters},
                    depends_on=[],
                    budget=PlanBudget(timeout_s=10.0, top_k=0),
                    priority=99,
                )
            )
    else:
        primary = resolved_agent_type if resolved_agent_type and resolved_agent_type != "fusion_agent" else "hybrid_agent"
        plan.append(
            PlanStep(
                step_id="step_0_default",
                objective="检索相关信息",
                tool=primary,
                tool_input={"query": query, "kb_prefix": kb_prefix, "top_k": 50},
                depends_on=[],
                budget=PlanBudget(timeout_s=15.0, top_k=50),
                priority=1,
            )
        )

    if debug:
        writer = _get_stream_writer(config)
        writer(
            {
                "execution_log": {
                    "node": "plan",
                    "node_type": "retrieval_subgraph",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "input": {
                        "query_preview": query[:200],
                        "kb_prefix": kb_prefix,
                        "query_intent": query_intent,
                        "media_type_hint": media_type_hint,
                    },
                    "output": {
                        "plan_steps": [dataclasses.asdict(s) for s in plan],
                    },
                }
            }
        )

    return {
        "plan": plan,
        "records": [],
        "runs": [],
        "reflection": None,
        "iterations": 0,
        "max_iterations": int(state.get("max_iterations") or 3),
        "merged": None,
        "stop_reason": None,
    }


# ==================== Execute ====================


async def _execute_single_step(
    *,
    step: PlanStep,
    state: RetrievalState,
    config: RunnableConfig,
    retrieval_runner: Any,
) -> tuple[ExecutionRecord, Optional[RagRunResult]]:
    started_at = _iso_now()
    t0 = time.monotonic()
    debug = bool(state.get("debug"))
    query = str((step.tool_input or {}).get("query") or state.get("query") or "")
    kb_prefix = str((step.tool_input or {}).get("kb_prefix") or state.get("kb_prefix") or "general")

    # Non-agent steps are represented for observability only.
    agent_type = _tool_to_agent_type(step.tool)
    if step.tool == "enrichment" or agent_type is None:
        record = ExecutionRecord(
            step_id=step.step_id,
            tool=step.tool,
            started_at=started_at,
            duration_ms=int((time.monotonic() - t0) * 1000),
            input_summary={"tool": step.tool, "objective": step.objective},
            output_summary={"skipped": True},
            raw_input=cast(dict[str, Any], step.tool_input or {}),
            raw_output={"skipped": True},
            status="success",
            sub_steps=[],
        )
        return record, None

    spec = RagRunSpec(agent_type=agent_type, timeout_s=float(step.budget.timeout_s))
    run = await retrieval_runner(
        spec=spec,
        message=query,
        session_id=str(state.get("session_id") or ""),
        kb_prefix=kb_prefix,
        debug=debug,
    )

    duration_ms = int((time.monotonic() - t0) * 1000)
    status: Literal["success", "failed", "timeout", "partial"] = "success"
    if run.error:
        if "timeout" in str(run.error).lower():
            status = "timeout"
        else:
            status = "failed"

    retrieval_count = 0
    if isinstance(run.retrieval_results, list):
        retrieval_count = len(run.retrieval_results)

    record = ExecutionRecord(
        step_id=step.step_id,
        tool=agent_type,
        started_at=started_at,
        duration_ms=duration_ms,
        input_summary={
            "objective": step.objective,
            "query_preview": query[:200],
            "kb_prefix": kb_prefix,
            "timeout_s": step.budget.timeout_s,
        },
        output_summary={"retrieval_count": retrieval_count, "error": run.error},
        raw_input={"query": query, "kb_prefix": kb_prefix, "spec": dataclasses.asdict(spec)},
        raw_output={
            "agent_type": run.agent_type,
            "error": run.error,
            "context_chars": len(run.context or ""),
            "retrieval_count": retrieval_count,
            "reference": run.reference,
            # retrieval_results could be huge; keep it out of raw_output (UI can use merged output).
        },
        status=status,
        error=run.error,
        sub_steps=list(run.execution_log or []) if isinstance(run.execution_log, list) else [],
    )
    return record, run


def _deps_satisfied(step: PlanStep, done: set[str]) -> bool:
    deps = step.depends_on or []
    if not deps:
        return True
    return all(d in done for d in deps)


async def _execute_plan_node(state: RetrievalState, config: RunnableConfig) -> dict[str, Any]:
    t0 = time.monotonic()
    debug = bool(state.get("debug"))
    writer = _get_stream_writer(config)

    plan = list(state.get("plan") or [])
    records = list(state.get("records") or [])
    runs = list(state.get("runs") or [])

    executed = {r.step_id for r in records if isinstance(r, ExecutionRecord)}
    done_step_ids = set(executed)

    # Prevent infinite loops when planner emits only "enrichment" steps.
    ready_steps = [s for s in plan if s.step_id not in done_step_ids and _deps_satisfied(s, done_step_ids)]
    if not ready_steps:
        if debug:
            writer(
                {
                    "execution_log": {
                        "node": "execute_plan",
                        "node_type": "retrieval_subgraph",
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                        "input": {"plan_steps": len(plan), "executed_steps": len(done_step_ids)},
                        "output": {"note": "no_ready_steps"},
                    }
                }
            )
        return {}

    # Allow tests to inject a retrieval runner so we can avoid network/LLM calls.
    retrieval_runner = None
    try:
        retrieval_runner = (config.get(CONF, {}) or {}).get("retrieval_runner")
    except Exception:
        retrieval_runner = None
    if not callable(retrieval_runner):
        rag_manager = RagManager()
        retrieval_runner = rag_manager.run_retrieval_for_spec

    # Fire a progress event compatible with existing SSE consumers.
    if plan:
        writer(
            {
                "status": "progress",
                "content": {
                    "stage": "retrieval",
                    "completed": len(done_step_ids),
                    "total": len(plan),
                    "error": None,
                    "agent_type": "",
                    "retrieval_count": None,
                },
            }
        )

    # Execute all ready steps concurrently (bounded by plan size; usually small).
    async def _run_step(s: PlanStep) -> tuple[ExecutionRecord, Optional[RagRunResult]]:
        record, run = await _execute_single_step(
            step=s, state=state, config=config, retrieval_runner=retrieval_runner
        )
        return record, run

    results = await asyncio.gather(*[_run_step(s) for s in ready_steps], return_exceptions=True)

    for step, res in zip(ready_steps, results):
        if isinstance(res, Exception):
            records.append(
                ExecutionRecord(
                    step_id=step.step_id,
                    tool=step.tool,
                    started_at=_iso_now(),
                    duration_ms=0,
                    input_summary={"objective": step.objective},
                    output_summary={},
                    raw_input=cast(dict[str, Any], step.tool_input or {}),
                    raw_output={},
                    status="failed",
                    error=str(res),
                    sub_steps=[],
                )
            )
            continue

        record, run = res
        records.append(record)
        if isinstance(run, RagRunResult):
            runs.append(run)

    if debug:
        writer(
            {
                "execution_log": {
                    "node": "execute_plan",
                    "node_type": "retrieval_subgraph",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "input": {"ready_steps": [dataclasses.asdict(s) for s in ready_steps]},
                    "output": {
                        "records_added": len(ready_steps),
                        "total_records": len(records),
                        "total_runs": len(runs),
                    },
                }
            }
        )

    return {"records": records, "runs": runs}


# ==================== Reflect ====================


def _get_min_evidence_count(query_intent: str) -> int:
    thresholds = {"qa": 5, "recommend": 10, "compare": 8, "list": 15, "unknown": 5}
    return int(thresholds.get(query_intent, 5))


def _get_min_top_score(query_intent: str) -> float:
    thresholds = {"qa": 0.4, "recommend": 0.6, "compare": 0.5, "list": 0.7, "unknown": 0.5}
    return float(thresholds.get(query_intent, 0.5))


async def _reflect_node(state: RetrievalState, config: RunnableConfig) -> dict[str, Any]:
    t0 = time.monotonic()
    debug = bool(state.get("debug"))
    writer = _get_stream_writer(config)

    plan = list(state.get("plan") or [])
    records = list(state.get("records") or [])
    runs = list(state.get("runs") or [])
    iterations = int(state.get("iterations") or 0)
    max_iterations = int(state.get("max_iterations") or 3)
    route_decision = state.get("route_decision")
    query_intent = _normalize_query_intent(route_decision)

    # Quality signals from merged retrieval results (deduped).
    aggregated = aggregate_run_results(results=list(runs)) if runs else RagRunResult(agent_type="unknown", answer="", error="no results")
    retrieval_results = aggregated.retrieval_results or []
    evidence_count = len(retrieval_results) if isinstance(retrieval_results, list) else 0

    top_score = 0.0
    if isinstance(retrieval_results, list):
        for item in retrieval_results:
            if not isinstance(item, dict):
                continue
            try:
                s = float(item.get("score", 0.0))
            except Exception:
                s = 0.0
            top_score = max(top_score, s)

    min_evidence = _get_min_evidence_count(query_intent)
    min_score = _get_min_top_score(query_intent)

    should_continue = False
    stop_reason = None
    reasoning: list[str] = []
    next_steps: list[PlanStep] = []

    if iterations >= max_iterations - 1:
        stop_reason = "max_iterations_reached"
    else:
        if evidence_count < min_evidence:
            should_continue = True
            reasoning.append(f"证据数量不足 ({evidence_count} < {min_evidence})")
        if top_score < min_score:
            should_continue = True
            reasoning.append(f"最高分过低 ({top_score:.2f} < {min_score:.2f})")

    # Fallback strategy: add a naive_rag_agent step if not already present.
    if should_continue:
        existing_tools = {(_tool_to_agent_type(s.tool) or s.tool) for s in plan}
        if "naive_rag_agent" not in existing_tools:
            query = str(state.get("query") or "")
            kb_prefix = str(state.get("kb_prefix") or "general")
            next_steps.append(
                PlanStep(
                    step_id=f"step_{len(plan)}_fallback_naive",
                    objective="追加兜底检索（纯向量）",
                    tool="naive_rag_agent",
                    tool_input={"query": query, "kb_prefix": kb_prefix, "top_k": 50},
                    depends_on=[],
                    budget=PlanBudget(timeout_s=12.0, top_k=50),
                    priority=10,
                )
            )
        else:
            # No more strategies available.
            should_continue = False
            stop_reason = "quality_insufficient_no_more_strategies"

    if not should_continue and stop_reason is None:
        stop_reason = "quality_satisfied"

    reflection = Reflection(
        should_continue=should_continue,
        next_steps=next_steps,
        rewrite_query=None,
        stop_reason=stop_reason,
        reasoning="；".join(reasoning) if reasoning else "检索质量满足要求",
        current_iteration=iterations,
        max_iterations=max_iterations,
        remaining_budget=0.0,
    )

    if debug:
        writer(
            {
                "execution_log": {
                    "node": "reflect",
                    "node_type": "retrieval_subgraph",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "input": {
                        "iterations": iterations,
                        "query_intent": query_intent,
                        "evidence_count": evidence_count,
                        "top_score": top_score,
                        "min_evidence": min_evidence,
                        "min_score": min_score,
                    },
                    "output": dataclasses.asdict(reflection),
                }
            }
        )

    if should_continue and next_steps:
        return {"reflection": reflection, "plan": plan + next_steps, "iterations": iterations + 1, "stop_reason": None}

    return {"reflection": reflection, "iterations": iterations + 1, "stop_reason": stop_reason}


def _should_continue_from_execute(state: RetrievalState) -> str:
    # After each execute pass, always run reflect once.
    return "reflect"


def _should_continue_from_reflect(state: RetrievalState) -> str:
    reflection = state.get("reflection")
    if isinstance(reflection, Reflection) and reflection.should_continue:
        return "continue"
    return "merge"


# ==================== Merge ====================


async def _merge_node(state: RetrievalState, config: RunnableConfig) -> dict[str, Any]:
    t0 = time.monotonic()
    debug = bool(state.get("debug"))
    writer = _get_stream_writer(config)

    query = str(state.get("query") or "")
    kb_prefix = str(state.get("kb_prefix") or "general")
    route_decision = state.get("route_decision")
    # route_decision 是 router 的结构化输出（dataclass），包含抽取实体/意图/过滤条件等。
    extracted_entities = getattr(route_decision, "extracted_entities", None) if isinstance(route_decision, RouteDecision) else None
    query_intent = getattr(route_decision, "query_intent", None) if isinstance(route_decision, RouteDecision) else None
    media_type_hint = getattr(route_decision, "media_type_hint", None) if isinstance(route_decision, RouteDecision) else None
    filters = getattr(route_decision, "filters", None) if isinstance(route_decision, RouteDecision) else None

    runs = list(state.get("runs") or [])
    aggregated = aggregate_run_results(results=list(runs)) if runs else RagRunResult(agent_type="unknown", answer="", error="no results")

    # 将各检索策略（run）的上下文串联成最终 combined_context（后续 generation 会直接使用）。
    combined_context = build_context_from_runs(
        runs=[
            {"agent_type": r.agent_type, "context": r.context or ""}
            for r in runs
            if not r.error and isinstance(r.context, str) and r.context.strip()
        ]
    )

    # 查询时增强（movie KB 专用）：当 GraphRAG 证据疑似缺失关键实体时，用 TMDB 补齐结构化事实。
    enriched_text = ""
    if (kb_prefix or "").strip() == "movie":
        enrichment_enabled = True
        try:
            val = (config.get(CONF, {}) or {}).get("enrichment_enabled")
            if isinstance(val, bool):
                enrichment_enabled = val
        except Exception:
            enrichment_enabled = True
        try:
            if enrichment_enabled and _should_enrich_by_entity_matching(
                query=query,
                graphrag_context=combined_context,
                extracted_entities=extracted_entities,
                query_intent=str(query_intent) if query_intent is not None else None,
                media_type_hint=str(media_type_hint) if media_type_hint is not None else None,
                filters=filters if isinstance(filters, dict) else None,
            ):
                from infrastructure.enrichment import get_tmdb_enrichment_service

                svc = get_tmdb_enrichment_service()
                if svc is None:
                    logger.debug("enrichment skipped: tmdb service not configured")
                else:
                    result = await svc.enrich_query(
                        message=query,
                        kb_prefix="movie",
                        extracted_entities=extracted_entities,
                        query_intent=str(query_intent) if query_intent is not None else None,
                        media_type_hint=str(media_type_hint) if media_type_hint is not None else None,
                        filters=filters if isinstance(filters, dict) else None,
                        user_id=state.get("user_id"),
                        session_id=state.get("session_id"),
                        request_id=state.get("request_id"),
                        conversation_id=state.get("conversation_id"),
                        user_message_id=state.get("user_message_id"),
                        incognito=bool(state.get("incognito")),
                    )
                    if result.success and result.transient_graph and not result.transient_graph.is_empty():
                        enriched_text = result.transient_graph.to_context_text().strip()
        except Exception as e:
            logger.debug("query-time enrichment failed: %s", e, exc_info=True)

    if enriched_text:
        combined_context = f"{combined_context}\n\n{enriched_text}".strip()

    if debug:
        # cache-only：写入 debug_cache，前端通过 /api/v1/debug/{request_id} 获取（避免污染 SSE token 流）。
        # Emit cache-only combined_context for debug UI (Context tab).
        truncated = False
        max_chars = int(DEBUG_COMBINED_CONTEXT_MAX_CHARS or 0)
        text_for_ui = combined_context
        if max_chars > 0 and len(text_for_ui) > max_chars:
            text_for_ui = text_for_ui[:max_chars]
            truncated = True

        writer(
            {
                "status": "combined_context",
                "content": {
                    "text": text_for_ui,
                    "total_chars": len(combined_context),
                    "truncated": truncated,
                    "has_enrichment": bool(enriched_text),
                },
            }
        )

        # cache-only：每条 run 的统计（agent_type / retrieval_count / context_chars），便于 UI 展示。
        # Emit cache-only rag_runs for debug UI.
        writer(
            {
                "status": "rag_runs",
                "content": [
                    {
                        "agent_type": r.agent_type,
                        "error": r.error,
                        "context_chars": len(r.context or ""),
                        "retrieval_count": len(r.retrieval_results or []) if isinstance(r.retrieval_results, list) else 0,
                    }
                    for r in runs
                ],
            }
        )

    # Provide a compact retrieval_done execution_log with step-level sub_steps.
    step_logs: list[dict[str, Any]] = []
    for rec in state.get("records") or []:
        if not isinstance(rec, ExecutionRecord):
            continue
        step_logs.append(
            {
                "node": rec.step_id,
                "node_type": "retrieval_step",
                "duration_ms": rec.duration_ms,
                "input": rec.input_summary,
                "output": rec.output_summary,
                "sub_steps": rec.sub_steps,
            }
        )

    retrieval_count = len(aggregated.retrieval_results or []) if isinstance(aggregated.retrieval_results, list) else 0
    if debug:
        writer(
            {
                "execution_log": {
                    "node": "rag_retrieval_done",
                    "node_type": "retrieval",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "input": {"plan_steps": len(state.get("plan") or [])},
                    "output": {"error": aggregated.error, "retrieval_count": retrieval_count},
                    "sub_steps": step_logs,
                }
            }
        )

        writer(
            {
                "execution_log": {
                    "node": "merge",
                    "node_type": "retrieval_subgraph",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "input": {"runs": len(runs), "has_enrichment": bool(enriched_text)},
                    "output": {
                        "combined_context_chars": len(combined_context),
                        "retrieval_count": retrieval_count,
                        "reference": aggregated.reference or {},
                    },
                }
            }
        )

    merged = MergedOutput(
        context=combined_context,
        retrieval_results=list(aggregated.retrieval_results or []),
        reference=dict(aggregated.reference or {}),
        statistics={
            "runs": len(runs),
            "plan_steps": len(state.get("plan") or []),
            "has_enrichment": bool(enriched_text),
            "merged_context_chars": len(combined_context),
        },
    )

    return {"merged": merged, "stop_reason": state.get("stop_reason") or "success"}


def build_retrieval_subgraph():
    # Retrieval 子图（Plan -> Execute -> Reflect -> Merge）：
    # - planner：产出检索计划（按意图/预算选择策略）
    # - executor：执行计划并收集 runs/records
    # - reflector：基于证据质量决定是否迭代
    # - merger：合并 runs 为 combined_context，并可选拼接 enrichment
    g = StateGraph(RetrievalState)
    # NOTE: node names must not collide with state keys (LangGraph channel names).
    g.add_node("planner", _plan_node)
    g.add_node("executor", _execute_plan_node)
    g.add_node("reflector", _reflect_node)
    g.add_node("merger", _merge_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "executor")
    g.add_edge("executor", "reflector")
    g.add_conditional_edges(
        "reflector", _should_continue_from_reflect, {"continue": "executor", "merge": "merger"}
    )
    g.add_edge("merger", END)
    return g.compile()


retrieval_subgraph_compiled = build_retrieval_subgraph()
