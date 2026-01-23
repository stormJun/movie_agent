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
| **PostgreSQL** | ✅ 必需 | 存储所有数据 | 2GB 内存，10GB 存储 |
| **ClickHouse** | 🔸 推荐 | 快速分析查询 | 2GB 内存，5GB 存储 |
| **Redis** | 🔸 推荐 | 缓存和队列 | 512MB 内存，1GB 存储 |

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

### 4.1 最小化部署（开发/测试）

**适用场景**：
- ✅ 开发/测试环境
- ✅ 小规模使用（<10万 traces）
- ❌ 不适合生产环境（分析查询慢）

**组件**：
- ✅ PostgreSQL（必需）
- ❌ ClickHouse（不需要）
- ❌ Redis（不需要）

**资源需求**：
- 内存：~2GB
- 存储：~10GB

**部署步骤**：

#### 1. 准备 PostgreSQL 数据库

```sql
-- 在你的本地 PostgreSQL 创建数据库
CREATE DATABASE langfuse;
```

#### 2. 启动 Langfuse（Docker）

```bash
docker run -d \
  --name langfuse \
  -p 3000:3000 \
  -e DATABASE_URL="postgresql://postgres:password@host.docker.internal:5432/langfuse" \
  langfuse/langfuse:latest
```

#### 3. 访问 Web UI

打开浏览器访问：http://localhost:3000

---

### 4.2 简化部署（已有 PostgreSQL + Redis）

**适用场景**：
- ✅ 本地已有 PostgreSQL 和 Redis
- ✅ 只需添加 ClickHouse
- ✅ 开发/测试/小规模生产

**组件**：
- ✅ PostgreSQL（已有，宿主机）
- ✅ Redis（已有，宿主机）
- 🆕 ClickHouse（新增，Docker）

**资源需求**：
- **新增**内存：~2GB
- **新增**存储：~5GB

#### 4.2.1 Docker Compose 配置（只包含 ClickHouse + Langfuse）

创建 `docker-compose.langfuse.yml`：

```yaml
version: '3.8'

services:
  # ClickHouse（唯一需要的新组件）
  clickhouse:
    image: clickhouse/clickhouse-server:23
    container_name: langfuse_clickhouse
    ports:
      - "8123:8123"   # HTTP 接口
      - "9000:9000"   # Native 接口
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

  # Langfuse Server（连接到你本地的 PostgreSQL 和 Redis）
  langfuse:
    image: langfuse/langfuse:latest
    container_name: langfuse_server
    ports:
      - "3000:3000"
    environment:
      # 连接你本地的 PostgreSQL（通过 host.docker.internal）
      DATABASE_URL: "postgresql://postgres:your_password@host.docker.internal:5432/langfuse"

      # 连接容器内的 ClickHouse
      CLICKHOUSE_URL: "clickhouse://clickhouse:9000/langfuse"

      # 连接你本地的 Redis（通过 host.docker.internal）
      REDIS_URL: "redis://host.docker.internal:6379"
    depends_on:
      clickhouse:
        condition: service_healthy
    restart: unless-stopped

volumes:
  clickhouse_data:
```

**关键说明**：
- `host.docker.internal`：允许容器访问宿主机的服务
- 你的 PostgreSQL 和 Redis 运行在宿主机上
- 只有 ClickHouse 和 Langfuse 运行在 Docker 容器中

#### 4.2.2 部署步骤

```bash
# 1. 在本地 PostgreSQL 创建数据库
psql -U postgres -c "CREATE DATABASE langfuse;"

# 2. 修改 docker-compose.langfuse.yml 中的 DATABASE_URL
# 把 your_password 替换成你实际的 PostgreSQL 密码
# DATABASE_URL: "postgresql://postgres:your_actual_password@host.docker.internal:5432/langfuse"

# 3. 确认本地 Redis 正在运行
redis-cli ping  # 应该返回 "PONG"

# 4. 启动 ClickHouse + Langfuse
docker-compose -f docker-compose.langfuse.yml up -d

# 5. 查看日志（确认启动成功）
docker-compose -f docker-compose.langfuse.yml logs -f langfuse

# 6. 访问 Web UI
open http://localhost:3000
```

#### 4.2.3 验证部署

```bash
# 检查容器状态
docker-compose -f docker-compose.langfuse.yml ps

# 测试 ClickHouse
curl 'http://localhost:8123/ping'  # 应该返回 "Ok"

# 测试 Langfuse
curl 'http://localhost:3000'  # 应该返回 HTML（Web UI）
```

---

### 4.3 完整部署（Docker Compose 全部组件）

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

### 5.1 安装依赖

```bash
cd backend
pip install langfuse
```

### 5.2 初始化 Langfuse 客户端

创建 `backend/infrastructure/observability/langfuse_client.py`：

```python
"""Langfuse 客户端初始化"""

import os
from langfuse import Langfuse

def get_langfuse_client() -> Langfuse | None:
    """
    获取 Langfuse 客户端

    如果未配置环境变量，返回 None
    """
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")

    if not secret_key or not public_key:
        return None

    return Langfuse(
        secret_key=secret_key,
        public_key=public_key,
        host=host,
    )
```

### 5.3 在 ChatStreamExecutor 中集成

修改 `backend/infrastructure/streaming/chat_stream_executor.py`：

```python
from infrastructure.observability.langfuse_client import get_langfuse_client

class ChatStreamExecutor:
    def __init__(self, *, rag_manager: RagManager) -> None:
        self._rag_manager = rag_manager
        self._langfuse = get_langfuse_client()  # 初始化 Langfuse

    async def stream(
        self,
        *,
        plan: list[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        request_id: str,  # 新增参数
        memory_context: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        # 创建 Trace（根节点）
        trace = None
        if self._langfuse and debug:
            trace = self._langfuse.trace(
                name="rag_chat",
                request_id=request_id,
                metadata={
                    "kb_prefix": kb_prefix,
                    "message": message,
                    "session_id": session_id,
                }
            )

        # 路由决策
        if debug:
            yield {"execution_log": {...}}  # 现有逻辑

            # 上报到 Langfuse
            if trace:
                trace.span(
                    name="rag_plan",
                    metadata={"plan": [spec.agent_type for spec in plan]}
                )

        # 检索阶段
        for task in asyncio.as_completed(retrieval_tasks):
            run = await task
            runs.append(run)
            yield {"status": "progress", ...}  # 现有逻辑

            # 上报到 Langfuse
            if trace:
                trace.span(
                    name="rag_retrieval",
                    metadata={
                        "agent_type": run.agent_type,
                        "retrieval_count": len(run.retrieval_results or []),
                        "error": str(run.error) if run.error else None,
                    }
                )

        # 生成阶段（LLM 调用会自动被 langfuse.openai 捕获）
        async for chunk in generate_rag_answer_stream(...):
            yield {"status": "token", "content": chunk}

        # 更新 Trace 状态
        if trace:
            trace.update(status="success")
```

### 5.4 自动捕获 LLM 调用

修改 `backend/infrastructure/llm/completion.py`：

```python
# 原来的代码
from openai import AsyncOpenAI

# 替换为 langfuse 的包装器（自动捕获 LLM 调用）
from langfuse.openai import AsyncOpenAI

async def generate_rag_answer_stream(...):
    client = AsyncOpenAI()  # langfuse 会自动记录这次调用

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[...],
    )

    async for chunk in response:
        yield chunk
```

**关键**：使用 `langfuse.openai.AsyncOpenAI` 替换 `openai.AsyncOpenAI`，Langfuse 会自动捕获所有 LLM 调用。

---

## 6. 环境变量配置

### 6.1 Langfuse 配置

在 `.env` 文件中添加：

```bash
# === Langfuse 可观测性（可选）===
# 是否启用 Langfuse
LANGFUSE_ENABLED=false

# Langfuse 公钥
LANGFUSE_PUBLIC_KEY="pk-xxx"

# Langfuse 密钥
LANGFUSE_SECRET_KEY="sk-xxx"

# Langfuse 服务地址（自托管）
LANGFUSE_HOST="http://localhost:3000"
```

### 6.2 获取 API Keys

```bash
# 启动 Langfuse 后，访问 Web UI
open http://localhost:3000

# 首次访问会要求创建账号
# 创建后，在 Settings > API Keys 获取:
# - Public Key (pk-xxx)
# - Secret Key (sk-xxx)
```

---

## 7. 使用示例

### 7.1 查看 traces

1. 访问 Langfuse Web UI：http://localhost:3000
2. 点击左侧菜单 "Traces"
3. 看到 traces 列表：
   ```
   ┌─────────────────────────────────────────────────────┐
   │ Name        │ ID       │ Duration │ Tokens │ Cost   │
   ├─────────────────────────────────────────────────────┤
   │ rag_chat    │ abc-123  │ 3.2s     │ 2150   │ $0.004 │
   │ rag_chat    │ def-456  │ 2.8s     │ 1800   │ $0.003 │
   └─────────────────────────────────────────────────────┘
   ```

### 7.2 查看 Trace 详情

点击某个 trace，查看详细执行路径：

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

**文档结束**
