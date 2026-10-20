# W5a handoff · 组合层核心（ScrollView / Form / CommandRegistry / Clipboard）

## A · 交付

分支 `w5a-composition`；最后一个实现 commit 为 `a51b0eb`，handoff 为 HEAD；实现 commit 按提交顺序：

| commit | 内容 |
|---|---|
| `ab9af1a` | `kernel: the clipboard is one copy door -- Clipboard, ScreenClipboard and MemoryClipboard` |
| `ec2cccd` | `widgets: the composition window and form -- ScrollView, Field and Form` |
| `db67251` | `commands: the registry matches, resolves and invokes named actions -- Command and CommandRegistry` |
| `aff4481` | `docs: the composition layer is documented -- ScrollView, Form, CommandRegistry and Clipboard` |
| `a51b0eb` | `widgets: the scroll view takes a pre-render offset -- the window clamps on first paint` |

`git diff --stat main...HEAD`（HEAD 含本 handoff，80 行）：14 files changed, 2078 insertions(+), 7 deletions(-)；
无 golden、`docs/CONTRACT.md`、`pyproject.toml`、`uv.lock`、`app.py`、`keys/**`、`interaction/**`、
`widgets/markdown/**`、禁触组件文件改动；demo 页面未动。

新增公开签名（本波范围）：

```python
kernel.clipboard: Clipboard (runtime-checkable protocol) / ScreenClipboard(screen) / MemoryClipboard()
kernel facade: Clipboard, MemoryClipboard, ScreenClipboard
widgets.scroll: ScrollView(child, *, height=None, offset=0, scrollbar=False, theme=None)
  render / handle / scroll_up / scroll_down / scroll_to / reveal
  offset / total_rows / viewport_height / child_at / revision
widgets.form: Field(name, component, label="", validate=None, value=None, error=None)
  Form(fields, *, gap=0, index=0, on_submit=None, theme=None)
  index / fields / focus / move / handle / activate / take_result / render / child_at / revision
widgets facade: ScrollView, Field, Form
motui.commands: Command(name, description="", handler=None, keys=(), enabled=True)
  CommandRegistry(commands=()): add / remove / get / match / by_key / invoke / options
```

基线真实结果（Windows，HEAD 待提交 handoff）：

- `uv run pytest -q -p no:cacheprovider`：**1900 passed, 2 skipped**（基线 1811 + 89 新增）。
- `uv run python tools/golden.py --check`：`golden: 11 pages match`。
- `uv run python tools/framebench.py`：render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`（未变）。
- demo：`python -m motui < /dev/null` exit 0 / 70 行；`--pages` exit 0 / 792 行；API import（验收 5）：exit 0。
- 新增测试：`test_clipboard.py` 7、`test_widgets_scroll.py` 28、`test_widgets_form.py` 35、
  `test_commands.py` 19；`test_api_root.py` 同步两个 facade 清单，根 34 名未动。

## B · 偏差、取舍与约束

- **ScrollView 的几何以最后一次 render 为准**：`total_rows`、`viewport_height`、`child_at` 都读上次
  render 的 `(inner width, offset, height, total)`；第一次 render 前 `total_rows=0`，`reveal` 返回
  False；固定 `height` 的视图在首次 render 前接受滚动请求、在上限未知时先记下 offset，首次 render
  再 clamp；`height=None` 的视图永远不滚。offset 每次 render 时按 `max(0, total - height)` 再
  clamp，因此子组件缩短后窗口自动收回合法范围。
- **`reveal` 取最小移动**，不居中；`TUI.reveal` 的居中语义属于文档 viewport，这里不复用也不改它。
  行号 clamp 进 `[0, total-1]`，负行落到 0。
- **滚动键只在真的移动时返回 True**（`scroll_to` 的 changed 语义），边界键留给 host；wheel 同理。
  `KeyEvent(kind="release")` 被忽略。scrollbar 在内容放得下时整条画 THUMB（不画 TRACK），thumb
  长度 `max(1, h*h//total)`，按 offset 比例定位。
- **Form 的导航键**：字段自己的 `handle`（若实现 Controller）永远优先；`tab`/`down`、`s-tab`/`up`
  只在 index 真移动时消费，所以末尾 Tab 会交还 host；`enter` 总是消费（校验失败也已把 error 画出来）。
- **值提取**：`Field.value()` 优先，否则按 `value`/`text`/`checked`/`selected`/`marked` duck typing
  （callable 调用），绝不调用破坏性的 `take_result()`。`Field` 是可变的普通 dataclass，`error`
  由 Form 写回；`Form.fields` 返回构造时的 tuple。
- **CommandRegistry**：重复名 `add` 抛 `ValueError`（保留原名）；`get`/`remove` 缺名抛 `KeyError`；
  `invoke` 缺名同样抛 `KeyError`，disabled/无 handler 返回 None；`by_key` 返回第一条命中（含
  disabled，便于 host 解释），重复 key 先注册者胜；`match` 默认过滤 disabled；`options()` 含全部
  command（过滤是 match 的职责）。`keys` 在 `Command.__post_init__` 归一为 tuple。
- `motui.commands` 从 `widgets.choice` 取 `Option` 作 Palette 桥，不在根 facade 增加导出。
- 未改 demo 文案/页面，golden 未移动；W5b 的菜单层与本波无关。

## C · 关键位置与稳定区

- `src/motui/kernel/clipboard.py:33`（Clipboard）、`:46`（ScreenClipboard）、`:67`（MemoryClipboard）。
- `src/motui/widgets/scroll.py:47`（ScrollView）、`:125`（scroll_to）、`:141`（reveal）、`:234`（render）。
- `src/motui/widgets/form.py:43`（Field）、`:70`（Form）、`:219`（activate）、`:252`（render）。
- `src/motui/commands.py:29`（Command）、`:49`（CommandRegistry）、`:96`（match）、`:136`（options）。
- 测试：`tests/test_clipboard.py`、`tests/test_widgets_scroll.py`、`tests/test_widgets_form.py`、
  `tests/test_commands.py`；facade 清单在 `tests/test_api_root.py` 的 `LAYER_ALLS`。
- 稳定区（未触碰）：`kernel/{frame,viewport,painter,selection,theme,style,events,block,lines}.py`、
  `app.py`、`keys/**`、`interaction/**`、禁触 widgets、`tests/golden/**`、`docs/CONTRACT.md`、
  `pyproject.toml`、`uv.lock`、demo 页面。
- 未决：ScrollView 的滚动键/Wheel 绑定是否需要 keymap（当前硬编码，与组件库其他 `handle` 一致）；
  Form 与 W6 FocusManager 的接线（当前 Form 自己镜像 Focusable，不注册 focus ring）。
