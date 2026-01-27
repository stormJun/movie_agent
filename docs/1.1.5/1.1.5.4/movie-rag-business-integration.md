# 电影业务下的 RAG Agent 组合策略（从“技术实现”到“产品能力”）

目标：把现有 GraphRAG/检索能力（agents + tools）与电影业务的“问题类型/结果形态”对齐，让系统默认就能给出**可用、可解释、可落地的电影结果**（而不是只做技术上的检索与生成）。

本文以当前实现为准：
- 主编排：`backend/application/chat/conversation_graph.py`（route → recall → retrieval_subgraph → generate）
- 检索子图：`backend/infrastructure/rag/retrieval_subgraph.py`（Plan → Execute → Reflect → Merge）
- Query-time Enrichment（TMDB）：`backend/infrastructure/enrichment/tmdb_enrichment_service.py`（由 merge 阶段触发）

---

## 1. 电影业务的“问题分型”（决定要什么证据 + 什么输出）

把用户问题先映射到“业务意图”（intent）与“媒体类型”（media_type），这是后续检索计划（plan）与输出结构（contract）的入口。

建议的最小集合（与当前 RouteDecision 字段对齐）：

- `query_intent`：
  - `fact`：单点事实（导演/年份/片长/主演/评分/国家/语言）
  - `list`：清单（某导演作品、某演员作品、某题材片单）
  - `recommend`：推荐（偏好/约束驱动）
  - `compare`：对比（A vs B）
  - `explain`：解释/深聊（风格/主题/影史脉络）
  - `unknown`：不确定（兜底）
- `media_type_hint`：
  - `movie` / `tv` / `person` / `unknown`
- `filters`（可选）：
  - `year`、`origin_country`、`original_language`、`region`、`date_range`、`genre`、`runtime_range` 等
- `extracted_entities`（可选）：
  - `low_level`：字符串候选（片名/人名/别名），用于消歧与 enrichment

---

## 2. 现有几个 Agent 在电影业务里各自“该干什么”

注意：在当前架构中，Agent 本质上是 retrieval_subgraph 的“工具”（PlanStep.tool），由 subgraph 统一调度；前端不需要、也不应该让用户手动选 agent。

- `naive_rag_agent`
  - 电影业务定位：语义兜底（实体抽取失败、KB 图不完整、用户描述很模糊）
  - 风险：容易“看起来相关但不准确”，输出要更保守（提示不确定性/建议 уточ）

- `graph_agent`
  - 电影业务定位：关系型问题的主力（人物-作品-合作关系-题材路径）
  - 典型问题：导演是谁/演员是谁/谁和谁合作过/某导演代表作

- `hybrid_agent`
  - 电影业务定位：综合型主力（既要细节又要概念背景；推荐/比较通常更稳）
  - 典型问题：相似片推荐、主题相似、风格相近、对比分析

- `deep_research_agent`
  - 电影业务定位：只在“解释/深聊”且用户明确要长文时启用（成本高、时延高）
  - 典型问题：导演风格分析、电影史定位、主题解读

- `fusion_agent`
  - 电影业务定位：不建议作为“一个单独 agent”执行。
  - 在当前实现里，它应被 **Plan → Execute → Reflect → Merge** 这套子图能力替代（融合检索、多步补证、反思迭代、最终合并）。

---

## 3. “电影业务优先”的检索计划（Plan）怎么写

核心原则：先把“对象”搞清楚（movie/person/tv 的消歧/定位），再扩展证据；不要在对象不确定时就做深度检索。

### 3.1 推荐的 Plan 模板（按意图）

下面的 “tool” 对应 retrieval_subgraph 的 `PlanStep.tool`（最终会映射到 `agent_type` 执行）：

1) `fact`（事实查询）
- step_0_primary：`graph_agent` 或 router 推荐 agent（通常更快）
- step_1_fallback：`naive_rag_agent`（兜底）
- merge：触发 query-time enrichment（当证据疑似缺失关键实体时）

2) `list`（清单/作品列表）
- 若 `media_type_hint=person`：
  - step_0_resolve_person：`graph_agent`（确认“是谁” + 基本关系）
  - step_1_person_works：`hybrid_agent`（作品与上下文补证）
- 否则：
  - step_0_candidates：`hybrid_agent`
  - step_1_evidence：`graph_agent`

3) `recommend`（推荐）
- 先用 filters/偏好确定候选空间，再用图/语义做重排与解释
- merge：
  - 若 `media_type_hint=tv`，建议走 TMDB discover（需要 tv 能力）
  - 若 `media_type_hint=movie` 且 filters 明确，允许触发 TMDB discover/movie enrichment

4) `compare`（对比）
- step_0_candidates：`hybrid_agent`（拉齐两者可比信息）
- step_1_evidence：`graph_agent`（关系与事实补证）
- merge：生成对比所需的结构化字段（title/year/director/genre/…）

5) `explain`（解释/深聊）
- step_0_default：`hybrid_agent`（快速拉证据）
- step_1_deep：`deep_research_agent`（可选；只在需要时）
- reflect：判断证据是否足够，决定是否追加一步检索

---

## 4. TMDB Enrichment 在电影业务里的定位（必须“产品化”）

电影问答里最常见的失败模式不是“LLM 不会答”，而是：
- 图谱/索引没收录该片或该人物（KB coverage gap）
- 实体消歧失败（同名片、译名/别名、年份不一致）

因此 enrichment 需要成为“可控的业务能力”：

### 4.1 触发策略（保守 but 可解释）

当前实现（概念）：
- 当 GraphRAG 的 combined_context 疑似没有覆盖抽取到的关键实体时，触发 TMDB enrichment。
- 对 TV 推荐（`recommend + tv`）可直接触发（依赖 router 的强信号）。

建议补充（产品侧约束）：
- enrichment 的结果必须能给出 “证据片段”（结构化字段 + 来源），否则宁可不触发/提示不确定。
- 对 “人物作品列表” 建议优先走 `/search/multi` → `/person/{id}?append_to_response=combined_credits`，避免把人名当片名搜。

### 4.2 Enrichment 的职责边界

- Enrichment 产出：一个“临时图（transient graph）”的结构化证据，可拼到 combined_context
- 不负责：最终自然语言答案（答案由 generate 阶段统一生成）
- Debug 可见性：应该在 debug cache 里可见（enrichment_start/enrichment_done/combined_context）

---

## 5. 电影业务的“输出契约”（比选 agent 更重要）

为了从“技术 demo”走向“产品能力”，建议为不同意图定义稳定的输出结构（即使最终仍由 LLM 生成，也要约束格式）：

### 5.1 `fact` 输出（最小契约）
- `entity`：movie/person/tv + 规范化名称（如可得 tmdb_id）
- `fields`：导演/年份/片长/主演/地区/语言 等（按问题取子集）
- `evidence`：1~3 条证据（source + snippet + metadata）
- `confidence`：high/medium/low
- `ambiguity`：是否存在同名/多版本，需要追问时给出追问

### 5.2 `recommend` 输出（最小契约）
- `candidates[]`：title/year + why（相似点/约束匹配）+ 是否已在想看/已看/不想看
- `filters_applied`：年份/地区/语言/题材等
- `next_questions`：缺信息时的补问（偏好/时长/年代/节奏）

### 5.3 `compare` 输出（最小契约）
- `items[]`：A/B 的关键字段
- `dimensions[]`：对比维度（固定集合）
- `verdict`：建议（并说明适用场景）

---

## 6. 与“记忆中心（Memory Center）”结合：让推荐变成产品

电影业务的记忆最有价值的不是“聊天摘要”，而是：
- 用户偏好画像（Taste DNA / tags）
- 观看状态（想看/已看/不想看）
- 会话内指代消解（episodic recall：刚才那部/第二个）

推荐场景的最小闭环：
1) 召回：从 watchlist/taste 过滤掉“已看/不想看/已在想看”
2) 检索：Graph/Hybrid 取候选证据
3) 生成：输出推荐列表 + “为什么推荐”
4) 行动：一键加入“想看清单”（watchlist auto-capture 或显式 add）

---

## 7. 调试与评估（确保你做的是“电影正确性”而不是“流式漂亮”）

Debug 面板应优先帮助定位电影业务失败点：
- route_decision：意图与 media_type 是否判断对
- execution_log：plan/merge/enrichment/persistence/postprocess 是否完整
- combined_context：最终喂给 LLM 的证据文本是什么（是否包含导演/年份等关键字段）
- rag_runs：各检索路径 hit 数与错误

评估建议（最小集）：
- Fact 准确率：导演/年份/主演（同名/别名覆盖）
- Person 清单正确性：作品列表、导演/演员区分
- 推荐有效性：重复率（去重）、命中偏好、可解释性
- 时延/成本：不同 intent 下的平均耗时与 token

---

## 8. 落地优先级建议（不引入大改的前提）

P0（马上可做）：
- router 输出 `query_intent/media_type_hint/filters` 的稳定化（强制字段 + 解析兜底）
- retrieval_subgraph 的 plan 模板按 intent 固化（少猜、多规则）

P1（产品化关键）：
- `fact/recommend/compare` 的输出契约（结构化字段 + ambiguity 追问）
- enrichment 的“可解释”字段进入 debug（候选、选择、拒绝原因）

P2（覆盖扩展）：
- TV 支持（/search/tv + /discover/tv），以及 tv 的图谱建模与检索
- 把 TMDB 入库（Postgres source of truth）→ 再 ETL 到 Neo4j（离线）

