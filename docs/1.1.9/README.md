# 1.1.9 Admin 与 MiniProgram 接口拆分迁移指南

## 目标

将当前混合在 `backend/server/api/rest/v1/` 下的接口按业务端拆分：

- Admin 后端接口代码迁移到 `backend/admin/`
- MiniProgram 后端接口代码迁移到 `backend/miniprogram/`

并保证迁移期间服务可持续运行、前端调用尽量不受影响。

---

## 当前现状（迁移前）

当前 API 入口与路由聚合：

- 应用入口：`backend/server/main.py`
- 路由总线：`backend/server/api_router.py`
- 路由实现：`backend/server/api/rest/v1/*.py`

其中：

- MiniProgram 专属路由：`mp_chat_stream.py`、`mp_movies.py`
- Admin/通用路由：`chat.py`、`chat_stream.py`、`memory.py`、`knowledge_graph.py` 等

---

## 目标结构（迁移后）

```text
backend/
  admin/
    __init__.py
    api_router.py
    api/
      rest/
        v1/
          chat.py
          chat_stream.py
          clear.py
          conversations.py
          debug.py
          examples.py
          feedback.py
          knowledge_graph.py
          memory.py
          messages.py
          source.py

  miniprogram/
    __init__.py
    api_router.py
    api/
      rest/
        v1/
          mp_chat_stream.py
          mp_movies.py

  server/
    main.py
```

说明：

- `server/main.py` 继续作为统一运行入口。
- `admin` 与 `miniprogram` 分别维护自己的路由聚合器 `api_router.py`。
- 公共 HTTP 依赖与模型下沉到 `backend/api_common/`，`admin/miniprogram` 不再依赖 `server.*`。

---

## 解耦结果（当前状态）

已完成“彻底解耦”改造：

- `admin` 与 `miniprogram` 路由层已不再 import `server.api.rest.dependencies` / `server.models.*`
- 新增共享层：
  - `backend/api_common/dependencies.py`
  - `backend/api_common/schemas.py`
  - `backend/api_common/stream_events.py`
- `server` 下原模块改为兼容转发层（re-export），用于平滑过渡旧测试和旧导入路径：
  - `backend/server/api/rest/dependencies.py`
  - `backend/server/models/schemas.py`
  - `backend/server/models/stream_events.py`

---

## 迁移策略（推荐两阶段）

### 阶段 A：代码物理拆分，URL 保持不变（推荐先做）

目标：先把代码分层清晰化，不改变前端调用路径。

- Admin 仍使用 `/api/v1/*`
- MiniProgram 仍使用 `/api/v1/mp/*`
- MiniProgram 反馈暂时继续调用 `/api/v1/feedback`（保持兼容）

优点：

- 风险低、可快速落地
- `frontend-react` 和 `miniprogram` 基本无需改动

### 阶段 B：接口域名/前缀彻底隔离（可选）

目标：进一步做 API 语义隔离，例如：

- MiniProgram 新增 `/api/v1/mp/feedback`
- Admin 保留 `/api/v1/feedback`

优点：

- 接口边界更清晰
- 更便于网关与权限策略独立配置

> 当前状态：已实施 MiniProgram 反馈独立路由，`miniprogram` 前端已切换为 `/api/v1/mp/feedback`。

---

## 文件迁移映射

### 迁移到 `backend/admin/api/rest/v1/`

- `chat.py`
- `chat_stream.py`
- `clear.py`
- `conversations.py`
- `debug.py`
- `examples.py`
- `feedback.py`
- `knowledge_graph.py`
- `memory.py`
- `messages.py`
- `source.py`

### 迁移到 `backend/miniprogram/api/rest/v1/`

- `mp_chat_stream.py`
- `mp_feedback.py`
- `mp_movies.py`

---

## 详细实施步骤

### 1. 新建包结构

创建目录与包初始化文件：

- `backend/admin/`, `backend/admin/api/rest/v1/`
- `backend/miniprogram/`, `backend/miniprogram/api/rest/v1/`
- 各层添加 `__init__.py`

### 2. 使用 `git mv` 迁移路由文件

示例：

```bash
git mv backend/server/api/rest/v1/chat.py backend/admin/api/rest/v1/chat.py
git mv backend/server/api/rest/v1/mp_chat_stream.py backend/miniprogram/api/rest/v1/mp_chat_stream.py
```

建议全部使用 `git mv`，保持历史可追踪。

### 3. 新建路由聚合器

新增：

- `backend/admin/api_router.py`（只 include admin 路由）
- `backend/miniprogram/api_router.py`（只 include mini 路由）

### 4. 更新统一入口 `backend/server/main.py`

从原来：

- `from server.api_router import api_router`
- `app.include_router(api_router)`

改为：

- `from admin.api_router import api_router as admin_api_router`
- `from miniprogram.api_router import api_router as miniprogram_api_router`
- `app.include_router(admin_api_router)`
- `app.include_router(miniprogram_api_router)`

### 5. 修正 import 路径

重点检查：

- 路由文件内部对 `server.api.rest.dependencies` 的依赖
- 新包下相互导入路径
- 任何硬编码 `server.api.rest.v1.xxx` 的引用

建议将依赖注入/组合根逐步下沉到 `backend/server/` 或抽到公共模块（如后续引入 `backend/interfaces/common/`），但阶段 A 可先保持兼容复用。

### 6. 回归验证

最小验证集合：

```bash
bash scripts/test.sh
```

手工验证：

- Admin：
  - `POST /api/v1/chat`
  - `POST /api/v1/chat/stream`
  - `GET /api/v1/conversations`
  - `GET /api/v1/messages`
  - `POST /api/v1/kg_reasoning`
  - `GET /api/v1/memory/dashboard`
- MiniProgram：
  - `POST /api/v1/mp/chat/stream`
  - `GET /api/v1/mp/movies/feed`
  - `GET /api/v1/mp/movies/{tmdb_id}`
  - `POST /api/v1/mp/movies/bulk`

---

## 风险与规避

1. 导入路径失效
- 规避：迁移后立即执行 `rg "server.api.rest.v1|server.api_router"` 全量检查。

2. 路由重复注册
- 规避：只在 `server/main.py` 注册新聚合器，不再注册旧 `server/api_router.py`。

3. 行为回归（SSE/debug）
- 规避：重点回归 `chat_stream` 与 `mp_chat_stream` 的流式事件契约。

4. 文档与代码不一致
- 规避：迁移完成后同步更新 `docs/README.md` 与相关 API 文档索引。

---

## 回滚方案

若阶段 A 出现大范围问题，可快速回滚：

1. 回退本次迁移 commit。
2. 恢复 `backend/server/api_router.py` 为唯一路由入口。
3. 再次运行 `bash scripts/test.sh` 确认恢复。

---

## 完成定义（DoD）

- 接口代码已物理拆分到 `backend/admin` 与 `backend/miniprogram`
- 前端 `frontend-react` 与 `miniprogram` 核心路径可用
- `bash scripts/test.sh` 通过
- 文档已更新（含本迁移文档）

---

## 建议的后续优化

1. 将 `feedback` 按端分离为 `/api/v1/feedback` 与 `/api/v1/mp/feedback`
2. 拆分依赖注入模块，减少 `admin/miniprogram` 对 `server.*` 的路径耦合
3. 为 Admin/MiniProgram 增加独立的路由测试文件，形成双套回归基线

---

## Langfuse 启动前自检（新增）

针对 `langfuse_server` 出现 `Restarting` 的场景（常见是 `clickhouse/minio` 未就绪），新增脚本：

- `scripts/langfuse_preflight.sh`

用途：

1. 检查并自动拉起 `clickhouse`、`minio`、`redis`、`langfuse-worker`、`langfuse`。
2. 等待并验证健康接口：`/api/public/health` 返回 `200`。
3. 超时失败时自动打印 `langfuse_server` 最近日志，便于定位问题。

使用方式：

```bash
# 直接执行
bash scripts/langfuse_preflight.sh

# 或通过统一 dev 入口
bash scripts/dev.sh langfuse
```

可配置环境变量：

- `LANGFUSE_COMPOSE_FILE`（默认 `docker/docker-compose.langfuse.yml`）
- `LANGFUSE_HEALTH_URL`（默认 `http://127.0.0.1:3000/api/public/health`）
- `LANGFUSE_WAIT_SECONDS`（默认 `60`）
