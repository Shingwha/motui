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
