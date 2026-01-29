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

### TRENDING（趋势内容 - 5 个端点）
| 端点 | 方法 | 描述 | 是否使用 |
|----------|--------|-------------|------|
| `/trending/{media_type}/{time_window}` | GET | 获取趋势内容（通用） | ✅ 推荐使用 |
| `/trending/all/{time_window}` | GET | 获取所有类型趋势 | ✅ 推荐使用 |
| `/trending/movie/{time_window}` | GET | 获取电影趋势 | ✅ 推荐使用 |
| `/trending/tv/{time_window}` | GET | 获取电视剧趋势 | ✅ 推荐使用 |
| `/trending/person/{time_window}` | GET | 获取人物趋势 | ✅ 推荐使用 |

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

## Genres 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/genre-movie-list
- https://developer.themoviedb.org/reference/genre-tv-list

用途：
- 获取所有电影/电视剧类型（Genre）列表
- 用于搜索过滤、分类展示、推荐系统
- **核心价值**：类型是内容分类的基础维度

### GET `/genre/movie/list`（电影类型列表）

**说明**：
- 获取所有电影类型（动作、喜剧、剧情、科幻等）
- 返回类型 ID 和名称的映射
- 支持多语言（类型名称会根据 `language` 参数本地化）

**请求参数**（Query）：
- `language`：语言，例如 `"zh-CN"` / `"en-US"`（默认：`"en-US"`）

**响应要点**：
```json
{
  "genres": [
    {
      "id": 28,
      "name": "Action"
    },
    {
      "id": 12,
      "name": "Adventure"
    },
    {
      "id": 16,
      "name": "Animation"
    },
    {
      "id": 35,
      "name": "Comedy"
    },
    {
      "id": 80,
      "name": "Crime"
    },
    {
      "id": 99,
      "name": "Documentary"
    },
    {
      "id": 18,
      "name": "Drama"
    },
    {
      "id": 10751,
      "name": "Family"
    },
    {
      "id": 14,
      "name": "Fantasy"
    },
    {
      "id": 36,
      "name": "History"
    },
    {
      "id": 27,
      "name": "Horror"
    },
    {
      "id": 10402,
      "name": "Music"
    },
    {
      "id": 9648,
      "name": "Mystery"
    },
    {
      "id": 10749,
      "name": "Romance"
    },
    {
      "id": 878,
      "name": "Science Fiction"
    },
    {
      "id": 10770,
      "name": "TV Movie"
    },
    {
      "id": 53,
      "name": "Thriller"
    },
    {
      "id": 10752,
      "name": "War"
    },
    {
      "id": 37,
      "name": "Western"
    }
  ]
}
```

**响应字段说明**：
- `genres[]`：类型列表
  - `id`：类型 ID（整数，用于搜索过滤）
  - `name`：类型名称（根据 `language` 参数本地化）

**官方参考**：
- https://developer.themoviedb.org/reference/genre-movie-list

---

### GET `/genre/tv/list`（电视剧类型列表）

**说明**：
- 获取所有电视剧类型
- 与电影类型基本一致，但略有差异（如 "Kids"、"News"、"Soap" 等）

**请求参数**（Query）：
- `language`：语言，例如 `"zh-CN"` / `"en-US"`（默认：`"en-US"`）

**响应要点**：
```json
{
  "genres": [
    {
      "id": 10759,
      "name": "Action & Adventure"
    },
    {
      "id": 16,
      "name": "Animation"
    },
    {
      "id": 35,
      "name": "Comedy"
    },
    {
      "id": 80,
      "name": "Crime"
    },
    {
      "id": 99,
      "name": "Documentary"
    },
    {
      "id": 18,
      "name": "Drama"
    },
    {
      "id": 10751,
      "name": "Family"
    },
    {
      "id": 10762,
      "name": "Kids"
    },
    {
      "id": 9648,
      "name": "Mystery"
    },
    {
      "id": 10763,
      "name": "News"
    },
    {
      "id": 10764,
      "name": "Reality"
    },
    {
      "id": 10765,
      "name": "Sci-Fi & Fantasy"
    },
    {
      "id": 10766,
      "name": "Soap"
    },
    {
      "id": 10767,
      "name": "Talk"
    },
    {
      "id": 10768,
      "name": "War & Politics"
    },
    {
      "id": 37,
      "name": "Western"
    }
  ]
}
```

**响应字段说明**：
- `genres[]`：类型列表
  - `id`：类型 ID
  - `name`：类型名称（根据 `language` 参数本地化）

**官方参考**：
- https://developer.themoviedb.org/reference/genre-tv-list

---

### 使用场景示例

#### 场景 1：获取类型列表并缓存

**需求**：系统启动时获取类型列表，并缓存在内存中

**实现**：
```python
import requests
from typing import Dict, List

class GenreCache:
    """类型缓存（单例）"""

    def __init__(self):
        self._movie_genres: Dict[int, str] = {}
        self._tv_genres: Dict[int, str] = {}

    def load_genres(self, language: str = "zh-CN"):
        """加载类型列表"""
        # 加载电影类型
        url = "https://api.themoviedb.org/3/genre/movie/list"
        params = {"api_key": TMDB_API_KEY, "language": language}
        response = requests.get(url, params=params)
        data = response.json()
        self._movie_genres = {g["id"]: g["name"] for g in data.get("genres", [])}

        # 加载电视剧类型
        url = "https://api.themoviedb.org/3/genre/tv/list"
        response = requests.get(url, params=params)
        data = response.json()
        self._tv_genres = {g["id"]: g["name"] for g in data.get("genres", [])}

    def get_movie_genre_name(self, genre_id: int) -> str:
        """获取电影类型名称"""
        return self._movie_genres.get(genre_id, "Unknown")

    def get_tv_genre_name(self, genre_id: int) -> str:
        """获取电视剧类型名称"""
        return self._tv_genres.get(genre_id, "Unknown")

# 全局缓存实例
genre_cache = GenreCache()

# 系统启动时加载
genre_cache.load_genres(language="zh-CN")
```

#### 场景 2：根据类型 ID 列表显示类型名称

**需求**：电影详情中包含 `genre_ids: [28, 12, 16]`，需要显示类型名称

**实现**：
```python
def format_genres(genre_ids: List[int], media_type: str = "movie") -> str:
    """
    格式化类型 ID 列表为类型名称

    Args:
        genre_ids: 类型 ID 列表
        media_type: "movie" 或 "tv"
    """
    genre_names = []
    for gid in genre_ids:
        if media_type == "movie":
            name = genre_cache.get_movie_genre_name(gid)
        else:
            name = genre_cache.get_tv_genre_name(gid)
        genre_names.append(name)

    return "、".join(genre_names)

# 示例
movie_genre_ids = [28, 12, 16]  # 动作、冒险、动画
genres_str = format_genres(movie_genre_ids, "movie")
print(f"类型：{genres_str}")
# 输出: 类型：动作、冒险、动画
```

#### 场景 3：按类型过滤搜索

**需求**：用户问"有哪些科幻电影？"，按类型过滤

**实现**：
```python
def search_movies_by_genre(genre_name: str, language: str = "zh-CN"):
    """
    按类型名称搜索电影

    Args:
        genre_name: 类型名称（如"科幻"、"喜剧"）
        language: 语言
    """
    # 1. 获取类型列表
    url = "https://api.themoviedb.org/3/genre/movie/list"
    params = {"api_key": TMDB_API_KEY, "language": language}
    response = requests.get(url, params=params)
    data = response.json()

    # 2. 查找匹配的类型 ID
    genre_id = None
    for genre in data.get("genres", []):
        if genre_name.lower() in genre["name"].lower():
            genre_id = genre["id"]
            break

    if not genre_id:
        return []

    # 3. 使用 Discover API 按类型过滤
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "language": language,
        "with_genres": genre_id,
        "sort_by": "popularity.desc",
        "page": 1
    }
    response = requests.get(url, params=params)
    data = response.json()

    return data.get("results", [])

# 示例
scifi_movies = search_movies_by_genre("科幻")
print(f"找到 {len(scifi_movies)} 部科幻电影")
```

#### 场景 4：多类型组合查询

**需求**：用户问"有哪些科幻动作片？"（同时满足多个类型）

**实现**：
```python
def search_movies_by_multiple_genres(genre_names: List[str], language: str = "zh-CN"):
    """
    按多个类型组合查询电影（AND 逻辑）

    Args:
        genre_names: 类型名称列表（如["科幻", "动作"]）
        language: 语言
    """
    # 1. 获取类型列表
    url = "https://api.themoviedb.org/3/genre/movie/list"
    params = {"api_key": TMDB_API_KEY, "language": language}
    response = requests.get(url, params=params)
    data = response.json()

    # 2. 查找匹配的类型 ID
    genre_ids = []
    for genre in data.get("genres", []):
        for genre_name in genre_names:
            if genre_name.lower() in genre["name"].lower():
                genre_ids.append(str(genre["id"]))

    if not genre_ids:
        return []

    # 3. 使用 Discover API，多个类型用逗号分隔（AND 逻辑）
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "language": language,
        "with_genres": ",".join(genre_ids),  # 如 "878,28"
        "sort_by": "popularity.desc",
        "page": 1
    }
    response = requests.get(url, params=params)
    data = response.json()

    return data.get("results", [])

# 示例
scifi_action_movies = search_movies_by_multiple_genres(["科幻", "动作"])
print(f"找到 {len(scifi_action_movies)} 部科幻动作片")
```

---

### 重要说明

1. **类型 ID 固定不变**：
   - 类型 ID 是全局唯一的，不会变更
   - 例如：`28` 永远代表 "Action"，`878` 永远代表 "Science Fiction"
   - **建议**：可在代码中硬编码常用类型 ID 映射

2. **语言本地化**：
   - 类型名称会根据 `language` 参数本地化
   - `"zh-CN"`：中文名称（如"动作"、"喜剧"）
   - `"en-US"`：英文名称（如"Action"、"Comedy"）
   - **建议**：根据用户语言偏好选择

3. **电影 vs 电视剧类型**：
   - 电影有 19 种类型（如 "Western"、"TV Movie"）
   - 电视剧有 16 种类型（如 "Kids"、"Soap"、"Talk"）
   - 部分类型 ID 相同（如 `16` = "Animation"）
   - 部分类型 ID 不同（如电影 `28` = "Action"，电视剧 `10759` = "Action & Adventure"）

4. **Discover API 集成**：
   - 类型 ID 主要用于 Discover API 的 `with_genres` 参数
   - 支持单类型过滤：`with_genres=28`
   - 支持多类型过滤（AND 逻辑）：`with_genres=28,878`（科幻 + 动作）
   - 支持排除类型：`without_genres=99`（排除纪录片）

5. **缓存策略**：
   - 类型列表变化频率极低，**建议全局缓存**
   - 可在系统启动时加载一次，之后无需重复请求
   - 避免每次查询电影时都调用类型端点

6. **常见类型 ID 速查**：

   **电影类型**：
   | ID | 英文名称 | 中文名称 |
   |----|---------|---------|
   | 28 | Action | 动作 |
   | 12 | Adventure | 冒险 |
   | 16 | Animation | 动画 |
   | 35 | Comedy | 喜剧 |
   | 80 | Crime | 犯罪 |
   | 99 | Documentary | 纪录片 |
   | 18 | Drama | 剧情 |
   | 14 | Fantasy | 奇幻 |
   | 27 | Horror | 恐怖 |
   | 878 | Science Fiction | 科幻 |
   | 10749 | Romance | 爱情 |
   | 53 | Thriller | 惊悚 |

   **电视剧类型**：
   | ID | 英文名称 | 中文名称 |
   |----|---------|---------|
   | 10759 | Action & Adventure | 动作与冒险 |
   | 16 | Animation | 动画 |
   | 35 | Comedy | 喜剧 |
   | 80 | Crime | 犯罪 |
   | 99 | Documentary | 纪录片 |
   | 18 | Drama | 剧情 |
   | 10751 | Family | 家庭 |
   | 10765 | Sci-Fi & Fantasy | 科幻与奇幻 |

---

### 端点对比

| 端点 | 返回内容 | 支持语言 | 调用频率 |
|------|---------|---------|---------|
| `/genre/movie/list` | 电影类型列表（19 种） | ✅ | 一次性（缓存） |
| `/genre/tv/list` | 电视剧类型列表（16 种） | ✅ | 一次性（缓存） |

---

### 与其他端点的集成

1. **Movie Details**：
   - 电影详情返回 `genre_ids[]` 数组
   - 需要结合类型列表将 ID 转换为名称

2. **Discover API**：
   - `with_genres={genre_id}`：按类型过滤
   - `without_genres={genre_id}`：排除某类型

3. **Search API**：
   - 搜索结果包含 `genre_ids[]`
   - 同样需要类型列表映射

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

**说明**：
- 获取电影在各外部数据库的 ID 映射
- 支持与 IMDb、TVDB、Wikidata 等数据源对齐

**请求参数**（Path）：
- `movie_id`（Path）：电影 ID

**响应要点**：
```json
{
  "id": 278,
  "imdb_id": "tt0111161",
  "tvdb_id": 1120,
  "wikidata_id": 25086,
  "facebook_id": "TheShawshankRedemption",
  "instagram_id": "shawshankredemptionfilm",
  "twitter_id": "ShawshankRedemption"
}
```

**核心用途**：
- 跨数据源去重（通过 IMDb ID）
- 整合第三方评分（IMDb、Douban 等）

官方参考：
- https://developer.themoviedb.org/reference/movie-external-ids

### 2) GET `/movie/{movie_id}/images`（movie-images）

**说明**：
- 获取电影的所有图片资源
- 包括海报、背景图、logo 等

**请求参数**（Query）：
- `include_image_language`：图片语言过滤（如 `"zh,null"`）

**响应要点**：
```json
{
  "id": 278,
  "backdrops": [
    {
      "file_path": "/path.jpg",
      "width": 1920,
      "height": 1080,
      "vote_average": 5.6
    }
  ],
  "posters": [...],
  "logos": [...]
}
```

**核心用途**：
- 前端展示封面、背景图
- 轮播展示高质量图片

官方参考：
- https://developer.themoviedb.org/reference/movie-images

### 3) GET `/movie/{movie_id}/keywords`（movie-keywords）

**说明**：
- 获取电影的关键词标签
- 用于主题推荐、相似度计算、标签展示

**请求参数**（Path）：
- `movie_id`（Path）：电影 ID

**响应要点**：
```json
{
  "id": 278,
  "keywords": [
    {"id": 1521, "name": "prison"},
    {"id": 1523, "name": "friendship"},
    {"id": 1525, "name": "hope"}
  ]
}
```

**核心用途**：
- 标签推荐（"关于监狱的电影"）
- 相似度计算（基于关键词重叠度）
- 主题聚合

官方参考：
- https://developer.themoviedb.org/reference/movie-keywords

### 4) GET `/movie/latest`（movie-latest-id）

**说明**：
- 获取最新创建的电影记录
- 注意：不是"最新上映"，而是最新添加到 TMDB 的电影

**请求参数**（Query）：
- `language`：语言（可选）

**响应要点**：
```json
{
  "id": 123456,
  "title": "Latest Movie Title",
  "release_date": "2024-01-15",
  "overview": "简介..."
}
```

**核心用途**：
- 测试 API 连接
- 获取最新电影 ID（开发/调试）

官方参考：
- https://developer.themoviedb.org/reference/movie-latest-id

### 5) GET `/movie/{movie_id}/lists`（movie-lists）

**说明**：
- 获取包含该电影的 TMDB 公共列表
- 用于发现相关电影合集、用户榜单

**请求参数**（Query）：
- `language`：语言
- `page`：页码

**响应要点**：
```json
{
  "id": 278,
  "results": [
    {
      "description": "经典电影合集",
      "favorite_count": 1500,
      "id": 12345,
      "item_count": 100,
      "list_type": "movie",
      "name": "Best Movies of All Time",
      "poster_path": "/poster.jpg"
    }
  ]
}
```

**核心用途**：
- 发现相关电影合集
- 用户榜单展示

官方参考：
- https://developer.themoviedb.org/reference/movie-lists

### 6) GET `/movie/{movie_id}/recommendations`（movie-recommendations）

**说明**：
- 获取推荐电影（基于协同过滤）
- 适合"看完该片还可看什么"场景

**请求参数**（Query）：
- `language`：语言
- `page`：页码

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "id": 238,
      "title": "电影标题",
      "release_date": "1994-09-10",
      "vote_average": 8.5
    }
  ]
}
```

**核心用途**：
- 推荐增强（协同过滤）
- 冷启动推荐

官方参考：
- https://developer.themoviedb.org/reference/movie-recommendations

### 7) GET `/movie/{movie_id}/similar`（movie-similar）

**说明**：
- 获取相似电影（基于内容相似度）
- 适合"类似该片的电影"场景

**请求参数**（Query）：
- `language`：语言
- `page`：页码

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "id": 278,
      "title": "肖申克的救赎",
      "vote_average": 8.7
    }
  ]
}
```

**核心用途**：
- 相似推荐（内容相似度）
- 相似度特征工程

官方参考：
- https://developer.themoviedb.org/reference/movie-similar

### 8) GET `/movie/{movie_id}/release_dates`（movie-release-dates）

**说明**：
- 获取各地区的上映日期、分级等信息
- 用于地区化上映信息展示

**请求参数**（Path）：
- `movie_id`（Path）：电影 ID

**响应要点**：
```json
{
  "id": 278,
  "results": [
    {
      "iso_3166_1": "US",
      "release_dates": [
        {
          "certification": "R",
          "iso_639_1": "en",
          "note": "",
          "release_date": "1994-09-23T00:00:00.000Z",
          "type": 3
        }
      ]
    }
  ]
}
```

**核心用途**：
- 地区化上映信息
- 分级查询（如美国 R 级）
- 上映日期对比

**type 字段说明**：
- 1: Premiere（首映）
- 2: Theatrical（影院上映）
- 3: Digital（数字发行）
- 4: Physical（物理介质）
- 5: TV（电视播出）

官方参考：
- https://developer.themoviedb.org/reference/movie-release-dates

### 9) GET `/movie/{movie_id}/reviews`（movie-reviews）

**说明**：
- 获取用户评论（详见"Reviews 端点"章节）

**请求参数**（Query）：
- `language`：语言
- `page`：页码

**响应要点**：
- `results[]`：评论列表（含 author/content/rating 等）

**核心用途**：
- 用户观点展示
- 情感分析、评论摘要

官方参考：
- https://developer.themoviedb.org/reference/movie-reviews

**详细文档**：参见"Reviews 端点对齐"章节

### 10) GET `/movie/{movie_id}/translations`（movie-translations）

**说明**：
- 获取电影的多语言标题和简介
- 用于语言回退、多语言展示

**请求参数**：无（仅需 `movie_id`）

**响应要点**：
```json
{
  "id": 278,
  "translations": [
    {
      "iso_639_1": "zh",
      "iso_3166_1": "CN",
      "name": "Chinese",
      "english_name": "Chinese",
      "data": {
        "title": "肖申克的救赎",
        "overview": "一场关于希望与友谊的经典故事..."
      }
    },
    {
      "iso_639_1": "en",
      "data": {
        "title": "The Shawshank Redemption",
        "overview": "Two imprisoned men bond..."
      }
    }
  ]
}
```

**核心用途**：
- 多语言标题/简介回退
- 国际化支持

官方参考：
- https://developer.themoviedb.org/reference/movie-translations

### 11) GET `/movie/{movie_id}/videos`（movie-videos）

**说明**：
- 获取电影的视频资源（预告片、片段、花絮等）
- 主要来自 YouTube、Vimeo 等平台

**请求参数**（Query）：
- `language`：语言过滤

**响应要点**：
```json
{
  "id": 278,
  "results": [
    {
      "iso_639_1": "en",
      "iso_3166_1": "US",
      "name": "Official Trailer",
      "key": "K_3tCv0JYHw",
      "site": "YouTube",
      "size": 1080,
      "type": "Trailer",
      "official": true,
      "published_at": "2014-10-02T19:20:22.000Z",
      "id": "65a1b2c3d4e5f6g7h8i9j0k"
    }
  ]
}
```

**核心字段说明**：
- `key`：视频 ID（用于构造 URL）
- `site`：视频平台（YouTube/Vimeo 等）
- `type`：视频类型（Trailer/Teaser/Clip/Featurette 等）
- `official`：是否官方视频
- `size`：视频分辨率（360/480/720/1080）

**核心用途**：
- 前端展示预告片
- 视频播放器集成

**视频 URL 构造**：
- YouTube: `https://www.youtube.com/watch?v={key}`
- YouTube 嵌入: `https://www.youtube.com/embed/{key}`

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

## Reviews 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/movie-reviews
- https://developer.themoviedb.org/reference/tv-reviews

用途：
- 获取电影/电视剧的用户评论内容
- 用于情感分析、评论摘要、用户观点聚合
- **核心价值**：评论是理解用户反馈的重要数据源

### GET `/movie/{movie_id}/reviews`（电影评论列表）

**说明**：
- 获取指定电影的用户评论
- 评论来自 TMDB 注册用户
- 适合"这部电影口碑如何"、"用户评价"等场景

**请求参数**（Path + Query）：
- `movie_id`（Path）：电影 ID
- `language`：语言，例如 `"zh-CN"` / `"en-US"`（过滤评论语言）
- `page`：页码（默认 `1`）

**响应要点**：
```json
{
  "id": 278,
  "page": 1,
  "results": [
    {
      "author": "username",
      "author_details": {
        "name": "Full Name",
        "username": "username",
        "avatar_path": "/avatar.jpg",
        "rating": 9.0
      },
      "content": "这是一部关于希望和友谊的经典电影。Tim Robbins 和 Morgan Freeman 的表演令人难忘...",
      "created_at": "2023-01-15T10:30:00.000Z",
      "updated_at": "2023-01-15T10:30:00.000Z",
      "id": "65a1b2c3d4e5f6g7h8i9j0k"
    }
  ],
  "total_pages": 5,
  "total_results": 100
}
```

**响应字段说明**：
- `results[]`：评论列表
  - `author`：作者用户名
  - `author_details`：作者详细信息
    - `name`：作者姓名
    - `username`：用户名
    - `avatar_path`：头像路径
    - `rating`：作者评分（0-10，可能为 `null`）
  - `content`：**评论内容**（核心字段）
  - `created_at`：评论创建时间（ISO 8601 格式）
  - `updated_at`：评论更新时间
  - `id`：评论 ID
- `total_pages`：总页数
- `total_results`：总评论数

**官方参考**：
- https://developer.themoviedb.org/reference/movie-reviews

---

### GET `/tv/{series_id}/reviews`（电视剧评论列表）

**说明**：
- 获取指定电视剧的用户评论
- 结构与电影版本完全一致

**请求参数**（Path + Query）：
- `series_id`（Path）：电视剧 ID
- `language`：语言过滤
- `page`：页码

**响应要点**：
```json
{
  "id": 1396,
  "page": 1,
  "results": [
    {
      "author": "breakingbadfan",
      "author_details": {
        "name": "Fan Name",
        "username": "breakingbadfan",
        "avatar_path": "/avatar2.jpg",
        "rating": 10.0
      },
      "content": "有史以来最好的电视剧之一。剧情紧凑，角色发展完整...",
      "created_at": "2023-02-20T14:20:00.000Z",
      "updated_at": "2023-02-20T14:20:00.000Z",
      "id": "6a5b4c3d2e1f0g9h8i7j6k5"
    }
  ],
  "total_pages": 3,
  "total_results": 50
}
```

**官方参考**：
- https://developer.themoviedb.org/reference/tv-reviews

---

### 使用场景示例

#### 场景 1：获取电影评论并分析情感

**需求**：获取电影评论，分析用户情感倾向

**实现**：
```python
import requests

def get_movie_reviews(movie_id: int, language: str = "en-US", page: int = 1):
    """获取电影评论"""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/reviews"
    params = {
        "api_key": TMDB_API_KEY,
        "language": language,
        "page": page
    }
    response = requests.get(url, params=params)
    return response.json()

def analyze_reviews_sentiment(movie_id: int):
    """分析评论情感"""
    data = get_movie_reviews(movie_id)
    reviews = data.get("results", [])

    if not reviews:
        return {"total": 0, "with_rating": 0, "avg_rating": 0}

    # 统计有评分的评论
    rated_reviews = [r for r in reviews if r["author_details"]["rating"] is not None]

    # 计算平均评分
    total_rating = sum(r["author_details"]["rating"] for r in rated_reviews)
    avg_rating = total_rating / len(rated_reviews) if rated_reviews else 0

    return {
        "total": len(reviews),
        "with_rating": len(rated_reviews),
        "avg_rating": round(avg_rating, 1)
    }

# 示例
stats = analyze_reviews_sentiment(278)
print(f"评论数: {stats['total']}, 有评分: {stats['with_rating']}, 平均分: {stats['avg_rating']}")
```

#### 场景 2：生成评论摘要

**需求**：从多条评论中提取关键观点，生成摘要

**实现**：
```python
from collections import Counter
import re

def extract_keywords(text: str) -> list:
    """提取关键词（简化版）"""
    # 简单分词（实际应使用 NLP 库）
    words = re.findall(r'\b\w{3,}\b', text.lower())
    # 过滤停用词
    stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'with', 'this', 'that'}
    return [w for w in words if w not in stopwords]

def generate_review_summary(movie_id: int, top_n: int = 10):
    """生成评论摘要（关键词聚合）"""
    data = get_movie_reviews(movie_id)
    reviews = data.get("results", [])

    # 提取所有评论内容
    all_text = " ".join([r["content"] for r in reviews])

    # 提取关键词
    keywords = extract_keywords(all_text)

    # 统计词频
    keyword_freq = Counter(keywords)

    # 返回 Top N 关键词
    return keyword_freq.most_common(top_n)

# 示例
summary = generate_review_summary(278)
print("高频关键词:")
for word, freq in summary:
    print(f"  {word}: {freq}次")
```

#### 场景 3：过滤高评分评论

**需求**：获取用户评分 ≥ 8.0 的正面评论

**实现**：
```python
def get_positive_reviews(movie_id: int, min_rating: float = 8.0, limit: int = 10):
    """获取正面评论"""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/reviews"
    params = {"api_key": TMDB_API_KEY, "page": 1}
    response = requests.get(url, params=params)
    data = response.json()

    reviews = data.get("results", [])

    # 过滤评分 >= min_rating 的评论
    positive_reviews = [
        r for r in reviews
        if r["author_details"]["rating"] is not None
        and r["author_details"]["rating"] >= min_rating
    ]

    # 返回前 limit 条
    return positive_reviews[:limit]

# 示例
positive = get_positive_reviews(278, min_rating=8.0)
print(f"找到 {len(positive)} 条正面评论")
for review in positive:
    print(f"- {review['author']}: {review['content'][:50]}...")
```

#### 场景 4：按语言过滤评论

**需求**：只获取中文评论

**实现**：
```python
def get_reviews_by_language(movie_id: int, language: str = "zh-CN"):
    """获取指定语言的评论"""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/reviews"
    params = {"api_key": TMDB_API_KEY, "language": language}
    response = requests.get(url, params=params)
    data = response.json()

    reviews = data.get("results", [])
    return reviews

# 示例
chinese_reviews = get_reviews_by_language(278, "zh-CN")
print(f"中文评论数: {len(chinese_reviews)}")
```

---

### 重要说明

1. **评论数量**：
   - 部分电影可能没有评论（`results: []`）
   - 热门电影评论较多，冷门电影可能很少
   - 单页最多返回 20 条评论

2. **评论质量**：
   - 评论来自 TMDB 用户，质量参差不齐
   - 部分评论可能为简短的一句话
   - 建议过滤评论长度（如 `len(content) > 50`）

3. **评分可用性**：
   - `author_details.rating` 可能为 `null`（用户未打分）
   - 仅部分评论包含评分
   - 评分范围：0-10

4. **语言过滤**：
   - `language` 参数过滤评论语言（基于用户设置）
   - 注意：评论语言可能与 `language` 参数不完全匹配
   - 建议结合内容语言检测

5. **时间信息**：
   - `created_at`：评论创建时间（ISO 8601）
   - `updated_at`：评论最后更新时间
   - 可用于过滤旧评论

6. **情感分析**：
   - 评论内容可用于情感分析（正面/负面）
   - 可结合 `rating` 字段进行训练
   - 建议使用 NLP 库（如 TextBlob、VADER）

7. **分页处理**：
   - 如需更多评论，使用 `page` 参数
   - 注意 API 限流（建议延迟请求）

---

### 端点对比

| 端点 | 适用对象 | 评论数量 | 语言过滤 |
|------|---------|---------|---------|
| `/movie/{id}/reviews` | 电影 | 0-1000+ | ✅ |
| `/tv/{id}/reviews` | 电视剧 | 0-500+ | ✅ |

---

### 与其他端点的集成

1. **Movie Details**：
   - 电影详情包含 `vote_average`（所有用户平均评分）
   - Reviews 提供详细的评论内容

2. **Ratings**：
   - TMDB 评分：`vote_average`（0-10）
   - 用户评分：`author_details.rating`（0-10）
   - 可对比两者差异

---

## Collections 端点对齐（官方 Reference）

本节对齐官方 Reference（示例页面：`/reference/collection-details`），补全 COLLECTIONS 相关端点的“参数/响应要点”，便于后续实现：
- 电影合集详情展示（系列电影，如 “The Lord of the Rings Collection”）
- 电影合集封面/背景图拉取（前端展示）
- 合集翻译（多语言）

注意：截至本文档更新，Collections 端点**在运行时 enrichment 中未使用**，因此这里属于“预备对齐”，用于后续产品能力扩展。

### 1) GET `/collection/{collection_id}`（合集详情）

**说明**：
- 获取电影合集的基本信息和包含的所有影片
- 适合系列电影，如《指环王》、《哈利波特》、《复仇者联盟》等

**请求参数**：
- **Path**：
  - `collection_id`（必需）：合集 ID
- **Query**：
  - `language`（可选）：语言，如 `"zh-CN"` / `"en-US"`

**响应示例**：
```json
{
  "id": 86311,
  "name": "The Avengers Collection",
  "overview": "A superhero film series produced by Marvel Studios...",
  "poster_path": "/collection_path.jpg",
  "backdrop_path": "/backdrop_path.jpg",
  "parts": [
    {
      "adult": false,
      "backdrop_path": "/movie1_backdrop.jpg",
      "genre_ids": [28, 12, 878],
      "id": 24428,
      "original_language": "en",
      "original_title": "The Avengers",
      "overview": "Earth's mightiest heroes must come together...",
      "poster_path": "/movie1_poster.jpg",
      "release_date": "2012-05-04",
      "title": "复仇者联盟",
      "vote_average": 7.66,
      "vote_count": 35000
    },
    {
      "id": 99861,
      "title": "Avengers: Age of Ultron",
      "release_date": "2015-05-01",
      "vote_average": 7.4,
      "overview": "When Tony Stark and Bruce Banner try to..."
    },
    {
      "id": 271110,
      "title": "Avengers: Infinity War",
      "release_date": "2018-04-27",
      "vote_average": 8.3,
      "overview": "The Avengers must stop Thanos..."
    },
    {
      "id": 299536,
      "title": "Avengers: Endgame",
      "release_date": "2019-04-26",
      "vote_average": 8.4,
      "overview": "After the devastating events of Infinity War..."
    }
  ]
}
```

**核心字段说明**：
- `id`：合集 ID（可用于查询合集图片、翻译等）
- `name`：合集名称
- `overview`：合集简介
- `poster_path` / `backdrop_path`：合集封面/背景图
- `parts[]`：合集内影片列表（按上映日期排序）
  - 每部影片包含完整信息（id、title、release_date、vote_average 等）

**核心用途**：
- 系列电影展示（如《指环王》系列）
- 观影顺序引导
- 系列电影推荐

**官方参考**：
- https://developer.themoviedb.org/reference/collection-details

### 2) GET `/collection/{collection_id}/images`（合集图片）

**说明**：
- 获取电影合集的图片资源（海报、背景图）
- 供前端展示合集封面、背景图

**请求参数**：
- **Path**：
  - `collection_id`（必需）：合集 ID
- **Query**：
  - `language`（可选）：语言过滤
  - `include_image_language`（可选）：例如 `"zh,null"`（包含无语言标注图片）

**响应示例**：
```json
{
  "id": 86311,
  "backdrops": [
    {
      "file_path": "/backdrop1.jpg",
      "width": 1920,
      "height": 1080,
      "aspect_ratio": 1.777,
      "vote_average": 5.8,
      "vote_count": 12
    }
  ],
  "posters": [
    {
      "file_path": "/poster1.jpg",
      "width": 1000,
      "height": 1500,
      "aspect_ratio": 0.667,
      "vote_average": 6.2,
      "vote_count": 20
    }
  ]
}
```

**核心字段说明**：
- `backdrops[]`：背景图列表
  - `file_path`：图片文件路径
  - `width` / `height`：图片尺寸
  - `aspect_ratio`：宽高比（通常为 1.777，即 16:9）
  - `vote_average`：图片质量评分
- `posters[]`：海报列表
  - `aspect_ratio`：宽高比（通常为 0.667，即 2:3）

**核心用途**：
- 前端展示合集封面、背景图
- 合集轮播图展示

**官方参考**：
- https://developer.themoviedb.org/reference/collection-images

### 3) GET `/collection/{collection_id}/translations`（合集翻译）

**说明**：
- 获取电影合集的多语言标题和简介
- 用于多语言 UI 展示或翻译回退策略

**请求参数**：
- **Path**：
  - `collection_id`（必需）：合集 ID

**响应示例**：
```json
{
  "id": 86311,
  "translations": [
    {
      "iso_639_1": "zh",
      "iso_3166_1": "CN",
      "name": "Chinese",
      "english_name": "Chinese",
      "data": {
        "name": "复仇者联盟系列",
        "overview": "漫威影业制作的超级英雄电影系列..."
      }
    },
    {
      "iso_639_1": "en",
      "iso_3166_1": "US",
      "name": "English",
      "english_name": "English",
      "data": {
        "name": "The Avengers Collection",
        "overview": "A superhero film series produced by Marvel Studios..."
      }
    }
  ]
}
```

**核心字段说明**：
- `translations[]`：翻译列表
  - `iso_639_1`：语言代码（如 `"zh"`、`"en"`）
  - `iso_3166_1`：国家代码（如 `"CN"`、`"US"`）
  - `data.name`：翻译后的合集名称
  - `data.overview`：翻译后的合集简介

**核心用途**：
- 多语言 UI 展示
- 翻译回退（优先显示用户语言，无则回退到英语）

**官方参考**：
- https://developer.themoviedb.org/reference/collection-translations

---

### 使用场景示例

#### 场景 1：展示系列电影的所有作品

**需求**：用户问"复仇者联盟系列有哪些电影？"，展示系列电影列表

**实现**：
```python
import requests

def get_collection_movies(collection_id: int, language: str = "zh-CN"):
    """获取合集内所有电影"""
    url = f"https://api.themoviedb.org/3/collection/{collection_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": language
    }
    response = requests.get(url, params=params)
    data = response.json()

    # 提取电影列表
    movies = data.get("parts", [])

    # 按上映日期排序
    movies.sort(key=lambda x: x.get("release_date", ""))

    return [
        {
            "id": m["id"],
            "title": m["title"],
            "release_date": m.get("release_date"),
            "vote_average": m.get("vote_average"),
            "overview": m.get("overview")
        }
        for m in movies
    ]

# 示例：复仇者联盟系列（Collection ID: 86311）
movies = get_collection_movies(86311)
print(f"《复仇者联盟》系列共 {len(movies)} 部电影：")
for i, movie in enumerate(movies, 1):
    print(f"{i}. {movie['title']} ({movie['release_date']}) - 评分: {movie['vote_average']}")
```

#### 场景 2：推荐观影顺序

**需求**：为用户提供系列电影的观影顺序

**实现**：
```python
def get_watch_order(collection_id: int, language: str = "zh-CN"):
    """获取观影顺序（按上映日期）"""
    url = f"https://api.themoviedb.org/3/collection/{collection_id}"
    params = {"api_key": TMDB_API_KEY, "language": language}
    response = requests.get(url, params=params)
    data = response.json()

    movies = data.get("parts", [])

    # 按上映日期排序
    movies.sort(key=lambda x: x.get("release_date", ""))

    # 生成观影顺序
    watch_order = []
    for i, movie in enumerate(movies, 1):
        watch_order.append({
            "order": i,
            "title": movie["title"],
            "release_date": movie.get("release_date"),
            "runtime": movie.get("runtime"),  # 时长（分钟）
            "vote_average": movie.get("vote_average")
        })

    return watch_order

# 示例
watch_order = get_watch_order(86311)
print("复仇者联盟观影顺序：")
for item in watch_order:
    print(f"{item['order']}. {item['title']} - {item['release_date']}")
```

#### 场景 3：计算系列电影平均评分

**需求**：计算整个系列电影的平均评分

**实现**：
```python
def get_collection_stats(collection_id: int, language: str = "zh-CN"):
    """获取合集统计信息"""
    url = f"https://api.themoviedb.org/3/collection/{collection_id}"
    params = {"api_key": TMDB_API_KEY, "language": language}
    response = requests.get(url, params=params)
    data = response.json()

    movies = data.get("parts", [])

    # 计算平均评分
    ratings = [m.get("vote_average", 0) for m in movies if m.get("vote_average")]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    # 找出评分最高和最低
    best_movie = max(movies, key=lambda x: x.get("vote_average", 0))
    worst_movie = min(movies, key=lambda x: x.get("vote_average", 0))

    return {
        "collection_name": data.get("name"),
        "total_movies": len(movies),
        "avg_rating": round(avg_rating, 1),
        "best_movie": {
            "title": best_movie["title"],
            "rating": best_movie.get("vote_average")
        },
        "worst_movie": {
            "title": worst_movie["title"],
            "rating": worst_movie.get("vote_average")
        }
    }

# 示例
stats = get_collection_stats(86311)
print(f"合集：{stats['collection_name']}")
print(f"电影数量：{stats['total_movies']}")
print(f"平均评分：{stats['avg_rating']}")
print(f"最高评分：{stats['best_movie']['title']} ({stats['best_movie']['rating']})")
print(f"最低评分：{stats['worst_movie']['title']} ({stats['worst_movie']['rating']})")
```

#### 场景 4：获取合集多语言名称

**需求**：获取合集的中英文名称

**实现**：
```python
def get_collection_translations(collection_id: int):
    """获取合集多语言名称"""
    url = f"https://api.themoviedb.org/3/collection/{collection_id}/translations"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    data = response.json()

    translations = data.get("translations", [])

    # 提取中英文名称
    names = {}
    for t in translations:
        iso = t.get("iso_639_1")
        name = t.get("data", {}).get("name")
        if name:
            names[iso] = name

    return {
        "zh": names.get("zh"),
        "en": names.get("en")
    }

# 示例
names = get_collection_translations(86311)
print(f"中文名：{names['zh']}")
print(f"英文名：{names['en']}")
```

---

### 重要说明

1. **Collection ID 获取**：
   - 电影详情中包含 `belongs_to_collection` 字段
   - 结构为：`{"id": 86311, "name": "The Avengers Collection"}`
   - 如果电影不属于任何合集，此字段为 `null`

2. **parts 字段排序**：
   - `parts[]` 默认可能不按上映日期排序
   - **建议**：前端按 `release_date` 重新排序

3. **合集 vs 单部电影**：
   - Collection（合集）：系列电影集合
   - Movie（电影）：单部电影
   - 一部电影只能属于一个合集

4. **常见电影合集**：
   - **漫威电影宇宙**：
     - The Avengers Collection（复仇者联盟系列）
     - Iron Man Collection（钢铁侠系列）
     - Captain America Collection（美国队长系列）
   - **DC 宇宙**：
     - The Dark Knight Trilogy（蝙蝠侠黑暗骑士三部曲）
   - **经典系列**：
     - The Lord of the Rings Collection（指环王系列）
     - Harry Potter Collection（哈利波特系列）
     - Star Wars Saga（星球大战系列）

5. **图片 URL 构造**：
   - 使用 `/configuration` 端点获取 `base_url`
   - 完整 URL：`{base_url}{size}{file_path}`
   - 合集海报推荐尺寸：`w500`、`w780`

6. **翻译回退策略**：
   - 优先显示用户语言（如 `zh-CN`）
   - 无则回退到英语（`en-US`）
   - 再无则使用合集原始名称

---

### 端点对比

| 端点 | 返回内容 | 主要用途 | 调用频率 |
|------|---------|---------|---------|
| `/collection/{id}` | 合集详情 + 电影列表 | 系列电影展示 | 按需 |
| `/collection/{id}/images` | 合集图片 | 前端展示封面 | 按需 |
| `/collection/{id}/translations` | 多语言翻译 | 国际化支持 | 按需 |

---

### 与其他端点的集成

1. **Movie Details**：
   - 电影详情包含 `belongs_to_collection` 字段
   - 可用于发现同一系列的其他电影

2. **Discover API**：
   - 可通过合集 ID 过滤：`with_collection={collection_id}`
   - 用于查找合集内所有电影

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

## Trending 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/trending-all
- https://developer.themoviedb.org/reference/trending-movies
- https://developer.themoviedb.org/reference/trending-tv
- https://developer.themoviedb.org/reference/trending-people

用途：
- 获取热门/趋势内容（日榜/周榜），用于"最近热门电影"、"本周热门电视剧"、"当下热门人物"等推荐场景
- 作为冷启动推荐、首页内容流、热门榜单的数据源

### 1) GET `/trending/{media_type}/{time_window}`（通用趋势端点）

**说明**：
- 通用趋势端点，支持按媒体类型和时间窗口获取趋势内容

**请求参数**：
- Path（必需）：
  - `media_type`：媒体类型
    - `"all"`：所有类型（电影 + 电视剧 + 人物）
    - `"movie"`：电影
    - `"tv"`：电视剧
    - `"person"`：人物
  - `time_window`：时间窗口
    - `"day"`：日榜（24小时）
    - `"week"`：周榜（7天）
- Query（常用）：
  - `language`：语言，例如 `"zh-CN"` / `"en-US"`
  - `page`：页码（默认 `1`）

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "adult": false,
      "backdrop_path": "/path.jpg",
      "id": 12345,
      "title": "电影标题",           // movie 类型
      "original_language": "en",
      "original_title": "Original Title",
      "overview": "简介",
      "poster_path": "/poster.jpg",
      "media_type": "movie",
      "genre_ids": [28, 12, 878],
      "popularity": 1234.56,
      "release_date": "2024-01-01",
      "video": false,
      "vote_average": 8.5,
      "vote_count": 1000
    },
    {
      "adult": false,
      "backdrop_path": "/path.jpg",
      "id": 67890,
      "name": "电视剧名称",           // tv 类型
      "original_language": "en",
      "original_name": "Original Name",
      "overview": "简介",
      "poster_path": "/poster.jpg",
      "media_type": "tv",
      "genre_ids": [18, 10765],
      "popularity": 987.65,
      "first_air_date": "2024-01-01",
      "origin_country": ["US"],
      "vote_average": 8.2,
      "vote_count": 800
    },
    {
      "id": 11111,
      "name": "人物姓名",             // person 类型
      "original_name": "Original Name",
      "media_type": "person",
      "known_for": [
        {
          "adult": false,
          "backdrop_path": "/path.jpg",
          "id": 22222,
          "title": "代表作1",
          "original_language": "en",
          "original_title": "Original Title 1",
          "overview": "简介",
          "poster_path": "/poster1.jpg",
          "media_type": "movie",
          "genre_ids": [28],
          "popularity": 543.21,
          "release_date": "2023-01-01",
          "video": false,
          "vote_average": 7.8,
          "vote_count": 500
        }
      ],
      "known_for_department": "Acting",
      "profile_path": "/profile.jpg",
      "popularity": 432.10
    }
  ],
  "total_pages": 100,
  "total_results": 2000
}
```

**响应字段说明**：
- `results[]`：趋势内容数组
  - 通用字段（所有类型）：
    - `id`：TMDB ID
    - `media_type`：`"movie"` / `"tv"` / `"person"`
    - `popularity`：热度值（越高越热门）
    - `vote_average` / `vote_count`：评分信息
    - `poster_path` / `backdrop_path`：图片路径
  - Movie 类型特有：
    - `title` / `original_title`
    - `release_date`
    - `adult` / `video`
  - TV 类型特有：
    - `name` / `original_name`
    - `first_air_date`
    - `origin_country[]`
  - Person 类型特有：
    - `name` / `original_name`
    - `known_for_department`
    - `profile_path`
    - `known_for[]`：代表作列表
- `page` / `total_pages` / `total_results`：分页信息

**官方参考**：
- https://developer.themoviedb.org/reference/trending-all

---

### 2) GET `/trending/all/{time_window}`（全类型趋势）

**说明**：
- 获取所有类型（电影 + 电视剧 + 人物）的趋势内容
- 等价于 `GET /trending/all/{time_window}`，即 `media_type="all"` 的快捷方式

**请求参数**：
- Path：
  - `time_window`：`"day"` / `"week"`
- Query（常用）：
  - `language`
  - `page`

**响应要点**：
- 同上，`results[]` 包含 movie/tv/person 混合内容

**官方参考**：
- https://developer.themoviedb.org/reference/trending-all

---

### 3) GET `/trending/movie/{time_window}`（电影趋势）

**说明**：
- 仅获取电影趋势内容
- 等价于 `GET /trending/movie/{time_window}`，即 `media_type="movie"` 的快捷方式

**请求参数**：
- Path：
  - `time_window`：`"day"` / `"week"`
- Query（常用）：
  - `language`
  - `page`

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "adult": false,
      "backdrop_path": "/path.jpg",
      "genre_ids": [28, 12, 878],
      "id": 12345,
      "original_language": "en",
      "original_title": "Original Title",
      "overview": "简介",
      "poster_path": "/poster.jpg",
      "release_date": "2024-01-01",
      "title": "电影标题",
      "video": false,
      "vote_average": 8.5,
      "vote_count": 1000,
      "popularity": 1234.56
    }
  ],
  "total_pages": 100,
  "total_results": 2000
}
```

**响应字段说明**：
- `results[]`：电影列表
  - `title` / `original_title`
  - `release_date`
  - `genre_ids[]`：类型 ID 列表
  - `adult` / `video`
  - `popularity`：热度值（可用于排序）

**官方参考**：
- https://developer.themoviedb.org/reference/trending-movies

---

### 4) GET `/trending/tv/{time_window}`（电视剧趋势）

**说明**：
- 仅获取电视剧趋势内容
- 等价于 `GET /trending/tv/{time_window}`，即 `media_type="tv"` 的快捷方式

**请求参数**：
- Path：
  - `time_window`：`"day"` / `"week"`
- Query（常用）：
  - `language`
  - `page`

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "adult": false,
      "backdrop_path": "/path.jpg",
      "genre_ids": [18, 10765],
      "id": 67890,
      "original_language": "en",
      "original_name": "Original Name",
      "overview": "简介",
      "origin_country": ["US"],
      "poster_path": "/poster.jpg",
      "first_air_date": "2024-01-01",
      "name": "电视剧名称",
      "vote_average": 8.2,
      "vote_count": 800,
      "popularity": 987.65
    }
  ],
  "total_pages": 50,
  "total_results": 1000
}
```

**响应字段说明**：
- `results[]`：电视剧列表
  - `name` / `original_name`
  - `first_air_date`：首播日期
  - `origin_country[]`：出品国家
  - `genre_ids[]`：类型 ID 列表
  - `popularity`：热度值

**官方参考**：
- https://developer.themoviedb.org/reference/trending-tv

---

### 5) GET `/trending/person/{time_window}`（人物趋势）

**说明**：
- 仅获取人物（演员/导演）趋势内容
- 等价于 `GET /trending/person/{time_window}`，即 `media_type="person"` 的快捷方式

**请求参数**：
- Path：
  - `time_window`：`"day"` / `"week"`
- Query（常用）：
  - `language`
  - `page`

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "id": 11111,
      "name": "人物姓名",
      "original_name": "Original Name",
      "media_type": "person",
      "known_for": [
        {
          "adult": false,
          "backdrop_path": "/path.jpg",
          "id": 22222,
          "title": "代表作1",
          "original_language": "en",
          "original_title": "Original Title 1",
          "overview": "简介",
          "poster_path": "/poster1.jpg",
          "media_type": "movie",
          "genre_ids": [28],
          "popularity": 543.21,
          "release_date": "2023-01-01",
          "video": false,
          "vote_average": 7.8,
          "vote_count": 500
        }
      ],
      "known_for_department": "Acting",
      "profile_path": "/profile.jpg",
      "popularity": 432.10
    }
  ],
  "total_pages": 20,
  "total_results": 400
}
```

**响应字段说明**：
- `results[]`：人物列表
  - `name` / `original_name`
  - `known_for_department`：`"Acting"` / `"Directing"` 等
  - `profile_path`：头像路径
  - `known_for[]`：代表作列表（最多 5 部）
    - 每部作品包含基础信息（id/title/release_date 等）
  - `popularity`：热度值

**官方参考**：
- https://developer.themoviedb.org/reference/trending-people

---

### 使用场景示例

#### 场景 1：首页"今日热门"榜单

**需求**：在首页展示今日热门电影、电视剧、人物

**实现**：
```python
# 获取今日热门电影（日榜）
trending_movies_day = await tmdb_client.get(
    "/trending/movie/day",
    params={"language": "zh-CN", "page": 1}
)

# 获取本周热门电视剧（周榜）
trending_tv_week = await tmdb_client.get(
    "/trending/tv/week",
    params={"language": "zh-CN", "page": 1}
)

# 获取今日热门人物
trending_people_day = await tmdb_client.get(
    "/trending/person/day",
    params={"language": "zh-CN", "page": 1}
)
```

#### 场景 2：推荐"最近热门"内容

**需求**：用户问"最近有什么好看的电影？"时，返回热门日榜

**实现**：
```python
# 获取今日热门电影
trending_movies = await tmdb_client.get(
    "/trending/movie/day",
    params={"language": "zh-CN"}
)

# 按 popularity 排序，返回 top 10
top_10 = sorted(
    trending_movies["results"],
    key=lambda x: x.get("popularity", 0),
    reverse=True
)[:10]
```

#### 场景 3：冷启动推荐

**需求**：新用户首次访问，无历史记录时，推荐热门内容

**实现**：
```python
# 获取全类型热门内容（包含 movie/tv/person）
trending_all = await tmdb_client.get(
    "/trending/all/day",
    params={"language": "zh-CN"}
)

# 分类展示
movies = [item for item in trending_all["results"] if item["media_type"] == "movie"]
tv_shows = [item for item in trending_all["results"] if item["media_type"] == "tv"]
people = [item for item in trending_all["results"] if item["media_type"] == "person"]
```

---

### 注意事项

1. **时间窗口选择**：
   - `"day"`：适合"今日热门"、"24小时热点"等实时性强的场景
   - `"week"`：适合"本周热门"、"一周热榜"等稍长期的趋势

2. **热度值（popularity）**：
   - TMDB 的 popularity 值由多个因素计算（浏览量、搜索量、评分等）
   - 不可直接作为排序标准，建议结合 `vote_average` / `vote_count` 使用

3. **多语言处理**：
   - 建议优先使用 `language=zh-CN` 获取中文内容
   - 若返回内容不完整（如 overview 为空），可回退到 `language=en-US`

4. **分页处理**：
   - `total_results` 可能很大（数千），建议只获取前几页
   - 日榜通常变化较快，可设置缓存时间（如 1 小时）

5. **人物趋势的 `known_for`**：
   - 人物的 `known_for[]` 最多返回 5 部代表作
   - 若需要完整作品清单，需额外调用 `/person/{id}/combined_credits`

---

### 端点总览表（TRENDING）

| 端点 | 方法 | 用途 | 是否使用 |
|----------|--------|-------------|------|
| `/trending/{media_type}/{time_window}` | GET | 通用趋势端点 | ✅ 推荐使用 |
| `/trending/all/{time_window}` | GET | 全类型趋势（快捷方式） | ✅ 推荐使用 |
| `/trending/movie/{time_window}` | GET | 电影趋势（快捷方式） | ✅ 推荐使用 |
| `/trending/tv/{time_window}` | GET | 电视剧趋势（快捷方式） | ✅ 推荐使用 |
| `/trending/person/{time_window}` | GET | 人物趋势（快捷方式） | ✅ 推荐使用 |

**说明**：
- `{time_window}` 必需：`"day"` 或 `"week"`
- 所有端点都支持分页（`page` 参数）
- 所有端点都支持语言（`language` 参数）

---

## Watch Providers 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/watch-providers-available-regions
- https://developer.themoviedb.org/reference/watch-providers-movie-list
- https://developer.themoviedb.org/reference/watch-provider-tv-list

用途：
- 获取"哪里能看"信息（流媒体平台、数字租赁、实体媒介等）
- 用于推荐系统中的"观看渠道"展示
- 支持按地区查询（不同地区的可用平台不同）

### 1) GET `/watch/providers/regions`（可用地区列表）

**说明**：
- 获取所有支持观看提供商的地区列表
- 用于展示"支持哪些国家/地区的观看信息"

**请求参数**：
- 无必需参数

**响应要点**：
```json
{
  "results": [
    {
      "iso_3166_1": "AD",
      "english_name": "Andorra",
      "native_name": "Andorra"
    },
    {
      "iso_3166_1": "AE",
      "english_name": "United Arab Emirates",
      "native_name": "United Arab Emirates"
    },
    {
      "iso_3166_1": "CN",
      "english_name": "China",
      "native_name": "中国"
    },
    {
      "iso_3166_1": "US",
      "english_name": "United States",
      "native_name": "United States"
    }
  ]
}
```

**响应字段说明**：
- `results[]`：地区列表
  - `iso_3166_1`：ISO 3166-1 国家/地区代码（如 `"CN"`, `"US"`, `"JP"`）
  - `english_name`：英文名称
  - `native_name`：本地语言名称

**官方参考**：
- https://developer.themoviedb.org/reference/watch-providers-available-regions

---

### 2) GET `/watch/providers/movie`（电影观看提供商）

**说明**：
- 获取特定地区的电影观看提供商列表
- 包括流媒体（flatrate）、租赁（rent）、购买（buy）、免费（free）等多种类型

**请求参数**（Query，常用）：
- `watch_region`（必需）：地区代码，例如 `"CN"` / `"US"` / `"JP"`
- `language`（可选）：语言，例如 `"zh-CN"` / `"en-US"`

**响应要点**：
```json
{
  "id": 8,
  "results": {
    "CN": {
      "link": "https://www.themoviedb.org/movie/12345-{provider_name}/watch?locale=CN",
      "flatrate": [
        {
          "display_priority": 13,
          "logo_path": "/ logos.png",
          "provider_id": 8,
          "provider_name": "Netflix",
          "display_prioritized": true
        },
        {
          "display_priority": 14,
          "logo_path": "/path.png",
          "provider_id": 9,
          "provider_name": "腾讯视频",
          "display_prioritized": true
        }
      ],
      "rent": [
        {
          "display_priority": 6,
          "logo_path": "/path.png",
          "provider_id": 10,
          "provider_name": "Amazon Prime Video",
          "display_prioritized": true
        }
      ],
      "buy": [
        {
          "display_priority": 6,
          "logo_path": "/path.png",
          "provider_id": 10,
          "provider_name": "Amazon Prime Video",
          "display_prioritized": true
        }
      ],
      "free": [
        {
          "display_priority": 22,
          "logo_path": "/path.png",
          "provider_id": 11,
          "provider_name": "Tubi TV",
          "display_prioritized": true
        }
      ]
    }
  }
}
```

**响应字段说明**：
- `id`：固定值 `8`（此端点的 ID）
- `results`：按地区分组的提供商列表
  - Key 为 `iso_3166_1` 地区代码（如 `"CN"`）
  - `link`：TMDB 查看页面链接
  - `flatrate[]`：流媒体平台（订阅观看，如 Netflix、腾讯视频）
    - `display_priority`：显示优先级（数值越小越靠前）
    - `logo_path`：平台 logo 图片路径
    - `provider_id`：提供商 ID
    - `provider_name`：提供商名称
    - `display_prioritized`：是否优先显示
  - `rent[]`：租赁平台（付费租赁，如 Amazon Prime）
  - `buy[]`：购买平台（付费购买，如 iTunes、Google Play）
  - `free[]`：免费平台（含广告，如 Tubi TV、Pluto TV）

**官方参考**：
- https://developer.themoviedb.org/reference/watch-providers-movie-list

---

### 3) GET `/watch/providers/tv`（电视剧观看提供商）

**说明**：
- 获取特定地区的电视剧观看提供商列表
- 结构与电影端点类似

**请求参数**（Query，常用）：
- `watch_region`（必需）：地区代码，例如 `"CN"` / `"US"` / `"JP"`
- `language`（可选）：语言，例如 `"zh-CN"` / `"en-US"`

**响应要点**：
```json
{
  "id": 8,
  "results": {
    "CN": {
      "link": "https://www.themoviedb.org/tv/67890-{provider_name}/watch?locale=CN",
      "flatrate": [
        {
          "display_priority": 13,
          "logo_path": "/logos.png",
          "provider_id": 8,
          "provider_name": "Netflix",
          "display_prioritized": true
        },
        {
          "display_priority": 14,
          "logo_path": "/path.png",
          "provider_id": 9,
          "provider_name": "爱奇艺",
          "display_prioritized": true
        }
      ],
      "rent": [
        {
          "display_priority": 6,
          "logo_path": "/path.png",
          "provider_id": 10,
          "provider_name": "Amazon Prime Video",
          "display_prioritized": true
        }
      ],
      "buy": [
        {
          "display_priority": 6,
          "logo_path": "/path.png",
          "provider_id": 10,
          "provider_name": "Amazon Prime Video",
          "display_prioritized": true
        }
      ],
      "free": []
    }
  }
}
```

**响应字段说明**：
- 结构与电影端点相同
- `flatrate[]` / `rent[]` / `buy[]` / `free[]` 含义与电影端点一致

**官方参考**：
- https://developer.themoviedb.org/reference/watch-provider-tv-list

---

### 使用场景示例

#### 场景 1：查询电影"在哪里能看"（中国地区）

**需求**：用户查询"《星际穿越》在哪里能看？"，返回中国地区的观看平台

**实现**：
```python
# 获取中国地区的电影观看提供商
providers = await tmdb_client.get(
    "/watch/providers/movie",
    params={"watch_region": "CN", "language": "zh-CN"}
)

# 提取该电影的具体提供商
# 注意：这是获取所有电影的提供商列表
# 若要获取特定电影的提供商，需调用 /movie/{id}/watch/providers

# 输出示例：
# "《星际穿越》在中国可以在以下平台观看：
# 流媒体：腾讯视频、爱奇艺
# 购买：Apple TV、Google Play"
```

#### 场景 2：查询美国地区的电视剧观看平台

**需求**：查询美国地区某部电视剧的观看平台

**实现**：
```python
# 获取美国的电视剧观看提供商
providers = await tmdb_client.get(
    "/watch/providers/tv",
    params={"watch_region": "US", "language": "en-US"}
)

# 常见美国平台：
# flatrate: Netflix, Hulu, Disney+, Amazon Prime Video
# rent: Amazon Prime Video, Apple TV, Google Play
# buy: Amazon Prime Video, Apple TV, Google Play, Vudu
```

#### 场景 3：查询所有支持的国家

**需求**：前端展示支持哪些国家/地区的观看信息

**实现**：
```python
# 获取所有支持的地区
regions = await tmdb_client.get(
    "/watch/providers/regions"
)

# 提取地区列表
supported_regions = regions["results"]
# 可用于前端下拉选择器
```

---

### 注意事项

1. **地区代码（watch_region）**：
   - 必需参数，不能省略
   - 使用 ISO 3166-1 标准（如 `"CN"`、`"US"`、`"JP"`）
   - 不同地区的提供商差异很大

2. **提供商类型**：
   - `flatrate`：订阅制流媒体（Netflix、腾讯视频等）
   - `rent`：付费租赁（通常有观看期限，如 48 小时）
   - `buy`：永久购买（可永久观看）
   - `free`：免费观看（通常含广告）

3. **显示优先级（display_priority）**：
   - 数值越小越靠前（优先显示）
   - 可用于排序前端展示

4. **Logo 图片**：
   - `logo_path` 需要拼接 TMDB 图片基础 URL
   - 基础 URL：`https://image.tmdb.org/t/p/w500_and_h284_face/{logo_path}`
   - 或从 `/configuration` 端点获取 `base_url`

5. **数据更新**：
   - 观看提供商信息经常变化（平台上下线、版权到期等）
   - 建议缓存时间不超过 1 天
   - 注意版权信息的准确性

6. **与详情端点的配合使用**：
   - `/watch/providers/movie` 和 `/watch/providers/tv` 返回的是**所有电影的提供商列表**
   - 若要查询**特定电影/电视剧**的提供商，应使用：
     - `/movie/{id}/watch/providers`
     - `/tv/{id}/watch/providers`

---

### 端点总览表（WATCH PROVIDERS）

| 端点 | 方法 | 用途 | 是否使用 |
|----------|--------|-------------|------|
| `/watch/providers/regions` | GET | 获取可用地区列表 | ✅ 推荐使用 |
| `/watch/providers/movie` | GET | 获取电影观看提供商 | ✅ 推荐使用 |
| `/watch/providers/tv` | GET | 获取电视剧观看提供商 | ✅ 推荐使用 |

**说明**：
- 所有端点都支持 `language` 参数（可选）
- `/watch/providers/movie` 和 `/watch/providers/tv` 需要 `watch_region` 参数（必需）

---

## TV Series Lists 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/tv-series-airing-today-list
- https://developer.themoviedb.org/reference/tv-series-on-the-air-list
- https://developer.themoviedb.org/reference/tv-series-popular-list
- https://developer.themoviedb.org/reference/tv-series-top-rated-list

用途：
- 获取电视剧榜单（今日播出、正在播出、热门、高评分）
- 用于"今天有什么好看的电视剧"、"最近热门电视剧"等推荐场景
- 与 Movie Lists 端点对应，但针对电视剧

### 1) GET `/tv/airing_today`（今日播出的电视剧）

**说明**：
- 获取今日播出的电视剧列表
- 用于"今天有什么好看的电视剧"推荐

**请求参数**（Query，常用）：
- `language`：语言，例如 `"zh-CN"` / `"en-US"`
- `page`：页码（默认 `1`）

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "backdrop_path": "/path.jpg",
      "first_air_date": "2024-01-27",
      "genre_ids": [18, 10765],
      "id": 12345,
      "name": "电视剧名称",
      "original_language": "en",
      "original_name": "Original Name",
      "overview": "简介",
      "poster_path": "/poster.jpg",
      "vote_average": 8.2,
      "vote_count": 500
    }
  ],
  "total_pages": 50,
  "total_results": 1000
}
```

**响应字段说明**：
- `results[]`：今日播出的电视剧列表
  - `name` / `original_name`：电视剧名称
  - `first_air_date`：首播日期
  - `genre_ids[]`：类型 ID 列表
  - `vote_average` / `vote_count`：评分信息
  - `poster_path` / `backdrop_path`：图片路径

**官方参考**：
- https://developer.themoviedb.org/reference/tv-series-airing-today-list

---

### 2) GET `/tv/on_the_air`（正在播出的电视剧）

**说明**：
- 获取正在播出的电视剧列表（不限于今日，可能是本周或近期）
- 与 `airing_today` 相比，范围更广

**请求参数**（Query，常用）：
- `language`：语言
- `page`：页码

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "backdrop_path": "/path.jpg",
      "first_air_date": "2024-01-20",
      "genre_ids": [18, 10765],
      "id": 67890,
      "name": "电视剧名称",
      "original_language": "en",
      "original_name": "Original Name",
      "overview": "简介",
      "origin_country": ["US"],
      "poster_path": "/poster.jpg",
      "vote_average": 8.5,
      "vote_count": 800
    }
  ],
  "total_pages": 40,
  "total_results": 800
}
```

**响应字段说明**：
- `results[]`：正在播出的电视剧列表
  - 包含 `origin_country[]`：出品国家（与 airing_today 的区别之一）

**官方参考**：
- https://developer.themoviedb.org/reference/tv-series-on-the-air-list

---

### 3) GET `/tv/popular`（热门电视剧）

**说明**：
- 获取热门电视剧列表
- 基于受欢迎程度排序（类似于电影的热门榜单）

**请求参数**（Query，常用）：
- `language`：语言
- `page`：页码

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "backdrop_path": "/path.jpg",
      "first_air_date": "2024-01-15",
      "genre_ids": [18, 10765],
      "id": 11111,
      "name": "电视剧名称",
      "original_language": "en",
      "original_name": "Original Name",
      "overview": "简介",
      "origin_country": ["US"],
      "poster_path": "/poster.jpg",
      "vote_average": 8.7,
      "vote_count": 1200
    }
  ],
  "total_pages": 100,
  "total_results": 2000
}
```

**官方参考**：
- https://developer.themoviedb.org/reference/tv-series-popular-list

---

### 4) GET `/tv/top_rated`（高评分电视剧）

**说明**：
- 获取评分最高的电视剧列表
- 按 `vote_average` 降序排序

**请求参数**（Query，常用）：
- `language`：语言
- `page`：页码

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "backdrop_path": "/path.jpg",
      "first_air_date": "2023-07-15",
      "genre_ids": [18, 80],
      "id": 22222,
      "name": "电视剧名称",
      "original_language": "en",
      "original_name": "Original Name",
      "overview": "简介",
      "origin_country": ["US"],
      "poster_path": "/poster.jpg",
      "vote_average": 9.2,
      "vote_count": 5000
    }
  ],
  "total_pages": 50,
  "total_results": 1000
}
```

**官方参考**：
- https://developer.themoviedb.org/reference/tv-series-top-rated-list

---

### 使用场景示例

#### 场景 1：推荐"今天有什么好看的电视剧"

**需求**：用户问"今天有什么好看的电视剧？"，返回今日播出列表

**实现**：
```python
# 获取今日播出的电视剧
airing_today = await tmdb_client.get(
    "/tv/airing_today",
    params={"language": "zh-CN", "page": 1}
)

# 按 vote_average 排序，返回高分剧集
top_rated = sorted(
    airing_today["results"],
    key=lambda x: x.get("vote_average", 0),
    reverse=True
)[:10]
```

#### 场景 2：推荐"最近热门电视剧"

**需求**：展示热门电视剧榜单

**实现**：
```python
# 获取热门电视剧
popular_tv = await tmdb_client.get(
    "/tv/popular",
    params={"language": "zh-CN"}
)

# 提取 top 10
top_10 = popular_tv["results"][:10]
```

#### 场景 3：推荐"高评分电视剧"

**需求**：为追求高质量内容的用户推荐高评分电视剧

**实现**：
```python
# 获取高评分电视剧
top_rated_tv = await tmdb_client.get(
    "/tv/top_rated",
    params={"language": "zh-CN"}
)

# 过滤：最低评分 8.0，且评分人数 > 1000
filtered = [
    show for show in top_rated_tv["results"]
    if show.get("vote_average", 0) >= 8.0
    and show.get("vote_count", 0) > 1000
]
```

---

### 注意事项

1. **与 Movie Lists 的对应关系**：
   - `/tv/airing_today` ≈ `/movie/now_playing`
   - `/tv/popular` ≈ `/movie/popular`
   - `/tv/top_rated` ≈ `/movie/top_rated`
   - 电视剧没有 `/tv/upcoming` 等价端点

2. **airing_today vs on_the_air**：
   - `airing_today`：严格限定"今日播出"
   - `on_the_air`：范围更广，可能是"本周/近期"在播

3. **地区过滤**：
   - 这些端点不直接支持 `region` 参数
   - 若要过滤特定地区，需要：
     - 使用 `origin_country` 字段（在响应中）
     - 或使用 `/discover/tv` 端点的 `with_origin_country` 参数

4. **分页处理**：
   - `total_results` 可能很大（数千）
   - 建议只获取前几页，避免过度请求

---

### 端点总览表（TV SERIES LISTS）

| 端点 | 方法 | 用途 | 是否使用 |
|----------|--------|-------------|------|
| `/tv/airing_today` | GET | 获取今日播出的电视剧 | ✅ 推荐使用 |
| `/tv/on_the_air` | GET | 获取正在播出的电视剧 | ✅ 推荐使用 |
| `/tv/popular` | GET | 获取热门电视剧 | ✅ 推荐使用 |
| `/tv/top_rated` | GET | 获取高评分电视剧 | ✅ 推荐使用 |

**说明**：
- 所有端点都支持 `language` 和 `page` 参数
- 返回的字段结构基本一致

---

## People Lists 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/person-popular-list

用途：
- 获取热门人物（演员/导演）榜单
- 用于"当下热门人物"、"热门导演/演员"等推荐场景

### GET `/person/popular`（热门人物列表）

**说明**：
- 获取当前热门人物列表（基于知名度、作品热度等）
- 适合"热门演员"、"热门导演"等榜单展示

**请求参数**（Query，常用）：
- `language`：语言，例如 `"zh-CN"` / `"en-US"`
- `page`：页码（默认 `1`）

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "adult": false,
      "gender": 1,
      "id": 12345,
      "known_for": [
        {
          "adult": false,
          "backdrop_path": "/path.jpg",
          "genre_ids": [28, 12],
          "id": 11111,
          "original_language": "en",
          "original_title": "Original Title",
          "overview": "简介",
          "poster_path": "/poster.jpg",
          "release_date": "2023-01-01",
          "title": "代表作1",
          "video": false,
          "vote_average": 8.5,
          "vote_count": 1000
        },
        {
          "adult": false,
          "backdrop_path": "/path2.jpg",
          "genre_ids": [18, 10765],
          "id": 22222,
          "original_language": "en",
          "original_title": "Original Title 2",
          "overview": "简介",
          "poster_path": "/poster2.jpg",
          "release_date": "2022-01-01",
          "title": "代表作2",
          "video": false,
          "vote_average": 8.2,
          "vote_count": 800
        }
      ],
      "known_for_department": "Acting",
      "name": "人物姓名",
      "original_name": "Original Name",
      "popularity": 1234.56,
      "profile_path": "/profile.jpg"
    }
  ],
  "total_pages": 100,
  "total_results": 2000
}
```

**响应字段说明**：
- `results[]`：热门人物列表
  - `name` / `original_name`：人物姓名
  - `known_for_department`：`"Acting"` / `"Directing"` 等
  - `profile_path`：头像路径
  - `popularity`：热度值（可用于排序）
  - `known_for[]`：代表作列表（通常 2-3 部）
    - 每部作品包含基础信息（id/title/release_date 等）
  - `gender`：性别（1 = 女性，2 = 男性）

**官方参考**：
- https://developer.themoviedb.org/reference/person-popular-list

---

### 使用场景示例

#### 场景 1：推荐"热门演员"

**需求**：用户问"最近有哪些热门演员？"，返回热门人物榜单

**实现**：
```python
# 获取热门人物
popular_people = await tmdb_client.get(
    "/person/popular",
    params={"language": "zh-CN", "page": 1}
)

# 按 popularity 排序
top_actors = sorted(
    popular_people["results"],
    key=lambda x: x.get("popularity", 0),
    reverse=True
)[:10]
```

#### 场景 2：按职业过滤热门人物

**需求**：只获取热门导演，或只获取热门演员

**实现**：
```python
# 获取热门人物
popular_people = await tmdb_client.get(
    "/person/popular",
    params={"language": "zh-CN"}
)

# 过滤：只要导演
directors = [
    person for person in popular_people["results"]
    if person.get("known_for_department") == "Directing"
]

# 过滤：只要演员
actors = [
    person for person in popular_people["results"]
    if person.get("known_for_department") == "Acting"
]
```

---

### 注意事项

1. **known_for_department**：
   - `"Acting"`：演员
   - `"Directing"`：导演
   - `"Writing"`：编剧
   - `"Production"`：制片人等
   - 有时可能为 `null` 或其他值

2. **known_for 限制**：
   - `known_for[]` 最多返回 2-3 部代表作
   - 不代表完整作品清单
   - 若需要完整作品，需额外调用 `/person/{id}/combined_credits`

3. **popularity 值**：
   - 由 TMDB 计算，综合考虑作品热度、评分等
   - 可用于排序，但不绝对准确

4. **gender 字段**：
   - `1`：女性
   - `2`：男性
   - 有时可能为 `null` 或 `0`（未知）

---

### 端点总览表（PEOPLE LISTS）

| 端点 | 方法 | 用途 | 是否使用 |
|----------|--------|-------------|------|
| `/person/popular` | GET | 获取热门人物列表 | ✅ 推荐使用 |

**说明**：
- 支持 `language` 和 `page` 参数
- 适合"热门演员"、"热门导演"等榜单展示

---

## TV Series（扩展端点）对齐（官方 Reference）

本节对齐官方 Reference（TV Series 相关扩展端点）：
- https://developer.themoviedb.org/reference/tv-alternative-titles
- https://developer.themoviedb.org/reference/tv-content-ratings
- https://developer.themoviedb.org/reference/tv-episode-groups
- https://developer.themoviedb.org/reference/tv-external-ids
- https://developer.themoviedb.org/reference/tv-images
- https://developer.themoviedb.org/reference/tv-keywords
- https://developer.themoviedb.org/reference/tv-recommendations
- https://developer.themoviedb.org/reference/tv-reviews
- https://developer.themoviedb.org/reference/tv-screened-theatrically
- https://developer.themoviedb.org/reference/tv-similar
- https://developer.themoviedb.org/reference/tv-translations
- https://developer.themoviedb.org/reference/tv-videos
- https://developer.themoviedb.org/reference/tv-watch-providers

用途（典型产品/数据场景）：
- 别名获取（Alternative Titles）
- 内容分级查询（Content Ratings）
- 剧集分组（Episode Groups）
- 外部 ID 对齐（External IDs）
- 图片资源（Images）
- 关键词标签（Keywords）
- 推荐/相似（Recommendations/Similar）
- 评论内容（Reviews）
- 影院放映信息（Screened Theatrically）
- 多语言翻译（Translations）
- 视频资源（Videos）
- 观看平台（Watch Providers）

**注意**：External IDs、Images、Reviews、Videos、Watch Providers 端点已在其他章节详细说明，此处仅列举。

---

### 1) GET `/tv/{series_id}/alternative_titles`（电视剧别名）

**说明**：
- 获取电视剧的别名（不同国家/地区的标题）
- 用于多语言展示、搜索匹配

**请求参数**：
- **Path**：
  - `series_id`（必需）：电视剧 ID
- **Query**：
  - `country`（可选）：国家代码，如 `"US"`、`"CN"`

**响应示例**：
```json
{
  "id": 1396,
  "results": [
    {
      "iso_3166_1": "US",
      "title": "Breaking Bad"
    },
    {
      "iso_3166_1": "CN",
      "title": "绝命毒师"
    },
    {
      "iso_3166_1": "JP",
      "title": "ブレイキング・バッド"
    }
  ]
}
```

**核心字段说明**：
- `iso_3166_1`：国家代码（如 `"US"`、`"CN"`、`"JP"`）
- `title`：该国家/地区的标题

**核心用途**：
- 多语言标题展示
- 搜索匹配（用户可能用别名搜索）

**官方参考**：
- https://developer.themoviedb.org/reference/tv-alternative-titles

---

### 2) GET `/tv/{series_id}/content_ratings`（内容分级）

**说明**：
- 获取电视剧的内容分级信息
- 不同国家/地区的分级标准（如 TV-MA、TV-14）

**请求参数**：
- **Path**：
  - `series_id`（必需）：电视剧 ID
- **Query**：
  - `language`（可选）：语言

**响应示例**：
```json
{
  "id": 1396,
  "results": [
    {
      "iso_3166_1": "US",
      "rating": "TV-MA"
    },
    {
      "iso_3166_1": "GB",
      "rating": "18"
    },
    {
      "iso_3166_1": "CN",
      "rating": "18+"
    }
  ]
}
```

**核心字段说明**：
- `iso_3166_1`：国家代码
- `rating`：分级等级

**常见分级（美国）**：
- `TV-Y`：适合所有儿童
- `TV-Y7`：适合 7 岁及以上
- `TV-G`：所有年龄
- `TV-PG`：建议家长指导
- `TV-14`：家长强烈警告
- `TV-MA`：仅限成人

**核心用途**：
- 内容分级展示
- 家长控制

**官方参考**：
- https://developer.themoviedb.org/reference/tv-content-ratings

---

### 3) GET `/tv/{series_id}/episode_groups`（剧集分组）

**说明**：
- 获取电视剧的剧集分组信息
- 用于按不同方式组织剧集（如按季度、按主题）

**请求参数**：
- **Path**：
  - `series_id`（必需）：电视剧 ID
- **Query**：
  - `language`（可选）：语言

**响应示例**：
```json
{
  "id": 1396,
  "results": [
    {
      "id": "5ac8844c0e0a263e2e01b5f6",
      "name": "Season 1",
      "type": 6,
      "group_count": 1,
      "groups": [
        {
          "id": "5ac8844c0e0a263e2e01b5f6",
          "name": "Season 1",
          "order": 1,
          "locked": false,
          "episode_count": 7,
          "air_date": "2008-01-20",
          "network": "AMC"
        }
      ]
    }
  ]
}
```

**核心字段说明**：
- `results[]`：分组列表
  - `id`：分组 ID
  - `name`：分组名称
  - `type`：分组类型
  - `groups[]`：子分组
    - `episode_count`：剧集数量
    - `air_date`：播出日期
    - `network`：播出网络

**核心用途**：
- 剧集组织（按季度、按主题）
- 播出计划展示

**官方参考**：
- https://developer.themoviedb.org/reference/tv-episode-groups

---

### 4) GET `/tv/{series_id}/keywords`（关键词）

**说明**：
- 获取电视剧的关键词标签
- 用于主题推荐、相似度计算

**请求参数**：
- **Path**：
  - `series_id`（必需）：电视剧 ID

**响应示例**：
```json
{
  "id": 1396,
  "results": [
    {"id": 14976, "name": "teacher"},
    {"id": 14978, "name": "drug dealer"},
    {"id": 14980, "name": "murder"},
    {"id": 1521, "name": "prison"}
  ]
}
```

**核心字段说明**：
- `results[]`：关键词列表
  - `id`：关键词 ID
  - `name`：关键词名称

**核心用途**：
- 标签推荐（"关于教师的电视剧"）
- 相似度计算（基于关键词重叠度）

**官方参考**：
- https://developer.themoviedb.org/reference/tv-keywords

---

### 5) GET `/tv/{series_id}/recommendations`（推荐电视剧）

**说明**：
- 获取推荐电视剧（基于协同过滤）
- 适合"看完该剧还能看什么"场景

**请求参数**：
- **Path**：
  - `series_id`（必需）：电视剧 ID
- **Query**：
  - `language`：语言
  - `page`：页码

**响应示例**：
```json
{
  "page": 1,
  "results": [
    {
      "id": 1399,
      "name": "Better Call Saul",
      "first_air_date": "2015-02-08",
      "vote_average": 8.5,
      "overview": "The trials and tribulations of criminal lawyer..."
    }
  ]
}
```

**核心用途**：
- 推荐增强（协同过滤）
- 冷启动推荐

**官方参考**：
- https://developer.themoviedb.org/reference/tv-recommendations

---

### 6) GET `/tv/{series_id}/similar`（相似电视剧）

**说明**：
- 获取相似电视剧（基于内容相似度）
- 适合"类似该剧的电视剧"场景

**请求参数**：
- **Path**：
  - `series_id`（必需）：电视剧 ID
- **Query**：
  - `language`：语言
  - `page`：页码

**响应示例**：
```json
{
  "page": 1,
  "results": [
    {
      "id": 66732,
      "name": "Stranger Things",
      "first_air_date": "2016-07-15",
      "vote_average": 8.6
    }
  ]
}
```

**核心用途**：
- 相似推荐（内容相似度）
- 相似度特征工程

**官方参考**：
- https://developer.themoviedb.org/reference/tv-similar

---

### 7) GET `/tv/{series_id}/screened_theatrically`（影院放映）

**说明**：
- 获取电视剧的影院放映信息
- 部分电视剧会在影院首播

**请求参数**：
- **Path**：
  - `series_id`（必需）：电视剧 ID

**响应示例**：
```json
{
  "id": 1396,
  "results": [
    {
      "id": 12345,
      "episode_number": 1,
      "season_number": 1,
      "type": "Premiere"
    }
  ]
}
```

**核心字段说明**：
- `results[]`：影院放映列表
  - `episode_number`：集数
  - `season_number`：季数
  - `type`：放映类型（如 "Premiere"）

**核心用途**：
- 影院首播信息展示
- 特殊放映事件

**官方参考**：
- https://developer.themoviedb.org/reference/tv-screened-theatrically

---

### 8) GET `/tv/{series_id}/translations`（翻译）

**说明**：
- 获取电视剧的多语言标题和简介
- 用于多语言 UI 展示或翻译回退策略

**请求参数**：
- **Path**：
  - `series_id`（必需）：电视剧 ID

**响应示例**：
```json
{
  "id": 1396,
  "translations": [
    {
      "iso_639_1": "zh",
      "iso_3166_1": "CN",
      "name": "Chinese",
      "english_name": "Chinese",
      "data": {
        "name": "绝命毒师",
        "overview": "一位高中化学老师因经济困难而制造冰毒..."
      }
    },
    {
      "iso_639_1": "en",
      "data": {
        "name": "Breaking Bad",
        "overview": "A high school chemistry teacher..."
      }
    }
  ]
}
```

**核心用途**：
- 多语言 UI 展示
- 翻译回退（优先显示用户语言，无则回退到英语）

**官方参考**：
- https://developer.themoviedb.org/reference/tv-translations

---

### 使用场景示例

#### 场景 1：获取电视剧别名和多语言标题

**需求**：用户搜索"绝命毒师"的别名，或需要显示多语言标题

**实现**：
```python
import requests

def get_tv_alternative_titles(series_id: int):
    """获取电视剧别名"""
    url = f"https://api.themoviedb.org/3/tv/{series_id}/alternative_titles"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    return response.json()

def get_tv_translations(series_id: int):
    """获取电视剧翻译"""
    url = f"https://api.themoviedb.org/3/tv/{series_id}/translations"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    return response.json()

# 示例：绝命毒师（ID: 1396）
aliases = get_tv_alternative_titles(1396)
translations = get_tv_translations(1396)

print("别名：")
for title in aliases.get("results", []):
    print(f"  {title['iso_3166_1']}: {title['title']}")

print("\n翻译：")
for t in translations.get("translations", []):
    name = t.get("data", {}).get("name")
    if name:
        print(f"  {t['iso_639_1']}: {name}")
```

#### 场景 2：查询内容分级

**需求**：家长想知道某电视剧是否适合孩子观看

**实现**：
```python
def get_tv_content_ratings(series_id: int, country: str = "US"):
    """获取内容分级"""
    url = f"https://api.themoviedb.org/3/tv/{series_id}/content_ratings"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    data = response.json()

    # 查找指定国家的分级
    for rating in data.get("results", []):
        if rating["iso_3166_1"] == country:
            return rating["rating"]

    return None

# 示例
rating = get_tv_content_ratings(1396, "US")
print(f"美国分级：{rating}")

# 分级说明
rating_guide = {
    "TV-Y": "适合所有儿童",
    "TV-Y7": "适合 7 岁及以上",
    "TV-G": "所有年龄",
    "TV-PG": "建议家长指导",
    "TV-14": "家长强烈警告",
    "TV-MA": "仅限成人"
}
print(f"说明：{rating_guide.get(rating, '未知分级')}")
```

#### 场景 3：获取相似和推荐电视剧

**需求**：用户看完《绝命毒师》，推荐类似电视剧

**实现**：
```python
def get_tv_recommendations(series_id: int, language: str = "zh-CN"):
    """获取推荐电视剧"""
    url = f"https://api.themoviedb.org/3/tv/{series_id}/recommendations"
    params = {"api_key": TMDB_API_KEY, "language": language}
    response = requests.get(url, params=params)
    return response.json().get("results", [])

def get_tv_similar(series_id: int, language: str = "zh-CN"):
    """获取相似电视剧"""
    url = f"https://api.themoviedb.org/3/tv/{series_id}/similar"
    params = {"api_key": TMDB_API_KEY, "language": language}
    response = requests.get(url, params=params)
    return response.json().get("results", [])

# 示例
recommended = get_tv_recommendations(1396)
similar = get_tv_similar(1396)

print(f"推荐电视剧（{len(recommended)} 部）：")
for show in recommended[:5]:
    print(f"  - {show['name']} ({show.get('first_air_date', 'N/A')})")

print(f"\n相似电视剧（{len(similar)} 部）：")
for show in similar[:5]:
    print(f"  - {show['name']} ({show.get('first_air_date', 'N/A')})")
```

#### 场景 4：获取电视剧关键词标签

**需求**：为电视剧添加标签，或根据关键词推荐相似内容

**实现**：
```python
def get_tv_keywords(series_id: int):
    """获取关键词"""
    url = f"https://api.themoviedb.org/3/tv/{series_id}/keywords"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    return response.json().get("results", [])

# 示例
keywords = get_tv_keywords(1396)
print("关键词标签：")
for kw in keywords:
    print(f"  - {kw['name']}")

# 根据关键词查找相似内容
keyword_names = [kw["name"] for kw in keywords]
print(f"\n主题：{', '.join(keyword_names[:5])}")
```

---

### 重要说明

1. **TV Series vs Movie**：
   - 电视剧使用 `first_air_date`（首播日期）
   - 电影使用 `release_date`（上映日期）
   - 电视剧使用 `name`，电影使用 `title`

2. **分集信息**：
   - 本章节关注电视剧级别的信息
   - 分集详细信息见 TV Seasons/TV Episodes 端点

3. **已详细说明的端点**：
   - **External IDs**：参见"External IDs 端点对齐"章节
   - **Images**：参见"Images & Configuration 端点对齐"章节
   - **Reviews**：参见"Reviews 端点对齐"章节
   - **Videos**：参见"Movies（扩展端点）"章节中的 Videos
   - **Watch Providers**：参见"Watch Providers 端点对齐"章节

4. **语言本地化**：
   - 大部分端点支持 `language` 参数
   - 建议根据用户语言偏好设置（中文：`zh-CN`）

5. **分页处理**：
   - Recommendations/Similar 端点支持分页
   - 单页返回 20 条结果

6. **数据完整性**：
   - 部分老旧电视剧可能缺少某些信息
   - 建议检查字段是否存在后再使用

---

### 端点对比

| 端点 | 返回内容 | 主要用途 | 调用频率 |
|------|---------|---------|---------|
| `/tv/{id}/alternative_titles` | 别名列表 | 多语言标题 | 按需 |
| `/tv/{id}/content_ratings` | 分级信息 | 家长控制 | 按需 |
| `/tv/{id}/episode_groups` | 剧集分组 | 剧集组织 | 按需 |
| `/tv/{id}/keywords` | 关键词标签 | 标签推荐 | 按需 |
| `/tv/{id}/recommendations` | 推荐列表 | 推荐增强 | 按需 |
| `/tv/{id}/similar` | 相似列表 | 相似推荐 | 按需 |
| `/tv/{id}/screened_theatrically` | 影院放映信息 | 特殊放映 | 按需 |
| `/tv/{id}/translations` | 多语言翻译 | 国际化 | 按需 |

---

### 与其他端点的集成

1. **TV Details**：
   - 电视剧详情包含基础信息
   - 扩展端点提供更详细的信息

2. **TV Seasons/Episodes**：
   - Season/Episode 端点提供分集级别信息
   - TV Series 扩展端点提供电视剧级别信息

3. **Discover API**：
   - 可通过关键词、类型等过滤
   - 结合 Keywords 端点实现主题推荐

---

## Similar & Recommendations 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/movie-similar-list
- https://developer.themoviedb.org/reference/movie-recommendations-list

用途：
- 获取"相似电影"和"推荐电影"列表
- 用于"类似 X 的电影"、"看完 X 还能看什么"等推荐场景
- 核心能力：协同过滤 + 内容相似度

### GET `/movie/{movie_id}/similar`（相似电影列表）

**说明**：
- 获取与指定电影相似的电影列表
- 基于内容相似度（类型、标签、关键词、元数据等）
- 适合"类似《肖申克的救赎》的电影"等场景

**请求参数**（Path + Query）：
- `movie_id`（Path）：电影 ID
- `language`：语言，例如 `"zh-CN"` / `"en-US"`
- `page`：页码（默认 `1`）

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "adult": false,
      "backdrop_path": "/path.jpg",
      "genre_ids": [18, 80],
      "id": 278,
      "original_language": "en",
      "original_title": "Original Title",
      "overview": "电影简介",
      "poster_path": "/poster.jpg",
      "release_date": "1994-09-23",
      "title": "电影标题",
      "video": false,
      "vote_average": 8.7,
      "vote_count": 25000,
      "popularity": 123.45
    }
  ],
  "total_pages": 50,
  "total_results": 1000
}
```

**响应字段说明**：
- `results[]`：相似电影列表（按相似度降序）
  - `id`：电影 ID（可用于二次查询详情）
  - `title` / `original_title`：电影标题
  - `overview`：简介
  - `release_date`：上映日期
  - `vote_average`：评分（0-10）
  - `vote_count`：评分人数
  - `popularity`：热度值
  - `genre_ids[]`：类型 ID 列表
  - `poster_path` / `backdrop_path`：海报/背景图路径

**官方参考**：
- https://developer.themoviedb.org/reference/movie-similar-list

---

### GET `/movie/{movie_id}/recommendations`（推荐电影列表）

**说明**：
- 获取基于指定电影的推荐电影列表
- 基于协同过滤（用户观看行为）+ 内容相似度
- 适合"看完《肖申克的救赎》还能看什么"等场景

**请求参数**（Path + Query）：
- `movie_id`（Path）：电影 ID
- `language`：语言，例如 `"zh-CN"` / `"en-US"`
- `page`：页码（默认 `1`）

**响应要点**：
```json
{
  "page": 1,
  "results": [
    {
      "adult": false,
      "backdrop_path": "/path.jpg",
      "genre_ids": [18, 80],
      "id": 238,
      "original_language": "en",
      "original_title": "Original Title",
      "overview": "电影简介",
      "poster_path": "/poster.jpg",
      "release_date": "1994-09-10",
      "title": "电影标题",
      "video": false,
      "vote_average": 8.5,
      "vote_count": 21000,
      "popularity": 98.76
    }
  ],
  "total_pages": 45,
  "total_results": 900
}
```

**响应字段说明**：
- 与 `/similar` 字段结构一致
- 差异：推荐逻辑不同（协同过滤 vs 内容相似度）

**官方参考**：
- https://developer.themoviedb.org/reference/movie-recommendations-list

---

### TV 端点（电视剧）

TMDB 也提供 TV 版本：
- `GET /tv/{series_id}/similar`：相似电视剧列表
- `GET /tv/{series_id}/recommendations`：推荐电视剧列表

请求/响应结构与 Movie 版本基本一致。

---

### 使用场景示例

#### 场景 1：相似电影推荐

**需求**：用户问"类似《肖申克的救赎》的电影有哪些？"，返回相似电影列表

**实现**：
```python
import requests

def get_similar_movies(movie_id: int, language: str = "zh-CN"):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/similar"
    params = {
        "api_key": TMDB_API_KEY,
        "language": language,
        "page": 1
    }
    response = requests.get(url, params=params)
    data = response.json()

    # 返回 Top 10 相似电影
    similar_movies = data.get("results", [])[:10]
    return [
        {
            "id": m["id"],
            "title": m["title"],
            "overview": m["overview"],
            "release_date": m["release_date"],
            "vote_average": m["vote_average"]
        }
        for m in similar_movies
    ]

# 示例：肖申克的救赎（ID: 278）
similar = get_similar_movies(278)
print(f"找到 {len(similar)} 部相似电影")
```

#### 场景 2：看完电影后的后续推荐

**需求**：用户看完《阿甘正传》，问"接下来还能看什么？"，返回推荐电影

**实现**：
```python
def get_recommended_movies(movie_id: int, language: str = "zh-CN"):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
    params = {
        "api_key": TMDB_API_KEY,
        "language": language,
        "page": 1
    }
    response = requests.get(url, params=params)
    data = response.json()

    # 返回 Top 10 推荐电影
    recommended = data.get("results", [])[:10]
    return [
        {
            "id": m["id"],
            "title": m["title"],
            "overview": m["overview"],
            "vote_average": m["vote_average"]
        }
        for m in recommended
    ]

# 示例：阿甘正传（ID: 13）
recommended = get_recommended_movies(13)
print(f"为您推荐 {len(recommended)} 部电影")
```

#### 场景 3：混合相似与推荐

**需求**：综合相似电影和推荐电影，提供更丰富的推荐列表

**实现**：
```python
def get_hybrid_recommendations(movie_id: int, language: str = "zh-CN"):
    # 获取相似电影
    similar = get_similar_movies(movie_id, language)
    # 获取推荐电影
    recommended = get_recommended_movies(movie_id, language)

    # 去重（基于 ID）
    seen_ids = {m["id"] for m in similar}
    unique_recommended = [m for m in recommended if m["id"] not in seen_ids]

    # 合并：相似（Top 5）+ 推荐（Top 5）
    hybrid = similar[:5] + unique_recommended[:5]
    return hybrid

# 示例
hybrid = get_hybrid_recommendations(278)
print(f"混合推荐：{len(hybrid)} 部电影")
```

---

### 重要说明

1. **相似度 vs 推荐**：
   - `/similar`：基于内容相似度（类型、标签、关键词）
   - `/recommendations`：基于协同过滤（用户行为）
   - 实际场景可结合两者提供更丰富的推荐

2. **结果质量**：
   - 热门电影的相似/推荐结果更丰富
   - 冷门电影可能结果较少（返回空列表）
   - 建议检查 `total_results`，避免空结果

3. **分页处理**：
   - 单次返回 20 部电影（`page_size` 固定）
   - 如需更多结果，使用 `page` 参数分页

4. **排序逻辑**：
   - 默认按相似度/推荐度降序
   - 可结合 `vote_average`、`popularity` 做二次排序

5. **TV 端点**：
   - 电视剧的相似/推荐端点与电影基本一致
   - 区别：路径为 `/tv/{series_id}/similar` 和 `/tv/{series_id}/recommendations`

6. **语言支持**：
   - 支持 `language` 参数，返回指定语言的标题和简介
   - 建议根据用户语言偏好设置（中文：`zh-CN`）

---

### 端点对比

| 端点 | 逻辑基础 | 适用场景 | 结果数量 |
|------|---------|---------|---------|
| `/movie/{id}/similar` | 内容相似度 | "类似 X 的电影" | 0-1000+ |
| `/movie/{id}/recommendations` | 协同过滤 | "看完 X 还能看什么" | 0-1000+ |

---

## External IDs 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/movie-external-ids
- https://developer.themoviedb.org/reference/person-external-ids

用途：
- 获取电影/人物在外部数据库的 ID 映射
- 用于与 IMDb、Douban（豆瓣）、TVDB 等数据库对齐
- 支持跨数据源去重和数据增强

### GET `/movie/{movie_id}/external_ids`（电影外部 ID）

**说明**：
- 获取指定电影在各外部数据库的 ID 映射
- 支持 IMDb、TVDB、TMDb 等多个数据源
- 适合"IMDb 评分"、"豆瓣评分"等跨数据源查询

**请求参数**（Path）：
- `movie_id`（Path）：电影 ID

**响应要点**：
```json
{
  "id": 278,
  "imdb_id": "tt0111161",
  "tvdb_id": 1120,
  "wikidata_id": 25086,
  "facebook_id": "TheShawshankRedemption",
  "instagram_id": "shawshankredemptionfilm",
  "twitter_id": "ShawshankRedemption"
}
```

**响应字段说明**：
- `imdb_id`：IMDb ID（格式：`tt` + 7-8 位数字）
  - 可用于查询 IMDb 评分：`https://www.imdb.com/title/{imdb_id}`
- `tvdb_id`：The TV Database ID（主要用于电视剧）
- `wikidata_id`：维基数据 ID
- `facebook_id`、`instagram_id`、`twitter_id`：社交媒体 ID

**官方参考**：
- https://developer.themoviedb.org/reference/movie-external-ids

---

### GET `/person/{person_id}/external_ids`（人物外部 ID）

**说明**：
- 获取指定人物（演员/导演）在各外部数据库的 ID 映射
- 支持 IMDb、TVDB、Wikidata 等多个数据源

**请求参数**（Path）：
- `person_id`（Path）：人物 ID

**响应要点**：
```json
{
  "id": 12345,
  "imdb_id": "nm0000156",
  "tvdb_id": 67890,
  "wikidata_id": 12345,
  "facebook_id": "actorname",
  "instagram_id": "actorname",
  "twitter_id": "actorname",
  "tvrage_id": 12345
}
```

**响应字段说明**：
- `imdb_id`：IMDb ID（格式：`nm` + 7-8 位数字）
  - 可用于查询 IMDb 人物页面：`https://www.imdb.com/name/{imdb_id}`
- `tvdb_id`：The TV Database ID
- `tvrage_id`：TVRage ID
- `wikidata_id`：维基数据 ID

**官方参考**：
- https://developer.themoviedb.org/reference/person-external-ids

---

### GET `/tv/{series_id}/external_ids`（电视剧外部 ID）

**说明**：
- 获取指定电视剧在各外部数据库的 ID 映射
- 结构与 Movie 版本一致

**响应要点**：
```json
{
  "id": 1396,
  "imdb_id": "tt0306414",
  "tvdb_id": 73695,
  "wikidata_id": 227014,
  "facebook_id": "BreakingBad",
  "instagram_id": "breakingbad",
  "twitter_id": "BreakingBad"
}
```

**官方参考**：
- https://developer.themoviedb.org/reference/tv-external-ids

---

### GET `/find/{external_id}`（通过外部 ID 查找）

**说明**：
- 反向查找：通过外部 ID 查找对应的 TMDb ID
- 支持的外部源：`imdb_id`、`tvdb_id`、`wikidata_id` 等

**请求参数**（Path + Query）：
- `external_id`（Path）：外部 ID（如 `tt0111161`）
- `api_key`：API Key
- `language`：语言（可选）

**响应要点**：
```json
{
  "movie_results": [
    {
      "id": 278,
      "title": "肖申克的救赎",
      "original_title": "The Shawshank Redemption",
      "poster_path": "/poster.jpg",
      "release_date": "1994-09-23",
      "vote_average": 8.7
    }
  ],
  "tv_results": [],
  "person_results": []
}
```

**官方参考**：
- https://developer.themoviedb.org/reference/find-by-id

---

### 使用场景示例

#### 场景 1：查询 IMDb 评分

**需求**：用户问"《肖申克的救赎》的 IMDb 评分是多少？"，需要先获取 IMDb ID，再查询 IMDb

**实现**：
```python
import requests

def get_imdb_id(movie_id: int) -> str:
    # 获取外部 ID
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/external_ids"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    data = response.json()

    imdb_id = data.get("imdb_id")
    return imdb_id

def get_imdb_rating(imdb_id: str) -> float:
    # 通过 IMDb ID 查询 IMDb 评分（需调用 IMDb API 或爬虫）
    # 这里仅展示 URL 构造
    imdb_url = f"https://www.imdb.com/title/{imdb_id}"
    # 实际实现需调用 IMDb API 或使用第三方服务
    # 例如：OMDB API (http://www.omdbapi.com/)
    return 9.3  # 示例值

# 示例
movie_id = 278
imdb_id = get_imdb_id(movie_id)
print(f"IMDb ID: {imdb_id}")
# 输出: IMDb ID: tt0111161

rating = get_imdb_rating(imdb_id)
print(f"IMDb 评分: {rating}")
```

#### 场景 2：跨数据源去重

**需求**：从多个数据源导入电影数据时，通过 IMDb ID 去重

**实现**：
```python
def deduplicate_movies(movies: list) -> list:
    """通过 IMDb ID 去重电影列表"""
    seen_imdb_ids = set()
    unique_movies = []

    for movie in movies:
        # 获取 IMDb ID
        imdb_id = get_imdb_id(movie["id"])
        if imdb_id and imdb_id not in seen_imdb_ids:
            seen_imdb_ids.add(imdb_id)
            unique_movies.append(movie)

    return unique_movies

# 示例
movies_from_different_sources = [
    {"id": 278, "title": "肖申克的救赎"},
    {"id": 999, "title": "肖申克的救赎（重复）"},  # 假设这是重复数据
]
unique_movies = deduplicate_movies(movies_from_different_sources)
print(f"去重后: {len(unique_movies)} 部电影")
```

#### 场景 3：反向查找（IMDb ID → TMDb ID）

**需求**：用户已知 IMDb ID，需要查找对应的 TMDb ID

**实现**：
```python
def find_tmdb_id_by_imdb(imdb_id: str) -> int:
    """通过 IMDb ID 查找 TMDb ID"""
    url = f"https://api.themoviedb.org/3/find/{imdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "external_source": "imdb_id"
    }
    response = requests.get(url, params=params)
    data = response.json()

    # 检查 movie_results
    if data.get("movie_results"):
        return data["movie_results"][0]["id"]

    # 检查 tv_results
    if data.get("tv_results"):
        return data["tv_results"][0]["id"]

    return None

# 示例
imdb_id = "tt0111161"
tmdb_id = find_tmdb_id_by_imdb(imdb_id)
print(f"TMDb ID: {tmdb_id}")
# 输出: TMDb ID: 278
```

#### 场景 4：数据增强（整合豆瓣评分）

**需求**：整合豆瓣评分（需额外接入豆瓣 API 或爬虫）

**实现**：
```python
def get_douban_id(movie_id: int, tmdb_id: int) -> str:
    """
    通过 TMDb ID 查找豆瓣 ID
    注意：TMDb 不直接提供豆瓣 ID，需通过第三方服务或爬虫
    这里仅展示逻辑
    """
    # 方法1：通过豆瓣搜索 API
    # 方法2：通过第三方数据库（如 Movie-Douban 映射表）
    # 方法3：通过维基数据（Wikidata）作为桥梁
    return "1292052"  # 示例值

def get_douban_rating(douban_id: str) -> float:
    """获取豆瓣评分（需接入豆瓣 API）"""
    # 实际实现需调用豆瓣 API 或使用爬虫
    # 示例：https://movie.douban.com/subject/{douban_id}/
    return 9.7  # 示例值

# 完整流程
movie_id = 278
tmdb_id = 278
douban_id = get_douban_id(movie_id, tmdb_id)
douban_rating = get_douban_rating(douban_id)
print(f"豆瓣评分: {douban_rating}")
```

---

### 重要说明

1. **IMDb ID 格式**：
   - 电影：`tt` + 7-8 位数字（如 `tt0111161`）
   - 人物：`nm` + 7-8 位数字（如 `nm0000156`）

2. **豆瓣 ID 支持**：
   - TMDb **不直接提供**豆瓣 ID
   - 需通过第三方服务、爬虫或维基数据（Wikidata）间接获取
   - 可维护本地映射表（TMDb ID ↔ 豆瓣 ID）

3. **反向查找限制**：
   - `/find` 端点仅支持部分外部源（`imdb_id`、`tvdb_id` 等）
   - 不支持豆瓣 ID 反向查找

4. **数据质量**：
   - IMDb ID 覆盖率高（大部分电影都有）
   - TVDB ID 主要用于电视剧
   - 社交媒体 ID 可能缺失

5. **API 调用频率**：
   - 批量查询外部 ID 时，注意 API 限流
   - 建议缓存已查询的 ID 映射

6. **外部数据源 API**：
   - IMDb：无官方免费 API，可使用 OMDb API（http://www.omdbapi.com/）
   - 豆瓣：无官方 API，需爬虫或第三方服务
   - TVDB：需注册 API Key（https://www.thetvdb.com/）

---

### 端点对比

| 端点 | 查询方向 | 适用场景 | 覆盖率 |
|------|---------|---------|---------|
| `/movie/{id}/external_ids` | TMDb ID → 外部 ID | 获取 IMDb/TVDB ID | 高（IMDb） |
| `/person/{id}/external_ids` | TMDb ID → 外部 ID | 获取人物 IMDb ID | 高（IMDb） |
| `/find/{external_id}` | 外部 ID → TMDb ID | 反向查找 TMDb ID | 中 |

---

## Images & Configuration 端点对齐（官方 Reference）

本节对齐官方 Reference：
- https://developer.themoviedb.org/reference/configuration-details
- https://developer.themoviedb.org/reference/movie-images
- https://developer.themoviedb.org/reference/person-images

用途：
- 获取图片配置信息（URL、尺寸、质量）
- 获取电影/人物图片列表（海报、背景、头像等）
- 前端展示封面、演员头像、背景图等

### GET `/configuration`（获取图片配置）

**说明**：
- 获取 TMDb 图片系统的配置信息
- 包含图片基础 URL、支持的尺寸、质量等
- **必须先调用此端点**，才能正确构造图片 URL

**请求参数**：无（仅需 `api_key`）

**响应要点**：
```json
{
  "images": {
    "base_url": "http://image.tmdb.org/t/p/",
    "secure_base_url": "https://image.tmdb.org/t/p/",
    "backdrop_sizes": [
      "w300",
      "w780",
      "w1280",
      "original"
    ],
    "logo_sizes": [
      "w45",
      "w92",
      "w154",
      "w185",
      "w300",
      "w500",
      "original"
    ],
    "poster_sizes": [
      "w92",
      "w154",
      "w185",
      "w342",
      "w500",
      "w780",
      "original"
    ],
    "profile_sizes": [
      "w45",
      "w185",
      "h632",
      "original"
    ],
    "still_sizes": [
      "w92",
      "w185",
      "w300",
      "original"
    ]
  },
  "change_keys": [
    "adult",
    "air_date",
    "also_known_as"
  ]
}
```

**响应字段说明**：
- `images.base_url`：HTTP 图片基础 URL（不推荐，建议用 HTTPS）
- `images.secure_base_url`：HTTPS 图片基础 URL（**推荐使用**）
- `images.backdrop_sizes`：背景图支持的尺寸
  - `w300`：宽度 300px
  - `w780`：宽度 780px
  - `w1280`：宽度 1280px
  - `original`：原始尺寸
- `images.poster_sizes`：海报支持的尺寸
  - `w92`、`w154`、`w185`、`w342`、`w500`、`w780`、`original`
- `images.profile_sizes`：人物头像支持的尺寸
  - `w45`、`w185`、`h632`（固定高度）、`original`
- `images.still_sizes`：剧情截图支持的尺寸（电视剧）

**图片 URL 构造公式**：
```
图片完整 URL = {secure_base_url}{size}{file_path}
示例: https://image.tmdb.org/t/p/w500/poster_path.jpg
```

**官方参考**：
- https://developer.themoviedb.org/reference/configuration-details

---

### GET `/movie/{movie_id}/images`（电影图片列表）

**说明**：
- 获取指定电影的所有图片
- 包括海报（posters）、背景图（backdrops）、logo 等

**请求参数**（Path + Query）：
- `movie_id`（Path）：电影 ID
- `include_image_language`：图片语言（可选），如 `"en,null"` 或 `"zh,null"`
- `language`：语言（可选）

**响应要点**：
```json
{
  "id": 278,
  "backdrops": [
    {
      "aspect_ratio": 1.777,
      "height": 1080,
      "iso_639_1": null,
      "file_path": "/path1.jpg",
      "vote_average": 5.6,
      "vote_count": 12,
      "width": 1920
    }
  ],
  "posters": [
    {
      "aspect_ratio": 0.676,
      "height": 1500,
      "iso_639_1": "en",
      "file_path": "/path2.jpg",
      "vote_average": 5.8,
      "vote_count": 20,
      "width": 1000
    }
  ],
  "logos": [
    {
      "aspect_ratio": 1.5,
      "height": 300,
      "iso_639_1": null,
      "file_path": "/path3.png",
      "vote_average": 5.2,
      "vote_count": 5,
      "width": 450
    }
  ]
}
```

**响应字段说明**：
- `backdrops[]`：背景图列表
  - `file_path`：图片文件路径（需拼接 `base_url`）
  - `aspect_ratio`：宽高比（背景图通常为 1.777，即 16:9）
  - `width` / `height`：图片尺寸
  - `vote_average`：图片质量评分（0-10）
- `posters[]`：海报列表
  - `aspect_ratio`：宽高比（海报通常为 0.676，即 2:3）
  - `iso_639_1`：语言代码（如 `"en"`、`"zh"`，`null` 表示无文字）
- `logos[]`：电影 logo 列表

**官方参考**：
- https://developer.themoviedb.org/reference/movie-images

---

### GET `/person/{person_id}/images`（人物图片列表）

**说明**：
- 获取指定人物（演员/导演）的图片
- 包括头像、照片等

**请求参数**（Path + Query）：
- `person_id`（Path）：人物 ID
- `include_image_language`：图片语言（可选）

**响应要点**：
```json
{
  "id": 12345,
  "profiles": [
    {
      "aspect_ratio": 0.667,
      "height": 1500,
      "iso_639_1": null,
      "file_path": "/profile1.jpg",
      "vote_average": 5.5,
      "vote_count": 10,
      "width": 1000
    }
  ]
}
```

**响应字段说明**：
- `profiles[]`：人物头像/照片列表
  - `file_path`：图片文件路径
  - `aspect_ratio`：宽高比（通常为 0.667，即 2:3）
  - `width` / `height`：图片尺寸

**官方参考**：
- https://developer.themoviedb.org/reference/person-images

---

### GET `/tv/{series_id}/images`（电视剧图片列表）

**说明**：
- 获取指定电视剧的图片
- 结构与 Movie 版本一致

**响应要点**：
```json
{
  "id": 1396,
  "backdrops": [...],
  "posters": [...],
  "logos": [...]
}
```

**官方参考**：
- https://developer.themoviedb.org/reference/tv-images

---

### 使用场景示例

#### 场景 1：获取电影海报 URL

**需求**：前端需要显示电影海报

**实现**：
```python
import requests

def get_configuration():
    """获取图片配置（建议全局缓存）"""
    url = "https://api.themoviedb.org/3/configuration"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    return response.json()

def get_poster_url(poster_path: str, size: str = "w500") -> str:
    """
    构造海报 URL

    Args:
        poster_path: 海报路径（从电影详情获取）
        size: 图片尺寸（w92/w154/w185/w342/w500/w780/original）
    """
    config = get_configuration()
    base_url = config["images"]["secure_base_url"]
    return f"{base_url}{size}{poster_path}"

# 示例
poster_path = "/example.jpg"  # 从电影详情获取
poster_url = get_poster_url(poster_path, size="w500")
print(f"海报 URL: {poster_url}")
# 输出: 海报 URL: https://image.tmdb.org/t/p/w500/example.jpg
```

#### 场景 2：获取电影所有背景图

**需求**：前端轮播展示电影背景图

**实现**：
```python
def get_movie_backdrops(movie_id: int, language: str = "null") -> list:
    """
    获取电影背景图列表

    Args:
        movie_id: 电影 ID
        language: 语言（"null" 表示无文字，推荐用于背景图）
    """
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/images"
    params = {
        "api_key": TMDB_API_KEY,
        "include_image_language": f"{language},null"
    }
    response = requests.get(url, params=params)
    data = response.json()

    config = get_configuration()
    base_url = config["images"]["secure_base_url"]

    # 构造背景图 URL 列表
    backdrops = []
    for backdrop in data.get("backdrops", []):
        url = f"{base_url}w1280{backdrop['file_path']}"
        backdrops.append({
            "url": url,
            "width": backdrop["width"],
            "height": backdrop["height"],
            "vote_average": backdrop["vote_average"]
        })

    # 按评分降序
    backdrops.sort(key=lambda x: x["vote_average"], reverse=True)
    return backdrops[:10]  # 返回 Top 10

# 示例
backdrops = get_movie_backdrops(278)
print(f"找到 {len(backdrops)} 张背景图")
```

#### 场景 3：获取演员头像

**需求**：前端显示演员头像

**实现**：
```python
def get_person_avatars(person_id: int) -> list:
    """获取演员头像列表"""
    url = f"https://api.themoviedb.org/3/person/{person_id}/images"
    params = {"api_key": TMDB_API_KEY}
    response = requests.get(url, params=params)
    data = response.json()

    config = get_configuration()
    base_url = config["images"]["secure_base_url"]

    avatars = []
    for profile in data.get("profiles", []):
        url = f"{base_url}h632{profile['file_path']}"
        avatars.append({
            "url": url,
            "width": profile["width"],
            "height": profile["height"]
        })

    return avatars

# 示例
avatars = get_person_avatars(12345)
if avatars:
    print(f"演员头像: {avatars[0]['url']}")
```

#### 场景 4：根据设备选择图片尺寸

**需求**：根据设备分辨率选择合适的图片尺寸

**实现**：
```python
def get_optimal_size(device_width: int, image_type: str = "poster") -> str:
    """
    根据设备宽度选择最优图片尺寸

    Args:
        device_width: 设备宽度（px）
        image_type: 图片类型（"poster"/"backdrop"/"profile"）
    """
    config = get_configuration()

    if image_type == "poster":
        sizes = config["images"]["poster_sizes"]
    elif image_type == "backdrop":
        sizes = config["images"]["backdrop_sizes"]
    elif image_type == "profile":
        sizes = config["images"]["profile_sizes"]
    else:
        return "original"

    # 选择最接近设备宽度的尺寸
    # 去除 "original"，仅比较数字尺寸
    numeric_sizes = [s for s in sizes if s != "original"]

    # 提取尺寸数字
    size_map = []
    for size in numeric_sizes:
        if size.startswith("w"):
            width = int(size[1:])
        elif size.startswith("h"):
            width = int(size[1:])  # 对于固定高度的，暂用高度值
        else:
            continue
        size_map.append((width, size))

    # 选择最接近但不超过设备宽度的尺寸
    size_map.sort()
    for width, size in size_map:
        if width >= device_width:
            return size

    # 如果所有尺寸都小于设备宽度，返回最大尺寸
    return size_map[-1][1] if size_map else "original"

# 示例
mobile_size = get_optimal_size(375, "poster")    # 移动端
tablet_size = get_optimal_size(768, "poster")    # 平板
desktop_size = get_optimal_size(1920, "backdrop")  # 桌面端

print(f"移动端尺寸: {mobile_size}")   # w342
print(f"平板尺寸: {tablet_size}")     # w500
print(f"桌面端尺寸: {desktop_size}")  # w1280
```

---

### 重要说明

1. **配置缓存**：
   - `/configuration` 响应变化频率低，**建议全局缓存**
   - 避免每次请求图片时都调用配置端点

2. **HTTPS 推荐**：
   - 使用 `secure_base_url`（HTTPS）而非 `base_url`（HTTP）
   - 现代浏览器可能对 HTTP 图片发出警告

3. **图片尺寸选择**：
   - **移动端**：`w92`、`w154`（节省流量）
   - **平板**：`w342`、`w500`（平衡质量）
   - **桌面端**：`w780`、`w1280`、`original`（高质量）
   - 背景图推荐：`w1280`（1080p 屏幕）

4. **语言过滤**：
   - `include_image_language` 参数用于过滤图片语言
   - `"null"` 表示无文字的图片（推荐用于背景图）
   - `"zh,null"`：中文 + 无文字图片

5. **图片质量**：
   - `vote_average` 字段可用于筛选高质量图片
   - 建议选择评分 > 5.0 的图片

6. **路径拼接**：
   - `file_path` 包含前导 `/`
   - 拼接时无需添加额外 `/`

7. **错误处理**：
   - 图片可能不存在（`file_path` 为 `null`）
   - 建议使用默认占位图

---

### 端点对比

| 端点 | 用途 | 返回内容 | 调用频率 |
|------|------|---------|---------|
| `/configuration` | 获取图片配置 | base_url、支持的尺寸 | 一次性（缓存） |
| `/movie/{id}/images` | 获取电影图片 | backdrops、posters、logos | 按需 |
| `/person/{id}/images` | 获取人物图片 | profiles（头像） | 按需 |
| `/tv/{id}/images` | 获取电视剧图片 | backdrops、posters、logos | 按需 |

---

### 图片尺寸速查表

| 图片类型 | 推荐尺寸（移动端） | 推荐尺寸（平板） | 推荐尺寸（桌面） |
|---------|------------------|----------------|----------------|
| 海报（poster） | `w154`、`w185` | `w342`、`w500` | `w780`、`original` |
| 背景图（backdrop） | `w300`、`w780` | `w780`、`w1280` | `w1280`、`original` |
| 头像（profile） | `w45`、`w185` | `w185`、`h632` | `h632`、`original` |
| 剧情截图（still） | `w92`、`w185` | `w185`、`w300` | `w300`、`original` |

---

## 未来扩展机会

当前项目已覆盖 movie/person/tv 的"查询时增强（enrichment）"核心链路。潜在的扩展领域：

1. ✅ **趋势内容**: `GET /trending/{media_type}/{time_window}` 支持"近期热门/口碑"（已补充）
2. ✅ **观看平台**: `GET /watch/providers/movie`、`GET /watch/providers/tv` 做"哪里能看"（已补充）
3. ✅ **电视剧榜单**: `/tv/airing_today`、`/tv/popular` 等榜单（已补充）
4. ✅ **人物榜单**: `/person/popular` 热门人物（已补充）
5. ✅ **相似/推荐**: `GET /movie/{id}/similar`、`GET /movie/{id}/recommendations` 做"类似 X / 看完 X 还能看什么"（已补充）
6. ✅ **外部 ID**: `GET /movie/{id}/external_ids`、`GET /person/{id}/external_ids` 做 IMDb/Douban（如有）对齐与去重（已补充）
7. ✅ **图片/海报**: `/images` + `/configuration` 做封面/演员头像展示（前端体验）（已补充）
8. ✅ **类型列表**: `GET /genre/movie/list`、`GET /genre/tv/list` 做类型过滤、分类展示（已补充）
9. ✅ **评论内容**: `GET /movie/{id}/reviews`、`GET /tv/{id}/reviews` 做用户评论、情感分析（已补充）
10. ✅ **电影扩展**: Alternative Titles、Keywords、Latest、Lists、Release Dates、Translations、Videos 等电影详细信息（已补充）
11. ✅ **电影合集**: `GET /collection/{id}`、`/images`、`/translations` 做系列电影展示、观影顺序引导（已补充）
12. ✅ **电视剧扩展**: Alternative Titles、Content Ratings、Episode Groups、Keywords、Recommendations、Similar、Translations 等电视剧详细信息（已补充）

**总结**：所有 12 项核心扩展已完成文档化！

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
