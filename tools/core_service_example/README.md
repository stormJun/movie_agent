# Core Service Example (GraphRAG Core)

This folder shows a minimal HTTP service wrapper around the **`graphrag_agent` core**.

It is intentionally small and uses the existing monorepo backend infrastructure as the
provider implementation (ports wiring). When you later extract `graphrag_agent` into a
separate service/repo, replace the backend providers with your own.

## Run (monorepo)

1) Create venv and install backend deps (includes langchain/neo4j stack):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r tools/core_service_example/requirements.txt
```

2) Configure `.env` (Neo4j + LLM keys) as in the backend.

3) Start:

```bash
uvicorn tools.core_service_example.app:app --reload --port 8010
```

## API

- `GET /health`
- `POST /v1/retrieve` (retrieve-only; returns evidence + reference)
- `GET /v1/kb_label?kb_prefix=movie:` (utility)

