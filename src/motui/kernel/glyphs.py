"""The glyph vocabulary: the structural marks row components draw.

Glyphs are content, not style, so they stay out of :class:`Theme`; a host
supplies its own :class:`Glyphs` to change them. The seat helpers keep
glyph columns aligned across states."""

from __future__ import annotations

from dataclasses import dataclass

from .text import visible_width

__all__ = [
    "GLYPHS",
    "Border",
    "Glyphs",
    "pair_seat",
    "seat",
    "seat_width",
]


# ---------------------------------------------------------------------------
# Box drawing: the Border value and the Glyphs vocabulary
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Border:
    """The fourteen marks one box-drawing style needs; ``none`` paints spaces
    and keeps the reserved geometry."""

    top_left: str = "\u250c"
    top: str = "\u2500"
    top_tee: str = "\u252c"
    top_right: str = "\u2510"
    left: str = "\u2502"
    middle: str = "\u2500"
    cross: str = "\u253c"
    right: str = "\u2502"
    middle_left: str = "\u251c"
    middle_right: str = "\u2524"
    bottom_left: str = "\u2514"
    bottom: str = "\u2500"
    bottom_tee: str = "\u2534"
    bottom_right: str = "\u2518"

    @classmethod
    def square(cls) -> Border:
        """The square corners and light lines of the defaults."""
        return cls()

    @classmethod
    def rounded(cls) -> Border:
        """Square lines with rounded corners."""
        return cls(
            top_left="\u256d",
            top_right="\u256e",
            bottom_left="\u2570",
            bottom_right="\u256f",
        )

    @classmethod
    def heavy(cls) -> Border:
        """Heavy box-drawing lines."""
        return cls(
            top_left="\u250f",
            top="\u2501",
            top_tee="\u2533",
            top_right="\u2513",
            left="\u2503",
            middle="\u2501",
            cross="\u254b",
            right="\u2503",
            middle_left="\u2523",
            middle_right="\u252b",
            bottom_left="\u2517",
            bottom="\u2501",
            bottom_tee="\u253b",
            bottom_right="\u251b",
        )

    @classmethod
    def double(cls) -> Border:
        """Double box-drawing lines."""
        return cls(
            top_left="\u2554",
            top="\u2550",
            top_tee="\u2566",
            top_right="\u2557",
            left="\u2551",
            middle="\u2550",
            cross="\u256c",
            right="\u2551",
            middle_left="\u2560",
            middle_right="\u2563",
            bottom_left="\u255a",
            bottom="\u2550",
            bottom_tee="\u2569",
            bottom_right="\u255d",
        )

    @classmethod
    def ascii(cls) -> Border:
        """Plain ASCII, for terminals without box drawing."""
        return cls(
            top_left="+",
            top="-",
            top_tee="+",
            top_right="+",
            left="|",
            middle="-",
            cross="+",
            right="|",
            middle_left="+",
            middle_right="+",
            bottom_left="+",
            bottom="-",
            bottom_tee="+",
            bottom_right="+",
        )

    @classmethod
    def none(cls) -> Border:
        """No visible border: spaces keep the reserved geometry."""
        return cls(**{name: " " for name in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True, kw_only=True)
class Glyphs:
    """The structural mark vocabulary, one field per seat; the defaults are
    single-column and avoid Emoji presentation so row geometry holds."""

    prompt: str = "\u276f"
    cursor: str = "\u2192"
    rail: str = "\u258c"
    fold_open: str = "\u25be"
    fold_closed: str = "\u25b8"
    radio_off: str = "( )"
    radio_on: str = "(\u2022)"
    check_off: str = "[ ]"
    check_on: str = "[x]"
    check_indeterminate: str = "[-]"
    more_up: str = "\u2191"
    more_down: str = "\u2193"
    bar_full: str = "\u2588"
    bar_empty: str = "\u2591"
    slider_track: str = "\u2501"
    slider_thumb: str = "\u25cf"
    horizontal_rule: str = "\u2500"
    vertical_rule: str = "\u2502"
    quote: str = "\u2502"
    separator: str = " \u00b7 "
    bullets: tuple[str, ...] = ("\u2022", "\u25e6", "\u25aa")
    notice_info: str = "i"
    notice_success: str = "\u2713"
    notice_warn: str = "!"
    notice_error: str = "\u00d7"
    diff_add: str = "+"
    diff_remove: str = "-"
    diff_context: str = " "
    spinner: tuple[str, ...] = (
        "\u280b",
        "\u2819",
        "\u2839",
        "\u2838",
        "\u283c",
        "\u2834",
        "\u2826",
        "\u2827",
        "\u2807",
        "\u280f",
    )
    box: Border = Border.square()
    grid: Border = Border.square()


#: The shipped glyph vocabulary every component falls back to.
GLYPHS = Glyphs()


def seat(glyph: str) -> str:
    """The glyph plus one separator column; ``""`` seats nothing and leaves no
    dangling space."""
    return glyph + " " if glyph else ""


def seat_width(glyph: str) -> int:
    """Display width of :func:`seat`; ``""`` answers 0. Measured, never
    ``len``, so wide glyphs keep their columns."""
    return visible_width(glyph) + 1 if glyph else 0


def pair_seat(glyph: str, other: str) -> str:
    """``glyph``'s seat padded to the wider member of the pair, so both states
    keep one width whichever is shown."""
    width = max(seat_width(glyph), seat_width(other))
    return seat(glyph) + " " * (width - seat_width(glyph))
