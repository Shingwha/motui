# Spec W3 · The demo themes the family; docs and the CHANGELOG
> Branch `docs/119-bands`; after: W2 merged; read first: `00-overview.md`, the whole group

## Goal

The demo becomes the taxonomy's reference host: its themes theme the band
family, so the shipped demo shows the opt-in working (D1's point made
visibly). The docs record the philosophy and the rehoming, and the CHANGELOG
carries the 1.1.9 correction (D6).

## Tickets (one commit each)

### T1 — the demo themes the band family

`src/motui/demo/assets.py` (the `THEMES` variants) and wherever the demo's own
chrome reads the theme:

- The `"default"` variant gains `ground`, `ground_active` and `hover` values —
  a real surface, a real engaged band, a real hover band — so the default
  demo paints the taxonomy instead of showing the bare defaults. Choose
  values in the shipped palette's register (the GitHub-dark family the
  semantic constants use); the engaged band must read clearly against the
  ground, and the hover band must be visible without being the cursor band
  (D3's split, demonstrated).
- The `amber` and `violet` variants extend their own palettes with the same
  three tokens in their hues (they already theme `hover`; after W1 their
  existing `hover` values are the ones the pointer rows read — keep them and
  add the ground pair).
- The demo's pages that hold row widgets (the rail, the tables, the tree)
  now show the opt-in: verify by eye through the piped dump that the cursor
  row and the hover band read as designed. The golden frames will move — the
  themed bands are style-only (invisible to the plain-text dump) unless the
  seat/marker text changed; re-record only if the dump itself moves, and
  report either way.

### T2 — `docs/DESIGN.md` and `docs/COMPONENTS.md`

- DESIGN.md: the theme section states the philosophy — the toolkit paints
  structure and position, the host paints feedback (D1/D2, with the industry
  line named: urwid/Rich/ratatui on motui's side, Textual on the other); the
  naming charter's surface-family row records the `NONE` defaults, the caret
  and focus carve-outs, and the pointer-row rehoming to `hover` (D3); the
  row-band contract states the marker seat (D4).
- COMPONENTS.md: the row-band resolution table shows the new defaults and the
  precedence rule (the hovered row wears `hover`); the theming recipe shows a
  host theme setting the three tokens (the mocode pill case is the worked
  example); the cursor-marker contract joins the per-widget row shapes.

### T3 — `CHANGELOG.md`

The `## [1.1.9]` entry (D6's framing — the correction is said plainly):

- **Breaking**: `Theme.hover` and `Theme.ground_active` default to `NONE`
  (with `ground`): the band family is the host's to theme, so a default
  render paints structure and position only. The row widgets' pointer row
  reads `hover` (not `ground_active`). NavList, Table and Tree rows carry a
  `▸` cursor seat on every row. Under the year-let rule, documented, no shim
  — and the entry says 1.1.8 shipped the reverse default and this version
  corrects it.
- **Added**: the cursor markers; the invariant test.
- **Fixed**: the token semantics — `hover` is the pointer's signal everywhere
  (list rows included), `ground_active` is the keyboard cursor row's.

### T4 — the gate

Run the overview's full gate block on the final tree and paste the real
output.

## Acceptance (real output in the report)

1. `uv run pytest -q` — full suite green; state the counts.
2. The golden check (green; the re-record policy from T1 stated honestly).
3. The framebench line and both piped demo runs.
4. Six doc-claim spot-checks against the code, with line numbers.

## Red lines (zero diff outside)

`src/motui/demo/`, `docs/DESIGN.md`, `docs/COMPONENTS.md`, `CHANGELOG.md`.
No other source, no tests, no `pyproject.toml`, no `specs/` (lead-owned), and
no version bump — the release waits for the release owner's instruction.

## Report format

Per-ticket status table / commit hashes + messages / the gate's real outputs /
the doc-claim spot-checks / the CHANGELOG entry as written / deviations /
open questions. Blocked → stop and report.
