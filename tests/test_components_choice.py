"""Tests for mocode_tui.components.choice (Option / Select / Confirm).

Contracts (COMPONENTS.md): ``Select`` is a vertical ``Option`` list with a
clamped, non-wrapping cursor; the selected row starts with ``\u276e `` and
forms one continuous ``selected_style`` band, hints trail in ``hint_style``;
``Confirm`` is the Yes/No specialization with optional danger styling.
"""

from mocode_tui.components.choice import Confirm, Option, Select
from mocode_tui.lines import Segment
from mocode_tui.style import DIM, ERROR, NONE, SELECTION, Style


def test_option_fields_and_defaults():
    assert Option("Save") == Option("Save", None, "")
    assert Option("x", value=1, hint="ctrl-s").value == 1


def test_select_move_clamps_and_selected_tracks_the_index():
    select = Select([Option("one"), Option("two"), Option("three")])
    assert select.index == 0 and select.selected == Option("one")
    assert select.move(1) is True and select.index == 1
    select.move(5)
    assert select.index == 2  # clamped at the end
    select.move(-9)
    assert select.index == 0  # clamped at the start, no wrap-around
    assert select.move(-1) is False
    assert Select([]).selected is None
    assert Select([]).move(1) is False


def test_select_render_marks_the_selected_row_as_one_band():
    select = Select([Option("one", hint="first"), Option("two")])
    select.move(1)
    rows = select.render(20)
    assert [row.text for row in rows] == ["  one  first", "\u276e two"]
    assert rows[1].segments == (Segment("\u276e two", SELECTION),)
    assert rows[0].segments == (Segment("  one", NONE), Segment("  first", DIM))


def test_select_custom_styles_apply():
    select = Select(
        [Option("one", hint="h")],
        title="T",
        selected_style=Style(reverse=True),
        hint_style=NONE,
        title_style=Style(fg="red"),
    )
    rows = select.render(20)
    assert rows[0].segments == (Segment("T", Style(fg="red")),)
    assert rows[1].segments == (Segment("\u276e one  h", Style(reverse=True)),)


def test_confirm_yes_no_with_optional_danger_styling():
    confirm = Confirm("Delete file?")
    assert confirm.selected == Option("Yes", True)
    confirm.move(1)
    assert confirm.selected == Option("No", False)
    confirm.move(1)
    assert confirm.index == 1  # clamped, no wrap back to Yes
    assert [row.text for row in Confirm("Quit?").render(30)] == ["Quit?", "\u276e Yes", "  No"]
    danger = Confirm("Delete everything?", danger=True).render(40)
    assert danger[0].segments == (Segment("Delete everything?", ERROR),)
