# Spec tabs-nav · W1 库重构（波次 W1）

> 分支 `tabs1-lib`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md`
> （规范依据、D1–D8、契约）。
> **最高约束：`Tabs` 的横向几何（恰好一行、`" a │ b │ c "` 形状、clamp 不环绕、
> 上次 render 行表命中）全部保留；被删的只有纵向模式与反白默认。**

## 目标

1. `widgets/tabs.py` 重写：横向内容条，按总纲契约加指示器与样式旋钮，删 `orientation`。
2. `widgets/navlist.py` 新文件：`NavList` 纵向导航，按契约实现。
3. 门面：`NavList` 进 `motui.widgets` 与根（33 → 34），`tests/test_api_root.py` 重钉。
4. 测试重写：`test_widgets_basics.py` 的 Tabs 段按新行为重写；新建
   `tests/test_widgets_navlist.py`（同族对称用例集）；`test_render_invariants.py` 的
   fixture 表加 `NavList`；`test_widgets_action.py`/`test_focus.py` 里用到 `Tabs` 的
   断言按新默认样式跟改（只改样式期望，不改被测行为）。
5. `demo/shell.py` 的 `mount_rail` 最小接线到 `NavList`（签名不变；样式选型与文案是 W2 的事）。
6. `docs/COMPONENTS.md`：组件目录表 `Tabs` 行重写、新增 `NavList` 行；
   `docs/DESIGN.md` 的门面表/名字计数若提到 33 名 → 34；`widgets/rows.py`、
   `widgets/indicators.py` 里"Tabs 先例"的注释如果语义变了就改词。

## 契约要点（详见总纲）

- `Tabs`：新参数 `hover_style/disabled_style/divider_style/indicator_style/disabled`；
  默认 激活=`accent`+underline、非激活=`dim`、分隔符=`muted`；失焦时**指示色降 muted、
  文字不 dim**；`disabled` 行 click/select 拒绝、hover 仍标记；`move` 跳过 disabled。
  失焦指示色的实现：`active_style.merge(indicator_style)` 在失焦时改为
  `active_style.merge(theme.muted)`（muted 有 fg，不能只 merge 到 accent 上再想"只降权重"，
  docstring 写清这个取色规则）。
- `NavList`：`bar`/`bar_space`/五组样式/`disabled`；每行 `bar + bar_space + label`；
  空列表渲染零行；无 `handle`；命中与 clamp 语义与 `Tabs` 对称。
- 两个组件都**不新增 Theme 字段**（用现有 `accent/dim/muted/hover/selection`）。

## 验收

1. `uv run pytest -q` 全绿（贴 passed/skipped；列出 Tabs/NavList 用例数）
2. `uv run python tools/golden.py --check` → 11 页；rail 换 NavList 后的新形态**重录并逐页解释**
   （本波 rail 只求"正确接线"，W2 才定稿样式——重录允许，解释清楚）
3. `uv run python tools/framebench.py` → 若 hash 变（Tabs 在轨上）逐条解释
4. demo 两入口 exit 0；rail 点击翻页仍工作（`test_demo_protocol.py` 里 rail 相关断言不许红，
   如需最小跟改，报告里列出）
5. `grep -rn "orientation" src/motui/widgets/tabs.py tests/test_widgets_basics.py` → 零命中；
   `grep -rn "Tabs(.*vertical\|orientation=\"vertical\"" src tests` → 零命中

## 禁触清单

`src/motui/kernel/**`、`src/motui/{app.py,testing.py,keys/**}`、`src/motui/interaction/**`、
`src/motui/demo/**`（除 `shell.py` 的 `mount_rail` 一个函数）、`README.md`、
`tools/**`、`pyproject.toml`、`specs/**`。`docs/` 只许 `COMPONENTS.md` 两表与 `DESIGN.md`
的计数/门面行。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论（逐条命令与输出）/ 偏差与取舍 / 未决问题。
