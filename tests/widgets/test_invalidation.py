"""The row cache follows in-place widget changes: every mutator touches.

A :class:`~motui.kernel.document.Section` caches a widget's rows on
``(width, max_height, generation)``.  These scenarios exercise the widgets
whose state moves through private fields, lists or sets -- the writes that
``Widget.__setattr__`` cannot see -- and assert that the section's rows
move after the documented mutator (or an explicit ``touch()`` for a host's
own in-place list edits).
"""

from __future__ import annotations

from motui.kernel.cell import Line, Segment, Surface
from motui.kernel.document import Section
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.text import WrapMode
from motui.widgets import Canvas, Form, Input, List, ScrollPanel, Table, Text
from motui.widgets.form import Field

from tests.testing import key


class SpanText(Text):
    """A Text whose one row carries an inline action (the documented seam)."""

    def _rows_for(self, width: int) -> list[Line]:
        return [
            Line(
                (Segment("see ", Style()), Segment("docs", Style(), action="open"))
            ).clip(WrapMode.ELLIPSIS, width)
        ]


def _rows(section: Section, width: int = 20) -> list[str]:
    return [row.text for row in section.rows(Constraints(width=width))]


def test_text_assignment_and_hover_move_the_section_rows():
    text = SpanText("ignored")
    block = Section("t", text)
    assert _rows(block) == ["see docs"]
    text.text = "changed"
    assert _rows(block) == ["see docs"]  # the subclass row is fixed; text is not painted
    assert text.on_hover(Pos(y=0, x=5)) is True
    assert _rows(block) == ["see docs"]
    # The hover band is a paint input even when the text bytes are equal.
    before = block.rows_view(Constraints(width=20))
    text.on_hover(None)
    after = block.rows_view(Constraints(width=20))
    assert after is not before

    plain = Text("one")
    plain_block = Section("p", plain)
    assert _rows(plain_block) == ["one"]
    plain.text = "two"
    assert _rows(plain_block) == ["two"]


def test_list_move_moves_the_section_rows():
    lst = List(["a", "b", "c"], window=8)
    block = Section("l", lst)
    assert _rows(block)[0] == "\u2192 a"
    lst.move(1)
    rows = _rows(block)
    assert rows[0] == "  a" and rows[1] == "\u2192 b"


def test_input_typing_moves_the_section_rows():
    field = Input("", prompt="")
    block = Section("i", field)
    assert _rows(block) == [" "]  # the empty focused field paints its caret cell
    field.on_key(key("a", "a"))
    assert _rows(block) == ["a "]
    field.on_key(key("b", "b"))
    assert _rows(block) == ["ab "]
    # A cursor-only move is a row input too.
    before = block.rows_view(Constraints(width=20))
    field.move_left()
    assert block.rows_view(Constraints(width=20)) is not before


def test_canvas_writes_move_the_section_rows():
    canvas = Canvas(width=4, height=2)
    block = Section("c", canvas)
    assert _rows(block) == ["    ", "    "]
    canvas.put(0, 0, "#")
    assert _rows(block)[0].startswith("#")
    canvas.clear()
    assert _rows(block) == ["    ", "    "]


def test_scroll_panel_scrolling_moves_the_section_rows():
    panel = ScrollPanel(Text("a\nb\nc\nd"), height=2)
    block = Section("s", panel)
    assert _rows(block) == ["a", "b"]
    assert panel.scroll_down() is True
    assert _rows(block) == ["b", "c"]
    assert panel.scroll_up() is True
    assert _rows(block) == ["a", "b"]


def test_table_cursor_and_an_explicit_touch_move_the_section_rows():
    table = Table(["A", "B"], [["1", "2"], ["3", "4"]])
    block = Section("t", table)
    without_cursor = block.rows_view(Constraints(width=20))
    table.move(1)
    with_cursor = block.rows_view(Constraints(width=20))
    assert with_cursor is not without_cursor  # a new cache list: the band moved
    # ``rows`` is the host's own list: an in-place edit is invisible until
    # the host touches its widget (the documented contract).
    before_count = block.row_count(Constraints(width=20))
    table.rows.append(["5", "6"])
    table.touch()
    assert block.row_count(Constraints(width=20)) == before_count + 2
    assert any("5" in row.text for row in block.rows(Constraints(width=20)))


def test_form_child_input_changes_the_form_rows():
    field = Input("", prompt="")
    form = Form([Field("name", field, label="Name")])
    block = Section("f", form)
    assert _rows(block) == ["Name", " "]
    field.on_key(key("x", "x"))
    assert _rows(block) == ["Name", "x "]
    # The form's own focus cursor is a row input as well.
    form2 = Form([Field("a", Input("", prompt="")), Field("b", Input("", prompt=""))])
    block2 = Section("f2", form2)
    start = block2.rows_view(Constraints(width=20))
    form2.move(1)
    assert block2.rows_view(Constraints(width=20)) is not start


def test_section_rows_are_not_cached_for_a_pure_component():
    class Once:
        def __init__(self) -> None:
            self.calls = 0

        def render(self, c: Constraints):
            self.calls += 1
            return Surface.clipped([Line.from_text(str(self.calls))], c.width)

    component = Once()
    block = Section("p", component)
    assert _rows(block) == ["1"]
    assert _rows(block) == ["2"]
