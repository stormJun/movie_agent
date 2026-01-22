import json
from pathlib import Path
from typing import Any, Dict, Optional


def load_tmdb_cache(cache_file: Path) -> Optional[Dict[str, Any]]:
    """从缓存读取 TMDB JSON（不存在则返回 None）。"""
    if not cache_file.exists():
        return None
    with open(cache_file, "r", encoding="utf-8") as file:
        return json.load(file)


def save_tmdb_cache(data: Dict[str, Any], cache_file: Path) -> None:
    """写入 TMDB JSON 缓存（覆盖写）。"""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
