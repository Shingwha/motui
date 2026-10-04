# Refactor Group · 2026-10-05 · mocode-tui tidy-up
> ✅ 2026-10-05 @ merged to main (R1 703/2, R2 698/1, R3 701/2, R4 703/2, R5 700/1, R6 202/1 — final gate)

## Goal and scope

One spec-team operation = this group. Goal: after the W1–W16 build-out the
toolkit works, but the tree carries dead helpers, duplicated helpers, one
881-line god module (`keys.py`), a misplaced `layout.py`, stale docs, and a
5,626-line test suite that pins private internals and exact escape bytes — so
ordinary code motion breaks it. This group restructures the package for
clarity, extensibility and API convenience, deletes ratified dead code, and
consolidates the test suite to a lean core. **No user-facing behavior change**
except the explicitly ratified deletions and additive API in R5.

Labels are **R-waves** (refactor), not W-waves: docs still cite the historical
W1–W16 build waves as history, and the new waves must stay distinguishable.

## Baseline facts (verified by the lead on 2026-10-05, commit f89e627)

- `.venv/Scripts/python.exe -m pytest -q` → **716 passed, 2 skipped in ~2.5s**
  (the 2 skips are POSIX-only marks in `tests/test_keys_windows.py`).
- Source ≈ 4,560 lines under `src/mocode_tui/`; tests ≈ 5,626 lines;
  `examples/pi_demo.py` 553 lines; docs 381 lines.
- Runtime dependency is `wcwidth` only; dev deps pytest / pytest-asyncio /
  pytest-timeout. No new dependency may be added.
- **Toolchain: `uv` only.** Python, environments and every run/test command go
  through `uv run` (the lead's ratified convention for this repo). A fresh
  worktree has no `.venv`, so the **first** `uv run` in a worktree builds one
  and installs the project editable — pointing at *that worktree's* `src/`.
  Verified: `uv run python -c "import mocode_tui; print(mocode_tui.__file__)"
  ` resolves inside the worktree, `uv run pytest -q` is green there
  (716 passed, 2 skipped), and no `PYTHONPATH` juggling is needed. Never use
  the main checkout's `.venv` interpreter directly, and never run gates from
  the main checkout while testing a wave.

## Target architecture

```
src/mocode_tui/
  __init__.py            # public face: package root exports (additive only)
  ansi.py                # escape-byte constructors + Windows VT probe
  style.py               # Style + semantic palette constants
  text.py                # width measurement / wrap / ellipsize (single source)
  lines.py               # Segment / Line / wrap_line
  block.py               # Component protocol, Block, BlockState, Document
  screen.py              # Screen protocol, TerminalScreen, HeadlessScreen
  viewport.py            # Viewport, ScreenLayout
  painter.py             # Painter (row-diff rendering, cursor anchor)
  app.py                 # TUI driver (facade, pump, lifecycle)
  testing.py             # headless_tui, snapshot
  keys/                  # NEW package: same public surface as old keys.py
    __init__.py          # re-exports the public names
    events.py            # Key, MouseEvent, Paste, KeySource protocol
    decoder.py           # KeyDecoder + key tables + SGR mouse decode
    sources.py           # ScriptedKeys, RawTerminalKeys
    console.py           # Windows console plumbing (ctypes, mode, records)
  components/
    __init__.py          # every component + Row/Column (one import surface)
    text.py spinner.py status.py message.py chrome.py choice.py
    table.py tools.py input.py markdown.py
    layout.py            # MOVED from mocode_tui/layout.py
```

Invariants the whole group must keep:

1. **Public surface is stable.** Every name in today's `mocode_tui.__all__`
   keeps importing from `mocode_tui`; R5 only *adds* `visible_width`,
   `wrap_text`, `ellipsize_tail`. `mocode_tui.components` exports every
   component plus (new) `Row`/`Column`. `mocode_tui.keys` exports the same
   seven names as before (`Key`, `KeyDecoder`, `KeySource`, `MouseEvent`,
   `Paste`, `RawTerminalKeys`, `ScriptedKeys`) — now via a package `__init__`.
   Deletions outside the ratified list below are forbidden.
2. **The component protocol is frozen**: `render(width) -> list[Line]`, pure,
   no screen/keys/app imports below `components/`.
3. **The non-TTY contract is unchanged**: non-live screen → silent run, final
   plain-text dump on exit (exception path included).
4. **Rendered output is behavior-preserving**: the piped `pi_demo` dump and
   doc examples must render identically (byte-identical) across R1–R5; any
   intentional diff must be listed in the wave report with justification.
5. **No new dependencies**; `wcwidth` stays the only runtime dep.
6. Every commit passes the full suite; no half-migrated intermediate states.

## Wave table

| Wave | Contents | Branch | Depends on | Parallel with |
|---|---|---|---|---|
| R1 | kernel tidy: dead ansi/text helpers out, `RESET` de-duplicated, `Line.filled` in, `probe_keys.py` deleted | `refactor/r1-kernel-tidy` | — | — |
| R2 | `keys.py` → `keys/` package (events/decoder/sources/console) | `refactor/r2-keys-package` | R1 | R3, R4 |
| R3 | render core + driver tidy: `Painter.throttle` dead param out, DESIGN sync | `refactor/r3-render-driver` | R1 | R2, R4 |
| R4 | components tidy + `layout.py` → `components/layout.py` | `refactor/r4-components-layout` | R1 | R2, R3 |
| R5 | root API additions (text helpers) + README/DESIGN/COMPONENTS final sync + demo count refresh | `refactor/r5-api-docs` | R2, R3, R4 | — |
| R6 | test-suite consolidation to a lean core (policy-driven deletion) | `refactor/r6-test-consolidation` | R5 | — |

Order inside the parallel block: R2 → merge → R3 → merge → R4 → merge (any
order; file sets are disjoint). Each gate runs before and after its merge.

## Ratified deletions (dead code — verified: no consumer in `src/`,
`examples/`, `docs/`, `README.md`; only their own unit tests reference them)

| Symbol | Module | Evidence |
|---|---|---|
| `move_up`, `move_to_column`, `delete_lines`, `erase_down`, `strip_ansi`, `stdout_isatty`, `RESET` | `ansi.py` | no src/examples/docs consumer; `RESET` duplicates `style.RESET` (the one `lines.py` imports) |
| `one_row`, `ellipsize_middle` | `text.py` | no consumer outside `tests/test_text.py` |
| `Spinner.interval` attribute | `components/spinner.py` | only asserted by `tests/test_components_spinner.py`; the demo drives `tui.every` with its own constant |
| `Input.newline()` | `components/input.py` | only called by `tests/test_components_input.py`; `insert("\n")` is the same operation |
| `Painter(..., throttle=...)` parameter + `_throttle` field | `painter.py` | stored, never read (its own docstring: "accepted for API stability only"); `TUI.throttle` is the real one |
| `probe_keys.py` | repo root | self-described "Temporary diagnostic" dev script from the W7 input debugging |

`Text.merge`/`Style.merge`, `Line.fit/pad_to`, `Viewport.offset` and friends,
`Block.pinned`, `StatusBar.segment`, `HeadlessScreen.clear` are **kept** — they
are documented public API or consumed by the library/demo. R3/R6 may delete
`HeadlessScreen.clear` only if nothing references it after the trim.

## Ratified merges (redundancy → one implementation)

- `Message._pad_row` and the pure-padding case of `tools._band_row` become
  `Line.filled(width, style=NONE)` in `lines.py` (R1 adds it; R4 adopts it).
- `app._stdin_isatty` stays the single TTY helper (ansi's `stdout_isatty` is
  deleted above).
- Keep the shared `_wrap_spans` seam between `text.py` and `lines.py` (already
  single-source — do not fork it).

## Test policy (binding from R6; earlier waves only fix what their moves break)

The final suite keeps **contract tests through the public API**: rendered rows
(`Line.text`) at representative widths (80 and a narrow width), state-machine
essentials, lifecycle/teardown contracts, scroll+pin+scroll_keys behavior,
non-TTY contract, streaming-safety spot checks, Markdown rule-registry
behavior. It deletes: private-name assertions (`_`-prefixed attributes, module
globals monkeypatched where a public seam exists), exact escape-byte
assertions of writer internals, ctypes struct size/offset asserts,
kernel32-prototype asserts, exhaustive parametrize matrices, tests whose only
subject is deleted code, and duplicated coverage across files. Target: **200–
320 tests**; every kept test must trace to a documented behavior (README /
DESIGN.md / COMPONENTS.md / a public docstring). One test file per source
module, named `tests/test_<module>.py`.

Seams that legitimately stay injectable (documented as test seams): `TUI._clock`,
`HeadlessScreen.width/height` setters, `ScriptedKeys` scripts.

## Git / worktree protocol

Same as the spec-team skill: worktrees under `~/.worktrees/mocode-tui/<branch>`,
one branch per wave created from the latest `main` at dispatch, agents never
merge/push/touch the main checkout, lead merges `--no-ff` with a gate before
and after each merge. No push, no tag, no version bump in this group.

## Gate commands (run from the wave's worktree root)

```
uv run pytest -q                                        # full suite (first run builds .venv)
uv run python examples/pi_demo.py < /dev/null           # headless smoke; dump must equal the R0 baseline
uv run python -c "import mocode_tui; print(mocode_tui.__file__)"   # sanity: must point at THIS worktree
```

`ref/r0-demo-dump.txt` is the lead-captured R0 output of the piped demo
(sha256 `71d09ff2…c9a1c981`, 5878 bytes, exit 0). Waves R1–R4 must reproduce
it byte-identically; R5 refreshes the demo's stale canned test-count line,
which is the group's single intentional dump diff and must be reported.

## Environment facts

Windows 10/11 x64, Git Bash, repo at `C:\Users\shifu\Desktop\mocode-tui`
(no non-ASCII path segments). `uv` manages Python and every command
(`uv run pytest`, `uv run python …`); the pre-existing `.venv` was built that
way. No interactive terminal is available to agents: do not attempt to run the
live demo; the piped headless run (`< /dev/null`) is the smoke test.
Windows-only code paths (`keys/console.py`, `RawTerminalKeys` console branch)
cannot be exercised interactively — they are covered by the pure-mapper tests.

## Honest exits (allowed fallbacks)

- If a wave discovers a deletion/merge above would change rendered output, it
  stops and reports rather than improvising a fix outside its ticket.
- If the `keys/` split cannot preserve every name R6's consumers need, keep the
  transitional re-export and note it in the report (R6 owns the final cleanup).
- Nothing in this group requires UI re-design decisions; taste calls are
  already made above and must not be re-opened per agent.
