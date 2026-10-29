# W5 · 样式重构（目标占位，JIT 补全）

> 分支 `w2.1.2-w5-styles`。依赖 W4b/W4c 合并。

## 目标

`SurfaceStyles` 增加 `control/accent/danger`；`ControlStyles` 瘦身为状态
overlay（`hover/focus/active/disabled` + `overlay()`），删除 `base`/`band()`；
`ButtonKind` 四态与统一 `action_band`；Input/Editor 字段底板；Link/Tabs/
MenuBar 焦点修复；Dialog `surfaces.raised`；`Theme.flat()` 覆盖新 token。

## 范围

`kernel/theme.py`、`widgets/action.py`、`textfield.py`、`dialog.py`、
`tabs.py`、`menubar.py`、`indicators.py`、`decor.py`、`pixel_canvas.py`、
相关测试、`tests/golden/semantic/*`。

## 验收

- 全量门禁全绿；semantic 可重录，但必须逐场景确认**行文本不变**（只有
  `\t` 后的 runs 变化），并在 handoff 记录。
- `framebench.py` 的 render-hash 会变：记录新值与原因。
- `api.py --check` 差异报告给 lead。

## 依赖

W4b/W4c 合并、`ref/interfaces.md` 更新。
