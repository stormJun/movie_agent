# TMDB -> Postgres 最小 MVP 表模型（电影域）

目标：用最小的表与字段集合，把 TMDB 查询时增强（Query-time Enrichment）过程中获取到的“基础事实数据”沉淀到 PostgreSQL，作为后续：
- 离线清洗 / 纠错 / 质量评估
- Postgres -> Neo4j 增量 ETL（Source of Truth）
- 复用 TMDB 数据减少重复请求（可选）

本文是“最小 MVP”版本：优先覆盖项目目前运行时真正会用到的 movie/person/tv + 请求日志 + ETL outbox。

相关文档：
- TMDB 端点参考：`docs/1.1.5/1.1.5.2/tmdb-api-reference.md`
- 更完整的持久化方案草案：`docs/1.1.5/1.1.5.2/tmdb-postgres-persistence.md`（如果你们要保留 translations/更多实体）
- 代码现状（运行时自举 schema）：`backend/infrastructure/persistence/postgres/tmdb_store.py`

---

## 1. MVP 设计原则（约束）

1) Postgres 不维护“关系表”
- 关系查询与图算法是 Neo4j 的职责；Postgres 只存“事实快照（raw JSONB）+ 少量索引字段 + 增量 outbox”。

2) raw 必须可重建图（Graph Builder / Neo4j ETL）
- `tmdb.movies.raw`：来自 `GET /movie/{id}?append_to_response=credits`
- `tmdb.people.raw`：来自 `GET /person/{id}?append_to_response=combined_credits`
- `tmdb.tv_shows.raw`：来自 `GET /tv/{id}?append_to_response=credits`

3) 幂等主键：TMDB ID
- 每次命中同一实体时，更新 `raw/raw_hash/fetched_at/last_seen_at`，避免重复插入。

4) 增量：raw_hash 作为“内容变更检测”
- 仅当 raw_hash 变化时，写入 `neo4j_etl_outbox`（让 Postgres -> Neo4j 的 ETL 成本可控）。

5) 允许 stub（占位）
- 有时只拿到了标题/名字，暂时没有 raw（或不想同步请求 TMDB）。MVP 允许先写 `data_state=stub`，后续再补全为 `full`。

---

## 2. MVP 覆盖的 TMDB 调用与落库映射

运行时（enrichment）常见链路：

1) 对象解析/消歧
- `GET /search/multi`
- 落库：`tmdb.enrichment_requests.multi_results_raw`（可选但推荐，便于回放/评估）

2) 详情快照（用于事实问答与图构建）
- `GET /movie/{id}?append_to_response=credits` -> `tmdb.movies.raw`
- `GET /person/{id}?append_to_response=combined_credits` -> `tmdb.people.raw`
- `GET /tv/{id}?append_to_response=credits` -> `tmdb.tv_shows.raw`

3) 推荐/筛选候选集合（可选）
- `GET /discover/movie` / `GET /discover/tv`
- 落库：`tmdb.enrichment_requests.discover_results_raw`（可选但推荐，便于回放/评估）

---

## 3. Schema 约定

- 统一 schema：`tmdb`
- 时间：`timestamptz`
- 原始快照：`jsonb`（整包存）
- Hash：`raw_hash`（建议 SHA-256，对 json 做稳定序列化后计算）

---

## 4. 最小 MVP DDL（含字段注释）

说明：
- 以下 DDL 是“推荐的最小集合”；生产环境建议用 migration 管理。
- 如果你们已采用 `backend/infrastructure/persistence/postgres/tmdb_store.py` 的运行时自举 schema，可把它视为该文档的“实现参考”。

### 4.1 Schema 与扩展

```sql
CREATE SCHEMA IF NOT EXISTS tmdb;

-- 仅当你需要 gen_random_uuid()（日志/outbox 用）：
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

### 4.2 tmdb.movies（电影快照）

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

COMMENT ON TABLE tmdb.movies IS 'TMDB 电影实体快照（raw 为 /movie/{id}?append_to_response=credits 返回）；Postgres 不维护关系，关系由 Neo4j/ETL 生成';
COMMENT ON COLUMN tmdb.movies.tmdb_id IS 'TMDB movie_id（主键，幂等）';
COMMENT ON COLUMN tmdb.movies.title IS '中文标题（来自 TMDB title，可能为空）';
COMMENT ON COLUMN tmdb.movies.original_title IS '原始标题（original_title）';
COMMENT ON COLUMN tmdb.movies.original_language IS '原始语言（original_language）';
COMMENT ON COLUMN tmdb.movies.release_date IS '上映日期（release_date）';
COMMENT ON COLUMN tmdb.movies.popularity IS 'TMDB popularity（用于排序/消歧参考）';
COMMENT ON COLUMN tmdb.movies.vote_average IS 'TMDB vote_average（评分均值）';
COMMENT ON COLUMN tmdb.movies.vote_count IS 'TMDB vote_count（评分数）';
COMMENT ON COLUMN tmdb.movies.raw_language IS 'raw 快照语言（默认 zh-CN；必要时可回退 en-US 并合并到 raw）';
COMMENT ON COLUMN tmdb.movies.data_state IS '数据状态：stub=占位无 raw；full=有 raw 快照';
COMMENT ON COLUMN tmdb.movies.raw IS '原始 JSONB 快照（建议包含 credits 以支持导演/演员与图构建）';
COMMENT ON COLUMN tmdb.movies.raw_hash IS 'raw 内容哈希（稳定序列化后 SHA-256）；用于增量 ETL 变更检测';
COMMENT ON COLUMN tmdb.movies.fetched_at IS '本次 raw 拉取时间（最后一次 fetch）';
COMMENT ON COLUMN tmdb.movies.first_seen_at IS '首次入库时间';
COMMENT ON COLUMN tmdb.movies.last_seen_at IS '最近一次被查询/命中时间（用于冷热/清理策略）';

CREATE INDEX IF NOT EXISTS idx_tmdb_movies_release_date
ON tmdb.movies(release_date DESC);

CREATE INDEX IF NOT EXISTS idx_tmdb_movies_last_seen
ON tmdb.movies(last_seen_at DESC);
```

### 4.3 tmdb.people（人物快照）

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

COMMENT ON TABLE tmdb.people IS 'TMDB 人物实体快照（raw 为 /person/{id}?append_to_response=combined_credits 返回）；用于导演/演员问答与作品列表';
COMMENT ON COLUMN tmdb.people.tmdb_id IS 'TMDB person_id（主键，幂等）';
COMMENT ON COLUMN tmdb.people.name IS '中文姓名（name）';
COMMENT ON COLUMN tmdb.people.original_name IS '原始姓名（original_name）';
COMMENT ON COLUMN tmdb.people.known_for_department IS '部门（Acting/Directing 等）';
COMMENT ON COLUMN tmdb.people.popularity IS 'TMDB popularity（用于排序/消歧参考）';
COMMENT ON COLUMN tmdb.people.raw_language IS 'raw 快照语言（默认 zh-CN）';
COMMENT ON COLUMN tmdb.people.data_state IS '数据状态：stub/full';
COMMENT ON COLUMN tmdb.people.raw IS '原始 JSONB 快照（建议包含 combined_credits）';
COMMENT ON COLUMN tmdb.people.raw_hash IS 'raw 内容哈希（用于增量 ETL）';
COMMENT ON COLUMN tmdb.people.fetched_at IS '本次 raw 拉取时间';
COMMENT ON COLUMN tmdb.people.first_seen_at IS '首次入库时间';
COMMENT ON COLUMN tmdb.people.last_seen_at IS '最近一次命中时间';

CREATE INDEX IF NOT EXISTS idx_tmdb_people_last_seen
ON tmdb.people(last_seen_at DESC);
```

### 4.4 tmdb.tv_shows（电视剧快照）

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

COMMENT ON TABLE tmdb.tv_shows IS 'TMDB 电视剧实体快照（raw 为 /tv/{id}?append_to_response=credits 返回）；用于电视剧推荐/人物作品列表补证';
COMMENT ON COLUMN tmdb.tv_shows.tmdb_id IS 'TMDB tv_id（主键，幂等）';
COMMENT ON COLUMN tmdb.tv_shows.name IS '中文剧名（name）';
COMMENT ON COLUMN tmdb.tv_shows.original_name IS '原始剧名（original_name）';
COMMENT ON COLUMN tmdb.tv_shows.original_language IS '原始语言（original_language）';
COMMENT ON COLUMN tmdb.tv_shows.first_air_date IS '首播日期（first_air_date）';
COMMENT ON COLUMN tmdb.tv_shows.popularity IS 'TMDB popularity';
COMMENT ON COLUMN tmdb.tv_shows.vote_average IS 'TMDB vote_average';
COMMENT ON COLUMN tmdb.tv_shows.vote_count IS 'TMDB vote_count';
COMMENT ON COLUMN tmdb.tv_shows.raw_language IS 'raw 快照语言（默认 zh-CN）';
COMMENT ON COLUMN tmdb.tv_shows.data_state IS '数据状态：stub/full';
COMMENT ON COLUMN tmdb.tv_shows.raw IS '原始 JSONB 快照（建议包含 credits）';
COMMENT ON COLUMN tmdb.tv_shows.raw_hash IS 'raw 内容哈希（用于增量 ETL）';
COMMENT ON COLUMN tmdb.tv_shows.fetched_at IS '本次 raw 拉取时间';
COMMENT ON COLUMN tmdb.tv_shows.first_seen_at IS '首次入库时间';
COMMENT ON COLUMN tmdb.tv_shows.last_seen_at IS '最近一次命中时间';

CREATE INDEX IF NOT EXISTS idx_tmdb_tv_last_seen
ON tmdb.tv_shows(last_seen_at DESC);
```

### 4.5 tmdb.enrichment_requests（请求日志：可观测/回放）

```sql
CREATE TABLE IF NOT EXISTS tmdb.enrichment_requests (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id           text,
  user_id              text NOT NULL,
  session_id           text NOT NULL,
  conversation_id      uuid,
  user_message_id      uuid,
  query_text           text NOT NULL,
  tmdb_endpoint        text NOT NULL DEFAULT '/search/multi',
  role_hint            text,
  extracted_entities   jsonb,
  selected             jsonb,
  selected_media_type  text,
  selected_tmdb_id     int,
  selected_score       double precision,
  candidates_top3      jsonb,
  multi_results_raw    jsonb,
  discover_results_raw jsonb,
  tmdb_language        text,
  duration_ms          double precision,
  created_at           timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE tmdb.enrichment_requests IS 'TMDB enrichment 请求日志（用于可观测、回放、质量评估）；可按时间清理';
COMMENT ON COLUMN tmdb.enrichment_requests.id IS '主键 UUID';
COMMENT ON COLUMN tmdb.enrichment_requests.request_id IS '业务 request_id（通常与 SSE request_id / Langfuse trace id 对齐）';
COMMENT ON COLUMN tmdb.enrichment_requests.user_id IS '用户 ID';
COMMENT ON COLUMN tmdb.enrichment_requests.session_id IS '前端会话 ID';
COMMENT ON COLUMN tmdb.enrichment_requests.conversation_id IS '后端对话 ID（可为空）';
COMMENT ON COLUMN tmdb.enrichment_requests.user_message_id IS '用户消息 ID（可为空）';
COMMENT ON COLUMN tmdb.enrichment_requests.query_text IS '用户原始 query 文本';
COMMENT ON COLUMN tmdb.enrichment_requests.tmdb_endpoint IS '触发的 TMDB 端点（/search/multi 或 /discover/* 等）';
COMMENT ON COLUMN tmdb.enrichment_requests.role_hint IS '人物角色提示（director/actor 等，来自 query/Router）';
COMMENT ON COLUMN tmdb.enrichment_requests.extracted_entities IS '实体候选列表（来自 Router 或 EntityExtractor）';
COMMENT ON COLUMN tmdb.enrichment_requests.selected IS '消歧选择结果（media_type/id/score/title 等）';
COMMENT ON COLUMN tmdb.enrichment_requests.selected_media_type IS '选中类型（movie/person/tv）';
COMMENT ON COLUMN tmdb.enrichment_requests.selected_tmdb_id IS '选中实体 TMDB ID';
COMMENT ON COLUMN tmdb.enrichment_requests.selected_score IS '选中实体消歧分数（用于调参/评估）';
COMMENT ON COLUMN tmdb.enrichment_requests.candidates_top3 IS 'Top3 候选摘要（用于 debug UI / 评估）';
COMMENT ON COLUMN tmdb.enrichment_requests.multi_results_raw IS '原始 /search/multi 返回（可为空）';
COMMENT ON COLUMN tmdb.enrichment_requests.discover_results_raw IS '原始 /discover 返回（可为空）';
COMMENT ON COLUMN tmdb.enrichment_requests.tmdb_language IS 'TMDB 返回语言（zh-CN/en-US 等）';
COMMENT ON COLUMN tmdb.enrichment_requests.duration_ms IS '本次 enrichment 总耗时（毫秒）';
COMMENT ON COLUMN tmdb.enrichment_requests.created_at IS '创建时间';

CREATE INDEX IF NOT EXISTS idx_tmdb_enrich_req_created
ON tmdb.enrichment_requests(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tmdb_enrich_req_user
ON tmdb.enrichment_requests(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tmdb_enrich_req_selected
ON tmdb.enrichment_requests(selected_media_type, selected_tmdb_id);
```

### 4.6 tmdb.neo4j_etl_outbox（增量 ETL 出站队列）

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

COMMENT ON TABLE tmdb.neo4j_etl_outbox IS 'Postgres -> Neo4j 增量 ETL Outbox（仅当 raw_hash 变化时入队）';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.id IS '主键 UUID';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.entity_type IS '实体类型：movie/person/tv';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.tmdb_id IS '实体 TMDB ID';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.raw_hash IS '对应实体 raw_hash（用于去重与幂等）';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.action IS '动作：upsert/delete';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.request_id IS '触发该 outbox 的 request_id（可为空）';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.enqueued_at IS '入队时间';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.locked_at IS 'worker 加锁时间（并发控制）';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.attempts IS '尝试次数';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.last_attempt_at IS '最后一次尝试时间';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.last_error IS '最后一次错误摘要';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.processed_at IS '处理完成时间（非空表示已完成）';

CREATE INDEX IF NOT EXISTS idx_tmdb_etl_outbox_pending
ON tmdb.neo4j_etl_outbox(processed_at, enqueued_at);

CREATE INDEX IF NOT EXISTS idx_tmdb_etl_outbox_entity
ON tmdb.neo4j_etl_outbox(entity_type, tmdb_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_tmdb_etl_outbox_dedupe
ON tmdb.neo4j_etl_outbox(entity_type, tmdb_id, raw_hash, action);
```

---

## 5. 可选表（非 MVP 必需，但强烈建议保留入口）

如果你们要做多语言/更强的离线分析，建议在“下一阶段”启用：
- `tmdb.movie_translations` / `tmdb.person_translations` / `tmdb.tv_translations`
  - 用于保存 `en-US` 或其它语言的翻译快照（而不是把 fallback 合并进 zh-CN raw）
- `tmdb.enrichment_request_entities`
  - 用于把一次请求关联到多个实体（候选/选中/分数），便于统计与评估

---

## 6. 最小 MVP 的落地顺序（建议）

1) 先确保 enrichment 写入：movies/people/tv_shows + enrichment_requests + neo4j_etl_outbox
2) 评估数据量与增长：按 `last_seen_at`/`created_at` 设置清理策略（尤其是 enrichment_requests）
3) 再做 ETL worker：消费 neo4j_etl_outbox，把 raw 转成 Neo4j node/edge
4) 最后再补 translations / images / external_ids 等（按业务需求）

