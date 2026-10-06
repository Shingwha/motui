# Spec 2026-10-06-frame-budget · W3 · Streaming Markdown renders what changed

> Branch `perf/w3-markdown-stream`; prerequisite: none (branches from latest
> `main`, file-disjoint from W1/W2). Deep read:
> `specs/2026-10-06-frame-budget/00-overview.md` (baselines, D1/D3), then
> `src/mocode_tui/widgets/markdown/component.py` (`Markdown.render`,
> `_run_blocks`), `src/mocode_tui/widgets/markdown/blocks.py` (the block
> loop, block-boundary semantics, the gap rule), and the viewport's open-block
> contract in `src/mocode_tui/core/viewport.py` (`_block_rows` — open blocks
> re-render on every layout).

## 目标

A growing or steady Markdown document must not re-parse from scratch every
frame — highest constraint first: **`Markdown.render(width)` stays a pure
function of `(text, width)` and returns byte-identical rows**, whatever the
cache. The component docstring's promise is the contract; the cache is
invisible.

## 证据（`main` `7c785c7` 的测量）

`render` runs `_run_blocks` over the full source on every call. While a
reply streams (`md.text` grows one line per frame), every frame re-parses
the whole accumulated source — O(n) per frame, O(n²) over the stream — and
an *unchanged* open block (the transcript markdown beside a streaming
preview) re-renders identically frame after frame. `stream-split` (58.9
ms/frame) carries both panes' renders.

## 工单（按序执行，每个 commit 独立过门禁）

### T1 The whole-render cache

- `Markdown.render(width)` caches its last `(text, width) → rows` answer
  (the `Style._prefix` value pattern, D3): a call at the same width with
  the same text returns the cached rows (a copy — the viewport treats
  returned lists as its own). Any text or width change re-renders and
  replaces the entry. One entry per component — this is a streaming
  working set, not a history.
- `text` is a plain public attribute (the streaming contract) — the cache
  keys on its value, no dirty flags on callers.

### T2 The append-only prefix reuse

- When the text **grew append-only** (the new text starts with the cached
  text's lines and the width is unchanged — `str.startswith` on the joined
  prefix or a line-wise check, whichever the implementation finds
  clearest), render only the rows the new source lines add and splice them
  onto the cached rows. The reuse must resume at a **block boundary**: the
  last cached source line that ended a block (the block loop's own rule —
  reuse nothing inside an open paragraph/fence/table/list) is the prefix's
  end; everything from there renders fresh. Text that shrank or changed
  mid-string takes the T1 path (full re-render, cache replaced).
- The result is byte-identical to a from-scratch render for every input —
  prove it with a differential test (ceiling: 3 functions total, existing
  files): a long fixture rendered whole vs rendered through a scripted
  sequence of append-only growths and mid-string rewrites, rows equal at
  every step. The NASTY corpus rows are fair input.
- Allowed files: `src/mocode_tui/widgets/markdown/**`,
  `tests/test_widgets_markdown.py`. One commit per work order, `perf:` style.

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` green — real tail line.
2. `uv run python tools/framebench.py` — run **twice**, report the second:
   `stream-single`/`stream-split` down measurably, `render-hash` exactly
   `5bcfdf164f89ca383194df2b1d3ac168137082220d690d708ba94c20423aba9a`, no
   line +5% or worse (W1/W2 may have landed first; measure against *your*
   worktree's pre-change numbers and say so).
3. `uv run python examples/pi_demo.py < /dev/null; echo exit=$?` → `exit=0`.

## 禁触清单

Everything outside `src/mocode_tui/widgets/markdown/**` and the one named
test file — including `core/**` (the viewport calls `render` and owns no
markdown state), `chat/**`, `tools/framebench.py`, `specs/`. If a fix
seems to need them, report the blocker and stop.

## 最终报告格式

工单状态表（commit hash + message）/ 门禁真实输出 / framebench 前后对比 /
偏差与取舍 / 未决问题。
