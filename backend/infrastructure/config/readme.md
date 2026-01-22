## backend/infrastructure/config（基础设施侧配置入口）

这里放“基础设施实现相关”的配置与注入逻辑，面向 `infrastructure/*`，并负责把运行时配置注入到 core（`graphrag_agent`）：

- `backend/infrastructure/config/settings.py`
  - 读取 `.env`（`load_dotenv(override=True)`）
  - 计算运行时目录（默认 `<repo>/files`，可用 `RUNTIME_ROOT` 覆盖）
  - 定义 Neo4j/LLM 等基础设施配置（如 `NEO4J_*`、`OPENAI_*`、`RAG_ANSWER_TIMEOUT_S` 等）
  - 定义路由相关配置（`KB_AUTO_ROUTE*`）
  - 在 import 时调用 `apply_core_settings_overrides()`，把 core defaults 覆盖为运行时值
- `backend/infrastructure/config/graphrag_settings.py`
  - 汇总并构建“core overrides”，用于注入 `graphrag_agent.config.settings`
- `backend/infrastructure/config/neo4jdb.py`（若存在）
  - Neo4jGraph/driver 的具体连接与适配（属于 infra 实现）

### 规则（防止混淆）

- 你在 `.env` 里调的“连接信息/模型供应商/运行时目录/超时”等，都属于 `backend/infrastructure/config/*`。
- API 侧（`server/`）不要直接 import `backend/infrastructure/config/*` 来拿业务语义；业务语义应走 `backend/config/rag.py`。

### 与 core 的边界

- core（`backend/graphrag_agent`）只保留默认值与类型；不应 import `infrastructure.*`
- 运行时由 `backend/infrastructure/bootstrap.py` 把 provider 注入到 `graphrag_agent.ports.*`
