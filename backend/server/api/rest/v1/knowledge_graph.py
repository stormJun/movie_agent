from __future__ import annotations

from fastapi import APIRouter, Depends

from application.knowledge_graph import KnowledgeGraphService
from server.api.rest.dependencies import get_knowledge_graph_service
from config.rag import entity_types as default_entity_types
from config.rag import relationship_types as default_relation_types
from server.models.schemas import (
    EntityData,
    EntityDeleteData,
    EntitySearchFilter,
    EntityUpdateData,
    ReasoningRequest,
    RelationData,
    RelationDeleteData,
    RelationSearchFilter,
    RelationUpdateData,
)


router = APIRouter(prefix="/api/v1", tags=["knowledge-graph-v1"])


@router.get("/knowledge_graph")
async def knowledge_graph(
    limit: int = 100,
    query: str | None = None,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.get_knowledge_graph(limit=limit, query=query)


@router.get("/knowledge_graph_from_message")
async def knowledge_graph_from_message(
    message: str,
    query: str | None = None,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.extract_kg_from_message(message=message, query=query)


@router.post("/kg_reasoning")
async def kg_reasoning(
    request: ReasoningRequest,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.run_reasoning(
        reasoning_type=request.reasoning_type,
        entity_a=request.entity_a,
        entity_b=request.entity_b,
        max_depth=request.max_depth or 3,
        algorithm=request.algorithm,
    )


@router.get("/entity_types")
async def entity_types() -> dict:
    return {"entity_types": list(default_entity_types)}


@router.get("/relation_types")
async def relation_types() -> dict:
    return {"relation_types": list(default_relation_types)}


@router.post("/entities/search")
async def entities_search(
    request: EntitySearchFilter,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    results = service.search_entities(
        term=request.term,
        entity_type=request.type,
        limit=request.limit or 100,
    )
    return {"entities": results}


@router.post("/relations/search")
async def relations_search(
    request: RelationSearchFilter,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    results = service.search_relations(
        source=request.source,
        target=request.target,
        relation_type=request.type,
        limit=request.limit or 100,
    )
    return {"relations": results}


@router.post("/entity/create")
async def entity_create(
    request: EntityData,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.create_entity(request.model_dump())


@router.post("/entity/update")
async def entity_update(
    request: EntityUpdateData,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.update_entity(request.model_dump())


@router.post("/entity/delete")
async def entity_delete(
    request: EntityDeleteData,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.delete_entity(request.id)


@router.post("/relation/create")
async def relation_create(
    request: RelationData,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.create_relation(request.model_dump())


@router.post("/relation/update")
async def relation_update(
    request: RelationUpdateData,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.update_relation(request.model_dump())


@router.post("/relation/delete")
async def relation_delete(
    request: RelationDeleteData,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.delete_relation(request.model_dump())
