# W3b3a 交接 · 焦点从树推导、App 树遍历与 keymap 路由

> 分支 `2.0/w3b3a-focus`；起点 `ba6d80e`。结论：T1–T5 完成；**1529 passed**（1513 基线 + 16 新）；
> 57 byte / 57 semantic / hash `e7ca544b…2986da` 全不变；demo 70 / 4059 行，exit 0。

## A. 交付面与门禁

### 焦点环（树推导，无注册）
- `focus._document_roots`：`frame.panes` 按绘制序，随后 `frame.docks.values()`（插入序）；
  每个 pane 按 `viewport.document.blocks()` 文档序。
- `focus.focus_targets(tui)`：前序栈；`focus_scope`（或 1.x 别名 `owns_focus`）节点**纳入并跳过子树**；
  其余节点仅 `focusable=True` 纳入；`id` 去重；无 `walk` 的纯组件只产出自身。
- `FocusManager.sync(targets)`：无焦点时只替换元组、**不写任何 focused 标志**（保留组件自身默认值，
  这是 `components--input` golden 不变的关键）；当前焦点仍在集合内则 `_replace` 重写标志；
  否则清空焦点并 `on_change(None)`。公开 `add/remove` 已删除。
- `App.focus/focus_next/focus_previous`：先 `sync(focus_targets(self.tui))` 再操作；
  `App._mount/_forget` 在挂载/移除后同步。
- `Form`/`Dialog`：`focus_scope=True`，只出现自身；`ComboBox.owns_focus=True` 同样按 scope 处理，
  内部 Input/Autocomplete 不进环（保持 1.x 的“组合框自己路由”）。

### keymap 路由（FocusManager.handle）
- 空焦点 → `False`；`KeyEvent` → `keymap[key]` 经 `on_action(name)`；未消费再 `on_key(event)`
  （纯对象回退 `handle`）；仍未被消费的 `enter` 且 `activatable` → `on_action("activate")`。
- `PasteEvent` → `on_paste`；`MouseEvent` → `on_mouse`；其它事件 → `False`。硬编码方向键/enter 已删。
- `click`：`hit.chain or descend_chain`；叶子 `clickable` → `on_click(Pos(x=leaf_col, y=leaf_row))`
  （纯对象回退 `click(row,col)`）；祖先逐个 `focus_at`（Form/Dialog 光标）；最近的已注册祖先为目标：
  首次点击聚焦，重复点击且叶子 `activatable` → `on_action("activate")`。能力 `isinstance` 已删。

### resize 广播
- `App.dispatch`：`type(event) is ResizeEvent` 时对 `iter_widgets(self.tui)` 逐个 `on_resize(event)`，
  不 return；scope 子树也收到，事件继续走原 handler 链与 host hooks。

### 门禁（本 worktree，Python 3.12.14 / uv 0.12.21）
- `pytest -q -p no:cacheprovider`：**1529 passed**
- golden **57**；semantic **57**；framebench hash `e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`
- `python -m motui < /dev/null`：exit 0，70 行；`--pages`：exit 0，4059 行
- ruff All checks passed；pyright 0；lint-imports 4 kept；`api --update/--check` **181 names，零内容变化**；
  `growth --quick` OK
- `grep -rn "_walk\|_looks_interactive\|set_focus_targets" src/motui/app`：App 侧 0
  （仅 `gesture.py` 的选择头 `_walk` 与 `widgets/tree.py` 的视图 `_walk`，与 App 无关）；
  全仓 `set_focus_targets` 0

## B. 实现细节 / W3b3b 提示

1. **sync 的标志策略**：无焦点时不动标志是刻意的。旧 `set_focus_targets` 只重写显式环内目标，
   ComboBox 内部 Input 的构造默认 `focused=True` 因而保留；若 sync 无条件清零，placeholder 消失、
   golden 立刻变。有焦点时仍全量重写，保证至多一个 focused。
2. **scope 判定**同时认 `focus_scope` 与 `owns_focus`；W3b3b 删除 `owns_focus` 前不要只读前者。
3. **click 保留祖先 `focus_at`**：T3 文字的“click 三步”省略了它，但 `Form.focus_at`/`Dialog.focus_at`
   是点击移动字段/按钮光标的唯一路径，删掉会回归 `test_a_form_owns...`。
4. **enter 回退用 `activatable` 标志**，不是 `isinstance(Activable)`；`_activate` 优先
   `on_action("activate")`，纯对象才回退 `activate()`。
5. **demo 例外**：`demo/session.py:_build_ring` 原调 `App.set_focus_targets`；删除该方法后 demo 无法构造
   （golden/--pages 全经此路径）。工单 T2 明确“测试/示例改 tree”，故最小改为
   `manager.sync(targets)` + 原 focus 两行，行为与顺序不变。它是本波**唯一**越出写入范围的文件；
   若 lead 要求 demo 零 diff，只能保留 `set_focus_targets` shim，则 T2 与 grep 门禁不可满足。
6. **ScrollPanel 的树缺口**：`widgets/scroll.py` 没有 `children=[child]`，`walk()` 到不了内容。
   App 的 theme/focus 因此不再进入 ScrollPanel 子组件（旧 `_walk` 会走 `child`）。当前 golden 不变；
   W3b3b 应补 `children=[child]`，并复核把 focusable 内容包在 ScrollPanel 里的宿主。
7. **遗留 `_walk`**：`app/gesture.py::SelectionGesture._walk`（选择头跨块）与 `widgets/tree.py::Tree._walk`
   （视图行展开）是各自算法的私有名，不是 App 的挂载遍历；本波未动。
8. **能力 isinstance 残留**（app 内，超出本波文件范围）：`app/pointer.py` 的
   `isinstance(old/target, Hoverable)` 与 `isinstance(component, Clickable)`。W3b3b 应换成
   `hoverable`/`clickable` 标志；`scrollbar.py` 的 `isinstance(..., ScrollPanel)` 是结构判别，可留。
9. **traps 与 sync**：`push_trap` 后若再调 App 的 focus 动词，sync 会用全树环覆盖 trap。
   当前 App 在 Modal 打开时先被 Modal 消费，不会走到 focus tier；W4 的 Workspace 需保持此顺序。
10. **W3b3b 待删别名清单**：5 个 `handle=on_key`（list/choice/tree/table/menubar/scroll 中除 ScrollPanel
    `_dispatch` 的 6 处）、各视图 `click`、`Text.hover_at`、9 个 `take_result`、`Form.owns_focus`；
    以及 pointer 的三处能力探测。
11. **测试**：`test_focus.py` 的 doubles 现在显式声明 `focusable/clickable/activatable` 与
    `on_key/on_action/on_click`；旧的硬编码方向键测试改为 keymap rebind、Input 自有方向键、
    Form scope 路由与 click Pos 断言。`test_app.py` 新增树 theme、移除重算、resize 广播。

## C. 位置与 commit

- 源码：`src/motui/app/{application,focus}.py`；`src/motui/demo/session.py`（唯一例外，见 B5）
- 测试：`tests/app/{test_app,test_focus}.py`
- commit：
  - `df0d3c4` focus: the ring is derived from the mounted tree（T1）
  - `4a08c23` app: mount, theme and focus walk the explicit tree（T2）
  - `cbb15b4` focus: keys route through keymaps, typed hooks and capabilities（T3）
  - `f1da9b4` app: a resize is broadcast to the whole mounted tree（T4）
  - 本文件（T5 收口；`api --update` 零内容变化）
- 禁触审计：`kernel/**`、`terminal/**`、其余 `widgets/**`、`tests/widgets/**`、`tests/golden/**`、
  `tools/{golden,framebench,semantic}.py`、`pyproject.toml`、`uv.lock`、`README.md`、`docs/**`、
  `CHANGELOG.md` 零 diff；`tools/api-2.0.txt` 无内容变化。`git diff --name-only ba6d80e..HEAD`
  仅上述 3 源文件 + 2 测试 + 本 handoff（另含分支起点已有的两份 spec commit）。
