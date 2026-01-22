import ast
import unittest
from pathlib import Path


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _is_graphrag_agent_config_settings(expr: ast.AST) -> bool:
    """
    Match: graphrag_agent.config.settings

    This covers direct module-attribute usage like:
      graphrag_agent.config.settings.response_type
    """
    # graphrag_agent.config.settings
    if not isinstance(expr, ast.Attribute) or expr.attr != "settings":
        return False
    cfg = expr.value
    if not isinstance(cfg, ast.Attribute) or cfg.attr != "config":
        return False
    root = cfg.value
    return isinstance(root, ast.Name) and root.id == "graphrag_agent"


class TestSemanticBridgeGuardrail(unittest.TestCase):
    def test_infrastructure_reads_response_type_via_semantics_bridge(self) -> None:
        """
        Guardrail: Infra components must not read `response_type` directly from core
        settings (`graphrag_agent.config.settings`). They should use the explicit
        semantic bridge: `infrastructure.config.semantics.get_response_type()`.

        Rationale:
        - RESPONSE_TYPE is a "semantic" config (backend/config/rag_semantics.py)
        - Infra should not couple itself to where semantics come from
        - A single bridge makes it obvious where to change semantics wiring later
        """
        repo_root = Path(__file__).resolve().parents[1]
        infra_root = repo_root / "backend" / "infrastructure"

        allowlist = {
            infra_root / "config" / "semantics.py",
            infra_root / "config" / "graphrag_settings.py",
        }

        offenders: list[str] = []
        for py_file in _iter_py_files(infra_root):
            if py_file in allowlist:
                continue

            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

            # Track aliases that refer to `graphrag_agent.config.settings`.
            core_settings_aliases: set[str] = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    # from graphrag_agent.config.settings import response_type
                    if node.module == "graphrag_agent.config.settings":
                        for alias in node.names:
                            if alias.name == "response_type" or alias.name == "*":
                                offenders.append(
                                    f"{py_file.relative_to(repo_root)}:{getattr(node, 'lineno', 1)}"
                                )

                    # from graphrag_agent.config import settings as core_settings
                    if node.module == "graphrag_agent.config":
                        for alias in node.names:
                            if alias.name == "settings":
                                core_settings_aliases.add(alias.asname or alias.name)

                elif isinstance(node, ast.Import):
                    # import graphrag_agent.config.settings as core_settings
                    for alias in node.names:
                        if alias.name == "graphrag_agent.config.settings":
                            core_settings_aliases.add(alias.asname or "graphrag_agent")

            # Detect direct reads:
            # - settings_alias.response_type
            # - graphrag_agent.config.settings.response_type
            for node in ast.walk(tree):
                if not isinstance(node, ast.Attribute) or node.attr != "response_type":
                    continue

                if isinstance(node.value, ast.Name) and node.value.id in core_settings_aliases:
                    offenders.append(
                        f"{py_file.relative_to(repo_root)}:{getattr(node, 'lineno', 1)}"
                    )
                    continue

                if _is_graphrag_agent_config_settings(node.value):
                    offenders.append(
                        f"{py_file.relative_to(repo_root)}:{getattr(node, 'lineno', 1)}"
                    )

        self.assertFalse(
            offenders,
            msg=(
                "Infra must read semantic `response_type` via "
                "`infrastructure.config.semantics.get_response_type()`.\n"
                "Direct access to `graphrag_agent.config.settings.response_type` is forbidden.\n"
                + "\n".join(offenders)
            ),
        )

