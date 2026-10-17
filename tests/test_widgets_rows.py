"""Tests for motui.widgets.rows (StatusLine / ShortcutBar / Notice).

The three one-row components a host pins around its content: the status row's
left/gutter/right composition (one row always, the left preserved and the
right cut from its tail when over-wide), the shortcut bar's key/label hints
and the notice's leveled message row -- each fitting back to the painting
width.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from motui.kernel import ACCENT, DIM, MUTED, Component, visible_width
from motui.kernel.block import Clickable
from motui.kernel.lines import Line, Segment
from motui.kernel.style import NONE, Style
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.widgets.rows import Notice, ShortcutBar, StatusLine

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
PLAIN = Style(fg="#123456")
WARN = Style(fg="#abcdef")
ERROR = Style(fg="#123456")


#: Gutter rule: left at column 0, right ending one column short of ``width``.
_GUTTER = 1


def _expected(left: str, right: str, width: int, style: Style = DIM) -> Line:
    """The row the demo's ``_StatusRow``-style composition builds."""
    used = visible_width(left) + visible_width(right)
    gutter = max(_GUTTER, width - used - 1)
    return Line.from_text(f"{left}{' ' * gutter}{right}", style).fit(width)


@pytest.mark.parametrize(
    ("left", "right", "width"),
    [
        (("left",), ("right",), 40),  # a wide screen: a deep gutter
        (("ab",), ("cd",), 6),  # the minimum gutter is one column
        (("a-much-too-long-left-part",), ("r",), 12),  # no room for the right
        (("l", "b", ("c", DIM)), ("d",), 12),  # adjacent equal styles coalesce
        ((), ("only-right",), 30),  # an empty left side
        (("only-left",), (), 30),  # an empty right side
        ((), (), 10),  # both empty: the gutter alone
        (("l",), ("r",), -3),  # degenerate widths still yield exactly one row
        (("l",), ("r",), 0),
        (("l",), ("r",), 1),
        (("l",), ("r",), 2),
    ],
)
def test_the_row_composes_left_gutter_right(left, right, width):
    bar = StatusLine(left=left, right=right)
    rows = bar.render(width)
    assert len(rows) == 1  # always exactly one row
    assert rows[0].width <= max(0, width)

    left_text = "".join(x if isinstance(x, str) else x[0] for x in left)
    right_text = "".join(x if isinstance(x, str) else x[0] for x in right)
    expected = _expected(left_text, right_text, width)
    assert rows[0].text == expected.text
    assert rows[0] == expected


@pytest.mark.parametrize(
    ("width", "marker"),
    [
        (14, "keep-me drop-…"),  # the right part is cut from its tail
        (15, "keep-me drop-m…"),
        (11, "keep-me dr…"),
    ],
)
def test_overflow_keeps_the_left_and_cuts_the_right_tail(width, marker):
    bar = StatusLine(left=("keep-me",), right=("drop-me-please",))
    (row,) = bar.render(width)
    assert row.width == width
    assert row.text.startswith("keep-me")  # the left part survives intact
    assert row.text.endswith("…")  # the right part is ellipsized
    assert row.text == marker  # cut from the tail, not from the head


def test_styles_resolve_explicit_element_over_gutter_over_theme():
    bar = StatusLine(
        left=(("ctx", ACCENT), "plain"),
        right=("r", ("tail", MUTED)),
        gap_style=Style(reverse=True),
    )
    (row,) = bar.render(30)
    # Only adjacent elements with *equal* styles fuse, so the gutter keeps
    # its own run and "plain" stays in the dim default beside it.
    assert row.segments == (
        Segment("ctx", ACCENT),
        Segment("plain", DIM),
        Segment(" " * 16, Style(reverse=True)),  # the computed gutter
        Segment("r", DIM),
        Segment("tail", MUTED),
    )
    # Bare strings with a custom gutter style stay dim, exactly like the demo.
    bar = StatusLine(left=("l",), right=("r",), gap_style=Style(reverse=True))
    (row,) = bar.render(10)
    assert row.segments == (
        Segment("l", DIM),
        Segment(" " * 7, Style(reverse=True)),
        Segment("r", DIM),
    )
    # A row of plain elements fuses into one dim run, like the demo's own
    # ``Line.from_text(row, DIM)``.
    bar = StatusLine(left=("a", "b", ("c", DIM)), right=("d",))
    (row,) = bar.render(12)
    assert row.segments == (Segment("abc" + " " * 7 + "d", DIM),)
    # The whole row's default comes from the theme when nothing is explicit.
    bar = StatusLine(left=("l",), right=("r",), theme=Theme(dim=MUTED))
    (row,) = bar.render(20)
    assert row.segments == (Segment("l" + " " * 17 + "r", MUTED),)
    # An explicit gap style still wins over the themed default.
    bar = StatusLine(left=("l",), right=("r",), theme=Theme(dim=MUTED), gap_style=ACCENT)
    (row,) = bar.render(20)
    assert row.segments[1].style == ACCENT


def test_left_and_right_are_reassignable_between_renders():
    bar = StatusLine(left=("one",), right=("two",))
    assert "one" in bar.render(40)[0].text
    bar.left = [("three", ACCENT)]
    bar.right = ()
    row = bar.render(40)[0]
    assert row.text == "three" + " " * 34  # left plus the gutter; no right part


def test_the_row_locks_its_bytes_after_the_move():
    """One sample row, byte for byte: the migration's own lock.

    ``StatusLine`` moved into the widgets library with rendering
    unchanged; this literal lock (text plus segments) fails on a
    single shifted space or fused segment.
    """
    bar = StatusLine(left=(("19.9k", ACCENT), " ready"), right=(("v4.1-flash", MUTED),))
    (row,) = bar.render(40)
    assert row.text == "19.9k ready" + " " * 18 + "v4.1-flash"
    assert row.segments == (
        Segment("19.9k", ACCENT),  # the explicit element style survives
        Segment(" ready" + " " * 18, DIM),  # bare text fuses with the gutter
        Segment("v4.1-flash", MUTED),
    )


# --- ShortcutBar -----------------------------------------------------------------


def test_shortcut_bar_renders_one_row_of_key_label_pairs():
    bar = ShortcutBar([("c-n", "next"), ("c-p", "prev"), ("/", "palette")])
    rows = bar.render(40)
    assert len(rows) == 1
    assert rows[0].text == "c-n next \u00b7 c-p prev \u00b7 / palette"
    assert rows[0].segments == (
        Segment("c-n", DEFAULT_THEME.accent),
        Segment(" next", DEFAULT_THEME.dim),
        Segment(" \u00b7 ", NONE),
        Segment("c-p", DEFAULT_THEME.accent),
        Segment(" prev", DEFAULT_THEME.dim),
        Segment(" \u00b7 ", NONE),
        Segment("/", DEFAULT_THEME.accent),
        Segment(" palette", DEFAULT_THEME.dim),
    )
    assert isinstance(bar, Component)
    assert not isinstance(bar, Clickable)  # chrome only: no interaction


def test_shortcut_bar_custom_separator_and_styles_round_trip():
    bar = ShortcutBar(
        [("a", "one"), ("b", "two")],
        separator=" | ",
        key_style=SELECTED,
        label_style=PLAIN,
    )
    assert bar.render(40)[0].text == "a one | b two"
    assert bar.render(40)[0].segments[1] == Segment(" one", PLAIN)
    assert bar.render(40)[0].segments[0] == Segment("a", SELECTED)


def test_shortcut_bar_truncates_instead_of_wrapping():
    bar = ShortcutBar([("c-n", "next"), ("c-p", "prev")])
    row = bar.render(8)[0]
    assert len(bar.render(80)) == 1  # a bar is always a single row
    assert row.text == "c-n nex\u2026" and row.width == 8
    assert bar.render(6)[0].text == "c-n n\u2026"
    assert ShortcutBar([]).render(20) == [Line()]  # an empty bar is one empty row
    assert ShortcutBar([]).render(0) == [Line()]


def test_shortcut_bar_counts_wide_characters_by_display_width():
    bar = ShortcutBar([("\u4e2d", "wide"), ("c-p", "prev")])
    row = bar.render(8)[0]
    assert row.text == "\u4e2d wide\u2026"  # 2 + 5 display cells, then the marker
    assert row.width == 8
    assert bar.render(4)[0].text == "\u4e2d \u2026"  # a cut inside the label's run
    assert bar.render(2)[0].text == "\u2026"  # no single cell holds the wide key
    assert bar.render(1)[0].text == "\u2026"


# --- Notice ------------------------------------------------------------------


@pytest.mark.parametrize("level, label", [("info", ""), ("verbose", "")])  # unknown -> info
def test_a_plain_notice_is_one_bare_row(level, label):
    assert Notice("hello", level=level).render(80) == [Line.from_text("hello")]


@pytest.mark.parametrize("level, label", [("warn", "WARNING: "), ("error", "ERROR: ")])
def test_a_leveled_notice_prefixes_the_message_with_the_themes_label(level, label):
    theme = replace(DEFAULT_THEME, warning=WARN, error=ERROR)
    row = Notice("careful", level=level, theme=theme).render(80)[0]
    assert row.text == label + "careful"
    assert row.segments[0] == Segment(label, WARN if level == "warn" else ERROR)


def test_a_narrow_notice_truncates_instead_of_wrapping():
    row = Notice("a very long warning message", level="warn").render(10)[0]
    assert row.text == "WARNING: \u2026"
    assert row.width == 10
