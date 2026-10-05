# Spec 01 · Core kernel: layering, naming, painter purity, gates (Wave W1)

> Branch `refactor/w1-core-kernel`. Prerequisite: none (first wave).
> Must read first: `specs/2026-10-05-api-overhaul/00-overview.md` (charter,
> layer rules, test policy — all binding here).

## Goal

Make `core` a pure kernel again, move the composition root above it, and
land the kernel-side naming charter — with the **root API surface and all
rendered output unchanged** (this wave re-points imports; the root curation
itself is wave 05).

## Work order (each task = one commit)

### T1 · Events sink into the kernel
- Create `src/mocode_tui/core/events.py` holding `Key`, `Paste`, `MouseEvent`,
  the `KeySource` protocol (moved verbatim from `keys/events.py`) **and**
  `ScriptedKeys` (moved from `keys/sources.py`; it is a pure replay list with
  zero dependencies).
- **Coordinates become 0-based**: `keys/decoder.py` subtracts 1 from the SGR
  report's x/y when building `MouseEvent` (name it in the class docstring).
  `RawTerminalKeys`/`console.py` are unaffected (they emit bytes, not events).
- Delete `keys/events.py`; every `keys/` module imports events from
  `core.events`. `keys/__init__.py` re-curates to its own surface:
  `KeyDecoder`, `RawTerminalKeys`, `Keymap`, `DEFAULT_INPUT_KEYMAP`,
  `DEFAULT_EDITOR_KEYMAP` (no event re-exports — they live at `core.events`
  and the root).
- Update every internal importer (`core/app.py`, `core/testing.py`,
  `widgets/input.py`, `widgets/editor.py`, `chat/*`, tests).
- Delete the test-only re-export shim in `keys/__init__.py`
  (`windows_input_mode`, `keys_from_console_events`): the Windows-plumbing
  tests import `mocode_tui.keys.console` directly. A re-export a facade keeps
  is listed in its `__all__`; the `from x import y as y` self-alias idiom is
  forbidden (see the overview's red lines).

### T2 · The driver and the test helpers leave the kernel
- Move `core/app.py` → `src/mocode_tui/app.py` (unchanged class names
  `TUI`/`Hit`/`EveryHandle`; its `..keys`/`..widgets` imports become legal
  top-level `core` + `keys` imports).
- Move `core/testing.py` → `src/mocode_tui/testing.py`; fix the missing
  `Iterable` import in `headless_tui`'s annotation while it moves.
- Move the `Text` component from `widgets/text.py` into `core/text.py`
  (alongside the measuring functions; `TUI.print()` now uses it legally).
  Delete `widgets/text.py`; `widgets/__init__.py` re-exports `Text` from
  `core.text` so the root surface is unchanged.
- `core/__init__.py` re-curates: kernel names + the events surface; no
  `TUI`/`headless_tui` (they are `mocode_tui.app` / `mocode_tui.testing`).
- `mocode_tui/__init__.py` re-points its imports to the new homes; **the
  82-name `__all__` stays byte-identical** until wave 05.

### T3 · Painter becomes a pure frame differ; kernel renames
- `Painter.__init__(screen)` — it no longer owns a viewport or document.
  New API: `paint(layout: ScreenLayout) -> None` (does `screen.refresh_size()`
  internally first, then full-repaint on `(width, height)` change else per-row
  diff, anchor epilogue, live-gate — byte policy unchanged), `rows` property
  (was `rows()`), `set_cursor(row, col)` (was `set_cursor_anchor`), `row`/`col`
  clamping unchanged.
- `TUI` now owns `self.viewport = Viewport(self.document)` (public attribute).
  `TUI.paint()` (was `flush`) refreshes size, lays out, and calls
  `painter.paint(layout)`. `TUI.rows` becomes a property. Scroll facades
  (`scroll_up/down/scroll_to_bottom`) hit the viewport directly and
  invalidate; `hit_test` reads `self.viewport.row_blocks`. Delete the nine
  painter scroll/ownership pass-throughs.
- `KeyDecoder.flush()` → `KeyDecoder.finish()` (same semantics).
- `Block.pinned` property: delete. `snapshot()` (now in `mocode_tui/testing.py`)
  marks pinned blocks as `,top` / `,bottom` from `block.pin` (fixes the
  missing `,top` case).
- Make `MORE_BELOW` a public constant in `core/viewport.py` (tests import it
  instead of re-typing the literal).
- Mechanical rename fallout is yours to fix in this commit: `examples/pi_demo.py`
  and README **code blocks only** (`tui.flush()` → `tui.paint()`,
  `tui.rows()` → `tui.rows`, 0-based `hit_test`/`MouseEvent` usage,
  `sync_query` untouched here). `tests/test_readme_examples.py` must stay green.

### T4 · Segment utilities + frozen-dataclass ceremony
- `core/lines.py` gains two module functions (consumers migrate in waves 02–04;
  they are public kernel API now): `fuse(segments)` — coalesce adjacent
  equal-style runs; `overlay(base, segments)` — the colored-vs-attribute rule
  (a segment with its own fg/bg keeps its style, otherwise `base.merge(style)`).
- `Theme.__post_init__` and `Style.prefix` collapse their `object.__setattr__`
  ceremony into one private derived-cache field each; frozen semantics and
  rendered SGR output unchanged.

### T5 · Kernel/keys tests rewritten under the policy
- Create `tests/_doubles.py`: `Rows(*texts)` component double,
  `RecordingScreen` (the `Recorder` from `test_painter.py`, with `delta()`),
  `texts(component, width)`, `many(n)`, `key(name, char="")`.
- `test_app.py`: 30 → ~18 tests. The five non-live dump tests collapse to two
  (dump text; pinned footer lands last). `─ more below ─` literals come from
  `mocode_tui.core.viewport.MORE_BELOW`.
- `test_viewport.py`: delete the four `row_blocks` golden tests (the public
  `hit_test` path covers ownership end-to-end); 15 → ~11 tests.
- `test_painter.py`: port to `paint()` / `rows` property / `set_cursor`; keep
  every diff-policy assertion (zero-byte unchanged frame, changed-rows-only,
  resize full repaint, anchor epilogue) — use `_doubles.py`.
- `test_keys.py`: MouseEvent expectations become 0-based; `flush` → `finish`.
- `test_api_root.py`: fix the identity paths for the moved symbols
  (`mocode_tui.app.TUI`, `mocode_tui.testing.headless_tui`,
  `mocode_tui.core.events.Key`, …). The `__all__` pin list itself is untouched
  here (wave 05 re-pins it).
- Delete stale `__pycache__` leftovers of the pre-restructure layout.

## Acceptance (run in your worktree, paste true output)

1. `uv run pytest -q` — green; report the counts (baseline: 411 passed,
   1 skipped; you should land within ±40 tests of the policy shape).
2. `grep -rn "from ..keys\|from ..widgets\|from ..chat" src/mocode_tui/core/`
   — zero hits (the kernel imports nothing upward).
3. `grep -rn " as " src/mocode_tui/*/__init__.py src/mocode_tui/__init__.py | grep "import"`
   — no self-alias re-exports anywhere.
4. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff (logical rows unchanged).

## Forbidden

- `pyproject.toml` (no tooling, no version changes in this wave — and no
  ruff/mypy anywhere, per the overview's red lines).

- `src/mocode_tui/widgets/**` except: deleting `widgets/text.py`, the import
  fix-ups its removal requires, and `widgets/__init__.py` re-pointing `Text`.
- `src/mocode_tui/chat/**` except import fix-ups (no behavior edits).
- `docs/*.md` entirely; README prose (README **code blocks** only, for renames).
- `specs/**` (lead-owned). Any file of wave 02's scope (`widgets/input.py`,
  `editor.py`, `choice.py`, `autocomplete.py`, `table.py`, `tree.py`,
  `tabs.py`, `chrome.py`, `progress.py`, `spinner.py`, `status.py`,
  `layout.py`) beyond the import fix-ups named above — their dedup is wave 02.

## Report

Per the overview's final-report format. Include the diff-free demo check
output and the kernel-purity grep output verbatim.
