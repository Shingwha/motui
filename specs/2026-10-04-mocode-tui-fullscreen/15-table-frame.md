# Spec W15 · Table 完整盒框（波次 W15，小修单）
> ✅ 2026-10-05 已交付合并（wfs15-table-frame）；Table 补完整盒框（顶/表头分隔/底，亮线 #9aa4b0）；markdown 三处形状断言与两份文档经 lead 授权连带更新。

## 背景（用户 2026-10-04 第七轮反馈 + pi 参照图）

pi 的 markdown 表格是**完整盒框**：顶线 `┌─┬─┐`、表头分隔 `├─┼─┤`、左右竖线、底线 `└─┴─┘`。
现 `Table` 只有左右竖线 + 表头分隔，缺上下外框。lead 裁决：**补全**（对齐 pi、表格区域更完整）。

## 工单（一个 commit）

### T1 `components/table.py`：补上下外框
- 渲染形状：顶行 `┌` + `─`×(列宽+2) + `┬` … + `┐`；表头下 `├─┼─┤`（不变）；
  数据行不变；末行后补 `└` + `─` + `┴` … + `┘`。列宽账不变（外框字符计入行宽，
  总行宽仍 ≤ width——超宽时的比例收缩规则与 ellipsize 语义不变）。
- 线样式仍走 `TABLE_BORDER`（亮线 #9aa4b0）。
- `tests/test_components_table.py`：更新形状断言（顶/底线字符）；收缩/ellipsize/
  样式单元格/空 rows 等既有语义用例等价适配（只允许加外框字符，其余不变）。

### T2 门禁
- `uv run pytest` 全绿（贴尾部，N ≥ 707）；
- 冒烟：`Markdown` 渲染一个 GFM 表格 + 独立 `Table` 各一次，打印行文本
  （确认顶/底/表头分隔三线齐全，贴输出）。
- `git diff --stat main..HEAD` 仅 `src/mocode_tui/components/table.py` +
  `tests/test_components_table.py`。

## 禁触
其余一切文件；不 merge/push/checkout main；不改 spec；Markdown 的 TableRule 自动继承
（复用 Table 组件，无需改动），但 `components/markdown.py` 本单不碰。

## 最终报告格式
commit hash+message / 自测真实结论 / 偏差与取舍 / 未决问题。
