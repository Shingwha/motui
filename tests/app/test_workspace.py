"""The Workspace facade: the runtime's document/frame/hit/selection surface."""

from __future__ import annotations

import pytest

from motui.app import Runtime, Workspace
from motui.kernel import Selection
from motui.kernel.document import Placement
from motui.kernel.geom import Axis
from motui.terminal import HeadlessScreen, Terminal, TerminalOptions
from motui.widgets.text import Text


def _runtime(width: int = 40, height: int = 6) -> Runtime:
    return Runtime(
        Terminal(TerminalOptions(screen=HeadlessScreen(width, height))),
        interactive=False,
    )


def test_the_facade_reads_the_runtime_it_was_made_from():
    runtime = _runtime()
    workspace = runtime.workspace

    assert isinstance(workspace, Workspace)
    assert workspace.document is runtime.document
    assert workspace.viewport is runtime.viewport
    assert workspace.frame is runtime.frame
    assert workspace.panes == runtime.frame.panes
    assert runtime.workspace is workspace  # cached, one facade per runtime
    assert isinstance(runtime.terminal, Terminal)
    assert runtime.terminal.screen is runtime.screen


def test_add_get_and_remove_delegate_to_the_runtime():
    runtime = _runtime()
    workspace = runtime.workspace

    section = workspace.add(Text("one"))
    assert section.id == "b0"
    assert section.widget.text == "one"
    assert runtime.get(section.id).text == "one"
    assert workspace.get(section.id) is section
    assert workspace.document is runtime.document
    assert [held.id for held in workspace.document.blocks()] == ["b0"]

    removed = workspace.remove(section.id)
    assert removed is section
    assert removed.widget.text == "one"
    assert workspace.document.blocks() == ()
    with pytest.raises(KeyError):
        workspace.get(section.id)


def test_fill_split_and_pane_delegate_to_the_runtime():
    runtime = _runtime()
    workspace = runtime.workspace

    section = workspace.fill(Text("fill"))
    assert section.id == runtime.document.blocks()[0].id
    assert runtime.document.fills() == (section,)

    left, right = workspace.split("vertical")
    assert [pane.id for pane in workspace.panes] == ["primary", "pane-1"]
    assert workspace.pane(right.id) is right
    assert workspace.frame.focused_pane is left
    assert left.document is runtime.document


def test_split_and_dock_accept_the_2_0_enums():
    runtime = _runtime()
    workspace = runtime.workspace

    left, right = workspace.split(Axis.X, weights=(2, 1))
    assert [pane.id for pane in workspace.panes] == ["primary", "pane-1"]
    assert left.rect.width > right.rect.width

    top = workspace.dock(Text("top"), placement=Placement.TOP)
    bottom = workspace.dock(Text("foot"), placement=Placement.BOTTOM)
    assert workspace.frame.dock("top") is top
    assert workspace.frame.dock("bottom") is bottom
    assert workspace.undock(Placement.BOTTOM) is bottom
    assert workspace.undock(Placement.TOP) is top


def test_dock_hit_and_reveal_delegate_to_the_runtime():
    runtime = _runtime()
    workspace = runtime.workspace

    dock = workspace.dock(Text("foot"))
    assert workspace.frame.dock("bottom") is dock
    assert workspace.dock_region() == runtime.dock_region()
    assert workspace.visible_range() == runtime.visible_range()

    block = workspace.add(Text("hello"))
    runtime.paint()
    hit = workspace.hit(0, 0)
    assert hit is not None and hit.block.id == block.id
    assert workspace.hit_leaf(0, 0) == runtime.hit_leaf(0, 0)
    assert workspace.reveal(block.id, 0) is True

    assert workspace.undock() is dock
    assert workspace.frame.dock("bottom") is None


def test_selection_reads_and_writes_through_the_facade():
    runtime = _runtime()
    workspace = runtime.workspace
    block = workspace.add(Text("alpha"))
    runtime.paint()

    selection = Selection.between((block.id, 0, 1), (block.id, 0, 3))
    workspace.set_selection(selection)
    assert workspace.selection is selection
    assert runtime.selection is selection
    assert workspace.selection_pane is runtime.frame.focused_pane

    workspace.set_selection(None)
    assert workspace.selection is None
    assert runtime.selection is None


def test_the_private_delegates_reach_the_same_state():
    runtime = _runtime()
    workspace = runtime.workspace
    block = workspace.add(Text("one"))

    assert workspace._next_block_id() == runtime._next_block_id() == "b1"
    assert workspace._holder(block.id) is runtime._holder(block.id)
    assert workspace._panes_holding(block.id) == runtime._panes_holding(block.id)
    assert workspace._document_panes() == runtime._document_panes()
    assert workspace._content_pane(None) is runtime._content_pane(None)
    assert workspace._focus_pane(None) is runtime._focus_pane(None)
    assert workspace._focused_viewport() is runtime._focused_viewport()
    assert workspace._focused_id() == runtime._focused_id()
    assert workspace._pane_id("primary") == runtime._pane_id("primary")
    assert workspace._dock_height("bottom", 40, 6) == runtime._dock_height(
        "bottom", 40, 6
    )

    workspace._retile()
    workspace._set_selection(None, None)
    assert workspace.selection is None
    with pytest.raises(KeyError):
        workspace._holder("missing")
