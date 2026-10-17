# Golden frames

`pages/<page>.txt` holds one demo page's `python -m motui --pages` dump —
the page header rule plus the plain-text screen, rendered on a
`HeadlessScreen` at the replay's own geometry (`motui.demo.script.HEADLESS_W/H`),
LF line endings, one trailing newline. `tests/test_golden_frames.py` asserts
these files byte for byte and `uv run python tools/golden.py --check` is the
same assertion as a command line; both are green when nothing a user sees
moved. The one accepted other spelling is the exact `LF -> CRLF` conversion
a Windows checkout makes (`core.autocrlf`; this tree carries no line-ending
attributes on purpose) — `golden.matches` is that rule, shared by the tool
and the test.

**When to re-record.** Re-record with `uv run python tools/golden.py
--update` only when a wave *intends* to change rendered output — a page's
content, a component's rendering, the shell chrome — and re-record the
whole set in the same commit, never a single file by hand: the left rail
carries every page's label and the header names the current page, so adding
one page moves all of them. A diff in a wave that did not mean to change
rendering is a bug report, not a re-record.
