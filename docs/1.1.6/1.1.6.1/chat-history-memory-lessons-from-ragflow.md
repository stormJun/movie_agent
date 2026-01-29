# 对话历史与记忆系统：从 RAGFlow 的工程实现可借鉴点

本文基于 RAGFlow 文档：
- `31-DialogService类-对话服务核心引擎与记忆系统.md`
- `32-ConversationService类-对话会话管理器.md`
- `33-对话历史管理与记忆系统-多轮对话实现详解.md`

结合本项目当前的 LangGraph 编排与记忆模块（Phase 1 summary / Phase 2 episodic / mem0），整理可直接落地的工程借鉴点与改造建议。

## 0. 结论（最值得借鉴的 6 件事）

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
- 补充：建议把 `request_id` 视为一次 turn 的稳定标识（turn_id），让“引用/反馈/trace/推荐列表”统一对齐同一个 turn。

5) **会话管理与对话引擎的职责边界清晰**
- 目的：把“会话生命周期/持久化/流式输出/错误兜底”与“RAG 核心（检索/生成/引用/指标）”分层隔离。
- 价值：多端（Web/小程序/SDK）复用更稳，避免接口层分叉导致行为不一致。

6) **流式输出节流（chunk buffering）**
- 目的：流式阶段按 token/时间做合并再推送，减少帧数和渲染压力。
- 价值：前端更顺滑、网络更稳定，尤其是移动端/小程序。

## 1. RAGFlow 的关键工程做法（摘取）

1) 职责拆分（ConversationService vs DialogService）：
- ConversationService：会话 CRUD、message/reference 存储、SSE 输出格式化、异常兜底
- DialogService：对话核心引擎（多轮重写、窗口管理、检索、生成、引用、指标/追踪）

2) 写入路径（多轮对话 + 流式）：
- 先追加 user 消息
- 再插入 assistant “占位消息”（content 为空、带 message_id）
- 流式过程中不断结构化/回填（包括 reference）
- 最终落库更新整段会话

3) 读取路径（多轮理解 + 窗口控制）：
- 提取最近 N 轮用户问题（示例 N=3）作为“重写输入”
- 可选执行 full_question（refine_multiturn=true）
- 在拼 prompt 前执行 token 裁剪（max_tokens 的 95%）

4) 流式输出节流：
- 流式生成时对增量答案做累积（例如累计到一定 token 再输出），避免“每个 token 一个 SSE 帧”导致前端压力。

## 2. 我们当前系统的对应位置（movie_agent）

核心链路（movie KB）：
- `/api/v1/chat` / `/api/v1/chat/stream`
  - `ConversationGraphRunner`: route -> build_context -> prepare_retrieval -> retrieval_subgraph -> generate
  - `ChatHandler`/`StreamHandler`: 负责会话与消息持久化、side effects（summary/episodic/mem0/watchlist）

现状差异（与 RAGFlow 对齐角度）：
- 流式：已实现“先写 assistant placeholder + 结束回填（update）”；断连会保留 completed=false 的 incomplete message（message_id 稳定）
  - 仍可优化：在 SSE 早期透传 `assistant_message_id`（便于前端在“第一 token 前”就能绑定反馈/引用/断连恢复）
  - 现有行为：上下文构建会过滤 completed=false 的历史消息，避免把断连残留的 incomplete 内容再次喂给模型
- 多轮重写：目前没有“只用于检索”的 query rewrite 步骤
- Token 预算：目前更多是按条数/字符做近似控制，没有统一 token budget 裁剪器
- 引用绑定：已有 citations 字段，但更偏“debug/citations 存储”，缺少强约束与回放接口形态统一

## 3. 建议的落地方案（MVP → 迭代）

### 3.1 流式占位消息 + 回填（已落地；建议继续完善）

目标：在流式开始就落库创建 assistant 占位消息，并在结束时标记 completed=true；断连时保留 completed=false。

当前实现形态（本项目）：
- ConversationStore：新增 `update_message(...)`，用于回填 content/debug/completed
- StreamHandler：
  - 在开始流式时创建 placeholder（拿到稳定 message_id）
  - 结束时 `update_message(..., completed=true)`；断连时 `update_message(..., completed=false)`（可回看 incomplete）
- 关键实现位置（便于定位代码）：
  - `backend/application/chat/handlers/stream_handler.py`
  - `backend/application/ports/conversation_store_port.py`
  - `backend/infrastructure/persistence/postgres/conversation_store.py`

建议继续完善：
- SSE：新增一个轻量事件（例如 `status=assistant_message_id`），让前端在“第一 token 之前”就能拿到 id
- MiniProgram：完成帧里 `message_id` 可以直接取 placeholder 的 id，而不是“list_messages 找最近一条 assistant”（避免竞态）

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
