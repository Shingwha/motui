# Spec 2026-10-06-split-row-truth · W1 · The split row is a grid and a segment is a clean slate

> ✅ 2026-10-06 @ `fix/w1-row-truth` — merged; T1 `e93fc85`, T2 `81ccca8`,
> gate 803 passed / 1 skipped. One authorized deviation from the allowed
> file list: the `test_widgets_containers.py` pin that asserted the old
> leaky `styled()` scheme (lead-approved, bytes in the worker's report).

> Branch `fix/w1-row-truth`; prerequisite: none (branches from latest
> `main`). Deep read: `specs/2026-10-06-split-row-truth/00-overview.md`
> (evidence + decisions D1-D4), then `src/mocode_tui/core/text.py`
> (`visible_width`, `fit_text`), `src/mocode_tui/core/lines.py`
> (`styled`, `cut_line`, `_column_to_index`, `pad_to`),
> `src/mocode_tui/core/frame.py` (`splice_row`, `_splice_chrome`).

## 目标

Restore the two invariants the split frame renders under — highest
constraint first: **no behavior change outside the two roots**. (1) A frame
row is a grid: `splice_row`'s pieces tile their windows exactly, on every
row, whatever clusters it contains — so the right pane's first column is the
same column on every row. (2) A `Line` segment renders from a clean SGR
slate: no attribute crosses a segment boundary — so the right pane's text
carries neither the scrollbar's `dim` nor the separator's `bold`.

## 证据（已在 `main` `24c8ed6` 复现，工单完成后须同样手段复验）

Run with `uv run python` from the worktree root (a scratch script, not
committed):

```python
import sys; sys.path.insert(0, "src")
from mocode_tui.core.lines import Line, cut_line
from mocode_tui.core.frame import splice_row
base = Line.from_text("A\u26a0\ufe0fB")
print(cut_line(base, 0, 2).width)            # today: 3   (window promised 2)
out = splice_row(Line.from_text("A\u26a0\ufe0fB     "), Line("#"), 6, 1, 10)
print(out.width)                             # today: 11  (frame promised 10)
from mocode_tui.core.lines import Segment
from mocode_tui.core.style import Style
row = Line([Segment("x", Style()), Segment("░", Style(dim=True)),
            Segment(" ", Style(fg="#58a6ff", bold=True)),
            Segment("### Escaping", Style(fg="#e3b341"))])
print(repr(row.styled()))  # today: dim+bold bleed into the heading, 1 RESET total
```

And end to end (the demo the owner screenshotted):
`uv run python examples/pi_demo.py < /dev/null` must still exit 0.

## 工单（按序执行，每个 commit 独立过 `uv run pytest -q` 全绿）

### T1 `cut_line` walks clusters — a splice window can never straddle one

- Move the column→index walk onto the cluster rules (decision D1): the
  scanner that `visible_width` runs becomes the one place in `core/text`
  that knows cluster boundaries, and the column walk is a second view of it
  (share the rule constants and the walk; do not write a second scanner).
  `lines._column_to_index` either moves to `core/text` under an honest name
  or becomes a one-call delegation — but `lines.py` keeps no width
  arithmetic of its own.
- The floor rule stays and finally becomes true for every cluster: a cut
  boundary landing strictly inside a multi-cell cluster snaps **down** to
  that cluster's start, exactly as it already does for plain wide (CJK)
  characters. Postconditions to pin by test:
  - `cut_line(line, a, b).width <= b - a`, with equality whenever the window
    is covered by cells (no cluster straddles `a` or `b`);
  - for `base.width == frame_width` and `line.width <= width`:
    `splice_row(base, line, x, width, frame_width).width == frame_width` —
    the tiling invariant, on rows with and without VS16/ZWJ clusters;
  - `visible_width` outputs unchanged (the existing `tests/test_core_text.py`
    pins already do this — they must pass untouched).
- Regression tests (ceiling D4: ≤2 functions here) in
  `tests/test_core_text.py` and/or `tests/test_frame.py` — pick the file
  each assertion already belongs in; no new files.
- Allowed files: `src/mocode_tui/core/text.py`,
  `src/mocode_tui/core/lines.py`, `tests/test_core_text.py`,
  `tests/test_frame.py`. One commit, `fix:` style.

### T2 `styled()` resets between segments — no SGR attribute crosses a boundary

- Rewrite `Line.styled()` to decision D2's rule: every segment after the
  first non-empty one is preceded by `RESET`; a segment's prefix then its
  text; the trailing `RESET` unchanged; zero-width segments still paint
  nothing and open no reset. Update the docstring to state the rule it now
  implements (the current docstring already claims the intent — keep the
  claim, fix the mechanism).
- Update exact-string expectations that encoded the leaky scheme (grep
  `styled` under `tests/`); each moved pin goes into the report with its old
  and new bytes. No assertion may lose strength: where the old string
  asserted the leak, assert the reset.
- Regression test (≤2 functions here) asserting, on the evidence row above,
  that the heading's gold prefix is the first SGR after a `RESET` and the
  whole line still ends with exactly one trailing `RESET`. Same two test
  files are available; no new files.
- Allowed files: `src/mocode_tui/core/lines.py`, `tests/test_core_text.py`,
  `tests/test_frame.py`. One commit, `fix:` style.

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` all green — paste the real tail line (count + skips).
2. The evidence script above prints: `2`, `10`, and a `styled()` string
   whose only `ESC[2m` is on the track segment — paste all three.
3. `uv run python examples/pi_demo.py < /dev/null; echo exit=$?` → `exit=0`.
4. A byte-level A/B for the split: compose the demo's two-pane frame
   headless (the `/preview` shape — Scrollbar on `primary`, `_Separator`
   from `TUI.split`, the markdown fixture in both panes at 180x45) before
   and after, and show for one `⚠️`-bearing row that (before) the right
   pane's slice at its region `x` lost its first cells and (after) it reads
   exactly as the pane's own layout row.

## 禁触清单

Everything not listed in T1/T2's allowed files — including
`examples/pi_demo.py`, `core/frame.py`, `core/style.py`, `core/painter.py`,
all `chat/` and `widgets/` modules. If a fix seems to need one of them,
that is a wrong fix: report the blocker and stop.

## 最终报告格式

- 工单状态表：T1/T2 → commit hash + one-line message。
- 自测真实结论：四条验收的真实输出（用例数、三个打印值、exit code、A/B）。
- 偏差与取舍：moved pins（old bytes → new bytes + reason）、扫描器形状的
  最终决定（搬移还是委托）。
- 未决问题：无则写 none。
