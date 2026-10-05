"""Message component: role-banded rows for chat-style interfaces.

:class:`Message` renders one logical message per role, mirroring the pi-style
chat layout: a ``user`` message is a full-width colored band (one cell of
padding on each side plus a pure band-colored row above and below -- the
in-band vertical padding the pi UI gives its user turns), an ``assistant``
message is a plain wrapped paragraph, and ``thinking`` is dim gray italic
(the "let me look at that" aside between turns).  Any unknown role degrades
to ``assistant`` rather than raising.  ``render`` is a pure function of the
component and ``width``; every row is word-wrapped and ``fit`` to ``width``.

The role styles come from the :class:`~mocode_tui.core.theme.Theme` this
component was built with (``theme.user_bg`` for the user band, a dim-italic
merge of ``theme.muted`` for thinking); an explicit ``style=`` overrides the
role default, and the shipped default is
:data:`~mocode_tui.core.theme.DEFAULT_THEME`.
"""

from __future__ import annotations

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.text import visible_width, wrap_text
from ..core.theme import DEFAULT_THEME, Theme

__all__ = ["Message"]


class Message:
    """A role-tagged chat message.

    ``role`` selects the treatment -- ``"user"`` (the theme's user band),
    ``"assistant"`` (plain) or ``"thinking"`` (dim italic); any other value
    degrades to ``"assistant"``.  ``style`` overrides the role's default for
    every segment (e.g. a red user band).  Each ``"\\n"`` starts a new logical
    line (:func:`~mocode_tui.core.text.wrap_text` itself does not split on
    newlines); lines are word-wrapped, and the user band keeps one padding
    cell per side, so its text area is ``width - 2``.  A user message also
    gets one pure band-colored row above and below its content rows (the
    in-band vertical padding); ``assistant``/``thinking`` have no band and
    therefore no padding -- the blank line between blocks separates them.
    Empty text still renders: a bare band wrapped in its padding rows for
    ``user``, an empty row otherwise.
    """

    __slots__ = ("role", "style", "text", "theme")

    def __init__(
        self,
        role: str,
        text: str = "",
        *,
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        self.role = role
        self.text = text
        self.style = style
        self.theme = theme

    def render(self, width: int) -> list[Line]:
        theme = self.theme or DEFAULT_THEME
        if self.role == "user":
            return self._user_rows(width, theme)
        if self.role == "thinking":
            style = self.style if self.style is not None else theme.muted.merge(Style(italic=True))
        else:  # assistant, or any unknown role (degraded)
            style = self.style if self.style is not None else NONE
        out: list[Line] = []
        for row in self.text.split("\n"):  # wrap_text does not split on "\n"
            for piece in wrap_text(row, width):
                out.append(Line.from_text(piece, style).fit(width))
        return out

    def _user_rows(self, width: int, theme: Theme) -> list[Line]:
        """A padded band: pure band rows, then the content rows band-wrapped.

        Every segment -- the leading pad, the content, the closing fill and
        the two pure padding rows -- carries the band style so the block
        reads as one continuous color from the top padding row to the
        bottom one.  The padding rows survive every width: at ``width <= 0``
        they collapse to empty lines while the content rows stay ``fit``.
        """
        style = self.style if self.style is not None else theme.user_bg
        rows: list[Line] = [Line.filled(width, style)]
        for row in self.text.split("\n"):  # wrap_text does not split on "\n"
            for piece in wrap_text(row, width - 2):  # one pad cell per side
                segments: list[Segment] = []
                if width > 0:
                    segments.append(Segment(" ", style))
                if piece:
                    segments.append(Segment(piece, style))
                gap = width - 1 - visible_width(piece)
                if gap > 0:
                    segments.append(Segment(" " * gap, style))
                rows.append(Line(segments).fit(width))
        rows.append(Line.filled(width, style))
        return rows

    def __repr__(self) -> str:
        return f"Message({self.role!r}, {self.text!r})"
