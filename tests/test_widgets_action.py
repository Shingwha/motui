"""The action primitives and the existing widgets' hover surface.

``Button`` / ``Checkbox`` / ``Link`` are the minimal clickable units: state
plus controller methods, no callbacks -- ``click`` / ``activate`` land the
operation in ``chosen``, which the host reads once -- and ``hover`` /
``focused`` only change rendering.  ``hover_at`` is the row-level half of
the same contract on the existing widgets: it marks the row under the
pointer and answers whether the render changed, and ``row < 0`` clears it
byte-for-byte back to the un-hovered output.
"""

from __future__ import annotations

from motui.app import TUI
from motui.interaction import FocusRing, Pointer
from motui.kernel import HeadlessScreen
from motui.kernel.block import Hoverable
from motui.kernel.events import MouseEvent
from motui.kernel.lines import Line
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.widgets import (
    Autocomplete,
    Button,
    Checkbox,
    Link,
    Padding,
    TreeNode,
)
from motui.widgets.choice import Option, Select
from motui.widgets.textfield import Editor, Input
from motui.widgets.table import Table
from motui.widgets.tabs import Tabs
from motui.widgets.tree import Tree

def row(component, width: int = 20) -> Line:
    """The component's first rendered row."""
    return component.render(width)[0]


def motion(x: int, y: int) -> MouseEvent:
    return MouseEvent("motion", button=0, x=x, y=y, kind="motion")


def click_event(x: int, y: int, kind: str) -> MouseEvent:
    return MouseEvent("left", button=0, x=x, y=y, kind=kind)


# --- Button ------------------------------------------------------------------


def test_button_renders_one_fitted_row_in_the_accent_band():
    button = Button("Run")
    assert row(button).text == " Run "
    assert row(button).segments[0].style == DEFAULT_THEME.accent
    assert row(button, width=3).text == " R\u2026"  # one row, never wider


def test_button_hover_and_focus_merge_their_bands():
    button = Button("Run")
    assert row(button).segments[0].style == DEFAULT_THEME.accent
    button.hover = True
    assert row(button).segments[0].style == DEFAULT_THEME.accent.merge(DEFAULT_THEME.hover)
    button.hover = False
    button.focused = True
    assert row(button).segments[0].style == DEFAULT_THEME.accent.merge(DEFAULT_THEME.focus)
    assert row(button).text == " Run "  # the bands never change the text


def test_button_click_and_activate_both_land_in_chosen():
    button = Button("Run")
    assert button.chosen is None
    assert button.click(0, 0) is True and button.chosen is True
    button.chosen = None  # the host reads once and resets
    assert button.activate() is True and button.chosen is True
    button.chosen = None
    assert button.click(9, 40) is True  # every cell is the button
    assert button.chosen is True


def test_explicit_styles_beat_the_theme_fields():
    theme = Theme(accent=Style(fg="#ff0000"), hover=Style(bg="#00ff00"))
    button = Button("x", style=Style(underline=True), hover_style=Style(italic=True), theme=theme)
    assert row(button).segments[0].style == Style(underline=True)
    button.hover = True
    assert row(button).segments[0].style == Style(underline=True).merge(Style(italic=True))


# --- Checkbox ------------------------------------------------------------------


def test_checkbox_flips_its_mark_and_mirrors_it_into_chosen():
    box = Checkbox("Bold")
    assert row(box).text == "[ ] Bold"
    assert box.activate() is True
    assert (box.checked, box.chosen) == (True, True)
    assert row(box).text == "[x] Bold"
    assert row(box).segments[0].style == DEFAULT_THEME.accent
    box.chosen = None  # the host reads once and resets
    assert box.click(0, 0) is True
    assert (box.checked, box.chosen) == (False, False)


# --- Link ------------------------------------------------------------------


def test_link_follows_a_click_and_wears_the_link_band():
    link = Link("docs/COMPONENTS.md")
    assert row(link).text == "docs/COMPONENTS.md"
    assert row(link).segments[0].style == DEFAULT_THEME.link
    link.hover = True
    assert row(link).segments[0].style == DEFAULT_THEME.link.merge(DEFAULT_THEME.hover)
    link.hover = False
    assert link.chosen is None
    assert link.click(0, 3) is True and link.chosen is True


# --- with the pointer and the ring ------------------------------------------------


def test_a_pointer_ring_click_completes_a_button_wrapped_in_padding():
    button = Button("Run")
    tui = TUI(screen=HeadlessScreen(40, 8, hover=True), interactive=False)
    tui.add(Padding(button, left=1, top=1))
    tui.paint()
    ring = FocusRing([button])  # a one-target ring focuses it at construction
    pointer = Pointer(tui, ring=ring)
    assert pointer.handle(motion(2, 1)) is True  # the wrapper descends to it
    assert button.hover is True and pointer.hovered is button
    pointer.handle(click_event(2, 1, "press"))
    assert pointer.handle(click_event(2, 1, "release")) is True
    assert button.chosen is True  # the focused target's click activates


# --- hover_at on the existing widgets ---------------------------------------------


def test_select_marks_the_option_row_under_a_cell_and_clears_back():
    menu = Select([Option("one"), Option("two"), Option("three")])
    plain = menu.render(20)
    assert menu.hover_at(2, 0) is True  # row 2 carries the third option
    marked = menu.render(20)
    assert marked[2].segments[0].style == DEFAULT_THEME.hover
    assert marked[2].segments[1].style == DEFAULT_THEME.hover
    assert marked[0] == plain[0] and marked[1] == plain[1]
    assert menu.hover_at(2, 0) is False  # the same row: nothing to repaint
    assert menu.hover_at(1, 0) is True
    assert menu.render(20)[2] == plain[2]  # the old row let the band go
    assert menu.hover_at(-1, -1) is True  # the pointer left
    assert menu.render(20) == plain  # byte-for-byte the un-hovered rows


def test_select_hover_merges_over_the_cursor_row_and_steps_over_non_options():
    menu = Select([Option("one"), Option("two")], title="Pick")
    plain = menu.render(20)
    assert menu.hover_at(0, 0) is False  # the title row carries no option
    assert menu.hover_at(1, 0) is True  # row 1 is the cursor row's option
    marked = menu.render(20)
    assert marked[1].segments[1].style == DEFAULT_THEME.accent.merge(DEFAULT_THEME.hover)
    assert marked[0] == plain[0] and marked[2] == plain[2]
    assert menu.hover_at(-1, -1) is True
    assert menu.render(20) == plain


def test_autocomplete_marks_the_row_over_its_matches():
    box = Autocomplete(options=[Option("alpha"), Option("beta")])
    plain = box.render(20)
    assert box.hover_at(1, 0) is True
    assert box.render(20)[1] != plain[1]
    box.set_query("alpha")  # one match left: row 1 is past the rows now
    assert box.hover_at(1, 0) is True
    assert [row.text for row in box.render(20)] == ["\u2192 alpha"]


def test_tabs_marks_the_label_under_a_cell_and_clears_back():
    strip = Tabs(["one", "two"])
    plain = strip.render(30)
    assert strip.hover_at(0, 8) is True  # cell 8 is inside "two"
    marked = strip.render(30)
    # "two": the dim label under the pointer's band; "one": the accent
    # label's own indicator (the underline the active tab wears).
    assert marked[0].segments[3].style == DEFAULT_THEME.dim.merge(DEFAULT_THEME.hover)
    assert marked[0].segments[1].style == DEFAULT_THEME.accent.merge(Style(underline=True))
    assert strip.hover_at(0, 8) is False
    assert strip.hover_at(0, 5) is True  # a divider gap: no label
    assert strip.render(30) == plain
    assert strip.hover_at(0, 8) is True
    assert strip.hover_at(0, 20) is True  # past the last label: no label
    assert strip.render(30) == plain
    assert strip.hover_at(-1, -1) is False  # nothing was marked: no change


def test_tree_marks_the_visible_node_row_and_clears_back():
    tree = Tree([TreeNode("a"), TreeNode("b")])
    plain = tree.render(20)
    assert tree.hover_at(1, 0) is True
    marked = tree.render(20)
    assert marked[1].segments[0].style == DEFAULT_THEME.dim.merge(DEFAULT_THEME.hover)
    assert marked[1].segments[1].style == DEFAULT_THEME.hover
    assert marked[0] == plain[0]
    assert tree.hover_at(1, 0) is False
    assert tree.hover_at(2, 0) is True  # past the last node: no node
    assert tree.render(20) == plain


def test_table_marks_the_data_row_under_a_rendered_row_and_clears_back():
    table = Table(["h"], [["a"], ["b"]])
    plain = table.render(30)
    # The frame: 0 top rule, 1 header, 2 header rule, 3 data 0, 4 row rule,
    # 5 data 1, 6 bottom.
    assert table.hover_at(5, 0) is True
    marked = table.render(30)
    assert marked[5] != plain[5]
    assert marked[3] == plain[3]
    assert table.hover_at(5, 0) is False
    assert table.hover_at(0, 0) is True  # a frame row carries no data
    assert table.render(30) == plain


def test_the_hovered_table_row_wears_the_cursors_band_and_leaves_it_clean():
    # D2: the keyboard cursor row and the pointer-hovered row share the one
    # ground_active token, so a hover over the cursor row has nothing to
    # merge and a hover over a resting row gives its cells the very band the
    # cursor row's carry.
    theme = Theme(ground_active=Style(bold=True))
    table = Table(["h"], [["a"], ["b"]], theme=theme)
    table.index = 0
    plain = table.render(30)
    assert table.hover_at(3, 0) is True  # the cursor row itself
    assert table.render(30) == plain  # the shared token: the no-op hover
    assert table.hover_at(5, 0) is True  # a resting row takes the cursor's band
    marked = table.render(30)
    assert marked[3] == plain[3]
    assert marked[5] != plain[5]
    assert marked[5].segments[1].style == theme.ground_active
    assert table.hover_at(-1, -1) is True
    assert table.render(30) == plain


def test_the_hovered_tree_row_wears_the_cursors_band_and_leaves_it_clean():
    # D2: the keyboard cursor row and the pointer-hovered row share the one
    # ground_active token, so a hover over the cursor row has nothing to
    # merge and a hover over a resting row gives it the very band the cursor
    # wears.
    theme = Theme(ground_active=Style(underline=True))
    tree = Tree([TreeNode("a"), TreeNode("b")], theme=theme)
    plain = tree.render(20)
    assert tree.hover_at(0, 0) is True  # the cursor row itself
    assert tree.render(20) == plain  # the shared token: the no-op hover
    assert tree.hover_at(1, 0) is True  # a resting row takes the cursor's band
    marked = tree.render(20)
    assert marked[0] == plain[0]
    assert marked[1].segments[0].style == theme.ground_active.merge(theme.dim)
    assert marked[1].segments[1].style == theme.ground_active
    assert tree.hover_at(-1, -1) is True
    assert tree.render(20) == plain


def test_the_text_fields_take_the_block_level_hover_band_only():
    field = Input()
    assert isinstance(field, Hoverable)
    assert not hasattr(field, "hover_at")  # a text row has no sub-row items
    plain = field.render(20)
    field.hover = True
    marked = field.render(20)
    assert marked != plain
    assert marked[0].segments[0].style == DEFAULT_THEME.accent.merge(DEFAULT_THEME.hover)
    assert marked[0].segments[1].style == DEFAULT_THEME.caret.merge(DEFAULT_THEME.hover)
    field.hover = False
    assert field.render(20) == plain
    editor = Editor(text="hello")
    assert isinstance(editor, Hoverable)
    plain = editor.render(20)
    editor.hover = True
    assert editor.render(20) != plain
    editor.hover = False
    assert editor.render(20) == plain


# --- the pointer over a real row-level widget --------------------------------------


def test_a_pointer_marks_and_clears_the_row_of_a_real_select():
    menu = Select([Option("one"), Option("two")])
    tui = TUI(screen=HeadlessScreen(40, 8, hover=True), interactive=False)
    tui.add(menu)
    tui.paint()  # the block's rows land at the screen top
    pointer = Pointer(tui)
    plain = menu.render(40)
    assert pointer.handle(motion(0, 1)) is True  # enter: the second option
    assert menu.hover is True and pointer.hovered is menu
    assert menu.render(40)[1].segments[1].style == DEFAULT_THEME.hover
    assert pointer.handle(motion(0, 1)) is False  # the same row: no change
    assert pointer.handle(motion(0, 0)) is True  # the cursor row, merged
    assert menu.render(40)[0].segments[1].style == DEFAULT_THEME.accent.merge(
        DEFAULT_THEME.hover
    )
    assert pointer.handle(motion(0, 6)) is True  # a blank row: the marking clears
    assert menu.hover is False and menu.render(40) == plain
    assert pointer.handle(motion(0, 6)) is False
