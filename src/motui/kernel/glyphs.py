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

from .text import visible_width

__all__ = [
    "COLLAPSED",
    "CURSOR",
    "EXPANDED",
    "MARKED",
    "MENU_CURSOR",
    "MORE_DOWN",
    "MORE_UP",
    "RAIL_BAR",
    "RADIO_EMPTY",
    "RADIO_FILLED",
    "TASK_DONE",
    "TASK_OPEN",
    "THUMB",
    "TRACK",
    "UNMARKED",
    "pair_seat",
    "seat",
    "seat_width",
]

#: A data list's cursor row (``List``).
CURSOR = "\u25b8"

#: A menu's cursor row (``Select`` / ``Autocomplete``).
MENU_CURSOR = "\u2192"

#: A navigation rail's active row (``NavList``).
RAIL_BAR = "\u258c"

#: A tree node's two fold states (``Tree``).
EXPANDED = "\u25be"
COLLAPSED = "\u25b8"

#: A radio row's two states (``Radio``).
RADIO_EMPTY = "( )"
RADIO_FILLED = "(\u2022)"

#: A row's mark pair (``List`` / ``Table`` / ``CheckGroup``).
MARKED = "[x]"
UNMARKED = "[ ]"

#: The counter rows above / below a list's window (``List``).
MORE_UP = "\u2191"
MORE_DOWN = "\u2193"

#: The scrollbar's two glyphs (W2 consumes; the vocabulary is W1's).
TRACK = "\u2591"
THUMB = "\u2588"

#: The Markdown task box's two glyphs (W2 consumes).
TASK_OPEN = "\u2610"
TASK_DONE = "\u2611"


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
