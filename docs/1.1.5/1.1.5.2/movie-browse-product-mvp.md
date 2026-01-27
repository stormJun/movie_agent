# 电影列表与详情页（基于 TMDB 入库）的产品设计 MVP

目标：在“只有聊天页”的基础上，补齐一个最小的“电影浏览体验”：
- 用户在聊天里提出推荐/筛选问题（例如“推荐几部近期热门电影”）
- 大模型返回：分析文本（自然语言）+ 推荐电影的 `tmdb_id` 列表（机器可读）
- 前端根据 `tmdb_id` 拉取电影列表卡片（海报/标题/年份/评分/主演/导演），支持点击进入详情页

本设计只覆盖 Movie（电影）；TV/Person 可按同样模式扩展。

相关文档：
- TMDB 端点参考：`docs/1.1.5/1.1.5.2/tmdb-api-reference.md`
- Postgres 入库建模（MVP）：`docs/1.1.5/1.1.5.2/tmdb-postgres-mvp-schema.md`

---

## 1. 用户场景与产品目标

### 1.1 典型场景

1) 近期热门推荐
- 用户：“推荐几部近期热门的电影”
- 系统：给出 6~12 部，附带简短理由（类型/口碑/节奏/主题），并可一键查看列表与详情。

2) 条件筛选推荐（年份/地区/语言/类型）
- 用户：“推荐 2024 年的高分电影，最好是中文片”
- 系统：给出候选 + 可追问（如果条件不足）。

3) 追问某部电影
- 用户：“第 2 个讲什么？导演是谁？”
- 系统：基于详情页信息 + GraphRAG/Enrichment 补充回答。

### 1.2 MVP 成功标准（可验收）

- 聊天里能稳定拿到 `tmdb_id` 列表（机器可读，不靠解析自然语言）
- 前端能根据 `tmdb_id` 拉到结构化字段并展示列表
- 点击列表项能进入详情页（至少包含：海报、标题、年份、简介、导演、主演、评分）

---

## 2. 数据来源与刷新策略（MVP）

### 2.1 数据来源优先级

MVP 优先用“官方榜单 + 近期”作为可展示的数据池（避免全量抓取成本）：
- `/movie/popular`
- `/movie/now_playing`
- `/movie/upcoming`
- （可选）`/discover/movie`（近两年切片兜底）

对于列表候选中的每个 `movie_id`，统一用详情补齐：
- `/movie/{id}?append_to_response=credits&language=zh-CN`

### 2.2 入库表（对齐 tmdb-postgres-mvp-schema）

写入（结构化，用于页面查询）：
- `tmdb.movies`
- `tmdb.movie_cast`
- `tmdb.movie_crew`
- `tmdb.genres`
- `tmdb.movie_genres`

可选写入（用于回放/ETL兜底）：
- `tmdb.raw_payloads`
- `tmdb.enrichment_requests`

### 2.3 MVP 刷新频率建议

- 定时任务：每天/每小时刷新榜单前 N 页（例如 popular 10 页、now_playing 5 页、upcoming 5 页）
- 对新增/变化的 `movie_id` 拉详情并 upsert
- 容错：详情 404/不可用要记录并跳过

---

## 3. 交互设计（前端）

### 3.1 聊天页新增交互

在聊天消息下方新增一个“推荐结果卡片区”（Message attachment）：
- 标题：例如“为你推荐（近期热门）”
- 列表：电影卡片（poster + title + year + rating）
- “查看更多”：进入“电影列表页”（可选）

### 3.2 详情页形态（MVP）

两种实现都可（优先实现成本低者）：

1) 详情 Drawer（不跳路由）
- 点击电影卡片 → 右侧抽屉展示详情

2) 详情页面（跳路由）
- 路由：`/movies/:tmdbId`
- 支持分享链接（更产品化）

详情展示字段（MVP）：
- 海报/背景图
- 标题（含原始标题）
- 上映年份、片长、类型
- 评分（vote_average/vote_count）
- 导演（从 crew 取 job=Director）
- 主演（cast 前 N）
- 简介

### 3.3 图片 URL 拼接

MVP 可先用 TMDB 公共图片域名（避免先接 `/configuration`）：
- poster：`https://image.tmdb.org/t/p/w500{poster_path}`
- backdrop：`https://image.tmdb.org/t/p/w780{backdrop_path}`

后续再做：通过 `/configuration` 动态获取 base_url + sizes（更规范）。

---

## 4. 后端 API 设计（MVP）

目标：前端能基于 `tmdb_id` 拉列表与详情；聊天接口能返回“推荐 id”。

### 4.1 电影查询 API（面向前端）

1) 批量查询（用于从 chat 推荐 id 渲染卡片）
- `POST /api/v1/movies/bulk`
  - body: `{ "ids": [603, 27205, ...] }`
  - resp: `{ "items": [MovieCard...] }`

2) 列表 feed（热门/近期）
- `GET /api/v1/movies/feed?type=popular|now_playing|upcoming&limit=50&offset=0`
  - resp: `{ "items": [MovieCard...], "next_offset": 50 }`

3) 详情
- `GET /api/v1/movies/{tmdb_id}`
  - resp: `{ "movie": MovieDetail }`

MovieCard（建议字段）：
- `tmdb_id`
- `title`
- `release_date`（或 `year`）
- `poster_url`（后端拼好，前端直接用）
- `vote_average` / `vote_count`
- `directors[]`（可选，最多 1~2 个）
- `top_cast[]`（可选，最多 3~5 个）

MovieDetail（建议字段）：
- MovieCard 全部字段
- `overview`
- `runtime`
- `genres[]`
- `crew[]`（可简化：只返回导演/编剧等关键岗位）
- `cast[]`（可限制数量）

数据源：
- 直接查询 Postgres `tmdb.*` 表（来自入库任务）

### 4.2 聊天接口如何返回“推荐电影 id”（关键）

要求：必须机器可读，不能靠解析自然语言。

MVP 两种实现方式（选其一）：

A) SSE 事件（推荐）
- `/api/v1/chat/stream` 在生成完成后追加一个事件：
  - `{"status":"recommendations","content":{"tmdb_ids":[...],"title":"近期热门推荐","mode":"movie_popular"}}`
- 前端收到该事件后调用 `/api/v1/movies/bulk` 渲染卡片区

B) 非流式返回字段
- `/api/v1/chat` 的 JSON 响应里新增：
  - `recommendations: { tmdb_ids: [...], title: "...", mode: "..." }`

推荐 id 的来源（MVP 简化）：
- 当 router 判定 `query_intent=recommend` 且 `media_type_hint=movie`：
  - 优先使用 Postgres 已入库的 feed（popular/now_playing/upcoming）挑选 top N（可按 vote/popularity 排序）
  - 大模型只负责“解释与排序理由”，不负责“去 TMDB 拉数据”

备注：
- 若 Postgres 本地没有足够数据，再 fallback 到 TMDB `/discover/movie` 或 `/movie/popular`（并触发入库任务），但这属于 Phase 2。

---

## 5. 大模型输出约束（推荐的最小协议）

为了稳定拿到 `tmdb_id`，建议让生成阶段遵循一个轻量 JSON 协议（可用提示词约束或 function-call）：

```json
{
  "analysis": "……自然语言解释……",
  "recommendations": [
    { "tmdb_id": 603, "reason": "……" },
    { "tmdb_id": 27205, "reason": "……" }
  ]
}
```

前端展示：
- `analysis`：作为聊天正文（markdown）
- `recommendations[]`：用于渲染卡片区；`reason` 可作为卡片副标题

后端校验：
- tmdb_id 必须为 int
- 去重、限制数量（例如 12 条）
- 允许部分 id 在本地不存在：缺失的 id 可忽略或触发异步补齐（下一阶段）

---

## 6. 权限与隐私（MVP）

- 推荐 feed 与电影详情：公共数据，无需用户权限
- 与用户记忆/清单相关（watchlist、已看/不想看）属于后续增强；MVP 可先不做过滤

---

## 7. 分阶段实现建议

Phase 0（纯展示，最快上线）：
- 后端实现 movies/feed + movies/{id} + movies/bulk（查询 Postgres）
- 前端新增“推荐卡片区”与“详情 Drawer”

Phase 1（聊天联动）：
- `/chat/stream` 增加 `recommendations` 事件（或 `/chat` 增加 recommendations 字段）
- LLM 输出 JSON 协议（或 function-call）保证拿到 tmdb_id

Phase 2（质量与覆盖）：
- 当本地缺数据时，触发 TMDB 拉取并入库（discover/popular/now_playing）
- 支持过滤条件（year/region/lang/genre）与更丰富的详情（images/videos/providers）

