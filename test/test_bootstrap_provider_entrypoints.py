import ast
import unittest
from pathlib import Path


class TestBootstrapProviderEntrypoints(unittest.TestCase):
    def test_bootstrap_imports_only_from_providers(self) -> None:
        """
        Guardrail: bootstrap should only wire ports from infrastructure.providers.*
        (and infra config overrides).

        This prevents "provider implementations" from drifting back into random
        infra modules and re-introducing multiple entrypoints.
        """
        repo_root = Path(__file__).resolve().parents[1]
        bootstrap = repo_root / "backend" / "infrastructure" / "bootstrap.py"
        tree = ast.parse(bootstrap.read_text(encoding="utf-8"), filename=str(bootstrap))

        offenders: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module is None:
                continue

            mod = node.module
            if mod.startswith("infrastructure.providers"):
                continue
            if mod.startswith("infrastructure.config"):
                continue
            if mod.startswith("graphrag_agent.ports"):
                continue

            # Allow future stdlib imports etc. Only flag infra imports outside providers/config.
            if mod.startswith("infrastructure."):
                offenders.append(f"from {mod} import ...")

        self.assertFalse(
            offenders,
            msg=(
                "bootstrap.py must import providers via `infrastructure.providers.*` only.\n"
                + "\n".join(offenders)
            ),
        )

