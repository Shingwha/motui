# W7d test trim — worker handoff

## A. Numbers and gates

- Collected: **1838 → 1383** (-455, -24.8%; target ~1380, hard cap 1400).
- Full suite: `1383 passed in 24.32s` (`uv run pytest -q -p no:cacheprovider`).
- Gates: `semantic: 9 scenes match`; `api: 244 names match`;
  `ruff check .` green; changed files with `--config "exclude=[]"` green;
  `pyright` 0 errors; `lint-imports` 5/5 kept.
- Scope: only `tests/**` plus this handoff. No src/docs/tools/pyproject/golden diff.

## B. Per-family dedup (before → after)

| family | files | cut |
|---|---|---|
| capabilities | action 29→17, choice 48→32, data 70→60, navigation 33→25, menubar 18→15, autocomplete 16→9, indicators 20→15, editing 89→65, scroll 38→36, text_widget 6→4 | one `CAPABILITIES` table in `test_contracts.py` now owns focusable/clickable/hoverable/activatable for every component; per-family copies deleted. |
| keymap rebind | data, choice, navigation, menubar, scroll, editing, base | class-table isolation stays once in `test_contracts.py`; family copies deleted. Input/Editor default-table guard kept as two assertions in the constructor-keymap test. |
| height budget | containers 56→48, form 15→12, dialog 21→15, combo 16→12, editing, indicators, action, data, choice, navigation, menubar, autocomplete | one `test_every_component_honours_the_height_budget` matrix over `tests/test_invariants.py::CASES` (0/1/2, width bound + idempotence). Unique budget edges kept: diff cache key, scroll explicit height/natural height, truncated Form/Collapsible/Input geometry, editor byte-identical render. |
| rename-only | app, workspace, base, navigation | deleted `set_focus_targets_is_gone`, runtime-has-no-surface, untyped-verbs-gone, base-names-out-of-facades, strip-no-second-cursor. |
| duplicate construction/result | choice, data, form, dialog, combo, autocomplete, editing | empty activation, take-once, move-clears-pending, table take, dialog take/on_click, combo toggle, paste folding are asserted once in `test_contract_*`; unique render/geometry details folded into the surviving test. |
| duplicate matrices | cell 249→74, theme_contract 59→13, contract_choice_nav 53→24, contract_text_form 23→16, surface 49→27, layout 41→32, containers, rows, text, syntax, action, api, focus, demo, editing | repeated single-contract parameter cases now loop inside the test (reflow keeps mode×width params and loops the 8 texts; 3 token contracts merged; auto env table, thumb table, clip/width tables, align anchors, notice levels, kind/hover tables, facades, demo scenes). Every assertion is still executed; failure messages carry the case context. |

Preserved unique coverage: editing/selection/undo, mask, wrap/wide chars, table grid/sort/widths/cell_wrap, tree visible rows/filter/jump/open, scroll geometry/sticky/reveal/thumb, Markdown/Diff/syntax, focus/click/drag routing, modal/overlay, Raster/quantize/palette, Drawing, and every component's distinct render assertions.

## C. Not cut further / deviations

- Width, marker, error and boundary matrices were kept as loops, not deleted: every case still runs (README rule 5).
- `ScrollPanel` is excluded from the central height matrix because an explicit `height` deliberately wins over `max_height`; its natural-height and explicit-height tests stay.
- `test_theme.py` role-default and render-adoption tests stay: they pin values the token contract does not.
- Remaining one-per-family keymap/typed-hook tests stay where they assert real coordinate or text routing (not just the shared verb); merging them would lose those positions.
- No source bug was found; no test was deleted to hide one.
