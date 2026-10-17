"""The demo: the library's own exhibits, shipped inside the package.

The one entry is ``python -m motui`` (:mod:`motui.__main__` dispatches
here), and it takes three shapes:

* a real terminal runs the interactive session -- alt screen, hover (1003)
  and focus events (1004) on;
* a pipe (``stdout`` not a tty, ``< /dev/null`` counts) replays the scripted
  session headless and dumps the final screen as plain text, exit 0;
* ``--pages`` dumps every page as plain text, no terminal needed.

``session`` is the :class:`~motui.demo.session.Gallery` controller and its
host loop; ``pages/`` holds the category exhibits, one theme per page;
``registry`` lists them; ``shell`` is the pinned chrome; ``script`` is the
headless replay; ``content`` holds the theme variants, the fixture splitter
and the fixture path.  Everything the demo shows is local and canned -- no
network, no model.
"""

from __future__ import annotations

import asyncio
import sys

from motui import TUI
from motui.kernel import HeadlessScreen, ScriptedKeys

from .content import THEMES
from .registry import PAGES
from .script import HEADLESS_H, HEADLESS_W, script
from .session import Gallery

__all__ = ["main"]


def _dump(tui: TUI) -> str:
    """The screen as plain text, trailing blank rows trimmed."""
    lines = [row.text.rstrip() for row in tui.rows]
    while lines and not lines[-1].strip():
        lines.pop()  # trailing blank rows below the content are not content
    return "\n".join(lines)


def _headless() -> None:
    """Replay the scripted session headless, then print the final screen.

    The dump is the page's own text -- the same reason the script dismisses
    the toasts it raised with its last three clicks -- so the session's
    tooltip band retires here: the script's canned pointer ends its run
    parked on the action page's hinted Button (that hover *is* the exhibit),
    and a pointer overlay left standing is not page content.  The run still
    exercised the band; only the stop-frame carries none of it.
    """
    tui = TUI(
        screen=HeadlessScreen(HEADLESS_W, HEADLESS_H),
        keys=ScriptedKeys(script()),
        interactive=False,
    )
    gallery = Gallery(tui)
    asyncio.run(tui.run(gallery.run))
    if gallery.tooltip is not None:
        gallery.tooltip.detach()
        tui.paint()
    sys.stdout.write(_dump(tui) + "\n")


def _pages() -> None:
    """Print every page as plain text, one after another (no terminal needed)."""
    for page in PAGES:
        tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
        Gallery(tui).show(page)
        tui.paint()
        rule = f"\u2500\u2500 /{page.name} "
        print(f"\n{rule}{'\u2500' * max(0, HEADLESS_W - len(rule))}")
        print(_dump(tui))


def main() -> None:
    if "--pages" in sys.argv[1:]:
        _pages()  # every page as text: a reviewable dump of the whole demo
        return
    if not sys.stdout.isatty():
        _headless()  # piped: scripted replay + plain-text dump
        return
    # a real terminal: the alt screen, hover (1003) and focus events (1004) on
    tui = TUI(theme=THEMES[0][1], hover=True, focus_events=True)
    asyncio.run(tui.run(Gallery(tui).run))  # the session's own host loop


if __name__ == "__main__":
    main()
