# Spec R6 · Test-suite consolidation to a lean core
> ✅ 2026-10-05 @ merged to main (R1 703/2, R2 698/1, R3 701/2, R4 703/2, R5 700/1, R6 202/1 — final gate)

> Branch `refactor/r6-test-consolidation`; worktree `~/.worktrees/mocode-tui/refactor-r6-test-consolidation`; depends on: R5
> merged; deep-read: `00-overview.md` (test policy section — binding here),
> `docs/DESIGN.md`, `docs/COMPONENTS.md`, `README.md`.

## Goal

The suite is 5,626 lines / 718 tests for 4,560 lines of source, and much of it
pins private internals (`_SETTLE_SECONDS`, `keys_mod.time`, `screen_mod
.terminal_size` monkeypatches, `Painter._throttle`, ctypes struct offsets),
asserts exact writer escape bytes, or runs exhaustive parametrize matrices —
so ordinary code motion breaks it. Consolidate to a **lean core suite that
tests contracts through the public API**, sized to catch real regressions
without breaking on refactors. Target: **200–320 tests**, ~30–45% of today's
line count, one test file per source module.

## Write scope (exclusively yours)

- all of `tests/` except `tests/test_api_root.py` (R5's file — keep untouched)
- the single canned-count line in `examples/pi_demo.py` (T8 only)
- nothing else. No source edits; if a kept test fails due to a *real* source
  bug, stop and report instead of patching source.

## Final suite shape (file → what must stay covered)

| File | Must keep covering (contract level) |
|---|---|
| `test_ansi.py` | the escape constructors the toolkit emits (`clear_screen`, `cursor_position`, mouse pair, alt pair) + `enable_vt` returns bool |
| `test_style.py` | `prefix()` for named/hex/tuple colors and attributes, attribute-only merge, `None` passthrough, hashability, unknown-name `KeyError` |
| `test_text.py` | `visible_width` (wide/CJK/empty), `wrap_text` space breaks + hard breaks + `width<=0`, `ellipsize_tail` essentials |
| `test_lines.py` | `Line.width/text/styled`, `fit` ellipsize, `pad_to`, `+`, `wrap_line` style survival + tab rule, `Line.filled` |
| `test_block.py` | duck-typed `Component`, add/get/remove, duplicate-id error, auto ids clear of explicit ones, `seal()` twice raises, `pin` validation + `pinned` |
| `test_screen.py` | non-live pipe screen: silent enter/leave, liveness decided once; `HeadlessScreen` records bytes, size settable |
| `test_viewport.py` | top/bottom regions never scroll, window height math, offset clamp, stick-to-bottom detach/re-attach, `more below` marker, cache invalidates on width change |
| `test_painter.py` | full repaint on resize (contains a clear-screen), steady-state writes only changed rows, unchanged frame writes zero bytes, non-live stays silent but `rows()` current, anchor clamping |
| `test_app.py` | document facade invalidation, `every`/cancel, throttle behavior via `TUI._clock` seam, `read_key` scroll interception + `scroll_keys` rebind/delete, `run()` enter/leave brackets incl. exception + `KeyboardInterrupt` + `stop()`, non-live dump contract (trailing blanks trimmed) |
| `test_keys.py` | decoder: printable/wide chars, control names, CSI nav + tilde family, modifiers ignored, incremental UTF-8, ESC/CSI settle + degrade, split sequences, bracketed paste (incl. unclosed), SGR wheel up/down, non-wheel dropped, unknown dropped |
| `test_keys_sources.py` | `ScriptedKeys` replay + EOF; `RawTerminalKeys` on pipes: cooked fallback flag, EOF sentinel, settle-after-silence (real time), close idempotent; console-record mapper via `keys_from_console_events` + `windows_input_mode` bit rules |
| `test_components_*.py` (11 files) | per component: default render at width 80, a narrow-width guard, the documented styles/tone/degrade paths, mutability contract (`.text` streaming where applicable) |
| `test_components_layout.py` | `Row` fixed/flex widths, gap, tallest-child height, overflow fit; `Column` stacking + gap |
| `test_api_root.py` | R5's export tripwire — untouched |

Renames allowed: `tests/test_layout.py` → `tests/test_components_layout.py`
(docstring updated; the module-name change mirrors R4's tree). `tests/
test_keys_windows.py` merges into `tests/test_keys_sources.py` (its
posix-pipe tests) plus the console-mapper rows; keep the `skipif` platform
gates that remain legitimate (real-console-only paths stay excluded).

## Deletion rules (from the overview, restated binding)

Delete any test that:
- asserts a private name (`_`-prefixed attribute inside a module, e.g.
  `painter._throttle`, `keys_mod._SETTLE_SECONDS`, ctypes struct fields),
- monkeypatches a module-global where a public seam exists
  (`screen_mod.terminal_size` → drive resize via `HeadlessScreen.width/height`
  setters; `keys_mod.time` → real-time settle tests),
- asserts exact writer escape bytes where the contract is "a full repaint
  happened / only changed rows were written" (assert on structure: presence of
  the clear-screen prefix, count of row writes, or the SpyScreen write list),
- duplicates a contract already covered by another file,
- has as its only subject code this group deleted,
- exists only as an exhaustive parametrize matrix of one behavior (keep 2–3
  representative rows).

Keep every test that names a documented behavior (README / DESIGN.md /
COMPONENTS.md / a public docstring) — if you cannot point at the sentence it
protects, it is a candidate for deletion.

## Tickets (one commit each)

### T1 — inventory + plan table

For each existing test file produce a table: file → current tests/lines →
final tests/lines → what is deleted (rule) → what stays (contract). Commit the
table in the branch as `tests/REFRACTOR_AUDIT.md`? No — do not add files to
`tests/`; put the table in your final report AND in the commit message of T2.

### T2 — component + layout files first (largest, safest)

Slim `tests/test_components_*.py` and rename/slim `test_layout.py` per the
rules; keep the contract rows in the table above. Commit per file group.

### T3 — kernel files (ansi/style/text/lines/block)

Same treatment. Keep `Line.filled` coverage, keep the unknown-color `KeyError`
contract, keep wrap CJK/wide rows.

### T4 — render core + driver files (screen/viewport/painter/app)

Replace `terminal_size` monkeypatches with `HeadlessScreen` size setters; keep
the zero-bytes-on-unchanged-frame and non-live-silent contracts via a
`SpyScreen`-style double if one already exists in the file; keep the
non-TTY dump contract.

### T5 — keys files

Rewrite `test_keys.py` (decoder contracts only) and fold `test_keys_windows.py`
into `test_keys_sources.py` per the shape table; console mapper stays pinned to
the two seams. Settle-window tests use real time with the documented 50 ms
window and a `pytest-timeout`-compatible margin.

### T6 — mutation audit (required evidence the suite still bites)

Before finishing, run at least these mutations one at a time, each confirmed
to make `uv run pytest -q` fail, reverting after each:

1. `Divider`'s default `char` changed;
2. `Viewport`'s `more below` marker condition inverted;
3. `KeyDecoder` `_char_key` mapping `\t` → dropped instead of `tab`;
4. `Line.fit` no longer appending the ellipsis;
5. `Painter` writing every row every frame (diff disabled);
6. `TUI.read_key` no longer intercepting `scroll_keys`.

Report each mutation's failing test names (at least one per mutation). If a
mutation passes the suite, the suite has a hole — add the missing contract
test or report why it cannot be caught cheaply.

### T7 — final shape check

- `uv run pytest -q` — record total count and runtime (expect ≤ ~30s).
- `grep -rn "monkeypatch\|\._[a-z]" tests/` audit: remaining monkeypatches must
  be only `TUI._clock` (the documented seam) and platform gates; no `module._x`
  private assertions.
- Confirm one file per source module per the shape table and that
  `tests/test_api_root.py` is untouched.

### T8 — refresh the demo's canned test count (the one edit outside `tests/`)

R5 refreshed the demo's fenced bash line to its merge-time count; R6 changes
the count again. Your single file edit outside `tests/` is that one line in
`examples/pi_demo.py` — set it to the final post-consolidation summary
(`NNN passed, M skipped in X.XXs`, real values from your T7 run). This keeps
the shipped demo honest at the end of the group.

## Acceptance (run in your worktree, report real output)

1. `uv run pytest -q` — green; total count within the 200–320 band; runtime
   reported. If outside the band, justify in the report.
2. Before/after table per file (tests, lines) + total lines saved.
3. Mutation audit: the six mutations with the failing test names each.
4. `uv run python examples/pi_demo.py < /dev/null > out.txt; echo exit=$?; sha256sum out.txt`
   — will differ from the R5 dump by the refreshed count line only; show the
   diff against `specs/2026-10-05-mocode-refactor/ref/r0-demo-dump.txt` and
   confirm the changed lines are the count/time ones (no layout diffs).
5. `uv run pytest -q -p no:randomly` twice to prove no order dependence
   (if the plugin is absent, say so; the command must still pass).

## Red lines

- No source edits. No new test dependencies. No `tests/conftest.py` unless a
  shared fixture genuinely replaces duplication — if you add one, keep it under
  40 lines and explain in the report.
- Do not delete the contracts listed in the shape table's "must keep" column;
  if one is impossible to keep, stop and report.
- Do not re-test internals through the public API just to keep a favorite test:
  the point is contract coverage, not test-count preservation.

## Report format

Per-file before/after table / ticket status / commit hashes+messages / the six
mutation results / acceptance outputs 1–5 with real numbers / deviations &
open questions.
