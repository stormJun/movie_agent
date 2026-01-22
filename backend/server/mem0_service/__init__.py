"""Self-hosted mem0-compatible service (optional).

This module exposes a small subset of mem0 HTTP API used by this repo:
- POST /v1/memories
- POST /v1/memories/search

It is intended for local/self-hosted deployments where you want to run a
"mem0-like" service side-by-side with the GraphRAG backend.
"""

