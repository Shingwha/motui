"""Link: a one-row text that a click follows.

The smallest *mouse-only* primitive: it renders its text in the theme's
``link`` band (soft blue, underlined) and takes a click into
:attr:`Link.chosen` for the host to read once and reset (D1).  It is
deliberately **not** :class:`~motui.kernel.block.Activable`: a link is
not a focus target's main operation -- the keyboard door belongs to the
widgets a ring registers (D9).
"""

from __future__ import annotations

from ..kernel.lines import Line
from ..kernel.style import Style
from ..kernel.theme import Theme, Themed

__all__ = ["Link"]


class Link(Themed):
    """A one-row clickable text, rendered in the theme's ``link`` band.

    The row is ``text``, ``fit`` to the painting width; the base style is
    ``style`` or the theme's ``link``, and while the pointer tier holds
    :attr:`hover` it merges ``hover_style`` or the theme's ``hover``.  A
    click anywhere on the row lands ``True`` in :attr:`chosen` -- the host
    reads it once and resets it -- and :meth:`click` always answers
    ``True``: the whole row is the link.  :attr:`hint` is the tooltip's
    protocol -- the ``chrome.Tooltip`` overlay reads it off the leaf under
    the pointer, and the empty default means no hint -- and styles resolve
    once, at construction, as explicit > theme field > ``DEFAULT_THEME``.
    """

    __slots__ = ("_base_style", "_hover_style", "chosen", "hint", "hover", "text")

    def __init__(
        self,
        text: str,
        *,
        style: Style | None = None,
        hover_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.text = text
        #: The pointer tier's flag; it only changes how the row renders.
        self.hover = False
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending follow: written by ``click``, read once by the host,
        #: which resets it to ``None``.
        self.chosen: bool | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._base_style = self._pick(style, "link")
        self._hover_style = self._pick(hover_style, "hover")

    def click(self, row: int, col: int) -> bool:
        """Follow the link on any of its cells; always ``True``.

        ``row``/``col`` are ignored -- the whole one-row text is the link
        -- and the answer is always ``True``; what the host does with
        :attr:`chosen` is its own policy.
        """
        self.chosen = True
        return True

    def render(self, width: int) -> list[Line]:
        style = self._base_style
        if self.hover:
            style = style.merge(self._hover_style)
        return [Line.from_text(self.text, style).fit(width)]

    def __repr__(self) -> str:
        return f"Link({self.text!r}, hover={self.hover})"
