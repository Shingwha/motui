
from motui.kernel import Component
from motui.kernel.lines import Line, Segment
from motui.kernel.lines import Text
from motui.kernel.style import RESET, Style
from motui.kernel.text import ellipsize_tail
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import (
    Column,
    Collapsible,
    Divider,
    Padding,
    Panel,
    Row,
    Spacer,
)
from motui.widgets.markdown import Markdown

"""The container widgets: Divider/Panel and Row/Column/Spacer/Padding.

Frames wrap and arrange child rows, every row fitting back to the painting
width; styles round-trip from the constructor, no default color pinned.
"""

import pytest
from dataclasses import replace

from _doubles import texts


#: Injected styles: they flow back out of the render equal.
RULE = Style(fg="#fedcba")


# --- Divider / Panel ---------------------------------------------------------


@pytest.mark.parametrize(
    "divider, width, span",
    [
        (Divider(), 10, "\u2500" * 10),  # the full painting width by default
        (Divider(max_width=10), 40, "\u2500" * 10),  # a cap paints a shorter row
        (Divider(char="\u65e5"), 9, "\u65e5" * 4),  # a wide char fills 4 whole columns at a time
        (Divider(max_width=80), 12, "\u2500" * 12),  # a cap beyond the width changes nothing
    ],
)
def test_a_rule_fills_the_width_with_one_repeated_char(divider, width, span):
    rows = divider.render(width)
    assert [row.text for row in rows] == [span]
    assert rows[0].width <= width
    assert rows[0].segments[0].style == DEFAULT_THEME.border  # uncolored by default


def test_an_injected_border_style_round_trips():
    row = Divider(style=RULE).render(10)[0]
    assert row.segments == (Segment("\u2500" * 10, RULE),)


def test_a_divider_embeds_the_label_between_rule_segments():
    row = Divider(label="Working", label_style=RULE).render(20)[0]
    assert row.text == "\u2500\u2500 Working " + "\u2500" * 9
    assert row.width == 20
    assert row.segments == (
        Segment("\u2500\u2500", DEFAULT_THEME.border),
        Segment(" ", DEFAULT_THEME.border),
        Segment("Working", RULE),  # the label carries its own injected style
        Segment(" ", DEFAULT_THEME.border),
        Segment("\u2500" * 9, DEFAULT_THEME.border),
    )


@pytest.mark.parametrize("divider", [Divider(), Divider(max_width=16)])
def test_a_label_is_mutable_and_ellipsized_when_over_wide(divider):
    span = 16 if divider.max_width else 10
    divider.label = "a very long working label"  # a host re-labels one divider in place
    row = divider.render(span)[0]
    # Locate the label by text: with an uncolored border the rule segments
    # share the label's (no-)style, so style is no longer a discriminator.
    assert ellipsize_tail("a very long working label", span - 4) in [seg.text for seg in row.segments]
    assert row.width == span


def test_a_label_too_wide_for_the_capped_width_degrades_to_the_pure_rule():
    # width < 4 leaves no room for a label: the pure rule, like an empty label.
    for width in range(0, 4):
        assert Divider(label="Working").render(width) == Divider().render(width)
    assert Divider().render(0) == [Line()]
    assert Divider().render(-3) == [Line()]
    assert Divider(max_width=0).render(10)[0].text == ""
    # A wide char leaves the columns ragged; the final fit keeps the row honest.
    for width in (5, 9, 16):
        assert Divider(char="\u65e5", label="Working").render(width)[0].width <= width


def test_a_cap_is_a_plain_attribute_a_host_can_move():
    divider = Divider(max_width=6)
    assert divider.render(40)[0].text == "\u2500" * 6
    divider.max_width = None
    assert divider.render(12)[0].text == "\u2500" * 12


def test_panel_frames_the_child_with_an_optional_title():
    assert texts(Panel(Text("hi")), 12) == [
        "\u250c" + "\u2500" * 10 + "\u2510",
        "\u2502 hi       \u2502",
        "\u2514" + "\u2500" * 10 + "\u2518",
    ]
    titled = Panel(Text("body"), title="Info").render(20)
    assert titled[0].text.startswith("\u250c\u2500 Info \u2500")
    assert titled[0].text.endswith("\u2510")
    assert titled[0].width == 20


def test_panel_below_four_columns_degrades_to_the_bare_child():
    assert texts(Panel(Text("hello world")), 3) == ["hel", "lo", "wor", "ld"]
    assert Panel(Text("x")).render(1) == [Line.from_text("x")]


# --- Row / Column --------------------------------------------------------------


def test_row_fixed_and_flex_widths():
    fixed = Row([Text("a"), Text("b")], widths=[3, 2], gap=1)
    assert texts(fixed, 10) == ["a   b "]  # "a" -> 3 cols, 1 gap, "b" -> 2 cols
    flex = Row([Text("a"), Text("b")], gap=1)
    assert texts(flex, 10) == ["a    b   "]  # 9 shared -> 4 each, the odd column discarded
    mixed = Row([Text("a"), Text("b")], widths=[2, None], gap=1)
    assert texts(mixed, 10) == ["a  b      "]
    short = Row([Text("a"), Text("b"), Text("c")], widths=[2], gap=0)
    assert texts(short, 9) == ["a b  c  "]  # children beyond widths are flexible


def test_row_gap_and_tallest_child_height():
    row = Row([Text("a\nb\nc"), Text("x")], gap=1)
    rows = row.render(10)
    assert len(rows) == 3  # the tallest child sets the height
    assert [r.text for r in rows] == ["a    x   ", "b        ", "c        "]


def test_row_over_constrained_widths_stay_within_width():
    row = Row([Text("aaa"), Text("bbb")], widths=[8, 8], gap=1)
    rows = row.render(10)
    assert rows and all(r.width <= 10 for r in rows)
    assert rows[0].text.startswith("aaa")
    assert Row([]).render(10) == []


def test_column_stacks_with_gap():
    assert texts(Column([Text("a"), Text("b")], gap=2), 10) == ["a", "", "", "b"]
    assert texts(Column([Text("a"), Text("b")]), 10) == ["a", "b"]  # gap defaults to 0
    assert Column([]).render(10) == []


def test_row_and_column_nest_one_level_and_are_components():
    assert isinstance(Row([Text("x")]), Component)
    assert isinstance(Column([Text("x")]), Component)
    row = Row([Column([Text("a"), Text("b")]), Text("z")], gap=1)
    assert texts(row, 10) == ["a    z   ", "b        "]
    # Both containers drop into a single flexible / stacked painting width.
    assert texts(Column([Markdown("# Title"), Text("tail")]), 40) == ["Title", "tail"]


# --- Spacer / Padding ----------------------------------------------------------


def test_spacer_renders_blank_rows():
    assert texts(Spacer(3), 10) == ["", "", ""]
    assert texts(Spacer(), 10) == [""]  # one row by default
    assert Spacer(0).render(10) == []
    assert Spacer(-2).render(10) == []  # negative is clamped to nothing
    assert Spacer(2).render(10) == [Line(), Line()]
    assert isinstance(Spacer(1), Component)


def test_padding_surrounds_the_child_with_plain_spaces():
    # one top row, the content row, one bottom row
    assert texts(Padding(Text("ab"), left=2, right=1, top=1, bottom=1), 10) == [
        "",
        "  ab ",
        "",
    ]
    assert texts(Padding(Text("a\nb"), left=1, right=1), 10) == [" a ", " b "]
    assert texts(Padding(Text("x")), 10) == ["x"]  # all pads default to 0
    assert texts(Padding(Text(""), left=1, top=2), 4) == ["", "", " "]


def test_padding_fits_back_to_the_painting_width():
    padded = Padding(Text("abcdef"), left=1, right=1)
    rows = padded.render(4)  # the child paints at 2 columns and wraps
    assert [row.text for row in rows] == [" ab ", " cd ", " ef "]
    assert all(row.width <= 4 for row in rows)
    assert all(row.width <= 2 for row in Padding(Text("abcdef")).render(2))


def test_fill_paints_the_blank_areas_into_a_continuous_band():
    band = Style(bg="#123456")
    rows = Padding(Text("hi"), left=2, right=2, top=1, bottom=1, fill_style=band).render(8)
    assert len(rows) == 3  # one top row, the content row, one bottom row
    # top and bottom are pure band rows, full width
    assert rows[0] == Line.filled(8, band)
    assert rows[2] == Line.filled(8, band)
    # the content row is one continuous band: pad, child, and the blank
    # columns out to inner + right, every segment carrying the fill
    assert rows[1].segments == (
        Segment("  ", band),
        Segment("hi", band),  # the fill merges *under* the child's style
        Segment("    ", band),  # 0 blank columns to inner (4 - 2) + right (2)
    )
    assert rows[1].text == "  hi    " and rows[1].width == 8
    # one continuous band: every segment carries the fill, and each
    # boundary opens from a clean slate -- a RESET before every segment
    # after the first, then the trailing one -- so no attribute of one
    # segment's style can reach the next even when the styles coincide.
    styled = rows[1].styled()
    assert styled.count(RESET) == 3 and styled.endswith(RESET)
    assert styled == (
        band.prefix() + "  " + RESET + band.prefix() + "hi" + RESET
        + band.prefix() + "    " + RESET
    )


def test_fill_merges_under_the_child_own_style():
    band = Style(bg="#123456")
    child = Text("hi", style=Style(fg="red", bg="#654321"))
    row = Padding(child, left=1, right=1, fill_style=band).render(4)[0]
    assert row.segments == (
        Segment(" ", band),
        # the child's own colors win over the fill
        Segment("hi", Style(fg="red", bg="#654321")),
        Segment(" ", band),
    )


# --- the wrap memory (render-cost W4) ------------------------------------------


class _Remembering:
    """A child with a row memory, like the widgets this wave touched.

    ``render`` answers the very same rows while untouched (what a
    component's own cache does), and :meth:`touch` forgets them, so a test
    can tell whether the *container* served its wrap from memory or wrapped
    afresh.
    """

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self._rows: list[Line] | None = None

    def render(self, width: int) -> list[Line]:
        if self._rows is None:
            self._rows = [Line.from_text(f"{t} {i}") for i, t in enumerate(self.texts)]
        return self._rows

    def touch(self) -> None:
        self._rows = None


def test_the_containers_remember_the_wrap_of_unchanged_child_rows():
    """D10/T4: a container's wrap is keyed on the child rows' identity, so an
    unchanged child hands back the very framed rows -- and the moment the
    child's rows move (or the parameters do) the wrap is rebuilt, never
    served stale."""
    child = _Remembering("alpha", "beta")
    panel = Panel(child, title="T")
    first = panel.render(20)
    again = panel.render(20)
    assert again == first and again is not first  # a fresh list, shared rows
    assert [row is other for row, other in zip(first, again)] == [True] * len(first)
    # The `child_at` geometry survives the hit (readers navigate the memo).
    hits = [(panel.child_at(r, c) or None) for r in range(4) for c in range(5)]
    panel.render(20)
    assert [(panel.child_at(r, c) or None) for r in range(4) for c in range(5)] == hits
    # The child's rows moving is a new key: the same bytes, built afresh.
    child.touch()
    moved = panel.render(20)
    assert moved == first
    assert not any(row is other for row, other in zip(moved, first))
    # The parameters are part of the key too: a new title rebuilds the top row.
    titled = Panel(child, title="U")
    assert titled.render(20)[0].text != first[0].text

    for container in (
        Row([child, child], gap=1),
        Column([child, child], gap=1),
        Padding(child, left=1, top=1),
    ):
        one = container.render(30)
        two = container.render(30)
        assert one == two and one is not two
        assert [row is other for row, other in zip(one, two)] == [True] * len(one)
        child.touch()
        three = container.render(30)
        assert three == one  # the same rows, rebuilt -- values, never staleness
        assert not any(row is other for row, other in zip(three, one))
    # The collapsible memoizes its body's inset rows; the title row is one
    # row and re-renders every call, so hover and focus never go stale.
    section = Collapsible("sec", child)
    one = section.render(30)
    two = section.render(30)
    assert one == two and one is not two
    assert [row is other for row, other in zip(one[1:], two[1:])] == [True] * len(one[1:])
    assert one[0] is not two[0]  # the title row is always fresh
    child.touch()
    three = section.render(30)
    assert three == one
    assert not any(row is other for row, other in zip(three[1:], one[1:]))
