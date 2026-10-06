"""Style value type: a frozen SGR-style builder over a named + truecolor palette.

This module is the single place that knows how a :class:`Style` turns into SGR
escape bytes.  Terminal-width measurement lives in :mod:`mocode_tui.core.text`;
line assembly lives in :mod:`mocode_tui.core.lines`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "ACCENT",
    "BORDER",
    "CODE",
    "CURSOR",
    "DIM",
    "ERROR",
    "FG_CODES",
    "HEADING",
    "INLINE_CODE",
    "LINK",
    "LIST_MARKER",
    "MUTED",
    "NONE",
    "RESET",
    "SELECTION",
    "SUCCESS",
    "WARNING",
    "Style",
]

#: Foreground name -> base SGR code (30-37); backgrounds use the code + 10.
FG_CODES: dict[str, int] = {
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


def _sgr_codes(style: "Style") -> list[str]:
    """Ordered SGR parameter list for ``style`` (attributes, then fg, then bg).

    A color is a name from :data:`FG_CODES` (unknown names raise ``KeyError``),
    a ``#rrggbb`` string, or an ``(r, g, b)`` tuple -- the latter two emit
    24-bit truecolor parameters (``38;2;r;g;b`` / ``48;2;r;g;b``).
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
        if isinstance(style.fg, tuple):
            codes.append(_truecolor_code(style.fg, background=False))
        elif isinstance(style.fg, str) and _HEX_RE.match(style.fg):
            codes.append(_truecolor_code(_hex_rgb(style.fg), background=False))
        else:
            codes.append(str(FG_CODES[style.fg]))
    if style.bg is not None:
        if isinstance(style.bg, tuple):
            codes.append(_truecolor_code(style.bg, background=True))
        elif isinstance(style.bg, str) and _HEX_RE.match(style.bg):
            codes.append(_truecolor_code(_hex_rgb(style.bg), background=True))
        else:
            codes.append(str(FG_CODES[style.bg] + 10))
    return codes


@dataclass(frozen=True)
class Style:
    """An immutable terminal style.

    ``fg``/``bg`` are colors: a name from :data:`FG_CODES` (unknown names raise
    ``KeyError`` from :meth:`prefix` -- an internal error, never silently
    swallowed), a ``#rrggbb`` string, or an ``(r, g, b)`` tuple.  The hex and
    tuple forms emit 24-bit truecolor SGR parameters.  Instances are frozen
    and hashable (tuples hash fine), so the SGR prefix can be memoized per
    instance without observable mutation.
    """

    fg: "str | tuple[int, int, int] | None" = None
    bg: "str | tuple[int, int, int] | None" = None
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


# Semantic constants: what components reach for by default.  The family is
# a soft GitHub-dark truecolor set -- the only 16-color blue is
# pure blue, which cannot read as "soft" -- and named colors stay available
# beside it: truecolor is a superset, not a replacement.
NONE = Style()
DIM = Style(dim=True)
MUTED = Style(fg="#8b949e")          # gray
ACCENT = Style(fg="#58a6ff", bold=True)  # soft blue
SUCCESS = Style(fg="#4bb563")        # soft green
ERROR = Style(fg="#e5534b", bold=True)  # soft red
WARNING = Style(fg="#d29922")        # amber
BORDER = NONE                        # no color: frames read in the terminal's
                                     # default foreground (the brightest base)
CODE = Style(fg="#a5d6ff")           # ice blue
CURSOR = Style(reverse=True)
#: The selection highlight: plain reverse video.  Any dimming on top would
#: dim the *foreground* a reverse paints with -- and a reversed foreground
#: is the highlight's *background* -- so the attribute would dim the
#: highlight itself: a whole-pane selection would read as a grey wash
#: instead of a selection.  Reverse alone leaves the colours exactly where
#: they were: a segment's own hue becomes the background, the terminal
#: default becomes the text, which is what a highlight is supposed to look
#: like on any terminal.
SELECTION = Style(reverse=True)
# The markdown palette: each construct gets its own hue, so normal prose
# reads in the terminal default while structure announces itself with
# color instead of weight (bold stays reserved for the **...** syntax).
HEADING = Style(fg="#e3b341")        # gold: the Markdown heading ladder
LINK = Style(fg="#58a6ff", underline=True)  # soft blue, underlined, not bold
INLINE_CODE = Style(fg="#f778ba")    # pink: inline `code`
LIST_MARKER = Style(fg="#bc8cff")    # soft purple: list bullets / numbers
