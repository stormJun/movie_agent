from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if _BACKEND_ROOT.exists() and str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from graphrag_agent.config.settings import kb_label_for_kb_prefix


app = FastAPI(title="GraphRAG Core Service Example")


def _bootstrap_backend_providers() -> None:
    """
    Monorepo helper: wire backend/infrastructure implementations into core ports.

    This keeps the example runnable now; for a standalone core service, replace
    this with service-local providers.
    """

    from infrastructure.bootstrap import bootstrap_core_ports
    from infrastructure.config.graphrag_settings import apply_core_settings_overrides

    apply_core_settings_overrides()
    bootstrap_core_ports()


@app.on_event("startup")
def _startup() -> None:
    try:
        _bootstrap_backend_providers()
    except Exception as exc:
        # Keep the service up for /health, but retrieval endpoints will fail.
        # This is useful when running without Neo4j/LLM configured.
        app.state.bootstrap_error = str(exc)


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "bootstrap_error": getattr(app.state, "bootstrap_error", None),
    }


@app.get("/v1/kb_label")
def kb_label(kb_prefix: str = "") -> dict:
    return {"kb_prefix": kb_prefix, "kb_label": kb_label_for_kb_prefix(kb_prefix)}


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    kb_prefix: str | None = None


@app.post("/v1/retrieve")
def retrieve(req: RetrieveRequest) -> dict:
    if getattr(app.state, "bootstrap_error", None):
        raise HTTPException(status_code=503, detail=f"bootstrap failed: {app.state.bootstrap_error}")

    try:
        from graphrag_agent.agents.fusion_agent import FusionGraphRAGAgent
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    agent = FusionGraphRAGAgent(kb_prefix=req.kb_prefix, agent_mode="retrieve_only")
    return agent.retrieve_with_trace(req.query)
