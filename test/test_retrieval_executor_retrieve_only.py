import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest


from graphrag_agent.agents.multi_agent.executor.retrieval_executor import (
    RetrievalExecutor,
)


class _DummyTool:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def structured_search(self, _payload):  # pragma: no cover
        self.calls.append("structured_search")
        raise AssertionError("structured_search should not be called in prefer_retrieve_only mode")

    def retrieve_only(self, _payload):
        self.calls.append("retrieve_only")
        return {"context": "ctx", "retrieval_results": [{"evidence": "e"}]}


class _DummyToolStructuredFirst:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def structured_search(self, _payload):
        self.calls.append("structured_search")
        return {"answer": "structured", "retrieval_results": []}

    def retrieve_only(self, _payload):  # pragma: no cover
        self.calls.append("retrieve_only")
        raise AssertionError("retrieve_only should not be called when prefer_retrieve_only is False")


class TestRetrievalExecutorRetrieveOnly(unittest.TestCase):
    def test_prefer_retrieve_only_calls_retrieve_only_and_injects_answer(self):
        executor = RetrievalExecutor(prefer_retrieve_only=True)
        tool = _DummyTool()
        payload = executor._invoke_tool(tool, "local_search", {"query": "q"})
        self.assertIn("retrieve_only", tool.calls)
        self.assertNotIn("structured_search", tool.calls)
        self.assertEqual(payload.get("context"), "ctx")
        self.assertEqual(payload.get("answer"), "ctx")

    def test_default_prefers_structured_search(self):
        executor = RetrievalExecutor(prefer_retrieve_only=False)
        tool = _DummyToolStructuredFirst()
        payload = executor._invoke_tool(tool, "local_search", {"query": "q"})
        self.assertIn("structured_search", tool.calls)
        self.assertNotIn("retrieve_only", tool.calls)
        self.assertEqual(payload.get("answer"), "structured")


if __name__ == "__main__":
    unittest.main()

