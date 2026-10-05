# Spec 05 · Selection documentation & extension cookbook (Wave W5)

> ✅ 2026-10-06 — merged via selection/w5-docs.

> Branch `selection/w5-docs`. Prerequisite: **W4 merged** (the API is
> frozen). Must read: `specs/2026-10-05-selection/00-overview.md` — the
> D1–D8 rationale is the source you are publishing.

## Goal

Document the feature the way the refactor group learned to: prose that
matches shipped code, the design rationale preserved (not just the how,
the why), and an extension cookbook that routes future feature authors to
the four replacement points instead of into the kernel.

## Work order (each task = one commit; README examples green at every commit)

### T1 · `docs/DESIGN.md`
- New "Selection" section: D1 document-space addresses (and why screen
  space was rejected), D2 the overlay at the composition root (sealed
  cache stays pristine, per-row diff repaint), D3 the mechanism/policy
  table, D4 time-driven edge auto-scroll (the stationary-pointer argument
  and the no-hit_test-in-tick rule), D5 the viewport-region edge, D6
  OSC 52 best-effort + the `on_end` contract, D7 the two-selections
  boundary (document overlay vs TextBuffer), D8 reflow/streaming
  semantics. Mode table updated (1000+1002+1006; what each buys).
  Event model section gains `MouseEvent.kind`.

### T2 · `docs/COMPONENTS.md` + README
- COMPONENTS: `SelectionGesture` constructor sketch, the gesture state
  machine (press/drag/release/edge/double-click), `copy_on_select`, the
  `Screen.copy` primitive, and the **extension cookbook** — four worked
  replacement points: (1) drive `tui.set_selection` from your own loop
  (e.g. select a search-hit range programmatically), (2) replace `on_end`
  (the `/quote` example: `composer.prefill(extract(doc, sel))` shown as a
  documented snippet, explicitly not shipped chat API), (3) disable
  sub-gestures (no double-click, no autoscroll knobs), (4) restyle the
  highlight (`merge` at the call site). README: feature bullet, a
  runnable quick-selection snippet (host reads events, one
  `SelectionGesture(tui)` line, paste-bracket symmetry note), the root
  table +1 row, the "what lives where" gains `mocode_tui.selection`.

### T3 · Final sweep
- `grep -rn "SelectionGesture\|copy_on_select\|set_selection\|OSC 52" docs README.md`
  — every hit true against shipped code; every executable block runs
  (`test_readme_examples.py` + local execution of the COMPONENTS
  snippets, stated in the report).

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. The T3 grep, verbatim, with a per-hit truth note.

## Forbidden

- `src/**`, `tests/**`, `examples/**`, `specs/**`, `pyproject.toml`,
  `uv.lock`. Docs-only wave; a claim that needs code means stop-and-report.

## Report

Per the overview format; list every snippet and how it was executed.
