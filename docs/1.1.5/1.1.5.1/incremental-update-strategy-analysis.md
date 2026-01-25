# GraphRAG 增量更新策略分析：Microsoft GraphRAG vs LightRAG

**日期**: 2026-01-25
**背景**: 在设计 [Query-Time Enrichment](./query-time-enrichment.md) 时，我们探讨了 "TriggerReindex" 的可行性，并对比了不同架构的优劣。

---

## 1. 核心问题

**Q: 为什么 Microsoft GraphRAG 需要“全局重跑” (Global Re-run)？不能增量更新吗？**

**A:**
Microsoft GraphRAG 的核心机制是 **社区发现 (Community Detection)**，通常使用 Leiden 算法。
*   **机制**: 它将全库数万个节点聚类成层级化的社区（Level 0-3），并为每个社区生成摘要（Community Summary）。
*   **痛点**: 社区划分是全局拓扑相关的。插入一个新的节点（如《喜宴》），可能会导致原本分离的两个社区合并，或者改变社区的重心。
*   **结论**: 为了更新 High-level 的社区摘要（用于回答宏观问题），必须对全量数据重新运行聚类算法（O(N)），无法做到低成本的实时增量（O(1)）。

---

## 2. 架构对比

### 2.1 Microsoft GraphRAG (Current Architecture)

*   **设计哲学**: **"Pre-computation" (预计算)**。
*   **宏观理解来源**: 预先生成的社区报告 (Community Reports)。
*   **增量能力**: **弱**。
    *   **Local Search (微观事实)**: 支持增量（只要写入点/边/向量）。
    *   **Global Search (宏观趋势)**: 不支持增量（必须等待 Batch 重跑）。
*   **我们的策略 (Hybrid)**:
    *   **Sync**: API 数据注入 Context（即时生效）。
    *   **Async**: 写入点/边/向量（Local Search 即时生效），但 **推迟** 社区聚类（Global Search 延迟生效）。
    *   **理由**: 用户对“新知识”的诉求通常是查具体事实，而非立刻要求宏观分析。

### 2.2 LightRAG (Alternative)

*   **设计哲学**: **"Vectorize Everything" (万物向量化)**。
*   **宏观理解来源**: **High-dimensional Retrieval (高维检索)**。
*   **增量能力**: **强 (O(1))**。
*   **机制**:
    *   LightRAG 放弃了笨重的“社区聚类”。
    *   **入库 (Profiling)**: 每个节点（Entity）和每条边（Relation）在入库时，都会通过 LLM 生成一段详细的描述，并计算 Embedding。
    *   **查询 (Retrieval)**: 当问宏观问题（如“李安的主题”）时，系统通过向量检索直接找到相关的“关系描述”（例如 `(李安)-[探讨]->(家庭伦理)` 的描述向量），实时拼凑出宏观答案。
*   **结论**: LightRAG 通过把计算成本从“检索时/批处理时”转移到“写入时”，实现了真正的增量更新。

---

## 4. 其他行业替代方案 (Industry Alternatives)

除了 LightRAG，业界还有解决“宏观理解 + 增量更新”的其他流派：

### 4.1 RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval)
*   **来源**: *Sarthi et al. (Stanford University), ICLR 2024*. ([Paper: arXiv:2401.18059](https://arxiv.org/abs/2401.18059))
*   **核心理念**: **"树状摘要" (Tree of Summaries)**。
*   **机制**:
    *   自底向上构建一棵摘要树。叶子节点是文本块，父节点是子节点的聚类摘要。
    *   **增量优势**: 插入新文档时，只需要更新它所属的那一个**树分支 (Branch)**，而不需要重建整棵树。复杂度从 O(N) 降为 O(log N)。
*   **宏观能力**: 查询时检索树的上层节点，天生具备宏观视角。
*   **适用性**: 适合文档型知识库，但在“实体关系密集”的图谱场景下，不如 GraphRAG 直观。

### 4.2 HippoRAG (Hippocampus RAG)
*   **来源**: *Gutierrez et al. (The Ohio State University), arXiv 2024*. ([Paper: arXiv:2405.14831](https://arxiv.org/abs/2405.14831))
*   **核心理念**: **"PageRank 游走" (Graph Traversal)**。
*   **机制**:
    *   **不做预聚类**。不生成 Community Summary。
    *   **查询时 (Query Time)**: 通过 Personalized PageRank (PPR) 算法，从与 Query 相关的节点出发，在图上“游走”，找到那些虽然没有直接关键词匹配、但拓扑结构紧密的节点。
*   **增量优势**: **完全增量**。因为没有 Community 预计算，新节点插进去，下次游走自然会走到它。
*   **宏观能力**: 通过图的连通性隐式体现（比如“李安”的所有电影自然会聚在一起）。
*   **代价**: Query Time 计算量稍大（但在现在的图数据库上不是问题）。

### 4.3 MemoRAG (TheWebConf 2025)
*   **来源**: *Qian et al., TheWebConf 2025*. ([Paper: arXiv:2409.05591](https://arxiv.org/abs/2409.05591))
*   **核心理念**: **"Dual-System" (Global Memory + Local Retrieval)**。
*   **机制**:
    *   **Light LLM (System 1)**: 一个轻量级长窗口模型，阅读全库（或摘要），负责形成“全局记忆”。
    *   **Heavy LLM (System 2)**: 负责生成答案。
    *   **宏观能力**: 当用户问宏观问题时，System 1 基于全局记忆生成模糊的 "Clues"（线索），指引 System 2 去检索具体的证据。
*   **增量优势**: 只要更新 System 1 的上下文（或轻量微调），就能感知新数据。它绕过了复杂的图谱聚类，用 LLM 本身的 Context 来承载宏观理解。
*   **适用性**: 适合没有图谱基础设施，但希望拥有全局理解能力的场景。
*   **缺陷 (Limitations)**:
    1.  **Context 扩容瓶颈**: 虽然 System 1 是轻量模型，但如果数据量达到 TB 级，仍无法全量塞入 Context，必须做分片或压缩，导致“全局记忆”破碎。
    2.  **延迟 (Latency)**: 查询必须经过 `System 1 (Clues) -> System 2 (Answer)` 的串行过程，比直接检索慢。
    3.  **可解释性差**: 它的“全局记忆”存在于模型的 Context/Weights 中，是隐性的。不像 GraphRAG 有明确的 `(A)-[Edge]->(B)`，很难 debug 为什么它认为两个东西相关。

### 4.4 Graphiti (2024/2025)
*   **核心理念**: **"Temporally-Aware Dynamic Graph" (时序感知动态图)**。
*   **机制**:
    *   专为 **AI Agents** 设计，强调记忆的“时效性”和“演变”。
    *   **增量能力**: 核心设计就是 Edge-based Incremental Update。节点包含时间戳，边的权重随时间动态变化。
    *   **解决痛点**: 解决了 GraphRAG 难以处理 "Fact Update" (比如导演由 A 变成了 B) 的问题。
    *   **适用性**: 适合不仅要增量添加，还要增量**修改/废弃**旧知识的动态场景。

### 4.5 DyG-RAG (Dynamic Graph RAG)
*   **核心理念**: **"Event-Centric Reasoning" (以事件为中心的推理)**。
*   **机制**:
    *   将图谱看作一系列 **Event Graph** 的流式叠加。
    *   **查询时**: 引入了 Time-sensitive Retrieval，优先游走最近的事件节点。
    *   **宏观能力**: 通过事件链 (Event Chain) 自动串联起宏观叙事，不需要预聚类。
    *   **适用性**: 适合新闻、金融等对“时间线”极其敏感的实时流数据场景。

---

## 5. 决策记录

**为什么我们不现在切换到 LightRAG？**

1.  **工程成本**: 我们的底层已经基于 GraphRAG 的 Community 概念构建。切换 LightRAG 需要重写 Indexer 和 Retriever。
2.  **当前够用**: 我们的 "Query-Time Enrichment" 主要是为了解决**实体缺失 (Missing Entity)** 问题（即 "Local Search" 问题）。
    *   例如：用户问《喜宴》，我们没有。
    *   这是典型的 Local Search 场景，**不需要** 社区摘要也能解决。
    *   只要我们将 Node/Edge 写入图数据库，Local Search 就能工作。

**最终方案**:
采用 **"Full Graph Sync (Async)"** 策略。
*   **写入**: 完整的 Node + Edge + Vector。
*   **收益**: 保证了图谱拓扑的完整性，Local Search 即刻可用。
*   **妥协**: 接受 Community Summary 的短期不一致（Staleness），留给夜间任务处理。

---

## 6. 整体总结 (Overall Summary)

在 2024-2025 年的 Graph RAG 技术演进中，针对 **"实时性 vs 全局理解 vs 增量更新"** 的不可能三角，业界诞生了五大流派：

| 流派 | 核心机制 | 增量能力 | 宏观能力 | 适用场景 | 代表作 |
|------|----------|----------|----------|----------|--------|
| **1. 社区聚类派** | Pre-computed Community Summary | ❌ (需 Batch 重跑) | ⭐⭐⭐ (最强) | 离线分析、高质量报告生成 | **Microsoft GraphRAG** |
| **2. 万物向量派** | Vectorize Entity & Relation | ✅ (O(1) 写入) | ⭐⭐ (高维检索) | 通用知识库、即时问答 | **LightRAG** |
| **3. 树状摘要派** | Recursive Tree Summarization | ✅ (O(logN) 修剪) | ⭐⭐ (层级检索) | 长文档分析 (法律/财报) | **RAPTOR** (Stanford) |
| **4. 图游走派** | PageRank / Graph Traversal | ✅ (Query Time) | ⭐ (隐式关联) | 高密度图谱、隐性关系挖掘 | **HippoRAG** (OSU) |
| **5. 双脑协同派** | Global Memory (LLM Weighs) | ✅ (Context Update) | ⭐⭐ (模糊线索) | 无图谱基建、轻量化部署 | **MemoRAG** (WebConf '25) |
| **6. 时序/事件派** | Time-decay / Event Chains | ✅ (Real-time Stream) | ⭐⭐ (时序叙事) | **Agent 记忆**、新闻流、金融流 | **Graphiti** / **DyG-RAG** |

### 我们的选择：Deep Fusion Strategy (深度融合)
鉴于 Movie Agent 的核心需求是 **"查到具体的缺失电影" (Local Fact)** 且兼顾 **"一定的宏观分析"**，我们采用了 **In-Memory Graph Overlay** 架构：
1.  **Sync Deep Fusion**: 不仅仅是文本拼接，而是将 TMDB 数据转化为 **临时图谱 (Transient Graph)**，在内存中与 GraphRAG 的检索子图进行拓扑融合。LLM 看到的是一张完整的、新旧节点互联的图。
2.  **Async Full Graph Write**: 模仿 LightRAG/Graphiti，后台实时构建拓扑结构，保证 "1秒后" 的 Local Search 可用。
3.  **Deferred Clustering**: 保留 Microsoft GraphRAG 的高质量摘要能力，接受 "1天" 的宏观数据延迟。

这也是目前在**成本、复杂度与效果**之间平衡得最好的 **Best Practice**。

---

## 7. 实现细节 (Implementation Details)

本章节详细说明 Deep Fusion Strategy 的工程实现要点。

### 7.1 错误处理与降级策略

**错误分类与处理**：

| 错误类型 | 影响 | 处理策略 |
|---------|------|----------|
| **TMDB API 限流** (429) | Sync Path 失败 | 使用缓存数据或降级到纯 GraphRAG |
| **TMDB API 超时** (>5s) | Sync Path 延迟 | 取消请求，使用 GraphRAG 结果 |
| **TMDB API 失败** (5xx) | Sync + Async 都失败 | 记录日志，降级到 GraphRAG |
| **Neo4j 写入失败** | Async Path 失败 | 重试 3 次，失败则记录到死信队列 |
| **锚点检测失败** | 无法融合 | 使用文本拼接方式注入上下文 |

**降级逻辑**：

```python
try:
    # 尝试 Deep Fusion
    transient_graph = await fetch_tmdb_graph(title)
    unified_context = overlay_and_merge(base_graph, transient_graph)
except TMDBRateLimitError:
    # 降级 1: 使用缓存
    cached_graph = await cache_store.get(title)
    if cached_graph:
        unified_context = cached_graph.to_context_text()
    else:
        # 降级 2: 纯 GraphRAG
        unified_context = base_context
except TMDBTimeoutError:
    # 超时则跳过 enrichment
    unified_context = base_context
except Exception as e:
    # 兜底: 记录错误，使用 GraphRAG
    logger.error(f"Unexpected enrichment error: {e}")
    unified_context = base_context
```

**重试机制**：

```python
@backoff.on_exception(
    backoff.expo,
    (Neo4jError, NetworkError),
    max_tries=3,
    jitter=backoff.full_jitter
)
async def persist_to_neo4j(transient_graph):
    """异步写入 Neo4j，带指数退避重试"""
    await graph_writer.merge_graph(transient_graph)
```

---

### 7.2 缓存策略详解

**Cache Key 设计**：

```python
def build_cache_key(title: str, year: Optional[int] = None) -> str:
    """处理同名电影问题"""
    key = f"tmdb:movie:{title}"
    if year:
        key += f":{year}"
    return key
```

**Cache TTL 策略**：

| 数据类型 | TTL | 理由 |
|---------|-----|------|
| **电影详情** | 7 天 | 元数据很少变化 |
| **演员信息** | 30 天 | 演员基本信息稳定 |
| **评分** | 1 天 | 评分变化频繁 |
| **搜索结果** | 1 小时 | 搜索结果可能变化 |

**并发请求去重**：

```python
class TMDBEnrichmentService:
    def __init__(self):
        self._in_flight: Dict[str, asyncio.Task] = {}

    async def fetch_movie_graph(self, title: str):
        cache_key = build_cache_key(title)

        # 检查是否有正在进行的请求
        if cache_key in self._in_flight:
            return await self._in_flight[cache_key]

        # 创建新请求
        task = asyncio.create_task(self._fetch_from_api(title))
        self._in_flight[cache_key] = task

        try:
            return await task
        finally:
            self._in_flight.pop(cache_key, None)
```

---

### 7.3 并发控制

**速率限制（TMDB 3 req/s）**：

```python
from asyncio import Semaphore

class TMDBEnrichmentService:
    def __init__(self, max_concurrent: int = 5):
        self._semaphore = Semaphore(max_concurrent)

    async def fetch_movie_graph(self, title: str):
        async with self._semaphore:
            return await self._fetch_from_api(title)
```

**令牌桶算法**：

```python
class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity

    async def acquire(self, tokens: int = 1):
        while self.tokens < tokens:
            await asyncio.sleep(0.1)
            self._refill()
        self.tokens -= tokens

rate_limiter = TokenBucket(rate=3.0, capacity=10)
```

---

### 7.4 锚点检测策略

**方案 1: 实体名称匹配**：

```python
def find_anchors_by_name(transient_graph, retrieved_subgraph):
    """通过实体名称匹配找锚点"""
    anchors = []
    for node in transient_graph.nodes.values():
        for retrieved_node in retrieved_subgraph.nodes:
            if node.display_name.lower() in retrieved_node.display_name.lower():
                anchors.append(retrieved_node)
                break
    return anchors
```

**方案 2: 向量相似度**：

```python
def find_anchors_by_similarity(
    transient_graph, retrieved_subgraph, threshold: float = 0.85
):
    """通过向量相似度找锚点"""
    anchors = []
    for node in transient_graph.nodes.values():
        node_embedding = embed(node.display_name)
        for retrieved_node in retrieved_subgraph.nodes:
            similarity = cosine_similarity(
                node_embedding,
                retrieved_node.embedding
            )
            if similarity >= threshold:
                anchors.append(retrieved_node)
    return anchors
```

**无锚点场景降级**：

```python
if not anchors:
    # 无法拓扑融合，降级为文本拼接
    enrichment_text = f"""
[来自 TMDB 的补充信息]
{transient_graph.to_context_text()}
"""
    return base_context + "\n" + enrichment_text
```

---

### 7.5 数据一致性保证

**Sync vs Async 一致性**：

```python
async def enrich_and_persist(title: str):
    # 1. Sync: 获取内存图（立即生效）
    transient_graph = await fetch_from_tmdb(title)

    # 2. Sync: 写入缓存（立即生效）
    await cache_store.set(title, transient_graph, ttl=7*24*3600)

    # 3. Async: 写入 Neo4j（最终一致）
    asyncio.create_task(persist_to_neo4j(transient_graph))

    # 即使 Neo4j 写入失败，缓存也保证了数据可用
```

---

### 7.6 性能监控

**关键指标**：

| 指标 | 类型 | 说明 |
|------|------|------|
| **enrichment_request_total** | Counter | Enrichment 请求总数 |
| **enrichment_cache_hit_rate** | Gauge | 缓存命中率 |
| **enrichment_latency_seconds** | Histogram | TMDB API 延迟 |
| **enrichment_anchor_found** | Counter | 找到锚点的次数 |
| **tmdb_api_call_total** | Counter | TMDB API 调用次数 |

**Prometheus Metrics**：

```python
from prometheus_client import Counter, Histogram, Gauge

enrichment_requests = Counter(
    'enrichment_requests_total',
    'Total enrichment requests',
    ['kb_prefix', 'status']
)

enrichment_latency = Histogram(
    'enrichment_latency_seconds',
    'Enrichment latency',
    ['source']  # tmdb, cache
)
```

---

### 7.7 成本控制

**TMDB API 成本预估**：

| 套餐 | 限制 | 价格 |
|------|------|------|
| **免费版** | 3 req/s, 1000 req/day | $0 |
| **Basic** | 10 req/s, 5000 req/day | $50/月 |
| **Pro** | 30 req/s, 20000 req/day | $200/月 |

**成本优化策略**：

1. **缓存优先**：命中率 > 80%，减少 API 调用
2. **按需启用**：只在 movie 领域启用 enrichment
3. **智能触发**：只在 GraphRAG miss 时触发

**预算告警**：

```python
class BudgetAlert:
    def __init__(self, daily_limit: int = 900):
        self.daily_limit = daily_limit
        self.daily_usage = 0

    async def check_budget(self):
        if self.daily_usage >= self.daily_limit:
            logger.warning("Daily budget exceeded")
            await alerting.send_alert("TMDB API budget exceeded")
            return False
        return True
```

---

### 7.8 实施检查清单

**配置检查**：
- [ ] TMDB_API_KEY 已配置
- [ ] ENABLE_ENRICHMENT=true
- [ ] ENRICHMENT_SCORE_THRESHOLD=0.4
- [ ] 缓存 TTL 已配置

**依赖检查**：
- [ ] PostgreSQL 已创建 `incremental_cache` 表
- [ ] Neo4j 已创建索引（tmdb_id）
- [ ] Milvus/Pgvector 已创建 collection
- [ ] Prometheus endpoint 已配置

**监控检查**：
- [ ] Grafana Dashboard 已创建
- [ ] 告警规则已配置（API 限流、失败率）
- [ ] 日志聚合已配置

---

## 8. 总结

本文档分析了 GraphRAG 增量更新的核心挑战，并对比了业界的多种解决方案。我们最终选择了 **Deep Fusion Strategy**，通过以下三点实现平衡：

1. **Sync Deep Fusion**: 即时生效的内存图融合
2. **Async Full Graph Write**: 保证拓扑完整性
3. **Deferred Clustering**: 接受宏观数据的短期延迟

这是一个在**实时性、全局理解、增量更新**三者之间找到平衡的最佳实践方案。
