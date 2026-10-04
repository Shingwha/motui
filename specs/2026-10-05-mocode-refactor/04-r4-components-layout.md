# Spec R4 · Components tidy + `layout.py` → `components/layout.py`
> ✅ 2026-10-05 @ merged to main (R1 703/2, R2 698/1, R3 701/2, R4 703/2, R5 700/1, R6 202/1 — final gate)

> Branch `refactor/r4-components-layout`; worktree `~/.worktrees/mocode-tui/refactor-r4-components-layout`;
> depends on: R1 merged (needs `Line.filled`); deep-read: `00-overview.md`,
> `docs/COMPONENTS.md`.

## Goal

Three tidy moves in the component layer: adopt R1's `Line.filled` where the
two band-padding implementations duplicated it; delete the two ratified dead
member (`Spinner.interval`, `Input.newline`); and fix the tree's one
misplacement — `Row`/`Column` are components (`render(width) -> list[Line]`)
but live at the root while the rest of the library lives in `components/`.
After this wave `components/` is the single import surface for every component
*including* the layout containers.

## Write scope (exclusively yours)

- all of `src/mocode_tui/components/` (11 component modules + `__init__.py`)
- `src/mocode_tui/layout.py` (deleted — content moves to `components/layout.py`)
- `src/mocode_tui/__init__.py`: **only** the `Row`/`Column` import line may
  change (`from .components.layout import Column, Row`); no other edit.
- `tests/test_components_*.py` (all 11 files), `tests/test_layout.py`
- `docs/COMPONENTS.md`
- nothing else — no `keys*`, `app.py`, `screen.py`, `viewport.py`, `painter.py`,
  `README.md`, `DESIGN.md`, demo.

## Tickets (one commit each)

### T1 — adopt `Line.filled` in the band components

- `message.py`: `_pad_row(band, width)` becomes `Line.filled(width, band)`.
- `tools.py`: in `_band_row`, the no-parts case becomes `Line.filled(width, band)`
  (keep `_band_row`'s parts logic for content rows).
- Verify with the rendered-output gate (acceptance 4): byte-identical demo dump.

### T2 — delete `Spinner.interval` and `Input.newline`

- `Spinner.__init__` loses the `interval` parameter and attribute; `__slots__`,
  docstring, `__repr__` and the demo (which passes `interval=`? grep it) follow.
  Check the demo before deleting — if `examples/pi_demo.py` passes
  `Spinner(..., interval=...)`, the demo is NOT in your write scope: then keep
  the parameter and report the conflict instead of editing the demo. (Lead's
  grep says the demo constructs `Spinner(text)` only — re-verify.)
- `Input.newline()` goes (`insert("\n")` is the same operation); remove its test
  in `tests/test_components_input.py` and any docstring mention.
- `docs/COMPONENTS.md`: the `Spinner` row loses the `interval` parameter from
  its `__init__` sketch.

### T3 — move the layout containers

- `src/mocode_tui/layout.py` → `src/mocode_tui/components/layout.py`, docstring
  updated ("Component library" framing: they are components; the old module
  path `mocode_tui.layout` is gone by design — no compatibility shim).
- `components/__init__.py` imports and re-exports `Row`, `Column` so
  `from mocode_tui.components import Row` works; root `__init__.py` import line
  for `Column, Row` switches to `from .components.layout import Column, Row`
  (the package-root exports are unchanged).
- `tests/test_layout.py`: keep the file name; change imports to
  `from mocode_tui.components.layout import Column, Row` (and the docstring's
  "mocode_tui.layout" reference). Keep the tests themselves.
- `docs/COMPONENTS.md`: the "Text & structure" table and the "Building your own
  component" section mention `mocode_tui.layout` — update to
  `mocode_tui.components.layout`; the final paragraph's claim that containers
  "drop straight into `Document.add`, `Row`, `Column`, and `Panel`" stays true.

### T4 — component docstring truth pass

In the component modules you touch, fix comments that reference removed things
(W-number archaeology like "the W4 driver decides when", "the W8 stopgap",
"W11 palette" history) may stay — they are accurate history — but anything
describing `interval`/`newline`/`mocode_tui.layout` must go. No redesign of any
component's rendering in this wave.

## Acceptance (run in your worktree, report real output)

1. `uv run pytest -q` — green; report the exact line.
2. `uv run python -c "from mocode_tui.components import Row, Column, Text, Panel; from mocode_tui.components.layout import Row as R2; print(Row is R2)"` → `True`.
3. `uv run python -c "import mocode_tui; print(hasattr(mocode_tui.components, 'layout'))"` → `True`; and
   `uv run python -c "import mocode_tui.layout"` must fail (no shim) — show it.
4. `uv run python examples/pi_demo.py < /dev/null > out.txt; echo exit=$?; sha256sum out.txt`
   — equals the R0 baseline `71d09ff2…c9a1c981`.
5. `uv run python -c "
from mocode_tui import Spinner, Input
import inspect
print(inspect.signature(Spinner.__init__)); print(hasattr(Input, 'newline'))"`
   — no `interval`; `False`.

## Red lines

- Rendered output must not change: the band components' rows are the same
  lines with the same styles; verify via acceptance 4 and your reading of
  `Line.filled` vs `Line.from_text(" " * width, style).fit(width)`.
- Do not add features (no `Panel(padding=)`, no style-registry refactors) —
  those are follow-ups, not this wave.
- No new public component names; `mocode_tui.layout` module path is deleted by
  design (this group owes no back-compat).

## Report format

Ticket status table / commit hashes+messages / real outputs for the five
acceptance commands / list of deleted tests / deviations & open questions.
