import builtins
import importlib
import sys
import unittest
from unittest.mock import patch


class TestAgentsImportHints(unittest.TestCase):
    def _import_with_missing_langchain(self, module_name: str) -> str:
        # Force a fresh import path for the target module.
        sys.modules.pop(module_name, None)

        orig_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            for blocked in ("langchain_core", "langgraph"):
                if name == blocked or name.startswith(blocked + "."):
                    raise ModuleNotFoundError(f"No module named '{blocked}'", name=blocked)
            return orig_import(name, globals, locals, fromlist, level)

        importlib.invalidate_caches()
        with patch.object(builtins, "__import__", new=fake_import):
            with self.assertRaises(ImportError) as ctx:
                importlib.import_module(module_name)
        return str(ctx.exception)

    def test_base_agent_import_hint(self):
        # v3: BaseAgent is retrieval-only and should not require langchain/langgraph at import time.
        sys.modules.pop("graphrag_agent.agents.base", None)

        orig_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            for blocked in ("langchain_core", "langgraph"):
                if name == blocked or name.startswith(blocked + "."):
                    raise ModuleNotFoundError(f"No module named '{blocked}'", name=blocked)
            return orig_import(name, globals, locals, fromlist, level)

        importlib.invalidate_caches()
        with patch.object(builtins, "__import__", new=fake_import):
            imported = importlib.import_module("graphrag_agent.agents.base")
        self.assertIsNotNone(imported)

    def test_graph_agent_import_hint(self):
        msg = self._import_with_missing_langchain("graphrag_agent.agents.graph_agent")
        self.assertIn("Optional dependencies required.", msg)
        self.assertIn("Missing: langchain_core", msg)


if __name__ == "__main__":
    unittest.main()
