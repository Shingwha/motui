"""The content page: ``Text``, ``Markdown`` and ``Diff`` -- the content primitives.

The Markdown sample is one of every construct the engine renders, and the
page is its whole loop: a click on the link label or a task box lands a
pick in ``chosen``, the host reads it once and the page's ``note`` echoes
it (a ``todo:<i>`` pick rewrites the sample's own text, so the box flips)."""

from __future__ import annotations

import re

from motui import Markdown, Text
from motui.kernel import DIM
from motui.widgets import Diff, Divider

from ..page import PageBody, api_note, header, section, try_line

#: The Markdown sample: one of every construct the engine renders, task
#: items included (the last section is the clickable-box exhibit).
MARKDOWN_SAMPLE = """\
### A Markdown block

Prose with **bold**, *italic*, `inline code` and a [link](https://example.invalid)
-- wrapped to the pane, never past it.

1. numbered items
2. a second one

> A quote, for the record.

```python
def hello(name: str) -> str:
    return f"hello {name}"
```

| column | meaning |
|:-------|--------:|
| rows   | 2       |

- [ ] click a box -- the host flips the source
- [x] and this one is already done
"""

#: The wrapping exhibit: one long paragraph, broken on the pane's edge.
PARAGRAPH = (
    "Plain Text is the kernel's simplest component: one logical line per "
    "\\n, each word-wrapped to the width its parent hands it. The pane you "
    "are reading is a Viewport window over one document; the scrollbar on "
    "the right maps the part above and below the fold."
)

#: The "before"/"after" versions the ``Diff`` exhibit compares: the measuring
#: and cutting rows of this very toolkit, before and after a refactor.
BEFORE = '''\
def measure(text):
    """Display width of one row, in columns."""
    return wcswidth(text)


def fit(row, width):
    """Truncate a row to the width, marking the cut."""
    return row.fit(width)
'''

AFTER = '''\
def measure(text):
    """Display width of one row, cluster by cluster."""
    return sum(width for _start, _stop, width in cell_spans(text))


def fit(row, width):
    """Truncate a row to the width, marking the cut with an ellipsis."""
    return row.fit(width)
'''

# Task marker lines in source order: the flat index counts these, exactly the
# order the rendered rows carry their ``todo:<i>`` payloads.
_TASK_LINE = re.compile(r"^(\s*[-*]\s+)\[([ xX])\](.*)$")


def _flip_task(text: str, index: int) -> str:
    """The host's own rewrite: flip the ``index``-th task marker in ``text``."""
    out: list[str] = []
    count = 0
    for line in text.split("\n"):
        matched = _TASK_LINE.match(line)
        if matched is not None:
            if count == index:
                box = " " if matched.group(2) in "xX" else "x"
                line = f"{matched.group(1)}[{box}]{matched.group(3)}"
            count += 1
        out.append(line)
    return "\n".join(out)


def page(session) -> PageBody:
    """The two content primitives, the diff, and the pick echoes."""
    theme = session.theme
    # The link echo: empty until a pick lands, so the line appears exactly
    # when there is something to report (and the page renders identically
    # before the first click).
    echo = Markdown("", theme=theme)
    sample = Markdown(MARKDOWN_SAMPLE, theme=theme)

    def note(text: str) -> None:
        """One pick was reported: echo it, and run the task loop on a box."""
        echo.text = f"echo \u25b8 {text}"
        pick = text.removeprefix("chosen: ").strip("'")
        if pick.startswith("todo:"):
            sample.text = _flip_task(sample.text, int(pick.removeprefix("todo:")))

    return PageBody([
        *header("content",
                "Text, Markdown and Diff -- the primitives that carry content, and the one "
                "that renders it.", theme),
        try_line("click the sample's link label, or a task box to flip it -- the toast and "
                 "the echo line report the pick", theme),
        section("Markdown -- one sample of every construct", theme),
        sample,
        api_note("Markdown(text) -- a rule-registry engine; fences, tables, task items and "
                 "inline rules", theme),
        # The row the sample's picks echo on (a toast reports them too).
        echo,
        api_note("Markdown.click(row, col) -> chosen: a link's url, a task box's 'todo:<i>' "
                 "-- the host reads it once and rewrites the text", theme),
        section("Text -- one paragraph, word-wrapped to the pane", theme),
        Text(PARAGRAPH, style=DIM),
        api_note("Text(text, style=\u2026) -- one logical line, wrapped by the renderer", theme),
        section("Divider -- two ways", theme),
        Divider(theme=theme),
        Divider(theme=theme, label="a labelled rule"),
        api_note("Divider(label=\u2026, char=\u2026, max_width=\u2026)", theme),
        section("Diff -- two texts, one line-level LCS, the hunks a reader wants", theme),
        Diff(BEFORE, AFTER, theme=theme),
        api_note("Diff(before, after, *, context=3) -- the LCS runs once, in the "
                 "constructor", theme),
    ], note=note)
