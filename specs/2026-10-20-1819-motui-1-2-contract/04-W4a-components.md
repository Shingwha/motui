# W4a · 组件结果契约、action/choice/input/modal 与 P0
> 分支 `w4a-components`；前置：W3 已合并 @ `1c7069f`；写入范围见下。
> 深读：`00-overview.md` D5/D9、`ref/interfaces.md` §3、`docs/CONTRACT.md` §5。

## 目标

把组件的一次性结果从公开的 `chosen` 迁到 `take_result()`，统一 cursor/activation 词汇；修掉组件层的 P0；
把 `Dialog`/`Collapsible`/`ComboBox` 变成真正的 `Container`；完成 action/choice/textfield/dialog/indicators
家族的契约。**W4b 继续 List/Table/Tree/Tabs/NavList/layout/decor/rows 与 RowBands。**

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §2/§3 → `handoff/W3-values.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
  期望：1742 passed / 2 skipped；11 页 match；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
- 稳定区（勿重读）：`kernel/events.py`、`keys/**`、W2/W3 的 driver/frame/value semantics、
  `widgets/{list,table,tree,tabs,navlist,layout,decor,rows,delegate}.py`（W4b）。
- W3 已知约束：`Text.render` 无组件 memo；`Block.rows` 唯一缓存；`ScreenLayout`/`Theme` 表不可变；
  `highlight(..., *, style=...)`；`Pane` 可变。

## 决策（照抄执行）

- `Resultful.take_result() -> object | None`：读取并清空；组件不再公开 `chosen`。
- `Controller.handle(event) -> bool`：`True` = consumed（本波只加协议，不重写 interaction tier）。
- `Radio` → `RadioGroup`，`CheckGroup` → `CheckboxGroup`；无 alias。
- cursor 词汇：`index`、`select(index) -> bool`、`move(delta) -> bool`、`home()`、`end()`、
  `activate() -> bool`、multi 加 `toggle() -> bool`。
- 样式名：`Select.cursor_text_style`（原 `selected_style` 文字样式）；`RadioGroup`/`CheckboxGroup`
  用 `active_style`（原 `selected_style` 行带）；`Input`/`Editor` 用 `caret_style`（原 `cursor_style`）。
- `disabled`：action/choice/form 控件加 `disabled: bool`；`Select` 家族再加 `disabled_items: Iterable[int]`；
  `Input`/`Editor`/`TextBuffer` 加 `read_only: bool`。
- `Option.description`：`RadioGroup`/`CheckboxGroup` 不渲染描述；非空描述直接 `ValueError`，不静默丢弃。
- `on_activate` 回调本波不做；`take_result()` 是唯一结果门。

## 工单（按序执行；HEAD 全绿即可，commit 粒度不限）

### T1 `kernel/block.py` + `kernel/__init__.py`：协议

- 增加 `Controller`（`handle(event) -> bool`）和 `Resultful`（`take_result() -> object | None`），
  runtime_checkable；kernel facade 导出。
- `kernel/events.py` 已落地；不要改事件模型。

### T2 `widgets/action.py`：`Button` / `Checkbox` / `Link`

- 三者删除 `chosen`，实现 `take_result()`；`activate`/`click` 写 pending，`take_result` 读一次并清空。
- 三者加 `disabled: bool = False`；disabled 时 `activate/click` 返回 `False`，渲染用 `disabled_style`
  （默认 theme.dim）。
- `Checkbox` 对齐 Button 的 style 面：`style`/`hover_style`/`focus_style`/`disabled_style`；
  加 `mark_pair: tuple[str,str] = (glyphs.MARKED, glyphs.UNMARKED)`，渲染不再硬编码 `[x]/[ ]`。
- `Link` 实现 `Focusable`（`focused: bool`，可写）与 `Activable`（`activate() -> bool`），
  加 `focus_style`/`disabled_style`/`disabled`；`click`/`activate` 写 pending。
- 三者的 `revision()` 覆盖 disabled、mark_pair、样式。
- 测试：`take_result` 读一次清空、disabled 拒绝、Checkbox 自定义 mark_pair、Link 键盘激活。

### T3 `widgets/choice.py`：选择家族

- `Select`：
  - 删除 `chosen`，实现 `take_result()`；`activate`/`toggle`/commit 写 pending。
  - 加 `select(index) -> bool`、`home()`、`end()`；`move/click/activate/toggle` 返回 consumed/moved 语义不变。
  - `disabled: bool = False` + `disabled_items: Iterable[int] = ()`；`move` 跳过 disabled 项，
    `click`/`activate`/`toggle` 拒绝 disabled 项；`disabled_style` 渲染。
  - `selected_style` → `cursor_text_style`；加 `active_style` 作为行带？`Select` 当前没有 `selected_style` band；
    保持文字样式命名。
  - `marker` 默认 `glyphs.MENU_CURSOR`；`mark_pair` 保持。
  - `marked` 只在 `multi=True` 时暴露/使用；`multi=False` 时 `toggle` 返回 `False` 且不保留 mark 状态。
- `Radio` 改名 `RadioGroup`：
  - `take_result()` 返回选中的 value（label 或 Option.value）。
  - `selected` 返回 label；`selected_style` → `active_style`。
  - `click`/`activate`/`move` 继续 commit；`disabled`/`disabled_items` 生效。
  - 构造时对非空 `Option.description` 抛 `ValueError`。
- `CheckGroup` 改名 `CheckboxGroup`：
  - **修 P0**：`click(row,col)` 必须移动 cursor **并 toggle 该行 mark**；不能只继承 `Select.click`。
  - `take_result()` 返回 marked values 列表（无 mark 时 `None`）。
  - `selected_style` → `active_style`；非空 description 抛 `ValueError`。
  - `disabled`/`disabled_items` 生效。
- 三者的 `revision()` 覆盖 disabled/disabled_items/mark_pair/marker/样式。
- 测试：`CheckboxGroup.click` 真的 toggle；`RadioGroup`/`CheckboxGroup` 的 `take_result`；
  disabled 项跳过；非空 description 抛错；`select/home/end`。

### T4 `widgets/autocomplete.py` + `widgets/combobox.py`

- `Autocomplete`：
  - `options` 改为位置参数（与 Select/ComboBox 一致）。
  - 过滤改为 case-insensitive。
  - `set_query` 清空 `_hover_row`（修 P0）。
  - 继承 `take_result`。
- `ComboBox`：
  - 删除 `chosen`，实现 `take_result()`。
  - **修 P0**：`handle` 打开时收到 `PasteEvent` 不得读 `.key`；Paste 交给 `input.handle`。
  - 实现 `Container.child_at(row,col)`：把输入行的 cell 映射到 `self.input`（`render` 记住 last width）。
  - 实现 `Focusable`（`focused` 委托 input）、`Clickable.click`（委托 input）、`Revisioned.revision`。
  - `revision()` 覆盖 input revision、is_open、pending result、options/max_rows。
  - 测试：打开时 Paste 不崩；child_at 映射；focus/click 委托；take_result。

### T5 `widgets/textfield.py` + `widgets/textbuf.py` + `kernel/lines.py`

- `Input(text="", *, ...)`：新增 `text` 构造参数；`_TextField.text` 增加 setter（写 buffer、清 undo）。
- `Editor(text="", *, ...)` 保持；两者 `cursor_style` → `caret_style`。
- `Input`/`Editor`/`TextBuffer` 加 `read_only`；`handle` 在 read_only 时返回 `False`，不修改 buffer。
  直接编辑方法（insert/backspace/...）按“程序化编辑仍允许”处理并在 docstring 说明；若选择全部拒绝，
  在报告里写明理由。
- `Text`：删除 `chosen`，实现 `take_result()`；`click` 写 pending；`revision` 不包含 pending。
- 测试：Input 构造 text、text setter、read_only 拒绝 handle、caret_style 命名、Text take_result。

### T6 `widgets/dialog.py` + `widgets/collapsible.py`

- `Dialog`：
  - 删除 `chosen`，实现 `take_result()`。
  - `focused` 属性改名 `focused_button`（避免被 `Focusable` 协议误判）；`FocusRing` 不应接受 Dialog。
  - 实现 `Container.child_at`：body 区域映射到 `self.body`，按钮行映射到对应 `Button`。
  - 按钮激活走 `Button.activate()` + `Button.take_result()`；dialog 的结果取 `ButtonSpec.value`。
  - `prompt_dialog` 从 `motui.widgets` facade 导出（修 P0）。
- `Collapsible`：
  - 删除 `chosen`，实现 `take_result()`。
  - 实现 `Container.child_at`：title 行归 wrapper，open 时 body 行映射到 `self.body`。
  - 加 `disabled`；disabled 时 activate/click 返回 False。
- 测试：Dialog 按钮激活/点击结果；child_at body/button；Dialog 不被 `isinstance(..., Focusable)`；
  Collapsible child_at 与结果；prompt_dialog facade 导入。

### T7 `widgets/indicators.py` + `widgets/markdown/component.py`

- `Spinner`：
  - 实现 `render(width) -> list[Line]`（`frame + text`，fit）；加 `style`/`theme` 可选；
  - 实现 `Revisioned.revision`（frame/text/style）。
  - 测试：`tui.add(Spinner(...))` 可用，advance 后 revision 变化。
- `Slider`：
  - 删除 `chosen`，实现 `take_result()`；`activate` 写 pending。
  - 加 `disabled`；`minimum`/`maximum`/`step` 改为 property setter，赋值时重新 clamp/snap `value`。
  - `revision()` 覆盖 disabled 与 value。
- `Markdown`：
  - **修 P0**：`revision()` 必须包含 `max_width`、`task_marks`（以及 render 读取的其他可变输入）。
  - 删除 `chosen`，实现 `take_result()`；`click` 写 pending。
  - 测试：改 `max_width` 后 `Block.rows` fresh；task_marks 变化 fresh；take_result。

### T8 facade、demo、文档、测试

- `widgets/__init__.py`：导出 `CheckboxGroup`/`RadioGroup`（删 `CheckGroup`/`Radio`）、`prompt_dialog`；
  `__all__` 排序按现有常量/类/函数规则。
- `tests/test_api_root.py`：同步 widgets facade 名单。
- 全仓迁移本波范围内的 `chosen` → `take_result()`、`Radio`/`CheckGroup`、`cursor_style`、
  `Input(text=...)`；demo 的 forms/modals/actions 页面同步。
- `docs/COMPONENTS.md`/`README.md` 只改与本波冲突的条目；W7 重写整篇。
- 跑 `## 验收`，写 `handoff/W4a-components.md`。
- 不 merge / push / tag。

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；总数 ≥ 1742 + 新增
2. `uv run python tools/golden.py --check`：11 页全 match（本波不应移动渲染；若有意移动，停下报告）
3. `uv run python tools/framebench.py`：exit 0；render-hash 不变（贴值）
4. `uv run python -m motui < /dev/null`：exit 0
5. `uv run python -m motui --pages`：exit 0
6. P0 测试全过：CheckboxGroup.click、ComboBox Paste、Markdown max_width、Spinner.render、
   Input(text=)、prompt_dialog facade、Autocomplete hover。
7. `grep -rn "\.chosen\|CheckGroup\|\bRadio\b\|cursor_style" src/motui/widgets/{action,choice,autocomplete,combobox,textfield,dialog,collapsible,indicators}.py src/motui/widgets/markdown/component.py src/motui/kernel/lines.py`：
   零命中（历史文档/测试除外）
8. `git diff --stat main...HEAD`：范围 = 本工单写范围并集，无 golden 变化

## 禁触清单

- 禁改：`widgets/{list,table,tree,tabs,navlist,layout,decor,rows,delegate}.py`（W4b）、
  `kernel/{frame,viewport,painter,selection,theme,style,block?}.py`（block.py 只允许加协议）、
  `app.py`、`keys/**`、`kernel/events.py`、`tests/golden/**`、`pyproject.toml`、`uv.lock`、`docs/CONTRACT.md`。
- 禁加：兼容 alias、旧名 re-export、deprecated 转发。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。
- 遇到阻塞：写清阻塞点后停止，不越界自救。

## 交接包

完成后写 `handoff/W4a-components.md`（60–80 行，A/B/C）：

- A：`git diff --stat`、新增/变更公开签名、基线真实结果
- B：与 spec 的偏差、踩坑、W4b 必须遵守的隐式约束、未决问题
- C：关键文件:行号、commit、稳定区

## 最终报告

工单状态表（T1–T8）/ commit 清单 / 自测真实输出 / 组件 API 变更清单 / 测试改动清单 /
P0 修复证据 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
