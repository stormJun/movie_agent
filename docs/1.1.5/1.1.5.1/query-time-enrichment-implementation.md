# Query-Time Enrichment Implementation Specification

**版本**: 1.0
**日期**: 2026-01-25
**关联设计**: [Architecture Design](./query-time-enrichment.md)

---

## 1. 概述 (Overview)

本文档是将 [Query-Time Enrichment 架构设计](./query-time-enrichment.md) 转化为 **工程落地代码** 的详细实施规范。
我们的目标是实现一套 **"基于 TMDB 的实时知识增强"** 机制，确保系统在回答用户关于缺失电影（如《喜宴》）的问题时，能实时获取数据并融合到回答中。

---

## 2. 领域模型设计 (Domain Models)

我们需要一组轻量级的内存图模型，用于在 Python 层流转知识，而无需依赖 Neo4j 驱动对象。

**文件**: `backend/domain/knowledge/graph.py`

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass(frozen=True)
class Node:
    """通用的图节点模型"""
    id: str         # 业务主键 (e.g., "tmdb:movie:10199")
    label: str      # "Movie" | "Person"
    properties: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def display_name(self) -> str:
        return self.properties.get("title") or self.properties.get("name") or self.id

@dataclass(frozen=True)
class Edge:
    """通用的图边模型"""
    source_id: str
    target_id: str
    relation: str   # "DIRECTED" | "ACTED_IN"
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TransientGraph:
    """
    临时图谱容器
    用于承载从 TMDB API 转换过来的知识子图
    """
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    
    def add_node(self, node: Node):
        self.nodes[node.id] = node
        
    def add_edge(self, edge: Edge):
        self.edges.append(edge)
        
    def to_context_text(self) -> str:
        """
        将图谱转化为可注入 Prompt 的自然语言描述。
        策略: 优先按照 Entity Grouping (电影 -> 导演/演员)
        """
        lines = []
        movies = [n for n in self.nodes.values() if n.label == "Movie"]
        for m in movies:
            lines.append(f"Movie: {m.display_name} ({m.properties.get('year', '')})")
            if m.properties.get('overview'):
                lines.append(f"Overview: {m.properties['overview']}")
            
            # 找关系
            related_edges = [e for e in self.edges if e.target_id == m.id]
            directors = [
                self.nodes[e.source_id].display_name 
                for e in related_edges if e.relation == "DIRECTED"
            ]
            actors = [
                self.nodes[e.source_id].display_name 
                for e in related_edges if e.relation == "ACTED_IN"
            ]
            
            if directors:
                lines.append(f"Director: {', '.join(directors)}")
            if actors:
                lines.append(f"Cast: {', '.join(actors)}")
                
        return "\n".join(lines)
```

---

## 3. 服务接口定义 (Service Interfaces)

### 3.1 实体抽取器 (EntityExtractor)

负责从用户的问题中提取出我们要去 TMDB 搜什么。

**文件**: `backend/application/inference/entity_extractor.py`

```python
import re
from typing import List

class EntityExtractor:
    """
    基于规则的实体抽取器 (MVP Ver.)
    后续可升级为 NER Model
    """
    
    # 匹配 《...》 和 "..."
    PATTERNS = [
        r"《(.+?)》",
        r'"(.+?)"',
        r"'(.+?)'"
    ]

    async def extract_search_candidates(self, text: str) -> List[str]:
        """
        Input: "介绍一下《喜宴》这部电影"
        Output: ["喜宴"]
        """
        candidates = set()
        for pattern in self.PATTERNS:
            matches = re.findall(pattern, text)
            candidates.update(matches)
        return list(candidates)
```

### 3.2 增量缓存存储 (IncrementalCacheStore)

核心作用：避免重复调用 TMDB API，永久存储查询结果。

**文件**: `backend/infrastructure/persistence/postgres/incremental_cache_store.py`

```sql
-- DDL
CREATE TABLE tmdb_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT NOT NULL UNIQUE,   -- "movie:喜宴:1993"
    data JSONB NOT NULL,              -- API 原文
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

```python
class IncrementalCacheStore:
    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        
    async def get(self, key: str) -> Optional[dict]:
        """SELECT data FROM tmdb_cache WHERE cache_key = :key"""
        ...

    async def set(self, key: str, data: dict):
        """INSERT INTO tmdb_cache ... ON CONFLICT DO UPDATE"""
        ...
```

### 3.3 TMDB 增强服务 (TMDBEnrichmentService)

核心业务逻辑：查 API -> 转 Graph。

**文件**: `backend/infrastructure/tmdb/enrichment_service.py`

```python
class TMDBEnrichmentService:
    def __init__(self, api_key: str, cache_store: IncrementalCacheStore):
        self._api_key = api_key
        self._cache = cache_store

    async def fetch_movie_graph(self, title: str) -> Optional[TransientGraph]:
        """
        执行完整的增强流程:
        1. Search Movie API -> 获取 ID
        2. Movie Details API -> 获取 Metadata
        3. Movie Credits API -> 获取 Cast/Crew
        4. 组装为 TransientGraph 给上层使用
        """
        # 1. Search (Step 1)
        search_res = await self._call_tmdb(f"/search/movie", params={"query": title, "language": "zh-CN"})
        if not search_res['results']:
            return None

        movie_data = search_res['results'][0]
        tmdb_id = movie_data['id']

        # 2. Details & Credits (Step 2 - Combined Call)
        # 使用 append_to_response 减少一次 RTT
        data = await self._call_tmdb(
            f"/movie/{tmdb_id}",
            params={"language": "zh-CN", "append_to_response": "credits"}
        )

        details = data
        credits = data.get("credits", {})

        # 3. Transform to Graph
        graph = TransientGraph()

        # Movie Node
        m_node = Node(
            id=f"tmdb:movie:{tmdb_id}",
            label="Movie",
            properties={
                "title": details.get('title'),
                "year": details.get('release_date', '')[:4],
                "overview": details.get('overview')
            }
        )
        graph.add_node(m_node)

        # Person Nodes (Director)
        for p in credits.get('crew', []):
            if p['job'] == 'Director':
                p_node = Node(id=f"tmdb:person:{p['id']}", label="Person", properties={"name": p['name']})
                graph.add_node(p_node)
                graph.add_edge(Edge(p_node.id, m_node.id, "DIRECTED"))

        return graph

    def _transform_crew(self, crew_list: list) -> list[Node]:
        """
        清洗逻辑：
        1. 仅保留 Director 和 Top 3 Cast
        2. 统一 ID 格式 "tmdb:person:{id}"
        """
        ...

    async def _call_tmdb(self, endpoint: str) -> dict:
        # 具体实现见 3.4 节
        ...
```

### 3.4 TMDB API 调用详情 (API Specifics)

为了减少 HTTP RTT，我们使用 `append_to_response` 特性，仅需两次调用即可获取所有信息。

#### 1. 搜索电影 (Search)
*   **Endpoint**: `GET /search/movie`
*   **Params**:
    *   `query`: 电影名 (e.g. "喜宴")
    *   `language`: "zh-CN"
*   **Response**: `{"results": [{"id": 10199, "title": "The Wedding Banquet", ...}]}`

#### 2. 获取详情 + 演职员 (Details + Credits)
*   **Endpoint**: `GET /movie/{movie_id}`
*   **Params**:
    *   `append_to_response`: "credits"  <-- 关键优化
    *   `language`: "zh-CN"
*   **URL 示例**: `https://api.themoviedb.org/3/movie/10199?api_key=XXX&language=zh-CN&append_to_response=credits`
*   **Response**:
    ```json
    {
        "id": 10199,
        "title": "The Wedding Banquet",
        "overview": "...",
        "credits": {
            "crew": [{"job": "Director", "name": "Ang Lee", ...}],
            "cast": [{"name": "Winston Chao", ...}]
        }
    }
    ```

### 3.5 增量写入器 (IncrementalGraphWriter)

负责“善后工作”：把内存里的图持久化。

**文件**: `backend/infrastructure/integrations/incremental_graph_writer.py`

```python
class IncrementalGraphWriter:
    def __init__(self, neo4j_adapter, vector_adapter):
        self._neo4j = neo4j_adapter
        self._vector = vector_adapter
        
    async def persist(self, graph: TransientGraph):
        """
        异步执行持久化流程
        """
        # 1. Neo4j MERGE (保证图谱连通性)
        # Schema: (:Movie {tmdb_id, title, ...})
        # Schema: (:Person {tmdb_id, name})
        # Schema: (:Person)-[:DIRECTED]->(:Movie)
        cypher_query = """
        UNWIND $nodes as n
        CALL apoc.merge.node([n.label], {tmdb_id: n.id}, n.props) YIELD node
        RETURN count(*)
        """
        await self._neo4j.execute_query(cypher_query, {"nodes": ...})
        
        # 2. Vector Upsert (保证下次检索能由 Embedding 召回)
        # 仅对 Movie 节点生成 Embedding
        movies = [n for n in graph.nodes.values() if n.label == "Movie"]
        texts = [f"{m.properties['title']}: {m.properties.get('overview','')}" for m in movies]
        
        if texts:
            embeddings = await self._vector.embed_documents(texts)
            # Metadata 映射
            metadatas = [{"source": "tmdb", "title": m.properties['title']} for m in movies]
            await self._vector.upsert(
                collection_name="entities",
                embeddings=embeddings, 
                metadatas=metadatas
            )
```

---

## 4. 集成接入点 (Integration Point)

**目标文件**: `backend/infrastructure/streaming/chat_stream_executor.py`

我们将在 `stream` 方法中插入逻辑，具体位置在 **GraphRAG 检索完成** 与 **Context 构建** 之间。

```python
# class ChatStreamExecutor:

    async def stream(self, ..., kb_prefix: str, ...):
        # ... (Run Retrieval) ...
        # runs = await asyncio.gather(...)
        
        # [NEW] 增强逻辑注入点
        if self._enrichment_service and kb_prefix == "movie":
            # 1. 判断是否增强 (无结果 or 低分)
            if self._should_enrich(runs):
                
                # 2. 提取待查询词
                candidates = await self._extractor.extract_search_candidates(message)
                
                for title in candidates:
                    # 3. 前端 Loading 状态
                    yield {"status": "enriching", "message": f"正在查询 TMDB: {title}"}
                    
                    # 4. 获取内存图谱
                    transient_graph = await self._enrichment_service.fetch_movie_graph(title)
                    
                    if transient_graph:
                        # 5. 上下文注入 (In-Memory Overlay)
                        # 将图谱转为文本，拼接到 GraphRAG Context 中
                        enrichment_text = transient_graph.to_context_text()
                        self._inject_context(runs, enrichment_text)
                        
                        yield {"status": "enriched", "source": "tmdb"}
                        
                        # 6. 异步持久化 (Fire & Forget)
                        asyncio.create_task(self._writer.persist(transient_graph))
                        
        # ... (Build Combined Context) ...
```

---

## 5. 开发实施计划 (Development Checklist)

### Phase 1: 基础设施 (Infrastructure)
- [ ] **Data Model**: 创建 `backend/domain/knowledge/graph.py`。
- [ ] **Cache Store**: 创建 PostgreSQL `tmdb_cache` 表及对应的 SQLAlchemy Model。
- [ ] **API Client**: 配置 `httpx` client 和 TMDB Base URL，处理 Retry 逻辑。

### Phase 2: 核心服务 (Core Service)
- [ ] **Entity Extractor**: 实现简单的正则提取逻辑。
- [ ] **Enrichment Service**: 完成 `fetch_movie_graph` 及其内部的 ID 转换、数据清洗逻辑。
- [ ] **Unit Test**: 针对 `to_context_text()` 方法编写单测，确保生成的文本 LLM 可读。

### Phase 3: 持久化 (Persistence)
- [ ] **Neo4j Writer**: 编写幂等的 Cypher 语句 (`MERGE`)。
- [ ] **Vector Writer**: 复用现有的 Embedding Service 接口。

### Phase 4: 集成 (Integration)
- [ ] **Dependency Injection**: 在 `rag_factory/manager.py` 中组装上述组件。
- [ ] **Stream Logic**: 修改 `ChatStreamExecutor.stream`，植入增强流程。
- [ ] **End-to-End Test**: 在本地环境测试 "介绍一下《喜宴》"，观察 Console Log 和回答变化。
