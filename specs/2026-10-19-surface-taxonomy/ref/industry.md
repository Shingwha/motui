# Verified industry reference — the surface taxonomy

Every fact below was checked against official documentation on 2026-10-19 while this
spec group was written. The tickets cite these sections; do not re-research.

## §1 — Textual: the band vocabulary (design tokens)

Source: <https://textual.textualize.io/guide/design/>

- `$surface` — "the default widget background", layered on `$background` (the screen).
- `$panel` — used sparingly to separate a region from the main content area.
- `$block-hover-background` — "background shown when hovering a block"; defaults to
  `$boost` at 5% opacity. This is a **background** token, not an attribute: a hover on
  a surfaced row changes the background, it does not reverse it.
- `$block-cursor-background` / `$block-cursor-foreground` / `$block-cursor-text-style`
  — the block cursor used by widgets like `OptionList`, **separate** from the hover
  token; plus `$block-cursor-blurred-*` for the unfocused state.
- `$input-cursor-background` / `$input-cursor-foreground` — the text caret, separate
  from the block cursor.
- `$input-selection-background` — selected text, its own token.
- `$border` / `$border-blurred` — the focused/unfocused border pair.

Reading for motui: the resting surface, the row cursor and the pointer hover are
**three distinct tokens** in the reference implementation, and the caret is distinct
from both. motui ships `ground` + `ground_active` (D2: cursor and hover share the
second token today) and splits `caret` out of the old `cursor`.

## §2 — Rich: the padding-with-style rule

Source: <https://rich.readthedocs.io/en/latest/padding.html>

`Padding("Hello", (2, 4), style="on blue")` — the `style` argument "applies a style to
the padding **and** contents". The style is the surface *underneath*: content colors
ride on top, the pad cells carry the style.

This is exactly `Line.fill(width, style)`'s merge direction: `style.merge(seg.style)`
— the style is the base, the segment's own colors win where it has them.

## §3 — Textual: `Select` — no per-option style

Source: <https://textual.textualize.io/widgets/select/>

Options are `Iterable[tuple[RenderableType, SelectType]]`: the label slot accepts any
Rich renderable (so per-item *richness* is possible), the value slot is plain data.
Styling the dropdown is done through CSS on the widget as a whole; the page states
the widget "has no component classes" and documents no per-option style hook.

Decision D4 follows: per-item richness belongs in the label slot, never a `style`
field on the option data.

## §4 — Textual: `max-width` and `height: auto`

Sources: <https://textual.textualize.io/styles/max_width/>,
<https://textual.textualize.io/styles/height/>

- `max-width: <scalar>` — "a maximum width for a widget"; numbers, percentages, `h`/
  `vw` units. There is a `min-width` counterpart.
- `height: <scalar>` — accepts `auto` ("the optimal size that fits the content
  without scrolling"), integer cell counts, percentages, `fr` fractions and relative
  units.

`Markdown(max_width=…)` (D6) and the future `Split` natural-size constraint both have
their precedent here.

## §5 — urwid: the wrapper/delegate tradition

Source: <https://urwid.org/reference/widget.html>

- `AttrMap(w, attr_map, focus_map=None)` — "A decoration that maps one set of display
  attributes to another". It wraps `w` (kept as `self.original_widget`), maps the
  resting attribute (`attr_map`) and the focused one (`focus_map`, defaulting to the
  resting map), and "will pass all function calls and variable references to the
  wrapped widget" — render and input both delegate.
- `Padding(w, align=…, width=…, min_width=…, left=…, right=…)` — layout only; it has
  **no** fill-attribute parameter (the attribute comes from wrapping it in an
  `AttrMap`). So the "pad cells with a style" primitive has no urwid precedent; Rich's
  `Padding(style=…)` (§2) is the one motui follows.
- `Pile`/`Columns` item forms seen in the reference: `('pack', widget)` — "try to pack
  self.original_widget to its ideal size" — beside the weight/given forms. `pack` is
  the natural-size precedent for the future `Split` constraint.

Decision D5 follows: `Delegate` is motui's `AttrMap` — a single-child wrapper that
forwards the protocol surfaces.

## §6 — ratatui: the constraint enum (and what it lacks)

Source: <https://docs.rs/ratatui/latest/ratatui/layout/enum.Constraint.html>

Six variants: `Min(u16)`, `Max(u16)`, `Length(u16)`, `Percentage(u16)`,
`Ratio(u32, u32)`, `Fill(u16)`. There is **no** content/natural-size variant — the
reference Rust toolkit leaves measuring to the application.

Industry is split on content sizing (Textual and urwid have it, ratatui does not).
motui follows Textual/urwid because `Viewport.natural_height` already exists — but the
next wave ships only the constraint kinds motui needs (`Weight`, `Natural`), not
ratatui's full enum.

## §7 — Textual's widget gallery: no Chip

Source: <https://textual.textualize.io/widget_gallery/>

The gallery lists: Button, Checkbox, Collapsible, ContentSwitcher, DataTable, Digits,
DirectoryTree, Footer, Header, Input, Label, Link, ListView, LoadingIndicator, Log,
MarkdownViewer, Markdown, MaskedInput, OptionList, Placeholder, Pretty, ProgressBar,
RadioButton, RadioSet, RichLog, Rule, Select, SelectionList, Sparkline, Static,
Switch, Tabs, TabbedContent, TextArea, Tree. There is **no** Chip, Pill, Badge or Tag.

The industry expression of a "chip" is a styled Label/span (a background plus
padding in CSS). motui's equivalent is a `StatusLine` element carrying a `ground`
style — no new component family ships.
