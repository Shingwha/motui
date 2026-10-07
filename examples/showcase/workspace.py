"""The workspace exhibit: a chat on the left, a tabbed inspector on the right.

The page is a **layout** rather than a list of rows.  The transcript -- the
page's own blocks, on the main document -- is a canned working session
(``Message`` turns, a ``ToolBlock`` running the suite, an ``EditBlock``
landing the change), and beside it the page opens a right pane of its own
through :attr:`~showcase.page.PageBody.aside`: a four-label ``Tabs`` strip
pinned at the pane's top (``tools / edits / reads / agent``) and **one**
content block below it, swapped as the strip moves.

The right pane is the page's own: the host opens it from
:meth:`~showcase.session.Showcase.show` and closes it when the page is
left, so ``/split`` -- which shares that one slot -- yields on this page
with a toast instead of stacking a third pane.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import (
    Component,
    EditBlock,
    FocusRing,
    Message,
    Pane,
    Tabs,
    ToolBlock,
    Theme,
)

from .page import PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["NAMES", "Inspector", "page"]

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


def _tools_view(theme: Theme) -> Component:
    """The ``tools`` view: one command and its output, the whole call."""
    return ToolBlock(
        "$ uv run pytest -q",
        TOOL_OUTPUT,
        tone="tool",
        footer="Took 4.6s",
        theme=theme,
    )


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
        self.view: Component = _tools_view(theme)
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
