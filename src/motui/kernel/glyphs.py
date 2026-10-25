"""The glyph vocabulary: the structural marks the row components draw.

**Glyphs are content, not style** -- a cursor, a rail bar, a tree fold, a
radio pair, a checkbox pair, a counter arrow -- so they never enter
:class:`~motui.kernel.theme.Theme`: a host that wants other marks passes
them to the component, and the theme keeps carrying only colors and
attributes.  One home for every shipped mark means the components agree on
the vocabulary and a reader finds "what is the cursor glyph" in one place.

Three helpers write the one seat rule the components share:

* :func:`seat` -- a glyph plus one separator column, ``""`` for no glyph;
* :func:`seat_width` -- the same seat's display width, measured through
  :func:`~motui.kernel.text.visible_width` (never ``len``: a CJK glyph is
  two columns), ``0`` for no glyph;
* :func:`pair_seat` -- one member of a state pair padded to the wider
  member's seat, so the two states keep one column whichever is shown.

The pair rule is what makes ``[x]``/``[ ]`` and ``(•)``/``( )`` line up when
a host substitutes a wider or narrower pair; ``seat`` collapses a disabled
glyph (`""`) to zero columns instead of leaving a dangling space.
"""

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
    """The fourteen marks one box-drawing style needs, as one frozen value.

    ``Border()`` is the square style (the same marks the 1.x components
    hard-coded).  :meth:`ascii` and :meth:`none` keep the same geometry in
    other vocabularies: ``none`` paints spaces, so a borderless box still
    occupies the cells its layout reserved instead of collapsing.
    """

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
        """The square corners and light lines of :class:`Border`'s defaults."""
        return cls()

    @classmethod
    def rounded(cls) -> Border:
        """Square lines with rounded corners (``╭ ╮ ╰ ╯``)."""
        return cls(
            top_left="\u256d",
            top_right="\u256e",
            bottom_left="\u2570",
            bottom_right="\u256f",
        )

    @classmethod
    def heavy(cls) -> Border:
        """Heavy box-drawing lines (``┏ ━ ┳ ┓`` ...)."""
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
        """Double box-drawing lines (``╔ ═ ╦ ╗`` ...)."""
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
        """Plain ASCII (``+ - |``), for terminals without box drawing."""
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
    """The structural mark vocabulary, one field per seat.

    Glyphs are content, not style: they stay out of :class:`Theme`, and a
    host that wants other marks supplies its own :class:`Glyphs`.  The
    defaults are single-column (or deliberate multi-column pairs) and avoid
    Emoji presentation -- a mark that terminals render two cells wide would
    break the row geometry.
    """

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
    """The seat of ``glyph``: the glyph and one separator column.

    ``""`` -- the disabled glyph -- seats nothing and leaves no dangling
    space, so a component's geometry collapses with it.
    """
    return glyph + " " if glyph else ""


def seat_width(glyph: str) -> int:
    """Display width of :func:`seat`: ``visible_width(glyph) + 1``.

    ``""`` answers ``0``.  The measure is
    :func:`~motui.kernel.text.visible_width`, never ``len``, so a wide
    glyph (a CJK character) takes its two columns plus the separator.
    """
    return visible_width(glyph) + 1 if glyph else 0


def pair_seat(glyph: str, other: str) -> str:
    """``glyph``'s seat padded to the wider member of the ``(glyph, other)`` pair.

    The pair's two states then share one column width whichever is shown;
    the padding is spaces, measured in display columns, so a wide member
    and a narrow one still line up.  Two empty members answer ``""``.
    """
    width = max(seat_width(glyph), seat_width(other))
    return seat(glyph) + " " * (width - seat_width(glyph))
