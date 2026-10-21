# W3 · Visual and glyph switch (JIT)

> 分支 `motui-2/w3-visual`；依赖 W2a-d 全部合并。详细工单在 W2 合并后补全。

## 目标

把 `Theme` 字段默认值切换到 Ink & Signal 暗色，迁移全部 `Glyphs`，让默认视觉
变成 2.0。重录全部 golden，更新视觉断言。

## 范围

- `kernel/theme.py`：字段默认值按 `ref/interfaces.md` §3.2；`DEFAULT_THEME = Theme()`。
- 全部 widget/interaction：逐字形参数 -> `glyphs=`；Notice 文本前缀 -> `notice_*`；
  Markdown task -> `check_*`；Input/Find prompt -> `prompt`；List/Select -> `cursor`；
  Slider -> `slider_*`；Scrollbar/Progress -> `bar_*`；Panel/Dialog -> `box`；Table -> `grid`。
- demo：`THEMES`/styling topic 改用新 groups。
- `tests/`：更新旧颜色/字形断言。
- `tests/golden/topics/*`：`tools/golden.py --update` 全量重录。

## 验收

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages > /tmp/pages.txt
```

新 render-hash 记录在 handoff；W3 之后 hash 稳定。

## 依赖

W2a/W2b/W2c/W2d 全部合并；`handoff/W2*-*.md` 必读。
