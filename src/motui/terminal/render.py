"""SGR and OSC 8 rendering: the row model's byte path for a terminal.

This is the one boundary where a Line becomes bytes; the cache is keyed
on ``(line, mode)`` because both are values."""

from __future__ import annotations

from functools import lru_cache

from ..kernel.cell import Line, Segment
from ..kernel.style import RESET, ColorMode, sgr_prefix
from .ansi import hyperlink_close, hyperlink_open

__all__ = ["styled_line"]


def _segment_bytes(seg: Segment, prefix: str) -> str:
    """One segment's bytes: its style prefix, its text and its OSC 8 link pair."""
    if seg.link is None:
        return prefix + seg.text
    return prefix + hyperlink_open(seg.link) + seg.text + hyperlink_close()


@lru_cache(maxsize=4096)
def _styled_line(line: Line, mode: ColorMode) -> str:
    """The cached rendering behind :func:`styled_line`."""
    parts: list[str] = []
    for seg in line.segments:
        if not seg.text:
            continue  # a zero-width segment paints nothing at all
        if parts:
            parts.append(RESET)  # a clean slate: no attribute crosses a boundary
        parts.append(_segment_bytes(seg, sgr_prefix(seg.style, mode)))
    return "".join(parts) + RESET if parts else ""


def styled_line(line: Line, mode: ColorMode = "truecolor") -> str:
    """SGR-escaped rendering of ``line`` for capability ``mode``: a RESET
    between segments and OSC 8 pairs closed inside their own segment."""
    return _styled_line(line, mode)
