# 基础设施层

基础设施层负责提供 **ports 的具体实现**（模型、图数据库、向量索引等）与运行时配置。
核心层只依赖 `graphrag_agent/ports`，不直接依赖任何基础设施代码。

## 与 core 的边界

- core 仅使用 ports 接口（例如 `ports.neo4jdb`、`ports.models`）。
- infrastructure 提供 provider，并在运行时注入到 core。
- 本仓库提供默认注入入口：`backend/infrastructure/bootstrap.py`（导入路径：`infrastructure.bootstrap`）。

**默认注入示例**：
```python
from infrastructure.bootstrap import bootstrap_core_ports

bootstrap_core_ports()
```

如需定制实现，可直接调用 ports 的 `set_*_provider` 注入自定义 provider。

## 目录说明

- `config/`：环境变量解析、路径与运行时配置注入
- `neo4jdb.py`：Neo4j 连接与执行入口（provider）
- `models/`：LLM / Embedding 实现
- `vector_store.py`：向量索引实现
- `pipelines/`：文档处理与预处理管道
- `integrations/build/`：图谱构建/索引/社区检测流程
- `rag/` / `routing/` / `agents/` / `streaming/`：应用运行所需的通用组件

## 配置与环境变量

基础设施层负责读取 `.env` 并将结果注入到 core 配置。核心只保留默认值。

- 入口：`backend/infrastructure/config/graphrag_settings.py`（导入路径：`infrastructure.config.graphrag_settings`）
- 基础设施配置：`backend/infrastructure/config/settings.py`（导入路径：`infrastructure.config.settings`）

## 图谱构建流程

图谱构建与社区检测属于运行层的编排流程，示例入口在：

- `tools/graphrag_agent_build/graphrag_agent_build/main.py`（兼容导入路径：`infrastructure.integrations.build.main`）
- `tools/graphrag_agent_build/graphrag_agent_build/build_index_and_community.py`（兼容导入路径：`infrastructure.integrations.build.build_index_and_community`）

这些流程负责调度 core 的算法能力，并在必要时调用 ports provider。
