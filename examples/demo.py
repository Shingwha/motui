"""demo: the mocode-tui showcase -- every component, style and feature, on screen.

Run it on a real terminal (the tab strip under the title is clickable -- a
click on a label opens that page, and ``c-n``/``c-p`` step to the next and the
previous exhibit, the ends wrap; a leading ``/`` opens the same list as a page
menu -- and on a page that can be played with, ``tab`` cycles the widget focus,
``\u2191\u2193`` drive the focused widget while ``enter`` activates it, and a
click focuses and then activates -- whatever a widget takes is reported once,
as a toast and on the page's own echo line (on the styles exhibit the pick
re-skins the whole shell); ``c-o`` switches the pane focus
after ``/split``)::

    uv run python examples/demo.py

or pipe anything in (``< /dev/null`` counts): the same session replays headless
from a :class:`ScriptedKeys` script -- every page, a few plays, a drag, the
exhibit keys, the feedback page's toast, the overview's live index, the
keymap tables, the interaction exhibit's ring with its log rows, the
streaming exhibit's control bar and finally the workspace exhibit's
two-column page, whose inspector the script switches by click and by arrow --
and prints the final screen as plain text, so the piped run is a smoke test::

    uv run python examples/demo.py < /dev/null; echo exit=$?

or dump every page as plain text without a terminal -- ``/overview``,
``/text``, ``/structure``, ``/lists``, ``/fields``, ``/feedback``, ``/styles``,
``/keys``, ``/features``, ``/interaction``, ``/workspace``, ``/streaming``,
``/chat`` -- for a quick read or a review of what the library renders::

    uv run python examples/demo.py --pages

Everything the "assistant" says is local and canned -- no network, no model.
The interactive stream pauses a few milliseconds per chunk so the growth is
visible; the headless replay never sleeps (it yields with ``sleep(0)``), so
the piped run stays instant.  The streaming exhibit is **dump-safe**: no
terminal, no beat and no pump clock, those two paths build the stream
complete, so their ``/streaming`` page is the whole fixture however the
control bar was played with.  The session lives in the :mod:`showcase`
package beside this entry point; this file is only wiring.
"""

from __future__ import annotations

import asyncio
import sys

from mocode_tui import HeadlessScreen, ScriptedKeys, TUI

from showcase.content import THEMES
from showcase.registry import PAGES
from showcase.script import HEADLESS_H, HEADLESS_W, script
from showcase.session import Showcase


def _dump(tui: TUI) -> str:
    """The screen as plain text, trailing blank rows trimmed."""
    lines = [row.text.rstrip() for row in tui.rows]
    while lines and not lines[-1].strip():
        lines.pop()  # trailing blank rows below the content are not content
    return "\n".join(lines)


def _headless() -> None:
    """Replay the scripted session headless, then print the final screen."""
    tui = TUI(
        screen=HeadlessScreen(HEADLESS_W, HEADLESS_H),
        keys=ScriptedKeys(script()),
        interactive=False,
    )
    asyncio.run(tui.run(Showcase(tui).run))
    sys.stdout.write(_dump(tui) + "\n")


def _pages() -> None:
    """Print every page as plain text, one after another (no terminal needed)."""
    for page in PAGES:
        tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
        Showcase(tui).show(page)
        tui.paint()
        rule = f"\u2500\u2500 /{page.name} "
        print(f"\n{rule}{'\u2500' * max(0, HEADLESS_W - len(rule))}")
        print(_dump(tui))


def main() -> None:
    if "--pages" in sys.argv[1:]:
        _pages()  # every page as text: a reviewable dump of the whole showcase
        return
    if not sys.stdout.isatty():
        _headless()  # piped: scripted replay + plain-text dump
        return
    tui = TUI(theme=THEMES[0][1])  # a real terminal: the alt screen
    asyncio.run(tui.run(Showcase(tui).run))  # the session's own host loop


if __name__ == "__main__":
    main()
