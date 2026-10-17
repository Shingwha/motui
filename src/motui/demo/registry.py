"""The registry: the demo's page table -- the eleven categories, in rail order."""

from __future__ import annotations

from .page import Page
from .pages import (
    action,
    choice,
    chrome,
    content,
    data,
    feedback,
    input,
    layout,
    overview,
    streaming,
    styles,
)

__all__ = ["BY_NAME", "PAGES"]

#: The demo's pages, in rail order -- eleven categories, one idea each.
PAGES: tuple[Page, ...] = (
    Page("overview", "What this demo is, and a clickable index of its pages",
         overview.page),
    Page("content", "Text, Markdown and Diff -- the primitives that carry content",
         content.page),
    Page("data", "Table, List and Tree -- cursors, picks and the row under the pointer",
         data.page),
    Page("input", "Input, Editor and Autocomplete -- click a cell and the cursor lands",
         input.page),
    Page("choice", "Select, Confirm, Radio and Checkbox -- activate one and the echo answers",
         choice.page),
    Page("action", "Button, Link and Slider -- hover, click, and a pick for each",
         action.page),
    Page("layout", "Panel, Row, Column, Padding, Spacer, Divider, Collapsible and Notice",
         layout.page),
    Page("feedback", "ProgressBar, Spinner, StatusLine, Toasts and Tooltip",
         feedback.page),
    Page("chrome", "Panes, Scrollbar, Stats, Palette, selection and the hit-test probe",
         chrome.page),
    Page("styles", "A theme picker, the colors, the attributes -- pick one and the shell re-skins",
         styles.page),
    Page("streaming", "The Markdown fixture, streamed block by block",
         streaming.page),
)

#: The pages by authoritative name: the host's dispatch table and the rail's.
BY_NAME = {page.name: page for page in PAGES}
