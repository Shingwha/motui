"""Tests for motui.widgets.delegate (the single-child identity wrapper).

The wrapper answers every protocol surface itself: the proxy door forwards
``render`` / ``revision`` / ``click`` / ``hover_at``, the container door maps
every cell to the child, and each door degrades to the protocol's own
negative rather than raising.  The block cache door -- ``isinstance`` on
method presence, decided once at construction -- is what makes the
``revision`` rule mandatory, so it is tested through a real
:class:`~motui.kernel.block.Block`.
"""

from __future__ import annotations

import pytest

from _doubles import Rows, texts

from motui.kernel import (
    Activable,
    Clickable,
    Component,
    Container,
    Focusable,
    Hoverable,
    Revisioned,
    descend,
)
from motui.kernel.block import Block
from motui.kernel.lines import Line
from motui.widgets import Delegate, Markdown, Panel, Text

# --- the doubles ---------------------------------------------------------------


class _Stable:
    """A child answering the very same rows -- and the very same list.

    The probe for the wrapper being the identity: a wrapper that copied or
    rebuilt anything would answer equal rows out of a different list.
    """

    def __init__(self, *rows: str) -> None:
        self._rows = [Line.from_text(row) for row in rows]

    def render(self, width: int) -> list[Line]:
        return self._rows


class _Counting:
    """A child that counts its renders: the probe for a cache being on or off."""

    def __init__(self, *rows: str) -> None:
        self.rows = list(rows)
        self.renders = 0

    def render(self, width: int) -> list[Line]:
        self.renders += 1
        return [Line.from_text(row) for row in self.rows]


class _Marked:
    """A hoverable, clickable, revisioned child: the marked row gains a mark.

    ``hover_at`` moves the mark and answers whether the render changed;
    ``revision`` publishes it -- the shape of a component whose rows depend
    on the pointer, which is what carries a hover to the screen through a
    block's row cache.
    """

    def __init__(self, *rows: str) -> None:
        self.rows = list(rows)
        self.marked: tuple[int, int] | None = None
        self.renders = 0

    def render(self, width: int) -> list[Line]:
        self.renders += 1
        return [
            Line.from_text(f"> {row}" if self.marked is not None and self.marked[0] == i else row)
            for i, row in enumerate(self.rows)
        ]

    def hover_at(self, row: int, col: int) -> bool:
        before, self.marked = self.marked, None if row < 0 else (row, col)
        return before != self.marked

    def click(self, row: int, col: int) -> bool:
        return 0 <= row < len(self.rows)

    def revision(self) -> object:
        return self.marked


def _sealed(component: Component) -> Block:
    """A sealed block holding ``component``, warmed twice (the probe's shape)."""
    block = Block("w", component)
    block.seal()
    block.rows(30)
    block.rows(30)
    return block


def _fresh(block: Block, component: Component) -> bool:
    """Whether the block's cached rows still match a direct child render."""
    cached = [row.styled() for row in block.rows(30)]
    direct = [row.styled() for row in component.render(30)]
    return cached == direct


# --- the proxy door ------------------------------------------------------------


def test_render_hands_back_the_childs_rows_verbatim():
    child = _Stable("alpha", "beta")
    wrapper = Delegate(child)
    assert texts(wrapper, 20) == ["alpha", "beta"]
    # The child's own answer, list and all: the identity allocates nothing.
    assert wrapper.render(20) is child.render(20)


def test_revision_forwards_the_childs_snapshot():
    child = _Marked("one", "two")
    wrapper = Delegate(child)
    assert wrapper.revision() is None  # unmarked: the child's own answer
    assert child.hover_at(1, 2) is True
    assert wrapper.revision() == child.revision() == (1, 2)
    child.hover_at(-1, -1)
    assert wrapper.revision() == child.revision() is None


def test_click_forwards_the_childs_answer():
    child = _Marked("one", "two")
    wrapper = Delegate(child)
    assert wrapper.click(0, 0) is True  # a row of the child's
    assert wrapper.click(9, 9) is False  # past them, the child's own answer


def test_click_forwards_into_a_real_widget():
    md = Markdown("go to [docs](https://example.invalid) now")
    wrapper = Delegate(md)
    wrapper.render(80)  # the span index the hit test reads comes from a render
    assert wrapper.click(0, 0) is False  # plain prose
    assert wrapper.click(0, 6) is True  # inside the label
    assert md.chosen == "https://example.invalid"


def test_hover_at_forwards_the_childs_answer():
    child = _Marked("one", "two")
    wrapper = Delegate(child)
    assert wrapper.hover_at(1, 0) is True  # the mark moved: a repaint
    assert wrapper.hover_at(1, 0) is False  # the same cell: nothing moved
    assert wrapper.hover_at(-1, -1) is True  # the pointer left a marked row
    assert wrapper.hover_at(-1, -1) is False  # already clear


def test_hover_at_forwards_into_a_real_widget():
    md = Markdown("read [the docs](https://example.com) now")
    wrapper = Delegate(md)
    wrapper.render(80)
    assert wrapper.hover_at(0, 6) is True  # inside the label
    assert wrapper.hover_at(0, 0) is True  # off it: the mark cleared
    assert wrapper.hover_at(0, 0) is False  # already clear: nothing repainted


def test_the_wrapper_answers_every_protocol_surface_itself():
    wrapper = Delegate(Text("hi"))
    assert isinstance(wrapper, Component)
    assert isinstance(wrapper, Container)
    assert isinstance(wrapper, Revisioned)  # the method is here, child or not
    assert isinstance(wrapper, Clickable)


# --- the container door --------------------------------------------------------


@pytest.mark.parametrize("row, col", [(0, 0), (0, 7), (3, 0), (3, 7), (11, 11)])
def test_child_at_maps_every_cell_to_the_child_at_the_same_coordinates(row, col):
    child = _Stable("a", "b")
    wrapper = Delegate(child)
    assert wrapper.child_at(row, col) == (child, row, col)


def test_child_at_needs_no_render_first():
    # The transforming siblings answer over their last render's geometry and
    # decline before it; the identity has no geometry, so it never declines.
    child = _Stable("a", "b")
    assert Delegate(child).child_at(1, 1) == (child, 1, 1)
    assert Panel(child).child_at(1, 1) is None


def test_descend_walks_through_the_wrapper_to_the_leaf():
    leaf = _Marked("one", "two", "three")
    assert descend(Delegate(leaf), 2, 3) == (leaf, 2, 3)
    # Nesting composes: every layer is the identity, so the coordinates
    # survive all the way down.
    nested = Delegate(Delegate(Delegate(leaf)))
    assert descend(nested, 1, 5) == (leaf, 1, 5)


def test_the_wrapper_composes_with_a_transforming_sibling():
    framed = Panel(Text("x"), title="T")
    assert texts(Delegate(framed), 12) == texts(framed, 12)
    assert Delegate(framed).render(12) == framed.render(12)


def test_child_is_a_plain_attribute_a_host_can_swap():
    wrapper = Delegate(_Stable("one"))
    assert texts(wrapper, 10) == ["one"]
    wrapper.child = _Stable("two")
    assert texts(wrapper, 10) == ["two"]


# --- the three degradation rules -----------------------------------------------


def test_a_child_without_revision_answers_none():
    # ``None`` is the documented "memory off" answer, not a snapshot: the
    # wrapper has the method (so a Block calls it cacheable) and must not
    # invent a value for a child that never promised one.
    wrapper = Delegate(Rows("a", "b"))
    assert wrapper.revision() is None
    assert not isinstance(Rows("a"), Revisioned)


def test_a_block_around_a_revision_less_wrapper_stays_uncached():
    child = _Counting("a", "b")
    block = Block("w", Delegate(child))
    assert isinstance(block.component, Revisioned)  # the door: method presence
    assert block.revision() is None
    first = block.rows(30)
    assert block.rows(30) == first
    assert child.renders == 2  # no snapshot: an open block re-renders per call


def test_a_sealed_block_around_a_revision_less_wrapper_caches_by_width_alone():
    child = _Counting("a", "b")
    block = Block("w", Delegate(child))
    block.seal()
    block.rows(30)
    assert block.rows(30) == block.rows(30)
    assert child.renders == 1  # frozen content: the older rule, unchanged
    block.rows(20)
    assert child.renders == 2  # a new width still re-wraps


def test_a_child_without_click_declines():
    wrapper = Delegate(Rows("a", "b"))
    assert wrapper.click(0, 0) is False
    assert wrapper.click(-1, -1) is False  # the pointer left, and nothing moved


def test_a_child_without_hover_at_declines():
    wrapper = Delegate(Rows("a", "b"))
    assert wrapper.hover_at(0, 0) is False
    assert wrapper.hover_at(-1, -1) is False


def test_the_forwarded_snapshot_turns_the_blocks_cache_on():
    child = _Marked("one", "two")
    child.hover_at(0, 0)  # a snapshot to key on: ``None`` is the off switch
    block = Block("w", Delegate(child))
    first = block.rows(30)
    assert [row.text for row in first] == ["> one", "two"]
    # An unchanged snapshot: the second rows() call is served from the cache.
    assert block.rows(30) == first
    assert child.renders == 1
    child.hover_at(1, 0)  # the snapshot moves
    assert [row.text for row in block.rows(30)] == ["one", "> two"]
    assert child.renders == 2
    # And the forwarded ``None`` is honoured as the off switch it is: with no
    # snapshot the open block re-renders per call rather than cache a lie.
    child.hover_at(-1, -1)
    block.rows(30)
    block.rows(30)
    assert child.renders == 4


def test_a_sealed_blocks_hovered_child_repaints_through_the_wrapper():
    """The sealed-staleness rule: sealing freezes the content, not the
    snapshot, so the wrapper's forwarded ``revision`` is what carries a
    hover on a sealed block to the screen."""
    child = _Marked("one", "two")
    block = _sealed(Delegate(child))
    assert child.hover_at(0, 0) is True
    assert _fresh(block, child)
    assert [row.text for row in block.rows(30)] == ["> one", "two"]


def test_the_wrapper_never_proxies_the_controller_verbs():
    wrapper = Delegate(_Marked("one"))
    for name in ("handle", "move", "activate", "focused", "hover"):
        assert not hasattr(wrapper, name), name
    assert not isinstance(wrapper, Focusable)
    assert not isinstance(wrapper, Activable)
    assert not isinstance(wrapper, Hoverable)
    assert wrapper.__slots__ == ("child",)  # no state of its own, beyond the child
