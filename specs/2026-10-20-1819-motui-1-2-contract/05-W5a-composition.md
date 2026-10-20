# W5a · 组合层核心（ScrollView / Form / CommandRegistry / Clipboard）
> 分支 `w5a-composition`；前置：W4b 已合并 @ `d819f74`；写入范围见下。
> 深读：`00-overview.md` D9、`ref/interfaces.md` §3、`docs/CONTRACT.md` §5/§6。

## 目标

补上“完整 TUI 库”缺的组合层核心：一个能裁剪/滚动任意子组件的 `ScrollView`；一个带字段导航、校验和
一次性结果的 `Form`/`Field`；一个 `Command`/`CommandRegistry`；一个 `Clipboard` 能力抽象。
**不改 demo 内容**，golden 不得移动（菜单层与 demo exhibits 归 W5b）。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §3 → `handoff/W4b-rowviews.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
  期望：1811 passed / 2 skipped；11 页 match；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
- 稳定区（勿重读）：W1–W4b 的 kernel/driver/事件/组件契约；`widgets/{action,choice,list,table,tree,tabs,navlist,textfield,dialog,collapsible,indicators,markdown}` 的现有行为。
- W4b 约束：`take_result()` 是唯一结果门；`RowBands.dim` 是未聚焦衰减；`Tabs/NavList.index` 只读；
  `disabled_items` 整体替换；demo 文案旧名保留（W7）。

## 工单（按序执行；HEAD 全绿即可）

### T1 `kernel/clipboard.py`（新）+ `kernel/__init__.py`

```python
@runtime_checkable
class Clipboard(Protocol):
    def copy(self, text: str) -> bool: ...

class ScreenClipboard:
    def __init__(self, screen: Screen) -> None: ...
    def copy(self, text: str) -> bool: ...   # screen.copy_to_clipboard

class MemoryClipboard:
    def __init__(self) -> None: self.text: str | None = None
    def copy(self, text: str) -> bool: ...
```

- kernel facade 导出 `Clipboard`/`ScreenClipboard`/`MemoryClipboard`。
- 测试：ScreenClipboard 调 screen、MemoryClipboard 记录、协议 runtime_checkable。
- 不改 `Screen.copy_to_clipboard` 语义。

### T2 `widgets/scroll.py`（新）：`ScrollView`

```python
class ScrollView(Themed):
    def __init__(self, child: Component, *, height: int | None = None,
                 offset: int = 0, scrollbar: bool = False, theme: Theme | None = None)
    def render(self, width: int) -> list[Line]
    def handle(self, event: Event) -> bool
    def scroll_up(self, n: int = 1) -> bool
    def scroll_down(self, n: int = 1) -> bool
    def scroll_to(self, offset: int) -> bool
    def reveal(self, row: int) -> bool
    @property offset -> int
    @property total_rows -> int
    @property viewport_height -> int
    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None
    def revision(self) -> object
```

- `height=None` 表示显示全部子 rows；此时滚动 no-op。
- `render`：子组件按 `width`（开启 scrollbar 时 `width-1`）渲染；按 offset 截取 height 行；
  不足补空白行；scrollbar 列用 `glyphs.TRACK`/`glyphs.THUMB`，`theme.scrollbar`/`theme.scrollbar_thumb`。
- `handle`：`up/down/page_up/page_down/home/end`；`MouseEvent(kind="wheel", button="wheel_up"/"wheel_down")`；
  只在真的移动时返回 True。
- `child_at`：可见行映射到 `offset + row` 的子组件行；scrollbar 列不归子组件。
- `revision`：子组件 revision（非 Revisioned 用 `id`）、offset、height、scrollbar。
- 测试：裁剪、补行、offset clamp、reveal、滚动键、wheel、child_at、scrollbar、sealed block 跟随子 revision。

### T3 `widgets/form.py`（新）：`Form` / `Field`

```python
@dataclass
class Field:
    name: str
    component: Component
    label: str = ""
    validate: Callable[[object], str | None] | None = None
    value: Callable[[], object] | None = None
    error: str | None = None

class Form(Themed):
    def __init__(self, fields: Sequence[Field], *, gap: int = 0, index: int = 0,
                 on_submit: Callable[[dict[str, object]], object] | None = None,
                 theme: Theme | None = None)
    @property index -> int
    @property fields -> tuple[Field, ...]
    def focus(self, target: int | str) -> bool
    def move(self, delta: int) -> bool
    def handle(self, event: Event) -> bool
    def activate(self) -> bool
    def take_result(self) -> dict[str, object] | None
    def render(self, width: int) -> list[Line]
    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None
    def revision(self) -> object
```

- 值提取：`Field.value()` 优先；否则按 `value`/`text`/`checked`/`selected`/`marked` 的属性 duck typing
  （callable 则调用）。不要调用 `take_result()`（破坏性）。
- focus：移动时给 `Focusable` 组件写 `focused`（旧的置 False，新的置 True）；非 Focusable 只跟踪 index。
- `handle`：先把事件交给当前字段的 `handle`（若实现 `Controller`）；它消费则返回 True。
  然后 `tab`/`down` 前进、`s-tab`/`up` 后退、`enter` 调用 `activate`；`PasteEvent` 交给字段。
- `activate`：对每个字段运行 `validate(value)`；任一错误写入 `field.error` 并返回 False；
  全部通过则 `take_result` 的 pending 为 `{name: value}`，调用 `on_submit`，返回 True。
- `render`：每字段可选 label 行、组件行、error 行；字段间 `gap` 空行；所有行 fit(width)。
- `child_at`：用 render 记录的 span 表映射到字段组件行。
- `revision`：字段名/label/error/value/子 revision、gap、index、theme。
- 测试：render/label/error、focus 移动、字段 handle 优先、校验失败/成功、on_submit、take_result、child_at、revision。

### T4 `motui/commands.py`（新）：`Command` / `CommandRegistry`

```python
@dataclass(frozen=True, slots=True)
class Command:
    name: str
    description: str = ""
    handler: Callable[..., object] | None = None
    keys: tuple[str, ...] = ()
    enabled: bool = True

class CommandRegistry:
    def __init__(self, commands: Iterable[Command] = ())
    def __iter__ / __len__
    def add(self, command: Command) -> None
    def remove(self, name: str) -> Command
    def get(self, name: str) -> Command
    def match(self, query: str, *, include_disabled: bool = False) -> list[Command]
    def by_key(self, key: str) -> Command | None
    def invoke(self, name: str, *args, **kwargs) -> object | None
    def options(self) -> list[Option]   # Palette 的桥：Option(name, command, description)
```

- `match`：name/description 的 case-insensitive 子串；默认只返回 enabled。
- `invoke`：disabled 或无 handler 返回 None；否则调用 handler。
- `options()` 从 `widgets.choice.Option` 构造；不要在 `motui.__init__` 增加根导出。
- 测试：add/remove/get/重复名、match、by_key、invoke、disabled、options。

### T5 facade、测试、文档

- `widgets/__init__.py` 导出 `ScrollView`、`Form`、`Field`；`tests/test_api_root.py` 同步。
- `kernel/__init__.py` 导出 clipboard 三件；`tests/test_api_root.py` 同步。
- `tests/test_widgets_scroll.py`、`tests/test_widgets_form.py`、`tests/test_commands.py`、`tests/test_clipboard.py`。
- `docs/COMPONENTS.md` 加四节（简短）；README 的组件列表补充；W7 重写整篇。
- **不改 demo 页面**；golden 必须不变。
- 跑验收，写 `handoff/W5a-composition.md`。不 merge/push/tag。

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；总数 ≥ 1811 + 新增
2. `uv run python tools/golden.py --check`：11 页全 match
3. `uv run python tools/framebench.py`：exit 0；render-hash 不变（贴值）
4. `uv run python -m motui < /dev/null`、`--pages`：exit 0
5. `uv run python -c "from motui.widgets import ScrollView, Form, Field; from motui.commands import Command, CommandRegistry; from motui.kernel import Clipboard, ScreenClipboard, MemoryClipboard"`：exit 0
6. `git diff --stat main...HEAD`：范围 = 本工单写范围并集，无 golden 变化

## 禁触清单

- 禁改：`widgets/{action,choice,list,table,tree,tabs,navlist,textfield,dialog,collapsible,indicators,decor,rows,layout,delegate}.py`、
  `widgets/markdown/**`、`kernel/{frame,viewport,painter,selection,theme,style,events,block,lines}.py`、
  `app.py`、`keys/**`、`interaction/**`、`tests/golden/**`、`pyproject.toml`、`uv.lock`、`docs/CONTRACT.md`。
- 禁加：兼容 alias、旧名 re-export；不要改根 34 名。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。
- 遇到阻塞：写清阻塞点后停止，不越界自救。

## 交接包

完成后写 `specs/2026-10-20-1819-motui-1-2-contract/handoff/W5a-composition.md`（60–80 行，A/B/C）。

## 最终报告

工单状态表 / commit 清单 / 自测真实输出 / 新公开 API / 测试改动清单 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题。
