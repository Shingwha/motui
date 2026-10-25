"""The action primitives: :class:`Button`, :class:`Checkbox` and :class:`Link`.

The three smallest interactive units the toolkit ships, one family file:
``Button`` renders its label as ``" label "``, ``Checkbox`` a ``[x] label`` /
``[ ] label`` toggle beside it, and ``Link`` a one-row text in the theme's
``link`` band that only the mouse and an activation follow.  Each holds state
and answers controller methods like every component (D1): ``on_click`` and
``on_action("activate")`` land the operation in a one-shot result the host reads through
``take()`` -- there is no callback, no event bus and no public
``chosen``.

``hover`` and ``focused`` are the flags the pointer and focus tiers write
(the pointer's and the focus tier's flags); they only change how the row
renders, and a component that is neither hovered nor focused renders exactly
the base style.  The three resolve their row band through the same rule --
base, then the hover band, then the focus band (:func:`_band`) -- so one
implementation carries the styling contract of the whole family.  ``hint``
is the tooltip's protocol: the :class:`~motui.app.overlays.Tooltip`
overlay reads it off the leaf under the pointer, and the empty default means
no hint -- a page assigns its own, and nothing renders by it.

The family is the first :class:`~motui.widgets.base.Widget` generation: the
theme value and the :class:`~motui.kernel.theme.Styles` group overrides stay
on the instance, and every render reads ``self.group(...)`` then.  A theme
or ``styles`` assignment therefore repaints a mounted control instead of
requiring a reconstruction, and the four per-token style parameters the
1.x constructors took are gone.

Every action carries ``disabled``: a disabled control refuses clicks and
activations (both answer ``False``) and renders the theme's faint text band
(``text.faint``, or the ``styles.text`` override) instead of the
interactive bands.
"""

from __future__ import annotations

from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Line, Segment, Surface
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.theme import Styles, Theme
from ..kernel.text import WrapMode
from ..widgets.base import Widget

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

    :meth:`on_click` and :meth:`on_action` are the two doors to the same
    operation -- a button always has a main one, so neither ever answers
    ``False`` while enabled -- and both write the pending result for the
    host to read once through :meth:`take`.  A disabled button
    refuses both doors and renders the faint text band.
    """

    __slots__ = (
        "_pending",
        "disabled",
        "hint",
        "label",
    )

    #: The action family's capability set: a button takes the focus ring,
    #: pointer clicks and the activation verb, and paints a hover band.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

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
        #: The pending operation: written by ``on_click`` / ``activate``,
        #: read once by :meth:`take`.
        self._pending: bool | None = None

    def on_click(self, pos: Pos) -> bool:
        """Take a click on any of the button's cells; ``False`` when disabled.

        The button is one small cell group -- ``" label "`` -- and every
        cell of it is the whole control, so ``pos`` is ignored and the click
        always lands while the button is enabled: a button has no dead cells
        and no miss.
        """
        return self.on_action("activate")

    def on_action(self, name: str) -> bool:
        """Run the button's one action (``"activate"``); others decline."""
        if name != "activate":
            return False
        if self.disabled:
            return False
        self._pending = True
        return True

    def take(self) -> bool | None:
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

    def render(self, c: Constraints) -> Surface:
        """The one fitted row, under the render constraints.

        The constraint carries the width; a ``max_height`` budget truncates
        the single row (``0`` paints nothing).  The answer is
        :meth:`~motui.kernel.cell.Surface.clipped`, not padded: the row keeps
        the natural width of the fitted label, so the bytes match the old
        list answer.
        """
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
        rows = [Line.from_text(f" {self.label} ", style).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return (
            f"Button({self.label!r}, focused={self.focused}, "
            f"disabled={self.disabled}, hover={self.hover})"
        )


class Checkbox(Widget):
    """A one-row checked/unchecked toggle with a ``[x]`` / ``[ ]`` mark.

    ``checked`` starts ``False`` (or at the constructor's value) and is
    flipped by :meth:`on_action` and :meth:`on_click` -- both are the same
    operation and always land ``True`` while enabled (a checkbox always has
    a main one) -- which leaves the new state pending for :meth:`take`.  The row renders ``"{mark} label"`` with the
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

    #: A checkbox is a focus-ring target, takes pointer clicks and the
    #: activation verb, and paints a hover band.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

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
        #: The pending toggle: written by ``on_click`` / ``activate`` (the
        #: new ``checked`` value), read once by :meth:`take`.
        self._pending: bool | None = None

    def on_click(self, pos: Pos) -> bool:
        """Flip the toggle on any of the checkbox's cells.

        ``pos`` is ignored: the whole one-row control is the toggle, mark
        and label alike.  ``False`` when disabled.
        """
        return self.on_action("activate")

    def on_action(self, name: str) -> bool:
        """Run the checkbox's one action (``"activate"``); others decline."""
        if name != "activate":
            return False
        if self.disabled:
            return False
        self.checked = not self.checked
        self._pending = self.checked
        return True

    def take(self) -> bool | None:
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

    def render(self, c: Constraints) -> Surface:
        """The mark-plus-label row, under the render constraints.

        See :meth:`Button.render`: ``max_height`` truncates (``0`` paints
        nothing) and the surface is clipped, not padded.
        """
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
        rows = [
            Line(
                (Segment(mark_text, mark_style), Segment(self.label, label_style))
            ).clip(WrapMode.ELLIPSIS, c.width)
        ]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

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
    A click anywhere on the row or an activation leaves ``True``
    pending for :meth:`take`; a disabled link refuses both doors and
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

    #: A link is a focus-ring target, takes pointer clicks and the
    #: activation verb, and paints a hover band.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

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
        #: The pending follow: written by ``on_click`` / ``activate``, read
        #: once by :meth:`take`.
        self._pending: bool | None = None

    def on_click(self, pos: Pos) -> bool:
        """Follow the link on any of its cells; ``False`` when disabled.

        ``pos`` is ignored -- the whole one-row text is the link -- and the
        answer is always ``True`` while enabled; what the host does with the
        pending result is its own policy.
        """
        return self.on_action("activate")

    def on_action(self, name: str) -> bool:
        """Run the link's one action (``"activate"``); others decline."""
        if name != "activate":
            return False
        if self.disabled:
            return False
        self._pending = True
        return True

    def take(self) -> bool | None:
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

    def render(self, c: Constraints) -> Surface:
        """The fitted row, under the render constraints.

        See :meth:`Button.render`: ``max_height`` truncates (``0`` paints
        nothing) and the surface is clipped, not padded.
        """
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
        rows = [Line.from_text(self.text, style).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return (
            f"Link({self.text!r}, focused={self.focused}, "
            f"disabled={self.disabled}, hover={self.hover})"
        )
