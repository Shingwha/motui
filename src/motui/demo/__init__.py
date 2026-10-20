"""The demo: the library's own exhibits, shipped inside the package."""

from __future__ import annotations

import asyncio
import sys

from motui import TUI
from motui.kernel import HeadlessScreen
from motui.testing import ScriptedEvents

from .assets import THEMES
from .registry import PAGES
from .script import HEADLESS_H, HEADLESS_W, script
from .session import Session

__all__ = ["main"]


def _dump(tui: TUI) -> str:
    """The screen as plain text, trailing blank rows trimmed."""
    lines = [row.text.rstrip() for row in tui.rows]
    while lines and not lines[-1].strip():
        lines.pop()  # trailing blank rows below the content are not content
    return "\n".join(lines)


def _utf8_stdout() -> None:
    """Write the dump paths in UTF-8 whatever the console's codepage is.

    A piped run on a legacy-codepage Windows (cp1252, cp437) cannot encode
    the frames: the scrollbar's ``\\u2591``/``\\u2588`` and the demo's own
    rules raise ``UnicodeEncodeError`` and the whole dump dies.  The frames
    are the same text everywhere, so the stream's encoding is what gives --
    a real console is untouched (Python writes it through ``WriteConsoleW``,
    which is Unicode already), and so is a stream that cannot be
    reconfigured.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError):  # a stream that has no say in its encoding
        pass


def _headless() -> None:
    """Replay the scripted session headless, then print the final screen."""
    tui = TUI(
        screen=HeadlessScreen(HEADLESS_W, HEADLESS_H),
        keys=ScriptedEvents(script()),
        interactive=False,
    )
    session = Session(tui)
    asyncio.run(tui.run(session.run))
    if session.tooltip is not None:
        session.tooltip.detach()
        tui.paint()
    sys.stdout.write(_dump(tui) + "\n")


def _pages() -> None:
    """Print every page as plain text, one after another (no terminal needed)."""
    for page in PAGES:
        tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
        Session(tui).show(page)
        tui.paint()
        rule = f"\u2500\u2500 /{page.name} "
        print(f"\n{rule}{'\u2500' * max(0, HEADLESS_W - len(rule))}")
        print(_dump(tui))


def main() -> None:
    _utf8_stdout()  # every path below prints frames: the codepage is not ours
    if "--pages" in sys.argv[1:]:
        _pages()  # every page as text: a reviewable dump of the whole demo
        return
    if not sys.stdout.isatty():
        _headless()  # piped: scripted replay + plain-text dump
        return
    # a real terminal: the alt screen, hover (1003) and focus events (1004) on
    tui = TUI(theme=THEMES[0][1], hover=True, focus_events=True)
    asyncio.run(tui.run(Session(tui).run))  # the session's own host loop


if __name__ == "__main__":
    main()
