"""Hit translation: the kernel's ``descend`` and the containers' ``child_at``.

``descend`` walks ``Container.child_at`` to the deepest component owning a
cell; the layout and decor containers answer it from the geometry of their
last render, so a container that has not rendered yet declines every cell.
Nothing here re-renders through ``child_at``: the cache is read, never
recomputed.
"""

from _doubles import Rows

from mocode_tui.core.block import Container, Hoverable, descend
from mocode_tui.core.lines import Line, Text
from mocode_tui.widgets.decor import Panel
from mocode_tui.widgets.layout import Column, Padding, Row, Spacer


class SelfReturning:
    """A malformed container that claims every cell as its own child."""

    def __init__(self) -> None:
        self.calls = 0

    def render(self, width: int) -> list[Line]:
        return [Line()]

    def child_at(self, row: int, col: int):
        self.calls += 1
        return self, row, col


class Flag:
    """The minimum a hoverable declares: one read-write flag."""

    def __init__(self) -> None:
        self.hover = False


class Counting:
    """A leaf that counts its renders, to prove ``child_at`` reads a cache."""

    def __init__(self) -> None:
        self.renders = 0

    def render(self, width: int) -> list[Line]:
        self.renders += 1
        return [Line.from_text("x")]


# --- the kernel protocols and descend -------------------------------------------


def test_hoverable_is_a_runtime_protocol_over_one_flag():
    assert isinstance(Flag(), Hoverable)
    # ``Text`` joined the protocol in tui-depth W2 (D6): its rows answer
    # ``hover_at`` (the span-level highlight) and the protocol's one flag
    # rides on it.  The flag itself changes nothing -- Text's own visual is
    # the span, and its docstring says so -- but the protocol is the flag's
    # shape, not its consumer.
    assert isinstance(Text("x"), Hoverable)


def test_container_is_a_runtime_protocol_over_child_at():
    assert isinstance(SelfReturning(), Container)
    assert not isinstance(Text("x"), Container)


def test_descend_returns_a_leaf_with_its_coords_unchanged():
    text = Text("x")
    assert descend(text, 0, 0) == (text, 0, 0)
    assert descend(text, 3, 4) == (text, 3, 4)


def test_descend_stops_at_a_malformed_container_that_returns_itself():
    loop = SelfReturning()
    assert descend(loop, 3, 4) == (loop, 3, 4)
    assert loop.calls == 64  # the module's _DESCEND_LIMIT guard


def test_descend_returns_a_container_that_declines_the_cell():
    row = Row([Text("a")], widths=[1], gap=1)
    row.render(10)
    assert descend(row, 0, 5) == (row, 0, 5)  # past the only column


def test_descend_walks_nested_containers_to_the_leaf():
    leaf = Text("x")
    column = Column([Spacer(), Padding(leaf, left=2)])
    column.render(10)
    assert descend(column, 1, 3) == (leaf, 0, 1)


# --- layout containers -----------------------------------------------------------


def test_the_layout_containers_implement_child_at():
    for container in (Row([Text("a")]), Column([Text("a")]), Padding(Text("a"))):
        assert isinstance(container, Container)
    assert not isinstance(Spacer(), Container)


def test_column_maps_a_row_to_the_child_that_owns_it():
    first, second = Text("a"), Text("b")
    column = Column([first, second], gap=0)
    assert column.child_at(1, 0) is None  # before the first render
    column.render(10)
    assert column.child_at(0, 0) == (first, 0, 0)
    assert column.child_at(1, 0) == (second, 0, 0)
    assert column.child_at(2, 0) is None  # past the last row
    assert column.child_at(1, 5) == (second, 0, 5)  # the column passes through


def test_column_gap_rows_belong_to_the_column_itself():
    column = Column([Text("a"), Text("b")], gap=1)
    column.render(10)
    assert column.child_at(1, 0) is None  # the gap row
    assert column.child_at(2, 0) == (column.children[1], 0, 0)


def test_row_maps_a_column_to_the_child_that_owns_it():
    first, second = Text("aa"), Text("bb")
    row = Row([first, second], widths=[2, None], gap=1)
    assert row.child_at(0, 0) is None  # before the first render
    row.render(10)
    assert row.child_at(0, 0) == (first, 0, 0)
    assert row.child_at(0, 3) == (second, 0, 0)
    assert row.child_at(0, 2) is None  # the gap column


def test_row_filler_rows_below_a_shorter_child_are_the_rows_own():
    tall, short = Rows("a", "b"), Rows("c")
    row = Row([tall, short], widths=[1, 1], gap=0)
    row.render(10)
    assert row.child_at(0, 0) == (tall, 0, 0)
    assert row.child_at(1, 0) == (tall, 1, 0)
    assert row.child_at(1, 1) is None  # blank filler beside the tall child


def test_padding_declines_its_own_whitespace():
    child = Text("x")
    padded = Padding(child, left=2, top=1)
    assert padded.child_at(1, 2) is None  # before the first render
    padded.render(10)
    assert padded.child_at(1, 2) == (child, 0, 0)
    assert padded.child_at(0, 0) is None  # the top inset


def test_padding_maps_the_right_fill_to_nothing():
    child = Text("x")
    padded = Padding(child, left=2, right=2, top=1)
    padded.render(10)
    assert padded.child_at(1, 2) == (child, 0, 0)
    assert padded.child_at(1, 8) is None  # the right fill: inner ends at 8
    assert padded.child_at(1, 9) is None


def test_child_at_reads_the_cache_and_never_re_renders():
    leaf = Counting()
    padded = Padding(leaf, left=1)
    padded.render(10)
    assert leaf.renders == 1
    padded.child_at(0, 1)
    padded.child_at(0, 0)
    assert leaf.renders == 1  # the cache was read, nothing re-rendered


def test_a_re_render_replaces_the_cached_geometry():
    child = Text("x")
    padded = Padding(child, left=2)
    padded.render(10)
    assert padded.child_at(0, 2) == (child, 0, 0)
    padded.render(1)  # the insets swallow the width: nothing maps
    assert padded.child_at(0, 2) is None


# --- the boxed panel -------------------------------------------------------------


def test_panel_maps_its_content_cells_to_the_child():
    child = Text("x")
    panel = Panel(child, title="t")
    assert isinstance(panel, Container)
    assert panel.child_at(1, 2) is None  # before the first render
    panel.render(10)
    assert panel.child_at(1, 2) == (child, 0, 0)
    assert panel.child_at(0, 0) is None  # the top border row
    assert panel.child_at(2, 0) is None  # the bottom border row
    assert panel.child_at(1, 1) is None  # the left border column
    assert panel.child_at(1, 8) is None  # the right border column


def test_a_degraded_panel_hands_the_bare_child_the_whole_block():
    child = Text("x")
    panel = Panel(child)
    panel.render(3)
    assert panel.child_at(0, 2) == (child, 0, 2)
    assert panel.child_at(1, 0) is None  # past the child's rows
