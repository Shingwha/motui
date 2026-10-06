"""Tool-call components: :class:`ToolBlock` and :class:`EditBlock`.

Band-framed blocks for a conversational transcript: a tool call (title row,
output rows, timing footer) and an edit (path row, line-numbered context and
a ``-``/``+`` diff closed by an ``(edited)`` badge).  Both fill the full
width behind a one-cell left padding, and both are wrapped in one pure
band-colored row above and below (the in-band vertical padding a chat UI
gives its blocks); :class:`ToolBlock` picks its band color from ``tone``.
``render`` is a pure function of the component and ``width``; every row is
``fit`` to ``width`` as a final guard.

The band colors come from the :class:`~mocode_tui.core.theme.Theme` this
component was built with -- ``tones``/``title_tones`` for :class:`ToolBlock`,
``code_bg`` for :class:`EditBlock` -- truecolor values from the soft
GitHub-dark set, so the bands stay gentle under white text.  Each block
resolves its theme once, at construction: ``tone`` is a plain (mutable)
attribute, so :class:`ToolBlock` keeps the resolved theme and looks the band
up from it per render.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import Theme, Themed

__all__ = ["EditBlock", "ToolBlock"]


def _banded_row(band: Style, width: int, parts: tuple[tuple[str, Style], ...]) -> Line:
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
    row = Line([Segment(" ", band), *(Segment(text, style) for text, style in parts if text)])
    return (row + Line.filled(width - row.width, band)).fit(width)


class ToolBlock(Themed):
    """A tool call: padding, title row, optional body rows, footer, padding.

    ``tone`` picks the band from the theme's ``tones`` table -- ``"tool"``
    (deep green with a green bold title), ``"code"`` (near black) or
    ``"plain"`` (no band); any other tone degrades to no band.  Rows stack as
    a pure band padding row, the title, a blank band row, the body rows, a
    blank band row, the footer and a closing pure band padding row -- each
    inner blank row disappears together with the section it introduces, so an
    empty body or footer leaves no stray gap, while the two padding rows
    always stay (the block keeps its vertical breathing room on every width).
    Body items are rendered verbatim, one row each (the caller wraps them).
    The title is bold (green on the ``"tool"`` band) and the footer
    dim-italic, both merged onto the band, and every row is ``fit`` to
    ``width``.
    """

    __slots__ = ("body", "footer", "theme", "title", "tone")

    def __init__(
        self,
        title: str,
        body: Iterable[str] = (),
        *,
        tone: str = "tool",
        footer: str = "",
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.title = title
        self.body = list(body)
        self.tone = tone
        self.footer = footer
        self.theme = theme
        # ``tone`` is a plain (mutable) attribute, so the pick is
        # state-dependent: the tone tables are looked up in the stored theme
        # at render time (charter: the theme fallback itself resolves once).

    def render(self, width: int) -> list[Line]:
        theme = self._theme
        band = theme.tones.get(self.tone, NONE)
        # The "tool" tone's green lives on the title row only; every other
        # tone keeps the plain ``band.merge(bold)`` emphasis.
        title = theme.title_tones.get(self.tone, band.merge(Style(bold=True)))
        rows = [Line.filled(width, band)]  # top in-band padding
        rows.append(_banded_row(band, width, ((self.title, title),)))
        if self.body:
            rows.append(Line.filled(width, band))
            for row in self.body:
                rows.append(_banded_row(band, width, ((row, band),)))
        if self.footer:
            rows.append(Line.filled(width, band))
            rows.append(
                _banded_row(band, width, ((self.footer, band.merge(Style(dim=True, italic=True))),))
            )
        rows.append(Line.filled(width, band))  # bottom in-band padding
        return rows

    def __repr__(self) -> str:
        return f"ToolBlock({self.title!r}, tone={self.tone!r})"


class EditBlock(Themed):
    """An edit: padding, path row, numbered context/removed rows, added
    rows, padding.

    Line numbers run from 1, continuous across ``context``, ``removed`` and
    ``added``.  Prefixes are ``"{n} "`` (plain), ``"-{n} "`` (red) and
    ``"+{n} "`` (green), carried inside the theme's ``code_bg`` band and
    wrapped in one pure band padding row above and below.  The last added
    row ends with a ``" (edited)"`` badge in green bold; the path row is
    accent bold.  Every row is ``fit`` to ``width``.
    """

    __slots__ = ("_band", "added", "context", "path", "removed", "theme")

    def __init__(
        self,
        path: str,
        context: Iterable[str] = (),
        removed: Iterable[str] = (),
        added: Iterable[str] = (),
        *,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.path = path
        self.context = list(context)
        self.removed = list(removed)
        self.added = list(added)
        self.theme = theme
        # No pick here depends on mutable state, so the whole band --
        # ``code_bg`` and the prefix/badge styles merged onto it -- resolves
        # once, at construction (charter: explicit > theme field > DEFAULT).
        self._band = self._theme.code_bg

    def render(self, width: int) -> list[Line]:
        band = self._band
        theme = self._theme
        rows = [Line.filled(width, band)]  # top in-band padding
        rows.append(_banded_row(band, width, ((self.path, band.merge(theme.accent)),)))
        n = 0
        for text in self.context:
            n += 1
            rows.append(_banded_row(band, width, ((f"{n} ", band), (text, band))))
        for text in self.removed:
            n += 1
            rows.append(
                _banded_row(band, width, ((f"-{n} ", band.merge(theme.error)), (text, band)))
            )
        last = len(self.added) - 1
        for i, text in enumerate(self.added):
            n += 1
            parts: list[tuple[str, Style]] = [
                (f"+{n} ", band.merge(theme.success)),
                (text, band),
            ]
            if i == last:
                parts.append((" (edited)", band.merge(theme.success).merge(Style(bold=True))))
            rows.append(_banded_row(band, width, tuple(parts)))
        rows.append(Line.filled(width, band))  # bottom in-band padding
        return rows

    def __repr__(self) -> str:
        return f"EditBlock({self.path!r})"
