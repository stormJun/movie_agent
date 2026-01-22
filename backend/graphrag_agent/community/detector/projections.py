from typing import Dict, Any, Tuple

from graphrag_agent.config.settings import GRAPH_ENTITY_ID_PREFIX_FILTER

class GraphProjectionMixin:
    """图投影功能的混入类"""
    
    def create_projection(self) -> Tuple[Any, Dict]:
        """创建图投影"""
        print("开始创建社区检测的图投影...")

        entity_prefix = GRAPH_ENTITY_ID_PREFIX_FILTER
        self.relationship_types = None

        # 检查节点数量
        node_count = self._get_node_count(entity_prefix)
        if node_count > self.node_count_limit:
            print(f"警告: 节点数量({node_count})超过限制({self.node_count_limit})")
            return self._create_filtered_projection(node_count, entity_prefix=entity_prefix)
        
        # 删除已存在的投影
        try:
            self.gds.graph.drop(self.projection_name, failIfMissing=False)
        except Exception as e:
            print(f"删除旧投影时出错 (可忽略): {e}")

        if entity_prefix:
            print(f"使用前缀过滤创建投影: {entity_prefix}")
            return self._create_prefix_filtered_projection(entity_prefix)

        # 创建标准投影
        try:
            self.G, result = self.gds.graph.project(
                self.projection_name,
                "__Entity__",
                {
                    "_ALL_": {
                        "type": "*",
                        "orientation": "UNDIRECTED",
                        "properties": {"weight": {"property": "*", "aggregation": "COUNT"}},
                    }
                },
            )
            print(f"图投影创建成功: {result.get('nodeCount', 0)} 节点, "
                  f"{result.get('relationshipCount', 0)} 关系")
            return self.G, result
        except Exception as e:
            print(f"标准投影创建失败: {e}")
            return self._create_conservative_projection()
    
    def _get_node_count(self, entity_prefix: str = "") -> int:
        """获取节点数量"""
        if entity_prefix:
            result = self.graph.query(
                """
                MATCH (e:__Entity__)
                WHERE e.id STARTS WITH $id_prefix
                RETURN count(e) AS count
                """,
                params={"id_prefix": entity_prefix},
            )
        else:
            result = self.graph.query(
                "MATCH (e:__Entity__) RETURN count(e) AS count"
            )
        return result[0]["count"] if result else 0

    def _create_prefix_filtered_projection(self, entity_prefix: str) -> Tuple[Any, Dict]:
        """
        基于 __Entity__.id 前缀创建 Cypher 投影（用于共库隔离）。

        备注：Cypher 投影在 GDS 中是“有向图”，需要再调用 toUndirected 生成 UNDIRECTED 关系，
        Leiden 才能运行。
        """
        try:
            node_query = """
            MATCH (e:__Entity__)
            WHERE e.id STARTS WITH $id_prefix
            RETURN id(e) AS id
            """

            rel_query = """
            MATCH (s:__Entity__)-[r]-(t:__Entity__)
            WHERE s.id STARTS WITH $id_prefix AND t.id STARTS WITH $id_prefix AND id(s) < id(t)
            WITH id(s) AS source, id(t) AS target, sum(coalesce(r.weight, 1.0)) AS weight
            RETURN source, target, weight
            """

            self.G, result = self.gds.graph.project.cypher(
                self.projection_name,
                node_query,
                rel_query,
                parameters={"id_prefix": entity_prefix},
            )

            # 变换为无向关系（写入到内存图，关系类型为 UNDIRECTED）
            self.graph.query(
                """
                CALL gds.graph.relationships.toUndirected(
                  $graph_name,
                  {relationshipType: '*', mutateRelationshipType: 'UNDIRECTED'}
                )
                """,
                params={"graph_name": self.projection_name},
            )
            self.relationship_types = ["UNDIRECTED"]
            print(
                f"前缀投影创建成功: {result.get('nodeCount', 0)} 节点, "
                f"{result.get('relationshipCount', 0)} 关系"
            )
            return self.G, result
        except Exception as e:
            print(f"前缀投影创建失败: {e}")
            return self._create_conservative_projection()
    
    def _create_filtered_projection(self, total_node_count: int, entity_prefix: str = "") -> Tuple[Any, Dict]:
        """创建过滤后的投影"""
        print("创建过滤后的投影...")
        
        try:
            # 获取重要节点
            if entity_prefix:
                result = self.graph.query(
                    """
                    MATCH (e:__Entity__)-[r]-()
                    WHERE e.id STARTS WITH $id_prefix
                    WITH e, count(r) AS rel_count
                    ORDER BY rel_count DESC
                    LIMIT toInteger($limit)
                    RETURN collect(id(e)) AS important_nodes
                    """,
                    params={"limit": self.node_count_limit, "id_prefix": entity_prefix},
                )
            else:
                result = self.graph.query(
                    """
                    MATCH (e:__Entity__)-[r]-()
                    WITH e, count(r) AS rel_count
                    ORDER BY rel_count DESC
                    LIMIT toInteger($limit)
                    RETURN collect(id(e)) AS important_nodes
                    """,
                    params={"limit": self.node_count_limit}
                )
            
            if not result or not result[0]["important_nodes"]:
                return self._create_conservative_projection()
            
            important_nodes = result[0]["important_nodes"]
            
            self.G, result = self.gds.graph.project.cypher(
                self.projection_name,
                """
                MATCH (e:__Entity__)
                WHERE id(e) IN $node_ids
                RETURN id(e) AS id
                """,
                """
                MATCH (s:__Entity__)-[r]-(t:__Entity__)
                WHERE id(s) IN $node_ids AND id(t) IN $node_ids AND id(s) < id(t)
                WITH id(s) AS source, id(t) AS target, sum(coalesce(r.weight, 1.0)) AS weight
                RETURN source, target, weight
                """,
                parameters={"node_ids": important_nodes},
            )
            self.graph.query(
                """
                CALL gds.graph.relationships.toUndirected(
                  $graph_name,
                  {relationshipType: '*', mutateRelationshipType: 'UNDIRECTED'}
                )
                """,
                params={"graph_name": self.projection_name},
            )
            self.relationship_types = ["UNDIRECTED"]
            print(f"过滤投影创建成功: {result.get('nodeCount', 0)} 节点, "
                  f"{result.get('relationshipCount', 0)} 关系")
            return self.G, result
            
        except Exception as e:
            print(f"过滤投影创建失败: {e}")
            return self._create_conservative_projection()
    
    def _create_conservative_projection(self) -> Tuple[Any, Dict]:
        """创建保守配置的投影"""
        print("尝试使用保守配置创建投影...")
        
        try:
            self.G, result = self.gds.graph.project(
                self.projection_name,
                "__Entity__",
                {
                    "_ALL_": {
                        "type": "*",
                        "orientation": "UNDIRECTED",
                        "properties": {
                            "weight": {"property": "*", "aggregation": "COUNT"}
                        },
                    }
                },
            )
            print(f"保守投影创建成功: {result.get('nodeCount', 0)} 节点")
            return self.G, result
            
        except Exception as e:
            print(f"保守投影创建失败: {e}")
            return self._create_minimal_projection()
    
    def _create_minimal_projection(self) -> Tuple[Any, Dict]:
        """创建最小化投影"""
        print("尝试创建最小化投影...")
        
        try:
            # 获取最重要的节点
            result = self.graph.query(
                """
                MATCH (e:__Entity__)-[r]-()
                WITH e, count(r) AS rel_count
                ORDER BY rel_count DESC
                LIMIT 1000
                RETURN collect(id(e)) AS critical_nodes
                """
            )
            
            if not result or not result[0]["critical_nodes"]:
                raise ValueError("无法获取关键节点")
            
            critical_nodes = result[0]["critical_nodes"]
            
            node_spec = {"__Entity__": {"filter": f"id(node) IN {critical_nodes}"}}
            self.G, result = self.gds.graph.project(self.projection_name, node_spec, "*")
            print(f"最小化投影创建成功: {result.get('nodeCount', 0)} 节点")
            return self.G, result
            
        except Exception as e:
            print(f"所有投影方法均失败: {e}")
            raise ValueError("无法创建必要的图投影")
