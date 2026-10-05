# Spec markdown-polish · 块间距 + 分割线限宽（波次 W2）

> 分支 `md-w2-rhythm`（从 W1 合并后的最新 main 创建）；前置：W1 已合并；
> 深读：`specs/2026-10-05-markdown-polish/00-overview.md`（决策 1/2/8 与不变量）、
> `src/mocode_tui/widgets/markdown.py:709-790`、`src/mocode_tui/widgets/chrome.py:53-112`。

## 目标

`Markdown` 相邻块之间渲染一个空行（对齐 pi 的分节呼吸感），`Divider` 支持最大宽度并以 80 列为
Markdown 默认上限。**最高约束：流式安全不回退；`gap=0` / `divider_max_width=None` 可完整恢复旧行为。**

## 工单（按序执行，每项一个 commit，每个 commit 独立过门禁）

### T1 块间距：`widgets/markdown.py`

- `Markdown.__init__` 新增关键字参数 `gap: int = 1`；负值按 0 处理（docstring 注明，库风格是降级不抛错）。
  `__slots__` 增加 `"_gap"`。
- `render`（771-790）：**已有输出且 gap > 0** 时，先 `out.append(Line())` 再 extend 新块——
  首块前、末块后不加；源文档空行仍然只是被跳过（连续空行不产生多个空行）。
- docstring 更新：类 docstring 722-723 "Blank input rows are dropped: blocks stack directly…" 改为
  空行分节 + `gap=0` 恢复堆叠；模块 docstring 如有"stack directly"表述一并同步。
- 松散列表不单独改代码：`ListRule` 序号 verbatim（不重编号），`1. a\n\n2. b` 在块间距生效后
  自然渲染为 `["1. a", "", "2. b"]`——用测试钉住这个行为。

### T2 分割线限宽：`widgets/chrome.py` + `widgets/markdown.py`

- `Divider`：新增 `max_width: int | None = None`（`__slots__`/`__init__`/docstring 同步）。
  `render` 里 `paint = width if max_width is None else max(0, min(width, max_width))`，
  纯 rule 分支与 label 分支都按 `paint` 计算（label 的 ellipsize 预算、`used`/`fill`），
  行仍 `fit(width)`；左对齐自然成立（行短于 width 是合法的，painter 会清行尾）。
  直接使用 `Divider` 的宿主（pi_demo 的 spinner 行等）默认 `None`，行为不变。
- `ThematicBreakRule`：新增 `max_width: int | None = None` 参数，`render` 传给 `Divider`；
  `with_theme` 保留 max_width；新增 `with_divider_width(width)` 返回绑定了宽度的副本
  （仿照 `with_highlighter` 的模式）。
- `Markdown`：新增关键字参数 `divider_max_width: int | None = 80`；`__init__` 末尾仿照
  `with_stops` 的 hasattr 链，对暴露 `with_divider_width` 的 rule 调用之；`None` = 通栏。

### 测试更新

- `tests/test_widgets_markdown.py:48` 的 pin 改为 `["one", "", "two"]`（本组批准的行为变更）；
  `test_custom_rules_join_the_registries` 的三块输出更新为 `["para one", "", "SHOUT", "", "para two"]`。
- 新增：`gap=0` 恢复 `["one", "two"]`；三块两空行；松散有序列表
  `Markdown("1. a\n\n2. b").render(80)` → `["1. a", "", "2. b"]`；
  流式测试 `test_streaming_every_prefix_is_safe_and_fits` 不得改动且必须仍绿（空行 width 0 天然安全）。
- 新增（`tests/test_widgets_markdown.py` 或 chrome 侧现有测试文件）：
  `Divider(max_width=10).render(40)` 行宽 = 10；带 label + max_width 时 label 分支同样受限；
  `Markdown("---").render(120)` 行宽 = 80；`Markdown("---", divider_max_width=None).render(120)` 行宽 = 120；
  `divider_max_width` 经 `with_theme` 链绑定后仍生效（自定义主题场景）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 全绿（用例数只增不减）。
2. 两个 piped demo exit 0；`pi_demo` dump 与 `ref/before-pi-demo.txt` 对比：
   差异**只允许**是新增的空行与 W1 已合并的表格变化；报告贴 diff 摘要行数。
3. `ref/before-toc-w100.txt` 对比：TOC 标题与列表之间出现一个空行。

## 禁触清单

`core/**`、`widgets/table.py`、`widgets/syntax.py`、`chat/**`、`examples/**`、`docs/**`、
`README.md`、`specs/**`、`pyproject.toml`、`src/mocode_tui/__init__.py` 及各 facade `__all__`。
（chat 层渲染会因空行自然变高，但不改 chat 代码。）越界即停、上报 lead。

## 最终报告格式

工单状态表 / commit 清单（hash + message）/ `uv run pytest -q` 真实输出结论 / demo exit code 与
dump diff 摘要 / 偏差与取舍 / 未决问题。阻塞即停，不越界自救。
