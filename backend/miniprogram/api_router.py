from __future__ import annotations

from fastapi import APIRouter

import miniprogram.api.rest.v1.mp_chat_stream as mp_chat_stream_v1
import miniprogram.api.rest.v1.mp_feedback as mp_feedback_v1
import miniprogram.api.rest.v1.mp_movies as mp_movies_v1

api_router = APIRouter()
api_router.include_router(mp_chat_stream_v1.router)
api_router.include_router(mp_feedback_v1.router)
api_router.include_router(mp_movies_v1.router)

__all__ = ["api_router"]
