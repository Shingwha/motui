# W6 · 交互层解耦与 overlay/focus 栈（占位，JIT）
> 状态：待 W2/W4 合并后补全。依赖 W2、W4。

## 目标

用 `kernel/host.py:Host` 断掉 `interaction -> app` 与 `interaction -> widgets`；overlay 显式 layer
与 z-order；Modal 栈 + focus trap/restore；Pointer enter/leave；selection 统一；dispatch order 由库提供。

## 范围（草稿）

`src/motui/kernel/host.py`（新）、`interaction/**`、`app.py`（实现 Host）、相关测试。

## 验收（草稿）

- import-linter/手写脚本零环
- 两个 modal 叠加/关闭后 focus 恢复
- overlay 层序可验证
- 全量门禁

## 不做

W7 的文档/发版。
