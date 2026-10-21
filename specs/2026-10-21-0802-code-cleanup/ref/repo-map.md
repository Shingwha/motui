# Repo map — motui

## 1. 目录职责

| 路径 | 职责 |
|---|---|
| `src/motui/kernel/` | 根层：行原语、样式/主题、事件、文档模型、屏幕/视口/画布、frame、selection、Host 协议 |
| `src/motui/keys/` | 字节 → 事件：decoder、keymap、终端来源（含 Windows console） |
| `src/motui/widgets/` | 通用组件库：action/form/list/tree/table/markdown/syntax 等 |
| `src/motui/interaction/` | 运行中驱动的策略层：focus、pointer、gesture、find、modal/palette、overlays、scrollbar |
| `src/motui/app.py` | `TUI` 驱动与组合根 |
| `src/motui/commands.py` | 命名动作注册表（只依赖 `widgets.choice.Option`） |
| `src/motui/demo/` | `python -m motui` 的可执行 demo（topics、session、assets） |
| `src/motui/testing.py` | 公开测试门面：`headless_tui` / `snapshot` / `ScriptedEvents` |
| `tests/` | 824 个行为契约；`tests/testing/` 是共享测试辅助；`tests/golden/` 是逐 topic 字节帧 |
| `tools/` | `golden.py`（帧比对）、`framebench.py`（耗时与 render-hash） |
| `docs/` | CONTRACT / DESIGN / COMPONENTS 与 release notes |

## 2. 入口点与核心模块

- 库入口：`src/motui/__init__.py`（34 个根名字）。
- 运行入口：`python -m motui`、`python -m motui --pages`（见 `src/motui/demo/__main__.py`）。
- 驱动：`src/motui/app.py` 的 `TUI`（生命周期、pump、document facade、hit test）。
- 文档模型：`kernel/block.py`（`Block` / `Document` / 组件协议 / `descend`）。
- 渲染：`kernel/viewport.py` → `kernel/frame.py` → `kernel/painter.py`。
- 交互 seam：`kernel/host.py` 的 `Host` 协议（`interaction/` 只看这个）。
- 行带共享值：`widgets/bands.py`（`RowBands` / `resolve_band` / `rest`）。

## 3. 构建、测试、lint

仓库根目录：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

**worktree 内的替代命令**（本机 venv 的 editable 安装指向主检出，必须把 worktree 的
`src` 放到 `PYTHONPATH` 前面）：

```bash
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m pytest -q -p no:cacheprovider
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/golden.py --check
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/framebench.py
```

没有单独的 lint 配置；`tests/test_api.py`、`tests/test_invariants.py` 与 import 图测试承担静态约束。

## 4. 关键类型与数据流

- `Component.render(width) -> list[Line]`：唯一渲染协议。
- `Clickable` / `Activable` / `Focusable` / `Hoverable` / `Controller` / `Resultful` /
  `Revisioned`：组件可实现的窄协议（`kernel/block.py`）。
- `Block.rows(width)`：按 `(width, revision)` 缓存；`Document` 按 id 持有 `Block`。
- `Viewport.layout(width, height) -> ScreenLayout`；`Frame.compose` 把多个 pane 拼成
  一张 `ScreenLayout` 与 `FrameTable`；`Painter.paint` 做行 diff。
- 事件流：`EventSource.read()` → `TUI.read_event`（滚动键拦截 + focus policy）→ host 分发
  → `hit()` / overlay / widget `handle`。
- overlay：`Frame.add_overlay(overlay, layer=...)` → `compose` 后 `apply_overlays`。

## 5. 约定

- 代码、docstring、注释、commit message 均为英文。
- Commit 风格：`area: imperative summary`（例：`widgets: share the row-band pipeline`）。
- 公开名字只出现在一个 facade；内部辅助用 `_` 前缀或私有模块。
- 测试是行为契约：不改测试来迁就实现。

## 6. 环境陷阱

- Windows + Git Bash；路径为 `C:\...`，命令里用 `/c/...`。
- `uv` 可用，但 worktree 使用 `PYTHONPATH` + 主 venv 更快，避免每个 worktree 重新安装。
- 并行工作必须带 `-p no:cacheprovider`，否则共享 `.pytest_cache`。
- golden 比较是字节级；Windows checkout 的 CRLF 只接受“整文件 LF→CRLF”这一种转换。
- `tools/framebench.py` 的 `replay` 是墙钟时间，允许波动；`render-hash` 必须逐字节不变。
- `motui` 的 metadata 版本来自 editable 安装，源码树内 fallback 为 `1.1.8`。

## 7. 找 X 去哪

| 想找 | 位置 |
|---|---|
| 驱动生命周期 / pump | `src/motui/app.py` 的 `_enter_run` / `_pump` / `_teardown` / `run_*` |
| Host 协议 | `src/motui/kernel/host.py` |
| frame 分屏 / chrome / overlay | `src/motui/kernel/frame.py` |
| 行带优先级 | `src/motui/widgets/bands.py` |
| 选择/单选框组 | `src/motui/widgets/choice.py` |
| 标签条与菜单条 | `src/motui/widgets/tabs.py` / `menubar.py` |
| 导航栏 | `src/motui/widgets/navlist.py` |
| 表格 | `src/motui/widgets/table.py` |
| find / palette | `src/motui/interaction/find.py` / `palette.py` |
| toast / tooltip / stats | `src/motui/interaction/overlays.py` |
| 公开面测试 | `tests/test_api.py` |
| 渲染不变量 | `tests/test_invariants.py` |
