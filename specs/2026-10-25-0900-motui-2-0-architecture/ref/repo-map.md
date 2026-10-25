# 仓库地图（repo-map）

> 本操作共用。基于 `main` @ `400773b` 实测（2026-10-25 09:00）。
> 只写“不知道就没法开工”的事实；稳定知识在这里维护，handoff 只留增量。

## 1. 目录职责

```
src/motui/
  __init__.py          curated root facade（41 names）
  __main__.py          python -m motui -> demo.main()
  py.typed
  core/                1.x 内核：值、几何、行、帧、文档、滚动、绘制、终端 I/O
  widgets/             组件库（render(width) -> list[Line]）
  app/                 运行时 + 策略 tiers（TUI / App / focus / pointer / gesture / modal / overlays / find / scrollbar / commands）
  demo/                内置演示（python -m motui / --pages）；golden 由它渲染
  testing.py           headless_tui / ScriptedEvents / snapshot（1.x 测试助手）
tests/
  core/ app/ widgets/  921 个用例（835 个 test 函数）
  golden/topics/       57 个字节级 golden（<section>--<topic>.txt）
  testing/             clock / doubles / events / layout 测试替身
tools/
  golden.py            --check / --update；按 demo.render_topic 逐字节比对
  framebench.py        9 条测量；render-hash 是全量字节摘要
docs/                  ARCHITECTURE? 实际为 DESIGN.md / CONTRACT.md / COMPONENTS.md / releases/
specs/                 历史 spec 组；本组为 2026-10-25-0900-motui-2-0-architecture
```

`core` 当前同时含纯值（`lines/text/style/theme/glyphs/cursor/mark/block/viewport/scroll/frame/hit/painter`）和终端 I/O（`ansi/screen/decoder/sources/console/clipboard`）。W1 按规格拆分。

## 2. 入口点与核心模块

| 入口 | 路径 | 说明 |
|---|---|---|
| 应用作者 | `from motui import App, Input, Markdown, ...` | root facade，41 names |
| 低层运行时 | `motui.app.TUI` | 1.x 的 1,333 行运行时（W4 拆） |
| 组件 | `motui.widgets.*` | 全部 `render(width) -> list[Line]` |
| 内核缝 | `motui.core.*` | 75 names（W1 拆成 kernel + terminal） |
| 终端 | `python -m motui` / `--pages` | demo，金标/门禁的字节来源 |
| 测试助手 | `motui.testing.headless_tui/snapshot` | W0 起扩充为 `testing/` 包 |

关键类型/数据流：

```
App/TUI
  Document(Block[id, Component, pin])
    Viewport.layout(width, height) -> ScreenLayout(rows, row_blocks, ...)
      Block.rows(width) 缓存 (width, revision)
        Component.render(width) -> list[Line]
  Frame.compose(width, height) -> ScreenLayout   # panes / docks / overlays
  Painter.paint(ScreenLayout) -> Screen.write   # 行 diff，一次 write + flush
  Hit / Selection / highlight / extract          # 行归属表
```

事件流：`Screen/EventSource.read -> TUI.run -> App.dispatch`（10 层 if 链）→ focus/pointer/gesture/modal/overlays/scrollbar → `Component.handle(event)`。

## 3. 构建、测试、lint 命令（真实可跑）

```bash
uv sync --locked                                  # 依赖（当前无 ruff/pyright/import-linter）
uv run pytest -q -p no:cacheprovider               # 921 passed（4.8s）
uv run python tools/golden.py --check              # 57 topics match
uv run python tools/framebench.py                  # 9 行；hash a82f7968…（当前基线）
uv run python tools/framebench.py --frames N       # 可选帧数
uv run python -m motui < /dev/null                 # exit 0
uv run python -m motui --pages                     # 4059 行，exit 0
```

W0b 起追加（需先写进 `pyproject.toml` 并 `uv lock`/`uv sync`）：

```bash
uv run ruff check .
uv run pyright
uv run lint-imports
uv run python tools/api.py --check
uv run python tools/growth.py
```

本地环境：Windows 10 x64，Git Bash，Python **3.13.16**，uv **0.12.21**。CI 用 Python **3.12** + 双平台。本地 3.13 只是快速反馈，门禁以 3.12 为准。

## 4. 关键类型/接口/数据流（1.x 现状 → 2.0 目标）

| 1.x 现实 | 2.0 目标 | 位置 |
|---|---|---|
| `Component.render(self, width: int) -> list[Line]` | `render(self, c: Constraints) -> Surface` | W2 |
| `core/block.py:Component` Protocol + `Block.pin: str|None` | `Section(placement: Placement, sizing: Sizing)` | W2/W4 |
| `core/lines.py:Line`（RLE of `Segment`），自由函数 `fit/fill/fuse/overlay/rest/cut_line/slice_line/styled_with/wrap_line/action_at` | `Line` 值方法 `clip/pad/fused/under/band/cut/slice/styled/reflow/action_at` + `Cell` | W0/W2.5 |
| `core/text.py:visible_width/fit_text/ellipsize_tail/wrap_spans/wrap_text` | `text.width/wrap/spans/fit/ellipsize/index_at/bounds` | W0/W2.5 |
| `core/scroll.py:ScrollState(offset)` + `Scrollable` | `Scroll(x: Axis, y: Axis)` + `Axis.clamp/max_offset/reveal/thumb` | W0/W2.6 |
| `core/viewport.py:Viewport.layout(width,height)` | 同，但输入 `Rect`，输出 `Surface`；FILL 跳过索引 | W2 |
| `core/frame.py:Rect/Split/Pane/Frame`（1,677 行） | `kernel/{geom,frame,hit,overlay}.py` | W1 |
| `core/painter.py:Painter.paint(ScreenLayout)` | `kernel/paint.py`，接收 `Surface` | W1/W2 |
| `core/screen.py:Screen` Protocol | `terminal/screen.py:Screen` ABC + `TerminalOptions/MouseMode` | W1/W4 |
| `core/widget.py:Widget`（theme/styles/focused/hover + handle/click/drag/hover_at/activate/take_result/revision） | `widgets/base.py:Widget`（parent/children/walk/hooks/keymap/touch） | W3 |
| `app/driver.py:TUI`（1,333 行） | `app/{terminal,runtime,workspace,router}.py` | W4 |
| `app/application.py:App.dispatch`（10 层 if） | `DEFAULT_HANDLERS` 元组 | W4 |
| `core/hit.py:EveryHandle/RowRange` | `runtime.Timer` / `layout.RowSpan` | W4 |
| `take_result()` / `Resultful` | `take()` / `HasResult` | W3 |
| `Themed` / `Revisioned` / `_CHILD_ATTRS` / `_looks_interactive` | 删除；`touch()` + `walk()` + 能力属性 | W3 |

## 5. 约定

- 注释与 docstring：**英文**；说明“为什么/约束”，不复述代码。现有代码注释密度较高，新代码保持同等密度即可。
- commit：`area: imperative lowercase phrase`（例：`frame: a chrome band names the region it decorates`）。一波一分支，每项任务一个 commit。
- 测试命名：`test_<behavior>`；参数化矩阵用于宽度/模式。
- 公开面：`__all__` 必须与真实属性一致（`tests/test_api.py` 会验）。
- 不新引入运行时依赖；测试不引入 hypothesis。
- golden 只通过 `tools/golden.py --update` 重录，不手改。

## 6. 环境陷阱

1. **旧 worktree / 分支残留**：`C:/Users/shifu/.worktrees/mocode-tui/*` 有 8 个 2026-10-21 的 worktree，分支 `motui-2/*` 已全部并入 main（`git log main..branch` 为空）。不要复用，也不要删除（非本次操作产物）；新波次用新目录/分支。
2. **未跟踪的 `__pycache__` 残留**：`src/motui/{kernel,interaction,keys}/__pycache__` 是上上次尝试的缓存，无源码、未跟踪。W0 建 `kernel/` 前先删除这些目录，避免 namespace package 干扰。
3. **Windows 路径/换行**：仓库无 `.gitattributes`；`golden.py` 兼容 LF→CRLF 的整文件转换，其他任何差异都算失败。写文件用 LF。
4. **Python 版本差**：本地 3.13，CI 3.12。不要用 3.13-only 语法（如 PEP 695 泛型）除非确认 3.12 可用。
5. **uv lock**：任何 `pyproject.toml` 依赖变化都要同时提交 `uv.lock`（CI `uv sync --locked`）。
6. **demo 是 golden 的来源**：改 demo / shell chrome 会让 57 个 golden 全变；W0/W1 禁止。
7. **非 ASCII**：仓库含中文注释/文档；文件编码 UTF-8。
8. **端口/服务**：无；全部门禁是本地命令。

## 7. “找 X 去哪”

| 找什么 | 去哪 |
|---|---|
| 组件实现 | `src/motui/widgets/<family>.py` |
| Widget 基类与交互 | `src/motui/core/widget.py`（W3 → `widgets/base.py`） |
| 行/段/内容门 | `src/motui/core/lines.py`（W1 → `kernel/cell.py`） |
| 宽度/换行/截断 | `src/motui/core/text.py` |
| 帧/分屏/合成 | `src/motui/core/frame.py` |
| 文档/块缓存 | `src/motui/core/block.py` |
| 滚动/布局 | `src/motui/core/{scroll,viewport}.py` |
| 绘制/字节 | `src/motui/core/{painter,ansi,screen}.py` |
| 事件解码 | `src/motui/core/{decoder,sources,events}.py` |
| 主题/样式/字形 | `src/motui/core/{theme,style,glyphs}.py` |
| 选择/命中 | `src/motui/core/{selection,hit}.py` |
| 运行时 | `src/motui/app/{driver,application}.py` |
| 焦点/指针/手势 | `src/motui/app/{focus,pointer,gesture}.py` |
| 覆盖层/模态/面板 | `src/motui/app/{overlays,modal,command_palette,find}.py` |
| 滚动条 | `src/motui/app/scrollbar.py` |
| 测试助手 | `tests/testing/*`、`src/motui/testing.py` |
| golden 数据 | `tests/golden/topics/*.txt` |
| 性能基线 | `tools/framebench.py` 文件头注释里的历史基线 |
| 规格原文 | `specs/2026-10-25-0900-motui-2-0-architecture/ref/source/` |
