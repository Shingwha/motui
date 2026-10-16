# Spec tui-depth · W6 组件基础（波次 W6）
> ✅ 已合并 2026-10-17 @ `td6-widgets`（tip `d774a68`）→ main `160adc3`；1381 passed，root 71。
> 分支 `td6-widgets`；前置：W5；深读：`00-overview.md`（D15、协议面与组件目录惯例）。
> **最高约束：四个新组件遵守既有形态（`Themed` + `chosen` 读一次 + `Hoverable/Clickable/
> Focusable/Activable` 按需）；`TextBuffer` 的 undo/redo 与选择在**五个写点**过账，
> 默认键表变化要写明「改前→改后」。**

## 目标

1. `Radio` / `Slider` / `Collapsible` / `ShortcutBar` 四件。
2. `TextBuffer`：有界 undo/redo + 文本内选择；`Input`/`Editor` 渲染选中、键表同步。
3. gallery 与文档同步（不新增页，13 页不变）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| `TextBuffer` 五写点 + `_set_offset`；`handle` 的 getattr 路由 | `widgets/textbuf.py:109-203,276` |
| `_TextField` 转发链；Input 的 paste 折行 | `widgets/field.py:129-172,256-289`；`input.py:122-136` |
| 键表：`DEFAULT_INPUT_KEYMAP` / `DEFAULT_EDITOR_KEYMAP` / `EDITOR_SUBMIT_KEYMAP` | `keys/keymap.py:54-82` |
| 既有原语形态（`Button`/`Checkbox` 的能力集与 `chosen`） | `widgets/button.py`、`widgets/checkbox.py` |
| 容器与主题惯例（`Themed` 解析、`merge`） | `core/theme.py`；`core/style.py` |
| `Choice`/`Tabs` 的 hover_at 先例（行/标签级 merge） | `widgets/choice.py`、`widgets/tabs.py` |
| gallery 页与组件表同步面 | `docs/COMPONENTS.md:138-186`；`README.md:294-348` |

## 工单（按序执行，每项一个 commit）

### T1 `widgets/radio.py`：`Radio`

- `Radio(labels, *, index=0, theme=None, focused=False)`（或等价的 options 形态，照 `Select` 惯例）；
  字段：`index`、`hover`、`focused`、`chosen: int | str | None`（读一次）；
  能力：`Hoverable + Focusable + Clickable + Activable`；`hover_at(row, col)` 行级高亮；
  `move(delta)` 与 `activate()`/`click()` 置 `chosen`；渲染 `( ) / (•)` 前缀 + 单行列表。
- 测试：键盘/鼠标两路 `chosen`、hover 行级归零字节、`focus_style` 区分。

### T2 `widgets/slider.py`：`Slider`

- `Slider(value=0, *, minimum=0, maximum=10, step=1, theme=None, focused=False)`；字段 `value`、
  `hover`、`focused`、`chosen: int | None`；能力同 Radio；`move(±1)`、`click(row,col)` 按列定位、
  `activate()` = 确认当前值；渲染 `[====----] 4`（轨道宽度随 `render(width)`）。
- 测试：边界 clamp、step 对齐、点击列→值、hover/归零字节。

### T3 `widgets/collapsible.py`：`Collapsible`

- `Collapsible(title, body, *, open=True, theme=None, focused=False)`；字段 `open`、`hover`、
  `focused`、`chosen: bool | None`（每次切换一次）；能力 `Hoverable + Clickable + Focusable +
  Activable`；渲染标题行（`▸/▾` 前缀）与展开时 body 行；`click`/`activate` 翻转 `open`。
- 测试：折叠/展开的字节、标题行 hover、`chosen` 读一次、嵌套内容宽度。

### T4 `widgets/shortcutbar.py`：`ShortcutBar`

- `ShortcutBar(items, *, theme=None, separator=" · ")`（`items: list[tuple[str, str]]`）；
  渲染一行 `c-n next · c-p prev …`，`fit(width)` 截断（够用即止，不做交互）。
- 测试：字节、宽字符、截断。

### T5 `widgets/textbuf.py`：undo / redo（D15）

- 有界历史（默认 100 步，常量）：五个写点（`insert/backspace/delete/newline/clear`）**先在改动前
  快照**（`(lines, row, col)` 元组），新改动截断 redo 栈；`undo()`/`redo()` 恢复快照并返回 bool；
  连续同型输入可合并（连续单字符插入合并为一步——写明规则）。
- 键表：`c-z` → undo、`c-y` → redo（`DEFAULT_INPUT_KEYMAP` 与 `EDITOR_SUBMIT_KEYMAP` 同步）；
  `docs/DESIGN.md` 的 Keys 段与 `docs/COMPONENTS.md` 的 Input/Editor 条目同步。
- 测试：五写点各自 undo/redo 往返；合并规则；栈界；paste 折行路径（`input.py:122-136`）过账。

### T6 `widgets/textbuf.py` + `field.py` + keymap：文本内选择（D15）

- `TextBuffer` 加选择锚（`anchor: int | None`）：`select_left/right/up/down`（shift 扩展，复用
  `move_*` 的列语义）、`select_home/end`、`select_all`（`c-a` 从「行首」改为「全选」——**写清
  改前→改后**，`c-a` 原语若在别处有消费者则保留 `home` 的 `c-a` 并另用 `c-g`？**decision：`c-a`
  改全选，行首由 `home` 承担**）；`selected_text`、`clear_selection`、`selection_range`；
  插入/删除/回车**先删选中**再落笔；任何移动（非 shift）清空选择。
- `_TextField`：渲染选中区间 `merge(theme.selection)`（光标与选择共存时选择优先视觉，光标仍在）。
- 键表：加 `s-left/s-right/s-up/s-down/s-home/s-end`（W1 的 D16 提供键名）；
  `EDITOR_SUBMIT_KEYMAP` 同步。
- 测试：shift 扩展四方向与列保持、替换语义、c-a 全选、非 shift 清空、选中渲染字节、归零。

### T7 gallery + 文档 + python pin

- gallery：`/choice` 页加 `Radio`；`/data` 页加 `Slider`；`/structure` 页加 `Collapsible`；
  footer 的 `StatusLine` 上方或 `features` 页加 `ShortcutBar`（择一，写明）；回放脚本覆盖新件。
- `widgets/__init__.py` + root `__init__.py`：四个新件 + `test_api_root.py` 同步（root 计数变化）。
- `docs/COMPONENTS.md` 组件表 + 对应 ## 小节；`README.md` 组件表；`docs/DESIGN.md` 命名表与
  Keys 段的键位改动（`c-a/c-z/c-y/s-*`）。
- `tests/test_widgets_basics.py` 的窄宽护栏扩到新件。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 只增不减；贴被更新的既有断言（`c-a` 语义变化的测试、键表 pin、root 计数）。
2. 探针：Radio/Slider/Collapsible 的 `chosen` 与 hover 三态；ShortcutBar 截断；undo/redo 一例原文；
   shift+方向选择的 `selected_text`。
3. `demo.py < /dev/null` exit 0；`--pages` 13 页头；`golden --check` 全过（本波重录一次，写明）。
4. framebench hash 如实报告（不碰工作负载 → 预期不变）。
5. import 干净；README 块全绿；`test_readme_examples.py` 若含键位块则同步。

## 禁触清单

- `SelectionGesture`/`Pointer`/`Find`（W2–W4 的成果）；`chosen` 读一次契约
- `TextBuffer.move_*` 的既有语义（选择层叠加在其上，不改移动本身）
- `specs/**`；gallery 页数（13 不变）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论 / 组件探针 / undo-redo 与选择探针 / 键表改动的改前→改后 /
golden 重录说明 / framebench hash / 偏差与取舍 / 未决问题 / 真机手测：未执行。
