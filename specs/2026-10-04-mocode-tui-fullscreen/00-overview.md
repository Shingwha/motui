# Spec 组 · mocode-tui 全屏 TUI 工具包（2026-10-04）

> ✅ 2026-10-04 六波全部交付并合并：W1 `e0a79b0`-系（wfs1-primitives）· W2（wfs2-render-core）·
> W3（wfs3-components）· W4（wfs4-driver）· W5（wfs5-pi-components）· W6（wfs6-pi-demo-docs）。
> 终验：585 passed；`examples/pi_demo.py < /dev/null` exit 0；wheel 构建通过；50 根符号导出面。
> 遗留：真机 TTY 交互验收（alt 进出/raw 键/Ctrl-C/resize）待用户在本机跑 `uv run python examples/pi_demo.py`。
> 分波 commit 哈希以 `git log --merges` 为准（各波合并 commit 即门禁记录）。

> 全新立项：仓库已清空重建（旧历史、旧 spec 一并删除，用户 2026-10-04 拍板「以一个全新的项目重做」）。
> 产品方向：**全屏渲染 TUI 工具包**——alt screen 整屏接管、应用自管 scrollback、视口滚动、固定尾区。
> spec 中文；代码/注释/文档/README/commit 英文。Git / worktree 协议见 spec-team SKILL.md，本组不重复。

## 用户决策（2026-10-04，已拍板写死）

| # | 决策 | 选择 |
|---|---|---|
| D1 | 全屏落点 | **备用屏幕 alt screen**（`\x1b[?1049h` 进入、`\x1b[?1049l` 退出；vim/htop 式标准全屏；退出后恢复 shell 原貌） |
| D2 | 文档溢出 | **应用自管 scrollback + 视口滚动**：整个文档常驻内存，屏幕只是文档的窗口；pgup/pgdn 回看；任何块随时可重画 |
| D3 | 布局切分 | **视口 + 固定尾区**：主滚动区（弹性高度）+ 底部固定区（输入框/状态栏等 pinned 块，永不被滚走） |

## 定位

`mocode-tui` 是**可复用的全屏 TUI 工具包**：任何 Python 程序可以用它构建自己的组件与界面，不绑定宿主。
能力：以块为单位的文档模型（id 寻址、生命周期）、视口滚动、固定尾区、一组常用组件、
自研键盘解码（POSIX raw / Windows console record / scripted）。运行时依赖仅 `wcwidth`；
组件库类依赖（prompt_toolkit / rich / textual / blessed）一律不用。Python ≥ 3.12，hatchling，uv。

## 模块契约（最终公共面，各波按此施工，不得凭空发明）

最终 `mocode_tui/__init__.py` 导出面（W4 收口时定型）：

```python
from .app import TUI
from .block import Block, BlockState, Component, Document
from .components import (Column, Confirm, Divider, EditBlock, Input, Markdown, Message, Notice,
                         Option, Panel, Row, Select, Spinner, StatusBar, StatusSegment, Table,
                         Text, ToolBlock)
from .keys import Key, KeyDecoder, KeySource, Paste, RawTerminalKeys, ScriptedKeys
from .lines import Line, Segment, wrap_line
from .painter import Painter
from .screen import HeadlessScreen, Screen, TerminalScreen
from .style import (ACCENT, BORDER, CODE, CURSOR, DIM, ERROR, MUTED, NONE, SELECTION, SUCCESS,
                    WARNING, Style)
from .testing import headless_tui, snapshot
```

| 模块 | 波次 | 契约要点（细节以各工单为准） |
|---|---|---|
| `style.py` | W1 | `Style`(frozen)：fg/bg/bold/dim/italic/underline/reverse，16 色命名调色板；`prefix()` 缓存 SGR；`merge()`；语义常量 NONE/DIM/MUTED/ACCENT/SUCCESS/ERROR/WARNING/BORDER/CODE/CURSOR/SELECTION |
| `text.py` | W1 | `visible_width`（唯一宽度真源）、`one_row`、`ellipsize_tail`、`ellipsize_middle`、`wrap_text`（词感知）、`terminal_size`（fallback 80x24） |
| `lines.py` | W1 | `Segment(text, style)`；`Line`（不可变，恰一可视行）：`from_text/segments/width/text/styled()/fit/pad_to/__add__`；`wrap_line`（词感知、CJK/长词硬断、保样式） |
| `ansi.py` | W1 | 转义构造唯一出处：`move_up/move_to_column/clear_line/delete_lines/erase_down/hide_cursor/show_cursor`、`enter_alt_screen()="\x1b[?1049h"`、`leave_alt_screen()="\x1b[?1049l"`、`strip_ansi`、`enable_vt() -> bool`（Windows VT 开关，返回成败）、`stdout_isatty` |
| `block.py` | W1 | `Component` 协议 `render(width) -> list[Line]`；`BlockState` 仅 `OPEN/SEALED`（**无 COMMITTED**——全屏下没有终端历史）；`Block(id, component, pinned=False)`：`set_component/seal/render/is_open`；`Document`：`add(component, *, id=None, pinned=False)/get/remove/blocks/__len__` |
| `screen.py` | W2 | `Screen` 协议 `width/height/live/enter()/leave()/write/flush/refresh_size()`；`TerminalScreen`（`live = isatty 且 VT 可用`；enter=alt+隐藏光标，leave=显光标+离 alt；非 live 不进不出）；`HeadlessScreen(width=80, height=24)`（`live` 恒 True，录制全部写字节，`output`/`clear()`） |
| `viewport.py` | W2 | `Viewport(document).layout(width, height) -> ScreenLayout(rows 恰 height 行, viewport_rows)`；`scroll_up(n)/scroll_down(n)/scroll_to_bottom()`；`offset/total_rows/viewport_height/at_bottom`；sealed 缓存按宽度失效；滚离贴底时视口末行 = `Line.from_text("─ more below ─", MUTED)` |
| `painter.py` | W2 | `Painter(document, screen, *, throttle=0.030)`；`flush()`：尺寸变→`\x1b[2J` 全清；逐行 diff，仅变化行写 `\x1b[{r};1H\x1b[K+行内容`；无变化零字节；`rows()` 返回当前目标屏（恰 height 行）；`live=False` 时零写入但逻辑行照算；`scroll_*` 转发 viewport |
| `layout.py` + `components/` | W3 + W5 | 组件协议即 `render(width) -> list[Line]`，全屏化下宽度 = `screen.width`。W3 清单：Text / Markdown / Input / Select / Confirm / Spinner / StatusBar / Notice / Divider / Panel / Row / Column。W5 清单（pi 式界面用）：Message（角色化消息：user 色带 / assistant / thinking 斜体暗灰）、ToolBlock（工具调用块：绿/暗/无底色带 + 标题 + 输出 + 计时尾行）、EditBlock（编辑 diff：路径 + ±行号 + (edited) 徽标）、Table（盒线表格：自然列宽、超宽比例收缩 + ellipsize、(text, Style) 单元格） |
| `keys.py` | W4 | `Key(name, char)`；`Paste(text)`；`KeyDecoder`（增量 UTF-8、CSI 含 page_up/page_down、c-a..c-z、isolated escape、bracketed paste）；`KeySource` 协议；`ScriptedKeys`；`RawTerminalKeys`（POSIX termios raw / Windows `ReadConsoleInputW` record / cooked 行回退） |
| `app.py` | W4 | `TUI(screen/keys/throttle/interactive)`：`add(pinned=False)/get/print（系统块）/invalidate/flush/every/read_key（拦截 page_up/down）/stop/scroll_*/run(body)`（enter/leave 成对；非 live 运行期静默、退出 dump 最终屏纯文本）；pump/节流/时钟 seam |
| `testing.py` | W4 | `headless_tui(width, height, *, script=None, keys=None)`；`snapshot(tui)`（文档结构化文本） |

## 测试纪律（不放松）

- 结构化断言为主：`Painter.rows()` 逻辑行、viewport 偏移、块/文档状态；
  字节级只断言关键 escape 形状（首帧 `\x1b[2J`、单行重写、enter/leave、非 live 零写入、dump 形状）。
- 无 golden 文件；无裸 sleep（`flush(force=True)`、注入时钟 `_clock`）；每测试 30s 超时（pyproject）。
- 每个 commit 独立过 `uv run pytest`。

## 波次表（串行，逐层依赖）

| 波 | 工单 | 内容 | 分支 | 前置 |
|---|---|---|---|---|
| W1 | 01 | 基础件：style / text / lines / ansi / block + 测试 | `wfs1-primitives` | 无 |
| W2 | 02 | 渲染内核：screen / viewport / painter + 测试 | `wfs2-render-core` | W1 |
| W3 | 03 | 组件：12 个基础组件 + Row/Column + 测试 | `wfs3-components` | W2 |
| W4 | 04 | 驱动：keys / app / testing + 测试 | `wfs4-driver` | W3 |
| W5 | 05 | pi 风格组件：Message / ToolBlock / EditBlock / Table + 测试 | `wfs5-pi-components` | W4 |
| W6 | 06 | pi 式 demo（假调用全屏编码助手界面）+ README/DESIGN/COMPONENTS + 终验 | `wfs6-pi-demo-docs` | W5 |

- 每波**一个 agent**，从合并时刻最新 main 切分支；合并前后各跑一次全量门禁贴真实输出。
- `src/mocode_tui/__init__.py` 由各波**按波序追加导出**（串行波，无并行冲突；W4 定型最终导出面）。

## 全局不变量

1. 组件协议 `render(width) -> list[Line]` 从 W1 起恒定，之后任何波次不改。
2. 运行时依赖只有 `wcwidth`。
3. 全屏运行期除 painter 外无人写 sink；enter/leave 成对（异常路径也 leave）。
4. painter diff：只有变化行被写；无变化帧零字节。
5. `Painter.rows()` 永远恰好 `screen.height` 行。
6. 非 live（管道/文件）= 运行期零写入 + 退出 dump 最终屏纯文本；非 live 时 `read_key()` 返回 `None`。
7. display width 只认 `text.visible_width`（wcwidth）；组件自己 wrap/fit，painter 只数行不重测。

## 回归红线

- 任一波合并前 `uv run pytest` 全绿；用例总数只增不减（W1 起步自建基线，W5 收口时 ≥ 220）。
- W5 合并后 main：全绿 + `python examples/chat_demo.py < /dev/null` 与 `python examples/showcase.py` exit 0。
- `import mocode_tui` 无宿主依赖；README quickstart 30 行内可跑。
- commit 英文、风格：`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`。

## 明确不做（写死，后续另立项）

- 鼠标滚轮滚动（需 Windows 鼠标记录 + SGR 1006；pgup/pgdn 够用）。
- 文档内存上限 / 历史裁剪（当前全量常驻，如实登记为已知取舍）。
- VT 序列跨 read 的 settle 超时（交互路径无此问题；pipe 字节路径维持现状并写入文档）。
  —— 2026-10-04 修订：W7 已实现跨 feed 组装 + 静默 settle，此条作废。
- ~~真彩色 / 256 色（16 色命名调色板封顶）~~ —— **2026-10-04 W11 修订**：用户要求「配色缓和易读」，
  16 色唯一蓝为纯蓝无法缓和；调色板升级为**真彩色（24-bit SGR）**，语义常量改取
  GitHub-dark/pi 风暗色；命名 16 色仍可用（真彩是超集）。
- 补全框架、虚拟化渲染优化（同行合并写等）、SIGWINCH 之外信号处理。
- 与 mocode 的集成（mocode 侧下一个 spec 的事）。

## 环境事实（lead 校准，2026-10-04）

- Windows 10 + Git Bash；Python 3.13 via uv（`/c/Users/shifu/.local/bin/uv`）；`.venv` 已 `uv sync`。
- **本验证环境无 TTY**：agent 不可能真跑交互 demo；验收面 = pytest + piped/dump 路径 + `import` 冒烟。
  真机 TTY 交互验收是 lead/user 的事（探针脚本 lead 自备，不占任何波的写入范围）。
- worktree 根：`C:/Users/shifu/.worktrees/mocode-tui/<分支>`（lead 统一创建销毁）。
- 路径含非 ASCII 无关（全英文）；组件渲染框线/emoji 由 wcwidth 处理，不假设字体。

## 收尾

- lead 终验：全门禁 + piped 两 demo + import 冒烟 + 各工单头部补状态行（`✅ 日期 @ 分支`）。
- **不 push、不发版、不打 tag**——等用户指令。清理各 worktree，保留分支。
