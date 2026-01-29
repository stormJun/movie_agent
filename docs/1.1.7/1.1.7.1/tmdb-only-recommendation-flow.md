# TMDB-Only Recommendation Flow (No Neo4j/GraphRAG)

目标：当用户意图为“推荐/片单/介绍几个”时，完全使用 TMDB 作为候选与事实来源，不再依赖 Neo4j/GraphRAG 检索；同时保证：

- 回答正文中出现的电影名/介绍，与返回给前端的 `recommendation_ids` 强一致（同一来源、同一选择结果）
- 小程序/网页端可用同一套后端能力（stream + 非 stream）
- TMDB 数据必须落库到 Postgres，供电影列表/详情页快速展示与后续离线同步

---

## 1. 适用范围与非目标

### 1.1 适用范围（触发 TMDB-only）

当 Router 输出满足以下条件时触发：

- `kb_prefix == "movie"`（或未来新增 `kb_prefix == "tv"`）
- `query_intent == "recommend"`（推荐/介绍/想看/片单/类似…）
- `media_type_hint in {"movie","tv"}`（可选，默认 movie）

### 1.2 非目标（仍走 GraphRAG/Neo4j）

以下不走 TMDB-only：

- 明确事实问答（导演是谁、上映时间、剧情是什么…）→ 可继续走 GraphRAG + TMDB enrichment（或按后续策略切到 TMDB-only QA）
- 对知识库内部专有数据的检索（本地 documents/datasets）
- 需要图算法/多跳关系推理的复杂问题

---

## 2. 总体流程（高层）

TMDB-only 推荐链路 = “路由识别 → TMDB 拉候选池 →（best-effort）补全详情 → LLM 结构化选片 + 文案 → 返回 ids + 文案”

```
Client
  ↓
/api/v1/(chat|mp/chat)/stream  (message, user_id, session_id, debug)
  ↓
Router (LLM/规则) → route_decision { query_intent, media_type_hint, filters, seed_entity? }
  ↓
TMDB Candidate Fetch
  - seed 模式：/search/multi → /movie/{id}/recommendations
  - no-seed 模式：/discover/movie  (filters + sort)
  ↓
Best-effort Detail Hydration
  - /movie/{id}?append_to_response=credits (top N)
  ↓
LLM Selection + Copywriting (STRICT)
  - 输出 selected_movies [{tmdb_id,title,year,blurb}]
  ↓
Response
  - answer: 仅基于 selected_movies 生成
  - recommendation_ids: selected_movies[*].tmdb_id
  - (optional) recommendation_items: selected_movies (供前端直接渲染)
```

关键点：推荐名单的“权威来源”是 `selected_movies`，而不是自由文本。

---

## 3. Router 输出（推荐场景最小契约）

为了让后续 TMDB 端点选择更稳，Router 在推荐场景需要输出：

- `query_intent`: `recommend`
- `media_type_hint`: `movie` / `tv`
- `filters`（可选，最小 MVP）：
  - `year`（如 2024）
  - `region`（如 CN，用于 discover）
  - `original_language`（如 zh）
  - `origin_country`（TV 推荐优先）
- `extracted_entities.low_level`（可选）：
  - 用于“类似《喜宴》”这类 seed 模式：低层实体中应包含候选片名

> 备注：推荐流程不要求实体抽取必然成功；如果没有 seed，就走 discover。

---

## 4. TMDB 候选池策略（Candidate Fetch）

推荐分两类：有 seed / 无 seed。

### 4.1 有 seed（“类似《喜宴》/给我推荐类似 X 的电影”）

1) `/search/multi?query=<seed_title>`
   - 目标：拿到 seed movie 的 `tmdb_id`
   - 选择策略：exact title match > year match > score

2) `/movie/{seed_id}/recommendations?page=1&language=...`
   - 得到候选列表 results（N=20）

3) 如果 `/movie/{seed_id}/recommendations` 为空：
   - fallback：`/movie/{seed_id}/similar`
   - 或 fallback：`/discover/movie`（按 seed 的 genre/keywords 近似过滤，后续迭代）

### 4.2 无 seed（“介绍几个电影/推荐几个电影/最近有什么好看的”）

使用：

- `/discover/movie?page=1&sort_by=popularity.desc&language=...&region=...`
- 结合 Router filters（year/original_language/region/date_range）

MVP 建议：

- 默认 `sort_by=popularity.desc`
- 默认 `language=zh-CN`，如果 `overview` 为空则 fallback 再拉一遍 `en-US`（仅补 overview）

---

## 5. 详情补全（Best-effort Detail Hydration）

目的：让最终展示具备导演/主演/类型等字段，并用于更好的 blurb。

对候选 top N（建议 N=10，最终展示 M=5）拉详情：

- `/movie/{id}?append_to_response=credits&language=zh-CN`

并发限制建议：

- `max_concurrency=5~8`
- 每个请求 `timeout_s=5`
- 失败容忍：任何单个详情失败不影响整体推荐；缺字段则降级展示

---

## 6. LLM “结构化选片 + 文案”严格契约

推荐一致性的核心：LLM 不允许创造候选池外的电影。

### 6.1 输入给 LLM 的信息

- `user_query`: 原问题
- `constraints`: 语言、地区、年份等（来自 Router filters）
- `candidates`: 候选池（必须包含 `tmdb_id`，以及可选 `title/year/overview/rating/genres/director`）

### 6.2 输出结构（严格 JSON）

建议输出字段：

```json
{
  "selected_movies": [
    {
      "tmdb_id": 123,
      "title": "片名",
      "year": 2024,
      "blurb": "2-3 句话推荐理由（不要剧透）"
    }
  ],
  "answer_style": {
    "tone": "friendly",
    "language": "zh-CN"
  }
}
```

强约束：

- `selected_movies[*].tmdb_id` 必须来自 candidates 的 id 集合
- `selected_movies` 长度建议固定（MVP：5）
- `title/year` 以 TMDB 为准（避免中文译名/别名不一致）

### 6.3 回答正文的生成方式

为了确保“正文提到的电影”与 ids 对齐，正文建议由后端基于 `selected_movies` 模板化生成，或让 LLM 生成但只引用 `selected_movies`：

- 标题：`为你推荐 5 部电影`
- 每条：`《{title}》({year})：{blurb}`

---

## 7. API 返回与前端渲染

### 7.1 Stream（SSE）建议事件

最小事件集（保持与现有 mp 兼容）：

- `generate_start`：携带 `request_id`
- `status`：routing / retrieval / generation
- `recommendations`：携带 `tmdb_ids`（候选或最终选择，建议是最终选择）
- `chunk`：回答流式 token
- `complete`：最终 answer + `response.extracted_info.recommendation_ids`

关键：`recommendation_ids` 应以 `selected_movies[*].tmdb_id` 为准（最终选择），而不是“候选池”。

### 7.2 非 Stream（/chat）建议字段

返回：

- `answer`（正文，电影名来自 `selected_movies`）
- `extracted_info.recommendation_ids`（与正文一致）
- （可选）`extracted_info.recommendation_items`：直接给前端渲染卡片，无需二次请求

---

## 8. Postgres 落库（必选）

目的：

- 发现页/详情页不必每次都打 TMDB
- 推荐结果可复用（缓存）
- 为未来 “离线全量同步/增量更新” 打基础

写入时机（必须写入）：

- Candidate Fetch 后（discover/recommendations 得到候选）
- Detail Hydration 后（movie/{id} 返回完整字段）

建议落库的最小字段（MVP）：

- `tmdb_id`（主键）
- `title/original_title`
- `release_date/year`
- `poster_path/backdrop_path`
- `vote_average/vote_count/popularity`
- `genres`（raw 中即可）
- `credits`（raw 中即可，用于导演/主演解析）
- `raw`（jsonb，全量快照）
- `raw_source_endpoint`（discover/recommendations/movie/{id}）
- `updated_at`

---

## 9. 失败降级策略（仍需保证落库一致性）

- TMDB 不可用：
  - 返回友好提示（“当前无法获取推荐，请稍后重试”）
  - 不返回 recommendation_ids（空列表）
- 详情补全失败：
  - 仍需把“候选池简版快照”落库（raw 不完整但可用），并标记 `raw_source_endpoint=/discover/...`
  - 同时对失败的 id 进入异步重试队列（后续补齐 `/movie/{id}?append_to_response=credits`）
- LLM 结构化输出解析失败：
  - fallback：后端直接取候选 top 5 作为 selected_movies，并用模板生成正文
  - 这些 top 5 的详情（若未补齐）同样需要进入补齐队列，保证详情页可用

---

## 10. 与现有系统的集成点（最小改动建议）

推荐场景 TMDB-only 的最小落地点：

1) Router：保持现有输出（query_intent/media_type_hint/filters）
2) retrieval_subgraph：
   - 当 `query_intent=recommend` 时，不再执行 GraphRAG runs（不调 Neo4j）
   - 只做 “TMDB Candidate Fetch + Detail Hydration + LLM Selection”
   - merge 阶段产出：
     - `merged.context`：由 selected_movies 模板化生成的“推荐上下文”
     - `recommendations`：发最终 selected tmdb_ids
3) 生成：若正文已经由模板生成，可直接 stream 输出（减少 LLM token 消耗）

---

## 11. MVP 参数建议

- 候选池大小：20
- 最终展示：5
- 详情补全：对 top 10 拉详情
- 并发：5
- 超时：5s
- 语言：zh-CN；overview 为空 fallback en-US
- 排序：popularity.desc（默认）
