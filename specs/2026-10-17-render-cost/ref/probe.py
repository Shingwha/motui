"""Probe harness for the render-cost spec: the per-frame case table and the hover regressions.

Run it from anywhere, pointing at the branch's ``src``::

    python ref/probe.py C:\\Users\\shifu\\.worktrees\\mocode-tui\\rc-w1-row-cache\\src

Copy it to ``%TEMP%`` first (the spec forbids committing probe files into a branch)::

    cp specs/2026-10-17-render-cost/ref/probe.py "$TEMP/rc_probe.py"
    "C:/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python.exe" "$TEMP/rc_probe.py" <worktree>/src

Every number is a *best of N* wall-clock measurement of the branch actually checked out, so a
wave re-runs it and compares against the table in ``00-overview.md``. The ``hover`` cases are
booleans: they are the regression probes for the sealed-block staleness bug (D4).
"""

from __future__ import annotations

import sys
import time

SRC = sys.argv[1] if len(sys.argv) > 1 else "src"
sys.path.insert(0, SRC)

from motui import Editor, Markdown, Scrollbar, TUI, Table, Text  # noqa: E402
from motui.kernel import HeadlessScreen  # noqa: E402
from motui.kernel.lines import Line, Segment  # noqa: E402
from motui.kernel.style import NONE  # noqa: E402
from motui.widgets import Button  # noqa: E402

LINE = "line %d with some words in it, wrapped by the renderer as it goes\n"


def ms(fn, n=30):
    best = float("inf")
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        best = min(best, (time.perf_counter() - t0) * 1000)
    return best


def fresh(w=180, h=45):
    return TUI(screen=HeadlessScreen(w, h), interactive=False)


def rows_of(tui):
    return [row.styled() for row in tui.rows]


def case_table():
    print("== per-frame cases ==")
    # A. chrome turns the compose pass-through off
    t = fresh()
    b = t.add(Text("\n".join(LINE % i for i in range(200))))
    b.seal()
    t.paint()
    no_chrome = ms(t.paint, 50)
    t2 = fresh()
    b2 = t2.add(Text("\n".join(LINE % i for i in range(200))))
    b2.seal()
    Scrollbar(t2, pane="primary")
    t2.paint()
    with_bar = ms(t2.paint, 50)
    print(f"A. sealed 200-row pane: no chrome {no_chrome:.3f} ms | +scrollbar {with_bar:.3f} ms "
          f"({with_bar / no_chrome:.1f}x)   [target: +scrollbar <= 0.2 ms (W3)]")

    # B. Text: an OPEN block re-wraps everything per frame
    big = Text("\n".join(LINE % i for i in range(3000)))
    print(f"B. Text 3000 lines: render(80) {ms(lambda: big.render(80), 10):.2f} ms")
    t3 = fresh()
    b3 = t3.add(Text("\n".join(LINE % i for i in range(3000))))
    b3.seal()
    t3.paint()
    print(f"   sealed frame {ms(t3.paint, 20):.3f} ms | ", end="")
    t4 = fresh()
    t4.add(Text("\n".join(LINE % i for i in range(3000))))
    t4.paint()
    print(f"OPEN frame {ms(t4.paint, 20):.3f} ms   [target: <= 1 ms (W1)]")

    # C. Table: full-table materialization
    for n in (60, 240):
        tab = Table([f"col {c}" for c in range(6)],
                    [[f"cell {r}.{c}" for c in range(6)] for r in range(n)])
        print(f"C. Table {n}x6: render(150) {ms(lambda: tab.render(150), 10 if n == 60 else 5):.2f} ms")
    t5 = fresh()
    t5.add(Table([f"col {c}" for c in range(6)],
                 [[f"cell {r}.{c}" for c in range(6)] for r in range(60)]))
    t5.paint()
    print(f"   Table 60x6 OPEN frame {ms(t5.paint, 10):.2f} ms   [target: <= 1 ms (W2)]")

    # D. Editor: wraps the whole buffer per render and per keystroke
    ed = Editor(text="\n".join(f"def f{i}(x): return x * {i}" for i in range(3000)), max_rows=20)
    ed.render(80)
    print(f"D. Editor 3000 lines: cold {ms(lambda: Editor(text=chr(10).join(f'def f{i}(x): return x * {i}' for i in range(3000)), max_rows=20).render(80), 3):.2f} ms | "
          f"warm render {ms(lambda: ed.render(80), 10):.2f} ms | move_down {ms(ed.move_down, 5):.2f} ms/key"
          f"   [target: warm <= 1 ms, key <= 1 ms (W2)]")

    # E. Markdown: one growing paragraph streams quadratically
    for n in (200, 400):
        md = Markdown("")
        t0 = time.perf_counter()
        for i in range(n):
            md.text = md.text + f"word {i} of a growing paragraph "
            md.render(80)
        print(f"E. Markdown growing paragraph: {n} appends -> {(time.perf_counter() - t0) * 1000:8.1f} ms"
              f"   [target: near-linear, tail <= 1 ms @1000 (W4)]")

    # F. all-sealed layout walks every block
    for n in (100, 1000):
        t6 = fresh()
        for i in range(n):
            t6.add(Text(f"block {i}\nline two")).seal()
        t6.paint()
        print(f"F. {n} sealed blocks: frame {ms(t6.paint, 10):.3f} ms   [target: <= 0.1 ms @1000 (W1)]")

    # I. containers re-wrap the child's cached rows
    child = Markdown("\n".join(LINE % i for i in range(2000)))
    from motui.widgets import Panel
    print(f"I. Markdown 2000 lines render {ms(lambda: child.render(150), 10):.2f} ms | "
          f"Panel(child) render {ms(lambda: Panel(child).render(150), 5):.2f} ms   [target: <= 2 ms (W4)]")


class _SpanText(Text):
    """A Text whose first row carries an action span -- the hoverable leaf shape."""

    def _rows_for(self, width):
        return [Line((Segment("label ", NONE), Segment("click me", NONE, action="x")))]


def hover_cases():
    print("\n== hover regressions (sealed blocks must reach the screen) ==")
    # F1: Button -- the shape the audit measured
    t = fresh(60, 10)
    btn = Button("Ship")
    t.add(btn).seal()
    t.paint()
    before = rows_of(t)
    btn.hover = True
    t.paint()
    print(f"F1. sealed Button hover reaches the screen: {before != rows_of(t)}   [target: True (W1)]")

    # F2: Text with an action span
    t = fresh(60, 10)
    span = _SpanText("x")
    t.add(span).seal()
    t.paint()
    before = rows_of(t)
    span.hover_at(0, 8)          # inside "click me" (col 6..13)
    t.paint()
    print(f"F2. sealed Text span hover reaches the screen: {before != rows_of(t)}   [target: True (W1)]")

    # F3: Table cursor band on a sealed block
    t = fresh(60, 10)
    tab = Table(["a", "b"], [["1", "2"], ["3", "4"], ["5", "6"]])
    t.add(tab).seal()
    t.paint()
    before = rows_of(t)
    tab.hover_at(1, 0)           # the first data row (header is row 0)
    t.paint()
    print(f"F3. sealed Table hover reaches the screen: {before != rows_of(t)}   [target: True (W2)]")

    # F4: Markdown link label on a sealed block
    t = fresh(80, 12)
    md = Markdown("read [the docs](https://example.com) now")
    t.add(md).seal()
    t.paint()
    row = next((r for r in md.render(80) if any(s.action for s in r.segments)), None)
    col = 0
    if row is not None:
        for seg in row.segments:
            if seg.action:
                break
            col += seg.width
    before = rows_of(t)
    if row is not None:
        md.hover_at(0, col + 1)
    t.paint()
    print(f"F4. sealed Markdown link hover reaches the screen: {before != rows_of(t)}   [target: True (W4)]")


if __name__ == "__main__":
    case_table()
    hover_cases()
