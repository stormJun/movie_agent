import ast
import unittest
from pathlib import Path


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _find_forbidden_imports(py_file: Path, forbidden_roots: tuple[str, ...]) -> list[str]:
    """
    Static guardrail: enforce layer boundaries regardless of installed optional deps.

    We use AST parsing (not regex) to avoid false positives from comments/strings.
    """
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except SyntaxError as exc:
        return [f"SyntaxError while parsing {py_file}: {exc}"]

    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith(forbidden_roots):
                    offenders.append(f"import {name}")
        elif isinstance(node, ast.ImportFrom):
            # Relative import (module=None) is always within the package boundary.
            if node.module is None:
                continue
            mod = node.module
            if mod.startswith(forbidden_roots):
                offenders.append(f"from {mod} import ...")

    return offenders


class TestLayerBoundaryImports(unittest.TestCase):
    def test_core_does_not_import_service_layers(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        core_root = repo_root / "backend" / "graphrag_agent"
        self.assertTrue(core_root.exists(), msg=f"Expected core dir: {core_root}")

        forbidden = ("infrastructure", "server", "application", "domain")
        violations: list[str] = []
        for py_file in _iter_py_files(core_root):
            offenders = _find_forbidden_imports(py_file, forbidden)
            if offenders:
                violations.append(f"{py_file.relative_to(repo_root)}: {offenders}")

        self.assertFalse(
            violations,
            msg=(
                "Core (`backend/graphrag_agent`) must not import service layers "
                "(server/application/domain/infrastructure).\n"
                + "\n".join(violations)
            ),
        )

    def test_domain_does_not_import_infra_or_server(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        domain_root = repo_root / "backend" / "domain"
        self.assertTrue(domain_root.exists(), msg=f"Expected domain dir: {domain_root}")

        forbidden = ("infrastructure", "server")
        violations: list[str] = []
        for py_file in _iter_py_files(domain_root):
            offenders = _find_forbidden_imports(py_file, forbidden)
            if offenders:
                violations.append(f"{py_file.relative_to(repo_root)}: {offenders}")

        self.assertFalse(
            violations,
            msg=(
                "Domain (`backend/domain`) must not import infrastructure/server.\n"
                + "\n".join(violations)
            ),
        )

    def test_application_does_not_import_server(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        app_root = repo_root / "backend" / "application"
        self.assertTrue(app_root.exists(), msg=f"Expected application dir: {app_root}")

        forbidden = ("server",)
        violations: list[str] = []
        for py_file in _iter_py_files(app_root):
            offenders = _find_forbidden_imports(py_file, forbidden)
            if offenders:
                violations.append(f"{py_file.relative_to(repo_root)}: {offenders}")

        self.assertFalse(
            violations,
            msg=(
                "Application (`backend/application`) must not import server.\n"
                + "\n".join(violations)
            ),
        )

