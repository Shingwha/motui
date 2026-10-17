"""Checkbox: a one-row toggle -- ``[x] label`` / ``[ ] label``.

The toggling sibling of :class:`~motui.widgets.button.Button`:
:meth:`Checkbox.activate` and :meth:`Checkbox.click` flip :attr:`checked`
and mirror the new value into :attr:`chosen`, which the host reads once and
resets (D1 -- state and controller methods, no callbacks).  Rendering is one
row, ``[x] label`` when checked and ``[ ] label`` when not, in the same
band rules the button follows (base accent; ``hover`` and ``focused``
merge their theme bands on top).
"""

from __future__ import annotations

from ..kernel.lines import Line
from ..kernel.theme import Theme, Themed

__all__ = ["Checkbox"]


class Checkbox(Themed):
    """A one-row checked/unchecked toggle with a ``[x]`` / ``[ ]`` mark.

    ``checked`` starts ``False`` (or at the constructor's value) and is
    flipped by :meth:`activate` and :meth:`click` -- both are the same
    operation and always land ``True`` (a checkbox always has a main one)
    -- which mirrors the new state into :attr:`chosen` for the host to read
    once and reset.  The row renders ``"[x] label"`` / ``"[ ] label"`` with
    the button's styling: the theme's ``accent`` as the base, the theme's
    ``hover`` merged while the pointer tier holds :attr:`hover`, the
    theme's ``cursor`` merged while the focus tier holds :attr:`focused`.
    :attr:`hint` is the tooltip's protocol: ``chrome.Tooltip`` reads it off
    the leaf under the pointer, and the empty default means no hint.
    """

    __slots__ = (
        "_base_style",
        "_focus_style",
        "_hover_style",
        "checked",
        "chosen",
        "focused",
        "hint",
        "hover",
        "label",
    )

    def __init__(
        self,
        label: str,
        *,
        checked: bool = False,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(theme)
        self.label = label
        self.checked = checked
        self.focused = focused
        #: The pointer tier's flag; it only changes how the row renders.
        self.hover = False
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending toggle: written by ``click`` / ``activate`` (the new
        #: ``checked`` value), read once by the host, which resets it.
        self.chosen: bool | None = None
        # Styles resolve once, at construction: theme field > DEFAULT_THEME.
        self._base_style = self._pick(None, "accent")
        self._hover_style = self._pick(None, "hover")
        self._focus_style = self._pick(None, "cursor")

    def click(self, row: int, col: int) -> bool:
        """Flip the toggle on any of the checkbox's cells; always ``True``.

        ``row``/``col`` are ignored: the whole one-row control is the
        toggle, mark and label alike.
        """
        return self.activate()

    def activate(self) -> bool:
        """Flip :attr:`checked`, mirror it into :attr:`chosen`; always ``True``."""
        self.checked = not self.checked
        self.chosen = self.checked
        return True

    def render(self, width: int) -> list[Line]:
        style = self._base_style
        if self.hover:
            style = style.merge(self._hover_style)
        if self.focused:
            style = style.merge(self._focus_style)
        mark = "x" if self.checked else " "
        return [Line.from_text(f"[{mark}] {self.label}", style).fit(width)]

    def __repr__(self) -> str:
        return f"Checkbox({self.label!r}, checked={self.checked})"
