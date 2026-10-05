# Spec 02 · Selection kernel: model, overlay, extract, OSC 52 (Wave W2)

> Branch `selection/w2-kernel`. Prerequisite: **W1 merged**. Must read:
> `specs/2026-10-05-selection/00-overview.md` — D1, D2, D6, D8 are this
> wave's constitution.

## Goal

The pure kernel half of the feature, with no driver integration yet: a
`Selection` value over document addresses, the `highlight` overlay that
renders it onto a `ScreenLayout`, `extract` that pulls its text out of the
document (off-screen parts included), and the OSC 52 clipboard primitive on
`Screen`. Everything in this wave is timeless and side-effect-free except
`Screen.copy`, which is a byte-emitting primitive in the screen's own tier.

## Design notes for the implementer

- **`core/selection.py`** (new module, kernel-pure: imports only
  `core.lines` / `core.style` / `core.block` / `core.viewport` types):
  - `SelectionAnchor = tuple[str, int, int]` (`block_id`, row, col).
  - `Selection` — frozen value holding the resolved span list plus the
    anchor/head it came from; constructor `Selection.between(anchor, head)`
    normalizes direction (dragging up selects backwards), clamps cols to
    row widths lazily at use time (rows come from the layout), and exposes
    `.anchors` for round-tripping. Span internals may evolve (D8: single
    range public, spans internal).
  - `highlight(layout: ScreenLayout, selection: Selection | None) -> ScreenLayout`
    — the D2 overlay: for each screen row whose `(block_id, row_in_block)`
    is in range, cut the row's segments at the column boundaries and
    `merge(SELECTION)` onto the base style of the cut pieces. Column
    cutting must be **cluster-aware** — reuse the kernel's existing
    cutting machinery (`core/lines.py`'s slicer used by `wrap_line`;
    promote it to an honestly-named public helper if the module boundary
    demands it, e.g. a `Line` method or a `core.lines` function — do not
    duplicate a third copy of width arithmetic). `selection=None` returns
    the layout unchanged (identity, zero allocation beyond reuse).
    Row ownership comes from the layout's `row_blocks` — rows with no
    owner are untouched.
  - `extract(document: Document, selection: Selection) -> str` — walks the
    document blocks in order over the range, joining row texts with `"\n"`,
    slicing first/last rows by columns with the same cluster-aware
    cutting. Missing blocks are skipped (D8). This is what copy consumes —
    and it reads the sealed-block row geometry, so it works for content
    the viewport has long scrolled past.
- **OSC 52**: `core/ansi.py` gains `copy_clipboard(text: str) -> str`
  (`\x1b]52;c;<base64>\x07`, base64 of UTF-8 — stdlib only). It is born
  here and nowhere else, per the all-escapes-live-in-ansi rule.
- **`Screen.copy(text) -> bool`**: protocol method; `TerminalScreen`
  writes the sequence on live screens and returns whether it wrote;
  `HeadlessScreen` records the bytes and returns `True` (testability —
  the recorded stream proves the copy happened); non-live returns `False`.
- Style: use the existing `SELECTION` constant (`reverse+dim`); `merge`
  semantics keep fg colors visible under the reversal. No theme field in
  v1 (documented: restyling via `merge` at the call site is possible
  later without model change).
- The sealed-row cache must remain untouched by all of this: `highlight`
  builds new `Line`s over the layout copy; it never writes back into the
  viewport, blocks, or components.

## Work order (each task = one commit, gate green)

### T1 · `Selection` + `highlight`
- Model + overlay + the cluster-aware cut (promote/reuse, never duplicate).
- Tests: headless purity — highlight over a pinned layout (rows from
  `_doubles`), mid-row boundaries, backward drag, wide-char/CJK boundary
  (a cut must not split a double-width cell), `None` identity, unowned
  rows untouched, sealed cache values unchanged after highlight.

### T2 · `extract`
- Range text across multiple blocks, partial first/last rows, missing
  block skipped, backwards range, empty selection → `""`.

### T3 · OSC 52 + `Screen.copy`
- `ansi.copy_clipboard` byte test (base64 round-trip); `TerminalScreen`
  live/non-live behavior with the existing stream doubles;
  `HeadlessScreen` records and returns `True`.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. A short inline script: build a document of 3 sealed blocks via
  `_doubles.Rows`, layout at 80×10, `Selection.between` spanning block 1
  row 2 col 4 → block 2 row 1 col 6, print `extract` — include verbatim.

## Forbidden

- `app.py` (no `tui.selection` yet — wave 03), the gesture (wave 04),
  `widgets/**`, `chat/**`, `keys/**` (read-only), `examples/**`, README,
  docs, `specs/**`, `pyproject.toml`.
- Any timer, event consumption, or clipboard *policy* — mechanism only.

## Report

Per the overview format; state the cut-helper decision (promoted name vs
reused private) and the `Selection` normalization rules you settled.
