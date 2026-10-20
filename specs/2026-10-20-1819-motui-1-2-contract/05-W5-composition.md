# W5 · 组合层补齐（占位，JIT）
> 状态：待 W4 合并后补全。依赖 W4。

## 目标

新增 `ScrollView`、`Form`/`Field`（校验/字段导航/错误行）、`MenuBar`/`ContextMenu`、
`FocusManager`（add/remove/next/prev、focus 事件、modal trap/restore）、`CommandRegistry`、
`Clipboard`；可选 Table/Tree 虚拟化。

## 范围（草稿）

新文件为主；`widgets/__init__.py`、`interaction/__init__.py`、`tests/**`、demo exhibit。

## 验收（草稿）

- 每个新组件有 render/协议/交互/golden 测试
- demo 至少一个 exhibit
- 全量门禁

## 不做

图表/日期选择器/网格/拖拽分隔条（D9）。
