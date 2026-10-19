# Spec W2 · The token vocabulary — rename, caret split, ground tokens
> Branch `refactor/118-tokens`; after: W1 merged; read first: `00-overview.md`, `ref/industry.md`

## Goal

Make the Theme's band vocabulary one token per role (D1/D2), with the demo's theme
showcase page updated in the same wave. No widget changes beyond the token picks — the
row-band contract is W3a's ticket.

## Tickets (one commit each, in order)

### T1 — the `CURSOR` constant becomes `FOCUS`

`src/motui/kernel/style.py` and `src/motui/kernel/__init__.py`: rename the constant
`CURSOR` → `FOCUS` (value unchanged: `Style(reverse=True)`), in `__all__`, in the
kernel facade's import list and `__all__`, and in the module's semantic-constants
comment block. Grep the tree for `CURSOR` (tests included — `tests/test_style.py`,
`tests/test_api_root.py`) and update every reference.

### T2 — the Theme fields

`src/motui/kernel/theme.py`:

- Rename the field `cursor` → `focus` (default `FOCUS`).
- Add `caret: Style = Style(reverse=True)` — inline, the `Theme.hover` precedent — the
  text caret's own token (Textual's `$input-cursor-background` is its analogue,
  `ref/industry.md` §1).
- Add `ground: Style = NONE` — the resting surface (Textual's `$surface`).
- Add `ground_active: Style = Style(reverse=True)` — the engaged row surface (Textual's
  `$block-cursor-background`; D2 records that the keyboard cursor and the pointer
  hover share this token today).
- Update the class docstring's band description so each token's role is stated once,
  and the module docstring's constant list.

### T3 — the consumers

- `widgets/textfield.py`: the caret's pick becomes `self._pick(cursor_style, "caret")`
  (the explicit parameter keeps its name `cursor_style` — it styles the caret).
- `widgets/action.py` (both sites), `widgets/collapsible.py`,
  `widgets/indicators.py`, `widgets/choice.py` (the `Radio` / `CheckGroup`
  `focus_style` picks): `"cursor"` → `"focus"`. These are controls; their band is the
  focus band.
- Grep the whole `src/` tree for `"cursor"` picks and `theme.cursor` attribute reads to
  prove the list is complete; report the grep output.

### T4 — the themes showcase page

`src/motui/demo/pages/themes.py`: in `_BANDS`, rename `"cursor"` → `"focus"` and add
`"ground"`, `"ground_active"`, `"caret"` (order them to read as the family: resting
surface, engaged surface, then the bands). The page renders a swatch per name through
`getattr`, so a wrong name fails loudly.

### T5 — the tests

- `tests/test_theme.py`: the token-set assertions (`DEFAULT_THEME.cursor == CURSOR`
  becomes the `focus` equality; add `ground` / `ground_active` / `caret` defaults), and
  the input-caret test (the `cursor=` theme override becomes `caret=`).
- `tests/test_style.py`, `tests/test_api_root.py` (facade pins), and every test the
  T3 grep finds.
- Re-record the golden frames (`uv run python tools/golden.py --update`) — the themes
  page grows rows, which is the registered golden move for this wave. Report
  `git diff --stat tests/golden/pages/`: **only the themes page may move**; any other
  page moving is a finding to report, not to silently accept.

## Acceptance (real output in the report)

1. `uv run pytest -q` — full suite green; state the counts.
2. `uv run python tools/golden.py --check` — green, with the diff summary above
   attached as the evidence for the one moved page.
3. The framebench line and both piped demo runs from the overview's gate block.
4. `grep -rn '"cursor"' src/` answers only the caret pick and the demo's renamed entry.

## Red lines (zero diff outside)

`kernel/lines.py`, `kernel/viewport.py`, `kernel/frame.py`, `interaction/`, every
`widgets/` file other than the picks in T3, `docs/`, `specs/`, `pyproject.toml`.

## Report format

Per-ticket status table / commit hashes + messages / the gate's real outputs / the T3
grep output / the golden diff summary / deviations / open questions. Blocked → stop
and report.
