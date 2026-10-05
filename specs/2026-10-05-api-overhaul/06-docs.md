# Spec 06 · Docs rewrite + test-file consolidation (Wave W4)

> Branch `refactor/w4-docs`. Prerequisite: **W3b merged** (the API is frozen
> by the time you start). Must read first:
> `specs/2026-10-05-api-overhaul/00-overview.md`.

## Goal

Make the three documents describe the shipped system (they currently carry
stale claims — the four-layer purity that W1 just made true again, an old
heading ladder, an old `builtin` token style, spec-history archaeology), and
finish the test-suite consolidation inside the ceiling.

## Work order (each task = one commit)

### T1 · `docs/DESIGN.md`
- Rewrite against the final architecture: top-level `app.py`/`testing.py`,
  `core.events` (0-based coordinate charter — one paragraph, all cells
  0-based), the painter-as-pure-differ (`Painter.paint(layout)`), the naming
  charter table from the overview, style-resolution-at-construction,
  `handle_key(event)` width-from-last-render, `MORE_BELOW` public.
- Delete the revision-history archaeology ("added 2026-10-05 (W16)",
  "revised by W11", the W-era paragraphs). Keep the "Deliberately out of
  scope" list, refreshed.

### T2 · `docs/COMPONENTS.md`
- Constructor sketches for the final signatures (`handle_key(event)`, no
  `prompt_style`, `theme=` only where read, `Markdown(text, theme=,
  highlighter=, block_rules=, inline_rules=, gap=, divider_max_width=)`).
- New "custom Markdown rule" walkthrough built on `RenderContext` (the
  replacement for the `with_*` cloning prose): one `InlineRule` example end
  to end. Fix the stale heading-ladder and `builtin`-bold rows to match
  `core/theme.py` and `widgets/syntax.py` as shipped.
- Keep the `ProgressBar` custom-component walkthrough and the
  measure-don't-guess rules.

### T3 · `README.md`
- Prose pass over the final feature set and the curated root; the import
  table of "what lives where" (root vs `core`/`keys`/`widgets.markdown`/
  `widgets.syntax`); theme/keymap customization sections on final names.
  **Every code block keeps executing green** (`test_readme_examples.py`).

### T4 · Test-file consolidation + ceiling
- Merge the small suites by domain: `test_widgets_{spinner,status,text,tabs,
  progress}.py` → `tests/test_widgets_basics.py`;
  `test_widgets_{tree,chrome,layout}.py` stay or merge at your judgment if
  the merge is pure motion (no assertion changes);
  `test_chat_{message,tools}.py` → `tests/test_chat_components.py`.
  Pure file motion only — assertions were settled in W1–W3a.
- Verify and report the final suite shape: **≤ 290 tests, ≤ 3,100 lines**,
  the eight contract families of the overview each with a home. If you are
  over the ceiling, stop and report rather than deleting contracts.

## Acceptance (paste true output)

1. `uv run pytest -q` — green, with the final counts.
2. `uv run ruff check src tests examples` + `uv run ruff format --check` — clean.
3. `uv run mypy src` — clean.
4. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
5. The counts: `find tests -name "*.py" | xargs wc -l | tail -1` and the
   test-function total, verbatim.

## Forbidden

- `src/**` (docs-only wave; if a doc claim cannot be made true without a code
  change, stop and report), `examples/**`, `specs/**`, `pyproject.toml`.
- Assertion changes in the merged test files (pure motion; renames only where
  a moved helper requires them).

## Report

Per the overview format, plus the final suite numbers against the ceiling.
