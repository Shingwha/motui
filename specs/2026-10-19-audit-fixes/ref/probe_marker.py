"""Probe (ref for W1/W5): the MORE_BELOW marker's conditions and ownership.

Layout-level truth: inspects ScreenLayout.rows / row_blocks directly, no
screen-byte parsing. Before W1: the marker appears when scrolled away from
the bottom, and its row still claims the displaced block's owner (F1).
After W1: no marker exists at all and every painted row is a block row or
blank fill.

Run: uv run python specs/2026-10-19-audit-fixes/ref/probe_marker.py
"""

from motui import Button
from motui.kernel.block import Document
from motui.kernel.viewport import Viewport

W, H = 40, 10


def make(n):
    doc = Document()
    for i in range(n):
        doc.add(Button(f"row {i}"), id=f"b{i}")
    return Viewport(doc)


def report(label, vp):
    layout = vp.layout(W, H)
    last = layout.rows[-1]
    marker = "more below" in last.text
    owner = layout.row_blocks[-1] if layout.row_blocks else None
    print(
        f"{label:<46} marker={'YES' if marker else 'no ':<3} "
        f"last-row owner={owner}  offset={layout.offset} total={layout.total_rows}"
    )
    return marker, owner


print(f"{'scenario':<46} result")
print("-" * 110)

vp = make(30)
report("30 blocks, fresh (sticky bottom)", vp)

vp = make(30)
vp.scroll_up(2)
report("30 blocks, scrolled up 2", vp)

vp = make(30)
vp.scroll_up(2)
vp.scroll_down(99)
report("30 blocks, scrolled up then back to bottom", vp)

vp = make(30)
vp.scroll_up(2)
vp.scroll_to_bottom()
report("30 blocks, scrolled up then scroll_to_bottom", vp)

vp = make(5)
report("5 blocks (fits), fresh", vp)
vp.scroll_up(2)
report("5 blocks (fits), scroll_up(2)", vp)

vp = make(30)
vp.scroll_up(5)
report("30 blocks, scrolled up 5", vp)
for i in range(29, 18, -1):
    vp.document.remove(f"b{i}")
report("...then 11 blocks removed (total=19)", vp)

print()
print("post-W1 expectation: no scenario prints marker=YES, and every last-row")
print("owner is either a real block row or None (blank fill) -- never a marker.")
