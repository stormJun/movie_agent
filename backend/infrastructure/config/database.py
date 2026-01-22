from __future__ import annotations

import os
from typing import Optional


def _get_env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {key} 需要整数值，但当前为 {raw}") from exc


def get_postgres_dsn() -> Optional[str]:
    """Return Postgres DSN if configured; otherwise None.

    Priority:
    1) POSTGRES_DSN
    2) POSTGRES_HOST/PORT/USER/PASSWORD/DB
    """

    dsn = (os.getenv("POSTGRES_DSN") or "").strip()
    if dsn:
        return dsn

    host = (os.getenv("POSTGRES_HOST") or "").strip()
    if not host:
        return None

    port = _get_env_int("POSTGRES_PORT", 5432)
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "graphrag_chat")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"
