from __future__ import annotations

import os


def _get_env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    return int(raw)


def _get_env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "y", "yes", "on"}


MEM0_SERVICE_HOST = os.getenv("MEM0_SERVICE_HOST", "0.0.0.0").strip() or "0.0.0.0"
MEM0_SERVICE_PORT = _get_env_int("MEM0_SERVICE_PORT", 8830) or 8830

# If MEM0_API_KEY is set, require "Authorization: Bearer <MEM0_API_KEY>".
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "").strip()

# Auth mode:
# - "api_key": require MEM0_API_KEY (default; suitable for internal/trusted callers)
# - "jwt": accept JWT tokens in Authorization (validated with MEM0_JWT_SECRET or MEM0_API_KEY fallback)
MEM0_AUTH_MODE = os.getenv("MEM0_AUTH_MODE", "api_key").strip().lower() or "api_key"
MEM0_JWT_SECRET = os.getenv("MEM0_JWT_SECRET", "").strip()
_algs = os.getenv("MEM0_JWT_ALGORITHMS", "HS256").strip()
MEM0_JWT_ALGORITHMS = tuple(a.strip() for a in _algs.split(",") if a.strip()) or ("HS256",)

# How to resolve user_id for "management" endpoints (delete/update/list/forget):
# - For internal services, you may trust user_id in request payloads.
# - For production, prefer extracting from JWT claims or an upstream-injected header.
MEM0_TRUST_REQUEST_USER_ID = _get_env_bool("MEM0_TRUST_REQUEST_USER_ID", True)
MEM0_USER_ID_HEADER = os.getenv("MEM0_USER_ID_HEADER", "x-user-id").strip() or "x-user-id"

# Metadata storage (PostgreSQL).
MEM0_PG_DSN = os.getenv(
    "MEM0_PG_DSN",
    "postgresql://postgres:postgres@postgres:5432/graphrag_chat",
).strip()

# Vector backend: "milvus" (recommended) or "none" (store only; search returns empty).
MEM0_VECTOR_BACKEND = os.getenv("MEM0_VECTOR_BACKEND", "milvus").strip().lower() or "milvus"

# Milvus connection (when MEM0_VECTOR_BACKEND=milvus). For Docker Desktop on macOS,
# "host.docker.internal" reaches services exposed on the host network.
MEM0_MILVUS_HOST = os.getenv("MEM0_MILVUS_HOST", "host.docker.internal").strip() or "host.docker.internal"
MEM0_MILVUS_PORT = _get_env_int("MEM0_MILVUS_PORT", 19530) or 19530
MEM0_MILVUS_COLLECTION = os.getenv("MEM0_MILVUS_COLLECTION", "mem0_memories").strip() or "mem0_memories"

# If set, will be used to pre-create Milvus collection with fixed dimension.
# If unset, the service will create the collection lazily on first embed() call.
_dim_raw = os.getenv("MEM0_EMBEDDING_DIM", "").strip()
MEM0_EMBEDDING_DIM = int(_dim_raw) if _dim_raw.isdigit() else None

# Safety knobs.
MEM0_MAX_TEXT_CHARS = _get_env_int("MEM0_MAX_TEXT_CHARS", 4000) or 4000
MEM0_DEFAULT_LIMIT = _get_env_int("MEM0_DEFAULT_LIMIT", 5) or 5
MEM0_MAX_LIMIT = _get_env_int("MEM0_MAX_LIMIT", 50) or 50

# Best-effort: if embedding generation fails, we still store in Postgres but
# skip vector indexing.
MEM0_STRICT_EMBEDDINGS = _get_env_bool("MEM0_STRICT_EMBEDDINGS", False)

# Optional lifecycle controls.
MEM0_ENABLE_TTL = _get_env_bool("MEM0_ENABLE_TTL", False)
MEM0_DEFAULT_TTL_DAYS = _get_env_int("MEM0_DEFAULT_TTL_DAYS", 90) or 90
