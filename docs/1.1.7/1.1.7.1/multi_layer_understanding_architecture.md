# 多层理解架构设计指南 (Multi-Layer Understanding Architecture)

## 1. 核心设计理念：如何更好地书写“多层理解”代码

当系统存在 Router、Rewrite、Extraction、Tool Calling 等多个理解层级时，为了通过代码结构清晰地管理复杂性，我们推荐遵循以下架构模式。

### 1.1 管道模式 (Pipeline / DAG Pattern)
**原则**：不要将所有逻辑堆砌在一个巨型函数中。每个“理解层”应被封装为一个独立的、无副作用的 **Step (节点)**。
**优势**：
*   **解耦**：Router 只需要关心路由，不需要知道后续是查 TMDB 还是 Vector DB。
*   **可编排**：可以像搭积木一样调整流程（例如：在 Rewrite 之前增加一个 Safety Check 节点）。

### 1.2 黑板模式 (Shared Context)
**原则**：使用统一的上下文对象 (`Context` 或 `State`) 在各节点间流转数据，而不是通过函数参数层层传递。
**优势**：
*   **数据隔离**：原始 Query 和 Rewrite 后的 Query 都有各自的字段存储，下游节点可按需取用。
*   **扩展性**：新增一个 "Emotion" 字段不需要修改整个链路函数的签名。

### 1.3 显式路由与分支 (Explicit Routing)
**原则**：将“决策”与“执行”分离。Router 节点只负责产出**统一语义对象**（`QuerySemantics`），不直接调用执行代码。后续节点只读取 `query_semantics` 来决定执行路径。  
**统一说明**：Router 产出 `QuerySemantics`（统一语义对象，供后续检索/生成使用）；`query_semantics` 仅在后端状态中流转，不作为 API 返回字段；调试通过 `execution_log` 的 `route` 节点查看。

---

## 2. 现有实现的架构映射 (Based on LangGraph)

在我们的现有代码 (`backend/application/chat/conversation_graph.py`) 中，**LangGraph** 正是上述设计理念的完美载体。

| 设计理念 | 代码中的实现 | 说明 |
| :--- | :--- | :--- |
| **Pipeline Container** | `StateGraph` | 负责定义节点 (`add_node`) 和流转关系 (`add_edge`)。 |
| **Shared Context** | `ConversationState(TypedDict)` | 作为“黑板”，存储 `message`, `kb_prefix`, `query_semantics` 等所有状态。 |
| **Decoupled Steps** | `_route_node`, `_rewrite_query_node` | 每个函数只处理 State 中的一部分数据，并返回增量更新。 |
| **Explicit Routing** | `QuerySemantics` | Router 节点产出统一语义对象，`query_semantics` 成为下游唯一语义来源。 |
| **Parallelism** | `asyncio.gather` / LangGraph Parallel | 虽然目前主要路径是串行，但框架支持未来将 Extraction 和 Rewrite 并行化。 |

## 3. 最佳实践指南

为了保持架构的整洁，在新增功能时请遵循以下规范：

### 3.1 新增理解层（例如：增加情感分析）
1.  **定义数据**：在 `ConversationState` 中新增字段 `sentiment_score: float`。
2.  **实现节点**：编写 `_sentiment_analysis_node(state) -> dict`，只负责计算并返回 `{"sentiment_score": 0.9}`。
3.  **注册节点**：在 `_build_graph` 中 `g.add_node("sentiment", ...)` 并插入到合适的位置（如 `route` 之后）。

### 3.2 修改路由逻辑
*   不要在 `_route_node` 里直接写 `if intent == 'movie': call_tmdb()`。
*   **正确做法**：Router 应该设置 `state["kb_prefix"] = "movie"`，然后由下游的条件边 (`conditional_edges`) 或子图 (`retrieval_subgraph`) 根据这个状态去响应。

### 3.3 调试与追踪
利用 LangGraph 的 Checkpointer 和 Event Stream：
*   不要依赖 `print` 调试。
*   确保每个 Node 都有清晰的 `execution_log` 输出（如代码中的 `_emit_execution_log`），这样在 Debug 面板中能清晰看到每一层的输入输出变化。

## 总结
**LangGraph** 不是推翻了我们的设计，而是**标准化**了我们的设计。它强制我们使用 Graph（图）和 State（状态）来思考问题，这天然符合“多层理解”所需的解耦和流转要求。保持当前的 DAG 结构，避免在该结构之外写“隐式逻辑”，是代码维护的关键。
