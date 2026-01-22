import sys
import unittest
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from domain.memory import MemoryItem
from domain.memory.policy import MemoryPolicy, build_memory_context, extract_memory_candidates


class TestMemoryPolicy(unittest.TestCase):
    def test_build_memory_context_filters_and_truncates(self) -> None:
        items = [
            MemoryItem(id="1", text="A" * 1000, score=0.9),
            MemoryItem(id="2", text="B" * 1000, score=0.8),
            MemoryItem(id="3", text="C" * 1000, score=0.1),
        ]
        ctx = build_memory_context(memories=items, policy=MemoryPolicy(top_k=10, min_score=0.5, max_chars=300))
        self.assertIsInstance(ctx, str)
        self.assertLessEqual(len(ctx or ""), 310)  # allow trailing newline
        self.assertIn("A", ctx)
        self.assertNotIn("C" * 10, ctx)

    def test_extract_memory_candidates_is_conservative(self) -> None:
        self.assertTrue(extract_memory_candidates(user_message="我喜欢科幻电影"))
        self.assertTrue(extract_memory_candidates(user_message="I like sci-fi movies"))
        self.assertFalse(extract_memory_candidates(user_message="今天北京天气怎么样？"))

