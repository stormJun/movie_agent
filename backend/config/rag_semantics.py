import os

from dotenv import load_dotenv

# Ensure `.env` is loaded for local/dev usage (same policy as infrastructure settings).
load_dotenv(override=True)


# ===== Knowledge base semantics =====

KB_NAME = os.getenv("KB_NAME", "华东理工大学")  # Knowledge base name (prompt semantics)

# Graph schema semantics (domain-specific)
theme = os.getenv("GRAPH_THEME", "华东理工大学学生管理")

entity_types = [
    item.strip()
    for item in (
        os.getenv(
            "GRAPH_ENTITY_TYPES",
            "学生类型,奖学金类型,处分类型,部门,学生职责,管理规定",
        ).split(",")
    )
    if item.strip()
]

relationship_types = [
    item.strip()
    for item in (
        os.getenv(
            "GRAPH_RELATIONSHIP_TYPES",
            "申请,评选,违纪,资助,申诉,管理,权利义务,互斥",
        ).split(",")
    )
    if item.strip()
]

# Conflict strategy: manual_first / auto_first / merge
conflict_strategy = os.getenv("GRAPH_CONFLICT_STRATEGY", "manual_first")

# Community algorithm: leiden / sllpa
community_algorithm = os.getenv("GRAPH_COMMUNITY_ALGORITHM", "leiden")


# ===== Answer / prompt semantics =====

response_type = os.getenv("RESPONSE_TYPE", "多个段落")

# Tool descriptions (domain-specific)
lc_description = os.getenv(
    "LC_DESCRIPTION",
    (
        "用于需要具体细节的查询。检索华东理工大学学生管理文件中的具体规定、条款、流程等详细内容。"
        "适用于某个具体规定是什么、处理流程如何等问题。"
    ),
)
gl_description = os.getenv(
    "GL_DESCRIPTION",
    (
        "用于需要总结归纳的查询。分析华东理工大学学生管理体系的整体框架、管理原则、学生权利义务等宏观内容。"
        "适用于学校的学生管理总体思路、学生权益保护机制等需要系统性分析的问题。"
    ),
)
naive_description = os.getenv(
    "NAIVE_DESCRIPTION",
    "基础检索工具，直接查找与问题最相关的文本片段，不做复杂分析。快速获取华东理工大学相关政策，返回最匹配的原文段落。",
)

examples = [
    item.strip()
    for item in (
        os.getenv(
            "FRONTEND_EXAMPLES",
            "旷课多少学时会被退学？,国家奖学金和国家励志奖学金互斥吗？,优秀学生要怎么申请？,那上海市奖学金呢？",
        ).split(",")
    )
    if item.strip()
]

__all__ = [
    "KB_NAME",
    "community_algorithm",
    "conflict_strategy",
    "entity_types",
    "examples",
    "gl_description",
    "lc_description",
    "naive_description",
    "relationship_types",
    "response_type",
    "theme",
]
