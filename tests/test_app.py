"""The TUI driver and the headless testing helpers.

``read_key()`` absorbs the scroll keys and hands the rest back; ``hit_test``
resolves 0-based reports into blocks; ``set_selection`` overlays the one
document-space selection between layout and paint; ``run`` brackets
enter/leave.
"""

import asyncio
import io
from dataclasses import replace

import pytest

from _doubles import Rows, key, many

from mocode_tui import app as app_module
from mocode_tui.app import TUI
from mocode_tui.core.ansi import enter_alt_screen, leave_alt_screen
from mocode_tui.core.block import BlockState, Document
from mocode_tui.core.events import Key, MouseEvent, Paste, ScriptedKeys
from mocode_tui.core.frame import Pane, Rect
from mocode_tui.core.lines import Line
from mocode_tui.core.screen import HeadlessScreen, TerminalScreen
from mocode_tui.core.selection import Selection
from mocode_tui.core.style import MUTED, SELECTION, Style
from mocode_tui.core.lines import Text
from mocode_tui.core.theme import DEFAULT_THEME, Theme
from mocode_tui.core.viewport import MORE_BELOW, Viewport
from mocode_tui.testing import headless_tui, snapshot


def _piped_tui() -> tuple[TUI, io.StringIO]:
    """A TUI on a non-live (piped) screen the test itself holds."""
    stream = io.StringIO()
    return TUI(screen=TerminalScreen(stream)), stream


def _enter_leave(tui: TUI) -> tuple[int, int]:
    output = tui.screen.output
    return output.find(enter_alt_screen()), output.find(leave_alt_screen())


# --- document facade -----------------------------------------------------------


def test_the_facade_addresses_prints_and_pins_blocks():
    tui = headless_tui()
    first = tui.add(Text("one"))
    second = tui.add(Text("footer"), pin="bottom")
    assert first.id == "b0" and second.pin == "bottom"
    assert tui.get("b0") is first
    block = tui.system("hello")
    assert isinstance(block.component, Text)
    assert block.component.text == "hello" and block.component.style == MUTED
    assert block.state is BlockState.OPEN and tui.get(block.id) is block
    assert tui.remove("b0") is first and len(tui.document) == 2
    with pytest.raises(KeyError):
        tui.get("b0")


def test_mutations_invalidate_the_frame():
    tui = headless_tui(80, 10)
    tui.paint()
    painted = len(tui.screen.output)
    tui.add(Text("x"))
    tui.paint()
    assert len(tui.screen.output) > painted  # the added block repainted
    painted = len(tui.screen.output)
    tui.remove("b0")
    tui.paint()
    assert len(tui.screen.output) > painted  # the removal repainted too


# --- scroll facade -------------------------------------------------------------


def test_scroll_facade_moves_the_window():
    tui = headless_tui(80, 10)
    tui.add(Rows(*many(30)))
    tui.paint()
    assert [row.text for row in tui.rows] == many(30)[20:]
    tui.scroll_up(3)
    tui.paint()
    assert [row.text for row in tui.rows] == [*many(30)[17:26], MORE_BELOW.text]
    tui.scroll_to_bottom()
    tui.paint()
    assert len(tui.rows) == 10
    assert [row.text for row in tui.rows] == many(30)[20:]


# --- read_key ------------------------------------------------------------------


async def test_read_key_absorbs_the_scroll_keys_and_returns_the_rest():
    # The wheel scrolls the table's three rows, a page key one; every other
    # event -- keys and pastes alike -- comes back untouched, then EOF.
    tui = headless_tui(
        80, 10,
        script=[
            MouseEvent("wheel_up", button=0, x=0, y=0),
            key("page_up"),
            key("a", "a"),
            Paste("p"),
            None,
        ],
    )
    tui.add(Rows(*many(30)))
    tui.paint()
    assert [row.text for row in tui.rows] == many(30)[20:]  # stuck to the bottom

    assert await tui.read_key() == key("a", "a")  # both scroll events absorbed
    assert await tui.read_key() == Paste("p")  # a paste is never a scroll key
    tui.paint()  # the wheel (-3) plus the page key (-1) moved four rows up
    assert [row.text for row in tui.rows] == [*many(30)[16:25], MORE_BELOW.text]
    assert await tui.read_key() is None  # EOF


async def test_scroll_keys_table_is_customizable():
    tui = headless_tui(
        80,
        10,
        script=[MouseEvent("wheel_down", button=1, x=0, y=0), MouseEvent("wheel_up"), None],
    )
    tui.add(Rows(*many(30)))
    tui.paint()
    tui.scroll_up(5)
    tui.paint()

    tui.scroll_keys["wheel_down"] = 1  # one row per notch, not the default three
    del tui.scroll_keys["wheel_up"]  # unbound: the event comes back untouched

    # The rebound wheel_down is absorbed on its way through (one row, not
    # three); the unbound wheel_up is handed back to the caller.
    assert await tui.read_key() == MouseEvent("wheel_up")
    tui.paint()
    assert [row.text for row in tui.rows] == [*many(30)[16:25], MORE_BELOW.text]
    assert await tui.read_key() is None  # EOF


async def test_read_key_escape_hatch_reads_the_raw_source():
    tui = headless_tui(80, 10, script=[key("page_up")])
    assert await tui.keys.read() == key("page_up")  # no interception here


async def test_read_key_hands_button_presses_to_the_host_for_hit_testing():
    tui = headless_tui(
        80, 6, script=[MouseEvent("left", button=0, x=0, y=0), key("a", "a"), None]
    )
    body = tui.add(Rows(*many(10)))
    tui.paint()
    event = await tui.read_key()  # a press is not in scroll_keys: it comes back
    assert event == MouseEvent("left", button=0, x=0, y=0)
    hit = tui.hit_test(event.x, event.y)  # the host resolves it against the frame
    assert hit is not None and hit.block is body and hit.row == 4 and hit.col == 0
    assert await tui.read_key() == key("a", "a")
    assert await tui.read_key() is None


async def test_read_key_returns_none_without_a_source_or_on_a_non_live_screen():
    assert await TUI(screen=HeadlessScreen()).read_key() is None  # no source at all
    # A non-live screen never answers, even with a source attached.
    tui = TUI(screen=TerminalScreen(io.StringIO()), keys=ScriptedKeys([key("a", "a")]))
    assert await tui.read_key() is None


# --- the split and focus surface ------------------------------------------------


def _split_tui() -> tuple:
    """A transcript | preview split: the first pane keeps the document."""
    tui = headless_tui(40, 6)
    left, right = tui.split("vertical", ratios=(2, 1))
    left.document.add(Rows("transcript"))
    right.document.add(Rows("preview"))
    return tui, left, right


def test_split_returns_the_two_panes_and_leaves_the_transcript_in_the_first():
    tui, left, right = _split_tui()
    assert [pane.id for pane in tui.frame.panes] == ["primary", "primary-1"]
    assert left.document is tui.document  # the split pane kept the document
    assert right.document is not tui.document  # a fresh, empty one for the preview
    assert [block.id for block in right.document.blocks()] == ["b0"]
    assert tui.frame.focused_pane is left  # a split leaves focus where it was
    tui.paint()
    assert [row.text for row in tui.rows] == [
        "transcript" + " " * 16 + "preview" + " " * 7,
    ] + [" " * 40] * 5
    assert left.rect.width == 26 and right.rect.x == 26  # 26 + the divider, then 14
    assert tui.viewport is left.viewport and tui._focused_viewport() is left.viewport


@pytest.mark.parametrize(
    ("orientation", "edge"), [("vertical", "right"), ("horizontal", "bottom")]
)
def test_the_divider_paints_the_accent_beside_its_focus(orientation: str, edge: str):
    """The tmux convention (D4): 1-cell chrome on the pane before the gap, in
    the theme's accent beside the focussed pane and its border otherwise."""
    theme = DEFAULT_THEME
    tui = headless_tui(40, 12)
    panes = tui.split(orientation, ratios=(1, 1, 1))
    for index, pane in enumerate(panes):
        pane.document.add(Rows(f"pane {index}"))
    tui.paint()
    assert tui.frame.focused_pane is panes[0]
    assert panes[-1].chrome == ()  # the last pane holds no divider of its own
    assert all(
        (pane.chrome[0].edge, pane.chrome[0].size) == (edge, 1) for pane in panes[:-1]
    )

    def styles(pane: Pane) -> list[Style]:
        strip = pane.chrome[0].paint(tui.frame.pane_layout(pane.id), 4)
        return [segment.style for row in strip for segment in row.segments]

    first, second = styles(panes[0]), styles(panes[1])
    assert first == [theme.accent] * len(first)  # the divider beside the focus
    assert second == [theme.border] * len(second)  # and the one that is not
    panes[2].focus()  # the focus moves beside the second divider: it flips
    assert styles(panes[1]) == [theme.accent] * len(second)
    assert styles(panes[0]) == [theme.border] * len(first)


def test_the_driver_theme_is_its_own_and_styles_the_divider():
    """``TUI.theme`` defaults to the toolkit theme, and it is the divider's:
    the split divider reads ``accent`` beside the focused pane and
    ``border`` otherwise, from the driver's own theme."""
    theme = replace(DEFAULT_THEME, accent=Style(fg="#ff8800"))
    tui = TUI(screen=HeadlessScreen(40, 6), interactive=False, theme=theme)
    assert tui.theme is theme
    assert TUI(screen=HeadlessScreen(40, 6), interactive=False).theme is DEFAULT_THEME

    panes = tui.split("vertical", ratios=(1, 1, 1))
    tui.paint()

    def styles(pane: Pane) -> list[Style]:
        strip = pane.chrome[0].paint(tui.frame.pane_layout(pane.id), 4)
        return [segment.style for row in strip for segment in row.segments]

    assert styles(panes[0]) == [theme.accent] * 4  # beside the focus
    assert styles(panes[1]) == [theme.border] * 4  # and the one that is not
    panes[2].focus()  # the focus moves beside the second divider: it flips
    assert styles(panes[0]) == [theme.border] * 4
    assert styles(panes[1]) == [theme.accent] * 4


def test_a_split_without_a_separator_leaves_the_panes_abutting():
    tui = headless_tui(40, 6)
    left, right = tui.split("vertical", ratios=(1, 1), separator=False)
    assert left.chrome == () and right.chrome == ()
    left.document.add(Rows("L"))
    right.document.add(Rows("R"))
    tui.paint()
    assert [row.text for row in tui.rows] == [
        "L" + " " * 19 + "R" + " " * 19,
    ] + [" " * 40] * 5


def test_a_close_drops_the_driver_divider_and_retakes_the_cells():
    """The themed divider is chrome of the pane before the gap: the close
    strips it by its mark, the transcript takes the whole pane area, and
    the focus lands back on it -- painted without a size change, so the
    driver's same-size retile cache is no mask for the tree change."""
    tui, left, right = _split_tui()
    tui.paint()  # the tiling cache now holds this rectangle
    assert tui.rows[0].text.startswith("transcript")
    right.focus()
    right.close()
    tui.paint()
    assert [pane.id for pane in tui.frame.panes] == ["primary"]
    assert tui.frame.pane("primary").chrome == ()  # the divider went
    assert tui.frame.pane("primary-1") is None
    assert tui.frame.focused_pane is tui.frame.pane("primary")
    # one pane again, the whole pane area its own: the single-pane
    # pass-through composes to the transcript's own layout
    assert [row.text for row in tui.rows] == ["transcript"] + [""] * 5
    assert left.document is tui.document  # the transcript's document rode the collapse
    assert tui._focused_viewport() is tui.viewport  # and so did the resident window


def test_a_press_focuses_the_pane_under_it_and_a_wheel_does_not():
    tui, left, right = _split_tui()
    tui.paint()
    assert tui.frame.focused_pane is left
    tui.focus_policy(tui, MouseEvent("left", button=0, x=30, y=0))
    assert tui.frame.focused_pane is right
    tui.focus_policy(tui, MouseEvent("wheel_down", button=1, x=4, y=0))
    assert tui.frame.focused_pane is right  # a notch scrolls, it never focuses
    tui.focus_policy(tui, MouseEvent("left", button=0, x=4, y=0))
    assert tui.frame.focused_pane is left


def test_the_focus_policy_hook_is_replaceable():
    tui, left, _ = _split_tui()
    seen: list[object] = []
    press = MouseEvent("left", button=0, x=30, y=0)
    tui.focus_policy = lambda app, event: seen.append(event) or None
    tui.focus_policy(tui, press)
    assert tui.frame.focused_pane is left and seen == [press]  # it decided nothing

    def always_first(app: TUI, event: Key | Paste | MouseEvent) -> Pane | None:
        return app.frame.panes[0]

    tui.focus_policy = always_first
    tui.focus_policy(tui, key("a", "a"))
    assert tui.frame.focused_pane is left


def test_the_scroll_keys_route_to_the_focused_pane():
    tui, left, right = _split_tui()
    left.document.add(Rows(*many(40)))
    right.document.add(Rows(*many(40)))
    right.focus()
    tui.paint()
    before_left, before_right = left.viewport.offset, right.viewport.offset
    # a key carries no pointer: every scroll key lands on the focused pane ...
    assert tui._scroll_viewport(key("page_up")) is right.viewport
    assert tui._scroll_viewport(key("page_down")) is right.viewport
    # ... while a wheel report scrolls the pane under the pointer (D5)
    assert tui._scroll_viewport(MouseEvent("wheel_up", button=0, x=4, y=0)) is left.viewport
    assert tui._scroll_viewport(MouseEvent("wheel_up", button=0, x=30, y=0)) is right.viewport
    # a report naming no pane (past the last composition) falls back to focus
    assert tui._scroll_viewport(MouseEvent("wheel_up", button=0, x=2, y=99)) is right.viewport
    tui.scroll_up(1)
    tui.paint()
    assert left.viewport.offset == before_left
    assert right.viewport.offset != before_right


def test_the_band_reserves_its_rows_beneath_the_pane_area():
    document = Document()
    document.add(Rows("the band"), pin="bottom")
    tui = headless_tui(40, 6)
    band = tui.add_band(Viewport(document))
    assert tui.band is band and tui.frame.band is band
    tui.add(Rows("transcript"))
    tui.paint()
    assert [row.text for row in tui.rows] == [
        "transcript",
        "",
        "",
        "",
        "",
        "the band",
    ]
    assert tui.frame.panes[0].rect == Rect(0, 0, 40, 5)
    assert band.rect == Rect(0, 5, 40, 1)
    assert tui.frame.panes == (tui.frame.panes[0],)  # the band is not a content pane
    hit = tui.hit_test(4, 5)
    assert hit is not None and hit.block is document.blocks()[0]
    assert tui.viewport_rows() == (0, 4)
    with pytest.raises(ValueError):
        tui.frame.focus("band")
    with pytest.raises(RuntimeError):
        tui.add_band(Viewport(Document()))
    tui.remove_band()
    tui.paint()
    assert [row.text for row in tui.rows] == ["transcript"] + [""] * 5


def test_a_wheel_over_the_band_scrolls_the_focused_pane():
    """The band holds no scroll state: a wheel over the footer scrolls focus."""
    document = Document()
    document.add(Rows("band"), pin="bottom")
    tui = headless_tui(40, 6)
    tui.add_band(Viewport(document))
    tui.add(Rows(*many(40)))
    tui.paint()
    assert tui._scroll_viewport(MouseEvent("wheel_up", button=0, x=4, y=5)) is tui.viewport


def test_hit_test_resolves_report_coordinates_into_a_block():
    tui = headless_tui(80, 6)
    body = tui.add(Rows(*many(10)))  # b0: r0..r9 in the scrollable body
    foot = tui.add(Rows("foot"), pin="bottom")  # b1: the bottom fixed region
    tui.paint()
    # Screen rows (0-based): r5..r9 above the pinned footer's one row.
    hit = tui.hit_test(2, 0)  # 0-based (col 2, row 0) -> screen row 0 = b0 row 5
    assert hit is not None and hit.block is body and hit.row == 5 and hit.col == 2
    hit = tui.hit_test(0, 5)  # the footer's only row, column 0
    assert hit is not None and hit.block is foot and hit.row == 0 and hit.col == 0


def test_hit_test_misses_blank_fill_out_of_range_removed_and_no_layout():
    tui = headless_tui(80, 4)
    tui.add(Rows("only"))
    tui.paint()
    assert tui.hit_test(0, 2) is None  # blank fill below the content
    assert tui.hit_test(0, 98) is None  # below the screen of the last layout
    tui.remove("b0")  # the ownership table is stale until the next layout
    assert tui.hit_test(0, 0) is None
    fresh = headless_tui(80, 6)  # and before any layout has run
    fresh.add(Text("x"))
    assert fresh.hit_test(0, 0) is None


def test_hit_test_on_the_more_below_marker_keeps_the_covered_row():
    tui = headless_tui(80, 4)
    body = tui.add(Rows(*many(10)))
    tui.paint()
    tui.scroll_up(1)  # the window shows r5..r8, the marker painted over r8
    tui.paint()
    hit = tui.hit_test(0, 3)  # screen row 3, where the marker sits
    assert hit is not None and hit.block is body and hit.row == 8


def test_hit_test_clamps_the_column_into_the_pane_at_both_edges():
    tui = headless_tui(80, 6)
    body = tui.add(Rows(*many(10)))  # b0: r0..r9, the window sticks to the tail
    tui.paint()
    left = tui.hit_test(-5, 0)  # a report left of the pane: the pane's first column
    right = tui.hit_test(500, 0)  # and past its right edge: the pane's last
    assert left is not None and right is not None
    assert (left.block is body, left.row, left.col) == (True, 4, 0)
    assert (right.block is body, right.row, right.col) == (True, 4, 79)


def test_hit_component_descends_one_block_to_whichever_child_owns_the_cell():
    from mocode_tui.widgets.choice import Option, Select
    from mocode_tui.widgets.layout import Column
    from mocode_tui.widgets.tree import Tree, TreeNode

    menu = Select([Option("one"), Option("two")])
    tree = Tree([TreeNode("node")])
    tui = headless_tui(40, 10)
    block = tui.add(Column([menu, tree]))
    tui.paint()
    # The menu paints rows 0..1, the tree row 2 -- one block, two widgets.
    assert tui.hit_component(0, 0) == (menu, 0, 0)
    assert tui.hit_component(0, 1) == (menu, 1, 0)
    assert tui.hit_component(0, 2) == (tree, 0, 0)
    # The block-level hit stays the block; a blank cell answers ``None``.
    assert tui.hit_test(0, 0).block is block
    assert tui.hit_component(0, 5) is None


# --- selection overlay ----------------------------------------------------------


def _marked(rows: list[Line]) -> list[str]:
    """Per row: the text of the pieces the selection marked, ``""`` when none.

    A piece counts as marked when it carries SELECTION's attributes --
    ``reverse`` -- which no base style in this file carries:
    colors are injected per row and round-tripped, never pinned.
    """
    return [
        "".join(seg.text for seg in row.segments if seg.style.reverse)
        for row in rows
    ]


def test_set_selection_marks_the_in_range_rows_and_leaves_the_rest_untouched():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta", "gamma"))
    tui.paint()
    plain = tui.rows
    written = len(tui.screen.output)

    selection = Selection.between(("b0", 0, 2), ("b0", 1, 3))
    tui.set_selection(selection)
    assert tui.selection is selection  # stored exactly as given
    tui.paint()

    assert _marked(tui.rows) == ["pha", "bet", "", "", "", ""]
    # The overlay is style over the frame: the rows keep their text, and the
    # painted bytes rewrite the marked rows only -- gamma never appears in
    # them, and its row comes back the very same value it was.
    assert [row.text for row in tui.rows] == [row.text for row in plain]
    assert tui.rows[2] == plain[2]
    fresh = tui.screen.output[written:]
    assert "pha" in fresh and "bet" in fresh and "gamma" not in fresh


def test_a_block_style_round_trips_under_the_selection_merge():
    tui = headless_tui(80, 6)
    styled = Style(fg="#abcdef")
    tui.add(Text("alpha", style=styled))
    tui.paint()
    tui.set_selection(Selection.between(("b0", 0, 2), ("b0", 0, 5)))
    tui.paint()
    assert [(seg.text, seg.style) for seg in tui.rows[0].segments] == [
        ("al", styled),
        ("pha", styled.merge(SELECTION)),
    ]


def test_set_selection_none_restores_the_exact_unhighlighted_rows():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta", "gamma"))
    tui.paint()
    plain = tui.rows
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 2, 3)))
    tui.paint()
    assert _marked(tui.rows) == ["alpha", "beta", "gam", "", "", ""]

    written = len(tui.screen.output)
    tui.set_selection(None)
    assert tui.selection is None
    tui.paint()
    assert tui.rows == plain  # every row is its un-highlighted value again ...
    fresh = tui.screen.output[written:]
    assert fresh  # ... rewritten back, ...
    assert SELECTION.prefix() not in fresh  # ... without one selection byte left


def test_set_selection_invalidates_and_the_pump_paints_the_highlight():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha"))
    now = [1000.0]
    tui.clock = lambda: now[0]  # the documented clock seam
    tui.tick(now[0])  # the initial frame
    written = len(tui.screen.output)

    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 0, 5)))
    assert len(tui.screen.output) == written  # queued: the throttle has not elapsed
    assert tui.tick(now[0]) == pytest.approx(tui.throttle)
    now[0] += 0.050  # comfortably past the throttle
    tui.tick(now[0])
    assert len(tui.screen.output) > written  # the pump painted the highlight
    assert _marked(tui.rows) == ["alpha", "", "", "", "", ""]


def test_scrolling_moves_the_text_and_leaves_the_selection_in_place():
    tui = headless_tui(80, 6)
    tui.add(Rows(*many(10)))  # b0: r0..r9, the window sticks to the tail
    tui.paint()
    selection = Selection.between(("b0", 1, 1), ("b0", 3, 2))
    tui.set_selection(selection)
    tui.paint()
    assert _marked(tui.rows) == ["", "", "", "", "", ""]  # scrolled out of the window

    tui.scroll_up(3)  # the window shows r1..r6, the more-below marker over r6
    tui.paint()
    assert tui.selection is selection  # not cleared, not moved: document space
    assert _marked(tui.rows) == ["1", "r2", "r3", "", "", ""]

    tui.scroll_to_bottom()
    tui.paint()
    assert tui.selection is selection  # still there, just out of view again
    assert _marked(tui.rows) == ["", "", "", "", "", ""]


@pytest.mark.parametrize(("field", "clears"), [("width", True), ("height", False)])
def test_a_width_change_clears_the_selection_but_a_height_change_keeps_it(
    field: str, clears: bool
):
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta"))
    tui.paint()
    selection = Selection.between(("b0", 0, 0), ("b0", 1, 2))
    tui.set_selection(selection)
    tui.paint()
    setattr(tui.screen, field, 40 if field == "width" else 12)  # the terminal resized
    tui.paint()
    if clears:
        assert tui.selection is None  # reflow: the columns address other glyphs (D8)
        assert not any(_marked(tui.rows))
    else:
        assert tui.selection is selection
        assert _marked(tui.rows)[:2] == ["alpha", "be"]


def test_a_selection_over_a_removed_block_highlights_nothing():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha"))
    tui.add(Rows("beta"))
    tui.paint()
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 0, 5)))
    tui.remove("b0")  # the block under the anchor leaves the document
    tui.paint()
    assert tui.selection is not None  # the driver keeps the stored value ...
    assert not any(_marked(tui.rows))  # ... and the overlay resolves to nothing


def test_the_presented_frame_shows_the_overlay_and_the_document_view_does_not():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta"))
    tui.paint()
    before = snapshot(tui)
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 1, 2)))
    tui.paint()
    assert _marked(tui.rows)[:2] == ["alpha", "be"]  # the presented frame shows it
    assert snapshot(tui) == before  # the document view is style-free and unchanged


def test_the_selection_overlay_rides_a_retiled_frame():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta"))
    tui.paint()
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 1, 2)))
    tui.paint()
    assert _marked(tui.rows)[:2] == ["alpha", "be"]

    tui.screen.height = 12  # the terminal resized: the frame is retiled
    tui.paint()
    assert tui.selection is not None  # only a width change clears it (D8) ...
    assert _marked(tui.rows)[:2] == ["alpha", "be"]  # ... and the overlay rode along


# --- pump: throttle and every --------------------------------------------------


def test_the_pump_paints_on_the_throttle_and_runs_every_callbacks():
    tui = headless_tui()
    now = [1000.0]
    tui.clock = lambda: now[0]  # the documented clock seam

    assert tui.tick(now[0]) is None  # the initial frame flushes immediately
    painted = len(tui.screen.output)

    tui.add(Text("x"))
    assert tui.tick(now[0]) == pytest.approx(tui.throttle)  # the window has not elapsed
    assert len(tui.screen.output) == painted  # nothing painted yet

    now[0] += 0.050  # comfortably past the throttle
    assert tui.tick(now[0]) is None  # now it flushes
    assert len(tui.screen.output) > painted

    # A periodic callback that invalidates lands on the next window again.
    block = tui.add(Text(""))

    def grow() -> None:
        block.component.text += "x"  # new content for the next frame
        tui.invalidate()

    handle = tui.every(0.010, grow)
    painted = len(tui.screen.output)
    now[0] += 0.010
    assert tui.tick(now[0]) == pytest.approx(0.010)  # due, throttle pending
    assert len(tui.screen.output) == painted

    now[0] += 0.050  # the throttle elapses
    tui.tick(now[0])
    assert len(tui.screen.output) > painted  # the new content was painted
    handle.cancel()


def test_every_runs_on_schedule_and_can_be_cancelled():
    tui = headless_tui()
    now = [1000.0]
    tui.clock = lambda: now[0]
    tui.tick(now[0])  # the initial frame

    calls: list[int] = []
    handle = tui.every(0.5, lambda: calls.append(1))
    assert tui.tick(now[0]) == pytest.approx(0.5)

    now[0] += 0.5
    assert tui.tick(now[0]) == pytest.approx(0.5)
    assert calls == [1]

    handle.cancel()
    assert handle.cancelled is True
    now[0] += 5.0
    assert tui.tick(now[0]) is None
    assert calls == [1]


# --- run: lifecycle ------------------------------------------------------------


async def _body_returns(app: TUI) -> None:
    app.add(Text("hi"))


async def _body_stops(app: TUI) -> None:
    app.add(Text("hi"))
    await asyncio.sleep(0)  # let the pump paint
    app.stop()


async def _body_raises(app: TUI) -> None:
    app.add(Text("hi"))
    raise ValueError("boom")


async def _body_interrupts(app: TUI) -> None:
    app.add(Text("hi"))
    raise KeyboardInterrupt


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(_body_returns, id="returns"),
        pytest.param(_body_stops, id="stops"),
        pytest.param(_body_raises, id="raises"),
        pytest.param(_body_interrupts, id="keyboard-interrupt"),
    ],
)
async def test_run_brackets_enter_and_leave_on_every_exit_path(body):
    tui = headless_tui(80, 6)

    async def runner(app):
        await body(app)

    if body is _body_raises:
        with pytest.raises(ValueError, match="boom"):
            await tui.run(runner)
    else:
        await tui.run(runner)  # a KeyboardInterrupt is swallowed as a stop

    enter_at, leave_at = _enter_leave(tui)
    assert enter_at >= 0 and leave_at > enter_at
    assert tui.screen.output.endswith(leave_alt_screen())
    assert tui.screen.output  # the body's frames reached the screen


async def test_run_attaches_and_closes_raw_keys_when_interactive_and_live():
    tui = TUI(screen=HeadlessScreen(80, 6), interactive=True)
    seen: list[object] = []

    async def body(app):
        seen.append(app.keys)

    await tui.run(body)
    assert seen[0] is not None  # a raw source was attached for the session
    assert await tui.keys.read() is None  # and closed again by teardown


def test_focus_events_defaults_off_and_passes_through_to_the_default_screen(monkeypatch):
    # The driver's switch is the default screen's: off unless asked, and the
    # asked-for value reaches the TerminalScreen constructor untouched.
    built: list[dict] = []

    def fake_screen(**kwargs):
        built.append(kwargs)
        return HeadlessScreen(**kwargs)

    monkeypatch.setattr(app_module, "TerminalScreen", fake_screen)
    TUI(interactive=False)
    assert built[-1]["focus_events"] is False
    tui = TUI(interactive=False, focus_events=True)
    assert built[-1]["focus_events"] is True
    tui.screen.enter()
    tui.screen.leave()
    assert tui.screen.output.startswith("\x1b[?1049h")  # a live bracket ran
    assert "\x1b[?1004h" in tui.screen.output and "\x1b[?1004l" in tui.screen.output


def test_color_mode_is_forwarded_to_the_default_screen_only_when_set(monkeypatch):
    built: list[dict] = []

    def fake_screen(**kwargs):
        built.append(kwargs)
        return HeadlessScreen(**kwargs)

    monkeypatch.setattr(app_module, "TerminalScreen", fake_screen)
    TUI(interactive=False)
    assert "color_mode" not in built[-1]  # the screen's own "auto" stands
    TUI(interactive=False, color_mode="none")
    assert built[-1]["color_mode"] == "none"


def test_a_downgraded_tui_paints_the_downgraded_bytes():
    # End to end: the driver's painter reads the screen's mode and renders
    # the rows for it.
    tui = TUI(screen=HeadlessScreen(20, 2, color_mode="256"), interactive=False)
    tui.add(Text("x", style=Style(fg="#58a6ff")))
    tui.paint()
    assert "\x1b[38;5;75m" in tui.screen.output
    assert "\x1b[38;2;88;166;255m" not in tui.screen.output


def test_set_title_writes_the_osc2_bytes_even_on_a_non_live_screen():
    # The title is a host-owned gesture, not session chrome: the bytes reach
    # the screen's write path whatever its liveness (the piped screen here
    # records them), so the call is assertable without a terminal.
    tui, stream = _piped_tui()
    tui.set_title("hello \u00b7 world")
    assert stream.getvalue() == "\x1b]2;hello \u00b7 world\x07"


def test_set_cursor_shape_writes_the_decscusr_bytes_and_an_unknown_raises():
    tui = TUI(screen=HeadlessScreen(20, 2), interactive=False)
    tui.set_cursor_shape("beam")
    assert tui.screen.output == "\x1b[6 q"
    with pytest.raises(KeyError):
        tui.set_cursor_shape("bar")
    assert tui.screen.output == "\x1b[6 q"  # the refused call wrote nothing


# --- run: non-live dump --------------------------------------------------------


async def test_non_live_run_stays_silent_and_dumps_plain_text():
    tui, stream = _piped_tui()
    seen: list[str] = []

    async def body(app):
        app.add(Text("hello"))
        app.add(Text("world"))
        seen.append(stream.getvalue())  # nothing written during the run

    await tui.run(body)
    assert seen == [""]
    # The dump is the final screen's rows as plain text: trailing all-blank
    # rows trimmed, and not one escape byte in it.
    dumped = stream.getvalue()
    assert dumped == "hello\nworld\n"
    assert enter_alt_screen() not in dumped and leave_alt_screen() not in dumped


async def test_non_live_dump_puts_the_pinned_footer_last():
    tui, stream = _piped_tui()

    async def body(app):
        app.add(Text("body"))
        app.add(Text("footer"), pin="bottom")

    await tui.run(body)
    lines = stream.getvalue().splitlines()
    assert lines[0] == "body" and lines[-1] == "footer"


# --- testing helpers -----------------------------------------------------------


def test_snapshot_renders_block_stanzas():
    tui = headless_tui(80, 24)
    tui.add(Text("first\nsecond"))
    footer = tui.add(Text("foot"), pin="bottom")
    footer.seal()
    text = snapshot(tui)
    assert text.startswith("[b0 | open]\n  |first\n  |second\n")
    assert "[b1 | sealed,bottom]" in text
    assert text.splitlines()[-1].startswith("  |")


def test_headless_tui_wires_a_recording_screen_and_scripted_keys():
    tui = headless_tui(80, 24, script=[key("x", "x")])
    assert isinstance(tui.screen, HeadlessScreen)
    assert tui.screen.live is True and tui.interactive is False
