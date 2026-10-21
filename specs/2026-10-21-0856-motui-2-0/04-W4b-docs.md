# W4b · Docs and 2.0 release

> 分支 `motui-2/w4b-docs`；起点 `main`（W3 已合并）；写入范围见下。

## 目标

把文档与版本更新到 2.0：Ink & Signal、role groups、Palette、Glyphs、Border、
新组件签名；版本 2.0.0；CHANGELOG 记录破坏性变更。

## 前置上下文

- 必读：`ref/interfaces.md` 全文 → W1/W2/W3 handoff → README/CONTRIBUTING/docs 现状。
- 基线：`uv run python -m motui --pages` exit 0；`tests/test_packaging.py` 通过。

## 写入范围

`docs/COMPONENTS.md`、`docs/DESIGN.md`、`docs/CONTRACT.md`、`README.md`、
`CONTRIBUTING.md`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 工单

### T1 版本与元数据

- `pyproject.toml`：`version = "2.0.0"`；description 可补 "Ink & Signal" 关键词。
- `uv lock` 更新 `uv.lock`；`uv sync --locked` 确认安装元数据为 2.0.0。
- 不修改 `src/motui/__init__.py`（fallback 由 W4a 改）。

### T2 文档重写

- 全篇命名：命令面板 `CommandPalette`（`motui.CommandPalette` /
  `motui.interaction.CommandPalette`，模块 `interaction/command_palette.py`）；
  主题色创作层 `ColorPalette`（`motui.ColorPalette` /
  `motui.kernel.ColorPalette`）。**文档中不得再把裸 `Palette` 当作当前 API。**
- `docs/CONTRACT.md`：
  - Theme 章节改成 `ColorPalette` → 10 个 role groups → `Theme.dark/light/flat/auto/from_palette`；
  - 加入 `Color`（ANSI 锚点）、`Glyphs`、`Border`；
  - 删除旧扁平字段（`accent/muted/dim/...`）作为公开契约的描述，改为 compat 已删除。
- `docs/DESIGN.md`：Theme 设计原理、role group 表、ColorPalette 创作层、Glyphs/Border 分离、
  dark/light/flat 策略；Host 章节保持。
- `docs/COMPONENTS.md`：每个组件签名更新（`glyphs=`、`Border`、删除旧字形参数）；
  RowBands 章节改为 `theme.rows`；Notice level 改为 `i/✓/!/×`；Markdown task
  `[ ]/[x]`；Slider/Scrollbar/Progress 字形；Table `grid=`；CommandPalette 条目。
- `README.md`：安装/快速开始示例改为 2.0 构造；主题示例用
  `replace(theme, content=replace(theme.content, accent=...))` 或
  `Theme.from_palette(ColorPalette(...))`；组件表更新。
- `CONTRIBUTING.md`：root facade 名字数量更新（37）；删除 RowBands/旧常量的规则；
  2.x 只做加法契约。
- `CHANGELOG.md`：新增 `## [2.0.0] — 2026-10-21`，列出：
  - Ink & Signal 暗色默认，light/flat/auto；
  - ColorPalette + 10 role groups；
  - Color ANSI anchors；
  - Glyphs/Border 统一字形；
  - `Palette` -> `CommandPalette` + `ColorPalette`（无裸 Palette）；
  - 删除旧 `style.py` 常量、旧 `glyphs.py` 常量、`RowBands`、逐组件字形参数；
  - 迁移提示（`replace(DEFAULT_THEME, group=...)`、`glyphs=`）。

### T3 校验

- 全仓 grep 旧名字，docs 中不得再作为当前 API 出现：
  `RowBands`、`mark_pair=`、`expanded=`、`collapsed=`、`bar=`、`divider=`、
  `task_marks`、`glyphs.CURSOR`、`theme.accent`、`DEFAULT_THEME.accent`、
  `WARNING: `、`ERROR: `。
- `uv run pytest tests/test_packaging.py -q -p no:cacheprovider`
- `uv run python -m motui --pages > /tmp/pages.txt` exit 0。
- `uv run pytest -q -p no:cacheprovider` 全绿（合并 W4a 后由 lead 终验）。

## 禁触清单

`src/`、`tests/`、`tools/`、`specs/`。不改代码与 golden。不 merge/push/tag。

## 交接包

`handoff/W4b-docs.md`：文档章节清单、版本/锁文件状态、grep 校验、遗留项。
