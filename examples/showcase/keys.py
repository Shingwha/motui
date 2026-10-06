"""The keys page: the three shipped keymaps and the whole rebinding story.

A keymap is a plain ``dict`` of key name to editing method, and the three
that ship stack in that order: ``DEFAULT_INPUT_KEYMAP`` for the single-line
field, ``DEFAULT_EDITOR_KEYMAP`` for the multi-line one, and
``COMPOSER_KEYMAP`` for the chat footer.  The three tables ride one row --
the layers are parallel, so key by key they compare, and all three fit one
screen together.  Below them the whole rebinding story in two lines: a copy
of the table with one entry replaced (a rebind), or one entry dropped (the
key leaves the component and falls back to the host -- which is how the
composer's ``enter`` became the submit gesture; the Composer table simply
does not carry it).  The shell's own keys live outside every table, and the
closing note spells them out: they are the host's dispatch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import (
    Column,
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
    Row,
    Table,
    Text,
    Theme,
)
from mocode_tui.chat import COMPOSER_KEYMAP

from .page import PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["page"]

#: The three shipped keymaps, in the order the layers stack.
KEYMAPS = (
    ("Input", DEFAULT_INPUT_KEYMAP),
    ("Editor", DEFAULT_EDITOR_KEYMAP),
    ("Composer", COMPOSER_KEYMAP),
)


def _column(theme: Theme, title: str, keymap: dict) -> Column:
    """One keymap column: the layer's name, then its key -> action table."""
    return Column([
        Text(title, style=theme.accent),
        Table(["key", "action"],
              [[f'"{key}"', action] for key, action in keymap.items()],
              theme=theme),
    ])


def page(session: Showcase) -> PageBody:
    """The three keymap tables in a row, then the rebind and unbind lines."""
    theme = session.theme
    return PageBody([
        *header("keys & keymaps",
                "The three keymaps that ship, layer by layer -- and the one line "
                "that rebinds a key.", theme),
        try_line("read a table, then copy the rebind line below into your host: that "
                 "key is re-routed", theme),
        section("keymaps -- one table per layer, all three on one screen", theme),
        Row([_column(theme, title, keymap) for title, keymap in KEYMAPS], gap=3),
        api_note('field.keymap = {**DEFAULT_INPUT_KEYMAP, "c-j": "clear"}', theme),
        api_note("drop the entry instead and the key is unbound -- the host routes it itself", theme),
        Text("Input is the single-line field, Editor the multi-line one, and Composer the "
             "chat footer's table on top of the editor's: enter is simply not in it, which "
             "is what makes enter the host's submit gesture. The shell keeps its own keys "
             "outside every table -- c-n and c-p step to the next and previous exhibit, tab "
             "cycles the focused widget of the page, c-o switches the pane focus after "
             "/split, / opens the page menu and Ctrl-C quits.",
             style=theme.dim),
    ])