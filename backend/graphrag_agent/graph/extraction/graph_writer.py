import re
import concurrent.futures
from typing import List, Set

from graphrag_agent.ports.neo4jdb import GraphClient, get_graph
from graphrag_agent.ports.graph_documents import add_graph_documents
from graphrag_agent.config.settings import BATCH_SIZE as DEFAULT_BATCH_SIZE, MAX_WORKERS as DEFAULT_MAX_WORKERS
from graphrag_agent.config.settings import kb_scoped_label_for_kb_prefix
from graphrag_agent.graph.extraction.graph_types import (
    GraphDocumentData,
    GraphNodeData,
    GraphRelationshipData,
    GraphSourceData,
)

class GraphWriter:
    """
    图写入器，负责将提取的实体和关系写入Neo4j图数据库。
    处理实体和关系的解析、转换为GraphDocumentData，以及批量写入图数据库。
    """
    
    def __init__(
        self,
        graph: GraphClient | None = None,
        batch_size: int = 50,
        max_workers: int = 4,
        kb_prefix: str = "",
    ):
        """
        初始化图写入器
        
        Args:
            graph: Neo4j图数据库对象，如果为None则使用连接管理器获取
            batch_size: 批处理大小
            max_workers: 并行工作线程数
            kb_prefix: 知识库命名空间前缀（用于同库隔离，比如 "edu"；为空则不加前缀）
        """
        self.graph = graph or get_graph()
        self.batch_size = batch_size or DEFAULT_BATCH_SIZE
        self.max_workers = max_workers or DEFAULT_MAX_WORKERS
        self.kb_prefix = (kb_prefix or "").strip()
        self.id_prefix = f"{self.kb_prefix}:" if self.kb_prefix else ""
        
        # 节点缓存，用于减少重复节点的创建
        self.node_cache = {}
        
        # 用于跟踪已经处理的节点，减少重复操作
        self.processed_nodes: Set[str] = set()

    def _with_prefix(self, value: str) -> str:
        if not self.id_prefix:
            return value
        if value.startswith(self.id_prefix):
            return value
        return f"{self.id_prefix}{value}"
        
    def convert_to_graph_document(self, chunk_id: str, input_text: str, result: str) -> GraphDocumentData:
        """
        将提取的实体关系文本转换为GraphDocumentData对象
        
        Args:
            chunk_id: 文本块ID
            input_text: 输入文本
            result: 提取结果
            
        Returns:
            GraphDocumentData: 转换后的图文档对象
        """
        node_pattern = re.compile(r'\("entity" : "(.+?)" : "(.+?)" : "(.+?)"\)')
        relationship_pattern = re.compile(r'\("relationship" : "(.+?)" : "(.+?)" : "(.+?)" : "(.+?)" : (.+?)\)')

        nodes = {}
        relationships = []

        def _parse_weight(raw_weight: str) -> float:
            try:
                return float(raw_weight)
            except Exception:
                match = re.search(r"(-?\\d+(?:\\.\\d+)?)\\s*$", raw_weight or "")
                return float(match.group(1)) if match else 1.0

        # 解析节点 - 使用缓存提高效率
        try:
            for match in node_pattern.findall(result):
                raw_node_id, node_type, description = match
                node_id = self._with_prefix(raw_node_id)
                if node_id in self.node_cache:
                    nodes[node_id] = self.node_cache[node_id]
                    continue
                if node_id in nodes:
                    continue

                new_node = GraphNodeData(
                    node_id=node_id,
                    node_type=node_type,
                    properties={"description": description},
                )
                nodes[node_id] = new_node
                self.node_cache[node_id] = new_node
        except Exception as e:
            print(f"解析节点时出错: {e}")
            return GraphDocumentData(
                nodes=[],
                relationships=[],
                source=GraphSourceData(
                    content=input_text,
                    metadata={"chunk_id": chunk_id, "error": str(e)},
                ),
            )

        # 解析关系（容错：单条关系格式异常不应导致整块丢弃）
        for match in relationship_pattern.findall(result):
            try:
                raw_source_id, raw_target_id, rel_type, description, weight = match
                source_id = self._with_prefix(raw_source_id)
                target_id = self._with_prefix(raw_target_id)

                if source_id not in nodes:
                    nodes[source_id] = self.node_cache.get(
                        source_id,
                        GraphNodeData(
                            node_id=source_id,
                            node_type="未知",
                            properties={"description": "No additional data"},
                        ),
                    )
                    self.node_cache[source_id] = nodes[source_id]

                if target_id not in nodes:
                    nodes[target_id] = self.node_cache.get(
                        target_id,
                        GraphNodeData(
                            node_id=target_id,
                            node_type="未知",
                            properties={"description": "No additional data"},
                        ),
                    )
                    self.node_cache[target_id] = nodes[target_id]

                relationships.append(
                    GraphRelationshipData(
                        source_id=source_id,
                        target_id=target_id,
                        rel_type=rel_type,
                        properties={
                            "description": description,
                            "weight": _parse_weight(weight),
                        },
                    )
                )
            except Exception as e:
                print(f"解析关系时出错，已跳过: {e}")
                continue

        # 创建并返回GraphDocumentData对象
        return GraphDocumentData(
            nodes=list(nodes.values()),
            relationships=relationships,
            source=GraphSourceData(
                content=input_text,
                metadata={"chunk_id": chunk_id},
            ),
        )
        
    def process_and_write_graph_documents(self, file_contents: List) -> None:
        """
        处理并写入所有文件的GraphDocumentData对象 - 使用并行处理和批处理优化
        
        Args:
            file_contents: 文件内容列表
        """
        all_graph_documents = []
        all_chunk_ids = []
        
        # 预分配列表大小
        total_chunks = sum(len(file_content[3]) for file_content in file_contents)
        all_graph_documents = [None] * total_chunks
        all_chunk_ids = [None] * total_chunks
        
        chunk_index = 0
        error_count = 0
        
        print(f"开始处理 {total_chunks} 个chunks的GraphDocumentData")
        
        # 使用线程池并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {}
            
            # 提交所有任务
            for file_content in file_contents:
                chunks = file_content[3]  # chunks_with_hash在索引3的位置
                results = file_content[4]  # 提取结果在索引4的位置
                
                for i, (chunk, result) in enumerate(zip(chunks, results)):
                    future = executor.submit(
                        self.convert_to_graph_document,
                        chunk["chunk_id"],
                        chunk["chunk_doc"].page_content,
                        result
                    )
                    future_to_index[future] = chunk_index
                    chunk_index += 1
            
            # 收集处理结果
            for future in concurrent.futures.as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    graph_document = future.result()
                    
                    # 只保留有效的图文档
                    if len(graph_document.nodes) > 0 or len(graph_document.relationships) > 0:
                        all_graph_documents[idx] = graph_document
                        all_chunk_ids[idx] = graph_document.source.metadata.get("chunk_id")
                    else:
                        all_graph_documents[idx] = None
                        all_chunk_ids[idx] = None
                        
                except Exception as e:
                    error_count += 1
                    print(f"处理chunk时出错 (已有{error_count}个错误): {e}")
                    all_graph_documents[idx] = None
                    all_chunk_ids[idx] = None
        
        # 过滤掉None值
        all_graph_documents = [doc for doc in all_graph_documents if doc is not None]
        all_chunk_ids = [id for id in all_chunk_ids if id is not None]
        
        print(f"共处理 {total_chunks} 个chunks, 有效文档 {len(all_graph_documents)}, 错误 {error_count}")
        
        # 批量写入图文档
        self._batch_write_graph_documents(all_graph_documents)
        
        # 批量合并chunk关系
        if all_chunk_ids:
            self.merge_chunk_relationships(all_chunk_ids)

        # 为当前 KB 打标（用于同库多 KB 的索引隔离）
        self._apply_kb_labels()

    def _apply_kb_labels(self) -> None:
        if not self.id_prefix:
            return

        entity_label = kb_scoped_label_for_kb_prefix(self.kb_prefix, "entity")
        chunk_label = kb_scoped_label_for_kb_prefix(self.kb_prefix, "chunk")
        document_label = kb_scoped_label_for_kb_prefix(self.kb_prefix, "document")
        if not entity_label and not chunk_label and not document_label:
            return

        prefix = self.id_prefix
        if entity_label:
            self.graph.query(
                f"""
                MATCH (e:`__Entity__`)
                WHERE e.id STARTS WITH $prefix
                SET e:`{entity_label}`
                """,
                params={"prefix": prefix},
            )
        if chunk_label:
            self.graph.query(
                f"""
                MATCH (c:`__Chunk__`)
                WHERE c.id STARTS WITH $prefix OR c.fileName STARTS WITH $prefix
                SET c:`{chunk_label}`
                """,
                params={"prefix": prefix},
            )
        if document_label:
            self.graph.query(
                f"""
                MATCH (d:`__Document__`)
                WHERE d.fileName STARTS WITH $prefix
                SET d:`{document_label}`
                """,
                params={"prefix": prefix},
            )
    
    def _batch_write_graph_documents(self, documents: List[GraphDocumentData]) -> None:
        """
        批量写入图文档
        
        Args:
            documents: 图文档列表
        """
        if not documents:
            return
            
        # 增加批处理大小的动态调整
        optimal_batch_size = min(self.batch_size, max(10, len(documents) // 10))
        total_batches = (len(documents) + optimal_batch_size - 1) // optimal_batch_size
        
        print(f"开始批量写入 {len(documents)} 个文档，批次大小: {optimal_batch_size}, 总批次: {total_batches}")
        
        # 批量写入图文档
        for i in range(0, len(documents), optimal_batch_size):
            batch = documents[i:i+optimal_batch_size]
            if batch:
                try:
                    self.write_graph_documents(batch)
                    print(f"已写入批次 {i//optimal_batch_size + 1}/{total_batches}")
                except Exception as e:
                    print(f"写入图文档批次时出错: {e}")
                    # 如果批次写入失败，尝试逐个写入以避免整批失败
                    for doc in batch:
                        try:
                            self.write_graph_documents([doc])
                        except Exception as e2:
                            print(f"单个文档写入失败: {e2}")

    def write_graph_documents(self, documents: List[GraphDocumentData]) -> None:
        """写入图文档（由基础设施适配具体存储）"""
        add_graph_documents(
            documents,
            base_entity_label=True,
            include_source=True,
        )
    
    def merge_chunk_relationships(self, chunk_ids: List[str]) -> None:
        """
        合并Chunk节点与Document节点的关系
        
        Args:
            chunk_ids: 块ID列表
        """
        if not chunk_ids:
            return
        
        # 去除重复的chunk_id以减少操作数量
        unique_chunk_ids = list(set(chunk_ids))
        print(f"开始合并 {len(unique_chunk_ids)} 个唯一chunk关系")
            
        # 动态批处理大小
        optimal_batch_size = min(self.batch_size, max(20, len(unique_chunk_ids) // 5))
        total_batches = (len(unique_chunk_ids) + optimal_batch_size - 1) // optimal_batch_size
        
        print(f"合并关系批次大小: {optimal_batch_size}, 总批次: {total_batches}")
        
        # 分批处理，避免一次性处理过多数据
        for i in range(0, len(unique_chunk_ids), optimal_batch_size):
            batch_chunk_ids = unique_chunk_ids[i:i+optimal_batch_size]
            batch_data = [{"chunk_id": chunk_id} for chunk_id in batch_chunk_ids]
            
            try:
                # 使用原始的查询，确保兼容性
                merge_query = """
                    UNWIND $batch_data AS data
                    MATCH (c:`__Chunk__` {id: data.chunk_id}), (d:Document{chunk_id:data.chunk_id})
                    WITH c, d
                    MATCH (d)-[r:MENTIONS]->(e)
                    MERGE (c)-[newR:MENTIONS]->(e)
                    ON CREATE SET newR += properties(r)
                    DETACH DELETE d
                """
                
                self.graph.query(merge_query, params={"batch_data": batch_data})
                print(f"已处理合并关系批次 {i//optimal_batch_size + 1}/{total_batches}")
            except Exception as e:
                print(f"合并关系批次时出错: {e}")
                # 如果批处理失败，尝试逐个处理
                for chunk_id in batch_chunk_ids:
                    try:
                        single_query = """
                            MATCH (c:`__Chunk__` {id: $chunk_id}), (d:Document{chunk_id:$chunk_id})
                            WITH c, d
                            MATCH (d)-[r:MENTIONS]->(e)
                            MERGE (c)-[newR:MENTIONS]->(e)
                            ON CREATE SET newR += properties(r)
                            DETACH DELETE d
                        """
                        self.graph.query(single_query, params={"chunk_id": chunk_id})
                    except Exception as e2:
                        print(f"处理单个chunk关系时出错: {e2}")
