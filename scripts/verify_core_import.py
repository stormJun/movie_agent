from __future__ import annotations

"""
Core-only import smoke test.

This script is intended to validate a *core-only installed* environment:
- No infrastructure providers configured (Neo4j, Redis, etc.)
- No optional dependency stack installed (langchain/langgraph/numpy/pandas)

It must not perform any network/DB calls; it only validates imports and
dependency boundaries.
"""

from pathlib import Path
import os
import sys
import tempfile
import importlib.util
import importlib

def main() -> None:
    # Ensure we don't accidentally import from the repo checkout (cwd or repo root).
    repo_root = Path(__file__).resolve().parents[1]
    orig_cwd = os.getcwd()
    orig_sys_path = list(sys.path)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            sys.path = [
                p
                for p in sys.path
                if p
                and p != str(repo_root)
                and Path(p).resolve() != repo_root
            ]

            import graphrag_agent  # noqa: F401

            # Ensure ports can be imported without configured providers.
            from graphrag_agent import ports  # noqa: F401
            from graphrag_agent.ports import cache, models, neo4jdb  # noqa: F401

            # Subpackages should be importable in a minimal install (lazy imports).
            import graphrag_agent.search  # noqa: F401
            import graphrag_agent.graph  # noqa: F401
            import graphrag_agent.community  # noqa: F401
            import graphrag_agent.search.tool_registry  # noqa: F401
            import graphrag_agent.search.tool  # noqa: F401
            import graphrag_agent.graph.extraction  # noqa: F401
            import graphrag_agent.graph.indexing  # noqa: F401
            import graphrag_agent.graph.processing  # noqa: F401
            import graphrag_agent.graph.structure  # noqa: F401
            import graphrag_agent.community.detector  # noqa: F401
            import graphrag_agent.community.summary  # noqa: F401

            # In a core-only environment, optional deps are not installed. Accessing
            # concrete implementations should fail with a helpful ImportError message.
            forbidden = ["langchain", "langchain_core", "langgraph", "pandas", "numpy"]
            optional_installed = any(importlib.util.find_spec(m) is not None for m in forbidden)
            if not optional_installed:
                for mod, symbol in [
                    ("graphrag_agent.search", "LocalSearch"),
                    ("graphrag_agent.graph", "EntityRelationExtractor"),
                    ("graphrag_agent.community", "CommunityDetectorFactory"),
                ]:
                    m = importlib.import_module(mod)
                    try:
                        getattr(m, symbol)
                    except ImportError as exc:
                        msg = str(exc)
                        if "Optional dependencies required." not in msg:
                            raise SystemExit(f"Expected helpful ImportError for {mod}.{symbol}, got: {msg}")
                    else:
                        raise SystemExit(
                            f"Expected ImportError in core-only env for {mod}.{symbol}, but it imported successfully."
                        )

                # Agents are optional (langchain/langgraph stack). Import should fail with a helpful message.
                try:
                    import graphrag_agent.agents.base  # noqa: F401
                except ImportError as exc:
                    msg = str(exc)
                    if "Optional dependencies required." not in msg:
                        raise SystemExit(f"Expected helpful ImportError for agents.base, got: {msg}")
                else:
                    raise SystemExit("Expected ImportError in core-only env for graphrag_agent.agents.base")

            print("OK: graphrag_agent core imports")
    finally:
        os.chdir(orig_cwd)
        sys.path = orig_sys_path


if __name__ == "__main__":
    main()
