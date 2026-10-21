# W4a · App 编排 / raw read_event / Hit chain

> 分支 `refactor/1.2-w4a-app`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w4a-app`
> 前置：W3d 已合并（`f8390e1`）；写入范围见下；波末必须全量绿。

## 目标

把“默认交互编排”从 demo 的手写循环收进 `App`，把 `TUI.read_event()` 恢复为纯事件读取，并把 `Hit` 收敛成携带祖先链的值（wheel/click 路由用）。本波**不重写 demo 的架构**（W4b 做），只做让门禁保持绿的**最小 demo 适配**。

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（§3 W4 App/TUI + §2 W3d 实际交付）
  3. `handoff/W3d-w3d-content.md`
  4. 本工单
- 基线命令：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
```

起点 **882 passed / 57 topics match**。
- 稳定区（勿重读/勿改）：`widgets/**` 已迁移的样式逻辑、`core/widget.py`、`core/theme.py`、全部 golden、`docs/**`。
- 已知约束/坑：
  - `App` 默认编排必须用现有控制器，不重写它们；`TUI` 只做“读事件 + 文档/分屏/pump”。
  - `read_event` 原始化后，demo 的手写循环需要临时补回 wheel/page/focus 路由（≤20 行），W4b 会删。
  - `Gesture` 目前读 `tui.scroll_keys`；改成自己的 `scroll_rows`（构造参数已有 `_scroll_rows`）。
  - `Pane` 目前只有 `scroll_state`，补 `scroll_to/scroll_by` 委托 viewport，才能作为 `Scrollable`。
  - `Hit` 的 `leaf/leaf_row/leaf_col` 改成从 `chain` 派生的 property；现有消费者读这些 property，尽量不改调用点。
  - `TUI.add` 返回 id、`get/remove` 返回 Component、`dock` 接受 Component；测试/demo 的调用点必须同步。不要保留返回 Block 的旧路径。

## 工单（按序执行，每项一个 commit）

### T1 · Hit chain + Pane scroll verbs

- `core/block.py`：新增 `descend_chain(component, row, col) -> tuple[tuple[Component, int, int], ...]`；`descend` 返回链尾（保持现有调用）。
- `core/hit.py`：
  ```python
  @dataclass(frozen=True)
  class Hit:
      pane: Pane
      block: Block
      row: int
      col: int
      chain: tuple[tuple[Component, int, int], ...] = ()
      @property leaf -> Component | None
      @property leaf_row -> int
      @property leaf_col -> int
      @property pane_id -> str
  ```
- `app/driver.py::hit` 用 `descend_chain` 构造 `Hit`；`hit_leaf` 从 properties 取。
- `core/frame.py::Pane` 增加 `scroll_to(offset)` / `scroll_by(delta)`，委托 `viewport`。
- 更新 `tests/interaction/test_focus.py` 里直接构造 `Hit` 的位置；其它消费者应因 properties 不变而无需改。
- 验证：pytest + golden 不变。

### T2 · TUI raw read_event + document/dock API

- `app/driver.py`：
  - 删除 `_DEFAULT_SCROLL_KEYS`、`scroll_keys`、`focus_policy`、`_press_focuses_a_pane` 及 `read_event` 里的 scroll/focus 分支；`read_event` 只返回下一个事件或 `None`。
  - `add(...) -> str`（返回 id）；`get(id) -> Component`；`remove(id) -> Component`；`system(text) -> str`。
  - `dock(component: Component, *, edge="bottom", size=None) -> Pane`：内部新建 `Document` + `Viewport`，把 component 加进去；删除 `dock(viewport)` 旧签名。
  - 保留 `scroll_up/down/to_bottom`、`reveal`、`split`、`visible_range`。
- `app/gesture.py`：wheel-during-drag 用 `self._scroll_rows`（wheel_down 为正、wheel_up 为负），不再读 `tui.scroll_keys`。
- `app/app.py`（新）：实现下面的 `App`。
- `app/__init__.py`：导出 `App`。
- 更新所有 `tui.add`/`get`/`remove`/`dock` 调用点（tests + demo 最小适配）。
- 更新 `tests/app/test_driver.py`：
  - 删除/改写“read_event 吸收 scroll_keys / focus_policy”的用例；新增“wheel/page 原样返回”的最小断言（并入现有 test 文件）。
- 验证：pytest + golden 不变 + demo 两个入口。

### T3 · App 默认编排（app/app.py）

必须实现（签名见 `ref/interfaces.md` §3）：

```python
class App:
    def __init__(self, *, theme=None, mouse=True, hover=True, color_mode=None,
                 title="", auto=True, screen=None, keys=None, throttle=0.030): ...
    def run(self): ...
    async def run_async(self): ...
    async def run_session(self, body): ...
    def add(self, component, *, id=None, pin=None, pane=None) -> str: ...
    def get(self, id) -> Component: ...
    def remove(self, id) -> Component: ...
    def bind(self, key, callback): ...
    def focus(self, target: str | Component) -> bool: ...
    def focus_next(self) -> bool: ...
    def set_focus_targets(self, targets): ...
    def split(...): ...
    def dock(self, component, *, edge="bottom", size=None): ...
    def toast(self, text, *, style=None): ...
    def open_modal(self, panel, **kwargs): ...
    def open_palette(self, commands, **kwargs): ...
    def find(self): ...
    def quit(self): ...
    def on_start(self): ...
    def on_stop(self): ...
    def on_event(self, event) -> bool: ...
    def on_key(self, event) -> bool: ...
    def on_mouse(self, event) -> bool: ...
```

行为要求：

- `auto=True` 时挂 `FocusManager`、`Pointer`、`SelectionGesture`、`Toasts`、`Tooltip`；`auto=False` 时都不挂。
- `add`：委托 `TUI.add`；对 `Widget` 且 `theme is None` 的控件设 App 主题（best-effort 递归：`child/children/body/input/list/_fields`）；如果控件看起来可交互（自身覆盖了 `handle/activate/select/move/toggle` 中任一，而非 `Widget` 默认），注册到焦点环。
- `set_focus_targets(targets)`：清空当前环并加入新目标，聚焦第一个。
- `focus(target)`：字符串 -> `get`；注册并聚焦。
- `dispatch(event) -> bool` 顺序：
  1. 打开的 `CommandPalette`（如果创建过）；
  2. 打开的 `Modal`（后进先出；`open_modal` 创建并 open）；
  3. 打开的 `Find`；
  4. `Toasts.handle`；
  5. wheel：`hit.chain` 反向找最近的 `Scrollable`，否则 pane（`Pane` 现在是 Scrollable）；按 `scroll_keys` 表滚动；
  6. mouse：`gesture.handle` -> `pointer.handle`（release 时补 gesture）-> press 时聚焦 pane；
  7. `focus.handle(event)`（键盘路由）；
  8. `bind` 的键；`tab`/`s-tab` 循环焦点；
  9. `on_key`/`on_mouse`/`on_event`。
- `run`/`run_async`：非 live 时每次读事件前 `paint()`；循环直到 `read_event()` 返回 `None`；`on_start`/`on_stop` 包住；`quit()` 调 `tui.exit()`。
- `App.theme` setter：更新 `tui.theme` 并遍历已挂载组件，给 `Widget.theme is None` 的控件赋新主题。允许 best-effort，不做全局上下文。
- `open_palette`：懒创建 `CommandPalette(self.tui, commands, theme=self.theme)`，`open()` 并返回；`find` 同理。
- `open_modal(panel)`：`Modal(self.tui, panel, theme=self.theme, focus=self.focus)`，`open()`，存入列表并返回。
- 不自动挂 `Stats`；不自动读 `take_result`（W4b demo 自己处理）。

测试（只加必要的 2 个，放 `tests/app/test_app.py`）：

1. `App` + Input + Button：`app.add` 返回 id，`app.focus("name")` 后脚本输入 `a` + `enter` 绑定到按钮，断言 `input.text == "a"` 且按钮被 activate。
2. `App` + `ScrollView(height=3, scrollbar=True)`：脚本 wheel 在内容上，断言 `view.offset` 增加（证明 wheel 路由到最近 Scrollable）。

### T4 · demo 最小适配 + 波末门禁

- demo 只做让现有手写循环继续工作的最小改动：
  - `TUI.dock` 改 Component 后，`Session` 的 header/footer 改成 `tui.dock(component)`，或把 `mount_header/footer` 改成返回组件；不要重写整个 Session。
  - `read_event` 原始化后，在 `Session.run` 里补回 wheel/page/focus 路由（≤20 行），W4b 删除。
  - `tui.add`/`get`/`remove` 返回类型变化的调用点。
- 门禁：

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

## 验收

1. 五条门禁全绿；报告贴真实用例数/失败项。
2. `rg "scroll_keys|focus_policy" src/motui/app/driver.py` 为空；`read_event` 无 scroll/focus 副作用。
3. `TUI.add` 返回 `str`；`get/remove` 返回 Component；`dock` 接受 Component。
4. `App` 的 2 个测试通过；demo 仍可运行。
5. golden 逐字节不变；framebench hash 不变。
6. `App` 的默认 dispatch 顺序与 `ref/interfaces.md` §3 一致。

## 禁触清单

- 任何 widget 的样式/构造器（W3 已完成）。
- `Table` wrap（W5a）、`ScrollView` bar 鼠标输入（W5b）。
- demo 的完整重写（W4b）；只做最小适配。
- `docs/**`、README/CHANGELOG/pyproject、root `__all__`、golden。
- `.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后写 `handoff/W4a-w4a-app.md`（60-80 行），重点写 `App` dispatch 顺序、Hit chain、TUI API 变化、demo 临时适配、测试改动。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题
