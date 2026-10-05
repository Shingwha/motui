"""Tests for mocode_tui.core.text (Text).

Contract: verbatim text block, one logical line per ``\\n``, word-wrapped and
``fit`` to the width (COMPONENTS.md).  ``.text`` is mutable for streaming.
"""

from mocode_tui.core.text import Text
from mocode_tui.core.lines import Line
from mocode_tui.core.style import DIM


def test_default_render_at_width_80():
    assert [row.text for row in Text("hello").render(80)] == ["hello"]


def test_blank_lines_survive_as_blank_rows():
    assert [row.text for row in Text("a\n\nb").render(80)] == ["a", "", "b"]


def test_wraps_at_spaces_at_a_narrow_width():
    rows = Text("hello world").render(5)
    assert [row.text for row in rows] == ["hello", "world"]
    assert all(row.width <= 5 for row in rows)


def test_style_applies_to_every_row():
    rows = Text("ab\ncd", style=DIM).render(10)
    assert [row.text for row in rows] == ["ab", "cd"]
    assert all(seg.style == DIM for row in rows for seg in row.segments)


def test_text_is_mutable_for_streaming():
    stream = Text("one ")
    assert stream.render(80) == [Line.from_text("one")]
    stream.text += "two"  # assign one chunk at a time
    assert stream.render(80) == [Line.from_text("one two")]


def test_narrow_width_guard():
    # width 1 hard-breaks every character; width 0 yields one empty row.
    assert [row.text for row in Text("hi").render(1)] == ["h", "i"]
    assert Text("hi").render(0) == [Line()]
