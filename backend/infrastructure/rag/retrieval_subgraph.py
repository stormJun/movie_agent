"""
Retrieval Subgraph：检索子图（Plan → Execute → Reflect → Merge）

核心功能：
1. Plan（计划）：根据查询意图生成检索计划（PlanStep[]）
2. Execute（执行）：并发/串行混合执行检索步骤
3. Reflect（反思）：基于检索质量决定是否迭代
4. Merge（合并）：聚合检索结果 + 可选 enrichment

架构特点：
- First-Class Subgraph：作为 LangGraph 节点，Studio 可展开查看
- 支持迭代：Reflect 可以追加步骤继续检索
- 预算约束：每个步骤有超时/top_k/max_evidence 限制
- 依赖管理：depends_on 控制串行 vs 并行执行

子图结构：
START → planner → executor → reflect → [循环回 executor] → merger → END
                                     ↓
                               (质量满足)
                                     ↓
                                  merger → END
"""

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
from infrastructure.llm.completion import select_tmdb_recommendation_movies

logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================

def _get_stream_writer(config: RunnableConfig) -> Callable[[Any], None]:
    """
    从 config 中提取 writer 函数（Python 3.10 兼容）

    用于发送自定义事件（stream_mode="custom"）
    """
    try:
        writer = config.get(CONF, {}).get(CONFIG_KEY_STREAM_WRITER)
    except Exception:
        writer = None
    return writer if callable(writer) else (lambda _chunk: None)


def _iso_now() -> str:
    """获取当前 ISO 时间戳"""
    return datetime.now().isoformat()


def _truncate_text(value: str, limit: int) -> str:
    """截断文本到指定长度（避免 debug payload 过大）"""
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + "…"


# ==================== Plan / Execution Models ====================
# 数据模型：PlanStep、ExecutionRecord、Reflection、MergedOutput


@dataclass(frozen=True)
class PlanBudget:
    """
    检索步骤的预算约束

    字段：
    - timeout_s: 超时时间（秒）
    - top_k: 返回 top-k 结果
    - max_evidence_count: 最大证据数量
    - max_retries: 最大重试次数
    """
    timeout_s: float = 15.0
    top_k: int = 50
    max_evidence_count: int = 100
    max_retries: int = 1


@dataclass(frozen=True)
class PlanStep:
    """
    检索计划步骤

    字段：
    - step_id: 步骤唯一标识（例如 "step_0_primary"）
    - objective: 步骤目标（例如 "检索相关信息（主路）"）
    - tool: 使用的工具/agent（例如 "hybrid_agent"）
    - tool_input: 工具输入参数
    - depends_on: 依赖的前置步骤（空列表=可并行执行）
    - budget: 预算约束
    - priority: 优先级（数字越小越优先）
    """
    step_id: str
    objective: str
    tool: str
    tool_input: Dict[str, Any]
    depends_on: Optional[List[str]]  # 依赖的步骤 ID 列表
    budget: PlanBudget
    priority: int = 1


@dataclass(frozen=True)
class ExecutionRecord:
    """
    执行记录：记录每个步骤的执行结果

    字段：
    - step_id: 步骤 ID
    - tool: 使用的工具
    - started_at: 开始时间（ISO 格式）
    - duration_ms: 执行耗时（毫秒）
    - input_summary: 输入摘要（用于 debug 展示）
    - output_summary: 输出摘要
    - raw_input: 原始输入（完整）
    - raw_output: 原始输出（完整）
    - status: 执行状态
    - error: 错误信息（如果有）
    - sub_steps: 子步骤（agent 内部执行的步骤）
    """
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
    """
    反思结果：决定是否继续检索

    字段：
    - should_continue: 是否继续迭代
    - next_steps: 如果继续，追加的步骤列表
    - rewrite_query: 可选的查询改写
    - stop_reason: 停止原因
    - reasoning: 推理过程
    - current_iteration: 当前迭代次数
    - max_iterations: 最大迭代次数
    - remaining_budget: 剩余预算
    """
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
    """
    合并输出：检索子图的最终产物

    字段：
    - context: 合并后的上下文文本（用于生成答案）
    - retrieval_results: 所有检索结果列表（去重后）
    - reference: 引用信息（来源、标题等）
    - statistics: 统计信息（可选）
    """
    context: str
    retrieval_results: List[Dict[str, Any]]
    reference: Dict[str, Any]
    statistics: Optional[Dict[str, Any]] = None


class RetrievalState(TypedDict, total=False):
    """
    检索子图 State（Phase 4）

    State 流转：
    1. 输入：query, kb_prefix, route_decision, ...
    2. plan: planner 填充
    3. records + runs: executor 填充
    4. reflection: reflector 填充
    5. merged: merger 填充
    """

    # ===== 输入字段（由 prepare_retrieval_node 填充）=====
    query: str  # 用户查询
    kb_prefix: str  # 知识库前缀（例如 "movie"）
    route_decision: RouteDecision  # 路由决策（包含抽取实体、意图等）
    debug: bool  # 是否启用 debug 模式
    session_id: str  # 会话 ID
    # Request context for enrichment persistence.
    user_id: str | None  # 用户 ID（用于 enrichment 持久化）
    request_id: str | None  # 请求 ID
    conversation_id: Any | None  # 对话 ID
    user_message_id: Any | None  # 用户消息 ID
    incognito: bool  # 隐身模式（不写入记忆）

    # Planner hints.
    resolved_agent_type: str | None  # Router 推荐的 agent_type

    # ===== Plan/Execute/Reflect 输出（子图内部流转）=====
    plan: List[PlanStep]  # 检索计划
    records: List[ExecutionRecord]  # 执行记录
    runs: List[RagRunResult]  # 检索运行结果
    reflection: Optional[Reflection]  # 反思结果
    iterations: int  # 当前迭代次数
    max_iterations: int  # 最大迭代次数

    # ===== 最终输出（由 merger 填充）=====
    merged: Optional[MergedOutput]  # 合并后的检索结果
    stop_reason: Optional[str]  # 停止原因

    # ===== TMDB-only 推荐（不走 Neo4j/GraphRAG）=====
    tmdb_only_recommendation: bool
    tmdb_selected_movies: list[dict[str, Any]]
    tmdb_only_answer: str


# ==================== Planner（计划节点）====================


def _normalize_query_intent(route_decision: RouteDecision | None) -> str:
    """规范化查询意图（小写）"""
    if not route_decision:
        return "unknown"
    return str(getattr(route_decision, "query_intent", "unknown") or "unknown").strip().lower()


def _normalize_media_type(route_decision: RouteDecision | None) -> str:
    """规范化媒体类型（小写）"""
    if not route_decision:
        return "unknown"
    return str(getattr(route_decision, "media_type_hint", "unknown") or "unknown").strip().lower()


def _tool_to_agent_type(tool: str) -> str | None:
    """
    将 PlanStep.tool 映射到具体的 agent_type（供 RagManager 执行）

    支持的工具映射：
    - hybrid/hybrid_agent → hybrid_agent
    - graph/graph_agent → graph_agent
    - naive/naive_rag_agent → naive_rag_agent
    - deep/deep_research_agent → deep_research_agent
    - fusion_agent → None（fusion_agent 由子图本身实现，不应作为工具）
    """
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
    """
    计划节点：生成检索计划（PlanStep[]）

    MVP 策略（确定性规则，不使用 LLM）：
    1. QA 查询：主路（router 推荐 agent） + 兜底（naive）
    2. Recommend/List/Compare：hybrid 候选 → graph 证据 + 兜底
    3. Person 查询：先解析人物（graph）→ 再获取作品（hybrid）

    返回：State 更新（plan 字段）
    """
    t0 = time.monotonic()
    query = str(state.get("query") or "")
    kb_prefix = str(state.get("kb_prefix") or "general")
    route_decision = state.get("route_decision")
    debug = bool(state.get("debug"))

    # 提取路由决策信息
    query_intent = _normalize_query_intent(route_decision)
    media_type_hint = _normalize_media_type(route_decision)
    filters = getattr(route_decision, "filters", None) if isinstance(route_decision, RouteDecision) else None
    extracted_entities = (
        getattr(route_decision, "extracted_entities", None) if isinstance(route_decision, RouteDecision) else None
    )

    resolved_agent_type = (state.get("resolved_agent_type") or "").strip() or None

    # ===== TMDB-only 推荐（不走 Neo4j/GraphRAG）=====
    # 当用户明确是“推荐电影”时，我们直接用 TMDB 作为候选与事实来源，
    # 不再执行 GraphRAG（Neo4j）检索。具体 TMDB 拉取与 LLM 结构化选片在 merge 阶段执行。
    if kb_prefix == "movie" and query_intent == "recommend" and media_type_hint == "movie":
        if debug:
            writer = _get_stream_writer(config)
            writer(
                {
                    "execution_log": {
                        "node": "planner",
                        "node_type": "retrieval_subgraph",
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                        "input": {"query_intent": query_intent, "media_type_hint": media_type_hint},
                        "output": {"mode": "tmdb_only_recommendation", "plan_steps": 0},
                    }
                }
            )
        return {
            "plan": [],
            "iterations": 0,
            "max_iterations": 1,
            "tmdb_only_recommendation": True,
        }

    # ===== MVP 确定性规划器 =====
    # QA: 主路（router 推荐） + 兜底
    # Recommend/List/Compare: hybrid 候选 → graph 证据 + 兜底
    plan: list[PlanStep] = []

    # ---- 场景 1：QA 查询（简单事实查询）----
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
    # ---- 场景 2：Recommend/Compare/List（复杂查询）----
    elif query_intent in {"recommend", "compare", "list"}:
        # 如果是人物查询，先用 graph 解析人物，再用 hybrid 获取作品
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
            # 非人物查询：候选优先策略
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

# ==================== Executor（执行节点）====================


async def _execute_single_step(
    *,
    step: PlanStep,
    state: RetrievalState,
    config: RunnableConfig,
    retrieval_runner: Any,
) -> tuple[ExecutionRecord, Optional[RagRunResult]]:
    """
    执行单个检索步骤

    流程：
    1. 检查是否为 agent 工具（enrichment 等非 agent 工具跳过）
    2. 调用 RagManager 执行检索
    3. 记录执行结果（ExecutionRecord）

    返回：(ExecutionRecord, RagRunResult | None)
    """
    started_at = _iso_now()
    t0 = time.monotonic()
    debug = bool(state.get("debug"))
    query = str((step.tool_input or {}).get("query") or state.get("query") or "")
    kb_prefix = str((step.tool_input or {}).get("kb_prefix") or state.get("kb_prefix") or "general")

    # 非步骤仅用于可观测性，不实际执行检索
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
    """检查步骤的依赖是否都已满足"""
    deps = step.depends_on or []
    if not deps:
        return True
    return all(d in done for d in deps)


async def _execute_plan_node(state: RetrievalState, config: RunnableConfig) -> dict[str, Any]:
    """
    执行计划节点：并发/串行混合执行检索步骤

    核心逻辑：
    1. 找出所有依赖已满足的步骤（ready_steps）
    2. 并发执行这些步骤（asyncio.gather）
    3. 记录执行结果（records + runs）
    4. 发送 progress 事件

    依赖管理：
    - depends_on=[] → 可并行执行（与其他无依赖步骤）
    - depends_on=[step_0] → 必须 step_0 完成后才执行

    返回：State 更新（records + runs）
    """
    t0 = time.monotonic()
    debug = bool(state.get("debug"))
    writer = _get_stream_writer(config)

    plan = list(state.get("plan") or [])
    records = list(state.get("records") or [])
    runs = list(state.get("runs") or [])

    executed = {r.step_id for r in records if isinstance(r, ExecutionRecord)}
    done_step_ids = set(executed)

    # 找出所有依赖已满足的未执行步骤
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

    # 获取 retrieval_runner（优先使用注入的，避免真实网络/LLM 调用）
    # Allow tests to inject a retrieval runner so we can avoid network/LLM calls.
    retrieval_runner = None
    try:
        retrieval_runner = (config.get(CONF, {}) or {}).get("retrieval_runner")
    except Exception:
        retrieval_runner = None
    if not callable(retrieval_runner):
        rag_manager = RagManager()
        retrieval_runner = rag_manager.run_retrieval_for_spec

    # 发送 progress 事件（兼容现有 SSE 消费者）
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

    # 并发执行所有就绪的步骤（无依赖关系的步骤可以并行）
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


# ==================== Reflect（反思节点）====================


def _get_min_evidence_count(query_intent: str) -> int:
    """根据查询意图获取最小证据数量阈值"""
    thresholds = {"qa": 5, "recommend": 10, "compare": 8, "list": 15, "unknown": 5}
    return int(thresholds.get(query_intent, 5))


def _get_min_top_score(query_intent: str) -> float:
    """根据查询意图获取最小分数阈值"""
    thresholds = {"qa": 0.4, "recommend": 0.6, "compare": 0.5, "list": 0.7, "unknown": 0.5}
    return float(thresholds.get(query_intent, 0.5))


async def _reflect_node(state: RetrievalState, config: RunnableConfig) -> dict[str, Any]:
    """
    反思节点：评估检索质量，决定是否继续迭代

    质量指标：
    1. evidence_count: 检索结果数量（去重后）
    2. top_score: 最高分数（相关性）

    决策逻辑：
    - 如果 evidence_count >= min_evidence AND top_score >= min_score → 停止（质量满足）
    - 否则且 iterations < max_iterations → 继续（追加步骤）
    - 否则 → 停止（达到最大迭代次数）

    返回：State 更新（reflection）
    """
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

    # 聚合检索结果（去重）
    # Quality signals from merged retrieval results (deduped).
    aggregated = aggregate_run_results(results=list(runs)) if runs else RagRunResult(agent_type="unknown", answer="", error="no results")
    retrieval_results = aggregated.retrieval_results or []
    evidence_count = len(retrieval_results) if isinstance(retrieval_results, list) else 0

    # 计算最高分数
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

    # 获取质量阈值
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


# ==================== Merge（合并节点）====================


async def _merge_node(state: RetrievalState, config: RunnableConfig) -> dict[str, Any]:
    """
    合并节点：聚合检索结果 + 可选 enrichment

    核心功能：
    1. 聚合所有检索运行结果（去重）
    2. 构建 combined_context（用于 generation）
    3. 可选的 enrichment（movie KB 专用 TMDB 补全）
    4. 发送 debug 事件（combined_context, rag_runs）

    返回：State 更新（merged, stop_reason）
    """
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

    def _extract_seed_title(extracted: Any) -> str | None:
        if not isinstance(extracted, dict):
            return None
        low = extracted.get("low_level")
        if not isinstance(low, list) or not low:
            return None
        for x in low:
            s = str(x or "").strip()
            if not s:
                continue
            # Skip generic category tokens.
            if s in {"电影", "电视剧", "__discover_movie__", "__discover_tv__"}:
                continue
            return s
        return None

    def _movie_year(details: dict[str, Any]) -> int | None:
        rd = details.get("release_date")
        if isinstance(rd, str) and len(rd) >= 4 and rd[:4].isdigit():
            try:
                return int(rd[:4])
            except Exception:
                return None
        return None

    def _movie_directors(details: dict[str, Any]) -> list[str]:
        credits = details.get("credits") if isinstance(details.get("credits"), dict) else {}
        crew = credits.get("crew") if isinstance(credits, dict) else None
        out: list[str] = []
        if isinstance(crew, list):
            for m in crew:
                if not isinstance(m, dict):
                    continue
                if str(m.get("job") or "") != "Director":
                    continue
                name = str(m.get("name") or "").strip()
                if name:
                    out.append(name)
                if len(out) >= 3:
                    break
        return out

    def _movie_candidate(details: dict[str, Any]) -> dict[str, Any] | None:
        mid = details.get("id")
        try:
            tmdb_id = int(mid)
        except Exception:
            return None
        title = str(details.get("title") or details.get("original_title") or "").strip()
        if not title:
            return None
        return {
            "tmdb_id": tmdb_id,
            "title": title,
            "year": _movie_year(details),
            "overview": str(details.get("overview") or "").strip(),
            "vote_average": details.get("vote_average"),
            "genres": details.get("genres") if isinstance(details.get("genres"), list) else [],
            "directors": _movie_directors(details),
        }

    def _build_tmdb_only_answer(selected: list[dict[str, Any]]) -> str:
        lines: list[str] = ["为你推荐以下电影："]
        for i, it in enumerate(selected, start=1):
            title = str(it.get("title") or "").strip()
            year = it.get("year")
            y = f"{int(year)}" if isinstance(year, int) else ""
            blurb = str(it.get("blurb") or "").strip()
            head = f"{i}. 《{title}》" + (f"（{y}）" if y else "")
            lines.append(head)
            if blurb:
                lines.append(blurb)
            lines.append("")  # blank line between items
        return "\n".join(lines).strip()

    # ---------------- TMDB-only recommendation path ----------------
    tmdb_only = bool(state.get("tmdb_only_recommendation"))
    if tmdb_only and (kb_prefix or "").strip() == "movie":
        from infrastructure.enrichment import get_tmdb_enrichment_service

        svc = get_tmdb_enrichment_service()
        if svc is None:
            writer({"status": "error", "message": "TMDB 未配置，无法执行推荐（TMDB-only）"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}

        store = getattr(svc, "get_store", lambda: None)()
        client = getattr(svc, "get_client", lambda: None)()
        if store is None:
            writer({"status": "error", "message": "Postgres 未配置，无法落库 TMDB 推荐数据"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}
        if client is None:
            writer({"status": "error", "message": "TMDB client 未初始化"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}

        seed_title = _extract_seed_title(extracted_entities)
        tmdb_endpoint = "/discover/movie"
        disambiguation: list[dict[str, Any]] = []
        multi_raw: Any | None = None
        discover_raw: Any | None = None

        candidate_ids: list[int] = []
        try:
            if seed_title:
                payload, meta = await client.resolve_entity_via_multi(text=seed_title, query=query)
                if isinstance(meta, dict):
                    disambiguation = [meta]
                    multi_raw = meta.get("multi_results_raw")
                if isinstance(payload, dict) and payload.get("type") == "movie":
                    data = payload.get("data")
                    if isinstance(data, dict) and data.get("id") is not None:
                        seed_id = int(data.get("id"))
                        tmdb_endpoint = f"/movie/{seed_id}/recommendations"
                        rec_raw = await client.movie_recommendations_raw(movie_id=seed_id, language="zh-CN", page=1)
                        discover_raw = rec_raw
                        results = rec_raw.get("results") if isinstance(rec_raw, dict) else None
                        if isinstance(results, list):
                            for r in results:
                                if not isinstance(r, dict):
                                    continue
                                rid = r.get("id")
                                if rid is None:
                                    continue
                                try:
                                    candidate_ids.append(int(rid))
                                except Exception:
                                    continue
            if not candidate_ids:
                raw = await client.discover_movie_raw(
                    language="zh-CN",
                    page=1,
                    sort_by=str((filters or {}).get("sort_by") or "popularity.desc"),
                    filters=filters if isinstance(filters, dict) else None,
                )
                discover_raw = raw
                results = raw.get("results") if isinstance(raw, dict) else None
                if isinstance(results, list):
                    for r in results:
                        if not isinstance(r, dict):
                            continue
                        rid = r.get("id")
                        if rid is None:
                            continue
                        try:
                            candidate_ids.append(int(rid))
                        except Exception:
                            continue
        except Exception as e:
            writer({"status": "error", "message": f"TMDB 获取候选失败: {e}"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}

        # Dedup & trim.
        dedup_ids: list[int] = []
        seen = set()
        for mid in candidate_ids:
            if mid in seen:
                continue
            seen.add(mid)
            dedup_ids.append(int(mid))
        candidate_ids = dedup_ids[:20]

        if not candidate_ids:
            writer({"status": "error", "message": "TMDB 未返回可用候选电影"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}

        sem = asyncio.Semaphore(6)

        async def _fetch_one(mid: int) -> dict[str, Any] | None:
            async with sem:
                d = await client.get_movie_details(int(mid), language="zh-CN")
                if not isinstance(d, dict) or not d:
                    return None
                overview = str(d.get("overview") or "").strip()
                if not overview:
                    d_en = await client.get_movie_details(int(mid), language="en-US")
                    if isinstance(d_en, dict) and str(d_en.get("overview") or "").strip():
                        d["overview"] = str(d_en.get("overview") or "")
                return d

        fetched = await asyncio.gather(*[_fetch_one(mid) for mid in candidate_ids[:10]], return_exceptions=True)
        details_list: list[dict[str, Any]] = []
        for r in fetched:
            if isinstance(r, dict) and r:
                details_list.append(r)

        if not details_list:
            writer({"status": "error", "message": "TMDB 详情拉取失败（无可用详情）"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}

        candidates: list[dict[str, Any]] = []
        payloads: list[dict[str, Any]] = []
        for d in details_list:
            payloads.append({"type": "movie", "data": d})
            c = _movie_candidate(d)
            if c is not None:
                candidates.append(c)

        if not candidates:
            writer({"status": "error", "message": "TMDB 详情解析失败（无可用候选）"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}

        # User/session are required to log enrichment requests in Postgres.
        if not str(state.get("user_id") or "").strip() or not str(state.get("session_id") or "").strip():
            writer({"status": "error", "message": "缺少 user_id/session_id，无法落库 TMDB 推荐请求"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}

        # Mandatory persistence (request log + entity snapshots).
        try:
            persist = getattr(store, "persist_enrichment", None)
            if not callable(persist):
                raise RuntimeError("tmdb store missing persist_enrichment")
            await persist(
                user_id=str(state.get("user_id") or ""),
                session_id=str(state.get("session_id") or ""),
                request_id=str(state.get("request_id") or "") if state.get("request_id") is not None else None,
                conversation_id=state.get("conversation_id"),
                user_message_id=state.get("user_message_id"),
                query_text=query,
                tmdb_endpoint=tmdb_endpoint,
                extracted_entities=[seed_title] if seed_title else ["__discover_movie__"],
                disambiguation=disambiguation or [{"type": "movie_recommendations"}],
                payloads=payloads,
                candidates_top3=None,
                multi_results_raw=multi_raw,
                discover_results_raw=discover_raw,
                tmdb_language="zh-CN",
                duration_ms=float((time.monotonic() - t0) * 1000),
            )
        except Exception as e:
            writer({"status": "error", "message": f"TMDB 数据落库失败: {e}"})
            return {"stop_reason": "tmdb_only_recommendation_failed"}

        selected_movies = await select_tmdb_recommendation_movies(question=query, candidates=candidates, k=5)
        answer_text = _build_tmdb_only_answer(selected_movies)
        reco_ids = [int(x.get("tmdb_id")) for x in selected_movies if isinstance(x.get("tmdb_id"), int)]

        if reco_ids:
            writer(
                {
                    "status": "recommendations",
                    "content": {
                        "tmdb_ids": reco_ids,
                        "title": "为你推荐（TMDB）",
                        "mode": "tmdb_recommendations",
                        "media_type": "movie",
                    },
                }
            )

        merged = MergedOutput(
            context="",
            retrieval_results=[],
            reference={},
            statistics={
                "tmdb_only_recommendation": True,
                "selected_movies": selected_movies,
                "answer": answer_text,
                "tmdb_endpoint": tmdb_endpoint,
            },
        )

        return {
            "merged": merged,
            "stop_reason": "tmdb_only_recommendation",
            "tmdb_selected_movies": selected_movies,
            "tmdb_only_answer": answer_text,
        }

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
                        # Best-effort: collect TMDB ids from enrichment so clients can render
                        # movie cards linked to citations/references (even for QA, not only recommend).
                        try:
                            mt = str(media_type_hint or "").strip().lower()
                            ids: list[int] = []
                            for n in result.transient_graph.nodes or []:
                                if not isinstance(getattr(n, "labels", None), set):
                                    continue
                                if mt == "tv" and "TV" not in n.labels:
                                    continue
                                if mt != "tv" and "Movie" not in n.labels:
                                    continue
                                props = getattr(n, "properties", None)
                                tid = props.get("tmdb_id") if isinstance(props, dict) else None
                                if isinstance(tid, int):
                                    ids.append(tid)
                            state.setdefault("_tmdb_reco_ids", [])
                            if isinstance(state.get("_tmdb_reco_ids"), list):
                                state["_tmdb_reco_ids"].extend(ids)
                        except Exception:
                            # Best-effort only.
                            pass

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

    # Emit TMDB recommendation list for recommendation intents.
    # We intentionally do NOT derive ids from GraphRAG `reference` here, because for
    # queries like "推荐类似《喜宴》的电影" the reference often only includes the seed movie.
    try:
        mt = str(media_type_hint or "").strip().lower()
        qi = str(query_intent or "").strip().lower()
        if qi != "recommend":
            ids = []
        else:
            ids: list[int] = []
            extra = state.get("_tmdb_reco_ids")
            if isinstance(extra, list):
                for x in extra:
                    if isinstance(x, int):
                        ids.append(x)

        # Dedup while preserving order.
        dedup: list[int] = []
        seen = set()
        for tid in ids:
            if tid in seen:
                continue
            seen.add(tid)
            dedup.append(tid)

        if dedup:
            title = "为你推荐（TMDB）"
            writer(
                {
                    "status": "recommendations",
                    "content": {
                        "tmdb_ids": dedup,
                        "title": title,
                        "mode": "tmdb_recommendations",
                        "media_type": mt or "movie",
                    },
                }
            )
    except Exception:
        # Never fail retrieval on UI hints.
        pass

    return {"merged": merged, "stop_reason": state.get("stop_reason") or "success"}


def build_retrieval_subgraph():
    """
    构建检索子图（Plan → Execute → Reflect → Merge）

    子图结构：
    START → planner → executor → reflect → [循环回 executor] → merger → END
                                     ↓
                               (质量满足)
                                     ↓
                                  merger → END

    节点功能：
    - planner（计划节点）：产出检索计划（按意图/预算选择策略）
    - executor（执行节点）：执行计划并收集 runs/records
    - reflector（反思节点）：基于证据质量决定是否迭代
    - merger（合并节点）：合并 runs 为 combined_context，并可选拼接 enrichment

    返回：compiled graph（可供主图 add_node 使用）
    """
    g = StateGraph(RetrievalState)
    # NOTE: node names must not collide with state keys (LangGraph channel names).
    g.add_node("planner", _plan_node)
    g.add_node("executor", _execute_plan_node)
    g.add_node("reflector", _reflect_node)
    g.add_node("merger", _merge_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "executor")
    g.add_edge("executor", "reflector")
    # 条件边：reflect 决定是继续迭代还是合并
    g.add_conditional_edges(
        "reflector", _should_continue_from_reflect, {"continue": "executor", "merge": "merger"}
    )
    g.add_edge("merger", END)
    return g.compile()


# 编译后的检索子图实例（导出给主图使用）
retrieval_subgraph_compiled = build_retrieval_subgraph()
