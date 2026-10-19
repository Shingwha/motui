"""Probe (ref for W5): hover hit-domain == click hit-domain, per component.

The library's stated invariant is that hover_at and click resolve a cell
through the same arithmetic. This probe walks every cell of every
interactive component's render grid and compares: does hover mark this cell
exactly when click consumes it?

Run: uv run python specs/2026-10-19-audit-fixes/ref/probe_hover_click.py
"""

from motui.widgets import (
    CheckGroup,
    Collapsible,
    List,
    NavList,
    Option,
    Radio,
    Select,
    Slider,
    Table,
    Tabs,
    Text,
    Tree,
)
from motui.widgets.tree import TreeNode

W = 60


def marked_state(component) -> bool:
    """Does the component currently carry a hover mark? (private state read)"""
    for attr in ("_hover_row", "_hover_index", "_hover_span", "_marked", "_hovered_row"):
        if hasattr(component, attr):
            value = getattr(component, attr)
            # a bool flag (Collapsible's _marked) vs an optional index/span
            return bool(value) if isinstance(value, bool) else value is not None
    return bool(getattr(component, "hover", False))


CASES = [
    ("Select", lambda: Select([Option("alpha"), Option("beta"), Option("gamma"), Option("delta")], title="pick one")),
    ("Radio", lambda: Radio(["one", "two", "three"])),
    ("CheckGroup", lambda: CheckGroup(["a", "b", "c"])),
    ("NavList", lambda: NavList(["overview", "text", "layout"])),
    ("List", lambda: List(["x", "y", "z"], window=2)),
    ("Table", lambda: Table(["h1", "h2"], [["r1a", "r1b"], ["r2a", "r2b"], ["r3a", "r3b"]])),
    ("Slider", lambda: Slider(4, maximum=10)),
    ("Collapsible", lambda: Collapsible("title", Text("body"))),
    ("Tabs", lambda: Tabs(["tab one", "tab two", "tab three"])),
    ("Tree", lambda: Tree([TreeNode("root", children=[TreeNode("child a"), TreeNode("child b", children=[TreeNode("leaf")])])])),
]

print(f"{'component':<12} {'cells':>6} {'agree':>7} {'mismatch':>9}  examples")
print("-" * 70)
total_mismatch = 0
for name, make in CASES:
    base = make()
    rows = base.render(W)
    agree = mismatch = 0
    bad = []
    for r in range(len(rows)):
        for c in range(W):
            a, b = make(), make()
            a.render(W)
            b.render(W)
            a.hover_at(r, c)
            marked = marked_state(a)
            clicked = b.click(r, c)
            if marked == clicked:
                agree += 1
            else:
                mismatch += 1
                if len(bad) < 3:
                    bad.append((r, c, marked, clicked))
    total_mismatch += mismatch
    tail = f"  e.g. (row,col,marked,clicked)={bad}" if bad else ""
    print(f"{name:<12} {len(rows) * W:>6} {agree:>7} {mismatch:>9}{tail}")

print()
print("TOTAL mismatches:", total_mismatch, "(must stay 0)")
