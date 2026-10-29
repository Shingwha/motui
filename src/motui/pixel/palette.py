"""The colors a quantizer may spend: slot color pairs and one background."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ..kernel.style import Color, Style
from ..kernel.theme import Theme
from .types import RGB, SlotColors

__all__ = ["PixelPalette", "StyleQuad"]

#: The four styles one slot can answer: main/cool, with and without ``bg``.
StyleQuad = tuple[Style, Style, Style, Style]

_WHITE: RGB = (255, 255, 255)

#: Per-slot fallbacks for a theme token that carries no RGB value -- a named
#: ANSI colour or no colour at all.  The order is the eight-slot order
#: :meth:`PixelPalette.from_theme` builds.
_FALLBACKS: tuple[RGB, ...] = (
    (77, 232, 210),   # accent
    (183, 160, 255),  # inline code
    (139, 234, 154),  # success
    (255, 209, 102),  # warning
    (255, 107, 139),  # danger
    (235, 250, 255),  # heading
    (138, 168, 181),  # muted
    (82, 108, 124),   # faint
)


def _token_rgb(style: Style, fallback: RGB) -> RGB:
    """The RGB triple a style's foreground names, or ``fallback``.

    Accepts the three colour spellings the kernel treats as RGB-authoring:
    a :class:`~motui.kernel.style.Color` wrapping a hex string or tuple, a
    bare ``#rrggbb`` string, and a bare tuple.  A named ANSI colour (or no
    foreground at all) cannot be mapped to a pixel colour, so it uses the
    slot's fixed fallback instead of inventing a lookup table.
    """
    fg = style.fg
    value = fg.value if isinstance(fg, Color) else fg
    if isinstance(value, tuple):
        return value
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        try:
            return (
                int(value[1:3], 16),
                int(value[3:5], 16),
                int(value[5:7], 16),
            )
        except ValueError:
            return fallback
    return fallback


@dataclass(frozen=True, slots=True)
class PixelPalette:
    """A caller-provided map from slot ids to ``(main, cool)`` colors.

    Fresh ink quantizes to the slot's *main* color; once a cell's peak heat
    drops below :data:`~motui.pixel.COOL_AT` it quantizes to the *cool*
    color.  ``bg`` is the color a ``"half"`` layer's unlit sub-rows show;
    ``None`` keeps them transparent.  The four styles per slot (main/cool,
    with and without ``bg``) are prebuilt once, so the quantizer answers
    each cell with a dict lookup and reuses one style object per
    ``(slot, state)`` -- the identity run fusion short-circuits on.

    A slot with no palette entry quantizes to white.
    """

    slots: Mapping[int, SlotColors]
    bg: RGB | None = None

    _styles: dict[int, StyleQuad] = field(
        init=False, repr=False, compare=False, default_factory=dict[int, StyleQuad]
    )
    _fallback: StyleQuad = field(
        init=False,
        repr=False,
        compare=False,
        default_factory=lambda: (
            Style(fg=_WHITE),
            Style(fg=_WHITE),
            Style(fg=_WHITE),
            Style(fg=_WHITE),
        ),
    )

    @classmethod
    def from_theme(cls, theme: Theme) -> PixelPalette:
        """Derive the eight-slot stage palette from a theme's role groups.

        The slots read accent, inline code, success, warning, danger, the
        first heading, muted and faint -- the theme's colour vocabulary in
        the order a pixel scene spends it.  Each slot's cool colour is 38%
        of its main colour per channel, and the stage keeps a transparent
        background.  A token that names no RGB value falls back to the
        showcase's fixed hue for that slot, so a theme built from ANSI names
        alone still yields a usable palette.
        """
        tokens = (
            theme.content.accent,
            theme.content.inline_code,
            theme.status.success,
            theme.status.warning,
            theme.status.danger,
            theme.content.headings[0],
            theme.text.muted,
            theme.text.faint,
        )
        slots: dict[int, SlotColors] = {}
        for index, (style, fallback) in enumerate(
            zip(tokens, _FALLBACKS, strict=True), start=1
        ):
            main = _token_rgb(style, fallback)
            cool = (
                round(main[0] * 0.38),
                round(main[1] * 0.38),
                round(main[2] * 0.38),
            )
            slots[index] = (main, cool)
        return cls(slots=slots)

    def __post_init__(self) -> None:
        object.__setattr__(self, "slots", MappingProxyType(dict(self.slots)))
        styles: dict[int, StyleQuad] = {}
        for slot_id, (main, cool) in self.slots.items():
            if not 1 <= slot_id <= 255:
                raise ValueError(f"palette slot id must be 1..255, got {slot_id}")
            styles[slot_id] = (
                Style(fg=main),
                Style(fg=cool),
                Style(fg=main, bg=self.bg),
                Style(fg=cool, bg=self.bg),
            )
        object.__setattr__(self, "_styles", styles)
        object.__setattr__(
            self,
            "_fallback",
            (
                Style(fg=_WHITE),
                Style(fg=_WHITE),
                Style(fg=_WHITE, bg=self.bg),
                Style(fg=_WHITE, bg=self.bg),
            ),
        )

    def tables(self) -> tuple[Mapping[int, StyleQuad], StyleQuad]:
        """The prebuilt slot table and the white fallback, for the quantizer."""
        return (self._styles, self._fallback)
