from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping


def kb_label_for_kb_prefix(kb_prefix: str) -> str:
    """
    将知识库前缀（如 movie/edu 或 movie:/edu:）转换为 Neo4j label（如 KB_movie/KB_edu）。

    - 为空返回空字符串
    - 仅做“受控、可预测”的字符清洗，避免 label 注入
    """
    raw = (kb_prefix or "").strip()
    if not raw:
        return ""
    raw = raw[:-1] if raw.endswith(":") else raw
    if not raw:
        return ""

    slug = re.sub(r"[^0-9A-Za-z_]", "_", raw).strip("_")
    if not slug:
        return ""
    if slug[0].isdigit():
        slug = f"kb_{slug}"
    return f"KB_{slug}"


def kb_scoped_label_for_kb_prefix(kb_prefix: str, scope: str) -> str:
    """
    为不同节点类型生成“作用域 KB label”，用于避免 VECTOR index 冲突：
    - 实体：KB_<slug>_entity
    - Chunk：KB_<slug>_chunk
    - Document：KB_<slug>_document
    """
    base = kb_label_for_kb_prefix(kb_prefix)
    if not base:
        return ""
    slug = base[len("KB_") :]

    scope_raw = (scope or "").strip()
    if not scope_raw:
        return base
    scope_slug = re.sub(r"[^0-9A-Za-z_]", "_", scope_raw).strip("_").lower()
    if not scope_slug:
        return base
    if scope_slug[0].isdigit():
        scope_slug = f"scope_{scope_slug}"
    return f"KB_{slug}_{scope_slug}"


# ===== 基础路径设置（默认值，运行时由基础设施层注入） =====

BASE_DIR: Path | None = None  # graphrag_agent 包目录
PROJECT_ROOT: Path | None = None  # 项目根目录
FILES_DIR = Path("files")
FILE_REGISTRY_PATH = Path("file_registry.json")

# ===== 知识库与系统参数（默认值，运行时由基础设施层注入） =====

KB_NAME = "默认知识库"

theme = "通用知识图谱"
entity_types: list[str] = []
relationship_types: list[str] = []

# Conflict strategy: manual_first / auto_first / merge
conflict_strategy = "manual_first"

# Community algorithm: leiden / sllpa
community_algorithm = "leiden"

# ===== Answer / prompt semantics =====

response_type = "多个段落"

lc_description = "用于需要具体细节的查询。"
gl_description = "用于需要总结归纳的查询。"
naive_description = "基础检索工具，直接查找与问题最相关的文本片段。"

examples: list[str] = []

# ===== 文本处理配置 =====

CHUNK_SIZE = 500  # 文本分块大小
OVERLAP = 100  # 分块重叠长度
MAX_TEXT_LENGTH = 500000  # 最大文本长度
# 文本分块器：hanlp（更好，但依赖较重）/ simple（纯 Python，稳定）
TEXT_CHUNKER_PROVIDER = "simple"
DOCUMENT_FILE_EXTENSIONS = [".txt", ".pdf", ".md", ".doc", ".docx"]
DOCUMENT_RECURSIVE = True

# ===== 性能优化配置 =====

MAX_WORKERS = 4  # 并行工作线程数
BATCH_SIZE = 100  # 批处理大小
ENTITY_BATCH_SIZE = 50  # 实体批次大小
CHUNK_BATCH_SIZE = 100  # 文本块批次
EMBEDDING_BATCH_SIZE = 64  # 向量批次
LLM_BATCH_SIZE = 5  # LLM 批次
COMMUNITY_BATCH_SIZE = 50  # 社区批次大小

# ===== 社区摘要（Global Search 输入）=====
# 默认仅摘要 Top 200 社区（避免成本/耗时）；设置为 0 可全量摘要（level=0）
COMMUNITY_SUMMARY_LIMIT = 200

# 仅为缺失 summary/full_content 的社区补跑摘要（便于断点续跑）
COMMUNITY_SUMMARY_ONLY_MISSING = True

# 摘要生成并发（默认沿用 MAX_WORKERS；建议根据供应商限流调小）
COMMUNITY_SUMMARY_MAX_WORKERS = MAX_WORKERS

# 分批收集社区信息时的最大批次数；0 表示不限制
COMMUNITY_SUMMARY_MAX_BATCHES = 20

# 每个社区用于摘要的最大节点/关系数（控制 prompt 长度与成本）；0 表示不限制（不建议）
COMMUNITY_SUMMARY_MAX_NODES = 50
COMMUNITY_SUMMARY_MAX_RELS = 100

# ===== GDS 相关配置 =====

GDS_MEMORY_LIMIT = 6  # GDS 内存限制(GB)
GDS_CONCURRENCY = 4  # GDS 并发度
GDS_NODE_COUNT_LIMIT = 50000  # 节点上限
GDS_TIMEOUT_SECONDS = 300  # 超时时长

# 向量相似度阈值（用于实体相似检测等算法）
SIMILARITY_THRESHOLD = 0.9

# ===== 实体消歧与对齐配置 =====

DISAMBIG_STRING_THRESHOLD = 0.7
DISAMBIG_VECTOR_THRESHOLD = 0.85
DISAMBIG_NIL_THRESHOLD = 0.6
DISAMBIG_TOP_K = 5

ALIGNMENT_CONFLICT_THRESHOLD = 0.5
ALIGNMENT_MIN_GROUP_SIZE = 2

# ===== 相似实体检测参数 =====

SIMILAR_ENTITY_SETTINGS = {
    "word_edit_distance": 3,
    "batch_size": 500,
    "memory_limit": GDS_MEMORY_LIMIT,
    "top_k": 10,
}

# ===== 搜索工具配置 =====

BASE_SEARCH_CONFIG = {
    "vector_limit": 5,
    "text_limit": 5,
    "semantic_top_k": 5,
    "relevance_top_k": 5,
}

LOCAL_SEARCH_SETTINGS = {
    "top_chunks": 3,
    "top_communities": 3,
    "top_outside_relationships": 10,
    "top_inside_relationships": 10,
    "top_entities": 10,
    "index_name": "vector",
}

# ===== 构建模式（统一框架改造） =====

# document: 现有“文档 → chunk → LLM抽取 → __Entity__”流程
# structured: 结构化数据（电影）导入 + Canonical 层生成
GRAPH_BUILD_MODE = "document"

# 文档模式的知识库命名空间前缀（用于同库多知识库共存，比如 "edu"）
# - 为空时：沿用历史行为（不加前缀）
# - 非空时：写入到 Neo4j 的 __Document__/__Chunk__/__Entity__/__Community__ 将使用 "<prefix>:" 命名空间
DOCUMENT_KB_PREFIX = ""

# 结构化数据目录（电影预处理产物所在目录）
# 允许指向 files/ 或 files/movie_data/；具体探测逻辑由 structured builder 处理
STRUCTURED_DATA_DIR = FILES_DIR / "movie_data"

# 向量索引名称（实体/Chunk 分开，避免 Neo4j index name 冲突）
# 默认值会随“运行模式/KB 前缀”自适应：
# - structured + STRUCTURED_KB_PREFIX=movie -> movie_vector / movie_chunk_vector
# - document + DOCUMENT_KB_PREFIX=edu -> edu_vector / edu_chunk_vector
_structured_kb_prefix_for_index = "movie"
_kb_slug_for_index = (
    _structured_kb_prefix_for_index
    if GRAPH_BUILD_MODE == "structured"
    else (DOCUMENT_KB_PREFIX if DOCUMENT_KB_PREFIX else "")
)
_default_entity_vector_index_name = (
    f"{_kb_slug_for_index}_vector" if _kb_slug_for_index else "vector"
)
_default_chunk_vector_index_name = (
    f"{_kb_slug_for_index}_chunk_vector" if _kb_slug_for_index else "chunk_vector"
)

ENTITY_VECTOR_INDEX_NAME = _default_entity_vector_index_name
CHUNK_VECTOR_INDEX_NAME = _default_chunk_vector_index_name

# 保证 LocalSearch 与实体索引使用同一 index name（避免“索引创建/检索口径不一致”）
LOCAL_SEARCH_SETTINGS["index_name"] = ENTITY_VECTOR_INDEX_NAME

GLOBAL_SEARCH_SETTINGS = {
    "default_level": 0,
    "community_batch_size": 5,
}

NAIVE_SEARCH_TOP_K = 3

HYBRID_SEARCH_SETTINGS = {
    "entity_limit": 15,
    "max_hop_distance": 2,
    "top_communities": 3,
    "batch_size": 10,
    "community_level": 0,
}

# ===== 图构建 / Phase 3（索引与社区）运行控制 =====

# 仅处理特定知识库前缀（用于共库隔离，比如 "movie:")
_structured_kb_prefix = "movie"
_default_structured_entity_prefix = (
    f"{_structured_kb_prefix}:" if GRAPH_BUILD_MODE == "structured" else ""
)
_default_document_entity_prefix = (
    f"{DOCUMENT_KB_PREFIX}:" if GRAPH_BUILD_MODE == "document" and DOCUMENT_KB_PREFIX else ""
)
_default_entity_prefix = _default_structured_entity_prefix or _default_document_entity_prefix
GRAPH_ENTITY_ID_PREFIX_FILTER = _default_entity_prefix
GRAPH_CHUNK_ID_PREFIX_FILTER = GRAPH_ENTITY_ID_PREFIX_FILTER

# 社区节点的命名空间前缀（避免与其他知识库共库时 __Community__.id 冲突）
GRAPH_COMMUNITY_ID_PREFIX = GRAPH_ENTITY_ID_PREFIX_FILTER

# 共库隔离：Neo4j 的 VECTOR index 不能在同一 (label, property) 上创建多份索引。
# 由于 __Entity__ / __Chunk__ 都使用 embedding 属性，这里需要“分作用域 label”来隔离索引。
GRAPH_ENTITY_KB_LABEL = (
    kb_scoped_label_for_kb_prefix(GRAPH_ENTITY_ID_PREFIX_FILTER, "entity")
    if GRAPH_ENTITY_ID_PREFIX_FILTER
    else ""
)
GRAPH_CHUNK_KB_LABEL = (
    kb_scoped_label_for_kb_prefix(GRAPH_CHUNK_ID_PREFIX_FILTER, "chunk")
    if GRAPH_CHUNK_ID_PREFIX_FILTER
    else ""
)
GRAPH_DOCUMENT_KB_LABEL = (
    kb_scoped_label_for_kb_prefix(GRAPH_ENTITY_ID_PREFIX_FILTER, "document")
    if GRAPH_ENTITY_ID_PREFIX_FILTER
    else ""
)
GRAPH_COMMUNITY_KB_LABEL = (
    kb_scoped_label_for_kb_prefix(GRAPH_COMMUNITY_ID_PREFIX, "community")
    if GRAPH_COMMUNITY_ID_PREFIX
    else ""
)

# Phase 3 可选跳过项（用于结构化模式快速验证/降级）
_structured_default_skip = GRAPH_BUILD_MODE == "structured"
GRAPH_SKIP_SIMILAR_ENTITY = _structured_default_skip
GRAPH_SKIP_ENTITY_MERGE = _structured_default_skip
GRAPH_SKIP_ENTITY_QUALITY = _structured_default_skip
GRAPH_SKIP_COMMUNITY = False
GRAPH_SKIP_COMMUNITY_SUMMARY = _structured_default_skip

# ===== Agent 配置 =====

AGENT_SETTINGS = {
    "default_recursion_limit": 5,
    "chunk_size": 4,
    "stream_flush_threshold": 40,
    "deep_stream_flush_threshold": 80,
    "fusion_stream_flush_threshold": 60,
}

# ===== 多智能体（Plan-Execute-Report）配置 =====

MULTI_AGENT_PLANNER_MAX_TASKS = 6
MULTI_AGENT_ALLOW_UNCLARIFIED_PLAN = True
MULTI_AGENT_DEFAULT_DOMAIN = "通用"

MULTI_AGENT_AUTO_GENERATE_REPORT = True
MULTI_AGENT_STOP_ON_CLARIFICATION = True
MULTI_AGENT_STRICT_PLAN_SIGNAL = True

MULTI_AGENT_DEFAULT_REPORT_TYPE = "long_document"
MULTI_AGENT_ENABLE_CONSISTENCY_CHECK = True
MULTI_AGENT_ENABLE_MAPREDUCE = True
MULTI_AGENT_MAPREDUCE_THRESHOLD = 20
MULTI_AGENT_MAX_TOKENS_PER_REDUCE = 4000
MULTI_AGENT_ENABLE_PARALLEL_MAP = True

MULTI_AGENT_SECTION_MAX_EVIDENCE = 8
MULTI_AGENT_SECTION_MAX_CONTEXT_CHARS = 800
MULTI_AGENT_REFLECTION_ALLOW_RETRY = False
MULTI_AGENT_REFLECTION_MAX_RETRIES = 1
MULTI_AGENT_WORKER_EXECUTION_MODE = "sequential"
MULTI_AGENT_WORKER_MAX_CONCURRENCY = MAX_WORKERS

_DEFAULT_KEYS = [
    "BASE_DIR",
    "PROJECT_ROOT",
    "FILES_DIR",
    "FILE_REGISTRY_PATH",
    "KB_NAME",
    "theme",
    "entity_types",
    "relationship_types",
    "conflict_strategy",
    "community_algorithm",
    "response_type",
    "lc_description",
    "gl_description",
    "naive_description",
    "examples",
    "CHUNK_SIZE",
    "OVERLAP",
    "MAX_TEXT_LENGTH",
    "TEXT_CHUNKER_PROVIDER",
    "DOCUMENT_FILE_EXTENSIONS",
    "DOCUMENT_RECURSIVE",
    "MAX_WORKERS",
    "BATCH_SIZE",
    "ENTITY_BATCH_SIZE",
    "CHUNK_BATCH_SIZE",
    "EMBEDDING_BATCH_SIZE",
    "LLM_BATCH_SIZE",
    "COMMUNITY_BATCH_SIZE",
    "COMMUNITY_SUMMARY_LIMIT",
    "COMMUNITY_SUMMARY_ONLY_MISSING",
    "COMMUNITY_SUMMARY_MAX_WORKERS",
    "COMMUNITY_SUMMARY_MAX_BATCHES",
    "COMMUNITY_SUMMARY_MAX_NODES",
    "COMMUNITY_SUMMARY_MAX_RELS",
    "GDS_MEMORY_LIMIT",
    "GDS_CONCURRENCY",
    "GDS_NODE_COUNT_LIMIT",
    "GDS_TIMEOUT_SECONDS",
    "SIMILARITY_THRESHOLD",
    "DISAMBIG_STRING_THRESHOLD",
    "DISAMBIG_VECTOR_THRESHOLD",
    "DISAMBIG_NIL_THRESHOLD",
    "DISAMBIG_TOP_K",
    "ALIGNMENT_CONFLICT_THRESHOLD",
    "ALIGNMENT_MIN_GROUP_SIZE",
    "SIMILAR_ENTITY_SETTINGS",
    "BASE_SEARCH_CONFIG",
    "LOCAL_SEARCH_SETTINGS",
    "GRAPH_BUILD_MODE",
    "DOCUMENT_KB_PREFIX",
    "STRUCTURED_DATA_DIR",
    "ENTITY_VECTOR_INDEX_NAME",
    "CHUNK_VECTOR_INDEX_NAME",
    "GLOBAL_SEARCH_SETTINGS",
    "NAIVE_SEARCH_TOP_K",
    "HYBRID_SEARCH_SETTINGS",
    "GRAPH_ENTITY_ID_PREFIX_FILTER",
    "GRAPH_CHUNK_ID_PREFIX_FILTER",
    "GRAPH_COMMUNITY_ID_PREFIX",
    "GRAPH_ENTITY_KB_LABEL",
    "GRAPH_CHUNK_KB_LABEL",
    "GRAPH_DOCUMENT_KB_LABEL",
    "GRAPH_COMMUNITY_KB_LABEL",
    "GRAPH_SKIP_SIMILAR_ENTITY",
    "GRAPH_SKIP_ENTITY_MERGE",
    "GRAPH_SKIP_ENTITY_QUALITY",
    "GRAPH_SKIP_COMMUNITY",
    "GRAPH_SKIP_COMMUNITY_SUMMARY",
    "AGENT_SETTINGS",
    "MULTI_AGENT_PLANNER_MAX_TASKS",
    "MULTI_AGENT_ALLOW_UNCLARIFIED_PLAN",
    "MULTI_AGENT_DEFAULT_DOMAIN",
    "MULTI_AGENT_AUTO_GENERATE_REPORT",
    "MULTI_AGENT_STOP_ON_CLARIFICATION",
    "MULTI_AGENT_STRICT_PLAN_SIGNAL",
    "MULTI_AGENT_DEFAULT_REPORT_TYPE",
    "MULTI_AGENT_ENABLE_CONSISTENCY_CHECK",
    "MULTI_AGENT_ENABLE_MAPREDUCE",
    "MULTI_AGENT_MAPREDUCE_THRESHOLD",
    "MULTI_AGENT_MAX_TOKENS_PER_REDUCE",
    "MULTI_AGENT_ENABLE_PARALLEL_MAP",
    "MULTI_AGENT_SECTION_MAX_EVIDENCE",
    "MULTI_AGENT_SECTION_MAX_CONTEXT_CHARS",
    "MULTI_AGENT_REFLECTION_ALLOW_RETRY",
    "MULTI_AGENT_REFLECTION_MAX_RETRIES",
    "MULTI_AGENT_WORKER_EXECUTION_MODE",
    "MULTI_AGENT_WORKER_MAX_CONCURRENCY",
]

_DEFAULT_SETTINGS = {key: globals()[key] for key in _DEFAULT_KEYS}


def get_default_settings() -> dict[str, Any]:
    return {key: value for key, value in _DEFAULT_SETTINGS.items()}


def apply_runtime_overrides(overrides: Mapping[str, Any]) -> None:
    for key, value in overrides.items():
        if key in _DEFAULT_SETTINGS:
            globals()[key] = value
