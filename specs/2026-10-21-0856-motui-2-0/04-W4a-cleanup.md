# W4a · Remove the bridge and close the visual contract

> 分支 `motui-2/w4a-cleanup`；起点 `main`（W3 已合并）；写入范围见下。

## 目标

删除 1.x 兼容层与旧 API，收口 §5 的最后两处视觉偏差，导出新公开类型，重录 golden
并记录最终 hash。

## 前置上下文

- 必读：`ref/interfaces.md` §3.2/§4/§5/§7.1 → W3 handoff。
- 基线：`uv run pytest -q -p no:cacheprovider` 897 passed；golden 58；hash
  `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`。

## 工单

### T1 删除兼容属性与 `_pick`

- `kernel/theme.py`：删除 §3.4 全部兼容属性（`accent/muted/dim/...`、`headings`、
  `notice_levels`）；删除 `Themed._pick`；只保留 `pick`。
- `kernel/lines.py`：`SpanText` 的 `_pick(None, "hover")` -> `pick(None, self._theme.surfaces.hover)`。
- 全仓 grep 旧属性读取，清零。

### T2 删除 RowBands/BandedRows

- 把 `rest(row, width, band)` 移到 `kernel/lines.py`（或 `Line` 的辅助函数），
  更新 list/tree/table/choice/navlist 的 import。
- 删除 `widgets/bands.py`。
- 删除 List/Select/RadioGroup/CheckboxGroup/Tree/NavList/Table 的
  `bands: RowBands | None = None` 参数；默认路径直接用 `theme.rows.band(...)`。
- `widgets/__init__.py` 删除 `RowBands` 导入与 `__all__`。
- `demo/topics/styling.py` 的 row-bands topic 改用
  `replace(DEFAULT_THEME, rows=...)`，更新文案与 golden。

### T3 删除旧常量

- `kernel/style.py`：删除 `ACCENT/BORDER/CODE/DIM/ERROR/FOCUS/HEADING/INLINE_CODE/
  LINK/LIST_MARKER/MUTED/SELECTION/SUCCESS/WARNING` 及其 `__all__`。
- `kernel/__init__.py`：同步删除这些导出。
- `app.py`：`Text(text, style=MUTED)` -> `self.theme.text.muted`。
- `kernel/selection.py`：默认样式改为 `Style(reverse=True)`（或局部常量），更新 docstring。
- `kernel/glyphs.py`：删除旧字形常量及 `__all__`；保留 `Glyphs/Border/GLYPHS/pair_seat/seat/seat_width`。
- `interaction/scrollbar.py`：确认 `track/thumb` 默认是 `None -> GLYPHS.bar_empty/full`，
  不再引用旧 `glyphs.TRACK/THUMB`。
- `widgets/indicators.py`：删除未使用的 `FILL/EMPTY/DEFAULT_FRAMES`。
- `kernel/mark.py`、`widgets/scroll.py` 等 docstring 中的旧常量引用改成 `Glyphs` 字段。

### T4 最终视觉收口

- `RadioGroup` / `CheckboxGroup` 的 label 改为 `text.base`（mark 保持 `content.accent`）。
- `List` counter 改为 `text.muted`。
- 删除 Table 的 `rows.hover is NONE -> surfaces.hover` 兼容桥。
- 如有其他 §5 与实现不一致处，按 §5 收口。

### T5 公开面

- `kernel/__init__.py` 导出 `Palette`、`Glyphs`、`Border`（以及 `GLYPHS` 可选）。
- 根 `src/motui/__init__.py` 导出 `Palette`、`Glyphs`、`Border`；`__all__` 同步。
- `src/motui/__init__.py` 的 fallback 版本改为 `2.0.0`（pyproject 由 W4b 改）。
- `tests/test_api.py` 保持结构性断言；必要时更新矩阵。
- `tests/test_invariants.py` 的 CASES 不受影响，但确认新构造签名仍覆盖。

### T6 测试与 golden

- `tests/kernel/test_theme.py`：删除兼容属性断言；新增“旧属性不存在”的断言。
- `tests/kernel/test_theme_contract.py`：同上。
- `tests/app/test_selection_overlay.py`：`DEFAULT_THEME.selection` -> `text.selection`。
- `tests/interaction/test_scrollbar.py`：旧 `glyphs.TRACK/THUMB` -> `GLYPHS.bar_empty/full`。
- 所有 `bands=RowBands(...)` 的测试改为 theme rows。
- `uv run python tools/golden.py --update` 重录；`--check` 通过；记录新 hash。
- `uv run python -m motui < /dev/null`、`--pages` exit 0。

## 验收

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages > /tmp/pages.txt
```

`tests/test_packaging.py` 必须通过（W4b 改 pyproject，W4a 改 fallback；两者合并后一致）。

## 禁触清单

`docs/`、`README.md`、`CONTRIBUTING.md`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`
（W4b 所有）。不改布局算法/事件模型/Host 协议。不 merge/push/tag。

## 交接包

`handoff/W4a-cleanup.md`：删除清单、最终签名、golden/hash、遗留项。
