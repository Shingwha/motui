"""Row-model tests: the content door, widths, lines and surfaces."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from motui.kernel.cell import Cell, Line, Segment, Style, Surface
from motui.kernel.geom import Size

# -- the content door -------------------------------------------------------


@pytest.mark.parametrize("char", ["\x00", "\x1b", "\x7f", "\x9b", "\x0a"])
def test_cell_deletes_control_characters(char: str) -> None:
    assert Cell(char=char).char == ""
    assert Cell(char=f"a{char}b").char == "ab"


def test_cell_normalizes_a_tab_to_one_space() -> None:
    assert Cell(char="\t").char == " "
    assert Cell(char="a\tb").char == "a b"


def test_cell_sanitizes_link_and_action() -> None:
    assert Cell(link="https://e\x00x").link == "https://ex"
    assert Cell(link="\x1b").link is None
    assert Cell(action="a\x00b").action == "ab"
    assert Cell(action="\x00").action is None


def test_cell_is_a_frozen_value() -> None:
    cell = Cell(char="a", style=Style(bold=True), link="u", action="act")
    assert cell == Cell(char="a", style=Style(bold=True), link="u", action="act")
    assert hash(cell) == hash(Cell(char="a", style=Style(bold=True), link="u", action="act"))
    assert cell != Cell(char="a", action="other")
    with pytest.raises(FrozenInstanceError):
        cell.char = "b"  # type: ignore[misc]


def test_cell_defaults() -> None:
    assert Cell() == Cell(char=" ", style=Style(), link=None, action=None)


def test_segment_deletes_control_characters() -> None:
    assert Segment("\x00\x1b\x7f\x9b").text == ""
    assert Segment("a\tb").text == "a b"
    assert Segment("x", link="u\x00").link == "u"
    assert Segment("x", link="\x01").link is None


@pytest.mark.parametrize(
    ("text", "width"),
    [
        ("", 0),
        ("a", 1),
        ("abc", 3),
        ("中", 2),
        ("😀", 2),
        ("a中b", 4),
        ("\u0301", 0),  # combining mark with no base
        ("a\u0301", 1),  # combining mark merges into its base
        ("👨\u200d👩\u200d👧\u200d👦", 2),  # one ZWJ family cell
    ],
)
def test_segment_width(text: str, width: int) -> None:
    assert Segment(text).width == width


def test_segment_payloads_do_not_add_width() -> None:
    seg = Segment("ab", link="https://example.com", action="open")
    assert seg.width == 2
    assert seg.link == "https://example.com"
    assert seg.action == "open"


def test_segment_action_is_metadata_only() -> None:
    assert Segment("a", action="x") == Segment("a", action="y")
    assert hash(Segment("a", action="x")) == hash(Segment("a", action="y"))
    assert Segment("a", link="x") != Segment("a", link="y")


def test_segment_with_style_keeps_text_and_payloads() -> None:
    seg = Segment("ab", Style(bold=True), link="u", action="act")
    restyled = seg.with_style(Style(italic=True))
    assert restyled.text == "ab"
    assert restyled.style == Style(italic=True)
    assert restyled.link == "u"
    assert restyled.action == "act"


# -- lines ------------------------------------------------------------------


def test_line_from_text_and_empty_line() -> None:
    line = Line.from_text("hello")
    assert line.text == "hello"
    assert line.width == 5
    assert len(line.segments) == 1
    assert Line.from_text("") == Line()
    assert Line.from_text("", Style(bold=True)) == Line()


def test_line_value_semantics() -> None:
    a = Line.from_text("ab")
    b = Line.from_text("ab")
    assert a == b
    assert hash(a) == hash(b)
    assert a != Line.from_text("ac")
    assert Line((Segment("a", action="x"),)) == Line((Segment("a", action="y"),))
    assert "ab" in repr(a)


def test_line_is_immutable() -> None:
    line = Line.from_text("ab")
    with pytest.raises(AttributeError):
        line.text = "x"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        del line._segments  # type: ignore[attr-defined]


@pytest.mark.parametrize(("text", "width", "expected"), [
    ("abcdef", 0, ""),
    ("abcdef", 1, "a"),
    ("abcdef", 3, "abc"),
    ("abcdef", 6, "abcdef"),
    ("abcdef", 9, "abcdef"),
    ("中a", 1, ""),  # a double-width cell never straddles the cut
    ("中a", 2, "中"),
    ("a中", 2, "a"),
    ("a中", 3, "a中"),
    ("😀x", 1, ""),
    ("😀x", 2, "😀"),
])
def test_line_clip(text: str, width: int, expected: str) -> None:
    clipped = Line.from_text(text).clip(width)
    assert clipped.text == expected
    assert clipped.width <= width


def test_line_clip_keeps_styles_and_payloads() -> None:
    line = Line((Segment("ab", Style(bold=True), link="u"), Segment("cd", action="act")))
    clipped = line.clip(3)
    assert clipped.text == "abc"
    assert clipped.segments[0] == Segment("ab", Style(bold=True), link="u")
    assert clipped.segments[1].text == "c"
    assert clipped.segments[1].action == "act"


def test_line_clip_rejects_negative_width() -> None:
    with pytest.raises(ValueError):
        Line().clip(-1)


def test_line_pad() -> None:
    line = Line.from_text("ab")
    assert line.pad(4).text == "ab  "
    assert line.pad(4).width == 4
    assert line.pad(2) == line
    assert line.pad(0) == line
    with pytest.raises(ValueError):
        line.pad(-1)


# -- surfaces ---------------------------------------------------------------


def test_surface_of_clips_and_pads_every_row() -> None:
    surface = Surface.of(
        [Line.from_text("ab"), Line.from_text("abcdef"), Line()], width=3
    )
    assert surface.width == 3
    assert surface.height == 3
    assert [row.text for row in surface.rows] == ["ab ", "abc", "   "]
    assert all(row.width == 3 for row in surface.rows)


def test_surface_of_handles_zero_width() -> None:
    surface = Surface.of([Line.from_text("ab"), Line()], width=0)
    assert surface.width == 0
    assert surface.height == 2
    assert all(row == Line() for row in surface.rows)


def test_surface_of_keeps_wide_cells_whole() -> None:
    clipped = Surface.of([Line.from_text("中")], width=1)
    assert clipped.rows[0].text == " "  # the wide cell is dropped, then padded
    kept = Surface.of([Line.from_text("中")], width=2)
    assert kept.rows[0].text == "中"


def test_surface_of_empty_rows() -> None:
    surface = Surface.of([], width=5)
    assert surface.height == 0
    assert surface.rows == ()


def test_surface_blank() -> None:
    surface = Surface.blank(Size(width=4, height=2))
    assert surface.width == 4
    assert surface.height == 2
    assert surface.rows == (Line(), Line())


def test_surface_validation() -> None:
    with pytest.raises(ValueError):
        Surface.of([], width=-1)
    with pytest.raises(ValueError):
        Surface(width=-1)
    with pytest.raises(ValueError):
        Surface.blank(Size(width=-1, height=0))
    with pytest.raises(ValueError):
        Surface.blank(Size(width=0, height=-1))


def test_surface_coerces_rows_and_is_frozen() -> None:
    row = Line.from_text("a")
    surface = Surface(width=1, rows=[row])
    assert surface.rows == (row,)
    with pytest.raises(FrozenInstanceError):
        surface.width = 2  # type: ignore[misc]


def test_surface_is_a_read_only_row_sequence() -> None:
    surface = Surface.of([Line.from_text("ab"), Line.from_text("cd")], width=3)
    assert len(surface) == 2 == surface.height
    assert [row.text for row in surface] == ["ab ", "cd "]
    assert surface[0].text == "ab "
    assert surface[-1].text == "cd "
    assert surface[0:2] == surface.rows
    assert surface[1:] == (Line.from_text("cd").pad(3),)


def test_surface_of_without_padding_keeps_short_rows_short() -> None:
    surface = Surface.of(
        [Line.from_text("ab"), Line.from_text("abcdef"), Line()],
        width=3,
        pad=False,
    )
    assert surface.width == 3
    assert [row.text for row in surface] == ["ab", "abc", ""]
    assert all(row.width <= 3 for row in surface)


def test_surface_clipped_only_truncates() -> None:
    rows = [Line.from_text("ab"), Line.from_text("abcdef"), Line()]
    surface = Surface.clipped(rows, 3)
    assert surface == Surface.of(rows, 3, pad=False)
    assert surface.width == 3
    assert [row.text for row in surface.rows] == ["ab", "abc", ""]


def test_surface_of_pads_by_contract_by_default() -> None:
    padded = Surface.of([Line.from_text("ab")], 4)
    assert [row.text for row in padded] == ["ab  "]
    assert all(row.width == 4 for row in padded)


# -- constraints ------------------------------------------------------------
