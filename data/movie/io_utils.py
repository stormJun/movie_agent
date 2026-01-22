import json
from pathlib import Path
from typing import Any


def save_json(data: Any, output_path: Path) -> None:
    """保存为 JSON 文件（UTF-8, pretty）。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
