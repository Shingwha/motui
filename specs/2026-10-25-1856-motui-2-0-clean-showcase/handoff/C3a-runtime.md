# C3a · Runtime / Workspace 真拆 + Router · 交接

> 分支 `2.0-clean/c3a-runtime`；起点 `c1ebbe4`；3 个工单 commit + 本 handoff。
> 结论：Workspace 是真状态所有者；Runtime 不再含 add/get/frame/split/dock/hit/selection；
> App.dispatch 是 handler 链；`headless_tui` 返回 Harness；1633 passed / semantic 5 / pages 5 / examples 3 全绿。

## A. 交付面
### Workspace（`src/motui/app/workspace.py`，894 行）
- 拥有 `_document/_viewport/_frame/_selection/_selection_pane_id/_layout_width/_dock_sizes/_tiling/_tiling_revision`；
  构造时建 primary pane、注册 `_SelectionOverlay(self)`、设 `frame.on_change = runtime.refresh`。
- 公开 `document/viewport/frame/panes/rows/selection/selection_pane` 与
  `pane/add/fill/get/remove/system/scroll_*/reveal/split/pane_at/visible_range/
  dock/undock/dock_region/set_selection/hit/hit_leaf`；私有 `_document_panes/
  _content_pane/_focus_pane/_next_block_id/_panes_holding/_holder/_focused_viewport/
  _focused_id/_pane_id/_retile/_dock_height/_set_selection/_reset`。
- `add/get/remove/system/fill` 统一返回 `Section`。控制器 host 需要的 6 个 runtime
  seam 显式暴露：`clock/every/refresh/screen/painter/copy_to_clipboard`（thin delegate）。
### Runtime（`src/motui/app/runtime.py`，729 行）
- 只剩 terminal/screen/keys/painter/throttle/interactive/_dirty/_timers/_clock/
  _wake*/_owned_source/_exit_event 与 `workspace`；生命周期 clock/advance/tick/
  every/animation/refresh/invalidate/paint/paint_now/read_event/exit/run*/_pump/
  _teardown/_dump_final_screen。
- `_paint_at`：`workspace._retile()` → `workspace.frame.compose` → `apply_overlays`
  → `painter.paint`；宽度变化清 selection。`set_title/set_cursor_shape/
  copy_to_clipboard` 保留（terminal 协议面）。
- 仅两个只读/引导 seam：`rows`（painter 输出；examples/quickstart 读
  `app.runtime.rows`）与 `fill`（只读 demo 的 `scene_output` 调 `runtime.fill`）。
### App（643 行）+ Router（`router.py`，357 行）
- `handlers is DEFAULT_HANDLERS`（默认），显式 tuple 可用；`auto=False` → `()`（显式 handlers 仍生效）。
  `dispatch`：ResizeEvent 先广播（不消费），再 `for handler in self.handlers: if handler(self, event): return True`。
- 顺序：palette → modal → find → toast → controllers → wheel → drag →
  mouse（gesture+pointer+pane focus）→ focus → page_keys → bindings → host。
- 旧的 `_wheel/_wheel_x/_drag_*/_scroll_key/_press_focuses_a_pane` 整体迁入 router；
  `app/__init__.py` 导出 `DEFAULT_HANDLERS/Handler`（api 188 names）。
### testing.Harness（`src/motui/testing/__init__.py`）
- `Harness(runtime, workspace=None, terminal=None)`；`__getattr__` dunder 拒绝，
  否则 workspace 优先、runtime 兜底；`__setattr__` 三件套走 object，私有名
  （`_clock`）代理 runtime，公开名写 workspace。
- `headless_tui` 返回 Harness；`snapshot(Harness)` 不变；生产代码 0 处引用。
### 门禁（真实输出）
```
uv sync --locked                    -> Checked 20 packages
pytest -q -p no:cacheprovider       -> 1633 passed in 11.85s
semantic --check                    -> semantic: 5 scenes match
python -m motui --pages             -> exit 0, 133 lines, 5 headers
python -m motui < /dev/null         -> exit 0, 20 lines
examples {quickstart,code,wide_table} --headless -> exit 0 x3
motui --scene {breakout,dashboard} --frames 30 --headless -> exit 0 x2
ruff / pyright / lint-imports       -> All checks passed / 0 errors / 4 kept
api --check                         -> 188 names match
growth.py (full)                    -> pytest/semantic/api pass, OK
framebench（2 轮交错 base c1ebbe4） -> 0.8-0.9/4.8-5.0/0.5/0.7-0.8/0.6/0.1/0.1/0.9 ms，
                                       replay 346-355 ms；hash e7ca544b…652986da 不变
```
行数：Runtime 1496→**729**（目标 450，差 279）、Workspace 274→**894**（差 444）、
App 847→**643**（目标 250，差 393）、router 新增 **357**。未删功能/docstring 凑数；
差距主因是迁移的完整契约 docstring 与 App 的控制器装配。后续：Runtime 拆 Timer/pump
到 `app/timer.py`；Workspace 按 document/frame/hit 拆 mixin；App 的默认控制器装配外移。
## B. 过程、偏差与坑
- **状态迁移**：方法体原样搬入 Workspace，`self._frame/_document/_viewport` 保持；
  `_dock_edge/_body_address` 一并迁入；`self.refresh()` 现为 Workspace→runtime。
- **控制器 host**：`Pointer/Gesture/Toasts/Tooltip/Modal/Find/CommandPalette/Scrollbar` 不在写入范围，
  却同时需要 frame/hit/selection 与 clock/every/painter/refresh。App 现在把它们构造在 `workspace`
  上，Workspace 提供上述 6 个 seam；`on_selection` 回调因此收到 Workspace（注解已改）。后续可让
  控制器显式收 `(workspace, runtime)` 后删 seam。
- **鼠标三层合并**：旧 dispatch 在 MouseEvent 上始终跑 gesture + pointer + pane focus
  （gesture 消费不阻止后两者：pointer 配对 press/release，press 仍聚焦 pane），故 router
  的 `mouse` 是一个 handler（OR 后统一 invalidate），不是三个会早退的 handler；行为 1:1。
- **demo/examples 只读依赖**：`demo/__init__.py:98 runtime.fill(showcase)` 与
  `examples/quickstart.py:24 app.runtime.rows` 在禁触文件里；为保持零 diff，Runtime
  保留这两个 seam（fill 转发 Workspace，rows 直接读 painter）。其余工具调用面
  （framebench 的 add/split/scroll/Scrollbar host）改为 `runtime.workspace`。
- **Harness 代理**：测试辅助 `Clock.install` 改设 `tui._clock`，保证 fake clock 落在
  runtime 的 `clock()` 缝上；`tui.theme` 解析到 workspace；`isinstance(tui, Runtime)`
  的断言改为 `tui.runtime`。`add/system` 返回 Section（`.id/.widget`），`get/remove`
  返回 Section；直接构造 Runtime 的测试改用 `runtime.workspace.*` 或 `Harness(runtime)`。
- **剩余旧名**：`app/find.py` 内部属性仍叫 `self.runtime`，实际收到 Workspace
  （禁触，行为不变）；`app/focus.py` 的 `focus_targets/iter_widgets` 注解仍写 Runtime，
  App 传 Workspace/Harness（duck-typed，禁触）。
- **坑**：首次 dock 后 `dock_region()` 仍为 None，要第一次 compose 才有 region；
  `Workspace.every` 必须转发 runtime 定时器，否则 Scrollbar/Gesture 的 ticker 不进
  pump；`Harness.__setattr__` 对公开名写 workspace，session 属性赋值要显式走 `runtime`。
## C. 路径与提交
关键路径：`src/motui/app/{runtime,workspace,application,router,__init__}.py`、
`src/motui/testing/__init__.py`、`tools/{framebench,api-2.0.txt}`、
`tests/app/{test_workspace,test_app,test_driver,test_pointer,test_hit,test_focus,
test_selection_overlay,test_surface}.py`、`tests/kernel/test_render_contract.py`、
`tests/testing/clock.py`。

commit：`521d16c` workspace 真状态/方法迁移 · `9847aae` Harness + 测试/工具迁移 · `5d9a2d8` Router/handlers · 本 handoff。
