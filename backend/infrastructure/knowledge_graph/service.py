import re
import traceback
from typing import Dict, List, Any, Optional

from application.ports.knowledge_graph_port import KnowledgeGraphPort
from infrastructure.providers.neo4jdb import get_db_manager
from infrastructure.utils.keywords import extract_smart_keywords
from infrastructure.utils.neo4j_batch import BatchProcessor


# 获取数据库连接
db_manager = get_db_manager()
driver = db_manager.driver


def _format_label(value: Optional[str]) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    return f"`{raw.replace('`', '``')}`"


def _sanitize_properties(properties: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    clean = {}
    for key, value in (properties or {}).items():
        if key in {"embedding", "vector"}:
            continue
        clean[key] = value
    return clean


def extract_kg_from_message(message: str, query: str = None, reference: Dict = None) -> Dict:
    """
    从消息中提取知识图谱实体和关系数据
    
    Args:
        message: 消息文本
        query: 用户查询内容(可选)
        reference: 引用数据(可选)
    
    Returns:
        Dict: 知识图谱数据，包含节点和连接
    """
    try:
        # 如果提供了reference数据，优先使用
        if reference and isinstance(reference, dict):
            # 从reference中直接提取实体、关系和文本块ID
            chunks = reference.get("chunks", [])
            chunk_ids = reference.get("Chunks", [])
            
            # 尝试从chunks中获取更多信息
            for chunk in chunks:
                if "chunk_id" in chunk:
                    chunk_ids.append(chunk["chunk_id"])
                
            # 提取实体和关系ID
            entities = reference.get("entities", [])
            entity_ids = [e.get("id") for e in entities if isinstance(e, dict) and "id" in e]
            
            relationships = reference.get("relationships", [])
            rel_ids = [r.get("id") for r in relationships if isinstance(r, dict) and "id" in r]
            
            # 如果找到了chunk_ids，使用它们获取图谱
            if chunk_ids:
                return get_knowledge_graph_for_ids(entity_ids, rel_ids, chunk_ids)
        
        # 如果没有提供reference或提取失败，回退到消息文本解析
        # 如果消息包含思考过程，需要先移除
        if isinstance(message, str) and "<think>" in message and "</think>" in message:
            # 提取思考过程外的内容
            think_pattern = r'<think>.*?</think>'
            message = re.sub(think_pattern, '', message, flags=re.DOTALL).strip()
        
        # 直接使用正则表达式提取各部分数据
        entity_ids = []
        rel_ids = []
        chunk_ids = []
        
        # 匹配 Entities 列表
        entity_pattern = r"['\"]?Entities['\"]?\s*:\s*\[(.*?)\]"
        entity_match = re.search(entity_pattern, message, re.DOTALL)
        if entity_match:
            entity_str = entity_match.group(1).strip()
            try:
                # 处理数字ID
                entity_parts = [p.strip() for p in entity_str.split(',') if p.strip()]
                for part in entity_parts:
                    clean_part = part.strip("'\"")
                    if clean_part.isdigit():
                        entity_ids.append(int(clean_part))
                    else:
                        entity_ids.append(clean_part)
            except Exception as e:
                print(f"解析实体ID时出错: {e}")
        
        # 匹配 Relationships 或 Reports 列表
        rel_pattern = r"['\"]?(?:Relationships|Reports)['\"]?\s*:\s*\[(.*?)\]"
        rel_match = re.search(rel_pattern, message, re.DOTALL)
        if rel_match:
            rel_str = rel_match.group(1).strip()
            try:
                # 处理数字ID
                rel_parts = [p.strip() for p in rel_str.split(',') if p.strip()]
                for part in rel_parts:
                    clean_part = part.strip("'\"")
                    if clean_part.isdigit():
                        rel_ids.append(int(clean_part))
                    else:
                        rel_ids.append(clean_part)
            except Exception as e:
                print(f"解析关系ID时出错: {e}")
        
        # 匹配 Chunks 列表
        chunk_pattern = r"['\"]?Chunks['\"]?\s*:\s*\[(.*?)\]"
        chunk_match = re.search(chunk_pattern, message, re.DOTALL)
        if chunk_match:
            chunks_str = chunk_match.group(1).strip()
            
            # 处理带引号的chunk IDs
            if "'" in chunks_str or '"' in chunks_str:
                # 匹配所有被引号包围的内容
                chunk_parts = re.findall(r"['\"]([^'\"]*)['\"]", chunks_str)
                chunk_ids = [part for part in chunk_parts if part]
            else:
                # 没有引号的情况，直接分割
                chunk_ids = [part.strip() for part in chunks_str.split(',') if part.strip()]
        
        # 提取关键词 (可选)
        query_keywords = []
        if query:
            query_keywords = extract_smart_keywords(query)
        
        # 获取知识图谱
        return get_knowledge_graph_for_ids(entity_ids, rel_ids, chunk_ids)
        
    except Exception as e:
        print(f"提取知识图谱数据失败: {str(e)}")
        traceback.print_exc()
        return {"nodes": [], "links": []}
    
# 辅助函数，用于从有思考过程的内容中提取实际回答
def extract_answer_from_thinking(content: str) -> str:
    """
    从带有思考过程的内容中提取实际回答
    
    Args:
        content: 带思考过程的内容
        
    Returns:
        str: 提取出的实际回答
    """
    if not isinstance(content, str):
        return content
        
    # 如果包含思考过程，提取出实际回答部分
    if "<think>" in content and "</think>" in content:
        # 使用正则表达式提取思考过程
        think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
        if think_match:
            # 移除思考过程，保留实际回答
            return content.replace(f"<think>{think_match.group(1)}</think>", "").strip()
    
    # 如果没有思考过程或提取失败，返回原内容
    return content


def check_entity_existence(entity_ids: List[Any]) -> List:
    """
    检查实体ID是否存在于数据库中
    
    Args:
        entity_ids: 实体ID列表
    
    Returns:
        List: 确认存在的实体ID列表
    """
    try:
        # 尝试多种格式查询，确保能找到实体
        query = """
        // 尝试不同格式匹配实体ID
        UNWIND $ids AS id
        OPTIONAL MATCH (e:__Entity__) 
        WHERE e.id = id OR 
              e.id = toString(id) OR
              toString(e.id) = toString(id)
        RETURN id AS input_id, e.id AS found_id, labels(e) AS labels
        """
        
        params = {"ids": entity_ids}
        
        result = driver.execute_query(query, params)
        
        if result.records:
            found_entities = [r.get("found_id") for r in result.records if r.get("found_id") is not None]
            return found_entities
        else:
            print("没有找到任何匹配的实体")
            return []
            
    except Exception as e:
        print(f"检查实体ID时出错: {str(e)}")
        return []


def get_entities_from_chunk(chunk_id: str) -> List:
    """
    根据文本块ID查询相关联的实体
    
    Args:
        chunk_id: 文本块ID
    
    Returns:
        List: 与该文本块关联的实体ID列表
    """
    try:
        query = """
        MATCH (c:__Chunk__)-[:MENTIONS]->(e:__Entity__)
        WHERE c.id = $chunk_id
        RETURN collect(distinct e.id) AS entity_ids
        """
        
        params = {"chunk_id": chunk_id}
        
        result = driver.execute_query(query, params)
        
        if result.records and len(result.records) > 0:
            entity_ids = result.records[0].get("entity_ids", [])
            return entity_ids
        else:
            print(f"文本块 {chunk_id} 没有关联的实体")
            return []
            
    except Exception as e:
        print(f"查询文本块关联实体时出错: {str(e)}")
        return []


def get_graph_from_chunks(chunk_ids: List[str]) -> Dict:
    """
    直接从文本块获取知识图谱
    
    Args:
        chunk_ids: 文本块ID列表
    
    Returns:
        Dict: 知识图谱数据，包含节点和连接
    """
    try:
        print(f"从文本块获取知识图谱: {chunk_ids}")
        
        query = """
        // 通过文本块直接查询相关实体
        MATCH (c:__Chunk__)-[:MENTIONS]->(e:__Entity__)
        WHERE c.id IN $chunk_ids
        
        // 获取这些实体集合
        WITH collect(DISTINCT e) AS entities
        
        // 处理实体间的关系 - 只处理每对实体一次
        UNWIND entities AS e1
        UNWIND entities AS e2
        // 确保只处理每对实体一次
        WITH entities, e1, e2 
        WHERE e1.id < e2.id
        OPTIONAL MATCH (e1)-[r]-(e2)
        
        // 收集关系
        WITH entities, e1, e2, collect(r) AS rels
        
        // 构建去重的关系集合
        WITH entities, 
             collect({
                 source: e1.id, 
                 target: e2.id, 
                 rels: rels
             }) AS relations
        
        // 扁平化和去重关系
        WITH entities,
             [rel IN relations WHERE size(rel.rels) > 0 |
              // 为每种类型的关系创建唯一记录
              [r IN rel.rels | {
                source: rel.source,
                target: rel.target,
                relType: type(r),
                label: type(r),
                weight: 1
              }]
             ] AS links_nested
             
        // 扁平化嵌套关系
        WITH entities,
             REDUCE(acc = [], list IN links_nested | acc + list) AS all_links
        
        // 最终去重，基于源、目标和关系类型
        WITH entities,
             [link IN all_links | 
              link.source + '_' + link.target + '_' + link.relType
             ] AS link_keys,
             all_links
        
        // 只保留唯一的关系
        WITH entities,
             [i IN RANGE(0, size(all_links)-1) WHERE 
              i = REDUCE(min_i = i, j IN RANGE(0, size(all_links)-1) |
                   CASE WHEN link_keys[j] = link_keys[i] AND j < min_i
                        THEN j ELSE min_i END)
             | all_links[i]
             ] AS unique_links
             
        // 收集结果
        RETURN 
        [e IN entities | {
            id: e.id,
            label: e.id,
            description: CASE WHEN e.description IS NULL THEN '' ELSE e.description END,
            group: CASE 
                WHEN [lbl IN labels(e) WHERE lbl <> '__Entity__'] <> []
                THEN [lbl IN labels(e) WHERE lbl <> '__Entity__'][0]
                ELSE 'Unknown'
            END
        }] AS nodes,
        [link IN unique_links | {
            source: link.source,
            target: link.target,
            label: link.label,
            weight: link.weight
        }] AS links
        """
        
        result = driver.execute_query(query, {"chunk_ids": chunk_ids})
        
        if not result.records or len(result.records) == 0:
            print("从文本块查询结果为空")
            return {"nodes": [], "links": []}
            
        record = result.records[0]
        nodes = record.get("nodes", [])
        links = record.get("links", [])
        print(f"从文本块查询结果: {len(nodes)} 个节点, {len(links)} 个连接")
        
        return {
            "nodes": nodes,
            "links": links
        }
        
    except Exception as e:
        print(f"从文本块获取知识图谱失败: {str(e)}")
        return {"nodes": [], "links": []}


def get_knowledge_graph_for_ids(entity_ids=None, relationship_ids=None, chunk_ids=None) -> Dict:
    """
    根据ID获取知识图谱数据
    
    Args:
        entity_ids: 实体ID列表(可选)
        relationship_ids: 关系ID列表(可选)
        chunk_ids: 文本块ID列表(可选)
    
    Returns:
        Dict: 知识图谱数据，包含节点和连接
    """
    try:
        # 确保所有参数都有默认值，避免None
        entity_ids = entity_ids or []
        relationship_ids = relationship_ids or []
        chunk_ids = chunk_ids or []
        
        # 如果提供了文本块ID，但没有实体ID，尝试从文本块获取实体
        if chunk_ids and not entity_ids:
            for chunk_id in chunk_ids:
                chunk_entities = get_entities_from_chunk(chunk_id)
                entity_ids.extend(chunk_entities)
            
            # 去重
            entity_ids = list(set(entity_ids))
        
        if not entity_ids and not chunk_ids:
            return {"nodes": [], "links": []}
        
        # 检查实体ID是否存在
        verified_entity_ids = check_entity_existence(entity_ids)
        if not verified_entity_ids:
            # 尝试直接使用文本块查询
            if chunk_ids:
                return get_graph_from_chunks(chunk_ids)
            return {"nodes": [], "links": []}
        
        # 使用确认存在的实体ID进行查询
        params = {
            "entity_ids": verified_entity_ids,
            "max_distance": 1
        }
        
        # 局部查询的Cypher
        query = """
        // 匹配指定的实体ID
        MATCH (e:__Entity__)
        WHERE e.id IN $entity_ids
        
        // 收集基础实体
        WITH collect(e) AS base_entities
        
        // 匹配实体之间的关系，只处理每对实体一次
        UNWIND base_entities AS e1
        UNWIND base_entities AS e2
        // 确保只处理每对实体一次
        WITH base_entities, e1, e2 
        WHERE e1.id < e2.id
        OPTIONAL MATCH (e1)-[r]-(e2)
        
        // 收集关系
        WITH base_entities, e1, e2, collect(r) AS rels
        
        // 获取一跳邻居，排除已经处理过的实体对
        UNWIND base_entities AS base_entity
        OPTIONAL MATCH (base_entity)-[r1]-(neighbor:__Entity__)
        WHERE NOT neighbor IN base_entities
        
        // 收集所有实体和关系
        WITH base_entities, 
             collect(DISTINCT {source: e1.id, target: e2.id, rels: rels}) AS internal_rels,
             collect(DISTINCT neighbor) AS neighbors,
             collect(DISTINCT {source: base_entity.id, target: neighbor.id, rel: r1}) AS external_rels
        
        // 合并所有实体
        WITH base_entities + neighbors AS all_entities, 
             internal_rels, external_rels
        
        // 构建去重的内部关系
        WITH all_entities,
             [rel IN internal_rels WHERE size(rel.rels) > 0 |
              // 为每种类型的关系创建一个唯一记录
              [r IN rel.rels | {
                source: rel.source,
                target: rel.target,
                label: type(r),
                relType: type(r),
                weight: CASE WHEN r.weight IS NULL THEN 1 ELSE r.weight END
              }]
             ] AS internal_links_nested,
             
             // 构建去重的外部关系
             [rel IN external_rels WHERE rel.rel IS NOT NULL |
              {
                source: rel.source,
                target: rel.target,
                label: type(rel.rel),
                relType: type(rel.rel),
                weight: CASE WHEN rel.rel.weight IS NULL THEN 1 ELSE rel.rel.weight END
              }
             ] AS external_links
        
        // 扁平化内部关系并合并
        WITH all_entities,
             [link IN external_links | link] + 
             [link IN REDUCE(acc = [], list IN internal_links_nested | acc + list) | link]
             AS all_links_raw
        
        // 最终去重，基于源、目标和关系类型
        WITH all_entities,
             [link IN all_links_raw | 
              link.source + '_' + link.target + '_' + link.relType
             ] AS link_keys,
             all_links_raw
        
        // 只保留唯一的关系
        WITH all_entities,
             [i IN RANGE(0, size(all_links_raw)-1) WHERE 
              i = REDUCE(min_i = i, j IN RANGE(0, size(all_links_raw)-1) |
                   CASE WHEN link_keys[j] = link_keys[i] AND j < min_i
                        THEN j ELSE min_i END)
             | all_links_raw[i]
             ] AS unique_links
        
        // 返回结果
        RETURN 
        [n IN all_entities | {
            id: n.id, 
            label: CASE WHEN n.id IS NULL THEN "未知" ELSE n.id END, 
            description: CASE WHEN n.description IS NULL THEN '' ELSE n.description END,
            group: CASE 
                WHEN [lbl IN labels(n) WHERE lbl <> '__Entity__'] <> []
                THEN [lbl IN labels(n) WHERE lbl <> '__Entity__'][0]
                ELSE 'Unknown'
            END
        }] AS nodes,
        [link IN unique_links | {
            source: link.source,
            target: link.target,
            label: link.label,
            weight: link.weight
        }] AS links
        """
        
        # 执行查询
        result = driver.execute_query(query, params)
        
        if not result.records or len(result.records) == 0:
            # 尝试直接使用文本块查询
            if chunk_ids:
                return get_graph_from_chunks(chunk_ids)
            return {"nodes": [], "links": []}
            
        record = result.records[0]
        nodes = record.get("nodes", [])
        links = record.get("links", [])
        
        return {
            "nodes": nodes,
            "links": links
        }
        
    except Exception as e:
        print(f"获取知识图谱失败: {str(e)}")
        
        # 尝试直接使用文本块查询
        if chunk_ids:
            return get_graph_from_chunks(chunk_ids)
        return {"nodes": [], "links": []}


def get_knowledge_graph(limit: int = 100, query: str = None) -> Dict:
    """
    获取知识图谱数据
    
    Args:
        limit: 节点数量限制
        query: 查询条件(可选)
    
    Returns:
        Dict: 知识图谱数据，包含节点和连接
    """
    try:
        # 确保limit是整数
        limit = int(limit) if limit else 100
        
        # 构建查询条件
        query_conditions = ""
        params = {"limit": limit}
        
        if query:
            query_conditions = """
            WHERE n.id CONTAINS $query OR 
                  n.description CONTAINS $query
            """
            params["query"] = query
        else:
            query_conditions = ""
            
        # 构建节点查询 - 动态获取节点类型
        node_query = f"""
        // 获取实体
        MATCH (n:__Entity__)
        {query_conditions}
        WITH n LIMIT $limit
        
        // 收集所有实体
        WITH collect(n) AS entities
        
        // 获取实体间的关系
        CALL {{
            WITH entities
            MATCH (e1:__Entity__)-[r]-(e2:__Entity__)
            WHERE e1 IN entities AND e2 IN entities
                AND e1.id < e2.id  // 避免重复关系
            RETURN collect(r) AS relationships
        }}
        
        // 返回结果
        RETURN 
        [entity IN entities | {{
            id: entity.id,
            label: entity.id,
            description: entity.description,
            // 动态使用实体标签作为组
            group: CASE 
                WHEN [lbl IN labels(entity) WHERE lbl <> '__Entity__'] <> []
                THEN [lbl IN labels(entity) WHERE lbl <> '__Entity__'][0]
                ELSE 'Unknown'
            END
        }}] AS nodes,
        [r IN relationships | {{
            source: startNode(r).id,
            target: endNode(r).id,
            label: type(r),
            weight: CASE WHEN r.weight IS NOT NULL THEN r.weight ELSE 1 END
        }}] AS links
        """
        
        result = driver.execute_query(node_query, params)
        
        if not result or not result.records:
            return {"nodes": [], "links": []}
            
        record = result.records[0]
        
        # 处理可能的None值
        nodes = record["nodes"] or []
        links = record["links"] or []
        
        # 返回标准格式
        return {
            "nodes": nodes,
            "links": links
        }
        
    except Exception as e:
        print(f"获取知识图谱数据失败: {str(e)}")
        return {"error": str(e), "nodes": [], "links": []}

def get_source_content(source_id: str) -> str:
    """
    根据源ID获取内容
    
    Args:
        source_id: 源ID
        
    Returns:
        str: 源内容
    """
    try:
        if not source_id:
            return "未提供有效的源ID"

        # Prefer chunk lookup first:
        # - document ingestion uses SHA1 chunk ids (len==40)
        # - structured graphs may use readable ids (e.g. "movie:movie:288:director")
        # - legacy composite ids may look like "2,...,<chunk_id>"
        id_parts = source_id.split(",")
        chunk_id = id_parts[-1] if (len(id_parts) >= 2 and id_parts[0] == "2") else source_id

        chunk_query = """
        MATCH (n:__Chunk__)
        WHERE n.id = $id
        RETURN n.fileName AS fileName, n.text AS text
        """

        from neo4j import Result
        chunk_result = driver.execute_query(
            chunk_query,
            {"id": chunk_id},
            result_transformer_=Result.to_df,
        )

        if chunk_result is not None and chunk_result.shape[0] > 0:
            return f"文件名: {chunk_result.iloc[0]['fileName']}\n\n{chunk_result.iloc[0]['text']}"

        # Fallback: community lookup (legacy/global search sources).
        community_id = id_parts[1] if len(id_parts) > 1 else source_id
        query = """
        MATCH (n:__Community__)
        WHERE n.id = $id
        RETURN n.summary AS summary, n.full_content AS full_content
        """
        params = {"id": community_id}
        
        result = driver.execute_query(
            query,
            params,
            result_transformer_=Result.to_df
        )
        
        if result is not None and result.shape[0] > 0:
            if "text" in result.columns:
                content = f"文件名: {result.iloc[0]['fileName']}\n\n{result.iloc[0]['text']}"
            else:
                content = f"摘要:\n{result.iloc[0]['summary']}\n\n全文:\n{result.iloc[0]['full_content']}"
        else:
            content = f"未找到相关内容: 源ID {source_id}"
            
        return content
    except Exception as e:
        print(f"获取源内容时出错: {str(e)}")
        return f"检索源内容时发生错误: {str(e)}"
    

def get_source_file_info(source_id: str) -> dict:
    """
    获取源ID对应的文件信息
    
    Args:
        source_id: 源ID
        
    Returns:
        Dict: 包含文件名等信息的字典
    """
    try:
        if not source_id:
            return {"file_name": "未知文件"}

        # Prefer chunk lookup first (see get_source_content()).
        id_parts = source_id.split(",")
        chunk_id = id_parts[-1] if (len(id_parts) >= 2 and id_parts[0] == "2") else source_id

        chunk_query = """
        MATCH (n:__Chunk__)
        WHERE n.id = $id
        RETURN n.fileName AS fileName
        """

        from neo4j import Result
        chunk_result = driver.execute_query(
            chunk_query,
            {"id": chunk_id},
            result_transformer_=Result.to_df,
        )

        if chunk_result is not None and chunk_result.shape[0] > 0:
            file_name = chunk_result.iloc[0]["fileName"]
            return {"file_name": os.path.basename(file_name) if file_name else "未知文件"}

        # Fallback: community label.
        query = """
        MATCH (n:__Community__)
        WHERE n.id = $id
        RETURN "社区摘要" AS fileName
        """
        params = {"id": id_parts[1] if len(id_parts) > 1 else source_id}
        
        result = driver.execute_query(
            query,
            params,
            result_transformer_=Result.to_df
        )
        
        if result is not None and result.shape[0] > 0 and "fileName" in result.columns:
            file_name = result.iloc[0]['fileName']
            # 获取文件名的基本名称（不含路径）
            import os
            base_name = os.path.basename(file_name) if file_name else "未知文件"
            return {"file_name": base_name}
        else:
            return {"file_name": f"源文本 {source_id}"}
            
    except Exception as e:
        print(f"获取源文件信息时出错: {str(e)}")
        return {"file_name": f"源文本 {source_id}"}


def get_chunks(limit: int = 10, offset: int = 0, kb_prefix: str | None = None):
    """
    获取数据库中的文本块
    
    Args:
        limit: 返回数量限制
        offset: 偏移量
        
    Returns:
        Dict: 文本块数据和总数
    """
    try:
        kb_prefix = (kb_prefix or "").strip().strip(":")
        id_prefix = f"{kb_prefix}:" if kb_prefix else None

        query = """
        MATCH (c:__Chunk__)
        {where_clause}
        RETURN c.id AS id, c.fileName AS fileName, c.text AS text
        ORDER BY c.fileName, c.id
        SKIP $offset
        LIMIT $limit
        """

        where_clause = ""
        params = {"limit": int(limit), "offset": int(offset)}
        if id_prefix:
            where_clause = "WHERE c.id STARTS WITH $id_prefix"
            params["id_prefix"] = id_prefix
        query = query.format(where_clause=where_clause)
        
        from neo4j import Result
        result = driver.execute_query(
            query, 
            # neo4j.Driver.execute_query uses `parameters_` (with trailing underscore).
            # Using `parameters` silently drops params (captured by **kwargs) and causes
            # Neo4j to report missing $limit/$offset.
            parameters_=params,
            result_transformer_=Result.to_df
        )
        
        if result is not None and not result.empty:
            chunks = result.to_dict(orient='records')
            return {"chunks": chunks, "total": len(chunks)}
        else:
            return {"chunks": [], "total": 0}
            
    except Exception as e:
        print(f"获取文本块失败: {str(e)}")
        return {"error": str(e), "chunks": []}
    

def get_shortest_path(driver, entity_a, entity_b, max_hops=3):
    """查询实体A和实体B之间的最短路径"""
    try:
        # 根据max_hops构建相应的路径模式
        if max_hops == 1:
            path_pattern = "[*..1]"
        elif max_hops == 2:
            path_pattern = "[*..2]"
        elif max_hops == 3:
            path_pattern = "[*..3]"
        elif max_hops == 4:
            path_pattern = "[*..4]"
        elif max_hops >= 5:
            path_pattern = "[*..5]"
        else:
            path_pattern = "[*..3]"
        
        query = f"""
        MATCH (a:__Entity__), (b:__Entity__)
        WHERE a.id = $entity_a AND b.id = $entity_b
        MATCH p = shortestPath((a)-{path_pattern}-(b))
        RETURN p
        """
        
        result = driver.execute_query(query, {
            "entity_a": entity_a,
            "entity_b": entity_b
        })
        
        # 转换结果为可视化格式
        nodes = []
        links = []
        node_ids = set()
        path_info = f"从 {entity_a} 到 {entity_b} 的最短路径"
        path_length = 0
        
        if result.records and len(result.records) > 0:
            path = result.records[0].get("p")
            if path:
                # 处理节点
                for node in path.nodes:
                    node_id = node.get("id")
                    if node_id not in node_ids:
                        node_ids.add(node_id)
                        group = [label for label in node.labels if label != "__Entity__"]
                        group = group[0] if group else "Unknown"
                        
                        nodes.append({
                            "id": node_id,
                            "label": node_id,
                            "description": node.get("description", ""),
                            "group": group
                        })
                
                # 处理关系
                for rel in path.relationships:
                    links.append({
                        "source": rel.start_node.get("id"),
                        "target": rel.end_node.get("id"),
                        "label": rel.type,
                        "weight": 1
                    })
                    path_length += 1
        
        return {
            "nodes": nodes,
            "links": links,
            "path_info": path_info,
            "path_length": path_length
        }
        
    except Exception as e:
        print(f"获取最短路径失败: {str(e)}")
        return {"nodes": [], "links": [], "error": str(e)}

def get_one_two_hop_paths(driver, entity_a, entity_b):
    """
    获取实体A到实体B的一到两步关系路径
    """
    try:
        query = """
        MATCH p = (a:__Entity__)-[*1..2]-(b:__Entity__)
        WHERE a.id = $entity_a AND b.id = $entity_b
        RETURN p
        """
        
        result = driver.execute_query(query, {
            "entity_a": entity_a,
            "entity_b": entity_b
        })
        
        # 转换结果为可视化格式
        nodes = []
        links = []
        paths_info = []
        node_map = {}
        link_map = {}
        
        for record in result.records:
            path = record.get("p")
            if path:
                path_desc = []
                
                # 处理节点
                for node in path.nodes:
                    node_id = node.get("id")
                    if node_id not in node_map:
                        group = [label for label in node.labels if label != "__Entity__"]
                        group = group[0] if group else "Unknown"
                        
                        node_data = {
                            "id": node_id,
                            "label": node_id,
                            "description": node.get("description", ""),
                            "group": group
                        }
                        nodes.append(node_data)
                        node_map[node_id] = node_data
                
                # 处理关系并构建路径描述
                prev_node = None
                for i, node in enumerate(path.nodes):
                    current_id = node.get("id")
                    if prev_node:
                        # 找到这两个节点之间的关系
                        for rel in path.relationships:
                            start_id = rel.start_node.get("id")
                            end_id = rel.end_node.get("id")
                            if (start_id == prev_node and end_id == current_id) or \
                               (start_id == current_id and end_id == prev_node):
                                
                                link_key = f"{start_id}_{end_id}_{rel.type}"
                                if link_key not in link_map:
                                    link_data = {
                                        "source": start_id,
                                        "target": end_id,
                                        "label": rel.type,
                                        "weight": 1
                                    }
                                    links.append(link_data)
                                    link_map[link_key] = link_data
                                
                                # 添加到路径描述
                                path_desc.append(f"{prev_node} -[{rel.type}]-> {current_id}")
                    
                    prev_node = current_id
                
                # 添加完整路径描述
                if path_desc:
                    path_str = " ".join(path_desc)
                    if path_str not in paths_info:
                        paths_info.append(path_str)
        
        return {
            "nodes": nodes,
            "links": links,
            "paths_info": paths_info,
            "path_count": len(paths_info)
        }
        
    except Exception as e:
        print(f"获取一到两跳路径失败: {str(e)}")
        return {"nodes": [], "links": [], "error": str(e)}

def get_common_neighbors(driver, entity_a, entity_b):
    """
    找出与实体A和实体B相关联的实体（共同邻居）
    """
    try:
        query = """
        MATCH (a:__Entity__ {id: $entity_a})--(x)--(b:__Entity__ {id: $entity_b})
        RETURN DISTINCT x
        """
        
        result = driver.execute_query(query, {
            "entity_a": entity_a,
            "entity_b": entity_b
        })
        
        # 转换结果为可视化格式
        nodes = []
        links = []
        common_neighbors = []
        node_ids = {entity_a, entity_b}
        
        # 首先添加A和B节点
        a_node = {"id": entity_a, "label": entity_a, "group": "Source", "description": ""}
        b_node = {"id": entity_b, "label": entity_b, "group": "Target", "description": ""}
        nodes.append(a_node)
        nodes.append(b_node)
        
        # 处理共同邻居
        for record in result.records:
            neighbor = record.get("x")
            if neighbor:
                neighbor_id = neighbor.get("id")
                common_neighbors.append(neighbor_id)
                
                if neighbor_id not in node_ids:
                    node_ids.add(neighbor_id)
                    group = [label for label in neighbor.labels if label != "__Entity__"]
                    group = group[0] if group else "Common"
                    
                    # 添加邻居节点
                    nodes.append({
                        "id": neighbor_id,
                        "label": neighbor_id,
                        "description": neighbor.get("description", ""),
                        "group": group
                    })
                
                # 添加到A和B的连接
                links.append({
                    "source": entity_a,
                    "target": neighbor_id,
                    "label": "连接",
                    "weight": 1
                })
                
                links.append({
                    "source": neighbor_id,
                    "target": entity_b,
                    "label": "连接",
                    "weight": 1
                })
        
        return {
            "nodes": nodes,
            "links": links,
            "common_neighbors": common_neighbors,
            "neighbor_count": len(common_neighbors)
        }
        
    except Exception as e:
        print(f"获取共同邻居失败: {str(e)}")
        return {"nodes": [], "links": [], "error": str(e)}

def get_all_paths(driver, entity_a, entity_b, max_depth=3):
    """查询两个实体之间的所有路径（有深度限制）"""
    try: 
        # 验证实体存在性
        check_query = """
        MATCH (a:__Entity__), (b:__Entity__)
        WHERE a.id = $entity_a AND b.id = $entity_b
        RETURN a.id AS id_a, b.id AS id_b
        """
        
        check_result = driver.execute_query(check_query, {
            "entity_a": entity_a,
            "entity_b": entity_b
        })
        
        if not check_result.records or len(check_result.records) == 0:
            return {
                "error": f"实体 '{entity_a}' 或 '{entity_b}' 不存在",
                "nodes": [],
                "links": []
            }
        
        # 根据max_depth的值构建不同的查询
        # Neo4j不允许在路径模式[*1..n]中使用参数，所以我们需要动态构建查询
        if max_depth == 1:
            path_pattern = "[*1..1]"
        elif max_depth == 2:
            path_pattern = "[*1..2]"
        elif max_depth == 3:
            path_pattern = "[*1..3]"
        elif max_depth == 4:
            path_pattern = "[*1..4]"
        elif max_depth >= 5:
            path_pattern = "[*1..5]"  # 限制最大深度为5
        else:
            path_pattern = "[*1..3]"  # 默认值
            
        query = f"""
        MATCH p = (a:__Entity__)-{path_pattern}-(b:__Entity__)
        WHERE a.id = $entity_a AND b.id = $entity_b
        RETURN p
        LIMIT 10
        """
        
        print(f"执行查询: {query}")
        result = driver.execute_query(query, {
            "entity_a": entity_a,
            "entity_b": entity_b
        })
        
        # 转换结果为可视化格式
        nodes = []
        links = []
        paths_info = []
        node_map = {}
        link_map = {}
        
        for record in result.records:
            path = record.get("p")
            if path:
                path_desc = []
                
                # 处理节点
                for node in path.nodes:
                    node_id = node.get("id")
                    if node_id not in node_map:
                        group = [label for label in node.labels if label != "__Entity__"]
                        group = group[0] if group else "Unknown"
                        
                        node_data = {
                            "id": node_id,
                            "label": node_id,
                            "description": node.get("description", ""),
                            "group": group
                        }
                        nodes.append(node_data)
                        node_map[node_id] = node_data
                
                # 处理关系并构建路径描述
                path_rels = []
                for rel in path.relationships:
                    start_id = rel.start_node.get("id")
                    end_id = rel.end_node.get("id")
                    
                    link_key = f"{start_id}_{end_id}_{rel.type}"
                    if link_key not in link_map:
                        link_data = {
                            "source": start_id,
                            "target": end_id,
                            "label": rel.type,
                            "weight": 1
                        }
                        links.append(link_data)
                        link_map[link_key] = link_data
                    
                    path_rels.append((start_id, rel.type, end_id))
                
                # 构建路径描述
                if path_rels:
                    path_str = " -> ".join([f"{start} -[{rel}]-> {end}" for start, rel, end in path_rels])
                    if path_str not in paths_info:
                        paths_info.append(path_str)
        
        return {
            "nodes": nodes,
            "links": links,
            "paths_info": paths_info,
            "path_count": len(paths_info)
        }
    except Exception as e:
        print(f"获取所有路径失败: {str(e)}")
        return {"nodes": [], "links": [], "error": str(e)}

def get_entity_cycles(driver, entity_id, max_depth=4):
    """查找实体的环路"""
    try:
        # 根据max_depth构建适当的路径模式
        if max_depth == 1:
            path_pattern = "[*1..1]"
        elif max_depth == 2:
            path_pattern = "[*1..2]"
        elif max_depth == 3:
            path_pattern = "[*1..3]"
        elif max_depth == 4:
            path_pattern = "[*1..4]"
        else:
            path_pattern = "[*1..4]"  # 限制最大为4，防止查询过于复杂
        
        query = f"""
        MATCH p = (a:__Entity__)-{path_pattern}->(a)
        WHERE a.id = $entity_id
        RETURN p
        LIMIT 10
        """
        
        result = driver.execute_query(query, {
            "entity_id": entity_id
        })
        
        nodes = []
        links = []
        cycles_info = []
        node_map = {}
        link_map = {}
        
        for record in result.records:
            path = record.get("p")
            if path:
                cycle_desc = []
                
                # 处理节点
                for node in path.nodes:
                    node_id = node.get("id")
                    if node_id not in node_map:
                        group = [label for label in node.labels if label != "__Entity__"]
                        group = group[0] if group else "Unknown"
                        
                        node_data = {
                            "id": node_id,
                            "label": node_id,
                            "description": node.get("description", ""),
                            "group": group
                        }
                        nodes.append(node_data)
                        node_map[node_id] = node_data
                
                # 处理关系并构建环路描述
                cycle_rels = []
                for rel in path.relationships:
                    start_id = rel.start_node.get("id")
                    end_id = rel.end_node.get("id")
                    
                    link_key = f"{start_id}_{end_id}_{rel.type}"
                    if link_key not in link_map:
                        link_data = {
                            "source": start_id,
                            "target": end_id,
                            "label": rel.type,
                            "weight": 1
                        }
                        links.append(link_data)
                        link_map[link_key] = link_data
                    
                    cycle_rels.append((start_id, rel.type, end_id))
                
                # 构建环路描述
                if cycle_rels:
                    cycle_str = " -> ".join([f"{start} -[{rel}]-> {end}" for start, rel, end in cycle_rels])
                    cycle_length = len(cycle_rels)
                    cycle_info = {
                        "description": cycle_str,
                        "length": cycle_length
                    }
                    if cycle_str not in [c["description"] for c in cycles_info]:
                        cycles_info.append(cycle_info)
        
        return {
            "nodes": nodes,
            "links": links,
            "cycles_info": cycles_info,
            "cycle_count": len(cycles_info)
        }
    except Exception as e:
        print(f"查找环路失败: {str(e)}")
        return {"nodes": [], "links": [], "error": str(e)}

def get_entity_influence(driver, entity_id, max_depth=2):
    """分析实体的影响范围"""
    try:
        # 根据max_depth构建路径模式
        if max_depth == 1:
            path_pattern = "[*1..1]"
        elif max_depth == 2:
            path_pattern = "[*1..2]"
        elif max_depth == 3:
            path_pattern = "[*1..3]"
        else:
            path_pattern = "[*1..2]"  # 默认值
        
        query = f"""
        MATCH p = (a:__Entity__)-{path_pattern}-(b:__Entity__)
        WHERE a.id = $entity_id
        RETURN p
        LIMIT 100
        """
        
        result = driver.execute_query(query, {
            "entity_id": entity_id
        })

        nodes = []
        links = []
        node_map = {}
        link_map = {}
        direct_connections = set()
        connection_types = {}
        
        # 首先添加中心实体
        center_node = {
            "id": entity_id,
            "label": entity_id,
            "description": "",
            "group": "Center"
        }
        nodes.append(center_node)
        node_map[entity_id] = center_node
        
        for record in result.records:
            path = record.get("p")
            if path:
                # 处理节点
                for node in path.nodes:
                    node_id = node.get("id")
                    if node_id != entity_id and node_id not in node_map:
                        group = [label for label in node.labels if label != "__Entity__"]
                        group = group[0] if group else "Unknown"
                        
                        # 根据与中心实体的距离设置不同的组
                        for i, path_node in enumerate(path.nodes):
                            if path_node.get("id") == node_id:
                                # 计算到中心节点的距离
                                if i == 1 or i == len(path.nodes) - 2:  # 直接相邻
                                    group = "Level1"
                                    direct_connections.add(node_id)
                                else:
                                    group = f"Level{min(i, len(path.nodes) - i - 1)}"
                                break
                        
                        node_data = {
                            "id": node_id,
                            "label": node_id,
                            "description": node.get("description", ""),
                            "group": group
                        }
                        nodes.append(node_data)
                        node_map[node_id] = node_data
                
                # 处理关系
                for rel in path.relationships:
                    start_id = rel.start_node.get("id")
                    end_id = rel.end_node.get("id")
                    rel_type = rel.type
                    
                    # 统计关系类型
                    if rel_type not in connection_types:
                        connection_types[rel_type] = 0
                    connection_types[rel_type] += 1
                    
                    link_key = f"{start_id}_{end_id}_{rel_type}"
                    if link_key not in link_map:
                        link_data = {
                            "source": start_id,
                            "target": end_id,
                            "label": rel_type,
                            "weight": 1
                        }
                        links.append(link_data)
                        link_map[link_key] = link_data
        
        # 构建返回结果
        influence_stats = {
            "direct_connections": len(direct_connections),
            "total_connections": len(nodes) - 1,  # 减去中心节点自身
            "connection_types": [{"type": k, "count": v} for k, v in connection_types.items()],
            "relation_distribution": connection_types
        }
        
        return {
            "nodes": nodes,
            "links": links,
            "influence_stats": influence_stats
        }
    except Exception as e:
        print(f"分析实体影响范围失败: {str(e)}")
        return {"nodes": [], "links": [], "error": str(e)}

def get_simplified_community(driver, entity_id, max_depth=2):
    """使用简化的方法获取实体所属社区"""
    try:
        # 验证实体存在性
        check_query = """
        MATCH (a:__Entity__)
        WHERE a.id = $entity_id
        RETURN a.id AS id, labels(a) AS labels
        """
        
        check_result = driver.execute_query(check_query, {
            "entity_id": entity_id
        })
        
        # 如果实体不存在，返回错误信息
        if not check_result.records or len(check_result.records) == 0:
            print(f"实体不存在: {entity_id}")
            return {
                "error": f"实体 '{entity_id}' 不存在",
                "nodes": [],
                "links": []
            }
            
        entity_record = check_result.records[0]
        print(f"实体存在: {entity_record['id']}, 标签: {entity_record['labels']}")
        
        # 根据max_depth构建路径模式
        if max_depth == 1:
            path_pattern = "[*0..1]"
        elif max_depth == 2:
            path_pattern = "[*0..2]"
        elif max_depth == 3:
            path_pattern = "[*0..3]"
        else:
            path_pattern = "[*0..2]"  # 默认值
        
        # 获取实体所在的N跳邻居
        neighbors_query = f"""
        MATCH p = (a:__Entity__)-{path_pattern}-(b:__Entity__)
        WHERE a.id = $entity_id
        RETURN DISTINCT b
        LIMIT 100
        """
        
        # 执行查询并处理结果
        neighbors_result = driver.execute_query(neighbors_query, {
            "entity_id": entity_id
        })
        
        print(f"获取到 {len(neighbors_result.records)} 个邻居")
        
        # 提取邻居ID
        entity_ids = []
        nodes = []
        node_map = {}
        
        for record in neighbors_result.records:
            entity = record.get("b")
            if entity:
                # 处理返回的实体数据
                try:
                    node_id = None
                    node_labels = []
                    
                    # 检查是否为节点对象或字典
                    if hasattr(entity, 'get'):  # 字典类型
                        node_id = entity.get("id")
                        # 尝试获取标签，可能存在不同形式
                        if "labels" in entity:
                            node_labels = entity["labels"]
                        elif "_labels" in entity:
                            node_labels = entity["_labels"]
                    elif hasattr(entity, 'id'):  # 节点对象
                        node_id = entity.id
                        if hasattr(entity, 'labels'):
                            node_labels = entity.labels
                    else:
                        # 如果是其他类型，尝试转为字符串
                        node_id = str(entity)
                
                    if node_id and node_id not in node_map:
                        # 从标签中确定组类型
                        group = "Unknown"
                        if isinstance(node_labels, list):
                            non_entity_labels = [lbl for lbl in node_labels if lbl != "__Entity__"]
                            if non_entity_labels:
                                group = non_entity_labels[0]
                        elif isinstance(node_labels, (str, dict)):
                            # 处理其他可能的标签格式
                            group = str(node_labels)
                        
                        # 标记中心实体
                        if node_id == entity_id:
                            group = "Center"
                        
                        # 获取描述，安全方式
                        description = ""
                        if hasattr(entity, 'get'):
                            description = entity.get("description", "")
                        elif hasattr(entity, 'description'):
                            description = entity.description
                        
                        node_data = {
                            "id": node_id,
                            "label": node_id,
                            "description": description,
                            "group": group,
                            "community": None  # 先初始化为None
                        }
                        nodes.append(node_data)
                        node_map[node_id] = node_data
                        entity_ids.append(node_id)
                except Exception as e:
                    print(f"处理节点数据时出错: {e}")
                    continue
        
        # 获取这些邻居之间的关系
        relations_query = """
        MATCH (a:__Entity__)-[r]-(b:__Entity__)
        WHERE a.id IN $entity_ids AND b.id IN $entity_ids AND a.id <> b.id
        RETURN DISTINCT a.id as source, b.id as target, type(r) as rel_type
        LIMIT 500
        """
        
        relations_result = driver.execute_query(relations_query, {
            "entity_ids": entity_ids
        })
        
        print(f"获取到 {len(relations_result.records)} 条关系")
        
        # 提取关系
        links = []
        link_map = {}
        
        for record in relations_result.records:
            source_id = record.get("source")
            target_id = record.get("target") 
            rel_type = record.get("rel_type")
            
            if source_id and target_id and rel_type:
                link_key = f"{source_id}_{target_id}_{rel_type}"
                if link_key not in link_map:
                    link_data = {
                        "source": source_id,
                        "target": target_id,
                        "label": rel_type,
                        "weight": 1
                    }
                    links.append(link_data)
                    link_map[link_key] = link_data
        
        # 使用简单的社区检测模拟
        communities = {}
        node_communities = {}
        
        # 计算节点的邻居集
        neighbors = {}
        for link in links:
            source = link["source"]
            target = link["target"]
            
            if source not in neighbors:
                neighbors[source] = set()
            if target not in neighbors:
                neighbors[target] = set()
                
            neighbors[source].add(target)
            neighbors[target].add(source)
        
        # 分配社区ID（基于连通分量的简单社区检测）
        community_id = 0
        visited = set()
        min_community_size = 2
        
         # 先识别主要社区
        for node_id in entity_ids:
            if node_id not in visited and len(neighbors.get(node_id, [])) >= 1:  # 至少有一个邻居
                # 开始一个新社区
                temp_community = []
                queue = [node_id]
                temp_visited = set([node_id])
                
                while queue:
                    current = queue.pop(0)
                    temp_community.append(current)
                    
                    # 检查邻居
                    for neighbor in neighbors.get(current, []):
                        if neighbor not in temp_visited:
                            temp_visited.add(neighbor)
                            queue.append(neighbor)
                
                # 只有社区大小达到阈值才保留
                if len(temp_community) >= min_community_size:
                    community_id += 1
                    communities[community_id] = temp_community
                    for member in temp_community:
                        node_communities[member] = community_id
                        visited.add(member)
        
        # 处理剩余孤立节点，将它们归入最近的社区或中心实体的社区
        for node_id in entity_ids:
            if node_id not in visited:
                # 如果是中心实体，创建自己的社区
                if node_id == entity_id:
                    community_id += 1
                    communities[community_id] = [node_id]
                    node_communities[node_id] = community_id
                    visited.add(node_id)
                else:
                    # 查找与该节点最相关的社区
                    best_community = None
                    best_score = 0
                    
                    for comm_id, members in communities.items():
                        score = 0
                        for member in members:
                            if member in neighbors.get(node_id, []):
                                score += 1
                        
                        if score > best_score:
                            best_score = score
                            best_community = comm_id
                    
                    # 如果找到相关社区，加入该社区
                    if best_community and best_score > 0:
                        communities[best_community].append(node_id)
                        node_communities[node_id] = best_community
                        visited.add(node_id)
                    # 否则，如果有中心实体社区，加入中心实体社区
                    elif entity_id in node_communities:
                        center_community = node_communities[entity_id]
                        communities[center_community].append(node_id)
                        node_communities[node_id] = center_community
                        visited.add(node_id)
        
        # 更新节点的社区信息
        for node in nodes:
            node_id = node["id"]
            if node_id in node_communities:
                node["community"] = node_communities[node_id]
                # 更新节点组以反映社区
                if node_id != entity_id:  # 保持中心节点的组
                    node["group"] = f"Community{node_communities[node_id]}"
        
        # 汇总社区统计信息
        community_stats = []
        for comm_id, members in communities.items():
            if members:
                is_center_in = entity_id in members
                comm_links = [link for link in links if link["source"] in members and link["target"] in members]
                
                # 计算密度 (在大型图中可能需要进一步优化)
                member_count = len(members)
                possible_links = max(1, member_count * (member_count - 1) / 2)
                density = len(comm_links) / possible_links
                
                community_stats.append({
                    "id": comm_id,
                    "size": member_count,
                    "density": density,
                    "contains_center": is_center_in,
                    "sample_members": members[:min(5, member_count)]
                })
        
        # 过滤微小社区（只有一个成员且不包含中心实体）
        filtered_communities = {}
        filtered_stats = []
        filtered_count = 0

        for comm_id, members in communities.items():
            # 保留包含中心实体的社区或成员数大于1的社区
            if entity_id in members or len(members) > 1:
                filtered_communities[filtered_count + 1] = members
                
                # 更新对应的社区统计信息
                for stat in community_stats:
                    if stat["id"] == comm_id:
                        stat_copy = stat.copy()
                        stat_copy["id"] = filtered_count + 1
                        filtered_stats.append(stat_copy)
                        break
                        
                filtered_count += 1

        # 使用过滤后的社区数据
        return {
            "nodes": nodes,
            "links": links,
            "communities": filtered_stats,
            "community_count": filtered_count,
            "entity_community": 1 if entity_id in node_communities else None
        }
    except Exception as e:
        print(f"简化社区检测失败: {str(e)}")
        traceback.print_exc()
        return {"nodes": [], "links": [], "error": str(e)}


def get_source_info_batch(source_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    return BatchProcessor.get_source_info_batch(source_ids, driver)


def get_content_batch(chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    return BatchProcessor.get_content_batch(chunk_ids, driver)


def get_entity_types_from_db() -> List[str]:
    try:
        query = """
        MATCH (e:__Entity__)
        RETURN collect(distinct coalesce(e.type, head([l IN labels(e) WHERE l <> '__Entity__']))) AS types
        """
        result = driver.execute_query(query)
        if result.records:
            types = result.records[0].get("types") or []
            return [t for t in types if t]
        return []
    except Exception as e:
        print(f"获取实体类型失败: {str(e)}")
        return []


def get_relation_types_from_db() -> List[str]:
    try:
        query = """
        MATCH ()-[r]-()
        RETURN collect(distinct type(r)) AS types
        """
        result = driver.execute_query(query)
        if result.records:
            types = result.records[0].get("types") or []
            return [t for t in types if t]
        return []
    except Exception as e:
        print(f"获取关系类型失败: {str(e)}")
        return []


def search_entities(
    *,
    term: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    try:
        query = """
        MATCH (e:__Entity__)
        WHERE ($term IS NULL OR $term = "" OR
               toLower(e.id) CONTAINS toLower($term) OR
               toLower(coalesce(e.name, "")) CONTAINS toLower($term))
          AND ($etype IS NULL OR $etype = "" OR
               $etype IN labels(e) OR e.type = $etype)
        RETURN e
        LIMIT $limit
        """
        result = driver.execute_query(
            query,
            {"term": term, "etype": entity_type, "limit": int(limit)},
        )
        entities = []
        for record in result.records:
            node = record.get("e")
            if not node:
                continue
            labels = list(node.labels) if hasattr(node, "labels") else []
            extra_labels = [lbl for lbl in labels if lbl != "__Entity__"]
            entity = {
                "id": node.get("id"),
                "name": node.get("name"),
                "description": node.get("description", ""),
                "type": node.get("type") or (extra_labels[0] if extra_labels else ""),
                "properties": _sanitize_properties(dict(node.items())),
            }
            entities.append(entity)
        return entities
    except Exception as e:
        print(f"查询实体失败: {str(e)}")
        return []


def search_relations(
    *,
    source: Optional[str] = None,
    target: Optional[str] = None,
    relation_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    try:
        query = """
        MATCH (a:__Entity__)-[r]-(b:__Entity__)
        WHERE ($source IS NULL OR $source = "" OR a.id = $source)
          AND ($target IS NULL OR $target = "" OR b.id = $target)
          AND ($rtype IS NULL OR $rtype = "" OR type(r) = $rtype)
        RETURN a, r, b
        LIMIT $limit
        """
        result = driver.execute_query(
            query,
            {"source": source, "target": target, "rtype": relation_type, "limit": int(limit)},
        )
        relations = []
        for record in result.records:
            rel = record.get("r")
            if not rel:
                continue
            relations.append(
                {
                    "source": record.get("a").get("id") if record.get("a") else None,
                    "target": record.get("b").get("id") if record.get("b") else None,
                    "type": rel.type,
                    "description": rel.get("description", ""),
                    "weight": rel.get("weight", 1),
                    "properties": _sanitize_properties(dict(rel.items())),
                }
            )
        return relations
    except Exception as e:
        print(f"查询关系失败: {str(e)}")
        return []


def create_entity(payload: Dict[str, Any]) -> Dict[str, Any]:
    entity_id = (payload.get("id") or "").strip()
    if not entity_id:
        return {"success": False, "message": "实体ID不能为空"}
    entity_type = payload.get("type") or ""
    label = _format_label(entity_type)

    try:
        exists = driver.execute_query(
            "MATCH (e:__Entity__ {id: $id}) RETURN count(e) AS cnt",
            {"id": entity_id},
        )
        if exists.records and exists.records[0].get("cnt"):
            return {"success": False, "message": f"实体已存在: {entity_id}"}

        props = _sanitize_properties(payload.get("properties"))
        props.update(
            {
                "id": entity_id,
                "name": payload.get("name") or entity_id,
                "description": payload.get("description") or "",
                "type": entity_type,
            }
        )

        label_clause = f":{label}" if label else ""
        query = f"CREATE (e:__Entity__{label_clause}) SET e += $props RETURN e.id AS id"
        driver.execute_query(query, {"props": props})
        return {"success": True, "message": "创建成功"}
    except Exception as e:
        print(f"创建实体失败: {str(e)}")
        return {"success": False, "message": str(e)}


def update_entity(payload: Dict[str, Any]) -> Dict[str, Any]:
    entity_id = (payload.get("id") or "").strip()
    if not entity_id:
        return {"success": False, "message": "实体ID不能为空"}

    entity_type = payload.get("type")
    label = _format_label(entity_type) if entity_type else None

    try:
        props = _sanitize_properties(payload.get("properties"))
        update_fields = {
            "name": payload.get("name"),
            "description": payload.get("description"),
            "type": entity_type,
        }
        update_fields = {k: v for k, v in update_fields.items() if v is not None}

        query = """
        MATCH (e:__Entity__ {id: $id})
        SET e += $props
        SET e += $fields
        RETURN count(e) AS cnt
        """
        result = driver.execute_query(
            query,
            {"id": entity_id, "props": props, "fields": update_fields},
        )
        if not result.records or result.records[0].get("cnt") == 0:
            return {"success": False, "message": f"实体不存在: {entity_id}"}

        if label:
            label_query = f"MATCH (e:__Entity__ {{id: $id}}) SET e:{label} RETURN e.id AS id"
            driver.execute_query(label_query, {"id": entity_id})

        return {"success": True, "message": "更新成功"}
    except Exception as e:
        print(f"更新实体失败: {str(e)}")
        return {"success": False, "message": str(e)}


def delete_entity(entity_id: str) -> Dict[str, Any]:
    if not entity_id:
        return {"success": False, "message": "实体ID不能为空"}

    try:
        result = driver.execute_query(
            "MATCH (e:__Entity__ {id: $id}) DETACH DELETE e RETURN count(e) AS cnt",
            {"id": entity_id},
        )
        if not result.records or result.records[0].get("cnt") == 0:
            return {"success": False, "message": f"实体不存在: {entity_id}"}
        return {"success": True, "message": "删除成功"}
    except Exception as e:
        print(f"删除实体失败: {str(e)}")
        return {"success": False, "message": str(e)}


def create_relation(payload: Dict[str, Any]) -> Dict[str, Any]:
    rel_type_raw = payload.get("type")
    rel_type = _format_label(rel_type_raw)
    if not rel_type:
        return {"success": False, "message": "关系类型不能为空"}

    source = (payload.get("source") or "").strip()
    target = (payload.get("target") or "").strip()
    if not source or not target:
        return {"success": False, "message": "关系必须包含 source/target"}

    props = _sanitize_properties(payload.get("properties"))
    if payload.get("description") is not None:
        props["description"] = payload.get("description")
    if payload.get("weight") is not None:
        props["weight"] = payload.get("weight")

    try:
        query = f"""
        MATCH (a:__Entity__ {{id: $source}}), (b:__Entity__ {{id: $target}})
        CREATE (a)-[r:{rel_type}]->(b)
        SET r += $props
        RETURN type(r) AS type
        """
        result = driver.execute_query(
            query,
            {"source": source, "target": target, "props": props},
        )
        if not result.records:
            return {"success": False, "message": "创建关系失败"}
        return {"success": True, "message": "创建成功"}
    except Exception as e:
        print(f"创建关系失败: {str(e)}")
        return {"success": False, "message": str(e)}


def update_relation(payload: Dict[str, Any]) -> Dict[str, Any]:
    source = (payload.get("source") or "").strip()
    target = (payload.get("target") or "").strip()
    original_type_raw = payload.get("original_type") or payload.get("type")
    original_type = _format_label(original_type_raw)
    if not source or not target or not original_type:
        return {"success": False, "message": "关系更新需要 source/target/original_type"}

    try:
        props = _sanitize_properties(payload.get("properties"))
        if payload.get("description") is not None:
            props["description"] = payload.get("description")
        if payload.get("weight") is not None:
            props["weight"] = payload.get("weight")

        new_type_raw = payload.get("new_type")
        new_type = _format_label(new_type_raw) if new_type_raw else None

        if new_type and new_type != original_type:
            # 复制旧关系属性（若存在）并创建新关系
            fetch_query = f"""
            MATCH (a:__Entity__ {{id: $source}})-[r:{original_type}]-(b:__Entity__ {{id: $target}})
            RETURN properties(r) AS props
            LIMIT 1
            """
            fetch_result = driver.execute_query(fetch_query, {"source": source, "target": target})
            existing_props = {}
            if fetch_result.records:
                existing_props = fetch_result.records[0].get("props") or {}
            existing_props.update(props)

            create_query = f"""
            MATCH (a:__Entity__ {{id: $source}}), (b:__Entity__ {{id: $target}})
            CREATE (a)-[r:{new_type}]->(b)
            SET r += $props
            RETURN type(r) AS type
            """
            driver.execute_query(create_query, {"source": source, "target": target, "props": existing_props})

            delete_query = f"""
            MATCH (a:__Entity__ {{id: $source}})-[r:{original_type}]-(b:__Entity__ {{id: $target}})
            DELETE r
            """
            driver.execute_query(delete_query, {"source": source, "target": target})
            return {"success": True, "message": "更新成功"}

        update_query = f"""
        MATCH (a:__Entity__ {{id: $source}})-[r:{original_type}]-(b:__Entity__ {{id: $target}})
        SET r += $props
        RETURN count(r) AS cnt
        """
        result = driver.execute_query(
            update_query,
            {"source": source, "target": target, "props": props},
        )
        if not result.records or result.records[0].get("cnt") == 0:
            return {"success": False, "message": "关系不存在"}
        return {"success": True, "message": "更新成功"}
    except Exception as e:
        print(f"更新关系失败: {str(e)}")
        return {"success": False, "message": str(e)}


def delete_relation(payload: Dict[str, Any]) -> Dict[str, Any]:
    source = (payload.get("source") or "").strip()
    target = (payload.get("target") or "").strip()
    rel_type = _format_label(payload.get("type"))
    if not source or not target or not rel_type:
        return {"success": False, "message": "删除关系需要 source/target/type"}

    try:
        query = f"""
        MATCH (a:__Entity__ {{id: $source}})-[r:{rel_type}]-(b:__Entity__ {{id: $target}})
        DELETE r
        RETURN count(r) AS cnt
        """
        result = driver.execute_query(query, {"source": source, "target": target})
        if not result.records or result.records[0].get("cnt") == 0:
            return {"success": False, "message": "关系不存在"}
        return {"success": True, "message": "删除成功"}
    except Exception as e:
        print(f"删除关系失败: {str(e)}")
        return {"success": False, "message": str(e)}


def run_reasoning(
    *,
    reasoning_type: str,
    entity_a: str,
    entity_b: Optional[str] = None,
    max_depth: int = 3,
    algorithm: Optional[str] = None,
) -> Dict[str, Any]:
    if reasoning_type == "shortest_path":
        return get_shortest_path(driver, entity_a, entity_b, max_depth)
    if reasoning_type == "one_two_hop":
        return get_one_two_hop_paths(driver, entity_a, entity_b)
    if reasoning_type == "common_neighbors":
        return get_common_neighbors(driver, entity_a, entity_b)
    if reasoning_type == "all_paths":
        return get_all_paths(driver, entity_a, entity_b, max_depth)
    if reasoning_type == "entity_cycles":
        return get_entity_cycles(driver, entity_a, max_depth)
    if reasoning_type == "entity_influence":
        return get_entity_influence(driver, entity_a, max_depth)
    if reasoning_type == "entity_community":
        return get_simplified_community(driver, entity_a, max_depth)
    return {"nodes": [], "links": [], "error": f"未知推理类型: {reasoning_type}"}


class Neo4jKnowledgeGraphService(KnowledgeGraphPort):
    def extract_kg_from_message(
        self,
        *,
        message: str,
        query: Optional[str] = None,
        reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return extract_kg_from_message(message, query=query, reference=reference)

    def get_knowledge_graph(self, *, limit: int = 100, query: Optional[str] = None) -> Dict[str, Any]:
        return get_knowledge_graph(limit=limit, query=query)

    def run_reasoning(
        self,
        *,
        reasoning_type: str,
        entity_a: str,
        entity_b: Optional[str] = None,
        max_depth: int = 3,
        algorithm: Optional[str] = None,
    ) -> Dict[str, Any]:
        return run_reasoning(
            reasoning_type=reasoning_type,
            entity_a=entity_a,
            entity_b=entity_b,
            max_depth=max_depth,
            algorithm=algorithm,
        )

    def search_entities(
        self,
        *,
        term: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return search_entities(term=term, entity_type=entity_type, limit=limit)

    def search_relations(
        self,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return search_relations(
            source=source,
            target=target,
            relation_type=relation_type,
            limit=limit,
        )

    def create_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return create_entity(payload)

    def update_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return update_entity(payload)

    def delete_entity(self, entity_id: str) -> Dict[str, Any]:
        return delete_entity(entity_id)

    def create_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return create_relation(payload)

    def update_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return update_relation(payload)

    def delete_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return delete_relation(payload)

    def get_source_content(self, source_id: str) -> str:
        return get_source_content(source_id)

    def get_source_file_info(self, source_id: str) -> Dict[str, Any]:
        return get_source_file_info(source_id)

    def get_source_info_batch(self, source_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        return get_source_info_batch(source_ids)

    def get_content_batch(self, chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        return get_content_batch(chunk_ids)

    def get_chunks(self, *, limit: int = 10, offset: int = 0, kb_prefix: str | None = None) -> Dict[str, Any]:
        return get_chunks(limit=limit, offset=offset, kb_prefix=kb_prefix)
