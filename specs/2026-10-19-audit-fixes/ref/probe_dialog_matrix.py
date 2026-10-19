"""Probe (ref for W2/W5): the Dialog frame-parameter staleness matrix (F2).

Warms a block cache (two rows() calls -- the first caches under the
pre-render snapshot), then mutates each row input render() reads through its
helpers and checks whether Block.rows serves stale rows.

Run: uv run python specs/2026-10-19-audit-fixes/ref/probe_dialog_matrix.py
"""

from motui import Dialog, Text
from motui.testing import headless_tui


def fresh_block():
    tui = headless_tui(80, 24)
    dialog = Dialog("first title", Text("body line"), ["ok", "cancel"])
    return tui, dialog, tui.add(dialog, id="d")


def rows_text(rows):
    return [r.text for r in rows]


print(f"{'mutation':<28} {'stale?':>8}  detail")
print("-" * 70)
for label, mutate in [
    ("title = 'second title'", lambda d: setattr(d, "title", "second title")),
    ("width = 40", lambda d: setattr(d, "width", 40)),
    ("frame = False", lambda d: setattr(d, "frame", False)),
    ("shade = False", lambda d: setattr(d, "shade", False)),
    ("align = 'right'", lambda d: setattr(d, "align", "right")),
]:
    tui, dialog, block = fresh_block()
    block.rows(80)  # call 1: caches under the pre-render (empty body) key
    block.rows(80)  # call 2: caches under the post-render key -- the warm cache
    mutate(dialog)
    cached = rows_text(block.rows(80))
    direct = rows_text(dialog.render(80))
    stale = cached != direct
    first_diff = next((i for i, (a, b) in enumerate(zip(cached, direct)) if a != b), None)
    print(f"{label:<28} {'STALE' if stale else 'fresh':>8}  first differing row: {first_diff}")

print()
print("post-W2 expectation: every row answers 'fresh'.")
