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
mounted :class:`~mocode_tui.chrome.Tooltip`, and back out again on the
1004 blur the host handles with ``pointer.clear()``.  The last three are the
search's host wiring: ``c-f`` opens the tier, its query row takes the keys
the host would otherwise claim, a page switch closes it with the page it
addressed, and a step on a long page moves the window through ``tui.reveal``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples"))

from mocode_tui import Button, HeadlessScreen, Key, Markdown, MouseEvent, TUI  # noqa: E402
from mocode_tui.core.ansi import cursor_shape, set_window_title  # noqa: E402
from mocode_tui.core.block import descend  # noqa: E402

from gallery.registry import BY_NAME  # noqa: E402
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
    assert set_window_title("mocode-tui gallery \u00b7 input") in fresh
    assert cursor_shape("beam") in fresh  # the Editor declares a bar cursor


def test_a_plain_widget_ring_brings_the_block_shape_back():
    tui, gallery = _mounted()
    gallery.show(BY_NAME["input"])
    marker = len(tui.screen.output)
    gallery.show(BY_NAME["choice"])  # the ring focuses a Select, not a field
    fresh = tui.screen.output[marker:]
    assert set_window_title("mocode-tui gallery \u00b7 choice") in fresh
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

