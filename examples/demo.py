"""demo: the mocode-tui gallery -- one page of exhibits, and no input box.

Run it on a real terminal: the header's tab strip is clickable (a click on a
label opens that page), ``c-n``/``c-p`` step to the next and the previous
page (the ends wrap), and a leading ``/`` opens a **modal palette** -- it
carries its own query row and disappears the moment a command is taken or
escape is pressed; the gallery mounts no input box anywhere else.  On a page
that can be played with, ``tab`` cycles the page's focus ring, ``\u2191\u2193``
drive the focused widget, ``enter`` activates it, and a click focuses and
then activates -- whatever a widget takes is reported once, as a toast and on
the page's own echo line (on the styles page the pick re-skins the whole
shell).  ``c-o`` moves the pane focus (the features page opens a right pane
of its own; ``/split`` opens a preview on the pages without one), ``c-g``
mounts and unmounts the dev stats overlay in the frame's corner, the leaf
under the pointer raises its own ``hint`` as a tooltip band, a drag
selects and release copies through OSC 52, and ``q`` or ``Ctrl-C`` quits.
The session opens DECSET 1004 with ``TUI(focus_events=True)``, so losing the
window scrubs the hover (and the band) until the pointer moves again::

    uv run python examples/demo.py

or pipe anything in (``< /dev/null`` counts): the same session replays
headless from a :class:`ScriptedKeys` script -- every page through the ``/``
palette, the rings driven by key, the hover and the click on the action
page's Button, a drag, the preview pane's wheel, the toast dismissal -- and
prints the final screen as plain text, so the piped run is a smoke test::

    uv run python examples/demo.py < /dev/null; echo exit=$?

or dump every page as plain text without a terminal -- ``/overview``,
``/content``, ``/data``, ``/structure``, ``/input``, ``/choice``,
``/navigation``, ``/action``, ``/feedback``, ``/styles``, ``/streaming``,
``/features``, ``/devtools`` -- for a quick read or a review of what the
library renders::

    uv run python examples/demo.py --pages

Everything the gallery shows is local and canned -- no network, no model.
The interactive paths pace themselves with short sleeps (the page beat, the
palette's expiries); the headless replay never sleeps, and the streaming
page is **dump-safe**: no terminal, no beat and no pump clock, so those two
paths build the stream complete -- their ``/streaming`` page is the whole
346-line fixture however the control bar was played with.  The session lives
in the :mod:`gallery` package beside this entry point; this file is only
wiring.
"""

from __future__ import annotations

import asyncio
import sys

from mocode_tui import HeadlessScreen, ScriptedKeys, TUI

from gallery.content import THEMES
from gallery.registry import PAGES
from gallery.script import HEADLESS_H, HEADLESS_W, script
from gallery.session import Gallery


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
        _pages()  # every page as text: a reviewable dump of the whole gallery
        return
    if not sys.stdout.isatty():
        _headless()  # piped: scripted replay + plain-text dump
        return
    # a real terminal: the alt screen, hover (1003) and focus events (1004) on
    tui = TUI(theme=THEMES[0][1], hover=True, focus_events=True)
    asyncio.run(tui.run(Gallery(tui).run))  # the session's own host loop


if __name__ == "__main__":
    main()
