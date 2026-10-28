"""Canvas: cell writes, clipping, marker plots and the dirty-row cache."""

from __future__ import annotations

import pytest

from motui.kernel.cell import Surface
from motui.kernel.glyphs import Border
from motui.kernel.layout import Constraints
from motui.widgets.canvas import Canvas, Sparkline


def texts(canvas: Canvas) -> list[str]:
    return [row.text for row in canvas.surface()]


def test_put_text_and_lines_clip_at_the_edges():
    canvas = Canvas(5, 3)
    canvas.put(1, 1, "#")
    assert texts(canvas) == ["     ", " #   ", "     "]
    canvas.put(-1, 0, "x")
    canvas.put(5, 0, "x")
    canvas.put(0, 3, "x")
    assert texts(canvas) == ["     ", " #   ", "     "]
    canvas.text(3, 0, "abcd")
    assert texts(canvas)[0] == "   ab"
    canvas.text(0, 2, "\u4e2dx")
    assert texts(canvas)[2] == "\u4e2dx  "
    canvas.hline(0, 0, 99, "-")
    canvas.vline(4, 0, 99, "|")
    assert texts(canvas) == ["----|", " #  |", "\u4e2dx |"]


def test_box_draws_corners_and_edges():
    canvas = Canvas(6, 4)
    canvas.box(1, 1, 4, 3)
    assert texts(canvas) == [
        "      ",
        " \u250c\u2500\u2500\u2510 ",
        " \u2502  \u2502 ",
        " \u2514\u2500\u2500\u2518 ",
    ]
    ascii_box = Canvas(4, 3)
    ascii_box.box(0, 0, 4, 3, border=Border.ascii())
    assert texts(ascii_box) == ["+--+", "|  |", "+--+"]


def test_a_box_outside_the_canvas_is_clipped():
    canvas = Canvas(4, 2)
    canvas.box(-2, 0, 4, 2)
    rows = texts(canvas)
    assert len(rows) == 2 and all(len(row) == 4 for row in rows)
    assert rows[0][1] == "\u2510"  # the visible right corner
    assert rows[1][1] == "\u2518"


def test_blit_copies_cells_at_an_offset():
    source = Canvas(2, 2)
    source.put(0, 0, "a")
    source.put(1, 1, "b")
    target = Canvas(4, 3)
    target.blit(source, 2, 1)
    assert texts(target) == ["    ", "  a ", "   b"]


def test_a_wide_character_owns_two_columns_and_never_splits():
    canvas = Canvas(4, 1)
    canvas.put(1, 0, "\u4e2d")
    assert texts(canvas) == [" \u4e2d "]
    assert canvas.surface().rows[0].width == 4
    canvas.put(3, 0, "\u4e2d")  # would cross the right edge: dropped
    assert texts(canvas) == [" \u4e2d "]
    canvas.width = 2  # cutting the continuation column blanks the lead
    assert texts(canvas) == ["  "]
    repaired = Canvas(4, 1)
    repaired.put(0, 0, "\u4e2d")
    repaired.put(1, 0, "x")  # writing half a wide glyph blanks the old cluster
    assert texts(repaired) == [" x  "]
    repaired.put(0, 0, "y")
    assert texts(repaired) == ["yx  "]


def test_a_write_marks_exactly_its_row_dirty():
    canvas = Canvas(3, 3)
    first = canvas.surface()
    assert canvas.surface() is first  # clean: the very same surface value
    canvas.put(0, 1, "x")
    second = canvas.surface()
    assert second is not first
    assert second[0] is first[0]
    assert second[2] is first[2]
    assert second[1] is not first[1]
    assert texts(canvas)[1] == "x  "


def test_resize_keeps_the_overlap_and_rebuilds_every_row():
    canvas = Canvas(3, 2)
    canvas.put(0, 0, "a")
    canvas.put(2, 1, "c")
    canvas.resize(2, 3)
    assert texts(canvas) == ["a ", "  ", "  "]
    assert canvas.width == 2 and canvas.height == 3


def test_the_cell_marker_plots_normalized_points():
    canvas = Canvas(4, 2)
    canvas.plot([(0, 0), (1, 1)])
    assert texts(canvas) == ["   \u2588", "\u2588   "]
    blank = Canvas(3, 2)
    blank.plot([])
    assert texts(blank) == ["   ", "   "]


def test_the_half_marker_packs_two_points_per_cell():
    canvas = Canvas(2, 1, marker="half")
    canvas.plot([(0, 0), (1, 1)])
    assert texts(canvas) == ["\u2584\u2580"]
    both = Canvas(1, 1, marker="half")
    both.plot([(0, 0), (0, 1)])
    assert texts(both) == ["\u2588"]


def test_the_braille_marker_maps_dots_to_the_standard_bitset():
    full = Canvas(1, 1, marker="braille")
    full.plot([(0, row) for row in range(4)] + [(1, row) for row in range(4)])
    assert texts(full) == ["\u28ff"]
    top_left = Canvas(2, 1, marker="braille")
    top_left.plot([(0, 3), (1, 0)])
    assert texts(top_left) == ["\u2801\u2880"]  # dot 1 top left, dot 8 bottom right
    bottom_left = Canvas(2, 1, marker="braille")
    bottom_left.plot([(0, 0), (1, 3)])
    assert texts(bottom_left) == ["\u2840\u2808"]  # dot 7 bottom left, dot 4 top right


def test_plot_rejects_an_unknown_marker():
    with pytest.raises(ValueError):
        Canvas(1, 1, marker="dots")
    with pytest.raises(ValueError):
        Canvas(1, 1).plot([(0, 0)], marker="dots")


def test_render_clips_to_the_constraints():
    canvas = Canvas(5, 3)
    assert canvas.render(Constraints(width=5)) is canvas.surface()
    clipped = canvas.render(Constraints(width=3, max_height=2))
    assert isinstance(clipped, Surface)
    assert [row.text for row in clipped] == ["   ", "   "]
    assert all(row.width <= 3 for row in clipped)
    assert clipped.width == 3 and clipped.height == 2
    assert canvas.render(Constraints(width=3, max_height=0)).height == 0
    assert canvas.render(Constraints(width=7)).height == 3  # the int spelling is a width alone


def test_sparkline_plots_its_values_into_one_row():
    surface = Sparkline([0, 1, 2, 3], marker="cell").render(Constraints(width=4))
    assert [row.text.rstrip() for row in surface] == ["\u2588\u2588\u2588\u2588"]
    half = Sparkline([1], marker="half").render(Constraints(width=7))
    assert [row.text.rstrip() for row in half] == ["\u2584"]
    budget = Sparkline([1, 2, 3], marker="cell").render(
        Constraints(width=3, max_height=2)
    )
    assert budget.height == 2
    assert Sparkline([1]).render(Constraints(width=0)).height == 0
