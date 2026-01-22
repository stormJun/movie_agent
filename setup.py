from __future__ import annotations

from setuptools import find_packages, setup

setup(
    # Phase2.5: core package name (library-first). The repository may still host
    # the full backend, but the distributable here is the core only.
    name="graphrag-agent",
    version="0.1.0",
    # Repo convention: backend code lives under `backend/`.
    # Phase2.5: package the GraphRAG core as a normal top-level import
    # (`import graphrag_agent`) while keeping sources physically under `backend/`.
    package_dir={"": "backend"},
    packages=find_packages(where="backend", include=["graphrag_agent", "graphrag_agent.*"]),
    python_requires=">=3.10",
    install_requires=[
        # Keep core deps minimal; optional capabilities are installed via extras.
        "pydantic==2.10.6",
        "pyyaml>=6.0",
    ],
    extras_require={
        # Optional: langchain stack (used by search/tools/agents).
        "langchain": [
            "langchain==0.3.21",
            "langchain_core==0.3.46",
            "langchain_community==0.3.20",
            "langgraph==0.3.18",
            "langsmith==0.3.18",
            "langchain_openai==0.3.9",
        ],
        # Optional: search runtime deps (some modules import these at module import time).
        "search": [
            "numpy==1.26.2",
            "pandas==2.2.3",
            "scikit-learn==1.6.1",
        ],
        # Optional: Neo4j integration (still via ports; useful for tools/clients).
        "neo4j": ["neo4j", "langchain_neo4j==0.4.0"],
        # Optional: evaluation tooling (kept out of core package directory).
        "eval": ["rich==13.9.4", "tqdm==4.66.3"],
        # Convenience: all optional deps.
        "full": [
            "numpy==1.26.2",
            "pandas==2.2.3",
            "scikit-learn==1.6.1",
            "neo4j",
            "langchain_neo4j==0.4.0",
            "langchain==0.3.21",
            "langchain_core==0.3.46",
            "langchain_community==0.3.20",
            "langgraph==0.3.18",
            "langsmith==0.3.18",
            "langchain_openai==0.3.9",
            "rich==13.9.4",
            "tqdm==4.66.3",
        ],
    },
)
