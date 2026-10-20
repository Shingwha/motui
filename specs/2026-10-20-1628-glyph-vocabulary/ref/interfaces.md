# 接口契约 — the glyph vocabulary

> 状态：W1 派工前草案。W1 合并后由 lead 回写为现实；W2 只读本文件，不读实现。

## 1. 词汇模块（W1 创建，`motui.kernel.glyphs`）

| 名称 | 值 | 角色 |
|---|---|---|
| `CURSOR` | `▸` | 数据列表的光标行 |
| `MENU_CURSOR` | `→` | 菜单的光标行 |
| `RAIL_BAR` | `▌` | 导航栏的当前项 |
| `EXPANDED` / `COLLAPSED` | `▾` / `▸` | 树的可展开状态 |
| `RADIO_EMPTY` / `RADIO_FILLED` | `( )` / `(•)` | 单选的未选/选中 |
| `MARKED` / `UNMARKED` | `[x]` / `[ ]` | 行的标记状态 |
| `MORE_UP` / `MORE_DOWN` | `↑` / `↓` | 窗口上/下的隐藏行 |
| `TRACK` / `THUMB` | `░` / `█` | 滚动条（W2 消费） |
| `TASK_OPEN` / `TASK_DONE` | `☐` / `☑` | Markdown 任务框（W2 消费） |

helper（纯函数，全部基于 `kernel.text.visible_width`）：

- `seat(glyph) -> str` — 字形 + 一个空格；空串 → `""`。
- `seat_width(glyph) -> int` — 可见宽度 + 1；空串 → 0。
- `pair_seat(glyph, other) -> str` — `seat(glyph)` 补空格到 `max(seat_width(glyph), seat_width(other))`。

## 2. 组件参数（W1，全部 keyword-only）

| 组件 | 参数 | 默认 | 座位/列规则 |
|---|---|---|---|
| `List` | `marker` / `more_up` / `more_down` / `mark_pair` | `CURSOR` / `MORE_UP` / `MORE_DOWN` / `(MARKED, UNMARKED)` | 光标座 `seat_width(marker)`；计数行用两字形；标记列 `pair_seat` |
| `Select`（含 `Autocomplete`） | `marker` | `MENU_CURSOR` | 空串 → 0 格，无悬空空格 |
| `NavList` | `bar` | `RAIL_BAR` | `bar=""` → 0 格（已支持） |
| `Tree` | `expanded` / `collapsed` | `EXPANDED` / `COLLAPSED` | 指示列 = pair 宽度；叶子留同样空列 |
| `Radio` | `empty` / `filled` | `RADIO_EMPTY` / `RADIO_FILLED` | 组件自己渲染 pair 列（不再借用 base 的 marker） |
| `CheckGroup` | `mark_pair` | `(MARKED, UNMARKED)` | 保留 `marked=`（初始下标集） |
| `Table` | `mark_pair` | `(MARKED, UNMARKED)` | 标记列 = pair 宽度 |

## 3. 不变量

1. 默认渲染逐字节不变（golden 零 diff、render-hash `f872187a…`）。
2. 座位宽度一律 `visible_width`；空字形 = 0 格。
3. 状态对按较宽者对齐。
4. 字形只染行文字样式，不带 band。
5. 每个字形参数进入所属组件的 `revision()`。

## 4. 旧名删除（无别名）

`widgets/list.py` 的 `MARKER`、`MORE_UP`、`MORE_DOWN`；`widgets/choice.py` 的 `MARKER`、`EMPTY_MARK`、
`FILLED_MARK`；`widgets/markdown/nested.py` 的 `TODO_MARK`、`DONE_MARK`；`interaction/scrollbar.py` 的
`TRACK`、`THUMB`。消费者在同一 commit 改用 `kernel.glyphs` 的名字。

## 5. 范围外

- `Panel` 的边框六字形（另立项）。
- `Tabs` 的指示器（SGR underline 属性）。
- `Divider.char` / `Tabs.divider`（已是参数，不改名）。

## 6. W2 消费的稳定事实

（W1 合并后由 lead 补：glyphs 模块的最终签名、Scrollbar/Markdown 的接入点、W1 的已知坑。）
