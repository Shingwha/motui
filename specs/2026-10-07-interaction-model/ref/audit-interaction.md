# ref · 交互面审计（W2–W6 的现状底稿）

> 采集日 2026-10-07，仓库 `mocode-tui` @ `59dee9d`。行号是采集时的锚点，实现前先按符号确认。

## 1. 命中（`click`）

### 1.1 协议

`src/mocode_tui/core/block.py:35-51`：

```python
@runtime_checkable
class Clickable(Protocol):
    """A component that can consume a click on one of its own rows.
    ``row`` is a 0-based row of the component's own ``render`` output --
    what :meth:`~mocode_tui.app.TUI.hit_test` reports as ``Hit.row`` -- so
    the component absorbs its own layout arithmetic (a title row above the
    options, a scrolled window).  ...
    """
    def click(self, row: int) -> bool: ...
```

导出面：`mocode_tui.core`（`core/__init__.py:61` import、`:109` `__all__`）；
根面**没有** `Clickable`（`src/mocode_tui/__init__.py` 无此名）；`README.md:189,229` 有两处条目。

### 1.2 坐标来源

`src/mocode_tui/app.py:116-131`：

```python
@dataclass(frozen=True)
class Hit:
    """``row``/``col`` are 0-based *within the block's own rows*; ``col`` is the
    screen column mapped into ``[0, width-1]``.  ``pane_id`` names the pane ..."""
    block: Block
    row: int
    col: int
    pane_id: str
```

`TUI.hit_test(x, y)`（`app.py:770+`）的 docstring 示例写着 `hit.block.component.click(hit.row)`——
W2 要改。

### 1.3 四个实现（全部 row-only）

| 组件 | 位置 | 语义 | 列语义 |
|---|---|---|---|
| `Select` | `widgets/choice.py:142` | title 行偏移 + `max_rows` 窗口 + 计数行；命中即移动 `index` | 无（整行） |
| `Confirm` | `widgets/choice.py:279-281` | 转发给内部 `Select` | 无 |
| `Autocomplete` | 继承 `Select`（`widgets/autocomplete.py`） | 同上，映射的是**当前命中集**的窗口 | 无 |
| `Tree` | `widgets/tree.py:109` | 可见节点行 → 光标 | 无 |
| `Tabs` | `widgets/tabs.py:82` | **收 tab 序号**，不是格子；docstring："the tab an ``x`` landed on is resolved by the host" | **在宿主** |

`Tabs.click(row)` 的实现体（`tabs.py:82-95`）只做 `0 <= row < len(self.tabs)` 判定后 `activate(row)`——
即"row"在这里被当成序号用。

### 1.4 宿主侧被挤出来的算术（W2 要删的证据）

`examples/showcase/session.py`：

```python
    def _tab_at(self, tabs: Tabs, col: int, pane_id: str | None) -> int | None:
        """The ordinal of the tab under ``col`` of the strip's rendered row. ..."""
        region = None if pane_id is None else self.tui.frame.region(pane_id)
        width = self.tui.screen.width if region is None else region.width
        names = list(tabs.tabs)
        x, seen = 0, 0
        for segment in tabs.render(width)[0].segments:
            span = visible_width(segment.text)
            if seen < len(names) and segment.text == names[seen]:
                if x <= col < x + span:
                    return seen
                seen += 1
            x += span
        return None
```

同文件 `_play_click` 的派发：

```python
        component = hit.block.component
        if isinstance(component, Tabs):
            ordinal = self._tab_at(component, hit.col, hit.pane_id)
            if ordinal is not None:
                component.click(ordinal)
        elif hasattr(component, "click"):
            component.click(hit.row)
```

`Tabs.render` 的几何（`tabs.py:97-107`）：一行，`Segment(" ")` 开头，逐 tab
`Segment(name, style)`，tab 之间 `Segment(" " + divider + " ")`，结尾 `Segment(" ")`。
（`_tab_at` 的起始算法可以搬进组件，但实现必须基于 `self.render(self._last_width)`。）

### 1.5 全部调用点（W2 逐条更新；行号为采集值）

**库内**：`app.py:797`（docstring 示例）、`core/block.py:49`（协议签名）。

**测试**（30 处）：`tests/test_widgets_choice.py:149,156,158,160,216,217,218`；
`tests/test_widgets_autocomplete.py:115,120,122,125,127,128`；
`tests/test_widgets_basics.py:181,182,184,185`（Tabs）、`:329,330,332,333`（Tree）。

**示例**：`examples/showcase/session.py:283,285`（派发）、`script.py:36`（自制 click 事件助手）。

**文档/README**：`docs/COMPONENTS.md:50`、`docs/DESIGN.md:455`、`README.md:379`。

## 2. 激活 / 选择

| 名字 | 位置 | 语义 | 归属 |
|---|---|---|---|
| `Select.selected` | `widgets/choice.py` | 读光标项（纯读，无副作用） | 菜单族 |
| `Confirm.selected` | `widgets/choice.py:279` | 转发 | 菜单族 |
| `Tree.toggle()` | `widgets/tree.py:123-135` | 展开/折叠光标节点；叶子 False；折叠后夹取光标 | 树 |
| `Tabs.activate(index)` | `widgets/tabs.py:69-77` | 选中第 i 个（夹取）；`move` 与 `click` 内部都调它 | tab 条（W2 改名 `select`） |
| `SlashPalette.chosen` | `chat/slash.py` | `handle("enter")` 时 `self.chosen = selected.value`，`close()`；宿主读一次清一次；`open()`/导航清空 | 面板（W3 改为委托 `Select.activate()`/`Select.chosen`） |

`SlashPalette.handle` 的现状（`chat/slash.py:130-134`）：

```python
        if event.name == "enter":
            selected = self._auto.selected
            self.chosen = None if selected is None else selected.value
            self.close()
            return True
```

## 3. 焦点

| 事实 | 位置 |
|---|---|
| **只有窗格焦点** | `core/frame.py` 的 `Frame.focused_pane` / `Pane.focus()`；demo 的 `_cycle_focus`（`examples/showcase/session.py`）用 `tab` 调用它 |
| 字段有 `focused` | `widgets/field.py` 的 `_TextField.focused`（构造参数，`Input`/`Editor` 都暴露）；语义 = 画不画块光标 + 空态画不画占位提示 |
| 列表族**没有** | `Select` / `Tree` / `Tabs` 的 `__slots__` 里没有任何焦点标志；渲染光标不依赖宿主状态 |
| 展示台的残缺替身 | `examples/showcase/page.py` 的 `Play(target, move, enter, hint)` + `PageBody.play`；`session.py` 的 `_play_key`（把 `↑↓/enter" 硬绑给唯一目标）、`_play_click`（点目标时补一次 `enter`）——W4 删除 |

`_play_key` 现状（`examples/showcase/session.py`）：

```python
        play = body.play
        if event.name in ("up", "left"):
            play.move(-1)
        elif event.name in ("down", "right"):
            play.move(1)
        elif event.name == "enter":
            play.enter()
```

## 4. 字段的行几何（W5）

`widgets/textbuf.py`：

```python
class _VisualRow(NamedTuple):
    """One rendered text row as a span of the (tab-normalized) joined text."""
    start: int        # flat offset of the row's first shown character
    end: int          # flat offset just past the row's last shown character
    text: str
    line_start: int   # flat offset of the logical line's first character
    line_end: int     # flat offset of the logical line's end (before "\n")
```

- `visual_rows(width, indent)`（`textbuf.py:293`）：把每逻辑行 `wrap_spans(line, inner)` 切成视觉行；
  `inner = max(0, width - indent)`；tab 归一成单空格（偏移因此与 `value` 等长）。
- `locate(rows) -> (row_index, column_in_row)`（`:312`）：flat → 视觉行/行内字符列。
- `cursor_position(width, indent, window)`（`:340`）：再映射成块内格子（`indent + visible_width(text[:column])`）。
- `move_up`/`move_down`（`:236+`）借 `locate` 保列。
- **没有** cell → offset 的反向映射（W5 的 `place`）。

字段 shell 的行策略：`Input._row_prefix`（prompt 在第 0 行、缩进 = `visible_width(prompt)`，
`widgets/input.py:102-108`）；`Editor._window_start`/`_row_cap`（`max_rows` 居中窗口，
`widgets/editor.py:85-97`）。

## 5. Table（W6）

- `widgets/table.py` 的 `__slots__`（`:115-123`）只有样式与数据：`_border_style` / `_first_column_style` /
  `_header_style` / `aligns` / `headers` / `rows` / `theme`。**零状态**。
- 渲染结构：顶框、表头、**每两数据行之间一条分隔线**、底框（列宽自然 + 收缩，见
  `docs/COMPONENTS.md` 的 Table 行）。
- 既有测试 `tests/test_widgets_table.py` 钉住宽度/收缩/对齐——W6 必须不动它们。

## 6. 键位（W4 的键位迁移依据）

三张默认表（`keys/keymap.py:54-82`）绑定的键名：
`left right home end c-a c-e backspace delete up down c-u`（Input/Editor）
`+ enter`（Editor；composer 的表去掉 enter、加 `c-j`）。
→ **`c-o`、`c-t`、`c-n`、`c-p`、`c-w` 未被任何默认表占用**；`tab` 目前由宿主的
`_cycle_focus`（窗格）消费，W4 把它交给焦点环，窗格改 `c-o`。

## 7. 文档面（每波同步）

| 文件 | 需要同步的内容 |
|---|---|
| `docs/COMPONENTS.md` | `:41-51` 交互表；`:139-153` 组件表（Input/Editor/Select/Confirm/Tabs/Tree/Autocomplete/Table）；`:565-572` 的"组件光标 vs 文档级 selection"段 |
| `docs/DESIGN.md` | `:86-96` 命名表（Consume one event / Palette selection / Click interaction / List movement / `Text and cursor`）；`:448-460` 的点击示例；层图与模块表（W4 加 `focus.py`） |
| `README.md` | `:189,229`（core facade 条目）、`:245-262` 组件表、`:375-380` 鼠标段、demo 段键位说明 |
| `widgets/__init__.py` | 模块 docstring `:10` 的 "move(delta) 或 activate(index)" 措辞 |
| `app.py` | `hit_test` docstring 的调用示例 |

## 8. 复现命令

```bash
grep -rn "def click" src/mocode_tui/
grep -rn "\.click(" src/ tests/ examples/ docs/ README.md
grep -rn "toggle()\|activate(" src/ tests/ examples/ docs/ README.md
grep -rn "class Play\|_play_key\|_play_click\|_tab_at" examples/showcase/
grep -rn "focused" src/mocode_tui/widgets/field.py src/mocode_tui/widgets/choice.py
```
