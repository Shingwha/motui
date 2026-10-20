# W4 · 组件契约、共享基类与 P0 修复（占位，JIT）
> 状态：待 W3 合并后补全。依赖 W3。

## 目标

统一 controller/result/cursor 契约；抽 `RowBands`/`RowView`/`RowCache`/`CursorWindow`/`Markable`/
`Disableable`；修 P0：`Markdown.revision`、`CheckGroup.click`、`ComboBox` paste、`Input(text=)`、
`Spinner.render`、`NavList.bar_space`、`Autocomplete`/`Tree` hover、`prompt_dialog` 导出；
`Dialog`/`Collapsible`/`ComboBox` 实现 `Container`；`Dialog` 复用 `Button` 激活语义。

## 范围（草稿）

`src/motui/widgets/**`、`kernel/{cursor,mark,glyphs}.py`、相关测试。

## 验收（草稿）

- 每个组件一张协议矩阵测试
- 所有 `chosen` 迁移为 `take_result()`
- `CheckboxGroup`/`RadioGroup` 命名落地
- 全量门禁 + golden 有意变化解释

## 不做

W5 的新组件、W6 的 Host。
