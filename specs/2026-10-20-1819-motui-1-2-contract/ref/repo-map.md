# repo-map · motui 1.2 contract

> 稳定知识，所有波次共用。只写“不知道就干不了”的事实；发现不准确时由 lead 更新。

## 1. 目录职责

| 路径 | 职责 | 备注 |
|---|---|---|
| `src/motui/kernel/` | 原语与应用无关的渲染核心：`style`/`theme`、`text`/`lines`/`ansi`、`cursor`/`mark`/`glyphs`、`events`、`block`、`screen`/`viewport`/`painter`、`frame`、`selection` | 依赖 stdlib + `wcwidth`；不依赖 motui 上层 |
| `src/motui/keys/` | 字节 → 事件：`decoder`、`keymap`、`sources`、Windows `console` | 依赖 kernel 的事件模型 |
| `src/motui/widgets/` | 通用组件库：动作、选择、输入、数据视图、布局、装饰、Markdown、语法高亮 | 依赖 kernel；`textbuf`/`textfield` 依赖 `keys.keymap` |
| `src/motui/widgets/markdown/` | Markdown 规则引擎与组件 | 子包有自己的 facade |
| `src/motui/interaction/` | 策略层：focus/pointer/gesture/find/modal/palette/overlays/scrollbar | 当前反向依赖 `app` 与部分 `widgets`（W6 修） |
| `src/motui/app.py` | `TUI` driver + composition root | 1229 行；W2 拆 driver/facade |
| `src/motui/testing.py` | `headless_tui` / `snapshot` | 测试替身入口 |
| `src/motui/demo/` | 随 wheel 发布的 showcase（`python -m motui`） | 3311 行；不参与公共 API |
| `tests/` | 1699 个用例；`golden/pages/*.txt` 是逐页字节基线 | 6.3s 全量 |
| `tools/` | `golden.py`（页面字节门禁）、`framebench.py`（性能/渲染哈希） | 不装进 wheel |
| `docs/` | `DESIGN.md`（机制）、`COMPONENTS.md`（使用契约）、`CONTRACT.md`（1.2 规范） | 与代码同 commit |
| `specs/` | 过程档案；不装进 sdist | 历史 spec 只增不改 |

## 2. 入口点与核心模块

- 包入口：`src/motui/__init__.py`（curated 34 名）；`python -m motui` → `src/motui/__main__.py` → demo。
- 组件协议：`kernel/block.py:Component.render(width) -> list[Line]`。
- 文档模型：`kernel/block.py:Block` / `Document` / `BlockState` / `Revisioned`。
- 屏幕/视口/画布：`kernel/screen.py:Screen`、`kernel/viewport.py:Viewport/ScreenLayout`、`kernel/painter.py:Painter`。
- 分屏/overlay：`kernel/frame.py:Rect/Split/Pane/Chrome/Frame/FrameTable`。
- 事件模型：`kernel/events.py:Event/KeyEvent/MouseEvent/PasteEvent/ResizeEvent/FocusEvent/EventSource`（W1 已落地）。
- 解码：`keys/decoder.py:KeyDecoder`；来源：`keys/sources.py:RawTerminalKeys`。
- 驱动：`app.py:TUI`（`add/get/remove`、`pane`、`split(pane=)`、`dock/undock`、`read_event`、`run_session/run_async/run`、`exit/refresh`、`hit/hit_leaf/pane_at`）。
- 交互：`interaction/focus.py:FocusRing`、`pointer.py:Pointer`、`gesture.py:SelectionGesture`、`find.py:Find`、`modal.py:Modal`、`palette.py:Palette`、`overlays.py:Toasts/Tooltip/Stats`、`scrollbar.py:Scrollbar`。
- 主题：`kernel/theme.py:Theme/DEFAULT_THEME/Themed`；样式：`kernel/style.py:Style`。
- 字形：`kernel/glyphs.py`（15 个常量 + `seat`/`seat_width`/`pair_seat`）。

## 3. 构建、测试、lint 命令（真实可跑）

```bash
# 环境（仓库根）
uv sync --locked

# 全量测试（W5a 后基线 1900 passed / 2 skipped；W4b 后 1811/2；W0 前 1699/1）
uv run pytest -q -p no:cacheprovider

# 单文件
uv run pytest -q tests/test_app.py -p no:cacheprovider

# 页面字节门禁
uv run python tools/golden.py --check
# 有意改渲染时（只在授权波次）
uv run python tools/golden.py --update

# 性能 + render-hash
uv run python tools/framebench.py

# demo 两条无终端入口
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

当前没有 ruff/mypy/pyright/import-linter 门禁；W7 前由 lead 决定是否加入。
Windows 上 `< /dev/null` 用 Git Bash；cmd 用 `< NUL`；CI 用 Python wrapper。

## 4. 关键类型/接口/数据流

```
bytes ──KeyDecoder.feed──> Event
                              │  KeyEvent / MouseEvent / PasteEvent / ResizeEvent / FocusEvent
                     TUI.read_event / host dispatch
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
  interaction tiers     hit/hit_leaf             widgets.handle/click/move/activate
        │                     │                      │
        └──────────────> Document (Block + Component) <──┘
                              │
                        Viewport.layout(width,height)
                              │
                        ScreenLayout (rows + ownership)
                              │
                        Frame.compose / overlays
                              │
                        Painter (row diff) ──> Screen.write/flush
```

- `Block.rows(width)` 是唯一带缓存的读口：sealed 按宽度缓存；open 只缓存 `Revisioned` 且 revision 非 `None` 的组件。
- `Viewport.layout` 是唯一把文档变成屏幕行的地方；`Frame.compose` 把多个 pane 拼成整屏并建 ownership table。
- `Painter.paint(layout)` 是唯一写终端的地方；`Screen.flush()` 是唯一真正 flush。
- `TUI.add` 默认进 focused pane；block id 在 frame 内全局唯一；`TUI.get/remove` 搜所有 pane + docks（歧义报错）。
- `TUI.dock(viewport, edge=...)` 取代 band；top/bottom 可并存；空 dock 不占行。

## 5. 约定

- 代码注释/文档/commit message：**英文**；用户报告/工单/handoff：中文。
- Commit 风格：`scope: lowercase message -- detail`（例：`kernel: the event model is typed -- KeyEvent, MouseEvent and PasteEvent split`）。
- 不引入兼容 shim；删除名字随最后一个消费者一起删。
- 测试命名描述行为；golden 只经工具重录。
- 库与测试不 sleep；时间经 `tui.clock()`。
- 公共 API 变更必须同时改 `tests/test_api_root.py`。

## 6. 环境陷阱

- **Python 3.12+**；`uv 0.12.21` 已安装；`uv.lock` 存在，CI 用 `uv sync --locked`。
- 主检出 `.venv` 已装 motui 1.1.8；worktree 需要自己的 `uv sync`，否则会 import 到主检出源码。
- `git worktree` 放仓库外：`C:\Users\shifu\.worktrees\motui\<branch>`。
- golden 文件是 LFS 无关的纯文本，写入 LF；Windows `core.autocrlf` 会把 LF 读成 CRLF，`golden.py` 只接受这一种转换。
- 不要在并行波次共用 `.pytest_cache`：统一加 `-p no:cacheprovider`。
- `docs/releases/` 目前只有 1.1.5–1.1.8；`CHANGELOG.md` 已有 1.1.9 段但 `pyproject.toml` 仍是 1.1.8——W7 收口，不在 W1 动。
- `dist/` 有 1.1.0 的旧 wheel，未跟踪；不要拿它做验证。
- Windows console 路径与 POSIX 路径行为不同；事件/来源改动必须在两边都跑测试。
- `src/motui/demo` 在 wheel 内；改公共 API 时 demo 也要迁移，但 demo 不是契约。
- 主检出只有未跟踪 `.zcodeignore`；不要提交它。

## 7. “找 X 去哪”

| 想找 | 去哪 |
|---|---|
| 一个组件怎么渲染 | `src/motui/widgets/<family>.py` 的 `render` |
| 一个组件有哪些动词 | 同名文件的 `handle/click/move/activate/select/toggle` |
| 键名/鼠标字段 | `kernel/events.py` + `keys/decoder.py` |
| 键位表 | `keys/keymap.py` |
| 屏幕行/滚动 | `kernel/viewport.py` |
| 分屏/overlay | `kernel/frame.py` |
| 终端写入 | `kernel/painter.py` + `kernel/screen.py` |
| 主题 token | `kernel/theme.py` |
| 字形常量 | `kernel/glyphs.py` |
| 命中测试 | `app.py:hit_test/hit_component` + `kernel/frame.py:FrameTable` |
| 测试基线 | `tests/`；golden 在 `tests/golden/pages` |
| 历史决策 | `specs/<date>-*/00-overview.md` |
