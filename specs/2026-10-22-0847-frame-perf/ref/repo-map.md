# repo-map · mocode-tui（motui）

> lead 2026-10-22 探索实记；关键命令均已实跑。perf 组（frame-perf）全波共用。

## 1. 目录职责

- `src/motui/core/` —— 内核：`block.py`（Block/Document/Revisioned 协议）、`viewport.py`
  （Viewport/ScreenLayout）、`frame.py`（Frame/Pane/组合与备忘录）、`scroll.py`
  （ScrollState/Scrollable）、`selection.py`、`lines.py`（Line/Segment，不可变值）、
  `painter.py`、`screen.py`（TerminalScreen/HeadlessScreen）、`chrome.py`。
- `src/motui/app/` —— 驱动与应用层：`driver.py`（TUI：paint 节流、reveal、dock）、
  `find.py`、`gesture.py`（点击/拖选行走）、`application.py`、`scrollbar.py`、
  `overlays.py`、`modal.py`、`command_palette.py`、`focus.py`。
- `src/motui/widgets/` —— 组件库：`textbuf.py`（TextBuffer：行/光标/undo/version）、
  `textfield.py`（Editor/Field/Input 壳）、`markdown/`（含 `component.py` 的
  `_StreamCache` 尾块增量）、`table.py`、`choice.py` 等。
- `tests/` —— `core/`、`app/`、`widgets/`、`golden/`（57 topics 的字节快照）。
- `tools/` —— `framebench.py`（度量尺，9 行）、`golden.py`（`--check`/`--update`）。
- `specs/<组>/` —— 过程产物；`docs/`（DESIGN/COMPONENTS/CONTRACT）。

## 2. 入口点与核心模块

- 库入口 `motui/__init__.py`（TUI/Text/Markdown/Table… 门面）；`python -m motui` 是 demo。
- 每帧热路径：`driver.py` `_paint_at`（30ms 节流+脏标记）→ `frame.compose`
  （frame.py:1286）→ 每 pane `viewport.layout(width, height)`（viewport.py:121）→
  `document.blocks()`（block.py:457）→ 每块 `block.rows(width)`（block.py:353，键
  `(width, revision)`，命中返回整表拷贝）→ 窗口切片 → painter.paint(diff)。

## 3. 构建、测试、lint 命令（实跑过）

- `uv run pytest -q` —— 893 passed in ~4s（当前全量门禁）。
- `uv run python tools/golden.py --check` —— `golden: 57 topics match`。
- `uv run python tools/framebench.py` —— 9 行度量 + `render-hash`（当前
  `a82f7968…`，见组 overview 红线 1）。
- demo 冒烟：`python -c "import subprocess,sys;raise SystemExit(subprocess.run([sys.executable,'-m','motui'],stdin=subprocess.DEVNULL).returncode)"`。
- 无独立 lint 命令、无 apidoc 门禁（API.md 已在后续组退役）；CI（`.github/workflows/ci.yml`）
  = pytest + framebench 退出码 + golden --check + demo replay + `--pages`。

## 4. 关键类型/接口/数据流（本组相关）

- `Revisioned` 协议（block.py:179）：`revision() -> object` 值快照；相等 ⟹ 同宽下行相等。
  `None` = 记忆关闭。`Block._cacheable` 构造时判一次。
- `Block` 三门（W1 后现实）：`rows(width)` 自有拷贝；`rows_view(width)` 借用缓存本体
  （只读契约）；`row_count(width)` 只问行数；私有 `_refresh` 是唯一 hit/miss 判定。
- `Document`（W1 后现实）：`mutation` 只读计数（add/remove 各 +1）；`blocks()` 按
  mutation 键缓存 tuple，未变返回同一对象。
- `Viewport.layout`：全块漫游构建 top/body/bottom + 窗口切片（M2/W2 对象，尚未索引化）；
  `natural_height`（W1 后走 `row_count`）只有 dock/resize 调（driver.py:764），不在每帧路径。
- `Frame.compose`（frame.py:1286）：`plan`/`table` 两层 list 每次全新分配（M5 对象）；
  行级备忘录 `self._row_memo`（D11）防重拼接；单 pane 无 chrome 时直通（pass-through）。
- `TextBuffer`（textbuf.py）：`lines` 公开可变、`_version` 每次内容变更 +1（D6）、
  `value` 每次全文 join（M6 对象）。内部无外部对 `lines` 的就地改动（已核实）。
- `ScrollState`（scroll.py）：offset/content_height/viewport_height + stick_to_bottom；
  `clamp()` 由 layout 喂数。本组零改动。

## 5. 约定

- 注释与 docstring：英文，讲"为什么/契约"，密度高（每个公共方法都有契约型 docstring）。
- commit：英文一行祈使句，模块前缀（`viewport: …`、`block: …`、`release: …`）。
- 测试风格：平铺函数 + 内联构造，无参数矩阵；golden 是字节级红线，不轻录。
- spec/handoff：中文；`specs/` 随仓库提交。

## 6. 环境陷阱

- Windows（Git Bash）+ uv；仓库自带 `.venv`；命令统一 `uv run …` 前缀。
- `tools/framebench.py` 计时行对 CPU 竞态敏感——不要与 pytest 并行跑。
- 路径含中文/空格时统一加引号；worktree 在仓库外 `C:\Users\shifu\.worktrees\mocode-tui\`。
- `render-hash` 与平台无关（HeadlessScreen 纯函数），但 docstring 里的历史基线值已过时，
  以组 overview 红线为准。

## 7. 找 X 去哪

- 每帧为什么卡 → `viewport.py:layout` + `block.py:rows` + `frame.py:compose`。
- "哪些路径在走块拿行" → W1 后 `grep -n "\.rows(" src/motui` **零命中**（只剩定义）；
  行走方全部走 `rows_view`/`row_count`。
- "blocks() 谁在调" → `grep -n "\.blocks()" src/motui`（testing/find/gesture/application/
  selection/viewport/driver）。
- 渲染字节谁定的 → `painter.py` + `lines.py`；快照对账 → `tools/golden.py`。
- 上一组纪律 → `specs/2026-10-17-render-cost/00-overview.md`（D1–D13 拍板表）。
