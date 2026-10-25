"""The demo: a master-detail browser shipped inside the package.

``python -m motui`` runs the browser on a real terminal; a piped run
replays the scripted tour headless and dumps the final screen;
``python -m motui --pages`` renders every topic as plain text.  The shell is
built from the library it shows: header and footer are real docks, the
catalog is a grouped ``NavList``, the stage is a pane with its own
scrollbar, and the palette, find, stats, tooltip and copy gesture are the
shipped tiers.

``render_topic`` is the one rendering path ``--pages`` and
``tools/golden.py`` share, so the golden frames are exactly the dumps the
command writes.
"""

from __future__ import annotations

import asyncio
import sys

from motui.app import Runtime
from motui.terminal import HeadlessScreen
from motui.testing import ScriptedEvents

from .assets import THEMES
from .model import Topic
from .registry import BY_KEY, SECTIONS, topics_for
from .script import HEADLESS_H, HEADLESS_W, script
from .session import Session

__all__ = ["main", "render_topic"]


def _dump(runtime: Runtime) -> str:
    """The screen as plain text, trailing blank rows trimmed."""
    lines = [row.text.rstrip() for row in runtime.rows]
    while lines and not lines[-1].strip():
        lines.pop()  # trailing blank rows below the content are not content
    return "\n".join(lines)


def render_topic(
    topic: Topic | str,
    *,
    width: int = HEADLESS_W,
    height: int = HEADLESS_H,
) -> str:
    """One topic as its plain-text frame: the header rule, the dump, LF.

    The path ``--pages`` and the golden tool share: a fresh headless
    session at the replay's geometry, ``show_topic``, one ``paint``.
    """
    value = topic if isinstance(topic, Topic) else BY_KEY[topic]
    session = Session(screen=HeadlessScreen(width, height), interactive=False)
    session.show_topic(value.key, toast=False)
    session.runtime.paint()
    header = f"\u2500\u2500 /{value.section}/{value.key} "
    return f"{header}{'\u2500' * max(0, width - len(header))}\n{_dump(session.runtime)}\n"


def _utf8_stdout() -> None:
    """Write the dump paths in UTF-8 whatever the console's codepage is."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError):  # a stream that has no say in its encoding
        pass


def _headless() -> None:
    """Replay the scripted session headless, then print the final screen."""
    session = Session(
        screen=HeadlessScreen(HEADLESS_W, HEADLESS_H),
        keys=ScriptedEvents(script()),
        interactive=False,
    )
    asyncio.run(session.run_async())
    if session.tooltip is not None:
        session.tooltip.detach()
        session.runtime.paint()
    sys.stdout.write(_dump(session.runtime) + "\n")


def _pages() -> None:
    """Print every section and every topic as plain text, no terminal needed."""
    for section in SECTIONS:
        rule = f"\u2500\u2500 /{section.key} "
        print(f"\n{rule}{'\u2500' * max(0, HEADLESS_W - len(rule))}")
        for topic in topics_for(section):
            sys.stdout.write(render_topic(topic))


def main() -> None:
    _utf8_stdout()  # every path below prints frames: the codepage is not ours
    if "--pages" in sys.argv[1:]:
        _pages()  # every topic as text: a reviewable dump of the whole demo
        return
    if not sys.stdout.isatty():
        _headless()  # piped: scripted replay + plain-text dump
        return
    # a real terminal: the alt screen, hover (1003) and focus events (1004) on
    session = Session(theme=THEMES[0][1], hover=True, focus_events=True)
    asyncio.run(session.run_async())


if __name__ == "__main__":
    main()
