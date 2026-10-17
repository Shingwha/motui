"""The page model: what a demo page is, and what a host may play with."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Sequence

from motui import FocusRing, Text, Theme
from motui.kernel import Component
from motui.widgets import Divider

if TYPE_CHECKING:
    from .session import Session

__all__ = ["Page", "PageBody", "api_note", "header", "section", "try_line"]


@dataclass
class PageBody:
    """One built page: the blocks it mounts, its ring, its hooks, its modal."""

    blocks: Sequence[Component]
    focus: FocusRing | None = None
    tick: Callable[[], None] | None = None
    note: Callable[[str], None] | None = None
    enter: Callable[[Session], None] | None = None
    leave: Callable[[Session], None] | None = None
    modal: Component | None = None


@dataclass(frozen=True)
class Page:
    """One demo page: its name, its one-line description, its builder.

    ``hints`` are the page's own ``(key, label)`` rows for the bottom band:
    ``Session.show`` rebuilds the band from them plus the session's global
    keys, so the band follows the page (its ``TRY`` line's keys, the ones
    that fit one row).
    """

    name: str
    description: str
    build: Callable[[Session], PageBody]
    hints: tuple[tuple[str, str], ...] = ()


def header(title: str, blurb: str, theme: Theme) -> list[Component]:
    """A page's opening rows: the title, the one-line blurb, the rule."""
    return [
        Text(title, style=theme.accent),
        Text(blurb, style=theme.dim),
        Divider(theme=theme),
    ]


def try_line(text: str, theme: Theme) -> Component:
    """The exhibit grammar's "what you do here" row: an accent ``TRY`` line."""
    return Text(f"TRY \u25b8 {text}", style=theme.accent)


def api_note(text: str, theme: Theme) -> Component:
    """The exhibit grammar's "which API" row: a dim ``API`` line."""
    return Text(f"API \u00b7 {text}", style=theme.dim)


def section(label: str, theme: Theme) -> Component:
    """A labelled rule between a page's parts."""
    return Divider(theme=theme, label=label)
