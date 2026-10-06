"""The page model: what a showcase page is, and what a host may play with.

A :class:`Page` is a palette entry: a name, the description in the menu's
second column, and a builder.  The builder is handed the live
:class:`~showcase.session.Showcase` -- so a page can read the current theme,
raise a toast, or append a streamed turn -- and returns a :class:`PageBody`:
the blocks to mount, the page's focus ring, and what "playing" means here.

A page's widgets mount as **separate blocks** (never buried inside a
``Row``/``Column``): a mouse hit resolves to a *block's* component, so only a
widget with its own block can answer :meth:`~mocode_tui.app.TUI.hit_test`.
A page whose widgets can be focused and driven hands the host a
:class:`~mocode_tui.focus.FocusRing`; ``tab`` cycles it, the arrows and
``enter`` reach whatever holds the focus, and a click runs the ring's click
policy.  A page with nothing to focus leaves ``focus`` empty and is
mouse-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Sequence

from mocode_tui import Component, Divider, Text, Theme
from mocode_tui.focus import FocusRing  # the root face exports it in W4's library commit

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["Page", "PageBody", "header", "section"]


@dataclass
class PageBody:
    """One built page: the blocks it mounts, its focus ring, its banner hint.

    ``focus`` is the page's :class:`~mocode_tui.focus.FocusRing` -- the
    targets ``tab`` cycles and the arrows/``enter`` drive -- or ``None``
    for a page with nothing to focus.  ``hint`` names what can be played
    with, so the banner says what ``tab``/``\u2191\u2193/enter`` will do
    before a key is pressed.  ``tick`` -- when set -- runs on the pump's
    clock and repaints, for pages with live widgets (a progress bar, a
    spinner).
    """

    blocks: Sequence[Component]
    focus: FocusRing | None = None
    hint: str = ""
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
