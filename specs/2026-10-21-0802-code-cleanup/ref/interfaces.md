# Interfaces — code cleanup

## 冻结面（本操作期间零变化）

- `motui.__all__` 的 34 个名字。
- `motui.kernel` / `motui.keys` / `motui.widgets` / `motui.interaction` /
  `motui.app` / `motui.testing` 的 `__all__`。
- 所有组件的构造签名、公开属性、渲染结果与 `revision()` 快照。
- `tests/` 与 `tests/golden/topics/*`。

## W1a：Host 工厂协议（`motui.kernel.host`）

新增三个 `Protocol`，只用于类型；运行时仍是 `widgets.textfield.Input` /
`widgets.autocomplete.Autocomplete`。

```python
class OptionLike(Protocol):
    label: str
    value: object


class QueryInput(Protocol):
    text: str
    def clear(self) -> None: ...
    def insert(self, text: str) -> None: ...
    def handle(self, event: Event) -> bool: ...
    def render(self, width: int) -> list[Line]: ...


class FilterList(Protocol):
    def set_query(self, query: str) -> None: ...
    def move(self, delta: int) -> bool: ...
    def activate(self) -> bool: ...
    def take_result(self) -> OptionLike | None: ...
    def render(self, width: int) -> list[Line]: ...
```

`Host` 的方法签名改为：

```python
def make_input(self, **kwargs: object) -> QueryInput: ...
def make_autocomplete(
    self, options: Sequence[object], **kwargs: object
) -> FilterList: ...
```

`TUI` 的实现返回同一签名。`interaction/find.py` 与 `interaction/palette.py`
删除 `cast(Any, ...)`，直接使用协议类型。

三个协议同时加入 `kernel.host.__all__`（seam 的公开类型；不属于冻结的 facade 清单）。
依赖方向不变：`kernel.host` 只 import `kernel` 内部模块，不 import `widgets`。

## W1a：驱动生命周期（`motui.app`）

公开入口不变：

```python
async def run_session(self, body: Callable[[TUI], Awaitable[None]]) -> None
async def run_async(self) -> None
def run(self) -> None
```

内部合并为一个 `_run(body: Callable[[], Awaitable[None]])`，必须保持：

1. `_enter_run()` → 创建 pump task → `await body()`；
2. `KeyboardInterrupt` 转为 `exit()` 并继续 teardown；
3. 其他 `BaseException` 记为 `body_error`，teardown 后重新抛出；
4. body 正常结束但 pump 抛错时，重抛 pump 的错误；
5. `_teardown` 只调用一次，仍负责关源、重置 wake、最终帧与 dump。

`TUI.get` / `TUI.remove` 共用 `_holder(id)`：

- 无持有者 → `KeyError("no block with id …")`；
- 多持有者 → `ValueError("block id … is held by multiple panes: …")`；
- 单持有者 → 返回该 `Pane`。

## W1a：overlay 生命周期（`motui.interaction.overlays`）

`Tooltip` 与 `Stats` 共用一个私有基类（名称由实现定，建议 `_MountedOverlay`）：

- 构造时 `tui.frame.add_overlay(self, layer=...)`；
- `detach()` 幂等，第二次调用不碰 registry；
- 子类只提供自己的 layer 与 paint/readings。

`Toasts` 不并入：它还有 ticker 取消与 stack 清空，语义不同。

## W1b：行带共享实现（`motui.widgets.bands`）

新增 mixin，`__slots__ = ()`：

```python
class BandedRows:
    bands: RowBands
    focused: bool

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style: ...
    def _rest(
        self, line: Line, width: int,
        current: bool = False, hovered: bool = False, disabled: bool = False,
    ) -> Line: ...
```

`_band` 固定调用 `resolve_band(self.bands, current, hovered, self.focused, disabled)`。
`_rest` 固定调用 `rest(line, width, self._band(current, hovered, disabled))`。

继承者：`List`、`Tree`、`Select`、`NavList`。`Table` 保留自己的 `_row_band`，
但删除 `_rest` 包装，在 `render` 与 `header_line` 两处直接调用
`rest(line, width, band)`。`BandedRows` 加入 `bands.__all__`。

`RadioGroup` / `CheckboxGroup` 在 `choice.py` 内共用 `_FormGroup(Select)`：

- `labels` 属性；
- 表单 band 规则（hover > focused-active > ground，不做 unfocused dim）；
- `_apply_form_bands(hover_style, active_style)`：构造期用 `replace` 覆盖
  `RowBands` 的 `hover` / `active`。

公开构造签名与 `revision()` 元组顺序不得变化。`_FormGroup` 是 `choice.py` 内部
私有基类，不进 `__all__`。

## W2：标签条共享实现（`motui.widgets.strip`，新增私有模块）

```python
class ClampedCursor:
    _index: int
    _disabled_items: frozenset[int]
    disabled: bool
    @property
    def index(self) -> int: ...
    def select(self, index: int) -> bool: ...
    def move(self, delta: int) -> bool: ...


class LabelStrip(ClampedCursor, Themed):
    @property
    def _entries(self) -> Sequence[str]: ...   # 子类实现
    def click(self, row: int, col: int) -> bool: ...
    def hover_at(self, row: int, col: int) -> bool: ...
    def _hit(self, row: int, col: int) -> int | None: ...
    def _label_at(self, col: int) -> int | None: ...
    def _spans_of(self, line: Line) -> tuple[tuple[int, int, int], ...]: ...
    def render(self, width: int) -> list[Line]: ...
```

继承者：`Tabs`、`MenuBar`（`LabelStrip`）；`NavList` 只用 `ClampedCursor`。
`MenuBar.move` 在 `super().move()` 返回 `True` 后清除 `_pending`；
`Tabs` 没有 pending 语义。`Tabs`/`MenuBar` 的 `revision()` 保留在各自类中。

实际落地（W2）：`strip.py` 是内部模块，未加入 `motui.widgets.__all__`；
`ClampedCursor` 只做类型声明、不持有存储，`LabelStrip` 与 `NavList` 各自保留
`_index` / `_disabled_items` / `disabled` slots；`NavList` 的 MRO 为
`BandedRows, ClampedCursor, Themed`。Tabs 的私有 `_tab_at` 由继承的 `_label_at`
取代，不留别名。

## 错误语义（全操作不变）

- `Document.get` 缺 id → `KeyError`；`Document.add` 重复 id → `ValueError`。
- `Pane.split` 已 split / dock → `RuntimeError`；`Pane.close` root/container/dock → `RuntimeError`。
- `Frame.add_overlay` 未知 layer → `ValueError`；`remove_overlay` 未注册 → `ValueError`。
- `TUI.dock` 未知 edge → `ValueError`；同 edge 二次 dock → `RuntimeError`。
- `TUI.set_selection` 未知 pane → `ValueError`。

## 调用顺序（全操作不变）

- 驱动：`refresh` 标脏 → pump `tick` → `_paint_at` → `compose` → `apply_overlays` → `paint`。
- overlay：构造注册；`detach` 注销；`Find`/`Toasts` 的 `close` 只改状态，不注销。
- 事件：scroll 拦截 → focus policy → host dispatch → overlay → chrome → content。
