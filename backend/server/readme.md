# 知识图谱问答系统服务端

本模块是一个基于知识图谱的智能问答系统后端 API 实现。系统通过 Neo4j 管理知识图谱数据，并使用 FastAPI 提供聊天问答与 SSE 流式响应。

## 项目结构

```
graph-rag-agent/
├── backend/application/              # 应用层（业务编排）
├── backend/domain/                   # 领域层（核心语义/实体）
├── backend/infrastructure/           # 基础设施层（RAG/路由/模型/DB）
├── backend/config/                   # 服务配置（settings/database/rag）
├── backend/graphrag_agent/           # 核心引擎（算法）
└── backend/server/                   # API 接口层（HTTP）
    ├── main.py               # FastAPI 应用入口文件
    ├── api/                  # REST API（v1）
    └── models/               # 请求/响应模型
```

## 核心实现思路

### 1. 基于FastAPI的路由结构

系统采用版本化 API（`/api/v1`），当前仅保留聊天相关端点：
- `POST /api/v1/chat`
- `POST /api/v1/chat/stream`

### 2. Agent系统设计

通过`AgentManager`类实现了多种智能Agent的统一管理：
- `graph_agent`：基于图谱的问答Agent
- `hybrid_agent`：混合模式Agent
- `naive_rag_agent`：基础检索增强生成Agent
- `deep_research_agent`：深度研究型Agent
- `fusion_agent`：融合图谱和RAG的Agent

系统可根据不同的问题类型选择合适的Agent进行处理。

### 3. 并发与持久化

系统实现了高效的并发与持久化机制：
- `ConcurrentManager`：处理请求锁和超时清理
- 聊天消息/反馈等通过 Postgres 持久化（用于回放/审计/产品分析）

### 4. 流式响应设计

支持通过Server-Sent Events (SSE)实现流式响应：
- `chat_stream`接口可发送增量更新的文本块
- 支持debug模式下的执行轨迹实时展示
- 提供思考过程和答案生成的分离展示

## 核心功能和函数

### 聊天处理

- `ChatHandler.handle`：处理同步聊天请求
- `StreamHandler.handle`：处理 SSE 流式输出
- `RagManager.run_plan_blocking`：统一执行与聚合（非流式）
- `ChatStreamExecutor`：流式执行（progress + token streaming + done）

#### 同库多 KB（movie + edu）按请求切换

`/api/v1/chat` 与 `/api/v1/chat/stream` 请求体支持传入 `kb_prefix`（如 `movie`/`edu`），服务端会按 `(agent_type, kb_prefix, session_id)` 维度隔离 Agent 实例，避免共库串 KB。

### Agent管理

- `RAGAgentManager.get_agent`：根据类型获取 Agent 实例
- `RAGAgentManager.clear_history`：清除会话历史
- `RAGAgentManager.close_all`：关闭 Agent 资源

### 并发处理
- `ConcurrentManager.try_acquire_lock`：尝试获取锁，防止并发冲突
- `measure_performance`：性能测量装饰器，记录API执行时间

## 特色功能

1. **多Agent协同**：根据问题类型选择不同的 Agent 处理
2. **流式响应**：减少首次响应时间，提供更好的用户体验
3. **执行轨迹可视化**：在 debug 模式下展示详细的推理过程
