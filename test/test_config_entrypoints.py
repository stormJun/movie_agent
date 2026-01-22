import ast
import unittest
from pathlib import Path


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _imports_module(tree: ast.AST, module: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module or alias.name.startswith(module + "."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.module == module or node.module.startswith(module + "."):
                return True
    return False


class TestConfigEntrypoints(unittest.TestCase):
    def test_infrastructure_does_not_import_service_config(self) -> None:
        """
        Guardrail: infrastructure should not import `config.*` (service-side config),
        otherwise devs won't know which config folder is authoritative.

        Exception: infra config can read semantic defaults from `config.rag_semantics`
        to build core overrides.
        """
        repo_root = Path(__file__).resolve().parents[1]
        infra_root = repo_root / "backend" / "infrastructure"

        allowlist = {
            infra_root / "config" / "graphrag_settings.py",
        }

        offenders: list[str] = []
        for py_file in _iter_py_files(infra_root):
            if py_file in allowlist:
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            if _imports_module(tree, "config"):
                offenders.append(str(py_file.relative_to(repo_root)))

        self.assertFalse(
            offenders,
            msg=(
                "Infrastructure must not import service config (`config.*`). "
                "Use `infrastructure.config.*` (infra env/path) or pass values in explicitly.\n"
                + "\n".join(offenders)
            ),
        )

    def test_server_and_application_do_not_import_infra_config(self) -> None:
        """
        Guardrail: API/application layers must not directly depend on infra config
        (env/path/overrides). They should use service config (`config.*`) and ports.
        """
        repo_root = Path(__file__).resolve().parents[1]
        roots = [
            repo_root / "backend" / "server",
            repo_root / "backend" / "application",
        ]

        offenders: list[str] = []
        for root in roots:
            for py_file in _iter_py_files(root):
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                if _imports_module(tree, "infrastructure.config"):
                    offenders.append(str(py_file.relative_to(repo_root)))

        self.assertFalse(
            offenders,
            msg=(
                "server/application must not import `infrastructure.config.*`. "
                "Use `config.*` and have infrastructure bootstrap providers.\n"
                + "\n".join(offenders)
            ),
        )

