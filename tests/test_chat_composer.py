"""Tests for mocode_tui.chat.composer (Composer).

Contract: ``attach`` pins the five-piece footer (top rule, editor, bottom
rule, palette slot, status line) bottom, in document order, once; the
editor's keymap leaves ``enter`` to the host and breaks lines on ``c-j``;
``set_working`` is ref-counted and drives the top rule's braille label
through ``TUI.every``; an open palette grows the slot block below the
closed box; ``anchor_cursor`` pins the painter's IME anchor to the
editor's cursor cell; ``detach`` unpins everything and stops the spinner.
"""

import pytest

from mocode_tui.chat.composer import BLOCK_IDS, Composer
from mocode_tui.chat.slash import SlashPalette
from mocode_tui.core.style import ACCENT
from mocode_tui.testing import headless_tui
from mocode_tui.core.theme import Theme
from mocode_tui.core.events import Key
from mocode_tui.widgets.choice import Option
from mocode_tui.widgets.editor import Editor
from mocode_tui.widgets.spinner import Spinner

_MENU = [
    Option("/help", value="help"),
    Option("/model", value="model"),
    Option("/clear", value="clear"),
    Option("/quit", value="quit"),
]


def _composer(**kwargs):
    tui = headless_tui(80, 24)
    composer = Composer(**kwargs).attach(tui)
    return tui, composer


def _row_texts(block) -> list[str]:
    return [row.text for row in block.render(80)]


def test_attach_pins_the_five_blocks_in_order():
    tui, composer = _composer()
    blocks = tui.document.blocks()
    assert [block.id for block in blocks] == list(BLOCK_IDS)
    assert all(block.pin == "bottom" for block in blocks)
    assert blocks[1].component is composer.editor
    assert blocks[4].component is composer.statusline


def test_attach_is_one_time():
    tui, composer = _composer()
    with pytest.raises(RuntimeError):
        composer.attach(tui)


def test_editor_keymap_leaves_enter_to_the_host():
    tui, composer = _composer()
    assert "enter" not in composer.editor.keymap
    assert composer.editor.keymap["c-j"] == "newline"
    # enter is not consumed: the host's submit gesture sees it.
    assert composer.editor.handle_key(Key("enter")) is False
    # c-j breaks lines, exactly like the editor's default enter did.
    composer.editor.insert("ab")
    composer.editor.handle_key(Key("c-j"))
    assert composer.editor.value == "ab\n"
    # every other editor binding survives.
    assert composer.editor.handle_key(Key("left")) is True


def test_editor_placeholder_is_empty_by_default():
    tui, composer = _composer()
    assert composer.editor.placeholder == ""  # the at-rest box shows only the cursor block
    assert composer.prompt == ""  # carried for hosts; the editor draws none


def test_theme_flows_into_every_piece():
    tui, composer = _composer(theme=Theme(accent=ACCENT))
    top = tui.get("composer-top").component
    assert top.theme is composer.theme
    assert top.label_style == ACCENT
    assert tui.get("composer-bottom").component.theme is composer.theme
    assert composer.statusline.theme is composer.theme
    assert composer.palette.theme is composer.theme


def test_commands_seed_the_palette():
    tui, composer = _composer(commands=_MENU)
    assert isinstance(composer.palette, SlashPalette)
    assert _row_texts(tui.get("composer-palette")) == []
    composer.palette.open()
    assert len(_row_texts(tui.get("composer-palette"))) == 4


def test_palette_grows_the_slot_block_below_the_box():
    tui, composer = _composer(commands=_MENU)
    slot = tui.get("composer-palette")
    assert _row_texts(slot) == []  # at rest: zero rows
    composer.palette.open()
    composer.palette.sync_query("/mod")
    assert len(_row_texts(slot)) == 1  # the filtered rows hang below the box
    composer.palette.close()
    assert _row_texts(slot) == []


def test_set_working_drives_the_spinner_and_clears_on_the_last_leave():
    tui, composer = _composer()
    now = [1000.0]
    tui._clock = lambda: now[0]
    top = tui.get("composer-top").component

    composer.set_working(True)
    assert top.label == f"{Spinner('Working').frame} Working"
    first = top.label
    now[0] += Composer.SPINNER_INTERVAL
    tui._tick(now[0])  # the every cycle fires
    assert top.label != first  # a new braille frame
    assert len(tui._every) == 1

    composer.set_working(True)  # a second, overlapping turn: ref-counted
    composer.set_working(False)  # one turn finishes: the label stays
    assert top.label != ""
    composer.set_working(False)  # the last turn finishes: label cleared
    assert top.label == ""
    assert [entry.handle.cancelled for entry in tui._every] == [True]

    now[0] += 10.0
    tui._tick(now[0])  # the pump prunes the cancelled cycle
    assert tui._every == []
    assert top.label == ""  # nothing resurrects the label afterwards


def test_set_working_clamps_at_zero():
    tui, composer = _composer()
    composer.set_working(False)  # no matching enter: a no-op, not a crash
    composer.set_working(False)
    assert tui.get("composer-top").component.label == ""
    composer.set_working(True)
    composer.set_working(False)
    assert tui.get("composer-top").component.label == ""


def test_set_working_and_anchor_require_an_attached_composer():
    composer = Composer()
    with pytest.raises(RuntimeError):
        composer.set_working(True)
    with pytest.raises(RuntimeError):
        composer.anchor_cursor(headless_tui())


def test_anchor_cursor_pins_the_ime_anchor_to_the_editor():
    tui, composer = _composer(commands=_MENU)
    composer.editor.insert("hi")
    composer.anchor_cursor(tui)
    # tail bottom-up: status / slot(0 rows) / rule / editor(1 row) / rule
    # -> the editor's only visual row sits at height - 2 - 1 - 0 = 21
    assert tui.painter._anchor == (21, 2)

    composer.palette.open()  # the open menu pushes the box up by its rows
    composer.anchor_cursor(tui)
    assert tui.painter._anchor == (21 - 4, 2)


def test_detach_unpins_everything_and_stops_the_spinner():
    tui, composer = _composer(commands=_MENU)
    composer.editor.insert("typed")
    composer.set_working(True)
    composer.detach()
    assert tui.document.blocks() == ()
    with pytest.raises(RuntimeError):
        composer.set_working(True)  # a detached composer is inert
    assert composer.editor.value == "typed"  # the typed text survives
    # And the composer can be attached again, with the spinner state reset.
    composer.attach(tui)
    assert [block.id for block in tui.document.blocks()] == list(BLOCK_IDS)
    assert tui.get("composer-top").component.label == ""


def test_the_editor_is_a_multiline_buffer():
    tui, composer = _composer()
    assert isinstance(composer.editor, Editor)
    composer.editor.insert("one")
    composer.editor.handle_key(Key("c-j"))
    composer.editor.insert("two")
    assert composer.editor.value == "one\ntwo"
    rows = tui.get("composer-input").render(80)
    assert [row.text.strip() for row in rows] == ["one", "two"]
