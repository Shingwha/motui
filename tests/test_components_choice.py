"""Tests for mocode_tui.components.choice (Option / Select / Confirm)."""

from mocode_tui.components.choice import Confirm, Option, Select
from mocode_tui.lines import Line, Segment
from mocode_tui.style import DIM, ERROR, NONE, SELECTION


# --- Option -------------------------------------------------------------------


def test_option_fields_and_defaults():
    option = Option("Save")
    assert option.label == "Save"
    assert option.value is None
    assert option.hint == ""
    assert Option("x", value=1, hint="ctrl-s") == Option("x", 1, "ctrl-s")


# --- Select: cursor -------------------------------------------------------------


def test_select_starts_on_first_option():
    select = Select([Option("one"), Option("two")])
    assert select.index == 0
    assert select.selected == Option("one")


def test_select_move_clamps_and_never_wraps():
    select = Select([Option("one"), Option("two"), Option("three")])
    assert select.move(1) is True
    assert select.index == 1
    select.move(5)
    assert select.index == 2  # clamped at the end
    select.move(-9)
    assert select.index == 0  # clamped at the start, no wrap-around
    assert select.move(-1) is False  # already at the top
    assert select.move(0) is False


def test_select_selected_tracks_index():
    select = Select([Option("a", 1), Option("b", 2)])
    select.move(1)
    assert select.selected == Option("b", 2)
    assert select.selected.value == 2


def test_select_empty_options_do_not_crash():
    select = Select([])
    assert select.selected is None
    assert select.move(1) is False
    assert select.index == 0
    assert select.render(20) == []


# --- Select: render -------------------------------------------------------------


def test_select_render_row_count_and_prefix():
    select = Select([Option("one"), Option("two")], title="Pick")
    rows = select.render(20)
    assert len(rows) == 3  # title + two options
    assert rows[0].text == "Pick"
    assert rows[0].segments == (Segment("Pick", NONE),)
    assert rows[1].text == "\u276e one"
    assert rows[2].text == "  two"


def test_select_selected_row_is_one_continuous_band():
    select = Select([Option("one", hint="first"), Option("two")])
    select.move(1)
    row = select.render(20)[1]
    assert row.text == "\u276e two"
    assert row.segments == (Segment("\u276e two", SELECTION),)


def test_select_hint_trails_in_dim_style():
    select = Select([Option("one", hint="ctrl-n")])
    row = select.render(30)[0]
    assert row.text == "\u276e one  ctrl-n"
    assert row.segments == (Segment("\u276e one  ctrl-n", SELECTION),)

    two = Select([Option("a", hint="ha"), Option("b")])
    two.move(1)  # cursor on "b", so "a" is an unselected row with a hint
    rows = two.render(30)
    assert rows[0].segments == (Segment("  a", NONE), Segment("  ha", DIM))
    assert rows[1].segments == (Segment("\u276e b", SELECTION),)


def test_select_rows_fit_width():
    select = Select([Option("a very long option label", hint="and a long hint too")])
    rows = select.render(12)
    assert all(row.width <= 12 for row in rows)
    assert rows[0].text == "\u276e a very lo\u2026"


def test_select_custom_styles():
    from mocode_tui.style import Style

    select = Select(
        [Option("one")],
        title="T",
        selected_style=Style(reverse=True),
        hint_style=NONE,
        title_style=Style(fg="red"),
    )
    rows = select.render(20)
    assert rows[0].segments == (Segment("T", Style(fg="red")),)
    assert rows[1].segments == (Segment("\u276e one", Style(reverse=True)),)


# --- Confirm ---------------------------------------------------------------------


def test_confirm_yes_no_options():
    confirm = Confirm("Delete file?")
    assert confirm.selected == Option("Yes", True)
    confirm.move(1)
    assert confirm.selected == Option("No", False)
    confirm.move(1)
    assert confirm.index == 1  # clamped, no wrap to Yes
    confirm.move(-2)
    assert confirm.index == 0


def test_confirm_render_message_plus_two_rows():
    rows = Confirm("Quit?").render(30)
    assert [row.text for row in rows] == ["Quit?", "\u276e Yes", "  No"]


def test_confirm_danger_styles_title_as_error():
    rows = Confirm("Delete everything?", danger=True).render(40)
    assert rows[0].segments == (Segment("Delete everything?", ERROR),)
    plain = Confirm("Sure?").render(40)
    assert plain[0].segments == (Segment("Sure?", NONE),)
