# Spec Group 2026-10-05-api-overhaul · Ground-up API & Architecture Overhaul

> Lead: the main ZCode session. Workers: one agent per work order (01–06).
> Baselines: `ref/pytest-baseline.txt` (411 passed, 1 skipped), `ref/pi-demo-baseline.txt`
> (60-line piped dump of `examples/pi_demo.py`). Scale today: src 8,500 lines,
> tests 5,812 lines / 412 test functions. Suite target after this group:
> **≤ 290 tests, ≤ 3,100 lines.**

## Goal

Rebuild the system around a strict layering, one naming charter, and deduplicated
engines, and ship a curated ~63-name root API for external module users. The
render **engine kernel is out of scope for redesign** (Document → Viewport →
Painter → Screen flow, the `Component.render(width) -> list[Line]` contract,
per-row diff policy, throttle semantics all stay); everything around it is fair
game. **No backward compatibility** is kept or shimmed.

Owner decisions (already taken, do not re-litigate):

1. Keep the engine kernel; refactor layering, naming, duplication, Markdown,
   and the public API surface.
2. Root namespace tightens from 82 names to the curated list below.
3. `Input` and `Editor` share one internal `TextBuffer` engine; both stay as
   public components.
4. The test suite is slimmed under the test policy below (≈412 → ≈280 tests).

## Target architecture

```
mocode_tui/
  __init__.py      curated root API (~63 names, final list in 05)
  app.py           the TUI driver (composition root: imports core + keys)
  testing.py       headless_tui / snapshot (developer helpers, above core)
  core/            pure kernel: ansi, style, theme, text (measurement + the
                   Text component), lines (+ Segment utils), block, screen,
                   viewport, painter, events (Key/Paste/MouseEvent/KeySource
                   protocol + ScriptedKeys)
  keys/            decoder, keymap, sources, console (imports core.events only)
  widgets/         component library (imports core; input/editor also keys.keymap)
  chat/            chat layer (imports core + keys + widgets)
```

Layer rules (enforced by review, verified by grep in gates):

- `core` imports nothing from `keys`, `widgets`, `chat`, or the top-level
  modules. The current `core/app.py → ..widgets` / `..keys` and
  `core/testing.py → ..keys` upward imports are the cycle being killed.
- `app.py` and `testing.py` sit at the top level precisely because they are the
  composition root and the developer helper that may import `core` + `keys`.
- `keys` imports `core` (events protocol) only. `widgets` imports `core`
  (plus `keys.keymap`/`keys.events` for Input/Editor). `chat` imports all three.

## Naming charter (applies to every wave)

| Concept | Old | New |
|---|---|---|
| Paint one frame | `TUI.flush()` / `Painter.flush()` | `TUI.paint()` / `Painter.paint(layout)` |
| Push OS stream bytes | `Screen.flush()` | unchanged (the only true flush) |
| End-of-stream finalize | `KeyDecoder.flush()` | `KeyDecoder.finish()` |
| Current frame rows | `TUI.rows()` / `Painter.rows()` methods | `.rows` properties |
| Mouse coordinates | `MouseEvent.x/y` 1-based vs `Hit.row/col` 0-based | **all toolkit cells 0-based**; the decoder subtracts 1; `hit_test(x, y)` takes 0-based |
| Query filtering | `Autocomplete.set_query` vs `SlashPalette.sync_query` | `set_query` on both |
| Cursor pin | `Painter.set_cursor_anchor(row, col)` | `Painter.set_cursor(row, col)`; `Composer.anchor_cursor(tui)` stays |
| Bottom-pinned query | `Block.pinned` (false for `pin="top"`) | removed; `snapshot()` marks `,top` / `,bottom` from `block.pin` |
| Truncation family | `fit_text` / `ellipsize_tail` / `Line.fit` / `Line.pad_to` | `Line.fit` is the public face; `ellipsize_tail` stays public; the rest internal |
| Available child width locals | inner/budget/avail/track/usable | `inner` |
| Consume a key | `Input/Editor.handle_key(event, width)`, `SlashPalette.handle_key(event)` | `handle_key(event)` everywhere; the width comes from the component's last render |
| Key event names | `c-j` chords, `page_up` words | unchanged (hyphen for chords, underscore for words) — now documented |

## Style resolution charter

Components resolve `explicit style= > theme field > DEFAULT_THEME` **once, at
construction**, storing the resolved `Style` (or the resolved `Theme` as
`self._theme` when the choice is state-dependent). The ~65 render-time
`self.theme or DEFAULT_THEME` boilerplate sites disappear. Constructors keep
taking `style=` / `theme=` exactly as today (except the dead parameters listed
in the work orders).

## Test policy (global invariant; every wave rewrites its own tests under it)

1. Assert semantics, not goldens: row counts, text content, widths, selection,
   cursor. Styles are round-trip asserted (inject `Style(fg="#abcdef")`, assert
   the equal style flows out). **Default color values are never pinned.**
2. Byte/escape literals only where they ARE the module contract: `ansi.py`,
   `style.py`, and the keys decoder's `bytes → events` table.
3. No private-underscore assertions (sole exemption: the `TUI._clock` / `_tick`
   test-clock seam). No imports of non-exported symbols past a layer facade.
4. One behavior, one test: case matrices become `@pytest.mark.parametrize`
   (the suite currently has zero).
5. Shared doubles live in `tests/_doubles.py` (`Rows`, `RecordingScreen`,
   `texts(component, width)`, `many(n)`, `key(name)`), created in W1.
6. `─ more below ─` and similar literals are imported from the module that owns
   them (W1 makes `MORE_BELOW` public in `core/viewport.py`), never re-typed.
7. Hard ceiling for the finished group: **≤ 290 test functions, ≤ 3,100 test
   lines** (parametrized cases count as their one function; pytest's collected
   items may exceed the function count).
   These contract families must each keep at least one surviving test:
   block lifecycle, viewport layout semantics, painter diff policy, key
   decoding, keymaps, component structure, API surface pin, README examples,
   headless integration.

## Root API target (63 names — final list, implemented in 05)

Driver: `TUI`, `Hit`, `EveryHandle` · Screens: `Screen`, `TerminalScreen`,
`HeadlessScreen` · Primitives: `Block`, `Component`, `Line`, `Segment`,
`Style`, `Theme`, `DEFAULT_THEME` · Constants: `MUTED`, `ACCENT`, `SUCCESS`,
`ERROR`, `WARNING`, `DIM` · Measuring: `visible_width`, `wrap_text` ·
Events/keys: `Key`, `Paste`, `MouseEvent`, `KeySource`, `ScriptedKeys`,
`RawTerminalKeys`, `Keymap`, `DEFAULT_INPUT_KEYMAP`, `DEFAULT_EDITOR_KEYMAP` ·
Testing: `headless_tui`, `snapshot` · Widgets: `Text`, `Markdown`, `Table`,
`Tabs`, `Tree`, `TreeNode`, `Input`, `Editor`, `Select`, `Option`, `Confirm`,
`Autocomplete`, `Notice`, `Divider`, `Panel`, `Row`, `Column`, `Spacer`,
`Padding`, `Spinner`, `ProgressBar`, `StatusBar`, `StatusSegment` · Chat:
`Composer`, `Transcript`, `StreamHandle`, `Message`, `ToolBlock`, `EditBlock`,
`StatusLine`, `SlashPalette`.

Everything else stays public at its submodule path (`mocode_tui.core.Painter`,
`mocode_tui.keys.KeyDecoder`, `mocode_tui.widgets.markdown.BlockRule`,
`mocode_tui.widgets.syntax.Highlighter`, …) but leaves the root.

## Waves

| Wave | Spec | Branch | Parallel |
|---|---|---|---|
| W1 core kernel & layering & naming | 01 | `refactor/w1-core-kernel` | serial |
| W2a widget engine dedup | 02 | `refactor/w2-widget-engine` | with W2b |
| W2b markdown package + RenderContext | 03 | `refactor/w2-markdown` | with W2a |
| W3a chat layer on new seams | 04 | `refactor/w3-chat` | serial |
| W3b root API + demo + README + 0.3.0 | 05 | `refactor/w3-root` | serial |
| W4 docs rewrite | 06 | `refactor/w4-docs` | with W5 |
| W5 test-suite consolidation & trim | 07 | `refactor/w5-test-trim` | with W4 |

Merge order = the table order; W2a merges before W2b (both cut from the same
post-W1 main). Between waves the lead merges `--no-ff` and runs the full gate.

## Global invariants & red lines

- Logical behavior is preserved: same row content, same interaction semantics,
  same non-TTY contract. The painter diff policy tests (zero-byte unchanged
  frame, changed-rows-only, full repaint on resize) keep passing unchanged in
  spirit.
- Every commit independently passes the gate (pytest + the wave's greps +
  the demo baseline diff).
- **No lint/type tooling**: ruff and mypy are not introduced — no config, no
  dev-dependency, no formatting pass, not even as a "nice to have". Code
  quality is enforced by the simplicity rules: honest imports (a re-export a
  facade keeps is listed in its `__all__` — the `from x import y as y`
  self-alias idiom is **forbidden**), no dead parameters, no unused imports
  left behind, one concept one name.
- Zero diff outside a work order's write scope; the forbidden lists are per
  work order.
- No new compatibility shims; when a moved name loses its last consumer, the
  old name is deleted in the same wave.
- No `push`, no tags, no release. Version bump to `0.3.0` happens only in 05.
- Comments/docstrings/commits in English; commit subjects follow the existing
  style (`refactor: …`, `test: …`, one line, imperative).

## Git / worktree protocol (applies to all workers)

- Your worktree: `C:\Users\shifu\.worktrees\mocode-tui\<branch>` (lead created
  it; work only there). The main checkout at `C:\Users\shifu\Desktop\mocode-tui`
  is off-limits, as are other worktrees.
- Never `merge`, `push`, `rebase`, `tag`, or `checkout` another branch. Commit
  to your branch only.
- The lead merges after accepting your report; spec files belong to the lead —
  do not edit anything under `specs/`.

## Environment facts (all workers)

Windows 10, Git Bash, `uv` on PATH (`uv run pytest`, `uv run python`).
Python 3.12 via the project venv. Paths are ASCII. No browser, no GUI. A
non-TTY run of the demo is the scripted replay path (`python examples/pi_demo.py`
piped) — use it for A/B checks. `wcwidth` is the only runtime dependency.

## Final report format (every worker)

1. Work-order status table (task → done/deviated/blocked).
2. Commit list (hash + subject).
3. Real self-test results: the gate commands and their true output (counts,
   failures). No "should be fine".
4. Deviations & trade-offs taken.
5. Open questions for the lead.

Blocked → report the blocker and stop. Do not self-rescue outside your write
scope.
