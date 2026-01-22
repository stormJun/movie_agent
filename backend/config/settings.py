import os

from dotenv import load_dotenv

# Service-side settings: focus on HTTP/runtime switches.
# Infrastructure env/path settings live under `backend/infrastructure/config/`.
load_dotenv(override=True)


def _get_env_int(key: str, default: int) -> int:
    """读取整型环境变量，未设置时返回默认值"""
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {key} 需要整数值，但实际为 {raw}") from exc


def _get_env_bool(key: str, default: bool) -> bool:
    """读取布尔型环境变量，支持 true/false/1/0 等表达"""
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    return raw.lower() in {"1", "true", "y", "yes", "on"}


def _get_env_float(key: str, default: float) -> float:
    """读取浮点型环境变量，未设置时返回默认值"""
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {key} 需要浮点数值，但实际为 {raw}") from exc


# ===== FastAPI / Uvicorn 运行参数 =====

SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")  # 服务监听地址
SERVER_PORT = _get_env_int("SERVER_PORT", 8000)  # 服务端口
SERVER_RELOAD = _get_env_bool("SERVER_RELOAD", False)  # 热重载开关
SERVER_LOG_LEVEL = os.getenv("SERVER_LOG_LEVEL", "info")  # 日志等级

# Worker 数量优先使用 SERVER_WORKERS，否则回落到核心配置
DEFAULT_SERVER_WORKERS = _get_env_int("FASTAPI_WORKERS", 2) or 2
SERVER_WORKERS = _get_env_int("SERVER_WORKERS", DEFAULT_SERVER_WORKERS) or DEFAULT_SERVER_WORKERS

# 统一封装 uvicorn.run 可用参数
UVICORN_CONFIG = {
    "host": SERVER_HOST,
    "port": SERVER_PORT,
    "reload": SERVER_RELOAD,
    "log_level": SERVER_LOG_LEVEL,
    "workers": SERVER_WORKERS,
}

# ===== SSE 运行参数 =====

# SSE keepalive (comment frames) interval. Helps proxies/gateways keep the
# connection open during long retrieval steps.
SSE_HEARTBEAT_S = _get_env_float("SSE_HEARTBEAT_S", 15.0)

# ===== Phase 2（handlers + infrastructure/rag）=====

PHASE2_ENABLE_BUSINESS_AGENTS = _get_env_bool("PHASE2_ENABLE_BUSINESS_AGENTS", True)
PHASE2_ENABLE_KB_HANDLERS = _get_env_bool(
    "PHASE2_ENABLE_KB_HANDLERS",
    PHASE2_ENABLE_BUSINESS_AGENTS,
)

# ===== Long-term Memory (mem0) =====
#
# Service-side switches only. Infrastructure connection details (MEM0_BASE_URL, etc.)
# live under `backend/infrastructure/config/` so infra does not depend on `config.*`.

MEMORY_ENABLE = _get_env_bool("MEMORY_ENABLE", False)
MEMORY_WRITE_ENABLE = _get_env_bool("MEMORY_WRITE_ENABLE", False)
MEMORY_TOP_K = _get_env_int("MEMORY_TOP_K", 5) or 5
MEMORY_MIN_SCORE = _get_env_float("MEMORY_MIN_SCORE", 0.6) or 0.6
MEMORY_MAX_CHARS = _get_env_int("MEMORY_MAX_CHARS", 1200) or 1200

# Only write when we can extract stable user info (preferences/facts/constraints).
MEMORY_WRITE_MODE = os.getenv("MEMORY_WRITE_MODE", "rules").strip() or "rules"
