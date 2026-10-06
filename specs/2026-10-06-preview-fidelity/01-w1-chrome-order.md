# Spec W1 · The divider stacks outermost on its edge

> Branch `fix/w1-chrome-order`;前置: baseline `main` at `b1ddf5e`; 深读:
> `specs/2026-10-06-preview-fidelity/00-overview.md` (report 3),
> `docs/DESIGN.md` § The frame model (budget negotiation).

## 目标

A chrome band registered *before* a split must not end up outside the
divider. `pi_demo` registers its `Scrollbar` at start-up and splits later,
so today the divider lands one cell *inside* the scrollbar: the dim `░`
track column hugs the preview pane's first column, and the divider reads
one cell away from the gap it divides. 最高约束: the divider is the
outermost cell of the pane's edge it divides, determined by the kernel's
one stacking rule — never by registration timing, never by a host
remembering to register in the right order.

## 工单（按序，每项一个 commit）

### T1 叠序规则移到谈判里

- `src/mocode_tui/core/frame.py` `_negotiate`: order the pane's chromes so
  that a band named :data:`SEPARATOR_CHROME_NAME` on an edge is negotiated
  **first** (hence outermost) on that edge; every other band keeps
  registration order. `sorted` is stable, so a group's internal order is
  preserved — express it in one line with that fact in a comment.
- Update the docstrings that state the old rule: the `Chrome` class
  ("Chromes stack in registration order"), `Pane` (its `chrome` field), and
  `Frame.compose`'s negotiation paragraph in `docs/DESIGN.md` is the lead's
  to touch **only if** the worker's change makes a sentence wrong — read it,
  and report any sentence that needs rewording instead of editing (see 禁触
  清单). State the rule as: the divider is outermost by definition, the rest
  stack inward in registration order.

### T2 回归锚点

- `tests/test_frame.py`: add **one** test that pins the fix with the demo's
  own construction order — a right-edge marker chrome registered on the
  pane *before* `tui.split`/`Pane.split`, then compose and assert the
  divider cell is the pane's outermost column and the marker sits inside
  it. Follow the file's existing conventions (`_marker_chrome`,
  `FrameSpan`, no private-underscore assertions).
- Do not weaken or renumber any existing assertion.

## 验收（自测，报告真实结论）

1. `uv run pytest -q tests/test_frame.py -q` — paste
   the real counts (functions and failures).
2. `uv run pytest -q` — paste the real counts.
3. `.venv/Scripts/python.exe - <<'PY'` style probe proving the order: build
   a `TUI`, register a right-edge chrome on the primary pane *before*
   `tui.split("vertical")`, paint, and print the painted row's segments for
   the columns `[inner.right-2 : inner.right]` — the divider (accent) must
   be the last column of the pane, the marker the one before it. Paste the
   output.

## 禁触清单

`src/mocode_tui/core/text.py`, `examples/pi_demo.py`, `docs/**`,
`README.md`, every other `tests/**` file, `.zcode/**`. If a change outside
`core/frame.py` + `tests/test_frame.py` looks necessary, stop and report.

## 最终报告格式

Task table / commits (hash + message) / the three real outputs above /
deviations & trade-offs / open questions.
