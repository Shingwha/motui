# repo-map · test refactor

> 稳定知识，所有波次共用。只写“不知道就干不了”的事实；不准确时由 lead 更新。

## 1. 目录职责（与本次重构相关）

| 路径 | 职责 | 备注 |
|---|---|---|
| `src/motui/kernel/` | 原语与渲染核心：text/lines/ansi/style/theme/events/block/screen/viewport/painter/frame/selection/cursor/mark/glyphs/clipboard | 测试目标 |
| `src/motui/keys/` | `decoder` / `keymap` / `sources` / Windows `console` | 测试目标 |
| `src/motui/widgets/` | 组件库：action/choice/input/data/layout/markdown/syntax | 测试目标 |
| `src/motui/interaction/` | focus/pointer/gesture/find/modal/palette/overlays/scrollbar | 测试目标 |
| `src/motui/app.py` | `TUI` driver + composition root | 测试目标 |
| `src/motui/testing.py` | 公开测试三名字：`ScriptedEvents` / `headless_tui` / `snapshot` | **不改**；`tests/testing` 重新导出 |
| `src/motui/demo/` | 随 wheel 发布的 showcase（58 topics） | 只保留 smoke；行为不测 |
| `tests/` | 被测对象；本次重构范围 | 旧文件全部重排/删除 |
| `tests/golden/topics/*.txt` | 逐 topic 字节基线（58 个） | 不动；`tools/golden.py` 是唯一断言者 |
| `tools/golden.py` | 视觉字节门禁 | 不动；CI 已跑 |
| `tools/framebench.py` | 性能 + render-hash | 不动；CI 已跑 |
| `docs/` | 公开文档 | 不动；文档测试删除 |
| `specs/` | 过程档案 | 本组新增 |

## 2. 入口点与核心模块（测试要打的公开面）

- 根：`motui`（34 名字：`TUI`、`Input`、`Markdown`、`headless_tui`、`snapshot`…）。
- 层 facade：`motui.kernel`（60+ 名字）、`motui.keys`、`motui.widgets`（44 名字）、`motui.interaction`、`motui.app`、`motui.testing`。
- 文档化深路径（允许直接 import）：
  - `motui.kernel.lines`（`Line`/`Segment`/`fuse`/`overlay`/`slice_line`/`cut_line`/`wrap_line`）
  - `motui.kernel.text`（`visible_width`/`wrap_text`/`fit_text`/`ellipsize_tail`）
  - `motui.kernel.frame`（`Rect`/`Split`/`Pane`/`Chrome`/`Frame`/`FrameSpan`/`splice_row`）
  - `motui.kernel.style`（`Style`/`sgr_prefix`/`NONE`/`RESET`/token 常量）
  - `motui.kernel.screen`（`Screen`/`HeadlessScreen`/`TerminalScreen`）
  - `motui.kernel.viewport`（`Viewport`/`ScreenLayout`）
  - `motui.kernel.painter`（`Painter`）
  - `motui.kernel.selection`（`Selection`/`highlight`/`extract`）
  - `motui.kernel.cursor` / `mark` / `glyphs` / `clipboard` / `events` / `block`
  - `motui.keys.decoder` / `keymap` / `sources`
  - `motui.widgets.<family>`（`textfield`/`choice`/`table`/`tree`/`list`/`scroll`/`form`/`dialog`/`diff`/`markdown`/`syntax`/`menubar`/`bands`/`rows`/`layout`/`delegate`/`indicators`/`autocomplete`/`combobox`/`action`/`collapsible`/`tabs`/`navlist`/`decor`/`textbuf`）
  - `motui.interaction.<tier>`
  - `motui.app.TUI`
- **禁止**：`motui._*`、任何 `obj._field` 读取、`motui.demo.*` 的内部结构（smoke 除外）。

## 3. 构建、测试、lint 命令（真实可跑）

主检出（lead）：

```bash
# 全量
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider

# 单目录/单文件
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/kernel
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/kernel/test_text.py

# 视觉/性能/入口门禁
.venv/Scripts/python.exe tools/golden.py --check
.venv/Scripts/python.exe tools/framebench.py
.venv/Scripts/python.exe -m motui --pages
.venv/Scripts/python.exe -m motui < /dev/null
```

worktree（worker，不建自己的 venv，用主检出解释器 + `PYTHONPATH` 指向本 worktree 源码）：

```bash
cd C:/Users/shifu/.worktrees/motui/<branch>
PYTHONPATH=C:/Users/shifu/.worktrees/motui/<branch>/src \
  C:/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
```

> `-m pytest` 把当前目录放在 `sys.path` 首位；`tests/` 是包，`tests.testing` 可导入；
> `PYTHONPATH` 保证 `motui` 解析到 worktree 的 `src`，而不是主检出。

## 4. 关键类型/数据流（测试怎么驱动）

```
bytes ──KeyDecoder.feed──> Event
Events ──TUI.read_event / handle──> interaction tiers / widgets
TUI.add(component) ──> Document(Block) ──Viewport.layout──> ScreenLayout
Frame.compose ──> Painter.paint ──> Screen.write/flush
```

- `TUI(screen=HeadlessScreen(...), keys=ScriptedEvents([...]), interactive=False)` 是无终端驱动。
- `tui.paint()` 同步画一帧；`tui.rows` 是当前屏幕行；`tui.screen.output` 是全部字节。
- 交互层用真实事件驱动：`tui.read_event()` / `tier.handle(event)` / `tui.dispatch` 的公开入口。
- 组件测试直接用 `component.render(width)` 与 `component.handle(event)` / `click(x,y)` / `move(delta)` / `activate()` / `take_result()`。
- 定时：`tui.clock = Clock()`；`clock.advance(seconds)`；`tui.tick()` / `tui.paint()` 按公开 API。

## 5. 约定

- 测试代码/注释/commit message：**英文**；工单/handoff/报告：中文。
- Commit 风格：`tests: lowercase message -- detail`。
- 测试名描述行为：`test_move_clamps_at_the_ends`，不写波次/旧名/迁移。
- 一个测试文件一个组件族；同类行为参数化。
- 不 sleep、不 mock、不碰网络、不依赖终端尺寸。
- 公开 API 删除/改名不在本操作范围；测试按现状写。
- 删除测试直接 `git rm`；不留 skip/xfail/TODO。

## 6. 环境陷阱

- Python 3.13.16（主检出的 `.venv`）；`pyproject` 要求 >=3.12。
- Windows Git Bash；路径含 `C:\Users\shifu`，`PYTHONPATH` 用正斜杠或 Git Bash 形式。
- 不要在 worktree 里 `uv sync`（会建第二套 venv、拉网络）；用第 3 节的 `PYTHONPATH` 命令。
- `-p no:cacheprovider`：并行 worktree 不共享 `.pytest_cache`。
- 主检出只有未跟踪 `.zcodeignore`；不要提交它。
- `tests/__pycache__` 是旧构建产物；不要提交。
- 旧 `tests/_doubles.py` 在 W0 删除；worker 不得恢复。
- `tests/golden/` 读写是 LF 规则；本操作不改渲染，不应触发重录。
- Windows 上 `< /dev/null` 用 Git Bash 可跑；worker 只需 pytest。

## 7. “找 X 去哪”

| 想找 | 去哪 |
|---|---|
| 共享测试方法 | `tests/testing/`（见 `ref/interfaces.md`） |
| 旧测试与新文件的映射 | `ref/interfaces.md` §3 |
| 某组件的公开动作 | `src/motui/widgets/<family>.py` 的 `render/handle/click/move/activate/take_result` |
| 事件构造 | `tests/testing/events.py` |
| 无终端驱动 | `motui.testing.headless_tui` / `src/motui/testing.py` |
| 视觉字节基线 | `tests/golden/topics/` + `tools/golden.py` |
| 组件矩阵 | `tests/test_invariants.py` |
| 历史决策 | `specs/<date>-*/00-overview.md` |
