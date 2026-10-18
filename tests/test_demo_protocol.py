"""The demo's protocol: the eleven pages, one play each, and the shell's roads.

One file for the demo's own contract, written around the structure the kit
gives it (``specs/2026-10-17-demo-structure``): the registry's page list and
the rail's click road; one representative play per page -- the index opening
a page, the task box flipping, the Collapsible folding, a Button landing its
pick, the ComboBox's dropdown over its ``Modal``, the table's pick and mark,
a danger dialog over the scrim, a palette row, the shell page's own pane, a
re-skin, the manual the search can address; and the shell's own roads -- the
search tier's ``c-f``, the selection's drag-and-copy through OSC 52, the
``c-g`` stats box, the tooltip band and the copy toast.  The host half of
the title / cursor-shape story is here as well: ``show`` titles the window
after the page and the host loop asks for the focused leaf's shape, and the
``c-t`` filter is pinned as the page's own data, never the host's.

Every probe drives the real :class:`~motui.demo.session.Session` with the
events the piped replay feeds it; the tests that script a screen cell take
it from :class:`~motui.demo.script.Anchors` -- the replay's own symbolic
anchors, resolved against a live layout at the replay's geometry -- so a
page that moves an exhibit fails here, not in the run.
:func:`test_the_replays_page_anchors_resolve_on_live_frames` walks every
anchor the replay scripts, and the streaming page's interactive-only paths
and the piped dump's codepage survival close the file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from motui import Button, Key, Markdown, MouseEvent, Select, Text, TUI
from motui.kernel import HeadlessScreen, Line
from motui.kernel.ansi import cursor_shape, set_window_title
from motui.kernel.block import descend
from motui.widgets import Collapsible, Editor

from motui.demo.kit import Echo, Exhibit
from motui.demo.page import Page, PageBody
from motui.demo.registry import BY_NAME, PAGES
from motui.demo.script import (
    HEADLESS_H,
    HEADLESS_W,
    AnchorError,
    Anchors,
    rail_cell,
)
from motui.demo.session import Session


def _mounted() -> tuple[TUI, Session]:
    """The session mounted on a headless screen, with its output readable."""
    tui = TUI(screen=HeadlessScreen(100, 30), interactive=False)
    return tui, Session(tui)


def _replay_sized() -> tuple[TUI, Session]:
    """A session at the replay's own geometry: the frame ``Anchors`` resolves against."""
    tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
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


def _echo_of(session: Session) -> Echo:
    """The page's kit echo line, read off the body's own blocks."""
    assert session.body is not None
    return next(block for block in session.body.blocks if isinstance(block, Echo))


def _click(session: Session, cell: tuple[int, int]) -> None:
    """One stationary click, through the host's own rounds (and the picks read)."""
    for kind in ("press", "release"):
        session._round(MouseEvent("left", button=0, x=cell[0], y=cell[1], kind=kind))
    session._after_round()


# --- the page table ------------------------------------------------------------------


def test_the_registry_is_the_eleven_families_in_rail_order():
    """The page list: the ten families and the manual, one name one home.

    The order is the rail's own, the labels carry no duplicate and every page
    brings its own hint rows -- the registry is the single source the rail,
    the index, the ``c-n`` / ``c-p`` walk and ``--pages`` all read.
    """
    assert [page.name for page in PAGES] == [
        "overview", "text", "layout", "actions", "forms", "views",
        "modals", "shell", "themes", "streaming", "notes",
    ]
    assert len({page.name for page in PAGES}) == len(PAGES)
    assert BY_NAME == {page.name: page for page in PAGES}
    assert all(page.description and page.hints for page in PAGES)
    _, session = _mounted()
    assert session.rail.items == [page.name for page in PAGES]  # the rail's own labels


# --- the window title and the cursor shape ------------------------------------------


def test_show_writes_the_page_title_and_the_focused_fields_cursor_shape():
    tui, session = _mounted()
    marker = len(tui.screen.output)
    session.show(BY_NAME["forms"])  # the page's ring focuses an Editor first
    fresh = tui.screen.output[marker:]
    assert set_window_title("motui \u00b7 forms") in fresh
    assert cursor_shape("beam") in fresh  # the Editor declares a bar cursor


def test_a_plain_widget_ring_brings_the_block_shape_back():
    tui, session = _mounted()
    session.show(BY_NAME["forms"])
    marker = len(tui.screen.output)
    session.show(BY_NAME["views"])  # the ring focuses a view, not a field
    fresh = tui.screen.output[marker:]
    assert set_window_title("motui \u00b7 views") in fresh
    assert cursor_shape("block") in fresh
    assert cursor_shape("beam") not in fresh  # and no stale shape is repeated


# --- the hint band ------------------------------------------------------------------


def test_the_hint_band_follows_the_page_and_survives_a_re_skin():
    """``show`` rebuilds the band from the page's own hints and the host's
    global keys; a theme switch keeps the page it is showing."""
    from motui.demo.assets import THEMES
    from motui.demo.shell import HINT_ITEMS

    tui, session = _mounted()
    views = BY_NAME["views"]
    session.show(views)
    assert session.hint_bar.items == [*views.hints, *HINT_ITEMS]
    assert session.hint_bar.render(200)[0].text.startswith("space mark the cursor row")

    session.set_theme(1)  # a re-skin rebuilds the band, not the page
    assert session.page is views and session.theme is THEMES[1][1]
    assert session.hint_bar.items == [*views.hints, *HINT_ITEMS]

    session.show(BY_NAME["notes"])
    assert session.hint_bar.items == [*BY_NAME["notes"].hints, *HINT_ITEMS]
    assert session.hint_bar.render(200)[0].text.startswith("wheel scroll the rest of it")


# --- the rail's click road ----------------------------------------------------------


def test_a_click_on_the_rails_label_opens_that_page():
    """The rail is a real pane: a stationary click on a label switches pages."""
    tui, session = _mounted()
    assert session.page is PAGES[0]
    x, y = rail_cell("shell")
    assert _component_at(tui, x, y) is session.rail
    session._round(MouseEvent("left", button=0, x=x, y=y, kind="press"))
    assert session._round(MouseEvent("left", button=0, x=x, y=y, kind="release")) is True
    session._after_round()  # the host follows the rail's active once per round
    assert session.page is BY_NAME["shell"]
    assert session.rail.active == PAGES.index(BY_NAME["shell"])


def test_the_replay_opens_on_the_page_the_rail_click_names():
    """The first events of the replay: the rail click lands on the views page."""
    tui = TUI(screen=HeadlessScreen(100, 30), interactive=False)
    session = Session(tui)
    x, y = rail_cell("views")
    session._round(MouseEvent("left", button=0, x=x, y=y, kind="press"))
    session._round(MouseEvent("left", button=0, x=x, y=y, kind="release"))
    session._after_round()
    assert session.page is BY_NAME["views"]


# --- one play per page ---------------------------------------------------------------


def test_the_overview_index_pick_opens_the_page_it_names():
    tui, session = _mounted()
    session.show(BY_NAME["overview"])
    ring = session.body.focus
    index = next(target for target in ring.targets if isinstance(target, Select))
    assert session._round(Key("down")) is True  # onto "text"
    assert index.index == 1
    assert session._round(Key("enter")) is True
    session._after_round()  # the row's Action opens the page it names
    assert session.page is BY_NAME["text"]


def test_the_text_pages_task_box_flips_its_own_source():
    """The sample's pick loop: the click lands ``todo:0``, the host reads it
    once, the page's own watch rewrites the sample and the box flips."""
    tui, session = _replay_sized()
    session.show(BY_NAME["text"])
    tui.paint()
    sample = next(block for block in session.body.blocks if isinstance(block, Markdown))
    _click(session, Anchors().cell("text", "sample", row=20, col=0))  # the first task box
    assert sample.chosen is None  # read exactly once
    assert "[x] click a box" in sample.text  # the page flipped its own source
    assert _echo_of(session).text == "echo \u25b8 todo:0"


def test_the_layout_pages_collapsible_folds_on_enter():
    """The page's one ring target: enter flips the fold, and the new state
    is the pick the kit reports (no page name on the host's side)."""
    tui, session = _mounted()
    session.show(BY_NAME["layout"])
    tui.paint()
    fold = next(block for block in session.body.blocks if isinstance(block, Collapsible))
    assert fold.open is True
    assert session._round(Key("enter")) is True
    session._after_round()
    assert fold.open is False  # the body folded away
    assert fold.chosen is None  # read once, by the host's round


def test_the_actions_page_lands_a_click_on_the_echo_and_the_toast():
    """The page's first exhibit, through its own click road: hover, press,
    release -- the pick reports itself on the echo line and in a toast."""
    tui, session = _replay_sized()
    session.show(BY_NAME["actions"])
    tui.paint()
    ship = Anchors().cell("actions", "button", row=0, col=2)
    session._round(MouseEvent("none", button=0, x=ship[0], y=ship[1], kind="motion"))
    _click(session, ship)
    assert _echo_of(session).text == "last pick \u25b8 True"
    tui.paint()
    assert "chosen: True" in tui.screen.output  # the toast the host raised


def test_the_forms_pages_combo_row_opens_its_dropdown():
    """The ComboBox road: the row's Action opens the dropdown over its
    ``Modal``, a typed query narrows it, enter takes the label into the
    field -- and the pick lands on the page's echo line."""
    tui, session = _replay_sized()
    session.show(BY_NAME["forms"])
    tui.paint()
    opening = Anchors().cell("forms", "composer", row=1, col=2)
    _click(session, opening)  # the first click focuses the row ...
    _click(session, opening)  # ... the second runs the row's Action
    panels = session._modal()
    assert panels is not None and panels.is_open  # the page's modal slot carries it
    for char in "log":  # the open field takes the keys; the query narrows the list
        assert session._round(Key(char, char)) is True
    assert panels.combo.input.text == "Dialog"  # "Dia" + "log", one match left
    assert session._round(Key("enter")) is True
    session._after_round()
    assert session._modal() is None  # the dropdown closed with the pick
    assert panels.combo.input.text == "Dialog"  # the row's label written back
    assert _echo_of(session).text == "last pick \u25b8 Dialog"


def test_the_views_pages_table_and_tree_echo_their_reports():
    """The table's pick and mark, and the shell's own ``c-t`` filter, each
    read once by the host and echoed on the page's kit echo line (the filter
    line and the pick line share one row since the views page rides the kit)."""
    from motui import Table, Tree

    tui, session = _mounted()
    session.show(BY_NAME["views"])
    assert session._round(Key("down")) is True
    assert session._round(Key("enter")) is True
    session._after_round()
    echo = _echo_of(session)
    assert echo.text == "last pick \u25b8 1"

    table = next(block for block in session.body.blocks if isinstance(block, Table))
    assert session._round(Key("space", " ")) is True  # the host routes the mark key
    assert 1 in table.marked  # the cursor row the arrows left behind

    tree = next(block for block in session.body.blocks if isinstance(block, Tree))
    assert session._round(Key("c-t")) is True  # the host's own key
    assert [row.text for row in tree.render(60)] == ["\u25be motui", "  \u25b8 kernel"]
    assert echo.text == "echo \u25b8 filter: 'kernel'"


def test_the_modals_pages_dialog_rides_a_modal_its_scrim_and_its_buttons():
    """A trigger opens its dialog over the scrim; ``escape`` cancels with
    ``chosen is None``; the button row's own value is the pick."""
    tui, session = _mounted()
    session.show(BY_NAME["modals"])
    tui.paint()
    body = session.body
    echo = _echo_of(session)
    delete = next(
        block
        for block in body.blocks
        if isinstance(block, Button) and block.label == "Delete project"
    )
    plain_dim = _dims(tui)
    assert delete.activate() is True  # the pick runs the slot's action: the dialog opens
    session._after_round()  # read once: the action raises the dialog on the report
    panels = session._modal()
    assert panels is not None and panels.is_open  # the page's modal field routes it
    dialog = panels.dialog
    assert dialog is not None
    tui.paint()
    assert any("delete the project?" in row.text for row in tui.rows)  # the panel is up
    assert _dims(tui) > plain_dim  # and the scrim reached the frame behind it

    assert session._round(Key("escape")) is True  # the modal owns the keyboard
    assert dialog.chosen is None and not dialog.is_open  # escape cancels with nothing chosen
    session._after_round()
    body.tick()  # the page's beat reads the result once and announces it
    assert echo.text == "last result \u25b8 cancel -- nothing chosen"

    assert delete.activate() is True  # a fresh visit, a fresh dialog
    session._after_round()
    panels = session._modal()
    assert panels is not None and panels.is_open
    dialog = panels.dialog
    assert dialog is not None
    assert session._round(Key("left")) is True  # off the cancel, onto the danger button
    assert session._round(Key("enter")) is True
    assert dialog.chosen is True  # the Delete button's own value
    assert not dialog.is_open
    session._after_round()
    body.tick()
    assert echo.text == "last result \u25b8 chosen: True"


def test_the_modals_pages_palette_exhibit_takes_the_keyboard_and_echoes():
    """The page's ``modal``: the row opens the palette, its query row filters,
    a pick echoes."""
    tui, session = _replay_sized()
    session.show(BY_NAME["modals"])
    tui.paint()
    panels = session.body.modal
    assert panels is not None and not panels.is_open
    opening = Anchors().cell("modals", "palette", row=1, col=2)
    _click(session, opening)  # the first click focuses the row ...
    _click(session, opening)  # ... the second opens the palette
    assert panels.is_open
    for char in "say":  # the palette's own query row takes the keys
        assert session._round(Key(char, char)) is True
    assert panels.input.text == "say"  # the dispatcher's own field seam
    assert session._round(Key("enter")) is True
    session._after_round()
    assert not panels.is_open
    tui.paint()
    assert "say hello" in tui.screen.output  # the toast (and the echo line) report it


def test_the_shell_pages_own_pane_opens_with_the_page_and_c_o_walks_into_it():
    """The page's ``enter`` / ``leave`` hooks: the aside is the page's own
    resource, ``c-o`` is the host's generic pane cycle, and the pane retires
    with the page that opened it."""
    tui, session = _mounted()
    session.show(BY_NAME["shell"])
    tui.paint()
    assert session.aside is not None  # the page's enter hook opened it
    assert tui.frame.focused_pane.id == session.main.id  # ... without taking the focus
    assert session._round(Key("c-o")) is True
    assert tui.frame.focused_pane is session.aside  # c-o cycled onto the page's own pane

    session.show(BY_NAME["text"])  # the visit ends ...
    assert session.aside is None  # ... and the pane retires with the page


def test_the_themes_pickers_pick_reskins_the_shell():
    """The one road to a new skin: the row's action re-skins the shell."""
    tui, session = _mounted()
    session.show(BY_NAME["themes"])
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


def test_the_notes_page_carries_the_manual_the_search_can_address():
    """The manual in the demo: one Markdown block naming every page and both
    headless roads -- and, no ring target on the page, still searchable."""
    tui, session = _mounted()
    session.show(BY_NAME["notes"])
    tui.paint()
    manual = next(block for block in session.body.blocks if isinstance(block, Markdown))
    assert "python -m motui --pages" in manual.text
    assert "copies the range through the terminal's OSC 52" in manual.text
    for page in PAGES:  # the list is the registry's own
        assert f"`{page.name}`" in manual.text

    assert session._round(Key("c-f")) is True
    for char in "headless":
        assert session._round(Key(char, char)) is True
    assert session.find.matches  # the page's own prose is addressable


# --- the shell's roads: search, copy, stats and the tooltip band ----------------------


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

    session.show(BY_NAME["views"])  # a click on the rail lands here too
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


def test_a_drag_release_copies_the_range_and_toasts_the_answer():
    """The copy road: both drag ends are rows of the sample, the gesture hands
    the range to the host, and the host copies it through OSC 52 -- the
    headless screen records the bytes and answers ``True``, so the toast says
    how many lines went out."""
    tui, session = _replay_sized()
    session.show(BY_NAME["text"])
    tui.paint()
    anchors = Anchors()
    start = anchors.cell("text", "sample", row=7, col=4)
    end = anchors.cell("text", "sample", row=10, col=48)
    sample = _component_at(tui, *start)
    assert isinstance(sample, Markdown)  # both ends are the sample's own rows
    assert _component_at(tui, *end) is sample

    session._round(MouseEvent("left", button=0, x=start[0], y=start[1], kind="press"))
    session._round(MouseEvent("motion", button=1, x=end[0], y=end[1], kind="motion"))
    session._round(MouseEvent("left", button=1, x=end[0], y=end[1], kind="release"))
    session._after_round()
    tui.paint()
    assert "Copied 4 lines" in tui.screen.output  # the toast, after the OSC 52 write


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


def _action_button(tui: TUI, session: Session):
    """The actions page's Button, with the cell it occupies on screen."""
    session.show(BY_NAME["actions"])
    tui.paint()
    ship = next(block for block in session.body.blocks if isinstance(block, Button))
    assert ship.hint  # the page handed the leaf its one-line hint
    return ship, _cell_of(tui, "Ship")


def test_the_actions_pages_hints_ride_the_pointer_into_the_tooltips_band():
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


# --- the filter gesture is the page's data, not the host's --------------------------


class _View:
    """A page-local view: a render, and the ``filter`` contract ``c-t`` uses."""

    def __init__(self) -> None:
        self.queries: list = []

    def render(self, width: int) -> list:
        return [Line.from_text("a local view")]

    def filter(self, query) -> None:
        self.queries.append(query)


def _local_page(name: str, view: _View, *, seeded: bool) -> Page:
    """A page the session has never heard of, its exhibit seeded or bare."""
    def build(session) -> PageBody:
        exhibit = Exhibit(session, title=name, blurb="a page the host never heard of",
                          try_text="press c-t", echo_label="echo")
        exhibit.show(exhibit.echo)
        slot = exhibit.show(view)
        if seeded:
            slot.meta = ("alpha", None)  # the page's own canned queries
        return exhibit.build()
    return Page(name, "a synthetic page", build)


def test_the_filter_key_belongs_to_the_page_that_seeds_the_exhibit():
    """``c-t`` is generic: the exhibit whose slot a page seeded answers it, and
    a page that seeds none leaves the key to nobody -- no page's name and no
    widget's class on the host's side, so this page is one it never knew."""
    tui, session = _mounted()
    view = _View()
    session.show(_local_page("synthetic", view, seeded=True))
    assert session._round(Key("c-t")) is True
    assert view.queries == ["alpha"]
    assert session._round(Key("c-t")) is True
    assert view.queries == ["alpha", None]  # the page's cycle, in its own order
    assert _echo_of(session).text == "echo \u25b8 filter: cleared"

    bare = _View()
    session.show(_local_page("bare", bare, seeded=False))
    assert session._round(Key("c-t")) is True  # the key is routed, nobody answers
    assert bare.queries == []


# --- the replay's anchors, resolved off live frames ----------------------------------


def test_the_replays_page_anchors_resolve_on_live_frames():
    """Every coordinate ``motui.demo.script`` scripts is a live page's own cell.

    The replay scripts no screen cell by hand: an anchor is a page, the name
    of one of its exhibits and a cell inside that exhibit's own rows, and
    this test resolves the same helper against frames of its own -- so a page
    that moves an exhibit fails here, not in the piped run.
    """
    tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
    session = Session(tui)
    anchors = Anchors()

    session.show(BY_NAME["text"])
    tui.paint()
    sample = next(
        block
        for block in session.body.blocks
        if isinstance(block, Markdown) and "example.invalid" in block.text
    )
    task_box = anchors.cell("text", "sample", row=20, col=0)  # the first task box
    assert _component_at(tui, *task_box) is sample
    assert sample.click(*_relative(tui, task_box)) is True  # and it takes the click
    assert sample.chosen == "todo:0"
    sample.chosen = None
    # Both ends of the drag are rows of the sample.
    for cell in (anchors.cell("text", "sample", row=7, col=4),
                 anchors.cell("text", "sample", row=10, col=48)):
        assert _component_at(tui, *cell) is sample

    session.show(BY_NAME["modals"])
    tui.paint()
    palette_row = _component_at(tui, *anchors.cell("modals", "palette", row=1, col=2))
    assert isinstance(palette_row, Select)
    assert palette_row.options[0].value == "open the palette"

    session.show(BY_NAME["shell"])
    tui.paint()
    probe = _component_at(tui, *anchors.cell("shell", "probe", row=0, col=1))
    assert probe is next(
        block for block in session.body.blocks
        if isinstance(block, Button) and block.label == "probe one -- a Button"
    )
    assert _component_at(tui, *anchors.aside("shell", row=6)) is not None  # the pane's row
    assert _component_at(tui, *anchors.corner()) is not None  # the toast stack's corner

    session.show(BY_NAME["forms"])
    tui.paint()
    windowed = next(
        block for block in session.body.blocks
        if isinstance(block, Editor) and block.max_rows == 5
    )
    assert _component_at(tui, *anchors.cell("forms", "windowed", row=4, col=0)) is windowed
    composer = _component_at(tui, *anchors.cell("forms", "composer", row=1, col=2))
    assert isinstance(composer, Select)  # the ComboBox exhibit's opening row
    assert composer.options[0].value == "open the composer"

    session.show(BY_NAME["actions"])
    tui.paint()
    assert _component_at(tui, *anchors.cell("actions", "button", row=0, col=2)) is next(
        block for block in session.body.blocks if isinstance(block, Button)
    )


def test_an_anchor_that_no_longer_resolves_fails_with_its_own_name():
    """A stale anchor is an explicit failure, never a neighbouring cell."""
    anchors = Anchors()
    with pytest.raises(AnchorError, match=r"views/tree\[0,0\]"):
        anchors.cell("views", "tree")  # the page has no exhibit by that name
    with pytest.raises(AnchorError, match="nowhere/sample"):
        anchors.cell("nowhere", "sample")
    with pytest.raises(AnchorError, match=r"text/sample\[99,0\]"):
        anchors.cell("text", "sample", row=99)  # the sample paints no such row


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


# --- the dump paths -----------------------------------------------------------------


def test_the_dump_paths_survive_a_legacy_codepage():
    """``--pages`` on a piped cp1252 stdout: the frames are the same text everywhere.

    The CI's Windows leg pipes the dump, and a Western-locale codepage cannot
    encode the scrollbar's ``\\u2591``/``\\u2588`` -- the child must still exit
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
