import ast
import unittest
from pathlib import Path


class TestInfrastructureShims(unittest.TestCase):
    def test_infrastructure_root_shims_are_thin_and_warn(self) -> None:
        """
        Guardrail: compatibility shims under `backend/infrastructure/*.py` that
        redirect to `infrastructure.providers.*` must stay thin and emit a
        DeprecationWarning.

        This prevents "real implementations" from drifting back into the old
        locations, and makes deprecations visible.
        """
        repo_root = Path(__file__).resolve().parents[1]
        infra_root = repo_root / "backend" / "infrastructure"

        # Only check top-level .py shims (not packages).
        candidates = sorted(p for p in infra_root.glob("*.py") if p.name != "__init__.py")

        offenders: list[str] = []
        for py_file in candidates:
            src = py_file.read_text(encoding="utf-8")
            if "from infrastructure.providers." not in src:
                continue

            tree = ast.parse(src, filename=str(py_file))

            if "DEPRECATED_REMOVE_MILESTONE" not in src:
                offenders.append(
                    f"{py_file.relative_to(repo_root)}: missing DEPRECATED_REMOVE_MILESTONE marker"
                )

            # Ensure there's a DeprecationWarning emitted.
            has_warn = False
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute):
                    continue
                if not isinstance(node.func.value, ast.Name):
                    continue
                if node.func.value.id != "warnings" or node.func.attr != "warn":
                    continue
                # Must pass DeprecationWarning as 2nd arg.
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Name) and node.args[1].id == "DeprecationWarning":
                    has_warn = True
                    break

            if not has_warn:
                offenders.append(f"{py_file.relative_to(repo_root)}: missing warnings.warn(..., DeprecationWarning)")

            # Ensure the shim doesn't import other infra modules (apart from providers).
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module is not None:
                    mod = node.module
                    if mod.startswith("infrastructure.providers"):
                        continue
                    if mod == "__future__":
                        continue
                    if mod.startswith("infrastructure."):
                        offenders.append(f"{py_file.relative_to(repo_root)}: imports {mod} (should only re-export providers)")

        self.assertFalse("SyntaxError" in "\n".join(offenders), msg="\n".join(offenders))
        self.assertFalse(offenders, msg="Shim guardrails violated:\n" + "\n".join(offenders))
