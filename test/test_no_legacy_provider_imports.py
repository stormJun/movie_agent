import ast
import unittest
from pathlib import Path


class TestNoLegacyProviderImports(unittest.TestCase):
    def test_no_backend_code_imports_legacy_provider_modules(self) -> None:
        """
        Guardrail: once providers are established, backend code should not import
        legacy provider modules directly (they are shims with DeprecationWarning).
        """
        repo_root = Path(__file__).resolve().parents[1]
        backend_root = repo_root / "backend"

        legacy = {
            "infrastructure.cache",
            "infrastructure.neo4jdb",
            "infrastructure.vector_store",
            "infrastructure.graph_documents",
            "infrastructure.gds",
        }

        shim_files = {
            repo_root / "backend" / "infrastructure" / "cache.py",
            repo_root / "backend" / "infrastructure" / "neo4jdb.py",
            repo_root / "backend" / "infrastructure" / "vector_store.py",
            repo_root / "backend" / "infrastructure" / "graph_documents.py",
            repo_root / "backend" / "infrastructure" / "gds.py",
        }

        offenders: list[str] = []
        for py_file in sorted(backend_root.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            if py_file in shim_files:
                continue

            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in legacy:
                            offenders.append(f"{py_file.relative_to(repo_root)}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        continue
                    if node.module in legacy:
                        offenders.append(f"{py_file.relative_to(repo_root)}: from {node.module} import ...")

        self.assertFalse(
            offenders,
            msg=(
                "Found imports of legacy provider modules. Use `infrastructure.providers.*` instead.\n"
                + "\n".join(offenders)
            ),
        )

