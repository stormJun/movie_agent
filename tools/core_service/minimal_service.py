from __future__ import annotations

"""
Minimal HTTP service example for Phase 2.5.

Goal: demonstrate a tiny service boundary that can be extracted later.
This example intentionally avoids binding any real providers (Neo4j/LLM).

Run:
  .venv/bin/python tools/core_service/minimal_service.py
"""

import sys
from pathlib import Path

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="GraphRAG Core (Minimal)", version="0.0.0")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if _BACKEND_ROOT.exists() and str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/core/import")
def core_import() -> dict[str, str]:
    # Only import checks; no provider binding and no network calls.
    import graphrag_agent  # noqa: F401

    from graphrag_agent import ports  # noqa: F401

    return {"status": "ok", "message": "graphrag_agent importable"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8010, log_level="info")
