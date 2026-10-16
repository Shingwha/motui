# Spec tui-depth · W8 组件进阶 B（波次 W8）
> 分支 `td8-widgets-b`；前置：W7；深读：`00-overview.md`（D17 的后半）。
> **最高约束：Table/Tree/Markdown 的既有行为与键位只做加法（每处 `chosen`/光标语义写明改前→改后）；
> 三者的既有字节 pin 与 golden 页在语义变化处随波重录并说明。**

## 目标

1. `Table`：`sort_by(col)`、`set_widths()`、`header_line(width)`（sticky header 的 recipe 形态）。
2. `Tree`：`filter(query)`、前缀跳转（type-ahead）。
3. `Markdown`：任务列表可点（`[ ]/[x]` → action span）、`fences()` 访问器 + gallery `c-y` 复制。
4. gallery 与文档同步（14 页不变）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| `Table` 的渲染/光标/selected_style 与 hover_at 现状 | `widgets/table.py` |
| `Tree` 的可见行/光标/展开状态 | `widgets/tree.py` |
| Markdown 的 rule 层与 `Line` 产出；行构建分散点 | `widgets/markdown/{inline,blocks,nested,tables}.py` |
| 行内 action span（W2 的成果）与 `action_at` | `core/lines.py`；`widgets/markdown/component.py` |
| `screen.copy`（OSC 52）与 gallery 的 `c-y` 可用性 | `core/screen.py`；`examples/gallery/session.py:97` |
| golden 页与 pin 面 | `tests/golden/pages/`；`tests/test_widgets_{table,markdown}.py` |

## 工单（按序执行，每项一个 commit）

### T1 `widgets/table.py`：排序 / 列宽 / 表头行

- `sort_by(col: int, *, reverse=False)`：按该列**渲染文本**排序（稳定排序；`chosen` 与光标索引跟随
  行身份而不是行号——写明实现策略）；表头行点击（若已有表头）或宿主显式调用触发。
- `set_widths(widths: list[int] | None)`：显式列宽（None 回宽度自适应）；列宽和 ≤ `width` 的约束由
  渲染 clamp。
- `header_line(width) -> Line | None`：把表头单独产出一行，供宿主放进 band/pinned 行（**不**做
  视口魔法；docstring 给 recipe）。
- 更新 `widgets/table.py` 的 docstring 与 `docs/COMPONENTS.md` 条目；测试：排序稳定性、列宽 clamp、
  header_line 与整表首行的字节一致。

### T2 `widgets/tree.py`：过滤与前缀跳转

- `filter(query: str | None)`：按节点 label 大小写不敏感子串剪枝（保留命中节点的祖先链；
  `None` 清除）；展开状态对命中链自动展开、清除过滤后恢复用户原展开集（用两个集合记）。
- 前缀跳转：可打印字符 → 光标跳到下一个 label 以该字符开头的可见节点（大小写不敏感，回绕）。
- 测试：剪枝结构、展开集恢复、跳转与回绕、与既有 expand/collapse 的互不干扰。

### T3 `widgets/markdown/`：任务列表 + `fences()`

- 任务列表：列表项 `- [ ]` / `- [x]` → 前缀标记（`☐/☑` 或 `[ ]/[x]`，择一写明）作为 action span
  （`action = "todo:<flat index>"`）；点击 → `Markdown.chosen == "todo:<i>"`（读一次），宿主持有
  `text` 并自己改写（文档写明循环：host 读 chosen → 替换文本 → 重设 `md.text`）。
- `Markdown.fences() -> list[tuple[str, str]]`：返回 `(lang, code)` 的围栏清单（从当前 `text` 解析，
  不依赖渲染缓存）；gallery 在 `/content`（或 `/streaming`）绑定 `c-y`：复制当前页第一个围栏
  （`screen.copy`），toast 回声。
- 测试：任务列表的 action span 与 chosen；`fences()` 的多围栏/无语言/嵌套缩进例；`c-y` 的 copy 调用
  （`HeadlessScreen.copy` 记录）。

### T4 gallery + 文档 + golden

- `/data` 页演示排序（表头点击或按钮）；`/navigation` 页演示 Tree 过滤（一个小 `Input` 或宿主键）；
  `/content` 页演示任务列表点击回声与 `c-y`；回放脚本覆盖三处。
- `tools/golden.py --update`（表头/任务列表等语义变化处，写明）。
- `docs/COMPONENTS.md` 三条目 + 交互表（Task list span、filter、sort_by 行）；`README.md` 组件表；
  `docs/DESIGN.md` 命名表（`sort_by`/`filter`/`fences`）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 只增不减；贴被更新的既有 pin（table/markdown 的字节或段断言）与说明。
2. 探针：排序前后表格首三行；filter 的可见节点集合；任务列表点击 → `chosen` → 文本改写 → 再渲染；
   `fences()` 清单；`c-y` 的 copy 内容。
3. `demo.py < /dev/null` exit 0；`--pages` 14 页头；`golden --check` 全过（重录说明）。
4. framebench hash 如实（Markdown 任务列表/表头若进 fixture 才可能变；预期不变，变了写原因）。
5. import 干净；README 块全绿。

## 禁触清单

- `Search`/`Find`、`Diff`/`List`、`Radio`/`Slider`（本组前几波成果）
- `Markdown` 的 `(text,width)` 缓存键；`Table`/`Tree` 的 `chosen` 既有语义（只加不改）
- `specs/**`；gallery 页数（14 不变）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论 / 排序与过滤探针 / 任务列表循环探针 / fences 与 c-y /
golden 重录说明 / framebench hash / 偏差与取舍 / 未决问题 / 真机手测：未执行。
