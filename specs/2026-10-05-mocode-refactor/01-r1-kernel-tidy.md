# Spec R1 · Kernel tidy (dead helpers out, `RESET` dedup, `Line.filled` in)
> ✅ 2026-10-05 @ merged to main (R1 703/2, R2 698/1, R3 701/2, R4 703/2, R5 700/1, R6 202/1 — final gate)

> Branch `refactor/r1-kernel-tidy`; worktree `~/.worktrees/mocode-tui/refactor-r1-kernel-tidy`;
> depends on: none (first wave); deep-read: `00-overview.md`, `docs/DESIGN.md`.

## Goal

Shrink the kernel to what the toolkit actually uses and remove the two
duplicated escape constants, **without changing rendered output**. This wave
adds the one new kernel primitive the later component tidy (R4) adopts.

## Write scope (exclusively yours)

- `src/mocode_tui/ansi.py`, `src/mocode_tui/style.py`, `src/mocode_tui/text.py`,
  `src/mocode_tui/lines.py`
- `tests/test_ansi.py`, `tests/test_style.py`, `tests/test_text.py`,
  `tests/test_lines.py`
- delete `probe_keys.py` (repo root)
- no other file. In particular you do NOT touch `src/mocode_tui/__init__.py`
  (it imports none of the deleted names), `components/`, `keys.py`, `app.py`,
  `screen.py`, `viewport.py`, `painter.py`, docs, or the demo.

## Tickets (one commit each, in order)

### T1 — delete the ratified dead helpers

Delete exactly these, in code and in each module's `__all__`, plus the tests
that exist only to assert them:

- `ansi.py`: `move_up`, `move_to_column`, `delete_lines`, `erase_down`,
  `strip_ansi`, `stdout_isatty`, `RESET` (and the now-unused `_ANSI_RE` regex).
- `text.py`: `one_row`, `ellipsize_middle`.

For each deletion first re-run the grep proof yourself (the lead already
verified it once):

```
grep -rn "<name>" src examples docs README.md tests --include="*.py" --include="*.md"
```

The only remaining references must be the definition site and that symbol's
own tests. Remove those tests (only tests whose subject is deleted — keep all
other tests in those files byte-for-byte where possible). `TAB_WIDTH` stays
(used by `visible_width`) but drops out of `text.__all__` since `one_row` is
gone; `ESC` and `CLEAR_LINE` in `ansi.py` stay (internal use / `clear_line`).
`style.RESET` is the single definition and stays where it is.

### T2 — add `Line.filled(width, style=NONE)`

In `lines.py`: a method returning a full-width single-segment line, i.e. the
equivalent of `Line.from_text(" " * width, style).fit(width)` but expressed
once, with `width <= 0` yielding an empty line. Document it as the primitive
for band/padding rows (used by `Message`/`ToolBlock`/`EditBlock` in R4 and by
custom components). Add 2–4 focused tests in `tests/test_lines.py` (empty at
`width <= 0`, exact width, style carried). Do **not** adopt it in
`message.py`/`tools.py` yet — that is R4's ticket.

### T3 — delete `probe_keys.py`

It is a self-described temporary diagnostic from the W7 input debugging; the
consumer it was built for no longer exists.

### T4 — doc touch inside the touched modules only

Update module docstrings/comments that reference deleted names (e.g.
`ansi.py`'s "single source of ANSI escape sequences" stays accurate; drop any
sentence about `strip_ansi`). No edits to `docs/`, `README.md`, or the demo in
this wave.

## Acceptance (run in your worktree, report real output)

1. `uv run pytest -q` — green (expect 716 minus the deleted-symbol tests,
   plus your new `Line.filled` tests; report the exact line).
2. `uv run python examples/pi_demo.py < /dev/null > out.txt; echo exit=$?` then
   `sha256sum out.txt` — must equal the R0 baseline
   `71d09ff2f763b8f24376eb764be9b5c2467bc869cf8110c4c17f8621c9a1c981`
   (a diff means you changed behavior — stop and report).
3. `uv run python -c "import mocode_tui, mocode_tui.ansi as a; print(mocode_tui.__file__); print(hasattr(a,'strip_ansi'))"`
   — worktree path + `False`.
4. `uv run python -c "from mocode_tui import Line, NONE, SUCCESS; print(repr(Line.filled(3, SUCCESS).segments))"`.

## Red lines

- No new dependency, no public-name removal beyond the ratified list, no
  rendered-output change.
- Never touch the main checkout, never merge/push, never `git checkout main`.
- If any deletion above turns out to have a consumer you did not expect: stop
  and report (honest exit), do not "save" the reference yourself.

## Report format

Ticket status table / commit hashes+messages / real command outputs for all
four acceptance commands / deviations & tradeoffs / open questions.
