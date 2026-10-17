"""The action primitives: :class:`Button`, :class:`Checkbox` and :class:`Link`.

The three smallest interactive units the toolkit ships, one family file:
``Button`` renders its label as ``" label "``, ``Checkbox`` a ``[x] label`` /
``[ ] label`` toggle beside it, and ``Link`` a one-row text in the theme's
``link`` band that only the mouse follows.  Each holds state and answers
controller methods like every component (D1): ``click`` and ``activate`` land
the operation in a ``chosen`` the host reads once and resets -- there is no
callback, no event bus.

``hover`` and ``focused`` are the flags the pointer and focus tiers write
(:class:`~motui.kernel.block.Hoverable` /
:class:`~motui.kernel.block.Focusable`); they only change how the row
renders, and a component that is neither hovered nor focused renders exactly
the base style.  The three resolve their row band through the same rule --
base, then the hover band, then the focus band (:func:`_band`) -- so one
implementation carries the styling contract of the whole family.  ``hint``
is the tooltip's protocol: the :class:`~motui.chrome.Tooltip` overlay reads
it off the leaf under the pointer, and the empty default means no hint -- a
page assigns its own, and nothing renders by it.
"""

from __future__ import annotations

from ..kernel.lines import Line
from ..kernel.style import NONE, Style
from ..kernel.theme import Theme, Themed

__all__ = ["Button", "Checkbox", "Link"]


def _band(
    base: Style,
    *,
    hover: bool,
    hover_style: Style,
    focused: bool = False,
    focus_style: Style = NONE,
) -> Style:
    """The row's resolved band: ``base``, hover merged, then focus merged.

    The action family's one styling rule.  ``base`` is the component's
    resolved base style; while ``hover`` is ``True`` the row merges
    ``hover_style`` and while ``focused`` is ``True`` (the ``Link`` has no
    focus band and never asks for one) ``focus_style`` merges on top of the
    result -- so hover and focus are each plainly visible against the base,
    and a component that is neither renders exactly ``base``.
    """
    style = base
    if hover:
        style = style.merge(hover_style)
    if focused:
        style = style.merge(focus_style)
    return style


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
        style = _band(
            self._base_style,
            hover=self.hover,
            hover_style=self._hover_style,
            focused=self.focused,
            focus_style=self._focus_style,
        )
        return [Line.from_text(f" {self.label} ", style).fit(width)]

    def __repr__(self) -> str:
        return f"Button({self.label!r}, focused={self.focused}, hover={self.hover})"


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

    def revision(self) -> object:
        """The row's value snapshot: label, state, flags and the styles.

        The checkbox's twin of :meth:`Button.revision`: the mark
        (``checked``), the label, the hover/focus flags and the
        construction-time styles are every row input, so a sealed block's
        toggle or hover still reaches the screen through the block's
        ``(width, revision)`` cache key.
        """
        return (
            self.label,
            self.checked,
            self.hover,
            self.focused,
            self._base_style,
            self._hover_style,
            self._focus_style,
        )

    def render(self, width: int) -> list[Line]:
        style = _band(
            self._base_style,
            hover=self.hover,
            hover_style=self._hover_style,
            focused=self.focused,
            focus_style=self._focus_style,
        )
        mark = "x" if self.checked else " "
        return [Line.from_text(f"[{mark}] {self.label}", style).fit(width)]

    def __repr__(self) -> str:
        return f"Checkbox({self.label!r}, checked={self.checked})"


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

    A link is deliberately **not** :class:`~motui.kernel.block.Activable`:
    it is not a focus target's main operation -- the keyboard door belongs
    to the widgets a ring registers (D9).
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

    def revision(self) -> object:
        """The row's value snapshot: text, hover flag and the two styles.

        What the row is made of, as plain values -- the block's
        ``(width, revision)`` cache key consults it, so a hover (or a
        streamed ``text =`` assignment) on a sealed block's link still
        repaints.  The styles are construction-time values, included
        because they are row inputs and the snapshot promises equal
        values mean equal rows.
        """
        return (self.text, self.hover, self._base_style, self._hover_style)

    def render(self, width: int) -> list[Line]:
        style = _band(
            self._base_style,
            hover=self.hover,
            hover_style=self._hover_style,
        )
        return [Line.from_text(self.text, style).fit(width)]

    def __repr__(self) -> str:
        return f"Link({self.text!r}, hover={self.hover})"
