# 对话历史管理演进方案设计

**版本**: 1.1.4.1  
**状态**: 设计中  
**作者**: AI Assistant  
**日期**: 2026-01-23

---

## 1. 背景与动机

### 1.1 当前实现（Baseline）

在 v1.1.4 中，我们实现了基础的对话历史注入机制：

```python
# 当前流程
history = await conversation_store.list_messages(limit=6, desc=True)
history.reverse()  # 时间正序
prompt = build_prompt(system + history + current_message)
```

**优点**：
- ✅ 简单直接，易于理解和维护
- ✅ 解决了基本的上下文丢失问题
- ✅ 对短会话（< 10 轮）效果良好

**局限性**：
- ❌ **固定窗口盲区**：超出 N 条的历史被遗忘（如用户在第 1 轮提到的重要信息）
- ❌ **Token 浪费**：每次都传递完整的历史消息，即使内容重复或无关
- ❌ **时间偏见**：只按时间切片，不考虑语义相关性（用户可能跳回之前的话题）
- ❌ **扩展性差**：随着对话变长，成本线性增长

### 1.2 演进目标

构建一个**可扩展、高效、智能**的对话记忆系统，支持：
1. **长期上下文保留**：即使对话超过 100 轮，关键信息不丢失
2. **成本优化**：降低 Token 消耗，提升响应速度
3. **语义感知**：根据相关性而非时间检索历史
4. **架构健壮性**：减少手动参数传递，降低维护成本

---

## 2. 三阶段演进方案

### Phase 1: 记忆压缩与摘要 (Memory Summarization)

#### 2.1.1 核心设计

采用 **滑动窗口 + 历史摘要** 策略：

```
[System Prompt]
[Summary]: "用户之前讨论了90年代科幻电影，特别关注克里斯托弗·诺兰导演作品..."
[Recent Window]: [最近 4-6 条原始对话]
[Current Message]
```

#### 2.1.2 数据模型

**方案 A：扩展现有表**
```sql
ALTER TABLE conversations ADD COLUMN summary TEXT;
ALTER TABLE conversations ADD COLUMN summary_updated_at TIMESTAMP;
ALTER TABLE conversations ADD COLUMN summary_message_count INT DEFAULT 0;
```

**方案 B：独立摘要表（推荐）**
```sql
CREATE TABLE conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    summary TEXT NOT NULL,
    covered_message_count INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(conversation_id)
);
```

#### 2.1.3 实现逻辑

```python
class ConversationSummarizer:
    def __init__(self, llm: BaseChatModel, min_messages: int = 10):
        self.llm = llm  # 使用轻量级模型，如 GPT-3.5-Turbo
        self.min_messages = min_messages
    
    async def should_summarize(self, conversation_id: str) -> bool:
        """判断是否需要生成/更新摘要"""
        message_count = await self.store.count_messages(conversation_id)
        last_summary = await self.store.get_summary(conversation_id)
        
        if message_count < self.min_messages:
            return False
        
        if last_summary is None:
            return True
        
        # 如果新增了 5+ 条消息，更新摘要
        return message_count - last_summary.covered_message_count >= 5
    
    async def generate_summary(self, conversation_id: str) -> str:
        """生成对话摘要"""
        # 获取所有历史消息（除了最近 6 条，它们会保留原文）
        all_messages = await self.store.list_messages(conversation_id)
        to_summarize = all_messages[:-6]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "请将以下对话历史浓缩为简洁的摘要，突出关键信息和用户偏好。"),
            ("user", "{conversation}")
        ])
        
        summary = await self.llm.ainvoke(prompt.format(
            conversation=format_messages(to_summarize)
        ))
        
        # 保存摘要
        await self.store.save_summary(
            conversation_id=conversation_id,
            summary=summary.content,
            covered_message_count=len(to_summarize)
        )
        
        return summary.content
```

#### 2.1.4 集成到 Handler

```python
# in ChatHandler.handle()
async def _get_context(self, conversation_id: str) -> dict:
    # 1. 获取摘要（如果存在）
    summary = await self._summarizer.get_or_generate_summary(conversation_id)
    
    # 2. 获取最近消息
    recent = await self._conversation_store.list_messages(
        conversation_id=conversation_id,
        limit=6,
        desc=True
    )
    recent.reverse()
    
    return {
        "summary": summary,
        "recent_history": recent
    }
```

#### 2.1.5 Prompt 构建调整

```python
# in completion.py
def _build_general_prompt(
    system_message: str,
    memory_context: str | None,
    summary: str | None,  # 新增
    history: list[dict] | None,
    question: str
) -> ChatPromptTemplate:
    messages = [("system", system_message)]
    
    if memory_context:
        messages.append(("system", f"长期记忆：\n{memory_context}"))
    
    if summary:  # 新增摘要注入
        messages.append(("system", f"对话背景：\n{summary}"))
    
    if history:
        messages.append(MessagesPlaceholder(variable_name="history"))
    
    messages.append(("human", "{question}"))
    
    return ChatPromptTemplate.from_messages(messages)
```

#### 2.1.6 优势分析

| 指标 | Baseline | Phase 1 (摘要) |
|------|----------|----------------|
| Token 消耗（50轮对话）| ~8000 | ~2000 |
| 上下文覆盖 | 最近 6 轮 | 全部历史（压缩） |
| 响应延迟 | 基准 | +50ms（摘要生成） |
| 实现复杂度 | 低 | 中 |

---

### Phase 2: 语义检索记忆 (Episodic Memory RAG)

#### 2.2.1 核心设计

将对话历史视为**可检索的知识库**，根据语义相关性而非时间顺序检索。

#### 2.2.2 架构图

```
┌─────────────┐
│ User Query  │
└──────┬──────┘
       │
       ├─────────────────┐
       ↓                 ↓
┌──────────────┐  ┌─────────────────┐
│ Time Window  │  │ Semantic Search │
│ (Recent 3)   │  │ (Milvus Vector) │
└──────┬───────┘  └────────┬────────┘
       │                   │
       └─────┬─────────────┘
             ↓
      ┌─────────────┐
      │   Merge +   │
      │  Deduplicate│
      └──────┬──────┘
             ↓
       [LLM Prompt]
```

#### 2.2.3 数据模型

**复用 Mem0 基础设施**（已有 Milvus + Postgres）

```sql
-- 扩展 messages 表
ALTER TABLE messages ADD COLUMN embedding vector(1536);
CREATE INDEX ON messages USING ivfflat (embedding vector_cosine_ops);
```

或者使用独立的向量存储（推荐，避免污染 messages 表）：

```python
# 在 Milvus 中创建新 Collection
conversation_episodes_collection = {
    "name": "conversation_episodes",
    "fields": [
        {"name": "id", "type": "VARCHAR", "is_primary": True},
        {"name": "conversation_id", "type": "VARCHAR"},
        {"name": "user_message", "type": "VARCHAR"},
        {"name": "assistant_message", "type": "VARCHAR"},
        {"name": "embedding", "type": "FLOAT_VECTOR", "dim": 1536},
        {"name": "created_at", "type": "INT64"},
    ]
}
```

#### 2.2.4 实现逻辑

```python
class ConversationEpisodicMemory:
    def __init__(self, milvus_client, embedding_model):
        self.milvus = milvus_client
        self.embedding_model = embedding_model
    
    async def index_episode(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str
    ):
        """将一轮对话索引为一个 Episode"""
        # 将 Q&A 拼接后向量化
        text = f"User: {user_message}\nAssistant: {assistant_message}"
        embedding = await self.embedding_model.embed_query(text)
        
        await self.milvus.insert({
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "embedding": embedding,
            "created_at": int(time.time())
        })
    
    async def recall_relevant(
        self,
        conversation_id: str,
        query: str,
        top_k: int = 3
    ) -> list[dict]:
        """检索语义相关的历史片段"""
        query_embedding = await self.embedding_model.embed_query(query)
        
        results = await self.milvus.search(
            collection_name="conversation_episodes",
            data=[query_embedding],
            filter=f"conversation_id == '{conversation_id}'",
            limit=top_k,
            output_fields=["user_message", "assistant_message", "created_at"]
        )
        
        return [
            {
                "role": "user",
                "content": hit["user_message"],
                "timestamp": hit["created_at"]
            },
            {
                "role": "assistant",
                "content": hit["assistant_message"],
                "timestamp": hit["created_at"]
            }
            for hit in results[0]
        ]
```

#### 2.2.5 集成到 Handler

```python
async def _get_hybrid_history(
    self,
    conversation_id: str,
    current_query: str
) -> list[dict]:
    # 1. 时间窗口：最近 3 轮
    recent = await self._conversation_store.list_messages(
        conversation_id=conversation_id,
        limit=6,  # 3 轮 * 2 消息
        desc=True
    )
    recent.reverse()
    
    # 2. 语义窗口：相关的历史片段
    relevant = await self._episodic_memory.recall_relevant(
        conversation_id=conversation_id,
        query=current_query,
        top_k=3
    )
    
    # 3. 合并去重（避免重复）
    seen_content = {msg["content"] for msg in recent}
    unique_relevant = [
        msg for msg in relevant
        if msg["content"] not in seen_content
    ]
    
    # 4. 排序：相关片段 + 最近消息
    return unique_relevant + recent
```

#### 2.2.6 优势分析

| 场景 | Baseline | Phase 2 |
|------|----------|---------|
| "刚才说的那个导演是谁"（10 轮前）| ❌ 遗忘 | ✅ 召回 |
| "回到之前讨论的科幻电影话题"| ❌ 需用户重述 | ✅ 自动召回 |
| Token 效率 | 固定 N 条 | 动态选择相关内容 |

---

### Phase 3: 架构重构 (LangGraph State Machine)

#### 2.3.1 问题诊断

**当前参数传递链路**（脆弱）：
```
StreamHandler
  ├─> KBHandler.process_stream(message, session_id, agent_type, history, ...)
  │     └─> RAGStreamExecutor.stream(plan, message, session_id, kb_prefix, history, ...)
  │           └─> RagManager.run_plan_blocking(plan, message, session_id, history, ...)
  │                 └─> generate_rag_answer(message, context, history, ...)
  └─> _executor.stream(plan, message, session_id, kb_prefix, history, ...)
```

**问题**：
- 任何一层漏传参数 → `TypeError`
- 新增参数需修改 6+ 个文件
- 测试成本高（集成测试才能发现问题）

#### 2.3.2 LangGraph 解决方案

**核心理念**：用 **State** 替代 "参数透传"

```python
from langgraph.graph import StateGraph
from typing import TypedDict, Annotated
from operator import add

class ConversationState(TypedDict):
    """对话全局状态"""
    # 核心数据
    messages: Annotated[list[BaseMessage], add]  # 自动追加
    user_id: str
    session_id: str
    conversation_id: str
    
    # 上下文
    memory_context: str | None
    conversation_summary: str | None
    episodic_memory: list[dict] | None
    
    # 决策
    kb_prefix: str | None
    agent_type: str
    use_retrieval: bool
    
    # 检索结果
    retrieval_results: list[dict] | None
    
    # 元数据
    debug: bool
```

#### 2.3.3 节点设计

```python
from langgraph.graph import StateGraph, START, END

# 1. 路由节点
async def route_node(state: ConversationState) -> ConversationState:
    decision = router.route(
        message=state["messages"][-1].content,
        session_id=state["session_id"]
    )
    return {
        **state,
        "kb_prefix": decision.kb_prefix,
        "agent_type": decision.agent_type,
        "use_retrieval": decision.kb_prefix not in ["", "general"]
    }

# 2. 记忆召回节点
async def recall_node(state: ConversationState) -> ConversationState:
    # 长期记忆
    memory_context = await memory_service.recall_context(
        user_id=state["user_id"],
        query=state["messages"][-1].content
    )
    
    # 对话摘要
    summary = await summarizer.get_summary(state["conversation_id"])
    
    # 语义记忆
    episodic = await episodic_memory.recall_relevant(
        conversation_id=state["conversation_id"],
        query=state["messages"][-1].content
    )
    
    return {
        **state,
        "memory_context": memory_context,
        "conversation_summary": summary,
        "episodic_memory": episodic
    }

# 3. 检索节点（条件执行）
async def retrieve_node(state: ConversationState) -> ConversationState:
    if not state["use_retrieval"]:
        return state
    
    results = await rag_executor.retrieve(
        query=state["messages"][-1].content,
        kb_prefix=state["kb_prefix"]
    )
    
    return {**state, "retrieval_results": results}

# 4. 生成节点
async def generate_node(state: ConversationState) -> ConversationState:
    # 构建 Prompt（自动包含 State 中的所有上下文）
    response = await llm.ainvoke(
        build_prompt_from_state(state),
        callbacks=[get_langfuse_callback()]
    )
    
    # 追加到 messages（自动合并）
    return {
        **state,
        "messages": [AIMessage(content=response.content)]
    }

# 5. 持久化节点
async def persist_node(state: ConversationState) -> ConversationState:
    await conversation_store.append_message(
        conversation_id=state["conversation_id"],
        role="assistant",
        content=state["messages"][-1].content
    )
    
    # 异步索引到 Episodic Memory
    asyncio.create_task(
        episodic_memory.index_episode(
            conversation_id=state["conversation_id"],
            user_message=state["messages"][-2].content,
            assistant_message=state["messages"][-1].content
        )
    )
    
    return state
```

#### 2.3.4 Graph 编排

```python
builder = StateGraph(ConversationState)

# 添加节点
builder.add_node("route", route_node)
builder.add_node("recall", recall_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("generate", generate_node)
builder.add_node("persist", persist_node)

# 定义边
builder.add_edge(START, "route")
builder.add_edge("route", "recall")
builder.add_edge("recall", "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", "persist")
builder.add_edge("persist", END)

# 编译
graph = builder.compile()
```

#### 2.3.5 HTTP 层调用

```python
# in chat_stream.py
async def stream_chat(request: ChatRequest):
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_id": request.user_id,
        "session_id": request.session_id,
        "conversation_id": await get_or_create_conversation_id(...),
        "debug": request.debug,
        "agent_type": request.agent_type,
    }
    
    async for event in graph.astream(initial_state):
        # 流式输出每个节点的结果
        yield event
```

#### 2.3.6 优势对比

| 维度 | 当前架构 | LangGraph |
|------|---------|-----------|
| 参数传递 | 手动 6 层 | 自动（State） |
| 扩展性 | 低（需改 N 个文件） | 高（加节点） |
| 可测试性 | 集成测试 | 单元测试（每个节点） |
| 可观测性 | 手动埋点 | 内置（每节点自动 trace） |
| 支持反思/工具调用 | 困难 | 天然支持（加 Loop） |

---

## 3. 实施路线图

| 阶段 | 工作量（人天） | 风险 | 优先级 |
|------|---------------|------|--------|
| **Phase 1: 摘要** | 3-5 | 低 | **P0** |
| **Phase 2: 语义检索** | 5-7 | 中 | P1 |
| **Phase 3: LangGraph** | 10-15 | 高 | P2 |

**建议**：
1. **短期（1-2 周）**：实施 Phase 1，立即降低成本并验证效果
2. **中期（1 个月）**：实施 Phase 2，提升用户体验（特别是长对话场景）
3. **长期（2-3 个月）**：评估 Phase 3，作为架构升级的技术储备

---

## 4. 附录

### 4.1 成本对比（估算）

**假设**：1000 次对话/天，平均每对话 20 轮

| 方案 | 月 Token 消耗 | 成本（GPT-4） | 节省 |
|------|--------------|--------------|------|
| Baseline | 120M | $3600 | - |
| + Phase 1 | 40M | $1200 | 67% |
| + Phase 2 | 35M | $1050 | 71% |

### 4.2 技术依赖

- **Phase 1**: LangChain, PostgreSQL
- **Phase 2**: Milvus, Embedding Model (OpenAI/本地)
- **Phase 3**: LangGraph, asyncio

### 4.3 兼容性

✅ 所有方案向后兼容，可渐进式迁移  
✅ Phase 1/2 可独立部署，不影响现有 API  
✅ Phase 3 需要较大重构，建议通过 Feature Flag 灰度
