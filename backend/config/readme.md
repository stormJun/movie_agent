## backend/config（服务侧配置入口）

这里放“服务/API 侧”的配置与语义入口，面向 `server/` 与 `application/`：

- `backend/config/settings.py`：服务运行参数与功能开关（如 `SERVER_*`、`PHASE2_ENABLE_*`、`SSE_HEARTBEAT_S`）
- `backend/config/database.py`：服务侧 DB 管理器/连接获取（供 API/use case 调用）
- `backend/config/rag_semantics.py`：RAG 语义配置（KB 名称、实体/关系类型、示例问题等）
- `backend/config/rag.py`：对外“server-facing”语义导出（API/schema 只 import 这个，避免直接依赖 core）

### 规则（防止混淆）

- 你在 `.env` 里调的“接口行为/开关/端口/路由策略”，通常对应 `backend/config/*`。
- 你在 `.env` 里调的“外部依赖与基础设施实现”（Neo4j/LLM/缓存/路径注入），通常对应 `backend/infrastructure/config/*`。

### 迁移提示

- `KB_AUTO_ROUTE*`（自动路由开关/阈值）属于基础设施侧路由配置，已迁移到 `backend/infrastructure/config/settings.py`。

> 备注：`backend/graphrag_agent/config/settings.py` 是 core 的默认值与类型定义（不应该在业务侧直接改/直接依赖）。
