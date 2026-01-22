import builtins
import importlib
import sys
import unittest
from unittest.mock import patch


class TestToolRegistryLazyImport(unittest.TestCase):
    def test_import_tool_registry_without_optional_deps(self):
        # Simulate a core-only environment: tool_registry import must not require optional deps.
        sys.modules.pop("graphrag_agent.search.tool_registry", None)

        orig_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            for blocked in ("langchain_core", "langgraph", "numpy", "pandas", "neo4j"):
                if name == blocked or name.startswith(blocked + "."):
                    raise ModuleNotFoundError(f"No module named '{blocked}'", name=blocked)
            return orig_import(name, globals, locals, fromlist, level)

        importlib.invalidate_caches()
        with patch.object(builtins, "__import__", new=fake_import):
            tool_registry = importlib.import_module("graphrag_agent.search.tool_registry")

        self.assertIn("local_search", tool_registry.TOOL_REGISTRY)

    def test_instantiating_tool_raises_helpful_importerror(self):
        import graphrag_agent.search.tool_registry as tool_registry

        # Force factory to try importing a concrete tool without optional deps.
        orig_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            for blocked in ("pandas", "langchain_core"):
                if name == blocked or name.startswith(blocked + "."):
                    raise ModuleNotFoundError(f"No module named '{blocked}'", name=blocked)
            return orig_import(name, globals, locals, fromlist, level)

        with patch.object(builtins, "__import__", new=fake_import):
            with self.assertRaises(ImportError) as ctx:
                _ = tool_registry.TOOL_REGISTRY["local_search"]()

        self.assertIn("Optional dependencies required.", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
