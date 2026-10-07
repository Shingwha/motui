"""The workspace exhibit: a chat on the left, a tabbed inspector on the right.

The page is a **layout** rather than a list of rows.  The transcript -- the
page's own blocks, on the main document -- is a canned working session
(``Message`` turns, a ``ToolBlock`` running the suite, an ``EditBlock``
landing the change), and beside it the page opens a right pane of its own
through :attr:`~showcase.page.PageBody.aside`: a four-label ``Tabs`` strip
pinned at the pane's top (``tools / edits / reads / agent``) and **one**
content block below it, swapped as the strip moves.

The four views are factories of the theme, kept in :data:`VIEWS` by tab
name: a tool call with its whole output (``tools``), a small diff
(``edits``), a real excerpt from ``src/mocode_tui/focus.py`` rendered by
``Markdown``'s python fence (``reads``), and the subagent report
(``agent``) -- a ``Column`` of the chat layer's own ``Message`` and
``ToolBlock``, canned this wave.  That column is the extension point: a
host growing it live appends a message and invalidates the frame, the
same road the chat layer's transcript takes.

The right pane is the page's own: the host opens it from
:meth:`~showcase.session.Showcase.show` and closes it when the page is
left, so ``/split`` -- which shares that one slot -- yields on this page
with a toast instead of stacking a third pane.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from mocode_tui import (
    Column,
    Component,
    EditBlock,
    FocusRing,
    Markdown,
    Message,
    Pane,
    Tabs,
    ToolBlock,
    Theme,
)

from .page import PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["NAMES", "VIEWS", "Inspector", "page"]

#: The inspector's tab labels, in order -- short on purpose, so the whole
#: strip renders inside the right pane's 37 columns without truncation (a
#: truncated label cannot be clicked).
NAMES: tuple[str, ...] = ("tools", "edits", "reads", "agent")

#: The tools view's body: one run, its whole output -- the narrow rows a
#: 37-column pane can hold without wrapping.
TOOL_OUTPUT: tuple[str, ...] = (
    "collected 949 items",
    "",
    "948 passed, 1 skipped in 4.60s",
    "",
    "1 skipped: no pty in this harness",
    "probe: 2 panes on, 1 after",
    "probe: /split toasts, slot taken",
    "probe: click 'reads' -> new view",
    "probe: offset 0 after the swap",
)


#: The reads view: a real excerpt from ``src/mocode_tui/focus.py`` -- the
#: focus move and the one-line flag rewrite -- kept to the narrow rows the
#: right pane can hold without wrapping (35 columns at most here).
READS_SNIPPET = '''\
```python
# focus.py -- FocusRing.focus()
if not self._registered(target):
    return False
self._set_focused(target)
return True

# the flags, rewritten in one move
self._focused = target
for known in self._targets:
    known.focused = known is target
```
'''


def _tools_view(theme: Theme) -> Component:
    """The ``tools`` view: one command and its output, the whole call."""
    return ToolBlock(
        "$ uv run pytest -q",
        TOOL_OUTPUT,
        tone="tool",
        footer="Took 4.6s",
        theme=theme,
    )


def _edits_view(theme: Theme) -> Component:
    """The ``edits`` view: the diff the conversation produced.

    A small one, in the layer's own voice: the hook changed from comparing
    a cached index to reading the strip -- which is the road this page's
    ``sync`` actually takes.
    """
    return EditBlock(
        "examples/showcase/workspace.py",
        context=["def sync(self) -> None:"],
        removed=["    if index == self.index:"],
        added=["    index = self.strip.active", "    self._swap(index)"],
        theme=theme,
    )


def _reads_view(theme: Theme) -> Component:
    """The ``reads`` view: a file's body, syntax-highlighted by the fence.

    The text is :data:`READS_SNIPPET` -- ``Markdown``'s python fence is the
    highlighter, so the view costs one component and no new renderer.
    """
    return Markdown(READS_SNIPPET, theme=theme)


def _agent_view(theme: Theme) -> Component:
    """The ``agent`` view: a subagent's report, canned for this wave.

    The same ``Message``/``ToolBlock`` components the chat layer and the
    transcript beside it use -- the view is the one place a live host would
    append to (append to the column's children, invalidate, repaint).
    """
    return Column([
        Message("thinking", "subagent: reading the frame layer before answering\u2026",
                theme=theme),
        ToolBlock("read src/mocode_tui/core/frame.py",
                  ["Pane.split -> children", "Pane.close -> collapse"],
                  tone="code", theme=theme),
        Message("assistant",
                "The right pane is a leaf: split once, close it on the way out.",
                theme=theme),
        ToolBlock("$ uv run pytest tests/test_frame.py -q", ["34 passed in 0.31s"],
                  tone="tool", footer="Took 0.3s", theme=theme),
        Message("assistant", "Report filed: the pane is a leaf, closed on the "
                "way out -- the rest is routing.", theme=theme),
    ])


#: The inspector's views, by tab name -- each a factory of the theme, so a
#: swap builds fresh components on the theme in force.  This dict is the
#: view seam: the handler for one name is replaced without touching the
#: strip, the swap or the page.
VIEWS: dict[str, Callable[[Theme], Component]] = {
    "tools": _tools_view,
    "edits": _edits_view,
    "reads": _reads_view,
    "agent": _agent_view,
}


class Inspector:
    """The right pane's controller: the strip and the content block.

    ``strip`` is the pane's only interactive widget -- the page's
    :class:`~mocode_tui.focus.FocusRing` holds exactly it -- and the host
    hands the controller's :meth:`mount` to
    :attr:`~showcase.page.PageBody.aside`.  The controller is built before
    the pane exists (the ring needs the strip at construction) and is
    filled in by ``mount`` when the host's ``show`` opens the pane.
    """

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self.strip = Tabs(list(NAMES), theme=theme)
        self.index = 0
        self.view: Component = VIEWS[NAMES[0]](theme)
        self.pane: Pane | None = None
        self.block_id: str | None = None

    def mount(self, pane: Pane) -> None:
        """Fill the pane the host opened: the strip pinned, one content block.

        The strip goes in first with ``pin="top"`` so it holds the pane's
        first row while the content scrolls under it; the content block
        below it is the current view.
        """
        self.pane = pane
        pane.document.add(self.strip, pin="top")
        self.block_id = pane.document.add(self.content()).id

    def content(self) -> Component:
        """The one content block: the current view."""
        return self.view


def page(session: Showcase) -> PageBody:
    """The transcript, the inspector, and the wiring between them."""
    theme = session.theme
    inspector = Inspector(theme)
    return PageBody(
        [
            *header("workspace",
                    "A chat beside an inspector: the transcript scrolls on the left, "
                    "the tabs on the right switch one view at a time.", theme),
            try_line("click a tab on the right -- or press tab, then \u2190\u2192 -- to "
                     "switch the inspector's view", theme),
            section("the transcript", theme),
            Message("user", "Run the suite, then wire the aside into session.show().",
                    theme=theme),
            Message("thinking", "Plan: run pytest, read show()'s order, then open the "
                     "right pane after the blocks mount\u2026", theme=theme),
            ToolBlock("$ uv run pytest -q", TOOL_OUTPUT, tone="tool", footer="Took 4.6s",
                      theme=theme),
            EditBlock(
                "examples/showcase/session.py",
                context=["self.body = page.build(self)"],
                removed=["self.main.focus()"],
                added=["self._open_aside()", "self.main.focus()"],
                theme=theme,
            ),
            Message("assistant",
                    "Green. show() now closes the previous aside first, mounts the blocks, "
                    "then opens this page's pane -- and /split steps aside while it is open.",
                    theme=theme),
            api_note("PageBody.aside -> pane; PageBody.sync -> document.remove/add + "
                     "scroll_up", theme),
        ],
        focus=FocusRing([inspector.strip]),
        hint="inspector tabs",
        aside=inspector.mount,
    )
