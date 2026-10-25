# Golden frames

`topics/<section>--<topic>.txt` holds one demo topic's
`python -m motui --pages` frame — the topic header rule plus the plain-text
screen, rendered on a `HeadlessScreen` at the replay's own geometry
(`motui.demo.script.HEADLESS_W/H`), LF line endings, one trailing newline.
`uv run python tools/golden.py --check` asserts these files byte for byte
and is the one gate that keeps them honest; it is green when nothing a user
sees moved. The one accepted other spelling is the exact `LF -> CRLF`
conversion a Windows checkout makes (`core.autocrlf`; this tree carries no
line-ending attributes on purpose) — `golden.matches` is that rule.

**When to re-record.** Re-record with `uv run python tools/golden.py
--update` only when a wave *intends* to change rendered output — a topic's
content, a component's rendering, the shell chrome — and re-record the
whole set in the same commit, never a single file by hand: the header
carries the section menu and the theme name, so a shell change moves every
file. A diff in a wave that did not mean to change rendering is a bug
report, not a re-record.

The file count is the registry's: one file per `motui.demo.registry.TOPICS`
entry, named `<topic.section>--<topic.key>.txt`. The old `pages/` directory
belonged to the retired Page/Exhibit demo and is gone.

## Semantic frames

`semantic/<section>--<topic>.txt` describes the same frame from the
terminal's side. The topic is painted through the same path as the byte
golden (`HeadlessScreen`, `show_topic(toast=False)`, one `paint`) and the
recorded bytes are fed to `motui.testing.Emulator`, which rebuilds the cell
grid. Each file is:

```
# <section>/<key> <width>x<height> cursor=<x>,<y>
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
moved focus/anchor shows up even when no glyph does. Files are LF and end
with one newline; `semantic.matches` accepts only the exact `LF -> CRLF`
checkout conversion, as `golden.matches` does.

**Relationship to the byte golden.** The byte files pin every escape,
ordering included; the semantic files pin what a terminal shows (glyphs,
SGR state per cell, OSC 8 links, cursor). They are two views of one frame,
so a wave that moves rendering moves both and re-records both in one
commit. The byte set is scheduled for deletion in W5; the semantic set
stays as the contract that survives it.

**Re-recording.** `uv run python tools/semantic.py --update` rewrites the
whole set; `--check` (the CI step) compares it byte for byte and fails on a
missing, extra or changed file. `--snapshot DIR` points either mode at
another directory (tests use a temporary one). When a check fails, classify
the diff before re-recording: **text** (glyphs moved), **style-only** (same
text, different SGR runs), **link** (a run's `:L...` changed) or **cursor**
(the header anchor moved without any cell changing). A re-record is only
correct for an intended change; an unintended diff in one class is a bug
report, not an update.

## W2.5b default changes

W2.5b moved two component defaults without moving a single recorded frame:

| Default | Before | After |
|---|---|---|
| Markdown code rows | cut with `…` (ELLIPSIS) | `code_wrap=WrapMode.WORD` (long lines wrap) |
| Input rows | wrap at the field width (ELLIPSIS guard) | `wrap=WrapMode.OVERFLOW` (one row, horizontal follow) |

Both sets were re-recorded with `tools/golden.py --update` and
`tools/semantic.py --update`: **0 of 57 byte files and 0 of 57 semantic files
changed**. The demo frames exercise neither default with an over-wide value:
every fenced code line in demo content fits the 85-column preview pane (the
longest, in `fixture.md`, is 68 columns), and every demo `Input` value fits
its field, so the old and new policies paint the same cells. The moved
behavior is pinned by unit tests instead: `tests/widgets/test_markdown.py`
renders a 200-character code line across rows, and
`tests/widgets/test_editing.py` pins the one-row Input, its horizontal window
and the end-of-row cursor.

The diff classification for this wave is therefore empty -- **no
`code-block` rows, no `input-single-line` rows**. A later topic that feeds an
over-wide code line or input value through the demo should move exactly those
two classes and nothing else.

