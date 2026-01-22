from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from config import rag_semantics
from graphrag_agent.config import settings as core_settings

# 统一加载环境变量，确保配置来源一致。
load_dotenv(override=True)

_APPLIED = False
_LAST_OVERRIDES: dict[str, Any] | None = None


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


def _get_env_choice(key: str, choices: set[str], default: str) -> str:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value not in choices:
        raise ValueError(
            f"环境变量 {key} 必须为 {', '.join(sorted(choices))} 之一，但当前为 {raw}"
        )
    return value


def _resolve_path(raw: str, base_dir: Path) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (base_dir / path)


def _parse_extensions(raw: str) -> list[str]:
    extensions: list[str] = []
    for ext in raw.split(","):
        ext = ext.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        extensions.append(ext)
    return extensions


def build_core_overrides() -> dict[str, Any]:
    defaults = core_settings.get_default_settings()

    infrastructure_dir = Path(__file__).resolve().parent.parent
    backend_dir = infrastructure_dir.parent
    if backend_dir.name == "backend":
        project_root = backend_dir.parent
    else:
        project_root = Path.cwd()

    # Core package directory: prefer the installed module location (works for both
    # monorepo and installed distributions).
    base_dir = Path(core_settings.__file__).resolve().parent.parent  # graphrag_agent/

    files_dir_default = defaults["FILES_DIR"]
    if isinstance(files_dir_default, Path) and files_dir_default.is_absolute():
        default_files_dir = files_dir_default
    else:
        default_files_dir = project_root / files_dir_default

    raw_files_dir = (os.getenv("FILES_DIR") or "").strip()
    files_dir = (
        _resolve_path(raw_files_dir, project_root)
        if raw_files_dir
        else default_files_dir
    )

    file_registry_default = defaults["FILE_REGISTRY_PATH"]
    if isinstance(file_registry_default, Path) and file_registry_default.is_absolute():
        file_registry_path = file_registry_default
    else:
        file_registry_path = project_root / file_registry_default

    chunk_size = _get_env_int("CHUNK_SIZE", defaults["CHUNK_SIZE"]) or defaults["CHUNK_SIZE"]
    overlap = _get_env_int("CHUNK_OVERLAP", defaults["OVERLAP"]) or defaults["OVERLAP"]
    max_text_length = (
        _get_env_int("MAX_TEXT_LENGTH", defaults["MAX_TEXT_LENGTH"]) or defaults["MAX_TEXT_LENGTH"]
    )

    text_chunker_provider = _get_env_choice(
        "TEXT_CHUNKER_PROVIDER",
        {"hanlp", "simple"},
        defaults["TEXT_CHUNKER_PROVIDER"],
    )

    raw_ext = os.getenv("DOCUMENT_FILE_EXTENSIONS")
    if raw_ext is None or raw_ext.strip() == "":
        document_file_extensions = list(defaults["DOCUMENT_FILE_EXTENSIONS"])
    else:
        document_file_extensions = _parse_extensions(raw_ext)

    document_recursive = _get_env_bool(
        "DOCUMENT_RECURSIVE",
        defaults["DOCUMENT_RECURSIVE"],
    )

    max_workers = _get_env_int("MAX_WORKERS", defaults["MAX_WORKERS"]) or defaults["MAX_WORKERS"]
    batch_size = _get_env_int("BATCH_SIZE", defaults["BATCH_SIZE"]) or defaults["BATCH_SIZE"]
    entity_batch_size = (
        _get_env_int("ENTITY_BATCH_SIZE", defaults["ENTITY_BATCH_SIZE"])
        or defaults["ENTITY_BATCH_SIZE"]
    )
    chunk_batch_size = (
        _get_env_int("CHUNK_BATCH_SIZE", defaults["CHUNK_BATCH_SIZE"])
        or defaults["CHUNK_BATCH_SIZE"]
    )
    embedding_batch_size = (
        _get_env_int("EMBEDDING_BATCH_SIZE", defaults["EMBEDDING_BATCH_SIZE"])
        or defaults["EMBEDDING_BATCH_SIZE"]
    )
    llm_batch_size = (
        _get_env_int("LLM_BATCH_SIZE", defaults["LLM_BATCH_SIZE"])
        or defaults["LLM_BATCH_SIZE"]
    )
    community_batch_size = (
        _get_env_int("COMMUNITY_BATCH_SIZE", defaults["COMMUNITY_BATCH_SIZE"])
        or defaults["COMMUNITY_BATCH_SIZE"]
    )

    community_summary_limit_raw = _get_env_int(
        "COMMUNITY_SUMMARY_LIMIT", defaults["COMMUNITY_SUMMARY_LIMIT"]
    )
    community_summary_limit = (
        defaults["COMMUNITY_SUMMARY_LIMIT"]
        if community_summary_limit_raw is None
        else community_summary_limit_raw
    )

    community_summary_only_missing = _get_env_bool(
        "COMMUNITY_SUMMARY_ONLY_MISSING",
        defaults["COMMUNITY_SUMMARY_ONLY_MISSING"],
    )

    community_summary_workers = _get_env_int(
        "COMMUNITY_SUMMARY_MAX_WORKERS",
        defaults["COMMUNITY_SUMMARY_MAX_WORKERS"],
    )
    if community_summary_workers and community_summary_workers > 0:
        community_summary_max_workers = community_summary_workers
    else:
        community_summary_max_workers = defaults["COMMUNITY_SUMMARY_MAX_WORKERS"]

    community_summary_max_batches_raw = _get_env_int(
        "COMMUNITY_SUMMARY_MAX_BATCHES",
        defaults["COMMUNITY_SUMMARY_MAX_BATCHES"],
    )
    community_summary_max_batches = (
        defaults["COMMUNITY_SUMMARY_MAX_BATCHES"]
        if community_summary_max_batches_raw is None
        else community_summary_max_batches_raw
    )

    community_summary_max_nodes_raw = _get_env_int(
        "COMMUNITY_SUMMARY_MAX_NODES",
        defaults["COMMUNITY_SUMMARY_MAX_NODES"],
    )
    community_summary_max_nodes = (
        defaults["COMMUNITY_SUMMARY_MAX_NODES"]
        if community_summary_max_nodes_raw is None
        else community_summary_max_nodes_raw
    )

    community_summary_max_rels_raw = _get_env_int(
        "COMMUNITY_SUMMARY_MAX_RELS",
        defaults["COMMUNITY_SUMMARY_MAX_RELS"],
    )
    community_summary_max_rels = (
        defaults["COMMUNITY_SUMMARY_MAX_RELS"]
        if community_summary_max_rels_raw is None
        else community_summary_max_rels_raw
    )

    gds_memory_limit = _get_env_int("GDS_MEMORY_LIMIT", defaults["GDS_MEMORY_LIMIT"]) or defaults[
        "GDS_MEMORY_LIMIT"
    ]
    gds_concurrency = (
        _get_env_int("GDS_CONCURRENCY", defaults["GDS_CONCURRENCY"])
        or defaults["GDS_CONCURRENCY"]
    )
    gds_node_count_limit = (
        _get_env_int("GDS_NODE_COUNT_LIMIT", defaults["GDS_NODE_COUNT_LIMIT"])
        or defaults["GDS_NODE_COUNT_LIMIT"]
    )
    gds_timeout_seconds = (
        _get_env_int("GDS_TIMEOUT_SECONDS", defaults["GDS_TIMEOUT_SECONDS"])
        or defaults["GDS_TIMEOUT_SECONDS"]
    )

    similarity_threshold = (
        _get_env_float("SIMILARITY_THRESHOLD", defaults["SIMILARITY_THRESHOLD"])
        or defaults["SIMILARITY_THRESHOLD"]
    )

    disambig_string_threshold = (
        _get_env_float("DISAMBIG_STRING_THRESHOLD", defaults["DISAMBIG_STRING_THRESHOLD"])
        or defaults["DISAMBIG_STRING_THRESHOLD"]
    )
    disambig_vector_threshold = (
        _get_env_float("DISAMBIG_VECTOR_THRESHOLD", defaults["DISAMBIG_VECTOR_THRESHOLD"])
        or defaults["DISAMBIG_VECTOR_THRESHOLD"]
    )
    disambig_nil_threshold = (
        _get_env_float("DISAMBIG_NIL_THRESHOLD", defaults["DISAMBIG_NIL_THRESHOLD"])
        or defaults["DISAMBIG_NIL_THRESHOLD"]
    )
    disambig_top_k = (
        _get_env_int("DISAMBIG_TOP_K", defaults["DISAMBIG_TOP_K"])
        or defaults["DISAMBIG_TOP_K"]
    )

    alignment_conflict_threshold = (
        _get_env_float(
            "ALIGNMENT_CONFLICT_THRESHOLD",
            defaults["ALIGNMENT_CONFLICT_THRESHOLD"],
        )
        or defaults["ALIGNMENT_CONFLICT_THRESHOLD"]
    )
    alignment_min_group_size = (
        _get_env_int("ALIGNMENT_MIN_GROUP_SIZE", defaults["ALIGNMENT_MIN_GROUP_SIZE"])
        or defaults["ALIGNMENT_MIN_GROUP_SIZE"]
    )

    similar_entity_settings = {
        "word_edit_distance": _get_env_int(
            "SIMILAR_ENTITY_WORD_EDIT_DISTANCE",
            defaults["SIMILAR_ENTITY_SETTINGS"]["word_edit_distance"],
        )
        or defaults["SIMILAR_ENTITY_SETTINGS"]["word_edit_distance"],
        "batch_size": _get_env_int(
            "SIMILAR_ENTITY_BATCH_SIZE",
            defaults["SIMILAR_ENTITY_SETTINGS"]["batch_size"],
        )
        or defaults["SIMILAR_ENTITY_SETTINGS"]["batch_size"],
        "memory_limit": _get_env_int(
            "SIMILAR_ENTITY_MEMORY_LIMIT",
            defaults["SIMILAR_ENTITY_SETTINGS"]["memory_limit"],
        )
        or defaults["SIMILAR_ENTITY_SETTINGS"]["memory_limit"],
        "top_k": _get_env_int(
            "SIMILAR_ENTITY_TOP_K",
            defaults["SIMILAR_ENTITY_SETTINGS"]["top_k"],
        )
        or defaults["SIMILAR_ENTITY_SETTINGS"]["top_k"],
    }

    base_search_config = {
        "vector_limit": _get_env_int(
            "SEARCH_VECTOR_LIMIT",
            defaults["BASE_SEARCH_CONFIG"]["vector_limit"],
        )
        or defaults["BASE_SEARCH_CONFIG"]["vector_limit"],
        "text_limit": _get_env_int(
            "SEARCH_TEXT_LIMIT",
            defaults["BASE_SEARCH_CONFIG"]["text_limit"],
        )
        or defaults["BASE_SEARCH_CONFIG"]["text_limit"],
        "semantic_top_k": _get_env_int(
            "SEARCH_SEMANTIC_TOP_K",
            defaults["BASE_SEARCH_CONFIG"]["semantic_top_k"],
        )
        or defaults["BASE_SEARCH_CONFIG"]["semantic_top_k"],
        "relevance_top_k": _get_env_int(
            "SEARCH_RELEVANCE_TOP_K",
            defaults["BASE_SEARCH_CONFIG"]["relevance_top_k"],
        )
        or defaults["BASE_SEARCH_CONFIG"]["relevance_top_k"],
    }

    local_search_settings = {
        "top_chunks": _get_env_int(
            "LOCAL_SEARCH_TOP_CHUNKS",
            defaults["LOCAL_SEARCH_SETTINGS"]["top_chunks"],
        )
        or defaults["LOCAL_SEARCH_SETTINGS"]["top_chunks"],
        "top_communities": _get_env_int(
            "LOCAL_SEARCH_TOP_COMMUNITIES",
            defaults["LOCAL_SEARCH_SETTINGS"]["top_communities"],
        )
        or defaults["LOCAL_SEARCH_SETTINGS"]["top_communities"],
        "top_outside_relationships": _get_env_int(
            "LOCAL_SEARCH_TOP_OUTSIDE_RELS",
            defaults["LOCAL_SEARCH_SETTINGS"]["top_outside_relationships"],
        )
        or defaults["LOCAL_SEARCH_SETTINGS"]["top_outside_relationships"],
        "top_inside_relationships": _get_env_int(
            "LOCAL_SEARCH_TOP_INSIDE_RELS",
            defaults["LOCAL_SEARCH_SETTINGS"]["top_inside_relationships"],
        )
        or defaults["LOCAL_SEARCH_SETTINGS"]["top_inside_relationships"],
        "top_entities": _get_env_int(
            "LOCAL_SEARCH_TOP_ENTITIES",
            defaults["LOCAL_SEARCH_SETTINGS"]["top_entities"],
        )
        or defaults["LOCAL_SEARCH_SETTINGS"]["top_entities"],
        "index_name": defaults["LOCAL_SEARCH_SETTINGS"]["index_name"],
    }

    graph_build_mode = _get_env_choice(
        "GRAPH_BUILD_MODE",
        {"document", "structured"},
        defaults["GRAPH_BUILD_MODE"],
    )

    document_kb_prefix = (os.getenv("DOCUMENT_KB_PREFIX") or defaults["DOCUMENT_KB_PREFIX"]).strip()

    structured_data_dir_raw = os.getenv("STRUCTURED_DATA_DIR")
    if structured_data_dir_raw:
        structured_data_dir = _resolve_path(structured_data_dir_raw, project_root)
    else:
        structured_data_dir = files_dir / "movie_data"

    structured_kb_prefix_for_index = (os.getenv("STRUCTURED_KB_PREFIX") or "movie").strip()
    kb_slug_for_index = (
        structured_kb_prefix_for_index
        if graph_build_mode == "structured"
        else (document_kb_prefix if document_kb_prefix else "")
    )
    default_entity_vector_index_name = (
        f"{kb_slug_for_index}_vector" if kb_slug_for_index else "vector"
    )
    default_chunk_vector_index_name = (
        f"{kb_slug_for_index}_chunk_vector" if kb_slug_for_index else "chunk_vector"
    )

    entity_vector_index_name = (
        os.getenv("ENTITY_VECTOR_INDEX_NAME")
        or os.getenv("LOCAL_SEARCH_INDEX_NAME")
        or default_entity_vector_index_name
    )
    chunk_vector_index_name = os.getenv("CHUNK_VECTOR_INDEX_NAME") or default_chunk_vector_index_name

    local_search_settings["index_name"] = entity_vector_index_name

    global_search_settings = {
        "default_level": _get_env_int(
            "GLOBAL_SEARCH_LEVEL",
            defaults["GLOBAL_SEARCH_SETTINGS"]["default_level"],
        )
        or defaults["GLOBAL_SEARCH_SETTINGS"]["default_level"],
        "community_batch_size": _get_env_int(
            "GLOBAL_SEARCH_BATCH_SIZE",
            defaults["GLOBAL_SEARCH_SETTINGS"]["community_batch_size"],
        )
        or defaults["GLOBAL_SEARCH_SETTINGS"]["community_batch_size"],
    }

    naive_search_top_k = (
        _get_env_int("NAIVE_SEARCH_TOP_K", defaults["NAIVE_SEARCH_TOP_K"])
        or defaults["NAIVE_SEARCH_TOP_K"]
    )

    hybrid_search_settings = {
        "entity_limit": _get_env_int(
            "HYBRID_SEARCH_ENTITY_LIMIT",
            defaults["HYBRID_SEARCH_SETTINGS"]["entity_limit"],
        )
        or defaults["HYBRID_SEARCH_SETTINGS"]["entity_limit"],
        "max_hop_distance": _get_env_int(
            "HYBRID_SEARCH_MAX_HOP",
            defaults["HYBRID_SEARCH_SETTINGS"]["max_hop_distance"],
        )
        or defaults["HYBRID_SEARCH_SETTINGS"]["max_hop_distance"],
        "top_communities": _get_env_int(
            "HYBRID_SEARCH_TOP_COMMUNITIES",
            defaults["HYBRID_SEARCH_SETTINGS"]["top_communities"],
        )
        or defaults["HYBRID_SEARCH_SETTINGS"]["top_communities"],
        "batch_size": _get_env_int(
            "HYBRID_SEARCH_BATCH_SIZE",
            defaults["HYBRID_SEARCH_SETTINGS"]["batch_size"],
        )
        or defaults["HYBRID_SEARCH_SETTINGS"]["batch_size"],
        "community_level": _get_env_int(
            "HYBRID_SEARCH_COMMUNITY_LEVEL",
            defaults["HYBRID_SEARCH_SETTINGS"]["community_level"],
        )
        or defaults["HYBRID_SEARCH_SETTINGS"]["community_level"],
    }

    structured_kb_prefix = (os.getenv("STRUCTURED_KB_PREFIX") or "movie").strip()
    default_structured_entity_prefix = (
        f"{structured_kb_prefix}:" if graph_build_mode == "structured" else ""
    )
    default_document_entity_prefix = (
        f"{document_kb_prefix}:" if graph_build_mode == "document" and document_kb_prefix else ""
    )
    default_entity_prefix = default_structured_entity_prefix or default_document_entity_prefix

    graph_entity_id_prefix_filter = (
        os.getenv("GRAPH_ENTITY_ID_PREFIX_FILTER", default_entity_prefix).strip()
        if default_entity_prefix is not None
        else ""
    )

    graph_chunk_id_prefix_filter = (
        os.getenv("GRAPH_CHUNK_ID_PREFIX_FILTER", "").strip()
        or graph_entity_id_prefix_filter
    )

    graph_community_id_prefix = (
        os.getenv("GRAPH_COMMUNITY_ID_PREFIX", "").strip()
        or graph_entity_id_prefix_filter
    )

    graph_entity_kb_label = (
        os.getenv("GRAPH_ENTITY_KB_LABEL", "").strip()
        or (
            core_settings.kb_scoped_label_for_kb_prefix(
                graph_entity_id_prefix_filter, "entity"
            )
            if graph_entity_id_prefix_filter
            else ""
        )
    )
    graph_chunk_kb_label = (
        os.getenv("GRAPH_CHUNK_KB_LABEL", "").strip()
        or (
            core_settings.kb_scoped_label_for_kb_prefix(
                graph_chunk_id_prefix_filter, "chunk"
            )
            if graph_chunk_id_prefix_filter
            else ""
        )
    )
    graph_document_kb_label = (
        os.getenv("GRAPH_DOCUMENT_KB_LABEL", "").strip()
        or (
            core_settings.kb_scoped_label_for_kb_prefix(
                graph_entity_id_prefix_filter, "document"
            )
            if graph_entity_id_prefix_filter
            else ""
        )
    )
    graph_community_kb_label = (
        os.getenv("GRAPH_COMMUNITY_KB_LABEL", "").strip()
        or (
            core_settings.kb_scoped_label_for_kb_prefix(
                graph_community_id_prefix, "community"
            )
            if graph_community_id_prefix
            else ""
        )
    )

    structured_default_skip = graph_build_mode == "structured"
    graph_skip_similar_entity = _get_env_bool(
        "GRAPH_SKIP_SIMILAR_ENTITY", structured_default_skip
    )
    graph_skip_entity_merge = _get_env_bool(
        "GRAPH_SKIP_ENTITY_MERGE", structured_default_skip
    )
    graph_skip_entity_quality = _get_env_bool(
        "GRAPH_SKIP_ENTITY_QUALITY", structured_default_skip
    )
    graph_skip_community = _get_env_bool("GRAPH_SKIP_COMMUNITY", False)
    graph_skip_community_summary = _get_env_bool(
        "GRAPH_SKIP_COMMUNITY_SUMMARY", structured_default_skip
    )

    agent_settings = {
        "default_recursion_limit": _get_env_int(
            "AGENT_RECURSION_LIMIT",
            defaults["AGENT_SETTINGS"]["default_recursion_limit"],
        )
        or defaults["AGENT_SETTINGS"]["default_recursion_limit"],
        "chunk_size": _get_env_int(
            "AGENT_CHUNK_SIZE",
            defaults["AGENT_SETTINGS"]["chunk_size"],
        )
        or defaults["AGENT_SETTINGS"]["chunk_size"],
        "stream_flush_threshold": _get_env_int(
            "AGENT_STREAM_FLUSH_THRESHOLD",
            defaults["AGENT_SETTINGS"]["stream_flush_threshold"],
        )
        or defaults["AGENT_SETTINGS"]["stream_flush_threshold"],
        "deep_stream_flush_threshold": _get_env_int(
            "DEEP_AGENT_STREAM_FLUSH_THRESHOLD",
            defaults["AGENT_SETTINGS"]["deep_stream_flush_threshold"],
        )
        or defaults["AGENT_SETTINGS"]["deep_stream_flush_threshold"],
        "fusion_stream_flush_threshold": _get_env_int(
            "FUSION_AGENT_STREAM_FLUSH_THRESHOLD",
            defaults["AGENT_SETTINGS"]["fusion_stream_flush_threshold"],
        )
        or defaults["AGENT_SETTINGS"]["fusion_stream_flush_threshold"],
    }

    multi_agent_planner_max_tasks = (
        _get_env_int("MA_PLANNER_MAX_TASKS", defaults["MULTI_AGENT_PLANNER_MAX_TASKS"])
        or defaults["MULTI_AGENT_PLANNER_MAX_TASKS"]
    )
    multi_agent_allow_unclarified_plan = _get_env_bool(
        "MA_ALLOW_UNCLARIFIED_PLAN",
        defaults["MULTI_AGENT_ALLOW_UNCLARIFIED_PLAN"],
    )
    multi_agent_default_domain = os.getenv(
        "MA_DEFAULT_DOMAIN", defaults["MULTI_AGENT_DEFAULT_DOMAIN"]
    )

    multi_agent_auto_generate_report = _get_env_bool(
        "MA_AUTO_GENERATE_REPORT",
        defaults["MULTI_AGENT_AUTO_GENERATE_REPORT"],
    )
    multi_agent_stop_on_clarification = _get_env_bool(
        "MA_STOP_ON_CLARIFICATION",
        defaults["MULTI_AGENT_STOP_ON_CLARIFICATION"],
    )
    multi_agent_strict_plan_signal = _get_env_bool(
        "MA_STRICT_PLAN_SIGNAL",
        defaults["MULTI_AGENT_STRICT_PLAN_SIGNAL"],
    )

    multi_agent_default_report_type = os.getenv(
        "MA_DEFAULT_REPORT_TYPE", defaults["MULTI_AGENT_DEFAULT_REPORT_TYPE"]
    )
    multi_agent_enable_consistency_check = _get_env_bool(
        "MA_ENABLE_CONSISTENCY_CHECK",
        defaults["MULTI_AGENT_ENABLE_CONSISTENCY_CHECK"],
    )
    multi_agent_enable_mapreduce = _get_env_bool(
        "MA_ENABLE_MAPREDUCE", defaults["MULTI_AGENT_ENABLE_MAPREDUCE"]
    )
    multi_agent_mapreduce_threshold = (
        _get_env_int(
            "MA_MAPREDUCE_THRESHOLD", defaults["MULTI_AGENT_MAPREDUCE_THRESHOLD"]
        )
        or defaults["MULTI_AGENT_MAPREDUCE_THRESHOLD"]
    )
    multi_agent_max_tokens_per_reduce = (
        _get_env_int(
            "MA_MAX_TOKENS_PER_REDUCE", defaults["MULTI_AGENT_MAX_TOKENS_PER_REDUCE"]
        )
        or defaults["MULTI_AGENT_MAX_TOKENS_PER_REDUCE"]
    )
    multi_agent_enable_parallel_map = _get_env_bool(
        "MA_ENABLE_PARALLEL_MAP", defaults["MULTI_AGENT_ENABLE_PARALLEL_MAP"]
    )

    multi_agent_section_max_evidence = (
        _get_env_int(
            "MA_SECTION_MAX_EVIDENCE", defaults["MULTI_AGENT_SECTION_MAX_EVIDENCE"]
        )
        or defaults["MULTI_AGENT_SECTION_MAX_EVIDENCE"]
    )
    multi_agent_section_max_context_chars = (
        _get_env_int(
            "MA_SECTION_MAX_CONTEXT_CHARS", defaults["MULTI_AGENT_SECTION_MAX_CONTEXT_CHARS"]
        )
        or defaults["MULTI_AGENT_SECTION_MAX_CONTEXT_CHARS"]
    )
    multi_agent_reflection_allow_retry = _get_env_bool(
        "MA_REFLECTION_ALLOW_RETRY", defaults["MULTI_AGENT_REFLECTION_ALLOW_RETRY"]
    )
    multi_agent_reflection_max_retries = (
        _get_env_int(
            "MA_REFLECTION_MAX_RETRIES", defaults["MULTI_AGENT_REFLECTION_MAX_RETRIES"]
        )
        or defaults["MULTI_AGENT_REFLECTION_MAX_RETRIES"]
    )
    multi_agent_worker_execution_mode = _get_env_choice(
        "MA_WORKER_EXECUTION_MODE",
        {"sequential", "parallel"},
        defaults["MULTI_AGENT_WORKER_EXECUTION_MODE"],
    )
    multi_agent_worker_max_concurrency = (
        _get_env_int(
            "MA_WORKER_MAX_CONCURRENCY", defaults["MULTI_AGENT_WORKER_MAX_CONCURRENCY"]
        )
        or defaults["MULTI_AGENT_WORKER_MAX_CONCURRENCY"]
    )
    if multi_agent_worker_max_concurrency < 1:
        raise ValueError("MA_WORKER_MAX_CONCURRENCY 必须大于等于 1")

    return {
        "BASE_DIR": base_dir,
        "PROJECT_ROOT": project_root,
        "FILES_DIR": files_dir,
        "FILE_REGISTRY_PATH": file_registry_path,
        "KB_NAME": rag_semantics.KB_NAME,
        "theme": rag_semantics.theme,
        "entity_types": list(rag_semantics.entity_types),
        "relationship_types": list(rag_semantics.relationship_types),
        "conflict_strategy": rag_semantics.conflict_strategy,
        "community_algorithm": rag_semantics.community_algorithm,
        "response_type": rag_semantics.response_type,
        "lc_description": rag_semantics.lc_description,
        "gl_description": rag_semantics.gl_description,
        "naive_description": rag_semantics.naive_description,
        "examples": list(rag_semantics.examples),
        "CHUNK_SIZE": chunk_size,
        "OVERLAP": overlap,
        "MAX_TEXT_LENGTH": max_text_length,
        "TEXT_CHUNKER_PROVIDER": text_chunker_provider,
        "DOCUMENT_FILE_EXTENSIONS": document_file_extensions,
        "DOCUMENT_RECURSIVE": document_recursive,
        "MAX_WORKERS": max_workers,
        "BATCH_SIZE": batch_size,
        "ENTITY_BATCH_SIZE": entity_batch_size,
        "CHUNK_BATCH_SIZE": chunk_batch_size,
        "EMBEDDING_BATCH_SIZE": embedding_batch_size,
        "LLM_BATCH_SIZE": llm_batch_size,
        "COMMUNITY_BATCH_SIZE": community_batch_size,
        "COMMUNITY_SUMMARY_LIMIT": community_summary_limit,
        "COMMUNITY_SUMMARY_ONLY_MISSING": community_summary_only_missing,
        "COMMUNITY_SUMMARY_MAX_WORKERS": community_summary_max_workers,
        "COMMUNITY_SUMMARY_MAX_BATCHES": community_summary_max_batches,
        "COMMUNITY_SUMMARY_MAX_NODES": community_summary_max_nodes,
        "COMMUNITY_SUMMARY_MAX_RELS": community_summary_max_rels,
        "GDS_MEMORY_LIMIT": gds_memory_limit,
        "GDS_CONCURRENCY": gds_concurrency,
        "GDS_NODE_COUNT_LIMIT": gds_node_count_limit,
        "GDS_TIMEOUT_SECONDS": gds_timeout_seconds,
        "SIMILARITY_THRESHOLD": similarity_threshold,
        "DISAMBIG_STRING_THRESHOLD": disambig_string_threshold,
        "DISAMBIG_VECTOR_THRESHOLD": disambig_vector_threshold,
        "DISAMBIG_NIL_THRESHOLD": disambig_nil_threshold,
        "DISAMBIG_TOP_K": disambig_top_k,
        "ALIGNMENT_CONFLICT_THRESHOLD": alignment_conflict_threshold,
        "ALIGNMENT_MIN_GROUP_SIZE": alignment_min_group_size,
        "SIMILAR_ENTITY_SETTINGS": similar_entity_settings,
        "BASE_SEARCH_CONFIG": base_search_config,
        "LOCAL_SEARCH_SETTINGS": local_search_settings,
        "GRAPH_BUILD_MODE": graph_build_mode,
        "DOCUMENT_KB_PREFIX": document_kb_prefix,
        "STRUCTURED_DATA_DIR": structured_data_dir,
        "ENTITY_VECTOR_INDEX_NAME": entity_vector_index_name,
        "CHUNK_VECTOR_INDEX_NAME": chunk_vector_index_name,
        "GLOBAL_SEARCH_SETTINGS": global_search_settings,
        "NAIVE_SEARCH_TOP_K": naive_search_top_k,
        "HYBRID_SEARCH_SETTINGS": hybrid_search_settings,
        "GRAPH_ENTITY_ID_PREFIX_FILTER": graph_entity_id_prefix_filter,
        "GRAPH_CHUNK_ID_PREFIX_FILTER": graph_chunk_id_prefix_filter,
        "GRAPH_COMMUNITY_ID_PREFIX": graph_community_id_prefix,
        "GRAPH_ENTITY_KB_LABEL": graph_entity_kb_label,
        "GRAPH_CHUNK_KB_LABEL": graph_chunk_kb_label,
        "GRAPH_DOCUMENT_KB_LABEL": graph_document_kb_label,
        "GRAPH_COMMUNITY_KB_LABEL": graph_community_kb_label,
        "GRAPH_SKIP_SIMILAR_ENTITY": graph_skip_similar_entity,
        "GRAPH_SKIP_ENTITY_MERGE": graph_skip_entity_merge,
        "GRAPH_SKIP_ENTITY_QUALITY": graph_skip_entity_quality,
        "GRAPH_SKIP_COMMUNITY": graph_skip_community,
        "GRAPH_SKIP_COMMUNITY_SUMMARY": graph_skip_community_summary,
        "AGENT_SETTINGS": agent_settings,
        "MULTI_AGENT_PLANNER_MAX_TASKS": multi_agent_planner_max_tasks,
        "MULTI_AGENT_ALLOW_UNCLARIFIED_PLAN": multi_agent_allow_unclarified_plan,
        "MULTI_AGENT_DEFAULT_DOMAIN": multi_agent_default_domain,
        "MULTI_AGENT_AUTO_GENERATE_REPORT": multi_agent_auto_generate_report,
        "MULTI_AGENT_STOP_ON_CLARIFICATION": multi_agent_stop_on_clarification,
        "MULTI_AGENT_STRICT_PLAN_SIGNAL": multi_agent_strict_plan_signal,
        "MULTI_AGENT_DEFAULT_REPORT_TYPE": multi_agent_default_report_type,
        "MULTI_AGENT_ENABLE_CONSISTENCY_CHECK": multi_agent_enable_consistency_check,
        "MULTI_AGENT_ENABLE_MAPREDUCE": multi_agent_enable_mapreduce,
        "MULTI_AGENT_MAPREDUCE_THRESHOLD": multi_agent_mapreduce_threshold,
        "MULTI_AGENT_MAX_TOKENS_PER_REDUCE": multi_agent_max_tokens_per_reduce,
        "MULTI_AGENT_ENABLE_PARALLEL_MAP": multi_agent_enable_parallel_map,
        "MULTI_AGENT_SECTION_MAX_EVIDENCE": multi_agent_section_max_evidence,
        "MULTI_AGENT_SECTION_MAX_CONTEXT_CHARS": multi_agent_section_max_context_chars,
        "MULTI_AGENT_REFLECTION_ALLOW_RETRY": multi_agent_reflection_allow_retry,
        "MULTI_AGENT_REFLECTION_MAX_RETRIES": multi_agent_reflection_max_retries,
        "MULTI_AGENT_WORKER_EXECUTION_MODE": multi_agent_worker_execution_mode,
        "MULTI_AGENT_WORKER_MAX_CONCURRENCY": multi_agent_worker_max_concurrency,
    }


def apply_core_settings_overrides() -> dict[str, Any]:
    global _APPLIED, _LAST_OVERRIDES
    if _APPLIED and _LAST_OVERRIDES is not None:
        return _LAST_OVERRIDES

    overrides = build_core_overrides()
    core_settings.apply_runtime_overrides(overrides)
    _APPLIED = True
    _LAST_OVERRIDES = overrides
    return overrides
