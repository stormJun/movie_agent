# TMDB API v3 参考文档

## 概述

The Movie Database (TMDB) API v3 是一个 REST API，提供关于电影、电视剧和影视行业人物的综合数据。

说明：
- TMDB 官方文档是权威来源（TMDB 会持续新增/调整端点）；本文档是一个“项目对齐的快照”，优先保证**项目实际用到的端点**标注准确。
- 端点非常多，本文以“端点总览 + 项目使用标记”的方式维护；如发现缺失/变更，建议以官方站点为准并回填这里。

**API 基础 URL**: `https://api.themoviedb.org/3`

**官方文档**: https://developer.themoviedb.org/reference/getting-started

---

## 端点总览

图例（是否使用）：
- ✅：后端运行时（`backend/infrastructure/enrichment/tmdb_client.py` / `tmdb_enrichment_service.py`）已使用
- ⚙️：离线/数据导入脚本（`data/movie/tmdb_client.py` 等）已使用
- ❌：当前项目未使用

### ACCOUNT（账户管理 - 11 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/account` | GET | 获取您的账户详情 | ❌ |
| `/account/{account_id}` | GET | 根据 ID 获取账户详情 | ❌ |
| `/account/{account_id}/lists` | GET | 获取账户创建的所有列表 | ❌ |
| `/account/{account_id}/favorite/movies` | GET | 获取您收藏的电影 | ❌ |
| `/account/{account_id}/favorite/tv` | GET | 获取您收藏的电视剧 | ❌ |
| `/account/{account_id}/favorite` | POST | 将电影或电视剧添加到收藏 | ❌ |
| `/account/{account_id}/rated/movies` | GET | 获取您评分的电影 | ❌ |
| `/account/{account_id}/rated/tv` | GET | 获取您评分的电视剧 | ❌ |
| `/account/{account_id}/rated/tv/episodes` | GET | 获取您评分的电视剧剧集 | ❌ |
| `/account/{account_id}/watchlist/movies` | GET | 获取您的电影待看列表 | ❌ |
| `/account/{account_id}/watchlist/tv` | GET | 获取您的电视剧待看列表 | ❌ |

### AUTHENTICATION（认证 - 7 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/authentication/token/new` | GET | 创建请求令牌 | ❌ |
| `/authentication/token/validate_with_login` | POST | 通过登录验证请求令牌 | ❌ |
| `/authentication/session/new` | POST | 从请求令牌创建会话 ID | ❌ |
| `/authentication/session/convert/4` | POST | 将 v3 访问令牌转换为 v4 访问令牌 | ❌ |
| `/authentication/guest_session/new` | GET | 创建访客会话 | ❌ |

### CERTIFICATIONS（内容分级 - 2 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/certification/movie/list` | GET | 获取电影分级列表 | ❌ |
| `/certification/tv/list` | GET | 获取电视剧分级列表 | ❌ |

### CHANGES（变更记录 - 3 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/movie/changes` | GET | 获取电影变更列表 | ❌ |
| `/tv/changes` | GET | 获取电视剧变更列表 | ❌ |
| `/person/changes` | GET | 获取人物变更列表 | ❌ |

### COLLECTIONS（电影合集 - 3 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/collection/{collection_id}` | GET | 根据 ID 获取合集详情 | ❌ |
| `/collection/{collection_id}/images` | GET | 根据 ID 获取合集图片 | ❌ |
| `/collection/{collection_id}/translations` | GET | 获取合集翻译 | ❌ |

### COMPANIES（制作公司 - 3 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/company/{company_id}` | GET | 获取公司详情 | ❌ |
| `/company/{company_id}/images` | GET | 获取公司图片 | ❌ |
| `/company/{company_id}/alternative_names` | GET | 获取公司别名 | ❌ |

### CONFIGURATION（配置信息 - 6 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/configuration` | GET | 获取 API 配置 | ❌ |
| `/configuration/countries` | GET | 获取国家列表 | ❌ |
| `/configuration/jobs` | GET | 获取职位列表 | ❌ |
| `/configuration/languages` | GET | 获取语言列表 | ❌ |
| `/configuration/primary_translations` | GET | 获取主要翻译列表 | ❌ |
| `/configuration/timezones` | GET | 获取时区列表 | ❌ |

### CREDITS（演职员 - 1 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/credit/{credit_id}` | GET | 获取演职员详情 | ❌ |

### DISCOVER（发现内容 - 2 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/discover/movie` | GET | 按条件发现电影 | ✅ |
| `/discover/tv` | GET | 按条件发现电视剧 | ✅ |

### FIND（查找数据 - 1 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/find` | GET | 根据外部 ID 查找数据 | ❌ |

### GENRES（类型 - 2 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/genre/movie/list` | GET | 获取电影类型列表 | ❌ |
| `/genre/tv/list` | GET | 获取电视剧类型列表 | ❌ |

### GUEST SESSIONS（访客会话 - 3 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/guest_session/{guest_session_id}/rated/movies` | GET | 获取访客会话的评分电影 | ❌ |
| `/guest_session/{guest_session_id}/rated/tv` | GET | 获取访客会话的评分电视剧 | ❌ |
| `/guest_session/{guest_session_id}/rated/tv/episodes` | GET | 获取访客会话的评分剧集 | ❌ |

### KEYWORDS（关键词 - 2 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/keyword/{keyword_id}` | GET | 获取关键词详情 | ❌ |
| `/keyword/{keyword_id}/movies` | GET | 根据关键词获取电影 | ❌ |

### LISTS（列表管理 - 7 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/list/{list_id}` | GET | 获取列表详情 | ❌ |
| `/list/{list_id}/item_status` | GET | 获取项目状态 | ❌ |
| `/list/{list_id}/clear` | POST | 清空列表 | ❌ |
| `/list/{list_id}/add_item` | POST | 向列表添加项目 | ❌ |
| `/list/{list_id}/remove_item` | POST | 从列表移除项目 | ❌ |
| `/list/{list_id}/check_item_status` | POST | 检查项目状态 | ❌ |

### MOVIE LISTS（电影列表 - 4 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/movie/now_playing` | GET | 获取正在上映的电影 | ❌ |
| `/movie/popular` | GET | 获取热门电影 | ❌ |
| `/movie/top_rated` | GET | 获取评分最高的电影 | ❌ |
| `/movie/upcoming` | GET | 获取即将上映的电影 | ❌ |

### MOVIES（电影详情 - 19 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/movie/{movie_id}` | GET | 获取电影详情 | ✅ |
| `/movie/{movie_id}/account_states` | GET | 获取电影账户状态 | ❌ |
| `/movie/{movie_id}/alternative_titles` | GET | 获取电影别名 | ❌ |
| `/movie/{movie_id}/changes` | GET | 获取电影变更 | ❌ |
| `/movie/{movie_id}/credits` | GET | 获取电影演职员 | ✅（通过 append_to_response） |
| `/movie/{movie_id}/external_ids` | GET | 获取电影外部 ID | ❌ |
| `/movie/{movie_id}/images` | GET | 获取电影图片 | ❌ |
| `/movie/{movie_id}/keywords` | GET | 获取电影关键词 | ❌ |
| `/movie/{movie_id}/lists` | GET | 获取包含此电影的列表 | ❌ |
| `/movie/{movie_id}/recommendations` | GET | 获取电影推荐 | ❌ |
| `/movie/{movie_id}/release_dates` | GET | 获取电影上映日期 | ❌ |
| `/movie/{movie_id}/reviews` | GET | 获取电影评论 | ❌ |
| `/movie/{movie_id}/similar` | GET | 获取相似电影 | ❌ |
| `/movie/{movie_id}/translations` | GET | 获取电影翻译 | ❌ |
| `/movie/{movie_id}/videos` | GET | 获取电影视频 | ❌ |
| `/movie/{movie_id}/watch/providers` | GET | 获取电影观看提供商 | ❌ |
| `/movie/latest` | GET | 获取最新电影 | ❌ |
| `/movie/{movie_id}/rating` | POST | 为电影评分 | ❌ |

### NETWORKS（电视网络 - 3 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/network/{network_id}` | GET | 获取电视网络详情 | ❌ |
| `/network/{network_id}/alternative_names` | GET | 获取电视网络别名 | ❌ |
| `/network/{network_id}/images` | GET | 获取电视网络图片 | ❌ |

### PEOPLE LISTS（人物列表 - 1 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/person/popular` | GET | 获取热门人物 | ❌ |

### PEOPLE（人物详情 - 10 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/person/{person_id}` | GET | 获取人物详情 | ✅（append_to_response=combined_credits） |
| `/person/{person_id}/changes` | GET | 获取人物变更 | ❌ |
| `/person/{person_id}/combined_credits` | GET | 获取人物综合演职员作品 | ✅（通过 append_to_response） |
| `/person/{person_id}/external_ids` | GET | 获取人物外部 ID | ❌ |
| `/person/{person_id}/images` | GET | 获取人物图片 | ❌ |
| `/person/{person_id}/latest` | GET | 获取最新人物 | ❌ |
| `/person/{person_id}/movie_credits` | GET | 获取人物电影作品 | ❌ |
| `/person/{person_id}/tv_credits` | GET | 获取人物电视剧作品 | ❌ |
| `/person/{person_id}/translations` | GET | 获取人物翻译 | ❌ |

### REVIEWS（评论 - 1 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/review/{review_id}` | GET | 获取评论详情 | ❌ |

### SEARCH（搜索 - 7 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/search/company` | GET | 搜索制作公司 | ❌ |
| `/search/collection` | GET | 搜索电影合集 | ❌ |
| `/search/keyword` | GET | 搜索关键词 | ❌ |
| `/search/movie` | GET | 搜索电影 | ⚙️（离线脚本 / 兼容备用） |
| `/search/multi` | GET | 多实体搜索 | ✅（movie/person/tv 消歧主入口） |
| `/search/person` | GET | 搜索人物 | ⚙️（离线脚本 / 兼容备用） |
| `/search/tv` | GET | 搜索电视剧 | ⚙️（离线脚本 / 兼容备用） |

### TRENDING（趋势内容 - 4 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/trending/{media_type}/{time_window}` | GET | 获取趋势内容 | ❌ |

### TV SERIES LISTS（电视剧列表 - 4 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/tv/airing_today` | GET | 获取今日播出的电视剧 | ❌ |
| `/tv/on_the_air` | GET | 获取正在播出的电视剧 | ❌ |
| `/tv/popular` | GET | 获取热门电视剧 | ❌ |
| `/tv/top_rated` | GET | 获取评分最高的电视剧 | ❌ |

### TV SERIES（电视剧详情 - 18 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/tv/{tv_id}` | GET | 获取电视剧详情 | ✅（append_to_response=credits） |
| `/tv/{tv_id}/account_states` | GET | 获取电视剧账户状态 | ❌ |
| `/tv/{tv_id}/alternative_titles` | GET | 获取电视剧别名 | ❌ |
| `/tv/{tv_id}/changes` | GET | 获取电视剧变更 | ❌ |
| `/tv/{tv_id}/content_ratings` | GET | 获取电视剧内容分级 | ❌ |
| `/tv/{tv_id}/credits` | GET | 获取电视剧演职员 | ✅（通过 append_to_response） |
| `/tv/{tv_id}/episode_groups` | GET | 获取电视剧剧集组 | ❌ |
| `/tv/{tv_id}/external_ids` | GET | 获取电视剧外部 ID | ❌ |
| `/tv/{tv_id}/images` | GET | 获取电视剧图片 | ❌ |
| `/tv/{tv_id}/keywords` | GET | 获取电视剧关键词 | ❌ |
| `/tv/{tv_id}/recommendations` | GET | 获取电视剧推荐 | ❌ |
| `/tv/{tv_id}/reviews` | GET | 获取电视剧评论 | ❌ |
| `/tv/{tv_id}/screened_theatrically` | GET | 获取电视剧影院放映信息 | ❌ |
| `/tv/{tv_id}/similar` | GET | 获取相似电视剧 | ❌ |
| `/tv/{tv_id}/translations` | GET | 获取电视剧翻译 | ❌ |
| `/tv/{tv_id}/videos` | GET | 获取电视剧视频 | ❌ |
| `/tv/{tv_id}/watch/providers` | GET | 获取电视剧观看提供商 | ❌ |

### TV SEASONS（电视剧季 - 10 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/tv/{tv_id}/season/{season_number}` | GET | 获取电视剧季详情 | ❌ |
| `/tv/{tv_id}/season/{season_number}/account_states` | GET | 获取季账户状态 | ❌ |
| `/tv/{tv_id}/season/{season_number}/changes` | GET | 获取季变更 | ❌ |
| `/tv/{tv_id}/season/{season_number}/credits` | GET | 获取季演职员 | ❌ |
| `/tv/{tv_id}/season/{season_number}/external_ids` | GET | 获取季外部 ID | ❌ |
| `/tv/{tv_id}/season/{season_number}/images` | GET | 获取季图片 | ❌ |
| `/tv/{tv_id}/season/{season_number}/videos` | GET | 获取季视频 | ❌ |

### TV EPISODES（电视剧集 - 11 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}` | GET | 获取电视剧集详情 | ❌ |
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}/account_states` | GET | 获取剧集账户状态 | ❌ |
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}/changes` | GET | 获取剧集变更 | ❌ |
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}/credits` | GET | 获取剧集演职员 | ❌ |
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}/external_ids` | GET | 获取剧集外部 ID | ❌ |
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}/images` | GET | 获取剧集图片 | ❌ |
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}/translations` | GET | 获取剧集翻译 | ❌ |
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}/rating` | POST | 为剧集评分 | ❌ |
| `/tv/{tv_id}/season/{season_number}/episode/{episode_number}/videos` | GET | 获取剧集视频 | ❌ |

### TV EPISODE GROUPS（剧集组 - 1 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/tv/episode_group/{episode_group_id}` | GET | 获取剧集组详情 | ❌ |

### WATCH PROVIDERS（观看提供商 - 3 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/watch/providers/movie` | GET | 获取电影观看提供商 | ❌ |
| `/watch/providers/tv` | GET | 获取电视剧观看提供商 | ❌ |
| `/watch/providers/regions` | GET | 获取可用观看提供商地区 | ❌ |

---

## 项目当前使用情况

### 已使用的端点

Movie Agent 当前在“查询时增强（Query-time Enrichment）”链路中，使用的 TMDB 端点主要集中在：
- “对象解析/消歧”（movie/person/tv）：`/search/multi` → `/{type}/{id}`（append_to_response）
- “推荐候选集合”：`/discover/movie`、`/discover/tv`

运行时（backend/enrichment）已使用端点：

| 端点 | 方法 | 用途 | 代码位置（示例） |
|----------|--------|---------|----------------|
| `/search/multi` | GET | 多类型搜索 + 消歧（movie/person/tv） | `backend/infrastructure/enrichment/tmdb_client.py`（`search_multi_raw` / `resolve_entity_via_multi`） |
| `/movie/{movie_id}` | GET | 电影详情 + 演职员（append_to_response=credits） | `backend/infrastructure/enrichment/tmdb_client.py`（`get_movie_details`） |
| `/tv/{tv_id}` | GET | 电视剧详情 + 演职员（append_to_response=credits） | `backend/infrastructure/enrichment/tmdb_client.py`（`get_tv_details`） |
| `/person/{person_id}` | GET | 人物详情 + 作品（append_to_response=combined_credits） | `backend/infrastructure/enrichment/tmdb_client.py`（`get_person_details`） |
| `/discover/movie` | GET | 按 filters 发现电影（推荐/筛选） | `backend/infrastructure/enrichment/tmdb_client.py`（`discover_movie_raw`） + `tmdb_enrichment_service.py` |
| `/discover/tv` | GET | 按 filters 发现电视剧（推荐/筛选） | `backend/infrastructure/enrichment/tmdb_client.py`（`discover_tv_raw`） + `tmdb_enrichment_service.py` |

离线/数据导入脚本（data/movie）还可能使用 `/search/movie`、`/search/person`、`/search/tv` 等单类型搜索端点（见后文）。

### 实现详情

#### 1. 对象解析/消歧：`/search/multi` → `/{type}/{id}`

**位置**:
- `backend/infrastructure/enrichment/tmdb_client.py`：`resolve_entity_via_multi(...)`
- `backend/infrastructure/enrichment/tmdb_enrichment_service.py`：调用 `resolve_entity_via_multi(...)` 并将结果构建为 transient graph

**用法**:
```python
async def resolve_entity_via_multi(self, *, text: str, query: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """用 /search/multi 将 text 解析为 movie/tv/person，并拉取对应详情（append_to_response）。"""
```

**请求参数**:
- `query`（必需）：候选实体名（可能是片名/人名/别名）
- `language`: 先尝试 `zh-CN`，再回退 `en-US`（用于 overview/biography 补全）

**流程**:
1. 调用 `/search/multi` 获取多类型候选（movie/tv/person）
2. 对候选进行打分（考虑精确匹配、年份一致性、人物角色提示等），若分数过低则拒绝（避免误认）
3. 选中最佳候选后：
   - movie：调用 `/movie/{id}?append_to_response=credits`
   - tv：调用 `/tv/{id}?append_to_response=credits`
   - person：调用 `/person/{id}?append_to_response=combined_credits`
4. 将返回 payload 交给 `TransientGraphBuilder` 转为“可引用证据”（transient graph），并拼入 combined_context

#### 2. 推荐候选集合：`/discover/movie` 与 `/discover/tv`

**位置**:
- `backend/infrastructure/enrichment/tmdb_enrichment_service.py`：当 router 给出 `query_intent=recommend` 且 `media_type_hint=movie|tv` 时触发
- `backend/infrastructure/enrichment/tmdb_client.py`：`discover_movie_raw(...)` / `discover_tv_raw(...)`

**请求参数（示例映射）**:
- movie：`filters.year` → `primary_release_year`，`filters.region` → `region`，`filters.original_language` → `with_original_language`，`filters.date_range.gte/lte` → `primary_release_date.gte/lte`
- tv：`filters.year` → `first_air_date_year`，`filters.origin_country` → `with_origin_country`，`filters.original_language` → `with_original_language`，`filters.date_range.gte/lte` → `first_air_date.gte/lte`

**流程**:
1. router 决定推荐意图与媒体类型，并输出结构化 filters（避免本地关键字猜测误触发）
2. 调用 `/discover/movie` 或 `/discover/tv` 得到候选集合（用于“推荐/筛选”场景）
3. （可选）对 top N 候选再拉详情（`/movie/{id}` 或 `/tv/{id}`）增强解释性与字段完整性
4. 同样构建为 transient graph 证据后进入 combined_context

---

## 项目中的其他 TMDB 客户端

### 数据导入 TMDB 客户端

**位置**: `data/movie/tmdb_client.py`

这是一个**独立的客户端**，用于从 TMDB 批量导入数据到我们的知识库。它使用**同步** HTTP 请求（与 enrichment 中使用的异步客户端相对）。

**可用方法**（不直接用于查询时 enrichment）:
```python
get_movie_details(tmdb_id)              # 电影详情
get_movie_credits(tmdb_id)              # 演职员表
get_movie_keywords(tmdb_id)             # 关键词标签
get_movie_recommendations(tmdb_id)      # 推荐电影
get_movie_similar(tmdb_id)              # 相似电影
get_genre_list()                        # 类型列表
search_movie(title, year)               # 搜索电影
```

---

## Certifications 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/certification-movie-list
- https://developer.themoviedb.org/reference/certifications-tv-list

用途：
- 获取不同国家/地区的内容分级字典（用于展示或过滤，例如 US/GB/CN 等）

### 1) GET `/certification/movie/list`（电影分级列表）

请求：
- 无必需参数（使用认证信息即可）

响应要点：
- `certifications`：按国家/地区分组的分级数组（每个条目通常包含 `certification`/`meaning`/`order`）

官方参考：
- https://developer.themoviedb.org/reference/certification-movie-list

### 2) GET `/certification/tv/list`（电视剧分级列表）

请求：
- 无必需参数

响应要点：
- `certifications`：按国家/地区分组的分级数组

官方参考：
- https://developer.themoviedb.org/reference/certifications-tv-list

---

## Changes 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/changes-movie-list
- https://developer.themoviedb.org/reference/changes-people-list
- https://developer.themoviedb.org/reference/changes-tv-list

用途：
- 拉取“发生过变更的资源 ID 列表”（movie/tv/person），用于离线同步、增量更新、ETL 触发等。

说明：
- 这些端点返回的是“ID + changed_at”等概要信息；真正的详情仍需再调用 `/movie/{id}`、`/tv/{id}`、`/person/{id}` 获取。

### 1) GET `/movie/changes`（电影变更列表）

常用请求参数（Query，按需）：
- `page`
- `start_date` / `end_date`：时间窗（官方要求范围有限制，超范围会报错）

响应要点：
- `results[]`：通常包含 `id`、`adult`（可能出现）、`changed_at`（或同等语义字段）
- `page` / `total_pages` / `total_results`

官方参考：
- https://developer.themoviedb.org/reference/changes-movie-list

### 2) GET `/tv/changes`（电视剧变更列表）

常用请求参数：
- `page`
- `start_date` / `end_date`

响应要点：
- `results[]`（id 列表 + 变更时间）

官方参考：
- https://developer.themoviedb.org/reference/changes-tv-list

### 3) GET `/person/changes`（人物变更列表）

常用请求参数：
- `page`
- `start_date` / `end_date`

响应要点：
- `results[]`（id 列表 + 变更时间）

官方参考：
- https://developer.themoviedb.org/reference/changes-people-list

---

## Companies 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/company-details
- https://developer.themoviedb.org/reference/company-alternative-names

用途：
- 制作公司信息展示（出品方/制作方），以及公司别名（用于实体归一）

### 1) GET `/company/{company_id}`（公司详情）

请求：
- Path：
  - `company_id`（必需）

响应要点（常用字段，非穷举）：
- `id`
- `name`
- `description`
- `headquarters`
- `homepage`
- `logo_path`
- `origin_country`

官方参考：
- https://developer.themoviedb.org/reference/company-details

### 2) GET `/company/{company_id}/alternative_names`（公司别名）

请求：
- Path：
  - `company_id`（必需）

响应要点：
- `id`
- `results[]`：别名数组（通常包含 `name` / `type` 等）

官方参考：
- https://developer.themoviedb.org/reference/company-alternative-names

（可选）3) GET `/company/{company_id}/images`（公司图片）
- 官方参考：https://developer.themoviedb.org/reference/company-images

---

## Collections 端点对齐（官方 Reference）

本节对齐官方 Reference（示例页面：`/reference/collection-details`），补全 COLLECTIONS 相关端点的“参数/响应要点”，便于后续实现：
- 电影合集详情展示（系列电影，如 “The Lord of the Rings Collection”）
- 电影合集封面/背景图拉取（前端展示）
- 合集翻译（多语言）

注意：截至本文档更新，Collections 端点**在运行时 enrichment 中未使用**，因此这里属于“预备对齐”，用于后续产品能力扩展。

### 1) GET `/collection/{collection_id}`（合集详情）

用途：
- 根据 TMDB collection_id 获取合集基本信息与包含的影片列表（parts）

请求：
- Path：
  - `collection_id`（必需）：合集 ID
- Query：
  - `language`（可选）：如 `zh-CN` / `en-US`

响应要点（常用字段，非穷举）：
- `id`：collection_id
- `name`：合集名
- `overview`：简介
- `poster_path` / `backdrop_path`
- `parts[]`：合集内影片列表（通常包含 `id/title/release_date/poster_path/vote_average/overview` 等）

官方参考：
- https://developer.themoviedb.org/reference/collection-details

### 2) GET `/collection/{collection_id}/images`（合集图片）

用途：
- 获取合集的 posters/backdrops，供前端展示

请求：
- Path：
  - `collection_id`（必需）
- Query（常用）：
  - `language`（可选）
  - `include_image_language`（可选）：例如 `zh,null`（包含无语言标注图片）

响应要点：
- `id`
- `backdrops[]` / `posters[]`（数组元素通常包含 `file_path/width/height/vote_average` 等）

官方参考：
- https://developer.themoviedb.org/reference/collection-images

### 3) GET `/collection/{collection_id}/translations`（合集翻译）

用途：
- 获取合集多语言翻译（标题/简介），用于多语言 UI 或翻译回退策略

请求：
- Path：
  - `collection_id`（必需）

响应要点：
- `id`
- `translations[]`（包含语言码、名称、overview 等）

官方参考：
- https://developer.themoviedb.org/reference/collection-translations

## API 密钥配置

**环境变量**（二选一）:
- `TMDB_API_TOKEN`（推荐）：v4 Read Access Token（HTTP Header Bearer）
- `TMDB_API_KEY`（兼容）：v3 API Key（Query 参数 api_key）

**配置位置**: `backend/infrastructure/config/settings.py`
```python
TMDB_BASE_URL = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3").strip()
TMDB_API_TOKEN = os.getenv("TMDB_API_TOKEN", "").strip()
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
TMDB_TIMEOUT_S = _get_env_float("TMDB_TIMEOUT_S", 5.0) or 5.0
```

**基础 URL**: `TMDB_BASE_URL`（默认 `https://api.themoviedb.org/3`）

**默认语言**: `zh-CN`（中文）

---

## 未来扩展机会

当前项目已覆盖 movie/person/tv 的“查询时增强（enrichment）”核心链路。潜在的扩展领域：

1. **趋势内容**: `GET /trending/{media_type}/{time_window}` 支持“近期热门/口碑”
2. **相似/推荐**: `GET /movie/{id}/similar`、`GET /movie/{id}/recommendations` 做“类似 X / 看完 X 还能看什么”
3. **观看平台**: `GET /movie/{id}/watch/providers`、`GET /tv/{id}/watch/providers` 做“哪里能看”
4. **外部 ID**: `GET /movie/{id}/external_ids`、`GET /person/{id}/external_ids` 做 IMDb/Douban（如有）对齐与去重
5. **图片/海报**: `/images` + `/configuration` 做封面/演员头像展示（前端体验）

---

## 参考资料

- TMDB API v3 文档: https://developer.themoviedb.org/reference/getting-started
- TMDB API 状态: https://status.themoviedb.org/
- TMDB 开发者社区: https://www.themoviedb.org/talk

---

**文档版本**: 1.0
**最后更新**: 2026-01-27
**API 版本**: TMDB API v3
