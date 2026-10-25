"""Golden frames: every demo topic pinned byte for byte, on disk.

Run it from the repository root::

    uv run python tools/golden.py            # the gate's line: --check
    uv run python tools/golden.py --check    # compare tests/golden/topics/*.txt
    uv run python tools/golden.py --update   # re-record every topic

Each topic is rendered through the very path ``python -m motui --pages``
walks -- ``motui.demo.render_topic``: a fresh ``TUI`` on a
:class:`~motui.terminal.screen.HeadlessScreen` at the replay's own geometry
(``motui.demo.script.HEADLESS_W/H``), ``Session.show_topic``, one ``paint``
-- and written to ``tests/golden/topics/<section>--<topic>.txt``: the topic
header rule, then the plain-text dump with trailing blank rows trimmed.

One file holds one topic, so a diff names the topic that moved.  The files
are written with LF endings and compared **byte for byte**; a Windows
checkout with ``core.autocrlf`` rewrites every LF as CRLF on the way out
(this repository has no line-ending attributes -- normalizing the tree is
another case), so :func:`matches` accepts that one exact conversion and
nothing else: mixed endings, a stray CR or any other byte is a diff.
:func:`check` therefore reads bytes, never text, and a missing file, an
extra one and a changed one are all problems; ``--check`` exits 1 when
there is any.

Re-record with ``--update`` only when the change is intended -- a topic's
content, the shell chrome every topic shares, or a component's rendering --
and re-record the whole set in the same commit: the header names the
section and theme, so one shell change moves every file (see
``tests/golden/README.md``).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from motui.demo import render_topic  # noqa: E402
from motui.demo.registry import TOPICS  # noqa: E402

#: Where the golden frames live: one ``<section>--<topic>.txt`` per topic.
GOLDEN = ROOT / "tests" / "golden" / "topics"


def topic_name(topic) -> str:
    """The file name of one topic's frame."""
    return f"{topic.section}--{topic.key}.txt"


def matches(recorded: bytes, expected: bytes) -> bool:
    """Whether a frame's bytes are the record -- LF, or a checkout's CRLF.

    ``expected`` is what the demo renders (LF endings); the recorded bytes
    may be that verbatim, or the exact ``LF -> CRLF`` conversion a Windows
    checkout with ``core.autocrlf`` makes on the way out of the index.
    """
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
        expected[name] = render_topic(topic).encode("utf-8")
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
            sink.write(render_topic(topic))


def main(argv: list[str] | None = None) -> int:
    """``--check`` (the default) or ``--update``; the exit code is the answer."""
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) > 1 or (args and args[0] not in ("--check", "--update")):
        print(f"usage: python {Path(sys.argv[0]).name} [--check | --update]")
        return 2
    mode = args[0] if args else "--check"
    if mode == "--update":
        update()
        print(f"golden: recorded {len(TOPICS)} topics into {GOLDEN}")
        return 0
    problems = check()
    for problem in problems:
        print(f"golden: {problem}")
    if problems:
        print(f"golden: {len(problems)} problem(s) -- re-record with --update if intended")
        return 1
    print(f"golden: {len(TOPICS)} topics match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
