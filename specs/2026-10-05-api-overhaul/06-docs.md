# Spec 06 · Docs rewrite (Wave W4)

> Branch `refactor/w4-docs`. Prerequisite: **W3b merged** (the API is frozen
> by the time you start). Runs in parallel with W5 (test trim) — your scope
> is `docs/**` + README prose; you do not touch `tests/**`.
> Must read first: `specs/2026-10-05-api-overhaul/00-overview.md`.

## Goal

Make the three documents describe the shipped system (they currently carry
stale claims — the old four-layer purity that W1 made true again in a new
shape, an old heading ladder, an old `builtin` token style, spec-history
archaeology, `handle_key(key, width)` rows, `sync_query`, and the flat
`markdown.py` tree). The test-file consolidation lives in wave 07 (W5) —
you do not touch `tests/**`.

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
  Known stale spots to fix: the Components table's `handle_key(key, width)`
  row for Input; the package-layout tree showing `markdown.py` (a package
  since W2b); "pins all five surfaces" (it is seven now); the testing
  section's link to `specs/2026-10-05-markdown-polish/ref/after-pi-demo.txt`.

### T3 · `README.md` (continued)
- Also drop the old `sync_query` mention if any survives, and keep the
  "Not on purpose" list refreshed.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (your changes must not break the README
   example tests).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. `grep -rn "sync_query\|set_cursor_anchor\|with_theme\|with_highlighter\|handle_key(.*width\|markdown\.py" docs README.md`
   — zero hits (no stale names survive the rewrite).
4. Every documented code snippet that is executable was either run or is
   covered by `test_readme_examples.py` — state which.

## Forbidden

- `src/**`, `tests/**` (wave 07 owns it), `examples/**`, `specs/**`,
  `pyproject.toml`. If a doc claim cannot be made true without a code
  change, stop and report.

## Report

Per the overview format.
