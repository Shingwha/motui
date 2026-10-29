"""The action primitives: :class:`Button`, :class:`Checkbox` and :class:`Link`.

Each is a one-row control whose activation leaves a one-shot result for
``take()``.  ``disabled``/``hint`` and result bookkeeping live in
``ActionWidget``; ``action_band`` is the family's single styling rule.
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

    NEUTRAL: control+text.base; PRIMARY: accent+inverse; GHOST: no floor,
    content.accent; DANGER: danger+inverse.  Disabled merges faint before
    the overlay, so its precedence wins.
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

    Renders ``" label "`` fitted to the width, on the kind's floor plus the
    shared control overlay.  Activation leaves ``True`` pending; a disabled
    button refuses and renders faint.
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
        """The theme with this button's ``styles`` groups folded in.

        ``action_band`` takes one theme, so overrides must win here too.
        """
        return replace(
            self._theme,
            text=self.group("text"),
            surfaces=self.group("surfaces"),
            controls=self.group("controls"),
            content=self.group("content"),
        )

    def render(self, c: Constraints) -> Surface:
        """The one fitted row, clipped to the width."""
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

    The mark uses ``content.accent`` and the label ``text.base``, with the
    shared control overlay for hover/focus/disabled.  ``toggle`` flips
    ``checked`` and leaves it pending; a disabled checkbox refuses and
    renders faint.  ``glyphs.check_on``/``check_off`` supply the mark; an
    empty glyph drops the mark and its separator.
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
        """The mark-plus-label row, clipped to the width."""
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

    Renders ``text`` in ``content.link``; hover/focus merge the shared
    control overlay.  A click or activation leaves ``True`` pending; a
    disabled link refuses and renders faint.
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
        """The fitted link row, clipped to the width."""
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
