"""The demo's canned assets: the theme variants and the Markdown fixture.

One home for the data the browser reads: the three skins ``c-t`` cycles
through, the fixture file beside this module, and the splitter the
streaming-Markdown pattern topic uses to append one block per beat.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from motui import DEFAULT_THEME, Style

#: The demo's band family: the opt-in the toolkit leaves to its host.  The
#: skins theme the **interactive** bands only -- a selection blue under the
#: keyboard cursor row and a lighter surface under the pointer -- so the demo
#: shows the feedback a reader needs (D3's split included: the pointer row
#: reads weaker than the cursor row) without painting a resting canvas.
#: Every band carries text, so the colours are chosen for contrast against
#: the default foreground and the accent labels, including the dim-free
#: unfocused state (a background band is not dimmed; see the widgets' focus
#: rule).  ``ground`` stays ``NONE`` on purpose: motui's ground is a row
#: band, not a region surface, and a page-wide one stripes every widget
#: instead of composing into a background.  A host that wants a resting
#: surface sets it where its shape is right (a menu row, a pill).
_DEFAULT_BANDS = {
    "ground_active": Style(bg="#1b3a5b"),
    "hover": Style(bg="#26303c"),
}

#: Three themes, all built with ``dataclasses.replace`` (nothing global is
#: mutated).  The variants recolor the default's own styles --
#: ``replace(..., fg=...)`` keeps each style's weight (the accent's bold), so
#: a variant only changes the hue -- and every variant themes the interactive
#: bands in its own palette: the cursor row's engaged band and the pointer's
#: band, so the pointer's highlight follows the skin and the cursor row stays
#: the stronger signal.  A background band is the whole signal: none of them
#: also reverses (reversing would swap the text into the band and undo the
#: contrast the hue was chosen for).
THEMES = (
    ("default", replace(DEFAULT_THEME, **_DEFAULT_BANDS)),
    ("amber", replace(
        DEFAULT_THEME, accent=replace(DEFAULT_THEME.accent, fg="#e8a020"),
        heading=Style(fg="#e8a020"),
        selection=Style(bg="#3a2d12"),
        ground_active=Style(bg="#3a2a0e"),
        hover=Style(bg="#2e2410"),
    )),
    ("violet", replace(
        DEFAULT_THEME, accent=replace(DEFAULT_THEME.accent, fg="#9d7cd8"),
        heading=Style(fg="#9d7cd8"),
        selection=Style(bg="#2a2140"),
        ground_active=Style(bg="#2c2450"),
        hover=Style(bg="#241d38"),
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
