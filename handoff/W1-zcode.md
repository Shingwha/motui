# W1 handoff — kernel overlay composition

Branch `w2.1.2-w1-overlay`, forked from main @ `561ed56`; worker `zcode`.
W1 T1–T3 complete; W2 then continued on the same branch.

## A. Recorded facts

Commits:
- `ae6655c` w1: add Line.overlay cell composition
- `1ea1975` w1: add Surface.overlay row composition
- `109bda5` w1: test line and surface overlay composition

Files: `src/motui/kernel/cell.py` (+206), `tests/kernel/test_cell.py` (+82).

Public API added:
- `Line.overlay(self, base: Line) -> Line` — `cell.py:395`.
- `Surface.overlay(self, base: Surface) -> Surface` — `cell.py:917`.

Rules implemented:
- Transparent cell = text `" "`, `Style()`, `link is None`, `action is None`;
  it keeps the base cell. An opaque cell takes the top glyph and payloads and
  style `base_style.merge(top_style)`.
- Width = `max(self.width, base.width)`; Surface also takes `height = max`.
  `Surface.overlay` normalizes through `Surface.of`, so rows come back exactly
  the result width.
- `Line()` or an all-transparent top returns `base` itself (padded only when
  the top row is wider).
- Wide characters are composed as clusters: covering either column of a
  double-width base glyph removes both columns; the leftover column is a
  one-column blank in the erased glyph's style. A transparent top preserves
  the whole glyph. No half glyph / dangling continuation is produced.
- Private helpers `_CellRun` (`:543`), `_line_cells` (`:559`),
  `_transparent` (`:613`), `_paint_cells` (`:627`) split segments through
  `text._cell_spans`, so overlay boundaries match the kernel's measure/cut
  cluster boundaries. `__all__` and the module-level `overlay(Style,
  segments)` function are unchanged; W1 adds no facade name.

Tests: 7 new cases in `tests/kernel/test_cell.py:500` ("overlay
composition"): transparent base, style merge, styled space, link/action,
width max + short side, wide chars (lead / continuation / transparent /
double-wide top), Surface rows and size.

Verification (real output):
- Start: `291 passed` (test_cell + test_surface); `semantic: 9 scenes match`.
- After W1: `298 passed`; `ruff` and `pyright` clean on `cell.py`.
- Full suite: `1687 passed, 3 failed`; every failure is cross-wave surface
  fixture fallout: `tests/test_invariants.py` matrix lacks Stack/Align
  factories (that file is W3's write scope), and two
  `tests/testing/test_api_tool.py` snapshot cases wait on the lead's
  `tools/api-2.1.txt` update.
- `ruff check .` green; `pyright` 0; `lint-imports` 5 kept; semantic 9 scenes.
- `framebench.py` render-hash
  `e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`,
  byte-identical to main @ `561ed56` measured from a temp `git archive`.
- `api.py --check`: `+ motui.widgets:Align`, `+ motui.widgets:Stack` (W2
  exports), expected; snapshot deliberately untouched.

## B. Only-in-the-head knowledge

- Wide-cell policy: a narrow top cell overlapping one half of a wider base
  cluster erases the **whole** base cluster; the uncovered column is an
  unstyled-content blank carrying the base cell's style. This keeps a
  background band continuous; locked by
  `test_wide_characters_are_replaced_or_kept_whole` (`"X "` / `" X"`).
- The all-transparent fast path returns `base` (identity when not wider),
  preserving zero-width-only segments that the cell decomposition drops;
  those segments paint nothing, so an opaque overlay may drop them.
- `Surface.overlay` pads rather than clips short rows; W2's `Stack` relies on
  rows being exactly `max` width.
- Blanks left by an erased wide glyph are one-column runs; `fuse()`
  coalesces them by style/payload, so untouched rows compare equal to base.

## C. Pointers

- `src/motui/kernel/cell.py:395` `Line.overlay`; `:917` `Surface.overlay`;
  `:543`–`:700` private cell composition.
- `tests/kernel/test_cell.py:500`–`:581` overlay test group.
- Next wave: `handoff/W2-zcode.md` on this branch.
