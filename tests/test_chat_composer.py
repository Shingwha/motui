"""Tests for mocode_tui.chat.composer (Composer).

``attach`` parks the five-piece footer in the driver's frame band once;
``set_working`` drives the braille label ref-counted, an open palette grows
the slot, and ``detach`` releases the band.  The band is the pinned footer
of before, one rectangle lower: the rows a band paints are exactly the rows
the five bottom-pinned blocks painted in the document, pinned here against
the five-block tail of the screen.
"""

import asyncio

import pytest

from _doubles import RecordingScreen, Rows, texts

from mocode_tui.app import TUI
from mocode_tui.chat.composer import Composer
from mocode_tui.chat.slash import SlashPalette
from mocode_tui.chat.statusline import StatusLine
from mocode_tui.core.ansi import cursor_position
from mocode_tui.core.block import Document
from mocode_tui.core.events import Key
from mocode_tui.core.screen import HeadlessScreen
from mocode_tui.core.style import ACCENT
from mocode_tui.core.theme import DEFAULT_THEME, Theme
from mocode_tui.core.viewport import Viewport
from mocode_tui.widgets.choice import Option
from mocode_tui.widgets.chrome import Divider
from mocode_tui.widgets.editor import Editor
from mocode_tui.widgets.spinner import Spinner

_MENU = [
    Option("/help", value="help"),
    Option("/model", value="model"),
    Option("/clear", value="clear"),
    Option("/quit", value="quit"),
]

#: The pinned footer's block ids, in document (screen) order.
_FOOTER_IDS = [
    "composer-top",
    "composer-input",
    "composer-bottom",
    "composer-palette",
    "composer-status",
]


def _composer(**kwargs):
    tui = TUI(screen=RecordingScreen(80, 24), interactive=False)
    return tui, Composer(**kwargs).attach(tui)


def _row_texts(block) -> list[str]:
    return [row.text for row in block.render(80)]


def _frame(tui) -> list[str]:
    """The rows of the frame the driver last painted."""
    return [row.text for row in tui.rows]


async def _sample(get, seconds: float) -> list:
    """Sample ``get()`` across ``seconds`` of live pump time."""
    out: list = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while True:
        out.append(get())
        if loop.time() >= deadline:
            return out
        await asyncio.sleep(0.02)


def test_attach_pins_the_five_blocks_in_order():
    tui, composer = _composer()
    # The footer is a frame-level band, not blocks pinned in the transcript:
    # they live in the composer's own document, parked in the driver's band.
    blocks = composer.document.blocks()
    assert [block.id for block in blocks] == _FOOTER_IDS
    assert all(block.pin == "bottom" for block in blocks)
    assert blocks[1].component is composer.editor
    assert blocks[4].component is composer.statusline
    assert tui.document.blocks() == ()  # the transcript holds no footer blocks
    assert tui.band is not None and tui.band.viewport is composer.viewport
    assert tui.frame.band is tui.band


def test_attach_is_one_time():
    tui, composer = _composer()
    with pytest.raises(RuntimeError):
        composer.attach(tui)


def test_the_editor_is_keymapped_for_the_hosts_submit_gesture():
    tui, composer = _composer()
    editor = composer.editor
    assert editor.placeholder == ""  # the at-rest box shows only the cursor block
    assert composer.prompt == ""  # carried for hosts; the editor draws none
    # enter is not consumed: the host's submit gesture sees it.
    assert "enter" not in editor.keymap
    assert editor.handle(Key("enter")) is False
    # c-j breaks lines, exactly like the editor's default enter did.
    editor.insert("one")
    assert editor.handle(Key("c-j")) is True
    editor.insert("two")
    assert editor.value == "one\ntwo"
    assert [row.text.strip() for row in tui.get("composer-input").render(80)] == ["one", "two"]
    # every other editor binding survives.
    assert editor.handle(Key("left")) is True


def test_theme_flows_into_every_piece():
    tui, composer = _composer(theme=Theme(accent=ACCENT))
    top = tui.get("composer-top").component
    assert top.theme is composer.theme
    assert top.label_style == ACCENT
    assert tui.get("composer-bottom").component.theme is composer.theme
    assert composer.statusline.theme is composer.theme
    assert composer.palette.theme is composer.theme


def test_commands_seed_the_palette_and_the_slot_grows_below_the_box():
    tui, composer = _composer(commands=_MENU)
    slot = tui.get("composer-palette")
    assert isinstance(composer.palette, SlashPalette)
    assert _row_texts(slot) == []  # at rest: zero rows
    composer.palette.open()
    assert len(_row_texts(slot)) == 4  # the full command list
    composer.palette.set_query("/mod")
    assert len(_row_texts(slot)) == 1  # the filtered rows hang below the box
    composer.palette.close()
    assert _row_texts(slot) == []


def test_the_working_label_rides_the_pump_until_the_last_turn_leaves():
    tui = TUI(screen=HeadlessScreen(80, 24), interactive=False)
    composer = Composer().attach(tui)
    top = tui.get("composer-top").component
    seen: list[str] = []

    async def body(app):
        composer.set_working(True)  # one turn starts the spinner cycle
        seen.extend(await _sample(lambda: top.label, 0.4))
        composer.set_working(True)  # a second, overlapping turn: ref-counted
        composer.set_working(False)  # one turn finishes: the label stays
        seen.append(top.label)
        composer.set_working(False)  # the last turn finishes: label cleared
        composer.set_working(False)  # a no-op leave: clamps at zero, no crash
        await _sample(lambda: top.label, 0.05)
        seen.append(top.label)  # nothing resurrects the label afterwards
        app.stop()

    asyncio.run(tui.run(body))

    working = seen[:-2]
    assert working and all("Working" in label for label in working)
    # The pump stepped the braille cycle: more than one frame was painted.
    assert len({label.split(" ")[0] for label in working}) >= 2
    assert seen[-2] != ""  # an overlapping turn keeps the label
    assert seen[-1] == ""  # the last leave clears it
    # And the final frame shows the closed box: a plain rule, no label.
    assert not any("Working" in row for row in _frame(tui))
    assert Spinner("Working").text not in _frame(tui)


def test_set_working_requires_an_attached_composer():
    composer = Composer()
    with pytest.raises(RuntimeError):
        composer.set_working(True)
    with pytest.raises(RuntimeError):
        composer.anchor_cursor(TUI(screen=RecordingScreen(80, 24), interactive=False))


def test_the_editor_cursor_cell_closes_the_frame():
    tui, composer = _composer(commands=_MENU)
    composer.editor.insert("hi")
    composer.anchor_cursor(tui)
    tui.paint()
    # tail bottom-up: status / slot(0 rows) / rule / editor(1 row) / rule
    # -> the editor's only visual row sits at height - 2 - 1 - 0 = 21,
    # and every frame closes on the cursor-position escape for that cell.
    assert tui.screen.delta().endswith(cursor_position(22, 3))

    composer.palette.open()  # the open menu pushes the box up by its rows
    composer.anchor_cursor(tui)
    tui.paint()
    assert tui.screen.delta().endswith(cursor_position(18, 3))


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
    assert [block.id for block in composer.document.blocks()] == _FOOTER_IDS
    assert tui.get("composer-top").component.label == ""


# --- the band (D6) --------------------------------------------------------------


def _pinned_footer(tui: TUI) -> None:
    """The pre-W5 footer: the same five blocks pinned into the document."""
    theme = DEFAULT_THEME
    tui.add(Divider(theme=None, label_style=theme.accent), id="composer-top", pin="bottom")
    tui.add(Editor(theme=None), id="composer-input", pin="bottom")
    tui.add(Divider(theme=None), id="composer-bottom", pin="bottom")
    tui.add(SlashPalette([]), id="composer-palette", pin="bottom")
    tui.add(StatusLine(theme=None), id="composer-status", pin="bottom")


def test_the_band_renders_the_same_rows_the_pinned_footer_did():
    """The equivalence proof: the band is the pinned tail, one rectangle lower."""
    banded = _composer()[0]
    pinned = TUI(screen=RecordingScreen(80, 24), interactive=False)
    _pinned_footer(pinned)
    banded.paint()
    pinned.paint()
    assert _frame(banded) == [row.text for row in pinned.rows]
    # the transcript holds no pinned footer of its own: the band's rows do
    assert all(block.pin is None for block in banded.document.blocks())
    assert banded.frame.table.rows[-1][0].pane_id == "band"
    # bottom-up: status / the palette's zero rows / bottom rule / editor / rule
    assert _frame(banded)[-4:] == ["─" * 80, " ", "─" * 80, " " * 79]


def test_the_band_spans_the_full_width_beneath_a_split():
    tui, composer = _composer()
    left, right = tui.split("vertical", ratios=(1, 1))
    left.document.add(Rows("transcript"))
    right.document.add(Rows("preview"))
    composer.editor.insert("two\nlines")
    tui.paint()
    rows = _frame(tui)
    # the band spans both panes, and the pane area is what is left of the screen
    assert rows[0] == "transcript" + " " * 30 + "preview" + " " * 33
    assert rows[19:] == [
        "─" * 80,
        "two",
        "lines ",
        "─" * 80,
        " " * 79,
    ]
    assert tui.frame.panes[0].rect.height == 19


def test_an_open_palette_grows_the_band_and_the_pane_area_shrinks():
    tui, composer = _composer(commands=_MENU)
    tui.add(Rows("body"))
    tui.paint()
    assert tui.band.rect.height == 4  # top rule + editor + bottom rule + status
    assert tui.viewport_rows() == (0, 19)
    composer.palette.open()
    tui.paint()
    assert tui.band.rect.height == 8  # the palette's four rows hang below the box
    assert tui.frame.panes[0].rect.height == 16
    assert tui.viewport_rows() == (0, 15)
    # bottom-up: status / the palette's rows / bottom rule / editor / rule
    rows = _frame(tui)
    assert rows[:16] == ["body"] + [""] * 15
    assert rows[16:] == [
        "─" * 80,
        " ",
        "─" * 80,
        "❮ /help",
        "  /model",
        "  /clear",
        "  /quit",
        " " * 79,
    ]
