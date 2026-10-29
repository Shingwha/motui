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
resolve their row band through one rule -- the kind's floor, then the
shared :meth:`~motui.kernel.theme.ControlStyles.overlay` -- so one
implementation (:func:`action_band`) carries the styling contract of the
whole family.  ``hint`` is the tooltip's protocol:
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

from dataclasses import replace
from enum import StrEnum

from ..kernel.cell import Line, Segment, Surface
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import ActionWidget

__all__ = ["Button", "ButtonKind", "Checkbox", "Link", "action_band"]


class ButtonKind(StrEnum):
    """The four button roles, each with its own floor and foreground."""

    NEUTRAL = "neutral"
    PRIMARY = "primary"
    GHOST = "ghost"
    DANGER = "danger"


def action_band(
    kind: ButtonKind | str,
    theme: Theme,
    *,
    hovered: bool = False,
    focused: bool = False,
    pressed: bool = False,
    disabled: bool = False,
) -> Style:
    """The one action-family band: the kind's floor plus the state overlay.

    ``NEUTRAL`` sits on ``surfaces.control`` with ``text.base``,
    ``PRIMARY`` on ``surfaces.accent`` with ``text.inverse``, ``GHOST``
    has no floor and takes ``content.accent``, and ``DANGER`` sits on
    ``surfaces.danger`` with ``text.inverse``.  A disabled control merges
    ``text.faint`` over the floor before the shared
    :meth:`~motui.kernel.theme.ControlStyles.overlay` (which then adds the
    ``dim``), so ``disabled`` always wins, then ``pressed``, ``focused``
    and ``hovered``.
    """
    kinds = ButtonKind(kind)
    base = {
        ButtonKind.NEUTRAL: theme.surfaces.control.merge(theme.text.base),
        ButtonKind.PRIMARY: theme.surfaces.accent.merge(theme.text.inverse),
        ButtonKind.GHOST: theme.content.accent,
        ButtonKind.DANGER: theme.surfaces.danger.merge(theme.text.inverse),
    }[kinds]
    overlay = theme.controls.overlay(
        hovered=hovered, focused=focused, pressed=pressed, disabled=disabled
    )
    if disabled:
        base = base.merge(theme.text.faint)
    return base.merge(overlay)


class Button(ActionWidget):
    """A one-row action: a label a click or an activation takes.

    The row renders as ``" label "``, ``fit`` to the painting width.  The
    base is the :class:`ButtonKind` floor -- ``NEUTRAL`` on
    ``surfaces.control`` with ``text.base``, ``PRIMARY`` on
    ``surfaces.accent`` with ``text.inverse``, ``GHOST`` without a floor in
    ``content.accent`` and ``DANGER`` on ``surfaces.danger`` with
    ``text.inverse`` -- and every state merges the shared
    ``controls.overlay`` on top, so hover, focus, pressed and disabled are
    plainly visible against it.  The groups resolve on every render, as
    ``styles`` override > theme group > :data:`DEFAULT_THEME`.

    :meth:`on_click` (inherited) and :meth:`activate` are the two doors to
    the same operation -- a button always has a main one, so neither ever
    answers ``False`` while enabled -- and both write ``True`` pending for
    the host to read once through :meth:`take`.  A disabled button
    refuses both doors and renders the faint, dim floor.
    """

    __slots__ = ("kind", "label")

    #: The action family's capability set: a button takes the focus ring,
    #: pointer clicks and the activation verb, and paints a hover band.
    focusable = True
    clickable = True
    hoverable = True

    def __init__(
        self,
        label: str,
        *,
        kind: ButtonKind | str = ButtonKind.NEUTRAL,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(disabled=disabled, theme=theme, styles=styles)
        self.label = label
        self.kind = ButtonKind(kind)

    def activate(self) -> bool:
        """Run the button's one action; ``False`` when disabled."""
        if self.disabled:
            return False
        self._emit(True)
        return True

    def _resolved_theme(self) -> Theme:
        """The theme with this button's ``styles`` groups applied.

        :func:`action_band` takes one theme value; the widget's per-group
        overrides are folded in here so ``styles`` keeps winning over the
        theme exactly as on every other render path.
        """
        return replace(
            self._theme,
            text=self.group("text"),
            surfaces=self.group("surfaces"),
            controls=self.group("controls"),
            content=self.group("content"),
        )

    def render(self, c: Constraints) -> Surface:
        """The one fitted row, under the render constraints.

        The constraint carries the width; a ``max_height`` budget truncates
        the single row (``0`` paints nothing).  The answer is
        :meth:`~motui.kernel.cell.Surface.clipped`, not padded: the row keeps
        the natural width of the fitted label, so the bytes match the old
        list answer.
        """
        style = action_band(
            self.kind,
            self._resolved_theme(),
            hovered=self.hover,
            focused=self.focused,
            disabled=self.disabled,
        )
        rows = [Line.from_text(f" {self.label} ", style).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return (
            f"Button({self.label!r}, kind={self.kind.value!r}, "
            f"focused={self.focused}, disabled={self.disabled}, "
            f"hover={self.hover})"
        )


class Checkbox(ActionWidget):
    """A one-row checked/unchecked toggle with a ``[x]`` / ``[ ]`` mark.

    ``checked`` starts ``False`` (or at the constructor's value) and is
    flipped by :meth:`toggle` -- reached through :meth:`activate` or the
    inherited :meth:`on_click`, both the same operation and always landing
    ``True`` while enabled (a checkbox always has a main one) -- which
    leaves the new state pending for :meth:`take`.  The row renders
    ``"{mark} label"`` with the checkbox's styling: the mark in
    ``styles.content.accent`` and the label in ``styles.text.base``, with
    the shared ``controls.overlay`` merged while the pointer tier holds
    :attr:`hover` or the focus tier holds :attr:`focused`.  The groups
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
        overlay = self.group("controls").overlay(
            hovered=self.hover, focused=self.focused, disabled=self.disabled
        )
        mark_style = self.group("content").accent
        label_style = self.group("text").base
        if self.disabled:
            mark_style = mark_style.merge(self.group("text").faint)
            label_style = label_style.merge(self.group("text").faint)
        mark_style = mark_style.merge(overlay)
        label_style = label_style.merge(overlay)
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
    ``styles.content.link``.  While :attr:`hover` or :attr:`focused` (the
    pointer and focus tiers' flags, writable by contract) it merges the
    shared ``controls.overlay`` -- so focus is a visible bold+underline
    reverse band on the link itself.
    A click anywhere on the row (the inherited :meth:`on_click`) or
    :meth:`activate` leaves ``True`` pending for :meth:`take`; a disabled
    link refuses both doors and renders the faint, dim band.  :attr:`hint`
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
        overlay = self.group("controls").overlay(
            hovered=self.hover, focused=self.focused, disabled=self.disabled
        )
        style = self.group("content").link
        if self.disabled:
            style = style.merge(self.group("text").faint)
        style = style.merge(overlay)
        rows = [Line.from_text(self.text, style).clip(WrapMode.ELLIPSIS, c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def __repr__(self) -> str:
        return (
            f"Link({self.text!r}, focused={self.focused}, "
            f"disabled={self.disabled}, hover={self.hover})"
        )
