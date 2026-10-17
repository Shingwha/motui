"""The diff page: ``Diff`` -- two versions of one text, the hunks a reader wants.

Two versions of a small helper module of this very toolkit (the measuring
and cutting rows, before and after a refactor) are handed to
:class:`~motui.Diff` **at construction**: the line-level LCS runs once,
the hunks and their context are stored as rows, and :meth:`Diff.render`
only fits them to the pane.  The page shows the two shapes the context knob
has: the default three lines of context around each change (the changes
close together merge into one hunk, and a ``\u2026`` row marks the lines the
hunks skip), and ``context=0`` (every change its own tight hunk).  Four
change kinds are on display -- a kept line, a deletion, an insertion, and a
modified line, which is one deletion row and one insertion row.

The exhibit is static: ``Diff`` implements no interaction protocol -- no
``chosen``, no cursor, no ring target -- so the page mounts no focus ring
and the pane's own scrolling is the whole interaction.
"""

from __future__ import annotations

from motui import Text
from motui.widgets import Diff

from ..page import PageBody, api_note, header, section, try_line

__all__ = ["page"]

#: The "before" version: a module of measuring helpers, as it reads today.
BEFORE = '''\
def measure(text):
    """Display width of one row, in columns."""
    if not text:
        return 0
    return wcswidth(text)


def cut(row, start, end):
    """The sub-line covering display columns [start, end)."""
    return slice_line(row, start, end)


def pad(row, width):
    """Grow a row with plain spaces up to the width."""
    return row.pad_to(width)


def fit(row, width):
    """Truncate a row to the width, marking the cut."""
    return row.fit(width)
'''

#: The "after" version: the same module with the fixes of a later wave --
#: one line measure, one comment, one documented marker.  ``pad`` sits
#: unchanged between ``cut`` and ``fit``, so the last change is far enough
#: from the first two for the elision row to show in the default exhibit.
AFTER = '''\
def measure(text):
    """Display width of one row, cluster by cluster."""
    if not text:
        return 0
    return sum(width for _start, _stop, width in cell_spans(text))


def cut(row, start, end):
    """The sub-line covering display columns [start, end)."""
    # The floor rule lives in the boundary resolver.
    return slice_line(row, start, end)


def pad(row, width):
    """Grow a row with plain spaces up to the width."""
    return row.pad_to(width)


def fit(row, width):
    """Truncate a row to the width, marking the cut with an ellipsis."""
    return row.fit(width)
'''


def page(gallery) -> PageBody:
    """The two versions, the default diff, and the context=0 shape."""
    theme = gallery.theme
    return PageBody(
        [
            *header(
                "diff",
                "Diff -- two texts in, one line-level LCS at construction, and the hunks a "
                "reader wants out.",
                theme,
            ),
            try_line(
                "read down the hunks: `-` rows leave, `+` rows arrive, the three rows of "
                "context around each change stay, and \u2026 marks the lines the hunks skip",
                theme,
            ),
            Diff(BEFORE, AFTER, theme=theme),
            api_note(
                "Diff(before, after, *, context=3) -- the LCS runs once, in the constructor; "
                "render(width) only fits the stored rows",
                theme,
            ),
            section("context=0 -- every change its own hunk", theme),
            Diff(BEFORE, AFTER, context=0, theme=theme),
            api_note(
                "context=0 -- the changes alone; two hunks close together still merge into one",
                theme,
            ),
            section("the bounded walk", theme),
            Text(
                "Two texts that share almost nothing would cost one LCS cell per line pair, "
                "so past LCS_LIMIT (20000 pairs) the walk is skipped: the whole text is "
                "replaced in two hunks instead -- every line still visible, just not matched "
                "line by line. The degradation is a documented shape, not a slowdown. Two "
                "texts that split to the same lines render no rows at all.",
                style=theme.dim,
            ),
            api_note(
                "Diff is display-only -- no chosen, no cursor, no ring target: the pane "
                "scrolls it, nothing else plays with it",
                theme,
            ),
        ]
    )
