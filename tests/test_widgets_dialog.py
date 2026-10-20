"""Tests for motui.widgets.dialog (ButtonSpec / Dialog / confirm_dialog / prompt_dialog).

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

from motui.interaction.modal import Modal
from motui.kernel.block import Activable
from motui.kernel.events import KeyEvent, MouseEvent
from motui.kernel.lines import Segment, Text
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.testing import headless_tui
from motui.widgets.action import Button
from motui.widgets.dialog import ButtonSpec, Dialog, confirm_dialog, prompt_dialog
from motui.widgets.textfield import Input


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
    assert dialog.handle(KeyEvent("enter")) is True and dialog.chosen is True
    dialog.chosen = None
    assert dialog.handle(KeyEvent("escape")) is True and dialog.chosen is None
    assert dialog.handle(KeyEvent("q", "q")) is False  # the body's keys are the host's to route


def test_a_danger_dialog_opens_on_its_last_safe_button():
    plain = confirm_dialog("Delete everything?")
    assert (plain.index, plain.focused.label) == (0, "Yes")  # the first button otherwise
    assert _bands(plain)["Yes"] == DEFAULT_THEME.accent.merge(DEFAULT_THEME.focus)
    assert _bands(plain)["No"] == DEFAULT_THEME.accent
    # dangerous: the confirm button takes the error band and the *cancel*
    # opens focused -- a stray return never lands the destructive action.
    danger = confirm_dialog("Delete everything?", danger=True)
    assert (danger.index, danger.focused.label) == (1, "No")
    assert _bands(danger)["Yes"] == DEFAULT_THEME.error
    assert _bands(danger)["No"] == DEFAULT_THEME.accent.merge(DEFAULT_THEME.focus)
    # the dangerous button is not disabled: walking onto it still takes enter
    assert danger.handle(KeyEvent("enter")) is True and danger.chosen is False  # the cancel
    assert danger.handle(KeyEvent("left")) is True and danger.index == 0
    assert danger.handle(KeyEvent("enter")) is True and danger.chosen is True


def test_the_button_arguments_normalize_and_the_keys_walk_without_wrapping():
    dialog = Dialog("t", Text("b"), ["Ok", ("Cancel", False)])
    assert dialog.handle(KeyEvent("enter")) is True and dialog.chosen is None  # "Ok": a label
    assert dialog.handle(KeyEvent("tab")) is True and dialog.index == 1
    assert dialog.handle(KeyEvent("enter")) is True and dialog.chosen is False  # its tuple value
    dialog.chosen = None
    assert dialog.handle(KeyEvent("tab")) is True and dialog.index == 1  # clamped: no wrap
    assert dialog.handle(KeyEvent("right")) is True and dialog.index == 1
    assert dialog.handle(KeyEvent("s-tab")) is True and dialog.index == 0
    assert dialog.handle(KeyEvent("left")) is True and dialog.index == 0
    assert dialog.handle(KeyEvent("up")) is False  # only the tab pair and left/right walk


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


def test_a_borderless_dialog_is_the_body_and_the_row_without_the_box():
    """``frame=False``: no frame rows, no title, one pad column per side."""
    dialog = confirm_dialog("Delete everything?", frame=False)
    assert texts(dialog, 60) == [
        " Delete everything?                 ",
        "              Yes   No              ",
    ]
    titled = Dialog("Info", Text("body"), [("Ok", True)], width=30, frame=False)
    rows = titled.render(40)
    assert rows[0].text == " body " + " " * 24  # the title drops with the frame
    assert all("\u250c" not in row.text and "\u2502" not in row.text for row in rows)
    assert all(row.width == 30 for row in rows)  # shaded: every row spans the box


def test_the_borderless_hit_columns_follow_the_missing_border():
    """A click lands the button under the cell in either mode; the spans
    start ``lead`` cells in from the box's left edge (two framed, one not)."""
    for frame in (True, False):
        dialog = confirm_dialog("Delete everything?", frame=frame)
        rows = dialog.render(60)
        index = next(i for i, row in enumerate(rows) if "Yes" in row.text)
        col = rows[index].text.index("Yes")
        assert dialog.click(0, col) is False  # the body row is not the button row
        assert dialog.click(index, 0) is False  # the pad column before any button
        assert dialog.click(index, col) is True and dialog.chosen is True
        dialog.chosen = None
        assert dialog.click(index, col + 10) is False  # past " Yes   No "


def test_a_borderless_dialog_keeps_the_danger_band_and_the_cancel_focus():
    danger = confirm_dialog("Delete everything?", danger=True, frame=False)
    assert (danger.index, danger.focused.label) == (1, "No")
    row = danger.render(40)[1]  # borderless: the body row, then the buttons
    bands = {seg.text.strip(): seg.style for seg in row.segments if seg.text.strip()}
    assert bands["Yes"] == DEFAULT_THEME.error  # the cue the box's border carried
    assert bands["No"] == DEFAULT_THEME.accent.merge(DEFAULT_THEME.focus)


def test_a_borderless_dialog_under_a_modal_keeps_the_one_geometry():
    """The modal splices the panel through the very rectangle it routes a
    press with: a click on a borderless button's cell decides, in the
    panel's own (borderless) coordinates."""
    tui = headless_tui(60, 12)
    dialog = confirm_dialog("Delete everything?", frame=False)
    modal = Modal(tui, dialog)
    modal.open()
    tui.paint()
    rows = [row.text.rstrip() for row in tui.rows]
    top = next(i for i, text in enumerate(rows) if "Delete everything?" in text)
    press_row = next(i for i, text in enumerate(rows) if "Yes" in text)
    press_col = rows[press_row].index("Yes")
    assert modal.handle(
        MouseEvent("left", x=press_col, y=press_row, kind="press")
    ) is True
    assert modal.chosen is True and modal.is_open is False  # the button was taken
    assert press_row == top + 1  # the body is the panel's first row: no frame rows


def test_the_builders_forward_the_borderless_switch():
    assert confirm_dialog("m").frame is True
    assert confirm_dialog("m", frame=False).frame is False
    assert prompt_dialog("rename").frame is True
    prompted = prompt_dialog("rename", placeholder="new name", frame=False)
    assert prompted.frame is False
    assert texts(prompted, 60)[0].startswith(" \u276e new name")
    assert "rename" not in "".join(texts(prompted, 60))  # the title goes with the frame


def test_a_buttonless_dialog_renders_its_body_and_answers_no_key():
    dialog = Dialog("t", Text("body"), [], width=20)
    assert texts(dialog, 40) == [
        "\u250c\u2500 t \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 body             \u2502",
        "\u2514" + "\u2500" * 18 + "\u2518",
    ]
    assert dialog.focused is None and dialog.index == 0
    assert dialog.handle(KeyEvent("enter")) is False and dialog.handle(KeyEvent("tab")) is False
    assert ButtonSpec("x") == ButtonSpec("x")  # the spec is a value


# --- the prompt: the field body, and the enter it does not take -------------------


def test_prompt_dialog_is_a_masked_field_over_the_ok_cancel_row():
    """The thin builder's wiring: an Input body, both texts, the safe focus."""
    prompt = prompt_dialog("rename", placeholder="new name", mask="\u2022")
    assert isinstance(prompt.body, Input)
    assert prompt.body.placeholder == "new name" and prompt.body.mask == "\u2022"
    rows = texts(prompt, 60)
    assert rows[0].startswith("\u250c\u2500 rename")
    assert "new name" in rows[1]  # the empty field shows its hint, no cursor cell
    assert "\u2502" in rows[1] and rows[-1].startswith("\u2514")
    assert prompt.focused.label == "OK"  # the plain prompt opens on the confirm
    assert {"OK", "Cancel"} <= set(_bands(prompt))  # both buttons on the row

    danger = prompt_dialog("delete the project", danger=True)
    assert danger.focused.label == "Cancel"  # the safe focus rule of D3
    assert danger.render(60)[0].segments[0].style == DEFAULT_THEME.error  # the box marks it


# --- the sealed block's revision (F2) --------------------------------------------


def _fresh(block, component, width: int) -> bool:
    """The sealed block's rows equal a direct render of the component."""
    cached = [row.styled() for row in block.rows(width)]
    direct = [row.styled() for row in component.render(width)]
    return cached == direct


def _warm(block, width: int) -> None:
    """Two reads: the first caches under the pre-render snapshot, the second
    under the snapshot the render itself moved (the probe's shape)."""
    block.rows(width)
    block.rows(width)


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(lambda dialog: setattr(dialog, "title", "second title"), id="title"),
        pytest.param(lambda dialog: setattr(dialog, "width", 40), id="width"),
        pytest.param(lambda dialog: setattr(dialog, "frame", False), id="frame"),
        pytest.param(lambda dialog: setattr(dialog, "shade", False), id="shade"),
        pytest.param(lambda dialog: setattr(dialog, "align", "right"), id="align"),
    ],
)
def test_a_sealed_dialogs_frame_inputs_reach_the_screen(mutation):
    """F2: every public row input the frame reads moves the block's key."""
    tui = headless_tui(80, 24)
    dialog = Dialog("first title", Text("body line"), ["ok", "cancel"])
    block = tui.add(dialog, id="d")
    block.seal()
    _warm(block, 80)
    mutation(dialog)
    assert _fresh(block, dialog, 80)


def test_a_sealed_dialogs_streamed_body_reaches_the_screen():
    """The body is a row input through its own snapshot, not row identity."""
    tui = headless_tui(80, 24)
    dialog = Dialog("t", Text("body line"), ["ok"])
    block = tui.add(dialog, id="d")
    block.seal()
    _warm(block, 80)
    dialog.body.text = "changed body"
    assert _fresh(block, dialog, 80)


def test_typing_fills_the_field_and_enter_reaches_the_button_row():
    """The body-first routing with the real parts: the Input keeps every
    printable, ``enter`` -- which the Input never binds -- lands on the
    focused button, and the host reads the payload off the field."""
    tui = headless_tui(40, 8)
    prompt = prompt_dialog("rename", placeholder="new name")
    modal = Modal(tui, prompt)
    modal.open()
    for char in "fresh":
        assert modal.handle(KeyEvent(char, char)) is True
    assert prompt.body.text == "fresh"  # the body took every keystroke
    assert modal.chosen is None

    assert modal.handle(KeyEvent("enter")) is True
    assert modal.chosen == "ok" and modal.is_open is False
    assert prompt.body.text == "fresh"  # the payload is the field's

    modal.open()  # a fresh visit: the host resets the field, not the modal
    prompt.body.clear()
    assert modal.handle(KeyEvent("escape")) is True
    assert modal.chosen is None and prompt.body.text == ""
