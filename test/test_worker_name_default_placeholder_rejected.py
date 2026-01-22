import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest


class TestWorkerNameDefaultPlaceholderRejected(unittest.TestCase):
    def test_get_agent_for_worker_name_rejects_default_kb_prefix(self) -> None:
        # v3 strict: RouterGraph no longer emits "default:*" placeholder names.
        # If they still appear, treat them as a hard error so we don't silently
        # hit the wrong KB or leak caches across KBs.
        from infrastructure.routing.orchestrator.worker_registry import get_agent_for_worker_name

        with self.assertRaises(ValueError):
            get_agent_for_worker_name(
                worker_name="default:hybrid_agent:retrieve_only",
                session_id="s1",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

