# API

> **Generated** by [`tools/apidoc.py`](../tools/apidoc.py): `uv run python
> tools/apidoc.py --check` (the same assertion as `tests/test_api_doc.py`)
> fails when this page drifts from the code.  Do not edit it by hand.

Every facade -- the package root and each layer's `__init__` -- and every
name in its `__all__`, in the facade's own curated order: the name, its
signature where it is callable (a class's is its constructor's), the first
paragraph of its docstring where it has one of its own, and the module that
defines it.

## mocode_tui

### ACCENT

```python
ACCENT: Style
```

*defined in* `mocode_tui.core.style`

### DEFAULT_EDITOR_KEYMAP

```python
DEFAULT_EDITOR_KEYMAP: dict
```

*defined in* `mocode_tui.keys.keymap`

### DEFAULT_INPUT_KEYMAP

```python
DEFAULT_INPUT_KEYMAP: dict
```

*defined in* `mocode_tui.keys.keymap`

### DEFAULT_THEME

```python
DEFAULT_THEME: Theme
```

*defined in* `mocode_tui.core.theme`

### DIM

```python
DIM: Style
```

*defined in* `mocode_tui.core.style`

### EDITOR_SUBMIT_KEYMAP

```python
EDITOR_SUBMIT_KEYMAP: dict
```

*defined in* `mocode_tui.keys.keymap`

### ERROR

```python
ERROR: Style
```

*defined in* `mocode_tui.core.style`

### MUTED

```python
MUTED: Style
```

*defined in* `mocode_tui.core.style`

### SUCCESS

```python
SUCCESS: Style
```

*defined in* `mocode_tui.core.style`

### WARNING

```python
WARNING: Style
```

*defined in* `mocode_tui.core.style`

### Autocomplete

```python
Autocomplete(*, options: Sequence[Option] = (), max_rows: int | None = 8, wrap: bool = True, label_style: Style | None = None, selected_style: Style | None = None, description_style: Style | None = None, theme: Theme | None = None)
```

A ``Select`` whose rows are the matches of :attr:`query`.

*defined in* `mocode_tui.widgets.autocomplete`

### Block

```python
Block(id: str, component: Component, *, pin: str | None = None)
```

One addressable row-producing unit inside a :class:`Document`.

*defined in* `mocode_tui.core.block`

### Button

```python
Button(label: str, *, style: Style | None = None, hover_style: Style | None = None, focus_style: Style | None = None, theme: Theme | None = None, focused: bool = False)
```

A one-row action: a label a click or an activation takes.

*defined in* `mocode_tui.widgets.button`

### Checkbox

```python
Checkbox(label: str, *, checked: bool = False, theme: Theme | None = None, focused: bool = False)
```

A one-row checked/unchecked toggle with a ``[x]`` / ``[ ]`` mark.

*defined in* `mocode_tui.widgets.checkbox`

### Collapsible

```python
Collapsible(title: str, body: Component, *, open: bool = True, title_style: Style | None = None, hover_style: Style | None = None, focus_style: Style | None = None, theme: Theme | None = None, focused: bool = False)
```

A titled section whose body folds away under its title row.

*defined in* `mocode_tui.widgets.collapsible`

### Column

```python
Column(children, *, gap: int = 0)
```

Children stacked vertically, ``gap`` blank rows between them.

*defined in* `mocode_tui.widgets.layout`

### Component

```python
Component(*args, **kwargs)
```

Anything that renders itself into rows: ``render(width) -> list[Line]``.

*defined in* `mocode_tui.core.block`

### Confirm

```python
Confirm(message: str, *, danger: bool = False, theme: Theme | None = None)
```

A Yes/No :class:`Select` specialization for confirmations.

*defined in* `mocode_tui.widgets.choice`

### Diff

```python
Diff(before: str, after: str, *, context: int = 3, theme: Theme | None = None)
```

A line-level unified diff of two texts, computed once at construction.

*defined in* `mocode_tui.widgets.diff`

### Divider

```python
Divider(*, char: str = '─', style: Style | None = None, label: str = '', label_style: Style | None = None, theme: Theme | None = None, max_width: int | None = None)
```

A horizontal rule built from one repeated character.

*defined in* `mocode_tui.widgets.decor`

### Editor

```python
Editor(*, text: str = '', placeholder: str = '', style: Style | None = None, cursor_style: Style | None = None, theme: Theme | None = None, keymap: Keymap | None = None, focused: bool = True, max_rows: int | None = None)
```

A multi-line text buffer with a reverse-video block cursor.

*defined in* `mocode_tui.widgets.editor`

### EveryHandle

```python
EveryHandle()
```

Cancellable handle returned by :meth:`TUI.every`.

*defined in* `mocode_tui.app`

### Find

```python
Find(tui: TUI, *, theme: Theme | None = None)
```

A self-contained search: one query row, its matches, and the overlay.

*defined in* `mocode_tui.search`

### FocusRing

```python
FocusRing(targets: Sequence[Component] = (), *, wrap: bool = True)
```

The focus tier: who is focused, how it cycles, where events go.

*defined in* `mocode_tui.focus`

### HeadlessScreen

```python
HeadlessScreen(width: int = 80, height: int = 24, *, mouse: bool = True, paste: bool = True, hover: bool = False, focus_events: bool = False, color_mode: ColorMode = 'truecolor')
```

An in-memory screen that records every byte written to it.

*defined in* `mocode_tui.core.screen`

### Hit

```python
Hit(block: Block, row: int, col: int, pane_id: str)
```

One hit-test result: the block under the cell, and the cell in it.

*defined in* `mocode_tui.app`

### Input

```python
Input(*, prompt: str = '❮ ', placeholder: str = '', style: Style | None = None, prompt_style: Style | None = None, cursor_style: Style | None = None, focused: bool = True, theme: Theme | None = None, keymap: Keymap | None = None)
```

A prompt-led text field with a reverse-video block cursor.

*defined in* `mocode_tui.widgets.input`

### Key

```python
Key(name: str, char: str = '')
```

One key press.

*defined in* `mocode_tui.core.events`

### Line

```python
Line(segments: Iterable[Segment] = ())
```

One immutable visual row made of styled :class:`Segment` values.

*defined in* `mocode_tui.core.lines`

### Link

```python
Link(text: str, *, style: Style | None = None, hover_style: Style | None = None, theme: Theme | None = None)
```

A one-row clickable text, rendered in the theme's ``link`` band.

*defined in* `mocode_tui.widgets.link`

### List

```python
List(items: Sequence[str] = (), *, window: int = 8, theme: Theme | None = None, focused: bool = False, prefix_jump: bool = True)
```

A cursor over ``items``, rendered as a ``window``-row view.

*defined in* `mocode_tui.widgets.list`

### Markdown

```python
Markdown(text: str = '', *, block_rules: Sequence[BlockRule] | None = None, inline_rules: Sequence[InlineRule] | None = None, theme: Theme | None = None, highlighter: Highlighter | None = None, gap: int = 1, divider_max_width: int | None = 80)
```

A Markdown document rendered as rows, rule-registry driven.

*defined in* `mocode_tui.widgets.markdown.component`

### MouseEvent

```python
MouseEvent(name: str, char: str = '', button: int = 0, x: int = 0, y: int = 0, kind: str = 'press')
```

A mouse report: a routable :class:`Key` name plus the report's data.

*defined in* `mocode_tui.core.events`

### Notice

```python
Notice(text: str, *, level: str = 'info', theme: Theme | None = None)
```

A one-row message with an optional level prefix.

*defined in* `mocode_tui.widgets.decor`

### Option

```python
Option(label: str, value: object = None, description: str = '')
```

One selectable entry: a label, a payload, and an optional description.

*defined in* `mocode_tui.widgets.choice`

### Padding

```python
Padding(child, *, left: int = 0, right: int = 0, top: int = 0, bottom: int = 0, fill_style: Style | None = None)
```

Whitespace around a child component.

*defined in* `mocode_tui.widgets.layout`

### Palette

```python
Palette(commands: list[Option], *, theme: Theme | None = None, max_rows: int = 8)
```

A command palette: an input row over a filtered command list.

*defined in* `mocode_tui.widgets.palette`

### Pane

```python
Pane(id: str, rect: Rect, viewport: Viewport, chrome: tuple = (), division: 'Split | None' = None, children: tuple['Pane', ...] = (), _frame: 'Frame | None' = None, _negotiation: 'tuple[Rect, tuple, Rect, tuple] | None' = None)
```

One pane of a frame: its rectangle and the viewport laid out inside it.

*defined in* `mocode_tui.core.frame`

### Panel

```python
Panel(child, *, title: str = '', style: Style | None = None, theme: Theme | None = None)
```

A child component inside a single-line box border.

*defined in* `mocode_tui.widgets.decor`

### Paste

```python
Paste(text: str)
```

A bracketed-paste payload: literal text, never re-interpreted.

*defined in* `mocode_tui.core.events`

### Pointer

```python
Pointer(tui: TUI, *, ring: FocusRing | None = None, hover: bool = True)
```

The pointer tier: what the pointer hovers, and what a click lands on.

*defined in* `mocode_tui.pointer`

### ProgressBar

```python
ProgressBar(fraction: float = 0.0, *, label: str = '', width_chars: int | None = None, done_style: Style | None = None, todo_style: Style | None = None, theme: Theme | None = None)
```

A determinate progress bar: label, ``[``, filled blocks, ``]``.

*defined in* `mocode_tui.widgets.progress`

### Radio

```python
Radio(labels: Sequence[str | Option], *, index: int = 0, label_style: Style | None = None, selected_style: Style | None = None, hover_style: Style | None = None, focus_style: Style | None = None, theme: Theme | None = None, focused: bool = False)
```

A vertical single-choice group with one ``(•)`` selection.

*defined in* `mocode_tui.widgets.radio`

### Row

```python
Row(children, *, widths: list[int | None] | None = None, gap: int = 1)
```

Children laid out side by side in aligned columns.

*defined in* `mocode_tui.widgets.layout`

### ScriptedKeys

```python
ScriptedKeys(events: Iterable[Key | Paste | None] = ())
```

A key source that replays a fixed sequence of events, then EOFs.

*defined in* `mocode_tui.core.events`

### Scrollbar

```python
Scrollbar(tui: TUI, *, pane: str | None = None, size: int = 1, min_thumb: int = 1, style: Style | None = None, thumb_style: Style | None = None, theme: Theme | None = None, scroll_tick: float = 0.05)
```

A right-edge scrollbar chrome: a budgeted strip that maps the scroll.

*defined in* `mocode_tui.chrome`

### Segment

```python
Segment(text: str, style: Style = Style(...), link: str | None = None, action: str | None = None)
```

A styled run of text. Segments are frozen and hashable.

*defined in* `mocode_tui.core.lines`

### Select

```python
Select(options: Sequence[Option] = (), *, title: str = '', max_rows: int | None = 8, wrap: bool = True, marker: str = '→', focused: bool = True, label_style: Style | None = None, selected_style: Style | None = None, description_style: Style | None = None, title_style: Style | None = None, theme: Theme | None = None)
```

A vertical :class:`Option` list with a cursor, a window and a counter.

*defined in* `mocode_tui.widgets.choice`

### Selection

```python
Selection(anchor: SelectionAnchor, head: SelectionAnchor)
```

A range of document addresses, carried as the ``(anchor, head)`` pair.

*defined in* `mocode_tui.core.selection`

### SelectionGesture

```python
SelectionGesture(tui: TUI, *, on_end: _OnEnd = copy_on_select, scroll_rows: int = 2, scroll_tick: float = 0.05, double_click_seconds: float = 0.35)
```

Mouse selection policy over the block document: anchor, drag, end.

*defined in* `mocode_tui.gesture`

### ShortcutBar

```python
ShortcutBar(items: Sequence[tuple[str, str]], *, separator: str = ' · ', key_style: Style | None = None, label_style: Style | None = None, theme: Theme | None = None)
```

One row of ``(key, label)`` hints, truncated to the painting width.

*defined in* `mocode_tui.widgets.shortcutbar`

### Slider

```python
Slider(value: int = 0, *, minimum: int = 0, maximum: int = 10, step: int = 1, filled_style: Style | None = None, empty_style: Style | None = None, hover_style: Style | None = None, focus_style: Style | None = None, theme: Theme | None = None, focused: bool = False)
```

A one-row ``[====----] value`` control over a stepped integer range.

*defined in* `mocode_tui.widgets.slider`

### Spacer

```python
Spacer(rows: int = 1)
```

``rows`` blank rows: vertical whitespace as a first-class component.

*defined in* `mocode_tui.widgets.layout`

### Spinner

```python
Spinner(text: str = '', *, frames: tuple[str, ...] | None = None)
```

A frame-cycling activity indicator with an optional label.

*defined in* `mocode_tui.widgets.spinner`

### Stats

```python
Stats(tui: TUI, *, pointer: Pointer | None = None, theme: Theme | None = None)
```

The dev overlay: frames, the frame rate, events, the last key, the hover.

*defined in* `mocode_tui.chrome`

### StatusLine

```python
StatusLine(*, left=(), right=(), theme: Theme | None = None, gap_style: Style | None = None)
```

A dim two-sided status row: left text, right text, gutter between.

*defined in* `mocode_tui.widgets.statusline`

### Style

```python
Style(fg: 'str | tuple[int, int, int] | None' = None, bg: 'str | tuple[int, int, int] | None' = None, bold: bool = False, dim: bool = False, italic: bool = False, underline: bool = False, reverse: bool = False, strike: bool = False)
```

An immutable terminal style.

*defined in* `mocode_tui.core.style`

### TUI

```python
TUI(*, screen: Screen | None = None, keys: KeySource | None = None, throttle: float = 0.03, interactive: bool | None = None, mouse: bool = True, hover: bool = False, focus_events: bool = False, sync: bool = True, color_mode: ColorMode | None = None, focus_policy: Callable[['TUI', Key | Paste], Pane | None] = _press_focuses_a_pane, theme: Theme | None = None)
```

A full-screen application driver.

*defined in* `mocode_tui.app`

### Table

```python
Table(headers: Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment], rows: Iterable[Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment]], *, header_style: Style | None = None, first_column_style: Style | None = None, border_style: Style | None = None, selected_style: Style | None = None, aligns: Sequence[str] | None = None, focused: bool = True, theme: Theme | None = None)
```

A box-line table of string, styled, or multi-segment cells.

*defined in* `mocode_tui.widgets.table`

### Tabs

```python
Tabs(tabs: list[str], *, active: int = 0, active_style: Style | None = None, inactive_style: Style | None = None, divider: str = '│', focused: bool = True, theme: Theme | None = None)
```

A horizontal tab strip with a clamped, non-wrapping selection.

*defined in* `mocode_tui.widgets.tabs`

### Text

```python
Text(text: str = '', *, style: Style | None = None, theme: Theme | None = None)
```

A block of plain text rendered verbatim, line by line.

*defined in* `mocode_tui.core.lines`

### Theme

```python
Theme(dim: Style = Style(...), muted: Style = Style(...), accent: Style = Style(...), success: Style = Style(...), error: Style = Style(...), warning: Style = Style(...), border: Style = Style(...), code: Style = Style(...), cursor: Style = Style(...), selection: Style = Style(...), heading: Style = Style(...), link: Style = Style(...), inline_code: Style = Style(...), list_marker: Style = Style(...), hover: Style = Style(...), table_border: Style = Style(...), first_column: Style = Style(...), scrollbar: Style = Style(...), scrollbar_thumb: Style = Style(...), toast: Style = Style(...))
```

Every semantic style the toolkit renders with, in one frozen value.

*defined in* `mocode_tui.core.theme`

### Toasts

```python
Toasts(tui: TUI, *, ttl: float = 4.0, max_shown: int = 3, corner: str = 'top-right', style: Style | None = None, theme: Theme | None = None)
```

A corner-anchored stack of transient toasts over the composed frame.

*defined in* `mocode_tui.chrome`

### Tooltip

```python
Tooltip(tui: TUI, pointer: Pointer, *, theme: Theme | None = None)
```

A one-row hint band beside the pointer, driven by the leaf's ``hint``.

*defined in* `mocode_tui.chrome`

### Tree

```python
Tree(root_nodes, *, indent: int = 2, guide_style: Style | None = None, label_style: Style | None = None, cursor_style: Style | None = None, focused: bool = True, theme: Theme | None = None)
```

An indented node list with a cursor and per-node expand/collapse.

*defined in* `mocode_tui.widgets.tree`

### TreeNode

```python
TreeNode(label: str, children=(), *, expanded: bool = False)
```

One tree node: a label, child nodes, and an ``expanded`` flag.

*defined in* `mocode_tui.widgets.tree`

### copy_on_select

```python
copy_on_select(tui: TUI, selection: Selection) -> bool
```

The shipped ``on_end`` default: extract the range and OSC 52 it (D6).

*defined in* `mocode_tui.gesture`

### extract

```python
extract(document: Document, selection: Selection | None, *, width: int) -> str
```

The plain text of ``selection`` over ``document``, rows joined by ``"\n"``.

*defined in* `mocode_tui.core.selection`

### headless_tui

```python
headless_tui(width: int = 80, height: int = 24, *, script: Iterable[Key | Paste | None] | None = None, keys: KeySource | None = None) -> TUI
```

A TUI wired for tests: recording screen, scripted keys, no terminal.

*defined in* `mocode_tui.testing`

### highlight

```python
highlight(layout: ScreenLayout, selection: Selection | None) -> ScreenLayout
```

The selection overlay (D2): one pure pass over a laid-out frame.

*defined in* `mocode_tui.core.selection`

### snapshot

```python
snapshot(tui: TUI) -> str
```

A structured plain-text view of the document: one stanza per block.

*defined in* `mocode_tui.testing`

### visible_width

```python
visible_width(text: str) -> int
```

Display width of ``text`` in terminal columns, measured by grapheme cluster -- the toolkit's single source of truth for display width, built on ``wcwidth`` alone: the cluster rules are expressed with code points, so there is no second measure and no new runtime dependency.

*defined in* `mocode_tui.core.text`

### wrap_text

```python
wrap_text(text: str, width: int) -> list[str]
```

Word-aware wrap of ``text`` into rows of at most ``width`` columns.

*defined in* `mocode_tui.core.text`

## mocode_tui.core

### ACCENT

```python
ACCENT: Style
```

*defined in* `mocode_tui.core.style`

### BORDER

```python
BORDER: Style
```

*defined in* `mocode_tui.core.style`

### CLEAR_LINE

```python
CLEAR_LINE: str = '\x1b[K'
```

*defined in* `mocode_tui.core.ansi`

### CODE

```python
CODE: Style
```

*defined in* `mocode_tui.core.style`

### CURSOR

```python
CURSOR: Style
```

*defined in* `mocode_tui.core.style`

### DEFAULT_THEME

```python
DEFAULT_THEME: Theme
```

*defined in* `mocode_tui.core.theme`

### DIM

```python
DIM: Style
```

*defined in* `mocode_tui.core.style`

### ELLIPSIS

```python
ELLIPSIS: str = '…'
```

*defined in* `mocode_tui.core.text`

### ERROR

```python
ERROR: Style
```

*defined in* `mocode_tui.core.style`

### ESC

```python
ESC: str = '\x1b'
```

*defined in* `mocode_tui.core.ansi`

### FG_CODES

```python
FG_CODES: dict
```

*defined in* `mocode_tui.core.style`

### MORE_BELOW

```python
MORE_BELOW: Line
```

*defined in* `mocode_tui.core.viewport`

### MUTED

```python
MUTED: Style
```

*defined in* `mocode_tui.core.style`

### NONE

```python
NONE: Style
```

*defined in* `mocode_tui.core.style`

### RESET

```python
RESET: str = '\x1b[0m'
```

*defined in* `mocode_tui.core.style`

### SELECTION

```python
SELECTION: Style
```

*defined in* `mocode_tui.core.style`

### SUCCESS

```python
SUCCESS: Style
```

*defined in* `mocode_tui.core.style`

### WARNING

```python
WARNING: Style
```

*defined in* `mocode_tui.core.style`

### Activable

```python
Activable(*args, **kwargs)
```

A component that can execute the thing under its cursor.

*defined in* `mocode_tui.core.block`

### Block

```python
Block(id: str, component: Component, *, pin: str | None = None)
```

One addressable row-producing unit inside a :class:`Document`.

*defined in* `mocode_tui.core.block`

### BlockState

```python
BlockState(*values)
```

Lifecycle of a block: open (writable) or sealed (frozen). No COMMITTED.

*defined in* `mocode_tui.core.block`

### Clickable

```python
Clickable(*args, **kwargs)
```

A component that can consume a click on one of its own cells.

*defined in* `mocode_tui.core.block`

### Component

```python
Component(*args, **kwargs)
```

Anything that renders itself into rows: ``render(width) -> list[Line]``.

*defined in* `mocode_tui.core.block`

### Container

```python
Container(*args, **kwargs)
```

A component made of children, translating its own cells to a child's.

*defined in* `mocode_tui.core.block`

### Document

```python
Document()
```

An ordered collection of blocks, addressable by id.

*defined in* `mocode_tui.core.block`

### Focusable

```python
Focusable(*args, **kwargs)
```

The minimum a component declares to be focusable: ``focused: bool``.

*defined in* `mocode_tui.core.block`

### Frame

```python
Frame(panes: Iterable[Pane] = (), *, band: Pane | None = None)
```

A tiling of panes over one screen, composed into a painting target.

*defined in* `mocode_tui.core.frame`

### HeadlessScreen

```python
HeadlessScreen(width: int = 80, height: int = 24, *, mouse: bool = True, paste: bool = True, hover: bool = False, focus_events: bool = False, color_mode: ColorMode = 'truecolor')
```

An in-memory screen that records every byte written to it.

*defined in* `mocode_tui.core.screen`

### Hoverable

```python
Hoverable(*args, **kwargs)
```

A component that can be highlighted while the pointer is over it.

*defined in* `mocode_tui.core.block`

### Key

```python
Key(name: str, char: str = '')
```

One key press.

*defined in* `mocode_tui.core.events`

### KeySource

```python
KeySource(*args, **kwargs)
```

Anything that can hand out key events: ``async read() -> event | None``.

*defined in* `mocode_tui.core.events`

### Line

```python
Line(segments: Iterable[Segment] = ())
```

One immutable visual row made of styled :class:`Segment` values.

*defined in* `mocode_tui.core.lines`

### MouseEvent

```python
MouseEvent(name: str, char: str = '', button: int = 0, x: int = 0, y: int = 0, kind: str = 'press')
```

A mouse report: a routable :class:`Key` name plus the report's data.

*defined in* `mocode_tui.core.events`

### Painter

```python
Painter(screen: Screen, *, sync: bool = True)
```

Renders one laid-out frame onto a screen, one diffed frame at a time.

*defined in* `mocode_tui.core.painter`

### Pane

```python
Pane(id: str, rect: Rect, viewport: Viewport, chrome: tuple = (), division: 'Split | None' = None, children: tuple['Pane', ...] = (), _frame: 'Frame | None' = None, _negotiation: 'tuple[Rect, tuple, Rect, tuple] | None' = None)
```

One pane of a frame: its rectangle and the viewport laid out inside it.

*defined in* `mocode_tui.core.frame`

### Paste

```python
Paste(text: str)
```

A bracketed-paste payload: literal text, never re-interpreted.

*defined in* `mocode_tui.core.events`

### Rect

```python
Rect(x: int, y: int, width: int, height: int)
```

One rectangle of the screen: a 0-based origin and a size in cells.

*defined in* `mocode_tui.core.frame`

### Screen

```python
Screen(*args, **kwargs)
```

A writable screen surface with a known size.

*defined in* `mocode_tui.core.screen`

### ScreenLayout

```python
ScreenLayout(rows: list[Line], viewport_rows: list[Line], row_blocks: list[tuple[str, int] | None] = <factory>, block_order: tuple[str, ...] = (), offset: int = 0, total_rows: int = 0)
```

One screen's worth of rows.

*defined in* `mocode_tui.core.viewport`

### ScriptedKeys

```python
ScriptedKeys(events: Iterable[Key | Paste | None] = ())
```

A key source that replays a fixed sequence of events, then EOFs.

*defined in* `mocode_tui.core.events`

### Segment

```python
Segment(text: str, style: Style = Style(...), link: str | None = None, action: str | None = None)
```

A styled run of text. Segments are frozen and hashable.

*defined in* `mocode_tui.core.lines`

### Selection

```python
Selection(anchor: SelectionAnchor, head: SelectionAnchor)
```

A range of document addresses, carried as the ``(anchor, head)`` pair.

*defined in* `mocode_tui.core.selection`

### Style

```python
Style(fg: 'str | tuple[int, int, int] | None' = None, bg: 'str | tuple[int, int, int] | None' = None, bold: bool = False, dim: bool = False, italic: bool = False, underline: bool = False, reverse: bool = False, strike: bool = False)
```

An immutable terminal style.

*defined in* `mocode_tui.core.style`

### TerminalScreen

```python
TerminalScreen(stream: io.TextIOBase | None = None, *, mouse: bool = True, paste: bool = True, hover: bool = False, focus_events: bool = False, color_mode: "ColorMode | Literal['auto']" = 'auto')
```

A screen backed by a real stream (``sys.stdout`` by default).

*defined in* `mocode_tui.core.screen`

### Text

```python
Text(text: str = '', *, style: Style | None = None, theme: Theme | None = None)
```

A block of plain text rendered verbatim, line by line.

*defined in* `mocode_tui.core.lines`

### Theme

```python
Theme(dim: Style = Style(...), muted: Style = Style(...), accent: Style = Style(...), success: Style = Style(...), error: Style = Style(...), warning: Style = Style(...), border: Style = Style(...), code: Style = Style(...), cursor: Style = Style(...), selection: Style = Style(...), heading: Style = Style(...), link: Style = Style(...), inline_code: Style = Style(...), list_marker: Style = Style(...), hover: Style = Style(...), table_border: Style = Style(...), first_column: Style = Style(...), scrollbar: Style = Style(...), scrollbar_thumb: Style = Style(...), toast: Style = Style(...))
```

Every semantic style the toolkit renders with, in one frozen value.

*defined in* `mocode_tui.core.theme`

### Viewport

```python
Viewport(document: Document)
```

Scroll state over a document: window offset, sealed-row cache, ownership.

*defined in* `mocode_tui.core.viewport`

### action_at

```python
action_at(line: Line, col: int) -> tuple[str, int, int] | None
```

The inline action under column ``col``: ``(action, start, end)`` or ``None``.

*defined in* `mocode_tui.core.lines`

### clear_screen

```python
clear_screen() -> str
```

Erase the whole screen.

*defined in* `mocode_tui.core.ansi`

### cursor_position

```python
cursor_position(row: int, col: int) -> str
```

Move the cursor to 1-based ``(row, col)``; the top-left corner is 1;1.

*defined in* `mocode_tui.core.ansi`

### descend

```python
descend(component: Component, row: int, col: int) -> 'tuple[Component, int, int]'
```

The deepest component owning a cell, with that component's own coords.

*defined in* `mocode_tui.core.block`

### disable_mouse_tracking

```python
disable_mouse_tracking(*, hover: bool = False) -> str
```

Stop mouse reporting: disable 1006 + 1003 + 1002 + 1000, in that order.

*defined in* `mocode_tui.core.ansi`

### ellipsize_tail

```python
ellipsize_tail(text: str, width: int) -> str
```

Truncate ``text`` to ``width`` columns, marking the cut with ``…`` at the end.

*defined in* `mocode_tui.core.text`

### enable_mouse_tracking

```python
enable_mouse_tracking(*, hover: bool = False) -> str
```

Ask the terminal to report mouse input: 1000 + (1003|1002) + SGR 1006.

*defined in* `mocode_tui.core.ansi`

### enable_vt

```python
enable_vt() -> bool
```

Best-effort Windows virtual-terminal enablement.

*defined in* `mocode_tui.core.ansi`

### enter_alt_screen

```python
enter_alt_screen() -> str
```

Switch to the alternate screen buffer (vim/htop-style full screen).

*defined in* `mocode_tui.core.ansi`

### extract

```python
extract(document: Document, selection: Selection | None, *, width: int) -> str
```

The plain text of ``selection`` over ``document``, rows joined by ``"\n"``.

*defined in* `mocode_tui.core.selection`

### hide_cursor

```python
hide_cursor() -> str
```

*defined in* `mocode_tui.core.ansi`

### highlight

```python
highlight(layout: ScreenLayout, selection: Selection | None) -> ScreenLayout
```

The selection overlay (D2): one pure pass over a laid-out frame.

*defined in* `mocode_tui.core.selection`

### leave_alt_screen

```python
leave_alt_screen() -> str
```

Restore the primary screen buffer.

*defined in* `mocode_tui.core.ansi`

### show_cursor

```python
show_cursor() -> str
```

*defined in* `mocode_tui.core.ansi`

### terminal_size

```python
terminal_size() -> tuple[int, int]
```

Current terminal size as ``(columns, rows)``, falling back to 80x24.

*defined in* `mocode_tui.core.text`

### visible_width

```python
visible_width(text: str) -> int
```

Display width of ``text`` in terminal columns, measured by grapheme cluster -- the toolkit's single source of truth for display width, built on ``wcwidth`` alone: the cluster rules are expressed with code points, so there is no second measure and no new runtime dependency.

*defined in* `mocode_tui.core.text`

### wrap_line

```python
wrap_line(line: Line, width: int) -> list[Line]
```

Word-aware wrap of ``line`` into rows of at most ``width`` columns.

*defined in* `mocode_tui.core.lines`

### wrap_text

```python
wrap_text(text: str, width: int) -> list[str]
```

Word-aware wrap of ``text`` into rows of at most ``width`` columns.

*defined in* `mocode_tui.core.text`

## mocode_tui.keys

### DEFAULT_EDITOR_KEYMAP

```python
DEFAULT_EDITOR_KEYMAP: dict
```

*defined in* `mocode_tui.keys.keymap`

### DEFAULT_INPUT_KEYMAP

```python
DEFAULT_INPUT_KEYMAP: dict
```

*defined in* `mocode_tui.keys.keymap`

### EDITOR_SUBMIT_KEYMAP

```python
EDITOR_SUBMIT_KEYMAP: dict
```

*defined in* `mocode_tui.keys.keymap`

### KeyDecoder

```python
KeyDecoder()
```

Turns a raw byte stream into :class:`Key` / :class:`Paste` events.

*defined in* `mocode_tui.keys.decoder`

### Keymap

```python
Keymap(*args, **kwargs)
```

*defined in* `mocode_tui.keys.keymap`

### RawTerminalKeys

```python
RawTerminalKeys(fd: int | None = None, *, hover: bool = False)
```

A key source reading a real terminal in (near) raw mode.

*defined in* `mocode_tui.keys.sources`

### RecordingKeys

```python
RecordingKeys(source: KeySource, path: str | Path, *, clock: Callable[[], float] | None = None)
```

A :class:`~mocode_tui.core.events.KeySource` that records what it serves.

*defined in* `mocode_tui.keys.recorder`

### ReplayKeys

```python
ReplayKeys(path: str | Path, *, speed: float = 1.0)
```

A key source that replays a :class:`RecordingKeys` file.

*defined in* `mocode_tui.keys.recorder`

## mocode_tui.widgets

### Autocomplete

```python
Autocomplete(*, options: Sequence[Option] = (), max_rows: int | None = 8, wrap: bool = True, label_style: Style | None = None, selected_style: Style | None = None, description_style: Style | None = None, theme: Theme | None = None)
```

A ``Select`` whose rows are the matches of :attr:`query`.

*defined in* `mocode_tui.widgets.autocomplete`

### Button

```python
Button(label: str, *, style: Style | None = None, hover_style: Style | None = None, focus_style: Style | None = None, theme: Theme | None = None, focused: bool = False)
```

A one-row action: a label a click or an activation takes.

*defined in* `mocode_tui.widgets.button`

### Checkbox

```python
Checkbox(label: str, *, checked: bool = False, theme: Theme | None = None, focused: bool = False)
```

A one-row checked/unchecked toggle with a ``[x]`` / ``[ ]`` mark.

*defined in* `mocode_tui.widgets.checkbox`

### Collapsible

```python
Collapsible(title: str, body: Component, *, open: bool = True, title_style: Style | None = None, hover_style: Style | None = None, focus_style: Style | None = None, theme: Theme | None = None, focused: bool = False)
```

A titled section whose body folds away under its title row.

*defined in* `mocode_tui.widgets.collapsible`

### Column

```python
Column(children, *, gap: int = 0)
```

Children stacked vertically, ``gap`` blank rows between them.

*defined in* `mocode_tui.widgets.layout`

### Confirm

```python
Confirm(message: str, *, danger: bool = False, theme: Theme | None = None)
```

A Yes/No :class:`Select` specialization for confirmations.

*defined in* `mocode_tui.widgets.choice`

### Diff

```python
Diff(before: str, after: str, *, context: int = 3, theme: Theme | None = None)
```

A line-level unified diff of two texts, computed once at construction.

*defined in* `mocode_tui.widgets.diff`

### Divider

```python
Divider(*, char: str = '─', style: Style | None = None, label: str = '', label_style: Style | None = None, theme: Theme | None = None, max_width: int | None = None)
```

A horizontal rule built from one repeated character.

*defined in* `mocode_tui.widgets.decor`

### Editor

```python
Editor(*, text: str = '', placeholder: str = '', style: Style | None = None, cursor_style: Style | None = None, theme: Theme | None = None, keymap: Keymap | None = None, focused: bool = True, max_rows: int | None = None)
```

A multi-line text buffer with a reverse-video block cursor.

*defined in* `mocode_tui.widgets.editor`

### Input

```python
Input(*, prompt: str = '❮ ', placeholder: str = '', style: Style | None = None, prompt_style: Style | None = None, cursor_style: Style | None = None, focused: bool = True, theme: Theme | None = None, keymap: Keymap | None = None)
```

A prompt-led text field with a reverse-video block cursor.

*defined in* `mocode_tui.widgets.input`

### Link

```python
Link(text: str, *, style: Style | None = None, hover_style: Style | None = None, theme: Theme | None = None)
```

A one-row clickable text, rendered in the theme's ``link`` band.

*defined in* `mocode_tui.widgets.link`

### List

```python
List(items: Sequence[str] = (), *, window: int = 8, theme: Theme | None = None, focused: bool = False, prefix_jump: bool = True)
```

A cursor over ``items``, rendered as a ``window``-row view.

*defined in* `mocode_tui.widgets.list`

### Markdown

```python
Markdown(text: str = '', *, block_rules: Sequence[BlockRule] | None = None, inline_rules: Sequence[InlineRule] | None = None, theme: Theme | None = None, highlighter: Highlighter | None = None, gap: int = 1, divider_max_width: int | None = 80)
```

A Markdown document rendered as rows, rule-registry driven.

*defined in* `mocode_tui.widgets.markdown.component`

### Notice

```python
Notice(text: str, *, level: str = 'info', theme: Theme | None = None)
```

A one-row message with an optional level prefix.

*defined in* `mocode_tui.widgets.decor`

### Option

```python
Option(label: str, value: object = None, description: str = '')
```

One selectable entry: a label, a payload, and an optional description.

*defined in* `mocode_tui.widgets.choice`

### Padding

```python
Padding(child, *, left: int = 0, right: int = 0, top: int = 0, bottom: int = 0, fill_style: Style | None = None)
```

Whitespace around a child component.

*defined in* `mocode_tui.widgets.layout`

### Palette

```python
Palette(commands: list[Option], *, theme: Theme | None = None, max_rows: int = 8)
```

A command palette: an input row over a filtered command list.

*defined in* `mocode_tui.widgets.palette`

### Panel

```python
Panel(child, *, title: str = '', style: Style | None = None, theme: Theme | None = None)
```

A child component inside a single-line box border.

*defined in* `mocode_tui.widgets.decor`

### ProgressBar

```python
ProgressBar(fraction: float = 0.0, *, label: str = '', width_chars: int | None = None, done_style: Style | None = None, todo_style: Style | None = None, theme: Theme | None = None)
```

A determinate progress bar: label, ``[``, filled blocks, ``]``.

*defined in* `mocode_tui.widgets.progress`

### Radio

```python
Radio(labels: Sequence[str | Option], *, index: int = 0, label_style: Style | None = None, selected_style: Style | None = None, hover_style: Style | None = None, focus_style: Style | None = None, theme: Theme | None = None, focused: bool = False)
```

A vertical single-choice group with one ``(•)`` selection.

*defined in* `mocode_tui.widgets.radio`

### Row

```python
Row(children, *, widths: list[int | None] | None = None, gap: int = 1)
```

Children laid out side by side in aligned columns.

*defined in* `mocode_tui.widgets.layout`

### Select

```python
Select(options: Sequence[Option] = (), *, title: str = '', max_rows: int | None = 8, wrap: bool = True, marker: str = '→', focused: bool = True, label_style: Style | None = None, selected_style: Style | None = None, description_style: Style | None = None, title_style: Style | None = None, theme: Theme | None = None)
```

A vertical :class:`Option` list with a cursor, a window and a counter.

*defined in* `mocode_tui.widgets.choice`

### ShortcutBar

```python
ShortcutBar(items: Sequence[tuple[str, str]], *, separator: str = ' · ', key_style: Style | None = None, label_style: Style | None = None, theme: Theme | None = None)
```

One row of ``(key, label)`` hints, truncated to the painting width.

*defined in* `mocode_tui.widgets.shortcutbar`

### Slider

```python
Slider(value: int = 0, *, minimum: int = 0, maximum: int = 10, step: int = 1, filled_style: Style | None = None, empty_style: Style | None = None, hover_style: Style | None = None, focus_style: Style | None = None, theme: Theme | None = None, focused: bool = False)
```

A one-row ``[====----] value`` control over a stepped integer range.

*defined in* `mocode_tui.widgets.slider`

### Spacer

```python
Spacer(rows: int = 1)
```

``rows`` blank rows: vertical whitespace as a first-class component.

*defined in* `mocode_tui.widgets.layout`

### Spinner

```python
Spinner(text: str = '', *, frames: tuple[str, ...] | None = None)
```

A frame-cycling activity indicator with an optional label.

*defined in* `mocode_tui.widgets.spinner`

### StatusLine

```python
StatusLine(*, left=(), right=(), theme: Theme | None = None, gap_style: Style | None = None)
```

A dim two-sided status row: left text, right text, gutter between.

*defined in* `mocode_tui.widgets.statusline`

### Table

```python
Table(headers: Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment], rows: Iterable[Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment]], *, header_style: Style | None = None, first_column_style: Style | None = None, border_style: Style | None = None, selected_style: Style | None = None, aligns: Sequence[str] | None = None, focused: bool = True, theme: Theme | None = None)
```

A box-line table of string, styled, or multi-segment cells.

*defined in* `mocode_tui.widgets.table`

### Tabs

```python
Tabs(tabs: list[str], *, active: int = 0, active_style: Style | None = None, inactive_style: Style | None = None, divider: str = '│', focused: bool = True, theme: Theme | None = None)
```

A horizontal tab strip with a clamped, non-wrapping selection.

*defined in* `mocode_tui.widgets.tabs`

### Text

```python
Text(text: str = '', *, style: Style | None = None, theme: Theme | None = None)
```

A block of plain text rendered verbatim, line by line.

*defined in* `mocode_tui.core.lines`

### Tree

```python
Tree(root_nodes, *, indent: int = 2, guide_style: Style | None = None, label_style: Style | None = None, cursor_style: Style | None = None, focused: bool = True, theme: Theme | None = None)
```

An indented node list with a cursor and per-node expand/collapse.

*defined in* `mocode_tui.widgets.tree`

### TreeNode

```python
TreeNode(label: str, children=(), *, expanded: bool = False)
```

One tree node: a label, child nodes, and an ``expanded`` flag.

*defined in* `mocode_tui.widgets.tree`

## mocode_tui.widgets.markdown

### BLOCK_RULES

```python
BLOCK_RULES: tuple
```

*defined in* `mocode_tui.widgets.markdown.component`

### INLINE_RULES

```python
INLINE_RULES: tuple
```

*defined in* `mocode_tui.widgets.markdown.inline`

### BoldInlineRule

```python
BoldInlineRule()
```

Strong emphasis: ``**content**`` (non-empty) merged bold onto base.

*defined in* `mocode_tui.widgets.markdown.inline`

### BlockRule

```python
BlockRule(*args, **kwargs)
```

One block-level construct: classify at the cursor, then render.

*defined in* `mocode_tui.widgets.markdown.blocks`

### CodeInlineRule

```python
CodeInlineRule()
```

Inline code: `` `content` `` (no nested backticks) in the theme's inline-code style.

*defined in* `mocode_tui.widgets.markdown.inline`

### FenceRule

```python
FenceRule()
```

Fenced code: ```` ``` ````-delimited lines, optional language tag.

*defined in* `mocode_tui.widgets.markdown.blocks`

### HeadingRule

```python
HeadingRule()
```

ATX heading: ``#``..``######`` + space, on the theme's heading ladder.

*defined in* `mocode_tui.widgets.markdown.blocks`

### InlineRule

```python
InlineRule(*args, **kwargs)
```

One inline construct: recognize at ``pos``, produce segments.

*defined in* `mocode_tui.widgets.markdown.inline`

### ItalicInlineRule

```python
ItalicInlineRule()
```

Emphasis: ``*content*`` on word boundaries (so ``2*3`` stays literal).

*defined in* `mocode_tui.widgets.markdown.inline`

### LinkInlineRule

```python
LinkInlineRule()
```

Link: ``[label](url)`` -- the label in the theme's link style (colored and underlined, never bold); the url is not rendered.

*defined in* `mocode_tui.widgets.markdown.inline`

### ListRule

```python
ListRule()
```

List: a run of ``-``/``*``/``N.`` items, markers kept verbatim.

*defined in* `mocode_tui.widgets.markdown.nested`

### Markdown

```python
Markdown(text: str = '', *, block_rules: Sequence[BlockRule] | None = None, inline_rules: Sequence[InlineRule] | None = None, theme: Theme | None = None, highlighter: Highlighter | None = None, gap: int = 1, divider_max_width: int | None = 80)
```

A Markdown document rendered as rows, rule-registry driven.

*defined in* `mocode_tui.widgets.markdown.component`

### ParagraphRule

```python
ParagraphRule()
```

The catch-all: soft-wrapped lines plus inline rules.

*defined in* `mocode_tui.widgets.markdown.blocks`

### QuoteRule

```python
QuoteRule()
```

Block quote: ``> `` lines re-run as blocks behind a muted ``│ `` bar.

*defined in* `mocode_tui.widgets.markdown.nested`

### RenderContext

```python
RenderContext(theme: Theme = Theme(...), highlighter: Highlighter | None = None, divider_max_width: int | None = 80, block_rules: Sequence[BlockRule] = (), inline_rules: Sequence[InlineRule] = ())
```

Everything a rule reads while rendering, frozen and shared.

*defined in* `mocode_tui.widgets.markdown.context`

### StrikeInlineRule

```python
StrikeInlineRule()
```

Strikethrough: ``~~content~~`` (non-empty) struck; unclosed stays literal, so a streaming prefix renders safely.

*defined in* `mocode_tui.widgets.markdown.inline`

### TableRule

```python
TableRule()
```

GFM pipe table: header row + delimiter row, aligned per column.

*defined in* `mocode_tui.widgets.markdown.tables`

### ThematicBreakRule

```python
ThematicBreakRule()
```

Thematic break: a standalone ``---`` / ``***`` line, as a Divider.

*defined in* `mocode_tui.widgets.markdown.blocks`

### default_block_rules

```python
default_block_rules() -> list[BlockRule]
```

A fresh built-in block registry, dep-free and in match order.

*defined in* `mocode_tui.widgets.markdown.component`

### default_inline_rules

```python
default_inline_rules() -> list[InlineRule]
```

A fresh built-in inline registry, dep-free and in match order.

*defined in* `mocode_tui.widgets.markdown.inline`

### inline_segments

```python
inline_segments(text: str, ctx: RenderContext, base: Style = Style(...)) -> list[Segment]
```

Split ``text`` into styled segments using ``ctx.inline_rules``.

*defined in* `mocode_tui.widgets.markdown.inline`
