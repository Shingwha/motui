"""The Workspace: the state owner for the document, frame, hit and selection."""

from __future__ import annotations

from motui.app import Runtime, Workspace
from motui.kernel import Selection
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
    runtime.paint()
    assert workspace.copy_to_clipboard("copied") is True
