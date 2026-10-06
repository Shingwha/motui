"""The page model: what a showcase page is, and what a host may play with.

A :class:`Page` is a palette entry: a name, the short label its tab carries,
the description in the menu's second column, and a builder.  The builder is
handed the live :class:`~showcase.session.Showcase` -- so a page can read the
current theme, raise a toast, or append a streamed turn -- and returns a
:class:`PageBody`: the blocks to mount, the page's focus ring, and what
"playing" means here.

A page's widgets mount as **separate blocks** (never buried inside a
``Row``/``Column``): a mouse hit resolves to a *block's* component, so only a
widget with its own block can answer :meth:`~mocode_tui.app.TUI.hit_test`.
A page whose widgets can be focused and driven hands the host a
:class:`~mocode_tui.focus.FocusRing`; ``tab`` cycles it, the arrows and
``enter`` reach whatever holds the focus, and a click runs the ring's click
policy.  A page with nothing to focus leaves ``focus`` empty and is
mouse-only.

**The exhibit grammar.**  Every page answers the same three questions with
the same three helpers, so a reader who learned one page has learned them
all: :func:`header` says *what this is*, :func:`try_line` says *what you do
here* (an accent line), and :func:`api_note` says *which API line it is* (a
dim line, naming something that exists in ``src/``).  :func:`section`
separates the parts in between::

    *header("text & data", "the primitives that carry content", theme),
    try_line("click any table row; \u2191\u2193 moves; enter takes it", theme),
    table,
    api_note("Table.index / Table.chosen", theme),

Pages mount their widgets as separate blocks, so the three helpers sit
beside -- never inside -- the exhibit they annotate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Sequence

from mocode_tui import Component, Divider, FocusRing, Text, Theme

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["Page", "PageBody", "api_note", "header", "section", "try_line"]


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
    """One showcase page: its name, its tab label, its description, its builder.

    ``name`` is the page's authoritative name: the palette's ``/name`` entry,
    the ``--pages`` dump header and the status line all read it, so it stays
    descriptive.  ``nav`` is the label the top tab strip renders -- short by
    contract, because **all** the labels share one row (the pane's width, 110
    columns on the headless screen) and the strip is ``fit`` to that row: a
    label that does not fit is truncated, and a truncated label cannot be
    clicked.  The two names differ because they answer different budgets, not
    different pages.
    """

    name: str
    nav: str
    description: str
    build: Callable[[Showcase], PageBody]


def header(title: str, blurb: str, theme: Theme) -> list[Component]:
    """A page's opening rows: the title, the one-line blurb, the rule.

    The first of the exhibit grammar's three helpers: it answers *what this
    is*.  The title is the exhibit's name, the blurb one sentence of
    positioning, and the rule separates the header from the exhibit itself.
    """
    return [
        Text(title, style=theme.accent),
        Text(blurb, style=theme.dim),
        Divider(theme=theme),
    ]


def try_line(text: str, theme: Theme) -> Component:
    """The exhibit grammar's "what you do here" row: an accent ``TRY \u25b8`` line.

    One sentence of direct instruction -- click what, press what, watch what
    -- rendered in the theme's ``accent``, so it is the first thing a
    reader's eye lands on after the header.  It is a plain :class:`Text` and
    wraps with the pane like any other row; keep it to one sentence::

        try_line("click any table row; \u2191\u2193 moves; enter takes it", theme)
    """
    return Text(f"TRY \u25b8 {text}", style=theme.accent)


def api_note(text: str, theme: Theme) -> Component:
    """The exhibit grammar's "which API" row: a dim ``API \u00b7`` line.

    One line naming the real API behind the exhibit -- a name and a
    signature that exist in ``src/``, so a reader can copy the line into
    their own host -- rendered in the theme's ``dim``: it annotates the
    exhibit above it without competing with it::

        api_note("Table.index / Table.chosen", theme)
    """
    return Text(f"API \u00b7 {text}", style=theme.dim)


def section(label: str, theme: Theme) -> Component:
    """A labelled rule between a page's parts."""
    return Divider(theme=theme, label=label)
