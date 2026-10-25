# C3a · Runtime / Workspace 真拆 + Router

> 分支 `2.0-clean/c3a-runtime`；前置：C4b 已合并（`c1ebbe4`）；写入范围：`src/motui/app/{runtime,workspace,application,router,__init__}.py`、`src/motui/testing/__init__.py`、`tests/**`、`tools/api-2.0.txt`
> 权威：`../2026-10-25-0900-motui-2-0-architecture/ref/source/{04-runtime,05-api-surface}.md` §5–7

## 目标

完成运行时的真正职责拆分（不再 facade 委托）：

1. `Workspace` 拥有 frame/document/viewport/pane/content/selection/hit/dock 的状态与方法；
2. `Runtime` 只拥有 terminal/painter/timers/dirty/session（clock/advance/tick/paint/run/read_event）；
3. `App` 组合 `terminal`/`runtime`/`workspace`，用 `router.DEFAULT_HANDLERS` 替代 `dispatch` if 链；
4. `testing.Harness` 提供测试用扁平代理（`headless_tui` 返回它），生产代码不留 shim；
5. 1626 用例、5 场景 semantic、demo/pages 全绿；行数向 Runtime/Workspace ≤450、App ≤250 靠拢（如实报告）。

**本波结束：Runtime 不再含 add/get/frame/split/dock/hit/selection；Workspace 是真状态所有者；App.dispatch 是 handler 链；全量绿。**

## 前置上下文

- 必读：C4b handoff → 本工单；`src/motui/app/{runtime,workspace,application}.py`、`testing/__init__.py`。
- 基线：`uv sync --locked`；`pytest`（1626 passed）；`semantic --check`（5 scenes）；`python -m motui --pages` 5 场景。
- 现状：
  - `Runtime`（~1496 行）仍持有 `_document/_viewport/_frame/_selection/_dock_sizes/_tiling` 与 add/get/frame/split/dock/hit/selection 等方法。
  - `Workspace`（~285 行）是纯 facade，逐方法 `self._runtime.<method>`。
  - `App`（~850 行）组合 runtime/workspace/terminal，`dispatch` 仍是 if 链，`handlers` 未被消费。
  - `headless_tui` 返回 `Runtime`；测试约 300 处 `tui.add/paint/rows/frame/...` 扁平调用。
- 设计：
  - `Workspace`：
    - `__init__(runtime, *, theme)`：创建 `_document/_viewport/_frame/_selection/_selection_pane_id/_layout_width/_dock_sizes/_tiling/_tiling_revision`；`Frame([Pane("primary", Rect(0,0,0,0), viewport)])`；`add_overlay(_SelectionOverlay(self), layer="selection")`；`frame.on_change = runtime.refresh`。
    - 把 Runtime 中以下方法体迁入（self 即 Workspace）：`document/viewport/pane/_document_panes/_content_pane/_focus_pane/_next_block_id/_panes_holding/add/fill/_holder/get/remove/system/_focused_viewport/scroll_up/scroll_down/scroll_to_bottom/reveal/frame/split/pane_at/visible_range/dock/undock/dock_region/_dock_height/_retile/rows/selection/selection_pane/set_selection/_set_selection/_focused_id/_pane_id/hit/hit_leaf`。
    - `Workspace` 需要 `runtime.refresh()/paint()/terminal/theme`；用 `self._runtime`。
    - `_SelectionOverlay` 构造改为 `(workspace)`；读取 `workspace.selection/_selection_pane_id/_document_panes`。
  - `Runtime`：
    - 只保留 `terminal/screen/painter/timers/dirty/interactive/throttle/session`；`workspace` 属性。
    - `paint` 用 `self.workspace.frame.compose(...)` / `workspace.rows()`；`refresh`/`invalidate`/`paint_now`。
    - `read_event/exit/run/run_session/_pump/_run/_teardown/_dump_final_screen/clock/advance/tick/_next_deadline/_paint_at/_wake*` 保留。
    - `set_title/set_cursor_shape/copy_to_clipboard` 保留（terminal）。
    - 删除所有 workspace 方法/状态；`Runtime.__init__` 创建 `self.workspace = Workspace(self, theme=...)`。
  - `App`：
    - `self.runtime`/`self.workspace`/`self.terminal`；`add/get/remove/fill/split/dock/...` 走 workspace。
    - `dispatch`：`for handler in self.handlers: if handler(self, event): return True`；`handlers` 默认 `DEFAULT_HANDLERS`，`auto=False` → `()`。
  - `app/router.py`：
    ```python
    Handler = Callable[["App", Event], bool]
    def palette(app,e): ...; def modal(app,e): ...
    DEFAULT_HANDLERS: tuple[Handler,...] = (...)
    ```
    顺序与现 `dispatch` 完全一致：palette → modal → find → toast → controllers → wheel → drag → gesture → pointer → pane focus → focus → page keys → bindings → host。每个 handler 只回答消费与否；需要 `app.invalidate()` 的自己调。
    保留 `app.on_event`/`on_key`/`on_mouse` 作为 host 钩子。
  - `testing.Harness`：
    - `__init__(runtime, workspace, terminal)`；`__getattr__` 先 workspace 再 runtime（含 `_clock` 等私有属性的 setattr 代理？`tui._clock = ...` 需要 `__setattr__` 代理到 runtime）。
    - `headless_tui` 返回 `Harness`；`snapshot` 接受 Harness。
    - 生产代码不依赖 Harness；`Runtime`/`Workspace` 公开面干净。
- 已知坑：
  - `Workspace` 方法内部大量 `self._frame/_document/_viewport`；迁移后保持不变。
  - `Runtime.paint`/`_paint_at` 需要 `workspace.frame/rows/visible_range`；`_SelectionOverlay` 注册在 Workspace。
  - `App` 的 `_mount/_forget/focus_targets(runtime)` 需要 root widgets 来自 `workspace.panes`；`focus_targets` 签名改成 `(workspace)` 或接受 `Runtime` 并用 `runtime.workspace`。
  - `Harness.__getattr__` 不能吞 `__slots__`/dunder；只代理普通名字；`__setattr__` 对 `_clock` 代理到 runtime。
  - 测试里 `isinstance(tui, Runtime)` 可能失败（Harness）；更新断言或用 `tui.runtime`。
  - `tools/framebench.py`/`semantic.py` 直接构造 Runtime 并使用 add/paint；改为 `runtime.workspace.add` 或 `Harness`。
  - `demo` 的 `Showcase` 使用 `app.fill`；不受影响。
  - `App.dispatch` 的 handler 顺序必须与旧 if 链完全一致；用现有测试 `test_driver/test_app` 验证。
  - 行数如实报告；不要为了行数删 docstring/功能。
- 不改 widget/kernel/terminal 行为；不改 demo 场景/文案；不改 examples。

## 工单（按序，每步一个 commit）

### T1 Workspace 真状态 + 方法迁移

- 按设计把 Runtime 的 workspace 状态/方法迁入 Workspace；`_SelectionOverlay` 改为 Workspace。
- `Runtime` 只留 session/timer/paint/terminal；`workspace` 属性；`__init__` 创建。
- 更新 `app/__init__.py`/类型注解。
- 验证：`uv run pytest -q tests/kernel tests/widgets`（workspace 相关测试后续修）。

### T2 testing.Harness + 测试/工具迁移

- `testing.Harness` + `headless_tui` 返回；`snapshot` 适配。
- 全仓测试/工具把 `Runtime.add/get/frame/...` 改为 `Harness`（`headless_tui` 自动）或 `runtime.workspace.*`。
- `tools/{framebench,semantic}.py` 适配（只改调用面，不改工作负载）。
- 验证：`uv run pytest -q -p no:cacheprovider`。

### T3 Router

- 新建 `app/router.py`，按旧 dispatch 顺序实现 handlers；`App.dispatch` 变为循环。
- `App.handlers` 默认 `DEFAULT_HANDLERS`；`auto=False` → `()`；自定义 handlers 可用。
- 测试 `test_app/test_driver`：顺序/consume 行为不变；额外加一个自定义 handler 测试。
- 验证：`uv run pytest -q tests/app`。

### T4 收口

- `tools/api.py --update`；全量验收；行数报告。
- `grep "def add/get/split/dock/hit/selection" src/motui/app/runtime.py` → 0（只剩 workspace 属性）。
- `python -m motui --pages` 5 场景；semantic 5；framebench hash/性能记录。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. semantic 5；pages 5；`< /dev/null` exit 0；examples 3 个 exit 0。
3. `Runtime` 不再含 workspace 方法；`Workspace` 拥有状态；`App.dispatch` 是 handlers 循环。
4. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth.py` full 全绿。
5. 行数：Runtime/Workspace/App 如实报告；目标 ≤450/450/250，超了写差距与后续计划。
6. framebench 无 >10% 劣化。

## 禁触清单

`kernel/**`、`terminal/**`、`widgets/**`、`demo/**`（只读）、`examples/**`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`、`tools/{golden（已删）,semantic,framebench,growth}.py`（仅调用面适配）。

## 交接包

最后 commit 写 `handoff/C3a-runtime.md`：A 节给 Workspace/Runtime/App/Router 面、测试 Harness、门禁、行数；B 节给状态迁移、Harness 代理、handler 顺序、剩余差距、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
