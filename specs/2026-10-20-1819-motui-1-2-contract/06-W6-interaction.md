# W6 · 交互层解耦、Host、FocusManager 与 overlay 层
> 分支 `w6-interaction`；前置：W2/W4b 已合并（最新 main `2dad1f5`）；写入范围见下。
> 深读：`00-overview.md` D8、`ref/interfaces.md` §4、`docs/CONTRACT.md` §6/§7。

## 目标

用 `kernel/host.py:Host` 断掉 `interaction -> app` 与 `interaction -> widgets`；把 `FocusRing` 升级为
`FocusManager`（add/remove/next/previous/on_change + trap/restore）；overlay 有显式 layer 与稳定 z-order；
`Modal`/`Palette` 迁到 `take_result()`；修 `Modal.detach()` 的隐形事件黑洞；`with_pane_rows` 不越界。
**渲染结果不变**（golden 不动；demo 的 API 调用点同步，但文案不改）。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §4 → `handoff/W4b-rowviews.md` → `handoff/W5a-composition.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
  期望：1900 passed / 2 skipped；11 页 match；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
- 稳定区（勿重读）：W1–W5a 的 kernel/keys/widgets；`widgets/**` 本波只读（W5b 的菜单另开）。
- W5a 约束：`ScrollView/Form/CommandRegistry/Clipboard` 已落地；Form 自己镜像 Focusable，W6 只需让
  `FocusManager` 可被宿主/Modal 使用，不强制 Form 接入。

## 决策

- `Hit` / `RowRange` / `EveryHandle` 移到 `kernel/host.py`；`motui.app` 不再导出它们（`motui.app.__all__`
  只剩 `TUI`）。`interaction` 从 `kernel.host` 导入。
- `Host` 是 runtime-checkable protocol；`TUI` 结构满足。`make_input`/`make_autocomplete` 返回 `object`
  （app 内部 import widgets 实现；interaction 用 `typing.cast`/`Any` 使用）。
- `FocusRing` → `FocusManager`；无 alias。根 34 名中 `FocusRing` 替换为 `FocusManager`。
- overlay layer 顺序：`background < content < selection < chrome < overlay < modal < tooltip < toast`；
  同层按注册顺序稳定。未知 layer 抛 `ValueError`。
- `Modal.take_result()` / `Palette.take_result()` 取代公开 `chosen`；`Modal.close(value)` 写 pending。
- `Modal.detach()` 必须关闭并清空结果，不再吞事件。
- `TUI.split` 的分隔条 chrome 从 `interaction.scrollbar._Separator` 移到 kernel，消除 app→interaction
  的私有依赖。

## 工单（按序执行；HEAD 全绿即可）

### T1 `kernel/host.py`（新）+ `app.py`：Host 与值类型

- 新建 `kernel/host.py`：
  ```python
  @dataclass(frozen=True)
  class Hit:
      pane: Pane; block: Block; row: int; col: int
      leaf: Component | None = None; leaf_row: int = 0; leaf_col: int = 0
      @property pane_id -> str
  @dataclass(frozen=True)
  class RowRange:
      first: int; last: int
  class EveryHandle:
      @property cancelled -> bool; def cancel(self) -> None
  @runtime_checkable
  class Host(Protocol):
      screen: Screen
      frame: Frame
      def refresh(self) -> None: ...
      async def read_event(self) -> Event | None: ...
      def clock(self) -> float: ...
      def every(self, seconds: float, fn: Callable[[], object]) -> EveryHandle: ...
      def hit(self, x: int, y: int) -> Hit | None: ...
      def set_selection(self, selection: Selection | None, *, pane: Pane | str | None = None) -> None: ...
      def visible_range(self, pane: Pane | str | None = None) -> RowRange | None: ...
      def copy_to_clipboard(self, text: str) -> bool: ...
      def make_input(self, **kwargs: object) -> object: ...
      def make_autocomplete(self, options: Sequence[object], **kwargs: object) -> object: ...
  ```
- 把 `Hit`/`RowRange`/`EveryHandle` 的实现从 `app.py` 移入；`app.py` 从 `kernel.host` import。
- `TUI.make_input`/`make_autocomplete`：函数内 import `widgets.textfield.Input` / `widgets.autocomplete.Autocomplete`；
  `copy_to_clipboard` 委托 `screen.copy_to_clipboard`。
- `kernel/__init__.py` 导出 `Host`/`Hit`/`RowRange`/`EveryHandle`；`motui.app.__all__` 改为 `["TUI"]`。
- `tests/test_api_root.py` 更新 kernel/app 两个 facade。
- 测试：`isinstance(TUI(...), Host)`；`TUI.make_input` 返回可 `handle` 的字段；`copy_to_clipboard`。

### T2 `interaction/focus.py`：`FocusManager`

```python
class FocusManager:
    def __init__(self, targets: Iterable[Component] = (), *, wrap: bool = True,
                 on_change: Callable[[Component | None], object] | None = None)
    @property targets -> tuple[Component, ...]
    @property focused -> Component | None
    def add(self, target: Component) -> bool
    def remove(self, target: Component) -> bool
    def focus(self, target: Component) -> bool
    def focus_next(self, delta: int = 1) -> bool
    def focus_previous(self) -> bool
    def handle(self, event: Event) -> bool
    def click(self, hit: Hit) -> bool
    def push_trap(self, targets: Iterable[Component]) -> None
    def pop_trap(self) -> None
```

- 构造**不**设置焦点；`focus_next` 从无焦点时选第一个（delta<0 选最后一个）。
- `add/remove` 维护顺序；remove 当前焦点时清空并通知。
- `_set_focused` 只给 `Focusable` 目标写 `focused`；非 Focusable 目标只作为路由目标（Dialog 可用）。
- `on_change(component)` 在焦点真正变化后调用。
- `push_trap(targets)` 保存 `(targets, focused)` 并替换，`pop_trap` 恢复；支持嵌套。
- `handle`/`click` 的现有路由/点击语义保留（up/down/left/right/enter；click 的 focus-or-activate）。
- 根导出 `FocusRing` → `FocusManager`；`tests/test_api_root.py`、demo、README/COMPONENTS 同步。
- 测试：构造无焦点、add/remove、next/previous、on_change、trap/restore、非 Focusable 路由、点击。

### T3 `kernel/frame.py`：overlay layers + 越界裁剪 + separator

- 新增 `LAYERS = ("background","content","selection","chrome","overlay","modal","tooltip","toast")`；
  `Frame.add_overlay(overlay, *, layer="overlay")`，保存 `(layer_index, overlay)`；未知 layer 抛 `ValueError`。
- `Frame.overlays` 继续返回注册顺序的 overlay tuple；`apply_overlays` 按 layer index 稳定排序后运行。
- `TUI._SelectionOverlay` 注册 `layer="selection"`；`Find`/`Toasts`/`Tooltip`/`Stats`/`Modal` 的构造注册
  分别用 `overlay`/`toast`/`tooltip`/`overlay`/`modal`。
- `with_pane_rows` 只写 `rows[:placement.height]`；placement 高 0 直接返回原 layout。
- 把 `interaction.scrollbar._Separator` 的分隔条实现移到 kernel（如 `kernel/frame.py:Separator` 或
  `kernel/chrome.py`）；`TUI.split` 直接用它，删掉 app→interaction 的 lazy import。
- 测试：层序（background 先于 toast）、同层注册顺序、未知 layer、with_pane_rows 不跨 pane、separator 仍渲染。

### T4 `interaction/modal.py` + `interaction/palette.py`：take_result、detach、focus trap

- `Modal`：删除公开 `chosen`；`close(value)` 写 `_result`；`take_result()` 读取并清空；`is_open` 不变。
- `Modal.detach()`：注销 overlay 的同时 `_open=False`、`_result=None`；`handle` 不再吞事件。
- `Modal` 构造增加 `focus: FocusManager | None = None`；`open()` 若 focus 非 None 则
  `push_trap([dialog])`，`close()`/`detach()` `pop_trap()`（只 pop 自己 push 的那层）。
- `Palette`：删除 `chosen` property；`take_result()` 委托 Modal；`open/close/detach` 同步。
- 更新 demo 的 Modal/Palette 使用（`take_result`、pass focus manager），tests。
- 测试：take_result 读一次清空；detach 后 handle False；focus trap 恢复；两个 modal 的 layer 顺序。

### T5 解耦清扫

- `interaction/**` 全部改为 `from ..kernel.host import Host, Hit, RowRange, EveryHandle`（或 `..kernel`）；
  删除所有 `from ..app import ...`。
  类型注解 `TUI` → `Host`；`copy_on_select(host: Host, ...)` 用 `host.copy_to_clipboard`。
- `Find`/`Palette` 删除 `..widgets` import，改用 `host.make_input`/`host.make_autocomplete`；
  返回值用 `typing.cast(Any, ...)` 使用 `text`/`handle`/`set_query`。
- `app.py` 不再 import `interaction.scrollbar`（T3 已移 separator）。
- 验收 grep：
  - `grep -rn "from \.\.app\|from \.\.widgets" src/motui/interaction` → 0
  - `grep -rn "interaction" src/motui/app.py` → 仅 docstring/正文，无 import
- 更新 `interaction/__init__.py` docstring（策略层只依赖 kernel + Host）。

### T6 测试、demo、文档、handoff

- 更新 `tests/test_focus.py`、`test_modal.py`、`test_palette.py`、`test_overlays.py`、`test_find.py`、
  `test_app.py`、`test_api_root.py`、`test_demo_protocol.py`。
- 新增 `tests/test_host.py`（Host 协议/TUI 实现）、overlay layer 测试、modal detach/trap 测试。
- demo：`FocusRing` → `FocusManager`；`Modal`/`Palette` 的 `chosen` → `take_result`；Modal 传 focus manager。
  **不改 demo 渲染文案**。
- `docs/COMPONENTS.md`/`README.md` 只改与本波冲突的条目；W7 重写整篇。
- 跑验收，写 `handoff/W6-interaction.md`。不 merge/push/tag。

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；总数 ≥ 1900 + 新增
2. `uv run python tools/golden.py --check`：11 页全 match
3. `uv run python tools/framebench.py`：exit 0；render-hash 不变（贴值）
4. `uv run python -m motui < /dev/null`、`--pages`：exit 0
5. `uv run python -c "from motui.kernel.host import Host; from motui import FocusManager; from motui import TUI; assert isinstance(TUI(), Host)"`：exit 0
6. `grep -rn "from \.\.app\|from \.\.widgets" src/motui/interaction`：0 命中
7. `grep -rn "FocusRing" src tests README.md docs`：0 命中（历史 spec 除外）
8. `git diff --stat main...HEAD`：范围 = 本工单写范围并集，无 golden 变化

## 禁触清单

- 禁改：`widgets/**`（W5b 菜单另开）、`kernel/{events,block,lines,viewport,painter,selection,theme,style,clipboard}.py`、
  `keys/**`、`tests/golden/**`、`pyproject.toml`、`uv.lock`、`docs/CONTRACT.md`。
- 禁加：兼容 alias、旧名 re-export（`FocusRing` 不保留）。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。
- 遇到阻塞：写清阻塞点后停止，不越界自救。

## 交接包

完成后写 `specs/2026-10-20-1819-motui-1-2-contract/handoff/W6-interaction.md`（60–80 行，A/B/C）。

## 最终报告

工单状态表 / commit 清单 / 自测真实输出 / 新公开 API / 测试改动清单 / 解耦 grep 证据 /
偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
