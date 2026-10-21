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

from typing import Sequence

from motui import Line, Text, Theme
from motui.core import Component, Document
from motui.widgets import Column, MenuBar, NavList, ShortcutBar, StatusLine

from .model import Section, Topic

__all__ = [
    "CATALOG_RATIOS",
    "Header",
    "SHORTCUTS",
    "catalog_groups",
    "mount_catalog",
    "mount_footer",
    "mount_header",
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

    def render(self, width: int) -> list[Line]:
        right = Text(f"theme: {self.label}", style=self.theme.text.faint).render(width)
        right_line = right[0] if right else Line()
        menu_width = max(0, width - right_line.width - 2)
        self._menu_width = menu_width
        menu_line = self.menu.render(menu_width)[0] if menu_width else Line()
        gap = width - menu_line.width - right_line.width
        if gap < 0:
            return [Line.from_text("motui studio").fit(width)]
        return [(menu_line + Line.filled(gap) + right_line).fit(width)]

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        if row == 0 and 0 <= col < self._menu_width:
            return self.menu, row, col
        return None

    def revision(self) -> object:
        return (self.menu.revision(), self.label, self.theme)

    def __repr__(self) -> str:
        return f"Header(menu={self.menu!r}, label={self.label!r})"


def mount_header(
    document: Document,
    *,
    theme: Theme,
    sections: Sequence[Section],
    index: int,
    theme_name: str,
) -> Header:
    """Mount the header dock's one block; answer it."""
    menu = MenuBar([section.title for section in sections], index=index, theme=theme)
    header = Header(menu, theme_name, theme=theme)
    document.add(header, id="header")
    return header


def mount_footer(
    document: Document,
    *,
    theme: Theme,
    left: str,
    right: str,
) -> tuple[ShortcutBar, StatusLine]:
    """Mount the footer dock: the key bar over the status line; answer both."""
    bar = ShortcutBar(SHORTCUTS, theme=theme)
    status = StatusLine(left=(left,), right=(right,), theme=theme)
    document.add(Column([bar, status], gap=0), id="footer")
    return bar, status


def catalog_groups(topics: Sequence[Topic]) -> tuple[tuple[int, str], ...]:
    """The catalog's group rows: one per contiguous run of ``topic.group``."""
    return tuple(
        (index, topic.group)
        for index, topic in enumerate(topics)
        if topic.group and (index == 0 or topics[index - 1].group != topic.group)
    )


def mount_catalog(
    document: Document,
    *,
    theme: Theme,
    topics: Sequence[Topic],
    index: int,
) -> NavList:
    """Mount the grouped catalog over ``topics``; select ``index``."""
    catalog = NavList(
        [topic.title for topic in topics],
        groups=catalog_groups(topics),
        index=index,
        focused=False,
        theme=theme,
    )
    document.add(catalog, id="catalog")
    return catalog
