# Spec Group 2026-10-06-split-row-truth · The split row is a grid and a segment is a clean slate

> Lead: the main ZCode session. Workers: one agent (W1).
> Lineage: follows `2026-10-06-preview-fidelity` (closed). Conventions carry
> over: English one-line imperative commits, no lint/type tooling, no
> push/tags, worktree protocol (`C:\Users\shifu\.worktrees\mocode-tui\<branch>`),
> lead merges only (`--no-ff`), specs are lead-owned.

## Owner brief

The `/preview` split still renders wrong on `main` (`24c8ed6`), with a fresh
screenshot as evidence: 1) several rows of the right pane are offset one cell
to the left of the others; 2) the right pane's colored text renders dim on
most rows — the owner reads it as "covered by the left scrollbar's
background" — while the scrollbar itself and the rows beside the thumb look
normal, even brighter. Brief: root causes, fixed from the structure, not
patched; code stays simple, clear, rigorous; everything runs through `uv`.

## The lead's verification (on `main`, `24c8ed6`)

Both defects reproduce headless and were pinned to unit level. The full
repro script is embedded in the work order. Baseline gate:
`uv run pytest -q` → **800 passed, 1 skipped**.

### Defect A — the one-cell offset: `cut_line`'s column arithmetic measures characters, everything else measures clusters

Since W2 of the previous group, `visible_width` (and therefore
`Line.width`, `pad_to`, `fit`, wrapping) measures by **grapheme cluster**.
`_column_to_index` in `core/lines.py` — the function every column-space cut
(`cut_line`, and therefore `splice_row`) is built on — still walks **per
character** with `wcwidth(ch)`. On any cluster whose whole-string width
exceeds its per-character sum (a VS16-widened base like `"⚠️"`: per-char 1+0,
cluster 2; a ZWJ family: per-char 8, cluster 2), the two disagree by one or
more cells. Unit evidence:

    cut_line(Line("A⚠️B"), 0, 2).width == 3   # the window promised 2
    splice_row(Line("A⚠️B     "), Line("#"), 6, 1, 10).width == 11  # the frame promised 10

`splice_row`'s pieces are cut to cell windows and padded back with the
*cluster* measure; when a cut boundary lands inside such a cluster the piece
overshoots its window, so the pieces stop tiling the row and cells drift
across the chrome/pane boundaries — in the screenshot, the right pane's
first columns land under the left pane's scrollbar/separator strip on the
two emoji-table rows (`Objects 物件：…`, `Nature & Food 自然与食物：…`, both
full of VS16 emoji), exactly the one-cell-left offset measured in the image
(first text column 1668 px on those rows vs 1679 px everywhere else).

`cut_line`/`splice_row` have **zero direct test coverage** today — grep over
`tests/` finds no assertion naming either.

### Defect B — the dim right pane: `Line.styled()` never resets between two styled segments

`styled()` inserts `RESET` only on a styled→unstyled transition. Between two
styled segments the second prefix only *adds* SGR state — SGR is a state
machine, so the first segment's attributes persist. In a split frame the
row reads `[left content][scrollbar ░, DIM][separator, accent fg+bold][right
pane …]`, and the right pane's row-initial colored segments (gold headings,
purple list markers) take the track's `dim` and the separator's `bold` with
no reset in between. Byte evidence from the composed row:

    'left \x1b[2m░\x1b[1;38;2;88;166;255m \x1b[38;2;227;179;65m### Escaping\x1b[0m'

— one `ESC[2m` (dim) opened by the track, never closed before the heading.
Rows beside the **thumb** look normal/bright because the thumb's style is
`NONE`, which forces a `RESET` before the separator; the separator's `bold`
then bleeds into the heading instead — the brighter-than-gold render the
owner read as "normal". This is why the defect tracks the scrollbar without
being the scrollbar's: any two adjacent styled segments contaminate each
other, the scrollbar is merely the split layout's most visible dim-carrying
segment. The same leak class hits toast bands and message bands (bg-carrying
segments followed by fg-only ones).

## Decisions (lead, final — do not re-litigate)

- D1 **One cluster scanner, in `core/text`.** The column→index walk moves to
  (or delegates to) the module that owns measurement, sharing the exact
  cluster rules `visible_width` runs, so measurement and cutting cannot
  diverge again. `lines.py` keeps no width arithmetic of its own — its
  docstring already promises "nothing here re-measures text".
  `visible_width`'s outputs stay pinned: no behavior change there.
- D2 **`styled()` resets between every pair of adjacent segments.** Not SGR
  state-tracking: every segment after the first is preceded by `RESET`, the
  trailing `RESET` unchanged. A few bytes per boundary, and correctness that
  is auditable at a glance — a segment's rendering becomes a pure function
  of its own style, which is what the docstring always claimed.
- D3 **One serial wave, one agent.** Both roots live in `core/lines.py` —
  parallel agents would share the file.
- D4 **Test ceiling: at most 4 focused test functions, existing files only**
  (owner's standing 非必要不要加测试). No new test files; no assertion
  weakened; exact-string expectations that encoded the leaky schemes move to
  the leak-free form, stated in the report.

## Wave table

| Wave | Work order | Branch | Touches |
|---|---|---|---|
| W1 | 01 | `fix/w1-row-truth` | `src/mocode_tui/core/lines.py`, `src/mocode_tui/core/text.py`, `tests/test_core_text.py`, `tests/test_frame.py` |

## Red lines

- Full suite green before and after (`uv run pytest -q`), real output pasted.
- The demo's piped replay exits 0: `uv run python examples/pi_demo.py <
  /dev/null; echo exit=$?`.
- No existing assertion weakened; moved pins stated with reasons.
- Kernel purity: no styling opinion added to `core/**` beyond the two roots;
  `visible_width` semantics unchanged (its tests pin them).
- No lint/type tooling; honest `__all__`; no compatibility shims.
- No push/tags; workers never merge.

## Environment & protocol

Windows 10, Git Bash, `uv`, Python 3.12. A worker's first command in its
fresh worktree is `uv sync`; every gate runs through `uv run`. Worktrees at
`C:\Users\shifu\.worktrees\mocode-tui\<branch>`; the lead merges `--no-ff`
and re-runs the full gate before and after each merge; blocked → report and
stop.
