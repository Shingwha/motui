"""Probe harness for the diff-view spec: the case table + two cost differentials.

Run it from anywhere, pointing at the branch's ``src``::

    python ref/probe.py C:\\Users\\shifu\\.worktrees\\mocode-tui\\diff-w1-core\\src

Copy it to ``%TEMP%`` first (the spec forbids committing probe files into the branch):

    cp specs/2026-10-17-diff-view/ref/probe.py "$TEMP/probe.py"
    python "$TEMP/probe.py" <worktree>/src

It measures the **installed** ``motui.widgets.Diff`` (whatever the branch carries) and is
independent of the implementation: the oracle below is this file's own rolling-DP LCS, so a
green run really says "no more edits than an optimal script", not "the module agrees with
itself". The expected values are pinned in ``specs/2026-10-17-diff-view/00-overview.md``.
"""

from __future__ import annotations

import random
import re
import sys
import time

SRC = sys.argv[1] if len(sys.argv) > 1 else "src"
sys.path.insert(0, SRC)

from motui.widgets import Diff  # noqa: E402
from motui.widgets.diff import ELISION, LCS_LIMIT  # noqa: E402

ELISION_ROW = re.compile(r"^\u2026 (\d+) lines?$")


def lcs_length(b: list[str], a: list[str]) -> int:
    """Longest common subsequence length, one rolling row (the probe's own oracle)."""
    if not b or not a:
        return 0
    prev = [0] * (len(a) + 1)
    for line in reversed(b):
        row = [0] * (len(a) + 1)
        for j in range(len(a) - 1, -1, -1):
            row[j] = prev[j + 1] + 1 if line == a[j] else max(prev[j], row[j + 1])
        prev = row
    return prev[0]


def optimal_cost(before: str, after: str) -> int:
    """The minimal edit script's cost: deletions plus insertions."""
    b, a = before.splitlines(), after.splitlines()
    return len(b) + len(a) - 2 * lcs_length(b, a)


def texts(n, edits, insert_at=None, disjoint=False, alphabet=None):
    if alphabet is None:
        before = [f"def f{i}(x): return x * {i} + 1" for i in range(n)]
    else:
        before = [f"line {random.choice(alphabet)} of {i}" for i in range(n)]
    after = [f"other {i}()" for i in range(n)] if disjoint else list(before)
    for i in edits:
        after[i] = before[i] + "  # edited"
    if insert_at is not None:
        after.insert(insert_at, "# a header comment added at the top")
    return "\n".join(before), "\n".join(after)


def measure(label, before, after, width=80, repeats=20):
    t0 = time.perf_counter()
    diff = Diff(before, after)
    build = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    rows = diff.render(width)
    first = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    for _ in range(repeats):
        diff.render(width)
    repeat = (time.perf_counter() - t0) / repeats * 1000
    texts_ = [row.text for row in rows]
    hunks = sum(1 for t in texts_ if t.startswith("@@"))
    elisions = [
        (m.group(1) if (m := ELISION_ROW.match(t)) else "?")
        for t in texts_
        if t == ELISION or ELISION_ROW.match(t)
    ]
    print(
        f"{label:<44} rows={len(rows):>5} hunks={hunks:>3} elisions={elisions} "
        f"build={build:7.2f}ms render1={first:7.2f}ms render_rep={repeat:7.3f}ms"
    )
    return len(rows), hunks, elisions


def case_table():
    print("== case table ==")
    cases = [
        ("2000 lines, one edit in the middle", texts(2000, [1000])),
        ("2000 lines, one line inserted at the top", texts(2000, [], insert_at=0)),
        ("500 lines, three edits spread (10/250/490)", texts(500, [10, 250, 490])),
        ("300 lines, one edit", texts(300, [150])),
        ("1000 lines, every other line changed", texts(1000, range(0, 1000, 2))),
        ("2000 vs 2000, nothing in common", texts(2000, [], disjoint=True)),
    ]
    for label, (before, after) in cases:
        measure(label, before, after)
    print("identical texts:", len(Diff("a\nb\nc", "a\nb\nc").render(80)), "rows (expect 0)")
    print(f"LCS_LIMIT = {LCS_LIMIT}, ELISION = {ELISION!r}")


def differential_small(trials=20000, seed=11):
    """Both sides under the budget: the trim path vs the oracle."""
    print(f"== differential, small inputs ({trials} trials) ==")
    rng = random.Random(seed)
    worse = same = 0
    worst = 0
    for _ in range(trials):
        alphabet = [f"L{i}" for i in range(rng.choice([2, 3, 6, 20]))]
        before = "\n".join(rng.choice(alphabet) for _ in range(rng.randint(0, 14)))
        after = "\n".join(rng.choice(alphabet) for _ in range(rng.randint(0, 14)))
        rows = [row.text for row in Diff(before, after).render(80)]
        cost = sum(1 for t in rows if t.startswith("-") or t.startswith("+"))
        best = optimal_cost(before, after)
        if cost > best:
            worse += 1
            worst = max(worst, cost - best)
        elif cost == best:
            same += 1
    print(f"trials={trials} same_as_optimal={same} worse={worse} max_delta={worst}")


def differential_anchored(trials=300, seed=23):
    """Over-budget inputs with unique lines: the anchored path vs the oracle."""
    print(f"== differential, anchored path ({trials} trials of 300x300) ==")
    rng = random.Random(seed)
    worse = same = 0
    worst = 0
    ceiling_violations = 0
    for _ in range(trials):
        alphabet = [f"TOKEN_{i}" for i in range(40)]
        # Every line carries its index, so lines are unique within the corpus: the
        # anchors have something to bite on, which is what this arm measures.
        b = [f"line {rng.choice(alphabet)} of {i}" for i in range(300)]
        a = list(b)
        for _ in range(rng.randint(1, 6)):
            i = rng.randrange(len(a))
            a[i] = a[i] + "  # touched"
        before, after = "\n".join(b), "\n".join(a)
        rows = [row.text for row in Diff(before, after).render(80)]
        cost = sum(1 for t in rows if t.startswith("-") or t.startswith("+"))
        best = optimal_cost(before, after)
        if cost > len(b) + len(a):
            ceiling_violations += 1
        if cost > best:
            worse += 1
            worst = max(worst, cost - best)
        elif cost == best:
            same += 1
    print(
        f"trials={trials} same_as_optimal={same} worse={worse} max_delta={worst} "
        f"over_ceiling(n+m)={ceiling_violations}"
    )


if __name__ == "__main__":
    case_table()
    print()
    differential_small()
    print()
    differential_anchored()
