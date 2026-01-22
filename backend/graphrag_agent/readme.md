# graphrag_agent（Core：GraphRAG 引擎）

`graphrag_agent` 是本仓库的 **RAG 核心算法库**：提供 Agent、检索策略、图处理与端口抽象（ports）。它被 `backend/server/` 作为服务运行时依赖，也支持未来抽成独立服务/独立包复用。

本仓库是 monorepo：后端源码物理位置统一在 `backend/` 下，但对外稳定 import 路径仍是 `graphrag_agent.*`。

## 📦 当前包结构（以代码为准）

```
backend/graphrag_agent/
├── agents/        # Agent 实现（含 multi_agent 编排栈）
├── community/     # 社区检测/摘要（算法与提示词）
├── config/        # core 默认值与提示模板（settings.py / prompts/）
├── graph/         # 图相关算法（提取/处理/索引）
├── ports/         # 端口抽象（models/neo4j/vector_store/...）
└── search/        # 检索策略与工具（local/global/hybrid/deep_research）
```

## ✅ 职责与边界（当前分层设计）

### 本包负责（怎么做）

- Agent 工作流与检索策略：`agents/`、`search/`
- 图算法与索引逻辑：`graph/`、`community/`
- 提示模板与 core 默认配置（仅默认值/类型）：`config/`
- 对外依赖的端口抽象（不绑定具体实现）：`ports/`

### 本包不负责（不要放进来）

- `.env` 读取与路径/运行参数决策（属于服务侧/基础设施侧配置）
- Neo4j driver / LLM client / 缓存落盘 等具体实现（属于 `backend/infrastructure/`）
- HTTP API / SSE 协议（属于 `backend/server/`）
- build / evaluation / scripts 工具链（优先放 `tools/`，或 `backend/infrastructure/` 的集成层）

## 🔌 Ports 与 Provider 注入

core 只通过 `graphrag_agent.ports.*` 获取外部能力；运行时必须注入 provider（由基础设施层提供实现）：

- `graphrag_agent.ports.models`
- `graphrag_agent.ports.neo4jdb`
- `graphrag_agent.ports.vector_store`
- `graphrag_agent.ports.gds`
- `graphrag_agent.ports.graph_documents`

本仓库默认注入入口：

- 服务启动时：`backend/server/main.py` 会调用 `infrastructure.bootstrap.bootstrap_core_ports()`
- 在脚本/REPL 中：你也可以手动调用：

```python
from infrastructure.bootstrap import bootstrap_core_ports

bootstrap_core_ports()
```

如果你要自定义 provider，可使用：

```python
from graphrag_agent.ports import (
    set_graph_document_provider,
    set_gds_provider,
    set_model_provider,
    set_neo4j_provider,
    set_vector_store_provider,
)

set_graph_document_provider(my_graph_document_provider)
set_gds_provider(my_gds_provider)
set_model_provider(my_model_provider)
set_neo4j_provider(my_neo4j_provider)
set_vector_store_provider(my_vector_store_provider)
```

## ⚙️ 语义配置与默认值（RESPONSE_TYPE 等）

约束：**语义默认值只在服务侧定义**，core 只保留默认值与类型。

- 语义默认值入口：`backend/config/rag_semantics.py`（从 `.env` 读取）
- 注入到 core settings：`backend/infrastructure/config/graphrag_settings.py`
- 基础设施侧读取语义（只读桥接）：`backend/infrastructure/config/semantics.py`
- core 默认值/类型：`backend/graphrag_agent/config/settings.py`

例如：`RESPONSE_TYPE` 只能在 `backend/config/rag_semantics.py` 读取 env；infra 通过 overrides 注入到 `graphrag_agent.config.settings.response_type`，其它模块不要直接读 env。

## 🔎 相关模块位置（便于定位）

- 基础设施实现（Neo4j/LLM/缓存/向量库）与 provider：`backend/infrastructure/providers/`
- 构建/增量更新入口：`backend/infrastructure/integrations/build/`（monorepo 运行）或 `tools/graphrag_agent_build/`（工具包形态）
- 评估工具：`tools/graphrag_agent_evaluation/`
