from typing import Dict, Any
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from graphrag_agent.config.prompts import LC_SYSTEM_PROMPT, LOCAL_SEARCH_CONTEXT_PROMPT
from graphrag_agent.ports.neo4jdb import get_graph_query
from graphrag_agent.ports.vector_store import from_existing_index
from graphrag_agent.config.settings import (
    GRAPH_CHUNK_ID_PREFIX_FILTER,
    GRAPH_COMMUNITY_ID_PREFIX,
    GRAPH_ENTITY_ID_PREFIX_FILTER,
    LOCAL_SEARCH_SETTINGS,
)

class LocalSearch:
    """
    本地搜索类：使用Neo4j和LangChain实现基于向量检索的本地搜索功能
    
    该类通过向量相似度搜索在知识图谱中查找相关内容，并生成回答
    主要功能包括：
    1. 基于向量相似度的文本检索
    2. 社区内容和关系的检索
    3. 使用LLM生成最终答案
    """
    
    def __init__(
        self,
        llm,
        embeddings,
        response_type: str = "多个段落",
        kb_prefix: str | None = None,
        index_name: str | None = None,
    ):
        """
        初始化本地搜索类
        
        参数:
            llm: 大语言模型实例
            embeddings: 向量嵌入模型
            response_type: 响应类型，默认为"多个段落"
        """
        # 保存模型实例和配置
        self.llm = llm
        self.embeddings = embeddings
        self.response_type = response_type
        
        # 获取数据库连接管理器
        self.graph_query = get_graph_query()
        
        # 设置检索参数
        self.top_chunks = LOCAL_SEARCH_SETTINGS["top_chunks"]
        self.top_communities = LOCAL_SEARCH_SETTINGS["top_communities"]
        self.top_outside_rels = LOCAL_SEARCH_SETTINGS["top_outside_relationships"]
        self.top_inside_rels = LOCAL_SEARCH_SETTINGS["top_inside_relationships"]
        self.top_entities = LOCAL_SEARCH_SETTINGS["top_entities"]

        kb_slug = (kb_prefix or "").strip()
        if kb_slug.endswith(":"):
            kb_slug = kb_slug[:-1]
        kb_slug = kb_slug.strip()
        self.kb_prefix = kb_slug

        # 同库多知识库共存：按前缀隔离（优先使用 kb_prefix；否则沿用环境配置）
        if self.kb_prefix:
            prefix = f"{self.kb_prefix}:"
            self.entity_id_prefix_filter = prefix
            self.chunk_id_prefix_filter = prefix
            self.community_id_prefix_filter = prefix
            self.index_name = (index_name or f"{self.kb_prefix}_vector").strip()
        else:
            self.entity_id_prefix_filter = GRAPH_ENTITY_ID_PREFIX_FILTER
            self.chunk_id_prefix_filter = GRAPH_CHUNK_ID_PREFIX_FILTER
            self.community_id_prefix_filter = GRAPH_COMMUNITY_ID_PREFIX
            self.index_name = (index_name or LOCAL_SEARCH_SETTINGS["index_name"]).strip()

        self.index_name_candidates = self._build_index_name_candidates(self.index_name)
        
        # 初始化社区节点权重
        self._init_community_weights()
        
    def _build_index_name_candidates(self, configured: str) -> list[str]:
        def _derive_kb_slug(prefix: str) -> str:
            raw = (prefix or "").strip()
            if not raw:
                return ""
            raw = raw[:-1] if raw.endswith(":") else raw
            if ":" in raw:
                raw = raw.split(":")[0]
            return raw.strip()

        kb_slug = _derive_kb_slug(self.entity_id_prefix_filter)
        candidates = [
            (configured or "").strip(),
            f"{kb_slug}_vector" if kb_slug else "",
            "vector",
        ]
        candidates = [c for c in candidates if c]
        return list(dict.fromkeys(candidates))

    def _create_vector_store(self, retrieval_query: str):
        last_error: Exception | None = None
        for index_name in self.index_name_candidates:
            try:
                return from_existing_index(
                    self.embeddings,
                    index_name=index_name,
                    retrieval_query=retrieval_query,
                )
            except Exception as e:
                last_error = e
                continue
        raise last_error or RuntimeError("无法创建向量索引（未知错误）")
        
    def _init_community_weights(self):
        """初始化Neo4j中社区节点的权重"""
        self.db_query("""
        MATCH (n:`__Community__`)<-[:IN_COMMUNITY]-()<-[:MENTIONS]-(c)
        WHERE ($community_prefix = '' OR n.id STARTS WITH $community_prefix)
          AND ($chunk_prefix = '' OR c.id STARTS WITH $chunk_prefix)
        WITH n, count(distinct c) AS chunkCount
        SET n.weight = chunkCount
        """, params={"community_prefix": self.community_id_prefix_filter, "chunk_prefix": self.chunk_id_prefix_filter})
        
    def db_query(self, cypher: str, params: Dict[str, Any] = {}) -> pd.DataFrame:
        """
        执行Cypher查询并返回结果
        
        参数:
            cypher: Cypher查询语句
            params: 查询参数
            
        返回:
            pandas.DataFrame: 查询结果
        """
        return self.graph_query.execute_query(cypher, params)
        
    @property
    def retrieval_query(self) -> str:
        """
        获取Neo4j检索查询语句
        
        返回:
            str: Cypher查询语句，用于检索相关内容
        """
        entity_filter_n = (
            f" AND n.id STARTS WITH '{self.entity_id_prefix_filter}'"
            if self.entity_id_prefix_filter
            else ""
        )
        entity_filter_m = (
            f" AND m.id STARTS WITH '{self.entity_id_prefix_filter}'"
            if self.entity_id_prefix_filter
            else ""
        )
        chunk_filter = (
            f" AND c.id STARTS WITH '{self.chunk_id_prefix_filter}'"
            if self.chunk_id_prefix_filter
            else ""
        )
        community_filter = (
            f" AND c.id STARTS WITH '{self.community_id_prefix_filter}'"
            if self.community_id_prefix_filter
            else ""
        )
        return """
        WITH collect(node) as nodes
        UNWIND nodes as n
        WITH collect(distinct n) as nodes
        UNWIND nodes as n
        WITH n
        WHERE n.id IS NOT NULL
        """ + entity_filter_n + """
        WITH collect(distinct n) as nodes
        WITH
        collect {
            UNWIND nodes as n
            MATCH (n)<-[:MENTIONS]-(c:__Chunk__)
            WHERE c.id IS NOT NULL""" + chunk_filter + """
            WITH distinct c, count(distinct n) as freq
            RETURN {id:c.id, text: c.text} AS chunkText
            ORDER BY freq DESC
            LIMIT $topChunks
        } AS text_mapping,
        collect {
            UNWIND nodes as n
            MATCH (n)-[:IN_COMMUNITY]->(c:__Community__)
            WHERE c.id IS NOT NULL""" + community_filter + """
            WITH distinct c, c.community_rank as rank, c.weight AS weight
            RETURN c.summary 
            ORDER BY rank, weight DESC
            LIMIT $topCommunities
        } AS report_mapping,
        collect {
            UNWIND nodes as n
            MATCH (n)-[r]-(m:__Entity__) 
            WHERE NOT m IN nodes AND m.id IS NOT NULL""" + entity_filter_m + """
            RETURN r.description AS descriptionText
            ORDER BY r.weight DESC 
            LIMIT $topOutsideRels
        } as outsideRels,
        collect {
            UNWIND nodes as n
            MATCH (n)-[r]-(m:__Entity__) 
            WHERE m IN nodes AND m.id IS NOT NULL""" + entity_filter_m + """
            RETURN r.description AS descriptionText
            ORDER BY r.weight DESC 
            LIMIT $topInsideRels
        } as insideRels,
        collect {
            UNWIND nodes as n
            RETURN n.description AS descriptionText
        } as entities
        RETURN {
            Chunks: text_mapping, 
            Reports: report_mapping, 
            Relationships: outsideRels + insideRels, 
            Entities: entities
        } AS text, 1.0 AS score, {} AS metadata
        """
    
    def as_retriever(self, **kwargs):
        """
        返回检索器实例，用于链式调用
        
        返回:
            检索器实例
        """
        # 生成包含所有检索参数的查询
        final_query = self.retrieval_query.replace("$topChunks", str(self.top_chunks))\
            .replace("$topCommunities", str(self.top_communities))\
            .replace("$topOutsideRels", str(self.top_outside_rels))\
            .replace("$topInsideRels", str(self.top_inside_rels))

        # 初始化向量存储（兼容：优先使用 KB 对应索引；若配置索引不存在则自动回退）
        vector_store = self._create_vector_store(final_query)
        
        # 返回检索器
        return vector_store.as_retriever(
            search_kwargs={"k": self.top_entities}
        )
        
    def search(self, query: str) -> str:
        """
        执行本地搜索
        
        参数:
            query: 搜索查询字符串
            
        返回:
            str: 生成的最终答案
        """
        # 初始化对话提示模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", LC_SYSTEM_PROMPT),
            ("human", LOCAL_SEARCH_CONTEXT_PROMPT),
        ])
        
        # 创建搜索链
        chain = prompt | self.llm | StrOutputParser()
        
        # 初始化向量存储（兼容：优先使用 KB 对应索引；若配置索引不存在则自动回退）
        vector_store = self._create_vector_store(self.retrieval_query)
        
        # 执行相似度搜索
        docs = vector_store.similarity_search(
            query,
            k=self.top_entities,
            params={
                "topChunks": self.top_chunks,
                "topCommunities": self.top_communities,
                "topOutsideRels": self.top_outside_rels,
                "topInsideRels": self.top_inside_rels,
            }
        )
        
        # 使用LLM生成响应
        response = chain.invoke({
            "context": docs[0].page_content if docs else "",
            "input": query,
            "response_type": self.response_type
        })
        
        return response
        
    def close(self):
        """关闭Neo4j驱动连接"""
        pass
        
    def __enter__(self):
        """上下文管理器入口"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
