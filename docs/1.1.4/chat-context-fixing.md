# 对话历史上下文修复文档

## 背景 (Context)

在之前的版本中，用户反馈 AI 助手在多轮对话中经常“断片”或产生幻觉。例如，当用户追问“谁主演的？”时，AI 无法联系上一轮提到的电影，因为它只接收到了系统提示词和当前问题，丢失了中间的对话历史。

## 问题分析 (Root Cause)

1.  **Prompt 构建缺失**：`completion.py` 中的 Prompt 模板只包含 `System Prompt` 和 `Human Message`，即使检索了 Memory Context（长期记忆），也唯独漏掉了 Short-term Chat History（短期对话历史）。
2.  **Handler 数据流缺失**：`ChatHandler` 和 `StreamHandler` 从未从数据库中拉取最近的对话记录传给 LLM。
3.  **列表顺序问题**：`ConversationStore.list_messages` 默认只支持按时间正序（ASC）拉取，要获取“最近 6 条”需要先取出所有或最后 N 条再倒序，效率较低且接口不支持。

## 解决方案 (Solution)

我们实施了“自底向上”的修复方案，确保最近的对话历史能被正确注入到 Prompt 中。

### 1. 数据库层 (Conversation Store)

**文件**: `backend/infrastructure/persistence/postgres/conversation_store.py`

*   **变更**: `list_messages` 方法增加了 `desc: bool = False` 参数。
*   **作用**: 允许直接通过 SQL `ORDER BY created_at DESC` 高效拉取最新的 N 条消息。

```python
async def list_messages(self, ..., desc: bool = False) -> List[Dict]:
    # ...
    order_dir = "DESC" if desc else "ASC"
    sql += f" ORDER BY created_at {order_dir}"
    # ...
```

### 2. 业务逻辑层 (Handlers)

**文件**:
*   `backend/application/chat/handlers/chat_handler.py`
*   `backend/application/chat/handlers/stream_handler.py`

*   **变更**:
    1.  新增 helper 方法 `_get_conversation_history`：拉取最近 6-7 条消息 (`desc=True`)，然后反转回时间正序 (`reverse()`)。
    2.  在 `handle` 方法中调用该 helper，并将 `history` 列表传递给下一层（Completion 或 Executor）。
    3.  增加去重逻辑：如果历史记录最后一条也是当前 Message（防止数据库已插入导致重复），则将其移除。

```python
async def _get_conversation_history(self, ...):
    history = await self._conversation_store.list_messages(..., limit=6, desc=True)
    history.reverse() # [Newest, ..., Oldest] -> [Oldest, ..., Newest]
    return history
```

### 3. 连接层 (Ports & Adapters)

**文件**:
*   `backend/application/ports/chat_completion_port.py`
*   `backend/application/ports/rag_executor_port.py`
*   `backend/infrastructure/llm/chat_completion_adapter.py`
*   `backend/infrastructure/rag/adapters/graphrag_executor.py`
*   ... (及其他相关 adapter)

*   **变更**: 更新了所有相关接口 (`generate`, `run`, `stream`) 的签名，新增 `history: list[dict] | None` 参数，确保数据能透传到底层。

### 4. 模型调用层 (LLM Infrastructure)

**文件**: `backend/infrastructure/llm/completion.py`

*   **变更**:
    1.  引入 LangChain 的 `MessagesPlaceholder`。
    2.  新增 `_convert_history_to_messages`：将字典格式的历史 (`[{role: user, content: ...}]`) 转换为 LangChain 的 `HumanMessage` / `AIMessage` 对象。
    3.  更新 `_build_general_prompt` 和 `_build_rag_prompt`，在 System Prompt 和 Human Input 之间插入 `MessagesPlaceholder(variable_name="history")`。

**Prompt 结构变化**:

**Before**:
```text
[System Prompt]
[Current Question]
```

**After**:
```text
[System Prompt]
[Chat History (MessagePlaceholder)] <-- 新增
  User: ...
  AI: ...
[Current Question]
```

## 验证 (Verification)

通过此修复，AI 现在能够理解代词（如“它”、“他”），并基于之前的对话内容进行回答，彻底解决了上下文丢失的问题。
