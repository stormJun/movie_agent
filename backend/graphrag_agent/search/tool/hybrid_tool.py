import time
import json
from typing import List, Dict, Any, Tuple

from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from graphrag_agent.config.prompts import (
    LC_SYSTEM_PROMPT,
    HYBRID_TOOL_QUERY_PROMPT,
    LOCAL_SEARCH_KEYWORD_PROMPT,
)
from graphrag_agent.config.settings import gl_description, response_type, HYBRID_SEARCH_SETTINGS
from graphrag_agent.search.tool.base import BaseSearchTool
from graphrag_agent.agents.multi_agent.core.retrieval_result import RetrievalResult
from graphrag_agent.search.retrieval_adapter import (
    create_retrieval_metadata,
    create_retrieval_result,
    merge_retrieval_results,
    results_from_entities,
    results_from_relationships,
    results_to_payload,
)


class HybridSearchTool(BaseSearchTool):
    """
    混合搜索工具，实现类似LightRAG的双级检索策略
    结合了局部细节检索和全局主题检索
    """
    
    def __init__(self, kb_prefix: str | None = None, use_llm: bool = True):
        """初始化混合搜索工具"""
        # 检索参数
        self.entity_limit = HYBRID_SEARCH_SETTINGS["entity_limit"]
        self.max_hop_distance = HYBRID_SEARCH_SETTINGS["max_hop_distance"]
        self.top_communities = HYBRID_SEARCH_SETTINGS["top_communities"]
        self.batch_size = HYBRID_SEARCH_SETTINGS["batch_size"]
        self.community_level = HYBRID_SEARCH_SETTINGS["community_level"]
        
        # 调用父类构造函数
        super().__init__(
            kb_prefix=kb_prefix,
            use_llm=use_llm,
        )

        # 最近一次检索的结构化载荷（供 Agent/RAG 执行层做聚合与引用）
        self.last_retrieval_payload: Dict[str, Any] | None = None

        # 设置处理链
        if self.use_llm:
            self._setup_chains()
        else:
            self.query_chain = None
            self.keyword_chain = None
    
    def _setup_chains(self):
        """设置处理链"""
        # 创建主查询处理链 - 用于生成最终答案
        self.query_prompt = ChatPromptTemplate.from_messages([
            ("system", LC_SYSTEM_PROMPT),
            ("human", HYBRID_TOOL_QUERY_PROMPT),
        ])
        
        # 链接到LLM
        self.query_chain = self.query_prompt | self.llm | StrOutputParser()
        
        # 关键词提取链
        self.keyword_prompt = ChatPromptTemplate.from_messages([
            ("system", LOCAL_SEARCH_KEYWORD_PROMPT),
            ("human", "{query}"),
        ])
        
        self.keyword_chain = self.keyword_prompt | self.llm | StrOutputParser()
    
    def extract_keywords(self, query: str) -> Dict[str, List[str]]:
        """
        从查询中提取双级关键词
        
        参数:
            query: 查询字符串
            
        返回:
            Dict[str, List[str]]: 分类关键词字典
        """
        if not self.use_llm or self.keyword_chain is None:
            fallback = {
                "low_level": [query],
                "high_level": [query.split()[0] if query.split() else query],
            }
            return fallback
            
        try:
            llm_start = time.time()
            
            # 调用LLM提取关键词
            result = self.keyword_chain.invoke({"query": query})
            
            print(f"DEBUG - LLM关键词结果: {result[:100]}...") if len(str(result)) > 100 else print(f"DEBUG - LLM关键词结果: {result}")
            
            # 解析JSON结果
            try:
                # 尝试直接解析
                if isinstance(result, dict):
                    # 结果已经是字典，无需解析
                    keywords = result
                elif isinstance(result, str):
                    # 清理字符串，移除可能导致解析失败的字符
                    result = result.strip()
                    # 检查字符串是否以JSON格式开始
                    if result.startswith('{') and result.endswith('}'):
                        keywords = json.loads(result)
                    else:
                        # 尝试提取JSON部分 - 寻找第一个{和最后一个}
                        start_idx = result.find('{')
                        end_idx = result.rfind('}')
                        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                            json_str = result[start_idx:end_idx+1]
                            keywords = json.loads(json_str)
                        else:
                            # 没有有效的JSON结构，使用简单的关键词提取
                            raise ValueError("No valid JSON structure found")
                else:
                    # 不是字符串也不是字典
                    raise TypeError(f"Unexpected result type: {type(result)}")
                    
            except (json.JSONDecodeError, ValueError, TypeError) as json_err:
                print(f"JSON解析失败: {json_err}，尝试备用方法提取关键词")
                
                # 备用方法：手动提取关键词
                if isinstance(result, str):
                    # 简单分词提取关键词
                    import re
                    # 移除标点符号，按空格分词
                    words = re.findall(r'\b\w+\b', query.lower())
                    # 过滤停用词（简化版，实际需要更完整的停用词表）
                    stopwords = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
                                "in", "on", "at", "to", "for", "with", "by", "about", "of", "and", "or"}
                    keywords = {
                        "high_level": [word for word in words if len(word) > 5 and word not in stopwords][:3],
                        "low_level": [word for word in words if 3 <= len(word) <= 5 and word not in stopwords][:5]
                    }
                else:
                    # 如果不是字符串，返回基于原始查询的简单关键词
                    keywords = {
                        "high_level": [query],
                        "low_level": []
                    }
            
            # 记录LLM处理时间
            self.performance_metrics["llm_time"] += time.time() - llm_start
            
            # 确保包含必要的键
            if not isinstance(keywords, dict):
                keywords = {}
            if "low_level" not in keywords:
                keywords["low_level"] = []
            if "high_level" not in keywords:
                keywords["high_level"] = []
                
            # 确保列表类型
            if not isinstance(keywords["low_level"], list):
                keywords["low_level"] = [str(keywords["low_level"])]
            if not isinstance(keywords["high_level"], list):
                keywords["high_level"] = [str(keywords["high_level"])]
                
            return keywords
            
        except Exception as e:
            print(f"关键词提取失败: {e}")
            # 返回基于原始查询的默认值
            return {"low_level": [query], "high_level": [query.split()[0] if query.split() else query]}
    
    def _vector_search(self, query: str, limit: int = 5) -> List[str]:
        """
        使用基类的向量搜索方法
        
        参数:
            query: 查询字符串
            limit: 最大结果数
            
        返回:
            List[str]: 实体ID列表
        """
        return self.vector_search(query, limit)

    def _translate_title_to_english(self, title: str) -> List[str]:
        title = str(title or "").strip()
        if not title:
            return []
        if not self.use_llm or self.llm is None:
            return []

        prompt = (
            "将下面的中文电影/作品名翻译为最可能的英文标题（或原片名）。"
            "只返回 JSON 数组（字符串列表），最多 3 个，不要输出其他内容。\n"
            f"中文：{title}"
        )

        try:
            msg = self.llm.invoke(prompt)
            content = msg.content if hasattr(msg, "content") else str(msg)
        except Exception:
            return []

        candidates: List[str] = []
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, list):
                candidates = [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            left = content.find("[")
            right = content.rfind("]")
            if left != -1 and right != -1 and left < right:
                try:
                    parsed = json.loads(content[left : right + 1].strip())
                    if isinstance(parsed, list):
                        candidates = [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            if not candidates:
                candidates = [c.strip(" \t\r\n'\"") for c in content.splitlines() if c.strip()]

        candidates = [c for c in candidates if c and c.lower() != title.lower()]
        candidates = list(dict.fromkeys(candidates))[:3]
        return candidates

    def _expand_keywords_with_translations(self, keywords: List[str]) -> List[str]:
        import re

        expanded: List[str] = []
        for kw in keywords or []:
            kw = str(kw or "").strip()
            if not kw:
                continue

            expanded.append(kw)
            if re.search(r"[\u4e00-\u9fff]", kw) and not re.search(r"[A-Za-z]", kw):
                expanded.extend(self._translate_title_to_english(kw))

        return list(dict.fromkeys(expanded))

    def _filter_generic_low_level_keywords(self, keywords: List[str]) -> List[str]:
        stopwords = {
            "导演",
            "主演",
            "演员",
            "编剧",
            "出品",
            "出品方",
            "公司",
            "国家",
            "语言",
            "类型",
            "上映",
            "评分",
            "片长",
            "剧情",
            "简介",
        }
        cleaned = [kw for kw in keywords if kw not in stopwords]
        return cleaned or keywords

    def _fallback_text_search(self, query: str, limit: int = 5) -> List[str]:
        """
        基于文本匹配的备用搜索方法
        
        参数:
            query: 搜索查询
            limit: 最大返回结果数
            
        返回:
            List[str]: 匹配实体ID列表
        """
        try:
            # 构建全文搜索查询
            cypher = """
            MATCH (e:__Entity__)
            WHERE (e.id CONTAINS $query OR e.description CONTAINS $query)
              AND ($entity_prefix = '' OR e.id STARTS WITH $entity_prefix)
            RETURN e.id AS id
            LIMIT $limit
            """
            
            results = self.db_query(cypher, {
                "query": query,
                "limit": limit,
                "entity_prefix": self.entity_id_prefix_filter or "",
            })
            
            if not results.empty:
                return results['id'].tolist()
            else:
                return []
                
        except Exception as e:
            print(f"文本搜索也失败: {e}")
            return []
    
    def _retrieve_low_level_content(self, query: str, keywords: List[str]) -> Tuple[str, List[RetrievalResult]]:
        """
        检索低级内容（具体实体和关系）
        
        参数:
            query: 查询字符串
            keywords: 低级关键词列表
            
        返回:
            Tuple[str, List[RetrievalResult]]: 格式化内容及对应证据
        """
        query_start = time.time()
        retrieval_results: List[RetrievalResult] = []
        
        # 首先使用关键词查询获取相关实体
        entity_ids: List[str] = []

        def _normalize_keywords(raw_keywords: List[str]) -> List[str]:
            cleaned: List[str] = []
            for kw in raw_keywords or []:
                if kw is None:
                    continue
                kw_str = str(kw).strip()
                if not kw_str:
                    continue
                cleaned.append(kw_str)
            return list(dict.fromkeys(cleaned))

        # 如果用户问题是中文但包含英文实体名（如电影英文名），先做一次轻量关键词兜底，
        # 避免“中文 query 的 embedding”在英文语料上召回偏差。
        import re

        phrase_candidates: List[str] = []
        if query:
            # 提取英文短语（允许中间空格），优先保留原短语用于精确命中实体/Chunk
            candidates = re.findall(
                r"[A-Za-z][A-Za-z0-9'’:\-]*(?:\s+[A-Za-z0-9'’:\-]+)*", query
            )
            normalized: List[str] = []
            for c in candidates:
                c = re.sub(r"\s+", " ", c).strip()
                if len(c) < 3:
                    continue
                normalized.append(c)
            phrase_candidates = list(dict.fromkeys(normalized))[:3]

        keywords = self._filter_generic_low_level_keywords(_normalize_keywords(keywords))
        keywords = self._expand_keywords_with_translations(keywords)
        if not keywords and phrase_candidates:
            keywords = [phrase_candidates[0]]
        elif phrase_candidates:
            # 若 LLM 将英文短语拆成 tokens，补上原短语以提升匹配稳定性
            phrase = phrase_candidates[0]
            if phrase not in keywords:
                keywords = [phrase, *keywords]
        
        if keywords:
            keyword_query = """
            MATCH (e:__Entity__)
            WHERE ($entity_prefix = '' OR e.id STARTS WITH $entity_prefix)
            WITH e,
                 $keywords AS keywords,
                 reduce(
                     hits = 0,
                     kw IN $keywords |
                     hits + CASE
                         WHEN toLower(e.id) CONTAINS toLower(kw)
                           OR toLower(coalesce(e.name, '')) CONTAINS toLower(kw)
                           OR toLower(coalesce(e.description, '')) CONTAINS toLower(kw)
                         THEN 1 ELSE 0 END
                 ) AS hits,
                 reduce(
                     score = 0,
                     kw IN $keywords |
                     score + CASE
                         WHEN toLower(e.id) CONTAINS toLower(kw)
                           OR toLower(coalesce(e.name, '')) CONTAINS toLower(kw)
                           OR toLower(coalesce(e.description, '')) CONTAINS toLower(kw)
                         THEN size(kw) ELSE 0 END
                 ) AS score
            WHERE hits > 0
            RETURN e.id AS id, hits, score
            ORDER BY hits DESC, score DESC, id ASC
            LIMIT $limit
            """

            try:
                keyword_results = self.db_query(
                    keyword_query,
                    {
                        "keywords": keywords[:8],
                        "limit": self.entity_limit,
                        "entity_prefix": self.entity_id_prefix_filter or "",
                    },
                )
                if not keyword_results.empty:
                    entity_ids = keyword_results["id"].tolist()
            except Exception as e:
                print(f"关键词查询失败: {e}")
        
        # 如果关键词搜索没有结果或没有提供关键词，尝试使用向量搜索
        if not entity_ids:
            try:
                # 使用我们的自定义向量搜索方法
                vector_entity_ids = self._vector_search(query, limit=self.entity_limit)
                if vector_entity_ids:
                    entity_ids = vector_entity_ids
            except Exception as e:
                print(f"向量搜索失败: {e}")
        
        # 如果仍然没有实体，使用基本文本匹配
        if not entity_ids:
            try:
                entity_ids = self._fallback_text_search(query, limit=self.entity_limit)
            except Exception as e:
                print(f"文本搜索失败: {e}")
        
        # 如果仍然没有实体，返回空内容
        if not entity_ids:
            self.performance_metrics["query_time"] += time.time() - query_start
            return "没有找到相关的低级内容。", retrieval_results
        
        # 获取实体信息 - 不使用多跳关系以避免复杂查询
        entity_query = """
        // 从种子实体开始
        MATCH (e:__Entity__)
        WHERE e.id IN $entity_ids
          AND ($entity_prefix = '' OR e.id STARTS WITH $entity_prefix)
        
        RETURN collect({
            id: e.id, 
            type: coalesce(
                    e.type,
                    CASE
                        WHEN size([lbl IN labels(e) WHERE lbl <> '__Entity__' AND NOT lbl STARTS WITH 'KB_']) > 0
                        THEN [lbl IN labels(e) WHERE lbl <> '__Entity__' AND NOT lbl STARTS WITH 'KB_'][0]
                        ELSE 'Unknown'
                    END
                  ),
            description: e.description
        }) AS entities
        """
        
        # 获取关系信息 - 分别查询，避免复杂路径
        relation_query = """
        // 查找实体间的关系
        MATCH (e1:__Entity__)-[r]-(e2:__Entity__)
        WHERE e1.id IN $entity_ids 
          AND e2.id IN $entity_ids
          AND e1.id < e2.id  // 避免重复关系
          AND ($entity_prefix = '' OR e1.id STARTS WITH $entity_prefix)
          AND ($entity_prefix = '' OR e2.id STARTS WITH $entity_prefix)
        
        RETURN collect({
            start: e1.id, 
            type: type(r), 
            end: e2.id,
            description: CASE WHEN r.description IS NULL THEN '' ELSE r.description END
        }) AS relationships
        """
        
        # 获取文本块信息
        chunk_query_by_doc = """
        // 优先：若命中 Movie 实体，则取该电影 document 内的 chunks（按 position 排序）
        MATCH (c:__Chunk__)
        WHERE c.fileName IN $doc_file_names
          AND ($chunk_prefix = '' OR c.id STARTS WITH $chunk_prefix)
        WITH DISTINCT c
        ORDER BY c.position ASC, c.id ASC
        RETURN collect({id: c.id, text: c.text})[0..5] AS chunks
        """

        chunk_query_by_mentions = """
        // 回退：查找包含这些实体的文本块，按“命中实体数”排序
        MATCH (c:__Chunk__)-[:MENTIONS]->(e:__Entity__)
        WHERE e.id IN $entity_ids
          AND ($entity_prefix = '' OR e.id STARTS WITH $entity_prefix)
          AND ($chunk_prefix = '' OR c.id STARTS WITH $chunk_prefix)
        WITH c, count(DISTINCT e) AS hits
        ORDER BY hits DESC, c.position ASC, c.id ASC
        RETURN collect({id: c.id, text: c.text})[0..5] AS chunks
        """
        
        try:
            # 获取实体信息
            entity_results = self.db_query(
                entity_query,
                {"entity_ids": entity_ids, "entity_prefix": self.entity_id_prefix_filter or ""},
            )
            
            # 获取关系信息
            relation_results = self.db_query(
                relation_query,
                {"entity_ids": entity_ids, "entity_prefix": self.entity_id_prefix_filter or ""},
            )
            
            # 获取文本块信息：优先取“命中的电影 document chunks”
            # 只取最相关的“电影实体”对应的 document（避免英文 token 过泛导致多部电影串文档）
            doc_file_names: List[str] = []
            for entity_id in entity_ids:
                if ":Movie:" not in entity_id:
                    continue
                parts = entity_id.split(":")
                # 预期格式：<kb>:Movie:<movieId>
                if len(parts) < 3:
                    continue
                kb = parts[0].strip()
                movie_id = parts[-1].strip()
                if not kb or not movie_id:
                    continue
                doc_file_names = [f"{kb}:movie:{movie_id}"]
                break

            if doc_file_names:
                chunk_results = self.db_query(
                    chunk_query_by_doc,
                    {
                        "doc_file_names": doc_file_names,
                        "chunk_prefix": self.chunk_id_prefix_filter or "",
                    },
                )
            else:
                chunk_results = self.db_query(
                    chunk_query_by_mentions,
                    {
                        "entity_ids": entity_ids,
                        "entity_prefix": self.entity_id_prefix_filter or "",
                        "chunk_prefix": self.chunk_id_prefix_filter or "",
                    },
                )
            
            self.performance_metrics["query_time"] += time.time() - query_start
            
            # 构建结果
            low_level = []
            
            # 添加实体信息
            if not entity_results.empty and 'entities' in entity_results.columns:
                entities = entity_results.iloc[0]['entities']
                if entities:
                    low_level.append("### 相关实体")
                    entity_dicts: List[Dict[str, Any]] = []
                    for entity in entities:
                        entity_desc = f"- **{entity['id']}** ({entity['type']}): {entity['description']}"
                        low_level.append(entity_desc)
                        entity_dicts.append(
                            {
                                "id": entity["id"],
                                "description": entity["description"],
                                "confidence": 0.65,
                                "type": entity["type"],
                            }
                        )
                    retrieval_results.extend(
                        results_from_entities(
                            entity_dicts,
                            source="hybrid_search",
                            confidence=0.65,
                        )
                    )
            
            # 添加关系信息
            if not relation_results.empty and 'relationships' in relation_results.columns:
                relationships = relation_results.iloc[0]['relationships']
                if relationships:
                    low_level.append("\n### 实体关系")
                    relationship_dicts: List[Dict[str, Any]] = []
                    for rel in relationships:
                        rel_desc = f"- **{rel['start']}** -{rel['type']}-> **{rel['end']}**: {rel['description']}"
                        low_level.append(rel_desc)
                        relationship_dicts.append(
                            {
                                "start": rel["start"],
                                "end": rel["end"],
                                "type": rel["type"],
                                "description": rel.get("description", ""),
                                "confidence": 0.6,
                                "weight": 0.6,
                            }
                        )
                    retrieval_results.extend(
                        results_from_relationships(
                            relationship_dicts,
                            source="hybrid_search",
                            confidence=0.6,
                        )
                    )
            
            # 添加文本块信息
            if not chunk_results.empty and 'chunks' in chunk_results.columns:
                chunks = chunk_results.iloc[0]['chunks']
                if chunks:
                    low_level.append("\n### 相关文本")
                    for chunk in chunks:
                        chunk_text = f"- ID: {chunk['id']}\n  内容: {chunk['text']}"
                        low_level.append(chunk_text)
                        retrieval_results.append(
                            create_retrieval_result(
                                evidence=chunk.get("text", ""),
                                source="hybrid_search",
                                granularity="Chunk",
                                metadata=create_retrieval_metadata(
                                    source_id=str(chunk.get("id")),
                                    source_type="chunk",
                                    confidence=0.7,
                                    extra={"raw_chunk": chunk},
                                ),
                                score=0.7,
                            )
                        )
            
            if not low_level:
                return "没有找到相关的低级内容。", retrieval_results
                
            return "\n".join(low_level), retrieval_results
        except Exception as e:
            self.performance_metrics["query_time"] += time.time() - query_start
            print(f"实体查询失败: {e}")
            return "查询实体信息时出错。", retrieval_results
    
    def _retrieve_high_level_content(self, query: str, keywords: List[str]) -> Tuple[str, List[RetrievalResult]]:
        """
        检索高级内容（社区和主题概念）
        
        参数:
            query: 查询字符串
            keywords: 高级关键词列表
            
        返回:
            Tuple[str, List[RetrievalResult]]: 格式化内容及对应证据
        """
        query_start = time.time()
        retrieval_results: List[RetrievalResult] = []
        
        # 构建关键词条件
        keyword_conditions = []
        params = {"level": self.community_level, "limit": self.top_communities}
        
        if keywords:
            for i, keyword in enumerate(keywords):
                param_name = f"keyword{i}"
                params[param_name] = keyword
                keyword_conditions.append(f"c.summary CONTAINS ${param_name} OR c.full_content CONTAINS ${param_name}")
        
        # 构建查询
        community_query = """
        // 使用关键词过滤社区
        MATCH (c:__Community__ {level: $level})
        """
        
        if keyword_conditions:
            community_query += "WHERE " + " OR ".join(keyword_conditions)
        else:
            # 如果没有关键词，则使用查询文本
            params["query"] = query
            community_query += "WHERE c.summary CONTAINS $query OR c.full_content CONTAINS $query"
        
        # 添加排序和限制
        community_query += """
        WITH c
        ORDER BY CASE WHEN c.community_rank IS NULL THEN 0 ELSE c.community_rank END DESC
        LIMIT $limit
        RETURN c.id AS id, c.summary AS summary
        """
        
        try:
            community_results = self.db_query(community_query, params)
            
            self.performance_metrics["query_time"] += time.time() - query_start
            
            # 处理结果
            if community_results.empty:
                return "没有找到相关的高级内容。", retrieval_results
                
            # 构建格式化的高级内容
            high_level = ["### 相关主题概念"]
            
            for _, row in community_results.iterrows():
                community_desc = f"- **社区 {row['id']}**:\n  {row['summary']}"
                high_level.append(community_desc)
                retrieval_results.append(
                    create_retrieval_result(
                        evidence=row.get("summary", ""),
                        source="hybrid_search",
                        granularity="DO",
                        metadata=create_retrieval_metadata(
                            source_id=str(row.get("id")),
                            source_type="community",
                            confidence=0.6,
                            community_id=str(row.get("id")),
                            extra={"raw_community": row.to_dict()},
                        ),
                        score=0.6,
                    )
                )
            
            return "\n".join(high_level), retrieval_results
        except Exception as e:
            self.performance_metrics["query_time"] += time.time() - query_start
            print(f"社区查询失败: {e}")
            return "查询社区信息时出错。", retrieval_results

    def _build_reference_from_retrieval_payload(
        self, retrieval_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        将标准化 retrieval_results payload 转为 server 侧可消费的 reference 结构。

        目标：对齐 `backend/application/knowledge_graph/service.py:extract_kg_from_message(..., reference=...)`
        """
        ref: Dict[str, Any] = {"chunks": [], "entities": [], "relationships": []}

        chunk_ids: set[str] = set()
        entity_ids: set[str] = set()
        relationship_ids: set[str] = set()

        for item in retrieval_results or []:
            metadata = item.get("metadata") or {}
            source_type = str(metadata.get("source_type") or "").strip()
            source_id = str(metadata.get("source_id") or "").strip()
            if not source_type or not source_id:
                continue

            if source_type == "chunk":
                chunk_ids.add(source_id)
            elif source_type == "entity":
                entity_ids.add(source_id)
            elif source_type == "relationship":
                relationship_ids.add(source_id)

        ref["chunks"] = [{"chunk_id": cid} for cid in sorted(chunk_ids)]
        ref["entities"] = [{"id": eid} for eid in sorted(entity_ids)]
        ref["relationships"] = [{"id": rid} for rid in sorted(relationship_ids)]
        return ref

    def retrieve_only(self, query_input: Any) -> Dict[str, Any]:
        """
        只做检索，不生成最终答案。

        返回结构用于：
        - Agent 侧统一生成（避免 tool 内二次生成）
        - RAG 执行层聚合去重（retrieval_results/reference）
        """
        overall_start = time.time()

        # 解析输入（沿用 structured_search 的入参格式）
        if isinstance(query_input, dict) and "query" in query_input:
            query = query_input["query"]
            low_keywords = query_input.get("low_level_keywords", [])
            high_keywords = query_input.get("high_level_keywords", [])
        else:
            query = str(query_input)
            keywords = self.extract_keywords(query)
            low_keywords = keywords.get("low_level", [])
            high_keywords = keywords.get("high_level", [])

        try:
            low_level_content, low_evidence = self._retrieve_low_level_content(
                query, low_keywords
            )
            high_level_content, high_evidence = self._retrieve_high_level_content(
                query, high_keywords
            )

            all_evidence = merge_retrieval_results(low_evidence, high_evidence)
            retrieval_payload = results_to_payload(all_evidence)
            reference = self._build_reference_from_retrieval_payload(retrieval_payload)

            payload = {
                "query": query,
                "low_level_content": low_level_content,
                "high_level_content": high_level_content,
                "retrieval_results": retrieval_payload,
                "reference": reference,
            }

            self.performance_metrics["total_time"] = time.time() - overall_start
            self.last_retrieval_payload = payload
            return payload
        except Exception as e:
            error_msg = f"检索过程中出现错误: {str(e)}"
            payload = {
                "query": query,
                "low_level_content": "",
                "high_level_content": "",
                "retrieval_results": [],
                "reference": {"chunks": [], "entities": [], "relationships": []},
                "error": error_msg,
            }
            self.last_retrieval_payload = payload
            return payload

    def retrieve_only_as_text(self, query_input: Any) -> str:
        """兼容 ToolNode：返回可直接作为生成上下文的纯文本。"""
        payload = self.retrieve_only(query_input)
        low = str(payload.get("low_level_content") or "").strip()
        high = str(payload.get("high_level_content") or "").strip()
        context = "\n\n".join([p for p in (low, high) if p]).strip()
        return context or "未找到相关信息。"

    def retrieve_high_level_only(self, query_input: Any) -> Dict[str, Any]:
        """只跑社区/主题侧检索，用于 global_retriever。"""
        overall_start = time.time()

        if isinstance(query_input, dict) and "query" in query_input:
            query = query_input["query"]
            high_keywords = query_input.get("high_level_keywords", [])
        else:
            query = str(query_input)
            keywords = self.extract_keywords(query)
            high_keywords = keywords.get("high_level", [])

        try:
            high_level_content, high_evidence = self._retrieve_high_level_content(
                query, high_keywords
            )
            retrieval_payload = results_to_payload(high_evidence)
            reference = self._build_reference_from_retrieval_payload(retrieval_payload)

            payload = {
                "query": query,
                "low_level_content": "",
                "high_level_content": high_level_content,
                "retrieval_results": retrieval_payload,
                "reference": reference,
            }

            self.performance_metrics["total_time"] = time.time() - overall_start
            self.last_retrieval_payload = payload
            return payload
        except Exception as e:
            error_msg = f"检索过程中出现错误: {str(e)}"
            payload = {
                "query": query,
                "low_level_content": "",
                "high_level_content": "",
                "retrieval_results": [],
                "reference": {"chunks": [], "entities": [], "relationships": []},
                "error": error_msg,
            }
            self.last_retrieval_payload = payload
            return payload

    def retrieve_high_level_only_as_text(self, query_input: Any) -> str:
        payload = self.retrieve_high_level_only(query_input)
        high = str(payload.get("high_level_content") or "").strip()
        return high or "未找到相关信息。"

    def get_tool(self) -> BaseTool:
        """覆盖 BaseSearchTool.get_tool：Agent 调用时只返回检索上下文，不在 tool 内生成答案。"""

        outer = self

        class HybridRetrieveTool(BaseTool):
            name: str = f"{outer.__class__.__name__.lower()}"
            description: str = "混合检索工具（检索-only）：返回可作为生成上下文的证据文本。"

            def _run(self_tool, query: Any) -> str:
                return outer.retrieve_only_as_text(query)

            def _arun(self_tool, query: Any) -> str:
                raise NotImplementedError("异步执行未实现")

        return HybridRetrieveTool()
    
    def structured_search(self, query_input: Any) -> Dict[str, Any]:
        """
        执行混合搜索，返回包含证据与答案的结构化结果。
        """
        overall_start = time.time()
        
        # 解析输入
        if isinstance(query_input, dict) and "query" in query_input:
            query = query_input["query"]
            # 支持直接传入分类的关键词
            low_keywords = query_input.get("low_level_keywords", [])
            high_keywords = query_input.get("high_level_keywords", [])
        else:
            query = str(query_input)
            # 提取关键词
            keywords = self.extract_keywords(query)
            low_keywords = keywords.get("low_level", [])
            high_keywords = keywords.get("high_level", [])
        
        try:
            retrieval_payload = self.retrieve_only(
                {
                    "query": query,
                    "low_level_keywords": low_keywords,
                    "high_level_keywords": high_keywords,
                }
            )

            low_level_content = retrieval_payload.get("low_level_content", "")
            high_level_content = retrieval_payload.get("high_level_content", "")

            llm_start = time.time()
            answer = self.query_chain.invoke(
                {
                    "query": query,
                    "low_level": low_level_content,
                    "high_level": high_level_content,
                    "response_type": response_type,
                }
            )
            self.performance_metrics["llm_time"] += time.time() - llm_start

            structured_result = {
                "query": query,
                "low_level_content": low_level_content,
                "high_level_content": high_level_content,
                "final_answer": answer if answer else "未找到相关信息",
                "retrieval_results": retrieval_payload.get("retrieval_results", []),
            }
            
            self.performance_metrics["total_time"] = time.time() - overall_start

            return structured_result
            
        except Exception as e:
            error_msg = f"搜索过程中出现错误: {str(e)}"
            print(error_msg)
            return {
                "query": query,
                "low_level_content": "",
                "high_level_content": "",
                "final_answer": error_msg,
                "retrieval_results": [],
                "error": error_msg,
            }
    
    def search(self, query_input: Any) -> str:
        """
        执行混合搜索，结合低级和高级内容
        
        参数:
            query_input: 字符串查询或包含查询和关键词的字典
            
        返回:
            str: 生成的最终答案
        """
        structured = self.structured_search(query_input)
        return structured.get("final_answer", "未找到相关信息")
    
    def get_global_tool(self) -> BaseTool:
        """
        获取全局搜索工具
        
        返回:
            BaseTool: 全局搜索工具实例
        """
        class GlobalSearchTool(BaseTool):
            name : str = "global_retriever"
            description : str= gl_description
            
            def _run(self_tool, query: Any) -> str:
                # 仅检索社区/主题证据（不在 tool 内生成）
                if isinstance(query, dict) and "query" in query:
                    original_query = query["query"]
                    keywords = query.get("keywords", [])
                    query = {
                        "query": original_query,
                        "high_level_keywords": keywords,
                    }
                else:
                    keywords = self.extract_keywords(str(query))
                    query = {
                        "query": str(query),
                        "high_level_keywords": keywords.get("high_level", []),
                    }

                return self.retrieve_high_level_only_as_text(query)
            
            def _arun(self_tool, query: Any) -> str:
                raise NotImplementedError("异步执行未实现")
                
        return GlobalSearchTool()
    
    def close(self):
        """关闭资源"""
        super().close()
