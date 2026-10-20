"""Tests for motui.widgets.menubar (MenuBar and ContextMenu).

``MenuBar`` is the one-row horizontal menu strip: a clamped, non-wrapping
cursor, a span table recorded by the last render for clicks and hovers, and
an activation that leaves the active label pending for ``take_result``.
``ContextMenu`` is the ``Select`` preset a host mounts at a click cell with a
``Modal``.
"""

from __future__ import annotations

from motui.interaction import Modal
from motui.kernel import glyphs
from motui.kernel.block import Component, Focusable
from motui.kernel.events import MouseEvent
from motui.kernel.lines import Line, Segment
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.testing import headless_tui
from motui.widgets import ContextMenu, MenuBar, Option, Select

ACTIVE = Style(fg="red")
INACTIVE = Style(fg="blue")
HOVER = Style(fg="green")
DISABLED = Style(fg="yellow")
DIVIDER = Style(fg="magenta")


# --- MenuBar: rendering ---------------------------------------------------------


def test_render_is_one_row_with_active_label_dividers_and_padding():
    bar = MenuBar(["File", "Edit", "View"])
    rows = bar.render(40)
    assert len(rows) == 1  # a menu bar is always a single row
    assert rows[0].text == " File \u2502 Edit \u2502 View "
    assert rows[0].segments == (
        Segment(" "),
        Segment("File", DEFAULT_THEME.accent),  # active: accent, no underline
        Segment(" \u2502 ", DEFAULT_THEME.muted),
        Segment("Edit", DEFAULT_THEME.dim),
        Segment(" \u2502 ", DEFAULT_THEME.muted),
        Segment("View", DEFAULT_THEME.dim),
        Segment(" "),
    )
    assert rows[0].segments[1].style.underline is False  # the bar never underlines
    assert isinstance(bar, Component)
    assert MenuBar([]).render(40) == [Line()]  # an empty bar's one empty row
    assert MenuBar([]).render(0) == [Line()]


def test_an_over_wide_bar_truncates_instead_of_wrapping():
    bar = MenuBar(["alpha", "beta"])
    row = bar.render(4)[0]
    assert len(bar.render(4)) == 1
    assert row.width == 4
    assert row.text == " al\u2026"
    assert bar.click(0, 1) is False  # the truncated label carries no span


def test_style_injection_round_trips():
    bar = MenuBar(
        ["a", "b"],
        active_style=ACTIVE,
        inactive_style=INACTIVE,
        hover_style=HOVER,
        disabled_style=DISABLED,
        divider="|",
        divider_style=DIVIDER,
    )
    assert bar.render(20)[0].segments == (
        Segment(" "),
        Segment("a", ACTIVE),
        Segment("|", DIVIDER),
        Segment("b", INACTIVE),
        Segment(" "),
    )


# --- MenuBar: the cursor --------------------------------------------------------


def test_move_clamps_without_wrapping_and_select_reports_change():
    bar = MenuBar(["a", "b", "c"], index=7)
    assert bar.index == 2  # clamped on construction
    assert bar.move(1) is False and bar.index == 2  # the edge: no wrap-around
    assert bar.move(-1) is True and bar.index == 1
    assert bar.select(0) is True and bar.index == 0
    assert bar.select(0) is False  # already active: nothing changed
    assert bar.select(99) is True and bar.index == 2  # clamped
    assert bar.select(-5) is True and bar.index == 0  # clamped
    assert MenuBar([]).index == 0
    assert MenuBar([]).select(1) is False
    assert MenuBar([]).move(1) is False


def test_move_steps_over_the_disabled_indices():
    bar = MenuBar(["a", "b", "c", "d"], disabled_items={1, 2})
    assert bar.move(1) is True and bar.index == 3  # 1 and 2 are stepped over
    assert bar.move(1) is False and bar.index == 3  # the edge: no landing left
    assert bar.move(-1) is True and bar.index == 0  # and back across both
    assert bar.move(-1) is False and bar.index == 0
    one = MenuBar(["a", "b"], disabled_items={1})  # the only step out is disabled
    assert one.move(1) is False and one.index == 0


def test_click_maps_the_last_render_spans():
    bar = MenuBar(["File", "Edit", "View"])
    bar.render(40)
    assert bar.click(0, 1) is True and bar.index == 0  # "File"
    assert bar.click(0, 8) is True and bar.index == 1  # "Edit"
    assert bar.click(0, 15) is True and bar.index == 2  # "View"
    assert bar.click(0, 5) is False  # the divider gap
    assert bar.click(0, 19) is False  # the trailing padding
    assert bar.click(1, 8) is False  # any row but the first is a miss
    assert bar.click(0, 99) is False  # past the row
    assert bar.click(0, 8) is True  # a hit on the active label still answers True


def test_a_disabled_label_is_visible_but_not_selectable():
    bar = MenuBar(["a", "b", "c"], disabled_items={1}, disabled_style=DISABLED)
    rows = bar.render(20)  # " a \u2502 b \u2502 c ": "b" spans cell 5
    assert rows[0].segments[3] == Segment("b", DISABLED)
    assert bar.click(0, 5) is False and bar.index == 0  # a click is refused
    assert bar.select(1) is False and bar.index == 0  # so is a select
    assert bar.activate() is True  # the active label is still enabled
    assert bar.take_result() == "a"
    assert bar.move(1) is True and bar.index == 2  # the step skips it


def test_a_disabled_bar_refuses_every_gesture():
    bar = MenuBar(["a", "b"], disabled=True)
    assert bar.move(1) is False and bar.index == 0
    assert bar.select(1) is False and bar.index == 0
    assert bar.click(0, 1) is False
    assert bar.hover_at(0, 1) is True  # the pointer echo is not a selection
    assert bar.activate() is False
    assert bar.take_result() is None


# --- MenuBar: hover, activation and revision ------------------------------------


def test_hover_at_marks_one_label_and_clears_back():
    bar = MenuBar(["File", "Edit"])
    assert bar.hover_at(0, 8) is True  # "Edit" spans cell 8
    assert bar.render(40)[0].segments[3] == Segment(
        "Edit", DEFAULT_THEME.dim.merge(DEFAULT_THEME.hover)
    )
    assert bar.hover_at(0, 8) is False  # still the same label: nothing changed
    assert bar.hover_at(0, 5) is True  # the divider: the marking is cleared
    assert bar.render(40)[0].segments[3] == Segment("Edit", DEFAULT_THEME.dim)
    assert bar.hover_at(-1, -1) is False  # already clear
    assert bar.hover_at(0, 8) is True
    assert bar.hover_at(1, 8) is True  # a row other than the first clears it
    assert bar.render(40)[0].segments[3] == Segment("Edit", DEFAULT_THEME.dim)
    assert isinstance(bar, Focusable) and bar.focused is True


def test_a_disabled_label_keeps_its_style_under_the_pointer():
    bar = MenuBar(["a", "b"], disabled_items={1}, disabled_style=DISABLED)
    assert bar.hover_at(0, 5) is True  # "b" spans cell 5
    assert bar.render(20)[0].segments[3] == Segment("b", DISABLED)


def test_activate_leaves_the_active_label_pending_once():
    bar = MenuBar(["File", "Edit"])
    assert bar.activate() is True
    assert bar.take_result() == "File"
    assert bar.take_result() is None  # read once, then clear
    assert bar.move(1) is True
    bar.activate()
    assert bar.move(-1) is True  # a moved step clears a stale pending pick
    assert bar.take_result() is None
    assert MenuBar([]).activate() is False
    assert MenuBar([]).take_result() is None
    assert MenuBar(["a"], disabled_items={0}).activate() is False
    assert MenuBar(["a"], disabled=True).activate() is False


def test_revision_covers_every_render_input():
    bar = MenuBar(["a", "b"])
    first = bar.revision()
    assert bar.revision() == first  # a stable state is a stable snapshot
    bar.select(1)
    assert bar.revision() != first
    moved = bar.revision()
    bar.hover_at(0, 1)
    assert bar.revision() != moved
    hovered = bar.revision()
    bar.hover_at(-1, -1)
    assert bar.revision() != hovered
    bar.focused = False
    assert bar.revision() != hovered
    bar.disabled = True
    assert bar.revision() != hovered
    bar.disabled = False
    bar.items.append("c")  # the snapshot copies the labels
    assert bar.revision() != hovered
    bar.divider = "|"
    assert bar.revision() != hovered
    restyled = MenuBar(["a"], active_style=ACTIVE)
    assert restyled.revision() != MenuBar(["a"]).revision()


# --- ContextMenu ----------------------------------------------------------------


def test_context_menu_is_the_desktop_menu_select_preset():
    menu = ContextMenu([Option("Open"), Option("Save", "save")])
    assert isinstance(menu, Select)
    assert menu.commit is False  # only activate settles a pick
    assert menu.wrap is True  # the ends cycle
    assert menu.window is False  # the window hangs at the top
    assert menu.max_rows == 8
    assert menu.marker == glyphs.MENU_CURSOR
    assert menu.title == ""


def test_context_menu_activate_leaves_the_option_pending():
    menu = ContextMenu([Option("Open"), Option("Save", "save")])
    assert menu.select(1) is True
    assert menu.activate() is True
    assert menu.take_result() == Option("Save", "save")
    assert menu.take_result() is None


def test_context_menu_renders_its_title_and_respects_disabled_items():
    menu = ContextMenu([Option("Open"), Option("Quit")], title="File")
    rows = menu.render(20)
    assert rows[0].text == "File"
    assert rows[1].text == "\u2192 Open"
    assert rows[2].text == "  Quit"
    disabled = ContextMenu([Option("Open"), Option("Quit")], disabled_items={1})
    assert disabled.select(1) is False and disabled.index == 0
    assert disabled.activate() is True
    assert disabled.take_result() == Option("Open")


def test_context_menu_mounts_at_a_click_cell_under_a_modal():
    tui = headless_tui(40, 12)
    menu = ContextMenu([Option("Open"), Option("Save")], title="File")
    modal = Modal(tui, menu, anchor=(1, 2))
    modal.open()
    assert modal.is_open is True
    tui.paint()  # the anchored panel paints at (row 1, col 2)
    assert tui.rows[1].text.find("File") == 2
    assert tui.rows[2].text.find("\u2192 Open") == 2
    # A press inside the panel is the menu's click: row 1 is the first option.
    assert modal.handle(MouseEvent("left", x=2, y=2, kind="press")) is True
    assert menu.index == 0
    assert modal.handle(MouseEvent("left", x=2, y=3, kind="press")) is True
    assert menu.index == 1
    assert menu.activate() is True
    assert menu.take_result() == Option("Save")
    assert modal.take_result() is None  # a cursor move is not a decision
    modal.close()
    tui.paint()
    assert tui.rows[1].text.find("File") == -1  # closed: the panel is gone
