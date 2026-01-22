import json
from typing import Optional


def normalize_kb_prefix(kb_prefix: Optional[str]) -> str:
    raw = (kb_prefix or "").strip()
    if raw.endswith(":"):
        raw = raw[:-1]
    return raw.strip()


def parse_loose_json_dict(text: str) -> Optional[dict]:
    raw = (text or "").strip()
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or start >= end:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None

