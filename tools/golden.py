"""Golden frames: the gallery's pages pinned byte for byte, on disk.

Run it from the repository root::

    uv run python tools/golden.py            # the gate's line: --check
    uv run python tools/golden.py --check    # compare tests/golden/pages/*.txt
    uv run python tools/golden.py --update   # re-record every page

Each page is rendered through the very path ``examples/demo.py --pages``
walks -- a :class:`~motui.app.TUI` on a
:class:`~motui.core.screen.HeadlessScreen` at the replay's own geometry
(``gallery.script.HEADLESS_W/H``), ``Gallery(tui).show(page)``, one
``paint()`` -- and written to ``tests/golden/pages/<page>.txt``: the page
header rule, then the plain-text dump with trailing blank rows trimmed.

One file holds one page, so a diff names the page that moved.  The files
are written with LF endings and compared **byte for byte**; a Windows
checkout with ``core.autocrlf`` rewrites every LF as CRLF on the way out
(this repository has no line-ending attributes -- normalizing the tree is
another case), so :func:`matches` accepts that one exact conversion and
nothing else: mixed endings, a stray CR or any other byte is a diff.
:func:`check` therefore reads bytes, never text, and a missing file, an
extra one and a changed one are all problems; ``--check`` exits 1 when
there is any, so the wave's gate line fails exactly when a page's rendered
output moved.

Re-record with ``--update`` only when the change is intended -- a page's
content, the shell chrome every page shares (the header strip carries every
page's label), or a component's rendering -- and re-record the whole set:
the header is shared, so one added page moves every file (see
``tests/golden/README.md``).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples"))

from motui import HeadlessScreen, TUI  # noqa: E402

from gallery.page import Page  # noqa: E402
from gallery.registry import PAGES  # noqa: E402
from gallery.script import HEADLESS_H, HEADLESS_W  # noqa: E402
from gallery.session import Gallery  # noqa: E402

#: Where the golden frames live: one ``<page name>.txt`` per registry page.
GOLDEN = ROOT / "tests" / "golden" / "pages"


def dump(tui: TUI) -> str:
    """The screen as plain text, trailing blank rows trimmed.

    The same rule ``examples/demo.py``'s own ``_dump`` applies to the piped
    dump, verbatim: each row's text rstripped, the blank rows below the
    content dropped.  It is duplicated here on purpose -- a tool must not
    import a script's private helpers -- and the golden test is what keeps
    the two in step.
    """
    lines = [row.text.rstrip() for row in tui.rows]
    while lines and not lines[-1].strip():
        lines.pop()  # trailing blank rows below the content are not content
    return "\n".join(lines)


def render_page(page: Page) -> str:
    """One page as its golden text: the ``demo.py --pages`` path, verbatim.

    The header rule first (``\u2500\u2500 /<name> \u2500\u2500\u2026``, the
    same shape and width the piped dump announces each page with), then the
    dump, then exactly one trailing newline.
    """
    tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
    Gallery(tui).show(page)
    tui.paint()
    rule = f"\u2500\u2500 /{page.name} "
    return f"{rule}{'\u2500' * max(0, HEADLESS_W - len(rule))}\n{dump(tui)}\n"


def matches(recorded: bytes, expected: bytes) -> bool:
    """Whether a frame's bytes are the record -- LF, or a checkout's CRLF.

    ``expected`` is what :func:`render_page` renders (LF endings); the
    recorded bytes may be that verbatim, or the exact ``LF -> CRLF``
    conversion a Windows checkout with ``core.autocrlf`` makes on the way
    out of the index.  Those two spellings are the same frame; anything
    else -- a mixed ending, a stray CR, a changed byte -- is a difference.
    """
    return recorded == expected or recorded == expected.replace(b"\n", b"\r\n")


def check(directory: Path | None = None) -> list[str]:
    """Compare every page against its file; one line per problem, sorted.

    ``"<name>: missing"`` for a page with no file, ``"<name>: differs"``
    (:func:`matches`) for one that moved, ``"<name>: extra"`` for a file no
    page owns.  An empty list is the gate's pass.
    """
    where = GOLDEN if directory is None else directory
    problems: list[str] = []
    expected: dict[str, bytes] = {}
    for page in PAGES:
        name = f"{page.name}.txt"
        expected[name] = render_page(page).encode("utf-8")
        path = where / name
        if not path.is_file():
            problems.append(f"{name}: missing")
        elif not matches(path.read_bytes(), expected[name]):
            problems.append(f"{name}: differs")
    for path in where.glob("*.txt"):
        if path.name not in expected:
            problems.append(f"{path.name}: extra")
    return sorted(problems)


def update(directory: Path | None = None) -> None:
    """Record every page afresh: one LF-terminated file per registry page."""
    where = GOLDEN if directory is None else directory
    where.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        path = where / f"{page.name}.txt"
        with path.open("w", encoding="utf-8", newline="\n") as sink:
            sink.write(render_page(page))


def main(argv: list[str] | None = None) -> int:
    """``--check`` (the default) or ``--update``; the exit code is the answer."""
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) > 1 or (args and args[0] not in ("--check", "--update")):
        print(f"usage: python {Path(sys.argv[0]).name} [--check | --update]")
        return 2
    mode = args[0] if args else "--check"
    if mode == "--update":
        update()
        print(f"golden: recorded {len(PAGES)} pages into {GOLDEN}")
        return 0
    problems = check()
    for problem in problems:
        print(f"golden: {problem}")
    if problems:
        print(f"golden: {len(problems)} problem(s) -- re-record with --update if intended")
        return 1
    print(f"golden: {len(PAGES)} pages match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
