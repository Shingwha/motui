"""The features page: what the toolkit does beyond drawing rows.

The capability table's second column is an **action**, not a description --
press this, drag that, click there -- so every row is something a reader can
do on this very screen.  Below it, the three commands that run the showcase
with no terminal at all: the piped replay, the page dump, and the two gates
the library keeps over itself (the test suite and the render-hash bench).
The keymap tables moved out to the ``keys`` exhibit, and this page has no
:class:`~mocode_tui.focus.FocusRing`: nothing here takes the focus, so the
banner hint stays the shell's own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import Table, Text

from .page import PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["page"]

#: What the toolkit does, and the action that shows it on this screen.
CAPABILITIES = (
    ("panes", "press /split, then c-o: a second pane opens and the focus moves between the two"),
    ("scrollback", "roll the wheel over this page: the scrollbar tracks the pane under the pointer"),
    ("selection", "drag across these rows and release: the range is copied through OSC 52"),
    ("mouse", "click the tab strip above, or a row on the lists exhibit: a hit resolves to a widget"),
    ("IME anchor", "type in the composer: the terminal cursor parks on the text caret after every key"),
    ("streaming", "ask the chat page a question: the answer streams in chunk by chunk"),
    ("themes", "click a theme name on the styles exhibit: the shell and the page re-skin at once"),
)

#: The three commands that need no terminal -- and what each one is for.
NO_TERMINAL = (
    ("uv run python examples/demo.py < /dev/null",
     "replays the session headless, dumps the screen"),
    ("uv run python examples/demo.py --pages",
     "prints every exhibit as plain text"),
    ("uv run pytest -q \u00b7 uv run python tools/framebench.py",
     "the gates: the suite, and the render hash"),
)


def page(session: Showcase) -> PageBody:
    """The action table, the split/selection API, and the three commands."""
    theme = session.theme
    return PageBody([
        *header("features",
                "What the toolkit does beyond drawing rows -- every row below is an action "
                "you can take right here.", theme),
        try_line("press /split then c-o for a second pane; drag across any rows and release "
                 "to copy them", theme),
        section("capabilities -- press it and watch", theme),
        Table(["feature", "how to see it"], [list(row) for row in CAPABILITIES], theme=theme),
        api_note('tui.split("vertical", ratios=(2, 1)) -- the left pane keeps the document', theme),
        api_note("SelectionGesture(tui, on_end=...) -- release hands the range to the host", theme),
        section("no terminal needed -- three commands", theme),
        Table(["command", "what it is for"], [list(row) for row in NO_TERMINAL], theme=theme),
        Text("The piped run and the dump are the showcase's own smoke test: the script drives "
             "every exhibit through the same host loop a terminal does, so a page that fails "
             "to build fails the run.", style=theme.dim),
    ])  # no ring: this page has nothing to focus, so the shell keeps its own hint