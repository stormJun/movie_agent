# graphrag_agent 与 server 的关系说明

## 📐 整体架构关系

```
graph-rag-agent/
├── backend/graphrag_agent/          # RAG Core（算法/流程）
├── backend/application/             # 用例编排（chat/stream/kg/feedback）
├── backend/domain/                  # 领域语义（实体/决策）
├── backend/infrastructure/          # 技术设施（RAG/路由/模型/缓存/DB）
├── tools/                   # 构建/评估/运维入口（原 integrations/evaluation）
├── backend/config/                  # 服务配置（基础设施层配置）
└── backend/server/                  # FastAPI 接口层
    ├── main.py              # FastAPI 入口
    ├── api/                 # REST API（v1）
    └── models/              # 请求/响应模型
```

## 🎯 核心关系

### 1. **依赖方向**

```
backend/server/ ──> backend/application/ ──> backend/domain/
   ↓             ↓
 FastAPI       ports
                 ↑
backend/infrastructure/ ──> backend/graphrag_agent/ ──> external services
```

- **backend/server/** 是 HTTP 入口（Consumer）
- **backend/application/domain** 组织用例与领域语义
- **backend/infrastructure/** 实现端口并适配 `backend/graphrag_agent/`
- **backend/graphrag_agent/** 是 RAG 核心算法库（Provider）

### 2. **调用链路**

```
Client Request
      ↓
backend/server/main.py (FastAPI)
      ↓
backend/server/api/rest/v1/chat.py (API 路由)
      ↓
backend/application/chat/handlers/chat_handler.py (用例编排)
      ↓
backend/application/ports/router_port.py (端口)
      ↓
backend/infrastructure/routing/router.py (端口实现)
      ↓
backend/application/ports/rag_executor_port.py (端口)
      ↓
backend/infrastructure/rag/rag_manager.py (端口实现)
      ↓
backend/infrastructure/agents/rag_factory/factory.py (工厂)
      ↓
backend/graphrag_agent/agents/* (RAG Agent 实现)
      ↓
backend/graphrag_agent/search/tool/* (搜索工具)
      ↓
backend/graphrag_agent/graph/ (知识图谱)
```

### 3. **具体代码示例**

#### 3.1 server 调用 graphrag_agent

**文件**: `backend/infrastructure/agents/rag_factory/factory.py`

```python
class RAGAgentFactory:
    def create_agent(self, agent_type: str, *, kb_prefix: str, agent_mode: str):
        # 👇 导入 graphrag_agent 的 Agent
        from graphrag_agent.agents.graph_agent import GraphAgent
        from graphrag_agent.agents.hybrid_agent import HybridAgent
        from graphrag_agent.agents.naive_rag_agent import NaiveRagAgent
        from graphrag_agent.agents.deep_research_agent import DeepResearchAgent
        from graphrag_agent.agents.fusion_agent import FusionGraphRAGAgent

        agent_classes = {
            "graph_agent": GraphAgent,
            "hybrid_agent": HybridAgent,
            "naive_rag_agent": NaiveRagAgent,
            "deep_research_agent": DeepResearchAgent,
            "fusion_agent": FusionGraphRAGAgent,
        }

        # 👇 创建并返回 Agent 实例
        agent_class = agent_classes[agent_type]
        return agent_class(kb_prefix=kb_prefix, agent_mode=agent_mode)
```

#### 3.2 使用示例

**文件**: `backend/infrastructure/rag/rag_manager.py`

```python
class RagManager:
    async def run_plan_blocking(self, *, plan, message, session_id, kb_prefix, debug):
        # 👇 通过 factory 获取 graphrag_agent 的 Agent
        agent = agent_manager.get_agent(
            spec.agent_type,        # "hybrid_agent"
            session_id=session_id,
            kb_prefix=kb_prefix,     # "movie" or "edu"
            agent_mode="retrieve_only"
        )

        # 👇 调用 Agent 的方法
        raw = await asyncio.to_thread(
            agent.retrieve_with_trace,  # graphrag_agent 提供的方法
            message,
            thread_id=session_id
        )

        return RagRunResult(...)
```

## 📦 分层职责

### backend/graphrag_agent/ 的职责

| 模块 | 职责 | 示例 |
|------|------|------|
| **agents/** | 提供 RAG Agent 实现 | `HybridAgent`, `GraphAgent`, `NaiveRagAgent` |
| **search/** | 提供搜索策略 | `LocalSearch`, `GlobalSearch`, `HybridSearchTool` |
| **graph/** | 提供知识图谱能力 | `EntityRelationExtractor`, `GraphWriter` |
| **pipelines/** | 提供纯处理流程 | 文档解析、分块、结构化处理 |
| **community/** | 提供社区检测能力 | Leiden/SLLPA |

**约束**：`backend/graphrag_agent/` 不直接依赖数据库、缓存、模型客户端与环境配置，全部通过端口注入。

**定位**：通用 RAG 库，不包含业务逻辑

### backend/server/ 的职责（HTTP 入口）

| 模块 | 职责 | 示例 |
|------|------|------|
| **main.py** | FastAPI 应用入口 | 启动 HTTP 服务 |
| **api/** | 版本化 API | `/api/v1/chat`, `/api/v1/chat/stream` |
| **models/** | 请求/响应模型 | `ChatRequest`, `ChatResponse` |

### backend/application/ 的职责

| 模块 | 职责 | 示例 |
|------|------|------|
| **chat/handlers/chat_handler.py** | 同步聊天用例 | 处理聊天请求 |
| **chat/handlers/stream_handler.py** | 流式聊天用例 | SSE 输出 |
| **ports/** | 端口协议 | `RAGExecutorPort`, `RouterPort` |

### backend/infrastructure/ 的职责

| 模块 | 职责 | 示例 |
|------|------|------|
| **agents/rag_factory/** | RAG Agent 工厂 | 创建、管理 Agent 实例 |
| **rag/** | RAG 编排层 | 并行执行、聚合、统一生成 |
| **routing/orchestrator/** | 路由层 | Router Graph |
| **routing/kb_router/** | KB 路由算法 | 启发式路由、LLM 兜底 |
| **cache/** | 缓存实现 | Session/Global 缓存 |
| **models/** | 模型客户端 | LLM/Embedding |
| **persistence/** | 数据持久化 | Neo4j/向量索引 |

**定位**：FastAPI 应用服务，包含业务逻辑和编排能力

## 🔄 4 层架构视图

```
┌─────────────────────────────────────────────────────────┐
│  backend/server/ + backend/application/                                 │  🔴 层 4
│  API + UseCases（业务编排）                             │     编排层
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  backend/domain/                                                │  🟠 层 3
│  RouteDecision / Entities / Plans                       │     领域层
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  backend/infrastructure/                                        │  🔵 层 2
│  RAG/路由/模型/缓存/DB 适配实现                          │     基础设施
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  backend/graphrag_agent/                                        │  🟢 层 1
│  Agents/Search/Graph（纯算法核心）                      │     RAG Core
└─────────────────────────────────────────────────────────┘
```

## 🎯 关键要点

### 1. **graphrag_agent 是独立的 Python 包**

- 可以被其他项目导入使用
- 不依赖 backend/server/ 或 backend/infrastructure/
- 可以单独测试和发布

### 2. **server 是 FastAPI 应用**

- 通过 backend/application/infrastructure 间接依赖 graphrag_agent
- 提供 HTTP API
- 不承载核心算法

### 3. **清晰的边界**

- **backend/graphrag_agent/**：提供 RAG 能力（怎么做）
- **backend/application/**：决定何时使用哪个能力（做什么）

### 4. **扩展性**

- 新增业务：在 `backend/application/` 内新增用例/handler（按 API 入口拆分）
- 新增 RAG 策略：在 `backend/graphrag_agent/agents/` 添加新的 Agent
- 两者互不影响

## 📝 实际例子

### 场景：用户问"推荐一些科幻电影"

```
1. Client: POST /api/v1/chat/stream {"message": "推荐一些科幻电影"}
   ↓
2. backend/server/api/rest/v1/chat_stream.py: 接收请求
   ↓
3. backend/application/chat/handlers/stream_handler.py: 处理会话
   ↓
4. backend/infrastructure/routing/router.py: 路由到 movie
   ↓
5. backend/infrastructure/rag/rag_manager.py: 决定并行执行多个策略
   ↓
6. backend/infrastructure/agents/rag_factory/factory.py: 创建多个 Agent 实例
   ↓
7. backend/graphrag_agent/agents/hybrid_agent.py: 执行混合检索
   backend/graphrag_agent/agents/graph_agent.py: 执行图检索
   backend/graphrag_agent/agents/naive_rag_agent.py: 执行向量检索
   ↓
8. backend/graphrag_agent/search/tool/*: 调用搜索工具
   ↓
9. backend/graphrag_agent/graph/: 访问知识图谱
    ↓
10. backend/infrastructure/rag/aggregator.py: 聚合结果
    ↓
11. backend/infrastructure/rag/answer_generator.py: 生成最终答案
    ↓
12. backend/server/api/rest/v1/chat_stream.py: SSE 流式输出
    ↓
13. Client: 收到答案
```

## 🚀 总结

- **backend/graphrag_agent/** = RAG 核心库（Python 包）
- **backend/server/** = FastAPI 应用服务
- **关系** = server 调用 graphrag_agent
- **边界** = graphrag_agent 提供能力，server 决定如何使用
- **扩展** = 新增业务在 server，新增 RAG 策略在 graphrag_agent
