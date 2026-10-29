# W4a · Foundation

> 分支 `w2.1.2-w4a-foundation`；起点 main @ `314c973`（W1–W3 已合并）。
> 写入范围：`src/motui/widgets/base.py`、`strip.py`、`action.py`、
> `src/motui/app/focus.py`、`tests/widgets/test_base.py`、`test_action.py`、
> `test_contracts.py`、`tests/app/test_focus.py`。
> 最高约束：**现有渲染字符零变化**；其他组件本波只做能跑的最小适配。

## 目标

在 `widgets/base.py` 落三个共享基类和 `Keymap` 描述符，把 Button/Checkbox/
Link 迁到 `ActionWidget`，并给焦点层加 `space` 激活回退。W4b/W4c 会以此为
基础迁移 Choice/Navigation 和 Text/Form 家族。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §1–§7 →
  `handoff/W1-zcode.md` → `handoff/W2-zcode.md` →
  `handoff/W3-deepseek-v4.1-flash.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：

```bash
uv run pytest -q tests/widgets/test_base.py tests/widgets/test_action.py tests/widgets/test_contracts.py tests/app/test_focus.py
uv run pytest -q -p no:cacheprovider
uv run python tools/semantic.py --check
```

- 基线事实：1700 tests；semantic 9/9；`api.py --check` 243 names match；
  `tools/api-2.1.txt` 由 lead 独占，worker 不提交。
- 稳定区（勿重读）：`kernel/`、`widgets/layout.py`、`widgets/canvas.py`、
  `widgets/pixel_canvas.py`、`widgets/drawing.py`、`app/` 其余文件。
- 已知约束：
  - `strip.py` 的类名是 `Keymap`（不是 `KeymapDescriptor`）。
  - 其它组件目前从 `strip.py` import `Keymap`；本波保留
    `strip.py` 的 re-export，避免改 8 个文件。
  - `Widget.__setattr__` 对公开属性赋值自动 `touch()`；下划线属性静默。
  - `Widget` 可以用 `object.__setattr__` 安装初始状态。
  - `app/focus.py` 的 `FocusManager.handle` 目前只对 `enter` 做
    `activatable` 回退；space 的 key 名是 `"space"`。
  - `ResultWidget` 的合法 `None` 结果必须与“无 pending”区分；take 读取即清空。
  - `CursorWidget` 的 `_cursor` 是内部 `Cursor` 值；空集合 `index == 0`，
    `selected is None`；移动/选择清 pending。
  - 测试用 `inspect.signature` 检查 keyword-only 时，注意 `Widget` 的
    `theme/styles` 仍是位置参数（本波不改基类构造）。

## 工单（按序执行，每项一个 commit）

### T1 `ResultWidget` + `ActionWidget`

- 在 `widgets/base.py` 增加：

```python
_MISSING = object()

class ResultWidget(Widget):
    __slots__ = ("_result",)
    def __init__(self, theme=None, styles=None): ...
    def _emit(self, value: object) -> None      # 写 pending + touch
    def _clear_result(self) -> bool             # 有 pending 才清并 touch
    def take(self) -> object | None             # 读一次即清；合法 None 用 sentinel

class ActionWidget(ResultWidget):
    __slots__ = ("disabled", "hint")
    activatable = True
    def __init__(self, *, disabled=False, hint="", theme=None, styles=None): ...
    def activate(self) -> bool: return False
    def toggle(self) -> bool: return False
    def on_click(self, pos) -> bool: return self.activate()
    def on_action(self, name) -> bool   # activate/toggle 委托；未知 False
```

- `action.py`：Button/Checkbox/Link 改为继承 `ActionWidget`；删除各自的
  `_pending`/`take`/`on_action`/`on_click` 重复实现；实现：
  - `Button.activate()`：disabled → False；否则 `_emit(True)`。
  - `Link.activate()`：同 Button。
  - `Checkbox.activate()` → `toggle()`；`toggle()`：disabled → False；
    翻转 `checked`；`_emit(self.checked)`。
- 保留 `hint` 的现有语义（Tooltip 协议，默认 `""`）。
- 删除子类 `__slots__` 里的 `_pending`/`hint`/`disabled`（由基类提供），
  避免重复 slot。
- 只改 `base.py`、`action.py`。
- 验证：`uv run pytest -q tests/widgets/test_action.py`；改动文件单跑
  `ruff --config "exclude=[]"`。

### T2 `Keymap` 移到基类

- 把 `Keymap` 类从 `strip.py` 移到 `base.py`（实现保持不变：类上返回
  `table`，实例上返回 `_keymap`；`__set__` 替换实例副本）。
- `Widget` 增加 `keymap = Keymap({})` 类属性；`__slots__` 增加 `_keymap`；
  `Widget.__init__` 用 `object.__setattr__(self, "_keymap",
  dict(type(self).keymap))` 初始化。
- `strip.py` 改为 `from .base import Keymap` 并保留 `__all__` 的 re-export；
  `LabelStrip.__slots__` 删除 `_keymap`，`__init__` 删除重复的
  `self._keymap = dict(type(self).keymap)`。
- 其它组件本波不动（它们自己的 `_keymap` slot/赋值可以继续工作；W4b/W4c
  删除）。
- 只改 `base.py`、`strip.py`。
- 验证：`uv run pytest -q tests/widgets/test_base.py tests/widgets/test_navigation.py tests/widgets/test_choice.py`
  （keymap rebind 不污染类表的既有用例必须继续绿）。

### T3 `CursorWidget`

- 在 `base.py` 增加：

```python
class CursorWidget(ResultWidget):
    __slots__ = ("_cursor",)
    def __init__(self, theme=None, styles=None): ...   # Cursor(0)
    def _entry_count(self) -> int: return 0
    def _entry_at(self, index: int) -> object | None: return None
    def _cursor_disabled(self) -> Iterable[int]: return ()
    def _cursor_wraps(self) -> bool: return False
    def _page_size(self, size: int) -> int: return size
    @property index -> int
    @property selected -> object | None
    def select(self, index) -> bool
    def move(self, delta) -> bool
    def home(self) -> bool
    def end(self) -> bool
    def on_action(self, name) -> bool   # 九个动作名
    def _sync_cursor(self) -> None       # 更新 count/disabled/wrap/clamp
```

- `select`/`move`/`home`/`end` 先 `_clear_result()`，再操作 `_cursor`，变化时
  `touch()`；`on_action("prev")` 返回 `move(-1)` 的真实结果，
  `page_prev/page_next` 用 `_page_size`。
- `selected` 空集合返回 None；`index` 空集合为 0。
- 本波不做消费者迁移；在 `tests/widgets/test_base.py` 用一个
  `_CursorProbe(CursorWidget)` 覆盖：空集、clamp、disabled 跳步、wrap 开关、
  `selected` 类型、移动清 pending、`on_action` 九名、page 步长。
- 只改 `base.py`、`tests/widgets/test_base.py`。
- 验证：`uv run pytest -q tests/widgets/test_base.py`。

### T4 焦点层 `space` 回退

- `app/focus.py` 的 `FocusManager.handle`：在 `on_key` 之后，对
  `activatable` 目标接受 `enter` 和 `space` 两个键：
  `if event.key in ("enter", "space") and ...: return self._activate(target)`。
- `tests/app/test_focus.py` 增加：Button/Checkbox 聚焦时 space 激活；
  Input/Editor 自己消费 space（不被回退抢走）；非 activatable 目标 space
  不消费。
- 只改 `app/focus.py`、`tests/app/test_focus.py`。
- 验证：`uv run pytest -q tests/app/test_focus.py tests/widgets/test_action.py`。

### T5 基类契约矩阵

- 扩展 `tests/widgets/test_contracts.py`（W4a 独占）：
  - `ResultWidget`: take 一次清空；`_emit(None)` 后 take 返回 None 且内部
    pending 清空；`_clear_result` 的返回值。
  - `ActionWidget`: `on_action("activate")` 委托 `activate()`；
    `on_action("toggle")` 委托 `toggle()`；disabled 全拒绝；`on_click` 走
    `activate`。
  - `CursorWidget`: 构造/状态/动词/keymap 默认表的契约。
  - `Keymap`: 类默认表、实例副本、rebind 不污染类表、`Widget` 默认空表。
- 只改 `tests/widgets/test_contracts.py`。
- 验证：`uv run pytest -q tests/widgets/test_contracts.py`。

## 验收

1. 全量 `uv run pytest -q -p no:cacheprovider` 全绿（贴用例数/失败项）。
2. `uv run ruff check .`、`uv run pyright`、`uv run lint-imports` 全绿；
   改动文件单跑 `ruff --config "exclude=[]"` 全绿。
3. `uv run python tools/semantic.py --check` 全绿（字符零变化）。
4. `uv run python tools/api.py --check` 全绿（本波不新增 facade 名；若因
   `Widget` 内部变化出现差异，贴给 lead，不改快照）。
5. `uv run python tools/framebench.py` 的 `render-hash` 不变。

## 禁触清单

`kernel/`、`widgets/layout.py`、`widgets/canvas.py`、`widgets/pixel_canvas.py`、
`widgets/drawing.py`、`widgets/choice.py`、`list.py`、`table.py`、`tree.py`、
`tabs.py`、`menubar.py`、`navlist.py`、`combobox.py`、`autocomplete.py`、
`text.py`、`textfield.py`、`form.py`、`dialog.py`、`collapsible.py`、
`decor.py`、`indicators.py`、`demo/`、`docs/`、`tools/`、`pyproject.toml`。
`handoff/W4a-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W4a-<agent>.md`：基类签名与钩子、`Keymap` 的 lazy/初始化规则、
ActionWidget 的 pending 规则、CursorWidget 的 `_sync_cursor` 约束、space
回退的路由顺序、给 W4b/W4c 的迁移提示。

## 最终报告

同 W1 模板。
