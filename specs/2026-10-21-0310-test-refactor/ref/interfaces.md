# interfaces · test refactor

> 本操作的冻结接口。W0 之后不再变；worker 需要新 helper 时写 handoff，由 lead 合并后追加。

## 1. `tests/testing/` 公开接口（唯一共享测试方法入口）

所有测试一律：

```python
from tests.testing import (
    Clock, RecordingScreen, Rows, document, many, tick,
    key, press, release, motion, wheel, paste, resize,
    texts, rows, marked,
    ScriptedEvents, headless_tui, snapshot,
)
```

### 1.1 `events.py`

```python
def key(name: str, char: str = "") -> KeyEvent
def press(x: int, y: int, button: str = "left",
          modifiers: frozenset[str] = frozenset()) -> MouseEvent
def release(x: int, y: int, button: str = "left",
            modifiers: frozenset[str] = frozenset()) -> MouseEvent
def motion(x: int, y: int, button: str = "none",
           modifiers: frozenset[str] = frozenset()) -> MouseEvent
def wheel(x: int, y: int, direction: str = "down",
          modifiers: frozenset[str] = frozenset()) -> MouseEvent
def paste(text: str) -> PasteEvent
def resize(width: int, height: int) -> ResizeEvent
```

- `key` 的 `char` 默认空；可打印键用 `key("a", "a")`，空格用 `key("space", " ")`。
- `press`/`release` 是 left button；要别的按钮显式传。
- `wheel` 的 `direction` ∈ `up/down/left/right`，生成 `button="wheel_<direction>"`, `kind="wheel"`。
- 不提供 `hover`/`click` 包装：click 是 press + release，测试自己表达意图。

### 1.2 `doubles.py`

```python
class Rows:
    """Component double rendering one row per given text."""
    def __init__(self, *texts: str) -> None
    def render(self, width: int) -> list[Line]

class RecordingScreen:
    """Screen double: records writes, counts enter/leave, settable size/live."""
    def __init__(self, width: int = 80, height: int = 24, *, live: bool = True)
    width: int
    height: int
    live: bool
    writes: list[str]
    flushes: int
    entered: int
    left: int
    def write(self, s: str) -> None
    def flush(self) -> None
    def refresh_size(self) -> None
    def enter(self) -> None
    def leave(self) -> None
    @property
    def output(self) -> str
    def delta(self) -> str

def many(n: int) -> list[str]   # ["r0", ..., "r{n-1}"]

def document(*texts: str) -> Document   # one Rows block over exactly those rows
```

- 需要真实屏幕字节时用 `motui.kernel.HeadlessScreen`，不要用 `RecordingScreen`。
- `Rows` 渲染时忽略宽度；只有需要“宽度敏感”的 double 时才在测试内定义局部组件（不导出）。

### 1.3 `layout.py`

```python
def texts(component, width: int) -> list[str]          # [row.text for row in component.render(width)]
def rows(tui) -> list[str]                             # [row.text for row in tui.rows]
def marked(tui) -> list[str]                           # 每行 reverse 片段的文本；无则 ""
```

`marked` 只用于 selection/gesture 这类“看 overlay 标了哪些列”的测试；断言的语义是
“这些文本被选中”，不是具体样式字节。

### 1.4 `clock.py`

```python
class Clock:
    now: float
    def __init__(self, now: float = 0.0)
    def __call__(self) -> float
    def advance(self, seconds: float) -> None
    def install(self, tui) -> "Clock"    # tui.clock = self; 返回 self

def tick(tui, clock: Clock, count: int = 1, seconds: float = 0.05) -> None
```

用法：

```python
clock = Clock().install(tui)
clock.advance(0.05)
tui.tick()
```

### 1.5 `__init__.py`

重新导出上述全部名字，以及：

```python
from motui.testing import ScriptedEvents, headless_tui, snapshot
```

`__all__` 是上述名字的完整集合（`src/motui/testing.py` 本身不改）。

## 2. 测试文件硬规则

1. `tests/` 是包：每个测试子目录有 `__init__.py`；导入写 `from tests.testing import ...`。
2. 每个测试文件顶部 docstring 一句话说明该文件覆盖的公开契约。
3. 不读私有属性：除 `obj.__all__` / `__name__` / `__version__` 外，正则 `\._[a-z]` 零命中。
4. 不写 `time.sleep` / `asyncio.sleep`；需要让异步 pump 跑一帧时用公开的 `tui.tick()` / `tui.paint()`。
5. 不做精确全帧断言；需要视觉基线时交给 `tools/golden.py`。
6. 参数化上限：一个测试函数的 `parametrize` 不超过 20 个 case；超过说明应拆成语义测试或删冗余。
7. 每个测试函数 1–3 个断言；不为“多覆盖”堆无关断言。
8. 组件测试优先构造真实组件；不要为测试给组件加产品代码。
9. 删除的旧文件用 `git rm`，不在新文件里保留同名旧测试。
10. 测试名用英文、描述行为；不出现 `old`/`legacy`/`wave`/`migration`。

## 3. 旧文件 → 新文件映射

### 3.1 W1（kernel + keys）

| 旧 | 新 | 处置 |
|---|---|---|
| `tests/test_core_text.py` | `tests/kernel/test_text.py` + `test_lines.py` | 拆分：text 测量/换行/fit/ellipsize；Line/Segment 操作与簇边界 |
| `tests/test_style.py` | `tests/kernel/test_style.py` | 重写，删 hidden cache 测试 |
| `tests/test_theme.py` | `tests/kernel/test_theme.py` | 重写，删旧常量清单；吸收 `test_default_theme_paints_structure.py` 的 1 个不变量 |
| `tests/test_default_theme_paints_structure.py` | 删除 | 1 个不变量并入 theme |
| `tests/test_block.py` | `tests/kernel/test_block.py` | 重写，删缓存机制测试 |
| `tests/test_viewport.py` | `tests/kernel/test_viewport.py` | 重写，保留布局/offset/pinned |
| `tests/test_frame.py` | `tests/kernel/test_frame.py` | 重写，保留 rect/split/close/chrome/compose/ownership |
| `tests/test_painter.py` | `tests/kernel/test_painter.py` | 重写，保留 diff/非 live/cursor |
| `tests/test_screen.py` | `tests/kernel/test_screen.py` | 重写，保留 bracket/copy/color mode |
| `tests/test_selection.py` | `tests/kernel/test_selection.py` | 重写，保留 range/highlight/extract |
| `tests/test_ansi.py` | `tests/kernel/test_ansi.py` | 精简，保留字节契约 |
| `tests/test_cursor.py` | `tests/kernel/test_cursor.py` | 保留核心窗口策略 |
| `tests/test_glyphs.py` | `tests/kernel/test_glyphs.py` | 精简，删全表逐字节 |
| `tests/test_mark.py` | `tests/kernel/test_mark.py` | 保留 |
| `tests/test_clipboard.py` | `tests/kernel/test_clipboard.py` | 保留 |
| `tests/test_events.py` | `tests/kernel/test_events.py` | 重写，删 ScriptedEvents 自测 |
| `tests/test_keys.py` | `tests/keys/test_decoder.py` | 重写，保留 decode 矩阵的代表性 case |
| `tests/test_keys_sources.py` | `tests/keys/test_sources.py` | 精简，保留 console/pipe/lifecycle |
| `tests/test_decoder_fuzz.py` | `tests/keys/test_decoder.py` | 并入 2 个 invariant 测试 |
| — | `tests/keys/test_keymap.py` | 新增：三张默认表与派生关系（从 editing 测试移来） |
| `tests/test_container_hit.py` | **W2** | 归 widgets（容器 child_at） |

### 3.2 W2（widgets）

| 旧 | 新 | 处置 |
|---|---|---|
| `tests/test_widgets_editing.py` | `tests/widgets/test_editing.py` | 重写，删逐行 rewrap/revision 机制 |
| `tests/test_widgets_choice.py` | `tests/widgets/test_choice.py` | 重写，保留 cursor/window/activate/disabled |
| `tests/test_widgets_table.py` | `tests/widgets/test_data.py`（Table） | 合并 |
| `tests/test_widgets_list.py` | `tests/widgets/test_data.py`（List） | 合并 |
| `tests/test_widgets_basics.py` | `tests/widgets/test_navigation.py`（Tabs）+ `test_data.py`（Tree） | 拆分 |
| `tests/test_widgets_navlist.py` | `tests/widgets/test_navigation.py` | 合并 |
| `tests/test_widgets_menubar.py` | `tests/widgets/test_menubar.py` | 保留 |
| `tests/test_widgets_markdown.py` | `tests/widgets/test_markdown.py` | 重写，删缓存/流式内部等价 |
| `tests/test_widgets_syntax.py` | `tests/widgets/test_syntax.py` | 保留核心 |
| `tests/test_widgets_scroll.py` | `tests/widgets/test_scroll.py` | 重写，删 revision/snapshot |
| `tests/test_widgets_form.py` + `test_widgets_forms.py` | `tests/widgets/test_form.py` + `test_containers.py` | 合并；Collapsible 归 containers |
| `tests/test_widgets_containers.py` | `tests/widgets/test_containers.py` | 重写，删 sealed cache |
| `tests/test_widgets_dialog.py` | `tests/widgets/test_dialog.py` | 保留核心 |
| `tests/test_widgets_diff.py` | `tests/widgets/test_diff.py` | 保留 hunk 逻辑 |
| `tests/test_widgets_indicators.py` | `tests/widgets/test_indicators.py` | 保留核心 |
| `tests/test_widgets_action.py` | `tests/widgets/test_action.py` | 保留 Button/Checkbox/Link；跨组件 hover 收敛 |
| `tests/test_widgets_autocomplete.py` | `tests/widgets/test_autocomplete.py` | 保留 |
| `tests/test_widgets_combobox.py` | `tests/widgets/test_combobox.py` | 保留 |
| `tests/test_widgets_delegate.py` | `tests/widgets/test_delegate.py` | 精简 |
| `tests/test_widgets_bands.py` | `tests/widgets/test_bands.py` | 保留 |
| `tests/test_widgets_rows.py` | `tests/widgets/test_rows.py` | 保留 |
| `tests/test_glyph_vocabulary.py` | 删除 | 代表性 glyph 用例并入 choice/navigation |
| `tests/test_container_hit.py` | `tests/widgets/test_containers.py` | 合并，删 cache 测试 |

### 3.3 W3（app + interaction）

| 旧 | 新 | 处置 |
|---|---|---|
| `tests/test_app.py` | `tests/app/test_driver.py` + `test_hit.py` + `test_selection_overlay.py` | 拆分 |
| `tests/test_focus.py` | `tests/interaction/test_focus.py` | 重写 |
| `tests/test_pointer.py` | `tests/interaction/test_pointer.py` | 重写 |
| `tests/test_gesture.py` | `tests/interaction/test_gesture.py` | 重写，保留拖选/自动滚动/双击三击 |
| `tests/test_find.py` | `tests/interaction/test_find.py` | 保留 |
| `tests/test_modal.py` | `tests/interaction/test_modal.py` | 保留 |
| `tests/test_palette.py` | `tests/interaction/test_palette.py` | 保留 |
| `tests/test_overlays.py` | `tests/interaction/test_overlays.py` | 重写，保留 stats/toasts/tooltip |
| `tests/test_scrollbar.py` | `tests/interaction/test_scrollbar.py` | 重写，保留 strip/drag/page |
| `tests/test_commands.py` | `tests/interaction/test_commands.py` | 保留核心 |
| `tests/test_host.py` | `tests/interaction/test_host.py` | 保留协议/factory |

### 3.4 W4（lead）

| 旧 | 新 | 处置 |
|---|---|---|
| `tests/test_api_root.py` | `tests/test_api.py` | 只保留：每个 facade `__all__` 可解析、无私有名、根名字在层里有家 |
| `tests/test_packaging.py` | `tests/test_packaging.py` | 保留版本/元数据 1–2 个 |
| `tests/test_docs_claims.py` | 删除 | 文档不测 |
| `tests/test_readme_examples.py` | 删除 | README 不执行 |
| `tests/test_demo_model.py` | 删除 | demo IA 不是产品契约 |
| `tests/test_demo_topics.py` | 删除 | 改由 `tests/test_smoke.py` 兜底 |
| `tests/test_demo_protocol.py` | 删除 | 交互 smoke 归 W3 的组件测试；入口归 smoke |
| `tests/test_golden_frames.py` | 删除 | `tools/golden.py --check` 是唯一门禁 |
| `tests/test_render_invariants.py` | `tests/test_invariants.py` | 合并为 1–3 个测试，覆盖全部公开组件 × 边界宽度 |

## 4. 每个新文件的“必须覆盖”清单

### kernel

- `test_text.py`：`visible_width`（ASCII/宽字符/组合/ZWJ/VS16/控制符/tab）；`wrap_text`（空格/硬断/CJK/宽字符/width 0/1）；`fit_text`；`ellipsize_tail`；`Text` 的 render/streaming/width 边界。
- `test_lines.py`：`Line`/`Segment` 的 width/fit/fill/add/merge/styled/wrap/cut/slice/overlay/fuse；宽字符与簇不劈开。
- `test_style.py`：SGR 前缀、命名色/truecolor、属性顺序、merge、quantize 16/256、downgrade、`detect_color_mode`。
- `test_theme.py`：默认 token、frozen/replace、显式样式优先、组件从 theme 取样式；默认主题不刷背景/反色（1 个不变量）。
- `test_block.py`：`Block.render` 转发、seal、`Document` auto id/重复 id/get/remove/blocks snapshot/pin 校验。
- `test_viewport.py`：layout 尺寸/offset clamp/stick bottom/scroll_to/pinned 区域/ownership。
- `test_frame.py`：`Rect`、`Split` 比例、`Pane.close` 折叠/重分、`Chrome` budget、compose、ownership、overlay 顺序。
- `test_painter.py`：首帧/无变化零字节/单行 diff/尺寸变化全刷/非 live/光标。
- `test_screen.py`：headless 记录、alt-screen bracket、live/non-live、clipboard、color mode。
- `test_selection.py`：`Selection.between` 归一化、highlight 边界/宽字符、extract 跨 block/越界。
- `test_ansi.py`：光标/清屏/鼠标/同步/粘贴/OSC52/标题/超链接/光标形状。
- `test_cursor.py`：窗口策略、clamp、单行窗口。
- `test_glyphs.py`：seat/pair/宽度，代表性字形。
- `test_mark.py`：toggle/clear/顺序/前缀。
- `test_clipboard.py`：protocol、memory、screen 转发与拒绝。
- `test_events.py`：事件类型关系、frozen/值相等、默认字段、EventSource 协议。

### keys

- `test_decoder.py`：可打印/控制键、CSI/SS3、修饰键、SGR/X10/urxvt 鼠标、bracketed paste、跨 feed 组装、非法字节降级、fuzz 不变量。
- `test_keymap.py`：`DEFAULT_INPUT_KEYMAP` / `DEFAULT_EDITOR_KEYMAP` / `EDITOR_SUBMIT_KEYMAP` 的派生关系与关键绑定。
- `test_sources.py`：Windows console 记录→事件、VT 路径、pipe fallback、start/close/EOF 生命周期。

### widgets

每个文件至少覆盖该族每个公开类的：构造、`render` 形状、一个核心动作（move/click/activate/toggle）、结果语义、disabled/空输入边界。Markdown 另需：块级/行内规则、表格、任务列表、流式渲染安全、链接点击。Editing 另需：keymap 路由、undo/redo、选择、光标放置、只读。Data 另需：window/counter、click 映射、排序、mark。Navigation 另需：active item、click、group row。Form：字段栈、导航、values/validation/submit。Scroll：clip/offset/reveal/child_at/scrollbar。Dialog：confirm/prompt/按钮/关闭。Diff：hunk/context/numbers。Indicators：progress/slider/spinner。Action：Button/Checkbox/Link 的结果与 disabled。Containers：Panel 降级/Divider/Row/Column/Padding/Spacer/Collapsible。Delegate：转发与 child swap。Bands：优先级。Rows：StatusLine/ShortcutBar/Notice。Autocomplete/Combobox：过滤、选择、打开边界。Menubar：bar/context menu。

### app

- `test_driver.py`：document facade、scroll/reveal、read_event 路由、exit/run、split/pane、dock、run bracket、non-live dump、snapshot。
- `test_hit.py`：hit/hit_leaf/pane_at、越界、pane 内坐标、dock。
- `test_selection_overlay.py`：set_selection/highlight、scrolling、resize 清除、painted frame vs document view。

### interaction

- `test_focus.py`：注册/循环/trap/路由/click 首击聚焦。
- `test_pointer.py`：hover 进入/离开、click 派发、drag 不派发、detach。
- `test_gesture.py`：拖选范围、跨 block、copy_on_select、自动滚动、双击词/三击行、detach。
- `test_find.py`：查询、匹配顺序/大小写、步进 wrap、reveal、overlay。
- `test_modal.py`：打开/居中/scrim、键盘吞掉、escape、take_result、focus trap。
- `test_palette.py`：查询过滤、导航、enter/escape、modal 集成。
- `test_overlays.py`：Stats 读数、Toasts TTL/evict/点击、Tooltip 跟随/翻转。
- `test_scrollbar.py`：strip 几何、thumb、drag、page、detach。
- `test_commands.py`：注册/查找/match/invoke/disabled。
- `test_host.py`：Host 协议、factory、copy。

## 5. 用例目标区间（硬边界）

| 目录 | 旧用例 | 目标区间 |
|---|---|---|
| `tests/kernel` | ~480 | 150–220 |
| `tests/keys` | ~71 | 45–70 |
| `tests/widgets` | ~900 | 240–330 |
| `tests/app` + `tests/interaction` | ~440 | 150–220 |
| 根级（api/packaging/invariants/smoke） | ~330 | 12–30 |
| **合计** | 2190 | **600–850** |

低于下限：handoff 解释哪些行为无法合并；高于上限：先删重复，再考虑参数化。
