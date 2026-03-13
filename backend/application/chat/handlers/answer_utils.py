from __future__ import annotations

from dataclasses import dataclass


_CITATION_MARKERS = ("#### 引用数据", "### 引用数据", "引用数据")


def _find_marker(text: str) -> int:
    idx = -1
    for marker in _CITATION_MARKERS:
        pos = text.find(marker)
        if pos == -1:
            continue
        if idx == -1 or pos < idx:
            idx = pos
    return idx


def strip_citation_block(text: str) -> str:
    """Strip the trailing citation block from user-facing answers."""
    if not isinstance(text, str) or not text.strip():
        return text

    # Prefer explicit headings; fall back to a generic marker only near the end.
    idx = _find_marker(text)
    if idx == -1:
        marker = "引用数据"
        pos = text.rfind(marker)
        if pos != -1 and pos >= max(len(text) - 2000, 0):
            idx = pos

    if idx == -1:
        return text
    return text[:idx].rstrip()


@dataclass
class CitationStreamStripper:
    """Stateful streaming filter that drops the trailing citation block."""

    pending: str = ""
    cut: bool = False

    def __post_init__(self) -> None:
        self._keep_len = max(len(m) for m in _CITATION_MARKERS) - 1

    def feed(self, chunk: str) -> str:
        if self.cut or not chunk:
            return ""
        self.pending += str(chunk)

        idx = _find_marker(self.pending)
        if idx != -1:
            out = self.pending[:idx]
            self.pending = ""
            self.cut = True
            return out

        if self._keep_len > 0 and len(self.pending) > self._keep_len:
            out = self.pending[: -self._keep_len]
            self.pending = self.pending[-self._keep_len :]
            return out

        return ""

    def flush(self) -> str:
        if self.cut:
            return ""
        out = self.pending
        self.pending = ""
        return out


__all__ = ["strip_citation_block", "CitationStreamStripper"]
