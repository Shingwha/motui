# Spec W1 · The defaults and the hover rehoming
> Branch `refactor/119-defaults`; after: main; read first: `00-overview.md` (D1-D3, D5)

## Goal

The band family paints nothing by default (D1), the pointer row reads `hover`
(D3), and the invariant that keeps it that way ships as a test (D5). The
caret, focus and selection carve-outs (D2) are untouched.

## Tickets (one commit each, in order)

### T1 — the Theme defaults

`src/motui/kernel/theme.py`:

- `hover: Style = NONE` and `ground_active: Style = NONE` (`ground` already
  is). Update the field comments and the class docstring's band description:
  the band family is the host's to theme, and a default render paints
  structure and position only.
- `caret`, `focus`, `selection` keep their current values (D2).

### T2 — the pointer row reads `hover` (D3)

Repoint the row widgets' hover picks from `"ground_active"` to `"hover"`,
keeping every explicit `hover_style=` parameter (widgets without one keep
`_pick(None, "hover")`):

- `widgets/list.py` (the `_hover_style` pick), `widgets/tree.py` (the
  `_hover_style` pick), `widgets/table.py` (the `_hover_style` pick),
  `widgets/navlist.py` (the `_hover_style` pick), `widgets/choice.py` (the
  three hover picks: `Select`, `Radio`, `CheckGroup`).
- The cursor/selected picks stay on `"ground_active"`.
- The non-row consumers already pick `"hover"` (action, collapsible,
  indicators, tabs, textfield, markdown) — untouched.

### T3 — the precedence rule in the row pipeline (D3)

In each row widget's band resolution, the hovered row's band is the **hover**
band whatever row it is on (the pointer is the more immediate signal); the
unhovered cursor row's band is the **active** band. Read each widget's
`_band`/`_row`/pipeline as W3a left it and state the rule in one place per
widget (or in the shared helper if one exists). The unfocused rule (merge
`dim`) still applies to the active band.

### T4 — the invariant test (D5)

A new test file `tests/test_default_theme_paints_structure.py` (or the
existing theme test file if that is the convention — check first):

- Render the row family (`List`, `Tree`, `Table`, `NavList`, `Select`,
  `Radio`, `CheckGroup`) and the hover consumers (`Button`, `Link`,
  `Checkbox`, `Collapsible`, `Tabs`, `Text`, `Markdown`, `Input`, `Editor`)
  under `DEFAULT_THEME` in their default states (resting, unfocused,
  un-hovered): **zero `bg` on every segment, zero `reverse` except the caret
  cell** of `Input`/`Editor`.
- The two carve-outs, asserted as the documented exceptions: a *focused*
  control paints the `focus` band (reverse) — render one focused `Button` and
  assert it; a *selection* paints the `selection` band — assert through the
  existing selection tests rather than duplicating them.
- The docstring states the principle: the default paints structure and
  position; feedback is the host's.

### T5 — the expectations and the probe

- Update the expectations that pinned the 1.1.8 reverse defaults: the
  W3a-registered full-width engaged bands are now `NONE` bands — the
  engaged-row assertions lose the band, the resting-row assertions are
  untouched. Annotate each moved expectation with the D1 correction.
- The A/B probe (styled bytes, base commit against head, every widget, every
  state): resting rows byte-identical; engaged rows differ by exactly the
  band's disappearance. Report the numbers.
- Golden check must stay green with **no re-record** (a style-only change is
  invisible to the plain-text dump).

## Acceptance (real output in the report)

1. `uv run pytest -q` — full suite green; state the counts.
2. `uv run python tools/golden.py --check` — zero diff.
3. The framebench line and both piped demo runs from the overview's gate
   block (the render-hash may move only if a row widget enters the workload —
   report whatever it does).
4. `grep -rn '"ground_active"' src/motui/widgets/` answers only the
   cursor/selected picks.

## Red lines (zero diff outside)

`kernel/` other than `theme.py`, `interaction/`, `demo/`, `docs/`, `specs/`,
and every `widgets/` file other than the picks in T2/T3 (list, tree, table,
navlist, choice) plus their test files.

## Report format

Per-ticket status table / commit hashes + messages / the gate's real outputs /
the probe numbers / deviations / open questions. Blocked → stop and report.
