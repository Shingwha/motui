"""The gallery's protocol wiring: the window title per page, the cursor shape,
the content page's link echo, the action page's tooltip hints, and the search
tier's c-f road.

The host half of the title / cursor-shape story: the library's ansi helpers
and :class:`TUI` methods have their own tests, and these two probes drive the
real gallery session to prove its wiring -- ``show`` titles the window after
the page, and the host loop asks for the focused leaf's shape.  The third
probe drives the content page's inline link the way the pointer does -- a
hit test, a descend, the component's own ``click`` -- and proves the host's
read-once turns that pick into the toast plus the page's echo line.  The last
two drive the action page's hints through the session's own pointer into the
mounted :class:`~motui.chrome.Tooltip`, and back out again on the
1004 blur the host handles with ``pointer.clear()``.  The last three are the
search's host wiring: ``c-f`` opens the tier, its query row takes the keys
the host would otherwise claim, a page switch closes it with the page it
addressed, and a step on a long page moves the window through ``tui.reveal``.
The wave's own four close the file: ``c-g`` mounts and unmounts the dev
``Stats`` overlay through the session's dispatch (the counters ride every
round, a blur included), the ``devtools`` page builds with its toolbox text
and a live hit-test probe, and both self-owned query rows -- the search
tier's and the modal palette's -- own the terminal's cursor shape while
they hold the caret.
The widgets-basic wave's four close it in turn: the ``/choice`` Radio and
the ``/data`` Slider are ring targets whose picks the host reads once, the
``/structure`` Collapsible folds through the ring's ``enter``, and the
footer's ``ShortcutBar`` row rides above the status row on every page.
The widgets-advanced wave's two close the file: the ``/diff`` page mounts
the display-only ``Diff`` with no ring at all, and the ``/data`` List is
the ring's third target, where ``enter`` lands the item under the cursor.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples"))

from motui import (  # noqa: E402
    Button,
    Collapsible,
    HeadlessScreen,
    Key,
    List,
    Markdown,
    MouseEvent,
    Radio,
    Slider,
    Text,
    TUI,
)
from motui.core.ansi import cursor_shape, set_window_title  # noqa: E402
from motui.core.block import descend  # noqa: E402

from gallery.registry import BY_NAME, PAGES  # noqa: E402
from gallery.script import HEADLESS_H, HEADLESS_W, TASK_BOX  # noqa: E402
from gallery.session import Gallery  # noqa: E402


def _mounted() -> tuple[TUI, Gallery]:
    """The gallery mounted on a headless screen, with its output readable."""
    tui = TUI(screen=HeadlessScreen(100, 30), interactive=False)
    return tui, Gallery(tui)


def _cell_of(tui: TUI, needle: str) -> tuple[int, int]:
    """The first on-screen cell whose painted row contains ``needle``.

    Read off the frame the user is looking at (``tui.rows``), the same
    geometry ``hit_test`` resolves -- no hard-coded coordinates.
    """
    for y, row in enumerate(tui.rows):
        col = row.text.find(needle)
        if col >= 0:
            return col, y
    raise AssertionError(f"{needle!r} is not on screen")


def test_show_writes_the_page_title_and_the_focused_fields_cursor_shape():
    tui, gallery = _mounted()
    marker = len(tui.screen.output)
    gallery.show(BY_NAME["input"])  # the page's ring focuses an Editor first
    fresh = tui.screen.output[marker:]
    assert set_window_title("motui gallery \u00b7 input") in fresh
    assert cursor_shape("beam") in fresh  # the Editor declares a bar cursor


def test_a_plain_widget_ring_brings_the_block_shape_back():
    tui, gallery = _mounted()
    gallery.show(BY_NAME["input"])
    marker = len(tui.screen.output)
    gallery.show(BY_NAME["choice"])  # the ring focuses a Select, not a field
    fresh = tui.screen.output[marker:]
    assert set_window_title("motui gallery \u00b7 choice") in fresh
    assert cursor_shape("block") in fresh
    assert cursor_shape("beam") not in fresh  # and no stale shape is repeated


def test_a_click_on_the_content_pages_link_lands_a_toast_and_the_echo_line():
    tui, gallery = _mounted()
    gallery.show(BY_NAME["content"])
    tui.paint()
    sample = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Markdown) and "example.invalid" in block.text
    )
    assert sample.chosen is None
    x, y = _cell_of(tui, "a link")  # the sample's prose, link label included
    cell = tui.hit_test(x + 2, y)  # the label starts two cells in: "a link"
    assert cell is not None
    component, row, col = descend(cell.block.component, cell.row, cell.col)
    assert component is sample  # the click resolves to the page's own sample
    assert component.click(row, col) is True  # the pointer's own dispatch
    assert component.chosen == "https://example.invalid"
    gallery._read_picks()  # the host's one read per round
    assert component.chosen is None  # read once, reset
    tui.paint()
    fresh = tui.screen.output
    assert "https://example.invalid" in fresh  # the toast reports the pick
    echo = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Markdown) and block is not sample and "echo" in block.text
    )
    assert [row.text for row in echo.render(80)] == [
        "echo \u25b8 chosen: 'https://example.invalid'"
    ]


def _action_button(tui: TUI, gallery: Gallery):
    """The action page's Button, with the cell it occupies on screen."""
    gallery.show(BY_NAME["action"])
    tui.paint()
    ship = next(block for block in gallery.body.blocks if isinstance(block, Button))
    assert ship.hint  # the page handed the leaf its one-line hint
    return ship, _cell_of(tui, "Ship")


def test_the_action_pages_hints_ride_the_pointer_into_the_tooltips_band():
    """The band's whole road: the page's ``hint``, the session's pointer, the overlay."""
    tui, gallery = _mounted()
    ship, (x, y) = _action_button(tui, gallery)
    gallery.pointer.handle(MouseEvent("none", button=0, x=x, y=y, kind="motion"))
    tui.paint()
    assert ship.hover is True
    assert ship.hint in tui.rows[y + 1].text  # the band sits under the pointer


def test_focus_out_scrubs_the_hover_and_takes_the_band_with_it():
    """DECSET 1004's blur: the host clears the pointer, so the band goes too."""
    tui, gallery = _mounted()
    ship, (x, y) = _action_button(tui, gallery)
    gallery.pointer.handle(MouseEvent("none", button=0, x=x, y=y, kind="motion"))
    tui.paint()
    assert ship.hint in tui.rows[y + 1].text
    assert gallery._round(Key("focus_out")) is True  # the host owns the blur
    tui.paint()
    assert ship.hover is False and gallery.pointer.position is None
    assert ship.hint not in tui.rows[y + 1].text


def test_c_f_opens_the_search_row_and_the_row_owns_the_keyboard():
    """The host wiring: ``c-f`` opens the tier, and while its row is open the
    host's own keys give way -- ``q`` searches, ``c-n``/``c-p`` do not move."""
    tui, gallery = _mounted()
    gallery.show(BY_NAME["content"])
    page = gallery.page
    assert gallery._round(Key("c-f")) is True
    assert gallery.find.is_open
    for char in "text":  # a printable typed at the shell searches
        assert gallery._round(Key(char, char)) is True
    assert gallery.find.query == "text" and gallery.find.matches

    assert gallery._round(Key("c-n")) is True  # the host's keys yield ...
    assert gallery._round(Key("c-p")) is True
    assert gallery._round(Key("tab")) is True
    assert gallery.page is page  # ... so the page did not move
    assert gallery._round(Key("q", "q")) is True  # and q is a query character
    assert gallery.find.query == "textq"

    assert gallery._round(Key("escape")) is True  # the row's own dismiss key
    assert not gallery.find.is_open
    assert gallery._round(Key("q", "q")) is False  # closed: q quits again


def test_a_page_switch_closes_the_search_with_the_page_it_addressed():
    tui, gallery = _mounted()
    gallery.show(BY_NAME["content"])
    gallery._round(Key("c-f"))
    for char in "text":
        gallery._round(Key(char, char))
    assert gallery.find.matches

    gallery.show(BY_NAME["data"])  # a click on the tab strip lands here too
    assert not gallery.find.is_open
    tui.paint()
    assert not any("find \u276e" in row.text for row in tui.rows)


def test_a_step_on_a_long_page_reveals_the_current_match():
    """The reveal road through the session: the window follows ``enter``."""
    tui, gallery = _mounted()
    gallery.show(BY_NAME["streaming"])  # the 346-line fixture
    tui.paint()
    assert tui.viewport.offset == 0  # the page opens at its top
    gallery._round(Key("c-f"))
    for char in "markdown":
        gallery._round(Key(char, char))
    assert gallery.find.matches

    for _ in range(len(gallery.find.matches)):
        if tui.viewport.offset:
            break
        assert gallery._round(Key("enter")) is True
    assert tui.viewport.offset > 0  # the window moved to the current match

    tui.paint()  # the next frame lays out at the revealed offset
    bid, row, _, _ = gallery.find.matches[gallery.find.index]
    owners = tui.frame.pane_layout("primary").row_blocks
    assert (bid, row) in [owner for owner in owners if owner is not None]


def test_c_g_mounts_and_unmounts_the_dev_stats_overlay():
    """The host wiring: ``c-g`` mounts the box, it counts rounds, ``c-g`` unmounts.

    The counting feed sits before every tier and consumes nothing: a round
    the host's own keys claim (``tab``) and a ``focus_out`` that still runs
    the host's cleanup are both counted, and the second ``c-g`` hands the
    corner back to the page.
    """
    tui, gallery = _mounted()
    assert gallery.stats is None
    assert gallery._round(Key("c-g")) is True
    stats = gallery.stats
    assert stats is not None and stats in tui.frame.overlays
    tui.paint()
    assert "frames " in tui.rows[0].text  # the box rides the top-right corner

    counted = stats.events
    assert gallery._round(Key("tab")) is True  # the ring's own door, still counted
    assert stats.events == counted + 1
    x, y = _cell_of(tui, "/content")
    assert gallery._round(MouseEvent("none", button=0, x=x, y=y, kind="motion")) is True
    assert gallery.pointer.position == (x, y)
    assert gallery._round(Key("focus_out")) is True  # the blur is the host's
    assert gallery.pointer.position is None  # ... and still clears the hover
    assert stats.events == counted + 3

    assert gallery._round(Key("c-g")) is True
    assert gallery.stats is None and stats not in tui.frame.overlays
    tui.paint()
    assert "frames " not in tui.rows[0].text


def _page_text(tui: TUI, gallery: Gallery) -> str:
    """Every row of the mounted page's blocks (the whole page, viewport or not).

    The screen shows what fits; this renders each block at the pane's own
    width, so an assertion about the page's *content* does not depend on how
    much of it the 30-row test screen happens to hold.
    """
    region = tui.frame.region("primary")
    width = region.width if region is not None else tui.screen.width
    return "\n".join(
        row.text for block in gallery.body.blocks for row in block.render(width)
    )


def test_the_devtools_page_shows_the_toolbox_and_a_live_hit_probe():
    """Page 14 of 14: the tools in prose, a live event row, and the probe's own walk."""
    tui, gallery = _mounted()
    assert len(PAGES) == 14 and BY_NAME["devtools"].nav == "dev"
    gallery.show(BY_NAME["devtools"])
    tui.paint()
    text = _page_text(tui, gallery)
    assert "developer tools" in text
    assert "tools/golden.py --check" in text
    assert "RecordingKeys" not in text and "ReplayKeys" not in text  # the recorder is gone
    assert "test_decoder_fuzz.py" in text and "test_render_invariants.py" in text
    assert "hit (pointer cell): -- move the pointer" in text  # the placeholder
    assert "c-g mounts the overlay that counts them" in text  # the event row, off

    # The probe resolves the pointer's own cell, once the page's beat runs --
    # and the refreshed row is on the screen, not merely in the block.
    x, y = _cell_of(tui, "probe one -- a Button")
    gallery.pointer.handle(MouseEvent("none", button=0, x=x, y=y, kind="motion"))
    gallery.body.tick()  # the beat the session's PAGE_TICK runs
    tui.paint()
    assert f"hit ({x}, {y}): Button" in "\n".join(row.text for row in tui.rows)

    # And the event row switches on the overlay: off -> counted.  The press
    # that mounts the box is not counted (no box existed when it arrived);
    # the round after it is.
    gallery._round(Key("c-g"))
    gallery._round(Key("tab"))
    gallery.body.tick()
    tui.paint()
    text = _page_text(tui, gallery)
    assert "events: 1 counted, last tab" in text


def test_the_search_query_row_owns_the_cursor_shape_while_the_tier_is_open():
    """The W4 leftover: with the query row open the terminal shape is its beam.

    The ring's leaf is not where the caret is while the search is open, so
    the host reads the query row's own ``cursor_shape`` -- and on the way
    out the ring's leaf has the terminal back.
    """
    tui, gallery = _mounted()
    gallery.show(BY_NAME["data"])  # a Table ring: the shape reads block
    marker = len(tui.screen.output)
    assert gallery._round(Key("c-f")) is True
    gallery._after_round()  # the loop's own work, run by hand
    assert gallery.find.is_open
    assert cursor_shape("beam") in tui.screen.output[marker:]
    marker = len(tui.screen.output)
    assert gallery._round(Key("escape")) is True
    gallery._after_round()
    assert not gallery.find.is_open
    assert cursor_shape("block") in tui.screen.output[marker:]


def test_the_palette_query_row_owns_the_cursor_shape_while_the_panel_is_open():
    """The same rule for the modal panel (the search fix's sibling).

    ``Palette`` carries its own query ``Input``, so while the panel is open
    its row holds the caret and the terminal must show the beam; escape
    closes it and the ring's leaf has the shape back.
    """
    tui, gallery = _mounted()
    gallery.show(BY_NAME["data"])  # a Table ring: the shape reads block
    marker = len(tui.screen.output)
    assert gallery._round(Key("/", "/")) is True
    gallery._after_round()
    assert gallery.palette.is_open
    assert cursor_shape("beam") in tui.screen.output[marker:]
    marker = len(tui.screen.output)
    assert gallery._round(Key("escape")) is True
    gallery._after_round()
    assert not gallery.palette.is_open
    assert cursor_shape("block") in tui.screen.output[marker:]


# --- the widgets-basic wave's four, on the real pages --------------------------------


def test_the_choice_page_rings_its_radio_and_a_step_lands_the_pick():
    """``/choice`` mounts a Radio as a ring target: a step under the focus
    already writes ``chosen``, and the host's one read turns it into the
    toast plus the page's echo line."""
    tui, gallery = _mounted()
    gallery.show(BY_NAME["choice"])
    tui.paint()
    ring = gallery.body.focus
    radio = next(target for target in ring.targets if isinstance(target, Radio))
    assert gallery._round(Key("tab")) is True  # off the menu onto the radio
    assert ring.focused is radio
    assert gallery._round(Key("down")) is True
    assert (radio.index, radio.chosen) == (2, "thorough")
    gallery._read_picks()
    assert radio.chosen is None  # the host read it once
    tui.paint()
    assert "chosen: 'thorough'" in tui.screen.output
    echo = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Text) and block.text.startswith("last pick:")
    )
    assert echo.text == "last pick: 'thorough'"


def test_the_data_page_rings_its_slider_and_activate_confirms_the_value():
    tui, gallery = _mounted()
    gallery.show(BY_NAME["data"])
    ring = gallery.body.focus
    slider = next(target for target in ring.targets if isinstance(target, Slider))
    assert gallery._round(Key("tab")) is True
    assert ring.focused is slider
    assert gallery._round(Key("right")) is True  # a step: no pick, a cleared one
    assert slider.value == 5 and slider.chosen is None
    assert gallery._round(Key("enter")) is True
    assert slider.chosen == 5
    gallery._read_picks()
    assert slider.chosen is None
    tui.paint()
    assert "chosen: 5" in tui.screen.output


def test_the_structure_page_rings_its_collapsible_and_enter_folds_it():
    tui, gallery = _mounted()
    gallery.show(BY_NAME["structure"])
    tui.paint()
    ring = gallery.body.focus
    (section,) = ring.targets
    assert isinstance(section, Collapsible) and section.open is True
    assert len(section.render(90)) > 1  # the body is showing
    assert gallery._round(Key("enter")) is True
    assert section.open is False and section.chosen is False
    gallery._read_picks()
    assert section.chosen is None
    tui.paint()
    assert "chosen: False" in tui.screen.output
    assert len(section.render(90)) == 1  # one title row: the body is folded away


def test_the_footer_carries_the_shortcut_bar_on_every_page():
    """The shell's key hints: one row above the status line, on any page."""
    tui, gallery = _mounted()
    for page in (BY_NAME["overview"], BY_NAME["data"], BY_NAME["devtools"]):
        gallery.show(page)
        tui.paint()
        bar = tui.rows[-2].text
        assert "c-n / c-p pages" in bar and "/ palette" in bar and "c-c quit" in bar
        assert "0.0 fps" in tui.rows[-1].text  # the status row stays the footer's last


# --- the widgets-advanced wave's two, on the real pages ------------------------------


def test_the_diff_page_renders_the_hunks_and_mounts_no_ring():
    """``/diff``: the two versions in rows, and nothing to tab onto."""
    tui, gallery = _mounted()
    assert len(PAGES) == 14 and BY_NAME["diff"].nav == "diff"
    gallery.show(BY_NAME["diff"])
    tui.paint()
    assert gallery.body.focus is None  # display-only: the page is mouse-free too
    text = _page_text(tui, gallery)
    # The unified rows: the modified measure line as its `-`/`+` pair, the
    # inserted comment, the elision row between the two hunks, and the
    # second, context=0 exhibit.
    assert "-    return wcswidth(text)" in text
    assert "+    return sum(width for _start, _stop, width in cell_spans(text))" in text
    assert "+    # The floor rule lives in the boundary resolver." in text
    assert "\n\u2026\n" in text  # the elision row between the hunks
    # Two hunks in the default exhibit (the first two changes merge, the
    # ``fit`` change follows an elision) and four tight ones under context=0.
    assert text.count("@@ -") == 6
    assert "LCS_LIMIT" in text  # the bounded walk is on the page


def test_the_data_page_rings_its_list_and_enter_lands_the_item():
    """``/data``: the List is the ring's third target; a pick lands the item."""
    tui, gallery = _mounted()
    gallery.show(BY_NAME["data"])
    ring = gallery.body.focus
    listing = next(target for target in ring.targets if isinstance(target, List))
    assert gallery._round(Key("tab")) is True  # the table -> the slider
    assert gallery._round(Key("tab")) is True  # the slider -> the list
    assert ring.focused is listing
    assert gallery._round(Key("down")) is True
    assert gallery._round(Key("down")) is True
    assert listing.index == 2 and listing.chosen is None  # a step is no pick
    assert gallery._round(Key("enter")) is True
    assert listing.chosen == "Checkbox"
    gallery._read_picks()
    assert listing.chosen is None  # the host read it once
    tui.paint()
    assert "chosen: 'Checkbox'" in tui.screen.output
    echo = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Text) and block.text.startswith("last pick:")
    )
    assert echo.text == "last pick: 'Checkbox'"
    # The window is on display: six item rows and one "down" counter row,
    # the marker riding the cursor two rows in.
    rows = listing.render(90)
    assert len(rows) == 7
    assert rows[0].text == "  Autocomplete" and rows[2].text == "\u25b8 Checkbox"
    assert rows[-1].text == "\u2193 22 more"



# --- the widgets-deepening wave's three, on the real pages ---------------------------


def test_the_data_page_sorts_on_the_sorters_pick():
    """``/data``: the sorter is the ring's fourth target; enter runs ``sort_by``."""
    from motui import Select, Table

    tui, gallery = _mounted()
    gallery.show(BY_NAME["data"])
    tui.paint()
    ring = gallery.body.focus
    table = next(target for target in ring.targets if isinstance(target, Table))
    sorter = next(target for target in ring.targets if isinstance(target, Select))
    assert ring.targets[-1] is sorter  # appended: the wave-7 tab walk is untouched
    assert gallery._round(Key("tab")) is True  # the table -> the slider
    assert gallery._round(Key("tab")) is True  # the slider -> the list
    assert gallery._round(Key("tab")) is True  # the list -> the sorter
    assert ring.focused is sorter
    assert gallery._round(Key("down")) is True
    assert gallery._round(Key("down")) is True  # "state"
    assert gallery._round(Key("enter")) is True
    assert sorter.chosen is not None and sorter.chosen.value == "sort:2"
    gallery._read_picks()  # the host's one read; the page's note runs the pick
    assert sorter.chosen is None
    # The table re-ordered by the state column's rendered text: below, live,
    # streams, you are here.
    assert [row[0] for row in table.rows] == ["Divider", "Markdown", "Text", "Table"]
    assert table.selected == ["Text", "verbatim rows, word-wrapped", ("streams", __import__("motui").SUCCESS)]
    tui.paint()
    assert "chosen: 'sort:2'" in tui.screen.output
    echo = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Text) and block.text.startswith("last pick:")
    )
    assert echo.text == "last pick: 'sort:2'"
    # The row cursor followed its record into the new order: the band sits
    # on the same record, now the third data row.
    rendered = table.render(90)
    banded = [
        row.text
        for row in rendered
        if any(seg.style.reverse for seg in row.segments)
    ]
    assert banded == ["\u2502 Text      \u2502 verbatim rows, word-wrapped        \u2502      streams \u2502"]


def test_the_navigation_page_cycles_the_trees_filter_on_c_t():
    """``/navigation``: the host's ``c-t`` applies the next canned query."""
    from motui import Tree

    tui, gallery = _mounted()
    gallery.show(BY_NAME["navigation"])
    tui.paint()
    tree = next(block for block in gallery.body.blocks if isinstance(block, Tree))
    echo = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Text) and block.text.startswith("filter:")
    )
    before = [row.text for row in tree.render(90)]
    assert before[0] == "\u25be motui" and len(before) == 7  # the whole tree
    # Press one: the canned query "core" prunes the tree to its chain; the
    # page's echo line names it (the host reported the query).
    assert gallery._round(Key("c-t")) is True
    assert [row.text for row in tree.render(90)] == ["\u25be motui", "  \u25b8 core"]
    assert echo.text == "filter: 'core'"
    tui.paint()
    assert "filter: 'core'" in tui.screen.output
    # Press two cycles on: "lines" keeps the deeper chain open (the hit and
    # every ancestor above it); a page with no tree has nothing to consume.
    assert gallery._round(Key("c-t")) is True
    assert [row.text for row in tree.render(90)] == [
        "\u25be motui",
        "  \u25be core",
        "      lines",
    ]
    assert echo.text == "filter: 'lines'"
    # The cycle is the host's own state and a page switch resets it with the
    # fresh tree: back on the page, the first press is "core" again.
    gallery.show(BY_NAME["data"])
    gallery._round(Key("c-t"))  # no tree on this page: the key does nothing
    gallery.show(BY_NAME["navigation"])
    tree = next(block for block in gallery.body.blocks if isinstance(block, Tree))
    assert gallery._round(Key("c-t")) is True
    assert [row.text for row in tree.render(90)] == ["\u25be motui", "  \u25b8 core"]


def test_the_content_pages_task_box_runs_the_whole_host_loop():
    """A click on the sample's box -> ``chosen`` -> the page rewrites its text."""
    from motui import Markdown

    tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
    gallery = Gallery(tui)  # the replay's own geometry: where TASK_BOX lives
    gallery.show(BY_NAME["content"])
    tui.paint()
    sample = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Markdown) and "example.invalid" in block.text
    )
    # The replay's anchor is this box: the frame the user sees resolves the
    # same cell (so a page that moves the box fails here, not in the replay).
    x, y = _cell_of(tui, "\u2610 click a box")
    assert (x, y) == TASK_BOX
    assert sample.text.count("- [ ] click") == 1  # the source, before the pick
    cell = tui.hit_test(x, y)
    assert cell is not None
    component, row, col = descend(cell.block.component, cell.row, cell.col)
    assert component is sample
    assert component.click(row, col) is True  # the pointer's own dispatch
    assert component.chosen == "todo:0"
    gallery._read_picks()  # the host's one read runs the page's note
    assert component.chosen is None
    # The page's note rewrote the sample's own text and the frame shows the
    # checked box; the echo line reports the pick it was handed.
    assert "- [x] click" in sample.text and "- [ ] click" not in sample.text
    tui.paint()
    assert "\u2611 click a box" in "\n".join(row.text for row in tui.rows)
    echo = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Markdown) and "echo" in block.text
    )
    assert echo.text == "echo \u25b8 chosen: 'todo:0'"
    # Clicking the same box again runs the loop the other way: the payload is
    # the same ordinal, the flip goes back, and the frame shows the open box.
    x, y = _cell_of(tui, "\u2611 click a box")
    cell = tui.hit_test(x, y)
    component, row, col = descend(cell.block.component, cell.row, cell.col)
    assert component.click(row, col) is True and component.chosen == "todo:0"
    gallery._read_picks()
    assert "- [ ] click" in sample.text and "- [x] click" not in sample.text
    tui.paint()
    assert "\u2610 click a box" in "\n".join(row.text for row in tui.rows)


def test_c_y_copies_the_pages_first_fence_and_toasts():
    """``c-y``: ``Markdown.fences()`` -> ``screen.copy`` (the OSC 52 bytes)."""
    from motui import Markdown
    from motui.core.ansi import copy_clipboard

    tui, gallery = _mounted()
    gallery.show(BY_NAME["content"])
    tui.paint()
    sample = next(
        block
        for block in gallery.body.blocks
        if isinstance(block, Markdown) and "example.invalid" in block.text
    )
    lang, code = sample.fences()[0]
    assert lang == "python" and code.startswith("def hello")
    marker = len(tui.screen.output)
    gallery._round(Key("c-y"))
    tui.paint()  # the toast is a painted band: it lands with the next frame
    fresh = tui.screen.output[marker:]
    assert copy_clipboard(code) in fresh  # the clipboard write is recorded
    assert "copied the python fence (2 lines)" in fresh  # the toast names it
    # A page with no fence consumes nothing and copies nothing (a fresh
    # session, so no earlier toast is on the stack to confuse the read).
    plain, plain_gallery = _mounted()
    plain_gallery.show(BY_NAME["data"])
    plain.paint()
    marker = len(plain.screen.output)
    plain_gallery._round(Key("c-y"))
    plain.paint()
    assert copy_clipboard(code) not in plain.screen.output[marker:]
    assert "copied the" not in plain.screen.output[marker:]
