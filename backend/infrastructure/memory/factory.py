"""Memory store factory for creating memory store instances.

This factory provides a centralized way to create memory store implementations
based on configuration, following the Factory pattern for loose coupling.
"""

from __future__ import annotations

import logging
from typing import Literal

from application.ports.memory_store_port import MemoryStorePort
from infrastructure.config.settings import (
    MEM0_ADD_PATH,
    MEM0_API_KEY,
    MEM0_BASE_URL,
    MEM0_DELETE_PATH,
    MEM0_LIST_PATH,
    MEM0_SEARCH_PATH,
    MEM0_TIMEOUT_S,
    MEM0_USER_ID_HEADER,
    MEMORY_PROVIDER,
)

logger = logging.getLogger(__name__)

ProviderType = Literal["mem0", "postgres", "null", ""]


class MemoryStoreFactory:
    """Factory for creating memory store instances based on configuration."""

    @staticmethod
    def create(provider: ProviderType | None = None) -> MemoryStorePort:
        """Create a memory store instance based on the provider type.

        Args:
            provider: The provider type ('mem0', 'postgres', 'null', or None).
                     If None, reads from MEMORY_PROVIDER environment variable.

        Returns:
            A MemoryStorePort implementation.

        Raises:
            ValueError: If an unsupported provider is specified.
        """
        if provider is None:
            provider = MEMORY_PROVIDER  # type: ignore[assignment]

        provider = (provider or "").strip().lower()

        match provider:
            case "mem0":
                from infrastructure.memory.mem0_http_memory_store import (
                    Mem0HttpMemoryStore,
                )

                if not MEM0_BASE_URL:
                    logger.warning(
                        "MEMORY_PROVIDER=mem0 but MEM0_BASE_URL is not set; "
                        "falling back to NullMemoryStore"
                    )
                    from infrastructure.memory.null_memory_store import (
                        NullMemoryStore,
                    )

                    return NullMemoryStore()

                return Mem0HttpMemoryStore(
                    base_url=MEM0_BASE_URL,
                    api_key=MEM0_API_KEY,
                    timeout_s=MEM0_TIMEOUT_S,
                    search_path=MEM0_SEARCH_PATH,
                    add_path=MEM0_ADD_PATH,
                    list_path=MEM0_LIST_PATH,
                    delete_path=MEM0_DELETE_PATH,
                    user_id_header=MEM0_USER_ID_HEADER,
                )

            case "postgres":
                # TODO: Implement PostgresMemoryStore with pgvector
                from infrastructure.memory.null_memory_store import NullMemoryStore

                logger.warning(
                    "PostgresMemoryStore is not yet implemented; "
                    "falling back to NullMemoryStore"
                )
                return NullMemoryStore()

            case "null" | "":
                from infrastructure.memory.null_memory_store import NullMemoryStore

                return NullMemoryStore()

            case _:
                raise ValueError(
                    f"Unsupported MEMORY_PROVIDER: {provider!r}. "
                    f"Supported values: 'mem0', 'postgres', 'null'"
                )


def create_memory_store(provider: ProviderType | None = None) -> MemoryStorePort:
    """Convenience function for creating a memory store.

    This is a shorthand for MemoryStoreFactory.create().
    """
    return MemoryStoreFactory.create(provider)
