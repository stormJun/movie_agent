import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest
from pathlib import Path


class TestBackendLayout(unittest.TestCase):
    def test_backend_code_is_scoped_under_backend_dir(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        # Guard-rail: backend code should not drift back to repo root.
        banned_root_dirs = [
            "server",
            "application",
            "domain",
            "infrastructure",
            "graphrag_agent",
            "rag_layer",
        ]
        found = [name for name in banned_root_dirs if (repo_root / name).exists()]
        self.assertFalse(
            found,
            msg=(
                "Backend packages must live under `backend/`. "
                f"Found unexpected root-level directories: {found}"
            ),
        )

