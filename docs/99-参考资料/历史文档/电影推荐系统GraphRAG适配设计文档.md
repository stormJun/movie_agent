# 电影推荐系统 GraphRAG 适配设计文档

## 文档信息

| 项目 | 信息 |
|------|------|
| **文档版本** | v1.0 |
| **创建日期** | 2025-12-26 |
| **项目名称** | GraphRAG 电影推荐系统 |
| **基础框架** | GraphRAG + Deep Search + Multi-Agent |
| **数据源** | MovieLens (SparrowRecSys) |
| **目标** | 将基于学生管理规章制度的 GraphRAG 系统适配为电影知识图谱和推荐系统 |

---

## 目录

1. [项目背景与目标](#1-项目背景与目标)
2. [系统架构设计](#2-系统架构设计)
3. [知识图谱设计](#3-知识图谱设计)
4. [数据迁移方案](#4-数据迁移方案)
5. [多智能体系统设计](#5-多智能体系统设计)
6. [检索与搜索策略](#6-检索与搜索策略)
7. [推荐算法集成](#7-推荐算法集成)
8. [实施路线图](#8-实施路线图)
9. [性能与扩展性](#9-性能与扩展性)
10. [测试与评估](#10-测试与评估)

---

## 1. 项目背景与目标

### 1.1 项目概述

本项目旨在将现有的 **GraphRAG + Deep Search** 框架（当前应用于华东理工大学学生管理规章制度）适配为 **电影推荐和知识问答系统**。通过结合 SparrowRecSys 的 MovieLens 数据和 GraphRAG 的知识图谱推理能力，构建一个兼具推荐和问答能力的智能系统。

### 1.2 核心目标

#### **主要目标**
1. **知识图谱构建**：从结构化电影数据（CSV）构建电影知识图谱
2. **智能问答**：支持电影相关的自然语言问答（推荐、查询、解释）
3. **多模态推荐**：结合图谱推理、协同过滤、内容推荐的混合推荐
4. **可解释性**：基于知识图谱的推荐解释（为什么推荐这部电影）

#### **次要目标**
1. **领域迁移验证**：验证 GraphRAG 框架从规章制度到推荐系统的可迁移性
2. **增量更新**：支持新电影、新评分的增量图谱更新
3. **用户画像**：构建基于图谱的用户兴趣画像

### 1.3 应用场景

| 场景类型 | 示例问题 | 使用的 Agent/策略 |
|---------|---------|------------------|
| **推荐类** | "推荐一些科幻电影" | HybridAgent / FusionGraphRAGAgent |
| **查询类** | "《肖申克的救赎》的评分是多少？" | Local Search / NaiveRAG |
| **比较类** | "《盗梦空间》和《星际穿越》哪个更受欢迎？" | Global Search / DeepResearch |
| **解释类** | "为什么推荐这部电影给我？" | Local Search + Community Detection |
| **探索类** | "有哪些类似《泰坦尼克号》的爱情片？" | Hybrid Search (图遍历) |
| **统计分析** | "评分最高的电影类型是什么？" | Global Search (社区聚合) |

---

## 2. 系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户交互层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Streamlit UI │  │  FastAPI     │  │  REST API    │              │
│  │  Frontend    │  │  Backend     │  │  Endpoints   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      多智能体编排层                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │        FusionGraphRAGAgent (Plan-Execute-Report)             │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │  │
│  │  │ Planner │→│Executor │→│Reporter │  │Reviewer │         │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  NaiveRAG    │  │  GraphAgent  │  │ HybridAgent  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐                               │
│  │ DeepResearch │  │ Multi-Agent  │                               │
│  │    Agent     │  │  Coordinator │                               │
│  └──────────────┘  └──────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         搜索工具层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Local Search │  │Global Search │  │ Naive Search │              │
│  │ (实体中心)   │  │ (社区聚合)   │  │ (向量检索)   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐                               │
│  │ Hybrid Search│  │ Deep Research│                               │
│  │ (多策略融合) │  │ (链式探索)   │                               │
│  └──────────────┘  └──────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         知识图谱层                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Neo4j Graph Database                     │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │  │
│  │  │ Movie    │  │ User     │  │ Genre    │  │ Rating   │    │  │
│  │  │ Entity   │  │ Entity   │  │ Entity   │  │ Relation │    │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │  │
│  │  │ Director │  │ Actor    │  │ Community│                    │  │
│  │  │ Entity   │  │ Entity   │  │ Detection│                    │  │
│  │  └──────────┘  └──────────┘  └──────────┘                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       数据处理层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Data         │  │ Entity       │  │ Community    │              │
│  │ Ingestion    │  │ Extraction   │  │ Detection    │              │
│  │ (CSV/TXT/MD) │  │ (LLM-based)  │  │ (Leiden/SLLPA)│              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐                               │
│  │ Entity       │  │ Vector       │                               │
│  │ Disambiguation││ Indexing     │                               │
│  └──────────────┘  └──────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         数据源层                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ movies.csv   │  │ ratings.csv  │  │ links.csv    │              │
│  │ (电影元数据) │  │ (评分记录)   │  │ (外部ID)     │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐                               │
│  │ MovieLens    │  │ 人工编写的   │                               │
│  │ 文档资料     │  │ 领域文档     │                               │
│  └──────────────┘  └──────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术组件 | 说明 |
|------|---------|------|
| **用户交互** | Streamlit, FastAPI | 前端 UI 和后端 API |
| **智能体编排** | LangGraph | 工作流编排 |
| **LLM** | OpenAI API / DeepSeek | 问答、推理、实体抽取 |
| **向量检索** | Neo4j Vector Index | 实体和文本块的向量索引 |
| **图数据库** | Neo4j + GDS | 知识图谱存储和图算法 |
| **数据处理** | Pandas, Python | CSV 处理和特征工程 |

---

## 3. 知识图谱设计

### 3.1 实体类型定义

```python
# backend/graphrag_agent/config/settings.py
entity_types = [
    "电影",           # Movie: 核心实体
    "用户",           # User: 评分者
    "类型",           # Genre: Action, Comedy, etc.
    "导演",           # Director: 可扩展
    "演员",           # Actor: 可扩展
    "年代",           # Year: 上映年代（如"90年代"）
    "评分等级",       # RatingLevel: 高分/中分/低分
    "系列",           # Franchise: 如"漫威电影宇宙"
]
```

#### **实体属性设计**

| 实体类型 | 属性字段 | 示例 |
|---------|---------|------|
| **电影** | movieId, title, year, genres, avgRating, ratingCount | `movieId: 1, title: "Toy Story", year: 1995, avgRating: 3.92` |
| **用户** | userId, avgRating, ratingCount, favoriteGenre | `userId: 1, avgRating: 3.5, ratingCount: 200` |
| **类型** | genreName, description | `genreName: "Sci-Fi", description: "科幻电影"` |
| **导演** | directorName, movieCount | `directorName: "Christopher Nolan"` |
| **演员** | actorName, movieCount | `actorName: "Tom Hanks"` |
| **年代** | decade, yearRange | `decade: "1990s", yearRange: "1990-1999"` |

### 3.2 关系类型定义

```python
relationship_types = [
    # 基础关系（从数据直接提取）
    "评分",           # User -> Movie (with rating property)
    "属于",           # Movie -> Genre
    "执导",           # Director -> Movie
    "主演",           # Actor -> Movie
    "上映于",         # Movie -> Year

    # 推导关系（通过图算法生成）
    "相似",           # Movie -> Movie (基于 embedding 余弦相似度)
    "同类型",         # Movie -> Movie (共享 genre)
    "同年代",         # Movie -> Movie (同年份或年代)
    "同导演",         # Movie -> Movie (同一导演)
    "同演员",         # Movie -> Movie (共享演员)

    # 社区关系（通过社区检测）
    "同社区",         # Movie -> Movie (在同一社区)

    # 偏好关系（用户行为推导）
    "偏爱",           # User -> Genre (用户对某类型评分高)
    "收藏",           # User -> Movie (评分 >= 4.0)
]
```

### 3.3 图谱模式（Schema）

#### **Neo4j 图模式**

```cypher
// 电影实体
(:Movie {
  movieId: Integer,
  title: String,
  year: Integer,
  genres: [String],
  avgRating: Float,
  ratingCount: Integer,
  embedding: [Float]  // 向量嵌入
})

// 用户实体
(:User {
  userId: Integer,
  avgRating: Float,
  ratingCount: Integer,
  embedding: [Float]
})

// 类型实体
(:Genre {
  name: String,
  movieCount: Integer
})

// 关系
(:User)-[:RATED {rating: Float, timestamp: Long}]->(:Movie)
(:Movie)-[:BELONGS_TO]->(:Genre)
(:Movie)-[:SIMILAR_TO {similarity: Float}]->(:Movie)
(:Movie)-[:IN_COMMUNITY {communityId: Integer}]->(:Movie)
```

### 3.4 社区检测策略

#### **社区划分逻辑**
1. **类型社区**：按 genre 聚类（如"科幻电影社区"）
2. **年代社区**：按上映年代聚类（如"90年代经典电影"）
3. **评分社区**：按评分分布聚类（如"高分电影社区"）
4. **图算法社区**：使用 Leiden/SLLPA 算法自动发现社区

#### **社区摘要生成**
为每个社区生成 LLM 摘要，用于全局搜索：
```
社区 "Sci-Fi Classics":
- 包含《盗梦空间》《星际穿越》《黑客帝国》等经典科幻片
- 平均评分 4.2，主要受众为科幻爱好者
- 代表作品特征：烧脑剧情、哲学思考、视觉特效
```

---

## 4. 数据迁移方案

### 4.1 数据源分析

#### **SparrowRecSys 数据文件**

| 文件名 | 大小 | 记录数 | 字段 | 用途 |
|--------|------|--------|------|------|
| `movies.csv` | ~50KB | 982 | movieId, title, genres | 电影元数据 |
| `ratings.csv` | ~30MB | 1,168,639 | userId, movieId, rating, timestamp | 用户评分 |
| `links.csv` | ~40KB | 982 | movieId, imdbId, tmdbId | 外部 ID |
| `trainingSamples.csv` | ~15MB | 88,828 | 26个特征字段 | 训练样本 |
| `testSamples.csv` | ~4MB | 22,441 | 26个特征字段 | 测试样本 |
| `item2vecEmb.csv` | ~100KB | 982 | movieId + 10维向量 | 电影嵌入 |
| `userEmb.csv` | ~500KB | 671 | userId + 10维向量 | 用户嵌入 |

### 4.2 数据转换策略

#### **策略 A：CSV 转 Markdown（推荐）**

将结构化 CSV 转换为 Markdown 文档，利用现有的文档处理流程。

**示例：movies.csv → 电影列表.md**
```markdown
# 电影列表

## Toy Story (1995)
- **电影ID**: 1
- **类型**: Adventure | Animation | Children | Comedy | Fantasy
- **IMDb ID**: 0114709
- **TMDb ID**: 862
- **平均评分**: 3.92
- **评分人数**: 313

## Jumanji (1995)
- **电影ID**: 2
- **类型**: Adventure | Children | Fantasy
- **IMDb ID**: 0113497
- **TMDb ID**: 8844
...
```

**示例：ratings.csv → 用户评分精选.md（采样）**
```markdown
# 用户评分记录

## 用户 1 的评分
- 《玩具总动员》(Toy Story, 1995): 3.5/5 (2005年3月12日)
- 《朱曼吉》(Jumanji, 1995): 3.5/5 (2005年3月12日)
...

## 用户 2 的评分
- 《玩具总动员》(Toy Story, 1995): 5.0/5 (1997年9月20日)
- 《天地大冲撞》(Deep Impact, 1998): 3.0/5 (1997年9月20日)
...
```

#### **策略 B：直接 CSV 导入（扩展 ingestion 模块）**

在 `backend/infrastructure/pipelines/ingestion/` 中添加专用 CSV 处理器。

**优势**：
- 保留原始数据结构
- 避免文本转换损失
- 支持批量导入

**劣势**：
- 需要额外的代码开发
- 需要处理 CSV → 图谱的映射逻辑

### 4.3 数据采样策略（性能优化）

由于全量数据（117 万条评分）可能导致图谱过大，建议分阶段导入：

#### **阶段 1：小规模测试（POC）**
```
- 电影数：50 部（高评分电影）
- 用户数：50 位（活跃用户）
- 评分数：~2,000 条
- 目标：验证流程和实体抽取质量
```

#### **阶段 2：中等规模**
```
- 电影数：200 部
- 用户数：200 位
- 评分数：~10,000 条
- 目标：测试推荐效果和社区检测
```

#### **阶段 3：全量导入（可选）**
```
- 电影数：982 部
- 用户数：671 位
- 评分数：117 万条
- 目标：生产环境部署
```

### 4.4 增量数据更新

基于 `file_registry.json` 和 `incremental_update.py`，支持：

1. **新电影上架**：检测到 `movies.csv` 新增行 → 增量抽取实体和关系
2. **新评分产生**：检测到 `ratings.csv` 新增行 → 更新用户-电影关系
3. **数据修正**：检测到文件修改 → 使用冲突策略更新（`manual_first` / `auto_first` / `merge`）

---

## 5. 多智能体系统设计

### 5.1 Agent 职责划分

| Agent | 适用场景 | 搜索策略 | 示例问题 |
|-------|---------|---------|---------|
| **NaiveRAG** | 简单事实查询 | 向量检索 | "《肖申克的救赎》的评分是多少？" |
| **GraphAgent** | 关系推理 | Local Search | "导演诺兰还导演过哪些电影？" |
| **HybridAgent** | 多维度查询 | Hybrid Search | "推荐一些科幻喜剧电影" |
| **DeepResearch** | 复杂探索 | 链式探索 | "分析近十年科幻电影的演变趋势" |
| **FusionGraphRAG** | 综合分析 | Plan-Execute-Report | "生成一份2024年电影推荐报告" |

### 5.2 Plan-Execute-Report 工作流

#### **Plan 阶段**
```python
输入: "推荐一些类似《盗梦空间》的烧脑电影"

Planner 输出:
- 子任务1: 解析《盗梦空间》的特征（类型、导演、主题）
- 子任务2: 查找相似特征的电影
- 子任务3: 评估候选电影的评分和口碑
- 子任务4: 生成推荐列表和理由
```

#### **Execute 阶段**
```python
Executor 工作流:
- 调用 Local Search: 获取《盗梦空间》的实体信息
- 调用 Graph Traversal: 查找 SIMILAR_TO 关系的电影
- 调用 Global Search: 获取"烧脑电影"社区的摘要
- 记录证据链: 《盗梦空间》→ Sci-Fi → Christopher Nolan → 高评分社区
```

#### **Report 阶段**
```python
Reporter 输出:
# 类似《盗梦空间》的烧脑电影推荐

## 推荐列表
1. **《星际穿越》** (2014)
   - 相似度: 0.92
   - 推荐理由: 同样由诺兰执导，科幻烧脑题材，涉及时空概念
   - 评分: 8.6/10

2. **《黑客帝国》** (1999)
   - 相似度: 0.88
   - 推荐理由: 同属经典科幻片，探讨现实与虚拟的哲学命题
   - 评分: 8.7/10

3. **《蝴蝶效应》** (2004)
   - 相似度: 0.85
   - 推荐理由: 时间旅行题材，复杂的因果逻辑
   - 评分: 7.6/10
```

### 5.3 Agent 工具注册

在 `backend/graphrag_agent/search/tool_registry.py` 中注册电影领域专用工具：

```python
# 新增电影推荐工具
tools = [
    NaiveSearchTool(...),
    LocalSearchTool(...),
    GlobalSearchTool(...),
    MovieRecommendationTool(...),  # 新增
    SimilarMovieFinderTool(...),   # 新增
    UserPreferenceAnalyzerTool(...), # 新增
]
```

---

## 6. 检索与搜索策略

### 6.1 Local Search（实体中心检索）

#### **应用场景**
- 查询特定电影的详细信息
- 基于实体的推荐（如"这个导演的其他作品"）

#### **工作流程**
```python
# 示例：查询《盗梦空间》的相关信息
1. 提取实体: "《盗梦空间》" → Movie Entity
2. 向量检索: 找到相似实体（Top K movies）
3. 邻域探索: 获取该电影的
   - 直接关系: BELONGS_TO Genre, DIRECTED_BY Director
   - 多跳关系: Director → (其他作品) → Movies
4. 社区上下文: 该电影所属社区的其他电影
5. 生成回答: 融合以上信息生成答案
```

#### **Neo4j 查询示例**
```cypher
// 查找《盗梦空间》的相似电影（同导演 + 高评分）
MATCH (m:Movie {title: "Inception"})-[:DIRECTED_BY]->(d:Director)
MATCH (d)-[:DIRECTED_BY]->(other:Movie)
WHERE other.avgRating >= 4.0 AND other <> m
RETURN other.title, other.avgRating, other.year
ORDER BY other.avgRating DESC
LIMIT 5
```

### 6.2 Global Search（社区聚合检索）

#### **应用场景**
- 宏观分析（如"哪个类型的电影评分最高"）
- 社区级别的推荐（如"经典科幻电影"）

#### **工作流程**
```python
# 示例：分析电影类型评分分布
1. 社区检测: 按 Genre 进行社区划分
2. 社区摘要: 为每个 Genre 生成统计摘要
   - Action: 平均 3.8 分，200 部电影
   - Drama: 平均 4.1 分，150 部电影
3. 社区排序: 按平均评分降序排列
4. 生成报告: "评分最高的类型是 Drama (4.1)，代表作品包括..."
```

### 6.3 Hybrid Search（混合检索）

#### **应用场景**
- 复杂查询（如"推荐一些既搞笑又感人的电影"）
- 多约束条件推荐

#### **工作流程**
```python
# 示例：推荐"搞笑又感人的电影"
1. 向量检索: 找到"喜剧"和"剧情"类型的电影
2. 图遍历: 查找同时属于 Comedy 和 Drama 社区的电影
3. 过滤: avgRating >= 4.0
4. 排序: 按 ratingCount 和 avgRating 综合排序
5. 返回: Top 10 电影及推荐理由
```

### 6.4 Deep Research（链式探索）

#### **应用场景**
- 深度分析（如"分析诺兰导演的电影风格演变"）
- 多跳推理

#### **工作流程**
```python
# 示例：分析诺兰导演风格
1. 初始查询: 找到所有诺兰导演的电影
2. 迭代探索:
   - 步骤1: 查看这些电影的类型分布 → 发现偏好科幻和惊悚
   - 步骤2: 查看这些电影的评分趋势 → 评分逐步上升
   - 步骤3: 查看主要演员合作 → 与 Christian Bale, Cillian Murphy 合作多次
3. 证据收集: 每一步记录证据（电影名、评分、类型）
4. 综合分析: 生成"诺兰导演风格演变"报告
```

---

## 7. 推荐算法集成

### 7.1 传统推荐方法集成

将 SparrowRecSys 的现有推荐算法与 GraphRAG 集成：

#### **7.1.1 协同过滤（ALS）**

```python
# 从 SparrowRecSys 导入 ALS 模型
from sparrowsrcsys.offline.spark.model import CollaborativeFiltering

# 在 GraphRAG 中使用
class CollaborativeFilteringTool:
    def recommend(self, user_id: int, top_k: int = 10):
        """为用户生成基于协同过滤的推荐"""
        # 调用 ALS 模型
        recommendations = als_model.recommendForAllUsers(top_k)
        return recommendations
```

#### **7.1.2 Item2Vec / DeepWalk 嵌入**

```python
# 使用预训练的电影嵌入
def find_similar_movies(movie_id: int, top_k: int = 10):
    """基于 Item2Vec 嵌入查找相似电影"""
    movie_embedding = embeddings[movie_id]
    similarities = cosine_similarity(movie_embedding, all_embeddings)
    top_similar = similarities.argsort()[-top_k:][::-1]
    return top_similar
```

### 7.2 图谱增强推荐

#### **7.2.1 图谱推理推荐**

```python
def graph_based_recommendation(user_id: int, top_k: int = 10):
    """基于知识图谱推理的推荐"""

    # 1. 分析用户偏好
    user_favorite_genres = get_user_favorite_genres(user_id)
    user_high_rated_movies = get_user_high_rated_movies(user_id, threshold=4.0)

    # 2. 图谱遍历
    recommendations = []
    for movie in user_high_rated_movies:
        # 查找同类型、同导演、相似的电影
        similar_movies = neo4j.execute("""
            MATCH (m:Movie {movieId: $movieId})-[:SIMILAR_TO|BELONGS_TO|DIRECTED_BY]-(other:Movie)
            WHERE NOT (u:User {userId: $userId})-[:RATED]->(other)
            RETURN other.movieId, other.title, other.avgRating
            LIMIT 5
        """, movieId=movie, userId=user_id)
        recommendations.extend(similar_movies)

    # 3. 去重和排序
    unique_recs = deduplicate(recommendations)
    ranked_recs = rank_by_score(unique_recs,
                                 score=calculate_hybrid_score)  # 融合图谱特征

    return ranked_recs[:top_k]
```

#### **7.2.2 可解释推荐**

```python
def explain_recommendation(user_id: int, movie_id: int):
    """生成推荐理由"""

    # 从图谱提取解释路径
    explanation_paths = neo4j.execute("""
        MATCH path = (u:User {userId: $userId})-[:RATED]->(m1:Movie)-[:SIMILAR_TO]-(m2:Movie {movieId: $movieId})
        RETURN [m1.title, m2.avgRating, "相似电影"] AS reason

        UNION

        MATCH (u:User {userId: $userId})-[:RATED]->(m1:Movie)-[:BELONGS_TO]->(g:Genre)<-[:BELONGS_TO]-(m2:Movie {movieId: $movieId})
        RETURN [m1.title, g.name, "同类型"] AS reason
    """, userId=user_id, movieId=movie_id)

    # 生成自然语言解释
    llm_prompt = f"""
    基于以下证据生成推荐理由：
    - 用户喜欢《{explanation_paths[0][0]}》
    - 推荐电影《{movie_title}》与用户喜欢的电影{explanation_paths[0][2]}
    """

    return llm.generate(llm_prompt)
```

### 7.3 混合推荐架构

```python
class HybridMovieRecommender:
    """混合推荐系统"""

    def __init__(self):
        self.cf_recommender = CollaborativeFilteringTool()
        self.graph_recommender = GraphBasedRecommender()
        self.embedding_recommender = EmbeddingBasedRecommender()

    def recommend(self, user_id: int, top_k: int = 10):
        """融合多种推荐策略"""

        # 1. 获取各方法的推荐结果
        cf_recs = self.cf_recommender.recommend(user_id, top_k * 2)
        graph_recs = self.graph_recommender.recommend(user_id, top_k * 2)
        embedding_recs = self.embedding_recommender.recommend(user_id, top_k * 2)

        # 2. 融合打分
        final_scores = {}
        for movie_id in set(cf_recs + graph_recs + embedding_recs):
            final_scores[movie_id] = (
                0.4 * cf_recs.get(movie_id, 0) +
                0.4 * graph_recs.get(movie_id, 0) +
                0.2 * embedding_recs.get(movie_id, 0)
            )

        # 3. 排序返回
        ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        return [movie_id for movie_id, score in ranked[:top_k]]
```

---

## 8. 实施路线图

### 8.1 阶段划分

#### **Phase 1: 环境准备与数据转换（1-2天）**

| 任务 | 描述 | 输出 |
|------|------|------|
| 1.1 备份现有配置 | 备份 `.env` 和 `settings.py` | 配置备份文件 |
| 1.2 修改配置文件 | 更新主题、实体类型、关系类型 | 修改后的 `settings.py` |
| 1.3 数据转换脚本 | 编写 CSV → Markdown 转换脚本 | `convert_movie_data.py` |
| 1.4 准备测试数据 | 转换 50 部电影 + 50 位用户的数据 | `files/` 目录下的文档 |

#### **Phase 2: 知识图谱构建（2-3天）**

| 任务 | 描述 | 输出 |
|------|------|------|
| 2.1 数据摄入 | 运行 ingestion pipeline | 文本块和初步实体 |
| 2.2 实体抽取 | LLM 抽取电影、用户、类型实体 | 实体库 |
| 2.3 实体消歧 | 对齐重复实体 | 消歧后的实体库 |
| 2.4 关系抽取 | 提取 RATED, BELONGS_TO 等关系 | 关系库 |
| 2.5 社区检测 | 运行 Leiden/SLLPA 算法 | 社区划分结果 |
| 2.6 向量索引 | 构建实体和文本块向量索引 | Neo4j Vector Index |

#### **Phase 3: 查询测试与调优（2-3天）**

| 任务 | 描述 | 输出 |
|------|------|------|
| 3.1 启动服务 | 启动 FastAPI + Streamlit | 可用的服务 |
| 3.2 基础查询测试 | 测试 NaiveRAG、GraphAgent | 测试报告 |
| 3.3 复杂查询测试 | 测试 HybridAgent、DeepResearch | 测试报告 |
| 3.4 推荐测试 | 测试电影推荐功能 | 推荐质量报告 |
| 3.5 性能调优 | 优化索引、缓存、批处理 | 优化后的配置 |

#### **Phase 4: 全量数据导入（可选，3-5天）**

| 任务 | 描述 | 输出 |
|------|------|------|
| 4.1 扩展数据转换 | 转换全部 982 部电影数据 | 完整数据文档 |
| 4.2 分批导入 | 分批次导入 Neo4j | 完整知识图谱 |
| 4.3 性能测试 | 测试全量数据下的查询性能 | 性能基准报告 |
| 4.4 生产部署 | 部署到生产环境 | 生产系统 |

### 8.2 关键里程碑

```
Week 1:
├─ Day 1-2: 环境准备 + 配置修改
├─ Day 3-4: 数据转换 + 测试数据准备
└─ Day 5: 初步图谱构建 + 基础查询验证

Week 2:
├─ Day 1-2: 社区检测 + 向量索引
├─ Day 3-4: Agent 测试 + 推荐功能验证
└─ Day 5: 性能调优 + 文档完善

Week 3 (可选):
├─ Day 1-3: 全量数据导入
└─ Day 4-5: 生产部署 + 监控配置
```

---

## 9. 性能与扩展性

### 9.1 性能瓶颈与优化

#### **9.1.1 数据摄入性能**

| 瓶颈 | 优化方案 | 预期提升 |
|------|---------|---------|
| LLM 实体抽取慢 | 批量处理 + 并行调用 | 3-5x |
| Neo4j 写入慢 | 使用 UNWIND 批量插入 | 5-10x |
| 向量生成慢 | 调整 `EMBEDDING_BATCH_SIZE` | 2-3x |

#### **9.1.2 查询性能**

| 瓶颈 | 优化方案 | 预期提升 |
|------|---------|---------|
| 图遍历慢 | 添加 Neo4j 索引（movieId, userId） | 10-100x |
| 向量检索慢 | 使用 Neo4j Vector Index vs 自计算 | 5-20x |
| 社区检测慢 | 调整 `GDS_MEMORY_LIMIT` + 并发度 | 2-5x |

### 9.2 扩展性设计

#### **9.2.1 水平扩展**

```python
# Neo4j 因果集群
# - 3个 Core 节点（读+写）
# - 2个 Read Replica 节点（只读）

# FastAPI 多进程部署
# - 使用 gunicorn + uvicorn workers
# - Nginx 负载均衡

# 缓存层
# - Redis 缓存热点查询结果
# - 向量相似度缓存（已有）
```

#### **9.2.2 垂直扩展**

```python
# Neo4j
# - 增加 JVM 堆内存（heap size）
# - 启用页面缓存（page cache）

# 应用层
# - 增加 `MAX_WORKERS`（并行线程）
# - 增加批处理大小（`BATCH_SIZE`, `ENTITY_BATCH_SIZE`）
```

### 9.3 缓存策略

#### **查询缓存**
```python
# 三级缓存架构
L1: 内存缓存（应用层）
   └─ 热点查询结果（TTL: 10分钟）

L2: 向量相似度缓存（已有）
   └─ cache/ 目录，持久化

L3: Neo4j 查询缓存
   └─ Neo4j 内置查询计划缓存
```

#### **实体缓存**
```python
# 预加载热门实体
popular_movies = neo4j.execute("""
    MATCH (m:Movie)
    WHERE m.ratingCount > 100
    RETURN m.movieId, m.title, m.avgRating
    ORDER BY m.ratingCount DESC
    LIMIT 100
""")

# 缓存到 Redis 或内存
cache.set("popular_movies", popular_movies, ttl=3600)
```

---

## 10. 测试与评估

### 10.1 功能测试

#### **10.1.1 基础查询测试**

| 测试用例 | 输入 | 预期输出 | Agent |
|---------|------|---------|-------|
| 电影详情查询 | "《肖申克的救赎》的评分是多少？" | 评分、年份、导演 | NaiveRAG |
| 类型查询 | "有哪些科幻电影？" | 科幻电影列表 | GraphAgent |
| 推荐查询 | "推荐一些类似《盗梦空间》的电影" | 相似电影推荐 | HybridAgent |
| 比较查询 | "诺兰导演的电影有哪些？" | 诺兰作品列表 | Local Search |
| 统计分析 | "评分最高的电影类型是什么？" | Drama, 4.1分 | Global Search |

#### **10.1.2 复杂推理测试**

| 测试用例 | 输入 | 预期输出 | Agent |
|---------|------|---------|-------|
| 多约束推荐 | "推荐90年代的高分科幻片" | 90年代科幻高分列表 | DeepResearch |
| 用户偏好分析 | "分析用户1的电影偏好" | 喜欢Sci-Fi和Drama | FusionGraphRAG |
| 趋势分析 | "近十年电影评分趋势" | 评分逐年上升的报告 | Multi-Agent |

### 10.2 推荐质量评估

#### **10.2.1 离线指标**

使用 SparrowRecSys 的 `testSamples.csv` 进行评估：

```python
# 评估指标
metrics = {
    "Precision@K": precision_at_k(recommendations, ground_truth, k=10),
    "Recall@K": recall_at_k(recommendations, ground_truth, k=10),
    "NDCG@K": ndcg_at_k(recommendations, ground_truth, k=10),
    "MAP": mean_average_precision(recommendations, ground_truth),
}
```

#### **10.2.2 在线指标**

```python
# A/B 测试配置
A组: GraphRAG 推荐系统
B组: 原始 SparrowRecSys (ALS)

# 观察指标
- 点击率 (CTR)
- 转化率（用户实际观看）
- 用户满意度（评分）
- 推荐多样性
- 推荐新颖性
```

#### **10.2.3 可解释性评估**

```python
# 人工评估推荐理由质量
explanation_quality = {
    "相关性": "理由与推荐电影的匹配度",
    "可理解性": "用户能否理解推荐逻辑",
    "说服力": "理由是否增加用户点击意愿",
    "准确性": "理由是否基于真实的图谱证据"
}
```

### 10.3 性能基准测试

#### **10.3.1 查询延迟**

| 查询类型 | 目标延迟 | 实测延迟 | 优化措施 |
|---------|---------|---------|---------|
| 简单查询（NaiveRAG） | < 1s | ___ | 向量索引优化 |
| 图遍历（Local Search） | < 3s | ___ | Neo4j 索引 |
| 社区聚合（Global Search） | < 5s | ___ | 缓存社区摘要 |
| 深度研究（DeepResearch） | < 10s | ___ | 并行化探索 |
| 推荐生成（Hybrid） | < 3s | ___ | 预计算相似度 |

#### **10.3.2 吞吐量**

```python
# 负载测试配置
concurrent_users = [10, 50, 100, 500]
requests_per_user = 100

# 测试指标
- 平均响应时间
- P95/P99 延迟
- 成功率
- 错误率
```

### 10.4 鲁棒性测试

#### **10.4.1 边界情况**

| 测试场景 | 输入 | 预期行为 |
|---------|------|---------|
| 空查询 | "" | 返回提示信息 |
| 不存在的电影 | "《不存在的电影》" | 返回"未找到" |
| 超长查询 | 1000字以上 | 截断或分段处理 |
| 并发请求 | 100个并发 | 全部成功，无崩溃 |
| 数据异常 | 评分=0或评分=10 | 过滤异常值 |

#### **10.4.2 容错测试**

```python
# Neo4j 断连模拟
neo4j.disconnect()
→ 系统应优雅降级，返回缓存结果或错误提示

# LLM API 超时模拟
llm.set_timeout(0)
→ 使用备用 LLM 或返回简化答案

# 缓存失效模拟
cache.clear()
→ 系统应能重建缓存，不影响核心功能
```

---

## 11. 风险与挑战

### 11.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **实体抽取质量差** | 推荐准确率低 | 中 | 添加电影领域的少样本示例到 LLM prompt |
| **图谱规模过大** | 查询性能下降 | 高 | 分阶段导入，采用采样策略 |
| **LLM 成本过高** | 运营成本超支 | 中 | 使用本地模型（如 DeepSeek）+ 缓存 |
| **增量更新失败** | 数据不一致 | 低 | 严格的冲突解决策略 + 事务管理 |

### 11.2 数据风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **CSV 格式变化** | 数据导入失败 | 低 | 添加数据验证和格式检测 |
| **评分数据缺失** | 用户画像不完整 | 中 | 使用默认值或插值 |
| **外部 API 失效** | IMDb/TMDb 数据无法获取 | 低 | 缓存外部数据，降级到本地数据 |

### 11.3 迁移风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **原有配置丢失** | 无法恢复学生管理主题 | 低 | 完整备份配置文件 |
| **依赖冲突** | 代码无法运行 | 中 | 使用虚拟环境 + 固定依赖版本 |
| **文档不完善** | 团队成员无法理解系统 | 中 | 编写详细的迁移文档和 API 文档 |

---

## 12. 后续优化方向

### 12.1 功能扩展

1. **用户画像增强**
   - 基于图谱的用户兴趣社区
   - 时序用户偏好演化分析

2. **多模态推荐**
   - 集成电影海报、预告片的视觉特征
   - 融合影评文本的情感分析

3. **社交推荐**
   - 添加用户社交网络关系（如有）
   - 基于社交图谱的推荐

4. **实时推荐**
   - 集成 Flink 流处理（参考 SparrowRecSys nearline 层）
   - 实时更新用户兴趣和推荐列表

### 12.2 技术优化

1. **LLM 优化**
   - 针对电影领域微调 LLM
   - 使用更小的本地模型降低成本

2. **图谱优化**
   - 实体对齐算法改进（处理电影别名、译名）
   - 关系抽取的置信度评估

3. **性能优化**
   - Neo4j Causal Cluster 部署
   - CDN 加速静态资源
   - 查询结果预计算

### 12.3 产品化

1. **前端优化**
   - 更丰富的可视化（电影知识图谱探索）
   - 个性化推荐界面

2. **API 设计**
   - RESTful API 规范化
   - GraphQL 支持灵活查询
   - API 限流和鉴权

3. **监控与运维**
   - 日志聚合（ELK Stack）
   - 性能监控（Prometheus + Grafana）
   - 告警系统

---

## 13. 总结

本文档详细描述了将 GraphRAG 框架从学生管理领域迁移到电影推荐系统的完整设计方案。核心要点包括：

### **13.1 可行性**
- ✅ **高度可行**：GraphRAG 框架完全适配电影推荐领域
- ✅ **数据兼容**：MovieLens CSV 数据可通过转换脚本处理
- ✅ **架构通用**：多智能体、知识图谱、检索策略均无需修改核心代码

### **13.2 关键优势**
1. **可解释推荐**：基于知识图谱的推荐理由生成
2. **多模态查询**：支持推荐、查询、分析、推理等多种场景
3. **增量更新**：支持新电影、新评分的实时更新
4. **领域迁移**：验证了 GraphRAG 框架的可迁移性

### **13.3 预期成果**
- **功能**：电影知识问答 + 智能推荐 + 趋势分析
- **性能**：查询延迟 < 3秒，推荐准确率 > 80%
- **扩展性**：支持全量数据（982部电影，117万评分）

---

## 附录

### A. 配置文件修改清单

```python
# backend/graphrag_agent/config/settings.py 修改点

# 1. 知识库主题
KB_NAME = "电影推荐系统"
theme = "电影知识图谱"

# 2. 实体类型
entity_types = [
    "电影", "用户", "类型", "导演", "演员", "年代", "评分等级", "系列"
]

# 3. 关系类型
relationship_types = [
    "评分", "属于", "执导", "主演", "上映于",
    "相似", "同类型", "同年代", "同导演", "同演员",
    "同社区", "偏爱", "收藏"
]

# 4. 示例问题
examples = [
    "推荐一些科幻电影",
    "《盗梦空间》的评分是多少？",
    "诺兰导演的电影有哪些？",
    "有哪些类似《肖申克的救赎》的电影？",
    "评分最高的电影类型是什么？"
]

# 5. Agent 工具描述
lc_description = (
    "用于需要具体电影信息的查询。检索电影数据库中的具体电影、评分、演员、导演等详细内容。"
    "适用于'某部电影的评分'、'某个演员演过哪些电影'等问题。"
)
gl_description = (
    "用于需要总结归纳的查询。分析电影类型的整体特征、用户偏好分布、推荐系统策略等宏观内容。"
    "适用于'电影类型分布'、'用户观影偏好分析'等需要系统性分析的问题。"
)
```

### B. 数据转换脚本框架

```python
# scripts/convert_movie_data.py

import pandas as pd
from pathlib import Path

def convert_movies_to_markdown(movies_csv: Path, output_md: Path):
    """将 movies.csv 转换为 Markdown 文档"""
    df = pd.read_csv(movies_csv)

    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("# 电影列表\n\n")
        for _, row in df.iterrows():
            f.write(f"## {row['title']} ({row['title'].extract_year()})\n")
            f.write(f"- **电影ID**: {row['movieId']}\n")
            f.write(f"- **类型**: {row['genres']}\n")
            f.write("\n")

def convert_ratings_to_markdown(ratings_csv: Path, output_md: Path, sample_size: int = 1000):
    """将 ratings.csv 采样并转换为 Markdown 文档"""
    df = pd.read_csv(ratings_csv)
    sampled = df.sample(min(sample_size, len(df)))

    # 按用户分组
    grouped = sampled.groupby('userId')

    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("# 用户评分记录\n\n")
        for user_id, group in grouped:
            f.write(f"## 用户 {user_id} 的评分\n")
            for _, row in group.iterrows():
                f.write(f"- 电影ID {row['movieId']}: {row['rating']}/5\n")
            f.write("\n")

if __name__ == "__main__":
    base_path = Path("../SparrowRecSys-master/src/main/resources/webroot/sampledata")
    output_path = Path("../files")

    convert_movies_to_markdown(
        base_path / "movies.csv",
        output_path / "电影列表.md"
    )

    convert_ratings_to_markdown(
        base_path / "ratings.csv",
        output_path / "用户评分记录.md",
        sample_size=1000
    )
```

### C. 测试用例集

```python
# tests/test_movie_queries.py

TEST_CASES = [
    # 基础查询
    {
        "query": "《肖申克的救赎》的评分是多少？",
        "expected_agent": "naive_rag_agent",
        "expected_keywords": ["肖申克的救赎", "评分", "9.3"]
    },
    # 关系查询
    {
        "query": "诺兰导演的电影有哪些？",
        "expected_agent": "graph_agent",
        "expected_keywords": ["诺兰", "盗梦空间", "星际穿越", "蝙蝠侠"]
    },
    # 推荐查询
    {
        "query": "推荐一些科幻电影",
        "expected_agent": "hybrid_agent",
        "expected_keywords": ["科幻", "推荐"]
    },
    # 比较查询
    {
        "query": "《盗梦空间》和《星际穿越》哪个评分更高？",
        "expected_agent": "graph_agent",
        "expected_keywords": ["盗梦空间", "星际穿越", "比较"]
    },
    # 统计分析
    {
        "query": "评分最高的电影类型是什么？",
        "expected_agent": "fusion_graph_rag_agent",
        "expected_keywords": ["类型", "评分", "最高"]
    }
]
```

---

**文档结束**
