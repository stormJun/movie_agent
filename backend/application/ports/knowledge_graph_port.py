from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class KnowledgeGraphPort(Protocol):
    def extract_kg_from_message(
        self,
        *,
        message: str,
        query: Optional[str] = None,
        reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ...

    def get_knowledge_graph(self, *, limit: int = 100, query: Optional[str] = None) -> Dict[str, Any]:
        ...

    def run_reasoning(
        self,
        *,
        reasoning_type: str,
        entity_a: str,
        entity_b: Optional[str] = None,
        max_depth: int = 3,
        algorithm: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...

    def search_entities(
        self,
        *,
        term: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        ...

    def search_relations(
        self,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        ...

    def create_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def update_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def delete_entity(self, entity_id: str) -> Dict[str, Any]:
        ...

    def create_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def update_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def delete_relation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def get_source_content(self, source_id: str) -> str:
        ...

    def get_source_file_info(self, source_id: str) -> Dict[str, Any]:
        ...

    def get_source_info_batch(self, source_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        ...

    def get_content_batch(self, chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        ...

    def get_chunks(self, *, limit: int = 10, offset: int = 0, kb_prefix: str | None = None) -> Dict[str, Any]:
        ...
