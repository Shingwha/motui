# W3b2 · 数据视图族迁移到树、Cursor 与 keymap

> 分支 `2.0/w3b2-views`；前置：W3a 已合并（`b5e1997`）；写入范围：`src/motui/widgets/{list,tree,table,choice,navlist,tabs,menubar,rows,strip,scroll}.py`、对应 `tests/widgets/*`、`tools/api-2.0.txt`
> 权威：`ref/source/03-interaction.md` §3–6、`06-widgets.md` §3–4、`10-waves/W3-tree-interaction.md` §4.1–4.6

## 目标

把数据视图/菜单/标签族迁到 W3a 基座，**行为 1:1、字节不变**：

1. `Cursor` 只有一套：所有数据视图用 `widgets.base.Cursor`；删除 `strip.ClampedCursor`；
2. `keymap → action`：每族声明类级 `keymap`；`on_key` 查表 → `on_action`；实例可 rebind；
3. 能力属性：`focusable/clickable/hoverable/activatable` 按语义设置；
4. hooks：`on_key/on_click(Pos)/on_hover(Pos|None)/on_drag(Pos,phase)/on_action`；旧 `handle/click/hover_at/drag` 用薄别名到 W3b3；
5. `take()` 落地（`take_result` 别名保留）；
6. 现有测试与 57 byte/semantic golden 不变。

**本波结束：1422+ 用例绿；golden/hash 不变；`ClampedCursor` 删除；`lst.keymap["j"]="next"` 生效；各视图 `on_action` 行为与旧按键 1:1。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W3a-base.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1422 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 迁移模式：
  - 类级 `keymap`：例如 List：`{"up":"prev","down":"next","home":"first","end":"last","pgup":"page_prev","pgdn":"page_next","enter":"activate"}`；`on_key`：
    ```python
    action = {**type(self).keymap, **getattr(self, "_keymap_override", {})}.get(event.key)
    if action is not None: return self.on_action(action)
    return self.on_mouse(event) if isinstance(event, MouseEvent) else False
    ```
    实例 rebind：`lst.keymap` 若是类属性，直接 `lst.keymap["j"]="next"` 会写穿类表；提供实例级 `_keymap` dict 或 property，使 `lst.keymap["j"]=...` 只影响实例。推荐 `self._keymap = dict(type(self).keymap)` 在 `__init__`，并用 property `keymap` 返回它。
  - `on_action(name)`：调用原 `move/select/activate/toggle` 等方法；返回 bool。
  - `on_click(pos)`：`pos.y, pos.x` 调原 click；`on_hover(pos)`：`pos is None` → `hover_at(-1,-1)`，否则 `hover_at(pos.y,pos.x)`。
  - 旧 `handle/click/hover_at` 用薄别名（`handle = on_key` 或 wrapper）保持 App 兼容；W3b3 删除。
  - `take()` 返回原 `take_result()`；`take_result` 别名保留。
- 现状：
  - List/Tree/Table/Choice/NavList/Tabs/Menubar 各自有 cursor 逻辑；`widgets/cursor.py:Cursor` 已存在并被部分使用；`strip.py:ClampedCursor` 是重复实现。
  - `List` 的 `window: int`、`Select` 的 `max_rows/window` 等参数保持（W4/W5 再改名）。
  - `Tabs`/`Menubar` 的 strip 基座有 `handle` 与方向键逻辑；`Keymap` 目前只在 textfield。
  - `Rows` 是纯展示（Notice/ShortcutBar/StatusLine），只需能力属性（无交互）与 `take`（若有）。
- 已知坑：
  - `keymap` 的实例覆盖不能写穿类字典；用每实例副本。
  - `MenuBar` 的展开/收起、`Tabs` 的 left/right、`Tree` 的展开需要 `on_action` 名称与旧键一一对应；先写 action 测试再删旧 if 链。
  - `Cursor.window` 的 anchor 语义（top/center/bottom）必须与各视图现有窗口一致；`ClampedCursor` 删除前逐个对照。
  - `Table` 的 cursor 是 `_index`（非 Cursor）；迁移时保持 `index`/`move`/`click`/`activate` 行为与 `take` 返回；不要把 `index=None` 的语义改掉。
  - `Select`/`MultiSelect`/`CheckboxGroup`/`RadioGroup` 共享 choice.py；不要改 `Option`/`MarkSet` 语义。
  - `Menubar`/`Tabs` 的 `on_key` 可能同时被 App 的旧 FocusManager 方向键路由；本波保留旧 `handle` 别名，行为不变；W3b3 改路由。
  - `take()` 的 `False`/`None` 两态必须保留（Checkbox/Collapsible 等在 W3b1；本族 `Select` 返回 Option|None，Table 返回 int|None）。
  - 只改交互入口；渲染算法/窗口/memo/revision 不动。
- 不改控件/编辑族（W3b1）、不改 app/focus（W3b3）、不改 kernel/terminal。

## 工单（每族一个 commit）

### T1 List / Select / MultiSelect / CheckboxGroup / RadioGroup
- `list.py`、`choice.py`：
  - 统一 `Cursor`（若尚未）；`keymap` 类表；`on_key`/`on_action`/`on_click`/`on_hover`；能力属性（focusable/clickable/activatable）；
  - `take()`/`take_result` 别名；`on_action("activate")` 调原 activate。
- 测试 `tests/widgets/test_choice.py`、`test_data.py`：action 表、实例 rebind（`lst.keymap["j"]="next"`）、on_click、take None/具体值。
- 验证：`uv run pytest -q tests/widgets/test_choice.py tests/widgets/test_data.py`。

### T2 Tree / NavList
- `tree.py`、`navlist.py`：Cursor 统一；keymap（up/down/left/right/home/end/enter）；on_action（prev/next/expand/collapse/activate）；on_click/on_hover；能力。
- 测试 `test_navigation.py`：展开/折叠 action、click、take。
- 验证：`uv run pytest -q tests/widgets/test_navigation.py`。

### T3 Table
- `table.py`：保留 `_index` 语义或改为 `Cursor`（行为 1:1）；keymap（up/down/home/end/enter）；on_action；on_click/on_hover；能力；`take` 返回行索引。
- 测试 `test_data.py`：action、click、take。
- 验证：`uv run pytest -q tests/widgets/test_data.py`。

### T4 Tabs / MenuBar / ContextMenu / strip
- `tabs.py`、`menubar.py`、`strip.py`：
  - 删除 `ClampedCursor`，统一 `Cursor`；keymap（left/right/up/down/home/end/enter/escape 按族）；on_action（next/prev/activate/open/close）；
  - `LabelStrip.on_key` 迁到新 hook；保留旧 `handle` 别名；
  - 能力属性。
- 测试 `test_menubar.py`、`test_navigation.py`：action、rebind、click。
- 验证：`uv run pytest -q tests/widgets/test_menubar.py tests/widgets/test_navigation.py`。

### T5 Rows / ScrollPanel
- `rows.py`：能力属性（无交互）、`take`（若有）；`on_key` 默认。
- `scroll.py`：`focusable=True`、`clickable=True`（如需）、`on_key`（up/down/page/home/end）与 `on_action`；`scroll_x` action；保留 wheel/drag；`take` 无。
- 测试 `test_rows.py`、`test_scroll.py`：ScrollPanel 的 on_key/on_action 与旧 handle 1:1。
- 验证：`uv run pytest -q tests/widgets/test_rows.py tests/widgets/test_scroll.py`。

### T6 收口
- `grep -rn "ClampedCursor" src` → 0。
- `grep -rn "def handle(" src/motui/widgets/{list,tree,table,choice,navlist,tabs,menubar,rows,strip,scroll}.py` → 0（别名）。
- `tools/api.py --update`；全量门禁。
- 只允许改：`tools/api-2.0.txt`、handoff。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `ClampedCursor` 删除；`Cursor` 只有一套；`lst.keymap["j"]="next"` 生效；on_action 与旧按键 1:1。
5. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。
6. 旧测试只允许为 action/rebind/hooks 增断言，不允许降低原断言。

## 禁触清单

`kernel/**`、`terminal/**`、`app/**`、`widgets/{text,decor,layout,action,collapsible,combobox,dialog,form,indicators,textfield,autocomplete,canvas,base,markdown/**}.py`、`demo/**`、`tests/golden/**`、`tools/{golden,framebench,semantic}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/W3b2-views.md`：A 节给 keymap 表/能力表/Cursor 统一清单/门禁；B 节给 rebind 实现、Table index 语义、strip 合并、W3b3 要删的别名/协议清单、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W3a 事实）/ 探索审计 / 未决问题。
