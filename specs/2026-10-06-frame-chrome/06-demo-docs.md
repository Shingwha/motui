# Spec 06 · Demo, docs, 0.4.0, re-baseline (Wave W6)

> Branch `chrome/w6-demo-docs`. Prerequisite: **W5 merged**. Must read:
> `specs/2026-10-06-frame-chrome/00-overview.md` (the constitution you are
> publishing; D9).

## Goal

Make the demo show the new world (scrollbar, copy-toast, `/preview`
split), make the documents describe it, bump 0.4.0, and re-baseline the
demo once, with the old baseline archived.

## Work order (each task = one commit; README examples green at every commit)

### T1 · Demo
- `examples/pi_demo.py`: attach a `Scrollbar` to the transcript pane;
  wire the selection `on_end` to copy + a success `Toasts.show("Copied N
  lines")` (the custom-on_end cookbook pattern, live in the demo); add a
  `/preview` slash command that splits the frame vertically
  (transcript | the Markdown fixture rendered live) with focus switching
  (a key binding and/or press-to-focus), closable back to one pane. The
  scripted replay gains a visit to `/preview`. Keep the demo's
  host-dispatched philosophy — the split command is host policy driving
  public APIs, nothing bespoke.
- Re-baseline: `git mv` the old baseline to `ref/pi-demo-baseline-pre-chrome.txt`
  (in `specs/2026-10-05-api-overhaul/ref/`), capture the new dump as
  `specs/2026-10-06-frame-chrome/ref/pi-demo-baseline.txt`. From this
  commit on, the gate diffs against the NEW baseline.

### T2 · Docs
- `docs/DESIGN.md`: the three-space-claims constitution (pane / chrome /
  overlay — with the "which one is this feature?" decision rule), the
  frame compositor, budget negotiation, the overlay registry, focus and
  wheel routing, the Composer band promotion, D7's selection scope.
- `docs/COMPONENTS.md` + README: `Scrollbar` / `Toasts` / `Pane` /
  `split` sketches, the dispatch-order contract, a "build your own
  chrome" walkthrough (a custom 2-column rail reading
  `offset/total_rows` — the reference recipe), a "build your own
  overlay" note pointing at the selection overlay as the worked example.
  README root table +3, feature bullets, the runnable quickstart gains
  the one-line `Scrollbar(tui)` (keeps executing green).

### T3 · Version + sweep
- `pyproject.toml` → `0.4.0` (uv.lock follows). Sweep: every doc claim
  grep-checked against shipped code (the selection-group T3 discipline);
  demo banner version follows; root pin = 68.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-06-frame-chrome/ref/pi-demo-baseline.txt`
   — no diff (the NEW baseline).
3. Root → 68; `grep -rn "0\.2\.0\|0\.3\.0" pyproject.toml examples README.md docs`
   → no stale version strings.
4. The docs truth-grep output, per-hit noted.

## Forbidden

- `src/**` (a doc/demo claim needing code = stop and report), `tests/**`
  (the demo's new behaviors get covered by the existing demo-execute
  harness `test_readme_examples.py` if it pins demo behavior — check and
  report; do not hand-add demo tests), `specs/**` except the two
  baseline-file moves of T1.

## Report

Per the overview format; include the new baseline's first/last lines and
the old baseline's archive path.
