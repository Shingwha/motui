"""The colors a quantizer may spend: slot color pairs and one background."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ..kernel.style import Style
from .types import RGB, SlotColors

__all__ = ["PixelPalette", "StyleQuad"]

#: The four styles one slot can answer: main/cool, with and without ``bg``.
StyleQuad = tuple[Style, Style, Style, Style]

_WHITE: RGB = (255, 255, 255)


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
