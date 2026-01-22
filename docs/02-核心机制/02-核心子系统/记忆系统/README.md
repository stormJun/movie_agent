# 记忆系统（mem0）

本项目的“记忆”指对话相关的长期记忆召回（可选启用），用于在回答时补充用户偏好/历史事实。v3 strict 下：

- 会话消息持久化：Postgres（ConversationStore）
- 长期记忆：mem0（本地/自托管；向量库 + Postgres 元数据）

## 1. 数据分层

1) 会话历史（短期）
- 由服务侧 ConversationStore 管理
- 按 `(user_id, session_id)` 映射到 `conversation_id`，记录 message 列表

2) 长期记忆（可选）
- 由 mem0 管理（按 `user_id` 维度召回）
- 召回内容以 `memory_context` 形式注入到聊天编排/生成阶段

## 2. 调用链路（简化）

- API 收到 `user_id/session_id/message`
- ConversationStore 追加消息
- 若启用 mem0：按 `user_id` 召回记忆，得到 `memory_context`
- Router 决策 worker
- RAG 执行器检索 evidence
- 生成器使用 `memory_context + evidence` 生成最终回答（流式/非流式）

## 3. 配置要点

- `POSTGRES_*`：会话与反馈持久化
- `MEM0_BASE_URL`：mem0 服务地址（为空则不启用长期记忆）

