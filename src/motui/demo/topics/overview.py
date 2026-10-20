"""The overview section: one welcome topic with a live index."""

from __future__ import annotations

from motui import Markdown, Table

from ..stage import topic

_LAYER_ROWS = [
    ["kernel", "rows, styles, events, frame, selection", "motui.kernel"],
    ["keys", "bytes to events, keymaps", "motui.keys"],
    ["widgets", "the component library", "motui.widgets"],
    ["interaction", "focus, pointer, find, modals", "motui.interaction"],
    ["app", "TUI, docks, panes, the pump", "motui.app"],
]

_INDEX_ROWS = [
    ["Overview", "1", "welcome"],
    ["Components", "38", "text"],
    ["Interactions", "7", "focus"],
    ["Styling", "4", "theme tokens"],
    ["Patterns", "4", "streaming markdown"],
    ["Reference", "4", "API layers"],
]

_INTRO = """\
# motui

A full-screen TUI toolkit: five layers, one component protocol,
and a host that composes them.

```python
from motui import TUI, Button

tui = TUI(hover=True)
tui.add(Button("Ship"), id="ship")
tui.run()
```
"""


def _build(b) -> None:
    session = b.session
    intro = Markdown(_INTRO, theme=b.theme)
    layers = Table(["layer", "what it owns", "import"], _LAYER_ROWS)
    index = Table(
        ["section", "topics", "first topic"], _INDEX_ROWS, theme=b.theme
    )
    b.preview(intro, layers)
    b.add(index)
    b.focus(index)

    def note(report) -> None:
        if report.source is index:
            session.show_section(int(report.value))

    b.note(note)


TOPICS = (
    topic(
        key="welcome",
        title="Welcome",
        summary="A master-detail browser over motui's components, tiers and patterns.",
        group="Start",
        section="overview",
        try_line="click a section row or press c-1..c-6; c-n next topic; / opens the palette",
        api_line="python -m motui  \u00b7  python -m motui --pages  \u00b7  TUI + widgets + interaction",
        components=("Markdown", "Table"),
        build=_build,
    ),
)
