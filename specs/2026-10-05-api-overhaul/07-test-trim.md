# Spec 07 · Test-suite consolidation and trim (Wave W5)

> ✅ 2026-10-05 — merged via refactor/w5-test-trim (honest-exit floor accepted).

> Branch `refactor/w5-test-trim`. Prerequisite: **W3b merged**. Runs in
> parallel with W4 (docs) — your scope is `tests/**` only, W4's is `docs/**`
> + README prose; you do not touch `README.md` or `docs/`.
> Must read first: `specs/2026-10-05-api-overhaul/00-overview.md` (test
> policy — binding).

## Goal

Finish what the per-wave rewrites started: the suite is behavior-clean
(zero private-underscore assertions, zero default-color pins, matrices
parametrized) but still **5,812 lines / 343 test functions / 456 collected
items**. Bring it to **≤ 3,100 lines and ≤ 290 test functions** without
orphaning any of the eight contract families (block lifecycle, viewport
layout semantics, painter diff policy, key decoding, keymaps, component
structure, API surface pin, README examples, headless integration).

Current per-area starting point (measure yourself, verify): kernel suites
(ansi/style/text/text_fit/lines/block), render/driver (screen/viewport/
painter/app), keys ×2, widgets ~13 files, chat ×6, pins (api_root/theme/
readme), `_doubles.py`.

## Work order (each task = one commit; gate green at every commit)

### T1 · File consolidation by domain
- Merge the small suites into domain files (pure motion + import fixes,
  no assertion changes): `test_widgets_{spinner,status,tabs,progress,
  tree,chrome,layout,layout_extras}.py` → `test_widgets_basics.py` (+
  a `test_widgets_containers.py` if basics would exceed ~450 lines);
  `test_chat_{message,tools}.py` → `test_chat_components.py`;
  `test_text.py` + `test_text_fit.py` + `test_lines.py` → `test_core_text.py`;
  `test_ansi.py` + `test_style.py` stay separate (byte-contract files,
  small already) or merge into `test_core_style.py` at your judgment.
- One short module docstring (≤ 5 lines) per consolidated file; the
  "Contracts (W…)" archaeology headers die with their files.

### T2 · Redundancy cuts (the audit's leftovers, now executable)
- The narrow-width guard (`row.width <= width`) exists as ~16 per-component
  variants → ONE parametrized test over the component set.
- `test_keys_sources.py`: consolidate the cooked/raw/pipe variants that
  assert the same contract through different entry points.
- Any test whose assertions are transitively implied by a surviving test
  (same public calls, same asserted outcomes, only setup differs) is cut.
- Module-docstring preambles across all remaining test files: ≤ 5 lines
  each (one sentence naming the contract under test).
- Local `_make`/`_field`-style builders that duplicate `_doubles.py`
  helpers go; `_doubles.py` may grow the genuinely shared ones (it is
  yours in this wave).

### T3 · Ceiling check
- Report the final shape: files, test functions, collected items, total
  lines, and the per-family survival map (which file/test holds each of
  the eight contract families).
- **Honest exit**: if reaching ≤ 3,100 lines would orphan a contract
  family or delete the last test of a documented public behavior, stop at
  the smallest safe number and report exactly what you would have had to
  cut — the lead decides, you do not guess.

## Acceptance (paste true output)

1. `uv run pytest -q` — green, final counts.
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff (you touch nothing the demo reads, but prove it).
3. `find tests -name "*.py" | xargs wc -l | tail -1` and the test-function
   total — verbatim, against the ceiling.
4. `grep -rn "tui\._\|painter\._\|composer\._\|_anchor" tests | grep -v "_clock\|_tick"`
   — zero hits (the policy holds after consolidation).

## Forbidden

- Anything outside `tests/**` (src, examples, README, docs, specs,
  pyproject). `_doubles.py` is yours here — the ONLY file outside
  `tests/` you may read-but-not-write is nothing; everything else is read-only.
- Assertion weakening to shrink lines: a test either keeps its contract or
  is deleted as redundant — never loosened.

## Report

Per the overview format, plus the per-family survival map and the
before/after file list.
