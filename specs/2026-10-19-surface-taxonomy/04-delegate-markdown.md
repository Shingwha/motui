# Spec W3b · `Delegate` and `Markdown(max_width)`
> ✅ 2026-10-19 @ `refactor/118-delegate` — merged (bedc9ba), the facade fix by the lead (6bc07cf)
> Branch `refactor/118-delegate`; after: W2 merged (parallel with W3a); read first: `00-overview.md`, `ref/industry.md`

## Goal

Two independent widget-layer additions: the single-child `Delegate` wrapper (D5 — the
urwid `AttrMap` pattern, `ref/industry.md` §5) and `Markdown`'s width cap (D6 — the
Textual `max-width` precedent, `ref/industry.md` §4). File-disjoint from W3a by
construction; do not touch W3a's files.

## Tickets (one commit each)

### T1 — `Delegate` (`widgets/delegate.py`, new; exported from `widgets/__init__.py`)

A single-child wrapper that answers every protocol surface itself, so a host wrapping
a motui component forwards nothing by hand. Read `kernel/block.py` first: `Block`
decides cacheability once with `isinstance(component, Revisioned)` (a
runtime-checkable protocol — method presence is the test), which is why the
degradation rules below are mandatory, not defensive decoration.

    class Delegate:
        child                                    # the wrapped component

        render(width)      -> the child's rows, verbatim
        revision()         -> the child's snapshot when it has one, else None
                              (None is the documented "memory off" answer — the block
                              cache stays off rather than keying on a lie)
        click(row, col)    -> the child's answer when it has the method, else False
        hover_at(row, col) -> the child's answer when it has the method, else False
        child_at(row, col) -> (child, row, col) — the container door: every cell maps
                              to the child at the same coordinates, so `descend`
                              reaches the leaf

- It never proxies `handle` / `move` / `activate` / `focused` — containers route
  coordinates and nothing else (the DESIGN.md rule); a host that needs those reaches
  `delegate.child` itself.
- No theme, no style, no memo: the wrapper is the identity — `Padding` (insets + fill)
  and `Panel` (frame) are the transforming siblings and stay as they are.
- Docstring: state both doors (the proxy door — the four forwarded surfaces; the
  container door — `child_at`) and the three degradation rules, each with its reason.
- Tests (a new `tests/test_widgets_delegate.py`, or `test_widgets_containers.py` if
  that is where single-child wrappers are tested today — check first): forwarding of
  each surface; the three degradations (a child without `revision` answers `None` and
  a `Block` around the wrapper stays uncached; a child without `click`/`hover_at`
  declines); `child_at` maps every cell and `descend` reaches the child; the
  revision-forwarding makes a sealed block's hovered child repaint (the
  sealed-staleness rule).

### T2 — `Markdown(max_width=None)` (`widgets/markdown/component.py`)

- New constructor parameter `max_width: int | None = None`, documented as the sibling
  of `divider_max_width` (Textual's `max-width`, `ref/industry.md` §4): it caps the
  wrap width, it never pads — a narrower row is legal, the painter clears the tail.
- `render` clamps before the cache: the effective width is
  `min(width, max_width)` when the cap is set, and the cache key uses the effective
  width so a pane wider than the cap still hits the cache. Degenerate caps
  (`<= 0`) clamp like a zero width does today — do not invent new behavior.
- Tests in `tests/test_widgets_markdown.py`: rows never exceed the cap; the cap is
  inert by default; the stream cache still hits at a pane width above the cap.

## Acceptance (real output in the report)

1. `uv run pytest -q` — full suite green; state the counts.
2. `uv run python tools/golden.py --check` — **zero diff** (this wave moves no pixel:
   nothing in the demo uses `max_width`, and `Delegate` has no demo consumer yet).
3. The framebench line and both piped demo runs from the overview's gate block.

## Red lines (zero diff outside)

Everything except `widgets/delegate.py` (new), `widgets/__init__.py`,
`widgets/markdown/component.py`, `tests/test_widgets_delegate.py` (new, or the
containers test file if that is the convention), `tests/test_widgets_markdown.py`.
In particular: `widgets/layout.py`, `widgets/decor.py`, every W3a widget, `kernel/`,
`interaction/`, `docs/`, `specs/`.

## Report format

Per-ticket status table / commit hashes + messages / the gate's real outputs /
deviations / open questions. Blocked → stop and report.
