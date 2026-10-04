"""Style value type: a frozen SGR-style builder over a 16-color named palette.

This module is the single place that knows how a :class:`Style` turns into SGR
escape bytes.  Terminal-width measurement lives in :mod:`mocode_tui.text`;
line assembly lives in :mod:`mocode_tui.lines`.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ACCENT",
    "BORDER",
    "CODE",
    "CURSOR",
    "DIM",
    "ERROR",
    "FG_CODES",
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


def _sgr_codes(style: "Style") -> list[str]:
    """Ordered SGR parameter list for ``style`` (attributes, then fg, then bg)."""
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
    if style.fg is not None:
        codes.append(str(FG_CODES[style.fg]))
    if style.bg is not None:
        codes.append(str(FG_CODES[style.bg] + 10))
    return codes


@dataclass(frozen=True)
class Style:
    """An immutable terminal style.

    ``fg``/``bg`` are names from :data:`FG_CODES`; unknown names raise
    ``KeyError`` from :meth:`prefix` (an internal error, never silently
    swallowed).  Instances are frozen and hashable, so the SGR prefix can be
    memoized per instance without observable mutation.
    """

    fg: str | None = None
    bg: str | None = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False

    def prefix(self) -> str:
        """SGR prefix that switches a terminal into this style.

        Returns ``""`` when the style changes nothing.  The value is computed
        at most once per instance (frozen instances are safely cacheable).
        """
        try:
            return self.__dict__["_prefix"]
        except KeyError:
            pass
        codes = _sgr_codes(self)
        prefix = "\x1b[" + ";".join(codes) + "m" if codes else ""
        # Bypass the frozen __setattr__; the cache key never collides with a
        # field name and is invisible to eq/hash (field-based only).
        object.__setattr__(self, "_prefix", prefix)
        return prefix

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
        )


# Semantic constants: what components reach for by default.
NONE = Style()
DIM = Style(dim=True)
MUTED = Style(fg="bright_black")
ACCENT = Style(fg="cyan", bold=True)
SUCCESS = Style(fg="green")
ERROR = Style(fg="red", bold=True)
WARNING = Style(fg="yellow")
BORDER = Style(fg="bright_black")
CODE = Style(fg="yellow")
CURSOR = Style(reverse=True)
SELECTION = Style(reverse=True, dim=True)
