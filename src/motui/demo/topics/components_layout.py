"""Layout topics: containers, framing, folding, spacing and scrolling."""

from __future__ import annotations

from motui import Button, Link, Text
from motui.widgets import (
    Collapsible,
    Column,
    Delegate,
    Divider,
    Padding,
    Panel,
    Row,
    ScrollView,
    Spacer,
)

from ..stage import topic

_LONG = Column([Text(f"row {index:02d}") for index in range(1, 21)], gap=0)


def _row_column(b) -> None:
    row = Row(
        [Text("left"), Text("middle"), Text("right")],
        widths=[8, 10, 8],
        gap=1,
    )
    flexible = Row([Text("one"), Text("two"), Text("three")], gap=2)
    b.preview(Column([row, Divider(max_width=40, theme=b.theme), flexible], gap=1))
    b.variants(
        ("fixed widths [8, 10, 8]", row),
        ("flexible, gap=2", flexible),
    )


def _padding_panel(b) -> None:
    padded = Padding(Text("one column of padding around the child"), left=1, right=1, top=1, bottom=1)
    panel = Panel(padded, title="padded", theme=b.theme)
    b.preview(panel)
    b.variants(
        ("Padding(left=2)", Padding(Text("inset"), left=2)),
        ("Panel(frame=False)", Panel(Text("no box, still padded"), frame=False)),
    )


def _divider(b) -> None:
    b.preview(
        Divider(theme=b.theme),
        Divider(label="section", max_width=40, theme=b.theme),
    )
    b.variants(
        ("capped max_width=30", Divider(label="capped", max_width=30, theme=b.theme)),
        ("char='='", Divider(char="=", max_width=30, theme=b.theme)),
    )


def _collapsible(b) -> None:
    fold = Collapsible("Details", Text("The body folds away under the title row."), open=True, theme=b.theme)
    closed = Collapsible("Closed", Text("body"), open=False, theme=b.theme)
    disabled = Collapsible("Disabled", Text("body"), disabled=True, theme=b.theme)
    b.preview(fold)
    b.variants(("open=False", closed), ("disabled", disabled))
    b.focus(fold)
    echo = b.echo("open")

    def note(report) -> None:
        if report.source is fold:
            echo.set(report.value)

    b.note(note)


def _spacer(b) -> None:
    b.preview(Column([Text("above"), Spacer(2), Text("below")], gap=0))
    b.variants(
        ("Spacer(1)", Column([Text("above"), Spacer(1), Text("below")])),
        ("Spacer(4)", Column([Text("above"), Spacer(4), Text("below")])),
    )


def _scroll_view(b) -> None:
    content = Column([Text(f"row {index:02d}") for index in range(1, 21)])
    view = ScrollView(content, height=6, scrollbar=True, theme=b.theme)
    short = ScrollView(
        Column([Text(f"row {index:02d}") for index in range(1, 9)]),
        height=4,
        theme=b.theme,
    )
    b.preview(view)
    b.variants(("height=4, no bar", short), ("offset=5", ScrollView(content, height=4, offset=5, theme=b.theme)))
    b.focus(view)


def _delegate(b) -> None:
    button = Button("Wrapped Button", theme=b.theme)
    button.hint = "the Delegate forwards the click"
    wrapped = Delegate(button)
    link = Link("wrapped link", theme=b.theme)
    link.hint = "hover works through the wrapper"
    b.preview(wrapped)
    b.variants(("Delegate(Link)", Delegate(link)), ("nested delegates", Delegate(Delegate(Text("one child, twice wrapped")))))
    b.focus(button)
    echo = b.echo("clicked")

    def note(report) -> None:
        if report.source is button:
            echo.set(report.value)

    b.note(note)


TOPICS = (
    topic(
        key="row-column",
        title="Row / Column",
        summary="The two layout containers: side-by-side columns and stacked rows with gaps.",
        group="Layout",
        section="components",
        try_line="none -- containers route cells, they never take focus",
        api_line="Row(children, *, widths, gap=1) \u00b7 Column(children, *, gap=0) \u00b7 child_at(row, col)",
        components=("Row", "Column"),
        build=_row_column,
    ),
    topic(
        key="padding-panel",
        title="Padding / Panel",
        summary="Whitespace around a child and the single-line box that frames one.",
        group="Layout",
        section="components",
        try_line="none -- both are pure containers; clicks descend to the child",
        api_line="Padding(child, *, left, right, top, bottom) · Panel(child, *, title, frame)",
        components=("Padding", "Panel"),
        build=_padding_panel,
    ),
    topic(
        key="divider",
        title="Divider",
        summary="A repeated-character rule, optionally labelled and capped.",
        group="Layout",
        section="components",
        try_line="none -- a divider is content; max_width caps its span",
        api_line="Divider(*, char='\u2500', style, label='', label_style, max_width, theme)",
        components=("Divider",),
        build=_divider,
    ),
    topic(
        key="collapsible",
        title="Collapsible",
        summary="A title row that folds its body away; the new state is the result.",
        group="Layout",
        section="components",
        try_line="enter or click folds the focused section; the state lands below",
        api_line="Collapsible(title, body, *, open, disabled) · activate() · take_result()",
        components=("Collapsible",),
        build=_collapsible,
    ),
    topic(
        key="spacer",
        title="Spacer",
        summary="Blank rows as a component: an explicit vertical gap between blocks.",
        group="Layout",
        section="components",
        try_line="none -- the variants show Spacer(1) and Spacer(4) between the same rows",
        api_line="Spacer(rows=1) \u00b7 render(width) returns exactly that many blank rows",
        components=("Spacer",),
        build=_spacer,
    ),
    topic(
        key="scroll-view",
        title="Scroll view",
        summary="A fixed-height window over any child, with optional scrollbar and wheel keys.",
        group="Layout",
        section="components",
        try_line="up/down scroll a row; page_up/page_down a window; home/end the edges",
        api_line="ScrollView(child, *, height, offset, scrollbar, glyphs, theme) \u00b7 scroll_up/down/reveal",
        components=("ScrollView",),
        build=_scroll_view,
    ),
    topic(
        key="delegate",
        title="Delegate",
        summary="The identity wrapper: render, click, hover and child_at forwarded unchanged.",
        group="Layout",
        section="components",
        try_line="enter or click the wrapped button; hover reads its hint through the wrapper",
        api_line="Delegate(child) \u00b7 forwards render/revision/click/hover_at/child_at only",
        components=("Delegate", "Button", "Link"),
        build=_delegate,
    ),
)
