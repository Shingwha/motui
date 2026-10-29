# W4b · Choice / Navigation 迁移

> 分支 `w2.1.2-w4b-choice-nav`；起点 main @ `ae2e88d`（W4a + CursorWidget 扩展）。
> 写入范围：`src/motui/widgets/{choice,autocomplete,combobox,menubar,list,table,
> tree,tabs,navlist,strip}.py`、`tests/widgets/{test_choice,test_autocomplete,
> test_combobox,test_menubar,test_navigation,test_data}.py`、
> `tests/widgets/test_contract_choice_nav.py`（新）、`tests/test_invariants.py`、
> `src/motui/demo/sections/components.py`、`src/motui/demo/sections/gallery.py`。
> 最高约束：**W4b 结束时 semantic golden 的 9 个场景行文本与 SGR 都不变**。
> W4c 在 W4b 合并后单独派工（两波共用 demo 文件，串行）。

## 目标

把 Choice（Select 族）和 Navigation（Tabs/MenuBar/NavList/List/Table/Tree）
迁到 `CursorWidget`/`ResultWidget`：统一 `index`/`selected`/`marked`，
`activate`/`toggle`/`select`/`move`，`take` 返回值，`open` 属性，
`CURSOR_KEYMAP`/`TREE_KEYMAP`，删除死键位和方言动作名。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §0–§7 →
  `handoff/W4a-deepseek-v4.1-flash.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：

```bash
uv run pytest -q tests/widgets/test_choice.py tests/widgets/test_autocomplete.py tests/widgets/test_combobox.py tests/widgets/test_menubar.py tests/widgets/test_navigation.py tests/widgets/test_data.py
uv run pytest -q -p no:cacheprovider
uv run python tools/semantic.py --check
```

- 基线事实：1737 tests；semantic 9/9；`api.py --check` 243 names match；
  `tools/api-2.1.txt` 由 lead 独占。
- 稳定区（勿重读）：`widgets/base.py`（W4a + CursorWidget 扩展已验收）、
  `widgets/action.py`、`app/focus.py`、`kernel/`、`widgets/layout.py`。
- W4a 已提供：`CursorWidget`（`index` 可读写、`index` setter 走 `select`、
  `_cursor_enabled` 钩子、通用 `on_key`、`_entry_count/_entry_at/
  _cursor_disabled/_cursor_wraps/_page_size` 钩子）、`ResultWidget`
  （`_emit`/`_clear_result`/`take`）、`CURSOR_KEYMAP`、`Keymap`。
- 已知约束：
  - `Select` 的 `commit` 参数本波删除；移动/选择只清 pending，不写 pending。
    Form 的值提取用 `selected`，不依赖 `take`。
  - `Select` 的 `window` 参数保留（菜单 top-stick vs 数据视图 center）。
  - `Table` 的“未产生光标前不画 cursor”渲染行为要保留：内部
    `_cursor_armed` 标志；`index` 对外始终是 int（空表 0），
    `selected` 始终返回 index 对应的行；`select/move/click/index setter`
    才 arm。这样 components 的 golden 不变。
  - `Tree` 的 `_cursor` 名字与基类 `CursorWidget._cursor` 冲突；删除自己的
    int `_cursor`，用基类属性 + `_visible()` 计算。
  - `LabelStrip` 也是 CursorWidget：删除 `_index`/`select`/`move`/`_cursor()`，
    使用基类 `index` 和钩子。
  - 动作名统一九个；`Tree` 覆盖 `open`/`close`；`prev/next` 一律返回
    `move()` 的真实结果（端点 False）。
  - `enter` 不再由组件 keymap 绑定；`activatable` 的 enter/space 由焦点层
    回退。直接 `on_key(key("enter"))` 将返回 False（测试改为 `activate()` 或
    走 `FocusManager`）。
  - `Tabs`/`MenuBar`/`NavList` 增加 `activate()`/`take()`；
    `Table.take()` 返回行对象（不是索引）。
  - `TreeNode.expanded` → `open`；`Tree.root_nodes` → `nodes`；
    `Tabs.tabs` → `items`；`RadioGroup.labels`/`CheckboxGroup.labels` 删除。

## 工单（按序执行，每项一个 commit）

### T1 LabelStrip / Tabs / MenuBar

- `strip.py`：`LabelStrip(CursorWidget)`；删除 `_index` slot、`_cursor()`、
  `select`、`move`；`_entries` 保持子类钩子；`_entry_count` =
  `len(self._entries)`，`_entry_at` = `entries[index]`，`_cursor_disabled` =
  `self._disabled_items`，`_cursor_wraps` = False。`on_click` 用
  `self.select(index)`；`on_hover` 不变；`_layout` 用 `self.index`。
- `tabs.py`：构造 `Tabs(items, *, index=0, glyphs=GLYPHS, disabled_items=(),
  disabled=False, theme=None, styles=None)`；`self.items`；`activatable=True`；
  `activate()` 在 disabled/空/disabled 行时 False，否则
  `_emit(self.items[self.index])`；`keymap = Keymap(CURSOR_KEYMAP)`；删除
  `on_action`/`on_key` 的本地实现（用基类）。
- `menubar.py`：构造 `MenuBar(items, *, ...)`；`activate()` 同上
  （pending 是 label 字符串）；`take` 用基类；`keymap = Keymap(CURSOR_KEYMAP)`；
  `activatable=True`。`ContextMenu` 的构造见 T2。
- 验证：`uv run pytest -q tests/widgets/test_navigation.py tests/widgets/test_menubar.py`。

### T2 Select 族

- `choice.py`：
  - `Select(CursorWidget)`：删除 `_index`/`_cursor()`/`select`/`move`/`home`/
    `end`/`_edge`/`on_action`/`on_key`/`take`/`_commit`；保留 `on_click`/
    `on_hover` 的几何映射，`on_click` 调 `self.select(target)`（不 emit）；
    `_entry_count` = `len(self._rows())`，`_entry_at` = `rows[index]`，
    `_cursor_disabled` = `disabled_items`，`_cursor_wraps` = `wrap`，
    `_cursor_enabled` = `not disabled`；`activate()` 在 disabled/空/
    disabled 行时 False，否则 `_emit(self._chosen_of(self.selected))`；
    `toggle()` 只在 `_multi` 时翻转 marks 并 `_sync_result()`；`selected`
    继承（返回 Option）。
  - 删除 `commit` 参数和 `_commit`；`window` 保留。构造尾部顺序：
    `options, *, title, max_rows, wrap, window, glyphs, disabled,
    disabled_items, theme, styles`。
  - `MultiSelect`：`keymap = Keymap({**CURSOR_KEYMAP, "space": "toggle"})`；
    `_sync_result` 仍用 `_emit(values)`（空列表用 `_clear_result()` 而不是
    `_emit(None)`，避免“无选择”被当成合法结果）。
  - `RadioGroup(options, ...)`：删除 `labels` 公开属性（内部 `_labels` 或
    直接用 `[o.label for o in options]`）；不再传 `commit=True`；
    `selected` 继承返回 Option（不再是 str）；`index` setter 走基类。
  - `CheckboxGroup(options, ...)`：同上；`on_click` 先 `self.select(target)`
    再 `self.toggle()`。
- `autocomplete.py`：构造尾部 `max_rows, wrap, glyphs, theme, styles`；
  `on_key` 先处理可打印字符/编辑键，其余调 `super().on_key(event)`；
  `activate` 继承。
- `combobox.py`：`open` 改为可读写 bool property；删除 `is_open`、
  `open()`、`close()`；`toggle()` 翻转 open 并返回是否变化；`activate()`
  关闭时打开并返回 True，打开时选中项 `_emit(value)`；`keymap` 保留自身
  编辑/下拉键；`take` 继承。构造尾部 `max_drop_rows, glyphs, theme, styles`。
- `menubar.py` 的 `ContextMenu`：删除 `**kwargs`；构造
  `ContextMenu(options=(), *, title="", max_rows=8, glyphs=GLYPHS,
  theme=None, styles=None)`；内部用 `window=False`。
- 验证：`uv run pytest -q tests/widgets/test_choice.py tests/widgets/test_autocomplete.py tests/widgets/test_combobox.py tests/widgets/test_menubar.py`。

### T3 List / Table

- `list.py`：`List(CursorWidget)`；删除 `_index`/`_cursor()`/`move`/`home`/
  `end`/`on_action`/`take`/`_current`；钩子 `_entry_count=len(items)`、
  `_entry_at=items[index]`、`_cursor_disabled=disabled_items`、
  `_cursor_enabled=not disabled`；`activate()` 用 `self.selected`（enabled
  才 emit）；`toggle()` 翻转 mark（不 emit）；`keymap =
  Keymap({**CURSOR_KEYMAP, "space": "toggle"})`；`on_key` 保留 prefix_jump，
  其余 `super().on_key`；`on_click` 调 `self.select(...)`。
- `table.py`：`Table(CursorWidget)`；构造
  `Table(rows, *, headers=(), aligns=None, glyphs=GLYPHS, grid=None,
  disabled=False, disabled_items=(), theme=None, styles=None,
  cell_wrap=WrapMode.WORD, max_col_width=40, min_col_width=3)`；
  `self.headers = list(headers)`，`self.rows = [list(row) for row in rows]`。
  - 钩子：`_entry_count=len(rows)`、`_entry_at=rows[index]`、
    `_cursor_disabled=disabled_items`、`_cursor_enabled=not disabled`。
  - `index` 对外 int（空表 0）；保留内部 `_cursor_armed`：
    `select`/`move`/`on_click`/index setter 置 True；`render` 只在 armed
    时画 cursor band；`selected` 始终返回行。
  - `activate()`：armed 且 selected 非 None 且行 enabled 时
    `_emit(selected)`；否则 False。
  - `take()` 返回行对象（继承）；删除 `_pending`/`take`。
  - `toggle()` 翻转 mark（不 emit）；`keymap =
    Keymap({**CURSOR_KEYMAP, "space": "toggle"})`；`on_key` 用基类。
  - `on_click` 映射到 data row 后 `self.select(data_row)`；保留
    `sort_by`/`set_widths`/`header_lines`/`header_line`/`_last_layout`。
- 验证：`uv run pytest -q tests/widgets/test_data.py`。

### T4 Tree

- `tree.py`：`TreeNode(label, children=(), *, open=False, disabled=False)`；
  所有 `expanded` 改 `open`。`Tree(nodes=(), *, indent=2, glyphs=GLYPHS,
  disabled=False, theme=None, styles=None)`；`self.nodes`。
- `Tree(CursorWidget)`：删除自己的 int `_cursor`；钩子基于 `_visible()`：
  `_entry_count=len(visible)`、`_entry_at=visible[index][0]`、
  `_cursor_disabled={i for i,(n,_,_) in ... if n.disabled}`、
  `_cursor_enabled=not disabled`、`_cursor_wraps=False`。
- `keymap = Keymap({k:v for k,v in CURSOR_KEYMAP.items() if k not in
  ("left","right")} | {"left": "close", "right": "open"})`。
- `activate()`：选中节点存在、enabled、有 children 时翻转 `open` 并
  `_emit(node)`；叶子/disabled 返回 False。`toggle()`：只翻转 `open`，不
  emit；`on_action("open"/"close")` 调 `_fold(True/False)`；删除
  `on_action` 的方言名 `expand`/`collapse`（内部 `_fold` 保留）。
- `filter`/`jump` 保留；filter 改变后把 cursor 归零（`self._cursor.index=0`）。
  `on_click` 用 `self.select(pos.y)`；`on_hover` 不变。
- 验证：`uv run pytest -q tests/widgets/test_data.py tests/widgets/test_navigation.py`。

### T5 Demo / invariants / 契约测试

- `demo/sections/components.py`：`pick = self.table.take()` 现在返回行对象；
  改为 `if pick is not None: self.toast(f"picked {pick[0]}", "info")`。
- `demo/sections/gallery.py`：`TreeNode(..., expanded=True)` → `open=True`。
- `tests/test_invariants.py`：`TreeNode(..., expanded=True)` → `open=True`；
  `Table([...], [...])` 若存在改为 `Table(rows, headers=...)`；
  `RadioGroup`/`CheckboxGroup` 的 `labels` 相关不变（构造已用位置 options）。
- `tests/widgets/test_contract_choice_nav.py`（新）：按 `ref/interfaces.md`
  §10 覆盖 Choice/Nav 的构造签名、状态、动词、take、keymap、open。
- 验证：`uv run pytest -q tests/widgets/test_contract_choice_nav.py tests/test_invariants.py tests/demo`。

## 验收

1. 全量 `uv run pytest -q -p no:cacheprovider` 全绿（贴用例数/失败项）。
2. `uv run ruff check .`、改动文件 no-exclude ruff、`pyright`、`lint-imports`
   全绿。
3. `uv run python tools/semantic.py --check` 全绿（硬门槛：行文本和 SGR 都
   不变）。如果 Table 的 `_cursor_armed` 做到了，components/gallery 不应变。
4. `uv run python tools/framebench.py` 的 `render-hash` 不变。
5. `api.py --check` 会因构造签名变化失败；贴差异，不改快照。

## 禁触清单

`widgets/base.py`、`widgets/action.py`、`widgets/layout.py`、`widgets/canvas.py`、
`widgets/pixel_canvas.py`、`widgets/drawing.py`、`widgets/text.py`、
`textfield.py`、`form.py`、`dialog.py`、`collapsible.py`、`indicators.py`、
`markdown/`、`app/`、`kernel/`、`docs/`、`tools/`、`pyproject.toml`。
`handoff/W4b-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W4b-<agent>.md`：每个家族的钩子实现、`_cursor_armed` 的 Table
细节、ComboBox 的 open/activate 规则、Tree 的可见行/折叠规则、给 W4c 的
迁移提示、api 差异。

## 最终报告

同 W1 模板。
