# Spec 2026-10-06-frame-budget · W1 · The scanner and the splice

> Branch `perf/w1-scanner-splice`; prerequisite: none (branches from latest
> `main`). Deep read: `specs/2026-10-06-frame-budget/00-overview.md`
> (baselines, D1/D2), then `src/mocode_tui/core/text.py`
> (`_cell_spans`, `visible_width`, `index_pair_at_columns`),
> `src/mocode_tui/core/lines.py` (`cut_line`), `src/mocode_tui/core/frame.py`
> (`splice_row`).

## 目标

Cut the per-frame cost of the column-space machinery — highest constraint
first: **every rendered byte stays identical** (the render-hash invariant,
D1), and the cluster rules keep exactly one home (`core/text.py`, D2).

## 证据（`main` `7c785c7` 的剖析）

`cProfile` over `stream-split` (40 frames): `_cell_spans` resumed 1.35M
times, 2.9 s of a 4.6 s profile; `index_pair_at_columns` 18,450 calls
(3.07 s cumulative) from `cut_line` (22,140 calls) from `splice_row`
(7,380 = 184/frame × 3 cuts); `ord` alone 3.9M calls. `splice_row` resolves
its base row's two cut points with **two** walks, each from the string's
head: the left cut walks `x` cells, the right cut walks `x + width` cells
again.

## 工单（按序执行，每个 commit 独立过门禁）

### T1 One walk resolves every cut point of a splice

- Generalize the two-boundary resolver to N boundaries:
  `index_bounds_at_columns(text, *columns) -> tuple[int, ...]` — the floor
  rule written once, the pair and single-entry forms delegating to it
  (`index_at_column` keeps its name and signature; it is imported
  elsewhere and pinned by tests). The printable-ASCII fast path moves
  inside it: printable ASCII is one cell per character — the scanner's own
  rule — so a whole-ASCII string resolves arithmetically, and a mixed
  string's walk bulk-skips its printable-ASCII stretches (`used +=
  run_length`) while resolving any boundary inside a stretch
  arithmetically; every non-ASCII stretch goes through `_cell_spans`
  (D2: the scanner stays the only home of cluster semantics — the fast
  path must not know the cluster rules, only the ASCII rule).
- `splice_row` resolves its base row's `x`, `x + width` and `frame_width`
  cut points in **one** call and slices with `slice_line` — the pieces are
  byte-identical to `cut_line(base, …)` by construction (a cut *is*
  `slice_line` at resolved indices); the middle piece still cuts `line`.
- Postconditions pinned by test (extend `tests/test_core_text.py` — the
  NASTY corpus is already there): the N-boundary resolver agrees with
  N single-boundary calls on every corpus row and every boundary
  combination; `splice_row`'s tiling invariants hold unchanged.
- Allowed files: `src/mocode_tui/core/text.py`, `src/mocode_tui/core/lines.py`,
  `src/mocode_tui/core/frame.py`, `tests/test_core_text.py`,
  `tests/test_frame.py`. One commit, `perf:` style.

### T2 The per-character width is memoized

- The scanner's innermost call — one character's `wcwidth` — is pure and
  its answers repeat massively across frames (CJK transcripts). Memoize it
  (`functools.lru_cache` with a bounded maxsize, the `Style._prefix`
  pattern) at the one place the scanner asks, so `_cell_spans`' per-cluster
  cost drops without touching its rules.
- `visible_width`'s outputs must not move a column: the existing pins in
  `tests/test_core_text.py` must pass untouched, and the NASTY corpus rows
  measure identically to direct `wcwidth`/`wcswidth` (a focused
  differential test is the right shape).
- Allowed files: `src/mocode_tui/core/text.py`, `tests/test_core_text.py`.
  One commit, `perf:` style.

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` green — real tail line.
2. `uv run python tools/framebench.py` — run **twice**, report the second:
   `stream-split` down measurably from 58.9, `render-hash` exactly
   `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`, no
   line +5% or worse.
3. `uv run python examples/pi_demo.py < /dev/null; echo exit=$?` → `exit=0`.

## 禁触清单

Everything outside the allowed files — including `tools/framebench.py`,
`specs/`, `core/viewport.py` (W2's), `widgets/**` (W3's). If a fix seems to
need them, report the blocker and stop.

## 最终报告格式

工单状态表（commit hash + message）/ 门禁真实输出 / framebench 前后两行对比 /
偏差与取舍 / 未决问题。
