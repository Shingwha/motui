"""The Workspace: the state owner for the document, frame, hit and selection."""

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


def test_the_workspace_owns_the_runtime_state():
    runtime = _runtime()
    workspace = runtime.workspace

    assert isinstance(workspace, Workspace)
    assert runtime.workspace is workspace  # one workspace per runtime
    assert workspace.document is not None
    assert workspace.viewport.document is workspace.document
    assert workspace.frame.pane("primary") is workspace.panes[0]
    assert workspace.panes[0].document is workspace.document
    assert isinstance(runtime.terminal, Terminal)
    assert runtime.terminal.screen is runtime.screen
    assert workspace.screen is runtime.screen
    assert workspace.painter is runtime.painter


def test_the_runtime_has_no_content_surface_left():
    runtime = _runtime()
    for name in (
        "add",
        "get",
        "remove",
        "system",
        "split",
        "dock",
        "undock",
        "frame",
        "document",
        "viewport",
        "selection",
        "set_selection",
        "hit",
        "hit_leaf",
        "reveal",
        "visible_range",
        "pane_at",
        "fill",
        "rows",
    ):
        assert not hasattr(runtime, name), name


def test_add_get_and_remove_answer_sections():
    workspace = _runtime().workspace

    section = workspace.add(Text("one"))
    assert section.id == "b0"
    assert section.widget.text == "one"
    assert workspace.get(section.id) is section
    assert [held.id for held in workspace.document.blocks()] == ["b0"]

    removed = workspace.remove(section.id)
    assert removed is section
    assert removed.widget.text == "one"
    assert workspace.document.blocks() == ()
    with pytest.raises(KeyError):
        workspace.get(section.id)


def test_fill_split_and_pane_own_the_state():
    workspace = _runtime().workspace

    section = workspace.fill(Text("fill"))
    assert section.id == workspace.document.blocks()[0].id
    assert workspace.document.fills() == (section,)

    left, right = workspace.split(Axis.X)
    assert [pane.id for pane in workspace.panes] == ["primary", "pane-1"]
    assert workspace.pane(right.id) is right
    assert workspace.frame.focused_pane is left
    assert left.document is workspace.document


def test_split_and_dock_accept_the_2_0_enums():
    workspace = _runtime().workspace

    left, right = workspace.split(Axis.X, weights=(2, 1))
    assert [pane.id for pane in workspace.panes] == ["primary", "pane-1"]
    assert left.rect.width > right.rect.width

    top = workspace.dock(Text("top"), placement=Placement.TOP)
    bottom = workspace.dock(Text("foot"), placement=Placement.BOTTOM)
    assert workspace.frame.dock("top") is top
    assert workspace.frame.dock("bottom") is bottom
    assert workspace.undock(Placement.BOTTOM) is bottom
    assert workspace.undock(Placement.TOP) is top


def test_dock_hit_and_reveal_are_workspace_operations():
    runtime = _runtime()
    workspace = runtime.workspace

    dock = workspace.dock(Text("foot"))
    assert workspace.frame.dock("bottom") is dock
    assert workspace.dock_region() is None  # no composition has run yet
    assert workspace.visible_range() is None  # nothing composed yet

    block = workspace.add(Text("hello"))
    runtime.paint()
    assert workspace.dock_region() is not None
    hit = workspace.hit(0, 0)
    assert hit is not None and hit.block.id == block.id
    assert workspace.hit_leaf(0, 0) is not None
    assert workspace.reveal(block.id, 0) is True
    assert len(workspace.rows) == runtime.screen.height

    assert workspace.undock() is dock
    assert workspace.frame.dock("bottom") is None


def test_selection_reads_and_writes_on_the_workspace():
    runtime = _runtime()
    workspace = runtime.workspace
    block = workspace.add(Text("alpha"))
    runtime.paint()

    selection = Selection.between((block.id, 0, 1), (block.id, 0, 3))
    workspace.set_selection(selection)
    assert workspace.selection is selection
    assert workspace.selection_pane is workspace.frame.focused_pane

    workspace.set_selection(None)
    assert workspace.selection is None


def test_the_private_delegates_live_on_the_workspace():
    workspace = _runtime().workspace
    block = workspace.add(Text("one"))

    assert workspace._next_block_id() == "b1"
    assert workspace._holder(block.id) is workspace.pane("primary")
    assert workspace._panes_holding(block.id) == (workspace.pane("primary"),)
    assert len(workspace._document_panes()) == 1
    assert workspace._content_pane(None) is workspace.pane("primary")
    assert workspace._focus_pane(None) is workspace.pane("primary")
    assert workspace._focused_viewport() is workspace.viewport
    assert workspace._focused_id() == "primary"
    assert workspace._pane_id("primary") == "primary"
    assert workspace._dock_height("bottom", 40, 6) == 0

    workspace._retile()
    workspace._set_selection(None, None)
    assert workspace.selection is None
    with pytest.raises(KeyError):
        workspace._holder("missing")


def test_the_workspace_exposes_the_runtime_seams_controllers_read():
    runtime = _runtime()
    workspace = runtime.workspace
    # The clock is a seam, not a wall-clock read: pin it so the two doors
    # cannot disagree by the microseconds between two monotonic() calls.
    runtime._clock = lambda: 42.0

    assert workspace.clock() == runtime.clock() == 42.0
    assert workspace.screen is runtime.screen
    assert workspace.painter is runtime.painter
    workspace.refresh()
    assert runtime._dirty is True  # noqa: SLF001 - the seam is the assertion
    assert workspace.copy_to_clipboard("copied") is True
