"""The stage: the topic template, the echo line and the object walk.

Every topic is built through :class:`TopicBuilder`, which enforces the one
template the browser uses:

1. a title row (accent);
2. a one-line summary (dim, at most :data:`SUMMARY_LIMIT` cells);
3. a ``Divider`` rule;
4. a ``Panel(title="preview")`` holding the live component(s);
5. an optional ``Panel(title="variants")`` of two or three captioned
   configurations;
6. optional extra blocks (a reference table, an index);
7. a ``Text("Try: ...")`` row;
8. a ``Text("API: ...")`` row;
9. an optional :class:`Echo` line.

A topic may mount at most :data:`MAX_BLOCKS` blocks.  A topic that needs
more is too broad: split it instead of writing prose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motui import Option, Text, Theme
from motui.app import FocusManager
from motui.kernel import Component, Constraints, Line, Surface
from motui.kernel.text import visible_width
from motui.widgets import Column, Divider, Panel

from .model import Report, Topic, TopicBody

if TYPE_CHECKING:  # pragma: no cover - type-only
    from .session import Session

__all__ = [
    "Echo",
    "MAX_BLOCKS",
    "SUMMARY_LIMIT",
    "TopicBuilder",
    "display",
    "topic",
    "walk_objects",
]

#: The template's hard ceiling: title, summary, rule, preview, variants,
#: try, API and one echo line.
MAX_BLOCKS = 8

#: The summary is one row; longer text is rejected at build time.
SUMMARY_LIMIT = 100


def display(value: object) -> str:
    """One pick as the inspector and the echo line spell it."""
    if isinstance(value, Option):
        return display(value.value if value.value is not None else value.label)
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key}={display(item)}" for key, item in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return ", ".join(display(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "none"
    return str(value)


class Echo:
    """The optional last-pick line: empty until the topic writes it.

    An empty echo renders no rows at all, so the golden frame of a fresh
    topic is exactly the template's eight blocks; the session's generic
    read calls the body's ``note`` hook, and the topic sets the line.
    """

    __slots__ = ("_line", "label")

    def __init__(self, theme: Theme, label: str = "last") -> None:
        self.label = label
        self._line = Text("", style=theme.text.faint)

    @property
    def text(self) -> str:
        return self._line.text

    def set(self, value: object, label: str | None = None) -> None:
        prefix = self.label if label is None else label
        self._line.text = f"{prefix}: {display(value)}"

    def clear(self) -> None:
        self._line.text = ""

    def render(self, c: Constraints) -> Surface:
        if not self._line.text:
            return Surface(width=c.width, rows=())
        return self._line.render(c)

    def __repr__(self) -> str:
        return f"Echo({self.label!r}, text={self._line.text!r})"


class TopicBuilder:
    """Build one topic through the fixed template.

    The builder owns the theme, the block list, the focus targets, the
    optional modal, the tick hook and the note chain.  Topic modules call
    :meth:`preview`, :meth:`variants` and :meth:`add` for content and
    :meth:`focus`, :meth:`modal`, :meth:`tick`, :meth:`note` and
    :meth:`echo` for behavior; :meth:`build` closes the body.
    """

    __slots__ = (
        "_blocks",
        "_echo",
        "_focus",
        "_modal",
        "_notes",
        "_overlays",
        "_previewed",
        "_tick",
        "session",
        "theme",
        "topic",
    )

    def __init__(self, session: "Session", topic: Topic) -> None:
        self.session = session
        self.topic = topic
        self.theme = session.theme
        self._blocks: list[Component] = []
        self._focus: list[Component] = []
        self._notes: list = []
        self._overlays: list[object] = []
        self._modal: object | None = None
        self._tick = None
        self._echo: Echo | None = None
        self._previewed = False

    # -- content ----------------------------------------------------------------

    def preview(self, *children: Component, title: str = "preview") -> Panel:
        """Mount the preview panel: one child, or a column of same-kind peers."""
        if not children:
            raise ValueError(f"{self.topic.key}: a topic needs a preview")
        child = children[0] if len(children) == 1 else Column(children, gap=1)
        panel = Panel(child, title=title, theme=self.theme)
        self._blocks.append(panel)
        self._previewed = True
        return panel

    def variants(self, *items: tuple[str, Component]) -> Panel:
        """Mount two or three captioned configurations as the variants panel."""
        if not 1 <= len(items) <= 3:
            raise ValueError(f"{self.topic.key}: variants take 1-3 configurations")
        rows: list[Component] = []
        for caption, component in items:
            rows.append(Text(caption, style=self.theme.text.faint))
            rows.append(component)
        panel = Panel(Column(rows, gap=0), title="variants", theme=self.theme)
        self._blocks.append(panel)
        return panel

    def add(self, *blocks: Component) -> None:
        """Mount extra blocks between the variants and the Try line."""
        self._blocks.extend(blocks)

    def focus(self, *components: Component) -> None:
        """Register keyboard targets, in tab order."""
        self._focus.extend(components)

    def modal(self, controller: object) -> object:
        """Register a modal controller and make it the topic's active panel."""
        self._modal = controller
        self._overlays.append(controller)
        return controller

    def controller(self, controller: object) -> object:
        """Register a controller for cleanup without making it active."""
        self._overlays.append(controller)
        return controller

    def tick(self, fn) -> None:
        self._tick = fn

    def note(self, fn) -> None:
        """Append one hook to the body's report chain."""
        self._notes.append(fn)

    def echo(self, label: str = "last") -> Echo:
        """Mount (at most) one optional last-pick line."""
        if self._echo is not None:
            raise ValueError(f"{self.topic.key}: one echo per topic")
        self._echo = Echo(self.theme, label)
        return self._echo

    # -- build ------------------------------------------------------------------

    def build(self) -> TopicBody:
        """Close the template into the value the session mounts."""
        if not self._previewed:
            raise ValueError(f"{self.topic.key}: every topic needs a preview panel")
        if visible_width(self.topic.summary) > SUMMARY_LIMIT:
            raise ValueError(f"{self.topic.key}: summary exceeds {SUMMARY_LIMIT} cells")
        head: list[Component] = [
            Text(self.topic.title, style=self.theme.content.accent),
            Text(self.topic.summary, style=self.theme.text.faint),
            Divider(theme=self.theme),
        ]
        tail: list[Component] = [
            Text(f"Try: {self.topic.try_line}", style=self.theme.text.faint),
            Text(f"API: {self.topic.api_line}", style=self.theme.text.faint),
        ]
        echo = [] if self._echo is None else [self._echo]
        blocks = [*head, *self._blocks, *tail, *echo]
        if len(blocks) > MAX_BLOCKS:
            raise ValueError(
                f"{self.topic.key}: {len(blocks)} blocks exceeds the {MAX_BLOCKS}-block ceiling"
            )
        note = self._note if self._notes else None
        focus = FocusManager(self._focus) if self._focus else None
        return TopicBody(
            blocks=blocks,
            focus=focus,
            modal=self._modal,
            tick=self._tick,
            note=note,
            overlays=tuple(self._overlays),
        )

    def _note(self, report: Report) -> None:
        if self._echo is not None:
            self._echo.set(report.value)
        for hook in self._notes:
            hook(report)


def topic(
    *,
    key: str,
    title: str,
    summary: str,
    group: str,
    section: str,
    try_line: str,
    api_line: str,
    components: tuple[str, ...],
    build,
) -> Topic:
    """Declare one topic whose body is built by ``build(TopicBuilder)``.

    The value is built before the callback runs, so the callback can read
    the topic's own title/summary through :class:`TopicBuilder` without a
    module-level forward reference.
    """
    value = Topic(
        key=key,
        title=title,
        summary=summary,
        group=group,
        section=section,
        build=lambda session: None,
        try_line=try_line,
        api_line=api_line,
        components=components,
    )

    def builder(session: "Session") -> TopicBody:
        stage = TopicBuilder(session, value)
        build(stage)
        return stage.build()

    return Topic(
        key=key,
        title=title,
        summary=summary,
        group=group,
        section=section,
        build=builder,
        try_line=try_line,
        api_line=api_line,
        components=components,
    )


def walk_objects(root: object) -> list[object]:
    """Every component and value object reachable from ``root``, once each.

    The demo's own structural walk: it follows the containers' public (and
    one form's private) child seats, so the session's generic
    ``take()`` scan and the coverage test see nested widgets, not
    only the stage's top-level blocks.  It is deliberately shallow about
    data: options, tree nodes, button specs and row bands are values, not
    containers.
    """
    out: list[object] = []
    seen: set[int] = set()

    def visit(obj: object | None) -> None:
        if obj is None or id(obj) in seen:
            return
        seen.add(id(obj))
        out.append(obj)
        for attr in ("children", "root_nodes", "options", "_fields", "_specs", "_buttons"):
            children = getattr(obj, attr, None)
            if isinstance(children, (list, tuple)):
                for child in children:
                    if attr == "_fields":
                        visit(child)  # the Field value and the component it wraps
                        visit(getattr(child, "component", None))
                    else:
                        visit(getattr(child, "component", child))
        for attr in ("child", "body", "dialog", "_dialog", "_modal", "input", "list", "menu", "combo", "modal", "bands"):
            child = getattr(obj, attr, None)
            if attr == "bands":
                visit(child)  # a value, not a component: the coverage walk needs it
            elif child is not None and (hasattr(child, "render") or hasattr(child, "is_open")):
                visit(child)

    visit(root)
    return out
