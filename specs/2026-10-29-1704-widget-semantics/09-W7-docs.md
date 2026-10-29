# W7 · 文档与 docstring 清理（目标占位，JIT 补全）

> 分支 `w2.1.2-w7-docs`。依赖 W6。

## 目标

- docstring 从“论文”改成“契约卡”：模块 1–2 句；类 ≤6 行；公开方法 ≤6 行；
  私有方法默认不写；禁止版本历史/参数复述/实现流水账；目标总量减半。
- `docs/CONTRACT.md`、`docs/WIDGETS.md`、`docs/ARCHITECTURE.md` 更新到新契约；
  新增四个 ADR（组合与透明、Drawing 生命周期、状态/动词/结果契约、
  控件样式 overlay）。
- 测试去重：删除重复的能力/keymap/height-budget/纯改名断言，目标用例总数
  减约 1/4，覆盖不降。

## 范围

`src/motui/**/*.py` 的 docstring、`docs/`、`tests/`。

## 验收

- 全量门禁全绿；semantic 全绿（本波不改渲染）。
- 报告 docstring 行数前后对比与用例数前后对比。

## 依赖

W6 合并。
