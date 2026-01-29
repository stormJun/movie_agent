# 微信小程序后端实现说明（MVP）

约束：
- 小程序后端接口实现必须写在本仓库 `backend/` 下（FastAPI 路由在 `backend/server/`）
- 为与现有 Web（React）接口隔离，新增小程序专用前缀：`/api/v1/mp/*`

相关文档：
- 产品文档：`docs/miniprogram/1.0/product-design.md`
- 前端文档：`docs/miniprogram/1.0/frontend-implementation.md`
- UI 规格：`docs/miniprogram/1.0/ui-design.md`
- TMDB API 参考：`docs/1.1.5/1.1.5.2/tmdb-api-reference.md`
- Postgres（MVP）建模：`docs/1.1.5/1.1.5.2/tmdb-postgres-mvp-schema.md`

---

## 1. 复用现有聊天主链路（不要再写一套）

原则：小程序只是“新的客户端”，后端继续复用现有 GraphRAG/LangGraph/Enrichment 全链路，不复制业务逻辑。

现有可复用入口：
- Web 流式聊天（SSE）：`backend/server/api/rest/v1/chat_stream.py` → `StreamHandler.handle(...)`
- Web 非流式聊天：`backend/server/api/rest/v1/chat.py` → `ChatHandler.handle(...)`
- enrichment：`backend/infrastructure/enrichment/*`
- Debug：`backend/infrastructure/debug/*` + `/api/v1/debug/*`

推荐做法：新增 `mp` 路由作为“薄包装”（内部调用同一个 handler）。

---

## 2. 小程序流式协议适配（status -> type）

问题：
- 现有 Web SSE 输出是 `{ "status": "...", "content": ... }`
- 小程序参考工程的 stream controller 按 `{ "type": "chunk|complete|..." }` 分发（更贴近 UI）

方案：
- `POST /api/v1/mp/chat/stream` 内部仍调用 `StreamHandler.handle(...)`
- 仅在对外 SSE 输出时做字段映射（不改变核心逻辑）：
  - `status=start` → `{ "type": "generate_start", "content": { "request_id": "..." } }`
  - `status=token` → `{ "type": "chunk", "content": "..." }`
  - `status=done` → `{ "type": "complete", "content": null, "answer": "（可选最终全文）" }`
  - `status=error` → `{ "type": "error", "content": { "message": "..." } }`
  - 其它状态：按需透传或归一到 `type=text`

备注：
- 这层映射能让小程序端直接复用参考工程的 `StreamHttpClient + controller`，避免改前端分发逻辑。

---

## 3. 小程序后端 API（MVP）

### 3.1 Chat（流式）

- `POST /api/v1/mp/chat/stream`
  - SSE：`Content-Type: text/event-stream`
  - 帧协议：见 `docs/miniprogram/1.0/frontend-implementation.md`（`type` 帧）
  - headers（建议）：
    - `Cache-Control: no-cache`
    - `Connection: keep-alive`
    - `X-Accel-Buffering: no`（如果有 Nginx）

请求体（建议与现有 ChatRequest 对齐，MVP 必填/可选）：
- 必填：`message`, `user_id`, `session_id`, `kb_prefix`
- 可选：`debug`, `incognito`, `watchlist_auto_capture`
- 建议约束：小程序侧不暴露 `agent_type` 选择（由 router 决策）

### 3.2 电影查询（用于列表/详情）

1) 批量查询（从 recommendations 渲染卡片）
- `POST /api/v1/mp/movies/bulk`
  - body: `{ "ids": [603, 27205, ...] }`
  - resp: `{ "items": [MovieCard...] }`

2) 列表 feed（热门/近期，作为空状态/默认推荐）
- `GET /api/v1/mp/movies/feed?type=popular|now_playing|upcoming&limit=50&offset=0`

3) 详情
- `GET /api/v1/mp/movies/{tmdb_id}`

MovieCard / MovieDetail 字段建议与产品/前端文档保持一致。

MovieCard 建议最小字段（足够渲染卡片）：
- `tmdb_id`, `title`, `release_date`(或 `year`), `poster_url`
- `vote_average`, `vote_count`
- `directors[]`（最多 1~2）
- `top_cast[]`（最多 3~5）

MovieDetail 建议最小字段：
- MovieCard 全部字段
- `overview`, `runtime`, `genres[]`
- `crew[]`（可只返回导演/编剧等关键岗位）
- `cast[]`（可限制数量）

实现注意（MVP）：`tmdb.movies.raw` 已包含 `credits`（详情调用 append credits），所以 directors/top_cast 可以从 raw 中提取，无需单独关系表。

### 3.3 API 契约与示例（工程师可直接对接）

统一约定：
- `tmdb_id`：int
- `poster_url`/`backdrop_url`：由后端拼好（前端直接用；避免前端重复拼接/版本不一致）
- 时间：ISO8601 字符串（例如 `2024-03-01`）；若缺失则为 `null`
- 返回顺序：保持输入顺序（bulk）或稳定排序（feed）

#### 3.3.1 POST /api/v1/mp/movies/bulk

用途：根据 recommendations 的 id 列表拉取卡片数据。

Request:
```json
{ "ids": [603, 27205, 13] }
```

Response:
```json
{
  "items": [
    {
      "tmdb_id": 603,
      "title": "The Matrix",
      "release_date": "1999-03-31",
      "year": 1999,
      "poster_url": "https://image.tmdb.org/t/p/w500/....jpg",
      "vote_average": 8.2,
      "vote_count": 24000,
      "directors": ["Lana Wachowski", "Lilly Wachowski"],
      "top_cast": ["Keanu Reeves", "Laurence Fishburne", "Carrie-Anne Moss"]
    }
  ],
  "missing_ids": [13]
}
```

规则（MVP 默认）：
- `items` 按请求 `ids` 的顺序返回（不排序）；不存在的 id 放入 `missing_ids`
- 对 `ids` 先去重，但保持第一次出现的顺序（避免重复卡片）
- 若 TMDB 可用且允许“缺失补齐”（见 3.4），后端可尝试补齐 missing 并返回（仍建议返回 `missing_ids` 便于观测）

#### 3.3.2 GET /api/v1/mp/movies/{tmdb_id}

用途：详情页。

Response:
```json
{
  "movie": {
    "tmdb_id": 603,
    "title": "The Matrix",
    "original_title": "The Matrix",
    "release_date": "1999-03-31",
    "year": 1999,
    "runtime": 136,
    "overview": "....",
    "poster_url": "https://image.tmdb.org/t/p/w500/....jpg",
    "backdrop_url": "https://image.tmdb.org/t/p/w780/....jpg",
    "vote_average": 8.2,
    "vote_count": 24000,
    "genres": ["Action", "Sci-Fi"],
    "directors": ["Lana Wachowski", "Lilly Wachowski"],
    "top_cast": ["Keanu Reeves", "Laurence Fishburne", "Carrie-Anne Moss"],
    "cast": [
      { "name": "Keanu Reeves", "character": "Neo" }
    ],
    "crew": [
      { "name": "Lana Wachowski", "job": "Director" }
    ]
  }
}
```

#### 3.3.3 GET /api/v1/mp/movies/feed

用途：空状态/默认推荐列表。

Query:
- `type`: `popular|now_playing|upcoming`
- `limit`: int（默认 20，最大 50）
- `offset`: int（默认 0）

Response:
```json
{
  "items": [ { "tmdb_id": 603, "title": "...", "poster_url": "...", "year": 1999 } ],
  "next_offset": 20
}
```

规则（MVP 默认）：
- 优先从 Postgres（`tmdb.movies`）按 `popularity DESC, tmdb_id ASC` 做稳定排序
- 若本地为空且允许“缺失补齐”（见 3.4），可触发一次 TMDB 刷新再返回；否则返回空数组

#### 3.3.4 POST /api/v1/mp/chat/stream（SSE）

返回帧：`data: {json}\n\n`

最小帧序列示例（含推荐）：
```text
data: {"type":"generate_start","content":{"request_id":"c2b7..."}}

data: {"type":"chunk","content":"给你推荐几部近期热门的电影："}

data: {"type":"chunk","content":"\\n1. ..."}

data: {"type":"recommendations","content":{"tmdb_ids":[603,27205,157336],"title":"为你推荐（近期热门）","mode":"movie_popular"}}

data: {"type":"complete","content":null,"answer":"（可选最终全文）"}
```

心跳（keep-alive）：
- 现有 Web 实现使用 SSE comment 帧：`: ping\n\n`（不是 `data:`）
- 小程序端 SSE 解析器默认忽略注释行（safe），但能帮助中间代理不超时断开

status->type 映射（mp 路由做）：
- `status=start` -> `type=generate_start`
- `status=token` -> `type=chunk`
- `status=done` -> `type=complete`
- `status=error` -> `type=error`
 - 其它 status（例如 progress/execution_log）：MVP 可丢弃或仅在 debug=true 时映射为 `type=debug`

### 3.4 “库里没有数据”时的策略（必须落锤，MVP 建议）

目标：保证“推荐卡片/详情页”尽量不空，同时遵守“入库作为基础数据”的设计。

建议默认策略（MVP）：
- movies/detail & movies/bulk：
  - 若 Postgres 没有该 `tmdb_id`：
    1) 若 TMDB 配置可用（`TMDB_API_TOKEN|TMDB_API_KEY`）且 `ENRICHMENT_ENABLE=true`：
       - 同步调用 TMDB `GET /movie/{id}?append_to_response=credits&language=zh-CN`
       - best-effort 写入 Postgres（复用 `PostgresTmdbStore.persist_enrichment` 或新增一个 upsert helper）
       - 返回补齐后的数据
    2) 否则返回 404，并给出可读错误：`"movie_not_found_in_db"`
- movies/feed：
  - 若本地为空：
    - 返回空列表，并在日志提示“需要跑 seed/refresh”（见 4.0 Path B）

备注：
- 以上“同步补齐”建议加并发/超时控制（避免 bulk 一次拉太多导致阻塞）

---

## 4. TMDB enrichment：从 TMDB 到 Postgres（现状代码如何写入）

### 4.0 数据来源与刷新策略（MVP）

MVP 优先用“官方榜单 + 近期”作为可展示的数据池（避免全量抓取成本）：
- `/movie/popular`
- `/movie/now_playing`
- `/movie/upcoming`
- （可选）`/discover/movie`（近两年切片兜底）

对列表候选中的每个 `movie_id`，用详情补齐关键字段（包含 credits）：
- `/movie/{id}?append_to_response=credits&language=zh-CN`

刷新频率建议：
- 定时任务：每天/每小时刷新榜单前 N 页（例如 popular 10 页、now_playing 5 页、upcoming 5 页）
- 对新增/变化的 `movie_id` 拉详情并 upsert
- 容错：详情 404/不可用要记录并跳过

MVP 落地建议（保证“详情页可查”）：
- 路径 A（最省）：先不做离线刷新；仅在聊天触发 enrichment 时写入 tmdb.movies（用户问到/推荐到才入库）
- 路径 B（更产品）：加一个定时任务/命令行脚本，定期拉热门/近期，把 tmdb.movies 填起来（详情页打开更稳定）
  - 两者可同时存在：离线任务做底库，enrichment 做增量补齐/修正

实现要求（为工程师落地留出明确接口）：
- 建议新增一个可重复执行的 seed/refresh 模块（命令行）：
  - 模块位置建议：`backend/infrastructure/integrations/tmdb_seed/main.py`
  - 运行方式：`bash scripts/py.sh infrastructure.integrations.tmdb_seed.main --help`
  - MVP 参数建议：
    - `--type popular|now_playing|upcoming`（可多次跑）
    - `--pages 5`（每类拉前 N 页）
    - `--language zh-CN`
    - `--concurrency 8`
    - `--dry-run`（可选）
- seed 的写入复用现有 store：
  - 对每个 movie_id 调 `TMDBClient.get_movie_details(... append_to_response=credits)`
  - 组装为 payload `{ "type":"movie","data": details }` 后调用 `PostgresTmdbStore.persist_enrichment(...)`
    - `user_id/session_id/request_id` 可用固定值（例如 `seed`），便于审计

### 4.1 触发与调用链

触发点（聊天链路）：
- `backend/server/api/rest/v1/chat_stream.py` → `StreamHandler.handle(...)` → 图执行过程中触发 enrichment
  - 条件：`kb_prefix=movie` 且 `ENRICHMENT_ENABLE=true`

编排：
- `backend/infrastructure/enrichment/tmdb_enrichment_service.py:TMDBEnrichmentService.enrich_query`

TMDB 调用与 payload 形态（简化）：
- 解析/消歧：`TMDBClient.resolve_entity_via_multi(...)`（/search/multi）
- 推荐：`TMDBClient.discover_movie_raw(...)` / `discover_tv_raw(...)`（/discover/movie|tv）+ 详情补齐
- 详情（电影会带 credits）：`TMDBClient.get_movie_details(... append_to_response="credits")`
- 最终 payloads：`[{ "type": "movie|person|tv", "data": { ...TMDB details payload... } }, ...]`

### 4.2 写入行为（best-effort，不影响聊天响应）

写入入口：
- `TMDBEnrichmentService._maybe_persist(...)` 组装 job
  -（可配置异步队列）→
- `backend/infrastructure/persistence/postgres/tmdb_store.py:PostgresTmdbStore.persist_enrichment(...)`

### 4.3 写到哪些表里（现状）

1) 实体快照（“查询列 + raw JSON”混合）
- `tmdb.movies`（电影；`raw` 包含 `credits` 等完整 payload）
- `tmdb.people`（人物）
- `tmdb.tv_shows`（电视剧/综艺，若走 TV enrichment）

2) 请求日志（可观测/排障）
- `tmdb.enrichment_requests`：记录 query、消歧候选、raw 搜索/推荐结果等
- `tmdb.enrichment_request_entities`：本次请求关联到的实体（selected/score）

3) Neo4j ETL 出站任务
- `tmdb.neo4j_etl_outbox`
  - 当 `raw_hash` 发生变化（或首次写入）会 enqueue `upsert`
  - 后续可由 ETL worker 做 Postgres→Neo4j 同步（不属于本 MVP 必需，但表已准备）

说明：
- cast/crew/genre 的“强关系表”当前未落地；MVP 页面展示导演/主演建议直接从 `tmdb.movies.raw.credits`
  提取（因为详情调用已经 append 了 credits）。

---

## 5. 代码落点建议（便于实现者快速开工）

建议新增/修改的位置（仅建议，不要求完全一致）：

1) mp 路由
- 新增：`backend/server/api/rest/v1/mp_chat_stream.py`
  - 复用：`get_stream_handler` + `StreamHandler.handle(...)`
  - 处理：SSE 输出做 `status -> type` 映射
- 新增：`backend/server/api/rest/v1/mp_movies.py`
  - 查询 Postgres（`tmdb.movies`）并组装 MovieCard/MovieDetail

并注册到 API 聚合路由：
- 修改：`backend/server/api_router.py`
  - `import server.api.rest.v1.mp_chat_stream as mp_chat_stream_v1`
  - `import server.api.rest.v1.mp_movies as mp_movies_v1`
  - `api_router.include_router(mp_chat_stream_v1.router)`
  - `api_router.include_router(mp_movies_v1.router)`

2) schemas（小程序专用响应可以复用现有 schemas，也可以新增 mp 前缀 schema）
- `backend/server/models/schemas.py`（或新文件）：
  - `MpChatRequest`（可直接复用 `ChatRequest`）
  - `MovieCard`, `MovieDetail`, `MpMoviesBulkRequest`

3) DB 读取
- 优先：直接从 `tmdb.movies` 读
  - `title/release_date/vote_*` 直接来自列
  - `poster_path/backdrop_path/genres/credits` 从 `raw` JSON 取

DB 连接（建议统一用项目内 helper）：
- DSN 获取：`backend/infrastructure/config/database.py:get_postgres_dsn`
- 如果 DSN 未配置：movies/feed/bulk/detail 建议返回空/404，并在日志提示“需要配置 Postgres”

---

## 6. 运行与配置（MVP 必需项）

必需环境变量（示例名以现有项目为准）：
- Postgres：`POSTGRES_DSN`（或项目内对应 DSN 变量）
- SSE 心跳：`SSE_HEARTBEAT_S`（已有）
- TMDB：
  - `ENRICHMENT_ENABLE=true`
  - `TMDB_API_TOKEN` 或 `TMDB_API_KEY`

排障建议：
- 如果小程序端收不到 chunk：
  - 检查响应 header 是否包含 `X-Accel-Buffering: no`
  - 检查中间层是否把流式响应缓冲成整包（开发环境尽量直连）

---

## 7. 验收与联调（最小步骤，能跑通就算 MVP）

### 7.1 后端自测（curl）

1) 流式 chat（mp）
```bash
curl -N 'http://localhost:5174/api/v1/mp/chat/stream' \\
  -H 'Accept: text/event-stream' \\
  -H 'Content-Type: application/json' \\
  --data-raw '{"message":"推荐几部近期热门的电影","user_id":"u1","session_id":"s1","kb_prefix":"movie","debug":false}'
```
预期：能看到多条 `data:`，并包含 `type=chunk`，最后 `type=complete`。

2) bulk（没有数据也应返回结构正确）
```bash
curl 'http://localhost:5174/api/v1/mp/movies/bulk' \\
  -H 'Content-Type: application/json' \\
  --data-raw '{"ids":[603,27205]}'
```
预期：返回 `items` 数组 + `missing_ids` 数组（可能全 missing）。

3) 详情（若缺失且启用同步补齐，会触发 TMDB 拉取）
```bash
curl 'http://localhost:5174/api/v1/mp/movies/603'
```

### 7.2 小程序联调自测（开发者工具）

1) baseURL 指向本地后端（通过 env-switch 或配置）
2) Chat 页发送一句话，验证：
- 文本能流式增长（不是一次性出现）
- recommendations 出现后能渲染卡片 skeleton 并替换为真实卡片（bulk 成功）
3) 点击卡片进入详情页，验证：
- 详情 skeleton → 渲染真实内容
