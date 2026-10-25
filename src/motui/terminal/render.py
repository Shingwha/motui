"""SGR and OSC 8 rendering: the row model's byte path for a terminal.

The kernel's :class:`~motui.kernel.cell.Line` is a pure value and builds no
terminal bytes.  This module is the one boundary where a row becomes bytes:
``styled_line(line, mode)`` renders the row for a terminal capability, with
the same RESET discipline and OSC 8 pairing the 1.x ``Line.styled`` always
had.  The answer depends on the terminal's capability, so the module-level
cache is keyed on ``(line, mode)`` -- a row and the mode are both values, and
a line is immutable.

The truecolor path is byte-for-byte the old cached rendering (each segment's
own cached ``Style.prefix()``); a downgraded mode resolves each prefix
through :func:`~motui.kernel.style.sgr_prefix` instead.
"""

from __future__ import annotations

from functools import lru_cache

from ..kernel.cell import Line, Segment
from ..kernel.style import RESET, ColorMode, sgr_prefix
from .ansi import hyperlink_close, hyperlink_open

__all__ = ["styled_line"]


def _segment_bytes(seg: Segment, prefix: str) -> str:
    """One segment's rendered bytes: its style prefix, its text and its link.

    A segment with a ``link`` has its text wrapped in the OSC 8 pair --
    ``prefix open text close`` -- so the terminal paints a real hyperlink
    over exactly the run the segment owns; the pair sits inside the SGR
    prefix's scope and is closed before the next segment's RESET, never
    leaking the link over a neighbour.  A segment without one renders
    ``prefix + text``, byte-for-byte what it always did.
    """
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
    """SGR-escaped rendering of ``line`` for a terminal of capability ``mode``.

    Every segment after the first non-empty one is preceded by a RESET,
    because SGR is a state machine and a prefix only *adds* attributes; a
    zero-width segment paints nothing and opens no reset; a trailing RESET
    closes the row.  A segment carrying a ``link`` wraps its own text in the
    OSC 8 pair, which is closed inside the segment so no hyperlink crosses a
    boundary.  ``"truecolor"`` resolves each segment through its own cached
    ``Style.prefix()``; the downgraded modes go through
    :func:`~motui.kernel.style.sgr_prefix`, and the answer is cached per
    ``(line, mode)`` because a line is a value.
    """
    return _styled_line(line, mode)
