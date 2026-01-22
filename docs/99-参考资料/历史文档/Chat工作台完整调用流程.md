# Chat 工作台完整调用流程

> 注意：本文基于旧版接口与 legacy 服务（`backend/application/services/chat_service.py` 等），当前已下线；仅供历史参考。

本文档详细描述了 Chat 工作台从用户输入到答案展示的完整调用链路，帮助开发者快速理解系统架构、排查问题和扩展功能。

## 目录

- [1. 快速索引](#1-快速索引)
- [2. 整体架构](#2-整体架构)
- [3. 完整调用流程](#3-完整调用流程)
- [4. 核心机制](#4-核心机制)
- [5. 关键文件速查](#5-关键文件速查)
- [6. 常见问题定位](#6-常见问题定位)

---

## 1. 快速索引

| 问题类型 | 定位位置 | 关键文件 |
| --- | --- | --- |
| 前端无响应/卡顿 | [3.1 前端层](#31-前端层) | `frontend/components/api/v1/chat.py` |
| API 请求失败 | [3.2 路由层](#32-路由层) | `backend/server/api/rest/v1/chat.py` |
| 缓存未命中/响应慢 | [4.1 三层缓存机制](#41-三层缓存机制) | `backend/infrastructure/cache_manager/` |
| Agent 未返回结果 | [3.4 Agent 层](#34-agent-层) | `backend/graphrag_agent/agents/base.py` |
| 检索结果不准确 | [3.5 搜索层](#35-搜索层) | `backend/graphrag_agent/search/` |
| Neo4j 查询错误 | [3.6 数据层](#36-数据层) | `backend/infrastructure/config/neo4jdb.py` |
| 知识图谱不展示 | [3.3 服务层](#33-服务层) | `backend/application/services/kg_service.py` |
| 添加新 Agent | [6.2 扩展 Agent](#62-扩展-agent) | `backend/application/services/agent_service.py` |

---

## 2. 整体架构

### 2.1 数据流向图

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 【前端层】Streamlit                                         │
│ - 收集用户输入 (chat.py)                                    │
│ - 流式渲染 / 标准展示                                       │
│ - 知识图谱可视化                                            │
└─────────────────────────────────────────────────────────────┘
    │ POST /api/v1/chat | /api/v1/chat/stream
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 【路由层】FastAPI                                           │
│ - 参数校验 (backend/server/api/rest/v1/chat.py)                               │
│ - SSE 流式响应                                              │
│ - 性能监控                                                  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 【服务层】Chat Service                                      │
│ - 并发控制 (ConcurrentManager)                             │
│ - 三层缓存检查 (FastCache/Session/Global)                  │
│ - Agent 分发与管理                                          │
│ - 知识图谱提取                                              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 【Agent 层】LangGraph Workflow                              │
│ - BaseAgent 工作流引擎                                      │
│ - 多轮对话状态管理 (MemorySaver)                           │
│ - 工具调用决策                                              │
│ - 流式/非流式生成                                           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 【搜索层】Search Tools                                      │
│ - LocalSearch: 实体中心检索                                 │
│ - GlobalSearch: 社区级聚合                                  │
│ - DeepResearch: 多轮推理链                                  │
│ - RAG Chain 编排                                            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 【数据层】Neo4j + Vector Index                             │
│ - 实体/关系图谱存储                                         │
│ - 向量索引 (entity_index / chunk_index)                    │
│ - 社区检测数据                                              │
│ - Cypher 查询执行                                           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 【LLM 推理】                                                │
│ - 问答生成                                                  │
│ - 工具调用决策                                              │
│ - 流式输出                                                  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
前端展示 (答案 + KG + Debug 信息)
```

### 2.2 核心组件关系

- **数据流向**: 前端 → API 网关 → 服务层 → Agent 层 → 搜索/数据层 → LLM
- **缓存系统**: 贯穿服务层和 Agent 层，提供多级加速
- **并发控制**: 在服务层保证同会话串行执行
- **知识图谱提取**: 从 LLM 输出中解析实体关系，支持前端可视化

---

## 3. 完整调用流程

### 3.1 前端层

**文件位置**: `frontend/components/api/v1/chat.py:318-520`

#### 核心职责

1. **用户输入捕获**: 使用 `st.chat_input` 收集问题
2. **并发控制**: 通过 `st.session_state.processing_lock` 防止重复提交
3. **消息渲染**: 实时展示用户消息和 AI 回复
4. **流式输出**: 逐 token 渲染 AI 回复，提升用户体验
5. **知识图谱展示**: Debug 模式下自动提取并可视化实体关系

#### 关键代码

```python
# frontend/components/api/v1/chat.py:318-430
if prompt := st.chat_input("请输入您的问题...", key="chat_input"):
    # 1. 并发控制
    if st.session_state.processing_lock:
        st.warning("请等待当前操作完成...")
        return

    st.session_state.processing_lock = True

    # 2. 展示用户消息
    with st.chat_message("user"):
        st.write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 3. 调用 API (流式/非流式)
    if st.session_state.stream_output:
        response = send_message_stream(prompt, ...)
    else:
        response = send_message(prompt, ...)

    # 4. 展示 AI 回复
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        for chunk in response:
            full_response += chunk
            message_placeholder.markdown(full_response + "▌")

        message_placeholder.markdown(full_response)

    # 5. 释放锁
    st.session_state.processing_lock = False
```

#### API 封装层

**文件位置**: `frontend/utils/api.py:14-142`

```python
def send_message_stream(message: str, session_id: str, agent_type: str, debug: bool):
    """流式 API 调用"""
    params = {
        "message": message,
        "session_id": session_id,
        "agent_type": agent_type,
        "debug": debug,
    }

    # 特定 Agent 的额外参数
    if agent_type == "deep_research_agent":
        params["use_deeper_tool"] = st.session_state.get("use_deeper_tool", True)
        params["show_thinking"] = st.session_state.get("show_thinking", False)

    response = requests.post(
        f"{API_URL}/api/v1/chat/stream",
        json=params,
        stream=True,
        # timeout=120  # 深度研究可能超时，建议注释
    )

    # SSE 解析
    for event in sseclient.SSEClient(response).events():
        data = json.loads(event.data)
        if data["type"] == "token":
            yield data["content"]
        elif data["type"] == "thinking":
            st.sidebar.write(data["content"])
```

---

### 3.2 路由层

**文件位置**: `backend/server/api/rest/v1/chat.py`（非流式） + `backend/server/api/rest/v1/chat_stream.py`（SSE）

#### 核心职责

1. **请求校验**: 使用 Pydantic 模型验证参数
2. **路由分发**: `/api/v1/chat` (标准) 和 `/api/v1/chat/stream` (流式)
3. **SSE 封装**: 将流式输出包装为 Server-Sent Events
4. **性能监控**: 记录请求耗时和吞吐量

#### 关键代码

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    handler: ChatHandler = Depends(get_chat_handler),
):
    return await handler.handle(
        message=request.message,
        session_id=request.session_id,
        kb_prefix=request.kb_prefix,
        debug=request.debug,
        agent_type=request.agent_type,
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    handler: StreamHandler = Depends(get_stream_handler),
):
    async def event_generator():
        sent_done = False
        yield format_sse({"status": "start"})

        async for event in handler.handle(
            message=request.message,
            session_id=request.session_id,
            kb_prefix=request.kb_prefix,
            debug=request.debug,
            agent_type=request.agent_type,
        ):
            payload = event
            if isinstance(event, dict) and "execution_log" in event:
                payload = {"status": "execution_log", "content": event["execution_log"]}
            elif not isinstance(event, dict):
                payload = {"status": "token", "content": str(event)}

            if isinstance(payload, dict) and payload.get("status") == "done":
                sent_done = True
            yield format_sse(payload)

        if not sent_done:
            yield format_sse({"status": "done"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

---

### 3.3 用例编排层

**文件位置**: `backend/application/chat/handlers/chat_handler.py` + `backend/application/chat/handlers/stream_handler.py`

#### 核心职责

1. **路由决策**: `RouterGraphAdapter` 选择 KB 与 worker
2. **执行计划**: 构造 `RagRunSpec` 并调用执行器
3. **结果聚合**: `RagManager` 汇总检索与生成结果
4. **流式输出**: SSE 事件封装与 `done` 兜底

#### 处理流程

```python
async def handle(message: str, session_id: str, kb_prefix: str, debug: bool):
    decision = router.route(...)
    plan = [RagRunSpec(agent_type=agent_type)]
    aggregated, runs = await executor.run(..., kb_prefix=decision.kb_prefix)
    return {"answer": aggregated.answer, "rag_runs": [...], "route_decision": ...}
```

---

### 3.4 Agent 层

**文件位置**: `backend/graphrag_agent/agents/base.py:81-420`

#### 核心职责

1. **LangGraph 工作流**: START → agent → retrieve → generate → END
2. **多轮对话**: 使用 MemorySaver 保存会话状态
3. **工具调用**: Zero-shot tool selection
4. **流式生成**: 模拟流式输出

#### LangGraph 工作流

```python
# backend/graphrag_agent/agents/base.py
def _setup_graph(self):
    """构建 LangGraph 工作流"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("agent", self._agent_node)          # 关键词提取 + 工具决策
    workflow.add_node("retrieve", ToolNode(self.tools))   # 工具执行
    workflow.add_node("generate", self._generate_node)    # 答案生成

    # 定义边
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        tools_condition,  # 判断是否需要调用工具
        {"tools": "retrieve", END: END},
    )
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)

    # 编译并添加 checkpointer
    self.graph = workflow.compile(checkpointer=self.memory)

# Agent 节点
def _agent_node(self, state):
    """处理用户消息，决定是否调用工具"""
    messages = state["messages"]
    last_message = messages[-1]

    # 提取关键词
    keywords = self._extract_keywords(last_message.content)

    # 附加 metadata
    human_message = HumanMessage(
        content=last_message.content,
        metadata={"keywords": keywords}
    )

    # LLM 推理 (可能产生 tool_calls)
    response = self.llm.invoke([human_message])

    return {"messages": [response]}

# 生成节点 (由子类实现)
def _generate_node(self, state):
    """基于检索结果生成答案"""
    messages = state["messages"]

    # 提取工具消息
    tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
    context = "\n".join([msg.content for msg in tool_messages])

    # 生成答案
    prompt = f"基于以下检索结果回答用户问题：\n{context}\n用户问题：{messages[0].content}"
    response = self.llm.invoke([HumanMessage(prompt)])

    return {"messages": [response]}
```

#### 缓存策略

```python
# 三层缓存
def check_fast_cache(self, message: str, session_id: str) -> Optional[str]:
    """L1: 快速缓存 - 高质量会话缓存"""
    cache_key = f"{session_id}:{message}"
    return self.fast_cache.get(cache_key)

def _check_session_cache(self, message: str, session_id: str) -> Optional[str]:
    """L2: 会话缓存 - Context-aware key"""
    return self.cache_manager.get(message, session_id)

def _check_global_cache(self, message: str) -> Optional[str]:
    """L3: 全局缓存 - 跨会话共享"""
    return self.global_cache_manager.get(message)
```

---

### 3.5 搜索层

**文件位置**: `backend/graphrag_agent/search/tool/local_search_tool.py:24-190`

#### 核心职责

1. **关键词提取**: 基于 LLM 的智能关键词提取
2. **向量检索**: 联合实体索引和 chunk 索引
3. **RAG Chain**: LangChain 检索链编排
4. **上下文聚合**: 合并实体、关系、社区、chunk

#### 本地搜索工具

```python
class LocalSearchTool:
    def __init__(self, llm, embeddings):
        # 初始化搜索器
        self.local_searcher = LocalSearch(llm, embeddings)
        self.retriever = self.local_searcher.as_retriever()

        # 构建 history-aware retriever
        self.history_aware_retriever = create_history_aware_retriever(
            llm,
            self.retriever,
            contextualize_q_prompt,  # 重写问题
        )

        # 构建 QA chain
        self.question_answer_chain = create_stuff_documents_chain(
            llm,
            lc_prompt_with_history
        )

        # 组装 RAG chain
        self.rag_chain = create_retrieval_chain(
            self.history_aware_retriever,
            self.question_answer_chain
        )

    def search(self, query: str, chat_history: List) -> str:
        """执行本地搜索"""
        result = self.rag_chain.invoke({
            "input": query,
            "chat_history": chat_history
        })

        return result["answer"]
```

#### 其他搜索工具

- **GlobalSearchTool**: 社区级聚合，Map-Reduce 式扫描
- **DeepResearchTool**: 多轮推理链，Chain of Exploration
- **NaiveSearchTool**: 基础向量检索

---

### 3.6 数据层

**文件位置**: `backend/graphrag_agent/search/local_search.py`, `backend/infrastructure/config/neo4jdb.py`

#### Neo4j 向量检索

```python
# backend/graphrag_agent/search/local_search.py
class LocalSearch:
    def __init__(self, llm, embeddings):
        self.llm = llm
        self.embeddings = embeddings

        # 连接 Neo4j 向量索引
        self.vector_store = Neo4jVector.from_existing_index(
            embeddings,
            url=settings.NEO4J_URI,
            username=settings.NEO4J_USERNAME,
            password=settings.NEO4J_PASSWORD,
            index_name="entity_index",  # 或 chunk_index
            retrieval_query=self._build_retrieval_query(),
        )

    def _build_retrieval_query(self) -> str:
        """构建复杂的 Cypher 检索查询"""
        return """
        // 获取实体
        MATCH (node:`__Entity__`)
        WHERE node.id = $entity_id

        // 获取邻居
        OPTIONAL MATCH (node)-[r]->(neighbor)

        // 获取社区摘要
        OPTIONAL MATCH (node)-[:IN_COMMUNITY]->(community)

        // 获取相关 chunks
        OPTIONAL MATCH (node)<-[:MENTIONS]-(chunk:`__Chunk__`)

        RETURN node, collect(DISTINCT r) as relationships,
               collect(DISTINCT neighbor) as neighbors,
               collect(DISTINCT community.summary) as community_summaries,
               collect(DISTINCT chunk.text) as chunks
        LIMIT $topChunks
        """

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """向量相似度搜索"""
        docs = self.vector_store.similarity_search(
            query,
            k=k,
            params={
                "topChunks": 10,
                "topCommunities": 3
            }
        )
        return docs
```

#### 数据库连接管理

```python
# backend/infrastructure/config/neo4jdb.py
class DBConnectionManager:
    """Neo4j 连接单例管理"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.neo4j_graph = Neo4jGraph(
                url=settings.NEO4J_URI,
                username=settings.NEO4J_USERNAME,
                password=settings.NEO4J_PASSWORD
            )
        return cls._instance

    def execute_query(self, query: str, params: dict = None):
        """执行 Cypher 查询"""
        return self.neo4j_graph.query(query, params)
```

---

## 4. 核心机制

### 4.1 三层缓存机制

**文件位置**: `backend/infrastructure/cache_manager/manager.py`

```python
# L1: 快速缓存 (10ms 级响应)
fast_result = selected_agent.check_fast_cache(message, session_id)
if fast_result:
    return {"answer": fast_result}

# L2: 会话缓存 (Context-aware, 60%+ 命中率)
session_result = cache_manager.get(message, session_id)
if session_result:
    return {"answer": session_result}

# L3: 全局缓存 (跨会话共享)
global_result = global_cache_manager.get(message)
if global_result:
    return {"answer": global_result}
```

**缓存策略**:
- **Fast Cache**: 存储高质量会话缓存，key = `session_id:message`
- **Session Cache**: Context-aware key，结合 `thread_id` 和关键词
- **Global Cache**: 跨会话共享，常见问题缓存

### 4.2 并发控制（线程锁机制）

**文件位置**: `backend/infrastructure/utils/concurrent.py`

#### 4.2.1 ConcurrentManager 设计

`ConcurrentManager` 是一个基于 `threading.Lock` 的分布式锁管理器，用于防止同一会话的并发请求冲突。

**核心数据结构**:

```python
class ConcurrentManager:
    def __init__(self, timeout_seconds=300, lock_wait_timeout=10):
        # 锁池：每个 key 对应一个独立的 threading.Lock
        self.locks: Dict[str, threading.Lock] = {}

        # 时间戳池：记录锁的最后活跃时间
        self.timestamps: Dict[str, float] = {}

        # 锁超时时间（默认 5 分钟）
        self.timeout_seconds = timeout_seconds

        # 获取锁时的最大等待时间（默认 10 秒）
        self.lock_wait_timeout = lock_wait_timeout
```

**数据结构示例**:

```python
locks = {
    "session_001_chat": <threading.Lock object at 0x7f8b8c1>,
    "session_002_chat": <threading.Lock object at 0x7f8b8c2>,
}

timestamps = {
    "session_001_chat": 1735454400.123,  # Unix 时间戳
    "session_002_chat": 1735454450.456,
}
```

#### 4.2.2 核心方法实现

**获取锁对象**:

```python
def get_lock(self, key: str) -> threading.Lock:
    """获取或创建锁对象（懒加载）"""
    if key not in self.locks:
        self.locks[key] = threading.Lock()
        self.timestamps[key] = time.time()
    return self.locks[key]
```

**尝试获取锁（核心方法）**:

```python
def try_acquire_lock(self, key: str, wait: bool = False) -> bool:
    """
    尝试获取锁

    Args:
        key: 锁键名（如 "session_001_chat"）
        wait: 是否等待锁释放

    Returns:
        bool: 是否成功获取锁
    """
    lock = self.get_lock(key)

    if wait:
        # 等待模式：最多等待 lock_wait_timeout 秒
        return lock.acquire(blocking=True, timeout=self.lock_wait_timeout)
    else:
        # 非阻塞模式：立即返回（默认）
        return lock.acquire(blocking=False)
```

**释放锁**:

```python
def release_lock(self, key: str) -> None:
    """释放锁（带安全检查）"""
    if key in self.locks and self.locks[key].locked():
        self.locks[key].release()
```

**清理过期锁**:

```python
def cleanup_expired_locks(self) -> None:
    """清理超过 timeout_seconds 未更新的锁"""
    current_time = time.time()
    expired_keys = []

    for key, timestamp in self.timestamps.items():
        if current_time - timestamp > self.timeout_seconds:
            expired_keys.append(key)

    for key in expired_keys:
        if key in self.locks:
            try:
                if self.locks[key].locked():
                    # 强制释放长时间持有的锁
                    self.locks[key].release()
                del self.locks[key]
            except:
                pass
        if key in self.timestamps:
            del self.timestamps[key]
```

#### 4.2.3 threading.Lock 详解

**基本操作**:

```python
import threading

lock = threading.Lock()

# 1. 获取锁
lock.acquire()                          # 阻塞直到获取锁
lock.acquire(blocking=False)            # 非阻塞，立即返回 True/False
lock.acquire(blocking=True, timeout=5)  # 最多等待 5 秒

# 2. 释放锁
lock.release()

# 3. 检查状态
lock.locked()  # True: 已锁定, False: 未锁定
```

**上下文管理器（推荐）**:

```python
# 方式 1: 手动管理（不推荐）
lock.acquire()
try:
    # 临界区代码
    pass
finally:
    lock.release()

# 方式 2: with 语句（推荐）
with lock:
    # 临界区代码
    pass
# 自动释放锁
```

**Lock vs RLock**:

| 特性 | threading.Lock | threading.RLock |
|------|----------------|-----------------|
| 可重入 | ❌ 否 | ✅ 是 |
| 性能 | 更好 | 稍差 |
| 同一线程重复获取 | 死锁 | 允许（需要相同次数 release） |
| 使用场景 | 简单场景 | 递归场景 |

#### 4.2.4 实际使用场景

**Chat 请求并发控制** (`backend/application/services/chat_service.py:34-44`):

```python
# 1. 生成锁键
lock_key = f"{session_id}_chat"

# 2. 尝试获取锁（非阻塞）
lock_acquired = chat_manager.try_acquire_lock(lock_key)

if not lock_acquired:
    # 锁已被占用，返回 429 错误
    raise HTTPException(
        status_code=429,
        detail="当前有其他请求正在处理，请稍后再试"
    )

try:
    # 3. 更新时间戳（防止被当作过期锁）
    chat_manager.update_timestamp(lock_key)

    # 4. 处理业务逻辑
    selected_agent = agent_manager.get_agent(agent_type)
    result = selected_agent.ask(message, thread_id=session_id)

finally:
    # 5. 释放锁
    chat_manager.release_lock(lock_key)

    # 6. 清理过期锁
    chat_manager.cleanup_expired_locks()
```

**工作流程**:

```
用户 A 发送请求
    │
    ▼
try_acquire_lock("001_chat")
    │
    ├─ 成功 ✅ ──────▶ 处理请求 ──▶ 释放锁
    │                     │
    │                     ▼
    │              返回正常响应
    │
    └─ 失败 ❌ ──────▶ 返回 429 错误
         (锁被占用)     "请稍后再试"
```

**防止重复提交示例**:

```
时间轴 ─────────────────────────────────▶

t=0s   用户点击"发送"
       ├─ 获取锁 ✅
       └─ 开始处理...

t=2s   用户再次点击（误操作）
       ├─ 尝试获取锁 ❌ (锁被占用)
       └─ 返回 429: "请稍后再试"

t=10s  第一个请求完成
       ├─ 释放锁
       └─ 现在可以再次发送
```

#### 4.2.5 两层防护机制

系统使用两层锁机制保证并发安全：

**外层防护 - ConcurrentManager**:
- **目的**: 防止同一会话的重复请求
- **粒度**: session_id 级别
- **锁类型**: `threading.Lock`（普通锁）
- **模式**: 非阻塞（快速失败）

**内层防护 - AgentManager**:
- **目的**: 保护 Agent 实例池数据一致性
- **粒度**: 全局
- **锁类型**: `threading.RLock`（可重入锁）
- **模式**: 阻塞（等待获取）

**调用链路**:

```
HTTP 请求
  │
  ▼
【外层】ConcurrentManager.try_acquire_lock()
  │  └─ 防止用户重复提交
  │  └─ 锁粒度: f"{session_id}_chat"
  │  └─ 非阻塞模式
  │
  ▼
【内层】AgentManager.get_agent()
  │  with self.agent_lock:
  │     └─ 保护实例池
  │     └─ 锁粒度: 全局
  │     └─ 阻塞模式
  │
  ▼
业务处理
```

**对比表**:

| 特性 | ConcurrentManager 锁 | AgentManager 锁 |
|------|---------------------|-----------------|
| 锁类型 | `threading.Lock` | `threading.RLock` |
| 数量 | 多个（每个 key 一个） | 1 个全局锁 |
| 可重入 | ❌ 否 | ✅ 是 |
| 粒度 | 细粒度（会话级） | 粗粒度（全局） |
| 阻塞方式 | 非阻塞 | 阻塞 |
| 超时清理 | ✅ 有 | ❌ 无 |

#### 4.2.6 应用场景

**全局实例**:

```python
# backend/infrastructure/utils/concurrent.py:98-99

# Chat 请求锁管理
chat_manager = ConcurrentManager()

# 反馈请求锁管理
feedback_manager = ConcurrentManager()
```

**锁键命名规范**:

- Chat 请求: `f"{session_id}_chat"`
- 反馈处理: `f"{session_id}_feedback"`

**配置参数**:

```python
ConcurrentManager(
    timeout_seconds=300,      # 锁超时时间（5 分钟）
    lock_wait_timeout=10,     # 等待模式最大等待时间（10 秒）
)
```

---

### 4.3 Agent 实例池管理

**文件位置**: `backend/application/services/agent_service.py`

#### 4.3.1 AgentManager 设计

`AgentManager` 是一个 **Agent 实例池管理器**，负责为每个会话创建和维护独立的 Agent 实例。

**核心职责**:

1. ✅ **Agent 类型注册** - 管理所有可用的 Agent 类型
2. ✅ **实例池管理** - 为每个会话创建和维护独立的 Agent 实例
3. ✅ **线程安全** - 使用锁保证并发访问安全
4. ✅ **会话隔离** - 每个 session_id 拥有独立的 Agent 实例
5. ✅ **历史清理** - 清除特定会话的聊天历史
6. ✅ **资源管理** - 关闭所有 Agent 资源

**类结构**:

```python
class AgentManager:
    def __init__(self):
        # 1. 注册 Agent 类型映射
        self.agent_classes = {
            "graph_agent": GraphAgent,
            "hybrid_agent": HybridAgent,
            "naive_rag_agent": NaiveRagAgent,
            "deep_research_agent": DeepResearchAgent,
            "fusion_agent": FusionGraphRAGAgent,
        }

        # 2. 创建实例池（空字典）
        self.agent_instances = {}

        # 3. 创建线程锁（RLock 支持重入）
        self.agent_lock = threading.RLock()
```

#### 4.3.2 核心数据结构

**实例池结构**:

```python
agent_instances = {
    "hybrid_agent:session-001": <HybridAgent 实例 A>,
    "hybrid_agent:session-002": <HybridAgent 实例 B>,
    "deep_research_agent:session-001": <DeepResearchAgent 实例 C>,
    "graph_agent:session-003": <GraphAgent 实例 D>,
}
```

**实例键格式**: `"{agent_type}:{session_id}"`

**示例**:
- 用户 A 使用 Hybrid Agent → `"hybrid_agent:user_a"`
- 用户 B 使用 Hybrid Agent → `"hybrid_agent:user_b"`
- 用户 A 使用 Deep Research → `"deep_research_agent:user_a"`

#### 4.3.3 get_agent() 方法 - 核心实现 ⭐

```python
def get_agent(self, agent_type: str, session_id: str = "default"):
    """
    获取指定类型的Agent，对每个会话使用独立实例

    Args:
        agent_type: Agent类型 (graph_agent/hybrid_agent/...)
        session_id: 会话ID

    Returns:
        Agent实例
    """
    # 1. 校验 Agent 类型
    if agent_type not in self.agent_classes:
        raise ValueError(f"未知的agent类型: {agent_type}")

    # 2. 生成实例唯一 key: "agent_type:session_id"
    instance_key = f"{agent_type}:{session_id}"

    # 3. 线程安全地获取/创建实例
    with self.agent_lock:
        if instance_key not in self.agent_instances:
            # 创建新的 Agent 实例
            self.agent_instances[instance_key] = self.agent_classes[agent_type]()

        return self.agent_instances[instance_key]
```

**工作流程**:

```
用户请求 (agent_type="hybrid_agent", session_id="abc123")
    │
    ▼
生成 instance_key = "hybrid_agent:abc123"
    │
    ▼
检查实例池
    │
    ├─ 存在 ─────────────▶ 直接返回现有实例
    │                       │
    │                       ▼
    │                  复用实例（保留上下文）
    │
    └─ 不存在 ──▶ 创建新实例 ──▶ 加入实例池 ──▶ 返回实例
                      │
                      ▼
                 初始化 LangGraph、Memory、Tools
```

#### 4.3.4 会话隔离机制

**设计原则**: **一个会话 + 一个 Agent 类型 = 一个独立实例**

**多用户并发场景**:

```
用户 A (session_id="001") + 用户 B (session_id="002")
同时请求 hybrid_agent
    ┌─────────────────┐         ┌─────────────────┐
    │  Session: 001   │         │  Session: 002   │
    └────────┬────────┘         └────────┬────────┘
             │                           │
             ▼                           ▼
    get_agent("hybrid", "001")  get_agent("hybrid", "002")
             │                           │
             ▼                           ▼
    instance_key =              instance_key =
    "hybrid_agent:001"          "hybrid_agent:002"
             │                           │
             └────────┬──────────────────┘
                      ▼
            【线程锁保护并发创建】
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
   创建实例 A                  创建实例 B
   HybridAgent()              HybridAgent()
         │                         │
         └────────────┬────────────┘
                      ▼
            【实例池最终状态】
    {
      "hybrid_agent:001": <HybridAgent A>,  # 用户 A 专属
      "hybrid_agent:002": <HybridAgent B>   # 用户 B 专属
    }
```

**关键**: 两个用户拥有完全独立的 Agent 实例，互不干扰！

#### 4.3.5 实例池增长示例

```python
# 初始状态
agent_instances = {}

# 请求 1: user_a 使用 hybrid_agent
get_agent("hybrid_agent", "user_a")
agent_instances = {
    "hybrid_agent:user_a": <HybridAgent>
}

# 请求 2: user_a 使用 deep_research_agent
get_agent("deep_research_agent", "user_a")
agent_instances = {
    "hybrid_agent:user_a": <HybridAgent>,
    "deep_research_agent:user_a": <DeepResearchAgent>
}

# 请求 3: user_b 使用 hybrid_agent
get_agent("hybrid_agent", "user_b")
agent_instances = {
    "hybrid_agent:user_a": <HybridAgent>,
    "deep_research_agent:user_a": <DeepResearchAgent>,
    "hybrid_agent:user_b": <HybridAgent>
}

# 请求 4: user_a 再次使用 hybrid_agent (复用)
get_agent("hybrid_agent", "user_a")
# 实例池不变，直接返回已有实例
# agent1 is agent2 → True (同一对象)
```

#### 4.3.6 实例复用优势

```python
# 第 1 次请求: 创建新实例
agent1 = agent_manager.get_agent("hybrid_agent", session_id="abc")
agent1.ask("什么是 GraphRAG?")
# Memory 中保存了对话历史

# 第 2 次请求: 复用实例
agent2 = agent_manager.get_agent("hybrid_agent", session_id="abc")
agent2.ask("它有什么优势?")  # 可以理解上下文中的"它"
# agent1 is agent2 → True (同一个对象)

# 好处:
# ✅ 保留会话上下文（Memory）
# ✅ 避免重复初始化（节省资源）
# ✅ 保持缓存状态
# ✅ 支持多轮对话
```

#### 4.3.7 clear_history() - 清除会话历史

```python
def clear_history(self, session_id: str) -> Dict:
    """
    清除特定会话的聊天历史

    工作流程:
    1. 遍历该会话的所有 Agent 实例
    2. 获取每个 Agent 的 memory
    3. 删除消息历史（保留前 2 条）
    """
    with self.agent_lock:
        for agent_type in self.agent_classes.keys():
            instance_key = f"{agent_type}:{session_id}"

            if instance_key in self.agent_instances:
                agent = self.agent_instances[instance_key]
                config = {"configurable": {"thread_id": session_id}}

                # 获取消息历史
                memory_content = agent.memory.get(config)
                if memory_content is None:
                    continue

                messages = memory_content["channel_values"]["messages"]

                # 删除消息（保留前 2 条，通常是系统提示）
                for message in reversed(messages):
                    if len(messages) <= 2:
                        break
                    agent.graph.update_state(
                        config,
                        {"messages": RemoveMessage(id=message.id)}
                    )

    return {"status": "success", "remaining_messages": "已清除会话历史"}
```

**关键点**:
- 🗑️ 只删除该会话的历史，不影响其他会话
- 📝 保留前 2 条消息（可能是系统提示词）
- 🔄 使用 LangGraph 的 `RemoveMessage` 机制

#### 4.3.8 线程安全实现

**使用 threading.RLock（可重入锁）**:

```python
self.agent_lock = threading.RLock()

# 为什么用 RLock 而不是 Lock？
# 1. 支持同一线程多次获取锁（可重入）
# 2. 防止递归调用时死锁
# 3. 适合复杂的实例管理场景

with self.agent_lock:
    # 临界区代码
    if instance_key not in self.agent_instances:
        self.agent_instances[instance_key] = ...
```

**并发场景示例**:

```python
# 线程 1
Thread-1: agent_manager.get_agent("hybrid", "session1")
# 线程 2
Thread-2: agent_manager.get_agent("hybrid", "session2")
# 线程 3
Thread-3: agent_manager.get_agent("graph", "session1")

# RLock 保护并发访问
with self.agent_lock:
    # 同一时刻只有一个线程可以修改实例池
    ...
```

#### 4.3.9 与 ConcurrentManager 的配合

**两层防护机制**:

```
HTTP 请求
  │
  ▼
【外层】ConcurrentManager.try_acquire_lock()
  │  └─ 防止同一用户重复提交
  │  └─ 锁粒度: f"{session_id}_chat"
  │  └─ 锁类型: threading.Lock (非阻塞)
  │
  ▼
【内层】AgentManager.get_agent()
  │  with self.agent_lock:
  │     └─ 保护实例池数据一致性
  │     └─ 锁粒度: 全局
  │     └─ 锁类型: threading.RLock (阻塞)
  │
  ▼
Agent 实例执行
```

**对比表**:

| 特性 | ConcurrentManager | AgentManager |
|------|------------------|--------------|
| **目的** | 防止用户重复提交 | 保护实例池 |
| **锁类型** | threading.Lock | threading.RLock |
| **锁粒度** | 细粒度（会话级） | 粗粒度（全局） |
| **可重入** | ❌ 否 | ✅ 是 |
| **阻塞模式** | 非阻塞 | 阻塞 |
| **锁数量** | 多个（每个 key 一个） | 1 个全局锁 |

#### 4.3.10 潜在问题与优化

**问题 1: 内存泄漏风险**

```python
# 用户访问 1000 个不同的 session
for i in range(1000):
    agent_manager.get_agent("hybrid_agent", f"session_{i}")

# 实例池会有 1000 个实例，占用大量内存
```

**解决方案**:

```python
# 添加过期时间戳
self.agent_instances = {
    "hybrid_agent:abc": {
        "instance": <HybridAgent>,
        "last_access": 1735454400,  # Unix 时间戳
    }
}

# 定期清理
def cleanup_expired_agents(self, max_idle_seconds=3600):
    """清理超过 1 小时未使用的 Agent"""
    current_time = time.time()
    with self.agent_lock:
        expired_keys = [
            key for key, data in self.agent_instances.items()
            if current_time - data["last_access"] > max_idle_seconds
        ]
        for key in expired_keys:
            self.agent_instances[key]["instance"].close()
            del self.agent_instances[key]
```

**问题 2: 会话过期机制缺失**

**当前**: 会话永不过期，除非手动调用 `clear_history()`

**建议**: 添加自动过期清理机制

```python
# 添加定时清理任务
import threading
import time

def periodic_cleanup():
    while True:
        time.sleep(3600)  # 每小时清理一次
        agent_manager.cleanup_expired_agents()

cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()
```

**问题 3: 实例数限制**

**建议**: 使用 LRU 缓存策略

```python
from collections import OrderedDict

class AgentManager:
    def __init__(self, max_instances=100):
        self.agent_instances = OrderedDict()
        self.max_instances = max_instances

    def get_agent(self, agent_type, session_id):
        instance_key = f"{agent_type}:{session_id}"

        with self.agent_lock:
            if instance_key in self.agent_instances:
                # 移到末尾（最近使用）
                self.agent_instances.move_to_end(instance_key)
                return self.agent_instances[instance_key]

            # 检查是否超过限制
            if len(self.agent_instances) >= self.max_instances:
                # 删除最久未使用的实例（第一个）
                oldest_key, oldest_agent = self.agent_instances.popitem(last=False)
                oldest_agent.close()

            # 创建新实例
            self.agent_instances[instance_key] = self.agent_classes[agent_type]()
            return self.agent_instances[instance_key]
```

#### 4.3.11 调用链路示例

```
用户请求到达
  ↓
ChatService.process_chat(agent_type="hybrid_agent", session_id="abc123")
  ↓
agent_manager.get_agent("hybrid_agent", "abc123")
  ↓
检查实例池
  ├─ 首次请求 → 创建新实例
  │               └─ agent_instances["hybrid_agent:abc123"] = HybridAgent()
  │               └─ 初始化 LangGraph、Memory、Tools
  │
  └─ 后续请求 → 直接返回 agent_instances["hybrid_agent:abc123"]
                  └─ 保留上下文、缓存状态
  ↓
使用返回的 Agent 实例处理请求
  ↓
selected_agent.ask(message, thread_id=session_id)
  ↓
LangGraph Workflow → Tools → LLM → Response
```

#### 4.3.12 全局实例

```python
# backend/application/services/agent_service.py:125

# 创建全局 AgentManager 实例
agent_manager = AgentManager()
```

**使用示例**:

```python
# 在 ChatService 中使用
from backend.application.services.agent_service import agent_manager

selected_agent = agent_manager.get_agent(agent_type, session_id)
answer = selected_agent.ask(message, thread_id=session_id)
```

---

### 4.4 知识图谱提取

**文件位置**: `backend/application/services/kg_service.py`

```python
def extract_kg_from_message(message: str, query: str = None, reference: Dict = None) -> Dict:
    """从回答中提取知识图谱数据"""

    # 1. 优先从 reference 中获取
    if reference and isinstance(reference, dict):
        chunk_ids = reference.get("Chunks", [])
        if chunk_ids:
            return get_knowledge_graph_for_ids(chunk_ids=chunk_ids)

    # 2. 从回答文本中提取实体
    entities = extract_entities_from_text(message)
    entity_ids = [e["id"] for e in entities]

    # 3. 查询 Neo4j
    return get_knowledge_graph_for_ids(entity_ids=entity_ids)

def get_knowledge_graph_for_ids(entity_ids: List = None, chunk_ids: List = None) -> Dict:
    """从 Neo4j 查询知识图谱"""
    query = """
    MATCH (e:__Entity__)
    WHERE e.id IN $entity_ids
    OPTIONAL MATCH (e)-[r]->(target)
    RETURN e, collect(r) as relationships, collect(target) as targets
    """

    result = db_manager.execute_query(query, {"entity_ids": entity_ids})

    return {
        "entities": [...],
        "relationships": [...],
    }
```

---

### 4.5 性能监控

**前端监控**: `frontend/utils/api.py`
```python
@monitor_performance
def send_message(message: str, ...):
    start_time = time.time()
    response = requests.post(...)
    duration = time.time() - start_time
    logger.info(f"API call duration: {duration:.2f}s")
    return response
```

**后端监控**: `backend/server/api/rest/v1/chat.py`
```python
@measure_performance("chat")
async def chat(request: ChatRequest):
    # 自动记录耗时
    ...
```

**Agent 监控**: `backend/graphrag_agent/agents/base.py`
```python
def _log_execution(self, node: str, duration: float):
    """记录执行日志"""
    self.execution_log.append({
        "node": node,
        "duration": duration,
        "timestamp": time.time()
    })
```

---

## 5. 关键文件速查

| 层级 | 文件 | 说明 | 行号 |
| --- | --- | --- | --- |
| **前端层** |
| 用户输入 | `frontend/components/api/v1/chat.py` | 输入捕获、流式渲染、KG 展示 | 318-520 |
| API 封装 | `frontend/utils/api.py` | HTTP 请求、SSE 解析 | 14-142 |
| **路由层** |
| 路由 | `backend/server/api/rest/v1/chat.py` | 请求校验、SSE 封装 | 13-120 |
| **服务层** |
| Chat 服务 | `backend/application/services/chat_service.py` | 并发控制、缓存、Agent 调度 | 14-340 |
| Agent 管理 | `backend/application/services/agent_service.py` | 实例管理、历史清理 | - |
| KG 提取 | `backend/application/services/kg_service.py` | 实体解析、Cypher 查询 | 1-140 |
| **Agent 层** |
| 基类 | `backend/graphrag_agent/agents/base.py` | LangGraph 工作流、缓存 | 81-420 |
| NaiveRAG | `backend/graphrag_agent/agents/naive_rag_agent.py` | 基础向量检索 | - |
| GraphAgent | `backend/graphrag_agent/agents/graph_agent.py` | 图结构推理 | - |
| HybridAgent | `backend/graphrag_agent/agents/hybrid_agent.py` | 混合搜索 | - |
| DeepResearch | `backend/graphrag_agent/agents/deep_research_agent.py` | 多轮推理 | - |
| FusionAgent | `backend/graphrag_agent/agents/fusion_agent.py` | Plan-Execute-Report | - |
| **搜索层** |
| LocalSearch | `backend/graphrag_agent/search/local_search.py` | 实体中心检索 | - |
| LocalSearchTool | `backend/graphrag_agent/search/tool/local_search_tool.py` | RAG Chain 编排 | 24-190 |
| GlobalSearch | `backend/graphrag_agent/search/global_search.py` | 社区级聚合 | - |
| DeepResearchTool | `backend/graphrag_agent/search/tool/deep_research_tool.py` | 多轮推理工具 | - |
| **数据层** |
| Neo4j 管理 | `backend/infrastructure/config/neo4jdb.py` | 连接管理、单例 | - |
| **缓存层** |
| 缓存管理 | `backend/infrastructure/cache_manager/manager.py` | 三层缓存策略 | - |
| **并发控制** |
| 并发管理 | `backend/infrastructure/utils/concurrent.py` | 非阻塞锁 | - |

---

## 6. 常见问题定位

### 6.1 调试流程

#### 步骤 1: 开启 Debug 模式
1. 前端: 在 Streamlit 界面勾选 "Debug 模式"
2. 检查响应是否包含 `execution_log` 和 `kg_data`

#### 步骤 2: 使用 curl 测试
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: backend/application/json" \
  -d '{
    "message": "测试问题",
    "session_id": "test-session",
    "agent_type": "naive_rag_agent",
    "debug": true
  }'
```

#### 步骤 3: 检查日志
- **前端日志**: Streamlit 终端输出
- **后端日志**: FastAPI 终端输出 + `logs/` 目录
- **Neo4j 日志**: Docker logs

#### 步骤 4: 定位问题层级
| 症状 | 可能原因 | 检查位置 |
| --- | --- | --- |
| 前端无响应 | 锁未释放 / API 超时 | `chat.py:processing_lock` |
| 429 错误 | 并发冲突 | `chat_service.py:try_acquire_lock` |
| 缓存未命中 | 关键词提取失败 | `base.py:_extract_keywords` |
| 检索无结果 | Neo4j 索引缺失 | `local_search.py:similarity_search` |
| 知识图谱空 | 实体提取失败 | `kg_service.py:extract_kg_from_message` |

### 6.2 扩展 Agent

#### 创建新 Agent

```python
# backend/graphrag_agent/agents/my_custom_agent.py
from backend.graphrag_agent.agents.base import BaseAgent
from langchain_core.tools import BaseTool

class MyCustomAgent(BaseAgent):
    def _setup_tools(self) -> List[BaseTool]:
        """配置工具"""
        return [
            MyCustomSearchTool(self.llm, self.embeddings),
            # ...
        ]

    def _extract_keywords(self, query: str) -> List[str]:
        """关键词提取 (可选覆盖)"""
        # 自定义逻辑
        return super()._extract_keywords(query)

    def _generate_node(self, state):
        """答案生成 (必须实现)"""
        messages = state["messages"]
        # 自定义生成逻辑
        response = self.llm.invoke(messages)
        return {"messages": [response]}
```

#### 注册 Agent

```python
# backend/application/services/agent_service.py
AGENT_CLASSES = {
    "naive_rag_agent": NaiveRagAgent,
    "my_custom_agent": MyCustomAgent,  # 添加这里
}
```

#### 前端配置

```python
# frontend/components/sidebar.py
agent_options = {
    "NaiveRAG": "naive_rag_agent",
    "我的自定义 Agent": "my_custom_agent",  # 添加这里
}
```

### 6.3 扩展搜索工具

```python
# backend/graphrag_agent/search/tool/my_custom_search_tool.py
from langchain_core.tools import BaseTool

class MyCustomSearchTool(BaseTool):
    name: str = "my_custom_search"
    description: str = "自定义搜索工具"

    def _run(self, query: str) -> str:
        """同步执行"""
        # 实现搜索逻辑
        return "搜索结果"

    async def _arun(self, query: str) -> str:
        """异步执行"""
        return self._run(query)
```

### 6.4 优化检索参数

```python
# .env 或 backend/graphrag_agent/config/settings.py
LOCAL_SEARCH_SETTINGS = {
    "top_entities": 10,      # 增加实体数量
    "top_chunks": 20,        # 增加 chunk 数量
    "top_communities": 5,    # 增加社区数量
    "similarity_threshold": 0.7,  # 相似度阈值
}
```

### 6.5 缓存调优

```python
# .env
CACHE_ENABLED=true
CACHE_EMBEDDING_PROVIDER=openai  # or sentence_transformer
CACHE_SIMILARITY_THRESHOLD=0.95  # 提高阈值减少误命中
CACHE_TTL=3600  # 缓存过期时间 (秒)
```

---

## 附录: 性能优化建议

### 1. Neo4j 索引优化
```cypher
// 创建额外的属性索引
CREATE INDEX entity_name_index FOR (n:__Entity__) ON (n.name);
CREATE INDEX chunk_text_index FOR (n:__Chunk__) ON (n.text);
```

### 2. 批处理配置
```env
MAX_WORKERS=4
BATCH_SIZE=100
ENTITY_BATCH_SIZE=50
CHUNK_BATCH_SIZE=100
EMBEDDING_BATCH_SIZE=64
```

### 3. Neo4j GDS 配置
```env
GDS_MEMORY_LIMIT=6  # GB
GDS_CONCURRENCY=4
```

### 4. 深度研究超时处理
```python
# frontend/utils/api.py
response = requests.post(
    f"{API_URL}/api/v1/chat/stream",
    json=params,
    stream=True,
    # timeout=None  # 完全禁用超时
)
```

---

**文档版本**: v1.1
**最后更新**: 2025-12-29
**维护者**: GraphRAG Team
