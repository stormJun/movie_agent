import unittest
from unittest.mock import patch


class TestLazyImportHints(unittest.TestCase):
    def test_search_lazy_import_optional_dep_hint(self):
        import graphrag_agent.search as search

        search.__dict__.pop("LocalSearch", None)
        with patch.object(
            search,
            "import_module",
            side_effect=ModuleNotFoundError("No module named pandas", name="pandas"),
        ):
            with self.assertRaises(ImportError) as ctx:
                _ = search.LocalSearch
        self.assertIn("Optional dependencies required.", str(ctx.exception))
        self.assertIn("Missing: pandas", str(ctx.exception))

    def test_search_lazy_import_internal_missing_not_wrapped(self):
        import graphrag_agent.search as search

        search.__dict__.pop("LocalSearch", None)
        with patch.object(
            search,
            "import_module",
            side_effect=ModuleNotFoundError(
                "No module named graphrag_agent.search.local_search",
                name="graphrag_agent.search.local_search",
            ),
        ):
            with self.assertRaises(ModuleNotFoundError):
                _ = search.LocalSearch

    def test_graph_lazy_import_optional_dep_hint(self):
        import graphrag_agent.graph as graph

        graph.__dict__.pop("EntityRelationExtractor", None)
        with patch.object(
            graph,
            "import_module",
            side_effect=ModuleNotFoundError("No module named neo4j", name="neo4j"),
        ):
            with self.assertRaises(ImportError) as ctx:
                _ = graph.EntityRelationExtractor
        self.assertIn("Optional dependencies required.", str(ctx.exception))
        self.assertIn("Missing: neo4j", str(ctx.exception))

    def test_community_lazy_import_optional_dep_hint(self):
        import graphrag_agent.community as community

        community.__dict__.pop("CommunityDetectorFactory", None)
        with patch.object(
            community,
            "import_module",
            side_effect=ModuleNotFoundError("No module named numpy", name="numpy"),
        ):
            with self.assertRaises(ImportError) as ctx:
                _ = community.CommunityDetectorFactory
        self.assertIn("Optional dependencies required.", str(ctx.exception))
        self.assertIn("Missing: numpy", str(ctx.exception))

    def test_search_tool_pkg_lazy_import_optional_dep_hint(self):
        import graphrag_agent.search.tool as tool_pkg

        tool_pkg.__dict__.pop("LocalSearchTool", None)
        with patch.object(
            tool_pkg,
            "import_module",
            side_effect=ModuleNotFoundError("No module named langchain", name="langchain"),
        ):
            with self.assertRaises(ImportError) as ctx:
                _ = tool_pkg.LocalSearchTool
        self.assertIn("Optional dependencies required.", str(ctx.exception))
        self.assertIn("Missing: langchain", str(ctx.exception))

    def test_graph_processing_pkg_lazy_import_optional_dep_hint(self):
        import graphrag_agent.graph.processing as processing

        processing.__dict__.pop("EntityMerger", None)
        with patch.object(
            processing,
            "import_module",
            side_effect=ModuleNotFoundError("No module named langchain", name="langchain"),
        ):
            with self.assertRaises(ImportError) as ctx:
                _ = processing.EntityMerger
        self.assertIn("Optional dependencies required.", str(ctx.exception))
        self.assertIn("Missing: langchain", str(ctx.exception))

    def test_community_detector_pkg_lazy_import_optional_dep_hint(self):
        import graphrag_agent.community.detector as detector

        detector.__dict__.pop("CommunityDetectorFactory", None)
        with patch.object(
            detector,
            "import_module",
            side_effect=ModuleNotFoundError("No module named neo4j", name="neo4j"),
        ):
            with self.assertRaises(ImportError) as ctx:
                _ = detector.CommunityDetectorFactory
        self.assertIn("Optional dependencies required.", str(ctx.exception))
        self.assertIn("Missing: neo4j", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
