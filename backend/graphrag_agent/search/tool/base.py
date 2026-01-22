from abc import ABC, abstractmethod
from typing import List, Dict, Any
import time

from langchain_core.tools import BaseTool

from graphrag_agent.ports.models import get_embeddings_model, get_llm_model
from graphrag_agent.ports.neo4jdb import get_graph, get_graph_query
from graphrag_agent.search.utils import VectorUtils
from graphrag_agent.config.settings import (
    BASE_SEARCH_CONFIG,
    ENTITY_VECTOR_INDEX_NAME,
    CHUNK_VECTOR_INDEX_NAME,
    GRAPH_CHUNK_ID_PREFIX_FILTER,
    GRAPH_COMMUNITY_ID_PREFIX,
    GRAPH_ENTITY_ID_PREFIX_FILTER,
)


class BaseSearchTool(ABC):
    """搜索工具基础类，为各种搜索实现提供通用功能"""
    
    def __init__(
        self,
        kb_prefix: str | None = None,
        entity_vector_index_name: str | None = None,
        chunk_vector_index_name: str | None = None,
        use_llm: bool = True,
    ):
        """
        初始化搜索工具
        
        参数:
            kb_prefix: 知识库前缀（用于同库多 KB 隔离）
        """
        kb_slug = (kb_prefix or "").strip()
        if kb_slug.endswith(":"):
            kb_slug = kb_slug[:-1]
        kb_slug = kb_slug.strip()
        self.kb_prefix = kb_slug

        # 初始化大语言模型和嵌入模型
        self.use_llm = use_llm
        self.llm = get_llm_model() if use_llm else None
        self.embeddings = get_embeddings_model()
        self.default_vector_limit = BASE_SEARCH_CONFIG["vector_limit"]
        self.default_text_limit = BASE_SEARCH_CONFIG["text_limit"]
        self.default_semantic_top_k = BASE_SEARCH_CONFIG["semantic_top_k"]
        self.default_relevance_top_k = BASE_SEARCH_CONFIG["relevance_top_k"]
        
        # 性能监控指标
        self.performance_metrics = {
            "query_time": 0,  # 数据库查询时间
            "llm_time": 0,    # 大语言模型处理时间
            "total_time": 0   # 总处理时间
        }
        
        # 初始化Neo4j连接
        self._setup_neo4j()

        # 前缀过滤（用于同库多知识库共存，避免串库）
        if self.kb_prefix:
            prefix = f"{self.kb_prefix}:"
            self.entity_id_prefix_filter = prefix
            self.chunk_id_prefix_filter = prefix
            self.community_id_prefix_filter = prefix
        else:
            self.entity_id_prefix_filter = GRAPH_ENTITY_ID_PREFIX_FILTER
            self.chunk_id_prefix_filter = GRAPH_CHUNK_ID_PREFIX_FILTER
            self.community_id_prefix_filter = GRAPH_COMMUNITY_ID_PREFIX

        # 向量索引命名（实体/Chunk 分开；同库多 KB 时按 kb_prefix 隔离）
        if self.kb_prefix:
            self.entity_vector_index_name = (
                entity_vector_index_name or f"{self.kb_prefix}_vector"
            )
            self.chunk_vector_index_name = (
                chunk_vector_index_name or f"{self.kb_prefix}_chunk_vector"
            )
        else:
            self.entity_vector_index_name = entity_vector_index_name or ENTITY_VECTOR_INDEX_NAME
            self.chunk_vector_index_name = chunk_vector_index_name or CHUNK_VECTOR_INDEX_NAME
    
    def _setup_neo4j(self):
        """设置Neo4j连接"""
        # 获取数据库连接管理器
        self.graph = get_graph()
        self.graph_query = get_graph_query()
    
    def db_query(self, cypher: str, params: Dict[str, Any] = {}):
        """
        执行Cypher查询
        
        参数:
            cypher: Cypher查询语句
            params: 查询参数
            
        返回:
            查询结果
        """
        # 使用查询端口执行查询
        return self.graph_query.execute_query(cypher, params)
        
    @abstractmethod
    def _setup_chains(self):
        """
        设置处理链，子类必须实现
        用于配置各种LLM处理链和提示模板
        """
        pass
    
    @abstractmethod
    def extract_keywords(self, query: str) -> Dict[str, List[str]]:
        """
        从查询中提取关键词
        
        参数:
            query: 查询字符串
            
        返回:
            Dict[str, List[str]]: 关键词字典，包含低级和高级关键词
        """
        pass
    
    @abstractmethod
    def search(self, query: Any) -> str:
        """
        执行搜索
        
        参数:
            query: 查询内容，可以是字符串或包含更多信息的字典
            
        返回:
            str: 搜索结果
        """
        pass

    def vector_search(self, query: str, limit: int = None) -> List[str]:
        """
        基于向量相似度的搜索方法
        
        参数:
            query: 搜索查询
            limit: 最大返回结果数
            
        返回:
            List[str]: 匹配实体ID列表
        """
        limit = limit or self.default_vector_limit
        # 生成查询的嵌入向量
        query_embedding = self.embeddings.embed_query(query)

        # 构建Neo4j向量搜索查询
        cypher = """
        CALL db.index.vector.queryNodes($index_name, $limit, $embedding)
        YIELD node, score
        WITH node, score
        WHERE $entity_prefix = '' OR node.id STARTS WITH $entity_prefix
        RETURN node.id AS id, score
        ORDER BY score DESC
        """

        kb_slug = (self.entity_id_prefix_filter or "").rstrip(":")
        candidate_indexes = [
            self.entity_vector_index_name,
            f"{kb_slug}_vector" if kb_slug else "",
            "vector",
        ]
        candidate_indexes = [idx for idx in candidate_indexes if idx]
        candidate_indexes = list(dict.fromkeys(candidate_indexes))

        last_error: Exception | None = None
        for index_name in candidate_indexes:
            try:
                results = self.db_query(
                    cypher,
                    {
                        "embedding": query_embedding,
                        "limit": limit,
                        "index_name": index_name,
                        "entity_prefix": self.entity_id_prefix_filter,
                    },
                )
                if not results.empty:
                    return results["id"].tolist()
                return []
            except Exception as e:
                last_error = e
                continue

        print(f"向量搜索失败: {last_error}")
        # 如果向量搜索失败，尝试使用文本搜索作为备用
        return self.text_search(query, limit)
    
    def text_search(self, query: str, limit: int = None) -> List[str]:
        """
        基于文本匹配的搜索方法（作为向量搜索的备选）
        
        参数:
            query: 搜索查询
            limit: 最大返回结果数
            
        返回:
            List[str]: 匹配实体ID列表
        """
        try:
            limit = limit or self.default_text_limit
            # 构建全文搜索查询
            cypher = """
            MATCH (e:__Entity__)
            WHERE ($entity_prefix = '' OR e.id STARTS WITH $entity_prefix)
              AND (e.id CONTAINS $query OR e.description CONTAINS $query)
            RETURN e.id AS id
            LIMIT $limit
            """
            
            results = self.db_query(cypher, {
                "query": query,
                "limit": limit,
                "entity_prefix": self.entity_id_prefix_filter,
            })
            
            if not results.empty:
                return results['id'].tolist()
            else:
                return []
                
        except Exception as e:
            print(f"文本搜索失败: {e}")
            return []
            
    def semantic_search(self, query: str, entities: List[Dict],
                        embedding_field: str = "embedding",
                        top_k: int = None) -> List[Dict]:
        """
        对一组实体进行语义相似度搜索
        
        参数:
            query: 搜索查询
            entities: 实体列表
            embedding_field: 嵌入向量的字段名
            top_k: 返回的最大结果数
            
        返回:
            按相似度排序的实体列表，每项增加"score"字段表示相似度
        """
        try:
            top_k = top_k or self.default_semantic_top_k
            # 生成查询的嵌入向量
            query_embedding = self.embeddings.embed_query(query)
            
            # 使用工具类进行排序
            return VectorUtils.rank_by_similarity(
                query_embedding, 
                entities, 
                embedding_field, 
                top_k
            )
        except Exception as e:
            print(f"语义搜索失败: {e}")
            return entities[:top_k] if top_k else entities
    
    def filter_by_relevance(self, query: str, docs: List, top_k: int = None) -> List:
        """
        根据相关性过滤文档
        
        参数:
            query: 查询字符串
            docs: 文档列表
            top_k: 返回的最大结果数
            
        返回:
            按相关性排序的文档列表
        """
        try:
            query_embedding = self.embeddings.embed_query(query)
            limit = top_k or self.default_relevance_top_k
            return VectorUtils.filter_documents_by_relevance(
                query_embedding,
                docs,
                top_k=limit
            )
        except Exception as e:
            print(f"文档过滤失败: {e}")
            limit = top_k or self.default_relevance_top_k
            return docs[:limit] if limit else docs
    
    def get_tool(self) -> BaseTool:
        """
        获取搜索工具实例
        
        返回:
            BaseTool: 搜索工具
        """
        # 创建动态工具类
        class DynamicSearchTool(BaseTool):
            name : str= f"{self.__class__.__name__.lower()}"
            description : str = "高级搜索工具，用于在知识库中查找信息"
            
            def _run(self_tool, query: Any) -> str:
                return self.search(query)
            
            def _arun(self_tool, query: Any) -> str:
                raise NotImplementedError("异步执行未实现")
        
        return DynamicSearchTool()
    
    def _log_performance(self, operation: str, start_time: float):
        """
        记录性能指标
        
        参数:
            operation: 操作名称
            start_time: 开始时间
        """
        duration = time.time() - start_time
        self.performance_metrics[operation] = duration
        print(f"性能指标 - {operation}: {duration:.4f}s")
    
    def close(self):
        """关闭资源连接"""
        # 关闭Neo4j连接
        if hasattr(self, 'graph'):
            # 如果图客户端有 close 方法，调用它
            if hasattr(self.graph, 'close'):
                self.graph.close()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，确保资源被正确释放"""
        self.close()
