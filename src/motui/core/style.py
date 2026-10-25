"""Style value type: a frozen SGR-style builder over a named + truecolor palette.

This module is the single place that knows how a :class:`Style` turns into SGR
escape bytes.  Terminal-width measurement lives in :mod:`motui.core.text`;
line assembly lives in :mod:`motui.core.lines`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

__all__ = [
    "FG_CODES",
    "NONE",
    "RESET",
    "Color",
    "ColorMode",
    "Style",
    "quantize",
    "sgr_prefix",
]

#: Foreground name -> base SGR code (30-37); backgrounds use the code + 10.
#: A read-only mapping: the palette is a contract, not a configuration knob.
FG_CODES: Mapping[str, int] = MappingProxyType(
    {
        "black": 30,
        "red": 31,
        "green": 32,
        "yellow": 33,
        "blue": 34,
        "magenta": 35,
        "cyan": 36,
        "white": 37,
        "bright_black": 90,
        "bright_red": 91,
        "bright_green": 92,
        "bright_yellow": 93,
        "bright_blue": 94,
        "bright_magenta": 95,
        "bright_cyan": 96,
        "bright_white": 97,
    }
)

#: SGR reset sequence.
RESET = "\x1b[0m"

#: Matches a ``#rrggbb`` hex color (case-insensitive).
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$")


def _hex_rgb(value: str) -> tuple[int, int, int] | None:
    """Parse a ``#rrggbb`` string into an ``(r, g, b)`` tuple (``None`` if not)."""
    match = _HEX_RE.match(value)
    if match is None:
        return None
    return tuple(int(part, 16) for part in match.groups())  # type: ignore[return-value]


def _truecolor_code(rgb: tuple[int, int, int], background: bool) -> str:
    """SGR 24-bit truecolor parameter for an ``(r, g, b)`` tuple."""
    lead = 48 if background else 38
    return f"{lead};2;{rgb[0]};{rgb[1]};{rgb[2]}"


@dataclass(frozen=True, slots=True)
class Color:
    """A color in both authoring and terminal vocabularies.

    ``value`` is the authoring color -- a ``#rrggbb`` string or an
    ``(r, g, b)`` tuple -- and renders as a 24-bit truecolor parameter.
    ``ansi`` is the color's name in :data:`FG_CODES`: the fallback a
    16-color terminal uses, so a brand hue keeps its intended hue instead
    of being quantized from RGB.  ``None`` means "quantize it", which is
    also the historical behavior of a bare hex/tuple color.

    A ``Color`` is a frozen value, so it may sit inside a :class:`Style`
    and keep the style's prefix cache valid.  An ``ansi`` that is not an
    :data:`FG_CODES` name is a construction error.
    """

    value: "str | tuple[int, int, int]"
    ansi: "str | None" = None

    def __post_init__(self) -> None:
        if self.ansi is not None and self.ansi not in FG_CODES:
            raise ValueError(
                f"unknown ANSI color name {self.ansi!r}: expected one of "
                f"{sorted(FG_CODES)} or None"
            )


def _color_rgb(color: Color) -> tuple[int, int, int] | None:
    """The RGB triple ``color.value`` names, or ``None`` for a named color."""
    value = color.value
    if isinstance(value, tuple):
        return value
    return _hex_rgb(value)


def _color_name(color: Color) -> str | None:
    """The ``FG_CODES`` name ``color.value`` is, if it is a bare name."""
    value = color.value
    if isinstance(value, str) and not _HEX_RE.match(value):
        return value
    return None


def _native_color_code(
    color: "Color | str | tuple[int, int, int]", *, background: bool
) -> str:
    """The truecolor-mode SGR parameter for one color.

    A :class:`Color` uses its authoring ``value`` (a name inside a
    ``Color`` still keeps its base code); a bare name from :data:`FG_CODES`
    keeps its base code (unknown names raise ``KeyError``); a hex string or
    tuple emits a 24-bit parameter.
    """
    offset = 10 if background else 0
    if isinstance(color, Color):
        name = _color_name(color)
        if name is not None:
            return str(FG_CODES[name] + offset)
        rgb = _color_rgb(color)
        return _truecolor_code(rgb, background)  # type: ignore[arg-type]
    if isinstance(color, tuple):
        return _truecolor_code(color, background)
    if _HEX_RE.match(color):
        return _truecolor_code(_hex_rgb(color), background)  # type: ignore[arg-type]
    return str(FG_CODES[color] + offset)


def _sgr_codes(style: "Style") -> list[str]:
    """Ordered SGR parameter list for ``style`` (attributes, then fg, then bg).

    A color is a :class:`Color`, a name from :data:`FG_CODES` (unknown names
    raise ``KeyError``), a ``#rrggbb`` string, or an ``(r, g, b)`` tuple --
    the last three forms emit what they always did.
    """
    codes: list[str] = []
    if style.bold:
        codes.append("1")
    if style.dim:
        codes.append("2")
    if style.italic:
        codes.append("3")
    if style.underline:
        codes.append("4")
    if style.reverse:
        codes.append("7")
    if style.strike:
        codes.append("9")
    if style.fg is not None:
        codes.append(_native_color_code(style.fg, background=False))
    if style.bg is not None:
        codes.append(_native_color_code(style.bg, background=True))
    return codes


@dataclass(frozen=True, slots=True)
class Style:
    """An immutable terminal style.

    ``fg``/``bg`` are colors: a :class:`Color`, a name from
    :data:`FG_CODES` (unknown names raise ``KeyError`` from :meth:`prefix`
    -- an internal error, never silently swallowed), a ``#rrggbb`` string,
    or an ``(r, g, b)`` tuple.  The hex and tuple forms emit 24-bit
    truecolor SGR parameters; a :class:`Color` carries its own 16-color
    fallback beside the truecolor value.  Instances are frozen and
    hashable (tuples hash fine), so the SGR prefix can be memoized per
    instance without observable mutation.
    """

    fg: "Color | str | tuple[int, int, int] | None" = None
    bg: "Color | str | tuple[int, int, int] | None" = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False
    strike: bool = False
    #: Derived cache: the SGR prefix, computed at most once per instance and
    #: invisible to eq/hash/repr (it follows from the fields alone).  ``None``
    #: is "not computed yet": a style that changes nothing legitimately
    #: computes to the empty string, so the two states stay told apart.
    _prefix: str | None = field(init=False, compare=False, repr=False, default=None)

    def prefix(self) -> str:
        """SGR prefix that switches a terminal into this style.

        Returns ``""`` when the style changes nothing.  The value is computed
        at most once per instance (frozen instances are safely cacheable):
        even the unstyled default -- the commonest path of all -- never
        rebuilds its SGR parameters.
        """
        if self._prefix is None:
            codes = _sgr_codes(self)
            object.__setattr__(
                self, "_prefix", "\x1b[" + ";".join(codes) + "m" if codes else ""
            )
        return self._prefix

    def merge(self, other: "Style") -> "Style":
        """Return a new style with ``other`` applied on top of ``self``.

        ``None`` fields of ``other`` pass through; boolean attributes are
        OR-ed.  Neither operand is mutated.
        """
        return Style(
            fg=other.fg if other.fg is not None else self.fg,
            bg=other.bg if other.bg is not None else self.bg,
            bold=self.bold or other.bold,
            dim=self.dim or other.dim,
            italic=self.italic or other.italic,
            underline=self.underline or other.underline,
            reverse=self.reverse or other.reverse,
            strike=self.strike or other.strike,
        )


# ---------------------------------------------------------------------------
# Capability and downgrade
# ---------------------------------------------------------------------------

#: The color capability a screen is painted for: 24-bit truecolor, the xterm
#: 256-color palette, the sixteen base colors, or no color at all -- the
#: attributes survive every mode, ``"none"`` included.
ColorMode = Literal["truecolor", "256", "16", "none"]

#: The xterm 256-color palette: the 6x6x6 cube's channel levels and the
#: 24-step grayscale ramp the quantizer searches beside it.
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)
_GRAY_STEPS = 24

#: The standard xterm reference table for the sixteen base colors, in
#: :data:`FG_CODES` order (index 0 = ``black`` ... 15 = ``bright_white``);
#: ``"16"`` snaps a color to the nearest entry here.
_XTERM16_NAMES = (
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
)
_XTERM16_RGB: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0),
    (205, 0, 0),
    (0, 205, 0),
    (205, 205, 0),
    (0, 0, 238),
    (205, 0, 205),
    (0, 205, 205),
    (229, 229, 229),
    (127, 127, 127),
    (255, 0, 0),
    (0, 255, 0),
    (255, 255, 0),
    (92, 92, 255),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 255),
)


def _distance(rgb: tuple[int, int, int], other: tuple[int, int, int]) -> int:
    """Squared euclidean distance between two RGB triples."""
    return sum((a - b) ** 2 for a, b in zip(rgb, other))


def _nearest_cube(rgb: tuple[int, int, int]) -> tuple[int, tuple[int, int, int]]:
    """The nearest 6x6x6-cube entry: its palette index and its RGB triple."""
    levels = tuple(
        min(range(len(_CUBE_LEVELS)), key=lambda i: abs(value - _CUBE_LEVELS[i]))
        for value in rgb
    )
    index = 16 + 36 * levels[0] + 6 * levels[1] + levels[2]
    return index, (  # type: ignore[return-value]
        _CUBE_LEVELS[levels[0]],
        _CUBE_LEVELS[levels[1]],
        _CUBE_LEVELS[levels[2]],
    )


def _nearest_gray(rgb: tuple[int, int, int]) -> tuple[int, tuple[int, int, int]]:
    """The nearest grayscale-ramp entry: its palette index and its RGB triple."""
    average = sum(rgb) / 3
    step = max(0, min(_GRAY_STEPS - 1, int((average - 8) / 10 + 0.5)))
    value = 8 + 10 * step
    return 232 + step, (value, value, value)


def quantize(rgb: tuple[int, int, int], mode: ColorMode = "256") -> int:
    """The palette index ``rgb`` quantizes to under ``mode``.

    ``"256"`` searches the xterm 256-color palette -- the 6x6x6 color cube
    (indices 16..231) and the 24-step grayscale ramp (232..255) -- and
    answers the nearer index; a tie keeps the cube entry.  ``"16"`` snaps
    to the nearest of the sixteen base colors of the reference table.  The
    full-precision and endless modes are not real quantizing paths:
    ``"truecolor"`` answers the 256-color index (the stable approximation a
    direct caller gets) and ``"none"`` answers ``-1`` -- no color, which is
    how :func:`sgr_prefix` reads it.
    """
    if mode == "none":
        return -1
    if mode == "16":
        return min(
            range(len(_XTERM16_RGB)), key=lambda i: _distance(rgb, _XTERM16_RGB[i])
        )
    cube_index, cube_rgb = _nearest_cube(rgb)
    gray_index, gray_rgb = _nearest_gray(rgb)
    if _distance(rgb, gray_rgb) < _distance(rgb, cube_rgb):
        return gray_index
    return cube_index


def _mode_color_code(
    color: "Color | str | tuple[int, int, int] | None",
    mode: ColorMode,
    *,
    background: bool,
) -> str | None:
    """One downgraded SGR parameter for ``color``, or ``None`` to drop it.

    A named color keeps its base code in every mode: a name is already the
    terminal's own vocabulary, so there is nothing to quantize.  A
    :class:`Color` whose ``value`` is a bare name behaves the same; a
    :class:`Color` carrying RGB uses its ``ansi`` name under ``"16"`` when
    one is given, and is quantized otherwise.  A bare hex string or tuple
    is quantized and emitted as ``38;5;N``/``48;5;N`` under ``"256"`` and
    as the nearest base color's code under ``"16"``.  ``"none"`` drops
    every color, the attributes aside.
    """
    if color is None or mode == "none":
        return None
    offset = 10 if background else 0
    if isinstance(color, Color):
        name = _color_name(color)
        if name is not None:
            return str(FG_CODES[name] + offset)
        if mode == "16" and color.ansi is not None:
            return str(FG_CODES[color.ansi] + offset)
        rgb = _color_rgb(color)
        index = quantize(rgb, mode)  # type: ignore[arg-type]
        if mode == "16":
            return str(FG_CODES[_XTERM16_NAMES[index]] + offset)
        return f"{48 if background else 38};5;{index}"
    if isinstance(color, tuple):
        rgb = color
    elif _HEX_RE.match(color):
        rgb = _hex_rgb(color)  # type: ignore[assignment]
    else:
        return str(FG_CODES[color] + offset)
    index = quantize(rgb, mode)
    if mode == "16":
        return str(FG_CODES[_XTERM16_NAMES[index]] + offset)
    return f"{48 if background else 38};5;{index}"


def _mode_codes(style: "Style", mode: ColorMode) -> list[str]:
    """Ordered SGR parameters for ``style`` under a downgraded ``mode``.

    The same order :func:`_sgr_codes` emits -- attributes, then fg, then bg
    -- rebuilt with the colors downgraded.  It lives beside that function
    rather than inside it, so ``Style.prefix()``'s cached path is untouched
    by the capability story.
    """
    codes: list[str] = []
    if style.bold:
        codes.append("1")
    if style.dim:
        codes.append("2")
    if style.italic:
        codes.append("3")
    if style.underline:
        codes.append("4")
    if style.reverse:
        codes.append("7")
    if style.strike:
        codes.append("9")
    for color, background in ((style.fg, False), (style.bg, True)):
        code = _mode_color_code(color, mode, background=background)
        if code is not None:
            codes.append(code)
    return codes


def sgr_prefix(style: "Style", mode: ColorMode = "truecolor") -> str:
    """SGR prefix that switches a terminal of capability ``mode`` into ``style``.

    ``"truecolor"`` returns :meth:`Style.prefix` -- the instance cache, so
    the default path's bytes are exactly what they always were.  The
    downgraded modes rebuild the parameters: a hex or tuple color is
    quantized (:func:`quantize`), a named color keeps its base code, and
    ``"none"`` drops the colors while every attribute survives.  The answer
    is never cached: it depends on the terminal, and
    :meth:`Style.prefix`'s cache must stay capability-free.
    """
    if mode == "truecolor":
        return style.prefix()
    codes = _mode_codes(style, mode)
    return "\x1b[" + ";".join(codes) + "m" if codes else ""


#: The unstyled default: every component's baseline, and the band whose fill
#: is the documented no-op fast path.
NONE = Style()
