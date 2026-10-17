"""The gallery's canned content: the theme variants and the splitter.

Everything here is local and fixed -- no network, no model.  Page copy lives
beside the page that shows it; this module holds the theme variants
``/theme`` cycles and the styles exhibit's picker names, and
:func:`blocks_of` -- the splitter the ``streaming`` exhibit grows its
document with.  The fixture is the file beside this package: one 346-line
document, every construct the engine renders.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from motui import DEFAULT_THEME, Style

#: Three themes, two built with ``dataclasses.replace`` (nothing global is
#: mutated).  The variants recolor the default's own styles --
#: ``replace(..., fg=...)`` keeps each style's weight (the accent's bold), so
#: a variant only changes the hue -- and the hover band is restyled with the
#: variant so the pointer's highlight follows the skin.
THEMES = (
    ("default", DEFAULT_THEME),
    ("amber", replace(
        DEFAULT_THEME, accent=replace(DEFAULT_THEME.accent, fg="#e8a020"),
        heading=Style(fg="#e8a020"),
        selection=Style(bg="#3a2d12"),
        hover=Style(bg="#3a2d12", reverse=True),
    )),
    ("violet", replace(
        DEFAULT_THEME, accent=replace(DEFAULT_THEME.accent, fg="#9d7cd8"),
        heading=Style(fg="#9d7cd8"),
        selection=Style(bg="#2a2140"),
        hover=Style(bg="#2a2140", reverse=True),
    )),
)

#: The Markdown rendering fixture, one level up beside the entry point.
FIXTURE = Path(__file__).resolve().parent.parent / "Markdown-Rendering-Test.md"

#: The fence runs a Markdown code block opens with, longest first: a line
#: that starts (after its indent) with three or more of one of these opens a
#: fence, and only a line of the same character, at least as long and nothing
#: else, closes it.  The splitter below tracks that state line by line.
FENCE_CHARS = ("`", "~")


def fixture_text() -> str:
    """The rendering fixture's source: the ``streaming`` exhibit's document.

    Read with the universal newline translation (``\\r\\n`` in the file comes
    back as ``\\n``), so the text the exhibit streams is exactly the text
    every other reader of the fixture renders.
    """
    return FIXTURE.read_text(encoding="utf-8")


def _fence_open(line: str) -> str | None:
    """The fence run ``line`` opens -- three or more backticks or tildes.

    A fence opens at any indent: the marker is what makes the line a fence,
    not its column.  The answer is the run itself, which is what the closing
    line has to match in character and length; the rest of the line is the
    info string.  ``None`` for a line that opens no fence.
    """
    stripped = line.lstrip()
    for char in FENCE_CHARS:
        if stripped.startswith(char * 3):
            return char * (len(stripped) - len(stripped.lstrip(char)))
    return None


def _fence_close(line: str, fence: str) -> bool:
    """Whether ``line`` closes the open ``fence``: one character, long enough."""
    stripped = line.strip()
    return len(stripped) >= len(fence) and set(stripped) == {fence[0]}


def blocks_of(text: str) -> list[str]:
    """The text's Markdown blocks, in source order -- the streaming unit.

    A block is what a streamed document grows by: a heading, a paragraph, a
    list group, a table, a blockquote -- the units the Markdown source already
    speaks in -- separated by the source's blank lines.  A **fenced code
    block is never cut**, whatever blank lines its body holds: the splitter
    carries the fence state line by line, and only a line outside every fence
    lets a blank line end a block.  Fences do not nest, and the splitter only
    tracks unquoted ones -- a fence quoted in a blockquote belongs to the
    quote's own block, because the quote marker leads the line.

    Each block carries the blank lines that followed it, so the blocks
    concatenate back into the source exactly -- ``"".join(blocks_of(text)) ==
    text`` -- and every prefix a stream publishes is a byte-exact slice of the
    source, its last one the source itself.  A text with nothing but blank
    lines has no blocks.
    """
    starts: list[int] = []  # where each block begins, ascending
    start: int | None = None
    fence: str | None = None
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.strip()
        if not line and fence is None:
            if start is not None:
                starts.append(start)
                start = None
        else:
            if start is None:
                start = offset
            if fence is None:
                fence = _fence_open(line)
            elif _fence_close(line, fence):
                fence = None
        offset += len(raw)
    if start is not None:
        starts.append(start)
    if not starts:
        return []
    cuts = [*starts, len(text)]
    return [text[begin:end] for begin, end in zip(cuts, cuts[1:])]
