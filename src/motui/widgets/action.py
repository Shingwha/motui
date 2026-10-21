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
(:class:`~motui.core.block.Hoverable` /
:class:`~motui.core.block.Focusable`); they only change how the row
renders, and a component that is neither hovered nor focused renders exactly
the base style.  The three resolve their row band through the same rule --
base, then the hover band, then the focus band (:func:`_band`) -- so one
implementation carries the styling contract of the whole family.  ``hint``
is the tooltip's protocol: the :class:`~motui.app.overlays.Tooltip`
overlay reads it off the leaf under the pointer, and the empty default means
no hint -- a page assigns its own, and nothing renders by it.

The family is the first :class:`~motui.core.widget.Widget` generation: the
theme value and the :class:`~motui.core.theme.Styles` group overrides stay
on the instance, and every render reads ``self.group(...)`` then.  A theme
or ``styles`` assignment therefore repaints a mounted control instead of
requiring a reconstruction, and the four per-token style parameters the
1.x constructors took are gone.

Every action carries ``disabled``: a disabled control refuses ``click`` and
``activate`` (both answer ``False``) and renders the theme's faint text band
(``text.faint``, or the ``styles.text`` override) instead of the
interactive bands.
"""

from __future__ import annotations

from ..core.glyphs import GLYPHS, Glyphs
from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import Styles, Theme
from ..core.widget import Widget

__all__ = ["Button", "Checkbox", "Link"]


def _band(
    base: Style,
    *,
    hover: bool,
    hover_band: Style,
    focused: bool = False,
    focus_band: Style = NONE,
) -> Style:
    """The row's resolved band: ``base``, hover merged, then focus merged.

    The action family's one styling rule.  ``base`` is the component's
    resolved base style; while ``hover`` is ``True`` the row merges
    ``hover_band`` and while ``focused`` is ``True`` ``focus_band`` merges
    on top of the result -- so hover and focus are each plainly visible
    against the base, and a component that is neither renders exactly
    ``base``.
    """
    style = base
    if hover:
        style = style.merge(hover_band)
    if focused:
        style = style.merge(focus_band)
    return style


class Button(Widget):
    """A one-row action: a label a click or an activation takes.

    The row renders as ``" label "``, ``fit`` to the painting width.  The
    base style is ``styles.controls.base`` (``content.accent`` by default);
    while ``hover`` is ``True`` the row merges ``styles.surfaces.hover``,
    and while ``focused`` is ``True`` it merges ``styles.controls.focus`` --
    so hover and focus are each plainly visible against the base (with the
    default theme both bands are reverse video; a host that wants them told
    apart overrides the groups).  The groups resolve on every render, as
    ``styles`` override > theme group > :data:`DEFAULT_THEME`.

    :meth:`click` and :meth:`activate` are the two doors to the same
    operation -- a button always has a main one, so neither ever answers
    ``False`` while enabled -- and both write the pending result for the
    host to read once through :meth:`take_result`.  A disabled button
    refuses both doors and renders the faint text band.
    """

    __slots__ = (
        "_pending",
        "disabled",
        "hint",
        "label",
    )

    def __init__(
        self,
        label: str,
        *,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.label = label
        #: Refuse the two doors and render the faint text band.
        self.disabled = disabled
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending operation: written by ``click`` / ``activate``, read
        #: once by :meth:`take_result`.
        self._pending: bool | None = None

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
        """The row's value snapshot: label, flags, state, theme and styles.

        One row, plain values -- cheaper than any render could be.  The
        snapshot exists so a cached block's button stays live where it
        always was: the row cache on the block keys on this value, so a
        ``hover = True`` (or ``focused``, a relabelled ``label``, a toggled
        ``disabled``) misses and the band reaches the screen.  ``theme`` and
        ``styles`` are row inputs now that the groups resolve at render
        time, so they are part of the snapshot too.
        """
        return (
            self.label,
            self.hover,
            self.focused,
            self.disabled,
            self.theme,
            self.styles,
        )

    def render(self, width: int) -> list[Line]:
        if self.disabled:
            style = self.group("text").faint
        else:
            style = _band(
                self.group("controls").base,
                hover=self.hover,
                hover_band=self.group("surfaces").hover,
                focused=self.focused,
                focus_band=self.group("controls").focus,
            )
        return [Line.from_text(f" {self.label} ", style).fit(width)]

    def __repr__(self) -> str:
        return (
            f"Button({self.label!r}, focused={self.focused}, "
            f"disabled={self.disabled}, hover={self.hover})"
        )


class Checkbox(Widget):
    """A one-row checked/unchecked toggle with a ``[x]`` / ``[ ]`` mark.

    ``checked`` starts ``False`` (or at the constructor's value) and is
    flipped by :meth:`activate` and :meth:`click` -- both are the same
    operation and always land ``True`` while enabled (a checkbox always has
    a main one) -- which leaves the new state pending for
    :meth:`take_result`.  The row renders ``"{mark} label"`` with the
    checkbox's styling: the mark in ``styles.content.accent`` and the label
    in ``styles.text.base``, the hover band merged while the pointer tier
    holds :attr:`hover`, the focus band merged while the focus tier holds
    :attr:`focused`.  The groups resolve on every render (``styles``
    override > theme group).  :attr:`glyphs` is the vocabulary the mark
    comes from: ``check_on`` / ``check_off``, with an empty glyph collapsing
    the mark and its separator.  A disabled checkbox refuses both doors and
    renders the faint text band.  :attr:`hint` is the tooltip's protocol:
    ``chrome.Tooltip`` reads it off the leaf under the pointer, and the
    empty default means no hint.
    """

    __slots__ = (
        "_pending",
        "checked",
        "disabled",
        "glyphs",
        "hint",
        "label",
    )

    def __init__(
        self,
        label: str,
        *,
        checked: bool = False,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.label = label
        self.checked = checked
        #: Refuse the two doors and render the faint text band.
        self.disabled = disabled
        #: The glyph vocabulary the mark is drawn from.
        self.glyphs = glyphs
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending toggle: written by ``click`` / ``activate`` (the new
        #: ``checked`` value), read once by :meth:`take_result`.
        self._pending: bool | None = None

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
        """The row's value snapshot: label, state, flags, theme and styles.

        The checkbox's twin of :meth:`Button.revision`: the mark
        (``checked`` and ``mark_pair``), the label, the hover/focus/disabled
        flags, and the ``theme`` / ``styles`` the groups resolve against are
        every row input, so a cached block's toggle, hover or retheme still
        reaches the screen through the block's ``(width, revision)`` cache
        key.  The pending result is deliberately out: no row reads it.
        """
        return (
            self.label,
            self.checked,
            self.glyphs.check_on,
            self.glyphs.check_off,
            self.hover,
            self.focused,
            self.disabled,
            self.theme,
            self.styles,
        )

    def render(self, width: int) -> list[Line]:
        if self.disabled:
            mark_style = label_style = self.group("text").faint
        else:
            mark_style = _band(
                self.group("content").accent,
                hover=self.hover,
                hover_band=self.group("surfaces").hover,
                focused=self.focused,
                focus_band=self.group("controls").focus,
            )
            label_style = _band(
                self.group("text").base,
                hover=self.hover,
                hover_band=self.group("surfaces").hover,
                focused=self.focused,
                focus_band=self.group("controls").focus,
            )
        mark = self.glyphs.check_on if self.checked else self.glyphs.check_off
        mark_text = f"{mark} " if mark else ""
        return [
            Line((Segment(mark_text, mark_style), Segment(self.label, label_style))).fit(
                width
            )
        ]

    def __repr__(self) -> str:
        return (
            f"Checkbox({self.label!r}, checked={self.checked}, "
            f"disabled={self.disabled})"
        )


class Link(Widget):
    """A one-row clickable and activable text in the theme's ``link`` band.

    The row is ``text``, ``fit`` to the painting width; the base style is
    ``styles.content.link``.  While the pointer tier holds :attr:`hover` it
    merges ``styles.surfaces.hover``, and while :attr:`focused` (the focus
    tier's flag, writable by contract) it merges ``styles.controls.focus``.
    A click anywhere on the row or an :meth:`activate` leaves ``True``
    pending for :meth:`take_result`; a disabled link refuses both doors and
    renders the faint text band.  :attr:`hint` is the tooltip's protocol --
    the ``chrome.Tooltip`` overlay reads it off the leaf under the pointer,
    and the empty default means no hint -- and the groups resolve on every
    render, as ``styles`` override > theme group > ``DEFAULT_THEME``.
    """

    __slots__ = (
        "_pending",
        "disabled",
        "hint",
        "text",
    )

    def __init__(
        self,
        text: str,
        *,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.text = text
        #: Refuse the two doors and render the faint text band.
        self.disabled = disabled
        #: The tooltip's protocol: the leaf's one-line hint, painted by
        #: ``chrome.Tooltip`` while the pointer rests on it.  ``""``: none.
        self.hint = ""
        #: The pending follow: written by ``click`` / ``activate``, read
        #: once by :meth:`take_result`.
        self._pending: bool | None = None

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
        """The row's value snapshot: text, flags, theme and styles.

        What the row is made of, as plain values -- the block's
        ``(width, revision)`` cache key consults it, so a hover (or a
        streamed ``text =`` assignment) on a cached block's link still
        repaints.  ``theme`` and ``styles`` are row inputs now that the
        groups resolve at render time.
        """
        return (
            self.text,
            self.hover,
            self.focused,
            self.disabled,
            self.theme,
            self.styles,
        )

    def render(self, width: int) -> list[Line]:
        if self.disabled:
            style = self.group("text").faint
        else:
            style = _band(
                self.group("content").link,
                hover=self.hover,
                hover_band=self.group("surfaces").hover,
                focused=self.focused,
                focus_band=self.group("controls").focus,
            )
        return [Line.from_text(self.text, style).fit(width)]

    def __repr__(self) -> str:
        return (
            f"Link({self.text!r}, focused={self.focused}, "
            f"disabled={self.disabled}, hover={self.hover})"
        )
