"""The features page: what the toolkit does beyond drawing rows.

A capability table (what it is, and how to see it) and the three keymap
tables, read straight off the library's own bindings -- a keymap is a plain
``dict`` of key name to editing method, which is the whole rebinding story.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import (
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
    Table,
    Text,
)
from mocode_tui.chat import COMPOSER_KEYMAP

from .page import PageBody, header, section

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["page"]

#: What the toolkit does, and the smallest way to see each one.
CAPABILITIES = (
    ("panes", "/split opens a second pane beside this one: the frame tiles, each pane scrolls on its own"),
    ("scrollback", "the right-hand scrollbar tracks this document; the wheel scrolls the pane under the pointer"),
    ("mouse", "click the widgets on component pages -- rows, tree nodes and tabs all answer a hit"),
    ("selection", "drag on this page: release copies the range through OSC 52 and the toast answers"),
    ("IME anchor", "the composer parks the terminal cursor at the text caret after every keypress"),
    ("streaming", "the chat page streams a canned Markdown reply chunk by chunk, invalidating per chunk"),
    ("headless", "python examples/demo.py < /dev/null replays every page and dumps the final screen"),
    ("themes", "styles resolve once, at construction; /theme rebuilds the shell and the current page"),
)

#: The three shipped keymaps, in the order the layers stack.
KEYMAPS = (
    ("Input", DEFAULT_INPUT_KEYMAP),
    ("Editor", DEFAULT_EDITOR_KEYMAP),
    ("Composer", COMPOSER_KEYMAP),
)


def page(session: Showcase) -> PageBody:
    """The capability list and the keymap tables."""
    theme = session.theme
    bindings = [[name, f'"{key}"', action]
                for name, table in KEYMAPS for key, action in table.items()]
    return PageBody([
        *header("features",
                "What the toolkit does beyond drawing rows -- the ones that say click or drag "
                "you can try right here.", theme),
        section("capabilities", theme),
        Table(["feature", "how to see it"], [list(row) for row in CAPABILITIES], theme=theme),
        section("keymaps -- the three shipped tables", theme),
        Table(["keymap", "key", "action"], bindings, theme=theme),
        Text("A keymap is a dict of key name -> editing method. A host rebinds one key with a copy "
             "({**DEFAULT_INPUT_KEYMAP, \"c-j\": \"clear\"}), or deletes the entry and routes the key "
             "itself -- which is how the composer's enter became the submit gesture.", style=theme.dim),
    ])
