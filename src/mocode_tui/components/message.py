"""Message component: role-banded rows for chat-style interfaces.

:class:`Message` renders one logical message per role, mirroring the pi-style
chat layout: a ``user`` message is a full-width colored band (one cell of
padding on each side, blue background), an ``assistant`` message is a plain
wrapped paragraph, and ``thinking`` is dim gray italic (the "let me look at
that" aside between turns).  Any unknown role degrades to ``assistant``
rather than raising.  ``render`` is a pure function of the component and
``width``; every row is word-wrapped and ``fit`` to ``width``.

The semantic constants below are defined here, not in :mod:`mocode_tui.style`
(that module is the frozen W1 layer): the palette picks the nearest named
16-color for the screenshot's dark blue / dim gray, per the spec's honest
exit note.
"""

from __future__ import annotations

from ..lines import Line, Segment
from ..style import MUTED, NONE, Style
from ..text import visible_width, wrap_text

__all__ = ["Message"]

#: User-message band: blue background (the pi UI's user turn; nearest named
#: 16-color to the screenshot's dark blue).
USER_BG = Style(bg="blue")

#: Thinking-message style: dim gray italic (the screenshot's gray aside).
THINKING = MUTED.merge(Style(italic=True))


class Message:
    """A role-tagged chat message.

    ``role`` selects the treatment -- ``"user"`` (blue band), ``"assistant"``
    (plain) or ``"thinking"`` (dim italic); any other value degrades to
    ``"assistant"``.  ``style`` overrides the role's default for every
    segment (e.g. a red user band).  Each ``"\\n"`` starts a new logical line
    (:func:`~mocode_tui.text.wrap_text` itself does not split on newlines);
    lines are word-wrapped, and the user band keeps one padding cell per
    side, so its text area is ``width - 2``.  Empty text still renders
    one row: a bare band for ``user``, an empty row otherwise.
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
        """One full-width band row per wrapped piece, padding included.

        Every segment -- the left pad, the content and the right fill --
        carries the band style so the row reads as one continuous color.
        """
        style = self.style if self.style is not None else USER_BG
        rows: list[Line] = []
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
        return rows

    def __repr__(self) -> str:
        return f"Message({self.role!r}, {self.text!r})"
