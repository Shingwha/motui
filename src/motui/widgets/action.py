"""The action primitives: :class:`Button`, :class:`Checkbox` and :class:`Link`.

The three smallest interactive units the toolkit ships, one family file:
``Button`` renders its label as ``" label "``, ``Checkbox`` a ``[x] label`` /
``[ ] label`` toggle beside it, and ``Link`` a one-row text in the theme's
``link`` band that only the mouse and an activation follow.  Each holds state
and answers controller methods like every component (D1): ``click`` and
``activate`` land the operation in a one-shot result the host reads through
``take_result()`` -- there is no callback, no event bus and no public
``chosen``.

``hover`` and ``focused`` are the flags the pointer and focus tiers write
(:class:`~motui.kernel.block.Hoverable` /
:class:`~motui.kernel.block.Focusable`); they only change how the row
renders, and a component that is neither hovered nor focused renders exactly
the base style.  The three resolve their row band through the same rule --
base, then the hover band, then the focus band (:func:`_band`) -- so one
implementation carries the styling contract of the whole family.  ``hint``
is the tooltip's protocol: the :class:`~motui.interaction.overlays.Tooltip`
overlay reads it off the leaf under the pointer, and the empty default means
no hint -- a page assigns its own, and nothing renders by it.

Every action carries ``disabled``: a disabled control refuses ``click`` and
``activate`` (both answer ``False``) and renders its resolved
``disabled_style`` (the theme's ``dim`` by default) instead of the
interactive bands.
"""

from __future__ import annotations

from ..kernel.glyphs import MARKED, UNMARKED
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
    ``hover_style`` and while ``focused`` is ``True`` ``focus_style`` merges
    on top of the result -- so hover and focus are each plainly visible
    against the base, and a component that is neither renders exactly
    ``base``.
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
    ``focus`` -- so hover and focus are each plainly visible against the
    base (with the default theme both bands are reverse video; a host that
    wants them told apart passes distinct ``hover_style`` /
    ``focus_style``).  Styles resolve once, at construction, as explicit >
    theme field > :data:`~motui.kernel.theme.DEFAULT_THEME`.

    :meth:`click` and :meth:`activate` are the two doors to the same
    operation -- a button always has a main one, so neither ever answers
    ``False`` while enabled -- and both write the pending result for the
    host to read once through :meth:`take_result`.  A disabled button
    refuses both doors and renders ``disabled_style``.
    """

    __slots__ = (
        "_base_style",
        "_disabled_style",
        "_focus_style",
        "_hover_style",
        "_pending",
        "disabled",
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
        disabled_style: Style | None = None,
        disabled: bool = False,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(theme)
        self.label = label
        self.focused = focused
        #: The pointer tier's flag; it only changes how the row renders.
        self.hover = False
        #: Refuse the two doors and render the disabled band.
        self.disabled = disabled
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending operation: written by ``click`` / ``activate``, read
        #: once by :meth:`take_result`.
        self._pending: bool | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._base_style = self.pick(style, self._theme.controls.base)
        self._hover_style = self.pick(hover_style, self._theme.surfaces.hover)
        self._focus_style = self.pick(focus_style, self._theme.controls.focus)
        self._disabled_style = self.pick(disabled_style, self._theme.text.faint)

    def click(self, row: int, col: int) -> bool:
        """Take a click on any of the button's cells; ``False`` when disabled.

        The button is one small cell group -- ``" label "`` -- and every
        cell of it is the whole control, so ``row``/``col`` are ignored and
        the click always lands while the button is enabled: a button has no
        dead cells and no miss.
        """
        return self.activate()

    def activate(self) -> bool:
        """Take the activation (the Activable verb); ``False`` when disabled."""
        if self.disabled:
            return False
        self._pending = True
        return True

    def take_result(self) -> bool | None:
        """Read the pending activation once and clear it."""
        value = self._pending
        self._pending = None
        return value

    def revision(self) -> object:
        """The row's value snapshot: label, flags, state and the styles.

        One row, plain values -- cheaper than any render could be.  The
        snapshot exists so a **sealed** block's button stays live where it
        always was: the row cache on the block keys on this value, so a
        ``hover = True`` (or ``focused``, a relabelled ``label``, a toggled
        ``disabled``) misses and the band reaches the screen.  The styles
        are construction-time values and never move through the public
        surface, but they are part of the snapshot all the same: they are
        row inputs, and the protocol promises equal snapshots mean equal
        rows.
        """
        return (
            self.label,
            self.hover,
            self.focused,
            self.disabled,
            self._base_style,
            self._hover_style,
            self._focus_style,
            self._disabled_style,
        )

    def render(self, width: int) -> list[Line]:
        style = (
            self._disabled_style
            if self.disabled
            else _band(
                self._base_style,
                hover=self.hover,
                hover_style=self._hover_style,
                focused=self.focused,
                focus_style=self._focus_style,
            )
        )
        return [Line.from_text(f" {self.label} ", style).fit(width)]

    def __repr__(self) -> str:
        return (
            f"Button({self.label!r}, focused={self.focused}, "
            f"disabled={self.disabled}, hover={self.hover})"
        )


class Checkbox(Themed):
    """A one-row checked/unchecked toggle with a ``[x]`` / ``[ ]`` mark.

    ``checked`` starts ``False`` (or at the constructor's value) and is
    flipped by :meth:`activate` and :meth:`click` -- both are the same
    operation and always land ``True`` while enabled (a checkbox always has
    a main one) -- which leaves the new state pending for
    :meth:`take_result`.  The row renders ``"{mark} label"`` with the
    checkbox's styling: the theme's ``accent`` as the base (``style``
    overrides it), the theme's ``hover`` merged while the pointer tier holds
    :attr:`hover`, the theme's ``focus`` merged while the focus tier holds
    :attr:`focused`.  :attr:`mark_pair` is the ``(checked, unchecked)``
    glyph pair, defaulting to the vocabulary's ``[x]`` / ``[ ]``.  A
    disabled checkbox refuses both doors and renders ``disabled_style``.
    :attr:`hint` is the tooltip's protocol: ``chrome.Tooltip`` reads it off
    the leaf under the pointer, and the empty default means no hint.
    """

    __slots__ = (
        "_base_style",
        "_disabled_style",
        "_focus_style",
        "_hover_style",
        "_pending",
        "checked",
        "disabled",
        "focused",
        "hint",
        "hover",
        "label",
        "mark_pair",
    )

    def __init__(
        self,
        label: str,
        *,
        checked: bool = False,
        style: Style | None = None,
        hover_style: Style | None = None,
        focus_style: Style | None = None,
        disabled_style: Style | None = None,
        mark_pair: tuple[str, str] = (MARKED, UNMARKED),
        disabled: bool = False,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(theme)
        self.label = label
        self.checked = checked
        self.focused = focused
        #: The pointer tier's flag; it only changes how the row renders.
        self.hover = False
        #: Refuse the two doors and render the disabled band.
        self.disabled = disabled
        #: The ``(checked, unchecked)`` glyph pair.
        self.mark_pair = mark_pair
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending toggle: written by ``click`` / ``activate`` (the new
        #: ``checked`` value), read once by :meth:`take_result`.
        self._pending: bool | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._base_style = self.pick(style, self._theme.controls.base)
        self._hover_style = self.pick(hover_style, self._theme.surfaces.hover)
        self._focus_style = self.pick(focus_style, self._theme.controls.focus)
        self._disabled_style = self.pick(disabled_style, self._theme.text.faint)

    def click(self, row: int, col: int) -> bool:
        """Flip the toggle on any of the checkbox's cells.

        ``row``/``col`` are ignored: the whole one-row control is the
        toggle, mark and label alike.  ``False`` when disabled.
        """
        return self.activate()

    def activate(self) -> bool:
        """Flip :attr:`checked` and leave the new state pending; ``False`` when disabled."""
        if self.disabled:
            return False
        self.checked = not self.checked
        self._pending = self.checked
        return True

    def take_result(self) -> bool | None:
        """Read the pending toggle (the new ``checked`` value) once and clear it."""
        value = self._pending
        self._pending = None
        return value

    def revision(self) -> object:
        """The row's value snapshot: label, state, flags and the styles.

        The checkbox's twin of :meth:`Button.revision`: the mark
        (``checked`` and ``mark_pair``), the label, the hover/focus/disabled
        flags and the construction-time styles are every row input, so a
        sealed block's toggle or hover still reaches the screen through the
        block's ``(width, revision)`` cache key.  The pending result is
        deliberately out: no row reads it.
        """
        return (
            self.label,
            self.checked,
            self.mark_pair,
            self.hover,
            self.focused,
            self.disabled,
            self._base_style,
            self._hover_style,
            self._focus_style,
            self._disabled_style,
        )

    def render(self, width: int) -> list[Line]:
        style = (
            self._disabled_style
            if self.disabled
            else _band(
                self._base_style,
                hover=self.hover,
                hover_style=self._hover_style,
                focused=self.focused,
                focus_style=self._focus_style,
            )
        )
        mark = self.mark_pair[0] if self.checked else self.mark_pair[1]
        return [Line.from_text(f"{mark} {self.label}", style).fit(width)]

    def __repr__(self) -> str:
        return (
            f"Checkbox({self.label!r}, checked={self.checked}, "
            f"disabled={self.disabled})"
        )


class Link(Themed):
    """A one-row clickable and activable text in the theme's ``link`` band.

    The row is ``text``, ``fit`` to the painting width; the base style is
    ``style`` or the theme's ``link``.  While the pointer tier holds
    :attr:`hover` it merges ``hover_style`` or the theme's ``hover``, and
    while :attr:`focused` (the focus tier's flag, writable by contract) it
    merges ``focus_style`` or the theme's ``focus``.  A click anywhere on
    the row or an :meth:`activate` leaves ``True`` pending for
    :meth:`take_result`; a disabled link refuses both doors and renders
    ``disabled_style``.  :attr:`hint` is the tooltip's protocol -- the
    ``chrome.Tooltip`` overlay reads it off the leaf under the pointer, and
    the empty default means no hint -- and styles resolve once, at
    construction, as explicit > theme field > ``DEFAULT_THEME``.
    """

    __slots__ = (
        "_base_style",
        "_disabled_style",
        "_focus_style",
        "_hover_style",
        "_pending",
        "disabled",
        "focused",
        "hint",
        "hover",
        "text",
    )

    def __init__(
        self,
        text: str,
        *,
        style: Style | None = None,
        hover_style: Style | None = None,
        focus_style: Style | None = None,
        disabled_style: Style | None = None,
        disabled: bool = False,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(theme)
        self.text = text
        self.focused = focused
        #: The pointer tier's flag; it only changes how the row renders.
        self.hover = False
        #: Refuse the two doors and render the disabled band.
        self.disabled = disabled
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending follow: written by ``click`` / ``activate``, read
        #: once by :meth:`take_result`.
        self._pending: bool | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._base_style = self.pick(style, self._theme.content.link)
        self._hover_style = self.pick(hover_style, self._theme.surfaces.hover)
        self._focus_style = self.pick(focus_style, self._theme.controls.focus)
        self._disabled_style = self.pick(disabled_style, self._theme.text.faint)

    def click(self, row: int, col: int) -> bool:
        """Follow the link on any of its cells; ``False`` when disabled.

        ``row``/``col`` are ignored -- the whole one-row text is the link --
        and the answer is always ``True`` while enabled; what the host does
        with the pending result is its own policy.
        """
        return self.activate()

    def activate(self) -> bool:
        """Take the link's activation; ``False`` when disabled."""
        if self.disabled:
            return False
        self._pending = True
        return True

    def take_result(self) -> bool | None:
        """Read the pending follow once and clear it."""
        value = self._pending
        self._pending = None
        return value

    def revision(self) -> object:
        """The row's value snapshot: text, flags and the four styles.

        What the row is made of, as plain values -- the block's
        ``(width, revision)`` cache key consults it, so a hover (or a
        streamed ``text =`` assignment) on a sealed block's link still
        repaints.  The styles are construction-time values, included
        because they are row inputs and the snapshot promises equal values
        mean equal rows.
        """
        return (
            self.text,
            self.hover,
            self.focused,
            self.disabled,
            self._base_style,
            self._hover_style,
            self._focus_style,
            self._disabled_style,
        )

    def render(self, width: int) -> list[Line]:
        style = (
            self._disabled_style
            if self.disabled
            else _band(
                self._base_style,
                hover=self.hover,
                hover_style=self._hover_style,
                focused=self.focused,
                focus_style=self._focus_style,
            )
        )
        return [Line.from_text(self.text, style).fit(width)]

    def __repr__(self) -> str:
        return (
            f"Link({self.text!r}, focused={self.focused}, "
            f"disabled={self.disabled}, hover={self.hover})"
        )
