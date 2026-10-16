# Spec base-components · W2 Pointer tier + 交互原语（波次 W2）
> ✅ 已合并 2026-10-16 @ `bc2-pointer`（tip `b80a0fc`）→ main `b7089b5`；1006 passed。
> 分支 `bc2-pointer`；前置：W1（`Hoverable` / `Container.child_at` / `descend` / `Theme.hover`）。
> 深读：`00-overview.md`（交互宪法、D1–D4、D9）、`01-w1-interaction-kernel.md`（`descend` 的真实签名）。
> **最高约束：hover 与点击都必须在 assembly tier 落地（新的 `pointer.py`），kernel 只加无策略的 1003 字节；
> 组件保持「持有状态 + 控制器方法」，不引入回调。**

## 目标

1. 新 tier `mocode_tui/pointer.py`：`Pointer` —— 指针位置、hover 跟踪、静止点击派发，可选挂 `FocusRing`。
2. hover 的终端开关：DECSET 1003（`enable_mouse_tracking(hover=True)` / `TerminalScreen(hover=...)` /
   `TUI(hover=...)`），**默认关**。
3. `FocusRing.click` 与 `Pointer` 都先 `descend()` 再派发；`TUI.hit_component(x, y)` 便利方法。
4. 新原语 `Button` / `Checkbox` / `Link`（`widgets/`），以及既有可交互组件的行/标签级 `hover_at`。
5. 单测：`tests/test_pointer.py`、`tests/test_widgets_action.py`。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| `enable_mouse_tracking` / `disable_mouse_tracking`（1000+1002+1006） | `src/mocode_tui/core/ansi.py:70,80` |
| `TerminalScreen.__init__(mouse, paste)` 与 enter/leave | `src/mocode_tui/core/screen.py:97,118,134` |
| `HeadlessScreen.__init__` 与 enter/leave | `src/mocode_tui/core/screen.py:192,226,237` |
| `TUI.__init__(..., mouse=True)` → `TerminalScreen(mouse=mouse)` | `src/mocode_tui/app.py:230`（class TUI 行 184） |
| `TUI.hit_test` 返回 `Hit(block, row, col, pane_id)` | `src/mocode_tui/app.py:770` |
| `FocusRing.click(hit)` 的点击策略四步 | `src/mocode_tui/focus.py`（class docstring + `click`） |
| 组件控制器方法（`click` / `move` / `activate`） | `widgets/{choice,tabs,tree,table,input,editor,field}.py` |
| decoder：`kind="motion"`、无按键低两位 0 | `src/mocode_tui/keys/decoder.py:337` |

## 工单（按序执行，每项一个 commit）

### T1 `core/ansi.py` + `core/screen.py` + `app.py`：1003 开关

- `core/ansi.py`：
  ```python
  def enable_mouse_tracking(*, hover: bool = False) -> str:
      """1000 + (1003 when hover else 1002) + SGR 1006.
      1002 reports motion while a button is held (drag); 1003 reports all
      motion, which is what hover needs.  Hover is opt-in: a host that never
      builds a Pointer keeps the smaller mode."""
  def disable_mouse_tracking(*, hover: bool = False) -> str:
      """Disable 1006 + 1003 + 1002 + 1000 (all of them; the reverse-order
      contract forbids leaving a mode on, and disabling an unset mode is a
      no-op)."""
  ```
  实现：`hover` → `ESC[?1000h ESC[?1003h ESC[?1006h`；否则维持 `...1002h...`。
  disable 恒为 `ESC[?1006l ESC[?1003l ESC[?1002l ESC[?1000l`。
- `core/screen.py`：`TerminalScreen(*, mouse=True, paste=True, hover=False)` 与
  `HeadlessScreen(*, ..., hover=False)`；`enter`/`leave` 把 `hover` 传给 ansi 函数。
  `HeadlessScreen` 依旧只录制字节（1003 的字节也照录，供测试断言）。
- `app.py`：`TUI.__init__(..., mouse=True, hover=False, ...)` → `TerminalScreen(mouse=mouse, hover=hover)`。
  docstring 写明：自定义 `screen=` 时由调用方自管 tracking 模式（沿用现有契约）。
- 验证（`tests/test_screen.py` / `tests/test_ansi.py`）：`enable_mouse_tracking(hover=True)` 含 `?1003h`
  且不含 `?1002h`；`headless hover=True` 的 `enter()` 输出含 `1003h`；默认输出与改前**逐字节一致**。

### T2 `focus.py`：`FocusRing.click` 先下钻

- `click(hit)` 第一步改为：
  ```python
  component, row, col = descend(hit.block.component, hit.row, hit.col)
  consumed = isinstance(component, Clickable) and component.click(row, col)
  ```
  之后 `_registered(component)` / focus / activate 全部针对**下钻后的叶子**。
- 类 docstring 的点击策略表补一句「先沿 `Container.child_at` 下钻到叶子，再派发/聚焦/激活」。
- 验证（`tests/test_focus.py` 追加）：把 `Select` 包进 `Padding`，`hit_test` 命中后 `ring.click` 能
  把焦点/激活落到 `Select`；`ring._registered` 认的是叶子。**不新增 `FocusRing` 构造参数。**

### T3 `pointer.py`（新）：指针 tier

- 新文件 `src/mocode_tui/pointer.py`，`__all__ = ["Pointer"]`。构造：
  ```python
  Pointer(tui, *, ring: FocusRing | None = None, hover: bool = True)
  ```
- 状态与接口：
  ```python
  @property
  def hovered(self) -> Component | None      # 当前悬停的叶子组件
  @property
  def position(self) -> tuple[int, int] | None   # 最后一次 motion 的 (x, y)
  def handle(self, event: Key | Paste) -> bool
  def clear(self) -> None                    # 丢弃 hover（pane 切换 / resize 后由宿主调用）
  def detach(self) -> None
  ```
- `handle` 只认 `MouseEvent`，其余一律 `False`：
  1. `kind == "motion"` 且 `button == 0`：`position = (x, y)`；`_update_hover(x, y)`；
     返回 hover 是否变化（变了宿主才会重绘）。
  2. `kind == "motion"` 且 `button != 0`（拖拽中）：清掉「静止点击待定」；返回 `False`（不改 hover）。
  3. `name` 是左键 `kind == "press"`：记 `_press = (x, y)`；返回 `False`（让 `gesture` 照常看到）。
  4. 左键 `kind == "release"` 且 `_press == (x, y)`（静止点击）：`hit = tui.hit_test(x, y)`；
     - `ring is not None`：`consumed = ring.click(hit)`（ring 自己下钻并走 dispatch/focus/activate）；
     - 否则 `component, row, col = descend(hit.block.component, hit.row, hit.col)`；
       `consumed = isinstance(component, Clickable) and component.click(row, col)`；
     - 清 `_press`；返回 `consumed`（供宿主 invalidate）。
  5. release 不静止 / 非左键 / wheel：`False`。
- `_update_hover(x, y)`：
  - `hit = tui.hit_test(x, y)`；无 hit → 目标 `None`；有 hit → `descend(hit.block.component, hit.row, hit.col)`
    得到 `(component, row, col)`。
  - 与当前 `_hovered` **同一组件**：若它实现了 `hover_at`，调 `hover_at(row, col)`（可能换了行），
    以返回值决定是否变化；否则无变化。
  - 换了组件：旧组件（若有）`hover = False`，并 `hover_at(-1, -1)`（若实现）；
    新组件 `hover = True`（若 `isinstance(Hoverable)`），并 `hover_at(row, col)`（若实现）。
    `_hovered = component`；返回是否「渲染会变」。
  - 变化时由 `handle` 返回 `True`，宿主自行 `invalidate()`（`Pointer` 不直接调 `tui.invalidate()`，
    保持与 `gesture`/`chrome` 相同的「消费即由宿主重绘」契约；若更省事也可在**变化时**直接
    `tui.invalidate()`，二选一，docstring 写明并保持一致）。
- `clear()`：旧 hover 组件置 `hover=False` + `hover_at(-1,-1)`，清 `_hovered` / `_press` / `position`。
- docstring 写清三段契约：**要 hover 必须 `TUI(hover=True)`（1003）**；`handle` 不消费 press/release
  （拖选归 `gesture`）；dispatch order 由宿主决定（见 `docs/COMPONENTS.md` 本波更新）。
- 验证（`tests/test_pointer.py`，全部用 `HeadlessScreen` + `ScriptedKeys` 离线驱动）：
  - motion(no button) 进入 `Button` → `button.hover is True`，`pointer.hovered is button`，返回 `True`；
  - motion 离开到空白 → 旧 `hover is False`，返回 `True`；同一格再 motion → 返回 `False`（零变化）；
  - 按住左键 motion → 不更新 hover、清待定；press+release 同格 → `click` 派发；
  - 有 `ring` 时点击包在 `Padding` 里的 `Select` → 聚焦/激活落在 `Select`；
  - 点空白 → 返回 `False`、不抛。

### T4 `app.py`：`TUI.hit_component`

- 新增：
  ```python
  def hit_component(self, x: int, y: int) -> tuple[Component, int, int] | None:
      """The deepest interactive component owning a cell, with its own coords.
      `hit_test` resolved to the block; this descends through every
      `Container.child_at` and returns the leaf."""
  ```
  实现：`hit = self.hit_test(x, y)`；`None` → `None`；否则 `descend(hit.block.component, hit.row, hit.col)`。
- `hit_test` docstring 补一句「要叶子用 `hit_component`」。
- 验证：`tests/test_app.py` 追加一条（`Column([Select, Tree])` 一个 block，`hit_component` 分别命中两者）。

### T5 `widgets/`：`Button` / `Checkbox` / `Link`

- **`Button(Themed)`**（`widgets/button.py`）：`__init__(label, *, style=None, hover_style=None,
  focus_style=None, theme=None, focused=False)`；字段 `label: str`、`hover: bool`、`focused: bool`、
  `chosen: bool | None`。
  - `render(width)`：单行；文本 ` f" {label} "`，基础样式取 `style or theme.accent`，
    `hover` 时 `merge(hover_style or theme.hover)`，失焦/聚焦用 `focus_style or theme.cursor` 区分
    （细节由实现定，但必须**肉眼可辨**且一行 `fit(width)`）。
  - `click(row, col) -> bool`：任意格 `True`，置 `chosen = True`。
  - `activate() -> bool`：同上（`False` 从不返回——按钮总有主操作）。
  - `Hoverable`（`hover`）+ `Focusable`（`focused`）+ `Clickable` + `Activable`。
- **`Checkbox(Themed)`**（`widgets/checkbox.py`）：`__init__(label, *, checked=False, theme=None,
  focused=False)`；字段 `checked: bool`、`hover`、`focused`、`chosen: bool | None`。
  `activate()` / `click()` 翻转 `checked` 并置 `chosen = checked`；render 用 `[x]`/`[ ]` 前缀 + label，
  hover/focus 样式同 Button。
- **`Link(Themed)`**（`widgets/link.py`）：`__init__(text, *, style=None, hover_style=None, theme=None)`；
  字段 `text`、`hover`、`chosen: bool | None`。render 用主题 `link` 样式（下划线），hover 时 `merge`；
  `click(row, col)` 置 `chosen = True`；`Hoverable + Clickable`（不 `Activable`——链接不是焦点主操作）。
- 三者都遵守 D1：无回调，宿主读 `chosen` 一次清一次。
- 加进 `widgets/__init__.py`。

### T6 既有组件的 `hover_at`

给下列组件加 `hover_at(row, col) -> bool`（组件级 `hover` 也一并实现，`Hoverable`），
**只在 hover 状态下改变渲染**（新增一个 `_hover_row`/`_hover_index` 私有字段，默认 `None`，
加进 `__slots__`；`row < 0` → 清空）。样式统一：在目标行/标签的现有样式上 `merge(theme.hover)`。

- `Select` / `Autocomplete` / `Confirm`：映射到可见行 → 数据行下标，渲染该行时 merge hover。
- `Tabs`：映射到标签下标（复用 `click` 的段宽算术），该标签 merge hover。
- `Tree`：映射到可见节点行，该行 `cursor_style` 之上再 merge hover。
- `Table`：映射到数据行下标，该行 `selected_style` 之上再 merge hover。
- `Input` / `Editor`：只实现组件级 `hover`（整块 merge hover），不做格级。
- **不改**任一组件现有的 `click` / `move` / `activate` 行为；`hover_at` 与它们互不干扰。
- 验证（`tests/test_widgets_*` 追加）：`select.hover_at(2, 0)` 后该行渲染含 `theme.hover` 的样式；
  `hover_at(-1, -1)` 后回到改前字节（**逐字节**对比 `render` 输出）。

### T7 `__init__.py`：导出新面

- root 导出 `Pointer`、`Button`、`Checkbox`、`Link`（`__all__` 分组顺序不变）。
- 更新模块 docstring 的层级描述（加 pointer tier 与新原语）。
- 验证：`python -c "from mocode_tui import Pointer, Button, Checkbox, Link"` 干净。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → 只增不减（贴 before/after 与本波新增测试文件名）。
2. `uv run python -c "from mocode_tui import Pointer, Button, Checkbox, Link; print('ok')"` → `ok`。
3. hover 探针（贴输出）：motion 进/出/同格三态、`hovered` 身份、返回 `True/False` 序列。
4. 点击下钻探针（贴输出）：`Padding(Select)` 与 `Column([Select, Tree])` 两种包法，
   截图 `hit_component` 的命中结果与 `ring.click` 后的焦点对象。
5. 1003 字节证据：贴 `enable_mouse_tracking(hover=True)` 与默认的原文；`HeadlessScreen(hover=True).enter()`
   含 `1003h`。**默认输出与改前逐字节一致**（framebench hash 不变）。
6. `hover_at` 归零证据：对 `Select`/`Tabs`/`Tree`/`Table` 各贴 `hover_at(-1,-1)` 前后 `render` 字节相等。
7. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0（旧 demo 未改，仍应跑通）。
8. 真机项（悬停观感、1003 事件代价）→ 无法执行，列「lead 终验项」。

## 禁触清单

- `chat/`（W3 的活）
- `examples/`（W5 的活；本波只跑验收）
- `core/theme.py` 的字段删改（W3 的活；本波只**读** `Theme.hover`）
- 组件的 `render` 输出（除 `hover`/`hover_at` 新分支的「未 hover 时零 diff」）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条命令 + 关键输出行 + pytest 数）/
hover 三态探针 / 下钻点击探针 / 1003 字节证据 / `hover_at` 归零字节证据 /
行为变化 A/B（hover 相关渲染的改前→改后） / framebench hash 证据 /
偏差与取舍 / 未决问题 / 真机手测：未执行（lead 终验）。

遇到阻塞（1003 影响既有序贯、`hover_at` 需要改 `click`、`isinstance` 误判、hash 变化）：
**停下上报，不越界自救**。
