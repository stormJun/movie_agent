import ast
import unittest
from pathlib import Path


class TestDotenvPolicy(unittest.TestCase):
    def test_load_dotenv_is_only_used_in_config_entrypoints_with_override_true(self) -> None:
        """
        Guardrail: `.env` loading policy must be centralized and consistent.

        - Only config entrypoints may call `load_dotenv(...)`
        - Must use `override=True` to avoid "I changed .env but nothing happened"
        """
        repo_root = Path(__file__).resolve().parents[1]
        backend_root = repo_root / "backend"

        allowed = {
            backend_root / "config" / "settings.py",
            backend_root / "config" / "rag_semantics.py",
            backend_root / "infrastructure" / "config" / "settings.py",
            backend_root / "infrastructure" / "config" / "graphrag_settings.py",
        }

        offenders: list[str] = []

        for py_file in sorted(backend_root.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue

            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                # Match `load_dotenv(...)`
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name != "load_dotenv":
                    continue

                if py_file not in allowed:
                    offenders.append(
                        f"{py_file.relative_to(repo_root)}: load_dotenv() must only appear in config entrypoints"
                    )
                    continue

                # Ensure override=True is present (positional or keyword).
                has_override_true = False
                for kw in node.keywords:
                    if kw.arg == "override" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        has_override_true = True
                        break

                if not has_override_true:
                    offenders.append(
                        f"{py_file.relative_to(repo_root)}: load_dotenv() must use override=True"
                    )

        self.assertFalse(offenders, msg="Dotenv policy violations:\n" + "\n".join(offenders))

