from infrastructure.providers.neo4jdb import (
    get_db_manager as original_get_db_manager,
    has_db_manager as original_has_db_manager,
)

import os
from typing import Optional

class DatabaseManager:
    """Neo4j 数据库管理类"""
    def __init__(self):
        self.driver = None

    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()


def get_db_manager():
    return original_get_db_manager()


def has_db_manager() -> bool:
    return original_has_db_manager()


def _get_env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {key} 需要整数值，但当前为 {raw}") from exc


def get_postgres_dsn() -> Optional[str]:
    """Service-side accessor for Postgres DSN (chat history persistence).

    Notes:
    - This function intentionally lives under `config.*` so server/application
      layers can consume it without importing `infrastructure.config.*`.
    - `.env` loading is centralized in config entrypoints (settings.py), so we
      only read environment variables here.
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
