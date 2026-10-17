"""Button: the minimal action component -- one clickable row.

A button is the smallest interactive unit the toolkit ships: one label,
rendered as ``" label "`` in the theme's ``accent``, that a click or an
activation takes.  It holds state and answers controller methods like every
component (D1): :meth:`Button.click` and :meth:`Button.activate` both land
``True`` in :attr:`Button.chosen`, which the host reads once and resets --
there is no callback, no event bus.

``hover`` and ``focused`` are the flags the pointer and focus tiers write
(:class:`~motui.kernel.block.Hoverable` /
:class:`~motui.kernel.block.Focusable`); they only change how the row
renders, and a button that is neither hovered nor focused renders exactly
the base style.  ``hint`` is the tooltip's protocol: the
:class:`~motui.chrome.Tooltip` overlay reads it off the leaf under the
pointer, and the empty default means no hint -- a page assigns its own, and
nothing renders by it.
"""

from __future__ import annotations

from ..kernel.lines import Line
from ..kernel.style import Style
from ..kernel.theme import Theme, Themed

__all__ = ["Button"]


class Button(Themed):
    """A one-row action: a label a click or an activation takes.

    The row renders as ``" label "``, ``fit`` to the painting width.  The
    base style is ``style`` or the theme's ``accent``; while ``hover`` is
    ``True`` the row merges ``hover_style`` or the theme's ``hover``, and
    while ``focused`` is ``True`` it merges ``focus_style`` or the theme's
    ``cursor`` -- so hover and focus are each plainly visible against the
    base (with the default theme both bands are reverse video; a host that
    wants them told apart passes distinct ``hover_style`` /
    ``focus_style``).  Styles resolve once, at construction, as explicit >
    theme field > :data:`~motui.kernel.theme.DEFAULT_THEME`.

    :meth:`click` and :meth:`activate` are the two doors to the same
    operation -- a button always has a main one, so neither ever answers
    ``False`` -- and both write :attr:`chosen` for the host to read once
    and reset (D1).
    """

    __slots__ = (
        "_base_style",
        "_focus_style",
        "_hover_style",
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
        style: Style | None = None,
        hover_style: Style | None = None,
        focus_style: Style | None = None,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(theme)
        self.label = label
        self.focused = focused
        #: The pointer tier's flag; it only changes how the row renders.
        self.hover = False
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending operation: written by ``click`` / ``activate``, read
        #: once by the host, which resets it to ``None``.
        self.chosen: bool | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._base_style = self._pick(style, "accent")
        self._hover_style = self._pick(hover_style, "hover")
        self._focus_style = self._pick(focus_style, "cursor")

    def click(self, row: int, col: int) -> bool:
        """Take a click on any of the button's cells; always ``True``.

        The button is one small cell group -- ``" label "`` -- and every
        cell of it is the whole control, so ``row``/``col`` are ignored and
        the click always lands: a button has no dead cells and no miss.
        """
        self.chosen = True
        return True

    def activate(self) -> bool:
        """Take the activation (the Activable verb); always ``True``."""
        self.chosen = True
        return True

    def revision(self) -> object:
        """The row's value snapshot: label, flags and the three styles.

        One row, six plain values -- cheaper than any render could be.  The
        snapshot exists so a **sealed** block's button stays live where it
        always was: the row cache on the block keys on this value, so a
        ``hover = True`` (or ``focused``, or a relabelled ``label``) misses
        and the band reaches the screen.  The styles are construction-time
        values and never move through the public surface, but they are part
        of the snapshot all the same: they are row inputs, and the protocol
        promises equal snapshots mean equal rows.
        """
        return (
            self.label,
            self.hover,
            self.focused,
            self._base_style,
            self._hover_style,
            self._focus_style,
        )

    def render(self, width: int) -> list[Line]:
        style = self._base_style
        if self.hover:
            style = style.merge(self._hover_style)
        if self.focused:
            style = style.merge(self._focus_style)
        return [Line.from_text(f" {self.label} ", style).fit(width)]

    def __repr__(self) -> str:
        return f"Button({self.label!r}, focused={self.focused}, hover={self.hover})"
