# W4a 交接包
> 分支 `refactor/1.2-w4a-app` / 起点 `5eea685`（W3d merge `f8390e1` + 工单）/ 2026-10-21

## A. 自动事实（从命令与代码生成，别凭记忆）

- commits：`cb3349b`（T1）、`f1b816a`（T2）、`d7fcb6f`（T3）、`64d85f4`（T4）、本文件所在 commit。
- `git diff --stat 5eea685..64d85f4`：14 files, +809/-309（不含本文件）：
  `app/{__init__,application,driver,gesture,scrollbar}.py`、`core/{block,frame,hit}.py`、`demo/session.py`、
  `tests/app/{test_app,test_driver,test_hit}.py`、`tests/interaction/{test_focus,test_gesture}.py`。
- 签名实测（`inspect.signature`）：
  - `App(*, theme=None, mouse=True, hover=True, color_mode=None, title="", auto=True, screen=None, keys=None, throttle=0.030)`
  - `App.add -> str`；`App.get/remove -> Component`；`App.dispatch(event) -> bool`
  - `TUI.add(...) -> str`；`TUI.get/remove -> Component`；`TUI.dock(component, *, edge="bottom", size=None) -> Pane`
  - `TUI.read_event() -> Event | None`；`Hit(pane, block, row, col, chain=())`
  - `descend_chain(component, row, col) -> tuple[tuple[Component, int, int], ...]`
- 全波真实结果（本 worktree，CPython 3.13）：`pytest -q -p no:cacheprovider` -> **880 passed**
  （882 起点 -4 删除用例 +2 新增）；`golden.py --check` -> **57 topics match**（未重录）；
  `framebench.py` -> render hash `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`；
  `python -m motui < /dev/null` -> exit 0；`--pages` -> exit 0，4059 行。
- `rg "scroll_keys|focus_policy" src/motui/app/driver.py` 与 `rg ... src` 均为空。

## B. 只存在于脑子里的东西（W4b/W5 直接复用）

**App dispatch 顺序（`App.dispatch`，先到先得；按工单 T3）**
1. 打开的 `CommandPalette`（懒创建，独立于 `_modals`）；
2. 打开的 `Modal`，`_modals` 反向遍历（后进先出）；
3. 打开的 `Find`；
4. `Toasts.handle`（只吃 toast 矩形内的左 press）；
5. wheel：先让 `SelectionGesture` 试（拖动中返回 True 并共扩展 head），否则 `hit.chain`
   反向找最近 `Scrollable` -> 命中的 pane -> focused pane；按 `app.application.SCROLL_KEYS`
   （page ±1、wheel ±3）`scroll_by`；
6. mouse：`gesture.handle` 与 `pointer.handle` **都调用**（不因 gesture 消费而跳过 pointer），
   之后 press 聚焦指针下非 dock 的 pane；
7. `FocusManager.handle`（键盘）；8. `bind` 表 -> `tab`/`s-tab`；9. `on_key/on_mouse/on_event`。
- 偏差：`ref/interfaces.md` §3 把 wheel 放最后并列出 chrome `Scrollbar`/ScrollView bar；
  本波按工单实现，App 没有控制器注册表，**不调用** `Scrollbar.handle`（其 docstring 已改）。
- `auto=False`：控制器全为 None；`dispatch` 跳过对应层；`toast()` 抛 `RuntimeError`；
  `open_modal/open_palette/find` 仍可工作（focus=None）。`Tooltip` 只注册 overlay、无 `handle`。
- 主题传播：`add` 递归 `child/children/body/input/list/_fields`，只给 `Widget.theme is None`
  赋值；`theme` setter 重走已挂载子树；显式 `theme=` 保留。
- 焦点注册：`_looks_interactive` 比较 `type(component).{handle,activate,select,move,toggle}`
  是否覆盖 `Widget` 默认；`add` 时递归注册（`FocusManager.add` 幂等）。
- `run_async` = `tui.run_session(_loop)`；非 interactive 时每次读前 `paint()`；
  `on_start`/`on_stop` 用 try/finally；`run()` 是 `asyncio.run`。

**Hit chain**
- `descend_chain` 返回 `((outermost,row,col), ..., (leaf,leaf_row,leaf_col))`，至少含起点；
  `descend` 是其 `[-1]`，语义与深度上限不变。
- `Hit.chain` 默认 `()`；`leaf/leaf_row/leaf_col` 从尾部派生（空链 `None/0/0`）；`pane_id` 不变。
  `TUI.hit` 一次 `descend_chain` 构造。
- `Pane` 新增 `scroll_to/scroll_by` 委托 viewport，故结构上满足 `Scrollable`（`scroll_state` 原有）。

**TUI API 变化（破坏性，无兼容路径）**
- `read_event` 纯读取：无 wheel/page 拦截、无 `focus_policy`；`scroll_keys`、`focus_policy`、
  `_DEFAULT_SCROLL_KEYS`、`_press_focuses_a_pane`、`_scroll_viewport` 删除。
- `add -> id`、`get/remove -> Component`、`system -> id`；`dock(component)` 内部
  `Document()+Viewport()`，块 id 用 `_next_block_id()`（frame 内唯一）。
- `Gesture` 拖动中 wheel 用自身 `scroll_rows`：`wheel_down=+2`、`wheel_up=-2`、横向忽略
  （旧默认 ±3，测试期望已改）。

**demo 临时适配（W4b 删除）**
- `Session.__init__` 先 `tui.dock(Text(""), edge=..., size=...)`，用返回 pane 的 `document`
  当 `header_doc/footer_doc`；`_mount_shell` 仍清空后 `mount_*` 挂组件。
- `_round` 开头调用 `_scroll_or_focus`（约 20 行）：page/wheel 滚动指针下或 focused pane 的
  viewport，press 聚焦 pane；顺序与旧 read_event 一致。`_SCROLL_KEYS` 是 session 模块常量。

**测试改动**
- `tests/app/test_app.py`（新增 2 例）：焦点/bind 路由；wheel 到最近 `ScrollView`。
- `test_driver.py`：删 press-focus、wheel-focus、focus_policy、wheel-over-dock 4 例；
  `read_event_absorbs...` 改为 `read_event_returns_wheel_and_page_events_untouched`；
  facade 断言改 id/component；dock 用例改 `dock(Rows(...))`。
- `test_hit.py`：add 返回值改 id；dock 改新签名。`test_focus.py`：直接构造 `Hit` 传 chain。
- `test_gesture.py`：wheel 拖动期望 3 -> 2（`scroll_rows` 默认）。

## C. 指针 / 未决
- `src/motui/app/application.py`：`SCROLL_KEYS`、`_walk`、`_looks_interactive`、`dispatch`、`_wheel`、
  `_press_focuses_a_pane`、`_loop`。
- `src/motui/core/block.py::descend_chain`；`core/hit.py::Hit`；`core/frame.py::Pane.scroll_to`。
- 未决：App 未挂 Stats、不读 `take_result`（工单要求）；demo `patterns.py` 的 api_line 与 golden
  仍写旧 dock 签名（渲染内容，W6 更新并重录）。
