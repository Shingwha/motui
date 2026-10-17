# ref：lead 已核实的事实（两个 agent 都只信这份与 spec 本体）

## 环境

- OS：Windows 10（win32 28120 x64），shell = Git Bash；`uv 0.12.21`，venv Python `3.13.16`
  （`.venv/Scripts/python.exe`）。
- 仓库根（主检出）：`C:\Users\shifu\Desktop\mocode-tui`（agent 不许碰）。
- worktree：`C:\Users\shifu\.worktrees\mocode-tui\<分支>`。
- 运行测试：`uv run pytest -q`（本机约 5.4 s）。

## 基线（lead 2026-10-17 实测，main `6dd2948`）

- `uv run pytest -q` → **1395 passed, 1 skipped**。
- `uv run python tools/golden.py --check` → 绿（11 页：`tests/golden/pages/`）。
- `uv run python tools/apidoc.py --check` → 绿。
- 门禁工具：`tools/golden.py --update` 整组重录；`tools/apidoc.py --write` 重生成
  `docs/API.md`；`tools/framebench.py` 打印六行（四个计时 + `replay` + `render-hash`，
  现基线 hash `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`——
  Diff 不在它的负载路径上，预期不变）。
- demo 两入口：`uv run python -m motui --pages`（打印每页）与
  `uv run python -m motui < /dev/null`（回放，exit 0）。

## `Diff` 今天的渲染字节（`Diff("a\nb", "a\nc", context=0).render(40)`）

```
'@@ -2,1 +2,1 @@'  ->  '\x1b[38;2;139;148;158m@@ -2,1 +2,1 @@\x1b[0m'   （muted，无 weight）
'-b'                ->  '\x1b[1;38;2;229;83;75m-b\x1b[0m'              （error + BOLD）
'+c'                ->  '\x1b[38;2;75;181;99m+c\x1b[0m'                （success，无 weight）
```

默认调色板里只有两个 bold：`ACCENT`、`ERROR`（`src/motui/kernel/style.py:384,386`）；
`SUCCESS`/`MUTED` 都不带 weight。仓规两处：`style.py:401-403` 的
「structure announces itself with color instead of weight (bold stays reserved for `**...**`)」
与 `kernel/theme.py` 的 heading 注释「No bold: weight stays reserved for `**...**` syntax」。

## 代码与测试的锚点

- 引擎：`src/motui/widgets/diff.py` —— `_split_lines` / `_lcs_ops` / `_regions` /
  `_line_counts` / `_range` / `Diff`（`LCS_LIMIT = 20_000`，`ELISION = "\u2026"`）。
  退化分支在 `_build`（`diff.py:211-224`），`render` 在 `diff.py:267-278`。
- 既有测试里**必须随行为更新的三条**（`tests/test_widgets_diff.py`）：
  - `test_the_bounded_walk_replaces_the_whole_text_in_two_hunks`（2000 行改 1 行 → 今天两个 hunk；
    改后它走真 hunk，fixture 与断言都要换，见 W1 的 T1）
  - `test_context_zero_tightens_the_hunk_and_keeps_the_numbers_exact`（断言 `ELISION in rows`）
  - `test_the_elision_row_sits_between_hunks_in_the_muted_band`（断言 segments == (ELISION, band)）
- 不变量门禁：`tests/test_render_invariants.py`（模块 docstring 的三条；组件矩阵里
  `"Diff"` 与 `"Diff no change"` 两条在 101–102 行，允许 +1 行新条目）。
- 宽度缓存的既有惯例：`src/motui/widgets/markdown/component.py:86-106`（`_rows` + `_width`，
  命中返回 `list(...)`）；viewport 只缓存 SEALED 块（`src/motui/kernel/viewport.py:248-265`）。
- 同仓另一套 diff 配色（只做说明、本次不改）：`src/motui/widgets/syntax.py:220-231`
  的 diff 语言表（`+` → string、`-` → comment），用于 Markdown 围栏里贴的 diff 文本。
- demo 展台：`src/motui/demo/pages/content.py` 的 `BEFORE` / `AFTER`（~52 行起）与
  `Diff(BEFORE, AFTER, theme=theme)`（~134 行）+ 紧随的 `api_note`；页面由
  `demo/registry.py` 的 `Page("content", …)` 注册，golden 页 = `tests/golden/pages/content.txt`。

## 文档面（W2 用）

- `docs/COMPONENTS.md:150`（Diff 表行）、`:193-215`（`### Diff` 小节）、`:142`（脚注提及）。
- `docs/DESIGN.md:139`（D17 行）、`:84`（`motui.widgets` 门面行，预计无改动）。
- `README.md:93`、`:126`（只列名字，预计无改动）。
- `CHANGELOG.md:13`（`## [Unreleased]`，当前为空）。
- `docs/API.md` 是生成物：`tools/apidoc.py --write`；`tests/test_api_doc.py` 是漂移门禁。

## 算法实测证据（lead 的原型，agent 用来对齐预期）

裁剪公共前后缀的收益（原型 vs 今天的 `Diff`）：

| 用例 | 今天 | 裁剪后 | 裁剪+锚点后 |
|---|---|---|---|
| 2000 行改 1 行 | 4002 行 | 9 行 | 9 行 |
| 2000 行顶部插 1 行 | 4003 行 | 5 行 | 5 行 |
| 500 行 3 处散布改动 | 1002 行 | 969 行（仍退化） | **29 行、3 hunk、省略 233/233** |
| 300 行改 1 行 | 602 行 | 9 行 | 9 行 |
| 1000 行隔行改 | 2002 行 | 2000 行 | 1501 行（1 hunk） |
| 2000 vs 2000 毫无共同行 | 4002 行 / 2 hunk | 4001 行 / 1 hunk | 同左 |

差分（30 000 组随机小输入、含重复行；裁剪后的 op 形状 vs 今天的全表 LCS）：
**11% 形状不同、编辑代价升高的样本 0 条**（重复行触发；现有测试与 demo fixture 都用不同文本，
实测 demo 的 12 行 fixture 字节不变）。20 000 组小输入的"裁剪+锚点 vs 全表 DP"差分：
**代价更贵的样本 0 条**。

代价上界（写进 W1 的 docstring/报告）：段内退化（整段 `del+ins`）意味着**总编辑代价 ≤ n+m**，
所以新管线在任何输入上都不会比今天的"整文替换"更差。

## 仓外惯例（本机实测，仅供报告引用，文档理由仍用仓规）

- git 2.56 默认 `git diff --color=always`：`diff --git`/`index`/`---`/`+++`（meta）是
  `\x1b[1m` 粗体；`@@` 是 `\x1b[36m` 青色（不粗）；`-` = `\x1b[31m`、`+` = `\x1b[32m`（不粗）。
- Vim 内置默认（`vim --clean` dump）：`DiffAdd`/`DiffChange`/`DiffDelete` 走底带色，
  彩色终端无 `cterm=bold`（只有给单色终端的 `term=bold`）；**`DiffText`（行内改动片段）
  才是 `cterm=bold`**。
- VS Code / GitHub 的差分：底带（`diffEditor.*Background`）+ 保留语法高亮，词级改动加深底带，
  不靠加粗。
