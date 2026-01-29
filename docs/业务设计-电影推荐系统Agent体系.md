# 电影推荐系统 - 业务驱动的 Agent 体系设计

## 一、当前问题诊断

### 现状：技术实现 vs 业务需求

| 维度 | 当前实现 | 业务需求 | 差距 |
|------|---------|---------|------|
| **定位** | 通用 RAG 检索系统 | **电影推荐/搜索平台** | ❌ 缺少业务建模 |
| **Agent命名** | Naive/Graph/Hybrid/Deep/Fusion | ❌ 技术视角，用户无法理解 | ❌ 缺少业务语义 |
| **核心逻辑** | Query → Retrieve → Answer | **发现 → 探索 → 决策** | ❌ 缺少用户旅程 |
| **个性化** | 对话上下文记忆 | **用户画像 + 偏好模型** | ❌ 无推荐算法 |
| **推荐能力** | 检索相似电影 | **基于口味、场景、社交** | ❌ 无多维度推荐 |

---

## 二、电影业务核心场景分析

### 场景 1: 🎯 精准搜索 (What)
**用户意图**：明确知道自己想找什么
- "诺兰导演的科幻电影"
- "2020年后的高评分悬疑片"
- "梁朝伟和刘德华主演的电影"

**业务特点**：
- ✅ 结构化查询（导演、类型、演员、年份、评分）
- ✅ 结果可排序（评分、年份、热度）
- ✅ 当前系统**已覆盖**（HybridAgent）

---

### 场景 2: 💡 模糊探索 (Discover)
**用户意图**：想看电影但不确定具体哪部
- "我想看一些烧脑的科幻片"
- "有没有适合周末放松的喜剧"
- "最近有什么好看的科幻电影"

**业务特点**：
- 🟡 半结构化查询（情绪、场景、时间）
- 🟡 需要**用户画像**辅助（历史偏好、当前状态）
- ❌ 当前系统**部分覆盖**（缺少场景化推荐）

---

### 场景 3: 🎲 个性化推荐 (Recommend)
**用户意图**：不知道看什么，需要系统主动推荐
- "给我推荐几部电影"
- "今晚看什么？"
- [直接访问首页，自动推荐]

**业务特点**：
- 🔴 需要**用户画像**：
  - 看过什么？评分多少？（显式反馈）
  - 搜索历史、观看时长？（隐式反馈）
  - 喜欢的类型、导演、演员？（偏好模型）
- 🔴 需要**推荐算法**：
  - 协同过滤（"喜欢X的用户还喜欢Y"）
  - 内容过滤（"你喜欢的诺兰电影"）
  - 知识图谱推理（"因喜欢《星际穿越》，推荐《盗梦空间》"）
- ❌ 当前系统**完全不覆盖**

---

### 场景 4: 🔗 相似推荐 (Similar)
**用户意图**：基于某部电影找相似的
- "喜欢《肖申克的救赎》，还有类似的吗？"
- "有没有和《黑暗骑士》风格一样的？"

**业务特点**：
- 🟡 需要**多维度相似度**：
  - 类型/主题相似（同类型电影）
  - 导演/演员相似（同一创作者）
  - 剧情元素相似（逆袭、复仇、爱情）
  - 知识图谱路径（A → 导演 → B）
- 🟡 当前系统**部分覆盖**（向量相似度）

---

### 场景 5: 🎬 影单管理 (Playlist)
**用户意图**：管理个人观影清单
- "我的待看清单"
- "标记为看过"
- "给这部电影打5星"

**业务特点**：
- ✅ 需要**持久化存储**（Watchlist已实现）
- ✅ 需要**评分系统**（⚠️ 缺失）
- ✅ 需要**数据驱动推荐**（利用评分数据）

---

## 三、业务驱动的 Agent 体系重新设计

### 设计原则
1. **以用户任务为中心**，而非技术实现
2. **每个Agent对应一个明确的业务场景**
3. **Agent之间可组合**，形成完整推荐链路
4. **充分利用知识图谱**，而非仅做检索

---

### 新 Agent 体系架构

```
用户输入
    ↓
[意图识别 Router]
    ↓
    ├─→ [精准搜索 Agent] → SearchEngine
    ├─→ [模糊探索 Agent] → UserProfile + SearchEngine
    ├─→ [个性化推荐 Agent] → RecommendationEngine
    ├─→ [相似推荐 Agent] → SimilarityEngine
    ├─→ [影单管理 Agent] → WatchlistService
    └─→ [电影问答 Agent] → QAEngine
```

---

## 四、详细 Agent 设计

### Agent 1: 🔍 PrecisionSearchAgent (精准搜索)

**业务场景**：用户明确知道找什么

**输入示例**：
- "诺兰导演的科幻电影"
- "评分8.0以上的2010年代电影"
- "梁朝伟和巩莉主演的电影"

**核心能力**：
1. **结构化查询解析**
   ```python
   query = "诺兰导演的科幻电影"
   parsed = {
       "directors": ["克里斯托弗·诺兰"],
       "genres": ["科幻"],
       "filters": {},
       "sort_by": "rating"  # 默认按评分排序
   }
   ```

2. **多维度过滤**
   - 类型、导演、演员、年份、评分、国家、语言
   - 支持组合条件（AND/OR）

3. **结果排序**
   - 按评分、年份、热度、匹配度
   - 支持用户自定义排序

**实现要点**：
- ✅ **复用当前 HybridAgent**
- ✅ 增强：结构化过滤器（Cypher查询优化）
- ✅ 返回：结构化结果（JSON）+ 上下文（RAG生成）

**当前差距**：
- 🟡 需要增强过滤器语法
- 🟡 需要优化排序逻辑

---

### Agent 2: 🧭 ExploratorySearchAgent (模糊探索)

**业务场景**：用户想看电影但不确定具体什么

**输入示例**：
- "我想看一些烧脑的科幻片"
- "有没有适合周末放松的喜剧"
- "最近有什么好看的悬疑剧"

**核心能力**：
1. **场景化意图识别**
   ```python
   query = "适合周末放松的喜剧"
   parsed = {
       "scenario": "relax",  # 放松
       "mood": "happy",      # 快乐
       "time": "weekend",    # 周末
       "genres": ["喜剧"],
       "duration": "< 120min"  # 放松时不看太长的
   }
   ```

2. **用户画像增强**
   - 当前偏好（最近搜索/观看的类型）
   - 观看历史（避免重复推荐）
   - 评分记录（优先推荐高分类型）

3. **智能排序**
   - 新鲜度（最近上映）
   - 匹配度（符合场景）
   - 个性化（用户偏好）

**实现要点**：
- 🟡 **增强当前 HybridAgent**
- 🟡 新增：场景意图分类器（LLM）
- 🟡 新增：用户画像查询接口
- 🟡 新增：场景化排序规则

**当前差距**：
- ❌ 缺少用户画像模块
- ❌ 缺少场景意图识别

---

### Agent 3: 🎯 PersonalizedRecommendationAgent (个性化推荐)

**业务场景**：用户不知道看什么，需要主动推荐

**输入示例**：
- "给我推荐几部电影"
- "今晚看什么？"
- [无输入，直接访问首页]

**核心能力**：
1. **用户画像构建**
   ```python
   UserProfile = {
       "user_id": "123",
       # 显式反馈
       "ratings": {"movie_1": 5, "movie_2": 4},
       "watchlist": ["movie_3", "movie_4"],

       # 偏好模型
       "favorite_genres": ["科幻", "悬疑"],
       "favorite_directors": ["诺兰"],
       "favorite_actors": ["梁朝伟"],

       # 观看模式
       "watch_time": ["周末", "晚上"],
       "duration_preference": "90-120min",
       "language": ["中文", "英文"],
   }
   ```

2. **多策略推荐**
   ```python
   recommendations = []

   # 策略1: 协同过滤
   similar_users = find_similar_users(user_profile)
   recommendations.extend(collaborative_filtering(similar_users))

   # 策略2: 内容过滤
   recommendations.extend(content_based(user_profile))

   # 策略3: 知识图谱推理
   recommendations.extend(kg_reasoning(user_profile))

   # 策略4: 探索与利用
   recommendations.extend(exploration(user_profile))
   ```

3. **多样性排序**
   - 80% 匹配偏好（利用）
   - 20% 探索新类型（探索）
   - 避免同导演/演员过于集中

**实现要点**：
- ❌ **全新 Agent**
- ❌ 新增：UserProfile 数据模型
- ❌ 新增：RecommendationEngine（多种推荐算法）
- ❌ 新增：FeedbackCollector（评分/点赞/观看时长）

**当前差距**：
- ❌ 完全缺失

---

### Agent 4: 🔗 SimilarityRecommendationAgent (相似推荐)

**业务场景**：基于某部电影找相似的

**输入示例**：
- "喜欢《肖申克的救赎》，还有类似的吗？"
- "有没有和《黑暗骑士》风格一样的？"

**核心能力**：
1. **多维度相似度计算**
   ```python
   movie = "肖申克的救赎"

  相似度 = {
       "genre_similarity": 0.8,        # 同类型（剧情、犯罪）
       "director_similarity": 0.0,     # 不同导演
       "actor_similarity": 0.3,        # 部分相同演员
       "theme_similarity": 0.9,        # 主题相似（希望、救赎）
       "kg_path_similarity": 0.7,      # 图谱路径：都获奖、都改编自小说
       "embedding_similarity": 0.85,   # 向量相似度
   }

   final_score = weighted_average(相似度)
   ```

2. **知识图谱路径推理**
   ```
   肖申克的救赎 → [改编自小说] → 绿里奇迹
   肖申克的救赎 → [主演: 摩根·弗里曼] → 不可饶恕
   肖申克的救赎 → [类型: 剧情片] → 美丽心灵
   肖申克的救赎 → [主题: 希望] → 阿甘正传
   ```

3. **可解释性推荐**
   - "因为你也喜欢《肖申克的救赎》的【剧情】【希望主题】"
   - "推荐《阿甘正传》"

**实现要点**：
- 🟡 **复用当前 GraphAgent**
- 🟡 增强：多维度相似度计算
- 🟡 增强：知识图谱路径查询
- 🟡 新增：可解释性文案生成

**当前差距**：
- 🟡 有基础能力，需要增强

---

### Agent 5: 📋 WatchlistManagerAgent (影单管理)

**业务场景**：用户管理个人观影清单

**输入示例**：
- "我的待看清单"
- "标记《星际穿越》为看过"
- "给这部电影打5星"

**核心能力**：
1. **CRUD 操作**
   - 添加到待看清单
   - 标记为看过/在看
   - 删除/归档
   - 评分/标签

2. **数据驱动推荐**
   - 基于评分数据优化推荐
   - 基于观看历史调整排序

3. **清单分享**
   - 导出清单（分享给朋友）
   - 导入朋友清单

**实现要点**：
- ✅ **已有基础**（WatchlistStore）
- ✅ 增强：评分系统
- 🟡 新增：标签系统
- 🟡 新增：分享功能

**当前差距**：
- 🟡 缺少评分系统

---

### Agent 6: 💬 MovieQAAgent (电影问答)

**业务场景**：用户想了解电影相关信息

**输入示例**：
- "《星际穿越》的结局是什么意思？"
- "诺兰的电影都有什么共同特点？"
- "漫威宇宙的时间线是怎样的？"

**核心能力**：
1. **剧情解析**
   - 结局解读
   - 彩蛋解析
   - 人物关系

2. **知识推理**
   - 导演风格分析
   - 系列电影关联
   - 票房/获奖数据

3. **多轮对话**
   - 上下文记忆
   - 追问澄清

**实现要点**：
- ✅ **复用当前 FusionGraphRAGAgent**
- ✅ 增强：剧情分析能力
- ✅ 增强：多轮对话优化

**当前差距**：
- 🟡 基本满足，可以优化

---

## 五、数据模型设计

### 5.1 用户画像 (UserProfile)

```python
@dataclass
class UserProfile:
    user_id: str

    # 显式反馈
    ratings: Dict[str, float]  # {movie_id: rating}
    watchlist: List[str]       # [movie_id]
    tags: Dict[str, List[str]]  # {movie_id: ["烧脑", "反转"]}

    # 偏好模型（自动学习）
    favorite_genres: List[str]
    favorite_directors: List[str]
    favorite_actors: List[str]
    favorite_themes: List[str]

    # 观看模式
    watch_time_preference: List[str]  # ["周末", "晚上"]
    duration_preference: str  # "90-120min"
    language_preference: List[str]

    # 更新时间
    updated_at: datetime

    def update_from_feedback(self, feedback: UserFeedback):
        """增量更新用户画像"""
        pass
```

### 5.2 用户反馈 (UserFeedback)

```python
@dataclass
class UserFeedback:
    user_id: str
    movie_id: str

    # 显式反馈
    rating: Optional[float]  # 1-5星
    is_watched: bool
    tags: List[str]  # 用户标签

    # 隐式反馈
    watch_duration: Optional[int]  # 观看时长（秒）
    click_count: int  # 点击次数
    last_interaction: datetime

    # 场景信息
    scenario: Optional[str]  # "周末放松", "工作日晚上"
```

---

## 六、推荐算法设计

### 6.1 协同过滤 (Collaborative Filtering)

```python
def collaborative_filtering(user_id: str, top_k: int = 10):
    """基于用户的协同过滤"""

    # 1. 找到相似用户
    similar_users = find_similar_users(
        user_id,
        method="cosine",  # 余弦相似度
        top_n=50
    )

    # 2. 聚合相似用户的喜好
    candidate_movies = {}
    for similar_user in similar_users:
        for movie_id, rating in similar_user.ratings.items():
            if movie_id not in current_user.watched:
                candidate_movies[movie_id] = (
                    candidate_movies.get(movie_id, 0) +
                    rating * similar_user.similarity
                )

    # 3. 排序返回
    return sorted(candidate_movies.items(), key=lambda x: x[1], reverse=True)[:top_k]
```

### 6.2 内容过滤 (Content-Based)

```python
def content_based_filtering(user_profile: UserProfile, top_k: int = 10):
    """基于内容的推荐"""

    scores = {}

    # 1. 基于类型偏好
    for genre in user_profile.favorite_genres:
        for movie in get_movies_by_genre(genre):
            scores[movie.id] = scores.get(movie.id, 0) + 0.3

    # 2. 基于导演偏好
    for director in user_profile.favorite_directors:
        for movie in get_movies_by_director(director):
            scores[movie.id] = scores.get(movie.id, 0) + 0.4

    # 3. 基于演员偏好
    for actor in user_profile.favorite_actors:
        for movie in get_movies_by_actor(actor):
            scores[movie.id] = scores.get(movie.id, 0) + 0.2

    # 4. 基于向量相似度
    preferred_movies = get_highly_rated_movies(user_profile)
    for movie in all_movies:
        for preferred in preferred_movies:
            similarity = cosine_similarity(movie.embedding, preferred.embedding)
            if similarity > 0.7:
                scores[movie.id] = scores.get(movie.id, 0) + similarity * 0.1

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
```

### 6.3 知识图谱推理 (KG Reasoning)

```python
def kg_reasoning(user_profile: UserProfile, top_k: int = 10):
    """基于知识图谱的推理推荐"""

    recommendations = []

    # 1. 基于图谱路径推理
    for movie_id in user_profile.get_highly_rated_movies():
        # 路径1: 电影 → 导演 → 其他电影
        director = get_movie_director(movie_id)
        other_movies = get_director_movies(director)
        recommendations.extend(other_movies)

        # 路径2: 电影 → 类型 → 高评分电影
        genres = get_movie_genres(movie_id)
        for genre in genres:
            top_movies = get_top_rated_by_genre(genre)
            recommendations.extend(top_movies)

        # 路径3: 电影 → 主演 → 其他电影
        actors = get_movie_actors(movie_id)
        for actor in actors:
            other_movies = get_actor_movies(actor)
            recommendations.extend(other_movies)

    # 2. 基于主题社区
    community = get_movie_community(movie_id)
    recommendations.extend(get_community_movies(community))

    # 3. 去重排序
    return deduplicate_and_rank(recommendations, user_profile)[:top_k]
```

---

## 七、实施路线图

### Phase 1: 基础能力完善 (2周)

**目标**：补齐缺失的基础模块

1. **评分系统**
   - [ ] 数据模型：`UserRating`
   - [ ] API：`POST /api/v1/ratings`
   - [ ] 前端：评分组件（星星评分）
   - [ ] 存储：PostgreSQL `user_ratings` 表

2. **用户行为追踪**
   - [ ] 数据模型：`UserBehavior`
   - [ ] 前端埋点：点击、观看时长、搜索
   - [ ] 后端接收：`POST /api/v1/behavior`
   - [ ] 数据处理：ETL 到数据仓库

3. **用户画像模块**
   - [ ] 数据模型：`UserProfile`
   - [ ] 构建逻辑：从行为数据学习偏好
   - [ ] 更新机制：增量更新/定期重训练
   - [ ] API：`GET /api/v1/profile`

---

### Phase 2: 核心推荐引擎 (3周)

**目标**：实现推荐算法

1. **RecommendationEngine 基础框架**
   - [ ] 抽象接口：`RecommendationEngine`
   - [ ] 实现类：`CollaborativeFiltering`, `ContentBased`, `KGReasoning`
   - [ ] 组合器：`HybridRecommendationEngine`

2. **算法实现**
   - [ ] 协同过滤（用户相似度）
   - [ ] 内容过滤（偏好匹配）
   - [ ] 知识图谱推理（路径查询）
   - [ ] 探索与利用策略

3. **推荐服务**
   - [ ] API：`GET /api/v1/recommendations?user_id=xxx`
   - [ ] 排序：多样性、新鲜度、个性化
   - [ ] 可解释性：返回推荐理由

---

### Phase 3: 业务 Agent 重构 (2周)

**目标**：从技术 Agent 转向业务 Agent

1. **新增业务 Agent**
   - [ ] `PrecisionSearchAgent` (复用 HybridAgent)
   - [ ] `ExploratorySearchAgent` (增强 HybridAgent)
   - [ ] `PersonalizedRecommendationAgent` (全新)
   - [ ] `SimilarityRecommendationAgent` (增强 GraphAgent)

2. **Router 增强**
   - [ ] 意图分类：搜索/探索/推荐/相似
   - [ ] 用户画像查询
   - [ ] Agent 选择策略

3. **Prompt 优化**
   - [ ] 业务化 prompt 模板
   - [ ] 个性化 prompt 变量

---

### Phase 4: 前端体验优化 (1周)

**目标**：提供符合用户心智的界面

1. **推荐首页**
   - [ ] "为你推荐"卡片（个性化）
   - [ ] "热门电影"（基于热度）
   - [ ] "新片速递"（基于时间）
   - [ ] "猜你喜欢"（基于历史）

2. **搜索优化**
   - [ ] 结构化筛选器（类型/导演/年份）
   - [ ] 搜索建议（自动补全）
   - [ ] 搜索历史

3. **影单管理**
   - [ ] 待看/在看/看过标签页
   - [ ] 评分界面
   - [ ] 标签管理

---

## 八、关键指标

### 业务指标
- **推荐准确率**：用户评分预测准确度
- **推荐覆盖率**：长尾电影推荐比例
- **用户参与度**：日活、观看时长
- **转化率**：推荐 → 观看转化

### 技术指标
- **召回率**：相关电影召回比例
- **多样性**：推荐结果类型分布
- **新颖性**：推荐新电影比例
- **响应时间**：推荐生成速度

---

## 九、总结

### 核心转变

| 维度 | 从 | 到 |
|------|---|---|
| **视角** | 技术实现 | 用户任务 |
| **Agent命名** | Naive/Graph/Hybrid | PrecisionSearch/Exploratory/Recommendation |
| **核心逻辑** | Query → Retrieve → Answer | Discover → Explore → Decide |
| **个性化** | 对话上下文 | 用户画像 + 偏好模型 |
| **推荐** | 检索相似 | 协同过滤 + 内容过滤 + KG推理 |

### 下一步行动

1. ✅ **确认业务优先级**（从哪个场景开始）
2. ✅ **设计数据模型**（UserProfile, UserFeedback）
3. ✅ **实现推荐算法**（从简单到复杂）
4. ✅ **重构 Agent 体系**（业务语义化）
5. ✅ **优化前端体验**（符合用户心智）

---

**问题**：你希望优先实现哪个场景？
- A. 精准搜索（立即可用）
- B. 个性化推荐（核心价值）
- C. 相似推荐（增强现有）
- D. 影单管理（基础建设）
