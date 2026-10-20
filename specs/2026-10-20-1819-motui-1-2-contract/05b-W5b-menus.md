# W5b · 菜单层（MenuBar / ContextMenu）
> 分支 `w5b-menus`；前置：W6 已合并 @ `33ad1a3` / cleanup `fc57f9e`；写入范围见下。
> 深读：`00-overview.md` D9、`ref/interfaces.md` §3、`docs/CONTRACT.md` §5。

## 目标

补齐“完整 TUI 库”最后缺的菜单层：一个纯横向 `MenuBar`（一项被选中时把 label 交给
`take_result()`），和一个 `ContextMenu`（`Select` 的预设，host 用 `Modal` 挂到点击位置）。
**不改 demo 页面**；demo exhibits 与 golden 在 W7 统一加/重录。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §3/§4 → `handoff/W6-interaction.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
  期望：1926 passed / 2 skipped；11 页 match；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
- 稳定区（勿重读）：W1–W6 的 kernel/driver/events/keys/interaction/widgets。
- W6 约束：`Resultful.take_result()` 是唯一结果门；`FocusManager` 负责焦点；`Frame.add_overlay(layer=...)`；
  demo 文案旧名保留（W7）。

## 工单（按序执行；HEAD 全绿即可）

### T1 `widgets/menubar.py`（新）：`MenuBar` + `ContextMenu`

- `MenuBar`：一行横向菜单条。
  ```python
  class MenuBar(Themed):
      def __init__(self, items: Sequence[str], *, index: int = 0,
                   active_style: Style | None = None, inactive_style: Style | None = None,
                   hover_style: Style | None = None, disabled_style: Style | None = None,
                   divider: str = " │ ", divider_style: Style | None = None,
                   disabled_items: Iterable[int] = (), disabled: bool = False,
                   focused: bool = True, theme: Theme | None = None)
      @property index -> int
      def select(self, index: int) -> bool
      def move(self, delta: int) -> bool
      def click(self, row: int, col: int) -> bool
      def hover_at(self, row: int, col: int) -> bool
      def activate(self) -> bool
      def take_result(self) -> str | None
      def render(self, width: int) -> list[Line]
      def revision(self) -> object
  ```
  - 只渲染一行：leading space + labels + separators + trailing space；active label 用 `active_style`
    （不画 underline）；hover label 叠加 `hover_style`；disabled 用 `disabled_style`；整体 `fit(width)`。
  - `move` clamp（不 wrap；菜单条是数据条，不是 Select 的循环菜单）；`select` 拒绝 disabled；
    `click` 用上次 render 的 span 表映射列；`hover_at` 标记 label；`row != 0` 一律 miss。
  - `activate` 把当前 label 写 pending；`take_result` 读一次清空；disabled/空 items 返回 False/None。
  - `revision` 覆盖 items/index/disabled/disabled_items/样式/theme/hover_index/focused。
  - 测试：render 一行、index/move/select、click 命中、disabled 跳过/拒绝、hover、activate/take_result、revision。

- `ContextMenu`：`Select` 的预设，供 host 用 `Modal` 挂到点击位置。
  ```python
  class ContextMenu(Select):
      def __init__(self, options=(), *, title="", max_rows=8,
                   marker=glyphs.MENU_CURSOR, **kwargs)
  ```
  - 默认 `commit=False`、`wrap=True`、`window=False`；`activate()` 返回 pending `Option`，`take_result()` 继承。
  - docstring 写清“host 用 `Modal(tui, menu, anchor=(y, x))` 挂载；菜单本身不打开/不定位”。
  - 测试：activate/take_result、title、disabled、Modal 挂载的 smoke（用 HeadlessTUI）。

### T2 facade、测试、文档

- `widgets/__init__.py` 导出 `MenuBar`、`ContextMenu`；`tests/test_api_root.py` 同步。
- 新增 `tests/test_widgets_menubar.py`（覆盖 T1 两个类）。
- `docs/COMPONENTS.md` 加 MenuBar/ContextMenu 两节（简短）；README 组件列表补充。
- **不改 demo 页面**；golden 必须不变（exhibits 在 W7）。
- 跑验收，写 `handoff/W5b-menus.md`。不 merge/push/tag。

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；总数 ≥ 1926 + 新增
2. `uv run python tools/golden.py --check`：11 页全 match
3. `uv run python tools/framebench.py`：exit 0；render-hash 不变（贴值）
4. `uv run python -m motui < /dev/null`、`--pages`：exit 0
5. `uv run python -c "from motui.widgets import MenuBar, ContextMenu"`：exit 0
6. `git diff --stat main...HEAD`：范围 = 本工单写范围并集，无 golden 变化

## 禁触清单

- 禁改：`widgets/{action,choice,list,table,tree,tabs,navlist,textfield,dialog,collapsible,indicators,decor,rows,layout,delegate,scroll,form}.py`、
  `widgets/markdown/**`、`kernel/**`、`app.py`、`keys/**`、`interaction/**`、`tests/golden/**`、
  `pyproject.toml`、`uv.lock`、`docs/CONTRACT.md`、demo 页面。
- 禁加：兼容 alias、旧名 re-export；不改根 34 名。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。
- 遇到阻塞：写清阻塞点后停止，不越界自救。

## 交接包

完成后写 `specs/2026-10-20-1819-motui-1-2-contract/handoff/W5b-menus.md`（60–80 行，A/B/C）。

## 最终报告

工单状态表 / commit 清单 / 自测真实输出 / 新公开 API / 测试改动清单 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题。
