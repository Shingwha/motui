# Spec tabs-nav · W2 demo 接线与定稿（波次 W2）

> 分支 `tabs2-demo`；前置：W1（库与最小接线已合并）；深读：`00-overview.md`（D4/D8）、
> `demo/shell.py`、`demo/registry.py`、`tests/golden/pages/*.txt`。
> **最高约束：本波只动 demo 层与它的门禁——库（`widgets/`、`kernel/`）一行不改；
> 若发现库需要补，停下来报告。**

## 目标

rail 从"最小接线"升为**定稿**：样式选型、间距/指示条与页面语义的对位、`--pages`
观感检查；golden 11 页定稿重录；demo 文案与相关断言跟改。

## 工单

### T1 rail 定稿

- `demo/shell.py` 的 `mount_rail`：按总纲 D4 给 `NavList` 明确选型（例如
  `active_style=` 用主题 accent、`bar="▌"`、`focused=True`），并确认：
  - rail 条宽（`RAIL_RATIOS=(1,4)` 下 22 列）与 `bar + space + label` 的 gutter 对齐；
  - 点击任一 label 仍翻页（`Session._follow_rail` 的路径不变）；
  - 主题切换（`set_theme`）重建 rail 后样式跟随新主题。
- 页名/提示文案里若有提到"左侧 tab"之类措辞，改为"rail"（`registry.py` 注释、
  `pages/notes.py` 的说明文字、`shell.py` 的 docstring）。

### T2 golden 定稿 + 断言对位

- `tools/golden.py --update`：11 页重录，commit message **逐页**说明（相对 W1 的差异：
  颜色/字形层面 golden 是纯文本，应只剩间距/字形可见的变化；若纯文本无差异要如实说明）。
- `tests/test_demo_protocol.py`：rail 点击/翻页相关断言按 `NavList` 的命中语义最小跟改
  （列忽略 → 行即条目；若有断言改措辞，报告里列出）。
- `tools/framebench.py`：hash 变化逐条解释（rail 在轨则可能变化）。

### T3 文档收口

- `docs/COMPONENTS.md`：`NavList` 行与 `Tabs` 行核对一遍（W1 已写则校对）；
  「dispatch order」等段落里若提到 rail/tab 的措辞同步。
- `CHANGELOG.md` 的 `## Unreleased` → Changed 加一条：
  `Tabs` 重做为内容切换条（指示器语汇）、新增 `NavList`、demo rail 迁移。

## 验收

1. `uv run pytest -q` 全绿
2. `uv run python tools/golden.py --check` → 11 页全等（重录后）
3. `uv run python tools/framebench.py` → hash 登记/解释
4. demo 两入口 exit 0；脚本化交互至少含「点 rail 翻页 + `c-n` 循环 + `c-o`」走通
5. `grep -rn "Tabs" src/motui/demo` → 只剩确属 Tabs 语义的引用（rail 相关措辞已改）

## 禁触清单

`src/motui/kernel/**`、`src/motui/widgets/**`、`src/motui/interaction/**`、
`src/motui/{app.py,testing.py}`、`README.md`、`tools/**` 除 golden `--update`、
`pyproject.toml`、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
