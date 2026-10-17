"""The demo's protocol wiring: the window title per page, the cursor shape,
the replay's anchors, the rail's click road, the tooltip band, the search
tier's ``c-f`` and the stats overlay's ``c-g``.

The host half of the title / cursor-shape story: the library's ansi helpers
and :class:`~motui.app.TUI` methods have their own tests, and these probes
drive the real :class:`~motui.demo.session.Session` to prove its wiring --
``show`` titles the window after the page, the host loop asks for the focused
leaf's shape, a click on the rail opens the page it names, the action page's
hints ride the session's pointer into the mounted
:class:`~motui.interaction.overlays.Tooltip`, ``c-f`` opens the search row and
its row owns the keyboard, ``c-g`` mounts and unmounts the
:class:`~motui.interaction.overlays.Stats` overlay, and the chrome page's
palette exhibit takes the keyboard through the
page's ``modal``.  :func:`test_the_replays_page_anchors_resolve_on_live_frames`
is the other half of the replay's contract: every coordinate
``motui.demo.script`` scripts is resolved off a live frame here, so a page
that moves an anchor fails a test, not the replay.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from motui import Button, Key, Markdown, MouseEvent, Select, Text, TUI
from motui.kernel import HeadlessScreen
from motui.kernel.ansi import cursor_shape, set_window_title
from motui.kernel.block import descend
from motui.widgets import Editor

from motui.demo.registry import BY_NAME, PAGES
from motui.demo.script import (
    ASIDE_CELL,
    BUTTON_ROW,
    COMBO_CELL,
    CONTENT_X,
    DRAG_FROM,
    DRAG_TO,
    EDITOR_CELL,
    HEADLESS_H,
    HEADLESS_W,
    PALETTE_CELL,
    PROBE_CELL,
    TASK_BOX,
    rail_cell,
)
from motui.demo.session import Session


def _mounted() -> tuple[TUI, Session]:
    """The session mounted on a headless screen, with its output readable."""
    tui = TUI(screen=HeadlessScreen(100, 30), interactive=False)
    return tui, Session(tui)


def _dims(tui: TUI) -> int:
    """How many painted segments carry the scrim's dim attribute."""
    return sum(1 for row in tui.rows for segment in row.segments if segment.style.dim)


def _cell_of(tui: TUI, needle: str) -> tuple[int, int]:
    """The first on-screen cell whose painted row contains ``needle``."""
    for y, row in enumerate(tui.rows):
        col = row.text.find(needle)
        if col >= 0:
            return col, y
    raise AssertionError(f"{needle!r} is not on screen")


def _component_at(tui: TUI, x: int, y: int):
    """The deepest component a screen cell resolves to (the click's own walk)."""
    hit = tui.hit_test(x, y)
    assert hit is not None, (x, y)
    return descend(hit.block.component, hit.row, hit.col)[0]


# --- the window title and the cursor shape ------------------------------------------


def test_show_writes_the_page_title_and_the_focused_fields_cursor_shape():
    tui, session = _mounted()
    marker = len(tui.screen.output)
    session.show(BY_NAME["input"])  # the page's ring focuses an Editor first
    fresh = tui.screen.output[marker:]
    assert set_window_title("motui \u00b7 input") in fresh
    assert cursor_shape("beam") in fresh  # the Editor declares a bar cursor


def test_a_plain_widget_ring_brings_the_block_shape_back():
    tui, session = _mounted()
    session.show(BY_NAME["input"])
    marker = len(tui.screen.output)
    session.show(BY_NAME["data"])  # the ring focuses a view, not a field
    fresh = tui.screen.output[marker:]
    assert set_window_title("motui \u00b7 data") in fresh
    assert cursor_shape("block") in fresh
    assert cursor_shape("beam") not in fresh  # and no stale shape is repeated


# --- the rail's click road ----------------------------------------------------------


def test_a_click_on_the_rails_label_opens_that_page():
    """The rail is a real pane: a stationary click on a label switches pages."""
    tui, session = _mounted()
    assert session.page is PAGES[0]
    x, y = rail_cell("chrome")
    assert _component_at(tui, x, y) is session.rail
    session._round(MouseEvent("left", button=0, x=x, y=y, kind="press"))
    assert session._round(MouseEvent("left", button=0, x=x, y=y, kind="release")) is True
    session._after_round()  # the host follows Tabs.active once per round
    assert session.page is BY_NAME["chrome"]
    assert session.rail.active == PAGES.index(BY_NAME["chrome"])


def test_the_replay_opens_on_the_page_the_rail_click_names():
    """The first events of the replay: the rail click lands on the data page."""
    tui = TUI(screen=HeadlessScreen(100, 30), interactive=False)
    session = Session(tui)
    x, y = rail_cell("data")
    session._round(MouseEvent("left", button=0, x=x, y=y, kind="press"))
    session._round(MouseEvent("left", button=0, x=x, y=y, kind="release"))
    session._after_round()
    assert session.page is BY_NAME["data"]


# --- the tooltip band ---------------------------------------------------------------


def _action_button(tui: TUI, session: Session):
    """The action page's Button, with the cell it occupies on screen."""
    session.show(BY_NAME["action"])
    tui.paint()
    ship = next(block for block in session.body.blocks if isinstance(block, Button))
    assert ship.hint  # the page handed the leaf its one-line hint
    return ship, _cell_of(tui, "Ship")


def test_the_action_pages_hints_ride_the_pointer_into_the_tooltips_band():
    """The band's whole road: the page's ``hint``, the session's pointer, the overlay."""
    tui, session = _mounted()
    ship, (x, y) = _action_button(tui, session)
    session.pointer.handle(MouseEvent("none", button=0, x=x, y=y, kind="motion"))
    tui.paint()
    assert ship.hover is True
    assert ship.hint in tui.rows[y + 1].text  # the band sits under the pointer


def test_focus_out_scrubs_the_hover_and_takes_the_band_with_it():
    """DECSET 1004's blur: the host clears the pointer, so the band goes too."""
    tui, session = _mounted()
    ship, (x, y) = _action_button(tui, session)
    session.pointer.handle(MouseEvent("none", button=0, x=x, y=y, kind="motion"))
    tui.paint()
    assert ship.hint in tui.rows[y + 1].text
    assert session._round(Key("focus_out")) is True  # the host owns the blur
    tui.paint()
    assert ship.hover is False and session.pointer.position is None
    assert ship.hint not in tui.rows[y + 1].text


# --- the search tier ----------------------------------------------------------------


def test_c_f_opens_the_search_row_and_the_row_owns_the_keyboard():
    """``c-f`` opens the tier; while the row is open the host's keys give way --
    ``q`` searches, ``c-n``/``c-p`` do not move the page."""
    tui, session = _mounted()
    session.show(BY_NAME["text"])
    page = session.page
    assert session._round(Key("c-f")) is True
    assert session.find.is_open
    for char in "text":  # a printable typed at the shell searches
        assert session._round(Key(char, char)) is True
    assert session.find.query == "text" and session.find.matches

    assert session._round(Key("c-n")) is True  # the host's keys yield ...
    assert session._round(Key("c-p")) is True
    assert session._round(Key("tab")) is True
    assert session.page is page  # ... so the page did not move
    assert session._round(Key("q", "q")) is True  # and q is a query character
    assert session.find.query == "textq"

    assert session._round(Key("escape")) is True  # the row's own dismiss key
    assert not session.find.is_open
    assert session._round(Key("q", "q")) is False  # closed: q quits again


def test_a_page_switch_closes_the_search_with_the_page_it_addressed():
    tui, session = _mounted()
    session.show(BY_NAME["text"])
    session._round(Key("c-f"))
    for char in "text":
        session._round(Key(char, char))
    assert session.find.matches

    session.show(BY_NAME["data"])  # a click on the rail lands here too
    assert not session.find.is_open
    tui.paint()
    assert not any("find \u276e" in row.text for row in tui.rows)


def test_a_step_on_a_long_page_reveals_the_current_match():
    """The reveal road through the session: the window follows ``enter``."""
    tui, session = _mounted()
    session.show(BY_NAME["streaming"])  # the 346-line fixture
    tui.paint()
    content = session.main.viewport  # the page's own pane, not the rail's
    assert content.offset == 0  # the page opens at its top
    session._round(Key("c-f"))
    for char in "markdown":
        session._round(Key(char, char))
    assert session.find.matches

    for _ in range(len(session.find.matches)):
        if content.offset:
            break
        assert session._round(Key("enter")) is True
    assert content.offset > 0  # the window moved to the current match


# --- the stats overlay --------------------------------------------------------------


def test_c_g_mounts_and_unmounts_the_dev_stats_overlay():
    """The host wiring: ``c-g`` mounts the box, it counts rounds, ``c-g`` unmounts."""
    tui, session = _mounted()
    assert session.stats is None
    assert session._round(Key("c-g")) is True
    stats = session.stats
    assert stats is not None and stats in tui.frame.overlays
    tui.paint()
    assert "frames " in tui.rows[0].text  # the box rides the top-right corner

    counted = stats.events
    assert session._round(Key("tab")) is True  # the ring's own door, still counted
    assert stats.events == counted + 1
    x, y = _cell_of(tui, "text")
    assert session._round(MouseEvent("none", button=0, x=x, y=y, kind="motion")) is True
    assert session.pointer.position == (x, y)
    assert session._round(Key("focus_out")) is True  # the blur is the host's
    assert session.pointer.position is None  # ... and still clears the hover
    assert stats.events == counted + 3

    assert session._round(Key("c-g")) is True
    assert session.stats is None and stats not in tui.frame.overlays
    tui.paint()
    assert "frames " not in tui.rows[0].text


# --- the chrome page's palette exhibit ----------------------------------------------


def test_the_chrome_pages_palette_exhibit_takes_the_keyboard_and_echoes():
    """The page's ``modal``: the row opens it, its query row filters, a pick echoes."""
    tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
    session = Session(tui)
    session.show(BY_NAME["chrome"])
    tui.paint()
    palette = session.body.modal
    assert palette is not None and not palette.is_open
    x, y = PALETTE_CELL
    for _ in range(2):  # the first click focuses the row, the second activates it
        session._round(MouseEvent("left", button=0, x=x, y=y, kind="press"))
        session._round(MouseEvent("left", button=0, x=x, y=y, kind="release"))
    session._after_round()  # the pick read opens the palette (the page's note)
    assert palette.is_open
    for char in "say":  # the palette's own query row takes the keys
        assert session._round(Key(char, char)) is True
    assert palette.input.text == "say"
    assert session._round(Key("enter")) is True
    session._after_round()
    assert not palette.is_open
    tui.paint()
    assert "say hello" in tui.screen.output  # the toast (and the echo line) report it


# --- the modal page's dialogs --------------------------------------------------------


def test_the_modal_pages_dialog_rides_a_modal_its_scrim_and_its_buttons():
    """A trigger opens its dialog over the scrim; ``escape`` cancels with
    ``chosen is None``; the button row's own value is the pick."""
    tui, session = _mounted()
    session.show(BY_NAME["modal"])
    tui.paint()
    body = session.body
    echo = next(
        block
        for block in body.blocks
        if isinstance(block, Text) and block.text == "last result: --"
    )
    delete = next(
        block
        for block in body.blocks
        if isinstance(block, Button) and block.label == "Delete project"
    )
    plain_dim = _dims(tui)
    assert delete.activate() is True  # the pick names the dialog it opens
    session._after_round()  # read once: the page opens the modal on the report
    modal = session._modal()
    assert modal is not None and modal.is_open  # the page's modal field routes it
    tui.paint()
    assert any("delete the project?" in row.text for row in tui.rows)  # the panel is up
    assert _dims(tui) > plain_dim  # and the scrim reached the frame behind it

    assert session._round(Key("escape")) is True  # the modal owns the keyboard
    assert modal.chosen is None and not modal.is_open  # escape cancels with nothing chosen
    session._after_round()
    body.tick()  # the page's beat reads the result once and announces it
    assert echo.text.startswith("last result: cancel")

    assert delete.activate() is True  # a fresh visit, a fresh dialog
    session._after_round()
    modal = session._modal()
    assert modal is not None and modal.is_open
    assert session._round(Key("left")) is True  # off the cancel, onto the danger button
    assert session._round(Key("enter")) is True
    assert modal.chosen is True  # the Delete button's own value
    assert not modal.is_open
    session._after_round()
    body.tick()
    assert echo.text == "last result: chosen: True"


# --- the page-level wiring behind the plays ------------------------------------------


def test_the_overview_index_pick_opens_the_page_it_names():
    tui, session = _mounted()
    session.show(BY_NAME["overview"])
    ring = session.body.focus
    index = next(target for target in ring.targets if isinstance(target, Select))
    assert session._round(Key("down")) is True  # onto "text"
    assert index.index == 1
    assert session._round(Key("enter")) is True
    session._after_round()  # the host reads the pick once and opens the page
    assert session.page is BY_NAME["text"]


def test_the_styles_pickers_pick_reskins_the_shell():
    """The one road to a new skin: the pick names a variant, the host rebuilds."""
    tui, session = _mounted()
    session.show(BY_NAME["styles"])
    assert session.theme_index == 0
    assert session._round(Key("down")) is True  # onto "amber"
    assert session._round(Key("enter")) is True
    session._after_round()
    assert session.theme_index == 1
    tui.paint()
    echo = next(
        block
        for block in session.body.blocks
        if isinstance(block, Text) and block.text.startswith("current theme:")
    )
    assert echo.text == "current theme: amber"  # the echo landed on the fresh page


def test_the_data_pages_table_and_tree_echo_their_reports():
    """One ring over the page: a table pick and the shell's own ``c-t`` filter,
    each read once by the host and echoed on the page's line."""
    from motui import Table, Tree

    tui, session = _mounted()
    session.show(BY_NAME["data"])
    assert session._round(Key("down")) is True
    assert session._round(Key("enter")) is True
    session._after_round()
    echo = next(
        block
        for block in session.body.blocks
        if isinstance(block, Text) and block.text.startswith("last pick:")
    )
    assert echo.text == "last pick: 1"

    tree = next(block for block in session.body.blocks if isinstance(block, Tree))
    assert session._round(Key("c-t")) is True  # the host's own key
    assert [row.text for row in tree.render(60)] == ["\u25be motui", "  \u25b8 kernel"]
    filter_echo = next(
        block
        for block in session.body.blocks
        if isinstance(block, Text) and block.text.startswith("filter:")
    )
    assert filter_echo.text == "filter: 'kernel'"


# --- the replay's anchors, resolved off live frames ----------------------------------


def test_the_replays_page_anchors_resolve_on_live_frames():
    """Every coordinate ``motui.demo.script`` scripts is a real cell of a live page.

    The replay hard-codes a handful of screen cells (the task box, the drag,
    the palette row, the probe row, the Editor cell, the aside's wheel cell,
    the action page's Button row); this test resolves each one through the
    frame the user sees, so a page that moves an anchor fails here, not in the
    piped run.
    """
    tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
    session = Session(tui)

    session.show(BY_NAME["text"])
    tui.paint()
    sample = next(
        block
        for block in session.body.blocks
        if isinstance(block, Markdown) and "example.invalid" in block.text
    )
    assert _component_at(tui, *TASK_BOX) is sample  # the task box's first cell
    assert sample.click(*_relative(tui, TASK_BOX)) is True  # and it takes the click
    assert sample.chosen == "todo:0"
    sample.chosen = None
    for cell in (DRAG_FROM, DRAG_TO):  # both ends of the drag are sample rows
        assert _component_at(tui, *cell) is sample

    session.show(BY_NAME["chrome"])
    tui.paint()
    palette_row = _component_at(tui, *PALETTE_CELL)
    assert isinstance(palette_row, Select)
    assert palette_row.options[0].value == "open the palette"
    probe = _component_at(tui, *PROBE_CELL)
    assert probe is next(
        block for block in session.body.blocks if isinstance(block, Button)
    )
    x, y = _cell_of(tui, "pane row 01")  # the aside pane's own rows
    assert x >= ASIDE_CELL[0] - 30  # the wheel cell sits inside the aside
    assert _component_at(tui, *ASIDE_CELL) is not None

    session.show(BY_NAME["input"])
    tui.paint()
    windowed = next(
        block for block in session.body.blocks
        if isinstance(block, Editor) and block.max_rows == 5
    )
    assert _component_at(tui, *EDITOR_CELL) is windowed
    composer = _component_at(tui, *COMBO_CELL)
    assert isinstance(composer, Select)  # the ComboBox exhibit's opening row
    assert composer.options[0].value == "open the composer"

    session.show(BY_NAME["action"])
    tui.paint()
    assert _component_at(tui, CONTENT_X + 2, BUTTON_ROW) is next(
        block for block in session.body.blocks if isinstance(block, Button)
    )


def _relative(tui: TUI, cell: tuple[int, int]) -> tuple[int, int]:
    """A screen cell as the block's own ``(row, col)``, through the hit test."""
    hit = tui.hit_test(*cell)
    assert hit is not None
    return hit.row, hit.col


# --- the interactive-only code paths --------------------------------------------


def _live_session(page_name: str) -> tuple[TUI, Session]:
    """A session on an **interactive** headless run: the live code paths.

    ``interactive=False`` is what every other probe here drives, and the dump
    paths never run a page's control-bar handler (``act`` returns early) --
    the split that let a broken stream reach a real terminal unnoticed.
    ``interactive=True`` on a headless screen runs the same handlers a real
    session does, with the events still scripted.
    """
    tui = TUI(screen=HeadlessScreen(100, 30), interactive=True)
    session = Session(tui)
    session.show(BY_NAME[page_name])
    return tui, session


def _progress(session: Session) -> str:
    """The streaming page's progress line, read off its own ``Text`` block."""
    body = session.body
    assert body is not None
    return next(
        block.text
        for block in body.blocks
        if isinstance(block, Text) and block.text.startswith("streaming:")
    )


def test_the_streaming_bar_runs_every_verb_on_the_interactive_path():
    """Every control-bar pick runs its verb -- ``step``, ``play``, ``speed``.

    The picks arrive as ``chosen: '<action>'`` reports and the page's ``note``
    turns the name into a verb on the stream, so this is the road a click on
    the bar takes.
    """
    _, session = _live_session("streaming")
    body = session.body
    assert body is not None and body.note is not None

    assert "playing" in _progress(session)  # a page opens playing
    body.note("chosen: 'pause'")
    paused = _progress(session)
    assert "paused" in paused

    body.note("chosen: 'speed'")  # used to be a no-op: no handler on the bar
    assert "2x" in _progress(session)
    body.note("chosen: 'speed'")
    assert "4x" in _progress(session)
    body.note("chosen: 'speed'")  # the cycle closes: 1x, and the suffix is gone
    assert _progress(session) == paused

    body.note("chosen: 'step'")  # used to raise: advance was a property
    stepped = _progress(session)
    assert stepped != paused and "\u00b7 paused" in stepped

    body.note("chosen: 'replay'")
    replayed = _progress(session)
    assert replayed.startswith("streaming: 0/") and "playing" in replayed

    body.note("chosen: 'play'")
    assert "playing" in _progress(session)

    body.note("chosen: 'off-the-bar'")  # a name no verb answers: ignored, never raised


def test_a_live_session_advances_the_stream_by_its_pace():
    """``beat`` appends the pace's blocks: the stream's own growth rule."""
    _, session = _live_session("streaming")
    body = session.body
    assert body is not None and body.tick is not None

    body.tick()  # one beat at 1x
    assert _progress(session).startswith("streaming: 1/")

    body.note("chosen: 'speed'")  # 2x
    body.tick()
    assert _progress(session).startswith("streaming: 3/")

    body.note("chosen: 'pause'")
    body.tick()  # a paused stream does not grow
    assert _progress(session).startswith("streaming: 3/")


def test_the_dump_paths_survive_a_legacy_codepage():
    """``--pages`` on a piped cp1252 stdout: the frames are the same text everywhere.

    The CI's Windows leg pipes the dump, and a Western-locale codepage cannot
    encode the scrollbar's ``\u2591``/``\u2588`` -- the child must still exit
    0, in UTF-8, rather than die on its own last line.
    """
    root = Path(__file__).resolve().parent.parent
    done = subprocess.run(
        [sys.executable, "-m", "motui", "--pages"],
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "PYTHONIOENCODING": "cp1252",
            "PYTHONPATH": str(root / "src"),
        },
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")[-2000:]
    assert done.stdout
    assert "\u2588".encode() in done.stdout  # the frames came out whole
