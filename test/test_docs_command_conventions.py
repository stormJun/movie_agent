import re
import unittest
from pathlib import Path


class TestDocsCommandConventions(unittest.TestCase):
    def test_docs_do_not_embed_legacy_backend_commands(self) -> None:
        """
        Guardrail: documentation should not hand-write legacy backend command variants.

        Rationale:
        - Backend sources live under `backend/`, and docs were drifting with inconsistent
          `PYTHONPATH=backend ...` snippets.
        - We standardize command entrypoints via scripts:
          - dev:  `bash scripts/dev.sh backend`
          - build: `bash scripts/py.sh <module>`
          - tests: `bash scripts/test.sh` / `bash scripts/ut.sh ...`

        This test intentionally only checks docs/markdown so it won't block legitimate
        code/scripts usage.
        """
        repo_root = Path(__file__).resolve().parents[1]
        roots = [
            repo_root / "docs",
            repo_root / "assets",
            repo_root / "tools",
            repo_root,  # for top-level *.md like readme.md/AGENTS.md/CLAUDE.md
        ]

        md_files: list[Path] = []
        for root in roots:
            if not root.exists():
                continue
            if root == repo_root:
                md_files.extend(sorted(root.glob("*.md")))
            else:
                md_files.extend(sorted(p for p in root.rglob("*.md") if ".git" not in p.parts))

        banned_patterns: list[tuple[str, re.Pattern[str]]] = [
            (
                "Do not embed `PYTHONPATH=backend <cmd>` in docs; use scripts/*.sh wrappers",
                re.compile(r"PYTHONPATH=backend\\s+(python3?|uvicorn|gunicorn)\\b"),
            ),
            (
                "Do not embed `python -m infrastructure.integrations...` in docs; use scripts/py.sh",
                re.compile(r"\\bpython3?\\s+-m\\s+infrastructure\\.integrations\\b"),
            ),
            (
                "Do not embed `python -m unittest discover test -v` in docs; use scripts/test.sh or scripts/ut.sh",
                re.compile(r"\\bpython3?\\s+-m\\s+unittest\\s+discover\\s+test\\s+-v\\b"),
            ),
            (
                "Do not embed `python -m server.main` in docs; use scripts/dev.sh backend",
                re.compile(r"\\bpython3?\\s+-m\\s+server\\.main\\b"),
            ),
        ]

        offenders: list[str] = []
        for md in md_files:
            text = md.read_text(encoding="utf-8", errors="replace")
            for msg, pat in banned_patterns:
                for m in pat.finditer(text):
                    # Compute 1-based line number quickly.
                    lineno = text.count("\n", 0, m.start()) + 1
                    offenders.append(f"{md.relative_to(repo_root)}:{lineno}: {msg}")

        self.assertFalse(
            offenders,
            msg="Legacy command variants found in docs (should use scripts/* wrappers):\n"
            + "\n".join(offenders),
        )

