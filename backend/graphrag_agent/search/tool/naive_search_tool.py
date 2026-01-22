from typing import List, Dict, Any
import time
import numpy as np

from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from graphrag_agent.config.prompts import NAIVE_PROMPT, NAIVE_SEARCH_QUERY_PROMPT
from graphrag_agent.config.settings import (
    NAIVE_SEARCH_TOP_K,
    response_type,
    naive_description,
)
from graphrag_agent.search.tool.base import BaseSearchTool
from graphrag_agent.search.utils import VectorUtils
from graphrag_agent.search.retrieval_adapter import (
    create_retrieval_metadata,
    create_retrieval_result,
    results_to_payload,
)


class NaiveSearchTool(BaseSearchTool):
    """简单的Naive RAG搜索工具，只使用embedding进行向量搜索"""
    
    def __init__(self, kb_prefix: str | None = None):
        """初始化Naive搜索工具"""
        # 调用父类构造函数
        super().__init__(kb_prefix=kb_prefix)
        
        # 搜索参数设置
        self.top_k = NAIVE_SEARCH_TOP_K  # 检索的最大文档数量
        
        # 设置处理链
        self._setup_chains()

        # 最近一次检索的结构化载荷（供 Agent/RAG 执行层做聚合与引用）
        self.last_retrieval_payload: Dict[str, Any] | None = None
        
    def _setup_chains(self):
        """设置处理链"""
        # 创建查询处理链
        self.query_prompt = ChatPromptTemplate.from_messages([
            ("system", NAIVE_PROMPT),
            ("human", NAIVE_SEARCH_QUERY_PROMPT),
        ])
        
        # 链接到LLM
        self.query_chain = self.query_prompt | self.llm | StrOutputParser()
    
    def extract_keywords(self, query: str) -> Dict[str, List[str]]:
        """
        从查询中提取关键词（naive rag不需要复杂的关键词提取）
        
        参数:
            query: 查询字符串
            
        返回:
            Dict[str, List[str]]: 空的关键词字典
        """
        return {"low_level": [], "high_level": []}
    
    def _cosine_similarity(self, vec1, vec2):
        """
        计算两个向量的余弦相似度
        
        参数:
            vec1: 第一个向量
            vec2: 第二个向量
            
        返回:
            float: 相似度值
        """
        # 确保向量是numpy数组
        if not isinstance(vec1, np.ndarray):
            vec1 = np.array(vec1)
        if not isinstance(vec2, np.ndarray):
            vec2 = np.array(vec2)
            
        # 计算余弦相似度
        dot_product = np.dot(vec1, vec2)
        norm_a = np.linalg.norm(vec1)
        norm_b = np.linalg.norm(vec2)
        
        # 避免被零除
        if norm_a == 0 or norm_b == 0:
            return 0
            
        return dot_product / (norm_a * norm_b)

    def _build_reference_from_chunk_ids(self, chunk_ids: List[str]) -> Dict[str, Any]:
        chunk_ids = [str(cid) for cid in (chunk_ids or []) if cid]
        chunk_ids = list(dict.fromkeys(chunk_ids))
        return {
            "chunks": [{"chunk_id": cid} for cid in chunk_ids],
            "entities": [],
            "relationships": [],
        }

    def retrieve_only(self, query_input: Any) -> Dict[str, Any]:
        """
        只做 Chunk 向量检索，不生成最终答案。

        Returns:
          {
            "query": str,
            "context": str,
            "retrieval_results": List[Dict],
            "reference": Dict,
          }
        """
        overall_start = time.time()

        if isinstance(query_input, dict) and "query" in query_input:
            query = query_input["query"]
        else:
            query = str(query_input)

        try:
            search_start = time.time()
            query_embedding = self.embeddings.embed_query(query)

            results: List[Dict[str, Any]] = []
            candidate_limit = max(self.top_k * 50, 200)

            try:
                def _derive_kb_slug(prefix: str) -> str:
                    raw = (prefix or "").strip()
                    if not raw:
                        return ""
                    raw = raw[:-1] if raw.endswith(":") else raw
                    if ":" in raw:
                        raw = raw.split(":")[0]
                    return raw.strip()

                kb_slug = _derive_kb_slug(self.chunk_id_prefix_filter)
                candidate_indexes = [
                    self.chunk_vector_index_name,
                    f"{kb_slug}_chunk_vector" if kb_slug else "",
                    "chunk_vector",
                ]
                candidate_indexes = [idx for idx in candidate_indexes if idx]
                candidate_indexes = list(dict.fromkeys(candidate_indexes))

                cypher = """
                CALL db.index.vector.queryNodes($index_name, $candidate_limit, $embedding)
                YIELD node, score
                WITH node, score
                WHERE node:__Chunk__
                  AND node.text IS NOT NULL
                  AND ($chunk_prefix = '' OR node.id STARTS WITH $chunk_prefix)
                RETURN node.id AS id, node.text AS text, score
                ORDER BY score DESC
                LIMIT $limit
                """

                last_index_error = None
                for index_name in candidate_indexes:
                    try:
                        df = self.db_query(
                            cypher,
                            {
                                "index_name": index_name,
                                "candidate_limit": candidate_limit,
                                "embedding": query_embedding,
                                "limit": self.top_k,
                                "chunk_prefix": self.chunk_id_prefix_filter or "",
                            },
                        )
                        if not df.empty:
                            results = df.to_dict("records")
                            break
                    except Exception as e:
                        last_index_error = e
                        continue

                if last_index_error and not results:
                    print(f"Chunk向量索引检索失败，回退到抽样检索: {last_index_error}")
            except Exception as e:
                print(f"Chunk向量索引检索失败，回退到抽样检索: {e}")

            if not results:
                chunks_with_embedding = self.graph.query(
                    """
                    MATCH (c:__Chunk__)
                    WHERE c.embedding IS NOT NULL
                      AND ($chunk_prefix = '' OR c.id STARTS WITH $chunk_prefix)
                    RETURN c.id AS id, c.text AS text, c.embedding AS embedding
                    LIMIT 100
                    """,
                    params={"chunk_prefix": self.chunk_id_prefix_filter or ""},
                )

                scored_chunks = VectorUtils.rank_by_similarity(
                    query_embedding,
                    chunks_with_embedding,
                    "embedding",
                    self.top_k,
                )
                results = scored_chunks[: self.top_k]

            search_time = time.time() - search_start
            self.performance_metrics["query_time"] = search_time

            chunks_content: List[str] = []
            chunk_ids: List[str] = []
            retrieval_results = []

            for item in results:
                chunk_id = str(item.get("id", "") or "").strip()
                text = item.get("text", "") or ""
                score = float(item.get("score", 0.6) or 0.6)

                if chunk_id and text:
                    chunks_content.append(f"Chunk ID: {chunk_id}\n{text}")
                    chunk_ids.append(chunk_id)

                    metadata = create_retrieval_metadata(
                        source_id=chunk_id,
                        source_type="chunk",
                        confidence=score,
                        extra={"raw_chunk": {"id": chunk_id}},
                    )
                    retrieval_results.append(
                        create_retrieval_result(
                            evidence=text,
                            source="naive_search",
                            granularity="Chunk",
                            metadata=metadata,
                            score=score,
                        )
                    )

            context = "\n\n---\n\n".join(chunks_content).strip()
            payload = {
                "query": query,
                "context": context,
                "retrieval_results": results_to_payload(retrieval_results),
                "reference": self._build_reference_from_chunk_ids(chunk_ids),
            }

            self.performance_metrics["total_time"] = time.time() - overall_start
            self.last_retrieval_payload = payload
            return payload
        except Exception as e:
            error_msg = f"检索过程中出现错误: {str(e)}"
            payload = {
                "query": query,
                "context": "",
                "retrieval_results": [],
                "reference": {"chunks": [], "entities": [], "relationships": []},
                "error": error_msg,
            }
            self.last_retrieval_payload = payload
            return payload

    def retrieve_only_as_text(self, query_input: Any) -> str:
        payload = self.retrieve_only(query_input)
        return str(payload.get("context") or "").strip() or "未找到相关信息。"
    
    def search(self, query_input: Any) -> str:
        """
        执行Naive RAG搜索 - 纯向量搜索
        
        参数:
            query_input: 用户查询或包含查询的字典
            
        返回:
            str: 基于检索结果生成的回答
        """
        overall_start = time.time()

        if isinstance(query_input, dict) and "query" in query_input:
            query = query_input["query"]
        else:
            query = str(query_input)

        payload = self.retrieve_only({"query": query})
        context = str(payload.get("context") or "").strip()
        chunk_ids = [
            c.get("chunk_id")
            for c in (payload.get("reference") or {}).get("chunks", [])
            if isinstance(c, dict)
        ]
        chunk_ids = [cid for cid in chunk_ids if cid]

        if not context:
            return f"没有找到与'{query}'相关的信息。\n\n{{'data': {{'Chunks':[] }} }}"

        llm_start = time.time()
        answer = self.query_chain.invoke(
            {"query": query, "context": context, "response_type": response_type}
        )
        self.performance_metrics["llm_time"] = time.time() - llm_start

        if "{'data': {'Chunks':" not in str(answer):
            chunk_references = ", ".join([f"'{cid}'" for cid in chunk_ids[:5]])
            answer = f"{answer}\n\n{{'data': {{'Chunks':[{chunk_references}] }} }}"

        self.performance_metrics["total_time"] = time.time() - overall_start
        return answer
    
    def get_tool(self) -> BaseTool:
        """
        获取搜索工具
        
        返回:
            BaseTool: 搜索工具实例
        """
        class NaiveRetrievalTool(BaseTool):
            name : str= "naive_retriever"
            description : str = naive_description
            
            def _run(self_tool, query: Any) -> str:
                # tool 调用只返回检索上下文（生成由上层统一处理）
                return self.retrieve_only_as_text(query)
            
            def _arun(self_tool, query: Any) -> str:
                raise NotImplementedError("异步执行未实现")
        
        return NaiveRetrievalTool()
    
    def close(self):
        """关闭资源"""
        super().close()
