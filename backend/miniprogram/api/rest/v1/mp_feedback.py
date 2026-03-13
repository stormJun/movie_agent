from __future__ import annotations

from fastapi import APIRouter, Depends
from api_common.request_logging import MiniProgramRequestLoggingRoute

from application.chat.feedback_service import FeedbackService
from api_common.dependencies import get_feedback_service
from api_common.schemas import FeedbackRequest, FeedbackResponse


router = APIRouter(route_class=MiniProgramRequestLoggingRoute, prefix="/api/v1/mp", tags=["mp-v1"])


@router.post("/feedback", response_model=FeedbackResponse)
async def mp_feedback(
    request: FeedbackRequest,
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    result = await service.process_feedback(
        message_id=request.message_id,
        query=request.query,
        is_positive=request.is_positive,
        thread_id=request.thread_id,
        request_id=request.request_id,
        agent_type=request.agent_type or "graph_agent",
    )
    return result
