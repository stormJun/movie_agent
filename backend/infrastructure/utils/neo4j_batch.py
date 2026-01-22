from typing import List, Dict
import os
from neo4j import Result

class BatchProcessor:
    """批量处理Neo4j查询的类"""

    @staticmethod
    def _resolve_chunk_id(source_id: str) -> str:
        """Resolve an incoming source_id to a __Chunk__.id when possible.

        - document ingestion uses SHA1-like ids (len==40)
        - structured graphs may use readable ids (e.g. "movie:movie:288:director")
        - legacy composite ids may look like "2,...,<chunk_id>"
        """
        if not source_id:
            return source_id
        parts = source_id.split(",")
        if len(parts) >= 2 and parts[0] == "2":
            return parts[-1]
        return source_id

    @staticmethod
    def _resolve_community_id(source_id: str) -> str:
        """Resolve an incoming source_id to a __Community__.id (legacy/global sources)."""
        if not source_id:
            return source_id
        parts = source_id.split(",")
        return parts[1] if len(parts) > 1 else source_id
    
    @staticmethod
    def get_source_info_batch(source_ids: List[str], driver) -> Dict[str, Dict]:
        """
        批量获取源信息
        
        Args:
            source_ids: 源ID列表
            driver: Neo4j驱动
            
        Returns:
            Dict: source_id到信息的映射
        """
        if not source_ids:
            return {}
            
        # 创建结果容器
        source_info = {}
        
        try:
            # Always try to resolve chunk ids first (covers both SHA1 ids and structured ids).
            resolved_chunk_ids = []
            for source_id in source_ids:
                if not source_id:
                    source_info[source_id] = {"file_name": "未知文件"}
                    continue
                resolved_chunk_ids.append(BatchProcessor._resolve_chunk_id(source_id))
            
            # 如果有Chunk IDs，批量查询
            if resolved_chunk_ids:
                chunk_query = """
                MATCH (n:__Chunk__) 
                WHERE n.id IN $ids 
                RETURN n.id AS id, n.fileName AS fileName
                """
                
                chunk_results = driver.execute_query(
                    chunk_query,
                    {"ids": list(set(resolved_chunk_ids))},
                    result_transformer_=Result.to_df
                )
                
                if not chunk_results.empty:
                    for _, row in chunk_results.iterrows():
                        chunk_id = row['id']
                        file_name = row['fileName']
                        base_name = os.path.basename(file_name) if file_name else "未知文件"
                        
                        # 找出原始请求中对应的IDs
                        for src_id in source_ids:
                            if BatchProcessor._resolve_chunk_id(src_id) == chunk_id:
                                source_info[src_id] = {"file_name": base_name}
            
            # For ids not matched as chunks, try community lookup.
            community_ids = []
            for source_id in source_ids:
                if not source_id or source_id in source_info:
                    continue
                community_ids.append(BatchProcessor._resolve_community_id(source_id))

            # 如果有Community IDs，批量查询
            if community_ids:
                community_query = """
                MATCH (n:__Community__) 
                WHERE n.id IN $ids 
                RETURN n.id AS id
                """
                
                community_results = driver.execute_query(
                    community_query,
                    {"ids": community_ids},
                    result_transformer_=Result.to_df
                )
                
                if not community_results.empty:
                    for _, row in community_results.iterrows():
                        community_id = row['id']
                        
                        # 找出原始请求中对应的IDs
                        for src_id in source_ids:
                            if BatchProcessor._resolve_community_id(src_id) == community_id:
                                source_info[src_id] = {"file_name": "社区摘要"}
            
            # 为未找到的ID添加默认信息
            for source_id in source_ids:
                if source_id not in source_info:
                    source_info[source_id] = {"file_name": f"源文本 {source_id}"}
            
            return source_info
            
        except Exception as e:
            print(f"批量获取源信息失败: {e}")
            # 返回默认值
            return {sid: {"file_name": f"源文本 {sid}"} for sid in source_ids}
    
    @staticmethod
    def get_content_batch(chunk_ids: List[str], driver) -> Dict[str, Dict]:
        """
        批量获取内容
        
        Args:
            chunk_ids: Chunk ID列表
            driver: Neo4j驱动
            
        Returns:
            Dict: chunk_id到内容的映射
        """
        if not chunk_ids:
            return {}
            
        # 创建结果容器
        chunk_content = {}
        
        try:
            resolved_chunk_ids = []
            for chunk_id in chunk_ids:
                if not chunk_id:
                    chunk_content[chunk_id] = {"content": "未提供有效的源ID"}
                    continue
                resolved_chunk_ids.append(BatchProcessor._resolve_chunk_id(chunk_id))
            
            # 如果有直接Chunk IDs，批量查询
            if resolved_chunk_ids:
                chunk_query = """
                MATCH (n:__Chunk__) 
                WHERE n.id IN $ids 
                RETURN n.id AS id, n.fileName AS fileName, n.text AS text
                """
                
                chunk_results = driver.execute_query(
                    chunk_query,
                    {"ids": list(set(resolved_chunk_ids))},
                    result_transformer_=Result.to_df
                )
                
                if not chunk_results.empty:
                    for _, row in chunk_results.iterrows():
                        chunk_id = row['id']
                        file_name = row.get('fileName', '未知文件')
                        text = row.get('text', '')
                        content = f"文件名: {file_name}\n\n{text}"
                        
                        # 找出原始请求中对应的IDs
                        for original_id in chunk_ids:
                            if BatchProcessor._resolve_chunk_id(original_id) == chunk_id:
                                chunk_content[original_id] = {"content": content}

            community_ids = []
            for chunk_id in chunk_ids:
                if not chunk_id or chunk_id in chunk_content:
                    continue
                community_ids.append(BatchProcessor._resolve_community_id(chunk_id))
            
            # 如果有Community IDs，批量查询
            if community_ids:
                community_query = """
                MATCH (n:__Community__) 
                WHERE n.id IN $ids 
                RETURN n.id AS id, n.summary AS summary, n.full_content AS full_content
                """
                
                community_results = driver.execute_query(
                    community_query,
                    {"ids": community_ids},
                    result_transformer_=Result.to_df
                )
                
                if not community_results.empty:
                    for _, row in community_results.iterrows():
                        comm_id = row['id']
                        summary = row.get('summary', '')
                        full_content = row.get('full_content', '')
                        content = f"摘要:\n{summary}\n\n全文:\n{full_content}"
                        
                        # 找出原始请求中对应的IDs
                        for original_id in chunk_ids:
                            if BatchProcessor._resolve_community_id(original_id) == comm_id:
                                chunk_content[original_id] = {"content": content}
            
            # 为未找到的ID添加默认信息
            for chunk_id in chunk_ids:
                if chunk_id not in chunk_content:
                    chunk_content[chunk_id] = {"content": f"未找到相关内容: 源ID {chunk_id}"}
            
            return chunk_content
            
        except Exception as e:
            print(f"批量获取内容失败: {e}")
            # 返回默认值
            return {cid: {"content": f"检索源内容时发生错误: {str(e)}", "chunk_id": cid} for cid in chunk_ids}
