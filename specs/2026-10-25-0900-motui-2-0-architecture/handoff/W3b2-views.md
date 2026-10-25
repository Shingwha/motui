# W3b2 交接 · 数据视图族迁移到树、Cursor 与 keymap

> 分支 `2.0/w3b2-views`；起点 `609eb67`（W3a 合并后的工单排序 commit）。
> 前置：`ref/interfaces.md`、`handoff/W3a-base.md`、工单 `15-W3b2-views.md`。
> 结论：T1–T6 完成；**1464 passed**（1422 旧 + 42 新）；57 byte / 57 semantic /
> render-hash `e7ca544b…2986da` 全不变；`ClampedCursor` 删除；各视图
> `keymap`/`on_action` 与旧按键 1:1。

## A. 交付面与门禁

### Cursor 统一清单
- List / Select / MultiSelect / RadioGroup / CheckboxGroup / Tree / Table /
  Tabs / MenuBar / NavList / ScrollPanel 全部只经 `widgets.cursor.Cursor`。
- `strip.ClampedCursor` 已删除，选择算术内联到 `LabelStrip` 与 `NavList`；
  全仓 `class .*Cursor` 只剩 `cursor.py:Cursor`。

### 类级 keymap（实例可 rebind）
| 族 | 键 → action |
|---|---|
| List | up→prev, down→next, home→first, end→last |
| Select 族（含 Multi/Radio/Check/ContextMenu） | up/left→prev, down/right→next, enter→activate |
| Tree / Table / MenuBar | up/left→prev, down/right→next, enter→activate |
| Tabs / NavList | up/left→prev, down/right→next |
| ScrollPanel | up/down→prev/next, page_up/page_down→page_prev/page_next, home/end→first/last |
| StatusLine / ShortcutBar / Notice | `{}`（纯展示） |
### 能力属性
| 类 | focusable | clickable | hoverable | activatable |
|---|---|---|---|---|
| List / Tree / Table / Select 族 / MenuBar | T | T | T | T |
| Tabs / NavList | T | T | T | F |
| ScrollPanel | T | T | F | F |
| StatusLine / ShortcutBar / Notice | F | F | F | F |

- action 名：`prev/next/first/last/page_prev/page_next/activate/toggle/expand/collapse/scroll_prev/scroll_next`；
  未知名字返回 `False` 且不动状态。
- 旧别名（W3b3 删除）：`handle = on_key`（ScrollPanel `handle = _dispatch`）；
  `take_result = take`。`take()` 在 List/Select/Table/MenuBar 落地；Tree/Nav/Tabs/
  Rows/Scroll 无结果（基类 `take()` → `None`）。
- `on_click(Pos)` / `on_hover(Pos|None)` / `on_drag(Pos, phase)` 复用 W3a 基类默认
  （Pos→row/col；`None`→`hover_at(-1,-1)`），未重复实现。
### 门禁（本 worktree，Python 3.12.14 / uv 0.12.21）
- pytest **1464 passed**；golden 57；semantic 57；hash `e7ca544b…2986da`；
  demo 70 行；`--pages` 4059 行
- ruff All checks passed；pyright 0；lint-imports 4 kept；api 181 names；growth --quick OK
- `grep -rn "ClampedCursor" src` = 0；本族 `def handle(` = 0；`def take_result` = 0

## B. 实现细节 / W3b3 提示

1. **rebind 实现**：`strip.Keymap` 是数据描述符。类访问 `List.keymap` 返回类默认
   dict；实例访问返回 `_keymap`（`__init__` 中 `dict(type(self).keymap)` 复制）。
   `lst.keymap["j"]="next"` 只改实例，整表赋值走 `__set__` 也只改实例。新增视图
   必须把 `_keymap` 写进 `__slots__`，否则 descriptor 写入报 `AttributeError`。
2. **消费语义**：List 的四个移动 action 在边界也返回 `True`（旧 `handle` 无条件消费
   这四个键）；其余视图的 prev/next 返回 `move` 的 bool（旧 `FocusManager._step`
   语义），所以边界键继续回落给 host。`enter` 只绑定给本来有 `activate` 的视图；
   List 的 `handle(enter)` 仍为 `False`（旧测试要求），FocusManager 随后 activate，
   App 行为不变。
3. **未绑定 home/end**：1.x 的 FocusManager 对 Tabs/NavList/MenuBar/Tree/Table 只
   处理四方向+enter；为避免新抢走 host 的 home/end 绑定，这五族默认表不含它们
   （List/ScrollPanel 原本处理 home/end，故保留）。W3b3 若统一键表可再补。
4. **Table `_index` 语义保持**：`None` 仍是“无 cursor”；首次 move 落在离开方向的
   边上（down→首个启用行，up→最后一行）；`take()` 返回 `int`，`take_result` 是同一
   函数对象。未改成持有 Cursor。
5. **strip 合并**：`ClampedCursor.select/move` 原样内联到 `LabelStrip`；NavList 不再
   是 mixin 子类，自带 `index/_cursor/select/move`（同一 Cursor 规则）。LabelStrip
   提供 focusable/clickable/hoverable=True、activatable=False；MenuBar 覆盖为 True。
6. **Rows / wheel**：三个 rows 类显式声明四项能力为 False、keymap 继承 `{}`；
   ScrollPanel 的上下键旧 `handle` 不做 axis 检查（x-only 也 `scroll_up`），已保留，
   只有 `wheel_up/down` 保留 `y/both` 检查，`wheel_left/right` 由 `scroll_x` 拒绝 y-only。
7. **W3b3 要删**：`handle` 别名（7 个视图 + ScrollPanel `_dispatch`）、`take_result`
   别名（list/choice/table/menubar）、`FocusManager` 方向键硬编码与
   `_looks_interactive`（app 范围）。
8. **坑**：`type(self).keymap` 在 `__init__` 依赖子类 class body 已声明 `Keymap`；
   未声明时回落 Widget 的 `{}`（Rows 即如此）。`Widget.__setattr__` 对整表赋值会
   额外 `touch()`，对渲染无影响。
## C. 位置与 commit

- 源码（10）：`src/motui/widgets/{list,tree,table,choice,navlist,tabs,menubar,rows,strip,scroll}.py`
- 测试（6）：`tests/widgets/{test_data,test_choice,test_navigation,test_menubar,test_rows,test_scroll}.py`（+42 例）
- commit：
  - `0b1adea` widgets: list and choice route keys through a private keymap（T1）
  - `dabfd1b` tree: the tree and nav rail route keys through named actions（T2）
  - `b50f797` table: the grid routes keys through named actions（T3）
  - `588f950` strip: one cursor, one keymap, no clamped-cursor copy（T4）
  - `82f839a` scroll: the panel routes keys and the wheel through typed hooks（T5）
  - 本文件（T6 收口；`api --update` 零内容变化）
- 禁触清单零 diff：`kernel/**`、`terminal/**`、`app/**`、`demo/**`、其余 `widgets/**`、
  `tests/golden/**`、`tools/{golden,framebench,semantic}.py`、`pyproject.toml`、
  `uv.lock`、`README.md`、`docs/**`、`CHANGELOG.md`。
  `git diff --name-only 609eb67..HEAD` 仅上述 10 源码 + 6 测试 + 本 handoff。
