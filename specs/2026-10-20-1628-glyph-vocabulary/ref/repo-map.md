# 仓库地图（glyph vocabulary 操作）

## 1. 目录职责

```
src/motui/
  kernel/       机制层：style/theme、text/lines（行模型）、events、block（Component/Block/Document）、
                screen/viewport/painter（渲染核心）、frame（Rect/Split/Frame）、selection、cursor、mark
  keys/         字节解码、键源、键表
  widgets/      组件库：一行一个家族（action、choice、list、tree、table、tabs、navlist、rows、
                decor、dialog、layout、diff、indicators、textfield、combobox、autocomplete、
                collapsible、syntax、markdown/）
  interaction/  策略层：focus、pointer、gesture、find、modal、palette、overlays、scrollbar
  app.py        driver（TUI）、testing.py（headless_tui/snapshot）、demo/
tests/          1570+ 用例；tests/golden/pages/*.txt 是 demo 页面的字节级快照
tools/          golden.py（--check/--update）、framebench.py
docs/           DESIGN.md（设计+命名宪章）、COMPONENTS.md（宿主契约）、releases/
specs/          过程资产（本组在 2026-10-20-1628-glyph-vocabulary/）
```

## 2. 入口点与核心模块

- 库入口：`motui`（根门面 34 个名字，`tests/test_api_root.py` 钉死各层 `__all__`）、`motui.kernel`、
  `motui.widgets`、`motui.interaction`。
- demo：`python -m motui`（交互/管道回放）、`python -m motui --pages`（逐页 dump）。
- 行模型：`kernel/lines.py` 的 `Segment`/`Line`；`Line.fit`（裁减）、`Line.fill`（延展+铺面，样式合并到内容之下）、
  `Line.filled`（整行空白）。
- 组件协议：`render(width) -> list[Line]`；交互动词 `click/hover_at/handle/move/activate`；
  `Revisioned.revision()` 是行缓存快照。
- 行带合约（1.1.9）：行组件按 `ground`（静息）/`ground_active`（光标行）/`hover`（指针行）解析，
  带子贴行自身单元（药丸），有背景的带不再叠 `dim`。

## 3. 命令（真实可跑）

```
uv run pytest -q                                  # 全量（基线 1623 passed, 1 skipped）
uv run python tools/golden.py --check             # 11 页快照
uv run python tools/golden.py --update            # 重录（仅当文本确实变化）
uv run python -c "<framebench wrapper>"           # exit 0 + render-hash 行（见总纲）
uv run python -m motui --pages                    # 逐页 dump，exit 0
```
无 lint / typecheck 配置；pytest 就是门禁。每个 worktree 先 `uv sync --locked`。

## 4. 关键类型/接口/数据流

- `Document`（有序 Block）→ `Viewport.layout(width, height)` → `ScreenLayout(rows, width, height, …)`
  → `Frame.compose` → `Painter.paint`。行缓存键 `(width, revision())`。
- `Theme`（冻结 dataclass，样式字段）+ `Themed._pick(explicit, field)`：显式 > theme > DEFAULT。
- 字形（本操作）：`widgets/list.py` 的 `MARKER`/`MORE_UP`/`MORE_DOWN`、`widgets/choice.py` 的
  `MARKER`/`EMPTY_MARK`/`FILLED_MARK`、`widgets/tree.py` render 内的 `▾/▸`、`widgets/navlist.py` 的 `bar` 参数、
  `kernel/mark.py` 的 `MARKED/UNMARKED/mark_prefix`、`widgets/markdown/nested.py` 的 `TODO_MARK/DONE_MARK`、
  `interaction/scrollbar.py` 的 `TRACK/THUMB`。
- 座位现状：Select 用 `visible_width(marker)+1`（正确）；List 用 `len(MARKER)+1`（宽字符下错位，本操作修复）；
  Tree 叶子固定一格；NavList 的 `bar_space` 宽度待核。

## 5. 约定

- 代码注释与文档一律英文；commit 信息 `area: statement -- reason`（如
  `widgets: the row band hugs the row's cells -- a pill, not a ribbon`）。
- 无 shim、无别名：改名即删旧名，消费者同 commit 更新。
- 样式解析一次（构造时）；组件不 import screen/painter/keys/app。

## 6. 环境陷阱

- Windows 10 + Git Bash；uv 0.12.21；Python 3.12；路径 `C:\Users\shifu\Desktop\mocode-tui`。
- **`core.autocrlf`**：golden 的 `matches` 只接受精确的 LF→CRLF 转换；`--update` 后其他页面若只有换行符
  diff，用 `git checkout --` 还原，别把噪声提交进去（历史波次踩过）。
- `uv.lock` 锁住本地包版本：改 `pyproject.toml` 版本必须先 `uv lock`（本操作不改版本）。
- worktree 在 `~/.worktrees/mocode-tui/<名称>`；不要用 `cd` 跨 worktree 跑 git 命令。
- demo 的皮肤在 `demo/assets.py`；golden 只对文本敏感（样式变化肉眼可见但 golden 看不见）。
- framebench 的 render-hash 打在一个不含行组件的工作负载上；行组件的变化不会移动它。

## 7. 找 X 去哪

- 标量座位/光标：`widgets/list.py`（`_row`/render 的 lead）、`widgets/choice.py`（`_row`/`_mark_width`）。
- 标记列：`kernel/mark.py` 的 `mark_prefix`，消费方 List/Table/CheckGroup。
- 树的缩进/指示：`widgets/tree.py` 的 `_node_row` 与 render 的 guide/indicator。
- 滚动条字形：`interaction/scrollbar.py` 顶部常量与 `_strip`。
- Markdown 任务框：`widgets/markdown/nested.py` 的 task 规则与 `RenderContext`。
- 文档：`docs/DESIGN.md`（命名宪章表）、`docs/COMPONENTS.md`（组件参数表）。
