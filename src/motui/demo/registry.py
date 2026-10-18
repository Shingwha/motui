"""The registry: the demo's page table -- the ten families and the manual, in rail order."""

from __future__ import annotations

from .page import Page
from .pages import (
    actions,
    forms,
    layout,
    modals,
    notes,
    overview,
    shell,
    streaming,
    text,
    themes,
    views,
)

__all__ = ["BY_NAME", "GROUPS", "PAGES"]

#: The demo's pages, in rail order -- ten families and the manual that reads
#: them, each page carrying its own rail group.  The hint rows are the page's
#: own keys for the bottom band, read on every switch (``Session.show``): the
#: page's rows first, the session's global ones after.
PAGES: tuple[Page, ...] = (
    Page("overview", "What this demo is, and a clickable index of its pages",
         overview.page,
         hints=(("enter", "open the page"),),
         group="FOUNDATIONS"),
    Page("text", "Text, Markdown, Diff and Spacer -- the primitives that carry content",
         text.page,
         hints=(("click", "a task box flips"),),
         group="FOUNDATIONS"),
    Page("layout", "Panel, Row, Column, Padding, Spacer, Divider, Collapsible, Notice "
         "and StatusLine",
         layout.page,
         hints=(("enter", "fold the Collapsible"),),
         group="FOUNDATIONS"),
    Page("actions", "Button, Link, Checkbox and Slider -- hover, click, and a pick for each",
         actions.page,
         hints=(("enter", "take the action"), ("\u2190 / \u2192", "step the Slider")),
         group="COMPONENTS"),
    Page("forms", "Input, Editor, ComboBox, Autocomplete, Select, Radio and CheckGroup -- "
         "the fields and the menus",
         forms.page,
         hints=(("\u2191 / \u2193", "move the cursor"), ("enter", "take the row")),
         group="COMPONENTS"),
    Page("views", "Table, List and Tree -- cursors, marks and the row under the pointer",
         views.page,
         hints=(("space", "mark the cursor row"), ("c-t", "filter the tree")),
         group="COMPONENTS"),
    Page("modals", "Dialog, Modal and Palette -- a confirm, a prompt, the scrim and a "
         "command row",
         modals.page,
         hints=(("enter", "open the panel"), ("escape", "cancel")),
         group="COMPONENTS"),
    Page("shell", "Panes, Scrollbar, Stats, Toasts, Tooltip, Find, selection and the "
         "hit-test probe",
         shell.page,
         hints=(("c-o", "pane"), ("c-g", "stats")),
         group="SHELL"),
    Page("themes", "A theme picker, the colors, the attributes -- pick one and the shell re-skins",
         themes.page,
         hints=(("enter", "re-skin the shell"),),
         group="SHELL"),
    Page("streaming", "The Markdown fixture, streamed block by block",
         streaming.page,
         hints=(("enter", "run the control bar"),),
         group="SHELL"),
    Page("notes", "How to read this demo: the rail, the keys, the mouse, the pages and "
         "the headless roads",
         notes.page,
         hints=(("wheel", "scroll the rest of it"),),
         group="SHELL"),
)

#: The rail's group rows, derived from the pages' own ``group`` field: one
#: ``(position, label)`` per contiguous run, the position being the first
#: page index of the run (``NavList.groups`` reads it).  One source, no
#: index to drift: the rail, the index's group column and any later reader
#: all spell the groups from ``PAGES``.
GROUPS: tuple[tuple[int, str], ...] = tuple(
    (index, page.group)
    for index, page in enumerate(PAGES)
    if page.group and (index == 0 or PAGES[index - 1].group != page.group)
)

#: The pages by authoritative name: the host's dispatch table and the rail's.
BY_NAME = {page.name: page for page in PAGES}
