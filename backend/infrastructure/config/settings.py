import os
import warnings
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from graphrag_agent.config import settings as core_settings
from infrastructure.config.graphrag_settings import apply_core_settings_overrides

# 统一加载环境变量，确保配置来源一致。
# 注意：本项目以项目根目录的 .env 为主要开发配置来源，优先级应高于外部 shell 环境变量，
# 否则容易出现“明明改了 .env 但运行仍读到旧值”的情况。
load_dotenv(override=True)

# 应用基础设施侧的配置注入，确保 core settings 获取运行时值。
apply_core_settings_overrides()


def _get_env_int(key: str, default: Optional[int]) -> Optional[int]:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {key} 需要整数值，但当前为 {raw}") from exc


def _get_env_float(key: str, default: Optional[float]) -> Optional[float]:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {key} 需要浮点值，但当前为 {raw}") from exc


def _get_env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


# ===== 基础路径设置（基础设施层需要）=====
#
# NOTE:
# - In monorepo layout, all backend code lives under `<repo>/backend/`.
# - Runtime artifacts should live under `<repo>/files/` (or a dedicated runtime
#   directory), NOT under `<repo>/backend/`.

INFRASTRUCTURE_DIR = Path(__file__).resolve().parent.parent  # backend/infrastructure/
_BACKEND_DIR = INFRASTRUCTURE_DIR.parent  # backend/

# Prefer repo root when the monorepo layout is detected; otherwise fall back to cwd
# (useful for installed runtime packages / container deployments).
if _BACKEND_DIR.name == "backend":
    PROJECT_ROOT = _BACKEND_DIR.parent
else:
    PROJECT_ROOT = Path.cwd()


# ===== 路径与运行时目录配置 =====

RUNTIME_ROOT = Path(os.getenv("RUNTIME_ROOT", PROJECT_ROOT / "files")).expanduser()
TIKTOKEN_CACHE_DIR = Path(
    os.getenv("TIKTOKEN_CACHE_DIR", RUNTIME_ROOT / "tiktoken")
).expanduser()
os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(TIKTOKEN_CACHE_DIR))

SIMILARITY_THRESHOLD = core_settings.SIMILARITY_THRESHOLD


# ===== Neo4j 连接配置（基础设施层需要）=====

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_MAX_POOL_SIZE = _get_env_int("NEO4J_MAX_POOL_SIZE", 10) or 10
NEO4J_REFRESH_SCHEMA = _get_env_bool("NEO4J_REFRESH_SCHEMA", False)

NEO4J_CONFIG = {
    "uri": NEO4J_URI,
    "username": NEO4J_USERNAME,
    "password": NEO4J_PASSWORD,
    "max_pool_size": NEO4J_MAX_POOL_SIZE,
    "refresh_schema": NEO4J_REFRESH_SCHEMA,
}

# ===== KB 路由（movie/edu 自动识别；基础设施层需要）=====

KB_AUTO_ROUTE = _get_env_bool("KB_AUTO_ROUTE", True)
KB_AUTO_ROUTE_OVERRIDE = _get_env_bool("KB_AUTO_ROUTE_OVERRIDE", True)
KB_AUTO_ROUTE_MIN_CONFIDENCE = _get_env_float("KB_AUTO_ROUTE_MIN_CONFIDENCE", 0.75) or 0.75


# ===== LLM 与嵌入模型配置（基础设施层需要）=====

# 模型类型选择：openai 或 gemini
MODEL_TYPE = os.getenv("MODEL_TYPE", "openai").strip().lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_EMBEDDINGS_MODEL = os.getenv("OPENAI_EMBEDDINGS_MODEL") or None
OPENAI_LLM_MODEL = os.getenv("OPENAI_LLM_MODEL") or None
LLM_TEMPERATURE = _get_env_float("TEMPERATURE", None)
LLM_MAX_TOKENS = _get_env_int("MAX_TOKENS", None)

OPENAI_EMBEDDING_CONFIG = {
    "model": OPENAI_EMBEDDINGS_MODEL,
    "api_key": OPENAI_API_KEY,
    "base_url": OPENAI_BASE_URL,
    "check_embedding_ctx_length": False,  # DashScope 不支持 token id 数组，必须关闭
}

OPENAI_LLM_CONFIG = {
    "model": OPENAI_LLM_MODEL,
    "temperature": LLM_TEMPERATURE,
    "max_tokens": LLM_MAX_TOKENS,
    "api_key": OPENAI_API_KEY,
    "base_url": OPENAI_BASE_URL,
}

# RAG 生成超时（秒），避免回答生成长时间阻塞
RAG_ANSWER_TIMEOUT_S = _get_env_float("RAG_ANSWER_TIMEOUT_S", 180.0) or 180.0

# RAG synthesize 兜底配置
_DEFAULT_SYNTHESIZE_MAX_CHARS = 1500
_DEFAULT_SYNTHESIZE_MAX_EVIDENCE = 3
_DEFAULT_SYNTHESIZE_STRATEGY = "score"

_raw_max_chars = _get_env_int("RAG_SYNTHESIZE_MAX_CHARS", _DEFAULT_SYNTHESIZE_MAX_CHARS)
if _raw_max_chars is None or _raw_max_chars <= 0:
    warnings.warn(
        "RAG_SYNTHESIZE_MAX_CHARS must be a positive integer; using default.",
        RuntimeWarning,
        stacklevel=2,
    )
    _raw_max_chars = _DEFAULT_SYNTHESIZE_MAX_CHARS
RAG_SYNTHESIZE_MAX_CHARS = _raw_max_chars

_raw_max_evidence = _get_env_int(
    "RAG_SYNTHESIZE_MAX_EVIDENCE", _DEFAULT_SYNTHESIZE_MAX_EVIDENCE
)
if _raw_max_evidence is None or _raw_max_evidence <= 0:
    warnings.warn(
        "RAG_SYNTHESIZE_MAX_EVIDENCE must be a positive integer; using default.",
        RuntimeWarning,
        stacklevel=2,
    )
    _raw_max_evidence = _DEFAULT_SYNTHESIZE_MAX_EVIDENCE
RAG_SYNTHESIZE_MAX_EVIDENCE = _raw_max_evidence

_raw_strategy = os.getenv("RAG_SYNTHESIZE_EVIDENCE_STRATEGY", _DEFAULT_SYNTHESIZE_STRATEGY)
_raw_strategy = _raw_strategy.strip().lower()
if _raw_strategy not in {"score", "confidence", "first"}:
    warnings.warn(
        "RAG_SYNTHESIZE_EVIDENCE_STRATEGY must be one of score/confidence/first; "
        "using default.",
        RuntimeWarning,
        stacklevel=2,
    )
    _raw_strategy = _DEFAULT_SYNTHESIZE_STRATEGY
RAG_SYNTHESIZE_EVIDENCE_STRATEGY = _raw_strategy


# ===== mem0 long-term memory (infrastructure) =====
#
# NOTE: This module is infrastructure-side config and may read env directly.
# Service-side feature switches live under `backend/config/settings.py`.

# Memory provider selection: mem0, postgres, or null
MEMORY_PROVIDER = os.getenv("MEMORY_PROVIDER", "mem0").strip().lower()

# Mem0 connection settings
MEM0_BASE_URL = os.getenv("MEM0_BASE_URL", "").strip()
MEM0_API_KEY = os.getenv("MEM0_API_KEY", "").strip()
MEM0_TIMEOUT_S = _get_env_float("MEM0_TIMEOUT_S", 10.0) or 10.0

# Allow overriding API paths to match different mem0 deployments.
MEM0_SEARCH_PATH = os.getenv("MEM0_SEARCH_PATH", "/v1/memories/search").strip() or "/v1/memories/search"
MEM0_ADD_PATH = os.getenv("MEM0_ADD_PATH", "/v1/memories").strip() or "/v1/memories"
MEM0_DELETE_PATH = os.getenv("MEM0_DELETE_PATH", "/v1/memories/{memory_id}").strip() or "/v1/memories/{memory_id}"
MEM0_LIST_PATH = os.getenv("MEM0_LIST_PATH", "/v1/memories").strip() or "/v1/memories"
# When talking to the bundled `server.mem0_service`, list/delete require a user id
# via this header (see mem0 service settings); external providers may ignore it.
MEM0_USER_ID_HEADER = os.getenv("MEM0_USER_ID_HEADER", "x-user-id").strip() or "x-user-id"


# ===== Gemini 配置（支持 API Key 和 OAuth 两种认证方式）=====

# Gemini 认证类型：api_key 或 oauth
GEMINI_AUTH_TYPE = os.getenv("GEMINI_AUTH_TYPE", "api_key").strip().lower()

# API Key 模式配置
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# OAuth 模式配置（Google 账号认证）
GEMINI_PROJECT_ID = os.getenv("GEMINI_PROJECT_ID", "").strip()
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "us-central1").strip()

# Gemini 模型配置
GEMINI_LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-2.0-flash-exp").strip()
GEMINI_EMBEDDINGS_MODEL = os.getenv("GEMINI_EMBEDDINGS_MODEL", "text-embedding-004").strip()
GEMINI_TEMPERATURE = _get_env_float("GEMINI_TEMPERATURE", None)
GEMINI_MAX_TOKENS = _get_env_int("GEMINI_MAX_TOKENS", None)


# ===== Query-Time Enrichment 配置 =====

# Enrichment 功能总开关
ENRICHMENT_ENABLE = _get_env_bool("ENRICHMENT_ENABLE", True)

# TMDB API 配置
TMDB_BASE_URL = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3").strip()
TMDB_API_TOKEN = os.getenv("TMDB_API_TOKEN", "").strip()
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()
TMDB_TIMEOUT_S = _get_env_float("TMDB_TIMEOUT_S", 5.0) or 5.0

# Enrichment 缓存配置（Phase 2 实现）
ENRICHMENT_CACHE_TTL_S = _get_env_int("ENRICHMENT_CACHE_TTL_S", 3600) or 3600  # 1小时

# Enrichment 重试配置
ENRICHMENT_MAX_RETRIES = _get_env_int("ENRICHMENT_MAX_RETRIES", 2) or 2

# 异步持久化配置（Phase 3 实现）
ENRICHMENT_ASYNC_WRITE_ENABLE = _get_env_bool("ENRICHMENT_ASYNC_WRITE_ENABLE", True)
ENRICHMENT_WRITE_QUEUE_SIZE = _get_env_int("ENRICHMENT_WRITE_QUEUE_SIZE", 100) or 100


# ===== Debug / Observability (infrastructure) =====
#
# Large debug payloads can overwhelm memory and the frontend. Store previews.
DEBUG_COMBINED_CONTEXT_MAX_CHARS = _get_env_int("DEBUG_COMBINED_CONTEXT_MAX_CHARS", 20000) or 20000
