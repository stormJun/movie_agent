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
- https://developer.themoviedb.org/reference/company-images

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

### 3) GET `/company/{company_id}/images`（公司图片）

用途：
- 获取制作公司的 logo 等图片资源（前端展示、出品方列表 UI）。

请求：
- Path：
  - `company_id`（必需）

响应要点：
- `id`
- `logos[]`：logo 图片数组（元素通常包含 `file_path/width/height/aspect_ratio/vote_average` 等）

官方参考：
- https://developer.themoviedb.org/reference/company-images

---

## Credits 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/credit-details

用途：
- 根据 `credit_id` 获取一条演职员信用记录的详情（可用于“某条 credit 的精确信息/补全”）。

### GET `/credit/{credit_id}`（credit-details）

请求：
- Path：
  - `credit_id`（必需）
- Query：
  - `language`（可选）

响应要点（常用字段，非穷举）：
- `id`（credit_id）
- `media`（movie/tv 的基础信息，字段随类型变化）
- `person`（人物信息）
- `media_type`

官方参考：
- https://developer.themoviedb.org/reference/credit-details

说明：
- 当前项目更常用 `/movie/{id}?append_to_response=credits` 或 `/tv/{id}?append_to_response=credits`，很少需要以 credit_id 单独查询。

---

## Discover 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/discover-movie
- https://developer.themoviedb.org/reference/discover-tv

用途：
- 推荐/筛选：按结构化条件发现 movie/tv 候选集合（通常作为“候选池”，再补细节与解释）。

### 1) GET `/discover/movie`（discover-movie）

请求（Query，常用）：
- `language`（如 `zh-CN`）
- `page`
- `sort_by`（例如 `popularity.desc` / `vote_average.desc`）
- `include_adult`（false）
- `primary_release_year`
- `primary_release_date.gte` / `primary_release_date.lte`
- `region`
- `with_origin_country`（best-effort）
- `with_original_language`

响应要点：
- `results[]`：候选电影数组（通常包含 `id/title/release_date/overview/vote_average` 等）
- `page/total_pages/total_results`

官方参考：
- https://developer.themoviedb.org/reference/discover-movie

### 2) GET `/discover/tv`（discover-tv）

请求（Query，常用）：
- `language`
- `page`
- `sort_by`
- `include_adult`
- `first_air_date_year`
- `first_air_date.gte` / `first_air_date.lte`
- `with_origin_country`
- `with_original_language`

响应要点：
- `results[]`：候选电视剧数组（通常包含 `id/name/first_air_date/overview/vote_average` 等）

官方参考：
- https://developer.themoviedb.org/reference/discover-tv

说明（与本项目实现对齐）：
- 项目在 `backend/infrastructure/enrichment/tmdb_client.py` 中封装了 `discover_movie_raw(...)` 与 `discover_tv_raw(...)`，并由 `tmdb_enrichment_service.py` 在 `query_intent=recommend` 且 `media_type_hint=movie|tv` 时触发。

---

## Keywords 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/keyword-details
- https://developer.themoviedb.org/reference/keyword-movies

用途：
- 关键词实体（keyword）可用于“主题/话题”维度的聚合检索与推荐，例如根据关键字拉相关电影集合。

### 1) GET `/keyword/{keyword_id}`（keyword-details）

请求：
- Path：
  - `keyword_id`（必需）

响应要点：
- `id`
- `name`

官方参考：
- https://developer.themoviedb.org/reference/keyword-details

### 2) GET `/keyword/{keyword_id}/movies`（keyword-movies）

请求（Query，常用）：
- `language`
- `page`
- `include_adult`

响应要点：
- `results[]`：电影列表（含 `id/title/release_date/overview/vote_average` 等）
- `page/total_pages/total_results`

官方参考：
- https://developer.themoviedb.org/reference/keyword-movies

---

## Movie Lists 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/movie-now-playing-list
- https://developer.themoviedb.org/reference/movie-popular-list
- https://developer.themoviedb.org/reference/movie-top-rated-list
- https://developer.themoviedb.org/reference/movie-upcoming-list

用途：
- 产品侧常用的“榜单/热门/近期上映”入口；可作为冷启动推荐或首页内容流。

通用请求参数（Query，常用）：
- `language`
- `page`
- `region`（可选）

通用响应要点：
- `results[]`：电影列表（含 `id/title/release_date/poster_path/vote_average` 等）
- `page/total_pages/total_results`

### 1) GET `/movie/now_playing`（now-playing-list）
- 官方参考：https://developer.themoviedb.org/reference/movie-now-playing-list

### 2) GET `/movie/popular`（popular-list）
- 官方参考：https://developer.themoviedb.org/reference/movie-popular-list

### 3) GET `/movie/top_rated`（top-rated-list）
- 官方参考：https://developer.themoviedb.org/reference/movie-top-rated-list

### 4) GET `/movie/upcoming`（upcoming-list）
- 官方参考：https://developer.themoviedb.org/reference/movie-upcoming-list

---

## Movies（详情与相关端点）对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/movie-details
- https://developer.themoviedb.org/reference/movie-account-states
- https://developer.themoviedb.org/reference/movie-alternative-titles
- https://developer.themoviedb.org/reference/movie-credits

用途：
- 获取单部电影的结构化字段（用于事实问答、对比、入库、图谱建模）
- 获取演职员（导演/演员）用于人物关系与回答“谁执导/谁主演”
- 获取别名用于实体归一（译名/别名/地区标题）

### 1) GET `/movie/{movie_id}`（movie-details）

请求：
- Path：
  - `movie_id`（必需）
- Query（常用）：
  - `language`
  - `append_to_response=credits`（本项目常用：一次拿到演职员）

响应要点（常用字段，非穷举）：
- `id`
- `title` / `original_title`
- `overview`
- `release_date`
- `runtime`
- `genres[]`
- `vote_average` / `vote_count`
- `credits.cast[]` / `credits.crew[]`（当 append_to_response=credits 时）

官方参考：
- https://developer.themoviedb.org/reference/movie-details

### 2) GET `/movie/{movie_id}/credits`（movie-credits）

请求：
- Path：`movie_id`（必需）
- Query：`language`（可选）

响应要点：
- `id`
- `cast[]`（演员；含 character/order 等）
- `crew[]`（剧组；含 job/department；导演通常是 `job=Director`）

官方参考：
- https://developer.themoviedb.org/reference/movie-credits

说明（与本项目实现对齐）：
- 项目优先使用 `GET /movie/{id}?append_to_response=credits`，避免再单独调用 `/movie/{id}/credits`。

### 3) GET `/movie/{movie_id}/alternative_titles`（movie-alternative-titles）

用途：
- 获取不同地区的标题/别名，用于实体归一与消歧（同名片/译名）

请求（Query，常用）：
- `country`（可选）：例如 `US` / `CN`

响应要点：
- `id`
- `titles[]`（含 `iso_3166_1`、`title`、`type` 等）

官方参考：
- https://developer.themoviedb.org/reference/movie-alternative-titles

### 4) GET `/movie/{movie_id}/account_states`（movie-account-states）

用途：
- 与账户体系相关（是否收藏/是否加入 TMDB watchlist/评分等）；需要用户级授权，不适合匿名 enrichment。

请求（常用）：
- `session_id` 或其它授权信息（具体以官方为准）

响应要点：
- `favorite` / `rated` / `watchlist` 等状态字段

官方参考：
- https://developer.themoviedb.org/reference/movie-account-states

---

## Movies（扩展端点）对齐（官方 Reference）

本节对齐官方 Reference（movie 相关补充端点）：
- https://developer.themoviedb.org/reference/movie-external-ids
- https://developer.themoviedb.org/reference/movie-images
- https://developer.themoviedb.org/reference/movie-keywords
- https://developer.themoviedb.org/reference/movie-latest-id
- https://developer.themoviedb.org/reference/movie-lists
- https://developer.themoviedb.org/reference/movie-recommendations
- https://developer.themoviedb.org/reference/movie-release-dates
- https://developer.themoviedb.org/reference/movie-reviews
- https://developer.themoviedb.org/reference/movie-similar
- https://developer.themoviedb.org/reference/movie-translations
- https://developer.themoviedb.org/reference/movie-videos

用途（典型产品/数据场景）：
- 实体归一（IMDb 等外部 ID）
- 资源展示（海报/剧照/视频预告）
- 推荐增强（similar/recommendations）
- 上映信息（release_dates）
- 多语言回退（translations）
- 主题标签（keywords）
- 内容运营（latest/列表聚合）

### 1) GET `/movie/{movie_id}/external_ids`（movie-external-ids）

用途：
- 对齐外部平台 ID（如 IMDb 等），用于去重/融合第三方数据源。

请求：
- Path：`movie_id`（必需）

响应要点：
- `id`
- `imdb_id`（常用）
- 以及其它外部 ID 字段（随 TMDB 返回而定）

官方参考：
- https://developer.themoviedb.org/reference/movie-external-ids

### 2) GET `/movie/{movie_id}/images`（movie-images）

用途：
- 获取 posters/backdrops/logos 等图片资源（前端展示）。

请求（常用 Query）：
- `language`（可选）
- `include_image_language`（可选，例如 `zh,null`）

响应要点：
- `id`
- `backdrops[]` / `posters[]` / `logos[]`（元素含 `file_path/width/height/vote_average` 等）

官方参考：
- https://developer.themoviedb.org/reference/movie-images

### 3) GET `/movie/{movie_id}/keywords`（movie-keywords）

用途：
- 获取关键词标签（可用于主题推荐、相似度特征、标签展示）。

请求：
- Path：`movie_id`（必需）

响应要点：
- `id`
- `keywords[]`（元素含 `id`/`name`）

官方参考：
- https://developer.themoviedb.org/reference/movie-keywords

### 4) GET `/movie/latest`（movie-latest-id）

用途：
- 获取“最新电影”的条目（注意：通常不是“最新上映”，而是最新创建/更新的 movie 记录）。

请求：
- `language`（可选）

响应要点：
- 返回一条 movie 详情（字段类似 movie-details）

官方参考：
- https://developer.themoviedb.org/reference/movie-latest-id

### 5) GET `/movie/{movie_id}/lists`（movie-lists）

用途：
- 获取包含该电影的 TMDB 公共 list（运营/用户列表场景）。

请求（常用 Query）：
- `language`
- `page`

响应要点：
- `results[]`：列表信息

官方参考：
- https://developer.themoviedb.org/reference/movie-lists

### 6) GET `/movie/{movie_id}/recommendations`（movie-recommendations）

用途：
- 获取“看完该片还可看什么”的候选集合（可用于推荐增强/冷启动）。

请求（常用 Query）：
- `language`
- `page`

响应要点：
- `results[]`：推荐电影列表（含 `id/title/release_date/vote_average` 等）

官方参考：
- https://developer.themoviedb.org/reference/movie-recommendations

### 7) GET `/movie/{movie_id}/similar`（movie-similar）

用途：
- 获取“类似该片”的候选集合（相似推荐）。

请求（常用 Query）：
- `language`
- `page`

响应要点：
- `results[]`：相似电影列表

官方参考：
- https://developer.themoviedb.org/reference/movie-similar

### 8) GET `/movie/{movie_id}/release_dates`（movie-release-dates）

用途：
- 获取各地区上映日期/分级等信息（地区化上映信息、影院/流媒体窗口）。

请求：
- Path：`movie_id`（必需）

响应要点：
- `results[]`：按 `iso_3166_1` 分组的 release dates 列表（结构较深）

官方参考：
- https://developer.themoviedb.org/reference/movie-release-dates

### 9) GET `/movie/{movie_id}/reviews`（movie-reviews）

用途：
- 获取影评（可用于展示或作为“观点证据”，注意版权/长度）。

请求（常用 Query）：
- `language`
- `page`

响应要点：
- `results[]`：评论列表（author/content/url 等）

官方参考：
- https://developer.themoviedb.org/reference/movie-reviews

### 10) GET `/movie/{movie_id}/translations`（movie-translations）

用途：
- 多语言标题/简介，用于语言回退与展示。

响应要点：
- `translations[]`：包含语言码、title、overview 等

官方参考：
- https://developer.themoviedb.org/reference/movie-translations

### 11) GET `/movie/{movie_id}/videos`（movie-videos）

用途：
- 预告片/片段等视频资源（YouTube 等），用于前端展示。

请求（常用 Query）：
- `language`

响应要点：
- `results[]`：包含 `site/key/type/name/official` 等

官方参考：
- https://developer.themoviedb.org/reference/movie-videos

---

## People Lists 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/person-popular-list

### GET `/person/popular`（person-popular-list）

用途：
- 热门人物榜单（导演/演员等），可用于冷启动推荐/探索入口。

请求（常用 Query）：
- `language`
- `page`

响应要点：
- `results[]`：人物列表（含 `id/name/known_for_department/known_for[]` 等）

官方参考：
- https://developer.themoviedb.org/reference/person-popular-list

---

## People 端点对齐（官方 Reference）

本节对齐官方 Reference（人物详情相关端点）：
- https://developer.themoviedb.org/reference/person-details
- https://developer.themoviedb.org/reference/person-combined-credits
- https://developer.themoviedb.org/reference/person-external-ids
- https://developer.themoviedb.org/reference/person-images
- https://developer.themoviedb.org/reference/person-latest-id
- https://developer.themoviedb.org/reference/person-movie-credits
- https://developer.themoviedb.org/reference/person-tv-credits
- https://developer.themoviedb.org/reference/person-translations

用途（典型产品/数据场景）：
- 回答 “导演/演员是谁、演过什么、导过什么”
- 人物消歧后的作品清单（combined_credits）
- 外部 ID 对齐（IMDb/Wikidata/social）
- 图片资源（profile 头像）
- 多语言信息回退（translations）

### 1) GET `/person/{person_id}`（person-details）

用途：
- 获取人物基础信息（姓名、简介、部门、生日等）

请求：
- Path：`person_id`（必需）
- Query（常用）：
  - `language`
  - `append_to_response=combined_credits`（可选；项目中常用，一次拿到 filmography）

响应要点（常用字段，非穷举）：
- `id`
- `name` / `also_known_as[]`
- `biography`
- `known_for_department`（Directing/Acting 等）
- `birthday` / `deathday`
- `place_of_birth`
- `profile_path`

官方参考：
- https://developer.themoviedb.org/reference/person-details

### 2) GET `/person/{person_id}/combined_credits`（person-combined-credits）

用途：
- 获取人物的综合作品清单（电影 + 电视剧），用于 “他导演了哪些/他演了哪些”

请求：
- Path：`person_id`（必需）
- Query：`language`（可选）

响应要点：
- `id`
- `cast[]`：表演作品（常见字段：`id/title/name/release_date/first_air_date/character` 等）
- `crew[]`：幕后作品（常见字段：`id/title/name/release_date/first_air_date/job/department` 等）

官方参考：
- https://developer.themoviedb.org/reference/person-combined-credits

### 3) GET `/person/{person_id}/external_ids`（person-external-ids）

用途：
- 外部 ID 对齐与去重（IMDb/Wikidata/社交媒体）

请求：
- Path：`person_id`（必需）

响应要点（常用字段，非穷举）：
- `id`
- `imdb_id`
- `wikidata_id`
- `facebook_id` / `instagram_id` / `twitter_id` 等（具体字段以 TMDB 返回为准）

官方参考：
- https://developer.themoviedb.org/reference/person-external-ids

### 4) GET `/person/{person_id}/images`（person-images）

用途：
- 头像/剧照等图片资源（前端展示）

请求（常用 Query）：
- `language`（可选）
- `include_image_language`（可选，例如 `zh,null`）

响应要点：
- `id`
- `profiles[]`（元素含 `file_path/width/height/vote_average` 等）

官方参考：
- https://developer.themoviedb.org/reference/person-images

### 5) GET `/person/latest`（person-latest-id）

用途：
- 获取“最新人物”条目（通常是最新创建/更新的 person 记录，不等同于热门）

请求：
- `language`（可选）

响应要点：
- 返回一条 person 详情（字段类似 person-details）

官方参考：
- https://developer.themoviedb.org/reference/person-latest-id

### 6) GET `/person/{person_id}/movie_credits`（person-movie-credits）

用途：
- 仅电影维度的作品清单（cast/crew）

请求：
- Path：`person_id`（必需）
- Query：`language`（可选）

响应要点：
- `cast[]` / `crew[]`（电影作品）

官方参考：
- https://developer.themoviedb.org/reference/person-movie-credits

### 7) GET `/person/{person_id}/tv_credits`（person-tv-credits）

用途：
- 仅电视剧维度的作品清单（cast/crew）

请求：
- Path：`person_id`（必需）
- Query：`language`（可选）

响应要点：
- `cast[]` / `crew[]`（电视剧作品）

官方参考：
- https://developer.themoviedb.org/reference/person-tv-credits

### 8) GET `/person/{person_id}/translations`（person-translations）

用途：
- 多语言名称/简介翻译（用于语言回退）

请求：
- Path：`person_id`（必需）

响应要点：
- `id`
- `translations[]`（包含语言码与对应的 name/biography 等）

官方参考：
- https://developer.themoviedb.org/reference/person-translations

说明（与本项目实现对齐）：
- 运行时 enrichment 当前更偏向：优先 `language=zh-CN`，若 biography 为空再回退 `en-US`（best-effort），而不是调用 translations。

---

## Search 端点对齐（官方 Reference）

本节对齐官方 Reference（搜索相关端点）：
- https://developer.themoviedb.org/reference/search-company
- https://developer.themoviedb.org/reference/search-collection
- https://developer.themoviedb.org/reference/search-keyword
- https://developer.themoviedb.org/reference/search-movie
- https://developer.themoviedb.org/reference/search-multi
- https://developer.themoviedb.org/reference/search-person
- https://developer.themoviedb.org/reference/search-tv

通用说明：
- Search 端点普遍返回分页结构：`page/results/total_pages/total_results`
- `query` 为必需字段；`language`/`page` 常用；`include_adult` 在部分端点可用

### 1) GET `/search/multi`（search-multi）

用途：
- 多类型搜索（movie/tv/person），用于“对象解析/消歧”的第一步（本项目运行时主入口）

请求（常用 Query）：
- `query`（必需）
- `language`
- `page`
- `include_adult`（可选）

响应要点：
- `results[]`：每个元素通常包含 `media_type`（movie/tv/person）与对应的基础字段（id/title/name/date 等）

官方参考：
- https://developer.themoviedb.org/reference/search-multi

### 2) GET `/search/movie`（search-movie）

用途：
- 仅电影搜索（可作为 multi 的补充/替代）

请求（常用 Query）：
- `query`（必需）
- `language`
- `page`
- `include_adult`（可选）
- `region`（可选）
- `year` / `primary_release_year`（可选；用于年份消歧）

响应要点：
- `results[]`：电影候选列表（含 `id/title/release_date/overview/vote_average` 等）

官方参考：
- https://developer.themoviedb.org/reference/search-movie

### 3) GET `/search/tv`（search-tv）

用途：
- 仅电视剧搜索（当 router 明确 `media_type_hint=tv` 时可使用）

请求（常用 Query）：
- `query`（必需）
- `language`
- `page`
- `first_air_date_year`（可选；用于年份消歧）

响应要点：
- `results[]`：电视剧候选（含 `id/name/first_air_date/overview/vote_average` 等）

官方参考：
- https://developer.themoviedb.org/reference/search-tv

### 4) GET `/search/person`（search-person）

用途：
- 仅人物搜索（导演/演员）

请求（常用 Query）：
- `query`（必需）
- `language`
- `page`

响应要点：
- `results[]`：人物候选（含 `id/name/known_for_department/known_for[]` 等）

官方参考：
- https://developer.themoviedb.org/reference/search-person

### 5) GET `/search/collection`（search-collection）

用途：
- 搜索电影合集（系列电影）

请求（常用 Query）：
- `query`（必需）
- `language`
- `page`

响应要点：
- `results[]`：合集候选（含 `id/name/overview/poster_path/backdrop_path` 等）

官方参考：
- https://developer.themoviedb.org/reference/search-collection

### 6) GET `/search/keyword`（search-keyword）

用途：
- 搜索关键词实体（keyword）

请求（常用 Query）：
- `query`（必需）
- `page`

响应要点：
- `results[]`：keyword 候选（含 `id/name`）

官方参考：
- https://developer.themoviedb.org/reference/search-keyword

### 7) GET `/search/company`（search-company）

用途：
- 搜索制作公司（出品方/制作方）

请求（常用 Query）：
- `query`（必需）
- `page`

响应要点：
- `results[]`：公司候选（含 `id/name/logo_path/origin_country` 等）

官方参考：
- https://developer.themoviedb.org/reference/search-company

说明（与本项目实现对齐）：
- 运行时 enrichment 当前优先使用 `/search/multi` 统一消歧；单类型 search 端点主要用于离线脚本或后续扩展。

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


## 官方 Reference 左侧栏目索引（全量）

本节按 TMDB 官方 Reference 左侧栏目（`/reference/getting-started` 页面导航）整理，用于保证‘有哪些 API’在本文档中都有落点。
- 链接为官方 reference 页面；端点的用途/参数/响应要点在本文其它章节会逐步补充与维护。
- 若官方页面新增/重命名端点：以官方为准，并回填本文档。

### Authentication

- https://developer.themoviedb.org/reference/authentication
- https://developer.themoviedb.org/reference/authentication-create-guest-session
- https://developer.themoviedb.org/reference/authentication-create-request-token
- https://developer.themoviedb.org/reference/authentication-create-session
- https://developer.themoviedb.org/reference/authentication-create-session-from-login
- https://developer.themoviedb.org/reference/authentication-create-session-from-v4-token
- https://developer.themoviedb.org/reference/authentication-delete-session
- https://developer.themoviedb.org/reference/authentication-how-do-i-generate-a-session-id
- https://developer.themoviedb.org/reference/authentication-validate-key

### Account

- https://developer.themoviedb.org/reference/account-add-favorite
- https://developer.themoviedb.org/reference/account-add-to-watchlist
- https://developer.themoviedb.org/reference/account-details
- https://developer.themoviedb.org/reference/account-favorite-tv
- https://developer.themoviedb.org/reference/account-get-favorites
- https://developer.themoviedb.org/reference/account-lists
- https://developer.themoviedb.org/reference/account-rated-movies
- https://developer.themoviedb.org/reference/account-rated-tv
- https://developer.themoviedb.org/reference/account-rated-tv-episodes
- https://developer.themoviedb.org/reference/account-watchlist-movies
- https://developer.themoviedb.org/reference/account-watchlist-tv

### Certifications

- https://developer.themoviedb.org/reference/certification-movie-list
- https://developer.themoviedb.org/reference/certifications-tv-list

### Changes

- https://developer.themoviedb.org/reference/changes-movie-list
- https://developer.themoviedb.org/reference/changes-people-list
- https://developer.themoviedb.org/reference/changes-tv-list

### Collections

- https://developer.themoviedb.org/reference/collection-details
- https://developer.themoviedb.org/reference/collection-images
- https://developer.themoviedb.org/reference/collection-translations

### Companies

- https://developer.themoviedb.org/reference/company-alternative-names
- https://developer.themoviedb.org/reference/company-details
- https://developer.themoviedb.org/reference/company-images

### Configuration

- https://developer.themoviedb.org/reference/configuration-countries
- https://developer.themoviedb.org/reference/configuration-details
- https://developer.themoviedb.org/reference/configuration-jobs
- https://developer.themoviedb.org/reference/configuration-languages
- https://developer.themoviedb.org/reference/configuration-primary-translations
- https://developer.themoviedb.org/reference/configuration-timezones

### Credits

- https://developer.themoviedb.org/reference/credit-details

### Discover

- https://developer.themoviedb.org/reference/discover-movie
- https://developer.themoviedb.org/reference/discover-tv

### Find

- https://developer.themoviedb.org/reference/find-by-id

### Genres

- https://developer.themoviedb.org/reference/genre-movie-list
- https://developer.themoviedb.org/reference/genre-tv-list

### Guest Sessions

- https://developer.themoviedb.org/reference/guest-session-rated-movies
- https://developer.themoviedb.org/reference/guest-session-rated-tv
- https://developer.themoviedb.org/reference/guest-session-rated-tv-episodes

### Keywords

- https://developer.themoviedb.org/reference/keyword-details
- https://developer.themoviedb.org/reference/keyword-movies

### Lists

- https://developer.themoviedb.org/reference/list-add-movie
- https://developer.themoviedb.org/reference/list-check-item-status
- https://developer.themoviedb.org/reference/list-clear
- https://developer.themoviedb.org/reference/list-create
- https://developer.themoviedb.org/reference/list-delete
- https://developer.themoviedb.org/reference/list-details
- https://developer.themoviedb.org/reference/list-remove-movie

### Movies

- https://developer.themoviedb.org/reference/movie-account-states
- https://developer.themoviedb.org/reference/movie-add-rating
- https://developer.themoviedb.org/reference/movie-alternative-titles
- https://developer.themoviedb.org/reference/movie-changes
- https://developer.themoviedb.org/reference/movie-credits
- https://developer.themoviedb.org/reference/movie-delete-rating
- https://developer.themoviedb.org/reference/movie-details
- https://developer.themoviedb.org/reference/movie-external-ids
- https://developer.themoviedb.org/reference/movie-images
- https://developer.themoviedb.org/reference/movie-keywords
- https://developer.themoviedb.org/reference/movie-latest-id
- https://developer.themoviedb.org/reference/movie-lists
- https://developer.themoviedb.org/reference/movie-now-playing-list
- https://developer.themoviedb.org/reference/movie-popular-list
- https://developer.themoviedb.org/reference/movie-recommendations
- https://developer.themoviedb.org/reference/movie-release-dates
- https://developer.themoviedb.org/reference/movie-reviews
- https://developer.themoviedb.org/reference/movie-similar
- https://developer.themoviedb.org/reference/movie-top-rated-list
- https://developer.themoviedb.org/reference/movie-translations
- https://developer.themoviedb.org/reference/movie-upcoming-list
- https://developer.themoviedb.org/reference/movie-videos
- https://developer.themoviedb.org/reference/movie-watch-providers

### People

- https://developer.themoviedb.org/reference/person-changes
- https://developer.themoviedb.org/reference/person-combined-credits
- https://developer.themoviedb.org/reference/person-details
- https://developer.themoviedb.org/reference/person-external-ids
- https://developer.themoviedb.org/reference/person-images
- https://developer.themoviedb.org/reference/person-latest-id
- https://developer.themoviedb.org/reference/person-movie-credits
- https://developer.themoviedb.org/reference/person-popular-list
- https://developer.themoviedb.org/reference/person-tagged-images
- https://developer.themoviedb.org/reference/person-tv-credits

### Search

- https://developer.themoviedb.org/reference/search-collection
- https://developer.themoviedb.org/reference/search-company
- https://developer.themoviedb.org/reference/search-keyword
- https://developer.themoviedb.org/reference/search-movie
- https://developer.themoviedb.org/reference/search-multi
- https://developer.themoviedb.org/reference/search-person
- https://developer.themoviedb.org/reference/search-tv

### Trending

- https://developer.themoviedb.org/reference/trending-all
- https://developer.themoviedb.org/reference/trending-movies
- https://developer.themoviedb.org/reference/trending-people
- https://developer.themoviedb.org/reference/trending-tv

### TV Series

- https://developer.themoviedb.org/reference/tv-series-account-states
- https://developer.themoviedb.org/reference/tv-series-add-rating
- https://developer.themoviedb.org/reference/tv-series-aggregate-credits
- https://developer.themoviedb.org/reference/tv-series-airing-today-list
- https://developer.themoviedb.org/reference/tv-series-alternative-titles
- https://developer.themoviedb.org/reference/tv-series-changes
- https://developer.themoviedb.org/reference/tv-series-content-ratings
- https://developer.themoviedb.org/reference/tv-series-credits
- https://developer.themoviedb.org/reference/tv-series-delete-rating
- https://developer.themoviedb.org/reference/tv-series-details
- https://developer.themoviedb.org/reference/tv-series-episode-groups
- https://developer.themoviedb.org/reference/tv-series-external-ids
- https://developer.themoviedb.org/reference/tv-series-images
- https://developer.themoviedb.org/reference/tv-series-keywords
- https://developer.themoviedb.org/reference/tv-series-latest-id
- https://developer.themoviedb.org/reference/tv-series-on-the-air-list
- https://developer.themoviedb.org/reference/tv-series-popular-list
- https://developer.themoviedb.org/reference/tv-series-recommendations
- https://developer.themoviedb.org/reference/tv-series-reviews
- https://developer.themoviedb.org/reference/tv-series-screened-theatrically
- https://developer.themoviedb.org/reference/tv-series-similar
- https://developer.themoviedb.org/reference/tv-series-top-rated-list
- https://developer.themoviedb.org/reference/tv-series-translations
- https://developer.themoviedb.org/reference/tv-series-videos
- https://developer.themoviedb.org/reference/tv-series-watch-providers

### TV Seasons

- https://developer.themoviedb.org/reference/tv-season-account-states
- https://developer.themoviedb.org/reference/tv-season-aggregate-credits
- https://developer.themoviedb.org/reference/tv-season-changes-by-id
- https://developer.themoviedb.org/reference/tv-season-credits
- https://developer.themoviedb.org/reference/tv-season-details
- https://developer.themoviedb.org/reference/tv-season-external-ids
- https://developer.themoviedb.org/reference/tv-season-images
- https://developer.themoviedb.org/reference/tv-season-translations
- https://developer.themoviedb.org/reference/tv-season-videos
- https://developer.themoviedb.org/reference/tv-season-watch-providers

### TV Episodes

- https://developer.themoviedb.org/reference/tv-episode-account-states
- https://developer.themoviedb.org/reference/tv-episode-add-rating
- https://developer.themoviedb.org/reference/tv-episode-changes-by-id
- https://developer.themoviedb.org/reference/tv-episode-credits
- https://developer.themoviedb.org/reference/tv-episode-delete-rating
- https://developer.themoviedb.org/reference/tv-episode-details
- https://developer.themoviedb.org/reference/tv-episode-external-ids
- https://developer.themoviedb.org/reference/tv-episode-group-details
- https://developer.themoviedb.org/reference/tv-episode-images
- https://developer.themoviedb.org/reference/tv-episode-translations
- https://developer.themoviedb.org/reference/tv-episode-videos

### Watch Providers

- https://developer.themoviedb.org/reference/watch-provider-tv-list
- https://developer.themoviedb.org/reference/watch-providers-available-regions
- https://developer.themoviedb.org/reference/watch-providers-movie-list

## 参考资料

- TMDB API v3 文档: https://developer.themoviedb.org/reference/getting-started
- TMDB API 状态: https://status.themoviedb.org/
- TMDB 开发者社区: https://www.themoviedb.org/talk

---

**文档版本**: 1.0
**最后更新**: 2026-01-27
**API 版本**: TMDB API v3
