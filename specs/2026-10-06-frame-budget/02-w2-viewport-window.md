# Spec 2026-10-06-frame-budget · W2 · The viewport paints its window, not its document

> Branch `perf/w2-viewport-window`; prerequisite: none (branches from latest
> `main`, file-disjoint from W1/W3). Deep read:
> `specs/2026-10-06-frame-budget/00-overview.md` (baselines, D1/D3), then
> `src/mocode_tui/core/viewport.py` whole, and its callers in
> `src/mocode_tui/app.py` (`viewport_region`, `_band_rect`) plus
> `src/mocode_tui/chrome.py` (`_thumb_of` reads `ScreenLayout.offset` /
> `total_rows` / `viewport_rows`).

## 目标

`Viewport.layout` must stop materializing the whole document on every frame
— highest constraint first: **the returned `ScreenLayout` is byte-identical
in content** (same `rows`, same `row_blocks` table, same
`offset`/`total_rows`/`viewport_rows`), and every documented behavior
(clamps, stick-to-bottom, the MORE_BELOW marker, blank fill, fixed-region
truncation order) is preserved exactly.

## 证据（`main` `7c785c7` 的测量）

`layout` extends every block's rows into `body_rows` and builds an
`(id, row)` owner tuple for every row of every block — then slices the
~45-row window. Cost is O(document) per frame per pane; `scroll-long`
(3000 sealed rows) measures **53.6 ms/notch** against `scroll`'s 9.8 —
the 5.4× is the materialization. The frame never paints more than the
window.

## 工单（按序执行，每个 commit 独立过门禁）

### T1 Window slicing over per-block geometry

- Maintain, per viewport, the per-block row counts and running body offsets
  alongside the existing sealed-row cache (same invalidation triggers: the
  width changed, the block set changed, the block identity changed, the
  block is open). A layout then:
  - renders only the blocks it must (open ones, and sealed ones missing
    from the cache) — a sealed block's cached rows are sliced, never
    copied whole;
  - extends the window rows and the window's owner tuples from the blocks
    overlapping `[offset, offset + vh)`;
  - computes `total_rows` from cached counts, never from a concatenated
    list.
- Every documented behavior survives: clamping and stick-to-bottom, the
  MORE_BELOW overwrite, blank fill below short content, bottom-region
  precedence and top-region truncation, `row_blocks` (still a fresh list
  per layout, `None` for unowned rows, the marker keeping the row it
  covers), `ScreenLayout`'s fields. `natural_height` keeps its meaning and
  may share the same counts.
- The cached-counts structure is value-shaped (D3): keyed on width and
  block identity, invalidated where the existing cache already
  invalidates — no new invalidation flags on callers.
- Focused regression (ceiling: 3 functions, existing files —
  `tests/test_viewport.py`): window slicing equals full materialization
  for a long document at several offsets, window heights and widths; the
  ownership table is identical row for row; an open block interleaved
  between sealed ones still lands its rows at the right addresses.
- Allowed files: `src/mocode_tui/core/viewport.py`,
  `tests/test_viewport.py`. One commit, `perf:` style.

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` green — real tail line.
2. `uv run python tools/framebench.py` — run **twice**, report the second:
   `scroll-long` down measurably from 53.6, `render-hash` exactly
   `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`, no
   line +5% or worse (W1 may land first and move the floor; measure against
   *your* worktree's pre-change numbers and say so).
3. `uv run python examples/pi_demo.py < /dev/null; echo exit=$?` → `exit=0`.

## 禁触清单

Everything outside `src/mocode_tui/core/viewport.py` and
`tests/test_viewport.py` — including `core/block.py` (the block lifecycle
is frozen), `tools/framebench.py`, `specs/`. If a fix seems to need them,
report the blocker and stop.

## 最终报告格式

工单状态表（commit hash + message）/ 门禁真实输出 / framebench 前后对比 /
偏差与取舍 / 未决问题。
