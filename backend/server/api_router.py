from __future__ import annotations

from fastapi import APIRouter

from admin.api_router import api_router as admin_api_router
from miniprogram.api_router import api_router as miniprogram_api_router

# Compatibility aggregator: keep server.main import path stable while splitting
# route modules by business surface (admin vs miniprogram).
api_router = APIRouter()
api_router.include_router(admin_api_router)
api_router.include_router(miniprogram_api_router)

__all__ = ["api_router"]
