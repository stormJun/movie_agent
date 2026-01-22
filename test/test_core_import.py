import unittest


class TestCoreImport(unittest.TestCase):
    def test_import_graphrag_agent(self):
        # Phase2.5: core should be importable without referencing `backend.`.
        import graphrag_agent  # noqa: F401

    def test_import_ports_without_providers(self):
        # Ports should not crash at import time (providers may be configured later).
        from graphrag_agent import ports  # noqa: F401

        from graphrag_agent.ports import models, neo4jdb, vector_store  # noqa: F401


if __name__ == "__main__":
    unittest.main()
