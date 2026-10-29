# W7c · Docs / ADR / README handoff

Agent: A. Branch `w2.1.2-w7c-docs`, from main @ `e1196cd`.

## Ticket status

| Item | Status | Commit |
|---|---|---|
| T1 CONTRACT.md | done | `a3224c0` |
| T2 WIDGETS.md | done | `92775b8` |
| T3 ARCHITECTURE + README | done | `6009a39` |
| T4 ADR-027..030 + index | done | `08967cb` |
| example/fence fixes | done | `4ab3f55` |

## What changed

- `docs/CONTRACT.md`: §1/§3/§4 overlay additions; §5 component
  hierarchy/`ResultWidget`/`ActionWidget`/`CursorWidget`/`Keymap`/take
  sentinel; §8 capability flags, action vocabulary, state/verb/result
  summary, composition pointer; new §9 "Component semantics contract"
  (construction/state/verbs/results/styles/keys); §11 error rows; §12
  public surface (7 facades, 206 names, 244 api rows).
- `docs/WIDGETS.md`: rewritten catalogue with 2.1.2 constructors, states,
  results, Stack/Align/ButtonKind examples, Drawing lifecycle, Dialog
  `body/title/buttons`, keyword-only Canvas/PixelCanvas, read-only
  `fraction`, `take` returns.
- `docs/ARCHITECTURE.md`: widgets 51 names; base/module map; new §8
  "Composition and drawing"; app line counts refreshed.
- `README.md`: PixelCanvas/Dialog/Table examples, ButtonKind, results
  paragraph, ADR count 27, Banner/WrapMode and Keymap examples.
- New ADRs: 027 transparent overlay/Stack/Align, 028 Drawing lifecycle,
  029 state/verb/result vocabulary, 030 control styles; index updated.

## Gates (real)

- `uv run pytest -q -p no:cacheprovider` -> `1838 passed in 27.12s`
  (baseline before edits: `1838 passed in 38.38s`).
- `uv run python tools/api.py --check` -> `api: 244 names match`.
- `uv run python tools/semantic.py --check` -> `semantic: 9 scenes match`.
- Old-name rg over `docs/**`/`README.md` (excluding MIGRATION, releases,
  historical ADRs): no matches. All python fences compile.

## Notes for W8

- `motui.widgets` has 51 names (ticket said 47): includes `ButtonKind`,
  `Stack`, `Align`; `Drawing` is internal and intentionally not exported.
- MIGRATION/CHANGELOG/version untouched. Suggested MIGRATION table is
  `specs/2026-10-29-1704-widget-semantics/ref/interfaces.md` §9; CHANGELOG
  should list constructor, state, result, style, composition and keymap
  changes (see CONTRACT §9 for the canonical wording).
- Only remaining old names in scope-adjacent files are historical release
  notes: `docs/releases/1.1.5.md` (`danger=True`) and
  `docs/releases/2.1.0.md` (`PixelCanvas(20, 8, ...)`); do not rewrite them.
- Minor discrepancy: `widgets/base.py` docstring says `on_action` routes
  "nine" names but lists ten (`prev/next/first/last/page_prev/page_next/
  activate/toggle/open/close`). Docs avoid a count; W8 may fix the
  docstring if in scope.
