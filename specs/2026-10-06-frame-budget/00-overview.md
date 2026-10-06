# Spec Group 2026-10-06-frame-budget · The frame budget

> ✅ 2026-10-06 — the group is closed: all three waves merged
> (`merge: perf W1 -- one column walk per splice, the scanner's widths
> memoized`; `merge: perf W2 -- the viewport slices its window out of
> per-block geometry`; `merge: perf W3 -- streaming markdown renders what
> changed`). Gates on the merged tree: 843 passed / 1 skipped; the
> render-hash is byte-identical through every merge; the demo's piped
> replay exits 0.

## The closed group's numbers

Measured on the merged tree, same window, against a fresh pre-merge
measurement of the same box (the overview's own table below was taken in a
noisy window — machine settling moved every absolute number by ~2.5×; the
A/B deltas are the honest currency, and every wave interleaved its own
before/after):

| workload | pre-group (same window) | merged | Δ |
|---|---|---|---|
| stream-single | 7.1 ms/frame | **3.9** | −45% |
| stream-split | 19.7 ms/frame | **9.4** | −52% |
| scroll | 3.3 ms/notch | **2.3** | −30% |
| scroll-long | 16.3 ms/notch | **15.8** | −3% (the notch is dominated by 2,950 open `Text` blocks re-rendering per layout — by-design cost; W2's isolated `Viewport.layout` microbench: −35%) |
| replay | 194 ms | **196 ms** | flat |
| render-hash | `5bcfdf16…` | `5bcfdf16…` | byte-identical |

Per-wave attributions (each wave's interleaved A/B, from its report):
W1 stream-split −34%, W3 stream-single −28% / stream-split −18% /
`Markdown.render` 9–12× on the streaming shapes, W2 `Viewport.layout` −35%
on the 3000-row shape.

## Deviations recorded at close

- **W1: the ASCII fast path is narrower than the spec's wording, by
  necessity.** Bulk-skipping a printable-ASCII stretch *to its end* is not
  byte-safe — a ZWJ run can swallow the ASCII character after it, so the
  seam with `_cell_spans` would move. The committed walk skips a run up to
  its last character and leaves that character to the scanner; differential
  testing caught 2.2M then 951k mismatches in the literal versions, zero in
  the committed one (4,030 rows × every boundary combination; 194,208
  splice shapes). D2's "provably equal to the scanner's answer" was the
  binding rule; the wording was not.
- **W2: the cache-prune keys on sealed ids** (the cache only ever holds
  sealed entries and sealing is one-way) — removes an O(document) set
  construction per layout; identity checks in `_block_rows` still cover a
  reused id. Disclosed and recovered mid-wave: a `git checkout` during
  mutation testing reverted the implementation; the edits were re-applied
  and re-verified (tests + render-hash).
- **W3: conservative on both edges of reuse** — the resume declines a
  block that reached the buffer's end *and* a closed trailing block
  (heading/break/fence-closing-line), and the prefix equality is line-wise
  (`str.startswith` would accept a rewritten last line). One block of slack
  per stream, judged not worth per-block rule identity in the cache entry.

> Lead: the main ZCode session. Workers: one agent per wave, three waves
> (01–03), run in parallel — their write scopes are file-disjoint. Lineage:
> follows `2026-10-06-split-row-truth` (closed). Conventions carry over:
> English one-line imperative commits, no lint/type tooling, no push/tags,
> worktrees at `C:\Users\shifu\.worktrees\mocode-tui\<branch>`, lead merges
> only (`--no-ff`), specs are lead-owned.

## Owner brief

After the split-row-truth fixes the demo is usable again, but the split
still costs ~59 ms/frame against the pump's 30 ms budget, and a long
transcript costs ~54 ms per wheel notch. The brief: find every remaining
structural cost in the per-frame path and remove it — without changing one
rendered byte. 全方位，但每一刀都要有测量背书。

## The measuring stick (lead-owned, do not edit)

`tools/framebench.py` — four workloads plus the invariant. Baselines on
`main` `7c785c7` (all workers measure against these; run the bench **twice**
and record the second run — the first pays Windows Defender's first-scan on
freshly written files):

| workload | baseline | what it is |
|---|---|---|
| stream-single | 21.5 ms/frame | one pane, open Markdown growing per frame |
| stream-split | 58.9 ms/frame | transcript \| preview, both composed every frame |
| scroll | 9.8 ms/notch | 350 sealed rows, wheel storm |
| scroll-long | 53.6 ms/notch | 3000 sealed rows, wheel storm |
| replay | ~480 ms | the demo's whole piped replay |
| render-hash | `5bcfdf16…3aba9a` | sha256 of one deterministic session's every recorded output byte |

**The render-hash invariant: a performance wave that moves the hash has
changed what the user sees, and has failed.**

## Where the time goes (lead's profiles, `main` `7c785c7`)

1. **The cluster scanner, driven by the splice storm.** `_cell_spans` is
   resumed 33.7k times per stream-split frame (2.9 s of a 4.6 s profile);
   `splice_row` runs 184 times per frame and `cut_line` 553 — every pane row
   of both panes is cut three times, and each cut re-walks the row's prefix
   from the head. The scanner's per-character cost (`ord` alone: 3.9M calls)
   is the single largest line item on the frame.
2. **The viewport materializes the whole document every frame.**
   `Viewport.layout` extends *every* block's rows into `body_rows` (and
   builds an `(id, row)` owner tuple for every row of every block), then
   slices the ~45-row window out of it. Cost is O(document) per frame per
   pane — which is exactly the scroll-long number: 5.4× the short-document
   scroll. The window is all the frame ever paints.
3. **Streaming Markdown re-parses from scratch per frame.**
   `Markdown.render` runs `_run_blocks` over the full source on every call,
   and an open block re-renders on every layout. A reply growing line by
   line is O(n) per frame, O(n²) over the stream — and an *unchanged* open
   block (the transcript's markdown beside a streaming preview) re-renders
   too.

## Decisions (lead, final — do not re-litigate)

- D1 **The rendering is frozen.** Every wave's changes are invisible in
  bytes: the render-hash must be exactly `5bcfdf16…3aba9a` after every
  merge, and each worker additionally A/Bs its own workload's recorded
  output before/after.
- D2 **One scanner still.** Cluster semantics live only in
  `core/text.py`. A faster boundary resolver may walk the string itself and
  bulk-skip runs it can prove equal to the scanner's answer (printable
  ASCII is one cell per character — the scanner's own rule), delegating
  every non-ASCII stretch to `_cell_spans`. Memoizing a pure per-character
  width is the `Style._prefix` pattern, not a second opinion.
- D3 **Caches are value-shaped.** A cache keys on the value it derives
  from (width, text prefix, block identity), is invalidated from the same
  mutation that would change the answer, and its docstring says so. No
  timers, no invalidation-by-flag sprinkled over callers.
- D4 **No workload may regress.** A wave's target workload improves with
  real numbers; every other workload line stays within +5% of the table.
- D5 **Merge order W1 → W2 → W3**, lead gating each — W1 moves the floor
  every later number is measured on.

## Wave table

| Wave | Work order | Branch | Touches |
|---|---|---|---|
| W1 | 01 | `perf/w1-scanner-splice` | `src/mocode_tui/core/text.py`, `src/mocode_tui/core/lines.py`, `src/mocode_tui/core/frame.py` |
| W2 | 02 | `perf/w2-viewport-window` | `src/mocode_tui/core/viewport.py` |
| W3 | 03 | `perf/w3-markdown-stream` | `src/mocode_tui/widgets/markdown/**` |

## Red lines

- `uv run pytest -q` green before and after every merge, real output pasted.
- The render-hash is byte-stable; the demo's piped replay exits 0.
- No new runtime dependency; no lint/type tooling; honest `__all__`; no
  compatibility shims; no new test files (focused tests join the existing
  files, ceiling three functions per wave).
- Workers never edit `tools/framebench.py` or anything under `specs/`.
- Blocked → report and stop; a wave that cannot show its number move does
  not merge.

## Environment & protocol

Windows 10, Git Bash, `uv`, Python 3.12. A worker's first command in its
fresh worktree is `uv sync`; gates run through `uv run`. Record real
numbers (workload lines before/after) in the final report — "should be
faster" is not a result.
