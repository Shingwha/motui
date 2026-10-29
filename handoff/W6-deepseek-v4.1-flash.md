# W6 handoff — demo integration (Stack / Align)

Branch `w2.1.2-w6-demo`; worker `deepseek-v4.1-flash`; start main @ `d98db42`.

## A. Recorded facts

`git log --oneline main..HEAD`:
```
c6a062e w6: float the splash text and buttons over the canvas
04e8229 w6: compose the components modal from a stack
a815138 w6: test the splash buttons and record the new framing
cb855b0 w6: hand off the demo integration wave
<本 commit> w6: keep the splash stack inside the scene budget
```
`git diff --stat main...HEAD`: 7 files, 420+/51- (including this handoff); forbidden-list diff is empty.
Splash:
- `Stack([Align(canvas, center/middle), Align(overlay, center/middle)])`; overlay =
  `Column([LinesView, Spacer(1), Align(Row([launch, remix], widths=[8,7], gap=2), horizontal="center")])`.
  Clicks walk `Stack.child_at -> Align -> Column -> Align(Row) -> Row -> Button` (<=16 hops);
  launch -> "menu", remix -> `remix()` + None; keys: enter launch/menu, space remix, q quit.
- `render` keeps resize/clear/paint; lines = header + blank + centred tagline + blank + effect
  + blank + hint. The canvas is measured from its own surface and vertically centred.
Components modal:
- `Stack([LinesView background, Align(_DialogBox(dialog), center/middle)])`; `_overlay` keeps
  `_dialog_frame(width)` for `(dx, dh)` and sets `_dialog_rect=(dy, dx, dh, dw)`.
- **Deviation (click parity):** Dialog's auto box width is constraint-derived (`3/5`), while
  `Align` passes the full frame: a literal `Align(self.dialog)` paints 48x4 at width 80 but
  `_dialog_frame` measures 33x5. `_DialogBox` pins `min(56, max(24, width-4))`, so painted
  geometry and the rect agree (arm/cancel clicks resolve to their toasts).
Goldens:
- Only `splash.txt` changed (8 rows); `components.txt` is byte-identical (the modal is not in
  the showcase frame). After the perf fix `semantic --update` rewrites no golden content.
Gates (real): pytest **1838 passed** (25.0 s); ruff repo + changed-files no-exclude green;
pyright 0; lint-imports 5 kept; semantic 9/9; api 244 names.
`framebench`: render-hash `e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`
unchanged; scene-render 10.80 p50 / 12.86 p95, scene-paint 12.03 / 14.92, replay 547 ms.

## B. Only-in-the-head knowledge

- Performance follow-up (authorized in `kernel/cell.py` + `widgets/layout.py`): render fell
  40.4 -> 10.8 ms. Pre-fix profile: `Line.overlay` called 600x/frame over 30-row stacks,
  `_paint_cells`/`_line_cells` ~10 ms, `Align` per-row pump. Fast paths added:
  1. `Line.overlay`: width 0 -> base; all segments plain NONE spaces -> base, no cells.
  2. `_paint_narrow`: both rows one-column glyphs -> span walk + buffered runs, no `_CellRun`;
     wide/combining/zero-width falls back to `_paint_cells` (8000-pair fuzz: 0 mismatches).
  3. `_line_cells`: ASCII -> one cell per char, skipping `_cell_spans`.
  4. `Align.render`: left==0 skips the prefix copy; clip/fill only when needed; one shared
     blank row. `Column.render` skips clip for rows already within the width.
- Remaining wall is outside the authorized files: `pixel.quantize` ~6.5 ms/frame (~35% of the
  render profile) and `paint_wordmark` ~1.2 ms, per-frame by design (palette and background
  change every frame). Evidence: the local pre-W6 splash scene measures 8.72 ms render /
  10.26 ms paint on today's machine, and `pixel-quantize` reads 9.2 ms vs the 3.8 ms documented
  baseline, so the 8 ms budget is unreachable here even before W6. Splash-specific new
  numbers: 11.1 ms render / 11.8 ms paint p50.
- `LinesView.render` pads rows to the constraint width (`Surface.of`), so `Align` measures the
  overlay as full-width (horizontal centring is a no-op); `demo/common.center` centres text.
- The emulated golden drops the frame's top row for splash (predates W6); the header became
  visible only after it moved down.
- `_button_cell` in `tests/demo/test_scenes.py` brute-forces cells through `child_at`.
- `Button.activate()` writes pending True; key and click paths take it immediately.

## C. Pointers

- Splash: `splash/scene.py:67` composition, `:209` render, `:249` on_key, `:263` on_click.
- Components: `components.py:70` `_DialogBox`, `:133` `_modal_stack`, `:375` `_overlay`.
- Kernel fast paths: `kernel/cell.py:395` overlay, `:579` `_narrow_widths`, `:584`
  `_paint_narrow`, `:742` `_line_cells`; `widgets/layout.py:216` Column, `:435` Align.
- Tests: `tests/demo/test_scenes.py:65` splash buttons. Previous: `handoff/W5-deepseek-v4.1-flash.md`.
