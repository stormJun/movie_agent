from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from infrastructure.debug.debug_cache import debug_cache

router = APIRouter(prefix="/api/v1", tags=["debug-v1"])


@router.get("/debug/{request_id}")
async def get_debug_data(
    request_id: str,
    user_id: str = Query(..., description="Internal-only: pass user_id explicitly"),
    session_id: str | None = Query(None, description="Optional: verify session ownership"),
) -> dict:
    payload = debug_cache.get(request_id)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"Debug data for request_id '{request_id}' not found or expired",
        )
    if isinstance(payload, dict):
        if payload.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied: different user")
        if session_id and payload.get("session_id") != session_id:
            raise HTTPException(status_code=403, detail="Access denied: different session")
        return payload

    if payload.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: different user")
    if session_id and payload.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied: different session")
    return payload.to_dict()


@router.delete("/debug/{request_id}")
async def clear_debug_data(
    request_id: str,
    user_id: str = Query(..., description="Internal-only: pass user_id explicitly"),
) -> dict:
    payload = debug_cache.get(request_id)
    if payload is not None:
        owner = payload.get("user_id") if isinstance(payload, dict) else payload.user_id
        if owner != user_id:
            raise HTTPException(status_code=403, detail="Access denied: different user")
    deleted = debug_cache.delete(request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found")
    return {"status": "cleared", "request_id": request_id}


@router.post("/debug/cleanup")
async def cleanup_expired_debug_data() -> dict:
    expired_count = debug_cache.cleanup_expired()
    return {"status": "cleaned", "expired_count": expired_count}
