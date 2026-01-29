# 子图事件冒泡机制（Event Bubbling with subgraphs=True）

## 目录
- [什么是事件冒泡](#什么是事件冒泡)
- [subgraphs=True 参数作用](#subgraphstrue-参数作用)
- [事件冒泡的数据结构](#事件冒泡的数据结构)
- [完整事件流示例](#完整事件流示例)
- [子图内部如何发送事件](#子图内部如何发送事件)
- [事件传播路径](#事件传播路径)
- [为什么需要 subgraphs=True](#为什么需要-subgraphstrue)
- [嵌套调用 vs First-Class Subgraph](#嵌套调用-vs-first-class-subgraph)
- [总结](#总结)

---

## 什么是事件冒泡

**事件冒泡**（Event Bubbling）是指：子图内部产生的事件，能够自动传递到父图（主图），就像水底的气泡浮到水面一样。

```
┌─────────────────────────────────────────┐
│           主图（ConversationGraph）       │
│  ┌─────────────────────────────────────┐ │
│  │  子图（RetrievalSubgraph）            │ │
│  │  ┌─────────────────────────────┐    │ │
│  │  │  节点：plan/execute/reflect  │    │ │
│  │  │  writer({"event": "..."})   │    │ │
│  │  └─────────────────────────────┘    │ │
│  │            ↓ 事件冒泡                 │ │
│  └─────────────────────────────────────┘ │
│                  ↓                        │
│          主图接收到子图事件                │
└─────────────────────────────────────────┘
```

---

## subgraphs=True 参数作用

### ❌ `subgraphs=False`（默认）

```python
async for chunk in self._graph.astream(
    dict(state),
    config=config,
    stream_mode="custom",
    subgraphs=False,  # ← 不启用子图事件冒泡
):
    # chunk 只包含主图节点的事件
    # 子图内部的事件会被吞掉！
```

**结果**：只能看到主图层级的事件，子图内部的执行细节对主图是**黑盒**。

---

### ✅ `subgraphs=True`（推荐）

```python
async for chunk in self._graph.astream(
    dict(state),
    config=config,
    stream_mode="custom",
    subgraphs=True,  # ← 启用子图事件冒泡
):
    # chunk 会包含子图内部的事件
```

**结果**：子图内部的事件会**自动冒泡到主图**，能在主图的流式输出中看到子图的执行细节。

---

## 事件冒泡的数据结构

### 子图事件的返回格式

当 `subgraphs=True` 时，LangGraph 返回的是 `(namespace, payload)` 元组：

```python
# 子图事件冒泡到主图时的格式
chunk = (
    "retrieval_subgraph",  # namespace：子图的节点名称
    {"status": "token", "content": "李"}  # payload：子图内部发送的事件
)
```

### 实际代码处理

**文件**：`backend/application/chat/conversation_graph.py`

```python
async def astream_custom(self, state: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
    """流式输出：支持子图事件冒泡（subgraphs=True）"""
    async for chunk in self._graph.astream(
        dict(state),
        config=config,
        stream_mode="custom",      # 自定义事件模式（支持 writer 发送的事件）
        subgraphs=True,            # 支持子图事件冒泡（返回 (ns, payload) 元组）
    ):
        # 当 subgraphs=True 时，LangGraph 返回 `(ns, payload)` 元组
        if isinstance(chunk, tuple) and len(chunk) == 2:
            _ns, payload = chunk
            # _ns = "retrieval_subgraph"（子图节点名称）
            # payload = {"status": "token", "content": "李"}
            if isinstance(payload, dict):
                yield payload  # 子图事件自动冒泡，透传给 SSE
            else:
                yield {"status": "token", "content": str(payload)}
            continue
```

---

## 完整事件流示例

### 场景：用户查询"李安的导演风格是怎样的？"

#### `subgraphs=False` 时（默认）

```
主图事件流：
├─ {"status": "route_decision", "content": {...}}
├─ {"status": "conversation_summary", "content": {...}}
├─ {"status": "episodic_memory", "content": [...]}
├─ {"status": "progress", "content": {"stage": "generation", ...}}
├─ {"status": "token", "content": "李"}
├─ {"status": "token", "content": "安"}
└─ {"status": "done"}

❌ 问题：子图内部的检索细节（plan/execute/reflect/merge）全部丢失！
```

---

#### `subgraphs=True` 时（生产环境使用）

```
主图事件流：
├─ {"status": "route_decision", "content": {...}}        ← 主图：route 节点
├─ {"status": "conversation_summary", "content": {...}}  ← 主图：recall 节点
├─ {"status": "episodic_memory", "content": [...]}      ← 主图：recall 节点

├─ ===== 【子图 retrieval_subgraph 事件冒泡开始】=====

├─ {"status": "execution_log", "content": {"node": "plan", ...}}        ← 子图：planner
├─ {"status": "progress", "content": {"stage": "retrieval", ...}}       ← 子图：executor
├─ {"status": "execution_log", "content": {"node": "execute_plan", ...}} ← 子图：executor
├─ {"status": "execution_log", "content": {"node": "reflect", ...}}      ← 子图：reflector
├─ {"status": "combined_context", "content": {...}}                     ← 子图：merger
├─ {"status": "rag_runs", "content": [...]}                             ← 子图：merger
├─ {"status": "execution_log", "content": {"node": "merge", ...}}       ← 子图：merger

└─ ===== 【子图事件冒泡结束】=====

├─ {"status": "progress", "content": {"stage": "generation", ...}}  ← 主图：generate 节点
├─ {"status": "token", "content": "李"}
├─ {"status": "token", "content": "安"}
└─ {"status": "done"}
```

**关键**：子图内部的 `execution_log`、`combined_context`、`rag_runs` 等事件，通过冒泡机制自动传递到主图！

---

## 子图内部如何发送事件

### 子图节点使用 `writer()` 发送事件

**文件**：`backend/infrastructure/rag/retrieval_subgraph.py`

```python
async def _plan_node(state: RetrievalState, config: RunnableConfig):
    """计划节点：生成检索计划（PlanStep[]）"""
    writer = _get_stream_writer(config)  # ← 获取 writer 函数

    # 发送 execution_log 事件
    writer({
        "execution_log": {
            "node": "plan",
            "node_type": "retrieval_subgraph",
            "duration_ms": 5,
            "input": {
                "query_preview": "李安...",
                "kb_prefix": "movie",
                "query_intent": "qa",
            },
            "output": {
                "plan_steps": [
                    {
                        "step_id": "step_0_primary",
                        "tool": "hybrid_agent",
                        "objective": "检索相关信息（主路）",
                        ...
                    }
                ]
            }
        }
    })

    return {"plan": [...], "records": [], ...}
```

### writer 函数的来源

**文件**：`backend/infrastructure/rag/retrieval_subgraph.py`

```python
def _get_stream_writer(config: RunnableConfig) -> Callable[[Any], None]:
    """从 config 中提取 writer 函数（Python 3.10 兼容）"""
    try:
        writer = config.get("configurable", {}).get("__stream_writer__")
    except Exception:
        writer = None
    return writer if callable(writer) else (lambda _chunk: None)
```

**关键点**：
- `writer` 是一个函数，可以通过 `config` 传递给节点
- 节点内部调用 `writer({"status": "...", "content": ...})` 就能实时发送事件
- 这些事件会立即通过 `astream()` 返回，不需要等节点完成

---

## 事件传播路径

```
子图节点 _plan_node()
  ↓ writer({"execution_log": {...}})
  ↓
子图内部事件流（StateGraph 内部）
  ↓ subgraphs=True
  ↓
冒泡到主图：("retrieval_subgraph", {"execution_log": {...}})
  ↓ astream_custom() 解包
  ↓
yield {"execution_log": {...}}
  ↓
StreamHandler.handle()
  ↓
chat_stream.py event_generator
  ↓
DebugCollector 缓存 / SSE 转发
  ↓
前端 DebugDrawer 展示
```

**文件路径**：

1. **子图**：`backend/infrastructure/rag/retrieval_subgraph.py`
   - `_plan_node()` / `_execute_plan_node()` / `_reflect_node()` / `_merge_node()`

2. **主图**：`backend/application/chat/conversation_graph.py`
   - `ConversationGraphRunner.astream_custom()`

3. **SSE 层**：`backend/server/api/rest/v1/chat_stream.py`
   - `event_generator()` 函数

4. **前端**：`frontend-react/src/components/debug/`
   - `DebugDrawer.tsx` / `RawTab.tsx` / `ContextTab.tsx`

---

## 为什么需要 subgraphs=True

### 1. 可观测性

- ✅ 能看到子图内部的执行细节（plan/execute/reflect/merge）
- ✅ 便于调试和监控检索质量
- ✅ 可以追踪每个步骤的耗时、输入输出

### 2. Debug UI 支持

- ✅ 前端 DebugDrawer 需要展示子图的执行日志
- ✅ 例如：plan 步骤、execution_record、merged_context 等
- ✅ 用户可以查看检索的完整链路

### 3. SSE 事件流一致性

- ✅ 所有事件（主图 + 子图）统一通过 SSE 发送给前端
- ✅ 前端不需要区分事件来自主图还是子图
- ✅ 统一的事件格式：`{"status": "...", "content": ...}`

### 4. LangGraph Studio 可视化

- ✅ 子图在 LangGraph Studio 中可见（可展开查看内部结构）
- ✅ 可以实时看到子图的执行状态
- ✅ 便于调试和优化子图逻辑

---

## 嵌套调用 vs First-Class Subgraph

### 嵌套调用（不推荐）

```python
# 主图节点手动调用子图
async def _execute_node(state, config):
    retrieval_output = await retrieval_subgraph_compiled.ainvoke(
        state, config=config
    )
    # ❌ 问题：子图内部的事件不会冒泡！
    # ❌ 只能看到最终输出，看不到中间步骤
    return {"retrieval_output": retrieval_output}
```

**缺点**：
- ❌ 子图事件被封装在 `ainvoke` 内部，外部看不到
- ❌ 无法在 LangGraph Studio 中可视化子图结构
- ❌ 难以调试和监控子图执行细节
- ❌ DebugDrawer 无法展示子图的执行链路

---

### First-Class Subgraph + subgraphs=True（推荐）

```python
# 主图直接将子图作为节点
g.add_node("retrieval_subgraph", retrieval_subgraph_compiled)

# astream 时启用事件冒泡
async for chunk in graph.astream(state, subgraphs=True):
    # ✅ 子图事件自动冒泡到主图
```

**优点**：
- ✅ 子图在 LangGraph Studio 中可见（可展开查看内部结构）
- ✅ 子图事件自动冒泡，可观测性强
- ✅ 调试时能看到完整的执行链路（主图 → 子图 → 子图内部节点）
- ✅ DebugDrawer 能展示完整的执行链路（包括子图细节）

---

## 主图和子图的代码位置

### 主图

**文件**：`backend/application/chat/conversation_graph.py`

**关键方法**：
```python
class ConversationGraphRunner:
    def _build_graph(self):
        g = StateGraph(ConversationState)
        g.add_node("route", self._route_node)
        g.add_node("recall", self._recall_node)
        g.add_node("prepare_retrieval", self._prepare_retrieval_node)

        # ===== 引入子图 =====
        from infrastructure.rag.retrieval_subgraph import retrieval_subgraph_compiled
        g.add_node("retrieval_subgraph", retrieval_subgraph_compiled)

        g.add_node("generate", self._generate_node)

        g.add_edge(START, "route")
        g.add_edge("route", "recall")
        g.add_edge("recall", "prepare_retrieval")
        g.add_conditional_edges("prepare_retrieval", _after_prepare, {
            "retrieval_subgraph": "retrieval_subgraph",
            "generate": "generate",
        })
        g.add_edge("retrieval_subgraph", "generate")
        g.add_edge("generate", END)

        return g.compile()

    async def astream_custom(self, state: dict[str, Any]):
        async for chunk in self._graph.astream(
            dict(state),
            config=config,
            stream_mode="custom",
            subgraphs=True,  # ← 启用子图事件冒泡
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                _ns, payload = chunk
                yield payload
```

### 子图

**文件**：`backend/infrastructure/rag/retrieval_subgraph.py`

**关键函数**：
```python
def build_retrieval_subgraph():
    """Retrieval 子图（Plan -> Execute -> Reflect -> Merge）"""
    g = StateGraph(RetrievalState)

    # 子图的 4 个节点
    g.add_node("planner", _plan_node)
    g.add_node("executor", _execute_plan_node)
    g.add_node("reflector", _reflect_node)
    g.add_node("merger", _merge_node)

    # 子图内部连接
    g.set_entry_point("planner")
    g.add_edge("planner", "executor")
    g.add_edge("executor", "reflector")
    g.add_conditional_edges("reflector", _should_continue_from_reflect, {
        "continue": "executor",
        "merge": "merger"
    })
    g.add_edge("merger", END)

    return g.compile()

# 编译后的子图实例（导出给主图使用）
retrieval_subgraph_compiled = build_retrieval_subgraph()
```

---

## 完整调用链示例

```
用户查询："李安的导演风格是怎样的？"

↓

【主图】conversation_graph.py
├─ _route_node()      → RouteDecision: kb_prefix="movie", query_intent="qa"
├─ _recall_node()     → 召回 mem0/summary/episodic 记忆
├─ _prepare_retrieval_node()  → 准备 RetrievalState: query, kb_prefix, route_decision...

↓

【子图】retrieval_subgraph.py
├─ _plan_node()
│  ├─ 生成 PlanStep[]
│  └─ writer({"execution_log": {"node": "plan", ...}})
│     ↓
│     【事件冒泡到主图】
│
├─ _execute_plan_node()
│  ├─ 执行检索：hybrid_agent.run() + naive_rag_agent.run()
│  ├─ writer({"status": "progress", "content": {"stage": "retrieval", ...}})
│  └─ writer({"execution_log": {"node": "execute_plan", ...}})
│     ↓
│     【事件冒泡到主图】
│
├─ _reflect_node()
│  ├─ 评估质量：evidence_count=15, top_score=0.75
│  └─ writer({"execution_log": {"node": "reflect", ...}})
│     ↓
│     【事件冒泡到主图】
│
└─ _merge_node()
   ├─ 合并结果：combined_context = "李安（1954年生）..."
   ├─ writer({"status": "combined_context", "content": {...}})
   ├─ writer({"status": "rag_runs", "content": [...]})
   └─ writer({"execution_log": {"node": "merge", ...}})
      ↓
      【事件冒泡到主图】

↓

【主图】conversation_graph.py
└─ _generate_node()
   ├─ 提取 merged.context
   └─ rag_stream(context=combined_context, ...)
      ├─ writer({"status": "token", "content": "李"})
      ├─ writer({"status": "token", "content": "安"})
      └─ ...

↓

【SSE 层】chat_stream.py
└─ event_generator()
   ├─ DebugCollector 缓存（cache-only 事件）
   └─ SSE 转发（token/progress/done 事件）

↓

【前端】DebugDrawer
└─ 展示完整执行链路（包括子图细节）
```

---

## stream_mode 参数补充

### LangGraph 的 4 种 stream_mode

| stream_mode | 输出内容 | 适用场景 |
|-------------|---------|---------|
| `"values"` | 完整的 State 对象 | 调试 State 变化 |
| `"updates"` | 节点返回的更新部分 | 追踪节点输出 |
| `"debug"` | 调试信息 | 开发调试 |
| `"custom"` | **自定义事件（writer 发送）** | **生产环境（推荐）** |

### 为什么选择 `stream_mode="custom"`？

```python
# ❌ values 模式的问题
async for chunk in graph.astream(state, stream_mode="values"):
    # 每个节点完成才输出一次，无法实时看到 token
    # route 节点完成 → 输出完整 State
    # recall 节点完成 → 输出完整 State
    # generate 节点完成 → 输出完整 State（包含完整答案）
    # 问题：无法逐 token 实时推送答案！

# ✅ custom 模式的优势
async for chunk in graph.astream(state, stream_mode="custom"):
    # generate 节点内部每生成一个 token 就 writer 发送一次
    # 实时推送：{"status": "token", "content": "李"}
    # 实时推送：{"status": "token", "content": "安"}
    # ... (逐字符流式输出)
```

**结论**：
- `stream_mode="custom"` + `subgraphs=True` = **完整的实时事件流**
- 支持细粒度流式输出（如逐 token）
- 子图事件自动冒泡，可观测性强

---

## 总结

### 核心配置

```python
async for chunk in self._graph.astream(
    dict(state),
    config=config,
    stream_mode="custom",  # 自定义事件（writer 发送）
    subgraphs=True,        # 子图事件冒泡
):
    if isinstance(chunk, tuple) and len(chunk) == 2:
        _ns, payload = chunk
        yield payload
```

### 关键优势

| 特性 | subgraphs=False | subgraphs=True |
|------|----------------|----------------|
| 子图可见性 | ❌ 黑盒 | ✅ 完整链路 |
| 调试能力 | ❌ 难以调试 | ✅ 逐步骤追踪 |
| LangGraph Studio | ❌ 不可展开 | ✅ 可展开查看 |
| DebugDrawer | ❌ 无子图细节 | ✅ 完整执行日志 |
| 生产环境 | ❌ 不推荐 | ✅ **推荐** |

### 最佳实践

1. ✅ **生产环境**：`subgraphs=True` + `stream_mode="custom"`
2. ✅ **开发调试**：`subgraphs=True` + `stream_mode="values"`（查看 State 变化）
3. ✅ **事件格式**：统一使用 `{"status": "...", "content": ...}`
4. ✅ **事件分离**：cache-only 事件（execution_log）vs SSE 事件（token/progress）

### 文件关联

- **子图定义**：`backend/infrastructure/rag/retrieval_subgraph.py`
- **主图定义**：`backend/application/chat/conversation_graph.py`
- **SSE 层**：`backend/server/api/rest/v1/chat_stream.py`
- **前端展示**：`frontend-react/src/components/debug/`
- **架构文档**：`docs/1.1.5/1.1.5.3/unified-langgraph-architecture.md`

---

## 参考资源

- [LangGraph Subgraph Documentation](https://langchain-ai.github.io/langgraph/concepts/low_level/#subgraphs)
- [LangGraph Streaming Modes](https://langchain-ai.github.io/langgraph/concepts/low_level/#streaming-modes)
- 项目内代码：
  - `backend/application/chat/conversation_graph.py`
  - `backend/infrastructure/rag/retrieval_subgraph.py`
  - `backend/server/api/rest/v1/chat_stream.py`
