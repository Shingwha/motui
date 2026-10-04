"""Message component: role-banded rows for chat-style interfaces.

:class:`Message` renders one logical message per role, mirroring the pi-style
chat layout: a ``user`` message is a full-width colored band (one cell of
padding on each side plus a pure band-colored row above and below -- the
in-band vertical padding the pi UI gives its user turns), an ``assistant``
message is a plain wrapped paragraph, and ``thinking`` is dim gray italic
(the "let me look at that" aside between turns).  Any unknown role degrades
to ``assistant`` rather than raising.  ``render`` is a pure function of the
component and ``width``; every row is word-wrapped and ``fit`` to ``width``.

The semantic constants below are defined here, not in :mod:`mocode_tui.style`
(that module is the frozen W1 layer): the palette picks the soft slate-blue
band from the W11 truecolor set (``#1c2b3a`` on ``48;2;28;43;58``), which
reads far calmer on a dark terminal than the old named-16 blue.
"""

from __future__ import annotations

from ..lines import Line, Segment
from ..style import MUTED, NONE, Style
from ..text import visible_width, wrap_text

__all__ = ["Message"]

#: User-message band: a soft slate-blue truecolor band (the pi UI's user
#: turn; ``#1c2b3a``, far calmer on a dark terminal than the old named-16
#: blue, which was pure blue and unreadable as "soft").
USER_BG = Style(bg="#1c2b3a")

#: Thinking-message style: dim gray italic (the screenshot's gray aside).
THINKING = MUTED.merge(Style(italic=True))


def _pad_row(band: Style, width: int) -> Line:
    """One pure band-colored padding row: full width, no content.

    Every column carries ``band`` so the row reads as part of the block; at
    ``width <= 0`` it collapses to an empty line (the padding row survives
    every width -- only its columns go away).
    """
    return Line.from_text(" " * width, band).fit(width)


class Message:
    """A role-tagged chat message.

    ``role`` selects the treatment -- ``"user"`` (soft slate-blue band),
    ``"assistant"`` (plain) or ``"thinking"`` (dim italic); any other value
    degrades to ``"assistant"``.  ``style`` overrides the role's default for
    every segment (e.g. a red user band).  Each ``"\\n"`` starts a new logical
    line (:func:`~mocode_tui.text.wrap_text` itself does not split on
    newlines); lines are word-wrapped, and the user band keeps one padding
    cell per side, so its text area is ``width - 2``.  A user message also
    gets one pure band-colored row above and below its content rows (the
    in-band vertical padding); ``assistant``/``thinking`` have no band and
    therefore no padding -- the blank line between blocks separates them.
    Empty text still renders: a bare band wrapped in its padding rows for
    ``user``, an empty row otherwise.
    """

    __slots__ = ("role", "style", "text")

    def __init__(self, role: str, text: str = "", *, style: Style | None = None) -> None:
        self.role = role
        self.text = text
        self.style = style

    def render(self, width: int) -> list[Line]:
        if self.role == "user":
            return self._user_rows(width)
        if self.role == "thinking":
            style = self.style if self.style is not None else THINKING
        else:  # assistant, or any unknown role (degraded)
            style = self.style if self.style is not None else NONE
        out: list[Line] = []
        for row in self.text.split("\n"):  # wrap_text does not split on "\n"
            for piece in wrap_text(row, width):
                out.append(Line.from_text(piece, style).fit(width))
        return out

    def _user_rows(self, width: int) -> list[Line]:
        """A padded band: pure band rows, then the content rows band-wrapped.

        Every segment -- the leading pad, the content, the closing fill and
        the two pure padding rows -- carries the band style so the block
        reads as one continuous color from the top padding row to the
        bottom one.  The padding rows survive every width: at ``width <= 0``
        they collapse to empty lines while the content rows stay ``fit``.
        """
        style = self.style if self.style is not None else USER_BG
        rows: list[Line] = [_pad_row(style, width)]
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
        rows.append(_pad_row(style, width))
        return rows

    def __repr__(self) -> str:
        return f"Message({self.role!r}, {self.text!r})"
