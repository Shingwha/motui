# Spec demo-presentation · W1 语法与骨架（波次 W1）

> 分支 `pres1-grammar`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md`
> （骨架、D1–D7）。
> **最高约束：本波是"机械改版"——去文字、`Section` 化、上分组；**组件展位集合与
> 交互行为一个不少、一个不改**（44 个组件对账表要出现在报告里）。

## 工单（按序执行，每项一个 commit）

### T1 `NavList.groups`（库层唯一改动）

- `widgets/navlist.py`：新增构造参数

  ```python
  NavList(items, *, groups: Sequence[tuple[int, str]] = (), group_style: Style | None = None, …)
  ```

  `(position, label)` 表示在 items 的第 `position` 个条目之前插入一条组标题行。
  语义（写进 docstring 并测试）：
  - 组行：`group_style`（默认 `theme.muted`）渲染 `label`，**不可点、不可选、
    hover 不标记**（`click`/`hover_at` 到组行返回 False/清空），
    字形默认按 `label.upper()` 原样（大小写由调用方决定，组件不改写——demo 自己给大写）；
  - `active`/`select`/`move` 只数**可选条目**（组行透明），`render` 的行数 = items + groups；
  - `hover_at`/`click` 的 row 是**渲染行**（含组行），内部映射到条目；
  - 组行的座位（bar 列）留空（`bar_space`）。
- 测试：`tests/test_widgets_navlist.py` 加 3–4 条（渲染形状/组行不可选与跳选/
  active 映射不受组行影响/hover 到组行清空）。
- facade 无变化（参数级改动）。

### T2 kit 新语法（`Section`）

- `demo/kit.py`：`Exhibit` 重写为总纲骨架：

  ```python
  @dataclass
  class Section:
      """One demo group: a spec, its blocks, an optional caption, its focus targets."""
      spec: str                      # "input -- an empty one and a filled one"
      blocks: list[Component]
      caption: str = ""              # 至多一行；紧随组件行之后、dim
      focus: list[Component] = field(default_factory=list)
      width: int | None = None       # 组内组件渲染宽度（默认页面宽度）
      draft: bool = False            # caption 待 W2 精修的草稿：见下
  ```

  `Exhibit(theme, title, blurb)`、`exhibit.section("input", Input(...), caption="…",
  focus=…, api=…)` 式的**流式 API 保留**（`show()` 更名 `section()` 或别名皆可，
  worker 定，报告说明）；`build()` 产出：
  页规则（`Divider(label=title)` + 一句 blurb 的 dim 行）→ 每组 ` ── spec ──`
  → 组件 → caption 行。**删 `api` 参数与自由段落通道**；`Exhibit.text()` 只保留
  `theme.dim` 行（给确实需要的单行说明）。
- `demo/page.py`：删 `header`/`try_line`/`section`/`api_note` 四个旧 helper；
  `Page`/`PageBody` 保留。
- **机械改版的 caption 规则**：旧 `api_note` 的内容**一律不搬到 caption**——
  签名统一由 W2 收编进 notes 页的"签名速查"（W1 在报告里列出所有被删的 `API ·` 行，
  作为 W2 的收编清单）；caption 从旧 section 标题/组件事实里取至多一行
  （如 `20 rows · 6 visible`），没有事实可取的 section caption 留空。

### T3 11 页机械改版 + rail 分组 + overview 索引

- 11 个页面文件改到新 `Exhibit` API：删 TRY 段、删 `API ·` 行、删自由段落
  （`exhibit.text(...)` 只在语义必要处留至多一行）；`registry.py` 的 `Page`
  增加分组数据（或 rail 侧定义 groups，worker 定，报告说明）。
- `demo/shell.py` 的 `mount_rail`：传 `groups=((0,"FOUNDATIONS"),(3,"COMPONENTS"),
  (7,"SHELL"))`（标签大写），样式沿用；`Session._follow_rail` 等不动。
- `pages/overview.py`：索引改 `Table(["page","group","what"], rows=…)`，`chosen`
  是行号（int）→ 页面的 note 里 `session.show(session.pages[row])`；caption 一行
  说明"点一行打开该页"。
- `tests/test_demo_protocol.py`：只做**最小跟随**（rail 组行计入渲染行会让锚点/索引
  位移；overview 索引从 Select 改 Table）。逐条列出改了什么。
- golden `--update`：11 页重录，commit message 逐页解释。

## 验收

1. `uv run pytest -q` 全绿（贴 passed/skipped）
2. `uv run python tools/golden.py --check` → 11 页全等（重录后）
3. `uv run python tools/framebench.py` → hash 登记/解释
4. demo 两入口 exit 0；脚本化交互含 rail 点击、`c-n` 循环、overview 表格点行
5. **对账表**：报告里列出 44 个组件 → 所在页/section 的映射（grep 结果），
   一个不少；`grep -rn "API ·\|TRY ▸" src/motui/demo` → 零命中

## 禁触清单

`src/motui/kernel/**`、`src/motui/{widgets/*（除 navlist.py）,interaction/**,app.py,testing.py,keys/**}`、
`demo/script.py`（锚机制不动，若页内行位移导致锚失效，允许最小修并报告）、`README.md`、
`docs/**`、`tools/**` 除 golden `--update`、`pyproject.toml`、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 对账表 / 偏差与取舍 / 未决问题。
