# Spec W2 · The cursor markers
> Branch `refactor/119-markers`; after: W1 merged; read first: `00-overview.md` (D4)

## Goal

With the band family silent by default, the cursor row needs a structural
position carrier. NavList, Table and Tree gain the `▸` seat `List` already
uses (`→` for `Select`; `Radio`/`CheckGroup` already carry their `(•)`/`[x]`
marks and need nothing). The contract: **marker = position, band = emphasis**
(D4) — a fixed-width seat on every row, the glyph on the cursor row, the seat
styled with the row's own text style.

## The seat (pin it)

- Two cells, the `▸` glyph plus one space — the `List` seat's exact width, so
  the family shares one shape. Export or reuse the existing `MARKER` constant
  where the module already has one (`widgets/list.py`'s `MARKER` is the
  precedent; do not invent a second glyph).
- Every row reserves the seat (the cursor row paints `▸ ` in it, every other
  row paints two spaces), so labels stay aligned across the cursor's motion —
  the `List`/`Select` indentation rule.
- The seat is structure, not feedback: it carries the row's own text style,
  never a band. At the default theme it is unstyled; under a themed `ground`
  it rests on the surface like every other cell.
- `Tree`: the seat sits before the label, after the guides — read the guide
  geometry and keep the guide columns' alignment intact.
- `Table`: the seat is a dedicated leading column outside the measured grid —
  the grid's own columns and widths are unchanged, the table widens by the
  seat. Check `set_widths` and the natural-width measurement: the seat must
  not enter them.
- `NavList`: the seat leads the active/inactive rows; the group headers (if
  they are rows) keep their own shape — read the widget first.

## Tickets (one commit each)

### T1 — `Tree`'s marker
### T2 — `NavList`'s marker
### T3 — `Table`'s marker

Each: read the widget's render, add the seat to every row, paint `▸` on the
cursor row, keep every existing byte for the non-seat cells, and update the
widget's docstring (the marker seat joins the documented row shape). If a
widget's geometry genuinely cannot carry the seat without a redesign beyond
this ticket, **stop and report** — do not force it.

### T4 — tests and the golden re-record

- Update the affected widget tests (the row shape gains the seat on every
  row; the cursor row's text changes). Resting-row assertions move by exactly
  the seat — annotate with D4.
- The markers are **text**, so the golden frames move: re-record with
  `uv run python tools/golden.py --update` and report
  `git diff --stat tests/golden/pages/` plus a per-page note of what moved
  (the pages holding a NavList rail, a Table or a Tree).
- The A/B probe per widget (styled bytes): the seat's two cells are the only
  change on resting rows; the cursor row gains the glyph.

## Acceptance (real output in the report)

1. `uv run pytest -q` — full suite green; state the counts.
2. `uv run python tools/golden.py --check` — green, with the diff summary
   attached.
3. The framebench line and both piped demo runs from the overview's gate
   block.
4. The invariant test from W1 still passes (the seat is unstyled structure).

## Red lines (zero diff outside)

`widgets/tree.py`, `widgets/navlist.py`, `widgets/table.py`, their test
files, `tests/golden/pages/` (the re-record), `kernel/`, `interaction/`,
`widgets/list.py`, `widgets/choice.py`, `demo/`, `docs/`, `specs/`.

## Report format

Per-ticket status table / commit hashes + messages / the gate's real outputs /
the golden diff summary (per page) / the probe numbers / deviations / open
questions. Blocked → stop and report.
