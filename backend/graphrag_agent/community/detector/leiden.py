from typing import Dict, Any
from .base import BaseCommunityDetector
from .projections import GraphProjectionMixin

from graphrag_agent.config.settings import GDS_CONCURRENCY
from graphrag_agent.config.settings import (
    GRAPH_COMMUNITY_ID_PREFIX,
    GRAPH_ENTITY_ID_PREFIX_FILTER,
)

class LeidenDetector(GraphProjectionMixin, BaseCommunityDetector):
    """Leiden算法社区检测实现"""
    
    def detect_communities(self) -> Dict[str, Any]:
        """执行Leiden算法社区检测"""
        if not self.G:
            raise ValueError("请先创建图投影")
            
        print("开始执行Leiden社区检测...")
        
        try:
            # 检查连通分量
            relationship_types = getattr(self, "relationship_types", None)
            if relationship_types:
                wcc = self.gds.wcc.stats(self.G, relationshipTypes=relationship_types)
            else:
                wcc = self.gds.wcc.stats(self.G)
            print(f"图包含 {wcc.get('componentCount', 0)} 个连通分量")
            
            # 执行Leiden算法
            config = {
                "writeProperty": "communities",
                "includeIntermediateCommunities": True,
                **self._get_optimized_leiden_params(),
            }
            if relationship_types:
                config["relationshipTypes"] = relationship_types

            try:
                result = self.gds.leiden.write(
                    self.G,
                    relationshipWeightProperty="weight",
                    **config,
                )
            except Exception as weight_err:
                print(f"Leiden使用weight失败（将降级不加权）: {weight_err}")
                result = self.gds.leiden.write(self.G, **config)
            
            return {
                'componentCount': wcc.get('componentCount', 0),
                'componentDistribution': wcc.get('componentDistribution', {}),
                'communityCount': result.get('communityCount', 0),
                'modularity': result.get('modularity', 0),
                'ranLevels': result.get('ranLevels', 0)
            }
            
        except Exception as e:
            print(f"Leiden算法执行失败: {e}")
            return self._execute_fallback_leiden()
    
    def _execute_fallback_leiden(self) -> Dict[str, Any]:
        """执行备用Leiden算法"""
        print("尝试使用备用参数...")
        
        try:
            relationship_types = getattr(self, "relationship_types", None)
            config = {
                "writeProperty": "communities",
                "includeIntermediateCommunities": False,
                "gamma": 0.5,
                "tolerance": 0.001,
                "maxLevels": 2,
                "concurrency": 1,
            }
            if relationship_types:
                config["relationshipTypes"] = relationship_types

            try:
                result = self.gds.leiden.write(
                    self.G,
                    relationshipWeightProperty="weight",
                    **config,
                )
            except Exception:
                result = self.gds.leiden.write(self.G, **config)
            
            return {
                'communityCount': result.get('communityCount', 0),
                'modularity': result.get('modularity', 0),
                'ranLevels': result.get('ranLevels', 0),
                'note': '使用了备用参数'
            }
        except Exception as e:
            raise ValueError(f"Leiden算法执行失败: {e}")
    
    def _get_optimized_leiden_params(self) -> Dict[str, Any]:
        """获取优化的Leiden算法参数"""
        if self.memory_mb > 32 * 1024:  # >32GB
            return {
                'gamma': 1.0,
                'tolerance': 0.0001,
                'maxLevels': 10,
                'concurrency': GDS_CONCURRENCY
            }
        elif self.memory_mb > 16 * 1024:  # >16GB
            return {
                'gamma': 1.0,
                'tolerance': 0.0005,
                'maxLevels': 5,
                'concurrency': max(1, GDS_CONCURRENCY - 1)
            }
        else:  # 小内存系统
            return {
                'gamma': 0.8,
                'tolerance': 0.001,
                'maxLevels': 3,
                'concurrency': max(1, GDS_CONCURRENCY // 2)
            }
    
    def save_communities(self) -> Dict[str, int]:
        """保存Leiden算法的社区检测结果"""
        print("开始保存Leiden社区检测结果...")
        
        try:
            # 创建约束
            self.graph.query(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:__Community__) REQUIRE c.id IS UNIQUE;"
            )
            
            entity_prefix = GRAPH_ENTITY_ID_PREFIX_FILTER
            community_prefix = GRAPH_COMMUNITY_ID_PREFIX

            # 保存基础社区关系
            base_result = self.graph.query("""
            MATCH (e:`__Entity__`)
            WHERE e.communities IS NOT NULL AND size(e.communities) > 0
              AND ($entity_prefix = '' OR e.id STARTS WITH $entity_prefix)
            WITH collect({entityId: id(e), community: e.communities[0]}) AS data
            UNWIND data AS item
            MERGE (c:`__Community__` {id: $community_prefix + '0-' + toString(item.community)})
            ON CREATE SET c.level = 0
            WITH item, c
            MATCH (e) WHERE id(e) = item.entityId
            MERGE (e)-[:IN_COMMUNITY]->(c)
            RETURN count(*) AS base_count
            """, params={"entity_prefix": entity_prefix, "community_prefix": community_prefix})
            
            base_count = base_result[0]['base_count'] if base_result else 0
            
            # 保存更高层级社区关系
            higher_result = self.graph.query("""
            MATCH (e:`__Entity__`)
            WHERE e.communities IS NOT NULL AND size(e.communities) > 1
              AND ($entity_prefix = '' OR e.id STARTS WITH $entity_prefix)
            WITH e, e.communities AS communities
            UNWIND range(1, size(communities) - 1) AS index
            WITH e, index, communities[index] AS current_community, 
                 communities[index-1] AS previous_community
            
            MERGE (current:`__Community__` {id: $community_prefix + toString(index) + '-' +
                                              toString(current_community)})
            ON CREATE SET current.level = index
            
            WITH e, current, previous_community, index
            MATCH (previous:`__Community__` {id: $community_prefix + toString(index - 1) + '-' +
                                              toString(previous_community)})
            MERGE (previous)-[:IN_COMMUNITY]->(current)
            
            RETURN count(*) AS higher_count
            """, params={"entity_prefix": entity_prefix, "community_prefix": community_prefix})
            
            higher_count = higher_result[0]['higher_count'] if higher_result else 0
            
            return {'saved_communities': base_count + higher_count}
            
        except Exception as e:
            print(f"社区保存失败: {e}")
            return self._save_communities_fallback()
