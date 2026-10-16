# Spec base-components · W3 chat 拆解与下沉（波次 W3）
> 分支 `bc3-salvage`；前置：W2。深读：`00-overview.md`（D5/D6/D8、现状问题 4）。
> **最高约束：整包删除 `src/mocode_tui/chat/`，但先把两个通用件下沉到 `widgets/`；被删的名字同波
> 从全仓（源码、facade、测试、docstring、文档）清零，不留 shim / alias。**

## 目标

1. `StatusLine` 下沉 `widgets/statusline.py`（语义不变）。
2. `SlashPalette` **升级**为自带查询输入行的 `Palette`（`widgets/palette.py`，组合 `Input` + `Autocomplete`），
   画廊不再需要常驻 editor。
3. 删除整个 `chat/`（`Message` / `ToolBlock` / `EditBlock` / `Composer` / `Transcript` / `StreamHandle` /
   `SlashPalette` / facade）。
4. `COMPOSER_KEYMAP` → `EDITOR_SUBMIT_KEYMAP`。
5. `Theme` 收敛：删 `user_bg` / `tool_bg` / `code_bg` / `tones` / `title_tones`。
6. 测试与 docstring 同波迁移，全仓 grep 零残留。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| chat 包与 facade | `src/mocode_tui/chat/**`（6 模块 + `__init__`） |
| `StatusLine`（通用两侧行） | `chat/statusline.py`（含 `fuse` 的用法） |
| `SlashPalette`（query 由宿主 editor 喂） | `chat/slash.py` |
| `Composer` / `Transcript` / `StreamHandle` | `chat/composer.py` / `chat/transcript.py` |
| `Message` / `ToolBlock` / `EditBlock` | `chat/message.py` / `chat/tools.py` |
| keymap 表 | `keys/keymap.py:79`（`COMPOSER_KEYMAP`），facade `keys/__init__.py` |
| Theme 的 band 字段与派生表 | `core/theme.py`（`user_bg` / `tool_bg` / `code_bg` / `tones` / `title_tones`） |
| 引用 chat 的 docstring | `gesture.py:444` `widgets/layout.py:143` `widgets/__init__.py:18` `keys/__init__.py:19` `core/theme.py:152,157` `keys/keymap.py:27,74` |
| chat 测试 | `tests/test_chat_{components,composer,slash,statusline,transcript}.py` |

## 工单（按序执行，每项一个 commit）

### T1 `widgets/statusline.py`：`StatusLine` 下沉

- 把 `chat/statusline.py` 整体移到 `widgets/statusline.py`，**行为与渲染零变化**；
  去掉 docstring 里对 chat / 输入框的定位描述，改成「两列状态行」的通用说法。
- `widgets/__init__.py` 导出；root `__init__.py` 的 `StatusLine` 来源改为 `widgets`。
- 迁移测试：`tests/test_chat_statusline.py` → `tests/test_widgets_statusline.py`，只改 import 路径。
- 验证：迁移后该测试文件全绿，且渲染字节与迁移前一致（可留一条断言锁住一段样例）。

### T2 `widgets/palette.py`：`Palette`（SlashPalette 的升级版）

- 新类 `Palette(Themed)`，**自带查询输入行**，组合现有 `Input` 与 `Autocomplete`：
  ```python
  Palette(commands, *, theme=None, max_rows=8)
  # 字段：input: Input, list: Autocomplete, commands, chosen: str | None
  @property
  def is_open(self) -> bool
  def open(self) -> None        # 清空查询 + 全量列表 + chosen=None + is_open=True
  def close(self) -> None
  def handle(self, event: Key | Paste) -> bool
  def render(self, width: int) -> list[Line]   # 关闭时零行
  ```
- `handle`（打开时）：
  - `up` / `down` → `list.move(±1)`，清 `chosen`，消费；
  - `enter` → `list.activate()`；`chosen = list.chosen.value if list.chosen else None`；
    `list.chosen = None`；`close()`；消费；
  - `escape` → `close()`（`chosen=None`），消费；
  - 其余 → `input.handle(event)`；若消费则 `list.set_query(input.text)`，返回 `True`。
  - 关闭时一律 `False`（零行）。
- `render`：`[input.*, list.*]` 的行拼接（`input.render(width) + list.render(width)`）。
- docstring 写清：这是**自包含**的命令面板（自带查询行），与旧 `SlashPalette`（查询由宿主 editor 喂）
  的区别；`chosen` 契约不变（读一次清一次）。
- 迁移测试：`tests/test_chat_slash.py` → `tests/test_widgets_palette.py`，按新 API 重写
  （打开/过滤/上下/回车/Esc、`chosen` 读一次、关闭零行）。
- **不做**：不保留 `SlashPalette` 名字（D10 无 alias）。

### T3 删除 `chat/` 与 keymap 改名

- `git rm -r src/mocode_tui/chat/`。
- `keys/keymap.py`：`COMPOSER_KEYMAP` → `EDITOR_SUBMIT_KEYMAP`；docstring 改为
  「editor 表去掉 `enter`，宿主拿 submit 的通用表」；`keys/__init__.py` 的导入与 `__all__` 同步。
- 全仓删除对 chat 的 import / 名字（`__init__.py` 的 9 个导出、`widgets/__init__.py:18`、
  `keys/__init__.py:19`、`gesture.py:444`、`widgets/layout.py:143`、`keys/keymap.py:27,74`）。
- 删除 chat 测试：`test_chat_components.py` / `test_chat_composer.py` / `test_chat_transcript.py`
  （`statusline` / `slash` 已由 T1/T2 迁移）。
- 验证：`git grep -n "mocode_tui.chat\|from .chat\|from \.\.chat\|COMPOSER_KEYMAP"` 为空；
  `python -c "import mocode_tui"` 干净。

### T4 `core/theme.py`：Theme 收敛

- 删除字段 `user_bg` / `tool_bg` / `code_bg`。
- 删除派生表 `tones` / `title_tones`（连同 `_Tables` 的两个字段与 `__post_init__` 里对应的两行）；
  `_Tables` 只留 `headings` / `notice_levels`，模块 docstring 的「四张表」改「两张表」。
- 保留 `hover`（W1 加的）、`headings`、`notice_levels`、`scrollbar` / `scrollbar_thumb` / `toast` /
  `table_border` / `first_column`。
- 更新 `tests/test_theme.py`：删掉对已删字段/表的断言，保留字段级相等与派生表断言。
- **依赖确认**：全仓 grep 确认 `user_bg` / `tool_bg` / `code_bg` / `tones` / `title_tones` 只在已删的
  chat 组件与 demo（W5 重写）里出现；若仍有源码消费者，**停下上报**。

### T5 facade / export / 文档引用同波

- root `__init__.py`：删 `from .chat import ...`；`StatusLine` 改从 `widgets`；新增 `Palette` 导出
  （`SlashPalette` 删）。`__all__` 同步（分组顺序不变）。
- `widgets/__init__.py`：导出 `Palette` / `StatusLine`。
- `tests/test_api_root.py`：删 `import mocode_tui.chat as chat`、`LAYER_ALLS["mocode_tui.chat"]`、
  `DOWN_LISTED["mocode_tui.chat.composer"]`、`keys` 里的 `COMPOSER_KEYMAP`（改 `EDITOR_SUBMIT_KEYMAP`）、
  widgets 列表加 `Palette` / `StatusLine`（`Button`/`Checkbox`/`Link` 由 W2 加，本波一起对账）。
  **本波先把 pin 改到「与当前代码一致」；W4 再做最终定稿。**
- `docs/DESIGN.md` / `docs/COMPONENTS.md` / `README.md` 里所有 chat 段落下沉为
  「StatusLine / Palette」或删除（大改放在 W4，本波只做**不再指向已删模块**的最小修正，
  例如把 `mocode_tui.chat.composer.Composer` 的交叉引用删掉）。
- 验证：`uv run pytest -q` 全绿；`git grep "chat"` 只剩 W5 之前的 demo 引用（`examples/`）与
  本 spec 自身。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → 贴 before/after；已删测试文件列出，新增/迁移测试文件列出。
2. `git grep -n "mocode_tui.chat\|from .chat\|from \.\.chat\|COMPOSER_KEYMAP\|SlashPalette\|ToolBlock\|EditBlock\|Transcript\|Composer" -- src tests` → **为空**（`examples/` 除外，W5 处理）。
3. `python -c "from mocode_tui import Palette, StatusLine, EDITOR_SUBMIT_KEYMAP; print('ok')"` → `ok`；
   `python -c "import mocode_tui.chat"` → **ImportError**（证明删除干净）。
4. `Palette` 探针（贴输出）：`open()` → `handle(Key("a"))` 过滤 → `enter` 取 `chosen`；
   `escape` 关闭；关闭时 `render` 零行。
5. `StatusLine` 迁移字节证据：迁移前后同一 `left/right` 的 `render(40)` 文本 + `Segment` 样式一致。
6. `Theme` 收敛证据：`dataclasses.fields(Theme)` 打印，确认三个 band 字段与两张 tone 表消失、
   `hover` 存在。
7. `uv run python examples/demo.py < /dev/null` 此时**预期失败**（旧 demo 仍 import chat）——
   报告里如实标注「W5 前 demo 不可用，属计划内」，并贴失败类型；**不得**为此在 W3 回填兼容层。

## 禁触清单

- `examples/`（W5 的活，本组内允许其暂时不可运行）
- W2 刚加的 `pointer.py` / 新原语 / `hover_at`（除非只是 `__init__` 导出对账）
- `core/` 的 render 路径（除 `theme.py` 的字段删改）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + pytest 数）/
grep 零残留证据 / `Palette` 探针 / `StatusLine` 字节证据 / `Theme` 字段清单 /
「demo 计划内不可用」的如实说明 / 偏差与取舍 / 未决问题 / 真机手测：无（库层，无真机项）。

遇到阻塞（有源码消费者仍用删掉的 Theme 字段、`Palette` 需要改 `Autocomplete` 契约、
测试数出现非计划变化）：**停下上报，不越界自救**。
