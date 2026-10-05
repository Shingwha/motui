"""Tool-call components: :class:`ToolBlock` and :class:`EditBlock`.

Band-framed blocks for the pi-style transcript: a tool call (title row,
output rows, timing footer) and an edit (path row, line-numbered context and
a ``-``/``+`` diff closed by an ``(edited)`` badge).  Both fill the full
width behind a one-cell left padding, and both are wrapped in one pure
band-colored row above and below (the in-band vertical padding the pi UI
gives its blocks); :class:`ToolBlock` picks its band color from ``tone``.
``render`` is a pure function of the component and ``width``; every row is
``fit`` to ``width`` as a final guard.

The band constants below are defined here, not in
:mod:`mocode_tui.core.style` (that module is the frozen W1 layer); the W11
palette upgrade gave them truecolor values from the soft GitHub-dark set
(the screenshot's dark green / near-black bands) -- white text on the old
bright-green named band had been reported as glaring, and W8's dark-gray
stopgap now gives way to the intended deep green.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..core.lines import Line, Segment
from ..core.style import ACCENT, ERROR, NONE, SUCCESS, Style
from ..core.text import visible_width

__all__ = ["EditBlock", "ToolBlock"]

#: "tool" tone band: a deep-green truecolor band (the pi UI's tool calls;
#: ``#16281c`` on ``48;2;22;40;28``).  The W8 stopgap had parked the band on
#: dark gray because white text on a full-width bright-green named band read
#: as glaring; truecolor restores the intended soft green.
TOOL_BG = Style(bg="#16281c")

#: "code" tone band -- and the :class:`EditBlock` band: a near-black
#: blue-tinted truecolor background (the pi UI's dark code panels).
CODE_BG = Style(bg="#12181f")

#: ToolBlock title emphasis: bold, merged onto the band.
_TITLE = Style(bold=True)

#: ToolBlock title overrides per tone.  The W8 palette gave the "tool"
#: band a green bold title on its dark gray band (SGR 1;32 on 100) while
#: the body keeps the default foreground; every other tone still falls
#: back to ``band.merge(_TITLE)``.
_TITLE_TONES: dict[str, Style] = {
    "tool": TOOL_BG.merge(SUCCESS).merge(Style(bold=True)),
}

#: ToolBlock footer emphasis ("Took 0.1s"): dim italic with the default
#: foreground.  MUTED's gray foreground was invisible on the dark bands
#: (the "tool" and "code" bands alike), so the quiet look comes from
#: ``dim`` instead -- readable on both.
_FOOTER = Style(dim=True, italic=True)

#: EditBlock badge emphasis: green bold, merged onto the band.
_EDITED = SUCCESS.merge(Style(bold=True))

#: ``tone`` -> band style; anything unknown degrades to ``plain``.
_TONES: dict[str, Style] = {"tool": TOOL_BG, "code": CODE_BG, "plain": NONE}


def _band_row(band: Style, width: int, parts: tuple[tuple[str, Style], ...]) -> Line:
    """One band row: a leading pad cell, the styled parts, then the fill.

    The leading cell and the closing fill carry ``band``, so the row reads
    as one continuous color.  With no parts the row is a pure band-colored
    row -- the block's in-band vertical padding, i.e.
    :meth:`~mocode_tui.core.lines.Line.filled`.  ``width <= 0`` yields an empty
    row, and a row whose parts exceed ``width`` is ``fit`` (ellipsized) at
    the end.
    """
    if not parts:
        return Line.filled(width, band)
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
    """A tool call: padding, title row, optional body rows, footer, padding.

    ``tone`` picks the band: ``"tool"`` (deep green with a green bold
    title), ``"code"`` (near black) or ``"plain"`` (no band); any other
    tone degrades to ``"plain"``.  Rows stack as a pure band padding row,
    the title, a blank band row, the body rows, a blank band row, the
    footer and a closing pure band padding row -- each inner blank row
    disappears together with the section it introduces, so an empty body
    or footer leaves no stray gap, while the two padding rows always stay
    (the block keeps its vertical breathing room on every width).  Body
    items are rendered verbatim, one row each (the caller wraps them).
    The title is bold (green on the ``"tool"`` band) and the footer
    dim-italic, both merged onto the band, and every row is ``fit`` to
    ``width``.
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
        # W8 palette: the "tool" tone's green lives on the title row only;
        # every other tone keeps the plain ``band.merge(_TITLE)`` emphasis.
        title = _TITLE_TONES.get(self.tone, band.merge(_TITLE))
        rows = [_band_row(band, width, ())]  # top in-band padding
        rows.append(_band_row(band, width, ((self.title, title),)))
        if self.body:
            rows.append(_band_row(band, width, ()))
            for row in self.body:
                rows.append(_band_row(band, width, ((row, band),)))
        if self.footer:
            rows.append(_band_row(band, width, ()))
            rows.append(_band_row(band, width, ((self.footer, band.merge(_FOOTER)),)))
        rows.append(_band_row(band, width, ()))  # bottom in-band padding
        return rows

    def __repr__(self) -> str:
        return f"ToolBlock({self.title!r}, tone={self.tone!r})"


class EditBlock:
    """An edit: padding, path row, numbered context/removed rows, added
    rows, padding.

    Line numbers run from 1, continuous across ``context``, ``removed`` and
    ``added``.  Prefixes are ``"{n} "`` (plain), ``"-{n} "`` (red) and
    ``"+{n} "`` (green), carried inside the near-black ``"code"`` band and
    wrapped in one pure band padding row above and below.  The last added
    row ends with a ``" (edited)"`` badge in green bold; the path row is
    accent bold.  Every row is ``fit`` to ``width``.
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
        rows = [_band_row(band, width, ())]  # top in-band padding
        rows.append(_band_row(band, width, ((self.path, band.merge(ACCENT)),)))
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
        rows.append(_band_row(band, width, ()))  # bottom in-band padding
        return rows

    def __repr__(self) -> str:
        return f"EditBlock({self.path!r})"
