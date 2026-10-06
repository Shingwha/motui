"""The page model: what a showcase page is, and what a host may play with.

A :class:`Page` is a palette entry: a name, the description in the menu's
second column, and a builder.  The builder is handed the live
:class:`~showcase.session.Showcase` -- so a page can read the current theme,
raise a toast, or append a streamed turn -- and returns a :class:`PageBody`:
the blocks to mount, and how the page can be played with.

A page's widgets mount as **separate blocks** (never buried inside a
``Row``/``Column``): a mouse hit resolves to a *block's* component, so only a
widget with its own block can answer :meth:`~mocode_tui.app.TUI.hit_test`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Sequence

from mocode_tui import Component, Divider, Text, Theme

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["Page", "PageBody", "Play", "header", "section"]


@dataclass(frozen=True)
class Play:
    """How the host plays with a page.

    ``target`` is the widget the arrows drive -- and the identity the click
    router compares against, so a click on it runs :attr:`enter` too.
    ``move(delta)`` steps the target's cursor (``-1`` up, ``+1`` down);
    ``enter()`` is its activation (fold a tree node, toast a pick, break a
    line); ``hint`` names the target in the banner, so the screen says what
    ``\u2191\u2193/enter`` will play before any key is pressed.
    """

    target: Component
    move: Callable[[int], object]
    enter: Callable[[], object]
    hint: str


@dataclass
class PageBody:
    """One built page: the blocks it mounts, and what can be played with.

    ``tick`` -- when set -- runs on the pump's clock and repaints, for pages
    with live widgets (a progress bar, a spinner).
    """

    blocks: Sequence[Component]
    play: Play | None = None
    tick: Callable[[], None] | None = None


@dataclass(frozen=True)
class Page:
    """One showcase page: its palette name, its description, its builder."""

    name: str
    description: str
    build: Callable[[Showcase], PageBody]


def header(title: str, blurb: str, theme: Theme) -> list[Component]:
    """A page's opening rows: the title, the one-line blurb, the rule."""
    return [
        Text(title, style=theme.accent),
        Text(blurb, style=theme.dim),
        Divider(theme=theme),
    ]


def section(label: str, theme: Theme) -> Component:
    """A labelled rule between a page's parts."""
    return Divider(theme=theme, label=label)
