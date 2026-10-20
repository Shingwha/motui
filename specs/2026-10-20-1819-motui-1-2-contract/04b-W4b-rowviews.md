# W4b · row views、共享行带与 rows/decor（占位，JIT）
> 状态：待 W4a 合并后补全。依赖 W4a。

## 目标

把 List/Table/Tree/Tabs/NavList 迁到同一套 cursor/result/disabled 契约；用 `RowBands`/`RowView`/
`CursorWindow`/`Markable` 收掉 5 份行带与窗口算术；修 `Tree.filter`/`Autocomplete` 遗留的 hover 状态；
`NavList.bar_space` 收成只读；`Tabs._tab_at` 不再每次 hit 重 render；`List/Table/Tree` 实现 `take_result`。
补齐 `Divider`/`Panel`/`Notice`/`StatusLine`/`ShortcutBar` 的 `Revisioned`；`Layout`/`Delegate` 容器契约。

## 范围（草稿）

`src/motui/widgets/{list,table,tree,tabs,navlist,bands,decor,rows,layout,delegate}.py`、相关测试、demo、文档。

## 验收（草稿）

- 五个 row view 的协议矩阵：index/select/move/home/end/activate/toggle/take_result/disabled
- `RowBands` 成为唯一行带实现；`CursorWindow` 覆盖 Select/List/Editor
- `Tree.filter`/`NavList` hover 清空
- sealed block 突变后 `Divider`/`Notice`/`StatusLine`/`ShortcutBar` 重绘
- 全量门禁 + golden 有意变化需解释

## 不做

W5 的新组件（ScrollView/Form/Menu/FocusManager/CommandRegistry/Clipboard）。
