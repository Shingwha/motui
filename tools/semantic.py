"""Semantic golden frames: the cell grid, its attributes and the cursor.

Run it from the repository root::

    uv run python tools/semantic.py            # the gate's line: --check
    uv run python tools/semantic.py --check    # compare tests/golden/semantic
    uv run python tools/semantic.py --update   # re-record every topic
    uv run python tools/semantic.py --check --snapshot DIR   # another set

Where the byte golden (:mod:`tools.golden`) pins the exact escape stream a
topic paints, this tool pins what a terminal would *show*: the bytes go
through :class:`~motui.testing.emulator.Emulator`, which rebuilds the cell
grid, and each row is written as its text plus the styled runs over it.  A
change that only reorders escapes stays green; a change in glyphs, SGR
attributes, OSC 8 links or the cursor anchor moves the snapshot.

The frame is the same one ``tools.golden`` renders -- the very path
``python -m motui --pages`` walks: a fresh headless ``Session`` at the
replay's geometry, ``show_topic(toast=False)``, one ``paint`` -- so the two
golden sets describe one frame from two angles.

Format, one LF-terminated file per topic::

    # <section>/<key> <width>x<height> cursor=<x>,<y>
    <row text>\\t<runs>
    ...

``row text`` is the row's cells concatenated and right-stripped (a
double-width glyph's placeholder contributes nothing); ``runs`` covers the
columns whose style is not the default style, as inclusive zero-based
``start-end:<sgrhex>[:L<link>]`` pieces joined with ``|``, or ``-`` when the
whole row is default.  ``sgrhex`` is ``Style.prefix()`` encoded as UTF-8 and
hexed, so the key is the exact SGR bytes without depending on ``repr``; a
link is appended as its ``repr`` (quotes included) and breaks a run when it
changes.  The cursor is the emulator's zero-based final position.

Re-record with ``--update`` only for an intended change, and re-record the
whole set in one commit: the shell chrome every topic shares means one
chrome change moves every file.  ``--check`` compares bytes; the one
accepted other spelling is the exact ``LF -> CRLF`` conversion a Windows
checkout makes (this repository has no line-ending attributes), the same
rule ``tools.golden`` applies.  Missing, extra and changed files all fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from motui.demo import Session  # noqa: E402
from motui.demo.registry import TOPICS  # noqa: E402
from motui.demo.script import HEADLESS_H, HEADLESS_W  # noqa: E402
from motui.kernel.style import Style  # noqa: E402
from motui.terminal import HeadlessScreen  # noqa: E402
from motui.testing import Emulator  # noqa: E402

#: Where the semantic snapshots live: one ``<section>--<topic>.txt`` per topic.
GOLDEN = ROOT / "tests" / "golden" / "semantic"

#: The style of a cell no run has touched; a run is everything else.
_DEFAULT_STYLE = Style()


def topic_name(topic) -> str:
    """The file name of one topic's semantic frame."""
    return f"{topic.section}--{topic.key}.txt"


def frame(topic, width: int = HEADLESS_W, height: int = HEADLESS_H) -> Emulator:
    """Emulate one topic's painted bytes on a ``width`` x ``height`` grid.

    This is ``demo.render_topic``'s path byte for byte up to the paint: a
    fresh session, ``show_topic`` with the toast off, one ``paint`` -- then
    the recorded bytes are fed to a fresh emulator.
    """
    screen = HeadlessScreen(width, height)
    session = Session(screen=screen, interactive=False)
    session.show_topic(topic.key, toast=False)
    session.runtime.paint()
    emulator = Emulator(width, height)
    emulator.feed(screen.output)
    return emulator


def _run(start: int, end: int, sgrhex: str, link: str | None) -> str:
    """One run: inclusive column span, SGR hex and, when present, the link."""
    piece = f"{start}-{end}:{sgrhex}"
    return piece if link is None else f"{piece}:L{link!r}"


def _runs(row) -> str:
    """The row's non-default styled runs, as ``|``-joined ``start-end:...``."""
    pieces: list[str] = []
    start = -1
    current: tuple[str, str | None] | None = None
    for column, cell in enumerate(row):
        if cell.style == _DEFAULT_STYLE:
            key = None
        else:
            key = (cell.style.prefix().encode("utf-8").hex(), cell.link)
        if key != current:
            if current is not None:
                pieces.append(_run(start, column - 1, *current))
            start = column
            current = key
    if current is not None:
        pieces.append(_run(start, len(row) - 1, *current))
    return "|".join(pieces) if pieces else "-"


def snapshot(topic, width: int = HEADLESS_W, height: int = HEADLESS_H) -> str:
    """One topic's semantic frame: the cursor header, then text and runs."""
    emulator = frame(topic, width, height)
    cursor = emulator.cursor
    lines = [
        f"# {topic.section}/{topic.key} {width}x{height} "
        f"cursor={cursor.x},{cursor.y}"
    ]
    for row in emulator.grid:
        text = "".join(cell.char for cell in row).rstrip()
        lines.append(f"{text}\t{_runs(row)}")
    return "\n".join(lines) + "\n"


def matches(recorded: bytes, expected: bytes) -> bool:
    """Whether a snapshot's bytes are the record -- LF, or a checkout's CRLF."""
    return recorded == expected or recorded == expected.replace(b"\n", b"\r\n")


def check(directory: Path | None = None) -> list[str]:
    """Compare every topic against its file; one line per problem, sorted.

    ``"<name>: missing"`` for a topic with no file, ``"<name>: differs"``
    (:func:`matches`) for one that moved, ``"<name>: extra"`` for a file no
    topic owns.  An empty list is the gate's pass.
    """
    where = GOLDEN if directory is None else directory
    problems: list[str] = []
    expected: dict[str, bytes] = {}
    for topic in TOPICS:
        name = topic_name(topic)
        expected[name] = snapshot(topic).encode("utf-8")
        path = where / name
        if not path.is_file():
            problems.append(f"{name}: missing")
        elif not matches(path.read_bytes(), expected[name]):
            problems.append(f"{name}: differs")
    if where.is_dir():
        for path in where.glob("*.txt"):
            if path.name not in expected:
                problems.append(f"{path.name}: extra")
    return sorted(problems)


def update(directory: Path | None = None) -> None:
    """Record every topic afresh: one LF-terminated file per topic."""
    where = GOLDEN if directory is None else directory
    where.mkdir(parents=True, exist_ok=True)
    for topic in TOPICS:
        path = where / topic_name(topic)
        with path.open("w", encoding="utf-8", newline="\n") as sink:
            sink.write(snapshot(topic))


def main(argv: list[str] | None = None) -> int:
    """``--check`` (the default) or ``--update``, plus ``--snapshot DIR``."""
    args = sys.argv[1:] if argv is None else list(argv)
    mode = "--check"
    taken = False
    where = GOLDEN
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("--check", "--update"):
            if taken:
                print(f"usage: python {Path(sys.argv[0]).name} "
                      "[--check | --update] [--snapshot DIR]")
                return 2
            mode, taken = arg, True
            index += 1
        elif arg == "--snapshot" and index + 1 < len(args):
            where = Path(args[index + 1])
            index += 2
        else:
            print(f"usage: python {Path(sys.argv[0]).name} "
                  "[--check | --update] [--snapshot DIR]")
            return 2
    if mode == "--update":
        update(where)
        print(f"semantic: recorded {len(TOPICS)} topics into {where}")
        return 0
    problems = check(where)
    for problem in problems:
        print(f"semantic: {problem}")
    if problems:
        print(f"semantic: {len(problems)} problem(s) -- re-record with --update if intended")
        return 1
    print(f"semantic: {len(TOPICS)} topics match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
