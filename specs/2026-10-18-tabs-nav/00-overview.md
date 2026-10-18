# Spec tabs-nav · 总纲（Tabs 按内容切换重构，导航栏拆出 NavList）

> 操作启动日 **2026-10-18**（组内 slug `tabs-nav`）。
> 基线：`main` @ `1e822b9`。**门禁基线（lead 已实测）**：`uv run pytest -q` =
> **1483 passed / 1 skipped**；`tools/golden.py --check` = 11 页全等；
> `tools/framebench.py` render-hash = `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`；
> demo 两入口 exit 0。版本**不 bump**。

把 `widgets/tabs.py` 的"一个类两个语义"拆开，各按主流规范重做：**`Tabs`**（横向，
内容视图切换——Material 3 / Textual 的指示器语汇）、**`NavList`**（纵向，应用导航——
VS Code / WinUI / GNOME 的左缘指示条语汇）。**不做兼容**：
`Tabs(orientation="vertical")` 随本组删除，`active_style` 默认从 `selection`（反白）
改为内容条语汇；demo 的 rail 迁 `NavList`。

## 规范依据（lead 调研，worker 不必重查）

- **横向条**：Material 3 primary tabs = **底部/文字级指示器 + accent 文字，不填背景**；
  Textual = 未激活灰、激活全色、`underline--bar`；FTXUI = 下划线选择器；
  ratatui `Tabs.highlight_style` 默认 REVERSED（TUI 老派，本组不采用）。
- **纵向导航**：VS Code 活动栏 = 左缘 2px 边框 + 透明度档；WinUI NavigationView =
  **左缘指示条 + 背景 wash**（"bar 是指示器，wash 是支撑"）；GNOME = 内缩圆角填充；
  Textual = focus 时提亮指示器。**持久态用反白是明确的反模式**（与光标/选择视觉冲突）。
- **无色彩可读性**：语义由**指示器字形 + 字重/色阶差**承载，颜色只做强化；
  失焦不是"拿掉指示器"，而是把指示器从 accent **降到 muted**。
- **反模式清单**（测试要挡住的）：反白持久激活、双/三重指示器、颜色唯一区分、
  hover 与 active 同款、分隔符用 accent 色、纵向用下划线指示。

## 决策登记（拍板）

- **D1 拆两个组件**：`Tabs`（横向，内容视图切换）与 `NavList`（纵向，导航）。
  旧 `orientation` 参数删除，无 alias。
- **D2 指示器位置与形态**：横向 = **激活标签自身加 underline**（单行内，不加行）；
  纵向 = **左缘 1 列 bar 字形**（`▌`），所有行形状一致。
- **D3 失焦档**：两个组件的指示器都随"条未聚焦"从 accent 降为 muted（`Tabs.focused=False`
  或 `NavList.focused=False`；默认 `True`）。**不 dim 激活文字**（旧行为作废）。
- **D4 状态与样式默认**（显式 > theme > DEFAULT_THEME）：
  - 横向：激活 = `accent` 前景 + underline；非激活 = `dim` 前景；分隔符 = 独立样式（默认 `muted`）；
    hover = `hover` 带（不改选中）。
  - 纵向：激活 = `accent` 前景 + bar/accent；非激活 = `dim` 前景 + bar/muted；
    hover = `hover` 带；disabled = `dim` 前景（bar 保持 muted）。
- **D5 字重克制**：默认不进 bold（仓库既有约定"bold 留给 `**…**`"）；宿主可显式给。
- **D6 不做**：分组标题行、图标、关闭按钮、roving cursor（激活即光标）、wash（`NavList`
  的整列底色明确不做，留给宿主自绘——wash 列必须每行染色否则参差，是脆弱设计）。
- **D7 门面**：`NavList` 进根（33 → 34 名），widgets 门面 `__all__` 增一名；
  `Tabs` 名字与位置不变。
- **D8 demo**：rail 从 `Tabs(orientation="vertical")` 换成 `NavList`（W2）。

## 契约（拍板，执行时不得再改形状）

```python
# widgets/tabs.py —— 横向内容条
Tabs(
    tabs: list[str], *,
    active: int = 0,
    active_style: Style | None = None,     # 默认 theme.accent
    inactive_style: Style | None = None,   # 默认 theme.dim
    hover_style: Style | None = None,      # 默认 theme.hover
    disabled_style: Style | None = None,   # 默认 theme.dim
    divider: str = "│", divider_style: Style | None = None,   # 默认 theme.muted
    indicator_style: Style | None = None,  # 默认 theme.accent；失焦时 mute
    disabled: Iterable[int] = (),          # 不可选（click/select 拒绝）
    focused: bool = True,
    theme: Theme | None = None,
)
```

- `render(width) -> list[Line]`：**恰好一行**。形状 `" a │ b │ c "`（首尾各一空格、
  分隔 `" │ "`，分隔符样式独立）；激活标签的 Segment 在 `active_style` 之上 merge
  `indicator_style`（默认 `accent`＝同色，失焦 merge `theme.muted` 的**前景**——实现用
  `accent.merge(muted)` 会同时带 muted.fg，故失焦档取 `muted` 整体作为指示色，写进 docstring）。
- `move/select`：clamp、不环绕、不可选（disabled）的索引被**跳过**（step 越过它）；
  `select` 到一个 disabled 索引返回 `False` 且不改状态。
- `click(row, col)`/`hover_at(row, col)`：沿用"上次 render 的行表"命中；分隔符/边距/截断
  `…` 不算命中；disabled 行 click 返回 False、hover 仍标记（可见但不可选）。

```python
# widgets/navlist.py —— 纵向导航（新文件，新组件）
NavList(
    items: list[str], *,
    active: int = 0,
    disabled: Iterable[int] = (),
    bar: str = "▌",            # 指示条字形；"" 关闭（则只靠前景与字重）
    bar_space: str = " ",
    active_style: Style | None = None,     # 默认 theme.accent
    inactive_style: Style | None = None,   # 默认 theme.dim
    hover_style: Style | None = None,      # 默认 theme.hover
    disabled_style: Style | None = None,   # 默认 theme.dim
    bar_style: Style | None = None,        # 非激活条：默认 theme.muted
    bar_active_style: Style | None = None, # 激活条：默认 theme.accent；失焦 merge muted
    focused: bool = True,
    theme: Theme | None = None,
)
```

- `render(width)`：**一行一条目**，`bar + bar_space + label`，每行 `fit(width)`；
  空列表渲染 `[]`（不占行——它进 viewport，空即零行）。
- 激活行：label `active_style`、条 `bar_active_style`；其余：label `inactive_style`、
  条 `bar_style`；hover 行 label merge `hover_style`（条不变）；disabled 行 label
  `disabled_style`、条 `bar_style`，`click`/`select` 拒绝。
- `click(row, col)`：行即条目（列忽略，disabled 拒绝）；`hover_at` 同 `Tabs` 契约。
  **不提供 `handle`**（纵向 rail 的键路由是宿主的事，和现状一致）。

## 波次表（严格串行；两波）

| W | 交付 | 主要写入范围 | 前置 |
|---|---|---|---|
| W1 | 库重构：`Tabs` 重写、`NavList` 新件、门面、测试重写 | `widgets/{tabs,navlist,__init__}.py` `__init__.py` `tests/**` `docs/{COMPONENTS,API}.md` `demo/shell.py`（最小接线） | — |
| W2 | demo rail 换 `NavList` + golden 11 页重录 + demo 文案/hints 对位 | `demo/**` `tests/golden/**` `tests/test_demo_protocol.py` | W1 |

> W1 的 `demo/shell.py` 最小接线：`mount_rail` 改用 `NavList`（签名不变），
> 使每个 commit 门禁自洽；W2 才做 rail 的样式选型、文案与 golden 重录。

## 红线（两波适用）

1. **无色彩可读性**：指示器（underline / bar）+ 色阶差必须同时承载语义，
   测试里加一条"无样式差异时仍可区分"的字形断言。
2. **不新增冗余测试**：`test_widgets_basics.py` 的 Tabs 段落**重写**（不是追加）；
   `NavList` 的用例写在同文件（同族），覆盖与 `Tabs` 对称的行为集，不加填充用例。
3. golden 重录逐页解释、同 commit；framebench hash 变了逐条解释。
4. 写入范围外零 diff；`kernel/` 不动（`Style`/`Theme` 不新增字段——用现有
   `accent/dim/muted/hover` 组合，D4）；不 bump 版本。
5. agent 不 merge / 不 push / 不 checkout main；spec 归 lead。
