# W1 · 内核拆分（机械迁移，行为零变化）

> 分支 `2.0/w1-kernel`；前置：W0b 已合并（`33c82be`）；写入范围：`src/motui/**`、`tests/**`、`tools/api.py`、`tools/api-2.0.txt`、`pyproject.toml`
> 权威：`ref/source/10-waves/W1-kernel-split.md`、`01-architecture.md`、`08-terminal-io.md`

## 目标

把 1.x 的 `core/` 拆成 **kernel（纯值/协议）+ terminal（I/O）**，删除 `core/` 包；
把 `frame.py` 拆成 geom/frame/hit/overlay，`viewport+scroll` 合成 layout，`block` 更名 `document`；
`Screen` 从 Protocol 改 ABC。**本波只做文件与边界迁移，不改渲染/交互行为。**

**本波结束：demo 两条命令逐字节不变；57 golden 不变；render-hash 仍为 `a82f7968…`；`grep -r "from .*core" src/motui tests` 为空；`kernel` 不 import 任何 I/O。**

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W0a-values.md` → `handoff/W0b-harness.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider     # 1017 passed
  uv run python tools/golden.py --check    # 57 topics match
  uv run python tools/framebench.py        # hash a82f7968…
  ```
- 稳定区（已验收，勿重读）：`src/motui/kernel/{geom,cell,layout,text}.py` 的 W0 值语义、`tests/kernel/**`（除非迁移测试导入）、`tools/golden.py`、`tools/framebench.py`、`tests/golden/**`、`src/motui/demo/**`（只改 import）。
- 已知坑：
  - `Rect` 在 W0 是 `kw_only`，测试断言 `Rect(0,0,1,1)` 抛 `TypeError`；全仓有 128 处 `Rect(...)` 位置参数，必须用 codemod 改成关键字参数，**不要**放宽 `kw_only`。
  - `core/lines.py` 的 `Line.styled()` / `styled_with()` 构造 SGR/OSC8 字节；kernel 不能 import terminal。见下方 D1。
  - `core/style.py` / `theme.py` / `text.py` 里的 `os` / `shutil` 只服务 `detect_color_mode` / `Theme.auto` / `terminal_size`；必须把这些 I/O 函数搬到 terminal，kernel 只留纯值。
  - `core/keys` 实际不存在；键盘表在 `core/keymap.py`，纯值，移 `kernel/keymap.py`。
  - `tests/core/test_clipboard.py` 用鸭子类型 `_RecordingScreen`；不要把 `Screen` ABC 变成运行时强制。
  - `tests/test_invariants.py` 会扫描 `widgets.__all__` 的 `Component` 子类；`Text` 进入 widgets 后必须补一个 CASES 工厂。
  - `tools/api.py` 的 FACADES 硬编码了 `motui.core`；改后必须 `--update`。
  - ruff/pyright 有 ratchet；迁移后的旧代码不要为了 lint 大改行为，按 D6 调整 ratchet。

## 已定决策（开工前先读，不要另选）

### D1 字节构造全部留在 terminal

- `core/painter.py` → `terminal/paint.py`（`Painter`）。
- `core/lines.py` 的 `Line.styled` / `styled_with` / `_segment_bytes` → 新 `terminal/render.py`：
  ```python
  def styled_line(line: Line, mode: ColorMode = "truecolor") -> str
  ```
  用模块级 `@lru_cache(maxsize=4096)` 保持旧缓存语义；truecolor/其他模式输出与 1.x 逐字节一致。
- kernel `Line` **删除** `styled()`；`Line` 保留 `segments/text/width/fit/fill/...`。
- 所有调用点（`Painter`、tests）改 `styled_line(line, mode)`。
- 记录：2.0 的 `Line.styled(mode)` 词表改为 `terminal.render.styled_line`；W5 文档按此写。

### D2 Screen ABC

- `terminal/screen.py`：`class Screen(ABC)`，`TerminalScreen` / `HeadlessScreen` 继承。
- 成员：`width`/`height`/`size`/`live`/`color_mode`/`encoding`/`enter`/`leave`/`write`/`flush`/`refresh_size`/`close` 为抽象或具体默认；`copy_to_clipboard` 本波保留（带默认 `False`），W4 移到 Clipboard 能力时删除。
- 删除 `@runtime_checkable Protocol`；不要在库里对 Screen 做 `isinstance` 检查（当前没有）。
- `Painter` 类型标注用 `Screen`（terminal 内部）。

### D3 Rect 关键字化

- 用一次性 codemod（AST 或 tokenize，跑完删除脚本）把全仓 `Rect(a, b, c, d)` 改成 `Rect(x=a, y=b, width=c, height=d)`；覆盖 `src/`、`tests/`、`tools/`。
- 只改调用形式，不改表达式；改完 `grep -rn "Rect("` 人工抽查 10 处嵌套表达式。
- `kernel/geom.Rect` 保持 `kw_only`；`Split`/`Pane`/`Frame` 全部用它。

### D4 Block → Section（只改名，不改变字段）

- `core/block.py` → `kernel/document.py`；`class Block` → `class Section`。
- `Document.add/get/remove` 返回 `Section`；字段仍是 `id/component/pin`（`widget/placement` 留 W4）。
- 全仓把类型名 `Block` 改为 `Section`（变量名 `block` 可保留）；更新 `__all__`、导入、测试、demo。
- `Component` 与能力协议（Clickable/Activable/...）本波留在 `kernel/document.py`；W3 删。

### D5 临时归属（W3 再合并）

- `core/widget.py` → `widgets/base.py`（旧 `Widget` 基类；W3 扩成树/hooks）。
- `core/cursor.py` → `widgets/cursor.py`；`core/mark.py` → `widgets/mark.py`（W3 并入 `widgets/base.py`，本波不合并）。
- `core/lines.py:Text` → `widgets/text.py`；`widgets/__init__.py` 导出 `Text`；root `motui` 从 `.widgets` 取 `Text`。
- `core/keymap.py` → `kernel/keymap.py`（纯表）。
- `core/hit.py` → `kernel/hit.py`；`EveryHandle`/`RowRange` 本波暂留（W4 移到 runtime/layout）。
- `core/chrome.py` → 并入 `kernel/frame.py`（`Separator`）。
- `core/overlay` 不存在：把 `frame.py` 里的 `Overlay` Protocol、层常量、`apply_overlays` 拆到 `kernel/overlay.py`。
- `core/style.py` → `kernel/style.py`（去掉 `detect_color_mode`）。
- `core/glyphs.py` → `kernel/glyphs.py`。
- `core/theme.py` → `kernel/theme.py`；`Theme.auto(env)` **要求显式 env**；新增 `terminal/capability.py:auto_theme(env=None)` 负责读 `os.environ`。更新测试；没有生产调用者。
- `core/text.py` → `kernel/text.py`（去掉 `terminal_size`，去 `shutil`）；`terminal/capability.py` 提供 `terminal_size()`。
- `core/style.py:detect_color_mode` → `terminal/capability.py`（保留 `env=None` 读 `os.environ`）。

### D6 静态护栏调整（诚实 ratchet）

- `pyproject.toml [tool.pyright]`：include 仍是 `kernel`/`testing`/`tools`；因为 kernel 现在含 1.x 迁移代码，允许 `typeCheckingMode = "basic"` + 顶层 `strict = ["src/motui/kernel/geom.py", "src/motui/testing", "tools/api.py", "tools/growth.py"]`。**W0b 已 strict 的文件必须继续 strict**；在 handoff 记录哪些迁移文件待 W2/W3 收紧。
- `[tool.ruff]`：删除 `src/motui/core`（已不存在）；把 `src/motui/terminal` 与迁移后的 `kernel` 旧模块加入显式 ratchet，或按文件 `per-file-ignores`；`ruff check .` 必须 0。清理波次写 handoff。
- `[tool.importlinter]`：保留两个 kernel 契约；新增：
  - `widgets may not import terminal/app`（forbidden source `motui.widgets`, targets `motui.terminal`, `motui.app`）
  - `terminal may not import widgets/app`（forbidden source `motui.terminal`, targets `motui.widgets`, `motui.app`）
  - kernel 的 forbidden 列表去掉 `motui.core`，加 `motui.testing`。
- `tools/api.py`：FACADES 改为 `motui`、`motui.kernel`、`motui.terminal`、`motui.widgets`、`motui.app`、`motui.testing`；`uv run python tools/api.py --update` 重录 `tools/api-2.0.txt`。

## 工单（分两段；同一 worktree/分支，全部完成后一次合并）

### W1a · terminal 迁移与字节边界

#### T1 建 `terminal/` 包并移动 I/O 模块
- `git mv src/motui/core/ansi.py src/motui/terminal/ansi.py`
- `git mv src/motui/core/screen.py src/motui/terminal/screen.py`
- `git mv src/motui/core/decoder.py src/motui/terminal/decoder.py`
- `git mv src/motui/core/sources.py src/motui/terminal/keys.py`
- `git mv src/motui/core/console.py src/motui/terminal/win32.py`
- `git mv src/motui/core/clipboard.py src/motui/terminal/clipboard.py`
- `git mv src/motui/core/painter.py src/motui/terminal/paint.py`
- 新建 `src/motui/terminal/__init__.py`（导出见 T5）与 `terminal/capability.py`（`terminal_size`、`detect_color_mode`、`auto_theme`）。
- 修这些模块内部的相对导入（`.ansi`/`.events`/`.style`/`.text` → `.ansi`/`..kernel.events`/`..kernel.style`/`..kernel.text` 或 capability）。
- 验证：`uv run python -c "import motui.terminal"`（此时 core 仍在，允许中间态）。

#### T2 `Screen` ABC + canvas 字节边界
- 按 D2 改 `terminal/screen.py`。
- 新建 `terminal/render.py`：从 `core/lines.py` 搬来 `_segment_bytes`/`styled_with` 与 `Line.styled` 的实现，命名 `styled_line`；`terminal/paint.py` 改调用它。
- `core/lines.py` 删除 `styled_with`/`_segment_bytes`/`Line.styled`；保留其余（暂时仍在 core，W1b 移动）。
- 更新 `Painter`/tests 的调用点。
- 验证：`uv run pytest -q tests/core/test_painter.py tests/core/test_lines.py`（tests 已改 import 或临时仍指向 core；以最终 W1b 为准）。

### W1b · kernel 迁移、Section、删 core

#### T3 建 `kernel/` 剩余模块
- `git mv src/motui/core/frame.py src/motui/kernel/frame.py`；把 `Rect` 类删除（用 `kernel.geom.Rect`），`Rect(...)` codemod；把 `Overlay`/层常量/`apply_overlays` 拆到 `kernel/overlay.py`；`core/chrome.py` 的 `Separator` 并入 `kernel/frame.py`。
- `git mv src/motui/core/viewport.py src/motui/kernel/layout.py` 会与 W0 `layout.py` 冲突：不要 mv 覆盖；把 viewport 内容**合并进** `kernel/layout.py`（保留 W0 的 `Constraints`/`ScrollAxis`/`Scroll`），把 `core/scroll.py` 的 `ScrollState`/`Scrollable` 也合并进去，删除两个旧文件。
- `git mv src/motui/core/block.py src/motui/kernel/document.py`；按 D4 改名 `Section`。
- `git mv src/motui/core/selection.py src/motui/kernel/selection.py`
- `git mv src/motui/core/events.py src/motui/kernel/events.py`
- `git mv src/motui/core/keymap.py src/motui/kernel/keymap.py`
- `git mv src/motui/core/hit.py src/motui/kernel/hit.py`
- `git mv src/motui/core/chrome.py` → 已并入 frame.py 后删除。
- `git mv src/motui/core/style.py src/motui/kernel/style.py`（去掉 `detect_color_mode`/`os`）
- `git mv src/motui/core/glyphs.py src/motui/kernel/glyphs.py`
- `git mv src/motui/core/theme.py src/motui/kernel/theme.py`（按 D5 处理 `auto`）
- `git mv src/motui/core/text.py src/motui/kernel/text.py` 会与 W0 `text.py` 冲突：保留 W0 的 `WrapMode`/`__all__`，把旧 `text.py` 的函数合并进来，去掉 `terminal_size`/`shutil`。
- `git mv src/motui/core/lines.py src/motui/kernel/cell.py` 会与 W0 `cell.py` 冲突：保留 W0 的 `Cell`/`Surface`，把旧 `Segment`/`Line`/自由函数合并进来；`Text` 移到 `widgets/text.py`；删除 `styled` 部分（已在 T2）。
- `git mv src/motui/core/widget.py src/motui/widgets/base.py`
- `git mv src/motui/core/cursor.py src/motui/widgets/cursor.py`
- `git mv src/motui/core/mark.py src/motui/widgets/mark.py`
- 新建 `widgets/text.py`（`Text`）；`widgets/__init__.py` 导出它。
- 删除 `src/motui/core/__init__.py` 与空 `core/` 目录。

#### T4 import 全量改写
- 建一张映射表（写进脚本）并按最长模块名优先替换：
  `core.ansi→terminal.ansi`、`core.screen→terminal.screen`、`core.decoder→terminal.decoder`、`core.sources→terminal.keys`、`core.console→terminal.win32`、`core.clipboard→terminal.clipboard`、`core.painter→terminal.paint`、`core.style→kernel.style`、`core.glyphs→kernel.glyphs`、`core.theme→kernel.theme`、`core.text→kernel.text`、`core.lines→kernel.cell`、`core.block→kernel.document`、`core.viewport→kernel.layout`、`core.scroll→kernel.layout`、`core.frame→kernel.frame`、`core.hit→kernel.hit`、`core.selection→kernel.selection`、`core.events→kernel.events`、`core.keymap→kernel.keymap`、`core.cursor→widgets.cursor`、`core.mark→widgets.mark`、`core.widget→widgets.base`、`core.chrome→kernel.frame`、`core.painter→terminal.paint`。
- `from ..core import A, B` / `from motui.core import (...)`: 按名字拆分到新模块；`Text` → `widgets.text`；`Painter`/`styled_with` → `terminal.paint`/`terminal.render`；`Screen`/`HeadlessScreen`/`TerminalScreen`/`KeyDecoder`/`RawTerminalKeys`/`Clipboard`/`ScreenClipboard`/`MemoryClipboard`/`terminal_size`/`detect_color_mode` → terminal；其余纯名 → kernel。
- `core/__init__` 导出的字节函数（`clear_screen` 等）只允许测试/terminal 直接 import `motui.terminal.ansi`，不再从公开面导出。
- 根 `src/motui/__init__.py`：`Text`/`Widget` 从 widgets，`Line`/`Segment`/`Style`/`Theme`/`Glyphs`/`Border`/`Component`/`Event` 从 kernel，`App` 从 app；保持当前 `__all__` 名字不变（除 `core` 路径）。
- 更新 `src/motui/testing/__init__.py`（`..kernel.events`、`..terminal.screen`、`..app`）。
- 更新 `src/motui/demo/**`（12 处 `motui.core`）与 `tools/api.py` FACADES。
- 验证：`grep -rnE "from .*core|import motui\.core" src/motui tests tools` 为空。

#### T5 `kernel/__init__.py` 与 `terminal/__init__.py`
- `kernel/__init__.py`：导出纯值/协议（至少：`Axis Size Pos Rect Cell Segment Line Surface WrapMode Constraints ScrollAxis Scroll Color ColorMode Style FG_CODES NONE RESET sgr_prefix Glyphs Border GLYPHS Theme Styles DEFAULT_THEME ColorPalette Event EventSource KeyEvent MouseEvent PasteEvent ResizeEvent FocusEvent Component Section Document Viewport ScreenLayout Rect Split Pane Frame Chrome Separator Overlay Hit EveryHandle RowRange Selection highlight extract action_at cut_line slice_line wrap_line ELLIPSIS visible_width wrap_text ellipsize_tail DEFAULT_INPUT_KEYMAP DEFAULT_EDITOR_KEYMAP EDITOR_SUBMIT_KEYMAP Keymap`）。
- `terminal/__init__.py`：导出 `Screen HeadlessScreen TerminalScreen KeyDecoder RawTerminalKeys Clipboard ScreenClipboard MemoryClipboard Painter styled_line terminal_size detect_color_mode auto_theme`；**不导出** `ansi` 或其字节函数。
- 保持 `kernel/__init__` 不 import terminal/widgets/app/testing。

#### T6 测试迁移与收口
- `tests/core/` 按模块拆分移动：
  - `tests/kernel/`: `test_block.py→test_document.py`、`test_frame.py`、`test_glyphs.py`、`test_lines.py→test_cell.py`、`test_selection.py`、`test_style.py`、`test_text.py`、`test_theme.py`、`test_theme_contract.py`、`test_events.py`、`test_keymap.py`
  - `tests/terminal/`: `test_ansi.py`、`test_screen.py`、`test_decoder.py`、`test_sources.py`、`test_clipboard.py`、`test_painter.py`；`test_style.py` 的 `detect_color_mode` 用例拆到 `tests/terminal/test_capability.py`
  - `tests/widgets/`: `test_cursor.py`、`test_mark.py`
  - 删除空 `tests/core/`。
- `tests/testing/*`、`tests/app/*`、`tests/widgets/*`、`tests/test_api.py`、`tests/test_invariants.py` 的 import 全部更新。
- `tests/test_invariants.py`：`Text` 进入 `widgets.__all__` 后，补 `"Text": lambda: Text(_WIDE)` 到 CASES（否则 completeness 红）。
- 更新 `tests/core/test_lines.py` 中 `styled_with`/`line.styled()` 的断言为 `terminal.render.styled_line`。
- `tools/api.py --update`；`tools/growth.py` 的注入目标仍是 `kernel.cell.Surface`/`kernel.layout.*`（确认路径）。
- `pyproject.toml` 按 D6 调整 ruff/pyright/import-linter；`uv lock` 若依赖未变则不需要。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴真实数字；预计 1017 左右）。
2. `uv run python tools/golden.py --check` → `57 topics match`（**逐字节**）。
3. `uv run python tools/framebench.py` → `render-hash a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（不变）。
4. `uv run python -m motui < /dev/null` / `--pages` exit 0，行数 70 / 4059。
5. `grep -rnE "from .*core|import motui\.core" src/motui tests tools` 为空；`src/motui/core/` 不存在。
6. `uv run python -c "import sys; import motui; assert 'motui.core' not in sys.modules"` 通过。
7. `uv run ruff check .`、`uv run pyright`、`uv run lint-imports` 全 0（贴 ratchet 范围）。
8. `uv run python tools/api.py --check` 通过；公开面计数：root ≤ 30、kernel ≤ 40、terminal ≤ 20（若超，贴实际并说明 W5 收敛）。
9. `uv run python tools/growth.py --quick` 通过。
10. `uv run python -c "import motui.kernel, sys; print([m for m in sys.modules if m in ('os','sys','io','ctypes') and 'motui.kernel' in m])"`：kernel 不因自身 import 引入 I/O（import-linter 已覆盖）。

## 禁触清单

`tests/golden/**`、`tools/golden.py`、`tools/framebench.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`src/motui/demo/**` 的**行为代码**（只允许 import 行）。
不新增运行时依赖；不改 `pyproject.toml` 的 `[project].dependencies`。

## 交接包

最后 commit 写 `specs/2026-10-25-0900-motui-2-0-architecture/handoff/W1-kernel.md`：
A 节给实际文件迁移清单、`kernel/__init__`/`terminal/__init__` 导出列表、Screen ABC 成员表、门禁真实结果、hash；
B 节写与 spec 的偏差（尤其 Painter/Line.styled 的 terminal 归属、Theme.auto、mark/cursor 临时位置、EveryHandle/RowRange 暂留）、坑、下一波（W2）要改的 `render(width)` 清单；
C 节给关键路径:行号与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W0a/W0b 哪些事实被验证/推翻）/ 探索审计 / 未决问题。
