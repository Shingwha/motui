"""Tests for mocode_tui.widgets.choice (Option / Select / Confirm).

Contracts (COMPONENTS.md): ``Select`` is a vertical ``Option`` list with a
clamped, non-wrapping cursor; the selected row starts with ``"\\u276e "`` and
forms one continuous ``selected_style`` band, hints trailing in
``hint_style``; ``click(row)`` places the cursor on the option under a
rendered row (the title row and rows past the last option are misses);
``Confirm`` is the Yes/No specialization with optional danger styling.
The row layout is shared with ``Autocomplete`` and pinned once here, on
the component that owns it.  Styles round-trip from the constructor.
"""

import pytest

from mocode_tui.widgets.choice import Confirm, Option, Select
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import Theme

from _doubles import texts

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
HINT = Style(fg="#123456")
LABEL = Style(bold=True)
TITLE = Style(fg="#fedcba")
DANGER = Style(fg="#0f0f0f")

THREE = [Option("one"), Option("two"), Option("three")]


def test_option_fields_and_defaults():
    assert Option("Save") == Option("Save", None, "")
    assert Option("x", value=1, hint="ctrl-s").value == 1


@pytest.mark.parametrize(
    "start, delta, index, moved",
    [
        (0, 1, 1, True),
        (0, 5, 2, True),  # clamped at the end
        (2, -9, 0, True),  # clamped at the start, no wrap-around
        (0, -1, 0, False),  # already at the top: nothing moved
    ],
)
def test_move_clamps_without_wrapping(start, delta, index, moved):
    select = Select(THREE)
    select.index = start
    assert select.move(delta) is moved
    assert select.index == index
    assert select.selected == THREE[index]


def test_an_empty_list_has_no_selection_and_cannot_move():
    empty = Select([])
    assert empty.selected is None
    assert empty.move(1) is False


def test_render_marks_the_selected_row_as_one_band():
    select = Select(
        [Option("one", hint="first"), Option("two")],
        label_style=LABEL,
        hint_style=HINT,
        selected_style=SELECTED,
    )
    select.move(1)
    rows = select.render(20)
    assert texts(select, 20) == ["  one  first", "\u276e two"]
    assert rows[1].segments == (Segment("\u276e two", SELECTED),)  # one continuous band
    assert rows[0].segments == (Segment("  one", LABEL), Segment("  first", HINT))


def test_style_injection_round_trips():
    select = Select(
        [Option("one", hint="h"), Option("two")],
        title="T",
        label_style=LABEL,
        selected_style=SELECTED,
        hint_style=HINT,
        title_style=TITLE,
    )
    select.move(1)
    rows = select.render(20)
    assert rows[0].segments == (Segment("T", TITLE),)  # the title row
    assert rows[1].segments == (Segment("  one", LABEL), Segment("  h", HINT))  # unselected
    assert rows[2].segments == (Segment("\u276e two", SELECTED),)  # one continuous band
    # the theme fields feed the same parameters
    theme = Theme(selection=SELECTED, dim=HINT)
    themed = Select([Option("one", hint="h")], theme=theme).render(20)
    assert themed[0].segments == (Segment("\u276e one  h", SELECTED),)


@pytest.mark.parametrize(
    "row, index, hit",
    [
        # Rendered rows: 0 = the title, 1 = one, 2 = two.
        (1, 0, True),  # the option under the row
        (2, 1, True),  # a hit even when the cursor already was there
        (0, 1, False),  # the title row is not an option
        (3, 1, False),  # past the last option
        (-1, 1, False),  # before the first option
    ],
)
def test_click_places_the_cursor_on_the_option_under_the_row(row, index, hit):
    select = Select([Option("one"), Option("two")], title="pick")
    select.move(1)
    assert select.click(row) is hit
    assert select.index == index


def test_confirm_is_a_two_option_select():
    confirm = Confirm("Delete file?")
    assert confirm.selected == Option("Yes", True)
    assert confirm.move(1) is True and confirm.selected == Option("No", False)
    assert confirm.move(1) is False and confirm.index == 1  # clamped, no wrap back to Yes
    assert texts(Confirm("Quit?"), 30) == ["Quit?", "\u276e Yes", "  No"]
    assert confirm.click(0) is False  # the message row
    assert confirm.click(1) is True and confirm.selected == Option("Yes", True)
    assert confirm.click(2) is True and confirm.selected == Option("No", False)


def test_a_dangerous_confirm_styles_its_message():
    theme = Theme(error=DANGER)
    row = Confirm("Delete everything?", danger=True, theme=theme).render(40)[0]
    assert row.segments == (Segment("Delete everything?", DANGER),)
    # without danger the message is unstyled
    plain = Confirm("Delete everything?", theme=theme).render(40)[0]
    assert plain.segments == (Segment("Delete everything?", Style()),)
