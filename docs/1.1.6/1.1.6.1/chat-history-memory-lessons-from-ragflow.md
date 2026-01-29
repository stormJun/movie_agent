# 对话历史与记忆系统：从 RAGFlow 的工程实现可借鉴点

本文基于 RAGFlow 文档 `33-对话历史管理与记忆系统-多轮对话实现详解.md` 的实现思路，结合本项目当前的 LangGraph 编排与记忆模块（Phase 1 summary / Phase 2 episodic / mem0），整理可直接落地的工程借鉴点与改造建议。

## 0. 结论（最值得借鉴的 4 件事）

1) **流式占位消息（placeholder）+ 最终回填**
- 目的：在流式开始时就确定 `assistant_message_id`，并允许“断连产生的 incomplete message”对前端可见。
- 价值：反馈绑定、引用绑定、Langfuse trace 对齐、断连恢复/重试体验都会更稳定。

2) **多轮问题重写（full_question）只用于“检索问句”**
- 目的：在检索阶段消解“它/那个/前者/后者”等指代，提高检索命中率；不改变用户原问题展示。
- 价值：电影/人物/电视剧等场景的多轮对话检索更稳（尤其是 entity 抽取失败时）。

3) **Token 预算裁剪（message_fit_in）+ 安全边际**
- 目的：用 token 预算而不是“条数限制”来管理上下文窗口，留 5% 安全边际避免溢出。
- 价值：当 summary/mem0/episodic/enrichment 变多时仍可控，并能解释“为什么这段被裁剪”。

4) **引用(reference)与“轮次/消息”的强绑定**
- 目的：每轮检索引用能可靠关联到对应 `assistant_message_id`（或 `request_id`），并可回放。
- 价值：前端引用展示、负反馈归因、离线评测更可追溯。

## 1. RAGFlow 的关键工程做法（摘取）

1) 写入路径：
- 先追加 user 消息
- 再插入 assistant “占位消息”（content 为空、带 message_id）
- 流式过程中不断结构化/回填（包括 reference）
- 最终落库更新整段会话

2) 读取路径：
- 提取最近 N 轮用户问题（示例 N=3）作为“重写输入”
- 可选执行 full_question（refine_multiturn=true）
- 在拼 prompt 前执行 token 裁剪（max_tokens 的 95%）

## 2. 我们当前系统的对应位置（movie_agent）

核心链路（movie KB）：
- `/api/v1/chat` / `/api/v1/chat/stream`
  - `ConversationGraphRunner`: route -> build_context -> prepare_retrieval -> retrieval_subgraph -> generate
  - `ChatHandler`/`StreamHandler`: 负责会话与消息持久化、side effects（summary/episodic/mem0/watchlist）

现状差异（与 RAGFlow 对齐角度）：
- 流式：目前是“流完后再写 assistant message”，没有占位/回填语义（断连只能生成 incomplete message，但 message_id 不稳定）
- 多轮重写：目前没有“只用于检索”的 query rewrite 步骤
- Token 预算：目前更多是按条数/字符做近似控制，没有统一 token budget 裁剪器
- 引用绑定：已有 citations 字段，但更偏“debug/citations 存储”，缺少强约束与回放接口形态统一

## 3. 建议的落地方案（MVP → 迭代）

### 3.1 流式占位消息 + 回填（推荐优先做）

目标：在流式开始就落库创建 assistant 占位消息，并在结束时标记 completed=true；断连时保留 completed=false。

建议实现形态：
- ConversationStore 增加 update 能力（或新增方法）：
  - `create_assistant_placeholder(conversation_id, reply_to_user_message_id, request_id, ...) -> assistant_message_id`
  - `append_assistant_delta(message_id, delta)`（可选：不建议逐 token 落库；可按 chunk 或最终一次性写入）
  - `finalize_assistant_message(message_id, content, citations, completed, ...)`
- StreamHandler：
  - 在开始流式时创建 placeholder（拿到稳定 message_id）
  - 将 message_id 透传给前端（用于反馈/引用/断连可见）
  - 结束时 finalize；断连时 finalize(completed=false)

### 3.2 多轮问题重写（仅用于检索 query）

目标：对“检索 query”做重写，改善检索与 enrichment，而不是替换用户原 message。

建议实现形态：
- 在主图 build_context 与 retrieval_subgraph 之间增加一个轻量节点（或在 retrieval_subgraph planner 内部实现）：
  - 输入：最近 N 轮 user messages + 当前 user message
  - 输出：`retrieval_query`（重写后）与 `rewrite_reason`
- 条件触发：
  - 多轮（历史 >= 1 轮）
  - query_intent in {qa, recommend, list, compare}
  - 检测到指代词/省略（中文“它/那个/前者/后者/这部/这位”等）或 router.confidence 较低
- 缓存：
  - cache_key = hash(history_ids + last_user_message_id + model_id)
  - 命中则直接复用重写结果

### 3.3 Token 预算裁剪（message_fit_in 对齐）

目标：提供一个“统一的上下文预算器”，确保 prompt 不溢出，并可解释裁剪策略。

建议实现形态：
- 在 generate 前统一组装 “最终上下文”（history/summary/mem0/episodic/enrichment/merged context）
- 设定总 token budget（例如模型 max_tokens 的 95%）
- 分配预算（示例）：
  - system/prompt 固定预算
  - merged context（检索证据）优先
  - summary 次之
  - episodic/mem0 再次
  - history 作为兜底滑窗
- debug 输出：记录每块的 token 数与裁剪结果（便于 UI 展示“到底拼接了什么”）

### 3.4 引用与消息绑定强化

目标：每轮引用能可靠绑定到 assistant_message_id 或 request_id，且结构稳定。

建议实现形态：
- citations/reference 入库时附带：
  - `request_id`
  - `assistant_message_id`
  - `retrieval_runs` 摘要（agent_type、top_k、source_ids）
- API：提供按 message_id 拉取引用详情（前端可点开）

## 4. 与现有 Phase 1/2/长期记忆的关系（避免重复）

- Phase 1 summary：属于 conversation scope 的“固定背景块”，更适合做成 Memory Block（可编辑/可清空/可查看版本）
- Phase 2 episodic：属于 conversation scope 的“向量召回”，适合与“检索问句重写”联动（重写后 query 更准）
- mem0：属于 user scope 的“长期偏好/事实”，建议做写入规则与删除策略，避免污染

## 5. 验收清单（工程落地）

- 流式开始时：前端能拿到 stable `assistant_message_id`
- 断连时：能在消息列表中看到 completed=false 的 assistant 消息（且后端可恢复/覆盖）
- debug 能回放：本轮的 build_context / retrieval_query（重写后）/ combined_context（最终拼接）/ reference
- Token 不溢出：长对话 + 开启 summary/mem0/episodic/enrichment 仍稳定

