"""Tests for motui.widgets.dialog (ButtonSpec / Dialog / confirm_dialog).

``Dialog`` is a pure component -- it reads no key of its own and knows
nothing about where the box goes: a titled frame around a body, a row of
``Button`` values built from ``ButtonSpec`` descriptions, and the small
keyboard state machine that row answers to.  Asserted here as behavior: the
frame's geometry (title edge, shading, custom borders), the default-focus
rule for a dangerous dialog, what ``escape``/``enter``/the tab pair write
into ``chosen``, and the click that presses a button -- never per-method
happy paths.
"""

from __future__ import annotations

import pytest

from _doubles import texts

from motui.kernel.block import Activable
from motui.kernel.events import Key
from motui.kernel.lines import Segment, Text
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets.action import Button
from motui.widgets.dialog import ButtonSpec, Dialog, confirm_dialog


def _bands(dialog: Dialog, width: int = 40) -> dict[str, Style]:
    """The button row's bands, keyed by label (the focus band included)."""
    row = dialog.render(width)[2]
    return {seg.text.strip(): seg.style for seg in row.segments if seg.text.strip()}


def test_confirm_dialog_is_the_two_button_yes_no_box():
    dialog = confirm_dialog("Delete everything?")
    assert texts(dialog, 60) == [
        "\u250c" + "\u2500" * 34 + "\u2510",
        "\u2502 Delete everything?               \u2502",
        "\u2502             Yes   No             \u2502",
        "\u2514" + "\u2500" * 34 + "\u2518",
    ]
    assert isinstance(dialog.focused, Button)
    assert not isinstance(dialog, Activable)  # keys are handle's, not an activate verb
    assert dialog.handle(Key("enter")) is True and dialog.chosen is True
    dialog.chosen = None
    assert dialog.handle(Key("escape")) is True and dialog.chosen is None
    assert dialog.handle(Key("q", "q")) is False  # the body's keys are the host's to route


def test_a_danger_dialog_opens_on_its_last_safe_button():
    plain = confirm_dialog("Delete everything?")
    assert (plain.index, plain.focused.label) == (0, "Yes")  # the first button otherwise
    assert _bands(plain)["Yes"] == DEFAULT_THEME.accent.merge(DEFAULT_THEME.cursor)
    assert _bands(plain)["No"] == DEFAULT_THEME.accent
    # dangerous: the confirm button takes the error band and the *cancel*
    # opens focused -- a stray return never lands the destructive action.
    danger = confirm_dialog("Delete everything?", danger=True)
    assert (danger.index, danger.focused.label) == (1, "No")
    assert _bands(danger)["Yes"] == DEFAULT_THEME.error
    assert _bands(danger)["No"] == DEFAULT_THEME.accent.merge(DEFAULT_THEME.cursor)
    # the dangerous button is not disabled: walking onto it still takes enter
    assert danger.handle(Key("enter")) is True and danger.chosen is False  # the cancel
    assert danger.handle(Key("left")) is True and danger.index == 0
    assert danger.handle(Key("enter")) is True and danger.chosen is True


def test_the_button_arguments_normalize_and_the_keys_walk_without_wrapping():
    dialog = Dialog("t", Text("b"), ["Ok", ("Cancel", False)])
    assert dialog.handle(Key("enter")) is True and dialog.chosen is None  # "Ok": a label
    assert dialog.handle(Key("tab")) is True and dialog.index == 1
    assert dialog.handle(Key("enter")) is True and dialog.chosen is False  # its tuple value
    dialog.chosen = None
    assert dialog.handle(Key("tab")) is True and dialog.index == 1  # clamped: no wrap
    assert dialog.handle(Key("right")) is True and dialog.index == 1
    assert dialog.handle(Key("s-tab")) is True and dialog.index == 0
    assert dialog.handle(Key("left")) is True and dialog.index == 0
    assert dialog.handle(Key("up")) is False  # only the tab pair and left/right walk


def test_click_presses_the_button_under_the_rendered_cell():
    dialog = confirm_dialog("Delete?")
    rows = texts(dialog, 60)
    assert rows[2] == "\u2502             Yes   No             \u2502"
    assert dialog.click(1, 15) is False  # the body row is not the button row
    assert dialog.click(2, 12) is False  # the pad before the first button
    assert dialog.click(2, 18) is False  # the one-column join between the two
    assert dialog.click(2, 15) is True and dialog.chosen is True  # inside " Yes "
    assert dialog.index == 0
    dialog.chosen = None
    assert dialog.click(2, 21) is True and dialog.chosen is False  # inside " No "
    assert dialog.index == 1
    assert Dialog("t", Text("b"), []).click(2, 3) is False  # a buttonless dialog misses


def test_the_title_sits_in_the_top_rule_and_an_over_wide_one_is_ellipsized():
    titled = Dialog("Delete?", Text("body"), [("Yes", True), ("No", False)], width=30)
    assert texts(titled, 30)[0] == "\u250c\u2500 Delete? \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510"
    narrow = Dialog("Delete everything?", Text("body"), ["Ok"], width=16)
    assert texts(narrow, 40)[0] == "\u250c\u2500 Delete eve\u2026 \u2510"
    bare = Dialog("", Text("body"), ["Ok"], width=16)
    assert texts(bare, 40)[0] == "\u250c" + "\u2500" * 14 + "\u2510"  # no title: the bare rule


def test_the_shaded_box_is_solid_and_shade_off_ends_a_row_at_its_content():
    shaded = Dialog("t", Text("one\ntwo"), [("Ok", 1)], width=20)
    assert [row.width for row in shaded.render(40)] == [20] * 5  # every row spans the box
    open_box = Dialog("t", Text("one\ntwo"), [("Ok", 1)], width=20, shade=False)
    rows = open_box.render(40)
    assert rows[1].text == "\u2502 one \u2502"  # no fill: the right border travels along
    assert rows[2].text == "\u2502 two \u2502"
    assert rows[3].width == 14  # the button row ends after its content too


def test_a_custom_border_and_style_land_on_every_frame_row():
    dialog = Dialog(
        "t",
        Text("b"),
        [("Yes", True, Style(bold=True))],
        width=20,
        border=("#", "#", "#", "#", "=", "!"),
        border_style=Style(fg="#ff0000"),
        title_style=Style(fg="#00ff00"),
    )
    rows = dialog.render(40)
    assert rows[0].text == "#= t ==============#"
    assert rows[-1].text == "#==================#"
    assert rows[0].segments[3] == Segment("t", Style(fg="#00ff00"))  # the title's own band
    for row in (rows[0], rows[1], rows[3], rows[-1]):  # every frame cell carries the border
        assert row.segments[0].style.fg == "#ff0000"
        assert row.segments[-1].style.fg == "#ff0000"
    assert _bands(dialog, 40)["Yes"].bold is True  # the spec's own style reaches the row
    with pytest.raises(ValueError, match="align"):  # an unknown alignment is a construction error
        Dialog("t", Text("b"), ["Ok"], align="middle")


def test_a_buttonless_dialog_renders_its_body_and_answers_no_key():
    dialog = Dialog("t", Text("body"), [], width=20)
    assert texts(dialog, 40) == [
        "\u250c\u2500 t \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 body             \u2502",
        "\u2514" + "\u2500" * 18 + "\u2518",
    ]
    assert dialog.focused is None and dialog.index == 0
    assert dialog.handle(Key("enter")) is False and dialog.handle(Key("tab")) is False
    assert ButtonSpec("x") == ButtonSpec("x")  # the spec is a value
