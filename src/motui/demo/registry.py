"""The registry: the demo's page table -- the ten families, in rail order."""

from __future__ import annotations

from .page import Page
from .pages import (
    actions,
    forms,
    layout,
    modals,
    overview,
    shell,
    streaming,
    text,
    themes,
    views,
)

__all__ = ["BY_NAME", "PAGES"]

#: The demo's pages, in rail order -- ten families, one idea each.  The hint
#: rows are the page's own keys for the bottom band (the session appends its
#: global ones); W3 hands them to the bar, so the data lives here meanwhile.
PAGES: tuple[Page, ...] = (
    Page("overview", "What this demo is, and a clickable index of its pages",
         overview.page,
         hints=(("enter", "open the page"),)),
    Page("text", "Text, Markdown, Diff and Spacer -- the primitives that carry content",
         text.page,
         hints=(("click", "a task box flips"),)),
    Page("layout", "Panel, Row, Column, Padding, Spacer, Divider, Collapsible, Notice "
         "and StatusLine",
         layout.page,
         hints=(("enter", "fold the Collapsible"),)),
    Page("actions", "Button, Link, Checkbox and Slider -- hover, click, and a pick for each",
         actions.page,
         hints=(("enter", "take the action"), ("\u2190 / \u2192", "step the Slider"))),
    Page("forms", "Input, Editor, ComboBox, Autocomplete, Select, Radio and CheckGroup -- "
         "the fields and the menus",
         forms.page,
         hints=(("\u2191 / \u2193", "move the cursor"), ("enter", "take the row"))),
    Page("views", "Table, List and Tree -- cursors, marks and the row under the pointer",
         views.page,
         hints=(("space", "mark the cursor row"), ("c-t", "filter the tree"))),
    Page("modals", "Dialog, Modal and Palette -- a confirm, a prompt, the scrim and a "
         "command row",
         modals.page,
         hints=(("enter", "open the panel"), ("escape", "cancel"))),
    Page("shell", "Panes, Scrollbar, Stats, Toasts, Tooltip, Find, selection and the "
         "hit-test probe",
         shell.page,
         hints=(("c-o", "pane"), ("c-g", "stats"))),
    Page("themes", "A theme picker, the colors, the attributes -- pick one and the shell re-skins",
         themes.page,
         hints=(("enter", "re-skin the shell"),)),
    Page("streaming", "The Markdown fixture, streamed block by block",
         streaming.page,
         hints=(("enter", "run the control bar"),)),
)

#: The pages by authoritative name: the host's dispatch table and the rail's.
BY_NAME = {page.name: page for page in PAGES}
