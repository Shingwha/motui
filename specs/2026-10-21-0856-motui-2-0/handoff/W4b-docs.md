# W4b 交接包（docs and 2.0 release）

> 分支 `motui-2/w4b` / 起点 `d661659`（main，W3 已合并）/ 2026-10-21
> 文档与版本 1 个 commit（`be00612`）；本文件为最后一个 commit。

## A. 自动事实

### 门禁真实输出

```text
uv run python -m motui --pages > /tmp/pages.txt
exit=0
4130 /tmp/pages.txt                      # 与基线行数相同

uv lock --check
Resolved 11 packages in 1ms
exit=0

uv sync --locked
exit=0
installed 2.0.0                          # importlib.metadata

uv run pytest tests/test_packaging.py -q -p no:cacheprovider
1 failed, 1 passed in 0.37s
exit=1
# 唯一失败：tests/test_packaging.py:45
# AssertionError: assert '1.1.8' == '2.0.0'
# 原因：src/motui/__init__.py 的 fallback 仍为 1.1.8；W4a T5 负责改为
# 2.0.0。工单禁止 W4b 修改 src/，故本分支单独跑必然失败；合并 W4a 后
# pyproject / metadata / fallback 三者一致。

uv run pytest -q -p no:cacheprovider
1 failed, 896 passed in 11.40s
# 失败项同上，其余 896 全绿（基线 897 = 896 passed + 该 packaging 用例）。
```

基线（开工前同 worktree）：`--pages` exit 0、4130 行；packaging 测试在
1.1.8 下通过。

### Commit 清单

| commit | 内容 |
|---|---|
| `be00612` | `docs: ship the 2.0 Ink & Signal documentation` |
| 本文件所在 commit | `specs: hand off the W4b docs release` |

### 变更范围 / 禁触审计

`be00612` 只改 8 个文件：

- `pyproject.toml`（version 2.0.0、description 补 Ink & Signal、keyword）
- `uv.lock`（editable motui 1.1.8 -> 2.0.0，仅此一行变化）
- `docs/CONTRACT.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`
- `README.md`、`CONTRIBUTING.md`、`CHANGELOG.md`

`git status` 确认 `src/`、`tests/`、`tools/`、`specs/`（除本交接文件）、
`docs/releases/` 零改动。未改 `src/motui/__init__.py` 的 fallback（W4a）。
未 merge/push/tag；golden 与 render-hash 未动。

### 文档章节清单

**docs/CONTRACT.md**

- 新增 §5 *Styles, Palette and theme*：`Color`/`Style` 值类型、ANSI 锚点
  在 `truecolor/256/16/none` 下的行为、`Palette` 18 字段、`Theme` 10 个
  role group 表、`dark/light/flat/auto/from_palette`、`RowStyles.band` /
  `ControlStyles.band`、`Glyphs`/`Border`/`seat`/`seat_width`/`pair_seat`、
  逐字形参数与实例覆盖规则。
- §6 *Components*：`RowBands` 段落改为 `theme.rows.band(...)` 与
  `theme.controls.band(...)`；新增 `glyphs=` 与空字形规则。
- §7 *Focus, selection and overlays*：选择 token 改为
  `theme.text.selection`。
- 旧 §6..§11 顺延为 §7..§12；文末 import-graph 引用改为 §8。

**docs/DESIGN.md**

- Layers 表的 `kernel` 职责补 palettes/glyphs/borders；root facade 34 -> 37。
- 新增 *Theme, Palette and glyphs* 设计章：1.x 扁平主题的问题、`Color`
  双词汇、`Palette` 创作层与 10 个 role group 的应用层、构造器表、
  `flat/auto` 策略、band 优先级、Glyphs/Border 与 Theme 分离、trade-off、
  extend 指引。
- *Value semantics*：删除 `RowBands`，补 `Color/Palette/Glyphs/Border`，
  `Theme` 两层冻结、`content.headings` tuple、无 derived mapping。
- Selection 段读取 `theme.text.selection`。

**docs/COMPONENTS.md**

- 全部公开组件签名更新到 2.0：新增 `glyphs=GLYPHS`（Markdown/Diff/Notice/
  Input/Checkbox/RadioGroup/CheckboxGroup/Select/ComboBox/Autocomplete/
  Slider/List/Table/Tree/Tabs/NavList/ProgressBar/Spinner/Panel/Divider/
  Collapsible/ScrollView/MenuBar/ContextMenu/ShortcutBar/Dialog/
  confirm_dialog/prompt_dialog/Palette controller），`Table(grid=)`、
  `Panel(border=)`、`Dialog(border=)`。
- 删除 `RowBands` 目录条目；*The row-band contract* 改为
  `theme.rows.band(...)` 的 6 级优先级与 `replace(DEFAULT_THEME, rows=...)`
  示例；控件走 `theme.controls.band(...)`。
- `Notice` 改为 `i/✓/!/×` 四级字形；Markdown task 改为
  `[ ]/[x]`、bullets/quote 走 Glyphs；Slider/Scrollbar/Progress/Spinner/
  ShortcutBar/NavList/Tabs/MenuBar 的字形来源全部改写。
- *Theme, Palette, glyphs and keymaps* 整节重写：10 组表、构造器、band、
  Palette/Color、31 个 Glyphs 字段表、Border 六种构造、seat 辅助函数。
- *Build your own* 的 Meter 示例不再使用 `DIM/SUCCESS`，改为
  `theme.status.success` / `theme.text.faint` 与 `GLYPHS.bar_*`；Chrome 示例
  的 `theme.dim` 改为 `theme.text.faint`。
- Find/Scrollbar/Toasts/Tooltip/Stats 的 token 改为新 group 路径。

**README.md**

- Features 的主题/字形条目改为 role groups + `Palette` + `Glyphs`/`Border`。
- root 34 -> 37 names；`motui.widgets` 44 -> 43（`RowBands` 删除后）。
- 组件表：`Notice` 改为 `i/✓/!/×`；删除 `RowBands` 行。
- *Styling* 整节重写：`replace(theme, group=...)`、`Theme.from_palette`、
  `Color` 锚点、`light/flat/auto`、`theme.rows.band`、`glyphs=`/`Border`。
- 命令面板示例的 `Palette` 改从 `motui.interaction` 导入，避免与品牌
  `Palette` 重名。

**CONTRIBUTING.md**

- 不变量重排为 1..9：root 37、`RowBands`/旧常量删除规则、2.x 契约只做
  加法、MAJOR 才拥有移除/改名。
- `kernel` 职责补 palettes/glyphs/borders；`tests/test_api_root.py` 更正为
  `tests/test_api.py`。
- Versioning 明确 2.x additive；MINOR 不再承载 breaking change。

**CHANGELOG.md**

- 新增 `## [2.0.0] — 2026-10-21`：Ink & Signal 暗色默认、10 role groups、
  Palette、Color ANSI、Glyphs/Border、RowBands/旧常量/逐字形参数删除、
  Notice/Markdown 行为变化、迁移示例（`replace(theme, group=...)`、
  `glyphs=`）。

**T1 版本与元数据**

- `pyproject.toml`: `version = "2.0.0"`；description 含 "Ink & Signal"；
  keywords 增 `ink-and-signal`。
- `uv lock` 后 `uv.lock` 的 `[[package]] motui` 为 2.0.0；`uv sync --locked`
  安装 metadata 2.0.0；未改 `src/motui/__init__.py`。

### T3 旧名字 grep 结果

命令：

```bash
grep -rn --include='*.md' -- '<name>' docs README.md CONTRIBUTING.md CHANGELOG.md
```

当前 API 文档（COMPONENTS / CONTRACT / DESIGN / README）中：

| 名字 | 结果 |
|---|---|
| `RowBands` | 0（CONTRIBUTING/CHANGELOG 仅作为“已删除”说明） |
| `mark_pair=` | 0（仅 CHANGELOG 删除清单/1.1.9 历史） |
| `task_marks` | 0（仅 CHANGELOG 删除清单/1.1.9 历史） |
| `glyphs.CURSOR` | 0 |
| `theme.accent` | 0 |
| `DEFAULT_THEME.accent` | 0 |
| `WARNING: ` / `ERROR: ` | 0 作为当前 API；仅 CHANGELOG 说明“已删除”及 1.x 历史 |
| `expanded=` / `collapsed=` | `collapsed=` 仅 CHANGELOG；`expanded=` 在 COMPONENTS 命中 `TreeNode(..., expanded=False)`（仍然有效的节点状态 API，不是已删除的 `Tree(expanded=)` 字形参数） |
| `bar=` | COMPONENTS 的两处命中是 `scrollbar=` 的子串（`ScrollView` 的 `scrollbar=False`）；不是已删除的 `NavList(bar=)` |
| `divider=` | 仅 CHANGELOG 删除清单 |

`docs/releases/*.md` 是历史发布说明，保留 1.x 名字，未改动。

## B. 只有存在于脑子里的东西

### 与 W4a 的交叉依赖（最重要）

1. **packaging 测试在本分支单独失败是预期。** `pyproject.toml` 2.0.0 后，
   `src/motui/__init__.py` 的 fallback 仍是 `1.1.8`，`tests/test_packaging.py`
   直接读源码正则并断言 fallback == pyproject version。工单明确 fallback
   由 W4a T5 修改。合并 W4a 后该用例应转绿；若先合 W4b 再合 W4a，中间
   main 会红一条。
2. **文档描述的是 W4a 之后的最终 2.0 面。** 因此：
   - 文档不再列 `bands=`，但本分支源码仍接受；
   - 文档不再列旧 `kernel.style`/`kernel.glyphs` 常量，但本分支源码仍有；
   - 文档写 `theme.rows.band(...)`、RadioGroup/CheckboxGroup label
     `text.base`、List counter `text.muted`，这些是 W4a T4 的收口。
   合并顺序应为 W4a → W4b，或二者一起终验。
3. **根导出 `Palette` 冲突。** 2.0 前根 `Palette` 已经是
   `motui.interaction.Palette`（命令面板 controller），demo 也这样用。
   interfaces §0 / W4a T5 又要求根新增品牌 `Palette`，同名无法共存。
   本波的处理：
   - 品牌调色板文档统一写 `from motui.kernel import Palette`；
   - 命令面板写 `from motui.interaction import Palette`；
   - README 的命令面板示例已改为从 `motui.interaction` 导入；
   - CHANGELOG 只说 `Palette/Glyphs/Border` 在 `motui.kernel` 公开，
     `Glyphs/Border` 也进根，未声称品牌 `Palette` 在根；
   - README/DESIGN/CONTRIBUTING 的 root 计数按工单写 37
     （34 + 新增 3）。若 W4a 实际保留根命令 `Palette`，则根只有 36 个
     名字，需要 lead 在合并时决定：改计数、改根命名，或让品牌
     `Palette` 只留在 `motui.kernel`。
4. **W4a T5 的 `tests/test_api.py`** 是结构性断言，不钉名字列表；新增
   `Palette/Glyphs/Border` 不会要求改测试。README 的 37/43 是文档声明，
   不是测试断言。

### 文档取舍

- **CHANGELOG 仍出现旧参数名**（`mark_pair=`、`task_marks`、
  `WARNING: ` 等），这是 Breaking 章节解释“删了什么”所必需；它们不是
  当前 API 示例。全仓机械 grep 不可能在保留历史 CHANGELOG 的前提下归零。
- **`TreeNode(expanded=)`** 是节点状态，保留；已删除的是
  `Tree(expanded=, collapsed=)` 的逐字形参数。grep `expanded=` 会命中前者。
- **`scrollbar=` 会命中 `bar=` 子串**；这不是 `NavList(bar=)` 残留。
- **`docs/releases/`** 属于历史归档，未改；其中仍有 1.x 的 `RowBands`、
  `theme.selection` 等描述。
- 没有改 `docs/releases/2.0.0.md` 或发布说明（工单不要求；release 时再写）。
- 没有改 golden、framebench、render-hash；本波零代码改动，视觉字节不变。

## C. 指针

- 工单：`specs/2026-10-21-0856-motui-2-0/04-W4b-docs.md`
- 接口：`specs/2026-10-21-0856-motui-2-0/ref/interfaces.md` §1–§5
- 视觉/清理：`specs/2026-10-21-0856-motui-2-0/handoff/W3-visual.md`、
  `04-W4a-cleanup.md`
- 契约：`docs/CONTRACT.md` §5（新增）、§6、§7
- 设计：`docs/DESIGN.md` *Theme, Palette and glyphs*、*Value semantics*
- 组件：`docs/COMPONENTS.md` *Theme, Palette, glyphs and keymaps*、
  *The row-band contract*
- 版本：`pyproject.toml`、`uv.lock`
- 变更清单：`git show --stat be00612`
- 起点 `d661659`；文档 commit `be00612`；本文件所在 commit 为 W4b HEAD
