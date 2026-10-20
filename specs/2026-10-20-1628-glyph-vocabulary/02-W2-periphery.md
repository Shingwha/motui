# W2 · 外围字形与文档
> 分支 `refactor/120-periphery`；前置 W1 合并；写入范围 `src/motui/interaction/scrollbar.py`、
> `src/motui/widgets/markdown/`、`docs/`、`CHANGELOG.md`、`README.md`、
> `specs/2026-10-20-1628-glyph-vocabulary/handoff/W2-periphery.md`

## 目标

把最后两处硬编码字形参数化（Scrollbar 的 track/thumb、Markdown 的任务框），并把整个词汇写进
设计文档与宿主契约。

## 范围

1. `Scrollbar(track=TRACK, thumb=THUMB)`：控制器的构造参数；strip 的缓存键/记忆纳入字形。
2. `Markdown(task_marks=(TASK_OPEN, TASK_DONE))`：穿 `RenderContext`，内置 task 规则读它；
   任务框的 action span 仍覆盖"字形 + 空格"整段。
3. `docs/DESIGN.md`：命名宪章加"Glyphs"一行（词汇模块 + 座位规则 + 空串语义）。
4. `docs/COMPONENTS.md`：组件参数总表加入每个字形参数、默认值、关闭规则与对齐规则。
5. `CHANGELOG.md`：1.1.9 的 Added/Changed 记录本词汇（旧模块常量删除、无别名）。
6. `README.md`：若枚举了组件参数则同步。

## 验收（草案，派工时以 W1 的现实为准）

1. 全量门禁全绿；golden 零 diff；render-hash 不变。
2. 字形默认值不变；`Scrollbar(track=…, thumb=…)` 与 `Markdown(task_marks=…)` 的用例各一。
3. 文档声明抽查逐条对得上代码（附行号）。

## 依赖

`kernel/glyphs.py` 的常量与 helper（W1）；`handoff/W1-glyphs.md` 的偏差/坑。

## 前置上下文

（W1 合并后由 lead 补全：必读顺序、W1 交付摘要、接口变更、基线命令、稳定区、已知坑。）
