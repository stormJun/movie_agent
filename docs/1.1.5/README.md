# 1.1.5 Query-Time Enrichment（查询时知识增强）

本版本介绍 **Query-Time Enrichment** 机制，解决 GraphRAG 知识库覆盖不足的问题。

---

## 背景

当前 GraphRAG 基于 MovieLens sample 数据（仅 1000 部电影，主要是 1995-1996 年），无法覆盖所有用户查询。

**问题案例**:
```
用户: "喜宴 导演是谁？"
系统: "未识别出任何实体明确提及《喜宴》及其导演李安..."
```

**原因**: 《喜宴》(1993) 不在源数据中

---

## 解决方案

当 GraphRAG 检索失败或置信度低时:
1. **意图识别优先**: 利用现有 `route_kb_prefix` 判断是否 movie 领域
2. **仅 movie 领域增强**: edu/general 直接返回，不调用 TMDB
3. 自动查询 TMDB API
4. 异步增量更新 GraphRAG 知识库
5. 同时返回结果给用户

**流程**:
```
用户查询 → 意图识别 (route_kb_prefix)
         ↓
    movie 领域?
         ↓
    是 → GraphRAG 检索 → 低置信度 → TMDB 查询 → 写入 Neo4j → 返回答案
                                              ↓
                                      异步后台：重新向量化
    否 → 直接返回（不调用 TMDB）
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [1.1.5.1 Query-Time Enrichment 详细设计](./1.1.5.1/query-time-enrichment.md) | 完整设计方案，包含架构、组件、集成方式 |
| [1.1.5.4 电影业务下的 RAG Agent 组合策略](./1.1.5.4/movie-rag-business-integration.md) | 将检索能力与电影业务问题分型/输出契约对齐（从技术实现走向产品能力） |

---

## 核心组件

1. **EntityExtractor** - 从查询中提取电影/人物实体
2. **TMDBEnrichmentService** - TMDB API 查询服务
3. **IncrementalCacheStore** - TMDB 结果永久存储
4. **IncrementalGraphWriter** - 增量写入 Neo4j
5. **ChatStreamExecutor 增强** - 在检索流程中嵌入增强逻辑

---

## 关键设计

| 决策点 | 方案 | 理由 |
|--------|------|------|
| **意图识别优先** | 利用现有 `route_kb_prefix` | 复用已有逻辑，非 movie 领域不调用 TMDB |
| **增强触发时机** | route 之后，`kb_prefix == "movie"` | 只有电影相关问题才需要 TMDB 增强 |
| 同步 vs 异步 | TMDB 查询同步，写入异步 | 用户等待 1s 可接受，写入 5-10s 需异步 |
| 缓存策略 | Postgres 永久存储 | 避免重复调用 TMDB API，方便核对数据 |
| 去重机制 | 基于 `tmdb_id` 的 MERGE | 幂等性，避免脏数据 |
| 触发条件 | max_score < 0.3 | 平衡召回率与成本 |
| 答案来源标注 | 标记 "TMDB" vs "GraphRAG" | 透明度，用户可信度 |

---

## 配置

```bash
# .env
TMDB_API_KEY=your_api_key
ENABLE_ENRICHMENT=true
ENRICHMENT_THRESHOLD=0.3
```

---

## 成本估算

- 日活 100 用户，每人触发 1 次增强
- 缓存命中率 70%
- **实际 API 调用**: ~900 / month
- **成本**: TMDB 免费层 (1000/day) 可覆盖

---

## 实施计划

- **Phase 1** (Week 1-2): 核心功能实现
- **Phase 2** (Week 3): GraphRAG 集成
- **Phase 3** (Week 4): 优化与监控

---

## 相关文档

- [1.1.4 Chat History Evolution](../1.1.4/chat-history-evolution.md) - 对话历史管理
- [02-核心机制/01-graphrag构建流程.md](../../02-核心机制/01-graphrag构建流程.md) - GraphRAG 构建流程
