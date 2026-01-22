import ast
import unittest
from pathlib import Path


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )


class TestSemanticEnvAccessGuardrail(unittest.TestCase):
    def test_response_type_env_is_only_read_in_rag_semantics(self) -> None:
        """
        Guardrail: RESPONSE_TYPE is a semantic config knob. It must be read from
        env in exactly one place: `backend/config/rag_semantics.py`.

        Everything else should consume it via:
        - core settings (`graphrag_agent.config.settings.response_type`) inside core, or
        - infra semantic bridge (`infrastructure.config.semantics.get_response_type()`).
        """
        repo_root = Path(__file__).resolve().parents[1]
        backend_root = repo_root / "backend"

        allowed = {
            backend_root / "config" / "rag_semantics.py",
        }

        offenders: list[str] = []

        for py_file in _iter_py_files(backend_root):
            if py_file in allowed:
                continue

            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

            for node in ast.walk(tree):
                # os.getenv("RESPONSE_TYPE", ...)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                        and node.func.attr == "getenv"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == "RESPONSE_TYPE"
                    ):
                        offenders.append(
                            f"{py_file.relative_to(repo_root)}:{getattr(node, 'lineno', 1)}"
                        )

                # os.environ.get("RESPONSE_TYPE", ...)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if (
                        node.func.attr == "get"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == "RESPONSE_TYPE"
                        and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr == "environ"
                        and isinstance(node.func.value.value, ast.Name)
                        and node.func.value.value.id == "os"
                    ):
                        offenders.append(
                            f"{py_file.relative_to(repo_root)}:{getattr(node, 'lineno', 1)}"
                        )

                # os.environ["RESPONSE_TYPE"]
                if isinstance(node, ast.Subscript):
                    target = node.value
                    if (
                        isinstance(target, ast.Attribute)
                        and target.attr == "environ"
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "os"
                    ):
                        # Python 3.10 ast uses Constant for string index
                        idx = node.slice
                        if isinstance(idx, ast.Constant) and idx.value == "RESPONSE_TYPE":
                            offenders.append(
                                f"{py_file.relative_to(repo_root)}:{getattr(node, 'lineno', 1)}"
                            )

        self.assertFalse(
            offenders,
            msg=(
                "RESPONSE_TYPE must be read from env only in `backend/config/rag_semantics.py`.\n"
                + "\n".join(offenders)
            ),
        )

