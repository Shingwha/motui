"""The demo's shell: the header, the grouped catalog and the footer.

The frame is four real regions:

* a top **dock** holding the :class:`Header` -- a one-row ``MenuBar`` of the
  six sections on the left and the current theme name right-aligned;
* a bottom **dock** holding the footer's ``ShortcutBar`` and ``StatusLine``;
* a body split, ``catalog | stage``, with a grouped ``NavList`` on the left
  and the topic's document on the right.

The header and footer are docks, not overlay bands: the frame budgets their
rows, hit-tests them and composes them like any other region.  The catalog's
group rows come from the topics' own ``group`` values -- one source, no
hand-maintained table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from motui import Line, Text, Theme
from motui.kernel import Component, Constraints, Surface, WrapMode
from motui.widgets import Column, MenuBar, NavList, ShortcutBar, StatusLine

from .assets import THEMES
from .model import Section, Topic
from .registry import BY_KEY, SECTIONS, topics_for

if TYPE_CHECKING:  # pragma: no cover - type-only
    from .session import Session

__all__ = [
    "CATALOG_RATIOS",
    "Header",
    "SHORTCUTS",
    "catalog_groups",
    "follow_shell",
    "mount_catalog",
    "mount_footer",
    "mount_header",
    "mount_shell",
    "refresh_status",
    "status_left",
    "status_right",
]

#: Catalog | stage weights: the catalog takes a fifth of the body.
CATALOG_RATIOS = (1, 4)

#: The footer's one row of demo-wide keys.
SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("c-1..6", "section"),
    ("c-n/c-p", "topic"),
    ("tab", "focus"),
    ("/", "palette"),
    ("c-f", "find"),
    ("c-t", "theme"),
    ("c-g", "stats"),
    ("q", "quit"),
)


class Header(Component):
    """The header dock's one row: the section bar plus the theme name.

    ``MenuBar`` renders into every column but the right margin, which the
    header reserves for ``theme: <name>``; ``child_at`` maps the bar's cells
    back onto the menu, so a click on a section label is a click on the
    ``MenuBar``'s own span table and the pointer tier needs no special case.
    """

    __slots__ = ("_menu_width", "label", "menu", "theme")

    def __init__(self, menu: MenuBar, label: str, *, theme: Theme) -> None:
        self.menu = menu
        self.label = label
        self.theme = theme
        self._menu_width = 0

    def render(self, c: Constraints) -> Surface:
        width = c.width
        right = Text(f"theme: {self.label}", style=self.theme.text.faint).render(
            Constraints(width=width)
        )
        right_line = right[0] if right else Line()
        menu_width = max(0, width - right_line.width - 2)
        self._menu_width = menu_width
        menu_line = (
            self.menu.render(Constraints(width=menu_width))[0] if menu_width else Line()
        )
        gap = width - menu_line.width - right_line.width
        if gap < 0:
            rows = [Line.from_text("motui studio").clip(WrapMode.ELLIPSIS, width)]
        else:
            rows = [(menu_line + Line.filled(gap) + right_line).clip(WrapMode.ELLIPSIS, width)]
        return Surface.clipped(rows, width)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        if row == 0 and 0 <= col < self._menu_width:
            return self.menu, row, col
        return None

    def revision(self) -> object:
        return (self.menu.revision(), self.label, self.theme)

    def __repr__(self) -> str:
        return f"Header(menu={self.menu!r}, label={self.label!r})"


def mount_header(
    *,
    theme: Theme,
    sections: Sequence[Section],
    index: int,
    theme_name: str,
) -> Header:
    """Build the header dock's one row; the session docks it."""
    menu = MenuBar([section.title for section in sections], index=index, theme=theme)
    return Header(menu, theme_name, theme=theme)


def mount_footer(
    *,
    theme: Theme,
    left: str,
    right: str,
) -> tuple[Column, ShortcutBar, StatusLine]:
    """Build the footer dock: the key bar over the status line; answer both."""
    bar = ShortcutBar(SHORTCUTS, theme=theme)
    status = StatusLine(left=(left,), right=(right,), theme=theme)
    return Column([bar, status], gap=0), bar, status


def catalog_groups(topics: Sequence[Topic]) -> tuple[tuple[int, str], ...]:
    """The catalog's group rows: one per contiguous run of ``topic.group``."""
    return tuple(
        (index, topic.group)
        for index, topic in enumerate(topics)
        if topic.group and (index == 0 or topics[index - 1].group != topic.group)
    )


def mount_catalog(
    *,
    theme: Theme,
    topics: Sequence[Topic],
    index: int,
) -> NavList:
    """Build the grouped catalog over ``topics``, selecting ``index``."""
    catalog = NavList(
        [topic.title for topic in topics],
        groups=catalog_groups(topics),
        index=index,
        theme=theme,
    )
    catalog.focused = False
    return catalog


def mount_shell(session: "Session") -> None:
    """Rebuild the session's header, footer and catalog in place.

    The two docks are undocked and docked afresh on the session's theme and
    state (the placeholder blocks of the first mount included), and the
    catalog is re-added to its pane; the undocked components leave the
    session's theme walk with them.
    """
    for edge in ("top", "bottom"):
        session.undock(edge)
    session.header = mount_header(
        theme=session.theme,
        sections=SECTIONS,
        index=session.section_index,
        theme_name=THEMES[session.theme_index][0],
    )
    session.dock(session.header, edge="top", size=1)
    footer, session.footer_bar, session.footer_status = mount_footer(
        theme=session.theme, left=status_left(session), right=status_right(session)
    )
    session.dock(footer, edge="bottom", size=2)
    if session.catalog_section is not None:
        try:
            session.remove(session.catalog_section)
        except KeyError:
            pass
        session.catalog_section = None
    topics = topics_for(BY_KEY[session.topic_key].section)
    index = next((i for i, topic in enumerate(topics) if topic.key == session.topic_key), 0)
    session.catalog = mount_catalog(theme=session.theme, topics=topics, index=index)
    session.catalog_section = session.add(
        session.catalog, id="catalog", pane=session.catalog_pane
    )


def status_left(session: "Session") -> str:
    """The footer inspector's left text for the session's live state."""
    manager = session.focus_manager
    target = None if manager is None else manager.focused
    focus = "-" if target is None else type(target).__name__.lower()
    return f"theme {THEMES[session.theme_index][0]} \u00b7 focus {focus} \u00b7 last {session.last_pick}"


def status_right(session: "Session") -> str:
    """The footer inspector's right text: the current section/topic."""
    topic = BY_KEY[session.topic_key]
    return f"{topic.section}/{topic.key}"


def refresh_status(session: "Session") -> None:
    """Write the footer inspector's two fields from the live state."""
    if session.footer_status is not None:
        session.footer_status.left = (status_left(session),)
        session.footer_status.right = (status_right(session),)


def follow_shell(session: "Session") -> None:
    """A header or catalog click lands on the section/topic it selected."""
    if session.header is not None and session.header.menu.index != session.section_index:
        session.show_section(session.header.menu.index)
        return
    topics = topics_for(BY_KEY[session.topic_key].section)
    if session.catalog is not None and topics:
        index = session.catalog.index
        if 0 <= index < len(topics) and topics[index].key != session.topic_key:
            session.show_topic(topics[index].key)
