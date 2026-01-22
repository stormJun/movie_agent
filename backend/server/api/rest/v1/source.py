from __future__ import annotations

from fastapi import APIRouter, Depends

from application.knowledge_graph import KnowledgeGraphService
from server.api.rest.dependencies import get_knowledge_graph_service
from server.models.schemas import (
    ContentBatchRequest,
    SourceInfoBatchRequest,
    SourceInfoResponse,
    SourceRequest,
    SourceResponse,
)


router = APIRouter(prefix="/api/v1", tags=["source-v1"])


@router.post("/source", response_model=SourceResponse)
async def source_content(
    request: SourceRequest,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> SourceResponse:
    return {"content": service.get_source_content(request.source_id)}


@router.post("/source_info", response_model=SourceInfoResponse)
async def source_info(
    request: SourceRequest,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> SourceInfoResponse:
    return service.get_source_file_info(request.source_id)


@router.post("/source_info_batch")
async def source_info_batch(
    request: SourceInfoBatchRequest,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.get_source_info_batch(request.source_ids)


@router.post("/content_batch")
async def content_batch(
    request: ContentBatchRequest,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.get_content_batch(request.chunk_ids)


@router.get("/chunks")
async def chunks(
    limit: int = 10,
    offset: int = 0,
    service: KnowledgeGraphService = Depends(get_knowledge_graph_service),
) -> dict:
    return service.get_chunks(limit=limit, offset=offset)
