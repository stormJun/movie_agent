from __future__ import annotations

from typing import Any, Dict, List, Optional

from application.ports.knowledge_graph_port import KnowledgeGraphPort


class KnowledgeGraphService:
    def __init__(self, *, port: KnowledgeGraphPort) -> None:
        self._port = port

    def extract_kg_from_message(
        self,
        *,
        message: str,
        query: Optional[str] = None,
        reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._port.extract_kg_from_message(
            message=message,
            query=query,
            reference=reference,
        )

    def get_knowledge_graph(self, *, limit: int = 100, query: Optional[str] = None) -> Dict[str, Any]:
        return self._port.get_knowledge_graph(limit=limit, query=query)

    def run_reasoning(
        self,
        *,
        reasoning_type: str,
        entity_a: str,
        entity_b: Optional[str] = None,
        max_depth: int = 3,
        algorithm: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._port.run_reasoning(
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
        return self._port.search_entities(term=term, entity_type=entity_type, limit=limit)

    def search_relations(
        self,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._port.search_relations(
            source=source,
            target=target,
            relation_type=relation_type,
            limit=limit,
        )

    def create_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._port.create_entity(payload)

    def update_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._port.update_entity(payload)

    def delete_entity(self, entity_id: str) -> Dict[str, Any]:
        return self._port.delete_entity(entity_id)

    def create_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._port.create_relation(payload)

    def update_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._port.update_relation(payload)

    def delete_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._port.delete_relation(payload)

    def get_source_content(self, source_id: str) -> str:
        return self._port.get_source_content(source_id)

    def get_source_file_info(self, source_id: str) -> Dict[str, Any]:
        return self._port.get_source_file_info(source_id)

    def get_source_info_batch(self, source_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        return self._port.get_source_info_batch(source_ids)

    def get_content_batch(self, chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        return self._port.get_content_batch(chunk_ids)

    def get_chunks(self, *, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        return self._port.get_chunks(limit=limit, offset=offset)
