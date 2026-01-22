from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

_DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "kb_routing.yaml"
_RULES_CACHE: Dict[str, Any] | None = None
KB_ROUTING_RULES_PATH_ENV = "KB_ROUTING_RULES_PATH"
KB_ROUTING_RULES_RELOAD_ENV = "KB_ROUTING_RULES_RELOAD"


def _load_rules(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _normalize_rules(data: Dict[str, Any]) -> Dict[str, Any]:
    rules = data.get("heuristic_rules", {})
    if not isinstance(rules, dict):
        return {}

    min_score = rules.get("min_score", 2)
    try:
        min_score = int(min_score)
    except (TypeError, ValueError):
        min_score = 2
    if min_score < 1:
        min_score = 1

    normalized_kbs: Dict[str, Any] = {}
    raw_kbs = rules.get("kbs", {})
    if isinstance(raw_kbs, dict):
        for kb_name, kb_rules in raw_kbs.items():
            if not isinstance(kb_rules, dict):
                continue
            keywords = kb_rules.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = []
            cleaned_keywords = [
                kw.strip() for kw in keywords if isinstance(kw, str) and kw.strip()
            ]
            normalized_kbs[kb_name] = {"keywords": cleaned_keywords}

    return {"heuristic_rules": {"min_score": min_score, "kbs": normalized_kbs}}


def _resolve_rules_path(path: Path | None) -> Path:
    if path is not None:
        return path
    env_path = os.getenv(KB_ROUTING_RULES_PATH_ENV)
    if env_path:
        return Path(env_path).expanduser()
    return _DEFAULT_RULES_PATH


def _should_reload(reload: bool | None) -> bool:
    if reload is not None:
        return reload
    env_value = os.getenv(KB_ROUTING_RULES_RELOAD_ENV, "").strip().lower()
    return env_value in {"1", "true", "yes", "on"}


def load_kb_routing_rules(path: Path | None = None) -> Dict[str, Any]:
    resolved_path = _resolve_rules_path(path)
    return _normalize_rules(_load_rules(resolved_path))


def get_kb_routing_rules(
    reload: bool | None = None,
    path: Path | None = None,
) -> Dict[str, Any]:
    global _RULES_CACHE
    if _RULES_CACHE is None or _should_reload(reload):
        _RULES_CACHE = load_kb_routing_rules(path)
    return _RULES_CACHE


__all__ = [
    "load_kb_routing_rules",
    "get_kb_routing_rules",
    "KB_ROUTING_RULES_PATH_ENV",
    "KB_ROUTING_RULES_RELOAD_ENV",
]
