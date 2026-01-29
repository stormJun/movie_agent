# 统一 LangGraph 架构重构设计：迁移 fusion_agent 核心能力

## 文档信息

- **版本**: v5.2
- **创建日期**: 2026-01-26
- **更新日期**: 2026-01-26
- **状态**: 设计方案（流式事件机制已明确，需要 POC 验证风险点）
- **作者**: Claude Code
- **核心目标**: 将 fusion_agent 的 **Plan → Execute → Reflect 迭代能力** 迁移到 LangGraph 子图
- **架构决策**: 子图作为主图的 First-Class Subgraph（直接 `add_node(subgraph)`，可在 Studio 展开）
- **I/O 契约**: Input/Output/Event 契约已明确；为保证可展开与事件冒泡，采用“State 扁平化”而非 nested `retrieval_input/retrieval_output`
- **能力映射**: rag_manager/chat_stream_executor 的能力已明确映射到子图节点
- **流式事件**: 沿用 custom + writer（与现有代码一致），不切换到 astream_events
- **关键优势**: 可视化、流式、调试、Human-in-the-loop 全部原生支持
- **风险点**: config/writer 透传、State 映射、事件冒泡需要 POC 验证
- **相关文档**:
  - [TMDB Enrichment 设计](../1.1.5.1/tmdb-enrichment.md)
  - [TMDB PostgreSQL 持久化](../1.1.5.2/tmdb-postgres-persistence.md)

## 目录

1. [背景与目标](#背景与目标)
2. [fusion_agent 核心能力分析](#fusion_agent-核心能力分析)
3. [设计原则](#设计原则)
4. [State 定义（强类型）](#state-定义强类型)
5. [Plan 节点：结构化计划生成](#plan-节点结构化计划生成)
6. [Execute 节点：按计划执行（串行/并行混合）](#execute-节点按计划执行串行并行混合)
7. [Reflect 节点：迭代闭环与预算约束](#reflect-节点迭代闭环与预算约束)
8. [Merge 节点：去重融合与产物整理](#merge-节点去重融合与产物整理)
9. [执行记录模型与时间线](#执行记录模型与时间线)
10. [挂载到对话主图](#挂载到对话主图)
11. [真实场景示例](#真实场景示例)
12. [实施计划](#实施计划)

---

## 背景与目标

### 当前系统的核心缺陷：缺少多步迭代能力

**现状**：
- LangGraph 负责对话流程（Router → Agent → LLM）
- Agent（graph/hybrid/naive）负责单次检索调用
- fusion_agent 有 Plan → Execute → Reflect 框架，但 **Reflector 未实现**，**Planner 简化为单任务**

**核心问题**：
1. **单次检索假设**：所有 Agent 都是"一次调用 → 返回结果"，缺少"补检索"能力
2. **固定工具选择**：Router 选定 agent_type 后，即使效果不好也无法降级
3. **无法处理多阶段任务**：推荐场景需要"先拉候选集 → 再补详情"，但当前只能单步完成

**例子**：用户问"推荐几部类似《喜宴》的电影"
- ❌ **当前**：Router → fusion_agent → 固定并行 4 路 → 去重 → 返回
  - 问题：4 路并行有重叠，且没有"先候选、再详情"的两阶段逻辑
- ✅ **期望**：Plan → Execute → Reflect
  - Plan：生成 2 步计划（step_0 拉候选 50 部，step_1 补充详情）
  - Execute：先执行 step_0（hybrid 拉候选），再执行 step_1（global 补详情）
  - Reflect：如果候选不足 10 部，追加 step_2（naive 兜底）

### 重构目标：迭代编排作为一等公民

> **将 fusion_agent 的 Plan → Execute → Reflect 迭代能力迁移到 LangGraph 子图**

**核心思想**：
- **Plan**：将用户问题拆解成结构化步骤（`PlanStep[]`），每步指定工具、参数、预算、依赖
- **Execute**：按计划执行（支持串行/并行混合），每步生成执行记录（`ExecutionRecord`）
- **Reflect**：评估质量，决定是否追加步骤、改写 query 或停止（有预算约束）
- **Merge**：去重、融合、整理产物

**与"固定并行"的根本区别**：

| 对比项 | ❌ Fanout + Reducer（固定并行） | ✅ Plan → Execute → Reflect（迭代编排） |
|-------|-------------------------------|-------------------------------------|
| **执行模式** | 固定 4 路并行（local/global/hybrid/naive） | 动态生成步骤，按 depends_on 串行/并行混合 |
| **工具选择** | Router 在 4 个 Agent 中选一个 | Plan 根据任务阶段动态选工具（hybrid/global/naive） |
| **迭代能力** | 无（单次调用） | Reflect 可追加步骤、改写 query、降级工具 |
| **预算控制** | 无（固定并行） | 每步有独立预算（timeout、top_k、max_retries） |
| **可观测性** | 简单的 retrieval_done | 三层嵌套执行记录（subgraph → step → tool） |
| **适用场景** | 简单 QA | QA + 推荐 + 比较 + 列表（复杂多步任务） |

**为什么需要迭代编排**？

1. **补检索**：单次检索可能证据不足，需要追加兜底检索
   - 示例：hybrid 检索返回 5 条，但阈值要求 10 条 → 追加 naive 检索
2. **降级**：选错工具导致超时或失败，需要降级到更简单的工具
   - 示例：global 超时 → 降级到 local（向量检索）
3. **多阶段任务**：某些场景需要多个步骤，不能一次完成
   - 示例：推荐电影 = 拉候选集（step_0） + 补详情（step_1）
4. **Query 改写**：原始 query 效果不好，需要 LLM 改写
   - 示例："李安的电影风格"检索结果太泛 → 改写为"李安导演作品的叙事特点和主题"

---

## fusion_agent 核心能力分析

### 当前 fusion_agent 的能力

通过阅读代码，fusion_agent (MultiAgentOrchestrator) 的核心能力是：

#### 1. Planner：任务拆解与结构化计划

```python
# 当前：RetrieveOnlyPlanner（简化版）
def generate_plan(state):
    task = TaskNode(
        task_type="hybrid_search",  # 工具类型
        description=query,            # 任务描述
        parameters={"query": query},  # 工具参数
        priority=1,                   # 优先级
    )
    plan_spec = PlanSpec(
        task_graph=TaskGraph(nodes=[task], execution_mode="sequential"),
        acceptance_criteria=AcceptanceCriteria(min_evidence_count=0),
    )
    return plan_spec
```

**能力**：
- ✅ 任务拆解（将用户问题拆成子任务）
- ✅ 工具选择（根据子任务选择 tool）
- ✅ 参数化（每个任务有独立的 parameters）
- ✅ 预算约束（acceptance_criteria）
- ❌ 但当前是简化版（只有单一任务）

#### 2. Executor：执行计划（RetrievalExecutor）

```python
# 当前：RetrievalExecutor
def execute_task(task, state):
    # 1. 根据 task_type 从 TOOL_REGISTRY 选择工具
    tool_instance = self._get_tool_instance(task.task_type)

    # 2. 调用工具
    result = tool_instance.retrieve_only(task.parameters)

    # 3. 记录执行记录
    record = ExecutionRecord(
        task_id=task.task_id,
        tool_calls=[...],
        evidence=...,
        metadata=...,
    )

    return record
```

**能力**：
- ✅ 工具路由（根据 task_type 选择工具）
- ✅ 参数化调用（每个任务有独立的 parameters）
- ✅ 执行记录（记录每次 tool call）
- ❌ 但当前没有利用 depends_on 关系

#### 3. Reflector：反思与迭代（当前未实现）

```python
# 当前：Reflector（理论上应该有，但 v3 没有实现）
def reflect(execution_records, plan_spec):
    # 1. 评估质量
    quality = assess_quality(execution_records)

    # 2. 决定是否继续
    if quality < threshold:
        # 追加新步骤或改写 query
        new_tasks = generate_new_tasks(...)

    return reflection
```

**应该有的能力**（但当前未实现）：
- ✅ 质量评估（证据数量、分数、覆盖率）
- ✅ 追加步骤（补充检索、兜底检索）
- ✅ 改写 query（如果原始 query 效果不好）
- ✅ 预算约束（最多 N 轮、每步超时）

#### 4. Reporter：报告生成（当前是 NoopReporter）

```python
# 当前：NoopReporter（retrieve_only 模式下不需要）
def generate_report(state):
    pass  # 不生成报告
```

### 我们要迁移的能力

| 能力 | fusion_agent 当前实现 | 新架构迁移 |
|-----|---------------------|----------|
| **任务拆解** | RetrieveOnlyPlanner（单任务） | Plan 节点（多步骤，支持依赖） |
| **工具路由** | ✅ RetrievalExecutor | ✅ Execute 节点（保留） |
| **串行/并行混合** | ❌ 未利用 depends_on | ✅ Execute 节点（按 depends_on 执行） |
| **执行记录** | ✅ ExecutionRecord | ✅ ExecutionRecord（增强） |
| **质量评估** | ❌ 未实现 | ✅ Reflect 节点 |
| **迭代闭环** | ❌ 未实现 | ✅ Reflect + Append 节点 |
| **预算约束** | ✅ acceptance_criteria | ✅ PlanStep.budget |

---

## 核心设计哲学：迭代编排作为一等公民

### 哲学 1：检索是迭代过程，不是单次调用

**传统假设**：Router 选 Agent → Agent 调用一次 → 返回结果
- ❌ 问题：单次检索可能证据不足、选错工具、无法处理多阶段任务

**新假设**：检索是"计划 → 执行 → 反思 → 追加/停止"的迭代过程
- ✅ Plan：先想好需要几步、每步用什么工具、什么预算
- ✅ Execute：按计划执行（可串行、可并行）
- ✅ Reflect：评估质量，决定是否需要补检索、改写 query 或停止
- ✅ 迭代：如果 Reflect 认为需要，追加新步骤并回到 Execute

**关键洞察**：
> 大部分复杂查询不能通过一次检索完成，需要多步迭代。例如：
> - 推荐：先拉候选集（向量检索）→ 再补详情（全局检索）→ 如果不足再兜底（关键词）
> - 比较：分别检索两部电影 → 再对比分析 → 如果信息不全再补字段
> - 分析：先用 hybrid 快速定位 → 再用 global 深挖 → 如果超时降级到 local

### 哲学 2：Plan 是"任务编排"而非"工具选择"

**传统理解**（错误）：
- Plan 节点 = 在 4 个 Agent 中选一个（graph/hybrid/naive/fusion）
- 本质还是"工具选择"，只是从 Router 移到了 Plan

**正确理解**：
- Plan 节点 = 任务拆解 + 工具编排 + 依赖管理
- 产出 `List[PlanStep]`，每个 step 包含：
  - **objective**：本步的目标（拉候选集？补详情？对比分析？）
  - **tool**：用什么工具完成（hybrid/global/local/naive/enrichment）
  - **depends_on**：依赖哪些前置步骤（控制串行 vs 并行）
  - **budget**：本步的预算约束（超时、top_k、重试次数）

**对比**：

| 场景 | 传统方式（工具选择） | Plan 方式（任务编排） |
|-----|-------------------|-------------------|
| 简单 QA | Router 选 hybrid_agent | Plan 生成 1 步：`{tool: hybrid, objective: "检索喜宴基本信息"}` |
| 推荐 | Router 选 fusion_agent → 固定 4 路并行 | Plan 生成 2 步：`step_0: {tool: hybrid, objective: "拉候选集"}` → `step_1: {tool: global, depends_on: [step_0], objective: "补详情"}` |
| 比较 | Router 选 fusion_agent → 固定 4 路并行 | Plan 生成 3 步：`step_0: {tool: hybrid, objective: "检索喜宴"}` ∥ `step_1: {tool: hybrid, objective: "检索饮食男女"}` → `step_2: {tool: global, depends_on: [step_0, step_1], objective: "对比分析"}` |

### 哲学 3：Reflect 是"质量门" + "补查策略"

**Reflect 不是简单的"阈值判断"**，而是：
1. **质量评估**：检查 evidence_count、top_score、missing_fields、errors
2. **补查策略**：根据不同质量问题采取不同策略
   - 证据数量不足 → 追加 naive 兜底检索
   - top_score 过低 → 改写 query（让 LLM 优化）→ 追加检索
   - 缺少关键字段 → 补充检索（用 enrichment 工具）
   - 超时/失败 → 降级到更简单的工具
3. **预算约束**：最多 N 轮迭代、总时长不超过 M 秒
4. **停止条件**：质量达标 OR 预算耗尽 OR 达到最大轮数

**示例**：

```python
# Reflect 节点输出（示例）
reflection = Reflection(
    should_continue=True,
    next_steps=[
        PlanStep(
            step_id="step_2_fallback",
            objective="证据不足，追加 naive 兜底检索",
            tool="naive_search",
            tool_input={"query": original_query, "top_k": 50},
            depends_on=[],
            budget=PlanBudget(timeout_s=10.0, top_k=50)
        )
    ],
    reasoning="当前返回 5 条证据，低于阈值 10 条，需要追加兜底检索",
    current_iteration=1,
    max_iterations=3,
    remaining_budget=18.5  # 秒
)
```

### 哲学 4：执行记录是"三层嵌套"的可观测性

**可观测性不是简单的"有个 log 就行"**，而是：
1. **子图层**（subgraph）：Plan / Execute / Reflect / Merge 各节点的执行记录
2. **步骤层**（step）：每个 PlanStep 的 ExecutionRecord（输入、输出、耗时、状态）
3. **工具层**（tool）：工具内部的 `_log_step`（如 hybrid 的低层/高层检索）

**三层嵌套结构**：

```json
{
  "retrieval_subgraph": {
    "started_at": "2026-01-26T10:00:00Z",
    "duration_ms": 3500,
    "nodes": {
      "plan": {...},
      "execute_plan": {
        "steps": [
          {
            "step_id": "step_0_candidates",
            "tool": "hybrid_search",
            "duration_ms": 1200,
            "sub_steps": [
              {"name": "hybrid_low_level_retrieval", "duration_ms": 800},
              {"name": "hybrid_high_level_retrieval", "duration_ms": 400}
            ]
          },
          {
            "step_id": "step_1_evidence",
            "tool": "global_search",
            "duration_ms": 1800,
            "sub_steps": [
              {"name": "global_search_community_retrieval", "duration_ms": 1800}
            ]
          }
        ]
      },
      "reflect": {...},
      "merge": {...}
    }
  }
}
```

### 哲学 5：串行/并行是"依赖关系"的自然表达

**不是"固定 4 路并行"**，而是：
- **depends_on = []**：无依赖，可并行（如分别检索两部电影）
- **depends_on = [step_0]**：依赖 step_0，必须串行（如先拉候选、再补详情）

**示例**：

```python
# 场景：对比《喜宴》和《饮食男女》
plan = [
    PlanStep(step_id="step_0_movie_a", tool="hybrid", depends_on=[]),      # 可并行
    PlanStep(step_id="step_1_movie_b", tool="hybrid", depends_on=[]),      # 可并行
    PlanStep(step_id="step_2_compare", tool="global", depends_on=["step_0_movie_a", "step_1_movie_b"]),  # 串行（等待两部电影都检索完）
]
```

**执行顺序**：
1. 并行执行 `step_0_movie_a` 和 `step_1_movie_b`
2. 等待两者完成
3. 执行 `step_2_compare`（对比分析）

---

## 架构定位：子图作为主图的一等公民节点（First-Class Subgraph）

### 关键架构决策

> **Plan → Execute → Reflect 子图作为主图的 First-Class Subgraph（通过 `add_node` 添加），而非在 execute_node 内部嵌套调用（`ainvoke`）。**

### 为什么选择 First-Class Subgraph 而非嵌套调用？

**LangGraph 支持两种嵌套方式**：

| 特性 | ❌ 嵌套调用（Nested ainvoke） | ✅ First-Class Subgraph（add_node） |
|-----|----------------------------|-----------------------------------|
| **可视化** | 子图逻辑在主图视图中是"黑盒"，只显示为一个 execute_node | 子图在 LangGraph Studio 中可展开/缩放，结构清晰可见 |
| **流式支持** | 需手动传递 writer 回调，需手动桥接子图事件 | 原生支持：主图会自动流式输出子图节点的所有事件 |
| **状态管理** | State 完全隔离，需手动映射输入/输出 | 可通过 input_mapping 或 State 嵌套（`retrieval: RetrievalState`）自动映射 |
| **中断/介入** | 只能在 execute_node 前后中断，难以在子图内部断点 | 原生支持：可在子图内部节点（如 reflect）触发 Human-in-the-loop |
| **调试能力** | 只能调试主图，子图内部是黑盒 | 可在子图内部任意节点断点，调试能力更强 |
| **代码耦合** | execute_node 需要手动处理子图调用逻辑 | 主图只负责编排，子图独立，耦合度低 |

**选择 First-Class Subgraph 的核心原因**：
1. **可观测性极佳**：子图在 LangGraph Studio 中可展开/缩放，符合 LangGraph 设计原语
2. **代码更简洁**：不需要手动传递 writer、不需要手动桥接子图事件
3. **调试和人工干预**：支持在子图内部节点（如 reflect）触发 Human-in-the-loop
4. **流式输出原生支持**：LangGraph 的 `astream_events` API 会自动冒泡子图的事件

### 技术形态：主图显式编排子图节点（可展开）

#### 1. State 设计：State 扁平化（为了可展开）

**关键结论**：
- 为了让子图成为“真正可展开”的 first-class subgraph，我们不使用 `retrieval_input/retrieval_output` 这种 nested state。
- 子图所需字段直接作为主图 `ConversationState` 的顶层 key（同名）存在；子图输出也写回同名 key（如 `merged/plan/records/...`）。

```python
# backend/application/chat/conversation_graph.py
class ConversationState(TypedDict, total=False):
    # ===== 现有字段（保持不变） =====
    stream: bool
    user_id: str
    message: str
    session_id: str
    request_id: str | None
    requested_kb_prefix: str | None
    debug: bool
    incognito: bool
    agent_type: str
    conversation_id: Any
    current_user_message_id: Any

    # ===== 路由相关 =====
    kb_prefix: str
    worker_name: str
    route_decision: RouteDecision
    routing_ms: int
    resolved_agent_type: str
    use_retrieval: bool

    # ===== 记忆召回 =====
    memory_context: str | None
    conversation_summary: str | None
    history: list[dict[str, Any]]
    episodic_memory: list[dict[str, Any]] | None
    episodic_context: str | None

    # ===== 子图输入（first-class subgraph 直接读取这些 key）=====
    query: str
    user_message_id: Any

    # ===== 子图输出（first-class subgraph 写回）=====
    merged: dict[str, Any] | None
    plan: list[dict[str, Any]] | None
    records: list[dict[str, Any]] | None
    runs: list[dict[str, Any]] | None
    reflection: dict[str, Any] | None
    stop_reason: str | None

    # ===== 最终响应 =====
    response: dict[str, Any]
```

**RetrievalState（子图专用 State）**：

```python
# backend/infrastructure/rag/retrieval_subgraph.py
from typing import Optional, Dict, Any, List, TypedDict

class RetrievalState(TypedDict, total=False):
    # ===== 输入（由主图 prepare_retrieval 节点填充到 ConversationState 顶层同名 key）=====
    query: str
    kb_prefix: str
    route_decision: RouteDecision
    debug: bool
    session_id: str
    user_id: str | None
    request_id: str | None
    conversation_id: Any | None
    user_message_id: Any | None
    incognito: bool
    resolved_agent_type: str | None

    # ===== 输出 =====
    plan: List[PlanStep]
    records: List[ExecutionRecord]
    runs: List[Any]  # RagRunResult（dataclass），debug 响应时需转换为 dict
    reflection: Optional[Reflection]
    merged: Optional[MergedOutput]
    stop_reason: Optional[str]
```

#### 2. 主图编排：first-class subgraph + conditional edge

**现有主图（Before）**：
```python
# backend/application/chat/conversation_graph.py (现有代码)
def _build_graph(self):
    g = StateGraph(ConversationState)
    g.add_node("route", self._route_node)
    g.add_node("recall", self._recall_node)
    g.add_node("execute", self._execute_node)  # 旧的 execute_node，内部调用 stream_executor

    g.add_edge(START, "route")
    g.add_edge("route", "recall")
    g.add_edge("recall", "execute")
    g.add_edge("execute", END)
    return g.compile()
```

**新主图（After）**：
```python
# backend/application/chat/conversation_graph.py (重构后)
def _build_graph(self):
    g = StateGraph(ConversationState)

    # 1. 路由 & 召回节点（保持不变）
    g.add_node("route", self._route_node)
    g.add_node("recall", self._recall_node)

    # 2. 准备检索节点（Input Adapter：填充 RetrievalState 顶层 key）
    g.add_node("prepare_retrieval", self._prepare_retrieval_node)

    # 3. 检索子图节点（First-Class Subgraph，可在 Studio 展开）
    from infrastructure.rag.retrieval_subgraph import retrieval_subgraph_compiled
    g.add_node("retrieval_subgraph", retrieval_subgraph_compiled)

    # 4. 生成答案节点（新增）
    g.add_node("generate", self._generate_node)

    # 5. 边连接
    g.add_edge(START, "route")
    g.add_edge("route", "recall")
    g.add_edge("recall", "prepare_retrieval")

    # prepare_retrieval 之后根据 use_retrieval / use_kb_handler 决定是否跳过子图
    g.add_conditional_edges(
        "prepare_retrieval",
        _after_prepare,
        {
            "retrieval_subgraph": "retrieval_subgraph",
            "generate": "generate",
        },
    )
    g.add_edge("retrieval_subgraph", "generate")
    g.add_edge("generate", END)

    return g.compile()
```

#### 3. prepare_retrieval 节点（Input Adapter）

**职责**：在 ConversationState 顶层填充 RetrievalState 需要的 key（使 subgraph 可直接运行）

```python
# backend/application/chat/conversation_graph.py
async def _prepare_retrieval_node(
    self,
    state: ConversationState,
    config: RunnableConfig
) -> dict[str, Any]:
    """准备检索输入：将 ConversationState 转换为 RetrievalState"""

    message = str(state.get("message") or "")
    kb_prefix = str(state.get("kb_prefix") or "general")
    route_decision = state.get("route_decision")
    debug = bool(state.get("debug"))
    session_id = str(state.get("session_id") or "")

    return {
        "query": message,
        "kb_prefix": kb_prefix,
        "route_decision": route_decision,
        "debug": debug,
        "session_id": session_id,
        "user_id": user_id,
        "request_id": request_id,
        "conversation_id": conversation_id,
        "user_message_id": current_user_message_id,
        "incognito": incognito,
        "resolved_agent_type": resolved_agent_type,
    }
```

#### 4. 子图节点（First-Class Subgraph）：事件冒泡与 streaming 形态

**结论（已验证）**：
- 子图内部节点可以继续使用 `_get_stream_writer(config)` 写 `stream_mode="custom"` 事件。
- 主图在 `astream(..., stream_mode="custom", subgraphs=True)` 时，LangGraph 会返回 **带 namespace 的 tuple**：
  - `(ns, payload)`（当 `stream_mode` 不是 list）
  - 因此对外的 SSE/前端事件层需要解包，只转发 `payload`（dict）。

**实现要点**（已在代码落地）：
```python
# ConversationGraphRunner.astream_custom
async for chunk in graph.astream(state, stream_mode="custom", subgraphs=True):
    if isinstance(chunk, tuple) and len(chunk) == 2:
        ns, payload = chunk
        yield payload
    else:
        yield chunk
```

```python
# backend/application/chat/conversation_graph.py
class ConversationGraphRunner:
    def _build_graph(self):
        g = StateGraph(ConversationState)

        # 1. 路由 & 召回节点（保持不变）
        g.add_node("route", self._route_node)
        g.add_node("recall", self._recall_node)

        # 2. 准备检索节点（Input Adapter）
        g.add_node("prepare_retrieval", self._prepare_retrieval_node)

        # 3. 检索子图节点（First-Class Subgraph，可展开）
        from infrastructure.rag.retrieval_subgraph import retrieval_subgraph_compiled
        g.add_node("retrieval_subgraph", retrieval_subgraph_compiled)

        # 4. 生成答案节点（Output Adapter）
        g.add_node("generate", self._generate_node)

        # 5. 边连接
        g.add_edge(START, "route")
        g.add_edge("route", "recall")
        g.add_edge("recall", "prepare_retrieval")
        # prepare_retrieval 后根据 use_retrieval / use_kb_handler 决定是否跳过子图
        g.add_conditional_edges(
            "prepare_retrieval",
            _after_prepare,
            {
                "retrieval_subgraph": "retrieval_subgraph",
                "generate": "generate",
            },
        )
        g.add_edge("retrieval_subgraph", "generate")
        g.add_edge("generate", END)

        return g.compile()
```

**关键点**：
- ✅ **可展开**：`retrieval_subgraph` 在 Studio 中可展开/缩放
- ✅ **State 映射**：由 `prepare_retrieval` 填充顶层 key 完成（不需要 wrapper）
- ✅ **事件冒泡**：主图 `astream(..., subgraphs=True)` 后需要解包 `(ns, payload)`，对外只转发 `payload`

#### 5. 子图构建（独立文件）

```python
# backend/infrastructure/rag/retrieval_subgraph.py
from langgraph.graph import StateGraph, END

def build_retrieval_subgraph() -> CompiledGraph:
    """构建 Plan → Execute → Reflect → Merge 子图"""
    g = StateGraph(RetrievalState)

    # 添加节点
    # NOTE: 节点名不能与 state key 冲突（LangGraph channel 名冲突会报错）
    g.add_node("planner", _plan_node)
    g.add_node("executor", _execute_plan_node)
    g.add_node("reflector", _reflect_node)
    g.add_node("merger", _merge_node)

    # 添加边
    g.set_entry_point("planner")
    g.add_edge("planner", "executor")
    g.add_edge("executor", "reflector")
    g.add_conditional_edges(
        "reflector",
        _should_continue_execution,
        {
            "continue": "executor",  # 追加步骤，回到 execute
            "merge": "merger",
        }
    )

    g.add_edge("merger", END)

    return g.compile()

# 全局单例（编译后的子图）
retrieval_subgraph_compiled = build_retrieval_subgraph()
```

#### 6. 子图节点中使用 writer

**关键修正**：子图节点**可以**使用 writer，与现有代码一致（继续使用 `stream_mode="custom"`）。

```python
# backend/infrastructure/rag/retrieval_subgraph.py
async def _execute_plan_node(state: RetrievalState, config: RunnableConfig):
    \"\"\"子图节点：执行计划（MVP：并行执行 ready steps，细粒度埋点放在 execution_log.sub_steps）\"\"\"

    writer = _get_stream_writer(config)
    debug = bool(state.get(\"debug\"))

    # progress 事件会被 SSE 转发（debug 不要求）
    writer({\"status\": \"progress\", \"content\": {\"stage\": \"retrieval\", \"completed\": 0, \"total\": 1, \"error\": None}})

    # debug 主要通过 execution_log 记录（并在 rag_retrieval_done.sub_steps 展开）
    if debug:
        writer({\"execution_log\": {\"node\": \"executor\", \"node_type\": \"retrieval_subgraph\", \"duration_ms\": 0, \"input\": {}, \"output\": {}}})

    ...
```

**关键点**：
- ✅ **子图节点可以使用 writer**：与现有代码一致，通过 `_get_stream_writer(config)` 获取
- ✅ **事件格式一致**：继续使用现有的 `execution_log` / `status` 事件格式
- ✅ **DebugCollector 分流规则不变**：`execution_log` 是 cache-only，`status` 走 SSE

#### 7. generate 节点（Output Adapter）

**职责**：从 `state.merged` 提取 `context/reference/retrieval_results`，生成答案

```python
# backend/application/chat/conversation_graph.py
async def _generate_node(
    self,
    state: ConversationState,
    config: RunnableConfig
) -> dict[str, Any]:
    """生成答案：从 state.merged 提取结果"""

    merged = state.get("merged") or {}
    if not merged or not merged.get("context"):
        raise ValueError("子图未返回 merged.context")

    context = merged["context"]
    reference = merged.get("reference", {})

    # 记忆上下文
    memory_context = state.get("memory_context")
    conversation_summary = state.get("conversation_summary")
    episodic_context = state.get("episodic_context")
    history = state.get("history")

    # 生成答案（流式或非流式）
    stream = bool(state.get("stream"))
    debug = bool(state.get("debug"))

    if stream:
        # 流式生成（通过 writer 发送 token）
        writer = _get_stream_writer(config)
        async for chunk in generate_rag_answer_stream(
            question=state.get("message"),
            context=context,
            memory_context=memory_context,
            summary=conversation_summary,
            episodic_context=episodic_context,
            history=history,
        ):
            writer({"status": "token", "content": chunk})

        writer({"status": "done"})
        return {}

    # 非流式生成（RAG：使用 generate_rag_answer，避免 ChatCompletionPort 的接口膨胀）
    answer = await asyncio.to_thread(
        generate_rag_answer,
        question=state.get("message"),
        context=context,
        memory_context=memory_context,
        summary=conversation_summary,
        episodic_context=episodic_context,
        history=history,
    )

    # 构建响应
    response = {"answer": answer, "reference": reference}

    if debug:
        # debug 模式下，返回 plan/records/reflection（从顶层 state 获取）
        response["plan"] = state.get("plan", []) or []
        response["records"] = state.get("records", []) or []
        response["reflection"] = state.get("reflection")

    return {"response": response}
```

#### 8. 流式输出：沿用 custom + writer（与现有代码一致）

**关键风险：astream_events 与现有 SSE/Debug 分离机制不兼容**

**现状**：
- ✅ 现有代码使用 `stream_mode="custom" + writer` 手动写事件
- ✅ SSE 层通过 DebugCollector 分流：`execution_log` 是 cache-only，`status` 走 SSE
- ❌ LangGraph 的 `astream_events` 是另一套事件模型（`on_chain_start`/`on_chain_end`/`on_custom_event`）
- ❌ 如果切换到 `astream_events`，必须重做 SSE 事件协议/DebugCollector 的分流策略

**结论**：**继续使用 `stream_mode="custom" + writer`**，而不是 `astream_events`

**主图流式输出（与现有代码一致）**：

```python
# backend/application/chat/conversation_graph.py
class ConversationGraphRunner:
    async def astream_custom(self, state: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        """流式输出：与现有代码一致，使用 stream_mode="custom" """
        async for chunk in self._graph.astream(dict(state), stream_mode="custom"):
            if isinstance(chunk, dict):
                yield chunk
            else:
                # Defensive fallback: surface as token-ish content.
                yield {"status": "token", "content": str(chunk)}
```

**SSE 层（与现有代码一致）**：

```python
# backend/server/api/rest/v1/chat_stream.py
@router.post("/stream")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    ...

    # 主图的 astream_custom 会自动流式输出子图的所有事件
    # 子图节点通过 writer 发送的事件会自动冒泡到这里
    async for ev in graph_runner.astream_custom(state):
        # ev 会包含子图节点的事件（execution_log/status）
        # SSE 层会通过 DebugCollector 分流
        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
```

**DebugCollector 分流规则（与现有代码一致）**：

```python
# backend/infrastructure/debug/debug_collector.py (现有代码)
class DebugCollector:
    def collect(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """收集 debug 事件，分离 cache-only 和 SSE 事件"""
        events = []

        if "execution_log" in event:
            # cache-only：不走 SSE，只存到 Redis
            self._store_to_redis(event)
            events.append(event)

        if "status" in event:
            status = event["status"]
            if status in ("progress", "token", "done", "error", "enrichment"):
                # SSE 事件：走 SSE
                events.append(event)
            elif status in ("retrieval_step_start", "retrieval_step_done"):
                # cache-only：不走 SSE
                self._store_to_redis(event)

        return events
```

**关键点**：
- ✅ **沿用现有机制**：继续使用 `stream_mode="custom" + writer`
- ✅ **DebugCollector 分流不变**：`execution_log` 是 cache-only，`status` 走 SSE
- ✅ **不依赖 astream_events**：避免重做 SSE 事件协议/DebugCollector 的分流策略

#### 9. 流式输出：为什么不用 astream_events？

**LangGraph 的 astream_events vs 现有 custom + writer 机制**：

| 对比项 | ✅ 现有方案（custom + writer） | ❌ astream_events |
|-------|---------------------------|------------------|
| **事件格式** | 自定义（`execution_log`/`status`） | LangGraph 格式（`on_chain_start`/`on_chain_end`） |
| **Debug 分流** | ✅ DebugCollector 分离 cache-only/SSE | ❌ 需要重做分流策略 |
| **SSE 协议** | ✅ 与现有 SSE 协议一致 | ❌ 需要重做 SSE 协议 |
| **子图事件冒泡** | ✅ writer 自动冒泡 | ❌ astream_events 需要特殊处理 |
| **Py3.10 兼容** | ✅ `_get_stream_writer(config)` 绕开限制 | ⚠️ 可能依赖 async contextvar |
| **前端适配** | ✅ 前端已适配现有事件格式 | ❌ 前端需要重做事件解析 |

**结论**：继续使用 `custom + writer`，不切换到 `astream_events`

**关键点**：
- ✅ **避免重做 SSE 协议**：现有 SSE 协议已经稳定工作
- ✅ **避免重做 Debug 分流**：DebugCollector 的分流逻辑已经完善
- ✅ **前端不需要改动**：前端已适配现有事件格式
- ✅ **Py3.10 兼容**：继续使用 `_get_stream_writer(config)` 绕开限制

#### 10. 落地验证清单（已验证）

1. **first-class subgraph 可展开**：主图直接 `add_node("retrieval_subgraph", retrieval_subgraph_compiled)`，Studio 可展开/缩放
2. **State 映射（扁平化）**：`prepare_retrieval` 在 ConversationState 顶层填充 `query/kb_prefix/route_decision/...`；子图写回 `merged/plan/records/runs/...`
3. **writer + custom 事件**：子图内部节点继续用 `_get_stream_writer(config)` 写 `stream_mode="custom"` 事件（与现有 SSE/Debug 协议一致）
4. **事件冒泡（关键细节）**：主图流式必须 `subgraphs=True`；LangGraph 会产出 `(ns, payload)`，需要解包并仅对外转发 `payload`
5. **节点名冲突规避**：子图节点使用 `planner/executor/reflector/merger`，避免与 state key（如 `plan/records/merged`）同名冲突
6. **Debug 分流不变**：`execution_log/route_decision/rag_runs/combined_context` 仍是 cache-only；`progress/error/token/done` 走 SSE
7. **非 debug 也有 progress**：`generate` 节点会发 `progress(stage=generation)`，保证 UI 在 debug=false 也能显示阶段

### 与现有代码的映射

| 现有代码 | 新架构中的位置 | 变化 |
|---------|--------------|------|
| `conversation_graph.py` | 主图 | ✅ route → recall → prepare_retrieval → retrieval_subgraph → generate（并用 conditional edge 跳过子图） |
| `chat_stream_executor.py` | 兼容/KB handler 内部 | ⚠️ /chat/stream 的主路径由 LangGraph generate 驱动；KB handler 分支仍可能使用它 |
| `rag_manager.py` | 子图执行/merge | ✅ 作为执行器：`run_retrieval_for_spec()` + enrichment decision helpers |
| `graphrag_agent/agents/*` | 子图执行的工具集合 | ✅ 仍然复用原有 Agent（graph/hybrid/naive/deep 等） |
| `fusion_agent` | 逐步被替代 | ⚠️ fusion_agent（旧 multi-agent）保留，但其 “Plan→Execute→Reflect” 能力已迁移到 retrieval_subgraph |

### 对比总结

| 对比项 | ❌ 嵌套调用（Nested ainvoke） | ✅ First-Class Subgraph（add_node） |
|-------|----------------------------|-----------------------------------|
| **可视化** | 子图是黑盒 | 子图在 LangGraph Studio 可展开 |
| **流式支持** | 需手动桥接事件 | `custom + writer` + `subgraphs=True`（tuple 解包）实现事件冒泡 |
| **State 管理** | 需 wrapper/nested 映射 | 通过“State 扁平化 + prepare_retrieval”稳定映射 |
| **调试能力** | 只能调试主图 | 可在子图内部任意节点断点 |
| **Human-in-the-loop** | 不支持 | 支持在子图内部节点（如 reflect）触发介入 |
| **代码耦合** | execute_node 需手动处理子图调用 | 主图只负责编排，耦合度低 |

---

## 现有能力映射清单：rag_manager/chat_stream_executor → 子图节点

### 为什么需要能力映射？

**问题**：文档虽然提出了 Plan → Execute → Reflect → Merge 子图，但没有明确说明：
- rag_manager.py 的现有能力（fanout 并行、聚合去重、enrichment 注入等）由子图的哪些节点承接
- chat_stream_executor.py 的现有能力（取消传播、debug 子步骤、进度更新等）如何保留

**风险**：如果没有明确映射，直接删除 rag_manager/chat_stream_executor 会丢功能/丢观测。

### rag_manager.py 的现有能力清单

| 能力 | 代码位置 | 功能描述 | 子图承接节点 |
|-----|---------|---------|------------|
| **单个 spec 检索** | `run_retrieval_for_spec()` | 调用 agent.retrieve_with_trace()，超时控制 | Execute 节点（`_execute_single_step()`） |
| **Fanout 并行** | `run_plan_retrieval()` | 并行执行多个 spec（asyncio.gather） | ❌ 不需要（Plan 节点的 depends_on 已处理并行） |
| **聚合去重** | `aggregate_run_results()` | 聚合多个 agent 的结果，去重 | Merge 节点（`_merge_node()`） |
| **Combined Context** | `build_context_from_runs()` | 将多个 agent 的 context 合并 | Merge 节点（`_merge_node()`） |
| **Enrichment 注入** | `run_plan_blocking()` | TMDB enrichment，注入 transient graph | Merge 节点（调用 `tmdb_enrichment_service`） |
| **Answer 生成** | `run_plan_blocking()` | 调用 generate_rag_answer() | ❌ 不承接（由主图 generate 节点负责） |

### chat_stream_executor.py 的现有能力清单

| 能力 | 代码位置 | 功能描述 | 子图承接节点 |
|-----|---------|---------|------------|
| **Fanout 并行** | `stream()` - asyncio.create_task | 并行执行多个 spec | ❌ 不需要（Plan 节点的 depends_on 已处理并行） |
| **取消传播** | `finally: pending tasks cancel()` | 客户端断开时取消未完成的任务 | Execute 节点（asyncio.CancelledError 自动传播） |
| **超时控制** | `asyncio.as_completed(timeout=)` | 整体超时控制 | Execute 节点（PlanStep.budget.timeout_s） |
| **进度更新** | `yield {"status": "progress", ...}` | 发送 progress 事件（stage, completed, total） | Execute 节点（通过 callback 发出） |
| **Debug 子步骤** | `execution_log + sub_steps` | 三层嵌套执行记录（subgraph → step → tool） | Execute 节点（ExecutionRecord.sub_steps） |
| **Enrichment 注入** | `tmdb_enrichment_service.enrich_query()` | TMDB enrichment，注入 transient graph | Merge 节点（在 merge 阶段注入） |
| **Combined Context** | `build_context_from_runs()` | 合并多个 agent 的 context | Merge 节点（`_merge_node()`） |
| **Combined Context 事件** | `yield {"status": "combined_context", ...}` | 发送 combined_context 事件（debug 用） | Merge 节点（通过 callback 发出） |
| **RAG Runs 事件** | `yield {"status": "rag_runs", ...}` | 发送 rag_runs 事件（debug 用） | Merge 节点（通过 callback 发出） |
| **Answer 流式生成** | `generate_rag_answer_stream()` | 流式生成答案 | ❌ 不承接（由主图 generate 节点负责） |

### 关键能力映射详解

#### 1. Fanout 并行：Plan 节点的 depends_on 处理

**现有代码**（chat_stream_executor.py）：
```python
# fanout 并行：多个 spec 同时执行
retrieval_tasks: list[asyncio.Task] = []
for spec in plan:
    task = asyncio.create_task(
        self._rag_manager.run_retrieval_for_spec(...)
    )
    retrieval_tasks.append(task)

for task in asyncio.as_completed(retrieval_tasks, timeout=overall_timeout_s):
    run = await task
    ...
```

**新架构**（Plan 节点）：
```python
# Plan 节点生成 PlanStep[]，通过 depends_on 控制并行
plan = [
    PlanStep(step_id="step_0_movie_a", tool="hybrid", depends_on=[]),      # 可并行
    PlanStep(step_id="step_1_movie_b", tool="hybrid", depends_on=[]),      # 可并行
    PlanStep(step_id="step_2_compare", tool="global", depends_on=["step_0", "step_1"]),  # 串行
]
```

**Execute 节点自动处理并行**：
```python
# Execute 节点根据 depends_on 自动并行/串行
parallel_steps = [s for s in plan if not s.depends_on]
serial_steps = [s for s in plan if s.depends_on]

# 并行执行无依赖的步骤
parallel_results = await asyncio.gather(
    *[_execute_single_step(step, state) for step in parallel_steps],
    return_exceptions=True
)
```

**关键点**：
- ✅ **不需要显式的 fanout 并行**：Plan 节点的 `depends_on` 已隐含了并行关系
- ✅ **Execute 节点自动识别**：`depends_on=[]` 的步骤自动并行执行

#### 2. 取消传播：Execute 节点的 asyncio.CancelledError

**现有代码**（chat_stream_executor.py）：
```python
try:
    for task in asyncio.as_completed(retrieval_tasks, timeout=overall_timeout_s):
        run = await task
        ...
except asyncio.CancelledError:
    raise
finally:
    # 取消未完成的任务
    pending = [t for t in retrieval_tasks if not t.done()]
    for t in pending:
        t.cancel()
```

**新架构**（Execute 节点）：
```python
# Execute 节点
async def _execute_plan_node(state: RetrievalState, config: RunnableConfig):
    plan = state.get("plan", [])

    # 执行步骤（如果有任何步骤抛出 asyncio.CancelledError，会自动传播）
    for step in plan:
        result = await _execute_single_step(step, state)
        records.append(result)

    return {"records": records}

# _execute_single_step 内部
async def _execute_single_step(step: PlanStep, state: RetrievalState):
    # 如果主图取消了，asyncio.CancelledError 会自动传播到这里
    # 不需要显式处理
    result = await agent.retrieve_with_trace(query, ...)
    return ExecutionRecord(...)
```

**关键点**：
- ✅ **自动传播**：`asyncio.CancelledError` 会自动从主图传播到子图节点
- ✅ **不需要手动取消**：LangGraph 会自动清理未完成的任务

#### 3. 聚合去重：Merge 节点的去重逻辑

**现有代码**（rag_manager.py）：
```python
def aggregate_run_results(results: list[RagRunResult]) -> RagRunResult:
    """聚合多个 agent 的结果，去重"""
    # 1. 合并 retrieval_results
    all_results = []
    for run in results:
        if run.retrieval_results:
            all_results.extend(run.retrieval_results)

    # 2. 去重（基于 source_id + chunk_id）
    seen = set()
    deduped = []
    for r in all_results:
        key = (r.metadata.get("source_id"), r.metadata.get("chunk_id"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return RagRunResult(
        retrieval_results=deduped,
        context=build_context_from_runs(deduped),
        ...
    )
```

**新架构**（Merge 节点）：
```python
# Merge 节点
def _merge_node(state: RetrievalState, config: RunnableConfig):
    records = state.get("records", [])
    retrieval_results = state.get("retrieval_results", [])

    # 1. 聚合所有步骤的 retrieval_results
    all_results = []
    for record in records:
        all_results.extend(record.raw_output.get("retrieval_results", []))

    # 2. 去重（基于 source_id + chunk_id）
    seen = set()
    deduped = []
    for r in all_results:
        metadata = r.get("metadata", {})
        key = (metadata.get("source_id"), metadata.get("chunk_id"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    # 3. 构建 combined context
    combined_context = _build_context_from_results(deduped)

    merged = MergedOutput(
        context=combined_context,
        retrieval_results=deduped,
        reference=_build_reference(deduped),
        statistics={"total_retrieved": len(all_results), "after_dedup": len(deduped)},
    )

    return {"merged": merged}
```

**关键点**：
- ✅ **Merge 节点承接**：聚合去重逻辑由 Merge 节点负责
- ✅ **逻辑一致**：与现有的 `aggregate_run_results()` 保持一致

#### 4. Combined Context：Merge 节点的 context 构建

**现有代码**（rag_manager.py）：
```python
def build_context_from_runs(runs: list[dict]) -> str:
    """将多个 agent 的 context 合并"""
    contexts = [r["context"] for r in runs if r.get("context")]
    return "\n\n".join(contexts)
```

**新架构**（Merge 节点）：
```python
# Merge 节点
def _merge_node(state: RetrievalState, config: RunnableConfig):
    retrieval_results = state.get("retrieval_results", [])

    # 构建combined context
    contexts = []
    for r in retrieval_results:
        if r.get("evidence"):
            contexts.append(f"[Source: {r.get('metadata', {}).get('source_id')}]\n{r['evidence']}")

    combined_context = "\n\n".join(contexts)

    merged = MergedOutput(
        context=combined_context,
        retrieval_results=retrieval_results,
        ...
    )

    return {"merged": merged}
```

**关键点**：
- ✅ **Merge 节点承接**：context 构建逻辑由 Merge 节点负责
- ✅ **格式一致**：与现有的 `build_context_from_runs()` 保持一致

#### 5. Enrichment 注入：Merge 节点的 TMDB enrichment

**现有代码**（chat_stream_executor.py）：
```python
# Query-time enrichment
if kb_prefix == "movie" and _should_enrich_by_entity_matching(...):
    svc = get_tmdb_enrichment_service()
    result = await svc.enrich_query(
        message=message,
        extracted_entities=extracted_entities,
        query_intent=query_intent,
        media_type_hint=media_type_hint,
        filters=filters,
        ...
    )

    if result.success and result.transient_graph:
        enriched_context = result.transient_graph.to_context_text()
        combined_context = f"{combined_context}\n\n{enriched_context}"
```

**新架构**（Merge 节点）：
```python
# Merge 节点
def _merge_node(state: RetrievalState, config: RunnableConfig):
    retrieval_results = state.get("retrieval_results", [])
    route_decision = state.get("route_decision")
    kb_prefix = state.get("kb_prefix")

    # 1. 构建 combined context（来自检索结果）
    combined_context = _build_context_from_results(retrieval_results)

    # 2. Enrichment 注入（TMDB）
    if kb_prefix == "movie" and _should_enrich_by_entity_matching(
        query=state.get("query"),
        graphrag_context=combined_context,
        extracted_entities=route_decision.extracted_entities,
        query_intent=route_decision.query_intent,
        media_type_hint=route_decision.media_type_hint,
        filters=route_decision.filters,
    ):
        from infrastructure.enrichment import get_tmdb_enrichment_service

        svc = get_tmdb_enrichment_service()
        result = await svc.enrich_query(
            message=state.get("query"),
            extracted_entities=route_decision.extracted_entities,
            query_intent=route_decision.query_intent,
            media_type_hint=route_decision.media_type_hint,
            filters=route_decision.filters,
            ...
        )

        if result.success and result.transient_graph:
            enriched_context = result.transient_graph.to_context_text()
            combined_context = f"{combined_context}\n\n{enriched_context}"

    merged = MergedOutput(
        context=combined_context,
        retrieval_results=retrieval_results,
        ...
    )

    return {"merged": merged}
```

**关键点**：
- ✅ **Merge 节点承接**：enrichment 注入逻辑由 Merge 节点负责
- ✅ **逻辑一致**：与现有的 `_should_enrich_by_entity_matching()` 和 enrichment service 保持一致

#### 6. Debug 子步骤：Execute 节点的 ExecutionRecord.sub_steps

**现有代码**（chat_stream_executor.py）：
```python
# 发送带有 sub_steps 的执行日志
yield {
    "execution_log": {
        "node": "rag_retrieval_done",
        "node_type": "retrieval",
        "input": {"agent_type": run.agent_type},
        "output": {...},
        "sub_steps": run.execution_log,  # 三层嵌套
    }
}
```

**新架构**（Execute 节点）：
```python
# Execute 节点
async def _execute_plan_node(state: RetrievalState, config: RunnableConfig):
    debug = state.get("debug", False)
    plan = state.get("plan", [])

    records = []
    for step in plan:
        # 执行步骤
        result = await agent.retrieve_with_trace(step.tool_input)

        # 构建 ExecutionRecord
        record = ExecutionRecord(
            step_id=step.step_id,
            tool=step.tool,
            started_at=...,
            duration_ms=...,
            input_summary={...},
            output_summary={...},
            raw_input=step.tool_input,
            raw_output=result,
            status="success" if not result.get("error") else "failed",
            error=result.get("error"),
            sub_steps=result.get("execution_log", []) if debug else [],  # 三层嵌套
        )
        records.append(record)

    return {"records": records, "retrieval_results": all_results}
```

**关键点**：
- ✅ **Execute 节点承接**：debug 子步骤由 Execute 节点负责
- ✅ **三层嵌套保留**：subgraph → step → tool，与现有结构一致

#### 7. 进度更新：Execute 节点的 progress 事件

**现有代码**（chat_stream_executor.py）：
```python
# 发送 progress 事件
yield {
    "status": "progress",
    "content": {
        "stage": "retrieval",
        "agent_type": run.agent_type,
        "retrieval_count": len(run.retrieval_results),
        "completed": len(runs),
        "total": total_runs,
        "error": run.error,
    }
}
```

**新架构**（Execute 节点 + callback）：
```python
# Execute 节点
async def _execute_plan_node(state: RetrievalState, config: RunnableConfig):
    debug = state.get("debug", False)
    plan = state.get("plan", [])

    # 通过 callback 发出 progress 事件
    if debug and "callbacks" in config:
        for callback in config["callbacks"]:
            if hasattr(callback, "on_chain_start"):
                callback.on_chain_start(
                    name="execute_plan",
                    inputs={"total_steps": len(plan)}
                )

    records = []
    for idx, step in enumerate(plan):
        # 执行步骤
        result = await _execute_single_step(step, state)
        records.append(result)

        # 发出 progress 事件
        if debug and "callbacks" in config:
            for callback in config["callbacks"]:
                callback.on_chain_end(
                    name="retrieval_step",
                    outputs={
                        "step_id": step.step_id,
                        "completed": idx + 1,
                        "total": len(plan),
                        "retrieval_count": len(result.retrieval_results),
                    }
                )

    return {"records": records}
```

**关键点**：
- ✅ **Execute 节点承接**：progress 事件由 Execute 节点通过 callback 发出
- ✅ **格式一致**：与现有的 progress 事件格式保持一致

### 能力映射总览表

| 现有能力 | rag_manager | chat_stream_executor | 子图承接节点 | 状态 |
|---------|-------------|---------------------|------------|------|
| **单个 spec 检索** | ✅ | ❌ | Execute（`_execute_single_step()`） | ✅ 明确 |
| **Fanout 并行** | ✅ | ✅ | ❌ 不需要（Plan.depends_on 处理） | ✅ 明确 |
| **聚合去重** | ✅ | ❌ | Merge（`_merge_node()`） | ✅ 明确 |
| **Combined Context** | ✅ | ✅ | Merge（`_build_context_from_results()`） | ✅ 明确 |
| **Enrichment 注入** | ✅ | ✅ | Merge（调用 `tmdb_enrichment_service`） | ✅ 明确 |
| **取消传播** | ❌ | ✅ | Execute（asyncio.CancelledError 自动传播） | ✅ 明确 |
| **超时控制** | ✅ | ✅ | Execute（PlanStep.budget.timeout_s） | ✅ 明确 |
| **进度更新** | ❌ | ✅ | Execute（通过 callback 发出） | ✅ 明确 |
| **Debug 子步骤** | ❌ | ✅ | Execute（ExecutionRecord.sub_steps） | ✅ 明确 |
| **Combined Context 事件** | ❌ | ✅ | Merge（通过 callback 发出） | ✅ 明确 |
| **RAG Runs 事件** | ❌ | ✅ | Merge（通过 callback 发出） | ✅ 明确 |
| **Answer 流式生成** | ❌ | ✅ | ❌ 不承接（主图 generate 节点） | ✅ 明确 |

### 实现阶段的检查清单

**子图实现者必须确保**：
- [ ] Execute 节点实现 `_execute_single_step()`（对应 `run_retrieval_for_spec()`）
- [ ] Merge 节点实现聚合去重逻辑（对应 `aggregate_run_results()`）
- [ ] Merge 节点实现 combined context 构建（对应 `build_context_from_runs()`）
- [ ] Merge 节点实现 enrichment 注入（对应 `tmdb_enrichment_service`）
- [ ] Execute 节点的 ExecutionRecord 包含 sub_steps（对应 debug 子步骤）
- [ ] Execute 节点通过 callback 发出 progress 事件
- [ ] Merge 节点通过 callback 发出 combined_context/rag_runs 事件

**兼容保留（当前不会删除）**：
- `rag_manager.py`：仍作为子图的“检索执行器”（调用 GraphRAG agent）+ enrichment decision helpers
- `chat_stream_executor.py`：/chat/stream 主路径已由 LangGraph generate 接管；但 KB handler/兼容路径仍可能使用

---

## 子图边界与 I/O 契约

### 为什么需要明确的契约？

**没有契约会导致**：
- ❌ 主图以为子图返回 `combined_context`，但子图实际只返回 `context_parts`
- ❌ 子图想用 `history` 做 query 改写，但主图没传
- ❌ stream/debug 事件由谁发不清楚，导致前端时间线显示缺失或重复

**有了契约的好处**：
- ✅ 实现阶段接口一致，减少调试成本
- ✅ 流式/非流式行为一致，不会出现差异
- ✅ 前端可以稳定解析事件，不会因为字段缺失导致崩溃

### Input Contract（主图 → 子图）

**调用方式**：
```python
# 主图：first-class subgraph 作为一个 node 被 LangGraph 调用（无需显式 ainvoke）
#
# 流式时主图使用：graph.astream(state, stream_mode="custom", subgraphs=True)
# 注意：subgraphs=True 会产生 (ns, payload)，需要解包后只转发 payload（dict）。
#
# 单元测试/独立验证时，可以直接调用子图：
# out = await retrieval_subgraph_compiled.ainvoke({"query": "...", "kb_prefix": "...", ...})
```

**输入字段（RetrievalState）**：

| 字段 | 类型 | 必填/可选 | 说明 | 流式/非流式差异 |
|-----|------|----------|------|---------------|
| `query` | `str` | ✅ 必填 | 原始用户问题 | 无差异 |
| `kb_prefix` | `str` | ✅ 必填 | 知识库前缀（movie/edu/general） | 无差异 |
| `route_decision` | `RouteDecision` | ✅ 必填 | Router 输出（包含 query_intent, media_type_hint, filters, extracted_entities） | 无差异 |
| `debug` | `bool` | ✅ 必填 | 是否产出 debug 信息（records/execution_log） | 无差异 |
| `session_id` | `str` | ✅ 必填 | 会话 ID（用于缓存/追踪） | 无差异 |
| `user_id` | `str\|None` | ⚠️ 可选 | 用于 enrichment 持久化/观测 | 无差异 |
| `request_id` | `str\|None` | ⚠️ 可选 | 用于 debug/观测关联 | 无差异 |
| `conversation_id` | `Any\|None` | ⚠️ 可选 | 用于 enrichment 持久化 | 无差异 |
| `user_message_id` | `Any\|None` | ⚠️ 可选 | 用于 enrichment 持久化 | 无差异 |
| `incognito` | `bool` | ⚠️ 可选 | 隐私模式（禁写入） | 无差异 |
| `resolved_agent_type` | `str\|None` | ⚠️ 可选 | Router 推荐的 agent，Plan 节点可参考 | 无差异 |

**详细定义**：

```python
from typing import Any, Optional, TypedDict

from domain.chat.entities.route_decision import RouteDecision

# NOTE:
# - 预算以 PlanStep.budget(PlanBudget) 的形式存在（见 retrieval_subgraph.py）
# - 为了 first-class subgraph 可展开，主图会在 ConversationState 顶层填充这些 key

class RetrievalState(TypedDict, total=False):
    # ===== 输入 =====
    query: str
    kb_prefix: str
    route_decision: RouteDecision
    debug: bool
    session_id: str
    user_id: Optional[str]
    request_id: Optional[str]
    conversation_id: Any
    user_message_id: Any
    incognito: bool
    resolved_agent_type: Optional[str]

    # ===== 输出 =====
    plan: list[dict[str, Any]]
    records: list[dict[str, Any]]
    runs: list[dict[str, Any]]
    merged: dict[str, Any]
    reflection: Optional[dict[str, Any]]
    stop_reason: Optional[str]
```

### Output Contract（子图 → 主图）

**输出字段（RetrievalState）**：

| 字段 | 类型 | 必填/可选 | 说明 | debug=False 时 | debug=True 时 |
|-----|------|----------|------|--------------|-------------|
| `merged` | `MergedOutput` | ✅ 必填 | 融合后的检索结果 | ✅ 必须返回 | ✅ 必须返回 |
| `merged.context` | `str` | ✅ 必填 | 融合后的上下文文本（用于生成答案） | ✅ 必须返回 | ✅ 必须返回 |
| `merged.retrieval_results` | `List[RetrievalResult]` | ✅ 必填 | 检索结果列表（去重后） | ✅ 必须返回 | ✅ 必须返回 |
| `merged.reference` | `Dict[str, Any]` | ✅ 必填 | 引用信息（source_id、chunk_id 等） | ✅ 必须返回 | ✅ 必须返回 |
| `merged.statistics` | `Dict[str, Any]` | ❌ 可选 | 统计信息（tool_distribution, timings） | ❌ 可省略 | ✅ 建议返回 |
| `plan` | `List[PlanStep]` | ⚠️ debug 时必填 | 计划步骤（用于 debug 时间线） | ❌ 可省略或只存摘要 | ✅ 必须返回完整 |
| `records` | `List[ExecutionRecord]` | ⚠️ debug 时必填 | 执行记录（用于 debug 时间线） | ❌ 可省略 | ✅ 必须返回 |
| `reflection` | `Optional[Reflection]` | ❌ 可选 | 反思输出（用于 debug） | ❌ 可省略 | ✅ 建议返回 |
| `stop_reason` | `str` | ❌ 可选 | 停止原因（success/budget_exhausted/max_iterations_reached） | ❌ 可省略 | ✅ 建议返回 |

**详细定义**：

```python
@dataclass(frozen=True)
class MergedOutput:
    """子图最终输出（必填）"""
    context: str                              # 融合后的上下文文本（用于生成答案）
    retrieval_results: List[RetrievalResult]  # 检索结果列表（去重后）
    reference: Dict[str, Any]                 # 引用信息
    statistics: Optional[Dict[str, Any]] = None  # 统计信息（可选）

@dataclass(frozen=True)
class RetrievalResult:
    """单个检索结果"""
    score: float                              # 相关性分数
    granularity: str                          # 粒度（low_level/high_level/community）
    evidence: str                             # 证据文本
    metadata: Dict[str, Any]                  # 元数据（source_id, chunk_id, doc_id, title, url 等）

@dataclass(frozen=True)
class ExecutionRecord:
    """执行记录（debug 时必填）"""
    step_id: str                              # 对应 PlanStep.step_id
    tool: str                                 # 实际使用的工具
    started_at: str                           # ISO 8601 时间戳
    duration_ms: int                          # 耗时（毫秒）
    input_summary: Dict[str, Any]             # 输入摘要（用于 UI 展示）
    output_summary: Dict[str, Any]            # 输出摘要（用于 UI 展示）
    raw_input: Dict[str, Any]                 # 原始输入（用于 debug 子步骤展开）
    raw_output: Dict[str, Any]                # 原始输出
    status: Literal["success", "failed", "timeout", "partial"]
    error: Optional[str] = None               # 错误信息
    sub_steps: List[Dict[str, Any]] = None    # 子步骤（工具内部的执行记录）
```

**关键契约**：

1. **merged.context 必须返回**：主图需要这个字段来生成答案
   ```python
   # 主图 generate 节点：
   merged = state.get("merged") or {}
   context = merged.get("context", "")  # 必须有值
   answer = await asyncio.to_thread(generate_rag_answer, question=message, context=context, ...)
   ```

2. **merged.retrieval_results 必须返回**：主图需要这个字段来生成 reference
   ```python
   retrieval_results = merged.get("retrieval_results", [])  # 必须有值（可为空）
   reference = build_reference(retrieval_results)
   ```

3. **plan/records 在 debug=True 时必填**：用于前端时间线展示
   ```python
   if debug:
       plan = state.get("plan", [])
       records = state.get("records", [])
       # 发送给前端 DebugDrawer
   ```

4. **流式/非流式输出必须一致**：
   - `astream()` 的最终 merged 事件必须与 `ainvoke()` 的 merged 字段一致
   - 不能出现"ainvoke 返回 context，astream 返回 context_parts"的情况

### Event Contract（子图产生的事件）

**事件类型**：

| 事件类型 | status 字段 | content 字段 | 谁负责发送 | 谁负责缓存 | 前端如何使用 |
|---------|------------|-------------|----------|----------|------------|
| **子步骤展开** | `execution_log.sub_steps` | `[{node,...,sub_steps}]` | 子图 merge_node | ✅ DebugCollector | Timeline 里 rag_retrieval_done 展开 |
| **执行日志** | `execution_log` | `{node, node_type, duration_ms, input, output, sub_steps}` | 子图各节点（debug=True 时） | ✅ DebugCollector | DebugDrawer 原始 Tab |
| **进度更新** | `progress` | `{stage, completed, total, error}` | 子图 execute_plan_node | ❌ 不缓存 | 进度条 |

**关键契约**：

1. **事件冒泡是 LangGraph 负责的**：
   - 主图 `astream(..., stream_mode="custom", subgraphs=True)` 会拿到 `(ns, payload)`，对外只转发 `payload`
   - 子图内部继续用 `_get_stream_writer(config)` 写事件即可

2. **缓存-only 事件不发给前端**：
   - `execution_log`、`route_decision`、`rag_runs`、`combined_context` 是 cache-only（由 DebugCollector 分离）
   - `progress`、`token`、`done` 走 SSE

3. **merged 事件必须包含完整的 MergedOutput**：
   ```python
   # 子图 merge_node
   writer({
       "status": "retrieval_merged",
       "content": {
           "context": combined_context,           # 必填
           "retrieval_results": retrieval_results, # 必填
           "reference": reference,                 # 必填
           "statistics": statistics,               # 可选
       }
   })
   ```

4. **execution_log 必须包含 sub_steps**：
   ```python
   # 子图 execute_plan_node
   writer({
       "execution_log": {
           "node": "execute_plan",
           "node_type": "retrieval",
           "duration_ms": total_duration_ms,
           "input": {...},
           "output": {...},
           "sub_steps": [  # 三层嵌套：subgraph → step → tool
               {
                   "node": "step_0_candidates",
                   "node_type": "retrieval_step",
                   "tool": "hybrid_search",
                   "sub_steps": [  # 工具内部的执行记录
                       {"node": "hybrid_low_level_retrieval", ...},
                       {"node": "hybrid_high_level_retrieval", ...},
                   ]
               }
           ]
       }
   })
   ```

### 流式/非流式的一致性保证

**原则**：无论 `/chat` 还是 `/chat/stream`，最终都由子图写回同一个 `state.merged`（其中包含 `context/retrieval_results/reference`）。

**非流式 `/chat`**：
- 主图 `ainvoke` 完成后，`generate` 会从 `state.merged` 生成答案并返回 `response`

**流式 `/chat/stream`**：
- 主图 `astream(..., stream_mode="custom", subgraphs=True)` 时，子图事件会冒泡到 SSE（需要解包 tuple）
- `generate` 节点负责输出 token，并在结束时发 `done`
- debug 数据（`execution_log/combined_context/rag_runs`）由 DebugCollector 缓存，前端通过 `/api/v1/debug/{request_id}` 拉取

### 主图调用子图的标准流程

**主图拓扑（实际落地）**：
- `route → recall → prepare_retrieval → (conditional) retrieval_subgraph → generate`
- `prepare_retrieval` 后根据 `use_retrieval/use_kb_handler` 决定是否跳过子图直接进入 `generate`

### 实现阶段的检查清单

**子图实现者必须确保**：
- [ ] `merged.context` 必须返回（不能为空字符串）
- [ ] `merged.retrieval_results` 必须返回（可以为空列表）
- [ ] `merged.reference` 必须返回（可以为空字典）
- [ ] debug=True 时，`plan` 和 `records` 必须返回
- [ ] 流式和非流式的 `merged` 字段必须一致
- [ ] debug 细粒度观测通过 `execution_log`（并在 rag_retrieval_done.sub_steps 展开）

**主图调用者必须确保**：
- [ ] `prepare_retrieval` 填充子图必填字段（query/kb_prefix/route_decision/debug/session_id）
- [ ] 流式模式使用 `subgraphs=True` 并解包 `(ns, payload)`（只对外转发 payload）

---

## 设计原则

### 原则 1：强类型 State，不可变更新

- 每个节点返回新的 State，而不是修改原 State
- 增量追加：plan / records / retrieval_results 都是追加，不覆盖
- 所有字段都有明确的类型定义

### 原则 2：Plan 产出的结构化计划

**关键**：Plan 节点产出 `List[PlanStep]`，每个步骤包含：
- `step_id`：唯一标识
- `objective`：本步目标（如"拉候选集"、"补证据"）
- `tool`：工具名称（local/global/hybrid/naive/enrichment/discover）
- `tool_input`：结构化参数（query、keywords、filters、top_k、kb_prefix）
- `depends_on`：依赖的 step_id 列表（空列表=无依赖，可并行）
- `budget`：预算约束（timeout_s、top_k、max_evidence_count、max_retries）
- `priority`：优先级（数字越小优先级越高）

### 原则 3：Execute 按计划执行（串行/并行混合）

**关键**：Execute 节点根据 `depends_on` 关系决定执行方式：
- **并行执行**：depends_on 为空的步骤（可同时执行）
- **串行执行**：depends_on 不为空的步骤（等待依赖完成）

### 原则 4：Reflect 迭代闭环 + 预算约束

**关键**：Reflect 节点评估质量，决定是否继续：
- 质量信号：evidence_count、top_score、missing_fields、errors
- 追加步骤：补充检索、兜底检索、降级检索
- 改写 query：如果原始 query 效果不好
- **预算约束**：最多 N 轮、每步超时、总预算

### 原则 5：执行记录模型

**关键**：每个 step 都有完整的 ExecutionRecord：
- `input_summary`：输入摘要（用于 UI 展示）
- `output_summary`：输出摘要（用于 UI 展示）
- `raw_input`：原始输入（用于 debug）
- `raw_output`：原始输出（用于 debug）
- `sub_steps`：工具内部的执行记录（三层嵌套）

---

## State 定义（强类型）

### RetrievalState（子图状态）

```python
from typing import Optional, List, Dict, Any, Literal, TypedDict
from dataclasses import dataclass
from datetime import datetime

# ==================== PlanStep 定义 ====================

@dataclass(frozen=True)
class PlanBudget:
    """单步预算约束"""
    timeout_s: float = 15.0          # 超时时间
    top_k: int = 50                  # 最多返回多少条结果
    max_evidence_count: int = 100    # 最多证据数
    max_retries: int = 1             # 最多重试次数


@dataclass(frozen=True)
class PlanStep:
    """计划步骤（fusion 能力迁移的核心）"""
    step_id: str                      # 唯一标识（如 "step_0", "step_1"）
    objective: str                    # 本步目标（如"拉候选集"、"补证据"、"解析人物"）
    tool: str                         # 工具名称（local/global/hybrid/naive/enrichment/discover）
    tool_input: Dict[str, Any]        # 工具参数（query、keywords、filters、top_k、kb_prefix）
    depends_on: Optional[List[str]]   # 依赖的 step_id（空列表=无依赖，可并行）
    budget: PlanBudget                # 预算约束（关键！）
    priority: int = 1                 # 优先级（1 最高，数字越小优先级越高）


# ==================== ExecutionRecord 定义 ====================

@dataclass(frozen=True)
class ExecutionRecord:
    """执行记录（用于时间线可视化）"""
    step_id: str                      # 对应 PlanStep.step_id
    tool: str                         # 实际使用的工具
    started_at: str                   # ISO 8601 时间戳
    duration_ms: int                  # 耗时（毫秒）

    # 输入/输出摘要（用于 UI 展示）
    input_summary: Dict[str, Any]     # 输入摘要
    output_summary: Dict[str, Any]    # 输出摘要

    # 原始输入/输出（用于 debug 子步骤展开）
    raw_input: Dict[str, Any]         # 原始输入
    raw_output: Dict[str, Any]        # 原始输出

    # 执行状态
    status: Literal["success", "failed", "timeout", "partial"]
    error: Optional[str] = None       # 错误信息（如果有）

    # 子步骤（工具内部的执行记录，三层嵌套）
    sub_steps: List[Dict[str, Any]] = None  # tool 内部的 _log_step


# ==================== RetrievalResult 定义 ====================

class RetrievalResult(TypedDict, total=False):
    """统一的检索结果格式"""
    source_id: str                    # 来源 ID（chunk_id / entity_id / relationship_id）
    source_type: str                  # 来源类型（chunk / entity / relationship）
    granularity: str                  # 粒度（low / high）
    score: float                      # 相关性分数
    evidence: str                     # 证据文本
    metadata: Dict[str, Any]          # 元数据


# ==================== Reflection 定义 ====================

@dataclass(frozen=True)
class Reflection:
    """反思输出（迭代闭环的关键）"""
    should_continue: bool             # 是否继续迭代
    next_steps: List[PlanStep]        # 追加的步骤（如果需要补检索）
    rewrite_query: Optional[str] = None  # 改写的 query（如果需要）
    stop_reason: Optional[str] = None    # 停止原因
    reasoning: str = ""               # 推理原因（用于 debug）

    # 预算约束（关键！）
    current_iteration: int = 0        # 当前迭代轮数
    max_iterations: int = 3           # 最多迭代轮数
    remaining_budget: float = 30.0    # 剩余预算（秒）


# ==================== RetrievalState 定义 ====================

class RetrievalState(TypedDict, total=False):
    """Multi-Agent 子图的完整状态"""

    # ===== 输入（只读，不变） =====
    query: str                        # 原始用户问题
    route_decision: Dict[str, Any]   # router 输出
    session_id: str                   # 会话 ID（用于追踪）
    kb_prefix: str                    # 知识库前缀

    # ===== Plan 阶段输出（追加，不变） =====
    plan: List[PlanStep]              # 结构化计划（关键！）
    plan_metadata: Dict[str, Any]     # 计划元数据（生成时间、LLM 输入等）

    # ===== Execute 阶段输出（追加，不变） =====
    records: List[ExecutionRecord]    # 执行记录（每步一条，用于时间线）
    retrieval_results: List[RetrievalResult]  # 统一格式的结果列表
    context_parts: List[str]          # 每步生成的 context chunk

    # ===== Reflect 阶段输出（可选） =====
    reflection: Optional[Reflection]  # 反思输出（迭代闭环）

    # ===== Merge 阶段输出（最终产物） =====
    merged: Optional[Dict[str, Any]]  # {
                                       #   "context": str,
                                       #   "retrieval_results": List[RetrievalResult],
                                       #   "reference": Dict[str, Any],
                                       #   "statistics": Dict[str, Any]
                                       # }

    # ===== 控制字段 =====
    current_step_index: int           # 当前执行到第几步
    stop_reason: Optional[str]        # 停止原因
```

### State 更新规则

```python
# ❌ 错误：直接修改 state（隐式 side-effect）
state["plan"].append(new_step)  # 禁止

# ✅ 正确：返回新的 state（不可变更新）
return {
    **state,
    "plan": state["plan"] + [new_step]  # 追加
}

# ✅ 正确：多个字段同时更新
return {
    **state,
    "records": state["records"] + [new_record],
    "retrieval_results": state["retrieval_results"] + new_results,
    "current_step_index": state["current_step_index"] + 1,
}
```

---

## Plan 节点：结构化计划生成

### 核心职责

**Plan 节点的核心职责**：根据 `route_decision` 生成 `List[PlanStep]`，每个步骤包含：
- **objective**：本步目标（不是简单的 single/multi 分支！）
- **tool**：工具名称
- **tool_input**：结构化参数
- **depends_on**：依赖关系（决定串行/并行）
- **budget**：预算约束（决定何时停止）

### 关键区别

| 对比项 | ❌ 错误理解（固定并行） | ✅ 正确理解（Plan 产出的结构化计划） |
|-------|---------------------|--------------------------------|
| **Plan 输出** | `strategy = "single" \| "multi"` | `List[PlanStep]`，每步有 objective、tool、depends_on、budget |
| **执行方式** | 固定 4 路并行 | 按 depends_on 关系，串行/并行混合 |
| **预算约束** | 无 | 每个 step 有独立的 budget（timeout、top_k） |

### 实现逻辑

```python
def plan_node(state: RetrievalState) -> RetrievalState:
    """
    Plan 节点：根据 route_decision 生成结构化计划

    核心产出：List[PlanStep]
    """
    query = state["query"]
    route_decision = state["route_decision"]
    query_intent = route_decision.get("query_intent", "unknown")
    extracted_entities = route_decision.get("extracted_entities", {})
    filters = route_decision.get("filters", {})
    kb_prefix = state.get("kb_prefix", "movie")

    plan = []
    plan_metadata = {
        "generated_at": datetime.now().isoformat(),
        "planner_type": "deterministic",  # 或 "llm"
        "route_decision": route_decision
    }

    # ========== 场景 1：QA + 实体明确 → 单步 + 可选 fallback ==========
    if query_intent == "qa" and extracted_entities.get("low_level"):
        entity_name = extracted_entities["low_level"][0]

        # 主路：hybrid_search（低层 + 高层）
        plan.append(PlanStep(
            step_id="step_0_primary",
            objective=f"查询 {entity_name} 的详细信息",
            tool="hybrid_search",
            tool_input={
                "query": query,
                "kb_prefix": kb_prefix,
                "top_k": 50,
            },
            depends_on=[],  # 无依赖，可先行执行
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ))

        # 可选：fallback（依赖主路结果，Reflect 会决定是否执行）
        plan.append(PlanStep(
            step_id="step_1_fallback",
            objective="兜底检索（如果主路结果不足）",
            tool="naive_search",
            tool_input={
                "query": query,
                "kb_prefix": kb_prefix,
                "top_k": 30,
            },
            depends_on=["step_0_primary"],  # 依赖主路（串行）
            budget=PlanBudget(timeout_s=10.0, top_k=30),
            priority=2  # 低优先级
        ))

    # ========== 场景 2：Recommend/Compare/List → 多步（串行依赖） ==========
    elif query_intent in ("recommend", "compare", "list"):
        # 第一步：拉候选集合
        if filters:
            # 有 filters：用 enrichment discover
            plan.append(PlanStep(
                step_id="step_0_discover",
                objective="根据筛选条件拉候选集合",
                tool="discover",
                tool_input={
                    "query": query,
                    "kb_prefix": kb_prefix,
                    "filters": filters,
                    "top_k": 50,
                },
                depends_on=[],
                budget=PlanBudget(timeout_s=20.0, top_k=50)
            ))
        else:
            # 无 filters：用 hybrid 拉候选
            plan.append(PlanStep(
                step_id="step_0_candidates",
                objective="拉取候选集合",
                tool="hybrid_search",
                tool_input={
                    "query": query,
                    "kb_prefix": kb_prefix,
                    "top_k": 50,
                },
                depends_on=[],
                budget=PlanBudget(timeout_s=15.0, top_k=50)
            ))

        # 第二步：补证据（依赖第一步，串行）
        first_step_id = "step_0_discover" if filters else "step_0_candidates"
        plan.append(PlanStep(
            step_id="step_1_evidence",
            objective="补充候选作品的详细信息（导演、年份、获奖等）",
            tool="global_search",
            tool_input={
                "query": query,  # TODO: 从 step_0 的结果中提取候选
                "kb_prefix": kb_prefix,
                "top_k": 30,
            },
            depends_on=[first_step_id],  # 依赖第一步（串行）
            budget=PlanBudget(timeout_s=15.0, top_k=30)
        ))

    # ========== 场景 3：Person 类 → 先 resolve，再作品列表（串行依赖） ==========
    elif route_decision.get("media_type_hint") == "person":
        person_name = extracted_entities.get("low_level", [""])[0]

        # 第一步：解析人物
        plan.append(PlanStep(
            step_id="step_0_resolve",
            objective=f"解析人物 {person_name}（实体识别）",
            tool="local_search",
            tool_input={
                "query": f"{person_name} 是谁？",
                "kb_prefix": kb_prefix,
                "top_k": 20,
            },
            depends_on=[],
            budget=PlanBudget(timeout_s=10.0, top_k=20)
        ))

        # 第二步：作品列表（依赖第一步，串行）
        plan.append(PlanStep(
            step_id="step_1_works",
            objective=f"获取 {person_name} 的作品列表",
            tool="hybrid_search",
            tool_input={
                "query": f"{person_name} 导演/主演的作品",
                "kb_prefix": kb_prefix,
                "top_k": 50,
            },
            depends_on=["step_0_resolve"],  # 依赖第一步（串行）
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ))

    # ========== 默认：单步 hybrid ==========
    else:
        plan.append(PlanStep(
            step_id="step_0_default",
            objective="检索相关信息",
            tool="hybrid_search",
            tool_input={
                "query": query,
                "kb_prefix": kb_prefix,
                "top_k": 50,
            },
            depends_on=[],
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ))

    # 返回新 state（追加 plan）
    return {
        **state,
        "plan": plan,
        "plan_metadata": plan_metadata,
    }
```

### Plan 输出示例

```python
# 示例 1：QA 查询
{
    "plan": [
        PlanStep(
            step_id="step_0_primary",
            objective="查询 喜宴 的详细信息",
            tool="hybrid_search",
            tool_input={"query": "喜宴哪一年上映？", "kb_prefix": "movie", "top_k": 50},
            depends_on=[],  # 可并行
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ),
        PlanStep(
            step_id="step_1_fallback",
            objective="兜底检索（如果主路结果不足）",
            tool="naive_search",
            tool_input={"query": "喜宴哪一年上映？", "kb_prefix": "movie", "top_k": 30},
            depends_on=["step_0_primary"],  # 依赖主路（串行）
            budget=PlanBudget(timeout_s=10.0, top_k=30),
            priority=2
        )
    ]
}

# 示例 2：Recommend 查询（多步串行）
{
    "plan": [
        PlanStep(
            step_id="step_0_candidates",
            objective="拉取候选集合",
            tool="hybrid_search",
            tool_input={"query": "推荐几部类似《喜宴》的电影", "kb_prefix": "movie", "top_k": 50},
            depends_on=[],  # 无依赖，可先行执行
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ),
        PlanStep(
            step_id="step_1_evidence",
            objective="补充候选作品的详细信息",
            tool="global_search",
            tool_input={"query": "...", "kb_prefix": "movie", "top_k": 30},
            depends_on=["step_0_candidates"],  # 依赖第一步（串行）
            budget=PlanBudget(timeout_s=15.0, top_k=30)
        )
    ]
}
```

---

## Execute 节点：按计划执行（串行/并行混合）

### 核心职责

**Execute 节点的核心职责**：
1. 根据 `PlanStep[]` 的 `depends_on` 关系，决定执行方式
2. **并行执行**：depends_on 为空的步骤（可同时执行）
3. **串行执行**：depends_on 不为空的步骤（等待依赖完成）
4. 记录 `ExecutionRecord`（每个 step 一条）

### 关键区别

| 对比项 | ❌ 错误理解（固定并行） | ✅ 正确理解（按计划执行） |
|-------|---------------------|------------------------|
| **执行方式** | 固定 4 路并行（local/global/hybrid/naive） | 按 depends_on 关系，串行/并行混合 |
| **执行记录** | 仅在 rag_retrieval_done 下塞 tool log | 每个 step 都有 ExecutionRecord |
| **依赖管理** | 无 | 检查 depends_on 是否满足 |

### 实现逻辑

```python
import asyncio
from typing import List, Dict, Any

async def execute_plan_node(state: RetrievalState) -> RetrievalState:
    """
    Execute 节点：按计划执行（串行/并行混合）

    核心逻辑：
    1. 并行执行：depends_on 为空的步骤
    2. 串行执行：depends_on 不为空的步骤（等待依赖完成）
    3. 记录 ExecutionRecord（每个 step 一条）
    """
    plan = state["plan"]
    current_index = state.get("current_step_index", 0)
    records = state.get("records", [])
    retrieval_results = state.get("retrieval_results", [])
    context_parts = state.get("context_parts", [])

    # 如果已经执行完所有步骤，直接返回
    if current_index >= len(plan):
        return state

    # ========== 第一步：分组（并行 vs 串行） ==========
    pending_steps = plan[current_index:]

    # 并行组：无依赖的步骤
    parallel_steps = [step for step in pending_steps if not step.depends_on]

    # 串行组：有依赖的步骤（按优先级排序）
    serial_steps = sorted(
        [step for step in pending_steps if step.depends_on],
        key=lambda s: s.priority
    )

    # ========== 第二步：并行执行无依赖的步骤 ==========
    new_records = []
    new_results = []
    new_context_parts = []

    if parallel_steps:
        # 并行执行（asyncio.gather）
        parallel_results = await asyncio.gather(
            *[_execute_single_step(step, state) for step in parallel_steps],
            return_exceptions=True
        )

        for step, result in zip(parallel_steps, parallel_results):
            if isinstance(result, Exception):
                # 记录错误
                record = ExecutionRecord(
                    step_id=step.step_id,
                    tool=step.tool,
                    started_at=datetime.now().isoformat(),
                    duration_ms=0,
                    input_summary={"tool": step.tool, "input": step.tool_input},
                    output_summary={},
                    raw_input=step.tool_input,
                    raw_output={},
                    status="failed",
                    error=str(result)
                )
            else:
                record, step_results, step_context = result
                new_records.append(record)
                new_results.extend(step_results)
                if step_context:
                    new_context_parts.append(step_context)

    # ========== 第三步：串行执行有依赖的步骤 ==========
    for step in serial_steps:
        # 检查依赖是否满足
        if not _check_dependencies(step, records + new_records):
            continue  # 依赖未满足，跳过（下一轮再执行）

        try:
            record, step_results, step_context = await _execute_single_step(step, state)
            new_records.append(record)
            new_results.extend(step_results)
            if step_context:
                new_context_parts.append(step_context)
        except Exception as e:
            # 记录错误，继续执行下一步
            record = ExecutionRecord(
                step_id=step.step_id,
                tool=step.tool,
                started_at=datetime.now().isoformat(),
                duration_ms=0,
                input_summary={"tool": step.tool, "input": step.tool_input},
                output_summary={},
                raw_input=step.tool_input,
                raw_output={},
                status="failed",
                error=str(e)
            )
            new_records.append(record)

    # ========== 第四步：更新 state ==========
    return {
        **state,
        "records": records + new_records,
        "retrieval_results": retrieval_results + new_results,
        "context_parts": context_parts + new_context_parts,
        "current_step_index": current_index + len(parallel_steps) + len(serial_steps),
    }


async def _execute_single_step(
    step: PlanStep,
    state: RetrievalState
) -> tuple[ExecutionRecord, List[RetrievalResult], str]:
    """
    执行单个步骤

    Returns:
        (ExecutionRecord, List[RetrievalResult], context)
    """
    from graphrag_agent.search.tool_registry import TOOL_REGISTRY

    # 1. 获取工具实例
    tool_factory = TOOL_REGISTRY.get(step.tool)
    if not tool_factory:
        raise ValueError(f"Unknown tool: {step.tool}")

    tool = tool_factory(kb_prefix=state["kb_prefix"])

    # 2. 执行工具（带超时）
    started_at = datetime.now()
    try:
        result = await asyncio.wait_for(
            _invoke_tool(tool, step.tool_input),
            timeout=step.budget.timeout_s
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"Tool {step.tool} timeout after {step.budget.timeout_s}s")

    duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)

    # 3. 提取结果
    retrieval_results = result.get("retrieval_results", [])
    context = result.get("context", "")

    # 限制数量（budget 约束）
    retrieval_results = retrieval_results[:step.budget.top_k]

    # 4. 提取子步骤（如果工具支持）
    sub_steps = []
    if hasattr(tool, "execution_log"):
        sub_steps = list(tool.execution_log or [])

    # 5. 构建 ExecutionRecord（关键！用于时间线可视化）
    record = ExecutionRecord(
        step_id=step.step_id,
        tool=step.tool,
        started_at=started_at.isoformat(),
        duration_ms=duration_ms,
        input_summary={
            "tool": step.tool,
            "objective": step.objective,
            "input_keys": list(step.tool_input.keys())
        },
        output_summary={
            "evidence_count": len(retrieval_results),
            "context_length": len(context),
            "top_score": _get_top_score(retrieval_results)
        },
        raw_input=step.tool_input,
        raw_output=result,
        status="success",
        sub_steps=sub_steps  # 三层嵌套：子图 → step → tool 内部
    )

    return record, retrieval_results, context


def _check_dependencies(step: PlanStep, records: List[ExecutionRecord]) -> bool:
    """
    检查依赖是否满足
    """
    if not step.depends_on:
        return True

    completed_step_ids = {r.step_id for r in records if r.status == "success"}
    return all(dep_id in completed_step_ids for dep_id in step.depends_on)


def _get_top_score(retrieval_results: List[RetrievalResult]) -> float:
    """获取最高分"""
    if not retrieval_results:
        return 0.0
    return max(r.get("score", 0.0) for r in retrieval_results)
```

### Execute 输出示例

```python
{
    "records": [
        ExecutionRecord(
            step_id="step_0_candidates",
            tool="hybrid_search",
            started_at="2026-01-26T10:00:01Z",
            duration_ms=1234,
            input_summary={
                "tool": "hybrid_search",
                "objective": "拉取候选集合",
                "input_keys": ["query", "kb_prefix", "top_k"]
            },
            output_summary={
                "evidence_count": 50,
                "context_length": 8234,
                "top_score": 0.85
            },
            raw_input={...},
            raw_output={...},
            status="success",
            sub_steps=[  # 三层嵌套：子图 → step → tool 内部
                {
                    "node": "hybrid_low_level_retrieval",
                    "node_type": "retrieval",
                    "duration_ms": 800,
                    "input": {...},
                    "output": {"evidence_count": 30}
                },
                {
                    "node": "hybrid_high_level_retrieval",
                    "node_type": "retrieval",
                    "duration_ms": 400,
                    "input": {...},
                    "output": {"evidence_count": 20}
                }
            ]
        )
    ],
    "retrieval_results": [...],  # 追加新结果
    "context_parts": [...],      # 追加新 context
    "current_step_index": 1       # 已执行 1 步（还有 step_1_evidence 待执行）
}
```

---

## Reflect 节点：迭代闭环与预算约束

### 核心职责

**Reflect 节点的核心职责**：
1. **评估质量**：根据 retrieval_results / records 判断是否满足要求
2. **追加步骤**：如果质量不足，追加 PlanStep（补充检索、兜底检索、降级检索）
3. **改写 query**：如果原始 query 效果不好，生成新的 query
4. **预算约束**：最多 N 轮、每步超时、总预算

### 关键区别

| 对比项 | ❌ 错误理解（简单阈值） | ✅ 正确理解（迭代闭环） |
|-------|---------------------|------------------------|
| **评估信号** | 仅 evidence_count / top_score | evidence_count + top_score + missing_fields + errors |
| **追加步骤** | 无（或固定的 naive fallback） | 根据缺失内容动态生成 PlanStep |
| **改写 query** | 无 | 支持改写 query（如果原始 query 效果不好） |
| **预算约束** | 无 | max_iterations、remaining_budget |

### 实现逻辑

```python
def reflect_node(state: RetrievalState) -> RetrievalState:
    """
    Reflect 节点：质量评估 + 迭代决策

    核心产出：Reflection（should_continue、next_steps、rewrite_query、stop_reason）
    """
    retrieval_results = state.get("retrieval_results", [])
    records = state.get("records", [])
    route_decision = state["route_decision"]
    query_intent = route_decision.get("query_intent", "unknown")

    # ========== 第一步：评估质量 ==========
    evidence_count = len(retrieval_results)
    top_score = _get_top_score(retrieval_results)

    # 检查关键字段（根据 query_intent）
    missing_fields = _check_missing_fields(retrieval_results, query_intent)

    # 检查错误
    has_timeout = any(r.status == "timeout" for r in records)
    has_failure = any(r.status == "failed" for r in records)

    # ========== 第二步：判断是否需要补检索 ==========
    should_continue = False
    next_steps = []
    rewrite_query = None
    stop_reason = None
    reasoning = []

    # 规则 1：证据数量不足
    min_evidence_count = _get_min_evidence_count(query_intent)
    if evidence_count < min_evidence_count:
        should_continue = True
        reasoning.append(f"证据数量不足 ({evidence_count} < {min_evidence_count})")

        # 追加 naive fallback（如果没有执行过）
        if not any(r.tool == "naive_search" for r in records):
            next_steps.append(PlanStep(
                step_id=f"step_fallback_{len(records)}",
                objective="兜底检索（纯向量）",
                tool="naive_search",
                tool_input={
                    "query": state["query"],
                    "kb_prefix": state["kb_prefix"],
                    "top_k": 30,
                },
                depends_on=[],  # 可并行（无依赖）
                budget=PlanBudget(timeout_s=10.0, top_k=30)
            ))

    # 规则 2：最高分过低
    min_top_score = _get_min_top_score(query_intent)
    if top_score < min_top_score:
        should_continue = True
        reasoning.append(f"最高分过低 ({top_score:.2f} < {min_top_score})")

        # 改写 query（提高质量）
        if not rewrite_query:
            rewrite_query = _rewrite_query_for_quality(
                state["query"],
                retrieval_results,
                missing_fields
            )

    # 规则 3：缺少关键字段（如导演、年份、国家）
    if missing_fields:
        should_continue = True
        reasoning.append(f"缺少关键字段: {', '.join(missing_fields)}")

        # 补充检索（针对缺失字段）
        next_steps.append(PlanStep(
            step_id=f"step_supplement_{len(records)}",
            objective=f"补充缺失字段: {', '.join(missing_fields)}",
            tool="local_search",
            tool_input={
                "query": _build_supplement_query(state["query"], missing_fields),
                "kb_prefix": state["kb_prefix"],
                "top_k": 20,
            },
            depends_on=[],  # 可并行（无依赖）
            budget=PlanBudget(timeout_s=10.0, top_k=20)
        ))

    # 规则 4：发生错误（超时、失败）
    if has_timeout or has_failure:
        should_continue = True
        reasoning.append("发生错误，尝试降级检索")

        # 降级到 naive（如果没有执行过）
        if not any(r.tool == "naive_search" for r in records):
            next_steps.append(PlanStep(
                step_id=f"step_degraded_{len(records)}",
                objective="降级检索（兜底）",
                tool="naive_search",
                tool_input={
                    "query": state["query"],
                    "kb_prefix": state["kb_prefix"],
                    "top_k": 30,
                },
                depends_on=[],
                budget=PlanBudget(timeout_s=10.0, top_k=30)
            ))

    # ========== 第三步：预算约束（关键！） ==========
    max_iterations = 3
    current_iteration = len(state.get("plan", []))

    # 计算剩余预算
    total_duration_ms = sum(r.duration_ms for r in records)
    remaining_budget_s = 30.0 - (total_duration_ms / 1000.0)

    if current_iteration >= max_iterations:
        should_continue = False
        stop_reason = "max_iterations_reached"
        reasoning.append(f"已达到最大迭代次数 ({max_iterations})")
    elif remaining_budget_s <= 0:
        should_continue = False
        stop_reason = "budget_exhausted"
        reasoning.append(f"预算已耗尽（剩余 {remaining_budget_s:.2f}s）")

    # 如果不需要继续
    if not should_continue and not stop_reason:
        stop_reason = "quality_satisfied"
        reasoning.append("检索质量满足要求")

    # ========== 第四步：构建反思输出 ==========
    reflection = Reflection(
        should_continue=should_continue,
        next_steps=next_steps,
        rewrite_query=rewrite_query,
        stop_reason=stop_reason,
        reasoning="；".join(reasoning),
        current_iteration=current_iteration,
        max_iterations=max_iterations,
        remaining_budget=remaining_budget_s
    )

    return {
        **state,
        "reflection": reflection,
    }


def _get_min_evidence_count(query_intent: str) -> int:
    """根据 query_intent 返回最少证据数量"""
    thresholds = {
        "qa": 5,
        "recommend": 10,
        "compare": 8,
        "list": 15,
        "unknown": 5
    }
    return thresholds.get(query_intent, 5)


def _get_min_top_score(query_intent: str) -> float:
    """根据 query_intent 返回最低 top score"""
    thresholds = {
        "qa": 0.4,
        "recommend": 0.6,
        "compare": 0.5,
        "list": 0.7,
        "unknown": 0.5
    }
    return thresholds.get(query_intent, 0.5)


def _check_missing_fields(retrieval_results: List[RetrievalResult], query_intent: str) -> List[str]:
    """
    检查缺失的关键字段

    TODO: 实现
    """
    # 1. 从 retrieval_results 中提取元数据
    # 2. 根据 query_intent 判断缺少哪些字段
    # 3. 返回缺失字段列表
    return []


def _rewrite_query_for_quality(
    original_query: str,
    retrieval_results: List[RetrievalResult],
    missing_fields: List[str]
) -> str:
    """
    改写 query 以提升质量

    TODO: 实现 LLM 改写
    """
    # 可以使用 LLM 改写，或使用规则改写
    return original_query


def _build_supplement_query(query: str, missing_fields: List[str]) -> str:
    """
    构建补充检索的 query
    """
    # TODO: 实现
    return query
```

### Reflect 输出示例

```python
# 示例 1：质量满足，停止迭代
{
    "reflection": Reflection(
        should_continue=False,
        next_steps=[],
        rewrite_query=None,
        stop_reason="quality_satisfied",
        reasoning="检索质量满足要求",
        current_iteration=2,
        max_iterations=3,
        remaining_budget=25.5
    )
}

# 示例 2：质量不足，追加步骤
{
    "reflection": Reflection(
        should_continue=True,
        next_steps=[
            PlanStep(
                step_id="step_fallback_2",
                objective="兜底检索（纯向量）",
                tool="naive_search",
                tool_input={"query": "...", "kb_prefix": "movie", "top_k": 30},
                depends_on=[],
                budget=PlanBudget(timeout_s=10.0, top_k=30)
            )
        ],
        rewrite_query=None,
        stop_reason=None,
        reasoning="证据数量不足 (3 < 10)；最高分过低 (0.35 < 0.6)",
        current_iteration=2,
        max_iterations=3,
        remaining_budget=15.2
    )
}
```

---

## Merge 节点：去重融合与产物整理

### 核心职责

**Merge 节点的核心职责**：
1. **去重**：按 (source_id, granularity) 保留最高分
2. **排序**：按 score 降序
3. **截断**：限制数量（max_results）和长度（max_context_chars）
4. **构建引用**：chunks / entities / relationships
5. **统计信息**：total_steps、total_duration_ms、tool_distribution、success_rate

### 实现逻辑

```python
def merge_node(state: RetrievalState) -> RetrievalState:
    """
    Merge 节点：去重、排序、截断、构建最终产物
    """
    retrieval_results = state.get("retrieval_results", [])
    context_parts = state.get("context_parts", [])
    records = state.get("records", [])

    # ========== 1. 去重：按 (source_id, granularity) 保留最高分 ==========
    merged = {}
    for item in retrieval_results:
        source_id = item.get("source_id")
        granularity = item.get("granularity")

        if not source_id or not granularity:
            continue

        key = (source_id, granularity)
        score = item.get("score", 0.0)

        if key not in merged or score > merged[key].get("score", 0.0):
            merged[key] = item

    # ========== 2. 排序：按 score 降序 ==========
    retrieval_results = sorted(
        merged.values(),
        key=lambda x: x.get("score", 0.0),
        reverse=True
    )

    # ========== 3. 截断：限制数量和长度 ==========
    max_results = 50
    retrieval_results = retrieval_results[:max_results]

    # 构建上下文
    context_parts = []
    for item in retrieval_results:
        evidence = item.get("evidence")
        if isinstance(evidence, str) and evidence.strip():
            context_parts.append(evidence.strip())

    context = "\n\n---\n\n".join(context_parts)

    # 限制长度（避免 context 过长）
    max_context_chars = 10000
    if len(context) > max_context_chars:
        context = context[:max_context_chars] + "\n\n...(已截断)"

    # ========== 4. 构建引用 ==========
    reference = _build_reference(retrieval_results)

    # ========== 5. 统计信息 ==========
    statistics = {
        "total_evidence_count": len(retrieval_results),
        "context_length": len(context),
        "total_steps": len(records),
        "total_duration_ms": sum(r.duration_ms for r in records),
        "tool_distribution": _get_tool_distribution(records),
        "success_rate": _get_success_rate(records),
    }

    # ========== 6. 最终产物 ==========
    merged_result = {
        "context": context,
        "retrieval_results": retrieval_results,
        "reference": reference,
        "statistics": statistics,
    }

    return {
        **state,
        "merged": merged_result,
        "stop_reason": state.get("reflection", {}).get("stop_reason", "completed"),
    }


def _build_reference(retrieval_results: List[RetrievalResult]) -> Dict[str, Any]:
    """构建引用信息"""
    chunks = set()
    entities = set()
    relationships = set()

    for item in retrieval_results:
        source_type = item.get("source_type")
        source_id = item.get("source_id")

        if not source_type or not source_id:
            continue

        if source_type == "chunk":
            chunks.add(source_id)
        elif source_type == "entity":
            entities.add(source_id)
        elif source_type == "relationship":
            relationships.add(source_id)

    return {
        "chunks": [{"chunk_id": cid} for cid in sorted(chunks)],
        "entities": [{"id": eid} for eid in sorted(entities)],
        "relationships": [{"id": rid} for rid in sorted(relationships)],
    }


def _get_tool_distribution(records: List[ExecutionRecord]) -> Dict[str, int]:
    """统计工具使用分布"""
    distribution = {}
    for record in records:
        tool = record.tool
        distribution[tool] = distribution.get(tool, 0) + 1
    return distribution


def _get_success_rate(records: List[ExecutionRecord]) -> float:
    """计算成功率"""
    if not records:
        return 1.0

    success_count = sum(1 for r in records if r.status == "success")
    return success_count / len(records)
```

---

## 执行记录模型与时间线

### 三层嵌套结构

```
retrieval_subgraph (子图)
├─ plan 节点
├─ execute_plan 节点
│  ├─ step_0: hybrid_search
│  │  ├─ hybrid_low_level_retrieval (工具内部)
│  │  └─ hybrid_high_level_retrieval (工具内部)
│  └─ step_1: global_search
│     └─ global_search_community_retrieval (工具内部)
├─ reflect 节点
└─ merge 节点
```

### execution_log 格式

```python
# 高层节点（主图）
{
    "node": "retrieval_subgraph",
    "node_type": "subgraph",
    "duration_ms": 3500,
    "timestamp": "2026-01-26T10:00:00Z",
    "input": {
        "query": "推荐几部类似《喜宴》的电影",
        "kb_prefix": "movie"
    },
    "output": {
        "merged": {
            "statistics": {
                "total_steps": 2,
                "total_evidence_count": 50
            }
        }
    },
    "sub_steps": [
        # 子节点（子图）
        {
            "node": "plan",
            "node_type": "planning",
            "duration_ms": 5,
            "timestamp": "2026-01-26T10:00:00Z",
            "input": {...},
            "output": {
                "plan": [
                    {"step_id": "step_0_candidates", "objective": "拉取候选集合", ...},
                    {"step_id": "step_1_evidence", "objective": "补充候选作品的详细信息", ...}
                ]
            }
        },
        {
            "node": "execute_plan",
            "node_type": "execution",
            "duration_ms": 2500,
            "timestamp": "2026-01-26T10:00:01Z",
            "input": {...},
            "output": {
                "records": [
                    {
                        "step_id": "step_0_candidates",
                        "tool": "hybrid_search",
                        "input_summary": {...},
                        "output_summary": {"evidence_count": 50}
                    }
                ]
            },
            "sub_steps": [
                # ExecutionRecord 的 sub_steps（三层嵌套）
                {
                    "node": "step_0_candidates",
                    "node_type": "step_execution",
                    "duration_ms": 1234,
                    "input_summary": {
                        "tool": "hybrid_search",
                        "objective": "拉取候选集合"
                    },
                    "output_summary": {"evidence_count": 50},
                    "sub_steps": [
                        # 工具内部的执行记录
                        {
                            "node": "hybrid_low_level_retrieval",
                            "node_type": "retrieval",
                            "duration_ms": 800,
                            "input": {"query": "..."},
                            "output": {"evidence_count": 30}
                        },
                        {
                            "node": "hybrid_high_level_retrieval",
                            "node_type": "retrieval",
                            "duration_ms": 400,
                            "input": {"query": "..."},
                            "output": {"evidence_count": 20}
                        }
                    ]
                },
                {
                    "node": "step_1_evidence",
                    "node_type": "step_execution",
                    "duration_ms": 1111,
                    "input_summary": {
                        "tool": "global_search",
                        "objective": "补充候选作品的详细信息"
                    },
                    "output_summary": {"evidence_count": 15},
                    "sub_steps": [
                        {
                            "node": "global_search_community_retrieval",
                            "node_type": "retrieval",
                            "duration_ms": 1100,
                            "input": {"query": "..."},
                            "output": {"evidence_count": 15}
                        }
                    ]
                }
            ]
        },
        {
            "node": "reflect",
            "node_type": "reflection",
            "duration_ms": 10,
            "timestamp": "2026-01-26T10:00:03Z",
            "input": {...},
            "output": {
                "should_continue": False,
                "stop_reason": "quality_satisfied"
            }
        },
        {
            "node": "merge",
            "node_type": "merge",
            "duration_ms": 100,
            "timestamp": "2026-01-26T10:00:04Z",
            "input": {...},
            "output": {
                "context_length": 8234,
                "deduplication_rate": 0.15  # 去重率
            }
        }
    ]
}
```

### 前端时间线展示

```
📊 retrieval_subgraph (3.5s)
├─ 📋 plan (5ms)
│  └─ 生成 2 步计划：step_0_candidates（拉取候选集合）、step_1_evidence（补充候选作品的详细信息）
├─ ⚙️ execute_plan (2.5s)
│  ├─ step_0_candidates: hybrid_search (1.2s)
│  │  ├─ 🔍 hybrid_low_level_retrieval (800ms) → 找到 30 条证据
│  │  └─ 🔍 hybrid_high_level_retrieval (400ms) → 找到 20 条证据
│  └─ step_1_evidence: global_search (1.1s)
│     └─ 🔍 global_search_community_retrieval (1100ms) → 找到 15 条证据
├─ 🤔 reflect (10ms)
│  └─ 质量满足（证据数量 50，最高分 0.85），停止迭代
└─ 🔀 merge (100ms)
   ├─ 去重：65 → 50 (去重率 23%)
   ├─ 截断：context 8234 chars
   └─ 统计：2 步，2 个工具（hybrid_search x1, global_search x1），100% 成功率
```

---

## 挂载到对话主图

```python
from langgraph.graph import StateGraph, END

def build_retrieval_subgraph():
    """构建 Multi-Agent 检索子图"""
    graph = StateGraph(RetrievalState)

    # 添加节点
    graph.add_node("plan", plan_node)
    graph.add_node("execute_plan", execute_plan_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("append_steps", append_steps_node)
    graph.add_node("merge", merge_node)

    # 添加边
    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute_plan")
    graph.add_conditional_edges(
        "execute_plan",
        should_reflect,
        {"reflect": "reflect", "merge": "merge"}
    )
    graph.add_conditional_edges(
        "reflect",
        should_continue,
        {"continue": "append_steps", "merge": "merge"}
    )
    graph.add_edge("append_steps", "execute_plan")
    graph.add_edge("merge", END)

    return graph.compile()


# 在对话主图中调用
def execute_node(state: ChatState) -> ChatState:
    """
    对话主图的 execute 节点
    """
    route_decision = state.get("route_decision", {})
    kb_prefix = route_decision.get("kb_prefix", "general")

    # general：跳过子图，直接返回
    if kb_prefix == "general":
        return {
            **state,
            "retrieval_result": {
                "context": "",
                "retrieval_results": [],
                "reference": {"chunks": [], "entities": [], "relationships": []}
            }
        }

    # movie/edu：进入子图
    retrieval_subgraph = build_retrieval_subgraph()

    initial_state: RetrievalState = {
        "query": state.get("message", ""),
        "route_decision": route_decision,
        "session_id": state.get("session_id", ""),
        "kb_prefix": kb_prefix,
        "plan": [],
        "records": [],
        "retrieval_results": [],
        "context_parts": [],
        "current_step_index": 0,
    }

    final_state = retrieval_subgraph.invoke(initial_state)

    return {
        **state,
        "retrieval_result": final_state.get("merged", {})
    }


def should_reflect(state: RetrievalState) -> str:
    """条件边：决定是否需要反思"""
    plan = state["plan"]
    current_index = state.get("current_step_index", 0)

    # 所有步骤都执行完成 → 需要 reflect
    if current_index >= len(plan):
        return "reflect"

    # 还有未执行的步骤，但当前批次失败 → 也需要 reflect
    records = state.get("records", [])
    failed_steps = [r for r in records if r.status == "failed"]

    if failed_steps:
        return "reflect"

    # 否则继续执行
    return "execute_plan"


def should_continue(state: RetrievalState) -> str:
    """条件边：决定是否继续迭代"""
    reflection = state.get("reflection")
    if not reflection:
        return "merge"

    if reflection.should_continue:
        return "continue"
    else:
        return "merge"


def append_steps_node(state: RetrievalState) -> RetrievalState:
    """Append Steps 节点：追加新步骤到 plan"""
    reflection = state.get("reflection")
    if not reflection or not reflection.should_continue:
        return state

    new_steps = reflection.next_steps
    current_plan = state.get("plan", [])

    return {
        **state,
        "plan": current_plan + new_steps,
    }
```

---

## 真实场景示例

### 场景 1：QA 查询（单步 + 可选 fallback）

**用户查询**："喜宴哪一年上映？"

**Plan 输出**：
```python
{
    "plan": [
        PlanStep(
            step_id="step_0_primary",
            objective="查询 喜宴 的详细信息",
            tool="hybrid_search",
            tool_input={"query": "喜宴哪一年上映？", "kb_prefix": "movie", "top_k": 50},
            depends_on=[],  # 无依赖
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ),
        PlanStep(
            step_id="step_1_fallback",
            objective="兜底检索（如果主路结果不足）",
            tool="naive_search",
            tool_input={"query": "喜宴哪一年上映？", "kb_prefix": "movie", "top_k": 30},
            depends_on=["step_0_primary"],  # 依赖主路
            budget=PlanBudget(timeout_s=10.0, top_k=30),
            priority=2
        )
    ]
}
```

**Execute 执行**：
1. 并行执行 step_0_primary（无依赖）
2. 检查 step_1_fallback 的依赖（主路完成）
3. Reflect 评估质量

**Reflect 评估**：
- 如果 evidence_count >= 5 且 top_score >= 0.4 → 停止迭代
- 如果不满足 → 执行 step_1_fallback（兜底检索）

### 场景 2：Recommend 查询（多步串行）

**用户查询**："推荐几部类似《喜宴》的电影"

**Plan 输出**：
```python
{
    "plan": [
        PlanStep(
            step_id="step_0_candidates",
            objective="拉取候选集合",
            tool="hybrid_search",
            tool_input={"query": "推荐几部类似《喜宴》的电影", "kb_prefix": "movie", "top_k": 50},
            depends_on=[],  # 无依赖
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ),
        PlanStep(
            step_id="step_1_evidence",
            objective="补充候选作品的详细信息（导演、年份、获奖等）",
            tool="global_search",
            tool_input={"query": "...", "kb_prefix": "movie", "top_k": 30},
            depends_on=["step_0_candidates"],  # 依赖第一步（串行）
            budget=PlanBudget(timeout_s=15.0, top_k=30)
        )
    ]
}
```

**Execute 执行**：
1. 先执行 step_0_candidates（拉候选集）
2. 检查 step_1_evidence 的依赖（step_0 完成）
3. 执行 step_1_evidence（补证据）

### 场景 3：Compare 查询（多步串行 + 迭代）

**用户查询**："对比一下《喜宴》和《饮食男女》的风格差异"

**Plan 输出**：
```python
{
    "plan": [
        PlanStep(
            step_id="step_0_first_movie",
            objective="检索《喜宴》的相关信息",
            tool="hybrid_search",
            tool_input={"query": "《喜宴》的风格特点", "kb_prefix": "movie", "top_k": 50},
            depends_on=[],
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ),
        PlanStep(
            step_id="step_1_second_movie",
            objective="检索《饮食男女》的相关信息",
            tool="hybrid_search",
            tool_input={"query": "《饮食男女》的风格特点", "kb_prefix": "movie", "top_k": 50},
            depends_on=[],  # 无依赖，可与 step_0 并行
            budget=PlanBudget(timeout_s=15.0, top_k=50)
        ),
        PlanStep(
            step_id="step_2_comparison",
            objective="对比两部电影",
            tool="naive_search",  # 用纯向量检索找到对比性信息
            tool_input={"query": "《喜宴》与《饮食男女》风格对比", "kb_prefix": "movie", "top_k": 30},
            depends_on=["step_0_first_movie", "step_1_second_movie"],  # 依赖前两步（串行）
            budget=PlanBudget(timeout_s=10.0, top_k=30)
        )
    ]
}
```

**Execute 执行**：
1. **并行执行**：step_0_first_movie + step_1_second_movie（无依赖）
2. **串行执行**：step_2_comparison（依赖前两步）

**Reflect 评估**：
- 如果对比信息不足 → 追加补充检索步骤

---

## 实施计划

### 阶段 1：准备阶段（1-2 天）

**任务清单**：
- [ ] 定义强类型 State（RetrievalState、PlanStep、ExecutionRecord、Reflection）
- [ ] 编写 E2E 测试（覆盖所有 query_intent：qa/recommend/compare/list）
- [ ] 添加性能基准测试
- [ ] 创建重构分支

### 阶段 2：实现 Multi-Agent 子图（5-7 天）

**步骤 1：实现 Plan 节点（1.5 天）**
- [ ] 实现 deterministic planner（根据 query_intent 生成 PlanStep[]）
- [ ] 支持 QA/Recommend/Compare/List/Person 等场景
- [ ] 单元测试：覆盖所有 query_intent

**步骤 2：实现 Execute 节点（2 天）**
- [ ] 实现串行/并行混合执行逻辑（根据 depends_on）
- [ ] 实现 ExecutionRecord 记录（input_summary、output_summary、raw_input、raw_output、sub_steps）
- [ ] 集成工具调用（TOOL_REGISTRY）
- [ ] 单元测试：测试依赖关系、并行执行

**步骤 3：实现 Reflect 节点（1.5 天）**
- [ ] 实现质量评估逻辑（evidence_count、top_score、missing_fields、errors）
- [ ] 实现追加步骤生成（补充检索、兜底检索、降级检索）
- [ ] 实现预算约束（max_iterations、remaining_budget）
- [ ] 单元测试：测试迭代决策

**步骤 4：实现 Merge 节点（1 天）**
- [ ] 实现去重逻辑（按 source_id + granularity）
- [ ] 实现统计信息（tool_distribution、success_rate）
- [ ] 单元测试：测试去重、排序

**步骤 5：集成测试（1 天）**
- [ ] 子图编译测试
- [ ] E2E 测试
- [ ] 性能对比测试

### 阶段 3：挂载到对话主图（1 天）

**任务清单**：
- [ ] 修改 execute_node
- [ ] Feature Flag 灰度发布
- [ ] 集成测试

### 阶段 4：Debug 与监控（1 天）

**任务清单**：
- [ ] 更新 execution_log 格式（三层嵌套）
- [ ] 前端时间线展示（子图 → step → tool 内部）
- [ ] 监控指标完善

### 阶段 5：删除旧代码（1 天）

**任务清单**：
- [ ] 删除 MovieKnowledgeBasePlanner
- [ ] 删除 fusion_agent 及相关组件
- [ ] 删除 graph_agent（可选）

### 时间线

| 阶段 | 预计时间 | 里程碑 |
|-----|---------|--------|
| 阶段 1：准备 | 1-2 天 | State 定义完成 |
| 阶段 2：子图实现 | 5-7 天 | 子图上线 |
| 阶段 3：挂载主图 | 1 天 | 集成完成 |
| 阶段 4：Debug | 1 天 | 监控完善 |
| 阶段 5：清理 | 1 天 | 代码删除 |
| **总计** | **9-12 天** | **重构完成** |

---

## 总结

### 核心改进

1. **Plan 产出的结构化计划**：`List[PlanStep]`（objective、tool、tool_input、depends_on、budget）
2. **Execute 按计划执行**：根据 depends_on 关系，支持串行/并行混合
3. **Reflect 迭代闭环**：评估质量 + 追加步骤/改写 query + 预算约束
4. **执行记录模型**：每个 step 都有 ExecutionRecord（三层嵌套：子图 → step → tool 内部）

### 与固定并行 4 路的本质区别

| 对比项 | 固定并行 4 路 | Plan → Execute → Reflect → Merge |
|-------|--------------|--------------------------------|
| **Plan 输出** | `strategy = "multi"` | `List[PlanStep]`（每步有 objective、tool、depends_on、budget） |
| **执行方式** | 固定 4 路并行 | 按 depends_on 关系，串行/并行混合 |
| **迭代能力** | 无（或固定 fallback） | 评估质量 + 追加步骤/改写 query + 预算约束 |
| **执行记录** | 仅在 rag_retrieval_done 下塞 tool log | 每个 step 都有 ExecutionRecord（三层嵌套） |

### 下一步行动

如果您认可这个设计方案，我们可以：

1. **评审方案**：团队评审设计文档
2. **实现阶段 1**：定义 State + 编写测试
3. **实现阶段 2**：实现 Multi-Agent 子图
4. **灰度发布**：Feature Flag + 监控
5. **全量上线**：删除旧代码

**预计时间**：9-12 天
