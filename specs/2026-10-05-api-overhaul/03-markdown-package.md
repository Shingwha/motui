# Spec 03 · Markdown package split + RenderContext (Wave W2b)

> Branch `refactor/w2-markdown`. Prerequisite: **W1 merged** (cut from post-W1
> main). Runs in parallel with W2a — your write scopes are disjoint.
> Must read first: `specs/2026-10-05-api-overhaul/00-overview.md`.

## Goal

Split the 961-line `widgets/markdown.py` monolith into a package and replace
the six stacked `with_*` re-bind passes with one `RenderContext` passed into
the rules — so a custom rule is "implement the protocol, read the ctx" instead
of "implement five cloning conventions". **Rendered rows stay identical.**

## Work order (each task = one commit)

### T1 · The package
- `widgets/markdown.py` → `widgets/markdown/`:
  - `__init__.py` — the public face: `Markdown`, `BlockRule`, `InlineRule`,
    `BLOCK_RULES`, `INLINE_RULES`, and the concrete rule classes
    (`HeadingRule`, `FenceRule`, `TableRule`, `ThematicBreakRule`,
    `QuoteRule`, `ListRule`, `ParagraphRule`, `CodeInlineRule`,
    `BoldInlineRule`, `ItalicInlineRule`, `LinkInlineRule`),
    `inline_segments`, `RenderContext`.
  - `blocks.py` — the block rules + `_run_blocks` loop.
  - `inline.py` — the inline rules + `inline_segments`.
  - `context.py` — `RenderContext`.
  - the component (`Markdown` class) in `__init__.py` or `component.py`, your
    call — keep files under ~300 lines each.
- Import paths stay stable: `from mocode_tui.widgets.markdown import Markdown`
  and `from .markdown import Markdown` (in `widgets/__init__.py`, which you do
  **not** touch) keep working unchanged.

### T2 · RenderContext kills the `with_*` quilt
- `RenderContext` is a frozen dataclass: `theme: Theme`, `highlighter:
  Highlighter | None`, `divider_max_width: int` (+ whatever `stops` actually
  carries — investigate and fold it in or drop it if inert).
- Protocol signatures become:
  - `BlockRule.render(lines, width, ctx) -> list[Line]` (`match(lines, i)`
    unchanged — matching never needed the deps);
  - `InlineRule.match(text, pos, ctx) -> tuple[int, list[Segment]] | None`
    (inline rules need `ctx.theme` for styling);
  - `inline_segments(text, ctx)`.
- `BLOCK_RULES` / `INLINE_RULES` become dep-free module singletons. Every
  `with_theme` / `with_highlighter` / `with_inline_rules` / `with_stops` /
  `with_divider_width` / `with_block_rules` method and the `_InlineMixin`
  constructor-signature shims are deleted. `Markdown.__init__` is a plain
  constructor: `text`, `theme=`, `highlighter=`, `block_rules=`,
  `inline_rules=`, `gap=`, `divider_max_width=` — it builds one `RenderContext`
  and passes it down.
- Delete the `starts_block` leak if it loses its consumer; keep streaming
  safety exactly as implemented (unclosed fence runs to end-of-buffer, tables
  need the delimiter row, unclosed inline markers stay literal).

### T3 · Syntax module tidy-up
- `widgets/syntax.py`: `_append` → `core.lines.fuse`; the markdown-side
  colored-vs-attribute rule (in the inline pipeline) → `core.lines.overlay`.
  Behavior identical; no public change to `Highlighter` / `RegexHighlighter` /
  `default_highlighter` / `highlight`.

### T4 · Tests under the policy
- `test_widgets_markdown.py`: keep ~12 focused tests — one representative
  box-drawing table grid (not four), heading/streaming/list/quote coverage via
  row-text assertions; drop `test_table_alignment_markers` (covered by the
  table suite); custom-rule tests rewritten to the RenderContext style.
- `tests/test_widgets_markdown_highlight.py`: delete; its two real cases merge
  into the syntax file.
- `tests/test_widgets_syntax.py`: 23 → ~12 tests; the 13 per-language token
  goldens become **one `@pytest.mark.parametrize` table** (language, code,
  expected token-text runs — assert token boundaries and round-trip styles,
  not default colors); drop the self-duplicate theme-variant pair.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts reported).
2. `uv run ruff check src tests examples` + `uv run ruff format --check` — clean.
3. `uv run mypy src` — clean.
4. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff (the demo's `/md` fixture exercises the engine).
5. `grep -rn "with_theme\|with_highlighter\|with_inline_rules\|with_stops\|with_divider_width\|with_block_rules\|_InlineMixin" src tests`
   — zero hits.
6. Render equivalence proof: a throwaway script (in your report, not
   committed) rendering `examples/Markdown-Rendering-Test.md` at widths
   40/80/120 through old (pre-W1 baseline via `git show main:…` if needed)
   and new engines producing identical `Line` streams — or state precisely
   why you rely on the test suite instead.

## Forbidden

- `src/mocode_tui/widgets/{input,editor,choice,autocomplete,table,tree,tabs,chrome,progress,spinner,status,layout}.py`
  and `widgets/textbuf.py` (wave W2a).
- `src/mocode_tui/widgets/__init__.py` (the import path preservation only
  works if you do not touch it — the package `markdown/` keeps the name).
- Their test files (`test_widgets_{input,editor,input_keymap,choice,
  autocomplete,table,tree,tabs,chrome,progress,spinner,status,layout}*.py`).
- `src/mocode_tui/chat/**`, `src/mocode_tui/core/**` (read-only),
  `src/mocode_tui/{app,testing}.py`, `examples/**` (the demo adapts in W3b),
  `docs/**`, `specs/**`, `pyproject.toml`, `tests/_doubles.py`.

## Report

Per the overview format. Include the new package's per-file line counts and
the before/after line count of the old monolith.
