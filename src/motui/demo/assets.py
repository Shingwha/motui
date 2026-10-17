"""The demo's canned assets: the theme variants and the Markdown fixture.

One home for the data the demo's pages read and another wave will import:
the three skins the styles page's picker and the session's re-skin walk,
the fixture file beside this module, and the splitter that cuts a Markdown
source into the :mod:`motui.demo.streaming` exhibit's blocks.
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

#: The Markdown rendering fixture: the file beside this module.
FIXTURE = Path(__file__).with_name("fixture.md")

#: The fence runs a Markdown code block opens with, longest first: a line
#: that starts (after its indent) with three or more of one of these opens a
#: fence, and only a line of the same character, at least as long and nothing
#: else, closes it.  The splitter below tracks that state line by line.
FENCE_CHARS = ("`", "~")


def fixture_text() -> str:
    """The rendering fixture's source: the ``streaming`` exhibit's document."""
    return FIXTURE.read_text(encoding="utf-8")


def _fence_open(line: str) -> str | None:
    """The fence run ``line`` opens -- three or more backticks or tildes."""
    stripped = line.lstrip()
    for char in FENCE_CHARS:
        if stripped.startswith(char * 3):
            return char * (len(stripped) - len(stripped.lstrip(char)))
    return None


def blocks_of(text: str) -> list[str]:
    """The text's Markdown blocks, in source order -- the streaming unit."""
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
            elif len(line) >= len(fence) and set(line) == {fence[0]}:
                fence = None
        offset += len(raw)
    if start is not None:
        starts.append(start)
    if not starts:
        return []
    cuts = [*starts, len(text)]
    return [text[begin:end] for begin, end in zip(cuts, cuts[1:])]
