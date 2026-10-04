# Components

A component is anything with `render(width) -> list[Line]`. That single protocol
— frozen since the first wave — is the whole contract.

## The protocol

- **`render(width)` returns rows.** One `Line` per visual row, each already
  wrapped and sized. A component never paints, scrolls, or touches a screen.
- **`width` is the full painting width** — on a real screen that is
  `screen.width`; a `Row`/`Column` child gets the width its parent gives it. The
  painter only counts rows; components own their own wrapping and truncation.
- **`Line`** is an immutable run of styled **`Segment`**s (`text` + `Style`), with
  `width` (display columns via wcwidth), `fit(width)` (truncate-with-ellipsis),
  and `pad_to(width)`. Style constants (`NONE`, `DIM`, `MUTED`, `ACCENT`,
  `SUCCESS`, `ERROR`, `WARNING`, `BORDER`, `CODE`, `CURSOR`, `SELECTION`) and the
  `Style` builder live in `mocode_tui.style` and are exported at the package root.
- **Sealing is a cache hint, not a render mode.** `BlockState` is `OPEN`/`SEALED`
  only — a sealed block renders once per width and is cached; an open block
  re-renders every frame. There is no "inline" or "committed" render mode; the
  same `render(width)` runs in both states.

Everything below is importable straight from `mocode_tui`.

## The palette

`Style(fg=..., bg=..., ...)` takes a color in one of three forms:

- a **named 16-color** from `style.FG_CODES` (`"red"`, `"bright_black"`, …);
  unknown names raise `KeyError` from `prefix()`;
- a **`"#rrggbb"` string** or an **`(r, g, b)` tuple** — both emit 24-bit
  truecolor SGR (`38;2;r;g;b` / `48;2;r;g;b`). Truecolor is a superset of
  the named set, so old named styles keep working unchanged.

The semantic constants (W11 GitHub-dark / pi-style soft set) are:

| Constant | Value | Used for |
|---|---|---|
| `BORDER` | `#3d444d` blue-gray | rules, panel borders |
| `ACCENT` | `#58a6ff` soft blue | prompts / emphasis / the working label |
| `MUTED` | `#8b949e` gray | secondary text (thinking, list markers) |
| `SUCCESS` | `#4bb563` soft green | success, `+` rows, ✓ |
| `ERROR` | `#e5534b` soft red | errors, `-` rows |
| `WARNING` | `#d29922` amber | warnings, notice titles |
| `CODE` | `#a5d6ff` ice blue | inline code |
| `Message.USER_BG` | `#1c2b3a` slate blue | the `user` band |
| `ToolBlock.TOOL_BG` | `#16281c` deep green | the `"tool"` tone band |
| `ToolBlock.CODE_BG` | `#12181f` near-black blue | the `"code"` tone / `EditBlock` band |
| `Table` first-column default | `#bc8cff` soft purple | data rows' first column |

`Style` is frozen and hashable, so `prefix()` is memoized per instance.

## Text & structure

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=NONE)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. |
| `Markdown` | `Markdown(text="", *, style=NONE)` | Subset: paragraphs, `#`–`####` headings, fenced code, lists, inline `` `code` ``/`**bold**`/`*italic*`; unknown constructs degrade to paragraph. |
| `Divider` | `Divider(*, char="─", style=BORDER, label="", label_style=NONE)` | Full-width rule from one repeated character; a `label` embeds `char*2 + " " + label + " " + char*fill` (e.g. `── ⠋ Working ───`) across the full width, an over-wide label is ellipsize'd to `width - 4`, and `label`/`label_style` are mutable attributes. |
| `Panel` | `Panel(child, *, title="", style=BORDER)` | Child inside a single-line box; titled top border when it fits. |
| `Notice` | `Notice(text, *, level="info")` | One message row; `warn`/`error` prepend a styled label. Truncated, never wrapped. |
| `Row` | `Row(children, *, widths=None, gap=1)` | Side-by-side columns (fixed/flex widths), tallest child sets the height. |
| `Column` | `Column(children, *, gap=0)` | Vertical stack with `gap` blank rows between children. |

## Input & choice

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Input` | `Input(*, prompt="❮ ", placeholder="", style=NONE, prompt_style=ACCENT, cursor_style=CURSOR, focused=True)` | Cursor-editable field (`insert`/`backspace`/`delete`/`move_*`/`home`/`end`/`clear`); up/down follow wrapped rows; empty+focused shows a dim placeholder. The driver feeds keys — it reads none. |
| `Select` | `Select(options, *, title="", selected_style=SELECTION, hint_style=DIM, title_style=NONE)` | Vertical `Option(label, value, hint)` list; `move(delta)` clamped cursor, `selected` getter; selected row marked `❮`. |
| `Confirm` | `Confirm(message, *, danger=False)` | Yes/No `Select`; `danger` styles the message in `ERROR`. |
| `Spinner` | `Spinner(text="", *, frames=None, interval=0.1)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |

## Status

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `StatusBar` | `StatusBar(*, segments=())` | Priority-ordered footer cells via `segment(text, priority)`; keeps the highest priority and drops the lowest first to fit. |

## pi-style chat blocks

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Message` | `Message(role, text="", *, style=None)` | Role-banded chat row: `user` (full-width color band, 1 pad cell per side, plus one **pure band padding row** above and below — the in-band vertical padding), `assistant` (plain), `thinking` (dim italic); unknown role degrades to `assistant`. `style` overrides the role default. |
| `ToolBlock` | `ToolBlock(title, body=(), *, tone="tool", footer="")` | Tool call: bold title row, blank row, `body` rows, italic footer ("Took 0.1s"), the whole block wrapped in **pure band padding rows** (top and bottom, following `tone`). `tone` picks the band: `tool` (deep-green truecolor, green bold title), `code` (near-black), `plain` (none). Empty sections leave no stray gap; the padding rows always stay. |
| `EditBlock` | `EditBlock(path, context=(), removed=(), added=())` | A diff wrapped in pure band padding rows (top and bottom): accent path row; numbered context / `-` (red) / `+` (green) rows; last added row ends in a green `(edited)` badge. |
| `Table` | `Table(headers, rows, *, header_style=None, first_column_style=None)` | Box-line grid (`│` / `├─┼─┤`); cells are `str` or `(str, Style)`; natural column widths, proportional shrink + ellipsis when over width, never stretched below natural size. |

## Building your own component

A component is one class with `render(width)`. The protocol is `mocode_tui.Component`:

```python
from mocode_tui import DIM, Line, NONE, Segment, Style, SUCCESS
from mocode_tui import Component

class ProgressBar:
    """A determinate progress bar -- a custom component, not a library one."""
    __slots__ = ("fraction", "label")

    def __init__(self, fraction: float, label: str = ""):
        self.fraction = min(1.0, max(0.0, fraction))  # clamp to [0, 1]
        self.label = label

    def render(self, width: int) -> list[Line]:
        lead = f"{self.label} " if self.label else ""
        lead_w = Line.from_text(lead).width
        track = max(0, width - lead_w - 2)  # room for the [ ] frame
        done = min(track, int(round(track * self.fraction))) if track else 0
        row = Line((
            Segment(lead),
            Segment("["),
            Segment("\u2588" * done, SUCCESS),         # filled: green
            Segment("\u2591" * (track - done), DIM),    # empty: shaded
            Segment("]"),
        ))
        return [row.fit(width)]  # always fit back to the painting width
```

Rules of thumb:

- **Measure, don't guess.** Use `Line(...).width` (or `Segment` counts) for
  display width — never `len()`, which miscounts wide characters. The toolkit's
  own truth is `visible_width` (wcwidth); `Line.width` is its root-level face.
- **Always `fit(width)`** the rows you return so a tight screen truncates with a
  `…` instead of wrapping or overflowing.
- **Keep it pure.** `render` must not paint, sleep, read keys, or mutate global
  state — the same component renders in any width and caches like any other.
- **Drive it through the driver.** Put it in a block (`tui.add(ProgressBar(0.4))`),
  mutate it over time, and call `tui.invalidate()`; the pump and diff handle the
  rest.

`ProgressBar` and any other class shaped like this drop straight into
`Document.add`, `Row`, `Column`, and `Panel` — which is exactly how the built-ins
are assembled.
