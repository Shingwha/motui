# W3b · TextBuffer.value 缓存（M6）—— 占位，待 W1 合并后补全 `## 前置上下文`
> 分支 `fp-w3b-value-cache`；前置 W1 已合并（与 W2 并行，文件级不相交）；写入范围 `src/motui/widgets/textbuf.py`、`tests/widgets/`（textbuf/field 所在既有文件）

## 目标

`TextBuffer.value`（textbuf.py:198-201）从"每次访问全文 join"改为按 `version` 缓存
（D6 已有的单调计数），任何编辑置脏。下游每键读 `editor.text` 的宿主不再 O(全文)/键。
语义不变：同样的调用序列返回同样的字符串。

## 范围与验收（占位，派工前不变）

- 缓存键 `version`；`lines` 公开可变的既有事实不改成 property（P8），docstring 补一行
  "直接改 `lines` 不 bump `version`，`value` 不跟随"。worker 开工时复核 motui 内部确无
  对 `lines` 的外部就地改动/整体赋值（lead 已核实一轮，结论在 P8）。
- 新增测试 ≤ 4 条（P9）：编辑后 value 更新、重复读不重 join（可用 join 计数或对象
  同一性断言）、undo/redo 后正确、set_text 后正确。
- 不动 `Editor`/`Field`/`Input` 的 revision 协议（D6 已就绪）。

## 依赖

仅 W1 合并（无代码依赖，逻辑上独立成波以保持文件级不相交）。
