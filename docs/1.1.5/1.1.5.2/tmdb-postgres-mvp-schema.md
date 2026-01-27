# TMDB -> Postgres 最小 MVP 表模型（电影域，面向列表展示）

目标：用最小的表与字段集合，把 TMDB 查询时增强（Query-time Enrichment）过程中获取到的“基础事实数据”沉淀到 PostgreSQL，作为后续：
- 离线清洗 / 纠错 / 质量评估
- Postgres -> Neo4j 增量 ETL（Source of Truth）
- 复用 TMDB 数据减少重复请求（可选）

本文是“最小 MVP”版本：优先覆盖“电影列表展示/详情页”所需的结构化数据（movies + people + credits + genres），并保留最小的请求日志与 ETL outbox。

相关文档：
- TMDB 端点参考：`docs/1.1.5/1.1.5.2/tmdb-api-reference.md`
- 更完整的持久化方案草案：`docs/1.1.5/1.1.5.2/tmdb-postgres-persistence.md`（如果你们要保留 translations/更多实体）
- 代码现状（运行时自举 schema）：`backend/infrastructure/persistence/postgres/tmdb_store.py`

---

## 1. MVP 设计原则（约束）

1) 面向 UI：Postgres 需要可查询的“结构化表”
- 仅存 JSON 快照不利于做“电影列表/筛选/排序/分页”；MVP 必须有可索引的列（title/year/rating/popularity/poster_path 等）。
- 关系表不是为了“做图算法”，而是为了 UI 的常见查询：导演是谁、主演有哪些、类型是什么。

2) 保留原始 raw，但不要把 raw 当主查询模型
- raw 更适合作为“可回放/可追溯”的原始证据（debug/ETL 兜底），不应成为页面展示的唯一数据源。
- 建议单独表 `tmdb.raw_payloads` 存 TMDB 原始返回（按 entity_type/id/language/hash），结构化表只存常用字段与可索引字段。

3) 幂等主键：TMDB ID
- `tmdb.movies.tmdb_id` / `tmdb.people.tmdb_id` 作为主键。
- 关系表使用复合主键（movie_id + person_id + role/job/order 等），并支持“整片刷新”（先删后插）以简化写入逻辑。

4) 增量：content_hash 作为“内容变更检测”
- 建议在结构化实体表上保留 `content_hash`（来自 raw 的稳定 hash），仅当 hash 变化时写入 `neo4j_etl_outbox`。

5) 允许 stub（占位）
- 允许只写 movie_id/title 的占位行，后续再补全 overview/credits/genres 等。

---

## 2. MVP 覆盖的 TMDB 调用与落库映射

运行时（enrichment）常见链路：

1) 对象解析/消歧
- `GET /search/multi`
- 落库：`tmdb.enrichment_requests.multi_results_raw`（可选但推荐，便于回放/评估）

2) 详情（结构化入库）
- `GET /movie/{id}?append_to_response=credits`
  - `tmdb.movies`（title/overview/release_date/runtime/poster_path/vote_average/...）
  - `tmdb.movie_cast` / `tmdb.movie_crew`（导演/演员等）
  - `tmdb.genres` / `tmdb.movie_genres`（类型）
  - 同时可写 `tmdb.raw_payloads`（movie 快照，用于回放/ETL 兜底）
- （可选）`GET /person/{id}?append_to_response=combined_credits`
  - `tmdb.people`（name/biography/profile_path/...）
  - person 的作品清单在 MVP 中不做“关系落库”（避免表爆炸），只存 raw_payloads + 需要时由 ETL/Neo4j 处理
  - 如果你们需要“人物详情页/作品列表”，下一阶段再加 `tmdb.person_credits_*` 之类表

3) 推荐/筛选候选集合（可选）
- `GET /discover/movie` / `GET /discover/tv`
- 落库：`tmdb.enrichment_requests.discover_results_raw`（可选但推荐，便于回放/评估）

---

## 3. Schema 约定

- 统一 schema：`tmdb`
- 时间：`timestamptz`
- 原始快照：`jsonb`（放到 `tmdb.raw_payloads` 与 `tmdb.enrichment_requests`）
- Hash：`content_hash`（建议 SHA-256，对 raw 做稳定序列化后计算）

---

## 4. 最小 MVP DDL（含字段注释）

说明：
- 以下 DDL 是“推荐的最小集合”；生产环境建议用 migration 管理。
- 目前代码 `backend/infrastructure/persistence/postgres/tmdb_store.py` 仍偏“快照落库”，与本文的“结构化模型”存在差异；若采用本文模型，需要同步调整持久化实现（后续再做）。

### 4.1 Schema 与扩展

```sql
CREATE SCHEMA IF NOT EXISTS tmdb;

-- 仅当你需要 gen_random_uuid()（日志/outbox 用）：
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

### 4.2 tmdb.raw_payloads（原始快照存档，可回放）

```sql
CREATE TABLE IF NOT EXISTS tmdb.raw_payloads (
  entity_type    text NOT NULL CHECK (entity_type IN ('movie','person','tv')),
  tmdb_id        int  NOT NULL,
  language       text NOT NULL DEFAULT 'zh-CN',
  payload        jsonb NOT NULL,
  payload_hash   text NOT NULL,
  fetched_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (entity_type, tmdb_id, language, payload_hash)
);

COMMENT ON TABLE tmdb.raw_payloads IS 'TMDB 原始返回存档（用于回放/ETL 兜底）；主查询请走结构化表';
COMMENT ON COLUMN tmdb.raw_payloads.entity_type IS '实体类型：movie/person/tv';
COMMENT ON COLUMN tmdb.raw_payloads.tmdb_id IS 'TMDB 实体 ID';
COMMENT ON COLUMN tmdb.raw_payloads.language IS '返回语言（zh-CN/en-US 等）';
COMMENT ON COLUMN tmdb.raw_payloads.payload IS '原始 JSONB（整包存）';
COMMENT ON COLUMN tmdb.raw_payloads.payload_hash IS 'payload 稳定 hash（SHA-256），用于去重与变更检测';
COMMENT ON COLUMN tmdb.raw_payloads.fetched_at IS '拉取时间';
```

### 4.3 tmdb.movies（电影信息，面向列表/详情查询）

```sql
CREATE TABLE IF NOT EXISTS tmdb.movies (
  tmdb_id            int PRIMARY KEY,
  title              text,
  original_title     text,
  overview           text,
  original_language  text,
  release_date       date,
  runtime            int,
  poster_path        text,
  backdrop_path      text,
  popularity         double precision,
  vote_average       double precision,
  vote_count         int,
  data_state         text NOT NULL DEFAULT 'full' CHECK (data_state IN ('stub','full')),
  content_hash       text,
  fetched_at         timestamptz NOT NULL DEFAULT now(),
  first_seen_at      timestamptz NOT NULL DEFAULT now(),
  last_seen_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_tmdb_movies_state
    CHECK (
      (data_state = 'stub')
      OR
      (data_state = 'full' AND content_hash IS NOT NULL)
    )
);

COMMENT ON TABLE tmdb.movies IS 'TMDB 电影信息（结构化列用于列表/筛选/排序；导演/演员/类型在关系表中）';
COMMENT ON COLUMN tmdb.movies.tmdb_id IS 'TMDB movie_id（主键，幂等）';
COMMENT ON COLUMN tmdb.movies.title IS '中文标题（来自 TMDB title，可能为空）';
COMMENT ON COLUMN tmdb.movies.original_title IS '原始标题（original_title）';
COMMENT ON COLUMN tmdb.movies.overview IS '简介（overview，可能较长）';
COMMENT ON COLUMN tmdb.movies.original_language IS '原始语言（original_language）';
COMMENT ON COLUMN tmdb.movies.release_date IS '上映日期（release_date）';
COMMENT ON COLUMN tmdb.movies.runtime IS '片长（分钟，runtime）';
COMMENT ON COLUMN tmdb.movies.poster_path IS '海报路径（poster_path，需配合 TMDB configuration 拼 URL）';
COMMENT ON COLUMN tmdb.movies.backdrop_path IS '背景图路径（backdrop_path）';
COMMENT ON COLUMN tmdb.movies.popularity IS 'TMDB popularity（用于排序/消歧参考）';
COMMENT ON COLUMN tmdb.movies.vote_average IS 'TMDB vote_average（评分均值）';
COMMENT ON COLUMN tmdb.movies.vote_count IS 'TMDB vote_count（评分数）';
COMMENT ON COLUMN tmdb.movies.data_state IS '数据状态：stub=占位无 raw；full=有 raw 快照';
COMMENT ON COLUMN tmdb.movies.content_hash IS '内容 hash（来自 raw_payload 的稳定 hash）；用于增量 ETL 变更检测';
COMMENT ON COLUMN tmdb.movies.fetched_at IS '本次 raw 拉取时间（最后一次 fetch）';
COMMENT ON COLUMN tmdb.movies.first_seen_at IS '首次入库时间';
COMMENT ON COLUMN tmdb.movies.last_seen_at IS '最近一次被查询/命中时间（用于冷热/清理策略）';

CREATE INDEX IF NOT EXISTS idx_tmdb_movies_release_date
ON tmdb.movies(release_date DESC);

CREATE INDEX IF NOT EXISTS idx_tmdb_movies_last_seen
ON tmdb.movies(last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_tmdb_movies_popularity
ON tmdb.movies(popularity DESC);

CREATE INDEX IF NOT EXISTS idx_tmdb_movies_vote_average
ON tmdb.movies(vote_average DESC);
```

### 4.4 tmdb.people（人物信息）

```sql
CREATE TABLE IF NOT EXISTS tmdb.people (
  tmdb_id               int PRIMARY KEY,
  name                  text,
  original_name         text,
  known_for_department  text,
  biography             text,
  profile_path          text,
  popularity            double precision,
  data_state            text NOT NULL DEFAULT 'full' CHECK (data_state IN ('stub','full')),
  content_hash          text,
  fetched_at            timestamptz NOT NULL DEFAULT now(),
  first_seen_at         timestamptz NOT NULL DEFAULT now(),
  last_seen_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_tmdb_people_state
    CHECK (
      (data_state = 'stub')
      OR
      (data_state = 'full' AND content_hash IS NOT NULL)
    )
);

COMMENT ON TABLE tmdb.people IS 'TMDB 人物信息（结构化列用于人物详情与消歧；作品列表关系可由 Neo4j/ETL 承担）';
COMMENT ON COLUMN tmdb.people.tmdb_id IS 'TMDB person_id（主键，幂等）';
COMMENT ON COLUMN tmdb.people.name IS '中文姓名（name）';
COMMENT ON COLUMN tmdb.people.original_name IS '原始姓名（original_name）';
COMMENT ON COLUMN tmdb.people.known_for_department IS '部门（Acting/Directing 等）';
COMMENT ON COLUMN tmdb.people.biography IS '人物简介（biography，可能较长）';
COMMENT ON COLUMN tmdb.people.profile_path IS '头像路径（profile_path）';
COMMENT ON COLUMN tmdb.people.popularity IS 'TMDB popularity（用于排序/消歧参考）';
COMMENT ON COLUMN tmdb.people.data_state IS '数据状态：stub/full';
COMMENT ON COLUMN tmdb.people.content_hash IS '内容 hash（来自 raw_payload 的稳定 hash）';
COMMENT ON COLUMN tmdb.people.fetched_at IS '本次 raw 拉取时间';
COMMENT ON COLUMN tmdb.people.first_seen_at IS '首次入库时间';
COMMENT ON COLUMN tmdb.people.last_seen_at IS '最近一次命中时间';

CREATE INDEX IF NOT EXISTS idx_tmdb_people_last_seen
ON tmdb.people(last_seen_at DESC);
```

### 4.5 tmdb.genres 与 tmdb.movie_genres（类型）

```sql
CREATE TABLE IF NOT EXISTS tmdb.genres (
  tmdb_genre_id  int PRIMARY KEY,
  name           text NOT NULL,
  media_type     text NOT NULL DEFAULT 'movie' CHECK (media_type IN ('movie','tv')),
  created_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE tmdb.genres IS 'TMDB 类型字典（movie/tv）';
COMMENT ON COLUMN tmdb.genres.tmdb_genre_id IS 'TMDB genre_id（主键）';
COMMENT ON COLUMN tmdb.genres.name IS '类型名称（通常为中文，视 language 而定）';
COMMENT ON COLUMN tmdb.genres.media_type IS '类型归属：movie 或 tv';
COMMENT ON COLUMN tmdb.genres.created_at IS '创建时间';

CREATE TABLE IF NOT EXISTS tmdb.movie_genres (
  tmdb_movie_id  int NOT NULL REFERENCES tmdb.movies(tmdb_id) ON DELETE CASCADE,
  tmdb_genre_id  int NOT NULL REFERENCES tmdb.genres(tmdb_genre_id) ON DELETE RESTRICT,
  PRIMARY KEY (tmdb_movie_id, tmdb_genre_id)
);

COMMENT ON TABLE tmdb.movie_genres IS '电影与类型的关联表（用于列表过滤/展示类型）';
COMMENT ON COLUMN tmdb.movie_genres.tmdb_movie_id IS 'TMDB movie_id';
COMMENT ON COLUMN tmdb.movie_genres.tmdb_genre_id IS 'TMDB genre_id';
```

### 4.6 tmdb.movie_cast 与 tmdb.movie_crew（演职员）

```sql
CREATE TABLE IF NOT EXISTS tmdb.movie_cast (
  tmdb_movie_id  int NOT NULL REFERENCES tmdb.movies(tmdb_id) ON DELETE CASCADE,
  tmdb_person_id int NOT NULL REFERENCES tmdb.people(tmdb_id) ON DELETE RESTRICT,
  credit_id      text,
  cast_order     int,
  character      text,
  PRIMARY KEY (tmdb_movie_id, tmdb_person_id, COALESCE(credit_id,''))
);

COMMENT ON TABLE tmdb.movie_cast IS '电影演员表（来自 movie credits.cast）；用于主演列表展示';
COMMENT ON COLUMN tmdb.movie_cast.tmdb_movie_id IS 'TMDB movie_id';
COMMENT ON COLUMN tmdb.movie_cast.tmdb_person_id IS 'TMDB person_id';
COMMENT ON COLUMN tmdb.movie_cast.credit_id IS 'TMDB credit_id（可选，用于与 /credit/{credit_id} 对齐）';
COMMENT ON COLUMN tmdb.movie_cast.cast_order IS '出演排序（order）';
COMMENT ON COLUMN tmdb.movie_cast.character IS '角色名';

CREATE INDEX IF NOT EXISTS idx_tmdb_movie_cast_movie
ON tmdb.movie_cast(tmdb_movie_id, cast_order);

CREATE TABLE IF NOT EXISTS tmdb.movie_crew (
  tmdb_movie_id  int NOT NULL REFERENCES tmdb.movies(tmdb_id) ON DELETE CASCADE,
  tmdb_person_id int NOT NULL REFERENCES tmdb.people(tmdb_id) ON DELETE RESTRICT,
  credit_id      text,
  department     text,
  job            text,
  PRIMARY KEY (tmdb_movie_id, tmdb_person_id, COALESCE(credit_id,''), COALESCE(job,''))
);

COMMENT ON TABLE tmdb.movie_crew IS '电影剧组表（来自 movie credits.crew）；导演通常 job=Director';
COMMENT ON COLUMN tmdb.movie_crew.tmdb_movie_id IS 'TMDB movie_id';
COMMENT ON COLUMN tmdb.movie_crew.tmdb_person_id IS 'TMDB person_id';
COMMENT ON COLUMN tmdb.movie_crew.credit_id IS 'TMDB credit_id（可选）';
COMMENT ON COLUMN tmdb.movie_crew.department IS '部门（Directing/Writing 等）';
COMMENT ON COLUMN tmdb.movie_crew.job IS '职位（Director/Writer/Producer 等）';

CREATE INDEX IF NOT EXISTS idx_tmdb_movie_crew_movie
ON tmdb.movie_crew(tmdb_movie_id);

CREATE INDEX IF NOT EXISTS idx_tmdb_movie_directors
ON tmdb.movie_crew(tmdb_movie_id)
WHERE job = 'Director';
```

### 4.7 tmdb.enrichment_requests（请求日志：可观测/回放）

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
  content_hash    text NOT NULL,
  action          text NOT NULL DEFAULT 'upsert' CHECK (action IN ('upsert','delete')),
  request_id      text,
  enqueued_at     timestamptz NOT NULL DEFAULT now(),
  locked_at       timestamptz,
  attempts        int NOT NULL DEFAULT 0,
  last_attempt_at timestamptz,
  last_error      text,
  processed_at    timestamptz
);

COMMENT ON TABLE tmdb.neo4j_etl_outbox IS 'Postgres -> Neo4j 增量 ETL Outbox（仅当 content_hash 变化时入队）';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.id IS '主键 UUID';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.entity_type IS '实体类型：movie/person/tv';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.tmdb_id IS '实体 TMDB ID';
COMMENT ON COLUMN tmdb.neo4j_etl_outbox.content_hash IS '对应实体 content_hash（用于去重与幂等）';
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
ON tmdb.neo4j_etl_outbox(entity_type, tmdb_id, content_hash, action);
```

---

## 5. 可选表（非 MVP 必需，但强烈建议保留入口）

如果你们要做更完整的页面展示或离线分析，建议在“下一阶段”启用：
- `tmdb.movie_images` / `tmdb.person_images`：海报/头像缓存（或仅存 file_path）
- `tmdb.movie_external_ids` / `tmdb.person_external_ids`：IMDb/Wikidata 对齐
- `tmdb.movie_keywords` / `tmdb.keywords`：主题标签
- `tmdb.movie_translations`：多语言标题/简介（用于语言回退）
- `tmdb.person_tagged_images`：人物 tagged images（如果做图库）

---

## 6. 最小 MVP 的落地顺序（建议）

1) 先确保 enrichment 写入结构化表：movies + people + movie_cast/movie_crew + genres/movie_genres
2) 请求日志：enrichment_requests（便于回放/评估；按 created_at 设置清理）
3) 原始快照：raw_payloads（可选但推荐，便于 ETL 兜底与数据纠错）
4) 再做 ETL worker：消费 neo4j_etl_outbox，把结构化表/或 raw_payloads 转成 Neo4j node/edge
5) 最后再补 images/external_ids/keywords 等（按产品需求）

---

## 7. 全站“全量 + 持续同步”怎么做（MVP 之外，但必须提前知道）

重要结论：TMDB API v3 **没有**“一次返回全站所有电影 ID”的 JSON API。
如果目标是“全站所有电影”，推荐走 TMDB 官方的 **Daily ID Exports**（文件下载）作为全量 ID 来源，再用详情接口补全入库。

### 7.1 全量初始化（一次性 backfill）

1) 下载当日全量 movie id 列表（gzip 文件）
- 官方文档：`https://developer.themoviedb.org/docs/daily-id-exports`
- 文件名形如：`movie_ids_YYYY_MM_DD.json.gz`

2) 解压后逐行读取（通常是 JSON Lines）
- 取每行的 `id` 作为 `tmdb_id`

3) 对每个 `tmdb_id` 拉取详情并入库（含 credits 以落 movie_cast/movie_crew）
- `GET /movie/{movie_id}?append_to_response=credits&language=zh-CN`
- 失败容错：部分条目可能 404/不可用；记录错误并跳过（不要让任务中断）

4) 写入 `tmdb.raw_payloads`（可选但推荐）
- 便于后续重建/纠错，以及 ETL 兜底

### 7.2 持续同步（每天增量）

建议组合两类信号：

1) 每日 Export（全量 id 快照）
- 作用：确保不会漏掉新增的 movie id（尤其是 API discover 难以覆盖的边角数据）
- 用法：每天下载当天 export，做一次“ID 集合对比”
  - 新增 id：补拉详情并 upsert
  - 已存在 id：可选择不动（避免全量刷新成本）

2) `/movie/changes`（变更列表）
- 作用：只更新“发生过变更”的 id，显著降低刷新成本
- 用法：每天以 `start_date/end_date` 拉取变更 id 列表 → 对这些 id 补拉详情并更新
- 注意：changes 返回的是“id 列表 + 变更时间”等概要信息，仍需调用 `/movie/{id}` 拿到最新字段

### 7.3 为什么要两者结合

- 仅用 changes：可能漏掉“新增但未被正确纳入变更窗口”的边缘情况（取决于 TMDB 的变更语义与窗口限制）
- 仅用 export：每天全量对比/刷新成本更高
- 组合方案：export 用于发现新增，changes 用于更新存量
