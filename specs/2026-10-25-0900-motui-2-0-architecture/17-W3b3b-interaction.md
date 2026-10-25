# W3b3b · 交互层收口（协议删除、hooks 全量、take 统一）

> 分支 `2.0/w3b3b-interaction`；前置：W3b3a 已合并（`fe64884`）；写入范围：`src/motui/{kernel/document.py,widgets/**,app/**}`、`tests/**`、`tools/api-2.0.txt`
> 权威：`ref/source/03-interaction.md` §3–11、`10-waves/W3-tree-interaction.md` §5–6

## 目标

完成 W3 的收口，**行为 1:1、字节不变**：

1. 删除能力协议 `Clickable/Activable/Focusable/Hoverable/Container/Controller/Resultful`（保留 `Component`/`Revisioned`/`Overlay`/`Scrollable`）；
2. 所有能力判断改为属性（`focusable/clickable/hoverable/activatable/focus_scope`）；
3. Pointer/Gesture/Modal/Find/Overlays/Palette/Scrollbar 改用 `on_hover/on_click/on_drag/on_key/on_paste/on_action/take`；
4. 删除组件的旧动词别名（`handle/click/hover_at/drag/activate/take_result`）；保留 `TextBuffer.handle`（编辑引擎，非 widget）；
5. `owns_focus` 删除，统一 `focus_scope`；
6. `ScrollPanel.children=[child]`，树覆盖其内容；
7. `_CHILD_ATTRS`/`_walk`/`_looks_interactive`/`set_focus_targets` 全仓 0；
8. widget `def handle(` = 0；能力 isinstance = 0；`take_result` = 0；
9. 现有 1529 用例、57 byte/semantic、hash 不变。

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W3b3a-focus.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1529 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状（全仓 grep）：
  - `def handle(` 15 处（widgets/app）；`take_result` 88 处（含别名/测试）；`isinstance` 144 处。
  - `app/pointer.py` 仍有 3 处能力 isinstance（Hoverable×2、Clickable×1）。
  - `ScrollPanel` 没有设置 `children=[child]`（W3b3a 发现）。
  - `Form`/`ComboBox` 可能仍设 `owns_focus`。
  - W3b1/b2 的旧动词是薄别名，行为本体在 `on_*`/`take`。
- 迁移规则：
  - 能力：`isinstance(x, Clickable)` → `getattr(x, "clickable", False)`；`Focusable` → `focusable`；`Hoverable` → `hoverable`；`Activable` → `activatable`。
  - 容器：`isinstance(x, Container)` → `getattr(x, "child_at", None) is not None` 或 `hasattr(x, "children")`（按调用点语义）。
  - 结果：`x.take_result()` → `x.take()`；`isinstance(x, Resultful)` → `hasattr(x, "take")`。
  - 控制器：`isinstance(x, Controller)` → `hasattr(x, "handle")`（W4 Router 会替换）。
  - Pointer：`component.hover = True/False` + `component.on_hover(Pos(...)|None)`；click → `component.on_click(Pos(x=col,y=row))`。
  - Gesture：`component.drag(row,col,kind)` → `component.on_drag(Pos(x=col,y=row), kind)`。
  - 焦点 scope：`getattr(w, "focus_scope", False)`；删除 `owns_focus`。
- 已知坑：
  - `TextBuffer.handle` 必须保留（它不是 Widget）；`_TextField.on_key` 继续调它。
  - `Modal`/`Pointer`/`Gesture`/`Scrollbar`/`FocusManager` 的 `handle` 是控制器 tier 契约，**保留**；W4 Router 再统一。widget 的 `handle` 必须 0。
  - `take()` 的 `False`/`None` 两态不能混淆；组件测试要保留两条路径。
  - 删除协议后，`kernel/document.py.__all__` 与所有 import 要同步；`tests/test_api.py` 只检查 facade 的 `__all__`，但要跑全量。
  - `ScrollPanel.children=[child]` 会改变 App 的 theme/focus 遍历（之前不到子内容）；这是修复，但可能让某些子组件首次收到 theme/焦点，**不允许改变渲染字节**；若 golden 变，先查是否 theme 默认值问题。
  - 事件类型判断保留 `isinstance(event, KeyEvent)` 等（值/事件判别，不是能力探测）；不要为了计数改坏。
  - 测试大量使用旧动词；用 codemod + 逐文件修复，不要降低断言。
- 不改渲染/布局/滚动/编辑算法；只改交互入口与协议。

## 工单（按序，每步一个 commit）

### T1 删除能力协议与旧别名

- `kernel/document.py`：删除 `Clickable/Activable/Focusable/Hoverable/Container/Controller/Resultful` 定义与 `__all__` 条目；保留 `Component/Revisioned/Overlay/Scrollable`。
- `widgets/base.py`：
  - 删除 `handle/click/hover_at/drag/activate/take_result` 的基类默认；`on_key/on_mouse/on_paste/on_click/on_hover/on_drag/on_action` 默认返回 False；`take` 默认 None。
  - 删除 `owns_focus`；保留 `focus_scope`。
- 全仓组件文件：删除旧别名（`handle = on_key`、`def handle`、`def click`、`def hover_at`、`def drag`、`def activate`、`def take_result`）；确保 `on_*`/`take` 是唯一入口。
- 更新所有 import（app/widgets/tests）到新面。
- 验证：`grep -rn "def handle(" src/motui/widgets` 只剩 `textbuf.py` 的 `TextBuffer.handle`；`grep -rn "take_result" src/motui` = 0。

### T2 Pointer / Gesture

- `app/pointer.py`：能力判断改属性；hover 用 `on_hover`；click 用 `on_click(Pos)`；保留 `handle`（tier）。
- `app/gesture.py`：drag 用 `on_drag(Pos, phase)`；能力判断改属性；`copy_on_select` 用 `take`/`on_selection`（若涉及）。
- 测试 `tests/app/test_pointer.py`、`test_gesture.py`：hover/click/drag 的 Pos 坐标与旧 (row,col) 一致；能力属性生效。
- 验证：`uv run pytest -q tests/app/test_pointer.py tests/app/test_gesture.py`。

### T3 Modal / Find / Overlays / Palette / Scrollbar

- `app/modal.py`、`find.py`、`overlays.py`、`command_palette.py`、`scrollbar.py`：
  - 能力/结果判断改属性/`take`；
  - `take_result` → `take`；
  - `handle` 保留（tier）；
  - 事件路由优先 `on_*`。
- 测试对应 `tests/app/test_{modal,find,overlays,command_palette,scrollbar}.py`。
- 验证：`uv run pytest -q tests/app`。

### T4 ScrollPanel 子树 + Form/ComboBox scope

- `widgets/scroll.py`：`__init__` 设 `self.children = [child]`（`super().__init__` 之后），保持 `child` 属性；`child_at` 不变。
- `widgets/form.py`/`combobox.py`：`owns_focus` → `focus_scope=True`；删除 `owns_focus`。
- `app/focus.py`：scope 判定只用 `focus_scope`。
- 测试：`test_scroll.py` 的 `walk()` 覆盖 child；`test_form.py`/`test_combobox.py` 的 scope 路由；`test_app.py` 的 theme 传播到 ScrollPanel 子内容。
- 验证：`uv run pytest -q tests/widgets/test_scroll.py tests/widgets/test_form.py tests/widgets/test_combobox.py tests/app/test_app.py`。

### T5 测试与全量收口

- 全仓测试把 `click(row,col)` → `on_click(Pos(x=col,y=row))`、`hover_at(row,col)` → `on_hover(Pos(...))`、`handle(event)`（widget）→ `on_key/on_mouse/on_paste`、`take_result()` → `take()`；逐文件修复。
- 删除 `isinstance(..., Clickable/Activable/...)` 断言，改为能力属性断言。
- `tools/api.py --update`。
- 验收 grep：
  - `def handle(` in `src/motui/widgets` → 只允许 `textbuf.py`；
  - `take_result` in `src/motui` → 0；
  - capability `isinstance` → 0（`grep -rn "isinstance(.*Clickable\\|Activable\\|Focusable\\|Hoverable\\|Resultful\\|Controller" src/motui` 为空）；
  - `_CHILD_ATTRS`/`_walk`/`_looks_interactive`/`set_focus_targets`/`owns_focus` → 0（注释除外）。
- 全量门禁。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. 能力协议删除；widget `handle`=0；`take_result`=0；能力 isinstance=0；`owns_focus`=0。
5. `lst.keymap["j"]="next"`、Form/Dialog scope、Pointer/Gesture Pos、`take` None/False 全部通过。
6. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。
7. `isinstance` 总数如实报告（事件/值判别可保留；能力探测必须 0）。

## 禁触清单

`kernel/{cell,layout,frame,hit,overlay,selection,style,glyphs,theme,text,events,keymap,geom}.py`、`terminal/**`、`demo/**`、`tests/golden/**`、`tools/{golden,framebench,semantic}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/W3b3b-interaction.md`：A 节给删除清单/能力表/take 路径/门禁；B 节给 Pointer/Gesture 坐标、scope、ScrollPanel 子树、剩余 isinstance 分类、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W3b3a 事实）/ 探索审计 / 未决问题。
