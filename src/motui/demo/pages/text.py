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
        blurb="Text, Markdown, Diff and Spacer -- the primitives that carry content.",
    )
    sample = Markdown(MARKDOWN_SAMPLE, theme=session.theme)

    def watch(pick: Pick) -> None:
        """One pick was reported: a task box flips the sample's own text."""
        value = pick.value
        if isinstance(value, str) and value.startswith("todo:"):
            sample.text = _flip_task(sample.text, int(value.removeprefix("todo:")))

    exhibit.watch(watch)
    exhibit.section("text",
                    Text(PARAGRAPH, style=DIM),
                    caption="one paragraph \u00b7 word-wrapped to the pane")
    exhibit.section(
        "markdown",
        sample,
        caption="prose \u00b7 fence \u00b7 table \u00b7 quote \u00b7 two task boxes",
    )
    # The row the sample's picks echo on (a toast reports them too); empty
    # until a pick lands, so the page renders identically before the click.
    exhibit.show(exhibit.echo)
    exhibit.section(
        "divider",
        Divider(theme=session.theme),
        Divider(theme=session.theme, label="a labelled rule"),
        caption="plain \u00b7 labelled",
    )
    exhibit.section(
        "diff",
        Diff(BEFORE, AFTER, numbers=True, theme=session.theme),
        caption="numbered \u00b7 elisions counted \u00b7 three lines of context",
    )
    exhibit.section("spacer", Spacer(2), caption="2 blank rows between the blocks")
    return exhibit.build()
