# Spec W4 · Docs and the CHANGELOG entry
> ✅ 2026-10-19 @ `docs/118-surface` — merged (8511bff)
> Branch `docs/118-surface`; after: W3a + W3b merged; read first: `00-overview.md`, the whole group

## Goal

Write the landed design down: the naming charter's new rows, the host-facing contracts,
and the 1.1.8 CHANGELOG entry. Read the merged code — the docs describe what shipped,
not what was planned. The version bump and the release wait for the release owner's
instruction (overview, Git protocol).

## Tickets (one commit each)

### T1 — `docs/DESIGN.md`

- **Naming charter**: add rows for the surface family (`ground` / `ground_active` /
  `focus` / `caret` / `selection` / `hover`, one role each, with the Textual analogue
  named), the row-band contract (the resolution rule in one block), the Line sizing
  family (`fit` trims, `fill` extends and surfaces, `filled` builds a blank row —
  replace the "Truncation family" row's wording accordingly), `Pane.inner_rect`, and
  `ScreenLayout`'s geometry fields.
- **The theme section** ("Style resolution, once at construction"): state the
  resting/engaged pair and that a row widget's hovered row reads `ground_active` (the
  reverse-on-a-background swap is why hover on a surfaced row is a background token,
  not `reverse`).
- **The frame model**: `Pane.inner_rect` joins `band()` as the public geometry reads.
- **The viewport section**: a layout ships its own `width`/`height`.
- Keep the document's voice: every claim matches the shipped modules.

### T2 — `docs/COMPONENTS.md`

The host-facing contracts, in the document's own style:

- The row-band resolution table (what a host themes to restyle every list/menu/tree/
  table at once, and the per-widget `ground_style=` / existing style params that
  override it).
- `Delegate`: the recipe (wrap, both doors, the three degradation rules, what it never
  proxies).
- `Markdown(max_width=…)`.
- `ScreenLayout.width` / `Pane.inner_rect` as the reads an IME anchor uses (the
  host's `_InputSlot` width-recording pattern is what these replace).

### T3 — `CHANGELOG.md`

The 1.1.8 entry, following the file's existing structure and voice:

- **Added**: `Theme.ground` / `ground_active` / `caret`; `Line.fill`;
  `ScreenLayout.width`/`height`; `Pane.inner_rect`; `Delegate`;
  `Markdown(max_width=…)`.
- **Changed**: `Theme.cursor` → `Theme.focus` (and the `CURSOR` constant → `FOCUS`);
  `Select`'s cursor row and `NavList`'s active row now carry the `ground_active` band
  under their accent label (the one default-visual change); the row widgets' hovered
  rows read `ground_active`; `Radio`/`CheckGroup`'s `focus_style` parameter is
  `selected_style`.
- **Removed**: `Line.pad_to` (absorbed into `fill`).
- Grep `README.md` for the token list / component list and update it if it enumerates
  either (the `ground` family belongs in the theme table if there is one).

### T4 — the final gate

Run the overview's full gate block on the merged main and paste the real output.

## Acceptance (real output in the report)

1. `uv run pytest -q` — full suite green; state the counts.
2. The golden check, the framebench line and both piped demo runs — all green.
3. Every doc claim spot-checked against the code (name a few you verified).

## Red lines (zero diff outside)

`docs/DESIGN.md`, `docs/COMPONENTS.md`, `CHANGELOG.md`, `README.md`. No source, no
tests, no `pyproject.toml`, no `specs/`.

## Report format

Per-ticket status table / commit hashes + messages / the gate's real outputs / the
doc-claim spot-checks / open questions.
