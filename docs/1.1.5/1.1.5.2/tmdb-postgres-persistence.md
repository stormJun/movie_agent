# TMDB 数据入库设计（PostgreSQL）

## 系统概览

### 整体数据流图

```mermaid
graph TB
    subgraph "用户交互层"
        Query[用户查询]
        Response[系统响应]
    end
    
    subgraph "应用服务层"
        Router[路由决策]
        Enrich[TMDB Enrichment<br/>Service]
        Graph[临时图构建]
    end
    
    subgraph "外部API层"
        TMDB[TMDB API]
    end
    
    subgraph "异步持久化层"
        Queue[写入队列]
        Writer[后台 Writer]
    end
    
    subgraph "数据存储层"
        Postgres[(PostgreSQL)]
    end
    
    subgraph "图数据库层"
        Neo4j[(Neo4j)]
    end
    
    Query --> Router
    Router -->|实体提取| Enrich
    Enrich -->|API调用| TMDB
    TMDB -->|返回数据| Enrich
    Enrich --> Graph
    Graph --> Response
    
    Enrich -.->|异步| Queue
    Queue --> Writer
    Writer --> Postgres
    
    subgraph "ETL Pipeline"
        ETL[ETL Worker]
        Postgres -->|增量| ETL
        ETL --> Neo4j
    end

    style Query fill:#e6f7ff
    style Enrich fill:#fff7e6
    style TMDB fill:#f6ffed
    style Postgres fill:#f9f0ff
    style Neo4j fill:#fff0f6
```

### 职责分工矩阵

| 层级 | 组件 | 职责 | 数据格式 |
|-----|------|------|---------|
| **交互层** | 用户查询 | 提问 | 自然语言 |
| **服务层** | Router | 实体提取、路由决策 | extracted_entities |
| **服务层** | TMDBEnrichmentService | TMDB API调用、临时图构建 | 临时 GraphState |
| **持久化层** | PostgresTmdbStore | 原始数据备份、ETL Outbox | JSONB raw |
| **图数据库** | Neo4j | 关系查询、图遍历 | Nodes + Relationships |
| **ETL层** | ETL Worker | Postgres → Neo4j 增量同步 | Cypher |

**系统职责分层**：
- **Neo4j**: 关系查询、跳跃查询、图算法（Online Query Engine）
- **Postgres**: 持久化备份、RAW 数据沉淀、离线清洗与画像（Offline / Backup / Source of Truth）

本文档描述将 TMDB enrichment 数据持久化到 PostgreSQL 的实现方案。

## 设计原则

1. **不在 Postgres 里维护关系表**：关系是 Neo4j 的职责；Postgres 只存原始事实（raw JSONB）与少量可索引字段
2. **raw 必须足够重建图**：
   - `tmdb.movies.raw` 必须包含 `/movie/{id}?append_to_response=credits` 的完整返回
   - `tmdb.people.raw` 必须包含 `/person/{id}?append_to_response=combined_credits` 的完整返回
   - `tmdb.tv_shows.raw` 必须包含 `/tv/{id}?append_to_response=credits` 的完整返回
3. **以 TMDB ID 做幂等主键**：避免重复入库；每次命中只更新 `last_seen_at`、`fetched_at` 与 `raw`
4. **为 ETL 做增量**：写入时计算 `raw_hash`，仅当内容变化时把实体放入 ETL outbox（Postgres -> Neo4j 更高效）
5. **全量持久化请求日志**：作为离线可观测与回放依据（但它是"请求日志"，需要可清理）
6. **多语言可扩展**：默认以 `zh-CN` 写入基础表，同时支持用 translations 表补 `en-US` 等
7. **异步持久化**：使用后台 queue + worker 实现非阻塞持久化，不影响用户响应时间

## 实现架构

### 系统架构图

```mermaid
graph TB
    subgraph "用户层"
        User[用户查询]
    end

    subgraph "应用层"
        Router[Router]
        Enrichment[TMDBEnrichmentService]
    end

    subgraph "异步写入层"
        Queue[Async Queue]
        Writer[Writer Loop]
    end

    subgraph "持久化层"
        Store[PostgresTmdbStore]
        Postgres[(PostgreSQL<br/>tmdb schema)]
    end

    subgraph "图数据库层"
        Neo4j[(Neo4j)]
    end

    User -->|query| Router
    Router -->|extracted_entities| Enrichment
    Enrichment -->|持久化任务| Queue
    Queue -->|consume| Writer
    Writer -->|persist_enrichment| Store
    Store -->|write| Postgres
    Postgres -.->|ETL Outbox| Neo4j

    style Enrichment fill:#e1f5ff
    style Queue fill:#fff7e6
    style Store fill:#f6ffed
    style Postgres fill:#f9f0ff
    style Neo4j fill:#fff0f6
```

### 核心组件

#### 组件层次结构

```
Router (路由决策)
    ↓
EntityExtractor (实体提取)
    ↓
TMDBEnrichmentService (Enrichment 编排)
    ↓
├─ TMDBClient (TMDB API 客户端 + 消歧评分)
│   └─ 消歧评分 (_score_movie_candidate)
├─ TransientGraphBuilder (临时图构建)
│   └─ TransientGraph (nodes + edges)
└─ PostgresTmdbStore (持久化存储)
    ↓
Async Queue + Writer Loop (异步写入)
    ↓
PostgreSQL (tmdb schema)
```

#### 组件职责矩阵

| 组件 | 文件位置 | 职责 | 输入 | 输出 |
|------|---------|------|------|------|
| **Router** | `application/chat/handlers/chat_handler.py` | 路由决策、意图识别 | 用户查询 | selected_agent, query_intent, extracted_entities |
| **EntityExtractor** | `infrastructure/enrichment/entity_extractor.py` | 实体提取（正则匹配） | query_text | List[str] 实体名 |
| **TMDBEnrichmentService** | `infrastructure/enrichment/tmdb_enrichment_service.py` | 编排 enrichment 流程 | message, entities, context | EnrichmentResult |
| **TMDBClient** | `infrastructure/enrichment/tmdb_client.py` | TMDB API 调用 + 消歧 | entity_name, role_hint | tmdb_id, raw JSON |
| **TransientGraphBuilder** | `infrastructure/enrichment/graph_builder.py` | 构建临时图结构 | tmdb raw JSON | TransientGraph |
| **PostgresTmdbStore** | `infrastructure/persistence/postgres/tmdb_store.py` | PostgreSQL 持久化 | payloads, metadata | 存储到 tmdb schema |
| **Async Queue** | `TMDBEnrichmentService._write_queue` | 异步任务队列 | persistence job | 解耦用户响应 |
| **Writer Loop** | `TMDBEnrichmentService._writer_loop` | 后台持久化 worker | queue jobs | 调用 store.persist_enrichment |

#### 关键子功能

**TMDBClient 消歧机制**:
- 标题标准化与模糊匹配
- 年份对齐（target_year）
- 角色 hint（导演/演员/编剧）
- Popularity 分数加权
- 返回消歧后的候选列表（带分数）

**TransientGraphBuilder 图构建**:
- Movie 节点：title, overview, release_date, vote_average
- Person 节点：name, known_for_department
- Genre 节点：name
- 关系边：DIRECTED, ACTED_IN, CREW_MEMBER, BELONGS_TO_GENRE

**PostgresTmdbStore 持久化**:
- 计算每个 payload 的 raw_hash（SHA256）
- 仅当 raw_hash 变化时写入 ETL outbox
- 全量记录 enrichment_requests（可观测性）



#### 组件交互流程图

```mermaid
sequenceDiagram
    participant User as 用户
    participant Router as Router
    participant Extractor as EntityExtractor
    participant Service as TMDBEnrichmentService
    participant Client as TMDBClient
    participant TMDB as TMDB API
    participant Builder as GraphBuilder
    participant Queue as Async Queue
    participant Writer as Writer Loop
    participant Store as PostgresTmdbStore
    participant DB as PostgreSQL

    User->>Router: 用户查询
    Router->>Router: 意图识别 + 路由决策
    Router-->>User: 返回响应（非阻塞）
    
    par Enrichment 流程
        Router->>Extractor: extracted_entities
        Extractor-->>Router: List[str] 实体名
        Router->>Service: enrich_query(message, entities)
        
        Service->>Client: search_disambiguate(entity)
        Client->>TMDB: /search/multi
        TMDB-->>Client: candidates[]
        Client->>Client: 消歧评分
        Client-->>Service: selected(tmdb_id, score)
        
        Service->>Client: get_details(tmdb_id)
        Client->>TMDB: /movie/id + credits
        TMDB-->>Client: raw JSON
        Client-->>Service: payload{type, data}
        
        Service->>Builder: build_from_tmdb_payloads([payloads])
        Builder->>Builder: 解析 credits
        Builder->>Builder: 构建 nodes + edges
        Builder-->>Service: TransientGraph
        Service-->>Router: EnrichmentResult
    and 异步持久化
        Service->>Queue: put(persistence_job)
        Note over Queue: 不阻塞用户响应
        Writer->>Queue: get(job)
        Writer->>Store: persist_enrichment(**job)
        Store->>DB: BEGIN TRANSACTION
        
        par 写入多个表
            Store->>DB: INSERT enrichment_requests
            Store->>DB: UPSERT tmdb.movies
            Store->>DB: UPSERT tmdb.people
            Store->>DB: UPSERT tmdb.tv_shows
        end
        
        Store->>DB: INSERT neo4j_etl_outbox
        Store->>DB: COMMIT
    end
```

#### 数据流向图

```mermaid
graph LR
    subgraph "查询解析层"
        Q[用户查询] --> R[Router]
        R --> E[EntityExtractor]
    end
    
    subgraph "Enrichment 层"
        E --> S[TMDBEnrichmentService]
        S --> C[TMDBClient]
        C --> T[TMDB API]
        T --> C
        C --> S
        S --> G[TransientGraphBuilder]
        G --> TG[TransientGraph]
    end
    
    subgraph "持久化层"
        S -.异步.-> AQ[Async Queue]
        AQ --> WL[Writer Loop]
        WL --> PS[PostgresTmdbStore]
        PS --> PG[(PostgreSQL)]
    end
    
    subgraph "ETL 层"
        PG -.增量.-> ETLOut[(ETL Outbox)]
        ETLOut --> ETLW[ETL Worker]
        ETLW --> Neo[(Neo4j)]
    end

    style Q fill:#e6f7ff
    style S fill:#fff7e6
    style TG fill:#f6ffed
    style PG fill:#f9f0ff
    style Neo fill:#fff0f6
```

### 代码位置

- **Store 实现**: `backend/infrastructure/persistence/postgres/tmdb_store.py`
- **集成点**: `backend/infrastructure/enrichment/tmdb_enrichment_service.py`
- **Schema 定义**: 在 `PostgresTmdbStore._ensure_schema()` 中动态创建

### 异步持久化机制

**配置项**（`backend/infrastructure/config/settings.py`）:
```python
ENRICHMENT_ASYNC_WRITE_ENABLE = True  # 启用异步写入
ENRICHMENT_WRITE_QUEUE_SIZE = 100     # 队列大小
```

**工作流程**:
1. Enrichment 完成后，调用 `_maybe_persist()` 准备持久化任务
2. 如果启用异步写入，任务放入 `asyncio.Queue`
3. 后台 `_writer_loop()` 持续消费队列，调用 `store.persist_enrichment()`
4. 持久化失败不影响用户响应（best-effort）

### 异步持久化时序图

```mermaid
sequenceDiagram
    participant User as 用户
    participant Enrichment as TMDBEnrichmentService
    participant Queue as Async Queue
    participant Writer as Writer Loop
    participant Store as PostgresTmdbStore
    participant DB as PostgreSQL

    User->>Enrichment: enrich_query(message)
    Enrichment->>Enrichment: 调用 TMDB API
    Enrichment->>Enrichment: 构建临时图
    Enrichment-->>User: 返回结果（不等待持久化）

    par 异步持久化
        Enrichment->>Enrichment: _maybe_persist()
        Enrichment->>Queue: put(job)
        Note over Queue: 不阻塞用户响应
        Writer->>Queue: get(job)
        Writer->>Store: persist_enrichment(**job)
        Store->>DB: BEGIN TRANSACTION
        Store->>DB: INSERT enrichment_requests
        Store->>DB: UPSERT movies/people/tv_shows
        Store->>DB: INSERT neo4j_etl_outbox
        Store->>DB: COMMIT
        DB-->>Store: 成功
    end
```



## 数据来源与入库策略

### TMDB API 调用流程图

```mermaid
graph TD
    Start[用户查询] --> Extract[实体提取]
    Extract --> QueryType{查询类型?}
    
    QueryType -->|有明确实体| Multi["/search/multi"]
    QueryType -->|电视剧推荐| DiscoverTV["/discover/tv"]
    QueryType -->|电影推荐| DiscoverMovie["/discover/movie"]
    
    Multi --> MultiResp[候选列表]
    DiscoverTV --> TVResp[电视剧候选]
    DiscoverMovie --> MovieResp[电影候选]
    
    MultiResp --> Select[用户选择/自动选择]
    TVResp --> TopNTV[Top N 电视剧]
    MovieResp --> TopNMovie[Top N 电影]
    
    Select --> Details[获取详情]
    TopNTV --> TVDetails["/tv/id + credits"]
    TopNMovie --> MovieDetails["/movie/id + credits"]
    
    Details --> MovieStore[(tmdb.movies)]
    TVDetails --> TVStore[(tmdb.tv_shows)]
    MovieDetails -->|人物| PersonStore[(tmdb.people)]
    
    MovieStore --> RequestLog[(enrichment_requests)]
    TVStore --> RequestLog
    PersonStore --> RequestLog

    style Multi fill:#e1f5ff
    style DiscoverTV fill:#fff7e6
    style DiscoverMovie fill:#fff7e6
    style MovieStore fill:#f6ffed
    style TVStore fill:#f6ffed
    style PersonStore fill:#f6ffed
```

### TMDB API 调用链

**典型 Enrichment 流程**:
1. `/search/multi?query=...` → 返回 movie/tv/person 混合候选（用于消歧与选择）
2. 根据选中类型调用详情接口：
   - Movie: `/movie/{id}?append_to_response=credits` → 写入 `tmdb.movies.raw`
   - Person: `/person/{id}?append_to_response=combined_credits` → 写入 `tmdb.people.raw`
   - TV: `/tv/{id}?append_to_response=credits` → 写入 `tmdb.tv_shows.raw`

**推荐类电视剧查询**（无明确实体）:
1. `/discover/tv?...` → 拉取候选剧集（例如"中国电视剧"推荐）
2. 对 topN 调用 `/tv/{id}?append_to_response=credits` → 写入 `tmdb.tv_shows.raw`

**推荐类电影查询**（无明确实体）:
1. `/discover/movie?...` → 拉取候选电影
2. 对 topN 调用 `/movie/{id}?append_to_response=credits` → 写入 `tmdb.movies.raw`

### 入库策略

| 数据来源 | 入库目标 | 策略 |
|---------|---------|------|
| `/search/multi` 原始响应 | `tmdb.enrichment_requests.multi_results_raw` | 全量 JSONB 入库 |
| `/discover/tv` 原始响应 | `tmdb.enrichment_requests.discover_results_raw` | 全量 JSONB 入库 |
| `/discover/movie` 原始响应 | `tmdb.enrichment_requests.discover_results_raw` | 全量 JSONB 入库 |
| Movie 详情 + credits | `tmdb.movies` (raw + raw_hash) | upsert，变化时入 ETL outbox |
| Person 详情 + combined_credits | `tmdb.people` (raw + raw_hash) | upsert，变化时入 ETL outbox |
| TV 详情 + credits | `tmdb.tv_shows` (raw + raw_hash) | upsert，变化时入 ETL outbox |


## 数据库 Schema

### Schema ER 图

```mermaid
erDiagram
    tmdb ||--o{ enrichment_requests : "logs"
    tmdb ||--o{ neo4j_etl_outbox : "ETL"
    tmdb ||--o{ movie_translations : "has"
    tmdb ||--o{ person_translations : "has"
    tmdb ||--o{ tv_translations : "has"
    enrichment_requests ||--o{ enrichment_request_entities : "contains"

    tmdb {
        int tmdb_id PK
        text title
        jsonb raw
        text raw_hash
        timestamptz fetched_at
    }

    movies {
        int tmdb_id PK
        text title
        date release_date
        jsonb raw
        text raw_hash
    }

    people {
        int tmdb_id PK
        text name
        text known_for_department
        jsonb raw
        text raw_hash
    }

    tv_shows {
        int tmdb_id PK
        text name
        date first_air_date
        jsonb raw
        text raw_hash
    }

    enrichment_requests {
        uuid id PK
        text user_id
        text query_text
        jsonb selected
        jsonb multi_results_raw
        timestamptz created_at
    }

    neo4j_etl_outbox {
        uuid id PK
        text entity_type
        int tmdb_id
        text raw_hash
        timestamptz processed_at
    }

    movie_translations {
        int tmdb_movie_id FK
        text language PK
        text title
        jsonb raw
    }

    person_translations {
        int tmdb_person_id FK
        text language PK
        text biography
        jsonb raw
    }

    tv_translations {
        int tmdb_tv_id FK
        text language PK
        text name
        jsonb raw
    }

    enrichment_request_entities {
        uuid enrichment_request_id FK
        text entity_type
        int tmdb_id
        boolean selected
    }
```

### 依赖

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE SCHEMA IF NOT EXISTS tmdb;
```

### 1. 基础数据表

#### 1.1 电影表（`tmdb.movies`）

```sql
CREATE TABLE IF NOT EXISTS tmdb.movies (
  tmdb_id            int PRIMARY KEY,
  title              text,
  original_title     text,
  original_language  text,
  release_date       date,
  popularity         double precision,
  vote_average       double precision,
  vote_count         int,
  raw_language       text NOT NULL DEFAULT 'zh-CN',
  data_state         text NOT NULL DEFAULT 'full' CHECK (data_state IN ('stub','full')),
  raw                jsonb,
  raw_hash           text,
  fetched_at         timestamptz NOT NULL DEFAULT now(),
  first_seen_at      timestamptz NOT NULL DEFAULT now(),
  last_seen_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_tmdb_movies_state
    CHECK (
      (data_state = 'stub' AND raw IS NULL AND raw_hash IS NULL)
      OR
      (data_state = 'full' AND raw IS NOT NULL AND raw_hash IS NOT NULL)
    )
);
```

**字段说明**:
- `tmdb_id`: TMDB movie id（主键）
- `title` / `original_title`: 从 raw 派生，用于索引/展示
- `raw_language`: raw 字段对应语言（zh-CN/en-US）
- `data_state`: 数据状态（`full`=已补齐raw可重建图，`stub`=仅占位）
- `raw`: `/movie/{id}?append_to_response=credits` 完整返回（必须包含 credits.cast/crew）
- `raw_hash`: SHA256(JSON)，用于 ETL 增量与去重
- `fetched_at`: 本次 raw 拉取时间
- `first_seen_at` / `last_seen_at`: 首次/最近命中时间

#### 1.2 人物表（`tmdb.people`）

```sql
CREATE TABLE IF NOT EXISTS tmdb.people (
  tmdb_id               int PRIMARY KEY,
  name                  text,
  original_name         text,
  known_for_department  text,
  popularity            double precision,
  raw_language          text NOT NULL DEFAULT 'zh-CN',
  data_state            text NOT NULL DEFAULT 'full' CHECK (data_state IN ('stub','full')),
  raw                   jsonb,
  raw_hash              text,
  fetched_at            timestamptz NOT NULL DEFAULT now(),
  first_seen_at         timestamptz NOT NULL DEFAULT now(),
  last_seen_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_tmdb_people_state
    CHECK (
      (data_state = 'stub' AND raw IS NULL AND raw_hash IS NULL)
      OR
      (data_state = 'full' AND raw IS NOT NULL AND raw_hash IS NOT NULL)
    )
);
```

#### 1.3 电视剧表（`tmdb.tv_shows`）

```sql
CREATE TABLE IF NOT EXISTS tmdb.tv_shows (
  tmdb_id            int PRIMARY KEY,
  name               text,
  original_name      text,
  original_language  text,
  first_air_date     date,
  popularity         double precision,
  vote_average       double precision,
  vote_count         int,
  raw_language       text NOT NULL DEFAULT 'zh-CN',
  data_state         text NOT NULL DEFAULT 'full' CHECK (data_state IN ('stub','full')),
  raw                jsonb,
  raw_hash           text,
  fetched_at         timestamptz NOT NULL DEFAULT now(),
  first_seen_at      timestamptz NOT NULL DEFAULT now(),
  last_seen_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_tmdb_tv_shows_state
    CHECK (
      (data_state = 'stub' AND raw IS NULL AND raw_hash IS NULL)
      OR
      (data_state = 'full' AND raw IS NOT NULL AND raw_hash IS NOT NULL)
    )
);
```

### 2. 多语言表（可选）

#### 2.1 电影多语言（`tmdb.movie_translations`）

```sql
CREATE TABLE IF NOT EXISTS tmdb.movie_translations (
  tmdb_movie_id  int NOT NULL REFERENCES tmdb.movies(tmdb_id) ON DELETE CASCADE,
  language       text NOT NULL,
  title          text,
  overview       text,
  raw            jsonb,
  raw_hash       text,
  fetched_at     timestamptz NOT NULL DEFAULT now(),
  first_seen_at  timestamptz NOT NULL DEFAULT now(),
  last_seen_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tmdb_movie_id, language)
);
```

#### 2.2 人物多语言（`tmdb.person_translations`）

```sql
CREATE TABLE IF NOT EXISTS tmdb.person_translations (
  tmdb_person_id  int NOT NULL REFERENCES tmdb.people(tmdb_id) ON DELETE CASCADE,
  language        text NOT NULL,
  biography       text,
  raw             jsonb,
  raw_hash        text,
  fetched_at      timestamptz NOT NULL DEFAULT now(),
  first_seen_at   timestamptz NOT NULL DEFAULT now(),
  last_seen_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tmdb_person_id, language)
);
```

#### 2.3 电视剧多语言（`tmdb.tv_translations`）

```sql
CREATE TABLE IF NOT EXISTS tmdb.tv_translations (
  tmdb_tv_id     int NOT NULL REFERENCES tmdb.tv_shows(tmdb_id) ON DELETE CASCADE,
  language       text NOT NULL,
  name           text,
  overview       text,
  raw            jsonb,
  raw_hash       text,
  fetched_at     timestamptz NOT NULL DEFAULT now(),
  first_seen_at  timestamptz NOT NULL DEFAULT now(),
  last_seen_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tmdb_tv_id, language)
);
```

### 3. Enrichment 请求日志（`tmdb.enrichment_requests`）

用于可观测、回放、统计命中率/耗时/候选质量、离线加工。

```sql
CREATE TABLE IF NOT EXISTS tmdb.enrichment_requests (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id          text,
  user_id             text NOT NULL,
  session_id          text NOT NULL,
  conversation_id     uuid,
  user_message_id     uuid,
  query_text          text NOT NULL,
  tmdb_endpoint       text NOT NULL DEFAULT '/search/multi',
  role_hint           text,
  extracted_entities  jsonb,
  selected            jsonb,
  selected_media_type text,
  selected_tmdb_id    int,
  selected_score      double precision,
  candidates_top3     jsonb,
  multi_results_raw   jsonb,
  discover_results_raw jsonb,
  tmdb_language       text,
  duration_ms         double precision,
  created_at          timestamptz NOT NULL DEFAULT now()
);
```

**索引**:
```sql
CREATE INDEX idx_tmdb_enrich_req_created ON tmdb.enrichment_requests(created_at DESC);
CREATE INDEX idx_tmdb_enrich_req_user ON tmdb.enrichment_requests(user_id, created_at DESC);
CREATE INDEX idx_tmdb_enrich_req_selected ON tmdb.enrichment_requests(selected_media_type, selected_tmdb_id);
CREATE INDEX idx_tmdb_enrich_req_endpoint ON tmdb.enrichment_requests(tmdb_endpoint, created_at DESC);
```

**字段说明**:
- `request_id`: 流式接口 request_id / Langfuse trace_id（用于串联 debug/trace）
- `tmdb_endpoint`: 本次使用的 TMDB 入口（`/search/multi` 或 `/discover/tv` 或 `/discover/movie`）
- `extracted_entities`: Router/regex 抽取的实体列表（JSONB）
- `selected`: 最终选中的 candidate（media_type/tmdb_id/score）
- `candidates_top3`: top3 候选（用于 UI/debug 快速展示）
- `multi_results_raw`: `/search/multi` 原始返回（results 全量 + page/total_pages）
- `discover_results_raw`: `/discover/tv` 或 `/discover/movie` 原始返回

### 4. Neo4j ETL Outbox（`tmdb.neo4j_etl_outbox`）

用于增量同步：仅当 `raw_hash` 变化时才入队。

```sql
CREATE TABLE IF NOT EXISTS tmdb.neo4j_etl_outbox (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type     text NOT NULL CHECK (entity_type IN ('movie','person','tv')),
  tmdb_id         int  NOT NULL,
  raw_hash        text NOT NULL,
  action          text NOT NULL DEFAULT 'upsert' CHECK (action IN ('upsert','delete')),
  request_id      text,
  enqueued_at     timestamptz NOT NULL DEFAULT now(),
  locked_at       timestamptz,
  attempts        int NOT NULL DEFAULT 0,
  last_attempt_at timestamptz,
  last_error      text,
  processed_at    timestamptz
);
```

**索引**:
```sql
CREATE INDEX idx_tmdb_etl_outbox_pending ON tmdb.neo4j_etl_outbox(processed_at, enqueued_at);
CREATE INDEX idx_tmdb_etl_outbox_entity ON tmdb.neo4j_etl_outbox(entity_type, tmdb_id);
CREATE UNIQUE INDEX ux_tmdb_etl_outbox_dedupe ON tmdb.neo4j_etl_outbox(entity_type, tmdb_id, raw_hash, action);
```

### 5. 请求-实体映射（`tmdb.enrichment_request_entities`，可选）

便于统计/回放/离线加工。

```sql
CREATE TABLE IF NOT EXISTS tmdb.enrichment_request_entities (
  enrichment_request_id uuid NOT NULL REFERENCES tmdb.enrichment_requests(id) ON DELETE CASCADE,
  entity_type           text NOT NULL CHECK (entity_type IN ('movie','person','tv')),
  tmdb_id               int  NOT NULL,
  selected              boolean NOT NULL DEFAULT false,
  score                 double precision,
  PRIMARY KEY (enrichment_request_id, entity_type, tmdb_id)
);
```


## 持久化流程实现

### 持久化流程图

```mermaid
flowchart TD
    Start([Enrichment 完成]) --> Check{检查条件}
    
    Check -->|incognito=True| End1([结束])
    Check -->|user_id 为空| End1
    Check -->|session_id 为空| End1
    Check -->|通过检查| Prepare[准备持久化任务]
    
    Prepare --> AsyncCheck{异步写入?}
    
    AsyncCheck -->|是| Queue[放入 Async Queue]
    AsyncCheck -->|否| Sync[同步写入]
    
    Queue --> Writer[Writer Loop 消费]
    Writer --> StoreCall[调用 persist_enrichment]
    Sync --> StoreCall
    
    StoreCall --> Begin[BEGIN TRANSACTION]
    
    Begin --> Step1[写入 enrichment_requests]
    Step1 --> Loop{遍历 payloads}
    
    Loop --> Payload1[movie payload]
    Loop --> Payload2[person payload]
    Loop --> Payload3[tv payload]
    
    Payload1 --> CalcHash1[计算 raw_hash]
    Payload2 --> CalcHash2[计算 raw_hash]
    Payload3 --> CalcHash3[计算 raw_hash]
    
    CalcHash1 --> Compare1{raw_hash<br/>变化?}
    CalcHash2 --> Compare2{raw_hash<br/>变化?}
    CalcHash3 --> Compare3{raw_hash<br/>变化?}
    
    Compare1 -->|是| Upsert1[UPSERT tmdb.movies]
    Compare2 -->|是| Upsert2[UPSERT tmdb.people]
    Compare3 -->|是| Upsert3[UPSERT tmdb.tv_shows]
    
    Upsert1 --> ETL1[写入 neo4j_etl_outbox]
    Upsert2 --> ETL2[写入 neo4j_etl_outbox]
    Upsert3 --> ETL3[写入 neo4j_etl_outbox]
    
    Compare1 -->|否| NextLoop
    Compare2 -->|否| NextLoop
    Compare3 -->|否| NextLoop
    
    ETL1 --> NextLoop{还有 payload?}
    ETL2 --> NextLoop
    ETL3 --> NextLoop
    
    NextLoop -->|是| Loop
    NextLoop -->|否| Commit[COMMIT]
    
    Commit --> Success{成功?}
    Success -->|是| End2([完成])
    Success -->|否| Log[记录错误日志]
    
    Log --> End2

    style Check fill:#fff1f0
    style AsyncCheck fill:#fff7e6
    style Queue fill:#e6f7ff
    style StoreCall fill:#f6ffed
    style Begin fill:#fff0f6
    style Commit fill:#fff0f6
```

### 数据流示意图

```mermaid
graph LR
    subgraph "TMDB API"
        M1["/movie/id"]
        M2["/person/id"]
        M3["/tv/id"]
    end
    
    subgraph "PostgreSQL Write"
        R1[enrichment_requests]
        M1 --> Movies[movies]
        M2 --> People[people]
        M3 --> TV[tv_shows]
        Movies --> ETL[neo4j_etl_outbox]
        People --> ETL
        TV --> ETL
    end
    
    subgraph "PostgreSQL Read"
        ETL -.->|增量同步| Worker[ETL Worker]
    end
    
    subgraph "Neo4j"
        Worker --> Nodes[(Movie Nodes)]
        Worker --> PersonNodes[(Person Nodes)]
        Worker --> Relations[Relations]
    end

    style R1 fill:#e6f7ff
    style Movies fill:#f6ffed
    style People fill:#f6ffed
    style TV fill:#f6ffed
    style ETL fill:#fff7e6
    style Nodes fill:#fff0f6
    style PersonNodes fill:#fff0f6
    style Relations fill:#fff0f6
```

**位置**: `backend/infrastructure/persistence/postgres/tmdb_store.py`

```python
class PostgresTmdbStore:
    async def persist_enrichment(
        self,
        *,
        user_id: str,
        session_id: str,
        query_text: str,
        tmdb_endpoint: str,
        extracted_entities: list[str] | None,
        disambiguation: list[dict[str, Any]] | None,
        payloads: list[dict[str, Any]] | None,
        request_id: str | None = None,
        conversation_id: UUID | None = None,
        user_message_id: UUID | None = None,
        candidates_top3: Any | None = None,
        multi_results_raw: Any | None = None,
        discover_results_raw: Any | None = None,
        role_hint: str | None = None,
        tmdb_language: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Persist one enrichment run (best-effort)."""
        # 1. 写入 enrichment_requests
        # 2. 对每个 payload（movie/person/tv）：
        #    a. 计算 raw_hash
        #    b. 比较 DB 中现有 raw_hash
        #    c. Upsert 到对应表（movies/people/tv_shows）
        #    d. 如果 raw_hash 变化：写入 neo4j_etl_outbox
        # 3. 写入 enrichment_request_entities（可选）
```

### TMDBEnrichmentService 集成

**位置**: `backend/infrastructure/enrichment/tmdb_enrichment_service.py`

```python
class TMDBEnrichmentService:
    def __init__(self, *, store=None):
        self._store = store  # PostgresTmdbStore instance
        self._write_queue = None
        self._writer_task = None

    async def _maybe_persist(self, ...) -> None:
        """Best-effort persistence (does not affect user response)."""
        if incognito:
            return
        if not user_id or not session_id:
            return

        job = { ... }  # 准备持久化参数

        if ENRICHMENT_ASYNC_WRITE_ENABLE:
            await self._ensure_writer()
            await self._write_queue.put(job)
        else:
            persist = getattr(self._store, "persist_enrichment", None)
            if callable(persist):
                await persist(**job)

    async def _writer_loop(self) -> None:
        """Background worker that processes persistence queue."""
        while True:
            job = await self._write_queue.get()
            if job is None:
                return
            try:
                await self._store.persist_enrichment(**job)
            except Exception as e:
                logger.debug("tmdb persistence job failed: %s", e)
```

### Upsert 策略

**以 Movie 为例**:
```python
# 1. 读取现有 raw_hash
current = await conn.fetchval(
    "SELECT raw_hash FROM tmdb.movies WHERE tmdb_id=$1",
    tmdb_id
)

# 2. Upsert (INSERT ... ON CONFLICT DO UPDATE)
await conn.execute("""
    INSERT INTO tmdb_movies (...)
    VALUES (...)
    ON CONFLICT (tmdb_id) DO UPDATE SET
        title=EXCLUDED.title,
        raw=EXCLUDED.raw,
        raw_hash=EXCLUDED.raw_hash,
        last_seen_at=now()
""")

# 3. 如果 raw_hash 变化，入 ETL outbox
if current != raw_hash:
    await conn.execute("""
        INSERT INTO tmdb.neo4j_etl_outbox
        VALUES (...)
        ON CONFLICT DO NOTHING
    """)
```


## Postgres -> Neo4j ETL（建议）

### ETL 架构图

```mermaid
graph TB
    subgraph "PostgreSQL Source"
        Outbox[(neo4j_etl_outbox)]
        MoviesRaw[(tmdb.movies)]
        PeopleRaw[(tmdb.people)]
        TVRaw[(tmdb.tv_shows)]
    end
    
    subgraph "ETL Worker"
        Fetch[拉取待处理任务]
        Lock[锁定任务]
        ReadRaw[读取 raw 数据]
        Parse[解析 Credits]
        Generate[生成 Nodes/Edges]
        WriteNeo[写入 Neo4j]
        Update[更新状态]
    end
    
    subgraph "Neo4j Target"
        MovieNodes[(Movie Nodes)]
        PersonNodes[(Person Nodes)]
        TVNodes[(TV Nodes)]
        DirectorRel[DIRECTED]
        CastRel[ACTED_IN]
        CrewRel[CREW_MEMBER]
    end
    
    Outbox --> Fetch
    Fetch --> Lock
    Lock --> ReadRaw
    ReadRaw --> Entity{entity_type?}
    
    Entity -->|movie| MoviesRaw
    Entity -->|person| PeopleRaw
    Entity -->|tv| TVRaw
    
    MoviesRaw --> Parse
    PeopleRaw --> Parse
    TVRaw --> Parse
    
    Parse --> Generate
    Generate --> WriteNeo
    
    WriteNeo --> MovieNodes
    WriteNeo --> PersonNodes
    WriteNeo --> TVNodes
    WriteNeo --> DirectorRel
    WriteNeo --> CastRel
    WriteNeo --> CrewRel
    
    WriteNeo --> Update
    Update --> Outbox

    style Outbox fill:#f9f0ff
    style MoviesRaw fill:#f6ffed
    style PeopleRaw fill:#f6ffed
    style TVRaw fill:#f6ffed
    style Fetch fill:#e6f7ff
    style WriteNeo fill:#fff0f6
```

### ETL 工作流程图

```mermaid
sequenceDiagram
    participant Worker as ETL Worker
    participant PG as PostgreSQL
    participant Neo as Neo4j

    Worker->>PG: SELECT * FROM neo4j_etl_outbox<br/>WHERE processed_at IS NULL<br/>LIMIT 10
    
    loop 处理每条任务
        Worker->>PG: UPDATE neo4j_etl_outbox<br/>SET locked_at = now()
        Worker->>PG: SELECT raw FROM tmdb.movies<br/>WHERE tmdb_id = $1
        PG-->>Worker: JSONB raw
        
        Worker->>Worker: 解析 credits.cast
        Worker->>Worker: 解析 credits.crew
        
        Worker->>Neo: BEGIN TRANSACTION
        
        par 创建 Movie 节点
            Worker->>Neo: MERGE (m:Movie {tmdb_id: $id})
            Worker->>Neo: SET m.title = $title
        and 创建 Person 节点
            Worker->>Neo: MERGE (p:Person {tmdb_id: $id})
        end
        
        par 创建关系
            Worker->>Neo: MATCH (m:Movie), (p:Person)
            Worker->>Neo: MERGE (p)-[:ACTED_IN]->(m)
        and 创建 Crew 关系
            Worker->>Neo: MATCH (m:Movie), (p:Person)
            Worker->>Neo: MERGE (p)-[:CREW_MEMBER]->(m)
        end
        
        Worker->>Neo: COMMIT
        
        Worker->>PG: UPDATE neo4j_etl_outbox<br/>SET processed_at = now()
    end
```

### ETL Worker 职责

1. 从 `tmdb.neo4j_etl_outbox` 拉取待处理任务（`WHERE processed_at IS NULL`）
2. 读取对应 `tmdb.movies.raw` / `tmdb.people.raw` / `tmdb.tv_shows.raw`
3. 解析 credits（movie/tv）与 combined_credits（person）
4. 生成 Neo4j nodes/edges 并写入 Neo4j
5. 更新 `processed_at` / `attempts` / `last_error`

**伪代码**:
```python
async def etl_worker():
    while True:
        tasks = await fetch_pending_tasks(limit=10)
        for task in tasks:
            try:
                entity_type, tmdb_id, raw_hash = task
                raw = await fetch_raw(entity_type, tmdb_id)
                await sync_to_neo4j(entity_type, tmdb_id, raw)
                await mark_processed(task.id)
            except Exception as e:
                await mark_failed(task.id, error=str(e))
```

## 隐私与数据保留

### 数据分类

| 表名 | 数据类型 | 保留策略 | 删除支持 |
|-----|---------|---------|---------|
| `tmdb.movies` | 第三方公开数据 | 长期保留 | 不需要 |
| `tmdb.people` | 第三方公开数据 | 长期保留 | 不需要 |
| `tmdb.tv_shows` | 第三方公开数据 | 长期保留 | 不需要 |
| `tmdb.enrichment_requests` | 包含用户 query | 支持 TTL 删除 | 按 `user_id` / `conversation_id` |
| `tmdb.neo4j_etl_outbox` | 无用户信息 | 处理后清理 | 不需要 |

### 删除支持

```sql
-- 按 user_id 删除所有 enrichment 日志
DELETE FROM tmdb.enrichment_requests WHERE user_id = $1;

-- 按 conversation_id 删除
DELETE FROM tmdb.enrichment_requests WHERE conversation_id = $1;

-- TTL 清理（例如保留 30 天）
DELETE FROM tmdb.enrichment_requests
WHERE created_at < now() - interval '30 days';
```

## 配置与依赖

### 环境变量

```bash
# PostgreSQL 连接
DATABASE_URL=postgresql://user:pass@host:port/db

# Enrichment 持久化开关
ENRICHMENT_ASYNC_WRITE_ENABLE=true
ENRICHMENT_WRITE_QUEUE_SIZE=100
```

### 依赖包

```python
# requirements.txt
asyncpg>=0.29.0  # PostgreSQL async driver
```

## 初始化与使用

### Store 初始化

```python
from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

store = PostgresTmdbStore(
    dsn="postgresql://user:pass@host:port/db",
    min_size=1,
    max_size=10,
)

# Schema 会在首次连接时自动创建（dev环境）
# 生产环境建议使用迁移工具管理 schema
```

### 集成到 Enrichment Service

```python
from infrastructure.enrichment.tmdb_enrichment_service import TMDBEnrichmentService

service = TMDBEnrichmentService(
    tmdb_client=tmdb_client,
    graph_builder=graph_builder,
    store=store,  # 注入 PostgresTmdbStore
)

# enrichment 完成后会自动持久化（如果 incognito=False）
result = await service.enrich_query(
    message="《喜宴》的导演是谁？",
    kb_prefix="movie",
    user_id="user123",
    session_id="session456",
    incognito=False,
)
```

## 生产环境建议

1. **Schema 管理**: 使用迁移工具（如 alembic、sqitch）而非 runtime auto-create
2. **连接池配置**: 根据负载调整 `min_size` / `max_size`
3. **监控**:
   - 监控 ETL outbox 积压情况
   - 监控持久化队列大小
   - 监控持久化失败率
4. **清理策略**:
   - 定期清理过期的 `enrichment_requests`
   - 定期清理已处理的 ETL outbox 记录
5. **索引优化**:
   - 根据查询模式添加额外索引
   - 定期 `VACUUM ANALYZE`

## 故障排查

### 持久化未生效

1. 检查 `ENRICHMENT_ASYNC_WRITE_ENABLE` 是否为 `True`
2. 检查 `incognito` 参数是否为 `False`
3. 检查 `user_id` / `session_id` 是否存在
4. 查看日志中的 "tmdb persistence job failed" 错误

### Schema 创建失败

1. 检查是否有 `pgcrypto` 扩展权限
2. 检查是否有 `CREATE SCHEMA` 权限
3. 生产环境应使用预建 schema

## 相关文档

- [TMDB Enrichment 设计](../1.1.5.1/tmdb-enrichment.md)
- [GraphRAG Integration](../../1.1.3/graphrag-integration.md)
- [系统架构](../../1.1.1/architecture.md)
