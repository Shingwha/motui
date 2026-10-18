"""The page model: what a demo page is, and what a host may play with."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Sequence

from motui import FocusRing
from motui.kernel import Component

if TYPE_CHECKING:
    from .session import Session

__all__ = ["Page", "PageBody"]


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
    """One demo page: its name, its description, its group, its builder.

    ``hints`` are the page's own ``(key, label)`` rows for the bottom band:
    ``Session.show`` rebuilds the band from them plus the session's global
    keys, so the band follows the page.  ``group`` is the rail group the
    page belongs to (the registry derives the rail's group rows and the
    index's group column from it); ``""`` is a page outside every group.
    """

    name: str
    description: str
    build: Callable[[Session], PageBody]
    hints: tuple[tuple[str, str], ...] = ()
    group: str = ""
