# TMDB API v3 参考文档

## 概述

The Movie Database (TMDB) API v3 是一个 REST API，提供关于电影、电视剧和影视行业人物的综合数据。本文档总结了所有可用的端点，并标识了 Movie Agent 项目中当前使用的端点。

**API 基础 URL**: `https://api.themoviedb.org/3`

**官方文档**: https://developer.themoviedb.org/reference/getting-started

---

## 端点总览

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
| `/discover/movie` | GET | 按条件发现电影 | ❌ |
| `/discover/tv` | GET | 按条件发现电视剧 | ❌ |

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
| `/person/{person_id}` | GET | 获取人物详情 | ❌ |
| `/person/{person_id}/changes` | GET | 获取人物变更 | ❌ |
| `/person/{person_id}/combined_credits` | GET | 获取人物综合演职员作品 | ❌ |
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
| `/search/movie` | GET | 搜索电影 | ✅ |
| `/search/multi` | GET | 多实体搜索 | ❌ |
| `/search/person` | GET | 搜索人物 | ❌ |
| `/search/tv` | GET | 搜索电视剧 | ❌ |

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
| `/tv/{tv_id}` | GET | 获取电视剧详情 | ❌ |
| `/tv/{tv_id}/account_states` | GET | 获取电视剧账户状态 | ❌ |
| `/tv/{tv_id}/alternative_titles` | GET | 获取电视剧别名 | ❌ |
| `/tv/{tv_id}/changes` | GET | 获取电视剧变更 | ❌ |
| `/tv/{tv_id}/content_ratings` | GET | 获取电视剧内容分级 | ❌ |
| `/tv/{tv_id}/credits` | GET | 获取电视剧演职员 | ❌ |
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

Movie Agent 项目当前仅使用 TMDB API v3 的 **2 个端点**：

| 端点 | 方法 | 用途 | 实现位置 |
|----------|--------|---------|----------------|
| `/search/movie` | GET | 根据标题搜索电影 | `backend/infrastructure/enrichment/tmdb_client.py` |
| `/movie/{movie_id}` | GET | 获取电影详情及演职员 | `backend/infrastructure/enrichment/tmdb_client.py` |

### 实现详情

#### 1. 搜索端点 (`/search/movie`)

**位置**: `backend/infrastructure/enrichment/tmdb_client.py:86-126`

**用法**:
```python
async def search_movie(self, title: str) -> dict[str, Any] | None:
    """根据标题搜索电影并获取完整详情。"""
```

**请求参数**:
- `query`（必需）：要搜索的电影标题
- `language`: 默认为 "zh-CN" 以获取中文结果
- `page`: 默认为 1

**响应**:
```json
{
  "page": 1,
  "results": [
    {
      "id": 12345,
      "title": "电影标题",
      "original_title": "原始标题",
      "release_date": "1993-01-01",
      "poster_path": "/path.jpg",
      "backdrop_path": "/path.jpg",
      "vote_average": 7.5,
      "overview": "电影描述..."
    }
  ],
  "total_pages": 1,
  "total_results": 1
}
```

**流程**:
1. 调用 `/search/movie` 传入电影标题
2. 提取第一个结果的 `id`
3. 调用 `get_movie_details()` 传入该 ID
4. 返回完整电影详情

#### 2. 电影详情端点 (`/movie/{movie_id}`)

**位置**: `backend/infrastructure/enrichment/tmdb_client.py:128-196`

**用法**:
```python
async def get_movie_details(self, movie_id: int) -> dict[str, Any] | None:
    """获取电影详细信息，包括演职员。"""
```

**请求参数**:
- `movie_id`（必需）：TMDB 电影 ID
- `language`: 默认为 "zh-CN"
- `append_to_response`: 设置为 "credits" 以在一次调用中包含演员和剧组信息

**响应**:
```json
{
  "id": 12345,
  "title": "电影标题",
  "original_title": "原始标题",
  "release_date": "1993-01-01",
  "runtime": 120,
  "genres": [{"id": 18, "name": "剧情"}],
  "overview": "电影描述...",
  "poster_path": "/path.jpg",
  "backdrop_path": "/path.jpg",
  "vote_average": 7.5,
  "credits": {
    "cast": [
      {
        "id": 67890,
        "name": "演员姓名",
        "character": "角色名称",
        "order": 1,
        "profile_path": "/path.jpg"
      }
    ],
    "crew": [
      {
        "id": 11111,
        "name": "导演姓名",
        "job": "Director",
        "department": "Directing",
        "profile_path": "/path.jpg"
      }
    ]
  }
}
```

**优化策略**:
- 使用 `append_to_response=credits` 在 **一次 API 调用**中同时获取电影详情和演职员信息
- 避免单独调用 `/movie/{movie_id}/credits`

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

## API 密钥配置

**环境变量**: `TMDB_API_KEY`

**配置位置**: `backend/infrastructure/config/settings.py`
```python
TMDB_API_KEY: str = Field(default="", env="TMDB_API_KEY")
```

**基础 URL**: `https://api.themoviedb.org/3`

**默认语言**: `zh-CN`（中文）

---

## 未来扩展机会

当前项目仅使用电影相关端点。潜在的扩展领域：

1. **电视剧支持**: 使用电视剧端点扩展知识库
2. **人物详情**: 使用 `/person/{person_id}` 丰富演员/导演信息
3. **发现功能**: 使用 `/discover/movie` 处理推荐查询
4. **趋势内容**: 使用 `/trending/movie/day` 处理热门电影查询
5. **相似电影**: 使用 `/movie/{movie_id}/similar` 处理"类似 X 的电影"查询

---

## 参考资料

- TMDB API v3 文档: https://developer.themoviedb.org/reference/getting-started
- TMDB API 状态: https://status.themoviedb.org/
- TMDB 开发者社区: https://www.themoviedb.org/talk

---

**文档版本**: 1.0
**最后更新**: 2026-01-26
**API 版本**: TMDB API v3
