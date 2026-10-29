"""Hit testing: screen cells resolve to panes, blocks, cells and leaves."""

from __future__ import annotations

from motui.kernel import Axis, RowSpan
from motui.kernel.cell import Line
from motui.kernel.document import Placement
from motui.kernel.frame import Chrome
from motui.widgets import Column, TreeNode
from motui.widgets.text import Text
from tests.testing import Rows, headless_tui, many


def test_hit_resolves_a_cell_to_its_block_row_and_column():
    tui = headless_tui(80, 6)
    body = tui.add(Rows(*many(10)))
    foot = tui.add(Rows("foot"), placement=Placement.BOTTOM)
    tui.paint()
    hit = tui.hit(2, 0)
    assert hit is not None and hit.block.id == body.id and hit.row == 5 and hit.col == 2
    hit = tui.hit(0, 5)
    assert hit is not None and hit.block.id == foot.id and hit.row == 0 and hit.col == 0


def test_hit_answers_none_for_blank_fill_out_of_range_removed_and_unpainted():
    tui = headless_tui(80, 4)
    tui.add(Rows("only"))
    tui.paint()
    assert tui.hit(0, 2) is None
    assert tui.hit(0, 98) is None
    tui.remove("b0")
    assert tui.hit(0, 0) is None

    fresh = headless_tui(80, 6)
    fresh.add(Text("x"))
    assert fresh.hit(0, 0) is None


def test_hit_columns_are_relative_to_the_inner_rect():
    tui = headless_tui(20, 4)
    body = tui.add(Rows("0123456789"))
    pane = tui.frame.pane("primary")
    pane.add_chrome(
        Chrome("left", 2, lambda layout, length: [Line.from_text("||")] * length)
    )
    pane.add_chrome(
        Chrome("right", 2, lambda layout, length: [Line.from_text("||")] * length)
    )
    tui.paint()
    hit = tui.hit(2, 0)
    assert hit is not None and hit.block.id == body.id and hit.row == 0 and hit.col == 0
    assert tui.hit(0, 0) is None
    assert tui.hit(18, 0) is None
    assert tui.hit(17, 0).col == 15


def test_hit_leaf_descends_through_a_container_to_the_child():
    from motui.widgets.choice import Option, Select
    from motui.widgets.tree import Tree

    menu = Select([Option("one"), Option("two")])
    tree = Tree([TreeNode("node")])
    tui = headless_tui(40, 10)
    block = tui.add(Column([menu, tree]))
    tui.paint()
    assert tui.hit_leaf(0, 0) == (menu, 0, 0)
    assert tui.hit_leaf(0, 1) == (menu, 1, 0)
    assert tui.hit_leaf(0, 2) == (tree, 0, 0)
    assert tui.hit(0, 0).block.id == block.id
    assert tui.hit_leaf(0, 5) is None


def test_hit_routes_each_split_pane_to_its_own_document():
    tui = headless_tui(20, 4)
    left, right = tui.split(Axis.X)
    left_block = left.document.add(Rows("left"))
    right_block = right.document.add(Rows("right"))
    tui.paint()
    hit = tui.hit(0, 0)
    assert hit is not None and hit.pane_id == "primary" and hit.block is left_block
    hit = tui.hit(right.rect.x, 0)
    assert hit is not None and hit.pane_id == right.id and hit.block is right_block


def test_hit_resolves_a_dock_row():
    tui = headless_tui(40, 6)
    dock = tui.dock(Rows("docked"))
    tui.add(Rows("body"))
    tui.paint()
    hit = tui.hit(3, 5)
    assert hit is not None and hit.block is dock.document.blocks()[0]
    assert hit.row == 0 and hit.col == 3


def test_visible_range_reports_screen_rows_including_a_top_pin():
    tui = headless_tui(20, 8)
    tui.dock(Rows("head"), placement=Placement.TOP, size=2)
    tui.add(Rows("body"))
    tui.paint()
    assert tui.visible_range() == RowSpan(2, 7)
    assert tui.visible_range("nowhere") is None

def test_hit_is_strict_at_every_edge():
    tui = headless_tui(80, 6)
    tui.add(Rows(*many(10)))
    tui.paint()
    assert tui.hit(-1, 0) is None
    assert tui.hit(0, -1) is None
    assert tui.hit(80, 0) is None
    assert tui.hit(0, 6) is None


def test_pane_at_resolves_content_dock_and_outside():
    tui = headless_tui(40, 6)
    tui.add(Rows("body"))
    dock = tui.dock(Rows("docked"))
    assert tui.pane_at(0, 0) is None  # no composition yet
    tui.paint()
    assert tui.pane_at(0, 0).id == "primary"
    assert tui.pane_at(0, 5) is dock
    assert tui.pane_at(-1, 0) is None
    assert tui.pane_at(0, 6) is None
    assert tui.pane_at(40, 0) is None


def test_hit_resolves_the_last_window_row():
    tui = headless_tui(80, 4)
    body = tui.add(Rows(*many(10)))
    tui.paint()
    tui.scroll_up(1)
    tui.paint()
    hit = tui.hit(0, 3)
    assert hit is not None and hit.block.id == body.id and hit.row == 8
