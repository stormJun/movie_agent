from __future__ import annotations

from infrastructure.config.graphrag_settings import apply_core_settings_overrides

from graphrag_agent.ports import (
    set_graph_document_provider,
    set_gds_provider,
    set_model_provider,
    set_neo4j_provider,
    set_vector_store_provider,
)


def bootstrap_core_ports() -> None:
    """Wire infrastructure providers into graphrag_agent ports."""
    # Apply infra-side env/path overrides before importing any infra modules.
    apply_core_settings_overrides()

    from infrastructure.providers import graph_documents as infra_graph_documents
    from infrastructure.providers import gds as infra_gds
    from infrastructure.providers import models as infra_models
    from infrastructure.providers import neo4jdb as infra_neo4jdb
    from infrastructure.providers import vector_store as infra_vector_store

    set_graph_document_provider(infra_graph_documents)
    set_gds_provider(infra_gds)
    set_model_provider(infra_models)
    set_neo4j_provider(infra_neo4jdb)
    set_vector_store_provider(infra_vector_store)
