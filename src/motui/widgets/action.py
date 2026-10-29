"""The action primitives: :class:`Button`, :class:`Checkbox` and :class:`Link`.

The three smallest interactive units the toolkit ships, one family file:
``Button`` renders its label as ``" label "``, ``Checkbox`` a ``[x] label`` /
``[ ] label`` toggle beside it, and ``Link`` a one-row text in the theme's
``link`` band that only the mouse and an activation follow.  Each holds state
and answers controller methods like every component (D1): ``on_click`` and
``on_action("activate")`` land the operation in a one-shot result the host reads through
``take()`` -- there is no callback, no event bus and no public
``chosen``.

The family shares :class:`~motui.widgets.base.ActionWidget`: ``disabled``,
``hint``, the pending-result bookkeeping, :meth:`~ResultWidget.take` and the
``activate``/``toggle`` action routing live there once, and each control
implements only the verbs it has.  ``hover`` and ``focused`` are the flags
the pointer and focus tiers write (the pointer's and the focus tier's
flags); they only change how the row renders, and a component that is
neither hovered nor focused renders exactly the base style.  The three
resolve their row band through the same rule -- base, then the hover band,
then the focus band (:func:`_band`) -- so one implementation carries the
styling contract of the whole family.  ``hint`` is the tooltip's protocol:
the :class:`~motui.app.overlays.Tooltip` overlay reads it off the leaf under
the pointer, and the empty default means no hint -- a page assigns its own,
and nothing renders by it.

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

from ..kernel.cell import Line, Segment, Surface
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import ActionWidget

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


class Button(ActionWidget):
    """A one-row action: a label a click or an activation takes.

    The row renders as ``" label "``, ``fit`` to the painting width.  The
    base style is ``styles.controls.base`` (``content.accent`` by default);
    while ``hover`` is ``True`` the row merges ``styles.surfaces.hover``,
    and while ``focused`` is ``True`` it merges ``styles.controls.focus`` --
    so hover and focus are each plainly visible against the base (with the
    default theme both bands are reverse video; a host that wants them told
    apart overrides the groups).  The groups resolve on every render, as
    ``styles`` override > theme group > :data:`DEFAULT_THEME`.

    :meth:`on_click` (inherited) and :meth:`activate` are the two doors to
    the same operation -- a button always has a main one, so neither ever
    answers ``False`` while enabled -- and both write ``True`` pending for
    the host to read once through :meth:`take`.  A disabled button
    refuses both doors and renders the faint text band.
    """

    __slots__ = ("label",)

    #: The action family's capability set: a button takes the focus ring,
    #: pointer clicks and the activation verb, and paints a hover band.
    focusable = True
    clickable = True
    hoverable = True

    def __init__(
        self,
        label: str,
        *,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(disabled=disabled, theme=theme, styles=styles)
        self.label = label

    def activate(self) -> bool:
        """Run the button's one action; ``False`` when disabled."""
        if self.disabled:
            return False
        self._emit(True)
        return True

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


class Checkbox(ActionWidget):
    """A one-row checked/unchecked toggle with a ``[x]`` / ``[ ]`` mark.

    ``checked`` starts ``False`` (or at the constructor's value) and is
    flipped by :meth:`toggle` -- reached through :meth:`activate` or the
    inherited :meth:`on_click`, both the same operation and always landing
    ``True`` while enabled (a checkbox always has a main one) -- which
    leaves the new state pending for :meth:`take`.  The row renders
    ``"{mark} label"`` with the checkbox's styling: the mark in
    ``styles.content.accent`` and the label in ``styles.text.base``, the
    hover band merged while the pointer tier holds :attr:`hover`, the focus
    band merged while the focus tier holds :attr:`focused`.  The groups
    resolve on every render (``styles`` override > theme group).
    :attr:`glyphs` is the vocabulary the mark comes from: ``check_on`` /
    ``check_off``, with an empty glyph collapsing the mark and its
    separator.  A disabled checkbox refuses both doors and renders the
    faint text band.  :attr:`hint` is the tooltip's protocol:
    ``chrome.Tooltip`` reads it off the leaf under the pointer, and the
    empty default means no hint.
    """

    __slots__ = (
        "checked",
        "glyphs",
        "label",
    )

    #: A checkbox is a focus-ring target, takes pointer clicks and the
    #: activation verb, and paints a hover band.
    focusable = True
    clickable = True
    hoverable = True

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
        super().__init__(disabled=disabled, theme=theme, styles=styles)
        self.label = label
        self.checked = checked
        #: The glyph vocabulary the mark is drawn from.
        self.glyphs = glyphs

    def activate(self) -> bool:
        """The checkbox's main operation is its toggle."""
        return self.toggle()

    def toggle(self) -> bool:
        """Flip ``checked`` and leave the new state pending; ``False`` when disabled."""
        if self.disabled:
            return False
        self.checked = not self.checked
        self._emit(self.checked)
        return True

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


class Link(ActionWidget):
    """A one-row clickable and activable text in the theme's ``link`` band.

    The row is ``text``, ``fit`` to the painting width; the base style is
    ``styles.content.link``.  While the pointer tier holds :attr:`hover` it
    merges ``styles.surfaces.hover``, and while :attr:`focused` (the focus
    tier's flag, writable by contract) it merges ``styles.controls.focus``.
    A click anywhere on the row (the inherited :meth:`on_click`) or
    :meth:`activate` leaves ``True`` pending for :meth:`take`; a disabled
    link refuses both doors and renders the faint text band.  :attr:`hint`
    is the tooltip's protocol -- the ``chrome.Tooltip`` overlay reads it off
    the leaf under the pointer, and the empty default means no hint -- and
    the groups resolve on every render, as ``styles`` override > theme group
    > ``DEFAULT_THEME``.
    """

    __slots__ = ("text",)

    #: A link is a focus-ring target, takes pointer clicks and the
    #: activation verb, and paints a hover band.
    focusable = True
    clickable = True
    hoverable = True

    def __init__(
        self,
        text: str,
        *,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(disabled=disabled, theme=theme, styles=styles)
        self.text = text

    def activate(self) -> bool:
        """Follow the link; ``False`` when disabled."""
        if self.disabled:
            return False
        self._emit(True)
        return True

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
