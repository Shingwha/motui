"""The text page: ``Text``, ``Markdown``, ``Diff`` and ``Spacer`` -- the content primitives.

The Markdown sample is one of every construct the engine renders, and the
page is its whole loop: a click on the link label or a task box lands a
pick in ``chosen``, the host reads it once, the toast reports it and the
page's ``watch`` echo line answers (a ``todo:<i>`` pick rewrites the
sample's own text, so the box flips)."""

from __future__ import annotations

import re

from motui import Markdown, Text
from motui.kernel import DIM
from motui.widgets import Diff, Divider, Spacer

from ..kit import Exhibit, Pick
from ..page import PageBody

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
#: and cutting rows of this very toolkit, before and after a refactor.  The
#: untouched ``split`` between the two edits keeps them further apart than
#: twice the default context, so the exhibit really shows the counted
#: elision row between the hunks.
BEFORE = '''\
def measure(text):
    """Display width of one row, in columns."""
    return wcswidth(text)


def split(text):
    """Logical lines: str.splitlines, so a trailing newline adds none."""
    return text.splitlines()


def fit(row, width):
    """Truncate a row to the width, marking the cut."""
    return row.fit(width)
'''

AFTER = '''\
def measure(text):
    """Display width of one row, cluster by cluster."""
    return sum(width for _start, _stop, width in cell_spans(text))


def split(text):
    """Logical lines: str.splitlines, so a trailing newline adds none."""
    return text.splitlines()


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
    """The text primitives, the diff, the spacer, and the pick echoes."""
    exhibit = Exhibit(
        session,
        title="text",
        blurb="Text, Markdown, Diff and Spacer -- the primitives that carry content, and "
              "the one that renders it.",
        try_text="click the sample's link label, or a task box to flip it -- the toast and "
                 "the echo line report the pick",
        echo_label="echo",
    )
    sample = Markdown(MARKDOWN_SAMPLE, theme=session.theme)

    def watch(pick: Pick) -> None:
        """One pick was reported: a task box flips the sample's own text."""
        value = pick.value
        if isinstance(value, str) and value.startswith("todo:"):
            sample.text = _flip_task(sample.text, int(value.removeprefix("todo:")))

    exhibit.watch(watch)
    exhibit.section("Markdown -- one sample of every construct")
    exhibit.show(
        sample,
        api="Markdown(text) -- a rule-registry engine; fences, tables, task items and "
            "inline rules",
    )
    # The row the sample's picks echo on (a toast reports them too); empty
    # until a pick lands, so the page renders identically before the click.
    exhibit.show(
        exhibit.echo,
        api="Markdown.click(row, col) -> chosen: a link's url, a task box's 'todo:<i>' "
            "-- the host reads it once and rewrites the text",
    )
    exhibit.section("Text -- one paragraph, word-wrapped to the pane")
    exhibit.show(Text(PARAGRAPH, style=DIM),
                 api="Text(text, style=\u2026) -- one logical line, wrapped by the renderer")
    exhibit.section("Divider -- two ways")
    exhibit.show(Divider(theme=session.theme))
    exhibit.show(Divider(theme=session.theme, label="a labelled rule"),
                 api="Divider(label=\u2026, char=\u2026, max_width=\u2026)")
    exhibit.section("Diff -- two texts, one line-level LCS, the hunks a reader wants")
    exhibit.show(Diff(BEFORE, AFTER, numbers=True, theme=session.theme),
                 api="Diff(before, after, *, context=3, numbers=True) -- the LCS runs once, "
                     "in the constructor; the \u2026 rows count the lines they skip")
    exhibit.section("Spacer -- blank rows between the blocks")
    exhibit.show(Spacer(2),
                 api="Spacer(rows=\u2026) -- vertical whitespace as a first-class component")
    return exhibit.build()
