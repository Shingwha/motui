"""The pixel core: sub-cell rasters quantized into row-model lines.

A terminal paints characters, so "pixels" are simulated: one :class:`Raster`
holds a ``cols*2 x rows*4`` sub-cell grid (braille geometry, roughly square
on a typical terminal font) of *slots* (which object a sub-cell belongs to)
and *heat* (how freshly it was inked).  :func:`quantize` turns one or more
rasters into :class:`~motui.kernel.cell.Line` values -- the ordinary row
model -- so pixels are just cells and nothing downstream changes.

**The two-color ceiling.**  A character cell carries exactly one glyph
shaped from a single-color template plus one SGR foreground and one
background -- so every quantized cell answers at most two colors, one ``fg``
for its ink and one ``bg`` for what is behind it.  Sub-pixel color within a
cell is a terminal fact, not a feature any quantizer can add; that ceiling
is why the raster stores slot + heat per sub-cell and the quantizer chooses
one slot color per cell (majority slot over the lit sub-pixels).

**Layers.**  ``quantize`` consumes a sequence of :class:`PixelLayer` values,
each a ``(raster, marker)`` pair with ``marker`` either ``"braille"`` (dot
matrices: curves, outlines, line art) or ``"half"`` (2x2 block fills: solid
shapes, washes).  A cell belongs to the **first layer in the sequence that
has ink in it** -- upper layers cover lower ones, first come first served by
layer order -- and the caller expresses any "mixed" marker by passing two
layers (a ``"half"`` fill under a ``"braille"`` line layer).  The kernel
never invents a mixed character.

This module is pure values and pure functions: no I/O, no terminal bytes,
stdlib only.  Every product is a row-model value, so pixel frames compose
with text through the ordinary :class:`~motui.kernel.cell.Surface` machinery.

Measured cost of :func:`quantize` on a 76x24 frame (CPython 3.12.14,
Windows, 300-frame average): **3.6 ms/frame** for a demo-like sparse
one-layer scene, **7.9 ms/frame** for a worst-case two-layer scene with
every cell inked and mixed slots -- inside the 16.7 ms a 60 fps budget
allows, with the per-cell ``Canvas`` bookkeeping that cost the prototype
13 ms never entering the picture (rows are built directly).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from .cell import Line, Segment
from .style import Style

__all__ = [
    "BRAILLE_BITS",
    "COOL_AT",
    "HALF_BOTTOM",
    "HALF_FULL",
    "HALF_TOP",
    "PixelLayer",
    "PixelPalette",
    "Raster",
    "quantize",
]


#: Braille dot bits by ``(sub-column, sub-row)`` inside one cell, the
#: standard U+2800 encoding: dot 1 sits at the cell's top left, and the
#: column-major pairs read ``(0x01 0x04 / 0x02 0x08 ...)`` down each
#: sub-column.  The glyph for a cell is ``chr(0x2800 + OR of its lit dots)``.
BRAILLE_BITS: tuple[tuple[int, int, int, int], tuple[int, int, int, int]] = (
    (0x01, 0x02, 0x04, 0x40),
    (0x08, 0x10, 0x20, 0x80),
)

#: Upper half block (the ``"half"`` marker with only the top sub-rows lit).
HALF_TOP = "\u2580"

#: Lower half block (the ``"half"`` marker with only the bottom sub-rows lit).
HALF_BOTTOM = "\u2584"

#: Full block (the ``"half"`` marker with both sub-rows lit).
HALF_FULL = "\u2588"

#: Heat at or above which a sub-cell still counts as lit; below it the
#: sub-cell has decayed into emptiness (its slot byte is stale and ignored).
_HEAT_LIT = 128

#: Fresh ink (heat at or above this) quantizes to the slot's main color;
#: cooler ink quantizes to the slot's cool color -- the cooling trail look.
COOL_AT = 192


def _heat_step(amount: int) -> bytes:
    """A 256-entry map subtracting ``amount`` from every heat value."""
    return bytes(v - amount if v > amount else 0 for v in range(256))


class Raster:
    """A ``cols x rows`` cell grid of ``cols*2 x rows*4`` sub-cells.

    Two parallel ``bytearray`` grids, both indexed ``y * width + x`` over
    sub-cell coordinates (``width == cols * 2``, ``height == rows * 4``):

    - ``slot`` -- which object a sub-cell belongs to: ``0`` is empty,
      ``1..255`` are caller-chosen slot ids (a palette maps ids to colors).
    - ``heat`` -- freshness ``0..255``; :meth:`set` re-freshens to 255 and
      :meth:`decay` cools the whole grid in one C-speed pass.  A sub-cell
      with heat below ``_HEAT_LIT`` is dead regardless of its slot byte.

    The dual grid is what makes trails cheap: drawing is "slot now, heat
    full", decay is one translate, and the quantizer reads ``(slot, heat)``
    to pick both the owning color and how cooled it is.
    """

    __slots__ = ("cols", "heat", "height", "rows", "slot", "width")

    def __init__(self, cols: int, rows: int) -> None:
        if cols < 0 or rows < 0:
            raise ValueError(f"raster size must be non-negative, got {cols}x{rows}")
        self.cols = cols
        self.rows = rows
        self.width = cols * 2
        self.height = rows * 4
        size = self.width * self.height
        self.slot = bytearray(size)
        self.heat = bytearray(size)

    def clear(self) -> None:
        """Every sub-cell's slot and heat to zero, two C-speed fills."""
        self.slot[:] = bytes(len(self.slot))
        self.heat[:] = bytes(len(self.heat))

    def decay(self, amount: int) -> None:
        """Subtract ``amount`` from every heat value (the trail primitive).

        Slot bytes are untouched -- objects keep their identity while their
        ink cools -- and a non-positive ``amount`` does nothing.  The whole
        grid decays through one ``bytes.translate`` table, so the cost is a
        single C-speed copy, never a Python loop over sub-cells.
        """
        if amount <= 0:
            return
        self.heat = self.heat.translate(_heat_step(amount))

    def set(self, x: float, y: float, slot: int = 1) -> None:
        """Ink one sub-cell: its slot id stored, its heat reset to full.

        Coordinates are sub-cell positions; fractional values truncate.
        Out-of-range coordinates clip silently (drawing never checks).  A
        slot id of ``0`` (empty) or less does nothing -- only ``1..255``
        carry ink.
        """
        if slot <= 0:
            return
        ix, iy = int(x), int(y)
        if 0 <= ix < self.width and 0 <= iy < self.height:
            index = iy * self.width + ix
            self.slot[index] = slot
            self.heat[index] = 255

    # -- primitives (sub-cell coordinates, silent clipping, slot-colored) --

    def line(self, x0: float, y0: float, x1: float, y1: float, slot: int = 1) -> None:
        """Bresenham line between two sub-cell points."""
        ix0, iy0, ix1, iy1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(ix1 - ix0), -abs(iy1 - iy0)
        sx = 1 if ix0 < ix1 else -1
        sy = 1 if iy0 < iy1 else -1
        err = dx + dy
        while True:
            self.set(ix0, iy0, slot)
            if ix0 == ix1 and iy0 == iy1:
                return
            step = 2 * err
            if step >= dy:
                err += dy
                ix0 += sx
            if step <= dx:
                err += dx
                iy0 += sy

    def rect(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        fill: bool = False,
        slot: int = 1,
    ) -> None:
        """Axis-aligned rectangle, outline by default or filled."""
        ix0, ix1 = sorted((int(x0), int(x1)))
        iy0, iy1 = sorted((int(y0), int(y1)))
        for y in range(max(0, iy0), min(self.height - 1, iy1) + 1):
            edge = y in (iy0, iy1)
            for x in range(max(0, ix0), min(self.width - 1, ix1) + 1):
                if fill or edge or x in (ix0, ix1):
                    self.set(x, y, slot)

    def disc(self, cx: float, cy: float, r: float, slot: int = 1) -> None:
        """Filled circle: one horizontal span of sub-cells per sub-row."""
        if r <= 0:
            self.set(cx, cy, slot)
            return
        top, bottom = int(cy - r), int(cy + r)
        for y in range(top, bottom + 1):
            dy = y - cy
            span = r * r - dy * dy
            if span < 0:
                continue
            half = math.sqrt(span)
            for x in range(int(cx - half), int(cx + half) + 1):
                self.set(x, y, slot)

    def ring(self, cx: float, cy: float, r: float, thickness: int = 1, slot: int = 1) -> None:
        """Circle outline of ``thickness`` sub-cells, parametric."""
        if r <= 0:
            return
        steps = max(32, int(2 * math.pi * r * 2))
        for index in range(steps):
            angle = 2 * math.pi * index / steps
            cos, sin = math.cos(angle), math.sin(angle)
            for offset in range(thickness):
                radius = r + offset - (thickness - 1) / 2
                self.set(cx + radius * cos, cy + radius * sin, slot)


#: One quantization layer: a raster plus the marker its cells quantize to.
#: A layer is a plain frozen tuple; "mixed" markers are expressed by passing
#: two layers (a ``"half"`` fill under a ``"braille"`` line layer), never by
#: a magic marker string.
PixelLayer = tuple[Raster, Literal["half", "braille"]]


#: ``chr(0x2800 + bits)`` for every dot pattern, precomputed so the inner
#: loop indexes a tuple instead of calling ``chr`` once per cell.
_BRAILLE_CHARS: tuple[str, ...] = tuple(chr(0x2800 + bits) for bits in range(256))


@dataclass(frozen=True, slots=True)
class PixelPalette:
    """The colors a quantize may spend: slot color pairs and one background.

    The palette is a caller-provided value -- the kernel ships no pixel
    theme -- mapping slot ids (what a :class:`Raster` stores, ``1..255``)
    to ``(main, cool)`` RGB pairs: fresh ink quantizes to the slot's *main*
    color, and once a cell's peak heat drops below :data:`COOL_AT` it
    quantizes to the *cool* color -- the cooling-trail look.  ``bg`` is the
    color a ``"half"`` layer's unlit sub-rows show (its styles carry it as
    the SGR background); ``"braille"`` styles are fg-only, off dots stay
    transparent.

    The four styles per slot (main/cool, with and without ``bg``) plus the
    plain ``bg`` style are prebuilt here once, so :func:`quantize` answers
    every cell with a dict lookup and reuses one style *object* per
    (slot, state) -- the identity same-style run fusion short-circuits on.
    A raster slot with no palette entry quantizes to white.
    """

    slots: Mapping[int, tuple[tuple[int, int, int], tuple[int, int, int]]]
    bg: tuple[int, int, int]

    _styles: dict[int, tuple[Style, Style, Style, Style]] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )
    _bg_style: Style = field(init=False, repr=False, compare=False, default=Style())
    _fallback: tuple[Style, Style, Style, Style] = field(
        init=False, repr=False, compare=False, default=()
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "slots", MappingProxyType(dict(self.slots)))
        styles: dict[int, tuple[Style, Style, Style, Style]] = {}
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
        object.__setattr__(self, "_bg_style", Style(bg=self.bg))
        white = (255, 255, 255)
        object.__setattr__(
            self,
            "_fallback",
            (
                Style(fg=white),
                Style(fg=white),
                Style(fg=white, bg=self.bg),
                Style(fg=white, bg=self.bg),
            ),
        )


def _majority(stats: dict[int, list[int]]) -> tuple[int, int]:
    """The majority slot's ``(id, peak heat)`` among a cell's lit sub-cells.

    Majority by lit count, ties broken by peak heat then by the lower slot
    id -- deterministic frame over frame.  Only mixed-slot cells pay for
    this: a single-slot cell (the common case) skips the dict entirely.
    """
    slot_id, entry = max(stats.items(), key=lambda item: (item[1][0], item[1][1], -item[0]))
    return slot_id, entry[1]


def quantize(layers: Sequence[PixelLayer], palette: PixelPalette) -> list[Line]:
    """Quantize layered rasters into one :class:`Line` per cell row.

    ``layers`` is a sequence of ``(raster, marker)`` pairs sharing one
    geometry (one ``ValueError`` otherwise); ``palette`` maps their slot
    ids to colors.  Every cell answers to the first layer that has ink in
    it; its marker picks the glyph:

    - ``"braille"`` -- ``U+2800 + bits`` over the cell's eight sub-cells
      (:data:`BRAILLE_BITS` order), one fg from the majority lit slot;
      off dots stay transparent (fg-only style).
    - ``"half"`` -- the cell's four sub-rows fold in two: both halves lit
      is :data:`HALF_FULL`, top-only :data:`HALF_TOP`, bottom-only
      :data:`HALF_BOTTOM`; the style carries ``bg`` so an unlit sub-row
      shows the palette background.

    A cell with no ink anywhere is a plain space -- the terminal's own
    background shows through, so a canvas never paints a rectangle of its
    own unless the caller fills one explicitly.  Within an inked
    ``"half"`` cell the unlit sub-rows still show the palette background.
    Adjacent cells with the same character and the very same style object
    fuse into one ``Segment``, so a frame is a handful of runs, not a
    per-cell bookkeeping walk.  An empty ``layers`` quantizes to no rows.

    The scan has one shape for both markers: walk the cell's eight
    sub-cells through a flat offset table, tracking the braille bits, the
    lit counts per half, and the owning slot -- where "owning" keeps a
    single-slot fast path (one slot id, its peak heat, no dict); only a
    cell inked by two or more slots falls back to the majority vote in
    :func:`_majority`.  The palette answers every cell with one dict
    lookup, returning a style *object* the run fusion below compares by
    identity.
    """
    if not layers:
        return []
    cols = layers[0][0].cols
    rows = layers[0][0].rows
    grids: list[tuple[bytearray, bytearray, int]] = []
    for raster, marker in layers:
        if raster.cols != cols or raster.rows != rows:
            raise ValueError(
                f"quantize layers must share one geometry, got {cols}x{rows}"
                f" and {raster.cols}x{raster.rows}"
            )
        if marker not in ("half", "braille"):
            raise ValueError(f"unknown pixel marker {marker!r}: expected 'half' or 'braille'")
        grids.append((raster.slot, raster.heat, 0 if marker == "braille" else 1))
    styles_get = palette._styles.get
    fallback = palette._fallback
    width = cols * 2
    lit = _HEAT_LIT
    cool_at = COOL_AT
    chars = _BRAILLE_CHARS
    majority = _majority
    # Dot bits paired with sub-cell offsets from the cell's top left corner,
    # upper two sub-rows first: one scan shape serves both markers.
    top_offsets = (
        (0x01, 0),
        (0x08, 1),
        (0x02, width),
        (0x10, width + 1),
    )
    bottom_offsets = (
        (0x04, width * 2),
        (0x20, width * 2 + 1),
        (0x40, width * 3),
        (0x80, width * 3 + 1),
    )
    cell_rows: list[Line] = []
    for cy in range(rows):
        row_base = cy * 4 * width
        segments: list[Segment] = []
        run_char: str | None = None
        run_style: Style | None = None
        run_start = 0
        for cx in range(cols + 1):
            char: str | None = None
            style: Style | None = None
            if cx < cols:
                col_base = row_base + cx * 2
                for slot_grid, heat_grid, kind in grids:
                    bits = 0
                    top = 0
                    bottom = 0
                    solo = 0  # the only slot seen so far (0 = none yet)
                    solo_n = 0
                    peak = 0
                    stats: dict[int, list[int]] | None = None
                    for bit, off in top_offsets:
                        cell = col_base + off
                        heat = heat_grid[cell]
                        if heat >= lit:
                            bits |= bit
                            top += 1
                            inked = slot_grid[cell]
                            if solo == 0:
                                solo, solo_n, peak = inked, 1, heat
                            elif inked == solo:
                                solo_n += 1
                                if heat > peak:
                                    peak = heat
                            else:
                                if stats is None:
                                    stats = {solo: [solo_n, peak]}
                                entry = stats.get(inked)
                                if entry is None:
                                    stats[inked] = [1, heat]
                                else:
                                    entry[0] += 1
                                    if heat > entry[1]:
                                        entry[1] = heat
                    for bit, off in bottom_offsets:
                        cell = col_base + off
                        heat = heat_grid[cell]
                        if heat >= lit:
                            bits |= bit
                            bottom += 1
                            inked = slot_grid[cell]
                            if solo == 0:
                                solo, solo_n, peak = inked, 1, heat
                            elif inked == solo:
                                solo_n += 1
                                if heat > peak:
                                    peak = heat
                            else:
                                if stats is None:
                                    stats = {solo: [solo_n, peak]}
                                entry = stats.get(inked)
                                if entry is None:
                                    stats[inked] = [1, heat]
                                else:
                                    entry[0] += 1
                                    if heat > entry[1]:
                                        entry[1] = heat
                    if bits:
                        if kind == 0:  # braille: fg-only, transparent off dots
                            char = chars[bits]
                            variant = 0
                        else:  # half: the bg rides so an unlit sub-row shows it
                            char = HALF_FULL if top and bottom else HALF_TOP if top else HALF_BOTTOM
                            variant = 2
                        if stats is None:  # single-slot cell: no vote needed
                            quad = styles_get(solo) or fallback
                            style = quad[variant] if peak >= cool_at else quad[variant + 1]
                        else:
                            slot_id, peak = majority(stats)
                            quad = styles_get(slot_id) or fallback
                            style = quad[variant] if peak >= cool_at else quad[variant + 1]
                        break
                if char is None:  # no layer has ink in this cell
                    char = " "
                    style = None
            if char == run_char and style is run_style:
                continue  # same run: fuse by identity, no segment spent
            if run_char is not None:
                count = cx - run_start
                if run_style is None:
                    segments.append(Segment(" " * count))
                else:
                    segments.append(Segment(run_char * count, run_style))
            run_char = char
            run_style = style
            run_start = cx
        cell_rows.append(Line(tuple(segments)))
    return cell_rows
