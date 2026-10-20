# W3 · 值语义、缓存所有权与 selection 主题（占位，JIT）
> 状态：待 W2 合并后补全。依赖 W2。

## 目标

让“frozen”名副其实：`Pane` 改普通可变类或真正不可变；`ScreenLayout` 用不可变容器；`Theme` 派生表、
`FG_CODES` 只读；`Style`/`Segment` 加 slots；一个 row-cache 所有者（`Block.rows`）；主选区使用
`Theme.selection`；`Painter.rows` 长度契约。

## 范围（草稿）

`kernel/{frame,viewport,theme,style,lines,block,selection,painter}.py`、`interaction/find.py`、相关测试。

## 验收（草稿）

- 不可变性测试：改 `Theme.notice_levels`/`Pane` 字段必须失败或返回新值
- `Markdown.max_width` 经 `Block.rows` 后必须 fresh
- selection overlay 跟随 `Theme.selection`
- `Painter.rows` 恒为 `screen.height` 行
- 全量门禁 + render-hash 有意变化需解释

## 不做

W4 的组件基类、W6 的 Host/overlay。
