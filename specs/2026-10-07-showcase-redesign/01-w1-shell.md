# Spec showcase-redesign · W1 壳与展品语法（波次 W1）
> 分支 `sr1-shell`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md`（设计定稿 A/B 节、决策 D1/D2/D7）、
> `ref/showcase-audit.md`（壳的现状、`--pages` 的 dump-safe 事实、键位空位）。
> **最高约束：先把"展示系统"立起来，再谈每一页。** 本波只做壳、语法、导航、overview 与 text 页样板；
> 其余页原样可用（可换名字/描述），不许顺手重排。

## 目标

1. **导航可见**：顶部一条可点的 `Tabs` 导航（点 tab 名直接切页）+ `c-n`/`c-p` 前后展品；
   `/` 面板照旧。换页后导航条 active 同步。
2. **语法统一**：`page.py` 提供 `try_line()` 与 `api_note()`，`header()`/`section()` 保留；
   `text` 页与 `overview` 页先用起来，作为后面几波的样板。
3. **overview 变活索引**：静态页表换成可点/可 `enter` 的 `Select`（activate → 打开该展品）。
4. **状态行可见状态**：footer 左侧显示 `<展品名> · focus=<聚焦对象或 ->`。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| banner 三条 pinned 块 + `_banner_labels()` | `examples/showcase/session.py:129-158` |
| 页切换只有 palette → `Command` → `show(page)` | `session.py:109-127`、`registry.py:79-89` |
| 事件路由顺序（含 `playing` 规则与 `tab`/`c-o` 分支） | `session.py:207-253` |
| `_page_click` 只喂 `body.focus`（pinned 块不在路上） | `session.py:262-289` |
| `PageBody(hint, focus, tick)` | `page.py:32-49` |
| 未占用键位：`c-n` / `c-p` | `ref/showcase-audit.md` 第 4 节 |
| `--pages` 不跑循环也不跑 tick | `examples/demo.py:61-69` |

## 工单（按序执行，每项一个 commit）

### T1 `page.py`：展品语法助手

- 新增 `try_line(text: str, theme: Theme) -> Component`（accent 样式，前缀 `TRY ▸ `，
  一行可折行）与 `api_note(text: str, theme: Theme) -> Component`（dim，前缀 `API · `）。
  实现用现有的 `Text`；样式解析走 `Theme` 字段（不新增 theme 字段）。
- docstring 写清它们是"展品语法"的三件套之二（另一个是 `header`），并给出用法示例。
- 验证：`text` 页的渲染里出现 `TRY ▸` 与 `API ·` 前缀（单测不做，靠 dump 与真机；见验收）。

### T2 `session.py`：导航条、前后键、状态行

- **导航条**：一个 `Tabs([page.nav for page in PAGES], active=<当前页下标>)`，pin 在 top，
  紧跟标题行、在提示行之前。换页（`show`）与换主题（`cmd_theme` → `show`）后 `active` 必须同步。
  **标签用 `Page.nav`（短标签，见 T3）而不是全名**：12 个全名约 117 列 > 110，会被 `fit` 截断，
  且截断的 label 不可点（interaction-model W2 的既定行为）。短标签组合必须 **≤ 110 列单行**，
  实测宽度写进报告（这是硬约束，不是口味）。
- **点击路由**：`_page_click` 之前先给导航块一个机会——`hit_test` 命中导航块时
  `tabs.click(hit.row, hit.col)`，命中（`True`）就 `self.show(PAGES[tabs.active])` 并 return；
  未命中（分隔符/空白）什么都不做。**不许**把导航塞进任何页面的 ring。
- **前后键**：事件链里新增 `c-n`（下一个展品，末尾回绕）/ `c-p`（上一个，回绕）分支，
  位置在 `tab`/`c-o` 一档（ring 与 editor 都不要这些键，天然落到宿主）。
  翻页一律走 `show()`（并同步导航条）。
- **状态行**：`_mount_footer()`/`_banner_labels()` 同步刷新左侧文案：
  `<展品名> · focus=<聚焦目标的类名小写，无环或无焦点时 ->`；右侧 fps 不动。
- 提示行（banner 第二行）文案更新为英文（演示文案一律英文，spec 才用中文）：
  `click a tab · c-n / c-p exhibits · ↑↓/enter: <hint> · tab focus · c-o pane · enter sends · c-j newline · c-c quits`
  （**必须在 110 列内单行**；超宽先截断自己的文案，不许折行——折行会动 dump 行数契约）。

### T3 `page.py` + `registry.py`：短标签与页表更名

- `page.py`：`Page` 增字段 `nav: str`（导航条上的短标签；`name` 仍是 `/` 面板与 `--pages` 的权威名）。
  docstring 写明两者分工与"短标签必须能在 110 列内与其余标签单行共处"的约束。
- `registry.py`：`data` → **`text`**、`markdown` → **`streaming`**（D7）；每个 `Page` 给出 `nav`
  短标签（建议 ≤6 字符，如 `over text struct menus fields feed styles keys shell interact stream chat`，
  实际取值由 agent 定并用实测宽度证明）；描述改成"展品口吻"的一句话
  （`streaming` 暂时仍是静态 fixture，描述写 "a long Markdown document -- every construct"；
  W5 才把它变成流式，届时再改描述）。
- `PAGES` 顺序 = 总纲 E 表的顺序（缺 `interaction`、`keys` 拆分两页，是 W3/W4 的活）。
- 导航条上任何标签**不得被 `fit` 截断**（截断即不可点）：以 `tabs.render(110)[0]` 的文本不含 `…` 为准。

### T4 `components.py`：`text` 页样板 + `overview` 活索引

- `components.data` → 改名 `components.text`，按语法重做：
  `header("text & data", …)` → `try_line("点表格任意一行；↑↓ 移动；enter 激活")` →
  Table（保留 W6 的行光标与 ring）→ `api_note("table.index / table.chosen（读一次清一次）")` →
  `section` → Markdown 短样 + `api_note("Markdown(text)")` → Text / Divider 两段各带一行 `api_note`。
  **不改组件本身、不改 ring 组成**（`FocusRing([table])`）。
- `overview`：`Select`（每行一个展品：label=`/<name>`，description=页描述）替代静态 Table；
  `enter`/点击激活 → 宿主读 `chosen` → `show(BY_NAME[chosen.value])`；
  另加一句 `try_line("点一行，或按 enter 打开当前行")` 与 `api_note("Select.activate() -> chosen")`。
  页脚保留现有那句"no model, no network"。
- 验证：headless 回放里点/激活 overview 的一行 → 当前页变成该展品（脚本覆盖，见 T5）。

### T5 `script.py` + `README.md` + `demo.py` docstring

- `script()`：追加可复现的导航动作——`c-n` 两次、`c-p` 一次、以及在 overview 上
  `Key("down")` + `Key("enter")` 打开一个展品；保持既有回放（页面遍历、点击、拖动、粘贴、提问）不动。
- `README.md` 的 `## The demo` 段按新事实重写：三条路（点导航条 / `c-n`/`c-p` / `/` 面板）、
  新页名（`text`、`streaming`）、`--pages`/piped 照旧；其余段（Quickstart 等）**一个字不动**。
- `examples/demo.py` 的模块 docstring 同步键位与页名。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → **必须一字不变** `948 passed, 1 skipped`。
2. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；dump 里能看到
   `text` 页的 `TRY ▸` 与 `API ·` 两行原文（贴出来）。
3. `uv run python examples/demo.py --pages` → exit 0；页头 = **10** 个（`/overview /text /structure /lists /fields /feedback /styles /features /streaming /chat`），
   贴 `grep -c '^── /'` 与页头清单；行数写进报告（**允许多于改前的 720**）。
4. 导航 headless 证据：`script()` 跑完后 dump 的 banner 里导航条 active 与最终页一致；
   并且单独探针证明 `c-n`/`c-p` 改页、点导航块改页（探针代码与输出贴报告）。
   另贴 `tabs.render(110)` 的整行文本与 `visible_width`（**不含 `…`、≤110**）。
5. `uv run python tools/framebench.py` → hash 与基线**逐字符一致**。
6. `uv run pytest tests/test_readme_examples.py -q` → `6 passed`；`git diff --stat <base>..HEAD -- src/` → **空**。
7. 真机项（点导航条、`c-n`/`c-p`、状态行读数）**无法执行** → 报告写"lead 终验项"，用 4 的探针替代。

## 禁触清单

- `src/`（任何文件；要动先上报）
- `examples/showcase/{styles,features,chat}.py`（W3 的活）、
  `examples/showcase/{components}.py` 的 `structure/lists/fields/feedback/markdown` 五个页面函数
  （W2/W5 的活；本波只改 `data`→`text` 与 `_overview` 的落点）
- `specs/`（spec 归 lead——不更新任何 spec 状态；完成信号 = 最终报告 + 分支 commit）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单（hash + message）/ 自测真实结论（逐条命令 + 关键输出行 + 行数与页头数）/
导航条实测宽度与 110 列单行证据 / 偏差与取舍 / 未决问题 / 真机手测：未执行（lead 终验）。

遇到阻塞（导航放不下、`--pages` 出现空页、pytest 数变化、src 必须改）：**停下上报，不越界自救**。
