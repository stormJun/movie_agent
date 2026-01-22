from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from server.mem0_service.settings import (
    MEM0_API_KEY,
    MEM0_AUTH_MODE,
    MEM0_JWT_ALGORITHMS,
    MEM0_JWT_SECRET,
    MEM0_TRUST_REQUEST_USER_ID,
    MEM0_USER_ID_HEADER,
)


def _bearer_token(authorization: Optional[str]) -> str:
    raw = (authorization or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw.split(" ", 1)[1].strip()
    return raw


def require_auth(authorization: Optional[str] = Header(default=None)) -> None:
    """Auth gate for mem0 service.

    Modes:
    - api_key (default): accept "Bearer <MEM0_API_KEY>"
    - jwt: accept a JWT in Authorization; signature validated with MEM0_JWT_SECRET (or MEM0_API_KEY fallback)
    """
    if not MEM0_API_KEY and not MEM0_JWT_SECRET:
        return

    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Always accept the shared API key if configured (internal service mode).
    if MEM0_API_KEY and token == MEM0_API_KEY:
        return

    if (MEM0_AUTH_MODE or "").lower() != "jwt":
        raise HTTPException(status_code=401, detail="Unauthorized")

    # JWT mode: validate token signature.
    _decode_jwt(token)


def _decode_jwt(token: str) -> dict:
    try:
        import jwt  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="JWT auth requires PyJWT (pip install pyjwt).",
        ) from exc

    secret = MEM0_JWT_SECRET or MEM0_API_KEY
    if not secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    try:
        return jwt.decode(token, secret, algorithms=list(MEM0_JWT_ALGORITHMS))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def resolve_user_id(
    *,
    authorization: Optional[str],
    header_user_id: Optional[str],
    request_user_id: Optional[str] = None,
) -> str:
    """Resolve effective user_id with defense-in-depth.

    Priority:
    1) If MEM0_TRUST_REQUEST_USER_ID is enabled, accept the user_id from request body.
       This is intended for internal trusted callers (GraphRAG backend).
    2) If a user_id header is provided (MEM0_USER_ID_HEADER), accept it.
       This is intended when an upstream gateway injects an authenticated user id.
    3) If auth mode is JWT, extract user_id from claims ("sub" or "user_id").
    """
    if MEM0_TRUST_REQUEST_USER_ID and request_user_id:
        return str(request_user_id)

    if header_user_id:
        return str(header_user_id)

    if (MEM0_AUTH_MODE or "").lower() == "jwt":
        token = _bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Unauthorized")
        claims = _decode_jwt(token)
        uid = claims.get("sub") or claims.get("user_id")
        if uid:
            return str(uid)
        raise HTTPException(status_code=401, detail="Invalid token: missing user_id")

    # Be explicit: without a trusted body user_id, we require a header.
    raise HTTPException(
        status_code=400,
        detail=(
            "Missing user_id. Provide it in request body (set MEM0_TRUST_REQUEST_USER_ID=true) "
            f"or via header '{MEM0_USER_ID_HEADER}'."
        ),
    )


def read_user_id_header(headers: dict) -> Optional[str]:
    # FastAPI Request.headers is case-insensitive, but this helper can be used in tests.
    name = (MEM0_USER_ID_HEADER or "x-user-id").strip()
    if not name:
        return None
    # Prefer case-insensitive lookup.
    for k, v in headers.items():
        if k.lower() == name.lower() and v:
            return str(v)
    return None
