# mem0 自托管集成设计文档

> **文档版本**: v1.8
> **创建日期**: 2025-01-21
> **最后更新**: 2025-01-21
> **作者**: GraphRAG Team
> **状态**: 已实现 + 增强规划

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| **v1.8** | 2025-01-21 | 🔒 **安全一致性修复**：统一所有数据库操作的 user_id 约束（update/restore/soft_delete），新增 SQL 层双重防护原则说明 |
| **v1.7** | 2025-01-21 | 🔒 **安全修复**：修复 forget_memory 认证不一致、soft_delete 约束缺失、架构边界不清晰（详见[修复说明](./mem0设计文档安全修复说明.md)） |
| **v1.6** | 2025-01-21 | 📝 新增 cache_manager 对比说明，明确 mem0 不做结果缓存 |
| **v1.5** | 2025-01-21 | 🎯 初始版本，完整的设计文档 |

---

## 目录

- [1. 概述](#1-概述)
- [2. 设计目标](#2-设计目标)
- [3. 系统架构](#3-系统架构)
  - [3.1 分层架构](#31-分层架构)
  - [3.2 数据流](#32-数据流)
  - [3.3 部署架构](#33-部署架构)
- [4. 核心组件](#4-核心组件)
  - [4.1 自托管服务端](#41-自托管服务端)
  - [4.2 客户端实现](#42-客户端实现)
  - [4.3 应用层编排](#43-应用层编排)
  - [4.4 策略与规则](#44-策略与规则)
- [5. 存储设计](#5-存储设计)
  - [5.1 PostgreSQL 元数据存储](#51-postgresql-元数据存储)
  - [5.2 Milvus 向量索引](#52-milvus-向量索引)
- [6. API 设计](#6-api-设计)
  - [6.1 添加记忆](#61-添加记忆)
  - [6.2 搜索记忆](#62-搜索记忆)
- [7. 配置系统](#7-配置系统)
- [8. 部署指南](#8-部署指南)
- [9. 安全设计](#9-安全设计)
- [10. 容错与降级](#10-容错与降级)
- [11. 监控与运维](#11-监控与运维)
- [12. 最佳实践](#12-最佳实践)
- [13. 高级能力增强](#13-高级能力增强) ⭐ **NEW**
  - [13.1 能力矩阵总览](#131-能力矩阵总览)
  - [13.2 用户画像/偏好中心](#132-用户画像偏好中心)
  - [13.3 可控写入策略](#133-可控写入策略)
  - [13.4 记忆生命周期](#134-记忆生命周期)
  - [13.5 多域/多会话共享](#135-多域多会话共享)
  - [13.6 Agent Tool 化](#136-agent-tool-化)
  - [13.7 路由/检索增强](#137-路由检索增强)
  - [13.8 观测与评估](#138-观测与评估)
  - [13.9 实施路线图](#139-实施路线图)
- [14. 附录](#14-附录)

---

## 1. 概述

### 1.1 背景

mem0 是一个长期记忆管理系统，用于存储和检索用户的偏好、事实和约束信息。本项目的 mem0 自托管集成提供以下能力：

- **跨会话记忆**: 在不同对话之间保持用户偏好和上下文
- **个性化体验**: 基于历史交互提供个性化回答
- **语义检索**: 通过向量相似度快速召回相关记忆
- **用户隔离**: 不同用户的记忆完全隔离，保护隐私

### 1.2 设计原则

1. **mem0 兼容性**: 提供与 mem0 HTTP API 兼容的接口，支持与不同 mem0 部署（自托管/SaaS）互操作
2. **依赖倒置**: 核心业务层仅依赖抽象端口（Port），具体实现通过基础设施层注入
3. **降级优先**: 记忆系统故障时自动降级，不影响主链路对话功能
4. **渐进式启用**: 通过功能开关控制记忆召回和写入，支持分阶段上线
5. **数据安全**: 内置敏感信息脱敏和用户隔离机制

### 1.3 与现有系统的关系

```mermaid
graph TB
    subgraph "业务层 (Backend)"
        ChatHandler[ChatHandler]
        StreamHandler[StreamHandler]
    end

    subgraph "应用层 (Application)"
        MemoryService[MemoryService<br/>记忆编排服务]
    end

    subgraph "域层 (Domain)"
        MemoryPolicy[MemoryPolicy<br/>记忆策略]
        MemoryItem[MemoryItem<br/>记忆项]
    end

    subgraph "端口层 (Ports)"
        MemoryStorePort[MemoryStorePort<br/>存储抽象接口]
    end

    subgraph "基础设施层 (Infrastructure)"
        Mem0Http[Mem0HttpMemoryStore<br/>HTTP 客户端]
        NullStore[NullMemoryStore<br/>空实现]
    end

    subgraph "外部服务"
        Mem0Service[mem0 自托管服务<br/>FastAPI]
        Postgres[(PostgreSQL<br/>元数据)]
        Milvus[(Milvus<br/>向量索引)]
    end

    ChatHandler --> MemoryService
    StreamHandler --> MemoryService
    MemoryService --> MemoryPolicy
    MemoryService --> MemoryStorePort
    MemoryStorePort -->|实现| Mem0Http
    MemoryStorePort -->|降级| NullStore
    Mem0Http -->|HTTP| Mem0Service
    Mem0Service --> Postgres
    Mem0Service --> Milvus
```

**关键差异**：

| 系统 | 用途 | 命中方式 | 存储内容 | 生命周期 |
|------|------|----------|----------|----------|
| **mem0** | 长期记忆 | 语义相似召回 | 用户偏好/事实/约束 | 跨会话持久化 |
| **cache_manager** | 结果缓存 | 精确 Key 匹配 | LLM 生成结果 | 会话内缓存 |

> **重要说明**：mem0 不做结果缓存，仅存储结构化的长期记忆。cache_manager 负责缓存 LLM 生成结果以优化成本和性能。

### 1.4 与 Neo4j 的关系（重要）

- **当前版本的 mem0 自托管服务不接入 Neo4j**：不会向 Neo4j 写入任何数据，也不依赖 Neo4j 做检索。
- Neo4j 在本项目中用于**知识图谱（GraphRAG）**相关的结构化检索与推理；mem0 用于**长期记忆**（偏好/事实/约束）的持久化与语义召回。
- 如果未来希望 “mem0 接入 Neo4j”，需要新增独立的存储/索引适配实现与数据模型映射（不属于本次自托管集成的默认能力）。

---

## 2. 设计目标

### 2.1 功能目标

- [x] 实现与 mem0 兼容的自托管服务
- [x] 支持记忆的添加、搜索和检索
- [x] 提供基于规则的候选记忆提取
- [x] 支持中英文偏好/事实/约束识别
- [x] 敏感信息自动脱敏（邮箱、电话）
- [x] 用户级记忆隔离

### 2.2 非功能目标

- **性能**: 记忆召回延迟 < 200ms（不含网络）
- **可用性**: mem0 服务故障时自动降级，主链路可用性 > 99.9%
- **可扩展性**: 支持水平扩展（stateless 服务端）
- **可维护性**: 清晰的分层架构，易于替换实现
- **安全性**: API 认证、用户隔离、敏感数据脱敏

---

## 3. 系统架构

### 3.1 分层架构

系统遵循标准的 DDD（领域驱动设计）分层架构：

```
┌─────────────────────────────────────────────────────────┐
│              Presentation Layer (API)                    │
│         backend/server/main.py + routers                 │
└─────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Application Layer                           │
│   - ChatHandler / StreamHandler                         │
│   - MemoryService (编排何时召回/写入)                     │
└─────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Domain Layer                                │
│   - MemoryPolicy (策略定义: top_k, min_score, max_chars) │
│   - MemoryItem (值对象: id, text, score, tags)          │
└─────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Ports Layer (抽象接口)                       │
│   - MemoryStorePort Protocol                            │
│     ├─ search(user_id, query, top_k)                    │
│     ├─ add(user_id, text, tags, metadata)               │
│     └─ close()                                           │
└─────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│              Infrastructure Layer                        │
│   - Mem0HttpMemoryStore (HTTP 客户端)                   │
│   - NullMemoryStore (降级空实现)                         │
└─────────────────────────────────────────────────────────┘
```

### 3.2 数据流

#### 3.2.1 记忆召回流程（Recall）

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant CH as ChatHandler
    participant MS as MemoryService
    participant Store as Mem0HttpMemoryStore
    participant M0 as mem0 Service
    participant PG as PostgreSQL
    participant MV as Milvus

    U->>API: POST /api/v1/chat {message}
    API->>CH: handle(user_id, message)

    CH->>MS: recall_context(user_id, query)
    MS->>Store: search(user_id, query, top_k)

    Store->>M0: POST /v1/memories/search
    M0->>MV: vector_search(query_embedding, user_id, limit)
    MV-->>M0: memory_ids[] + scores

    M0->>PG: SELECT * FROM mem0.memories WHERE id = ANY(ids)
    PG-->>M0: memory_records[]
    M0-->>Store: MemorySearchResponse {memories}

    Store-->>MS: MemoryItem[]

    MS->>MS: build_memory_context() <br/>过滤低分项，限制长度

    MS-->>CH: formatted_context

    CH->>CH: 将 memory_context 注入 LLM prompt
    CH-->>API: response
    API-->>U: answer
```

#### 3.2.2 记忆写入流程（Write）

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant CH as ChatHandler
    participant MS as MemoryService
    participant MP as MemoryPolicy
    participant Store as Mem0HttpMemoryStore
    participant M0 as mem0 Service
    participant PG as PostgreSQL
    participant MV as Milvus

    U->>API: POST /api/v1/chat {message}
    API->>CH: handle(user_id, message)

    Note over CH: 执行对话逻辑...

    CH->>MS: maybe_write(user_id, user_message, assistant_message)

    MS->>MS: 检查 MEMORY_WRITE_ENABLE

    MS->>MP: extract_memory_candidates(user_message)
    MP->>MP: 正则匹配 "我喜欢/我不喜欢/我希望..."
    MP-->>MS: [("我喜欢科幻电影", ("preference",))]

    MS->>MP: guardrail_memory_text() <br/>脱敏敏感信息

    MS->>Store: add(user_id, text, tags, metadata)
    Store->>M0: POST /v1/memories

    M0->>PG: INSERT INTO mem0.memories
    PG-->>M0: memory_id

    M0->>M0: 生成 embedding

    alt MEM0_STRICT_EMBEDDINGS=true
        M0->>MV: vector.add(memory_id, embedding)
        MV-->>M0: success
    else MEM0_STRICT_EMBEDDINGS=false (最佳努力)
        alt embedding 成功
            M0->>MV: vector.add(memory_id, embedding)
        else embedding 失败
            M0->>M0: 记录警告日志，不中断
        end
    end

    M0-->>Store: MemoryAddResponse {id}
    Store-->>MS: memory_id
```

### 3.3 部署架构

#### 3.3.1 标准部署模式

```mermaid
graph TB
    subgraph "Docker Network"
        subgraph "graphrag-backend"
            Backend[FastAPI Backend<br/>:8324]
        end

        subgraph "mem0-service"
            Mem0Srv[mem0 自托管服务<br/>FastAPI :8830]
        end

        subgraph "databases"
            Postgres[(PostgreSQL<br/>:5432)]
            Neo4j[(Neo4j<br/>:7474, :7687)]
        end

        subgraph "vector-store"
            Milvus[Milvus<br/>:19530]
        end
    end

    User([User Browser]) --> Backend
    Backend -->|HTTP/AIOHTTP| Mem0Srv
    Mem0Srv --> Postgres
    Mem0Srv --> Milvus
    Backend --> Neo4j
```

**端口分配**：

| 服务 | 宿主机端口 | 容器内端口 | 用途 |
|------|-----------|-----------|------|
| Backend | 8324 | 8324 | GraphRAG 主服务 |
| mem0 Service | 8830 | 8830 | mem0 自托管服务 |
| PostgreSQL | 5433 | 5432 | 元数据存储（宿主机 5433 映射到容器内 5432）|
| Neo4j | 7474, 7687 | 7474, 7687 | 知识图谱（HTTP/Bolt）|
| Milvus | 19530 | 19530 | 向量索引 |

**说明**：容器间通信使用容器内端口（如 `postgres:5432`），宿主机访问使用映射端口（如 `localhost:5433`）。

#### 3.3.2 集群部署模式

```mermaid
graph TB
    LB[Load Balancer] --> B1[Backend Instance 1]
    LB --> B2[Backend Instance 2]
    LB --> B3[Backend Instance N]

    B1 --> Mem0Srv1[mem0 Service 1]
    B2 --> Mem0Srv2[mem0 Service 2]
    B3 --> Mem0Srv3[mem0 Service 3]

    Mem0Srv1 --> SharedPG[(Shared PostgreSQL)]
    Mem0Srv2 --> SharedPG
    Mem0Srv3 --> SharedPG

    Mem0Srv1 --> SharedMV[(Shared Milvus)]
    Mem0Srv2 --> SharedMV
    Mem0Srv3 --> SharedMV
```

**扩展性设计**：

- mem0 服务**无状态**（stateless），支持水平扩展
- PostgreSQL 和 Milvus 作为**共享存储**，需要支持高并发
- 通过 Load Balancer 分发请求到多个 mem0 实例

---

## 4. 核心组件

### 4.1 自托管服务端

#### 4.1.1 服务入口

**文件**: `backend/server/mem0_service/main.py`

```python
def create_app() -> FastAPI:
    app = FastAPI(title="mem0 (self-hosted, compat)", version="0.1.0")
    app.state.pg = PostgresMemoryStore(dsn=MEM0_PG_DSN)
    app.state.vector = None

    @app.on_event("startup")
    async def _startup() -> None:
        await app.state.pg.open()
        if MEM0_VECTOR_BACKEND == "milvus":
            index = MilvusVectorIndex(...)
            index.connect()
            app.state.vector = index

    @app.post("/v1/memories", response_model=MemoryAddResponse)
    async def add_memory(req: MemoryAddRequest) -> MemoryAddResponse:
        # 1. 存储元数据到 PostgreSQL
        mid = await app.state.pg.add(user_id=req.user_id, text=text, ...)

        # 2. 生成向量索引
        if app.state.vector:
            emb = _embed_text(text)
            app.state.vector.add(memory_id=mid, user_id=req.user_id, embedding=emb)

        return MemoryAddResponse(id=mid)

    @app.post("/v1/memories/search", response_model=MemorySearchResponse)
    async def search_memories(req: MemorySearchRequest) -> MemorySearchResponse:
        # 1. 向量检索
        emb = _embed_text(req.query)
        hits = app.state.vector.search(user_id=req.user_id, embedding=emb, limit=limit)

        # 2. 批量获取元数据
        ids = [h.memory_id for h in hits]
        meta = await app.state.pg.get_many(ids=ids, user_id=req.user_id)

        # 3. 组装结果
        memories = [MemoryOut(id=h.memory_id, text=meta[h.memory_id]["text"], score=h.score, ...)]
        return MemorySearchResponse(memories=memories)

    return app
```

**关键设计点**：

1. **双存储架构**: PostgreSQL 存储元数据，Milvus 存储向量
2. **延迟索引**: 向量索引失败时可根据配置选择是否中断
3. **用户隔离**: 所有搜索操作强制添加 `user_id` 过滤

#### 4.1.2 认证中间件

```python
def _require_auth(authorization: Optional[str] = Header(default=None)) -> None:
    if not MEM0_API_KEY:
        return  # 未配置 API Key 时跳过认证
    expected = f"Bearer {MEM0_API_KEY}"
    if (authorization or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

**使用方式**：

```bash
# 带认证请求
curl -X POST http://localhost:8830/v1/memories \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "text": "我喜欢科幻电影"}'
```

#### 4.1.3 向量后端抽象

**Milvus 向量索引** (`backend/server/mem0_service/vector_milvus.py`):

```python
class MilvusVectorIndex:
    def __init__(self, *, host: str, port: int, collection: str, embedding_dim: Optional[int]):
        self._collection_name = collection
        self._embedding_dim = embedding_dim
        self._collection = None

    def connect(self) -> None:
        connections.connect(alias="default", host=self._host, port=self._port)
        # 延迟创建 collection，直到首次 embed() 调用时确定维度

    def ensure_collection(self, *, dim: int) -> None:
        if self._collection is not None:
            return
        if utility.has_collection(self._collection_name):
            self._collection = Collection(self._collection_name)
            self._collection.load()
        else:
            # 创建新 collection
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
                FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=int(dim)),
                FieldSchema(name="created_at", dtype=DataType.INT64),
            ]
            schema = CollectionSchema(fields, description="mem0 memories (GraphRAG self-hosted)")
            c = Collection(self._collection_name, schema=schema)
            c.create_index(field_name="embedding", index_params={
                "index_type": "HNSW",
                "metric_type": "IP",
                "params": {"M": 16, "efConstruction": 200},
            })
            c.load()
            self._collection = c

    def add(self, *, memory_id: str, user_id: str, embedding: list[float]) -> None:
        if self._collection is None:
            dim = self._embedding_dim or len(embedding)
            self.ensure_collection(dim=dim)
        vec = _l2_normalize(list(embedding))  # L2 归一化
        self._collection.insert([[memory_id], [user_id], [vec], [created_at]])
        self._collection.flush()

    def search(self, *, user_id: str, embedding: list[float], limit: int) -> list[VectorHit]:
        vec = _l2_normalize(list(embedding))
        expr = f'user_id == "{user_id}"'  # 用户隔离
        results = self._collection.search(
            data=[vec],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"ef": 64}},
            limit=int(limit),
            expr=expr,
            output_fields=["id", "user_id", "created_at"],
        )
        hits = [VectorHit(memory_id=hit.id, score=hit.distance) for hit in results[0]]
        return hits
```

**设计亮点**：

- **延迟创建 Collection**: 首次 `embed()` 调用时确定向量维度，避免硬编码
- **L2 归一化**: 使用 IP（内积）度量时等价于余弦相似度
- **用户过滤**: 在 Milvus 层面强制用户隔离，防止跨用户泄露
- **HNSW 索引**: 高性能近似最近邻搜索

#### 4.1.4 PostgreSQL 元数据存储

**文件**: `backend/server/mem0_service/storage_postgres.py`

```python
class PostgresMemoryStore:
    async def _ensure_schema(self) -> None:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS mem0;")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mem0.memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                text TEXT NOT NULL,
                tags TEXT[] NOT NULL DEFAULT '{}'::text[],
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS mem0_memories_user_id_idx ON mem0.memories(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS mem0_memories_created_at_idx ON mem0.memories(created_at);")

    async def add(self, *, user_id: str, text: str, tags: list[str], metadata: dict) -> str:
        mid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        await conn.execute(
            "INSERT INTO mem0.memories (id, user_id, text, tags, metadata, created_at) VALUES ($1, $2, $3, $4, $5::jsonb, $6);",
            mid, user_id, text, tags, json.dumps(metadata), now
        )
        return mid

    async def get_many(self, *, ids: list[str], user_id: str) -> dict[str, dict]:
        rows = await conn.fetch(
            "SELECT id, text, tags, created_at FROM mem0.memories WHERE user_id = $1 AND id = ANY($2::text[]);",
            user_id, ids
        )
        return {r["id"]: {"text": r["text"], "tags": r["tags"], "created_at": r["created_at"]} for r in rows}
```

**表结构设计**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT (PK) | 记忆唯一标识 |
| `user_id` | TEXT (NOT NULL, INDEXED) | 用户 ID，强制隔离 |
| `text` | TEXT (NOT NULL) | 记忆文本内容 |
| `tags` | TEXT[] | 标签数组，如 `['preference', 'dislike']` |
| `metadata` | JSONB | 扩展元数据，灵活存储 |
| `created_at` | TIMESTAMPTZ (INDEXED) | 创建时间 |

**索引优化**：

- `user_id` 索引：快速按用户过滤
- `created_at` 索引：支持按时间排序和过期清理

### 4.2 客户端实现

#### 4.2.1 HTTP 客户端

**文件**: `backend/infrastructure/memory/mem0_http_memory_store.py`

```python
class Mem0HttpMemoryStore(MemoryStorePort):
    """mem0 HTTP client (best-effort; schema tolerant)."""

    def __init__(
        self,
        *,
        base_url: str = MEM0_BASE_URL,
        api_key: str = MEM0_API_KEY,
        timeout_s: float = MEM0_TIMEOUT_S,
        search_path: str = MEM0_SEARCH_PATH,
        add_path: str = MEM0_ADD_PATH,
    ) -> None:
        self._base_url = (base_url or "").strip()
        self._api_key = (api_key or "").strip()
        self._timeout_s = float(timeout_s or 10.0)
        self._search_url = _join(self._base_url, search_path)
        self._add_url = _join(self._base_url, add_path)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session
        timeout = aiohttp.ClientTimeout(total=self._timeout_s)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def search(self, *, user_id: str, query: str, top_k: int) -> list[MemoryItem]:
        if not self._base_url:
            return []  # 未配置 mem0 时返回空

        session = await self._get_session()
        payload = {"user_id": str(user_id), "query": str(query), "limit": int(top_k)}

        async with session.post(self._search_url, json=payload, headers=self._headers()) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(f"mem0 search failed ({resp.status}): {text[:200]}")
            data = await resp.json(content_type=None)

        return self._parse_items(data)  # 容错解析

    async def add(
        self,
        *,
        user_id: str,
        text: str,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self._base_url:
            return None

        session = await self._get_session()
        payload: dict[str, Any] = {"user_id": str(user_id), "text": str(text)}
        if tags:
            payload["tags"] = list(tags)
        if metadata:
            payload["metadata"] = dict(metadata)

        async with session.post(self._add_url, json=payload, headers=self._headers()) as resp:
            if resp.status >= 400:
                text_resp = await resp.text()
                raise RuntimeError(f"mem0 add failed ({resp.status}): {text_resp[:200]}")
            data = await resp.json(content_type=None)

        if isinstance(data, dict):
            mid = data.get("id") or data.get("memory_id") or data.get("data", {}).get("id")
            if mid:
                return str(mid)
        return None
```

**特性**：

1. **异步 HTTP 客户端**: 使用 `aiohttp` 支持高并发
2. **会话复用**: 维护长连接减少握手开销
3. **容错解析**: `_parse_items()` 支持多种响应格式
4. **超时控制**: 默认 10 秒超时，防止阻塞

#### 4.2.2 响应容错解析

```python
@staticmethod
def _parse_items(payload: Any) -> list[MemoryItem]:
    # 支持多种响应格式
    if isinstance(payload, dict):
        for key in ("memories", "data", "results", "items"):
            if key in payload and isinstance(payload[key], list):
                payload = payload[key]
                break

    items: list[MemoryItem] = []
    if not isinstance(payload, list):
        return items

    for raw in payload:
        if not isinstance(raw, dict):
            continue
        mid = str(raw.get("id") or raw.get("memory_id") or raw.get("_id") or "")
        text = str(raw.get("text") or raw.get("content") or raw.get("memory") or "")
        score = float(raw.get("score") or raw.get("similarity") or 0.0)
        tags_raw = raw.get("tags") or raw.get("tag") or []
        tags: tuple[str, ...] = ()
        if isinstance(tags_raw, list):
            tags = tuple(str(t) for t in tags_raw if t)
        elif isinstance(tags_raw, str) and tags_raw:
            tags = (tags_raw,)

        created_at = None
        ts = raw.get("created_at") or raw.get("createdAt") or raw.get("timestamp")
        if isinstance(ts, str) and ts:
            try:
                created_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                created_at = None

        if not mid and not text:
            continue
        items.append(MemoryItem(id=mid or text[:16], text=text, score=score, created_at=created_at, tags=tags))
    return items
```

**兼容性**：

- 支持 mem0 开源版、SaaS 版、自定义部署
- 自动适配不同的字段命名（`id`/`memory_id`/`_id`）
- 宽松的标签解析（数组或字符串）

#### 4.2.3 Null Object 模式

**文件**: `backend/infrastructure/memory/null_memory_store.py`

```python
class NullMemoryStore(MemoryStorePort):
    """空实现，用于降级场景。"""

    async def search(self, *, user_id: str, query: str, top_k: int) -> list[MemoryItem]:
        return []

    async def add(self, *, user_id: str, text: str, tags: Optional[list[str]] = None, metadata: Optional[dict[str, Any]] = None) -> Optional[str]:
        return None

    async def close(self) -> None:
        return None
```

**用途**：

- mem0 服务未配置时注入
- mem0 服务故障时降级
- 测试环境 Mock

### 4.3 应用层编排

#### 4.3.1 MemoryService

**文件**: `backend/application/chat/memory_service.py`

```python
class MemoryService:
    """Application-layer memory orchestration (when to recall/write)."""

    def __init__(
        self,
        *,
        store: MemoryStorePort,
        policy: MemoryPolicy,
        write_enabled: bool,
        write_mode: str = "rules",
    ) -> None:
        self._store = store
        self._policy = policy
        self._write_enabled = bool(write_enabled)
        self._write_mode = (write_mode or "rules").strip() or "rules"

    async def recall_context(self, *, user_id: str, query: str) -> Optional[str]:
        """召回相关记忆并格式化为 LLM prompt 上下文。"""
        try:
            memories = await self._store.search(
                user_id=user_id,
                query=query,
                top_k=int(self._policy.top_k),
            )
        except Exception:
            # Best-effort degradation: memory recall must never break chat.
            return None
        return build_memory_context(memories=memories, policy=self._policy)

    async def maybe_write(
        self,
        *,
        user_id: str,
        user_message: str,
        assistant_message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """基于规则提取候选记忆并写入。"""
        if not self._write_enabled:
            return
        if self._write_mode != "rules":
            return  # v3 minimal: only rule-based write is supported for now.

        candidates = extract_memory_candidates(user_message=user_message)
        if not candidates:
            return

        text, tags = candidates[0]
        try:
            await self._store.add(
                user_id=user_id,
                text=text,
                tags=list(tags),
                metadata=metadata,
            )
        except Exception:
            # Best-effort degradation: memory write must never break chat.
            return
```

**职责**：

- **何时召回**: 每次用户请求时调用 `recall_context()`
- **何时写入**: 基于 `MEMORY_WRITE_ENABLE` 开关控制
- **如何降级**: 所有异常捕获，返回 `None` 或静默失败

#### 4.3.2 ChatHandler 集成

```python
class ChatHandler:
    def __init__(self, ..., memory_service: MemoryService):
        self._memory_service = memory_service

    async def handle(self, *, user_id: str, message: str, session_id: str, ...):
        # 1. 召回长期记忆
        memory_context = await self._memory_service.recall_context(user_id=user_id, query=message)

        # 2. 路由决策（RAG or General）
        route_decision = await self._router.route(message=message, session_id=session_id, ...)

        if route_decision.is_general:
            # General 路径：直接传给 completion
            answer = await self._completion.generate(
                message=message,
                memory_context=memory_context  # 注入记忆上下文
            )
        else:
            # RAG 路径：传给 executor
            result, _ = await self._executor.run(
                plan=plan,
                message=message,
                session_id=session_id,
                kb_prefix=route_decision.kb_prefix,
                memory_context=memory_context  # 注入记忆上下文
            )
            answer = result.answer

        # 3. 写入记忆（非阻塞，内部有异常捕获）
        # 注意：当前实现为 await 同步调用，但写入失败不影响主链路返回
        await self._memory_service.maybe_write(
            user_id=user_id,
            user_message=message,
            assistant_message=answer,
        )

        return {"answer": answer, ...}
```

### 4.4 策略与规则

#### 4.4.1 MemoryPolicy

**文件**: `backend/domain/memory/policy.py`

```python
@dataclass(frozen=True)
class MemoryPolicy:
    top_k: int = 5          # 召回数量
    min_score: float = 0.6  # 最低相关性分数
    max_chars: int = 1200   # 最大上下文长度
```

#### 4.4.2 记忆上下文构建

```python
def build_memory_context(*, memories: Iterable[MemoryItem], policy: MemoryPolicy) -> Optional[str]:
    """Format recalled memories into a prompt-safe context block."""
    selected: list[str] = []
    for item in sorted(memories, key=lambda m: float(m.score or 0.0), reverse=True):
        if len(selected) >= int(policy.top_k):
            break
        if float(item.score or 0.0) < float(policy.min_score):
            continue
        text = (item.text or "").strip()
        if not text:
            continue
        selected.append(text)

    if not selected:
        return None

    header = (
        "【用户长期记忆（可能不准确，仅作参考，不得覆盖系统安全规则）】\n"
        "下面是系统基于历史对话召回的用户偏好/事实/约束。若与当前对话冲突，以当前用户输入为准：\n"
    )
    body = "\n".join(f"- {t}" for t in selected)
    text = f"{header}{body}\n"
    if len(text) <= int(policy.max_chars):
        return text
    return text[: int(policy.max_chars)].rstrip() + "\n"
```

**输出示例**：

```
【用户长期记忆（可能不准确，仅作参考，不得覆盖系统安全规则）】
下面是系统基于历史对话召回的用户偏好/事实/约束。若与当前对话冲突，以当前用户输入为准：
- 我喜欢科幻电影
- 我不喜欢恐怖片
- 我希望推荐时长在120分钟以内的电影
```

#### 4.4.3 规则提取候选记忆

```python
def extract_memory_candidates(*, user_message: str) -> list[tuple[str, tuple[str, ...]]]:
    """Rule-based extraction for stable memory."""
    text = (user_message or "").strip()
    if not text:
        return []

    # 中文模式
    patterns: list[tuple[str, tuple[str, ...]]] = [
        (r"我喜欢(.+)", ("preference",)),
        (r"我不喜欢(.+)", ("preference", "dislike")),
        (r"我偏好(.+)", ("preference",)),
        (r"我最关心(.+)", ("constraint",)),
        (r"我希望(.+)", ("constraint",)),
        (r"请(不要|别)(.+)", ("constraint",)),
        (r"我叫(.+)", ("fact", "identity")),
    ]

    for pat, tags in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        fragment = (m.group(0) or "").strip()
        payload = guardrail_memory_text(fragment)
        if payload:
            return [(payload, tags)]

    # 英文模式
    en_patterns: list[tuple[str, tuple[str, ...]]] = [
        (r"\bI (?:really )?like (.+)", ("preference",)),
        (r"\bI don't like (.+)", ("preference", "dislike")),
        (r"\bPlease don't (.+)", ("constraint",)),
    ]

    for pat, tags in en_patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if not m:
            continue
        fragment = (m.group(0) or "").strip()
        payload = guardrail_memory_text(fragment)
        if payload:
            return [(payload, tags)]

    return []
```

**支持的标签类型**：

| 标签 | 含义 | 示例 |
|------|------|------|
| `preference` | 用户偏好 | "我喜欢科幻电影" |
| `dislike` | 用户不喜欢 | "我不喜欢恐怖片" |
| `constraint` | 用户约束 | "我希望推荐时长小于120分钟的电影" |
| `fact` | 用户事实 | "我叫张三" |
| `identity` | 身份信息 | （属于 fact 的子类） |

#### 4.4.4 敏感信息脱敏

```python
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\b(\+?\d[\d -]{7,}\d)\b")

def guardrail_memory_text(text: str) -> Optional[str]:
    """Best-effort scrub for memory write payloads."""
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    cleaned = _EMAIL_RE.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _PHONE_RE.sub("[REDACTED_PHONE]", cleaned)
    return cleaned.strip() or None
```

**脱敏规则**：

- 邮箱地址: `user@example.com` → `[REDACTED_EMAIL]`
- 电话号码: `+86 138 0013 8000` → `[REDACTED_PHONE]`

---

## 5. 存储设计

### 5.1 PostgreSQL 元数据存储

#### 5.1.1 表结构

```sql
CREATE SCHEMA IF NOT EXISTS mem0;

CREATE TABLE IF NOT EXISTS mem0.memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    text TEXT NOT NULL,
    tags TEXT[] NOT NULL DEFAULT '{}'::text[],
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS mem0_memories_user_id_idx ON mem0.memories(user_id);
CREATE INDEX IF NOT EXISTS mem0_memories_created_at_idx ON mem0.memories(created_at);
```

#### 5.1.2 字段说明

| 字段 | 类型 | 约束 | 索引 | 说明 |
|------|------|------|------|------|
| `id` | TEXT | PRIMARY KEY | - | UUID 格式记忆 ID |
| `user_id` | TEXT | NOT NULL | BTREE | 用户 ID，支持快速过滤 |
| `text` | TEXT | NOT NULL | - | 记忆文本内容 |
| `tags` | TEXT[] | NOT NULL | - | 标签数组，GIN 索引（可选） |
| `metadata` | JSONB | NOT NULL | - | 扩展元数据，支持灵活查询 |
| `created_at` | TIMESTAMPTZ | NOT NULL | BTREE | 创建时间，支持排序和 TTL |

#### 5.1.3 查询优化

**批量获取**（用于搜索后的元数据补全）：

```sql
SELECT id, text, tags, created_at
FROM mem0.memories
WHERE user_id = $1 AND id = ANY($2::text[]);
```

**用户统计**（用于监控和清理）：

```sql
SELECT user_id, COUNT(*) as memory_count
FROM mem0.memories
GROUP BY user_id
ORDER BY memory_count DESC;
```

**过期清理**（可选，基于 TTL）：

```sql
DELETE FROM mem0.memories
WHERE created_at < NOW() - INTERVAL '90 days';
```

### 5.2 Milvus 向量索引

#### 5.2.1 Collection 结构

```python
fields = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, auto_id=False, max_length=64),
    FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=128),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=<dynamic>),
    FieldSchema(name="created_at", dtype=DataType.INT64),
]
```

#### 5.2.2 索引配置

```python
index_params = {
    "index_type": "HNSW",  # 分层导航小世界图
    "metric_type": "IP",   # 内积（Inner Product）
    "params": {
        "M": 16,            # HNSW 图的连接数
        "efConstruction": 200  # 构建时的搜索范围
    }
}
```

**选择理由**：

- **HNSW**: 高性能近似最近邻算法，召回率 > 95%
- **IP (内积)**: 配合 L2 归一化等价于余弦相似度，计算更快

#### 5.2.3 向量归一化

```python
def _l2_normalize(vec: list[float]) -> list[float]:
    s = 0.0
    for v in vec:
        s += float(v) * float(v)
    if s <= 0.0:
        return vec
    inv = (s**0.5)
    if inv == 0.0:
        return vec
    return [float(v) / inv for v in vec]
```

**为什么归一化？**

- L2 归一化后，内积（IP）等价于余弦相似度
- 避免向量长度差异影响相似度计算
- 提高搜索稳定性

#### 5.2.4 用户隔离查询

```python
expr = f'user_id == "{user_id}"'
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "IP", "params": {"ef": 64}},
    limit=int(limit),
    expr=expr,  # 强制用户过滤
    output_fields=["id", "user_id", "created_at"],
)
```

**安全性**：

- 在 Milvus 层面强制过滤 `user_id`
- 防止向量检索时跨用户泄露
- 即使客户端错误配置也不会泄露数据

---

## 6. API 设计

### 6.1 添加记忆

#### 6.1.1 请求

```http
POST /v1/memories HTTP/1.1
Host: localhost:8830
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json

{
  "user_id": "user_123",
  "text": "我喜欢科幻电影",
  "tags": ["preference"],
  "metadata": {
    "source": "chat",
    "confidence": 0.9
  }
}
```

#### 6.1.2 响应

**成功**（200 OK）：

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**失败**（400 Bad Request）：

```json
{
  "detail": "text is required"
}
```

#### 6.1.3 处理流程

```mermaid
graph TD
    A[POST /v1/memories] --> B{参数校验}
    B -->|失败| C[400 Bad Request]
    B -->|成功| D[文本长度限制]
    D --> E[插入 PostgreSQL]
    E --> F{向量后端可用?}
    F -->|否| G[返回 memory_id]
    F -->|是| H[生成 embedding]
    H --> I{embedding 成功?}
    I -->|否| J{MEM0_STRICT_EMBEDDINGS}
    J -->|true| K[500 Error]
    J -->|false| L[记录警告日志]
    L --> G
    I -->|是| M[插入 Milvus]
    M --> N[返回 memory_id]
```

### 6.2 搜索记忆

#### 6.2.1 请求

```http
POST /v1/memories/search HTTP/1.1
Host: localhost:8830
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json

{
  "user_id": "user_123",
  "query": "推荐一些电影",
  "limit": 5
}
```

#### 6.2.2 响应

**成功**（200 OK）：

```json
{
  "memories": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "text": "我喜欢科幻电影",
      "score": 0.85,
      "tags": ["preference"],
      "created_at": "2025-01-21T10:30:00Z"
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "text": "我不喜欢恐怖片",
      "score": 0.72,
      "tags": ["preference", "dislike"],
      "created_at": "2025-01-21T11:15:00Z"
    }
  ]
}
```

**失败**（500 Internal Server Error）：

```json
{
  "detail": "embedding failed: connection timeout"
}
```

#### 6.2.3 处理流程

```mermaid
graph TD
    A[POST /v1/memories/search] --> B{向量后端可用?}
    B -->|否| C[返回空列表]
    B -->|是| D[生成 query embedding]
    D --> E{embedding 成功?}
    E -->|否| F{MEM0_STRICT_EMBEDDINGS}
    F -->|true| G[500 Error]
    F -->|false| H[返回空列表]
    E -->|是| I[Milvus 向量搜索<br/>expr: user_id == xxx]
    I --> J[获取 memory_ids + scores]
    J --> K[PostgreSQL 批量获取元数据<br/>WHERE id = ANY ids]
    K --> L[组装 MemoryOut]
    L --> M[返回 MemorySearchResponse]
```

---

## 7. 配置系统

### 7.1 服务端配置

**文件**: `backend/server/mem0_service/settings.py`

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `MEM0_SERVICE_HOST` | string | `0.0.0.0` | 服务监听地址 |
| `MEM0_SERVICE_PORT` | int | `8830` | 服务监听端口 |
| `MEM0_API_KEY` | string | `""` | API 认证密钥（空值禁用认证） |
| `MEM0_AUTH_MODE` | string | `"api_key"` | 认证模式：`api_key` / `jwt` |
| `MEM0_JWT_SECRET` | string | `""` | JWT 验签密钥（仅 `jwt` 模式；空值时可复用 `MEM0_API_KEY`） |
| `MEM0_JWT_ALGORITHMS` | string | `"HS256"` | JWT 算法白名单（逗号分隔） |
| `MEM0_TRUST_REQUEST_USER_ID` | bool | `True` | 是否信任请求体里的 `user_id`（internal 模式推荐） |
| `MEM0_USER_ID_HEADER` | string | `"x-user-id"` | 上游注入 user_id 的 Header 名（production 推荐） |
| `MEM0_PG_DSN` | string | `postgresql://postgres:postgres@postgres:5432/graphrag_chat` | PostgreSQL 连接字符串 |
| `MEM0_VECTOR_BACKEND` | string | `"milvus"` | 向量后端：`milvus` 或 `none` |
| `MEM0_MILVUS_HOST` | string | `"host.docker.internal"` | Milvus 主机地址（⚠️ Linux 需要额外配置）|
| `MEM0_MILVUS_PORT` | int | `19530` | Milvus 端口 |
| `MEM0_MILVUS_COLLECTION` | string | `"mem0_memories"` | Milvus Collection 名称 |
| `MEM0_EMBEDDING_DIM` | int | `None` | Embedding 维度（None 表示动态检测） |
| `MEM0_MAX_TEXT_CHARS` | int | `4000` | 记忆文本最大长度 |
| `MEM0_DEFAULT_LIMIT` | int | `5` | 默认搜索返回数量 |
| `MEM0_MAX_LIMIT` | int | `50` | 搜索返回数量上限 |
| `MEM0_STRICT_EMBEDDINGS` | bool | `False` | Embedding 失败时是否中断 |
| `MEM0_ENABLE_TTL` | bool | `False` | 是否启用 TTL（到期后查询过滤） |
| `MEM0_DEFAULT_TTL_DAYS` | int | `90` | 默认 TTL 天数（未识别标签时使用） |
| `MEM0_OPENAI_API_KEY` | string | `""` | Embeddings API Key（推荐；避免与本机其他服务的 `OPENAI_*` 冲突） |
| `MEM0_OPENAI_BASE_URL` | string | `""` | OpenAI 兼容 Base URL（如 DashScope：`https://dashscope.aliyuncs.com/compatible-mode/v1`） |
| `MEM0_OPENAI_EMBEDDINGS_MODEL` | string | `""` | Embeddings 模型名（如 DashScope/Qwen：`text-embedding-v3`） |

### 7.2 客户端配置

**文件**: `backend/infrastructure/config/settings.py`

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `MEM0_BASE_URL` | string | `""` | mem0 服务地址（空值禁用） |
| `MEM0_API_KEY` | string | `""` | API 认证密钥 |
| `MEM0_TIMEOUT_S` | float | `10.0` | HTTP 请求超时（秒） |
| `MEM0_SEARCH_PATH` | string | `"/v1/memories/search"` | 搜索 API 路径 |
| `MEM0_ADD_PATH` | string | `"/v1/memories"` | 添加 API 路径 |

### 7.3 功能开关

**文件**: `backend/config/settings.py`

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `MEMORY_ENABLE` | bool | `False` | 是否启用记忆召回 |
| `MEMORY_WRITE_ENABLE` | bool | `False` | 是否启用记忆写入 |
| `MEMORY_TOP_K` | int | `5` | 召回记忆数量 |
| `MEMORY_MIN_SCORE` | float | `0.6` | 最低相关性分数 |
| `MEMORY_MAX_CHARS` | int | `1200` | 记忆上下文最大长度 |
| `MEMORY_WRITE_MODE` | string | `"rules"` | 写入模式：`rules`（规则提取） |

### 7.4 配置示例

#### 7.4.1 完整配置（.env）

```env
# ===== mem0 自托管服务配置 =====
MEM0_SERVICE_HOST=0.0.0.0
MEM0_SERVICE_PORT=8830
MEM0_API_KEY=your-secret-api-key

# PostgreSQL（复用现有数据库）
# 注意：容器内端口默认 5432，宿主机映射端口根据 docker/docker-compose.yaml 配置
# 宿主机访问用 localhost:5433，容器间通信用 postgres:5432
MEM0_PG_DSN=postgresql://postgres:postgres@postgres:5432/graphrag_chat

# Milvus 向量后端
MEM0_VECTOR_BACKEND=milvus
MEM0_MILVUS_HOST=host.docker.internal
MEM0_MILVUS_PORT=19530
MEM0_MILVUS_COLLECTION=mem0_memories

# Embedding 配置（服务端侧；推荐用 MEM0_OPENAI_*，避免与本机其他服务的 OPENAI_* 冲突）
# Qwen/DashScope（OpenAI 兼容接口）示例：
MEM0_OPENAI_API_KEY=sk-xxx
MEM0_OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MEM0_OPENAI_EMBEDDINGS_MODEL=text-embedding-v3
#
# 如果你的 .env 里配置了 HTTP_PROXY/HTTPS_PROXY 且指向 localhost，
# 容器内可能无法访问（会表现为 Connection error）。本仓库的 compose
# 会对 mem0 容器显式清空 proxy；如确有需要请改为容器可达的代理地址。

# 安全参数
MEM0_MAX_TEXT_CHARS=4000
MEM0_STRICT_EMBEDDINGS=false

# ===== mem0 客户端配置（Backend） =====
MEM0_BASE_URL=http://localhost:8830
MEM0_API_KEY=your-secret-api-key
MEM0_TIMEOUT_S=10.0

# ===== 功能开关 =====
MEMORY_ENABLE=true
MEMORY_WRITE_ENABLE=true
MEMORY_TOP_K=5
MEMORY_MIN_SCORE=0.6
MEMORY_MAX_CHARS=1200
MEMORY_WRITE_MODE=rules
```

#### 7.4.2 最小配置（测试环境）

```env
# 禁用向量索引（仅元数据存储，无语义召回能力）
MEM0_VECTOR_BACKEND=none

# 禁用记忆功能（完全关闭 mem0）
MEMORY_ENABLE=false
MEMORY_WRITE_ENABLE=false
```

**注意**：`MEM0_VECTOR_BACKEND=none` 时向量搜索会返回空，语义召回功能不可用。如需测试召回功能，请保持 Milvus 配置。

#### 7.4.3 生产配置

```env
# 启用严格模式（embedding 失败时中断）
MEM0_STRICT_EMBEDDINGS=true

# 增加超时时间
MEM0_TIMEOUT_S=30.0

# 降低召回阈值（提高召回率）
MEMORY_MIN_SCORE=0.5
MEMORY_TOP_K=10
```

---

## 8. 部署指南

### 8.1 Docker Compose 部署

#### 8.1.1 启动服务

```bash
# 1. 启动基础服务（PostgreSQL, Neo4j）
docker compose -f docker/docker-compose.yaml up -d

# 2. 启动 mem0 自托管服务
docker compose -f docker/docker-compose.yaml -f docker/docker-compose.mem0.yaml up -d --build

# 3. 检查服务状态
docker compose ps
curl http://localhost:8830/healthz
```

#### 8.1.2 docker/docker-compose.mem0.yaml

```yaml
version: "3.8"
services:
  mem0:
    build:
      context: ..
      dockerfile: docker/Dockerfile.mem0
    env_file:
      - ../.env
    ports:
      - "8830:8830"
    environment:
      MEM0_API_KEY: "${MEM0_API_KEY:-}"
      MEM0_AUTH_MODE: "${MEM0_AUTH_MODE:-api_key}"
      MEM0_JWT_SECRET: "${MEM0_JWT_SECRET:-}"
      MEM0_JWT_ALGORITHMS: "${MEM0_JWT_ALGORITHMS:-HS256}"
      MEM0_TRUST_REQUEST_USER_ID: "${MEM0_TRUST_REQUEST_USER_ID:-true}"
      MEM0_USER_ID_HEADER: "${MEM0_USER_ID_HEADER:-x-user-id}"
      MEM0_PG_DSN: "${MEM0_PG_DSN:-postgresql://postgres:postgres@postgres:5432/graphrag_chat}"
      MEM0_VECTOR_BACKEND: "${MEM0_VECTOR_BACKEND:-milvus}"
      MEM0_MILVUS_HOST: "${MEM0_MILVUS_HOST:-host.docker.internal}"  # ⚠️ Linux 见下文
      MEM0_MILVUS_PORT: "${MEM0_MILVUS_PORT:-19530}"
      MEM0_MILVUS_COLLECTION: "${MEM0_MILVUS_COLLECTION:-mem0_memories}"
      MEM0_EMBEDDING_DIM: "${MEM0_EMBEDDING_DIM:-}"
      MEM0_ENABLE_TTL: "${MEM0_ENABLE_TTL:-false}"
      MEM0_DEFAULT_TTL_DAYS: "${MEM0_DEFAULT_TTL_DAYS:-90}"

      # Embeddings config (OpenAI compatible; recommend MEM0_OPENAI_* to avoid collisions)
      MEM0_OPENAI_API_KEY: "${MEM0_OPENAI_API_KEY:-}"
      MEM0_OPENAI_BASE_URL: "${MEM0_OPENAI_BASE_URL:-}"
      MEM0_OPENAI_EMBEDDINGS_MODEL: "${MEM0_OPENAI_EMBEDDINGS_MODEL:-}"

      # Avoid inheriting host proxy settings that point to localhost.
      HTTP_PROXY: ""
      HTTPS_PROXY: ""
      NO_PROXY: "localhost,127.0.0.1,postgres,host.docker.internal"
    depends_on:
      - postgres
    restart: unless-stopped
```

#### 8.1.3 docker/Dockerfile.mem0

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=120

COPY requirements.mem0.txt /app/requirements.mem0.txt
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r /app/requirements.mem0.txt

COPY backend /app/backend
ENV PYTHONPATH=/app/backend

EXPOSE 8830
CMD ["python", "-m", "uvicorn", "server.mem0_service.main:app", "--host", "0.0.0.0", "--port", "8830"]
```

#### 8.1.4 Linux 兼容性说明

**问题**：`host.docker.internal` 在 macOS/Windows 上默认可用，但在 Linux 上需要额外配置。

**解决方案 1：使用 `extra_hosts`（推荐）**

修改 `docker/docker-compose.mem0.yaml`：

```yaml
services:
  mem0:
    # ... 其他配置
    extra_hosts:
      - "host.docker.internal:host-gateway"  # Linux 需要显式映射
```

**解决方案 2：将 Milvus 加入同一 Compose 网络**

如果 Milvus 也通过 Docker Compose 部署，直接使用服务名：

```yaml
services:
  milvus:
    image: milvusdb/milvus:latest
    # ... Milvus 配置

  mem0:
    # ... 其他配置
    environment:
      MEM0_MILVUS_HOST: "milvus"  # 使用 Compose 服务名而非 host.docker.internal
    depends_on:
      - milvus
```

**解决方案 3：使用宿主机网络（仅适用于 Linux）**

```yaml
services:
  mem0:
    network_mode: host  # 使用宿主机网络
    # ⚠️ 注意：ports 映射会被忽略，端口直接占用宿主机
    environment:
      MEM0_MILVUS_HOST: "localhost"  # 直接访问宿主机 localhost
```

**副作用警告**：
- `network_mode: host` 会**忽略** `ports` 映射配置
- 容器端口直接占用宿主机端口（如 8830），可能与其他服务冲突
- 仅适用于 Linux，且需确保端口未被占用

**说明**：
- macOS/Windows：默认支持 `host.docker.internal`，无需额外配置
- Linux：需要上述 3 种方案之一，推荐**方案 1**（`extra_hosts`）或**方案 2**（同一 Compose 网络）

### 8.2 本地开发部署

#### 8.2.1 启动 mem0 服务

```bash
# 方式 1：直接运行（开发模式）
cd backend
python -m uvicorn server.mem0_service.main:app --host 0.0.0.0 --port 8830 --reload

# 方式 2：Docker Compose（推荐）
docker compose -f docker/docker-compose.yaml -f docker/docker-compose.mem0.yaml up -d mem0
```

#### 8.2.2 测试服务

```bash
# 健康检查
curl http://localhost:8830/healthz

# 添加测试记忆
curl -X POST http://localhost:8830/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "text": "我喜欢科幻电影", "tags": ["preference"]}'

# 搜索记忆
curl -X POST http://localhost:8830/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "query": "电影推荐", "limit": 5}'
```

### 8.3 Milvus 部署

#### 8.3.1 Docker 部署 Milvus

> **注意**：以下命令仅作为快速示例，实际部署请参考 [Milvus 官方文档](https://milvus.io/docs/install_standalone-docker.md)，不同版本和部署形态（Standalone/Cluster）配置差异较大。

```bash
# 使用官方 Milvus Standalone 镜像（示例）
docker run -d \
  --name milvus-standalone \
  -p 19530:19530 \
  -p 9091:9091 \
  -v /path/to/milvus:/var/lib/milvus \
  milvusdb/milvus:latest
```

#### 8.3.2 验证 Milvus 连接

```python
from pymilvus import connections

connections.connect(alias="default", host="localhost", port="19530")
print("Milvus 连接成功！")
```

### 8.4 生产部署检查清单

- [ ] 配置 `MEM0_API_KEY` 并启用认证
- [ ] PostgreSQL 和 Milvus 数据持久化配置
- [ ] 设置资源限制（CPU/Memory）
- [ ] 配置日志收集和监控
- [ ] 设置健康检查和自动重启
- [ ] 配置 HTTPS 和负载均衡
- [ ] 备份策略（数据库快照）
- [ ] 灾难恢复计划

---

## 9. 安全设计

### 9.1 认证与授权

#### 9.1.1 API 密钥认证

```python
def _require_auth(authorization: Optional[str] = Header(default=None)) -> None:
    if not MEM0_API_KEY:
        return  # 未配置时跳过（开发模式）
    expected = f"Bearer {MEM0_API_KEY}"
    if (authorization or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

**最佳实践**：

- 生产环境必须配置 `MEM0_API_KEY`
- 定期轮换 API 密钥
- 使用强随机密钥（至少 32 字符）

#### 9.1.2 用户隔离

```python
# Milvus 搜索时强制过滤
expr = f'user_id == "{user_id}"'
results = collection.search(..., expr=expr, ...)

# PostgreSQL 查询时强制过滤
await conn.fetch(
    "SELECT * FROM mem0.memories WHERE user_id = $1 AND id = ANY($2::text[]);",
    user_id, ids
)
```

**多层防护**：

1. **应用层**: `MemoryService` 传递正确的 `user_id`
2. **服务层**: mem0 服务所有 API 强制要求 `user_id`
3. **存储层**: Milvus 和 PostgreSQL 查询强制过滤

### 9.2 数据脱敏

#### 9.2.1 敏感信息识别

```python
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\b(\+?\d[\d -]{7,}\d)\b")

def guardrail_memory_text(text: str) -> Optional[str]:
    cleaned = text.strip()
    if not cleaned:
        return None
    cleaned = _EMAIL_RE.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _PHONE_RE.sub("[REDACTED_PHONE]", cleaned)
    return cleaned.strip() or None
```

#### 9.2.2 脱敏示例

| 原始文本 | 脱敏后 |
|---------|--------|
| "我的邮箱是 user@example.com" | "我的邮箱是 [REDACTED_EMAIL]" |
| "联系电话 +86 138 0013 8000" | "联系电话 [REDACTED_PHONE]" |
| "我叫张三" | "我叫张三"（无敏感信息） |

### 9.3 输入验证

#### 9.3.1 文本长度限制

```python
def _cap_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) <= int(MEM0_MAX_TEXT_CHARS):
        return t
    return t[: int(MEM0_MAX_TEXT_CHARS)].rstrip()
```

#### 9.3.2 限制参数校验

```python
def _cap_limit(limit: int) -> int:
    try:
        limit = int(limit)
    except Exception:
        limit = int(MEM0_DEFAULT_LIMIT)
    if limit <= 0:
        limit = int(MEM0_DEFAULT_LIMIT)
    return min(limit, int(MEM0_MAX_LIMIT))
```

**防止资源耗尽**：

- 限制单次添加的文本长度（默认 4000 字符）
- 限制单次搜索的返回数量（默认最多 50 条）
- 防止恶意大请求拖垮服务

### 9.4 传输安全

**生产环境建议**：

1. **HTTPS**: 使用反向代理（Nginx/Traefik）终止 TLS
2. **内网通信**: Backend → mem0 服务走内网
3. **API 密钥**: 通过环境变量传递，不写入日志

---

## 10. 容错与降级

### 10.1 降级策略

#### 10.1.1 三层降级机制

```mermaid
graph TD
    A[用户请求] --> B{MEMORY_ENABLE?}
    B -->|false| C[跳过记忆召回]
    B -->|true| D{mem0 服务可用?}
    D -->|false| E[返回空记忆列表]
    D -->|true| F{调用成功?}
    F -->|false| G[捕获异常，返回 None]
    F -->|true| H[正常召回记忆]

    C --> I[主链路继续]
    E --> I
    G --> I
    H --> I
```

#### 10.1.2 实现代码

```python
async def recall_context(self, *, user_id: str, query: str) -> Optional[str]:
    try:
        memories = await self._store.search(
            user_id=user_id,
            query=query,
            top_k=int(self._policy.top_k),
        )
    except Exception:
        # Best-effort degradation: memory recall must never break chat.
        return None
    return build_memory_context(memories=memories, policy=self._policy)
```

**降级原则**：

- 记忆召回失败**绝不**中断主链路对话
- 异常捕获后返回 `None`，主链路继续执行
- 记录错误日志供排查

### 10.2 最佳努力模式

#### 10.2.1 Embedding 失败处理

```python
try:
    emb = _embed_text(text)
    app.state.vector.add(memory_id=mid, user_id=req.user_id, embedding=emb)
except Exception as exc:
    if MEM0_STRICT_EMBEDDINGS:
        raise HTTPException(status_code=500, detail=f"embedding/indexing failed: {exc}") from exc
    logger.warning("mem0 indexing failed (best-effort): %s", exc)
```

**两种模式**：

| 模式 | Embedding 失败时行为 | 适用场景 |
|------|---------------------|----------|
| `MEM0_STRICT_EMBEDDINGS=true` | 返回 500 错误，拒绝写入 | 测试环境，要求数据完整性 |
| `MEM0_STRICT_EMBEDDINGS=false` | 记录警告，继续保存元数据 | 生产环境，优先可用性 |

**权衡**：

- **严格模式**: 确保所有记忆都可以被搜索，但可能丢失部分记忆
- **最佳努力**: 确保所有记忆都被保存，但部分无法被搜索

### 10.3 超时控制

```python
self._timeout_s = float(timeout_s or 10.0)
timeout = aiohttp.ClientTimeout(total=self._timeout_s)
self._session = aiohttp.ClientSession(timeout=timeout)
```

**超时设置建议**：

- 开发环境: 10 秒（默认）
- 生产环境: 5-10 秒
- 高并发场景: 3-5 秒

### 10.4 熔断机制

**未实现，可作为未来增强**：

- 连续失败 N 次后暂时跳过 mem0 调用
- 一段时间后尝试恢复
- 防止级联故障

---

## 11. 监控与运维

### 11.1 健康检查

#### 11.1.1 端点

```python
@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"ok": True, "vector_backend": MEM0_VECTOR_BACKEND}
```

#### 11.1.2 使用方式

```bash
# 手动检查
curl http://localhost:8830/healthz

# Kubernetes 健康检查
livenessProbe:
  httpGet:
    path: /healthz
    port: 8830
  initialDelaySeconds: 10
  periodSeconds: 30
```

### 11.2 日志记录

#### 11.2.1 关键日志点

```python
logger.info("mem0 service started", extra={
    "vector_backend": MEM0_VECTOR_BACKEND,
    # 注意：不要记录完整 DSN，可能包含敏感信息
    "pg_host": MEM0_PG_DSN.split("@")[-1] if "@" in MEM0_PG_DSN else "unknown",
})

logger.warning("mem0 indexing failed (best-effort): %s", exc, extra={
    "user_id": _hash_user_id(req.user_id),  # 生产环境应 hash/脱敏
    "text_length": len(text),
})

logger.error("mem0 search failed", exc_info=True, extra={
    "user_id": _hash_user_id(req.user_id),  # 生产环境应 hash/脱敏
    "query": req.query[:50] if req.query else "",  # 截断 query（避免泄露敏感内容）
})

# 脱敏辅助函数
def _hash_user_id(user_id: str) -> str:
    """生产环境应对 user_id 进行 hash 或截断。"""
    # 示例：只记录前 8 位或使用 hash
    return user_id[:8] if user_id else "unknown"
```

**日志脱敏说明**：
- ❌ **避免**：记录完整的 `user_id`（可能为敏感标识符）
- ❌ **避免**：记录完整的 `query`（可能包含用户隐私信息）
- ✅ **推荐**：
  - `user_id` → 使用 hash（SHA-256）或截断（如前 8 位）
  - `query` → 截断至 50-100 字符，或移除敏感词（邮箱、电话等）
  - 生产环境建议配置日志过滤规则（如 `python-json-logger` + 字段级过滤）

#### 11.2.2 日志级别

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| DEBUG | 详细调试信息 | 向量维度、搜索参数 |
| INFO | 正常业务流程 | 服务启动、记忆添加成功 |
| WARNING | 可恢复的异常 | Embedding 失败（最佳努力模式） |
| ERROR | 需要关注的错误 | 数据库连接失败、超时 |

### 11.3 指标监控

**建议添加的指标**：

```python
from prometheus_client import Counter, Histogram

# 记忆添加计数（注意：避免使用 user_id 等高基数 label）
memory_add_total = Counter(
    "mem0_memory_add_total",
    "Total number of memories added",
    ["status"]  # status: success / failure
)

# 记忆搜索计数
memory_search_total = Counter(
    "mem0_memory_search_total",
    "Total number of memory searches",
    []  # 不使用 user_id label，避免高基数
)

# 搜索延迟
memory_search_duration = Histogram(
    "mem0_memory_search_duration_seconds",
    "Memory search duration",
    []  # 不使用 user_id label
)

# 使用方式
memory_add_total.labels(status="success").inc()
memory_search_total.inc()
memory_search_duration.observe(0.123)

# 如需按用户维度分析，请使用日志而非 Prometheus label
```

**注意**：避免在 Prometheus 指标中使用 `user_id` 等**高基数 label**（cardinality > 10,000），这会导致 TSDB 性能问题。用户维度的分析建议通过日志系统（如 ELK）实现。

### 11.4 告警规则

**Prometheus 告警示例**：

```yaml
groups:
  - name: mem0_alerts
    rules:
      - alert: Mem0HighErrorRate
        expr: rate(mem0_memory_add_total{status="failure"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "mem0 添加记忆失败率过高"
          description: "过去 5 分钟失败率超过 10%"

      - alert: Mem0SearchLatencyHigh
        expr: histogram_quantile(0.95, mem0_memory_search_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "mem0 搜索延迟过高"
          description: "P95 延迟超过 1 秒"
```

---

## 12. 最佳实践

### 12.1 开发建议

#### 12.1.1 本地开发

```bash
# 1. 禁用向量索引（减少依赖）
export MEM0_VECTOR_BACKEND=none

# 2. 禁用认证（简化测试）
export MEM0_API_KEY=

# 3. 启用详细日志
export LOG_LEVEL=DEBUG
```

#### 12.1.2 单元测试

本项目测试体系使用 `unittest` + `bash scripts/test.sh`，测试示例应遵循项目规范：

```python
# test_mem0_integration.py
import sys
import unittest
from pathlib import Path

# 添加 backend 根目录到路径（项目规范）
_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from application.chat.memory_service import MemoryService
from application.ports.memory_store_port import MemoryStorePort
from domain.memory import MemoryItem
from domain.memory.policy import MemoryPolicy


class _StubMemoryStore(MemoryStorePort):
    """测试用的模拟存储，避免真实数据库依赖。"""

    async def search(self, *, user_id: str, query: str, top_k: int) -> list[MemoryItem]:
        return [
            MemoryItem(id="m1", text="用户喜欢科幻电影", score=0.9),
            MemoryItem(id="m2", text="用户不喜欢恐怖片", score=0.8),
        ]

    async def add(self, *, user_id: str, text: str, tags=None, metadata=None) -> str:
        return "test_id_123"

    async def close(self) -> None:
        pass


class TestMem0Integration(unittest.IsolatedAsyncioTestCase):
    """测试 mem0 记忆服务集成（项目测试规范）。"""

    async def test_memory_recall_context(self) -> None:
        """测试记忆召回功能。"""
        memory = MemoryService(
            store=_StubMemoryStore(),
            policy=MemoryPolicy(top_k=5, min_score=0.0, max_chars=500),
            write_enabled=False,
        )

        context = await memory.recall_context(
            user_id="test_user",
            query="电影推荐",
        )

        # 验证召回结果包含记忆内容
        self.assertIsInstance(context, str)
        self.assertIn("用户喜欢科幻电影", context)

    async def test_memory_write_enabled(self) -> None:
        """测试记忆写入功能（启用写入）。"""
        memory = MemoryService(
            store=_StubMemoryStore(),
            policy=MemoryPolicy(top_k=5, min_score=0.0, max_chars=500),
            write_enabled=True,
        )

        # maybe_write 不会抛出异常（best-effort 语义）
        await memory.maybe_write(
            user_id="test_user",
            user_message="我喜欢科幻电影",
            assistant_message="好的，已记录您的偏好",
            metadata={"source": "test"},
        )

        # 如果有异常，测试会失败；否则通过

    async def test_memory_write_disabled(self) -> None:
        """测试记忆写入功能（禁用写入）。"""
        memory = MemoryService(
            store=_StubMemoryStore(),
            policy=MemoryPolicy(top_k=5, min_score=0.0, max_chars=500),
            write_enabled=False,
        )

        # write_enabled=False 时不会调用 store.add
        await memory.maybe_write(
            user_id="test_user",
            user_message="我喜欢科幻电影",
            assistant_message="好的，已记录您的偏好",
        )

        # 测试通过即表示正确跳过写入


# 运行测试（项目规范）：
# bash scripts/ut.sh test.test_mem0_integration -v
```

**说明**：
- 使用 `unittest.IsolatedAsyncioTestCase` 进行异步测试
- 测试依赖（数据库/外部服务）通过 stub/mock 隔离
- 运行测试使用 `bash scripts/ut.sh` 或 `bash scripts/test.sh`
- 测试 `MemoryService` 应用层而非直接测试 FastAPI 路由
- 参考：`test/test_mem0_memory_plumbing.py`（项目实际测试文件）

### 12.2 生产建议

#### 12.2.1 配置清单

```env
# 安全
MEM0_API_KEY=<强随机密钥>
MEM0_STRICT_EMBEDDINGS=true

# 性能
MEM0_TIMEOUT_S=10.0
MEMORY_TOP_K=5
MEMORY_MIN_SCORE=0.6

# 资源限制
# Docker: --memory="2g" --cpus="2"
```

#### 12.2.2 备份策略

```bash
# PostgreSQL 备份（使用 docker-compose 服务名）
docker exec postgres pg_dump -U postgres graphrag_chat > backup.sql

# 或使用 docker-compose exec（推荐）
docker compose exec postgres pg_dump -U postgres graphrag_chat > backup.sql

# Milvus 备份（需要额外工具）
# 参考：https://milvus.io/docs/backup_guide.md
```

### 12.3 性能优化

#### 12.3.1 批量操作

**当前**: 单条添加记忆

**优化方向**: 支持批量添加

```python
@app.post("/v1/memories/batch")
async def add_memories_batch(req: MemoryBatchRequest) -> MemoryBatchResponse:
    # 1. 批量插入 PostgreSQL
    # 2. 批量生成 embeddings（并行）
    # 3. 批量插入 Milvus
    pass
```

#### 12.3.2 连接池优化

```python
# PostgresMemoryStore
self._pool = await asyncpg.create_pool(
    dsn=self._dsn,
    min_size=5,   # 最小连接数
    max_size=20,  # 最大连接数
)
```

#### 12.3.3 Embedding 缓存

**优化方向**: 缓存常见文本的 embedding

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def _embed_text_cached(text: str) -> list[float]:
    return _embed_text(text)
```

### 12.4 常见问题

#### 12.4.1 Milvus 连接失败

**症状**: `MilvusException: connection failed`

**排查**:

```bash
# 1. 检查 Milvus 是否运行
docker ps | grep milvus

# 2. 测试连接
telnet localhost 19530

# 3. 检查配置
echo $MEM0_MILVUS_HOST $MEM0_MILVUS_PORT
```

#### 12.4.2 Embedding 超时

**症状**: `TimeoutError: embedding generation timeout`

**解决**:

```bash
# 增加超时时间
export MEM0_TIMEOUT_S=30

# 或切换到更快的 embedding 模型
export OPENAI_EMBEDDINGS_MODEL=text-embedding-3-small
```

#### 12.4.3 记忆召回为空

**症状**: 搜索返回空列表

**排查**:

1. 检查 `user_id` 是否一致
2. 检查向量索引是否成功
3. 降低 `MEMORY_MIN_SCORE` 阈值
4. 检查 embedding 模型是否可用

---

## 13. 高级能力增强

> **章节说明**: 本章介绍 mem0/长期记忆服务的 7 大高级能力，包括当前实现状态、设计方案和未来增强方向。

### 13.1 能力矩阵总览

| 能力 | 当前状态 | 优先级 | 复杂度 | 预期收益 |
|------|---------|--------|--------|----------|
| **13.1 用户画像/偏好中心** | ⚠️ 部分实现 | 🔴 高 | 🟡 中 | 大幅减少重复沟通 |
| **13.2 可控写入策略** | 🟢 基础实现 | 🔴 高 | 🔴 高 | 降低记忆污染，提升质量 |
| **13.3 记忆生命周期** | ❌ 未实现 | 🟡 中 | 🟢 低 | 合规与隐私保护 |
| **13.4 多域/多会话共享** | ❌ 未实现 | 🟢 低 | 🟡 中 | 跨渠道连续性 |
| **13.5 Agent Tool 化** | ❌ 未实现 | 🟡 中 | 🟡 中 | 按需召回，减少成本 |
| **13.6 路由/检索增强** | ❌ 未实现 | 🔴 高 | 🔴 高 | 个性化路由和过滤 |
| **13.7 观测与评估** | ❌ 未实现 | 🟡 中 | 🟢 低 | 数据驱动优化 |

---

### 13.2 用户画像/偏好中心

#### 13.2.1 当前实现状态

**已实现**：
- ✅ 标签系统（`preference/dislike/constraint/fact/identity`）
- ✅ 基于标签的召回（`tags` 字段过滤）
- ✅ 规则提取（中英文模式识别）

**未实现**：
- ❌ 画像聚合与管理
- ❌ 偏好权重计算
- ❌ 画像可视化与用户编辑

#### 13.2.2 设计方案

##### A. 画像数据结构

**新增表**：`mem0.user_profiles`

```sql
CREATE TABLE IF NOT EXISTS mem0.user_profiles (
    user_id TEXT PRIMARY KEY,
    display_name TEXT,
    preferences JSONB NOT NULL DEFAULT '{}',      -- {"favorite_genres": ["科幻", "动作"]}
    constraints JSONB NOT NULL DEFAULT '{}',       -- {"max_duration": 120, "exclude_genres": ["恐怖"]}
    facts JSONB NOT NULL DEFAULT '{}',             -- {"name": "张三", "location": "北京"}
    stats JSONB NOT NULL DEFAULT '{}',             -- {"total_memories": 42, "last_updated": "2025-01-21"}
    version INT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS mem0_user_profiles_updated_at_idx ON mem0.user_profiles(updated_at);
```

**JSONB 结构示例**：

```json
{
  "preferences": {
    "favorite_genres": ["科幻", "动作", "悬疑"],
    "favorite_actors": ["刘德华", "成龙"],
    "preferred_duration": "90-120分钟",
    "language_preference": "中文"
  },
  "constraints": {
    "exclude_genres": ["恐怖", "血腥"],
    "max_duration": 150,
    "content_warnings": ["避免暴力场景"]
  },
  "facts": {
    "name": "张三",
    "age": 28,
    "location": "北京",
    "occupation": "工程师"
  },
  "stats": {
    "total_memories": 42,
    "preference_count": 15,
    "constraint_count": 8,
    "fact_count": 19,
    "last_updated": "2025-01-21T10:30:00Z"
  }
}
```

##### B. 画像构建策略

**文件**: `backend/domain/memory/profile_builder.py`（新增）

```python
from typing import Optional
from collections import Counter
from datetime import datetime

@dataclass
class UserProfile:
    user_id: str
    preferences: dict[str, Any]
    constraints: dict[str, Any]
    facts: dict[str, Any]
    stats: dict[str, Any]
    version: int
    updated_at: datetime

class ProfileBuilder:
    """从分散的记忆聚合成用户画像。"""

    async def build_profile(self, *, user_id: str, memories: list[MemoryItem]) -> UserProfile:
        # 1. 按标签分组
        by_tag: dict[str, list[MemoryItem]] = {}
        for m in memories:
            for tag in m.tags:
                by_tag.setdefault(tag, []).append(m)

        # 2. 聚合偏好（preference）
        preferences = self._aggregate_preferences(by_tag.get("preference", []))

        # 3. 聚合约束（constraint）
        constraints = self._aggregate_constraints(by_tag.get("constraint", []))

        # 4. 聚合事实（fact）
        facts = self._aggregate_facts(by_tag.get("fact", []))

        # 5. 统计信息
        stats = {
            "total_memories": len(memories),
            "preference_count": len(by_tag.get("preference", [])),
            "constraint_count": len(by_tag.get("constraint", [])),
            "fact_count": len(by_tag.get("fact", [])),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        return UserProfile(
            user_id=user_id,
            preferences=preferences,
            constraints=constraints,
            facts=facts,
            stats=stats,
            version=1,
            updated_at=datetime.now(timezone.utc)
        )

    def _aggregate_preferences(self, memories: list[MemoryItem]) -> dict[str, Any]:
        """从偏好记忆中提取结构化信息。"""
        # 示例：从"我喜欢科幻电影"中提取"科幻"
        genres: Counter = Counter()
        for m in memories:
            text = m.text
            # 简单规则提取（可升级为 LLM 提取）
            if "科幻" in text:
                genres["科幻"] += 1
            if "动作" in text:
                genres["action"] += 1
            # ... 更多规则

        return {
            "favorite_genres": [g for g, _ in genres.most_common(5)],
            "preference_sources": [m.text for m in memories[:3]]  # 保留原始记忆
        }

    def _aggregate_constraints(self, memories: list[MemoryItem]) -> dict[str, Any]:
        """从约束记忆中提取限制条件。"""
        constraints = []
        for m in memories:
            constraints.append(m.text)

        # 结构化提取（示例）
        exclude_genres = []
        max_duration = None
        for c in constraints:
            if "恐怖" in c:
                exclude_genres.append("恐怖")
            if "分钟" in c:
                # 提取数字：如"120分钟以内"
                import re
                match = re.search(r'(\d+)\s*分钟', c)
                if match:
                    duration = int(match.group(1))
                    if max_duration is None or duration < max_duration:
                        max_duration = duration

        return {
            "exclude_genres": exclude_genres,
            "max_duration": max_duration,
            "constraint_sources": constraints
        }

    def _aggregate_facts(self, memories: list[MemoryItem]) -> dict[str, Any]:
        """从事实记忆中提取用户信息。"""
        facts = {}
        for m in memories:
            # 提取键值对（可升级为 LLM 提取）
            if "我叫" in m.text:
                import re
                match = re.search(r'我叫(.+)', m.text)
                if match:
                    facts["name"] = match.group(1).strip()
            # ... 更多提取规则

        return facts
```

##### C. 画像更新机制

**触发时机**：
1. 每次写入记忆后异步更新
2. 定时批量重建（每小时）
3. 用户主动触发

**实现代码**：

```python
class MemoryService:
    async def maybe_write(self, *, user_id: str, user_message: str, assistant_message: str, ...):
        # ... 现有写入逻辑 ...

        # 异步更新画像（不阻塞主链路）
        asyncio.create_task(self._update_profile_background(user_id))

    async def _update_profile_background(self, user_id: str):
        try:
            # 获取所有记忆
            all_memories = await self._store.search(user_id=user_id, query="", top_k=1000)

            # 构建画像
            builder = ProfileBuilder()
            profile = await builder.build_profile(user_id=user_id, memories=all_memories)

            # 保存到数据库
            await self._profile_store.upsert(profile)
        except Exception as e:
            logger.warning(f"Failed to update profile for {user_id}: {e}")
```

##### D. 画像注入策略

**场景 1：每次对话注入**（推荐用于强个性化场景）

```python
def build_memory_context(*, memories: Iterable[MemoryItem], profile: UserProfile, policy: MemoryPolicy) -> str:
    """优先使用画像，补充细粒度记忆。"""

    parts = []

    # 1. 画像摘要（高优先级）
    if profile.preferences or profile.constraints:
        parts.append("【用户画像】")
        if profile.preferences.get("favorite_genres"):
            parts.append(f"- 偏好类型：{', '.join(profile.preferences['favorite_genres'][:3])}")
        if profile.constraints.get("exclude_genres"):
            parts.append(f"- 避免类型：{', '.join(profile.constraints['exclude_genres'])}")
        if profile.constraints.get("max_duration"):
            parts.append(f"- 时长限制：{profile.constraints['max_duration']}分钟以内")

    # 2. 细粒度记忆（补充）
    if memories:
        parts.append("\n【相关记忆】")
        for m in list(memories)[:3]:
            parts.append(f"- {m.text}")

    return "\n".join(parts) if parts else None
```

**场景 2：按需注入**（减少 token 消耗）

```python
# 仅在特定场景注入画像
if agent_type == "recommendation":
    memory_context = await self._memory_service.recall_with_profile(user_id, query, include_profile=True)
else:
    memory_context = await self._memory_service.recall_context(user_id, query)
```

#### 13.2.3 实现优先级

**Phase P1（MVP）**：
- [ ] 新增 `user_profiles` 表
- [ ] 实现 `ProfileBuilder` 基础逻辑
- [ ] 每次写入后异步更新画像
- [ ] 注入逻辑优先使用画像

**Phase P2（增强）**：
- [ ] LLM 提取结构化信息（替代规则）
- [ ] 画像可视化 API（用户查看与编辑）
- [ ] 画像冲突消解（如"喜欢恐怖片" vs "不喜欢恐怖片"）

**Phase P3（高级）**：
- [ ] 偏好权重计算（如"科幻电影"出现 10 次 → 强偏好）
- [ ] 时效性衰减（3 个月前的偏好降低权重）
- [ ] 跨用户画像聚类（发现群体偏好）

---

### 13.3 可控写入策略

#### 13.3.1 当前实现状态

**已实现**：
- ✅ 规则提取模式（`MEMORY_WRITE_MODE=rules`）
- ✅ 敏感信息脱敏（邮箱、电话）
- ✅ 基础标签分类

**未实现**：
- ❌ 总结写入模式
- ❌ 结构化写入
- ❌ 去重与冲突消解
- ❌ 置信度管理

#### 13.3.2 设计方案

##### A. 写入模式扩展

**配置扩展**（`backend/config/settings.py`）：

```python
# 写入模式扩展
MEMORY_WRITE_MODE = os.getenv("MEMORY_WRITE_MODE", "rules").strip()  # rules | summarize | structured | llm
MEMORY_WRITE_DEDUPLICATE = _get_env_bool("MEMORY_WRITE_DEDUPLICATE", True)  # 是否去重
MEMORY_WRITE_CONFIDENCE_THRESHOLD = _get_env_float("MEMORY_WRITE_CONFIDENCE_THRESHOLD", 0.7)  # 置信度阈值
```

##### B. 总结写入模式

**实现代码**：`backend/domain/memory/summarizer.py`（新增）

```python
from application.ports.llm_port import LLMPort

class MemorySummarizer:
    """将对话总结为结构化记忆。"""

    def __init__(self, llm: LLMPort):
        self._llm = llm

    async def summarize_conversation(
        self,
        *,
        user_message: str,
        assistant_message: str,
        existing_memories: list[MemoryItem]
    ) -> Optional[MemoryItem]:
        """总结对话，提取持久化记忆。"""

        prompt = f"""
分析以下对话，提取需要长期记忆的用户偏好/事实/约束。
如果对话中没有值得长期记忆的信息，返回 "NONE"。

对话：
用户：{user_message}
助手：{assistant_message}

现有记忆（避免重复）：
{self._format_existing(existing_memories)}

输出格式（JSON）：
{{
  "should_remember": true/false,
  "type": "preference|constraint|fact",
  "summary": "简短总结（1句话）",
  "confidence": 0.0-1.0
}}
"""

        response = await self._llm.generate(prompt)

        try:
            import json
            result = json.loads(response)
            if not result.get("should_remember"):
                return None

            confidence = float(result.get("confidence", 0.5))
            if confidence < MEMORY_WRITE_CONFIDENCE_THRESHOLD:
                return None

            return MemoryItem(
                id="",  # 后续生成
                text=result["summary"],
                score=confidence,
                tags=(result["type"],),
            )
        except Exception as e:
            logger.warning(f"Failed to parse summarization result: {e}")
            return None

    def _format_existing(self, memories: list[MemoryItem]) -> str:
        return "\n".join(f"- {m.text}" for m in memories[:5])
```

**集成到 MemoryService**：

```python
class MemoryService:
    async def maybe_write(self, *, user_id: str, user_message: str, assistant_message: str, ...):
        if not self._write_enabled:
            return

        if self._write_mode == "rules":
            # 现有逻辑
            candidates = extract_memory_candidates(user_message=user_message)
            if candidates:
                text, tags = candidates[0]
                await self._store.add(user_id=user_id, text=text, tags=list(tags))

        elif self._write_mode == "summarize":
            # 新增：总结写入
            existing = await self._store.search(user_id=user_id, query="", top_k=20)
            memory = await self._summarizer.summarize_conversation(
                user_message=user_message,
                assistant_message=assistant_message,
                existing_memories=existing
            )
            if memory:
                await self._store.add(
                    user_id=user_id,
                    text=memory.text,
                    tags=list(memory.tags),
                    metadata={"confidence": memory.score, "source": "summarizer"}
                )
```

##### C. 去重与冲突消解

**去重逻辑**：

```python
class MemoryDeduplicator:
    """检测并避免重复记忆。"""

    async def is_duplicate(
        self,
        *,
        candidate_text: str,
        existing_memories: list[MemoryItem],
        similarity_threshold: float = 0.85
    ) -> bool:
        """检查候选记忆是否与现有记忆重复。"""

        # 方法 1：精确匹配
        for m in existing_memories:
            if m.text == candidate_text:
                return True

        # 方法 2：向量相似度（需要 embedding）
        candidate_emb = await self._embed_text(candidate_text)
        for m in existing_memories:
            existing_emb = await self._embed_text(m.text)
            similarity = self._cosine_similarity(candidate_emb, existing_emb)
            if similarity >= similarity_threshold:
                return True

        return False
```

**冲突消解逻辑**：

```python
class MemoryConflictResolver:
    """检测并解决记忆冲突。"""

    async def resolve_conflict(
        self,
        *,
        new_memory: MemoryItem,
        existing_conflicts: list[MemoryItem]
    ) -> ResolutionAction:
        """
        冲突类型：
        - 相似但相反："我喜欢科幻电影" vs "我不喜欢科幻电影"
        - 时效冲突："我叫张三" vs "我叫李四"（可能改名）

        返回动作：
        - REPLACE: 用新记忆替换旧记忆
        - MERGE: 合并新旧记忆（如保留时间戳）
        - IGNORE: 忽略新记忆（旧记忆更可信）
        - BOTH: 都保留（不冲突）
        """

        # 示例：检测相反偏好
        for existing in existing_conflicts:
            if self._is_opposite_preference(new_memory, existing):
                # 策略：保留最新的（基于 created_at）
                if new_memory.created_at and existing.created_at:
                    if new_memory.created_at > existing.created_at:
                        return ResolutionAction.REPLACE, [existing.id]
                    else:
                        return ResolutionAction.IGNORE, []

        return ResolutionAction.BOTH, []

    def _is_opposite_preference(self, m1: MemoryItem, m2: MemoryItem) -> bool:
        """检测是否为相反偏好。"""
        # 简单规则（可升级为 LLM 判断）
        if "喜欢" in m1.text and "不喜欢" in m2.text:
            # 提取关键实体是否相同
            entity1 = m1.text.replace("我喜欢", "").strip()
            entity2 = m2.text.replace("我不喜欢", "").strip()
            return entity1 == entity2
        return False

@dataclass
class ResolutionAction:
    type: str  # REPLACE | MERGE | IGNORE | BOTH
    memory_ids_to_delete: list[str] = None
```

##### D. 置信度管理

**置信度来源**：

| 来源 | 置信度范围 | 说明 |
|------|-----------|------|
| 规则提取 | 0.9-1.0 | 高置信度（显式表达） |
| LLM 总结 | 0.5-0.9 | 中等置信度（需 LLM 判断） |
| 推理推断 | 0.3-0.7 | 低置信度（易出错） |

**置信度衰减**：

```python
class MemoryConfidenceManager:
    """管理记忆置信度与过期。"""

    async def decay_confidence(self, *, memory: MemoryItem, age_days: int) -> float:
        """根据记忆年龄衰减置信度。"""

        initial_confidence = memory.score or 0.8

        # 衰减曲线（可配置）
        if age_days < 7:
            return initial_confidence  # 1 周内不衰减
        elif age_days < 30:
            return initial_confidence * 0.9  # 1 个月内衰减 10%
        elif age_days < 90:
            return initial_confidence * 0.7  # 3 个月内衰减 30%
        else:
            return initial_confidence * 0.5  # 3 个月后衰减 50%

        # 低于阈值的记忆不再召回
        if decayed < MEMORY_MIN_SCORE:
            return 0.0
        return decayed
```

#### 13.3.3 实现优先级

**Phase W1（去重）**：
- [ ] 实现精确匹配去重
- [ ] 实现向量相似度去重
- [ ] 添加 `MEMORY_WRITE_DEDUPLICATE` 开关

**Phase W2（总结写入）**：
- [ ] 实现 `MemorySummarizer`
- [ ] 添加 `MEMORY_WRITE_MODE=summarize` 模式
- [ ] 置信度阈值过滤

**Phase W3（冲突消解）**：
- [ ] 实现冲突检测
- [ ] 实现冲突消解策略
- [ ] 冲突日志与审计

---

### 13.4 记忆生命周期

#### 13.4.1 当前实现状态

**已实现**：
- ✅ 创建时间戳（`created_at`）
- ✅ 过期清理 SQL（未启用）

**未实现**：
- ❌ TTL/过期机制
- ❌ 删除/撤回 API
- ❌ 用户可见与可编辑
- ❌ "忘记我说过的…"功能

#### 13.4.2 设计方案

##### A. TTL 机制

**表结构扩展**：`mem0.memories` 增加字段

```sql
ALTER TABLE mem0.memories ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE mem0.memories ADD COLUMN IF NOT EXISTS ttl_days INT DEFAULT 90;
CREATE INDEX IF NOT EXISTS mem0_memories_expires_at_idx ON mem0.memories(expires_at);
```

**TTL 策略**：

| 标签类型 | 默认 TTL | 说明 |
|---------|---------|------|
| `preference` | 90 天 | 偏好可能随时间变化 |
| `constraint` | 180 天 | 约束相对稳定 |
| `fact` | 365 天 | 事实最稳定 |
| `identity` | 永不过期 | 身份信息长期有效 |

**实现代码**：

```python
# backend/server/mem0_service/storage_postgres.py

async def add(self, *, user_id: str, text: str, tags: list[str], metadata: dict) -> str:
    mid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 根据标签计算 TTL
    ttl_days = self._calculate_ttl(tags)
    expires_at = now + timedelta(days=ttl_days) if ttl_days else None

    await conn.execute(
        """
        INSERT INTO mem0.memories (id, user_id, text, tags, metadata, created_at, expires_at, ttl_days)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8);
        """,
        mid, user_id, text, tags, json.dumps(metadata), now, expires_at, ttl_days
    )
    return mid

def _calculate_ttl(self, tags: list[str]) -> Optional[int]:
    """根据标签计算 TTL。"""
    if "identity" in tags:
        return None  # 永不过期
    elif "fact" in tags:
        return 365
    elif "constraint" in tags:
        return 180
    elif "preference" in tags:
        return 90
    else:
        return 90  # 默认
```

**过期清理任务**：

```python
# backend/server/mem0_service/tasks.py

from apscheduler.schedulers.background import BackgroundScheduler
# ⚠️ 注意：以下代码为简化示例，生产环境需使用 AsyncIOScheduler 或包装 async 调用

class MemoryCleanupTask:
    """定期清理过期记忆。

    ⚠️ 实现注意事项：
    - BackgroundScheduler 不会自动 await async 函数，需使用 AsyncIOScheduler
    - 或使用 sync_to_async 包装：asyncio.run(self._cleanup_expired())
    - 推荐方案：from apscheduler.schedulers.asyncio import AsyncIOScheduler
    """

    def __init__(self, pg_store: PostgresMemoryStore):
        self._pg = pg_store
        self._scheduler = BackgroundScheduler()

    def start(self):
        """每小时清理一次过期记忆。"""
        self._scheduler.add_job(self._cleanup_expired, 'interval', hours=1)
        self._scheduler.start()

    async def _cleanup_expired(self):
        """删除过期记忆。"""
        now = datetime.now(timezone.utc)

        # 软删除（标记为已删除，保留审计）
        await self._pg.execute(
            "UPDATE mem0.memories SET deleted_at = $1 WHERE expires_at < $2 AND deleted_at IS NULL",
            now, now
        )

        # 硬删除（30 天后彻底删除）
        hard_delete_cutoff = now - timedelta(days=30)
        await self._pg.execute(
            "DELETE FROM mem0.memories WHERE deleted_at < $1",
            hard_delete_cutoff
        )
```

**生产实现建议**：

```python
# 推荐使用 AsyncIOScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class MemoryCleanupTask:
    def __init__(self, pg_store: PostgresMemoryStore):
        self._pg = pg_store
        self._scheduler = AsyncIOScheduler()  # ✅ 使用 AsyncIOScheduler

    def start(self):
        self._scheduler.add_job(self._cleanup_expired, 'interval', hours=1)
        self._scheduler.start()
```

##### B. 删除/撤回 API

**新增 API 端点**：

```python
# backend/server/mem0_service/main.py

from fastapi import Header, HTTPException
import jwt  # PyJWT

# 方案 1：从 JWT Token 解析 user_id（生产推荐）
def _extract_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    """从认证上下文提取 user_id（避免客户端伪造）。

    生产环境实现方案：
    1. JWT Token：从 Authorization Header 解析 JWT claims，提取 user_id
    2. 上游鉴权：GraphRAG Backend 已校验用户身份，通过 HTTP Header 传递 user_id
    3. 内部服务：受信任的后端服务间调用，通过共享密钥或 mTLS

    ⚠️ 注意：全局 API Key 无法区分不同用户，仅适用于单租户场景。
    """
    if not MEM0_API_KEY:
        raise HTTPException(status_code=500, detail="Authentication not configured")

    token = (authorization or "").replace("Bearer ", "").strip()

    # 生产实现 A：JWT Token（推荐用于多用户场景）
    try:
        # JWT 示例（需要 PyJWT：pip install pyjwt）
        payload = jwt.decode(token, MEM0_API_KEY, algorithms=["HS256"])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user_id")
        return str(user_id)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 生产实现 B：上游鉴权传递（GraphRAG Backend 已校验）
    # 如果调用方是受信任的后端服务，可以简化为：
    # user_id = token  # 前提：上游已验证身份并注入 user_id
    # return user_id

    # 开发/测试实现：单租户 API Key（不适用于生产多用户场景）
    # if token != MEM0_API_KEY:
    #     raise HTTPException(status_code=401, detail="Invalid token")
    # return "test_user"  # 固定用户（仅用于开发/测试）


@app.delete("/v1/memories/{memory_id}", dependencies=[Depends(_require_auth)])
async def delete_memory(
    memory_id: str,
    user_id: str = Depends(_extract_user_id),  # 从认证上下文提取
) -> dict[str, Any]:
    """删除指定记忆（软删除）。"""

    # 权限检查：只能删除自己的记忆
    memory = await app.state.pg.get_by_id(memory_id)
    if not memory or memory["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Memory not found")

    # 软删除（必须带 user_id 约束，防止越权删除）
    await app.state.pg.soft_delete(memory_id, user_id=user_id)
    return {"deleted": True, "memory_id": memory_id}


@app.post("/v1/memories/{memory_id}/restore", dependencies=[Depends(_require_auth)])
async def restore_memory(
    memory_id: str,
    user_id: str = Depends(_extract_user_id),  # 从认证上下文提取
) -> dict[str, Any]:
    """恢复已删除的记忆。"""

    await app.state.pg.restore(memory_id, user_id)
    return {"restored": True, "memory_id": memory_id}
```

**安全说明**：
- ❌ **不推荐**：将 `user_id` 作为请求参数（query/body）- 客户端可伪造
- ✅ **推荐**：从认证上下文（JWT claims/Authorization Header）提取 `user_id`
- ✅ **内部服务场景**：如果调用方是受信任的后端服务，可直接传递 `user_id`，但需在文档中明确说明"上游已校验身份"

**PostgreSQL 存储**：

```sql
ALTER TABLE mem0.memories ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- 软删除（SQL 层约束：必须同时匹配 id 和 user_id）
UPDATE mem0.memories SET deleted_at = NOW() WHERE id = $1 AND user_id = $2;

-- 恢复（SQL 层约束：必须同时匹配 id 和 user_id）
UPDATE mem0.memories SET deleted_at = NULL WHERE id = $1 AND user_id = $2;

-- 更新（SQL 层约束：防止越权修改其他用户的记忆）
UPDATE mem0.memories
SET text = $2, tags = $3, metadata = $4, updated_at = NOW()
WHERE id = $1 AND user_id = $5
RETURNING *;

-- 查询时过滤
SELECT * FROM mem0.memories WHERE user_id = $1 AND (deleted_at IS NULL OR deleted_at > NOW());
```

> **🔒 安全原则：数据库层双重防护**
>
> 所有写操作（INSERT/UPDATE/DELETE）必须在 SQL 层包含 `user_id` 约束：
> - ✅ `WHERE id = $1 AND user_id = $2` - 同时匹配记忆 ID 和用户 ID
> - ✅ 应用层检查：提前返回 404（友好错误）
> - ✅ 数据库层约束：最终防护（即使应用层有漏洞也无法越权）
>
> **防御深度**：
> 1. 应用层：`if memory["user_id"] != user_id: raise 404`
> 2. 数据库层：`WHERE id = $1 AND user_id = $2`（必须传递）

##### C. 用户可见与编辑

**新增 API**：

```python
@app.get("/v1/memories", response_model=MemoryListResponse, dependencies=[Depends(_require_auth)])
async def list_memories(
    user_id: str = Depends(_extract_user_id),  # 从认证上下文提取
    limit: int = 20,
    offset: int = 0,
    tags: Optional[str] = None
) -> MemoryListResponse:
    """列出用户的所有记忆（分页）。"""

    tag_filter = tags.split(",") if tags else None
    memories = await app.state.pg.list_by_user(
        user_id=user_id,
        limit=limit,
        offset=offset,
        tags=tag_filter
    )
    return MemoryListResponse(memories=memories, total=len(memories))

@app.put("/v1/memories/{memory_id}", dependencies=[Depends(_require_auth)])
async def update_memory(
    memory_id: str,
    user_id: str = Depends(_extract_user_id),  # 从认证上下文提取
    req: MemoryUpdateRequest
) -> MemoryOut:
    """编辑记忆内容。"""

    # 权限检查：只能编辑自己的记忆
    memory = await app.state.pg.get_by_id(memory_id)
    if not memory or memory["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Memory not found")

    # 更新（必须带 user_id 约束，防止越权更新）
    updated = await app.state.pg.update(
        memory_id=memory_id,
        user_id=user_id,  # SQL 层双重防护：WHERE id=$1 AND user_id=$2
        text=req.text,
        tags=req.tags,
        metadata=req.metadata
    )
    return updated
```

##### D. "忘记我说过的…"功能

**自然语言删除**：

```python
@app.post("/v1/memories/forget", dependencies=[Depends(_require_auth)])
async def forget_memory(
    req: ForgetRequest,
    user_id: str = Depends(_extract_user_id),  # ⚠️ 必须从认证上下文提取
) -> dict[str, Any]:
    """
    用户说："忘记我说过的所有关于电影偏好的内容"
    系统识别并批量删除相关记忆。
    """

    # 1. 向量检索相关记忆（user_id 从认证上下文提取，不可伪造）
    query_embedding = _embed_text(req.query)
    hits = app.state.vector.search(user_id=user_id, embedding=query_embedding, limit=50)

    # 2. 用户确认（返回候选列表）
    if req.require_confirmation:
        memory_ids = [h.memory_id for h in hits]
        candidates = await app.state.pg.get_many(ids=memory_ids, user_id=user_id)
        return {
            "candidates": candidates,
            "total": len(candidates),
            "message": "是否删除这些记忆？再次调用 confirm=true"
        }

    # 3. 批量删除（必须带 user_id 约束）
    deleted_count = 0
    for hit in hits:
        await app.state.pg.soft_delete(hit.memory_id, user_id=user_id)
        deleted_count += 1

    return {
        "deleted": True,
        "count": deleted_count,
        "message": f"已删除 {deleted_count} 条记忆"
    }
```

**⚠️ 安全关键**：
- ❌ **不安全**：`user_id=req.user_id`（客户端可伪造请求体）
- ✅ **安全**：`user_id = Depends(_extract_user_id)`（从认证上下文提取）
- ✅ **双重防护**：`soft_delete(memory_id, user_id=user_id)` 在数据库层强制 user_id 约束

#### 13.4.3 实现优先级

**Phase L1（基础生命周期）**：
- [ ] 添加 `expires_at` / `deleted_at` 字段
- [ ] 实现软删除 API
- [ ] 实现过期清理任务

**Phase L2（用户管理）**：
- [ ] 实现列出记忆 API
- [ ] 实现编辑记忆 API
- [ ] 实现恢复记忆 API

**Phase L3（高级交互）**：
- [ ] 实现"忘记我说过的…"功能
- [ ] 用户界面集成

---

### 13.5 多域/多会话共享

#### 13.5.1 当前实现状态

**已实现**：
- ✅ 单一 `user_id` 隔离

**未实现**：
- ❌ 多渠道 user_id 统一
- ❌ 会话级记忆与全局级记忆区分
- ❌ 跨会话记忆继承

#### 13.5.2 设计方案

##### A. 多渠道身份统一

**新增表**：`mem0.user_identities`

```sql
CREATE TABLE IF NOT EXISTS mem0.user_identities (
    unified_id TEXT NOT NULL,
    channel TEXT NOT NULL,        -- web | app | wechat | slack
    channel_user_id TEXT NOT NULL,
    primary_channel BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (channel, channel_user_id)
);

CREATE INDEX IF NOT EXISTS mem0_user_identities_unified_idx ON mem0.user_identities(unified_id);
```

**示例数据**：

| unified_id | channel | channel_user_id | primary_channel |
|-----------|---------|-----------------|-----------------|
| user_123 | web | web_session_abc | true |
| user_123 | wechat | wx_openid_xyz | false |
| user_123 | app | app_device_123 | false |

**身份合并服务**：

```python
# backend/application/chat/identity_service.py

class IdentityService:
    """多渠道身份统一管理。"""

    async def get_or_create_unified_id(
        self,
        *,
        channel: str,
        channel_user_id: str
    ) -> str:
        """获取或创建 unified_id。"""

        # 1. 查找现有身份
        unified_id = await self._identity_store.find_unified_id(channel, channel_user_id)
        if unified_id:
            return unified_id

        # 2. 创建新身份
        unified_id = f"unified_{uuid.uuid4().hex[:12]}"
        await self._identity_store.create(
            unified_id=unified_id,
            channel=channel,
            channel_user_id=channel_user_id,
            primary_channel=True  # 第一个渠道标记为主渠道
        )
        return unified_id

    async def merge_identities(
        self,
        *,
        primary_channel: str,
        primary_channel_user_id: str,
        secondary_channel: str,
        secondary_channel_user_id: str
    ) -> str:
        """手动合并两个身份（用户认证后）。"""

        primary_unified = await self._identity_store.find_unified_id(primary_channel, primary_channel_user_id)
        secondary_unified = await self._identity_store.find_unified_id(secondary_channel, secondary_channel_user_id)

        if not primary_unified or not secondary_unified:
            raise ValueError("Identity not found")

        if primary_unified == secondary_unified:
            return primary_unified  # 已经合并

        # 合并：将 secondary 的记忆迁移到 primary
        await self._memory_store.transfer_user_id(
            from_user_id=secondary_unified,
            to_user_id=primary_unified
        )

        # 删除 secondary 统一身份
        await self._identity_store.delete(secondary_unified)

        return primary_unified
```

##### B. 会话级记忆 vs 全局级记忆

**表结构扩展**：

```sql
ALTER TABLE mem0.memories ADD COLUMN IF NOT EXISTS scope TEXT NOT NULL DEFAULT 'global';
-- scope: 'global' | 'session:{session_id}' | 'channel:{channel}'
CREATE INDEX IF NOT EXISTS mem0_memories_scope_idx ON mem0.memories(user_id, scope);
```

**召回策略**：

```python
class MemoryService:
    async def recall_context(self, *, user_id: str, query: str, session_id: str) -> Optional[str]:
        """召回策略：全局记忆 + 会话记忆。"""

        # 1. 全局记忆（跨会话）
        global_memories = await self._store.search(
            user_id=user_id,
            query=query,
            top_k=int(self._policy.top_k),
            scope="global"
        )

        # 2. 会话记忆（当前会话优先）
        session_memories = await self._store.search(
            user_id=user_id,
            query=query,
            top_k=3,
            scope=f"session:{session_id}"
        )

        # 3. 合并（会话记忆优先级更高）
        all_memories = list(session_memories) + list(global_memories)
        return build_memory_context(memories=all_memories, policy=self._policy)
```

#### 13.5.3 实现优先级

**Phase M1（身份统一）**：
- [ ] 新增 `user_identities` 表
- [ ] 实现 `IdentityService`
- [ ] 支持 3 个主流渠道（web/app/wechat）

**Phase M2（会话隔离）**：
- [ ] 添加 `scope` 字段
- [ ] 实现会话级记忆写入
- [ ] 实现分层召回策略

---

### 13.6 Agent Tool 化

#### 13.6.1 当前实现状态

**已实现**：
- ✅ 每轮对话注入记忆（全局）

**未实现**：
- ❌ recall() / remember() 工具
- ❌ Agent 按需调用
- ❌ 多 Agent 记忆隔离

#### 13.6.2 设计方案

##### A. 记忆工具定义

**文件**: `backend/domain/memory/tools.py`（新增）

```python
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

class RecallInput(BaseModel):
    query: str = Field(description="搜索查询，如'用户喜欢什么电影'")
    top_k: int = Field(default=5, description="返回数量")

class RememberInput(BaseModel):
    text: str = Field(description="需要记住的内容，如'用户不喜欢恐怖片'")
    memory_type: str = Field(default="preference", description="记忆类型：preference|constraint|fact")
    confidence: float = Field(default=0.8, description="置信度 0-1")

class MemoryToolsFactory:
    """为 multi-agent 创建记忆工具。"""

    def __init__(self, memory_store: MemoryStorePort):
        self._store = memory_store

    def create_recall_tool(self, user_id: str) -> StructuredTool:
        """创建 recall 工具。"""

        async def recall(query: str, top_k: int = 5) -> str:
            memories = await self._store.search(user_id=user_id, query=query, top_k=top_k)
            if not memories:
                return f"未找到关于'{query}'的记忆。"
            return "\n".join(f"- {m.text}" for m in memories)

        return StructuredTool.from_function(
            name="recall_memory",
            description="搜索用户的长期记忆，包括偏好、约束、事实等。",
            func=recall,
            args_schema=RecallInput
        )

    def create_remember_tool(self, user_id: str) -> StructuredTool:
        """创建 remember 工具。"""

        async def remember(text: str, memory_type: str = "preference", confidence: float = 0.8) -> str:
            memory_id = await self._store.add(
                user_id=user_id,
                text=text,
                tags=[memory_type],
                metadata={"confidence": confidence, "source": "agent_tool"}
            )
            if memory_id:
                return f"已记住：{text}"
            else:
                return f"记忆失败：{text}"

        return StructuredTool.from_function(
            name="remember",
            description="记住用户的信息，包括偏好、约束、事实等。",
            func=remember,
            args_schema=RememberInput
        )
```

##### B. Multi-Agent 集成

**集成到 FusionGraphRAGAgent**：

```python
# backend/graphrag_agent/agents/multi_agent/executor/research_executor.py

class ResearchExecutor:
    def __init__(self, ..., memory_tools_factory: MemoryToolsFactory):
        self._memory_tools = memory_tools_factory

    async def run(self, *, plan: list[RagRunSpec], user_id: str, ...):
        # 为当前任务创建记忆工具
        recall_tool = self._memory_tools.create_recall_tool(user_id)
        remember_tool = self._memory_tools.create_remember_tool(user_id)

        # 注入到 LangGraph 工具节点
        tools = [recall_tool, remember_tool, ...其他工具...]

        # Agent 可以按需调用：
        # - recall_memory(query="用户喜欢什么电影")
        # - remember(text="用户不喜欢恐怖片", memory_type="preference")
```

##### C. 按需召回 vs 全局注入

**对比**：

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **全局注入**（当前） | 简单，确保所有对话都有记忆上下文 | Token 成本高，可能不相关 | 通用问答、强个性化场景 |
| **Agent Tool**（新增） | 按需调用，节省成本 | Agent 需学会何时调用 | 复杂推理、多步骤任务 |

**混合策略**：

```python
class MemoryService:
    async def recall_context(self, *, user_id: str, query: str, agent_type: str, enable_auto_recall: bool = True) -> Optional[str]:
        """智能召回策略。"""

        # 策略 1：特定 agent_type 自动注入
        if agent_type in ["recommendation", "personalized"]:
            return await self._auto_recall(user_id, query)

        # 策略 2：其他 agent_type 仅提供工具
        return None

    async def _auto_recall(self, user_id: str, query: str) -> str:
        """自动召回高相关记忆。"""

        # 1. 高置信度召回（score > 0.8）
        memories = await self._store.search(user_id=user_id, query=query, top_k=3)
        high_conf = [m for m in memories if m.score > 0.8]

        if high_conf:
            return build_memory_context(memories=high_conf, policy=self._policy)

        # 2. 低置信度时不注入，依赖 agent tool
        return None
```

#### 13.6.3 实现优先级

**Phase T1（工具实现）**：
- [ ] 实现 `recall_memory` 工具
- [ ] 实现 `remember` 工具
- [ ] 工具描述优化（Prompt）

**Phase T2（Agent 集成）**：
- [ ] FusionGraphRAGAgent 集成
- [ ] 测试 Agent 学会何时调用

**Phase T3（混合策略）**：
- [ ] 实现智能召回策略
- [ ] A/B 测试：全局注入 vs Tool 调用

---

### 13.7 路由/检索增强

#### 13.7.1 当前实现状态

**已实现**：
- ✅ 记忆注入 LLM prompt（通用）

**未实现**：
- ❌ 记忆影响路由决策
- ❌ 记忆影响 RAG 检索（过滤/重排）
- ❌ 个性化回答风格

#### 13.7.2 设计方案

##### A. 记忆影响路由

**场景**：用户说"推荐电影"

- **无记忆**：路由到 `movie:hybrid_agent`（通用推荐）
- **有记忆**（用户偏好科幻）：路由到 `movie:scifi_agent`（科幻专家）或带上过滤参数

**实现代码**：

```python
# backend/application/routing/memory_aware_router.py

class MemoryAwareRouter:
    """基于长期记忆的路由决策。"""

    async def route(
        self,
        *,
        message: str,
        user_id: str,
        session_id: str,
        agent_type: str
    ) -> RouteDecision:
        # 1. 获取用户画像
        profile = await self._profile_store.get(user_id)
        if not profile:
            # 降级到默认路由
            return await self._default_router.route(message, session_id, None, agent_type)

        # 2. 基于画像调整路由
        decision = RouteDecision(
            requested_kb_prefix=None,
            routed_kb_prefix=decision.kb_prefix,
            kb_prefix=decision.kb_prefix,
            confidence=decision.confidence,
            method=decision.method,
            reason=decision.reason,
            worker_name=decision.worker_name
        )

        # 示例 1：偏好类型 → 特定 worker
        if profile.preferences.get("favorite_genres"):
            top_genre = profile.preferences["favorite_genres"][0]
            decision.worker_name = f"movie:{top_genre}_agent"
            decision.reason = f"用户偏好{top_genre}，路由到专家 Agent"

        # 示例 2：约束 → 过滤参数
        if profile.constraints.get("exclude_genres"):
            decision.metadata = {
                "exclude_genres": profile.constraints["exclude_genres"]
            }

        return decision
```

##### B. 记忆影响 RAG 检索

**场景 1：过滤**

- 用户记忆："我不喜欢恐怖片"
- RAG 检索：在 Cypher 查询中过滤掉恐怖类型

```cypher
// 原始查询
MATCH (m:Movie) WHERE m.genre = $genre RETURN m

// 记忆增强查询
MATCH (m:Movie)
WHERE m.genre = $genre
  AND NOT $exclude_genres IN m.genres  // 记忆过滤
RETURN m
```

**场景 2：重排**

- 用户偏好："科幻" > "动作"
- RAG 检索结果重排：科幻电影得分加权

**实现代码**：

```python
# backend/application/rag/memory_aware_retriever.py

class MemoryAwareRetriever:
    """基于长期记忆的检索增强。"""

    async def search(
        self,
        *,
        query: str,
        kb_prefix: str,
        user_id: str,
        top_k: int
    ) -> list[RetrievalResult]:
        # 1. 获取用户画像
        profile = await self._profile_store.get(user_id)
        if not profile:
            return await self._default_searcher.search(query, kb_prefix, top_k)

        # 2. 基础检索
        results = await self._default_searcher.search(query, kb_prefix, top_k * 2)

        # 3. 记忆过滤
        if profile.constraints.get("exclude_genres"):
            exclude = set(profile.constraints["exclude_genres"])
            results = [r for r in results if not any(g in exclude for g in r.get_genres())]

        # 4. 记忆重排
        if profile.preferences.get("favorite_genres"):
            favorite = set(profile.preferences["favorite_genres"])
            for r in results:
                # 如果结果匹配偏好，提升得分
                if any(g in favorite for g in r.get_genres()):
                    r.score *= 1.2  # 提升 20%

        # 5. 返回 top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
```

##### C. 个性化回答风格

**场景**：

- 用户画像：{"language": "中文", "tone": "专业", "max_length": "200字"}
- LLM Prompt 增加：用户偏好约束

**实现代码**：

```python
class MemoryAwareCompletion:
    """基于长期记忆的生成增强。"""

    async def generate(self, *, message: str, user_id: str, memory_context: str) -> str:
        # 1. 获取用户画像
        profile = await self._profile_store.get(user_id)

        # 2. 构建个性化 prompt
        system_prompt = self._build_system_prompt(profile)

        # 3. 注入记忆上下文
        full_prompt = f"{system_prompt}\n\n{memory_context}\n\n用户问题：{message}"

        # 4. 生成回答
        return await self._llm.generate(full_prompt)

    def _build_system_prompt(self, profile: UserProfile) -> str:
        """根据画像构建系统提示。"""

        parts = ["你是一个有用的助手。"]

        if profile.facts.get("language") == "中文":
            parts.append("请用中文回答。")

        if profile.preferences.get("tone") == "专业":
            parts.append("请使用专业、严谨的语气。")

        if profile.constraints.get("max_length"):
            parts.append(f"回答长度控制在{profile.constraints['max_length']}字以内。")

        return "\n".join(parts)
```

#### 13.7.3 实现优先级

**Phase R1（路由增强）**：
- [ ] 实现 `MemoryAwareRouter`
- [ ] 支持 worker_name 动态选择
- [ ] A/B 测试：CTR/用户满意度

**Phase R2（检索增强）**：
- [ ] 实现 `MemoryAwareRetriever`
- [ ] 支持过滤与重排
- [ ] 性能优化（避免二次检索）

**Phase R3（生成增强）**：
- [ ] 实现个性化 prompt 模板
- [ ] 支持多语言、多风格

---

### 13.8 观测与评估

#### 13.8.1 当前实现状态

**已实现**：
- ⚠️ 部分日志（warning/error）

**未实现**：
- ❌ 记忆命中率指标
- ❌ 记忆带来的改进评估
- ❌ 幻觉风险监控
- ❌ A/B 测试框架

#### 13.8.2 设计方案

##### A. 核心指标定义

**文件**：`backend/domain/memory/metrics.py`（新增）

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MemoryMetrics:
    """记忆系统核心指标。"""

    # 召回指标
    recall_total: int = 0           # 总召回次数
    recall_hit: int = 0             # 有记忆返回次数
    recall_hit_rate: float = 0.0    # 召回命中率

    # 注入指标
    injection_total: int = 0        # 总注入次数
    injection_effective: int = 0    # 有效注入次数（记忆被 LLM 使用）
    injection_effective_rate: float = 0.0

    # 写入指标
    write_total: int = 0            # 总写入次数
    write_duplicate: int = 0        # 重复写入次数（被去重）
    write_duplicate_rate: float = 0.0

    # 质量指标
    avg_confidence: float = 0.0     # 平均置信度
    avg_age_days: float = 0.0       # 记忆平均年龄（天）

    # 用户反馈
    positive_feedback: int = 0      # 正向反馈（点赞）
    negative_feedback: int = 0      # 负向反馈（点踩）
    feedback_rate: float = 0.0      # 反馈率

    def calculate_rates(self):
        """计算比率指标。"""
        self.recall_hit_rate = self.recall_hit / self.recall_total if self.recall_total > 0 else 0.0
        self.injection_effective_rate = self.injection_effective / self.injection_total if self.injection_total > 0 else 0.0
        self.write_duplicate_rate = self.write_duplicate / self.write_total if self.write_total > 0 else 0.0
        self.feedback_rate = (self.positive_feedback + self.negative_feedback) / self.recall_total if self.recall_total > 0 else 0.0
```

##### B. 指标收集

**集成到 MemoryService**：

```python
class MemoryService:
    def __init__(self, *, store: MemoryStorePort, policy: MemoryPolicy, metrics_collector: MetricsCollector):
        self._store = store
        self._policy = policy
        self._metrics = metrics_collector

    async def recall_context(self, *, user_id: str, query: str) -> Optional[str]:
        self._metrics.increment("recall_total")

        try:
            memories = await self._store.search(user_id=user_id, query=query, top_k=int(self._policy.top_k))
            if memories:
                self._metrics.increment("recall_hit")

            context = build_memory_context(memories=memories, policy=self._policy)
            if context:
                self._metrics.increment("injection_total")
                # TODO: 追踪是否被 LLM 使用（需要 LLM 反馈）
            return context
        except Exception:
            return None

    async def maybe_write(self, *, user_id: str, user_message: str, ...):
        self._metrics.increment("write_total")

        # 去重检测
        existing = await self._store.search(user_id=user_id, query=user_message, top_k=1)
        if existing and existing[0].score > 0.95:
            self._metrics.increment("write_duplicate")
            return  # 跳过重复写入

        # 写入逻辑...
```

**Prometheus 指标导出**：

```python
from prometheus_client import Counter, Histogram, Gauge

# 定义指标（避免高基数 label）
memory_recall_total = Counter("memory_recall_total", "Total memory recalls", ["status"])
memory_recall_hit = Counter("memory_recall_hit", "Successful memory recalls", ["status"])
memory_write_total = Counter("memory_write_total", "Total memory writes", ["status", "tag"])
memory_avg_confidence = Gauge("memory_avg_confidence", "Average memory confidence")
memory_age_days = Histogram("memory_age_days", "Memory age distribution")

# 收集时记录（不使用 user_id 作为 label）
memory_recall_total.labels(status="success").inc()
memory_recall_hit.labels(status="hit").inc()

# ⚠️ tag 必须来自有限枚举（如 "preference", "fact", "instruction"）
# 如果 tags 不受控，应移除 tag label 或使用预定义映射
memory_write_total.labels(status="success", tag=_normalize_tag(raw_tag)).inc()

memory_avg_confidence.set(avg_confidence)
memory_age_days.observe(age_days)

# 标签归一化函数（将任意 tag 映射到有限集合）
def _normalize_tag(tag: str) -> str:
    """将用户自定义 tag 归一化到有限枚举，避免高基数。"""
    mapping = {
        "preference": "preference",
        "pref": "preference",
        "fact": "fact",
        "knowledge": "fact",
        "instruction": "instruction",
        "rule": "instruction",
    }
    return mapping.get(tag.lower(), "other")  # 未知 tag 统一归类为 "other"
```

**注意**：
- ❌ **禁止**：使用 `user_id` 作为 Prometheus label（高基数会导致 TSDB 性能问题）
- ❌ **禁止**：使用不受控的 `tag` 作为 label（如果 tags 可由用户自定义，会无限膨胀）
- ✅ **推荐**：
  - 用户维度分析通过日志系统（如 ELK）实现
  - 只保留低基数标签（status、kb_name 等，cardinality < 100）
  - 如果必须使用 tag，必须归一化到**有限枚举**（如 preference/fact/instruction/other）
  - 使用 `_normalize_tag()` 等函数将任意输入映射到预定义集合

##### C. A/B 测试框架

**场景**：测试"记忆注入"是否真的改进用户体验

```python
# backend/application/chat/ab_test.py

class MemoryABTest:
    """记忆系统 A/B 测试。"""

    async def route_request(
        self,
        *,
        user_id: str,
        query: str
    ) -> str:
        """根据用户分桶决定是否启用记忆。"""

        # 分桶算法（一致性哈希）
        bucket = self._hash_user(user_id) % 2

        if bucket == 0:
            # A 组：启用记忆
            return await self._with_memory(user_id, query)
        else:
            # B 组：禁用记忆（对照组）
            return await self._without_memory(user_id, query)

    def _hash_user(self, user_id: str) -> int:
        """一致性哈希（确保同一用户始终在同一组）。"""
        import hashlib
        return int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100

    # 比较指标：
    # - 用户满意度（点赞率）
    # - 对话轮次（是否更快解决问题）
    # - 响应时间（记忆是否增加延迟）
```

##### D. 幻觉风险监控

**风险场景**：

- 记忆不准确但 LLM 采信 → 产生幻觉答案
- 例如：记忆说"用户喜欢恐怖片"（错误），推荐恐怖片（错误）

**监控方案**：

```python
class HallucinationMonitor:
    """记忆幻觉风险监控。"""

    async def check_risk(self, *, memory: MemoryItem, query: str) -> float:
        """评估记忆使用风险（0-1）。"""

        risk_score = 0.0

        # 风险因素 1：置信度低
        if memory.score < 0.6:
            risk_score += 0.3

        # 风险因素 2：记忆过旧
        if memory.created_at:
            age_days = (datetime.now(timezone.utc) - memory.created_at).days
            if age_days > 90:
                risk_score += 0.2

        # 风险因素 3：记忆类型（fact 类型风险更高）
        if "fact" in memory.tags:
            risk_score += 0.1

        # 风险因素 4：查询与记忆相关性低
        if memory.score < 0.5:
            risk_score += 0.4

        return min(risk_score, 1.0)

    async def warn_if_risky(self, *, memories: list[MemoryItem], query: str):
        """如果风险高，记录警告。"""

        for m in memories:
            risk = await self.check_risk(memory=m, query=query)
            if risk > 0.7:
                logger.warning(
                    "High risk memory usage",
                    extra={
                        "memory_id": m.id,
                        "memory_text": m.text,
                        "risk_score": risk,
                        "query": query
                    }
                )
```

#### 13.8.3 实现优先级

**Phase O1（基础指标）**：
- [ ] 实现核心指标收集
- [ ] Prometheus 指标导出
- [ ] Grafana 仪表盘

**Phase O2（A/B 测试）**：
- [ ] 实现 A/B 测试框架
- [ ] 运行小规模实验（5% 流量）
- [ ] 分析结果并决策

**Phase O3（高级监控）**：
- [ ] 幻觉风险监控
- [ ] 自动化回滚机制
- [ ] 记忆质量评估报告

---

### 13.9 实施路线图

#### 13.9.1 短期目标（1-2 个月）

**优先级：高**

| 任务 | 预期工作量 | 收益 | 风险 |
|------|-----------|------|------|
| ✅ 可控写入策略（去重 + 总结） | 2 周 | 大幅降低记忆污染 | 中 |
| ✅ 记忆生命周期（TTL + 删除 API） | 1 周 | 合规与隐私保护 | 低 |
| ✅ 观测与评估（基础指标） | 1 周 | 数据驱动优化 | 低 |

**里程碑 M1**：
- 重复写入率降低 80%
- 记忆过期自动清理
- 可视化监控仪表盘

#### 13.9.2 中期目标（3-6 个月）

**优先级：中**

| 任务 | 预期工作量 | 收益 | 风险 |
|------|-----------|------|------|
| ✅ 用户画像/偏好中心 | 3 周 | 减少重复沟通 50% | 中 |
| ✅ Agent Tool 化 | 2 周 | 降低 Token 成本 30% | 中 |
| ✅ 路由/检索增强 | 4 周 | 提升个性化体验 | 高 |

**里程碑 M2**：
- 用户画像覆盖 80% 活跃用户
- Agent 按需召回命中率 > 70%
- 个性化推荐 CTR 提升 20%

#### 13.9.3 长期目标（6-12 个月）

**优先级：低**

| 任务 | 预期工作量 | 收益 | 风险 |
|------|-----------|------|------|
| ⚠️ 多域/多会话共享 | 3 周 | 跨渠道连续性 | 高 |
| ⚠️ 冲突消解 + 置信度管理 | 2 周 | 记忆质量提升 | 中 |
| ⚠️ 幻觉风险监控 | 2 周 | 安全性增强 | 中 |

**里程碑 M3**：
- 支持 5+ 主流渠道
- 记忆冲突自动处理率 > 90%
- 幻觉率降低 50%

#### 13.9.4 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **记忆污染** | 用户体验下降，召回不准确 | 1. 去重机制<br/>2. 置信度阈值<br/>3. 用户反馈纠错 |
| **Token 成本激增** | 运营成本上升 | 1. Agent Tool 化（按需召回）<br/>2. 智能注入策略<br/>3. 记忆压缩 |
| **隐私合规** | GDPR/数据安全违规 | 1. TTL/过期机制<br/>2. 用户可见与删除<br/>3. 脱敏与加密 |
| **幻觉风险** | LLM 采信错误记忆 | 1. 风险监控<br/>2. 低置信度标记<br/>3. A/B 测试验证 |
| **性能瓶颈** | 高并发延迟 | 1. 批量操作<br/>2. 连接池优化<br/>3. Embedding 缓存 |

---

## 14. 附录

### 14.1 相关文件清单

| 文件路径 | 说明 |
|---------|------|
| `backend/server/mem0_service/main.py` | 自托管服务入口 |
| `backend/server/mem0_service/settings.py` | 服务端配置 |
| `backend/server/mem0_service/storage_postgres.py` | PostgreSQL 存储实现 |
| `backend/server/mem0_service/vector_milvus.py` | Milvus 向量索引实现 |
| `backend/server/mem0_service/schemas.py` | API 请求/响应模型 |
| `backend/infrastructure/memory/mem0_http_memory_store.py` | HTTP 客户端 |
| `backend/infrastructure/memory/null_memory_store.py` | 空实现（降级） |
| `backend/application/ports/memory_store_port.py` | 存储抽象接口 |
| `backend/domain/memory/memory_item.py` | 记忆项值对象 |
| `backend/domain/memory/policy.py` | 记忆策略和规则 |
| `backend/application/chat/memory_service.py` | 应用层编排服务 |
| `docker/docker-compose.mem0.yaml` | Docker Compose 配置 |
| `docker/Dockerfile.mem0` | Docker 镜像构建 |
| `backend/config/settings.py` | 功能开关配置 |
| `backend/infrastructure/config/settings.py` | 客户端连接配置 |

### 13.2 参考资料

- [mem0 官方文档](https://docs.mem0.ai/)
- [Milvus 文档](https://milvus.io/docs)
- [asyncpg 文档](https://magicstack.github.io/asyncpg/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [PyMilvus 文档](https://milvus.io/api-reference/pymilvus/v2.4.x/About.md)

### 13.3 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0 | 2025-01-21 | 初始版本，实现基本 mem0 自托管集成 |
| v1.1 | 2025-01-21 | 新增"高级能力增强"章节（第 13 章），包含用户画像、可控写入、生命周期管理等 7 大能力 |
| v1.2 | 2025-01-21 | 文档修正：修复 8 处误导性和安全问题（启动命令、端口说明、异步描述、测试示例、DSN 日志、Prometheus 基数、配置矛盾、Milvus 部署） |
| v1.3 | 2025-01-21 | 文档修正 v2：修复测试示例导入错误、清除剩余 Prometheus 高基数标签、修正部署图端口、更新备份命令容器名 |
| v1.4 | 2025-01-21 | 安全与兼容性增强：修复 user_id 安全问题（从认证上下文提取）、添加日志脱敏提示、强调 tag 必须有限枚举、添加 Linux 下 host.docker.internal 兼容性说明（3 种解决方案） |
| v1.5 | 2025-01-21 | 安全与可运行性完善：修复列表/更新 API 的 user_id 一致性、澄清认证方案生产实践（JWT/上游鉴权）、标注定时任务伪代码需 AsyncIOScheduler、补充 Linux host network 端口冲突警告 |

---

**文档结束**
