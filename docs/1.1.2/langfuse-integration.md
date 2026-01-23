# Langfuse 集成部署指南

> **版本**: 1.1.2
> **更新时间**: 2025-01-23
> **状态**: 可选集成
> **部署模式**: 自托管（本地化部署）

## 目录

- [1. 概述](#1-概述)
- [2. Langfuse vs 现有 Debug 模式](#2-langfuse-vs-现有-debug-模式)
- [3. Langfuse 架构](#3-langfuse-架构)
- [4. 部署方式](#4-部署方式)
- [5. 代码集成](#5-代码集成)
- [6. 环境变量配置](#6-环境变量配置)
- [7. 使用示例](#7-使用示例)
- [8. 故障排查](#8-故障排查)
- [9. 常见问题](#9-常见问题)

---

## 1. 概述

### 1.1 什么是 Langfuse？

Langfuse 是一个开源的 LLM 可观测性平台，提供：

- ✅ **LLM 调用追踪**：自动记录 prompt、response、tokens、cost
- ✅ **执行轨迹**：Trace 和 Span 层级结构
- ✅ **长期存储**：持久化存储历史数据
- ✅ **强大的查询**：过滤、聚合、对比分析
- ✅ **Web UI**：开箱即用的可视化界面

### 1.2 为什么需要 Langfuse？

#### 现有 Debug 模式的限制

| 功能 | 现有 Debug 模式 | Langfuse |
|------|----------------|----------|
| **路由决策** | ✅ route_decision | ✅ span metadata |
| **检索结果** | ✅ rag_runs | ✅ span metadata |
| **执行日志** | ✅ execution_log | ✅ span |
| **LLM 调用详情** | ❌ 不支持 | ✅ generation（自动捕获） |
| **Token 统计** | ❌ 不支持 | ✅ 自动统计 |
| **成本计算** | ❌ 不支持 | ✅ 自动计算 |
| **长期存储** | ❌ Redis TTL 1小时 | ✅ 持久化 |
| **查询/搜索** | ❌ 需要自己实现 | ✅ 强大的过滤和搜索 |

#### Langfuse 的独特价值

1. **LLM 调用层追踪**：自动捕获 token/cost/latency
2. **长期可观测性**：持久化存储，历史趋势分析
3. **强大的分析能力**：90 分位延迟、成本趋势、模型对比

---

## 2. Langfuse vs 现有 Debug 模式

### 2.1 功能对比

#### 现有 Debug 模式的优势

| 优势 | 说明 |
|------|------|
| **前端集成** | 在当前页面侧边栏展示，不离页 |
| **数据本地化** | 完全在本地（Redis），无需外部服务 |
| **UI 完全自定义** | 可以按产品风格定制 |
| **部署简单** | 仅需 Redis（可选） |

#### Langfuse 的优势

| 优势 | 说明 |
|------|------|
| **LLM 调用追踪** | 自动捕获 prompt/response/tokens/cost |
| **长期存储** | 持久化存储，历史数据不丢失 |
| **强大的查询** | 过滤、聚合、对比、趋势分析 |
| **开箱即用** | 无需自己开发 UI |

### 2.2 使用场景建议

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| **开发/调试** | Debug 模式 | 实时反馈，无需额外组件 |
| **生产环境监控** | Langfuse | 长期存储、成本分析 |
| **性能优化** | Langfuse | Token 统计、延迟分析 |
| **政府/金融/医疗** | Debug 模式 | 数据不出内网 |
| **前端深度定制** | Debug 模式 | 完全自定义 UI |

### 2.3 推荐方案：两者结合

```python
# 同时上报两份数据
async def stream(..., debug: bool, request_id: str):
    collector = DebugDataCollector() if debug else None
    trace = langfuse.trace(request_id=request_id) if debug else None

    # 路由决策
    decision = self._router.route(...)

    # 🔴 Debug Cache（给前端侧边栏）
    if collector:
        collector.add_event("route_decision", decision.__dict__)

    # 🔵 Langfuse（给长期可观测性）
    if trace:
        trace.span(name="route_decision", metadata=decision.__dict__)
```

**结果**：
- 用户看到：前端侧边栏实时调试信息
- 开发者看到：Langfuse Web UI 的长期分析

---

## 3. Langfuse 架构

### 3.1 核心组件

```
┌─────────────────────────────────────────────────┐
│  Langfuse Server                                │
│  - API Server（Python/FastAPI）                  │
│  - Web UI（Next.js）                             │
└─────────────────────────────────────────────────┘
          ↓                ↓
┌─────────────────┐  ┌─────────────────┐
│  PostgreSQL     │  │  ClickHouse     │  ← 用于大规模分析查询
│  (主数据库)      │  │  (可选，推荐)    │
└─────────────────┘  └─────────────────┘
          ↓
┌─────────────────┐
│  Redis          │  ← 缓存（可选，但推荐）
└─────────────────┘
```

### 3.2 组件说明
 
 | 组件 | 必需性 | 作用 | 最小配置 |
 |------|--------|------|---------|
 | **PostgreSQL** | ✅ 必需 | 存储业务实体数据 (Projects, Users, etc.) | 2GB 内存 |
 | **ClickHouse** | ✅ 必需 | 存储高吞吐事件数据 (Traces, Spans) | 2GB 内存 |
 | **Redis** | 🔸 推荐 | 缓存和任务队列 | 512MB 内存 |
 
 > **注意**：为了确保能够处理海量 Trace 数据并支持高级分析功能，本次落地 **必需部署 ClickHouse**。我们不采用无 ClickHouse 的降级方案。
 
 ### 3.3 数据流

```
你的应用
   ↓ 上报 Trace/Span/Generation
Langfuse API
   ↓ 写入
PostgreSQL（存储原始数据）
   ↓ 同步（可选）
ClickHouse（用于分析查询）
   ↓ 查询
Langfuse Web UI
```

### 3.4 Langfuse Web UI 功能介绍

Langfuse 提供了一个**完整的 Web UI**，启动后访问 http://localhost:3000 即可使用。

#### 主要页面和功能

##### 1. Traces（追踪列表）
**路径**：http://localhost:3000/traces

**功能**：
- 查看所有请求追踪记录
- 按时间、模型、用户 ID 过滤
- 搜索特定 trace ID
- 查看每个 trace 的耗时、tokens、成本

**界面示例**：
```
┌─────────────────────────────────────────────────────┐
│ Traces                                              │
├─────────────────────────────────────────────────────┤
│ Search: [按 ID/用户ID/模型搜索...]                  │
│ Filter: [日期范围] [模型] [状态]                    │
├─────────────────────────────────────────────────────┤
│ Name        │ ID       │ Duration │ Tokens │ Cost   │
│ rag_chat    │ abc-123  │ 3.2s     │ 2150   │ $0.004 │
│ rag_chat    │ def-456  │ 2.8s     │ 1800   │ $0.003 │
└─────────────────────────────────────────────────────┘
```

##### 2. Trace Details（追踪详情）
**路径**：点击任意 trace 进入

**功能**：
- 查看 trace 的完整执行路径（Span 层级结构）
- 查看 LLM 调用的完整 prompt 和 response
- 查看每个 Span 的耗时和 metadata
- 查看 token 使用量和成本

**界面示例**：
```
┌─────────────────────────────────────────────────────────┐
│ Trace: rag_chat (abc-123)                               │
│ Total: 3.2s | 2150 tokens | $0.004                     │
├─────────────────────────────────────────────────────────┤
│ 📍 Span: rag_plan (0ms)                                │
│    - plan: ["graph_agent"]                             │
│                                                         │
│ 📍 Span: rag_retrieval (120ms)                         │
│    - agent_type: "graph_agent"                         │
│    - retrieval_count: 8                                │
│                                                         │
│ 💬 Generation: llm_generation (2500ms)                 │
│    - model: gpt-4o                                     │
│    - prompt_tokens: 1800                               │
│    - completion_tokens: 350                            │
│    - [View full prompt/response] ← 点击查看完整内容     │
└─────────────────────────────────────────────────────────┘
```

##### 3. Scores（评分和反馈）
**路径**：http://localhost:3000/scores

**功能**：
- 查看用户对回答的评分
- 按分数、时间、用户过滤
- 导出评分数据

##### 4. Datasets（数据集管理）
**路径**：http://localhost:3000/datasets

**功能**：
- 管理测试数据集
- 创建和编辑数据集条目
- 运行批量评估

##### 5. Users（用户会话）
**路径**：http://localhost:3000/users

**功能**：
- 查看所有用户的会话历史
- 按用户 ID 过滤
- 查看特定用户的所有 traces

##### 6. Query（查询和分析）
**路径**：http://localhost:3000/query

**功能**：
- 执行 SQL 查询（需要 ClickHouse）
- 分析 token 使用趋势
- 计算成本、延迟统计

**示例查询**：
```sql
-- 平均 token 使用量
SELECT
    model,
    AVG(total_tokens) as avg_tokens
FROM generations
WHERE created_at > now() - INTERVAL 7 DAY
GROUP BY model;

-- 90 分位延迟
SELECT
    name,
    quantile(0.9)(latency_ms) as p90_latency
FROM traces
WHERE created_at > now() - INTERVAL 7 DAY
GROUP BY name;
```

##### 7. Settings（设置）
**路径**：http://localhost:3000/settings

**功能**：
- 获取 API Keys（Public Key、Secret Key）
- 配置项目设置
- 管理团队成员

---

#### 界面布局

```
┌─────────────────────────────────────────────────────────┐
│ Langfuse                    [Search]        [User]     │
├──────┬──────────────────────────────────────────────────┤
│      │                                                  │
│ ☰ Traces│  Trace Details                                  │
│      │  ┌─────────────────────────────────────────┐   │
│ 📊 Scores│  │ Name: rag_chat                           │   │
│      │  │ ID: abc-123                              │   │
│ 📁 Datasets│ Duration: 3.2s                            │   │
│      │  ├─────────────────────────────────────────┤   │
│ 👥 Users │  │ 📍 rag_plan (0ms)                       │   │
│      │  │ 📍 rag_retrieval (120ms)                │   │
│ 🔍 Query │  │ 💬 llm_generation (2500ms)             │   │
│      │  │   - Model: gpt-4o                       │   │
│ ⚙️ Settings│  │   - Tokens: 1800 → 350                  │   │
│      │  └─────────────────────────────────────────┘   │
└──────┴──────────────────────────────────────────────────┘
```

#### 与你的 Debug 前端对比

| 维度 | Langfuse Web UI | 你的 Debug 前端 |
|------|----------------|----------------|
| **访问方式** | 新标签页打开 http://localhost:3000 | 在当前页面侧边栏展开 |
| **UI 风格** | Langfuse 通用风格 | 完全自定义 React 组件 |
| **Traces 列表** | ✅ 支持搜索、过滤、排序 | ❌ 无 |
| **Trace 详情** | ✅ 层级结构展示 | ✅ 扁平化展示 |
| **LLM 调用详情** | ✅ 完整 prompt/response | ❌ 无 |
| **Token/Cost** | ✅ 自动统计 | ❌ 无 |
| **SQL 查询** | ✅ 支持（需要 ClickHouse）| ❌ 无 |
| **用户体验** | ❌ 需要离开应用 | ✅ 不离页，侧边栏展示 |

#### 访问 Web UI

```bash
# 启动 Langfuse 后
docker-compose -f docker-compose.langfuse.yml up -d

# 访问
open http://localhost:3000
```

首次访问会要求创建账号，创建后即可使用所有功能。

---

## 4. 部署方式

> **前置条件**：
> 1. 本地已安装 Docker / Docker Compose
> 2. 本地已运行 PostgreSQL (端口 5433)（本仓库复用 `graph-rag-agent-postgres-1`）

### 4.1 标准部署（推荐）

此方案复用现有的 PostgreSQL，仅使用 Docker 运行 ClickHouse / Redis / MinIO / Langfuse（Server + Worker），最节省资源。

**组件分布**：
- **宿主机**: PostgreSQL (5433)
- **Docker**: ClickHouse, Redis, MinIO, Langfuse Server, Langfuse Worker

#### 4.1.1 Docker Compose 配置

本仓库已提供：`docker/docker-compose.langfuse.yml`，直接使用即可（包含 ClickHouse / Redis / MinIO / Langfuse Server / Langfuse Worker）。

关键约束/注意事项：
- Redis 使用 **Compose 内置服务**（服务名 `redis`，容器名 `langfuse_redis`），对宿主机映射 `6380 -> 6379` 避免与本机 6379 冲突。
- Langfuse 不识别 `REDIS_URL`，请使用 `REDIS_CONNECTION_STRING` 或 `REDIS_HOST`/`REDIS_PORT`/`REDIS_AUTH`（否则 ingestion 会报 `Redis not initialized, aborting event processing`，UI 会出现 `Trace not found`）。

#### 4.1.2 部署步骤

我们复用项目中已有的 PostgreSQL 容器 (`graph-rag-agent-postgres-1`，映射端口 **5433**)。

```bash
# 1. 在现有 PostgreSQL (5433) 中创建数据库
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -c "CREATE DATABASE langfuse;"

# 2. 启动 ClickHouse + Redis + MinIO + Langfuse
docker compose -f docker/docker-compose.langfuse.yml up -d

# 3. （可选）确认 Compose 内 Redis 正在运行（宿主机端口 6380）
redis-cli -p 6380 ping  # 应该返回 "PONG"

# 4. 访问 Web UI
open http://localhost:3000
```

#### 4.1.3 验证部署

```bash
# 检查 ClickHouse 是否就绪
curl 'http://localhost:8123/ping'
# 返回: Ok

# 检查 Langfuse 是否就绪
curl 'http://localhost:3000/api/public/health'

# （推荐）创建一条测试 Trace 并验证可查询
python backend/langfuse_diag.py
```

---

### 4.2 全容器化部署 (可选)

**适用场景**：
- ✅ 生产环境（没有本地 PostgreSQL/Redis）
- ✅ 完全容器化部署
- ✅ 中等规模（10万-100万 traces）

**组件**：
- ✅ PostgreSQL（Docker）
- ✅ ClickHouse（Docker）
- ✅ Redis（Docker）

**资源需求**：
- 内存：~3-4GB
- 存储：~15GB

#### 4.3.1 Docker Compose 配置（包含所有组件）

创建 `docker-compose.langfuse.yml`：

```yaml
version: '3.8'

services:
  # ClickHouse（用于分析查询）
  clickhouse:
    image: clickhouse/clickhouse-server:23
    container_name: langfuse_clickhouse
    ports:
      - "8123:8123"
      - "9000:9000"
    environment:
      CLICKHOUSE_DB: langfuse
    volumes:
      - clickhouse_data:/var/lib/clickhouse
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'
        reservations:
          memory: 1G
          cpus: '1'
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:8123/ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Redis（用于缓存）
  redis:
    image: redis:7
    container_name: langfuse_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1'

  # Langfuse Server
  langfuse:
    image: langfuse/langfuse:latest
    container_name: langfuse_server
    ports:
      - "3000:3000"
    environment:
      # 使用你本地的 PostgreSQL（替换为实际连接信息）
      DATABASE_URL: "postgresql://postgres:password@host.docker.internal:5432/langfuse"
      # ClickHouse
      CLICKHOUSE_URL: "clickhouse://clickhouse:9000/langfuse"
      # Redis
      REDIS_URL: "redis://redis:6379"
    depends_on:
      clickhouse:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped

volumes:
  clickhouse_data:
  redis_data:
```

#### 4.3.2 启动服务

```bash
# 1. 创建数据库（在本地 PostgreSQL）
psql -U postgres -c "CREATE DATABASE langfuse;"

# 2. 修改 DATABASE_URL（替换为你的实际密码）
# 编辑 docker-compose.langfuse.yml

# 3. 启动服务
docker-compose -f docker-compose.langfuse.yml up -d

# 4. 查看日志（确认启动成功）
docker-compose -f docker-compose.langfuse.yml logs -f langfuse
```

#### 4.3.3 验证部署

```bash
# 检查服务状态
docker-compose -f docker-compose.langfuse.yml ps

# 测试 ClickHouse
curl 'http://localhost:8123/ping'  # 应该返回 "Ok"

# 测试 Redis
redis-cli -h localhost -p 6379 ping  # 应该返回 "PONG"

# 访问 Web UI
open http://localhost:3000
```

---

## 5. 代码集成

本项目已集成 Langfuse，采用**装饰器追踪**方式，无需手动传递 callbacks。

### 5.1 已完成的集成

#### 依赖安装

✅ 已在 `requirements.txt` 中添加 `langfuse==2.60.2`

安装依赖：

```bash
pip install langfuse==2.60.2
```

#### Langfuse Handler 模块

✅ 已创建 `backend/infrastructure/observability/langfuse_handler.py`

主要功能：
- **配置管理**：从环境变量读取 `LANGFUSE_ENABLED`、`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST`
- **客户端初始化**：单例模式管理 Langfuse 客户端
- **装饰器支持**：`@langfuse_observe()` 装饰器自动追踪函数调用
- **刷新缓冲区**：`flush_langfuse()` 确保数据发送到服务器

#### LLM Completion 集成

✅ 已在 `backend/infrastructure/llm/completion.py` 中添加装饰器

```python
from infrastructure.observability import langfuse_observe

@langfuse_observe(name="generate_general_answer")
def generate_general_answer(*, question: str, memory_context: str | None = None) -> str:
    # ... 函数实现

@langfuse_observe(name="generate_general_answer_stream")
async def generate_general_answer_stream(
    *,
    question: str,
    memory_context: str | None = None,
) -> AsyncGenerator[str, None]:
    # ... 函数实现

@langfuse_observe(name="generate_rag_answer")
def generate_rag_answer(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    response_type: str | None = None,
) -> str:
    # ... 函数实现

@langfuse_observe(name="generate_rag_answer_stream")
async def generate_rag_answer_stream(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    response_type: str | None = None,
) -> AsyncGenerator[str, None]:
    # ... 函数实现
```

#### 环境变量配置

✅ 已在 `.env.example` 中添加 Langfuse 配置

```bash
# === Langfuse 可观测性（可选）===
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY="pk-xxx"
LANGFUSE_SECRET_KEY="sk-xxx"
LANGFUSE_HOST="http://localhost:3000"
```

### 5.2 自动追踪的工作原理

Langfuse 的 `@langfuse_observe()` 装饰器会自动：

1. **捕获函数输入**：记录函数参数（如 `question`、`context`）
2. **捕获函数输出**：记录返回值
3. **创建 Trace/Span**：在 Langfuse 中自动创建调用链
4. **自动关联 LLM 调用**：LangChain 集成会自动捕获底层的 OpenAI 调用

### 5.3 验证集成

#### 1. 启用 Langfuse

在 `.env` 文件中设置：

```bash
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY="pk-xxx"  # 从 Langfuse Web UI 获取
LANGFUSE_SECRET_KEY="sk-xxx"  # 从 Langfuse Web UI 获取
LANGFUSE_HOST="http://localhost:3000"
```

#### 2. 重启后端服务

```bash
bash scripts/dev.sh backend
```

#### 3. 发送测试请求

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "session_id": "test_session",
    "use_stream": true
  }'
```

#### 4. 查看 Langfuse Web UI

访问 http://localhost:3000/traces，你应该能看到：

- **Trace 列表**：每次请求都会创建一个 Trace
- **Span 详情**：点击 Trace 可以看到调用链
  - `generate_rag_answer_stream` (根 Span)
  - `OpenAI.chat` (LLM 调用 Span)
- **LLM 详情**：Token 统计、成本、延迟

### 5.4 手动创建 Trace（可选）

如果你需要更精细的控制，可以手动创建 Trace 并添加元数据：

```python
from infrastructure.observability import _get_langfuse_client

async def stream(..., request_id: str, session_id: str):
    langfuse = _get_langfuse_client()

    # 创建 Trace
    trace = langfuse.trace(
        name="rag_chat",
        session_id=session_id,
        user_id="user_123",
        metadata={
            "kb_prefix": "movie",
            "agent_type": "hybrid_agent",
        }
    )

    # 使用装饰器自动追踪 LLM 调用
    async for chunk in generate_rag_answer_stream(...):
        yield chunk

    # 更新 Trace 状态
    trace.update(output="answer completed")
```

### 5.5 应用关闭时刷新缓冲区

确保在应用关闭时刷新 Langfuse 缓冲区：

```python
# backend/server/main.py
from infrastructure.observability import flush_langfuse

@app.on_event("shutdown")
async def shutdown_event():
    # 刷新 Langfuse 缓冲区
    await flush_langfuse()
```

### 5.6 前端 Debug Drawer 集成

✅ 已在 Debug Drawer 底部添加 Langfuse 链接按钮，点击后可在新标签页打开对应的 Trace 详情。

**修改文件**: `frontend-react/src/components/debug/DebugDrawer.tsx`

**实现效果**:
- 当 `debugData` 存在 `request_id` 时，显示"在 Langfuse 中查看 LLM 调用详情"按钮
- 点击按钮后，在新标签页打开 `http://localhost:3000/trace/{request_id}`

**代码片段**:

```tsx
{debugData?.request_id && (
    <div style={{ marginTop: 24, textAlign: 'center', borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
        <Button
            type="link"
            icon={<ExportOutlined />}
            onClick={() => {
                const langfuseHost = 'http://localhost:3000';
                window.open(`${langfuseHost}/trace/${debugData.request_id}`, '_blank');
            }}
        >
            在 Langfuse 中查看 LLM 调用详情
        </Button>
    </div>
)}
```

**使用场景**:
1. 用户在 Debug Drawer 中查看概览信息
2. 需要深入分析 LLM 调用时，点击按钮跳转到 Langfuse
3. 在 Langfuse 中查看完整的 Prompt/Response、Token 统计、成本等

---

## 6. 环境变量配置

在 `.env` 文件中添加以下配置：

```bash
# === Langfuse 可观测性 ===
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="http://localhost:3000" # 如果使用 Docker，可能是 http://host.docker.internal:3000
```

## 7. 验证清单

为了确保集成成功，请按照以下清单验证：

1.  **Docker 启动**：Langfuse 服务 (Postgres + Clickhouse + Server) 正常运行。
2.  **API Key 配置**：`.env` 中的 Key 与 Langfuse 后台一致。
3.  **Trace 创建**：发送一次对话，Langfuse 后台能看到一条新的 Trace。
4.  **Span 完整性**：Trace 中应包含 `rag_plan`, `retrieval`, `generation` 等子 Span。
5.  **LLM 详情**：点击 `generation` span，应该能看到具体的 Prompt 和 AI 回复。
6.  **Token 统计**：Trace 列表页应显示本次对话的 Token 消耗和预估成本。

---

## 8. 常见问题 (FAQ)

### Q: 为什么我看不到 LLM 的 Token 数？
**A**: 确保你已将 `LangfuseCallbackHandler` 传递给了 LangChain 的 `chain.astream` 方法。如果没有传递回调，Langfuse 只能记录手动创建的 span，无法深入 LLM 内部。

### Q: 本地 Docker 连接失败？
**A**: 如果 backend 运行在宿主机，langfuse 运行在 Docker，请确保 `.env` 中的 `LANGFUSE_HOST` 指向 `http://localhost:3000`。如果 backend 也在 Docker 中，需使用 `http://langfuse:3000` (服务名) 或 `http://host.docker.internal:3000`。

### Q: 会影响接口性能吗？
**A**: Langfuse 的 Python SDK 默认是**异步批处理**发送数据的，不会阻塞主线程的 `await` 调用，对接口延迟的影响微乎其微。


```
┌─────────────────────────────────────────────────────────┐
│ Trace: rag_chat (abc-123)                               │
│ Total: 3.2s | 2150 tokens | $0.004                     │
├─────────────────────────────────────────────────────────┤
│ 📍 Span: rag_plan (0ms)                                │
│    - plan: ["graph_agent"]                             │
│                                                         │
│ 📍 Span: rag_retrieval (120ms)                         │
│    - agent_type: "graph_agent"                         │
│    - retrieval_count: 8                                │
│                                                         │
│ 💬 Generation: llm_generation (2500ms)                 │
│    - model: gpt-4o                                     │
│    - prompt_tokens: 1800                               │
│    - completion_tokens: 350                            │
│    - [View full prompt/response]                       │
└─────────────────────────────────────────────────────────┘
```

### 7.3 分析查询

#### 查看 Token 使用趋势

```sql
-- 在 Langfuse UI 的 Query 页面
SELECT
    model,
    AVG(total_tokens) as avg_tokens,
    SUM(cost) as total_cost
FROM generations
WHERE created_at > now() - INTERVAL 7 DAY
GROUP BY model
```

#### 查看 90 分位延迟

```sql
SELECT
    name,
    quantile(0.9)(latency_ms) as p90_latency
FROM traces
WHERE created_at > now() - INTERVAL 7 DAY
GROUP BY name
```

---

## 8. 故障排查

### 8.1 Langfuse 无法连接

**现象**：
```
Error: Failed to connect to Langfuse: Connection refused
```

**解决方案**：
```bash
# 1. 检查 Langfuse 是否运行
docker ps | grep langfuse

# 2. 检查端口是否被占用
lsof -i :3000

# 3. 查看日志
docker logs langfuse_server

# 4. 检查环境变量
echo $LANGFUSE_HOST
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY
```

### 8.2 ClickHouse 启动失败

**现象**：
```
Error: ClickHouse is not ready
```

**解决方案**：
```bash
# 1. 检查 ClickHouse 状态
docker ps | grep clickhouse

# 2. 查看 ClickHouse 日志
docker logs langfuse_clickhouse

# 3. 测试连接
curl 'http://localhost:8123/ping'

# 4. 如果 OOM，增加内存限制
docker update --memory=4g langfuse_clickhouse
docker restart langfuse_clickhouse
```

### 8.3 LLM 调用没有被捕获

**现象**：Langfuse UI 中没有看到 generation

**原因**：没有使用 `langfuse.openai` 包装器

**解决方案**：
```python
# 错误：
from openai import AsyncOpenAI

# 正确：
from langfuse.openai import AsyncOpenAI
```

---

## 9. 常见问题

### 9.1 Langfuse 会影响性能吗？

**答**：影响很小

- 上报数据是异步的（不阻塞主流程）
- 如果 Langfuse 服务不可用，不会影响你的应用
- 可以通过 `LANGFUSE_ENABLED=false` 禁用

### 9.2 数据会丢失吗？

**答**：不会

- 数据存储在 PostgreSQL（持久化）
- ClickHouse 是只读副本（用于查询）
- 即使 ClickHouse 故障，数据仍然在 PostgreSQL

### 9.3 可以在现有 PostgreSQL 上运行吗？

**答**：可以

```bash
# 在现有 PostgreSQL 创建数据库
psql -U postgres -c "CREATE DATABASE langfuse;"

# 连接时指定数据库名
DATABASE_URL="postgresql://postgres:password@localhost:5432/langfuse"
```

### 9.4 如何备份数据？

```bash
# 备份 PostgreSQL
pg_dump -U postgres langfuse > langfuse_backup.sql

# 备份 ClickHouse
clickhouse-client --query="BACKUP TABLE langfuse.* TO File('/backup/langfuse')"
```

### 9.5 如何清理旧数据？

```sql
-- 删除 30 天前的 traces
DELETE FROM traces
WHERE created_at < NOW() - INTERVAL '30 days';
```

---

## 10. 参考资料

- [Langfuse 官方文档](https://langfuse.com/docs)
- [Langfuse GitHub](https://github.com/langfuse/langfuse)
- [Docker Hub - langfuse](https://hub.docker.com/r/langfuse/langfuse)
- [ClickHouse 文档](https://clickhouse.com/docs)

---

## 11. 附录

### 11.1 资源需求对比

| 部署方式 | 内存 | 存储 | 组件数量 | 适用场景 |
|---------|------|------|---------|---------|
| **最小化** | ~2GB | ~10GB | 1 个（PostgreSQL） | 开发/测试 |
| **标准** | ~3-4GB | ~15GB | 3 个（PostgreSQL + ClickHouse + Redis） | 生产环境 |
| **生产级** | ~8GB+ | ~100GB+ | 3 个（高可用配置） | 大规模生产 |

### 11.2 与现有 Debug 模式对比

| 维度 | Debug 模式 | Langfuse |
|------|-----------|----------|
| **前端集成** | ✅ 在当前页面侧边栏展示 | ❌ 需要打开外部 UI |
| **数据本地化** | ✅ 完全在本地 | ❌ 发送到外部服务 |
| **UI 定制** | ✅ 完全自定义 | ❌ 固定 UI |
| **LLM 调用追踪** | ❌ 不支持 | ✅ 自动捕获 |
| **Token 统计** | ❌ 不支持 | ✅ 自动统计 |
| **成本计算** | ❌ 不支持 | ✅ 自动计算 |
| **长期存储** | ❌ Redis TTL 1小时 | ✅ 持久化 |
| **查询/搜索** | ❌ 需要自己实现 | ✅ 强大的过滤和搜索 |
| **部署复杂度** | 极简（Redis 可选） | 中等（PostgreSQL + ClickHouse + Redis） |

### 11.3 推荐使用场景

| 场景 | 推荐方案 |
|------|---------|
| **开发/调试** | Debug 模式 |
| **生产环境监控** | Langfuse |
| **性能优化** | Langfuse |
| **政府/金融/医疗** | Debug 模式（或自托管 Langfuse） |
| **前端深度定制** | Debug 模式 |
| **长期趋势分析** | Langfuse |
| **成本控制** | Langfuse（自动计算成本） |

---


## 9. 部署故障排查指南 (Troubleshooting)

如果在部署过程中遇到问题，请参考以下实战经验：

### 9.1 Trace 列表为空 (Total 0)
**现象**：后端日志显示 Trace 创建成功，但在 Langfuse UI 中看不到数据。
**原因 1**：**缺少 Worker 容器**。Langfuse 架构分为 Server (Web) 和 Worker。Server只负责接收请求放入队列，Worker 负责从队列取出并写入数据库。
**解决**：确保 `docker-compose.yml` 中包含 `langfuse-worker` 服务。

**原因 2**：**MinIO Bucket 不存在**。Worker 尝试将事件上传到 MinIO 时失败，日志报错 `bucket does not exist`。
**解决**：手动创建 `langfuse` bucket。
```bash
# 需确保 minio 容器已运行
docker exec langfuse_minio mc alias set myminio http://localhost:9000 minio miniosecret
docker exec langfuse_minio mc mb myminio/langfuse --ignore-existing
```

### 9.2 ClickHouse 连接错误
**现象**：`Error: ClickHouse URL protocol must be either http or https`
**原因**：Langfuse Server/Worker 使用 HTTP 协议连接 ClickHouse，而不是原生 TCP。
**解决**：将 `CLICKHOUSE_URL` 设置为 `http://clickhouse:8123` (注意是 8123 端口)，而不是 `clickhouse://`。

### 9.3 认证错误 (Not found within authorized project)
**现象**：`Trace ... not found within authorized project`
**原因**：Trace 使用的 API Key 与当前登录用户查看的项目不匹配。
**解决**：
1. 确保 `.env` 中的 `LANGFUSE_PUBLIC_KEY` 与 Langfuse 后台 Settings -> API Keys 中的 Key 完全一致。
2. 确保 `load_dotenv()` 在读取环境变量之前被调用（特别是在 Python 脚本或模块导入时）。

### 9.4 环境变量未生效
**现象**：代码里 `LANGFUSE_ENABLED` 为 False，即使 `.env` 已配置。
**原因**：Python 模块（如 `langfuse_handler.py`）在导入时直接执行 `os.getenv`，此时 `load_dotenv` 尚未运行（通常在 main.py 启动时才运行）。
**解决**：在 `langfuse_handler.py` 文件顶部显式加载环境变量：
```python
from dotenv import load_dotenv
load_dotenv(override=True)
```

### 9.5 容器可见性
**现象**：`docker ps` 看不到容器，或者 Docker Desktop 看不到。
**原因**：Docker Compose 启动的容器默认会以文件夹名作为前缀（如 `movie_agent_langfuse_server_1`）。
**解决**：
```bash
# 过滤查看
docker ps -f name=langfuse
```
