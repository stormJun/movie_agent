# 记忆中心（Memory Center）产品设计文档

**版本**：1.1.4.2  
**状态**：设计稿（对齐当前 Phase 1/2/3 实现，补齐产品化交互）  
**日期**：2026-01-25  

## 1. 背景与目标

当前系统已经具备三类“记忆来源”：

- **短期上下文**：最近 N 条消息（`messages`），用于对话连续性
- **会话摘要（Phase 1）**：每个会话一段滚动摘要（`conversation_summaries`）
- **会话情节记忆（Phase 2 episodic）**：会话内语义召回（Milvus 仅存 `message_id`，回 Postgres 补全文）
- **用户长期记忆（mem0）**：用户级跨会话偏好/事实/约束（向量检索）

现状问题：

- 用户不知道系统“记住了什么、为什么记住、如何删除”，导致不信任与隐私担忧
- “清空聊天记录”和“清除记忆”语义不一致：会产生残留索引/回填失败等一致性问题
- Debug 数据能看见部分信息，但不适合普通用户使用

记忆中心目标：

1) **可见**：用户能看到当前系统会用到的记忆（摘要/情节召回/长期记忆）  
2) **可控**：用户能开关记忆、删除本次/删除会话/删除全部、导出  
3) **一致**：删除要跨存储一致（DB + 向量库 + cache），并可追踪执行状态  
4) **可解释**：每条记忆提供来源（message ids / 会话 / 时间）与生效范围（会话/用户）  

非目标（MVP 不做）：

- 复杂可视化图谱编辑（属于 KG 功能，不属于记忆中心）
- 自动“跨会话 episodic”扩展（后续可做成可选能力）

## 2. 记忆分类（面向产品解释口径）

### 2.1 会话内（Session-scoped）

1) **短期上下文**（最近对话）  
- 来源：`messages`（completed=true）  
- 用途：保证连续对话  
- 删除：清空/删除会话 = 删除

2) **会话摘要（Phase 1）**  
- 来源：后台任务把“滑出窗口”的历史压缩成摘要，写入 `conversation_summaries`  
- 用途：减少 prompt 长度，保留背景/偏好/关键决定  
- 删除：删除会话 = 删除；“清空会话”建议也删除（见 7.2）

3) **会话情节记忆（Phase 2 episodic）**  
- 来源：每个 completed 回合（user+assistant）写入 episode（Milvus 仅存 ids）  
- 用途：当用户提到“刚才/上次/继续/那个…”时，语义召回相关历史片段补全上下文  
- 删除：删除会话 = 必须删除；删除单条消息 = 删除对应 episode 或标记不可召回

### 2.2 用户级（User-scoped）

4) **用户长期记忆（mem0）**  
- 来源：从对话抽取“稳定、可复用”的偏好/事实/约束（建议支持用户确认）  
- 用途：跨会话持续个性化  
- 删除：用户可逐条删除、禁用，或一键清空

## 3. 入口与信息架构（IA）

### 3.1 前端入口

- Chat 页面右上角：`记忆中心`（与 `调试信息` 区分；调试面向开发）
- 每条消息气泡更多菜单：`删除本次（同时从记忆中移除）`
- 会话列表更多菜单：`导出会话` / `删除会话`（二次确认）
- 设置页：`记忆开关`（细粒度开关：会话摘要/会话情节/长期记忆）

### 3.2 记忆中心页面布局（建议）

Tab 结构：

1) **本会话**（conversation_id）  
   - 最近消息窗口（只读，展示 system 会读取的“短期上下文”范围）
   - 会话摘要（显示 summary + 版本/覆盖范围）
   - 本会话情节记忆（展示最近召回/或最近索引的 episodes）

2) **长期记忆（我的）**（user_id）  
   - 列表：偏好/事实/约束（可筛选、可删除、可禁用）
   - 支持“新增/确认写入”（可选）

3) **数据管理**  
   - 导出：会话导出 / 全部导出
   - 删除：删除本次、删除会话、删除全部（强确认）
   - 任务状态：展示异步清理的进度/失败重试

## 4. 关键交互（UX Flow）

### 4.1 开关记忆（用户可控）

入口：设置 -> 记忆中心 -> 开关

- 开关项（建议）：
  - 会话摘要：ON/OFF（默认 ON）
  - 会话情节记忆：ON/OFF（默认 ON）
  - 长期记忆：ON/OFF（默认 OFF 或 ON，取决于隐私策略）

开关语义：

- OFF：停止写入 + 停止召回（不影响已有数据是否删除，需配合“清空”）
- ON：恢复写入/召回

### 4.2 删除本次（message-level forget）

入口：消息气泡更多 -> 删除本次（提示：同时移除相关记忆）

推荐语义：

- 默认删除：该 assistant 消息（可选联动删除紧邻的 user 消息）
- 同步移除：
  - Phase 2：删除与该 assistant_message_id 对应的 episode 索引（或标记 disabled）
  - mem0：如果这次写入产生了 mem0 记忆条目，删除对应条目（需要 mapping 表）

### 4.3 删除会话（conversation-level forget）

入口：会话列表更多 -> 删除会话（强确认）

删除范围：

- Postgres：`messages`、`conversation_summaries`、`feedback`、（如使用 Postgres episodic store，则 `conversation_episodes`）
- Milvus：该 conversation 下的 episodes（按 conversation_id / assistant_message_id 批量删除）
- cache：debug cache / 其它缓存 best-effort 清理

### 4.4 删除全部（user-level forget）

入口：记忆中心 -> 数据管理 -> 删除全部（强确认 + 二次输入）

删除范围：

- Postgres：该 user 的所有 conversations 及其关联数据（由外键 cascade）
- Milvus：按 conversation_id 批量删除（或按 user_id 的 conversation 列表逐个删）
- mem0：删除该 user 的所有长期记忆条目

### 4.5 导出（export）

支持两类导出：

- 导出会话：messages + summary + episodic（ids + 回填的文本）+ feedback
- 导出全部：按会话打包 + mem0 记忆条目

格式建议：

- 默认：JSON（可选 zip）
- 字段包含：来源（message ids）、时间、开关状态、以及是否完成清理（如存在异步任务）

## 5. 后端接口设计（建议新增）

说明：当前已有 `/api/v1/conversations`、`/api/v1/messages`、`/api/v1/clear`、`/api/v1/feedback`、`/api/v1/debug/{request_id}`。

记忆中心建议新增（MVP）：

### 5.1 设置

- `GET /api/v1/memory/settings?user_id=...`
- `PUT /api/v1/memory/settings`
  - body: `{ user_id, summary_enabled, episodic_enabled, longterm_enabled }`

### 5.2 会话内记忆读取

- `GET /api/v1/memory/summary?conversation_id=...`
  - return: `{ text, version, covered_message_count, updated_at }`
- `GET /api/v1/memory/episodes?conversation_id=...&limit=...`
  - return: `[{ user_message_id, assistant_message_id, similarity?, created_at, user_message?, assistant_message? }]`

### 5.3 长期记忆（mem0）

- `GET /api/v1/memory/long_term?user_id=...&limit=...`
- `DELETE /api/v1/memory/long_term/{memory_id}?user_id=...`
- （可选）`POST /api/v1/memory/long_term/confirm`：用户确认写入

### 5.4 删除与任务状态（跨存储一致）

- `POST /api/v1/memory/forget`
  - body: `{ scope: "message"|"conversation"|"user", user_id, conversation_id?, message_id?, cascade?: boolean }`
  - return: `{ status: "accepted", op_id }`
- `GET /api/v1/memory/ops/{op_id}`
  - return: `{ status, progress, last_error }`

## 6. 数据模型（建议）

### 6.1 user_settings（新增）

- `user_id (pk)`
- `summary_enabled bool`
- `episodic_enabled bool`
- `longterm_enabled bool`
- `updated_at`

### 6.2 data_ops / outbox（新增，保证跨存储一致）

- `id (uuid)`
- `type`：`forget_message|forget_conversation|forget_user|export_*|cleanup_*`
- `payload jsonb`
- `status`：`pending|running|succeeded|failed`
- `retry_count`
- `last_error`
- `created_at/updated_at`

### 6.3 mem0 映射表（建议新增，否则无法“删除本次”时精准删除长期记忆）

- `id`
- `user_id`
- `source_message_id`（assistant_message_id 或 user_message_id）
- `mem0_memory_id`
- `created_at`

## 7. 关键策略与边界

### 7.1 优先级（避免冲突）

推荐策略（用于 prompt 注入时的解释口径）：

1) 安全/禁忌（长期记忆）  
2) 用户稳定偏好/约束（长期记忆）  
3) 会话摘要（Phase 1）  
4) 会话情节记忆（Phase 2 episodic）  
5) 最近消息窗口（短期上下文）  

备注：若出现冲突，以“最新消息”或“用户明确更正”优先，且应更新长期记忆条目。

### 7.2 “清空聊天”语义统一（强烈建议）

用户视角“清空聊天”通常意味着“忘掉这段会话”。建议将 `/api/v1/clear` 升级为：

- 清空 messages
- 同时清空该 conversation 的 summary + episodic 索引

否则会出现：

- episodic 只存 message_id：messages 被删后回填失败（召回空片段）
- summary 仍存在：用户以为清空了但系统仍能读到摘要（隐私风险）

### 7.3 隐私与合规

- 默认不展示内部 debug 信息（只展示“记忆中心”整理后的用户可读内容）
- 对导出/删除提供强确认与审计（op_id + 日志）
- 对敏感内容可选：不写入长期记忆；或脱敏后写入

## 8. MVP 交付清单（建议）

1) 前端记忆中心页面（本会话/长期记忆/数据管理）  
2) 后端新增 summary/episodic/mem0 的读取接口（不依赖 debug=true）  
3) forget API + outbox（先支持删除会话、删除全部；再支持删除本次）  
4) 删除一致性：DB + Milvus + mem0（cache best-effort）  

## 9. 与现有实现的对齐说明

- Phase 1/2/3 已具备核心能力；记忆中心主要补齐“产品化入口与可控操作”
- Phase 1 摘要已可在 debug 中查看（最新实现），但记忆中心应提供**非 debug**的 summary 查看接口
- Phase 2 episodic 当前为会话内隔离（conversation_id）；跨会话连续性由 mem0 承担

