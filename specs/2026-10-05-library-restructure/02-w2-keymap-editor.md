> ✅ 2026-10-05 @ 分支 lib-w2 — 已合并 main

# Spec W2 · keymap 体系 + Input 改造 + Editor(波次 W2)

> 分支 `lib-w2-keymap-editor`;前置:W1 已合并;深读:总纲、`src/mocode_tui/keys/events.py`(Key/Paste 形态)、`src/mocode_tui/widgets/input.py`(现状)、`src/mocode_tui/core/app.py`(`read_key` 与 scroll_keys)。

## 目标

把「键→编辑动作」的映射从宿主硬编码(demo 的 chat 循环)提炼为库的 keymap 体系:`Input` 改造为 keymap 驱动,新增多行 `Editor`。**只动 `keys/keymap.py`(新)、`widgets/input.py`、`widgets/editor.py`(新)及对应测试;其他文件零 diff。**

## 工单(按序执行,每项一个 commit)

### T1 `keys/keymap.py`

```python
Keymap = dict[str, str]   # 键事件名(Key.name)→ 动作名

DEFAULT_INPUT_KEYMAP: Keymap = {
    "left": "move_left", "right": "move_right",
    "home": "home", "end": "end",
    "c-a": "home", "c-e": "end",
    "backspace": "backspace", "delete": "delete",
    "up": "move_up", "down": "move_down",
    "c-u": "clear",
}

DEFAULT_EDITOR_KEYMAP: Keymap = {**DEFAULT_INPUT_KEYMAP, "enter": "newline"}  # Input 不含 enter
```

- 模块是纯数据 + 类型别名;动作名就是组件的方法名,不做动作注册表。

### T2 Input 改造为 keymap 驱动

- `Input(*, ..., keymap: Keymap | None = None)`:keymap 为 None 时用 `DEFAULT_INPUT_KEYMAP`;构造时存 `self.keymap`。
- 新增 `handle_key(key: Key | Paste, width: int) -> bool`:
  - `Paste` → 插入文本,返回 True;
  - `key.char` 可打印(非 None 且非控制名)→ `insert(char)`,返回 True;
  - `key.name in keymap` → 调用同名方法(无参),返回 True;
  - 其余返回 False(交还宿主路由 submit/palette/quit)。
- `handle_key` 需要 width 是因为 `move_up/move_down/cursor_position` 依赖视觉换行;签名以现状方法为准。
- 现有公开方法(insert/backspace/delete/move_*/home/end/clear/cursor_position)签名与语义**不变**;现有测试全部保持通过(可改 import,不改断言语义)。
- 新增 `tests/test_widgets_input_keymap.py` 或在现有 input 测试文件追加:默认 keymap 各键行为、自定义 keymap 覆盖(如 `"c-j": "clear"`)、未映射键返回 False、Paste 插入。

### T3 `widgets/editor.py` 新增多行 Editor

- `Editor(*, text="", placeholder="", style=None, prompt_style=None, cursor_style=None, theme=None, keymap=None, focused=True, max_rows: int | None = None)`。
- 多行缓冲区:内部 `list[str]` 行;`newline()` 在光标处断行;`insert` 支持含 `\n` 的文本(粘贴多行);`backspace` 在行首时并上行;`move_up/down` 跨行移动(列位置尽量保持)。
- `handle_key` 同 Input 语义,默认 `DEFAULT_EDITOR_KEYMAP`(enter → newline,即编辑器自身消费回车;submit 由宿主绑定其他键如 `c-enter`?——**裁决:enter 归编辑器换行,提交键不在库内定义,宿主用未被消费的键自行实现**)。文档字符串写明这一点。
- `render(width)`:每逻辑行按 wrap 规则折行渲染;`focused` 时块光标;空+focused 显示 dim placeholder;`max_rows` 限制渲染行数(超出时以光标所在视觉行为中心滚动窗口——实现简化为「保证光标可见的滑动窗口」)。
- `cursor_position(width) -> (row, col)` 与 Input 同语义,供 IME 锚点。
- `value` 属性读全文;`clear()`。
- 样式解析遵循 Theme 规则(显式 > theme > DEFAULT_THEME)。
- 新增 `tests/test_widgets_editor.py`:多行插入/断行/并行/光标跨行、wrap 渲染、placeholder、max_rows 窗口、keymap 自定义、handle_key 返回值语义。

## 验收

1. `uv run pytest -q` 全绿(贴真实输出,用例数列出)。
2. `uv run python examples/pi_demo.py < /dev/null | diff - specs/2026-10-05-library-restructure/ref/w1-demo-dump.txt` 为空(demo 未改,渲染不变)。
3. `uv run python -c "from mocode_tui.widgets.editor import Editor; from mocode_tui.keys.keymap import DEFAULT_EDITOR_KEYMAP"` 正常。

## 禁触清单

`src/mocode_tui/__init__.py`、`core/`、`keys/`(除新增 keymap.py)、`widgets/` 其他文件、`tests/test_api_root.py`、`examples/`、`docs/`、`README.md`、`pyproject.toml`。

## 最终报告格式

工单状态表 / commit 清单 / 门禁真实输出 / keymap 默认表全量 / Editor 与 Input 的行为差异清单 / 偏差与取舍 / 未决问题。
