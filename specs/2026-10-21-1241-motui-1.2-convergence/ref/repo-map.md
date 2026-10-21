# repo-map — motui

> 基线：`cbebdf9`（2026-10-21 12:41 UTC+8）。本文件只记录稳定知识；波次增量写 handoff。

## 1. 目录职责

```
src/motui/
  __init__.py           curated root: 41 names final (W6)
  app.py                TUI driver: document facade, pump, frame, selection, run lifecycle
  commands.py           Command / CommandRegistry
  testing.py            headless_tui, snapshot, ScriptedEvents
  kernel/               primitives + document + render + frame + host seam
    __init__.py         73 public names
    style.py            Style, Color, ColorMode, NONE
    theme.py            Theme (10 role groups), ColorPalette, Themed, DEFAULT_THEME
    glyphs.py           Glyphs, Border, GLYPHS, seat helpers
    lines.py            Line, Segment, Text, wrap_line, action_at
    text.py             visible_width, wrap_text, ellipsize_tail, terminal_size
    events.py           Event, KeyEvent, MouseEvent, PasteEvent, ResizeEvent, FocusEvent
    block.py            Component + 8 capability protocols, Block, BlockState, Document, descend
    cursor.py           CursorWindow
    mark.py             MarkSet, mark_prefix
    viewport.py         ScreenLayout, Viewport
    frame.py            Rect, Pane, Frame, Chrome, Separator (+ FrameTable)
    screen.py           Screen, TerminalScreen, HeadlessScreen
    painter.py          Painter (row diff, one flush)
    selection.py        Selection, highlight, extract
    host.py             Host protocol, Hit, RowRange, EveryHandle, QueryInput, FilterList, OptionLike
    clipboard.py        Clipboard, ScreenClipboard, MemoryClipboard
    chrome.py           _ChromeHost, Separator helpers
    ansi.py             escape sequences
  keys/
    decoder.py          pure bytes -> events
    keymap.py           Keymap, DEFAULT_INPUT_KEYMAP, DEFAULT_EDITOR_KEYMAP, EDITOR_SUBMIT_KEYMAP
    sources.py          RawTerminalKeys, event sources
    console.py          Windows console record API
  widgets/
    __init__.py         43 public names
    action.py           Button, Checkbox, Link
    choice.py           Select, RadioGroup, CheckboxGroup, Option
    autocomplete.py     Autocomplete (Select subclass)
    combobox.py         ComboBox (Input + dropdown)
    form.py             Form, Field
    textfield.py        Input, Editor (_TextField)
    textbuf.py          TextBuffer (editing engine)
    list.py             List
    table.py            Table (single table engine; Markdown delegates here)
    tree.py             Tree, TreeNode
    navlist.py          NavList
    tabs.py             Tabs
    menubar.py          MenuBar, ContextMenu
    strip.py            ClampedCursor, LabelStrip (private)
    collapsible.py      Collapsible
    decor.py            Divider, Panel
    diff.py             Diff
    dialog.py           Dialog, ButtonSpec, confirm_dialog, prompt_dialog
    indicators.py       ProgressBar, Slider, Spinner
    layout.py           Row, Column, Padding, Spacer
    rows.py             Notice, ShortcutBar, StatusLine
    scroll.py           ScrollView (paint-only bar today)
    delegate.py         Delegate (no production consumer)
    syntax.py           Highlighter, RegexHighlighter, highlight
    markdown/           component.py, blocks.py, inline.py, tables.py, nested.py, context.py
  interaction/
    __init__.py         11 public names
    focus.py            FocusManager
    pointer.py          Pointer
    gesture.py          SelectionGesture, copy_on_select
    find.py             Find
    modal.py            Modal
    command_palette.py  CommandPalette (+ private _CommandPalettePanel)
    overlays.py         Toasts, Tooltip, Stats
    scrollbar.py        Scrollbar (pane chrome; drives Pane.viewport)
  demo/
    __main__.py         demo entry
    session.py          552-line manual host loop: dispatch order, tiers, theme rebuild
    shell.py            Header/footer/catalog docks
    stage.py            TopicBuilder, Echo, walk_objects
    registry.py         topic registry
    topics/*.py         topic pages
    fixture.md          streaming Markdown fixture (contains tables)
tests/
  test_api.py           facade resolvability (does not pin exact names)
  golden/topics/*.txt   byte-exact rendered topics (58 files)
  kernel/, keys/, widgets/, interaction/, app/
tools/
  golden.py             record/check the topic frames
  framebench.py         timing workloads + render hash
docs/
  DESIGN.md             architecture rationale
  CONTRACT.md           normative contracts
  COMPONENTS.md         component catalogue
  releases/*.md         release notes
specs/                  process archive (add-only)
```

## 2. 入口点与核心模块

| 入口 | 用途 |
|---|---|
| `src/motui/__init__.py` | 公共 root；`TUI`、widgets、Theme 值 |
| `src/motui/app.py` | `TUI`：驱动、pump、frame、selection、run_session |
| `src/motui/demo/__main__.py` | `python -m motui` 的 demo |
| `src/motui/testing.py` | headless 驱动 |
| `tools/golden.py` | golden 帧录制/校验 |
| `tools/framebench.py` | 渲染 hash 与性能基准 |

核心数据流（当前）：

```
terminal bytes -> keys.KeyDecoder -> Event -> host loop
  -> FocusManager / Pointer / SelectionGesture / Scrollbar / Modal
  -> TUI.add -> Document -> Block -> Component.render(width) -> list[Line]
  -> Viewport.layout -> ScreenLayout
  -> Frame.compose (panes/chrome/docks/overlays)
  -> Painter.paint (row diff)
  -> Screen
```

关键不变量：

- 所有 cell 索引 0-based；鼠标报告在 decoder 里减 1。
- `Component.render(width) -> list[Line]` 是唯一渲染义务。
- `Line` 是一个视觉行；`Segment` 是带样式的文本段。
- `Block` 目前有 OPEN/SEALED 两态；`Block.rows` 是按 `(width, revision)` 的缓存。
- `Hit` 目前是 7 字段：pane/block/row/col/leaf/leaf_row/leaf_col。
- 主题是值；当前控件在 `__init__` 解析样式，换主题需要重建控件。
- `TUI.read_event` 当前会拦截 `scroll_keys` 并执行 `focus_policy`（W4 改掉）。

## 3. 构建、测试、lint

环境：Python 3.12+，`uv` + `.venv`，Windows Git Bash。

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

当前基线（lead 已跑）：

- `./.venv/Scripts/python.exe -m pytest -q` -> **889 passed in 4.41s**。
- 没有 ruff/mypy 配置；不要引入新 linter，除非工单明确要求。
- `-p no:cacheprovider` 用于并行 worktree，避免共享 `.pytest_cache`。
- golden 校验命令是 `uv run python tools/golden.py --check`；重录用 `--update`，不要手改文件。

## 4. 关键类型 / 接口 / 数据流

| 类型 | 位置 | 备注 |
|---|---|---|
| `Component` | `kernel/block.py` | `render(width)`；零运行时 isinstance 检查 |
| `Clickable`/`Activable`/`Focusable`/`Hoverable`/`Container`/`Controller`/`Resultful`/`Revisioned` | `kernel/block.py` | 9 个 `runtime_checkable` protocol；W3 收敛为 `Widget` 基类 + 内部 duck typing |
| `Block` | `kernel/block.py` | id + component + pin + row cache + state |
| `Document` | `kernel/block.py` | 有序、id 可寻址；`blocks()` 快照 |
| `Viewport` | `kernel/viewport.py` | offset + stick-to-bottom + 固定区；`layout(width,height)` |
| `ScreenLayout` | `kernel/viewport.py` | rows/body_rows/row_blocks/block_order/offset/total_rows |
| `Frame`/`Pane` | `kernel/frame.py` | split tree、chrome、docks、overlays；pane 拥有 viewport |
| `Host` | `kernel/host.py` | 交互层看到的窄驱动协议；W2 删除 |
| `Hit` | `kernel/host.py` | 命中结果；W2/W4 简化 |
| `Scrollbar` | `interaction/scrollbar.py` | pane chrome；驱动 `Pane.viewport`；11 参数 |
| `ScrollView` | `widgets/scroll.py` | 自己的 `_offset`；bar 只绘制；6 参数 |
| `Table` | `widgets/table.py` | 单表引擎；一行数据 = 一个 `Line`；15 参数 |
| `Markdown` | `widgets/markdown/component.py` | 规则注册表；表格委托 `Table` |

## 5. 约定

- 代码注释/docstring：英文；提交信息：`area: lowercase imperative`（如 `widgets: drop the unused List ground cache`）。
- 公共名字只在一个 facade 出现；root 是 curated subset。
- 不写兼容 shim；删除名字时同步删除测试和文档。
- 渲染变化必须重录 golden 并在 commit message 解释。
- 不主动 push / tag / 发版。
- 文档与代码同 commit。

## 6. 环境陷阱

- Windows Git Bash；`python` 可能不是项目环境，使用 `./.venv/Scripts/python.exe` 或 `uv run`。
- 工作区可能残留 `.zcodeignore`（未跟踪）；worker 不要提交它。
- `.pytest_cache` 不能并行共享；用 `-p no:cacheprovider`。
- 非 ASCII 路径（`C:\Users\shifu\...`）在脚本里用引号。
- `tools/golden.py` 可能依赖 `uv`；若不可用，用 `.venv` 解释器直接跑。
- 当前 `dist/` 里是 1.1.0 的旧产物；不要在 W6 之前改 `pyproject.toml`。

## 7. 找 X 去哪

| 要改什么 | 去哪 |
|---|---|
| 渲染原语 / Line / Segment | `kernel/lines.py`、`kernel/text.py` |
| 主题 / 样式 / 颜色 | `kernel/theme.py`、`kernel/style.py` |
| Glyph / Border | `kernel/glyphs.py` |
| 事件 / decoder | `kernel/events.py`、`keys/decoder.py` |
| 文档 / Block / 缓存 | `kernel/block.py` |
| 滚动 / 视口 | `kernel/viewport.py`、`widgets/scroll.py`、`interaction/scrollbar.py` |
| 分屏 / dock / overlay | `kernel/frame.py`、`app.py` |
| Hit test / 坐标下降 | `app.py`、`kernel/block.py`（descend） |
| 焦点 / 指针 / 选择 | `interaction/focus.py`、`pointer.py`、`gesture.py` |
| 模态 / 命令面板 | `interaction/modal.py`、`command_palette.py` |
| Markdown | `widgets/markdown/` |
| 表格 | `widgets/table.py`（Markdown 的 `tables.py` 只解析） |
| demo 页面 | `demo/topics/`、`demo/registry.py` |
| 公共 API | `src/motui/__init__.py`、各层 `__init__.py`、`tests/test_api.py` |
