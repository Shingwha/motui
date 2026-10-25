# Semantic golden frames

`semantic/<scene>.txt` records one showcase scene from the terminal's side.
The scene (`splash`, `menu`, `snake`, `dashboard`, `gallery`) is painted
by `motui.demo.scene_output` — a fresh headless runtime, `fill(Showcase)`
and one `paint` at `PAGE_PHASE` (20 ticks), with no event pump and no
clock — and the recorded bytes are fed to `motui.testing.Emulator`, which
rebuilds the cell grid. Each file is:

```
# <scene> <width>x<height> cursor=<x>,<y>
<row text>\t<runs>
...
```

one line per grid row. `row text` is the row's cells concatenated and
right-stripped (a double-width glyph's placeholder contributes nothing).
`runs` is the RLE of the columns whose style is not the default style:
inclusive zero-based `start-end:<sgrhex>[:L<link>]` pieces joined with `|`,
or `-` when the whole row is default. `sgrhex` is `Style.prefix()` encoded
as UTF-8 and hexed — the exact SGR bytes, independent of `repr` — and a
link is appended as its `repr` (quotes included); a link change breaks the
run. The header's cursor is the emulator's zero-based final position, so a
moved focus/anchor shows up even when no glyph does.

The byte golden (`tools/golden.py`, `topics/*.txt`) was deleted in C4a
together with the 57-topic tour. The showcase has five scenes, so the
semantic set has five files; there is no second byte-for-byte set to keep
in step. Phase 20 is the shared stable frame: the splash sweep is mid-word,
the snake has taken its first steps, and the dashboard has a streamed window.

**Re-recording.** `uv run python tools/semantic.py --update` rewrites the
whole set; `--check` (the CI step) compares it byte for byte and fails on a
missing, extra or changed file. `--snapshot DIR` points either mode at
another directory (tests use a temporary one). Files are LF and end with
one newline; `semantic.matches` accepts only the exact `LF -> CRLF`
checkout conversion (`core.autocrlf`; this tree carries no line-ending
attributes on purpose).

When a check fails, classify the diff before re-recording: **text** (glyphs
moved), **style-only** (same text, different SGR runs), **link** (a run's
`:L...` changed) or **cursor** (the header anchor moved without any cell
changing). A re-record is only correct for an intended change; an
unintended diff in one class is a bug report, not an update. Re-record the
whole set in one commit, never a single file by hand: a change to the
shared art, theme or scene chrome moves every scene.
