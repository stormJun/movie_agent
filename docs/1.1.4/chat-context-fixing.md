# 对话历史上下文修复文档

## 1. 背景 (Context)

在之前的版本中，用户反馈 AI 助手在多轮对话中经常“断片”或产生幻觉。例如，当用户追问“谁主演的？”时，AI 无法联系上一轮提到的电影，因为它只接收到了系统提示词和当前问题，**丢失了中间的对话历史**。

## 2. 问题分析 (Root Cause)

1.  **Prompt 构建缺失**：`completion.py` 中的 Prompt 模板只包含 `System Prompt` 和 `Human Message`，即使检索了 Memory Context（长期记忆），也唯独漏掉了 Short-term Chat History（短期对话历史）。
2.  **Handler 数据流缺失**：`ChatHandler` 和 `StreamHandler` 从未从数据库中拉取最近的对话记录传给 LLM。
3.  **列表顺序问题**：`ConversationStore.list_messages` 默认只支持按时间正序（ASC）拉取，要获取“最近 6 条”效率较低。

## 3. 解决方案 (Solution)

我们实施了“自底向上”的修复方案，确保最近的对话历史能被正确注入到 Prompt 中。

### 3.1 数据库层 (Conversation Store)

**文件**: `backend/infrastructure/persistence/postgres/conversation_store.py`

*   **变更**: `list_messages` 方法增加了 `desc: bool = False` 参数。
*   **作用**: 允许直接通过 SQL `ORDER BY created_at DESC` 高效拉取最新的 N 条消息。

### 3.2 业务逻辑层 (Handlers)

**文件**:
*   `backend/application/chat/handlers/chat_handler.py`
*   `backend/application/chat/handlers/stream_handler.py`
*   `backend/application/handlers/base.py` (新增修改)

*   **变更**:
    1.  新增 helper 方法 `_get_conversation_history`：拉取最近 6-7 条消息 (`desc=True`)，然后反转回时间正序。
    2.  **接口更新**: 更新了 `KnowledgeBaseHandler` 的 `.process` 和 `.process_stream` 签名，增加了 `history` 参数。
    3.  **参数透传**: 在 `handle` 方法中，将 `history`、`message`、`session_id`、`agent_type` 等关键参数完整传递给下一层执行器。

### 3.3 连接层 (Ports & Adapters)

**文件**:
*   `backend/application/ports/*` (ChatCompletionPort, RAGExecutorPort, RAGStreamExecutorPort)
*   `backend/infrastructure/rag/adapters/*`

*   **变更**: 更新了所有相关接口 (`generate`, `run`, `stream`) 的签名，新增 `history: list[dict] | None` 参数，确保数据能透传到底层。

### 3.4 模型调用层 (LLM Infrastructure)

**文件**: `backend/infrastructure/llm/completion.py`

*   **变更**:
    1.  引入 LangChain 的 `MessagesPlaceholder`。
    2.  新增 `_convert_history_to_messages`：将字典格式的历史转换为 LangChain 的消息对象。
    3.  更新 Prompt 构建逻辑，在 System Prompt 和 Human Input 之间插入 `MessagesPlaceholder(variable_name="history")`。

## 4. 故障排除与回归修复 (Troubleshooting)

在部署过程中，我们通过三轮调试解决了一些隐蔽问题：

### 4.1 "Ghost Process" 环境问题
*   **现象**：代码已修复，数据库也存入了历史，但 AI 依然“失忆”。
*   **原因**：前端连接的是本地端口 `8324`，但该端口被一个**过期的本地 Python 进程** (PID 16105) 占用，且未随代码更新重启。Docker 容器虽然重启了但并未被使用。
*   **解决**：强制终止僵尸进程，使用虚拟环境 (`.venv`) 重新启动后端服务。

### 4.2 TypeError 回归缺陷 (Regressions)
*   **现象**：服务启动后，请求 API 出现连接中断或不返回任何数据。
*   **原因 1**：在整合 `KB Handler` 时，`StreamHandler.py` 调用 `.process_stream` 漏传了 `message` 和 `session_id`。
*   **原因 2**：在通用 RAG 路径中，`StreamHandler.py` 调用 `_executor.stream` 也漏传了相同参数。
*   **解决**：全面检查并补全了所有层级调用的参数传递，确保 `StreamHandler` -> `KnowledgeBaseHandler` / `RAGStreamExecutor` -> `Adapter` -> `Manager` 的链路完整。

## 5. 验证 (Verification)

*   **脚本验证**: 使用 `scripts/test_conversation_store.py` (已移除) 验证了 DB 层的倒序拉取逻辑。
*   **端到端验证**:
    1.  发送 "推荐几部90年代的高分科幻电影"。
    2.  发送 "请总结以上内容的要点"。
    3.  AI 能够正确输出之前提到的电影列表，证明 `history` 已成功注入。
