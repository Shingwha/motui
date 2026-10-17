# ref · motui 目标结构与逐字清单（权威副本）

> 本文件是 W1–W4 的**唯一**结构依据。清单里的名字、顺序、路径都按此逐字实现；
> worker 不得自行增删名字或调整层级。与代码冲突时以本文件为准（并把冲突写进报告）。

## 1. 目标目录树（W2 完成后）

```
src/motui/
├── __init__.py            精简根门面（31 名，见 §3）
├── py.typed
├── kernel/                原 core/ 改名；模块名不变
│   ├── __init__.py        60 名门面（与今天 `mocode_tui.core` 逐字相同）
│   ├── ansi.py  block.py  events.py  frame.py  lines.py  painter.py
│   ├── screen.py  selection.py  style.py  text.py  theme.py  viewport.py
├── keys/
│   ├── __init__.py        6 名门面（去掉 RecordingKeys / ReplayKeys）
│   ├── console.py  decoder.py  keymap.py  sources.py      ← recorder.py 已删
├── widgets/
│   ├── __init__.py        32 名门面（与今天相同，逐字）
│   ├── autocomplete.py button.py checkbox.py choice.py collapsible.py
│   ├── decor.py diff.py editor.py field.py input.py layout.py link.py
│   ├── list.py palette.py progress.py radio.py shortcutbar.py slider.py
│   ├── spinner.py statusline.py table.py tabs.py textbuf.py tree.py
│   ├── syntax.py
│   └── markdown/  (blocks context inline nested tables component __init__)
├── interaction/           新包：四个策略层
│   ├── __init__.py        5 名门面（见 §4）
│   ├── focus.py  gesture.py  pointer.py  search.py
├── app.py                 TUI · Hit · EveryHandle
├── chrome.py              Scrollbar · Stats · Toasts · Tooltip
└── testing.py             headless_tui · snapshot
```

依赖方向不变：`kernel` 不依赖任何其它层；`keys` 只依赖 `kernel`；`widgets` 只依赖 `kernel`（+`keys` 的 keymap）；`interaction` / `app` / `chrome` / `testing` 在其上；`interaction/*` 可以导入 `app`（`TUI` 类型与品牌）与 `chrome`（`pointer` 只在类型注解上需要，保持现状写法）。

## 2. 各层 `__all__`（逐字，顺序即门面文件的 `__all__`）

顺序规则（`tests/test_api_root.py` 的 `_groups` 强制）：**全大写常量按字典序在前，其余（类与函数混排）按字典序在后**。

### `motui.kernel` — 60 名（与今天 `mocode_tui.core` 完全一致，只改模块路径）

```
ACCENT BORDER CLEAR_LINE CODE CURSOR DEFAULT_THEME DIM ELLIPSIS ERROR ESC
FG_CODES MORE_BELOW MUTED NONE RESET SELECTION SUCCESS WARNING
Activable Block BlockState Clickable Component Container Document Focusable
Frame HeadlessScreen Hoverable Key KeySource Line MouseEvent Painter Pane Paste
Rect Screen ScreenLayout ScriptedKeys Segment Selection Style TerminalScreen
Text Theme Viewport
action_at clear_screen cursor_position descend disable_mouse_tracking
ellipsize_tail enable_mouse_tracking enable_vt enter_alt_screen extract
hide_cursor highlight leave_alt_screen show_cursor terminal_size visible_width
wrap_line wrap_text
```

### `motui.keys` — 6 名（裁掉 RecordingKeys / ReplayKeys）

```
DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP EDITOR_SUBMIT_KEYMAP
KeyDecoder Keymap RawTerminalKeys
```

### `motui.widgets` — 32 名（与今天相同）

```
Autocomplete Button Checkbox Collapsible Column Confirm Diff Divider Editor
Input Link List Markdown Notice Option Padding Palette Panel ProgressBar Radio
Row Select ShortcutBar Slider Spacer Spinner StatusLine Table Tabs Text Tree
TreeNode
```

### `motui.widgets.markdown` — 与今天相同，不动

### `motui.interaction` — 5 名（新门面）

```
Find FocusRing Pointer SelectionGesture copy_on_select
```

### `motui.app` / `motui.chrome` / `motui.testing` — 与今天相同

```
motui.app       : EveryHandle Hit TUI
motui.chrome    : Scrollbar Stats Toasts Tooltip
motui.testing   : headless_tui snapshot
```

## 3. 根门面 `motui.__all__` — 31 名（逐字、逐序）

```
DEFAULT_THEME
Button Checkbox Editor FocusRing Input Key Line Link List Markdown MouseEvent
Option Palette Paste Pointer Scrollbar Segment Select SelectionGesture
StatusLine Style TUI Table Tabs Text Theme Toasts Tree headless_tui snapshot
```

即：

- **常量（1）**：`DEFAULT_THEME`
- **其余（30）**：Button, Checkbox, Editor, FocusRing, Input, Key, Line, Link,
  List, Markdown, MouseEvent, Option, Palette, Paste, Pointer, Scrollbar,
  Segment, Select, SelectionGesture, StatusLine, Style, TUI, Table, Tabs, Text,
  Theme, Toasts, Tree, headless_tui, snapshot

（顺序由 `_groups` 规则决定：常量区按字典序，其余按字典序混排；`Segment` < `Select`
< `SelectionGesture`，`TUI` < `Table`（大写字母序在小写之前），`headless_tui` /
`snapshot` 排在小写尾部。落地后由 `tests/test_api_root.py` 逐字校验。）

**入选规则（写进根 `__init__` 的 docstring）**：根 = 驱动 + 样式三件（`Theme`/`DEFAULT_THEME`/`Style`）+ 行原语（`Line`/`Segment`）+ 事件三件 + 内容/编辑/数据/选择/动作组件中「一个应用起手就要用到的」+ 交互与 chrome 的接线入口 + headless 两件。其余名字**全部保留在各层门面**，只是不再出现在根。

## 4. 下放清单（今天在根、W2 后不在根的 42 名及其文档化落点）

`tests/test_api_root.py` 的 `DOWN_LISTED` 按此重写（每条都断言可解析）：

| 落点（facade） | 名字 |
|---|---|
| `motui.kernel` | ACCENT DIM ERROR MUTED SUCCESS WARNING Block Component Pane Selection extract highlight visible_width wrap_text |
| `motui.kernel.screen` | HeadlessScreen |
| `motui.kernel.events` | ScriptedKeys |
| `motui.keys` | DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP EDITOR_SUBMIT_KEYMAP |
| `motui.widgets` | Autocomplete Collapsible Column Confirm Diff Divider Notice Padding Panel ProgressBar Radio Row ShortcutBar Slider Spacer Spinner TreeNode |
| `motui.interaction` | Find copy_on_select |
| `motui.chrome` | Stats Tooltip |
| `motui.app` | EveryHandle Hit |

## 5. `tools/apidoc.py` 的 `FACADES`（W2 更新为新表面，顺序即页面顺序）

```python
FACADES: tuple[str, ...] = (
    "motui",
    "motui.kernel",
    "motui.keys",
    "motui.widgets",
    "motui.widgets.markdown",
    "motui.app",
    "motui.chrome",
    "motui.interaction",
    "motui.testing",
)
```

## 6. 消费者导入口径（W2 应用在 examples/ 与 tests/ 上）

- 名字在根 31 名内 → 从根导入（gallery 页面的展示面就是这一条）。
- 名字不在根 → 从**最浅的层门面**导入：组件从 `motui.widgets`，内核值类型从 `motui.kernel`，
  交互层从 `motui.interaction`，chrome 从 `motui.chrome`。
- 只有需要「内核深缝」（`motui.kernel.frame`、`motui.kernel.painter`、`motui.kernel.viewport` …）
  时才下到具体模块——`examples/gallery/shell.py` 现在就是这么写的，保持。
- **不要**为了少写字而在 `widgets/__init__.py` 里新增名字；层门面清单是锁定的。

## 7. 根 `__init__.py` docstring 的内容要求（W2）

重写（保留仓库文体），必须讲清：

1. 一句定位：`motui` 是一个分层全屏 TUI 工具包（block 文档、alt screen、视口滚动、pinned band、行级 diff 绘制）。
2. 五个层：`kernel` / `keys` / `widgets` / `interaction` + 顶层的 `app` / `chrome` / `testing`，各一句职责。
3. 导入契约：根是 31 名的高频面；其余在任何层级命名空间下公开（给出 §6 的例子）。
4. 依赖方向：kernel 不依赖任何层，各层单向向上。

## 8. 名字替换口径（W1）

- `mocode_tui` → `motui`（import、docstring 交叉引用、测试里的 `import mocode_tui`）。
- `mocode-tui` → `motui`（发行名、CLI 示例、README/docs 散文里的库名）。
- 全仓**没有**裸 `mocode`（已验证）；若替换中发现，一并改成 `motui` 并在报告里列出。
- `specs/2026-*` 历史目录**不动**（本组 spec 除外）。
- 仓库地址 `https://github.com/Shingwha/mocode-tui` 保留不改（D9）。
