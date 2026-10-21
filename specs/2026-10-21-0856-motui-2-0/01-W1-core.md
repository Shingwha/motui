# W1 · 2.0 core value layer + legacy bridge

> 分支 `motui-2/w1-core`；起点 `main`；写入范围见下。

## 目标

建立 2.0 的全部值类型与 Theme/Glyphs API，同时把默认值保持为 1.x 的 legacy 视觉，
并提供**临时兼容属性**让未迁移组件继续工作。本波结束后 824 tests、58 goldens、
render-hash 必须与基线逐字节一致。

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → 本工单。
- 基线（worktree 根，先 `uv sync --locked`）：

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
```

- 已知约束：`DEFAULT_THEME` 在 W1/W2 必须保持 legacy 视觉；兼容属性 W4 删除。

## 工单（每项一个 commit）

### T1 `Color` + `Style`

- `src/motui/kernel/style.py`：
  - 新增 `Color(value: str | tuple[int,int,int], ansi: str | None = None)`；
    `ansi` 必须是 `FG_CODES` 键或 `None`，否则 `ValueError`。
  - `Style.fg/bg` 类型扩展为 `Color | str | tuple | None`。
  - `_sgr_codes`、`_mode_color_code` 支持 `Color`：truecolor/256 用 `value`，
    16 用 `ansi`（缺失才量化），none 丢弃颜色。
  - 保留现有语义常量（W4 删除）。
- 只允许改：`src/motui/kernel/style.py`。
- 验证：`uv run pytest tests/kernel/test_style.py -q -p no:cacheprovider`。

### T2 Palette、role groups、Theme

- `src/motui/kernel/theme.py`：
  - 新增 `Palette`、`DARK_PALETTE`、`LIGHT_PALETTE`，字段与值严格按
    `ref/interfaces.md` §2。
  - 新增 `TextStyles`、`SurfaceStyles`、`BorderStyles`、`ControlStyles`、
    `RowStyles`、`StatusStyles`、`ContentStyles`、`ChromeStyles`、
    `OverlayStyles`、`SyntaxStyles`；全部 `frozen=True, slots=True, kw_only=True`，
    字段默认值 = `ref/interfaces.md` §3.1 的 legacy 值。
  - 新增 `Theme`（10 个 group 字段），全部有默认工厂。
  - `Theme.dark()/light()/flat()` 用 `from_palette` 构建；`auto(env=None)` 读
    `COLORBGBG`/`TERM_BACKGROUND`，未知回退 dark；`from_palette` 按 §3.2 派生。
  - `RowStyles.band(...)`、`ControlStyles.band(...)` 按 §3.3 实现。
  - 临时兼容属性按 §3.4 实现；`headings` 返回 `content.headings`；
    `notice_levels` 返回只读 mapping（旧前缀）。
  - `DEFAULT_THEME = Theme()`（legacy）。
  - `Themed` 新增 `pick(explicit, fallback: Style)`；保留 `_pick` 供未迁移组件。
- 只允许改：`src/motui/kernel/theme.py`。
- 验证：`uv run pytest tests/kernel/test_theme.py -q -p no:cacheprovider`。

### T3 Glyphs + Border

- `src/motui/kernel/glyphs.py`：
  - 新增 `Border`（14 字段）与 `square/rounded/heavy/double/ascii/none`。
  - 新增 `Glyphs`（字段/默认值严格按 `ref/interfaces.md` §4）与 `GLYPHS`。
  - 保留旧常量（W4 删除）。
- 只允许改：`src/motui/kernel/glyphs.py`。
- 验证：`uv run pytest tests/kernel/test_glyphs.py -q -p no:cacheprovider`。

### T4 机械更新旧 Theme 构造

把全仓（`src/`、`tests/`，不含 `docs/`）所有 `Theme(old_field=...)` 和
`replace(DEFAULT_THEME, old_field=...)` 按 `ref/interfaces.md` §6 映射到 group 覆盖。
只改主题构造，不改断言与组件逻辑。

至少覆盖（grep 确认）：

```text
src/motui/demo/assets.py
src/motui/demo/topics/styling.py
tests/app/test_selection_overlay.py
tests/interaction/test_scrollbar.py
tests/interaction/test_find.py
tests/interaction/test_overlays.py
tests/kernel/test_theme.py
tests/kernel/test_text.py
tests/widgets/test_action.py
tests/widgets/test_containers.py
tests/widgets/test_syntax.py
tests/widgets/test_indicators.py
tests/widgets/test_markdown.py
tests/widgets/test_editing.py
tests/widgets/test_diff.py
tests/widgets/test_menubar.py
```

`tests/kernel/test_theme.py` 可重写为 2.0 结构断言 + 兼容属性断言。

- 只允许改：上述文件及 grep 到的同类构造点。
- 验证：`uv run pytest -q -p no:cacheprovider`。

### T5 契约测试

- 新增/扩展：
  - `tests/kernel/test_theme_contract.py`：所有 token dataclass 是
    `frozen/slots/kw_only`，所有字段有默认值，`Theme()`/`DEFAULT_THEME` 行为。
  - `tests/kernel/test_glyphs.py`：每个单字形 `wcswidth == 1`；默认 Glyphs 不含
    Emoji 展示字符（维护一个小型拒绝集：`ℹ ✔ ✖ ☐ ☑ ⚠ ❗ ❌ ✅` 等）。
  - `tests/kernel/test_style.py`：`Color` 在 truecolor/256/16/none 下的 SGR。
- 只允许改：上述测试文件。
- 验证：`uv run pytest tests/kernel -q -p no:cacheprovider`。

## 验收

```bash
uv run pytest -q -p no:cacheprovider          # 824 passed
uv run python tools/golden.py --check         # 58 topics match
uv run python tools/framebench.py             # hash f872187a…d6e1
uv run python -m motui < /dev/null            # exit 0
uv run python -m motui --pages > /tmp/pages.txt  # exit 0, 4130 lines
```

## 禁触清单

- `src/motui/widgets/`、`src/motui/interaction/`、`src/motui/app.py`、
  `src/motui/keys/`、`tests/golden/`、`tools/`、`docs/`、`pyproject.toml`。
- 不运行 `tools/golden.py --update`；不 merge/push/tag。

## 交接包

最后一个 commit 写 `handoff/W1-core.md`。重点写：Color 的降级路径、
legacy 默认值与兼容属性映射、`RowStyles.band` 的精确语义、契约测试结果、
哪些测试被机械改写。

## 最终报告

工单状态表 / commits / 真实门禁输出 / 偏差与取舍 / 探索审计 / 未决问题。
