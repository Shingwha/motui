# W3b3a · 焦点从树推导 + App 树遍历 + keymap 路由

> 分支 `2.0/w3b3a-focus`；前置：W3b1/W3b2 已合并（`ba6d80e`）；写入范围：`src/motui/app/{application,focus,driver}.py`、`src/motui/widgets/base.py`（只加 enter 回退/必要钩子）、`tests/app/{test_app,test_focus,test_driver}.py`、`tests/widgets/test_base.py`、`tools/api-2.0.txt`
> 权威：`ref/source/03-interaction.md` §5–6、`04-runtime.md` §7、`10-waves/W3-tree-interaction.md` §4.3–4.4

## 目标

把焦点与挂载从“注册/反射”切到“树 + 属性 + keymap”，**行为 1:1、字节不变**：

1. 焦点环 = 所有挂载组件树的前序遍历中 `focusable`（或 `focus_scope`）节点；`focus_scope` 节点跳过其子树；
2. `FocusManager` 内部化：不再公开注册 `add/remove`；`App.set_focus_targets` 删除；
3. `App.add/remove/theme` 用 `walk()`，删除 `_walk` / `_looks_interactive`；
4. keymap 路由：焦点 widget 的 `keymap` → `on_action`；未命中再 `on_key`；`enter` 作为 `activatable` 的默认 `activate` 回退；
5. `on_resize` 广播给整棵已挂载树；
6. 现有 1513 用例、57 byte/semantic、hash 不变。

**本波结束：1513+ 用例绿；焦点环前序测试通过；`lst.keymap["j"]="next"` 经 FocusManager 生效；Form scope 路由不变；`_walk`/`_looks_interactive` 删除。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W3b1-controls.md` → `handoff/W3b2-views.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1513 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状：
  - `app/application.py:App.add` 用 `_walk`（属性名遍历）与 `_looks_interactive`（反射）；`App._forget` 同；`set_focus_targets` 公开。
  - `app/focus.py:FocusManager` 注册式，`handle` 里硬编码 up/left/down/right/enter；`click` 用 `isinstance(Clickable/Activable/...)`。
  - W3b1/b2 已在组件上设置 `focusable/clickable/hoverable/activatable/focus_scope`、`keymap`、`on_action`、`on_click`、`on_hover`、`take`；旧 `handle/click/...` 仍是薄别名（W3b3b 删）。
  - `Widget.walk()` 前序、去重；`children` 已由容器设置。
  - `Form.owns_focus=True` 且 `focus_scope=True`（W3b1 保留 owns_focus 兼容）。
  - `TUI.frame.panes` 含所有 pane；`pane.viewport.document.blocks()` 是内容顺序。
- 已知坑：
  - 焦点环必须包含 `focus_scope` 容器本身（Form/Dialog），并跳过其子树；否则现有 `test_app` 的 `targets == (form,)` 会红。
  - 1.x FocusManager 的硬编码 enter 激活要保留：keymap 未命中且 `event.key == "enter"` 且 `focused.activatable` → `on_action("activate")`。
  - 1.x 方向键硬编码：W3b2 已给数据视图 keymap；Input/Editor 自己处理；不要给未绑定方向的组件加默认箭头（会抢 host 键）。
  - `focus_scope` 容器的 `on_key` 自己路由子字段；外层只把键交给 scope 的 `on_key`，不要walk 到子字段。
  - `on_resize` 广播要给整棵树（含 scope 子树），不消费事件；ResizeEvent 仍交给后续 handler/host。
  - `App.add` 的 theme 传播要包含非 Widget 组件（它们没有 theme）；只对 `hasattr(w, "theme")` 的 Widget 设置。
  - `App.remove` 后焦点若指向被移除子树，要清空/重算；`FocusManager` 的 target 集合同步。
  - `TUI.document` 只代表主 pane；焦点环要遍历所有 pane + docks。
  - 删除 `set_focus_targets` 会破坏测试/示例；全仓更新到树推导（W4 的 Workspace 会再收口）。
  - 不改 `App.dispatch` 的 handler 顺序（W4 Router）；只在进入 if 链前做 resize 广播，key 路由仍由 FocusManager tier 完成。
- 不改 widgets 的渲染/交互行为；不改 kernel/terminal（除必要的 `Pos` 导入）。

## 工单（按序，每步一个 commit）

### T1 树推导的焦点目标

- `app/application.py` 或 `app/focus.py` 新增私有 `iter_widgets(tui) -> Iterator[Widget]`：
  - 遍历 `tui.frame.panes`（含 docks），每个 `pane.viewport.document.blocks()` 的 `section.widget`；
  - 对每个根组件：若有 `walk()`，`yield from root.walk()`；否则 yield root；
  - 按 `id` 去重。
- `focus_targets(tui) -> tuple[Widget, ...]`：
  - 前序；`focus_scope` 节点：纳入（若它 `focusable` 或 `focus_scope`），跳过其子树；
  - 普通节点：`focusable=True` 才纳入；
  - 保持文档/pane 顺序。
- `FocusManager`：
  - 增加 `sync(targets)`（内部替换 `_targets`；若当前焦点不在新集合，清空并 `on_change(None)`）；
  - 删除公开 `add/remove`（改为私有或直接删）；`targets` property 返回当前集合；
  - `focus/focus_next/focus_previous` 保持；`focus` 仍要求目标在集合内。
- `App.focus/focus_next/focus_previous`：先 `sync(focus_targets(self.tui))` 再操作。
- 测试 `tests/app/test_focus.py`：
  - 前序：Pane 文档 A(Button)+Container(Button,Input) → 目标顺序正确；
  - `focus_scope` 容器只出现自己，子树不出现；
  - 移除/新增组件后目标集合更新；
  - `focus_next` 从空焦点选第一个；wrap 与 clamps 保持。
- 只允许改：`app/focus.py`、`app/application.py`、`tests/app/test_focus.py`。
- 验证：`uv run pytest -q tests/app/test_focus.py`。

### T2 App.add/remove/theme 用 walk

- `app/application.py`：
  - 删除 `_walk` / `_looks_interactive`（模块级函数）。
  - `App.add`：
    - `tui.add(...)` 后，`walked = list(component.walk()) if hasattr(component, "walk") else [component]`；
    - theme：对 `hasattr(current, "theme") and current.theme is None` 的节点设 App theme；
    - focus：`self._focus.sync(focus_targets(self.tui))`（不再手动 add）。
  - `App._forget`：用 `walk()` 收集子树；从 `_components` 移除；`sync` 焦点。
  - `App.set_focus_targets`：删除；测试/示例改 tree。
  - `App.mount/unmount` 控制器的逻辑不变。
- 测试 `tests/app/test_app.py`：
  - 嵌套容器（Row/Panel/Form）的 theme 传播到所有 Widget；
  - 移除父容器后子组件的焦点目标消失；
  - `set_focus_targets` 不再存在（`AttributeError`）。
- 只允许改：`app/application.py`、`tests/app/test_app.py`。
- 验证：`uv run pytest -q tests/app/test_app.py`。

### T3 FocusManager keymap 路由

- `app/focus.py:FocusManager.handle`：
  1. 空焦点 → False；
  2. 事件分派：`KeyEvent` → 先 keymap：
     ```python
     action = dict(getattr(focused, "keymap", {}) or {}).get(event.key)
     if action is not None and focused.on_action(action): return True
     ```
     再 `focused.on_key(event)`；
     - 若未消费、`event.key == "enter"`、`focused.activatable` → `focused.on_action("activate")`；
  3. `PasteEvent` → `focused.on_paste(event)`；
  4. `MouseEvent` → `focused.on_mouse(event)`（若实现；默认 handle 转发）；
  5. 其它 → False。
  - 删除硬编码 up/left/down/right/enter 分支。
- `FocusManager.click`：
  - 用 `hit.leaf`；`leaf.clickable` → `leaf.on_click(Pos(x=hit.leaf_col, y=hit.leaf_row))`（注意 Pos 的 x=col,y=row）；
  - 未聚焦且是 target → focus；
  - 已聚焦且 `activatable` → `on_action("activate")`；
  - 删除 `isinstance(Clickable/Activable/Focusable/Hoverable)`。
- 测试 `tests/app/test_focus.py`：
  - 数据视图 `lst.keymap["j"]="next"` 经 FocusManager 生效（index 前移）；
  - enter 对 `activatable` 触发 activate；
  - Input 的方向键仍由自己的 `on_key` 处理；
  - click 的 Pos 坐标与旧 `(row,col)` 一致；
  - Form scope：键交给 Form 的 `on_key`，不进入子字段。
- 只允许改：`app/focus.py`、`tests/app/test_focus.py`、`widgets/base.py`（仅在需要 enter 回退/`on_*` 辅助时）。
- 验证：`uv run pytest -q tests/app/test_focus.py tests/widgets/test_choice.py tests/widgets/test_editing.py`。

### T4 resize 广播

- `app/application.py:App.dispatch`（或 `TUI.dispatch`）在进入现有 handler 链前：
  ```python
  if type(event) is ResizeEvent:
      for widget in iter_widgets(self.tui):
          widget.on_resize(event)
      # 不 return；继续现有链（host 仍可处理）
  ```
- 测试 `tests/app/test_app.py`：
  - 一棵树的多个 Widget 都收到一次 `on_resize`（用记录型 fake Widget）；
  - ResizeEvent 不被消费（返回值/后续 handler 仍收到）。
- 只允许改：`app/application.py`、`tests/app/test_app.py`。
- 验证：`uv run pytest -q tests/app/test_app.py`。

### T5 收口

- `grep -rn "_walk\|_looks_interactive\|set_focus_targets" src/motui` → 0（注释除外）。
- `grep -rn "isinstance" src/motui/app` 只允许事件/值类型判别；能力探测 0。
- `tools/api.py --update`；全量门禁。
- 只允许改：`tools/api-2.0.txt`、handoff。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. 焦点环前序/scope/移除更新测试通过；keymap rebind 与 enter 激活通过；Form/Dialog 路由不变。
5. `_walk`/`_looks_interactive`/`set_focus_targets` 删除；能力 isinstance 在 app 为 0。
6. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。

## 禁触清单

`kernel/**`、`terminal/**`、`widgets/**`（除 T3 必要）、`demo/**`、`tests/widgets/**`（除 T3 必要）、`tests/golden/**`、`tools/{golden,framebench,semantic}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/W3b3a-focus.md`：A 节给焦点目标算法/keymap 路由/click/resize、门禁；B 节给 scope 规则、enter 回退、删除清单、W3b3b 剩余协议/别名/isinstance 清单、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W3b1/W3b2 事实）/ 探索审计 / 未决问题。
