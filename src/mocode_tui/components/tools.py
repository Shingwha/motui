"""Tool-call components: :class:`ToolBlock` and :class:`EditBlock`.

Band-framed blocks for the pi-style transcript: a tool call (title row,
output rows, timing footer) and an edit (path row, line-numbered context and
a ``-``/``+`` diff closed by an ``(edited)`` badge).  Both fill the full
width behind a one-cell left padding; :class:`ToolBlock` picks its band
color from ``tone``.  ``render`` is a pure function of the component and
``width``; every row is ``fit`` to ``width`` as a final guard.

The band constants below are defined here, not in
:mod:`mocode_tui.style` (that module is the frozen W1 layer); the
screenshot's dark green / near-black bands map onto the nearest named
16-colors (``green`` / ``black``) per the spec's honest exit note -- no
256-color or true-color escape is introduced.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..lines import Line, Segment
from ..style import ACCENT, ERROR, MUTED, NONE, SUCCESS, Style
from ..text import visible_width

__all__ = ["EditBlock", "ToolBlock"]

#: "tool" tone band: green background (nearest named 16-color to the
#: screenshot's dark green).
TOOL_BG = Style(bg="green")

#: "code" tone band -- and the :class:`EditBlock` band: near-black
#: background (the screenshot's dark code panels).
CODE_BG = Style(bg="black")

#: ToolBlock title emphasis: bold, merged onto the band.
_TITLE = Style(bold=True)

#: ToolBlock footer emphasis ("Took 0.1s"): dim italic, merged onto the band.
_FOOTER = MUTED.merge(Style(italic=True))

#: EditBlock badge emphasis: green bold, merged onto the band.
_EDITED = SUCCESS.merge(Style(bold=True))

#: ``tone`` -> band style; anything unknown degrades to ``plain``.
_TONES: dict[str, Style] = {"tool": TOOL_BG, "code": CODE_BG, "plain": NONE}


def _band_row(band: Style, width: int, parts: tuple[tuple[str, Style], ...]) -> Line:
    """One band row: a leading pad cell, the styled parts, then the fill.

    The leading cell and the closing fill carry ``band``, so the row reads
    as one continuous color.  ``width <= 0`` yields an empty row, and a row
    whose parts exceed ``width`` is ``fit`` (ellipsized) at the end.
    """
    segments: list[Segment] = []
    used = 0
    if width > 0:
        segments.append(Segment(" ", band))
        used = 1
    for text, style in parts:
        if text:
            segments.append(Segment(text, style))
            used += visible_width(text)
    gap = width - used
    if gap > 0:
        segments.append(Segment(" " * gap, band))
    return Line(segments).fit(width)


class ToolBlock:
    """A tool call: title row, optional body rows, optional footer row.

    ``tone`` picks the band: ``"tool"`` (green), ``"code"`` (near black) or
    ``"plain"`` (no band); any other tone degrades to ``"plain"``.  Rows
    stack as title, a blank band row, the body rows, a blank band row and
    the footer -- each blank row disappears together with the section it
    introduces, so an empty body or footer leaves no stray gap.  Body items
    are rendered verbatim, one row each (the caller wraps them).  The title
    is bold and the footer dim-italic, both merged onto the band, and every
    row is ``fit`` to ``width``.
    """

    __slots__ = ("body", "footer", "title", "tone")

    def __init__(
        self,
        title: str,
        body: Iterable[str] = (),
        *,
        tone: str = "tool",
        footer: str = "",
    ) -> None:
        self.title = title
        self.body = list(body)
        self.tone = tone
        self.footer = footer

    def render(self, width: int) -> list[Line]:
        band = _TONES.get(self.tone, NONE)
        rows = [_band_row(band, width, ((self.title, band.merge(_TITLE)),))]
        if self.body:
            rows.append(_band_row(band, width, ()))
            for row in self.body:
                rows.append(_band_row(band, width, ((row, band),)))
        if self.footer:
            rows.append(_band_row(band, width, ()))
            rows.append(_band_row(band, width, ((self.footer, band.merge(_FOOTER)),)))
        return rows

    def __repr__(self) -> str:
        return f"ToolBlock({self.title!r}, tone={self.tone!r})"


class EditBlock:
    """An edit: path row, numbered context/removed/added rows, edited badge.

    Line numbers run from 1, continuous across ``context``, ``removed`` and
    ``added``.  Prefixes are ``"{n} "`` (plain), ``"-{n} "`` (red) and
    ``"+{n} "`` (green), carried inside a near-black band (the ``"code"``
    band).  The last added row ends with a ``" (edited)"`` badge in green
    bold; the path row is accent bold.  Every row is ``fit`` to ``width``.
    """

    __slots__ = ("added", "context", "path", "removed")

    def __init__(
        self,
        path: str,
        context: Iterable[str] = (),
        removed: Iterable[str] = (),
        added: Iterable[str] = (),
    ) -> None:
        self.path = path
        self.context = list(context)
        self.removed = list(removed)
        self.added = list(added)

    def render(self, width: int) -> list[Line]:
        band = CODE_BG
        rows = [_band_row(band, width, ((self.path, band.merge(ACCENT)),))]
        n = 0
        for text in self.context:
            n += 1
            rows.append(_band_row(band, width, ((f"{n} ", band), (text, band))))
        for text in self.removed:
            n += 1
            rows.append(_band_row(band, width, ((f"-{n} ", band.merge(ERROR)), (text, band))))
        last = len(self.added) - 1
        for i, text in enumerate(self.added):
            n += 1
            parts: list[tuple[str, Style]] = [(f"+{n} ", band.merge(SUCCESS)), (text, band)]
            if i == last:
                parts.append((" (edited)", band.merge(_EDITED)))
            rows.append(_band_row(band, width, tuple(parts)))
        return rows

    def __repr__(self) -> str:
        return f"EditBlock({self.path!r})"
