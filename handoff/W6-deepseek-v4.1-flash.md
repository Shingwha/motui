# W6 handoff — demo integration (Stack / Align)

Branch `w2.1.2-w6-demo`; worker `deepseek-v4.1-flash`; start main @ `d98db42`.

## A. Recorded facts

`git log --oneline main..HEAD`:
```
a815138 w6: test the splash buttons and record the new framing
04e8229 w6: compose the components modal from a stack
c6a062e w6: float the splash text and buttons over the canvas
```
`git diff --stat main...HEAD`: 4 files, 144+/47- before this handoff commit (which
adds 80); `components.py`, `splash/scene.py`, `test_scenes.py`, `splash.txt`. Forbidden-list diff is empty.
Splash:
- `Stack([Align(canvas, center/middle), Align(overlay, center/middle)])`; overlay =
  `Column([LinesView, Spacer(1), Align(Row([launch, remix], widths=[8, 7], gap=2), horizontal="center")])`.
- `render` keeps resize/clear/paint; its lines are header + blank + centred tagline +
  blank + effect + blank + hint, assigned to `LinesView.lines`. The canvas is measured
  from its own `Surface` (78x22 at 100x30) and vertically centred; the 9-row overlay
  centres at `(height-9)//2`. Clicks go `Stack.child_at` → `Align` → `Column` →
  `Align(Row)` → `Row` → `Button` (≤16 hops): launch → `"menu"`, remix → `remix()` +
  `None`, else `"menu"`.
- Keyboard: `enter` activates/takes launch → `"menu"`; `space` activates/takes remix,
  queues `remix()` → `None`; `q` → `"quit"`.

Components modal:
- `Stack([LinesView background, Align(_DialogBox(dialog), center/middle)])`; `_overlay`
  keeps `_dialog_frame(width)` for `(dx, dh)` and sets `_dialog_rect = (dy, dx, dh, dw)`
  with `dy = (height-dh)//2`.
- **Deviation (click parity):** `Dialog`'s auto box width comes from its constraint
  (`3/5` of it). `Align` hands the child the full frame, so a literal `Align(self.dialog)`
  paints 48x4 at width 80 while `_dialog_frame` (constraint `min(56, width-4)`) measures
  33x5 — off by 7 columns and 1 row. `_DialogBox` (private `Widget`) renders at the same
  `min(56, max(24, width-4))` width, so painted geometry and `_dialog_rect` agree exactly
  (arm/cancel clicks resolve to `"uplink armed"` / `"uplink remains safe"`). `_dialog_frame`
  is unchanged.

Goldens:
- Only `splash.txt` changed (8 rows). `components.txt` is byte-identical: the modal is not
  in the showcase frame and the non-modal path is unchanged. `git diff --stat
  tests/golden/semantic` = 1 file; the other 8 were restored from the index (the update
  rewrote CRLF→LF with no content change); `--check` is 9/9.
- Splash text: canvas moved down ~3 rows (vertical centring); header now at emulated row 9
  with `ACT 01 · 2.1.0` right-aligned, tagline at 11 over the wordmark, effect at 13, hint
  at 15, buttons at 17 (` launch ` + gap + ` remix `). Cursor header unchanged
  (`cursor=0,29`).

Gates (real output): `pytest -q -p no:cacheprovider` **1838 passed** (26.19 s);
`ruff check .` all passed and the 4 changed py files pass with `--config "exclude=[]"`;
`pyright` 0 errors; `lint-imports` 5 kept; `semantic.py --check` 9 scenes match;
`api.py --check` 244 names match. `framebench`: render-hash
**`e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`** (unchanged);
scene-render 40.37 ms p50 / 44.74 p95, scene-paint 41.61 ms p50 / 69.47 p95 (100x30 splash).

## B. Only-in-the-head knowledge

- The render-hash workload is Markdown + Scrollbar only, so it cannot move for a splash
  layout change: the work order's "hash change is expected" is wrong; semantic `splash.txt`
  is the visual evidence.
- `LinesView.render` pads every row to the constraint width (`Surface.of`), so `Align`
  measures the overlay as full-width: its horizontal centring is a no-op by construction;
  `demo/common.center` centres the text rows. The buttons need their own inner `Align` for
  the same reason.
- The emulated golden drops the scene's top row (frame row 0) for splash; this predates W6
  (the old golden also lacked `MOTUI // SIGNAL LAB`), so the header became visible only
  after it moved down.
- `_button_cell` in `tests/demo/test_scenes.py` brute-forces 80x24 cells through the same
  `child_at` chain as `on_click`; it is layout-agnostic.
- `Button.activate()` writes pending `True`; both key and click paths take it immediately
  so no stale result crosses frames.

## C. Pointers

- Splash: `src/motui/demo/sections/splash/scene.py:67` composition, `:209` render, `:249`
  on_key, `:263` on_click.
- Components: `src/motui/demo/sections/components.py:70` `_DialogBox`, `:133`
  `_modal_stack`, `:375` `_overlay`.
- Tests: `tests/demo/test_scenes.py:65` splash buttons.
- Previous wave: `handoff/W5-deepseek-v4.1-flash.md`.
