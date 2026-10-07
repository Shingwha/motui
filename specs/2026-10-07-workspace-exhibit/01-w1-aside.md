# Spec workspace-exhibit · W1 aside 机制 + 工作台页面（波次 W1）
> 分支 `ws1-aside`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md`（版式、决策 D1–D9）、
> `ref/workspace-audit.md`（几何与 API 实测：窗格 73/37、标签条 31 列不截断、pin 与换装已跑通）。
> **最高约束：这一页的交互面只有右栏标签条；切换必须是确定性的（事件后 `sync`），不许靠 tick。**
> ✅ **2026-10-07 已合并** @ `ws1-aside`（`PageBody.aside/sync` + `/split` 让位 + 四视图；13 页、936 行）。

## 目标

1. `PageBody` 长出 `aside` 与 `sync` 两个钩子，`show()` 有了"页面自带右窗格"的开关顺序，
   `/split` 的预览与 aside 共用唯一右窗格槽位（`/split` 规则见 D6）。
2. 新页面 `workspace`：左栏 canned 对话（纯展示、独立滚动），右栏 = `pin="top"` 的四个标签 +
   当前视图内容块；点标签、`tab`+`←→` 两条路都能切，切完回顶。
3. 四个视图的静态内容（`tools` / `edits` / `reads` / `agent`；agent 的 live 化是 W2 的活，
   本波先放**完整静态**内容，保证 dump-safe 与会话确定性）。
4. 回放覆盖：`script()` 进入 `/workspace` → 点/切一个标签；README 与 registry 同步（13 页）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 分屏几何：110 宽 → 左 73 / 右 37（内容 36） | `ref/workspace-audit.md` 第 1 节（实测） |
| 窗格内 `pin="top"` 与"移除+重挂"换装 | 同上第 2 节（实测已跑通；`remove` 收 **id 字符串**） |
| 现有预览：`_open_preview` / `_close_preview`（同一槽位） | `examples/showcase/session.py` |
| `PageBody(hint, focus, tick, note)` 与 `show()` 顺序 | `examples/showcase/page.py`、`session.py` |
| 事件路由顺序与 `playing` 规则、`_page_click` | `session.py` 的 `run()`（audit 第 4 节） |
| 标签条：`Tabs.click(row, col)` / `move(delta)`（夹取）/ `select` / `focused` 失焦变暗 | `src/mocode_tui/widgets/tabs.py` |
| 滚回顶部：`pane.viewport.scroll_up(1 << 20)` | audit 第 2 节 |

## 工单（按序执行，每项一个 commit）

### T1 `page.py` + `session.py`：aside 与 sync

- `page.py`：`PageBody` 增两个可选字段——
  `aside: Callable[[Pane], None] | None = None`（页面用右窗格时的挂载函数，收该 `Pane`）、
  `sync: Callable[[], None] | None = None`（宿主每轮事件后调用一次；页面据此把"组件状态"落到界面，
  与 `note`/`tick` 同性质的页面级钩子）。docstring 写清三者的分工与调用时机。
- `session.py`：
  - `show()` 顺序固定为：**先关上一页的 aside**（若开着）→ 清 transcript → 挂本页 blocks →
    **再开本页的 aside** → 聚焦/滚顶/banner；`show()` 期间置一个内部标志避免 `sync` 被重入调用。
  - 新增 `_open_aside()` / `_close_aside()`：用 `tui.split("vertical", ratios=(2, 1))` 拿右窗格，
    `body.aside(pane)` 挂载；关闭时 `pane.close()`（与 `_close_preview` 同款）。
  - **`/split` 规则**：当前页 `aside` 非空时，`cmd_split` 不开预览，改为 `toasts.show(...)` 一条说明
    （文案英文，如 `this exhibit owns the right pane -- /split is for pages without one`）；
    其它页行为一字不变。
  - `sync` 的调用点：主循环里每轮事件处理完（含被 ring 消费、被编辑器消费、被宿主处理的所有分支）
    在 `tui.invalidate()` 之前调用一次 `body.sync`（**一个调用点**，不在每个分支里散落）。
- 验证：headless 探针——进入 `/workspace` 后 `tui.frame.panes` 有 2 个；切到别的页后回到 1 个；
  `/split` 在 `/workspace` 上不新增窗格且 toast 出现；`/split` 在 `/chat` 上仍然开预览。

### T2 新模块 `examples/showcase/workspace.py`：版式

- 页名 `workspace`，`nav="work"`，注册进 `PAGES`（`interaction` 之后、`streaming` 之前 → **13 页**）。
- 左栏（本页 blocks，挂在主 document 上）：一段 canned 对话，按真实组件与真实时序写：
  `Message("user", …)` → `Message("thinking", …)` → `ToolBlock("$ uv run pytest -q", [...])` →
  `EditBlock("examples/showcase/session.py", context/removed/added)` → `Message("assistant", …)`；
  行文与 `content.py` 的 canned 口径一致（"no model, no network"）。
- 右栏（`aside(pane)`）：`pane.document.add(strip, pin="top")` + `pane.document.add(view_block)`；
  标签 = `Tabs(["tools", "edits", "reads", "agent"])`（**短标签，36 列内不截断**，实测复核）。
- `header` / `TRY ▸` / `API ·` 三件套齐：TRY 说"点一个标签，或 `tab` 后 `←→`"；
  API 行写真实契约（`tui.split(...)` / `Tabs.click(row, col)` / `Tabs.select(index)` /
  `pane.document.add(..., pin="top")`）。
- `hint="inspector tabs"`（banner 用），`focus=FocusRing([strip])`。

### T3 四个视图的静态内容（本页自有文本，短行、窄栏友好）

- `tools`：`ToolBlock`——一条命令 + 它的输出（≥8 行，能看出"工具调用的全貌"）。
- `edits`：`EditBlock`——一个小 diff（context / removed / added 各若干行）。
- `reads`：文件正文——用 `Markdown` 的 ```python 围栏（顺带演语法高亮），内容取自本仓真实片段
  （如 `focus.py` 的一小段），行宽 ≤ 30 列左右，避免右栏折行太碎。
- `agent`：**本波先静态**——几条 `Message("assistant", …)` / `ToolBlock` 组成的"子代理汇报"，
  保证 `--pages` 一定完整；W2 再让它 live。
- 视图内容各是一个组件，存在字典里 `VIEWS: dict[str, Callable[[Theme], Component]]`，
  切换时按名取用（便于 W2 替换 agent 的实现）。

### T4 切换：点击 + 键盘 + `sync`

- `sync()`（页面提供）：比较 `strip.active` 与"当前已挂视图"的下标，不同就
  `pane.document.remove(current.id)` + `pane.document.add(VIEWS[name](theme))` +
  `pane.viewport.scroll_up(1 << 20)`，并更新 `status`（可用一行 `Text` 显示 `view: edits (2/4)`）。
- 键盘路径：`tab` → 环把焦点给 strip；`←→` → `Tabs.move(±1)`（夹取、两端不回头）→ 环消费 →
  事件后 `sync` 换视图。鼠标路径：`hit_test` → `ring.click(hit)` → `Tabs.click` 选中 → `sync`。
- **边界**：点在分隔符/两端空白上 → `Tabs.click` False、不换视图（报告里要贴这条探针）。
- 验证（探针，贴真实输出）：点 `reads` 标签 → 右栏首个渲染行变成 `reads` 视图的标记行；
  `tab` + `←→`×2 → 视图跟着变、`strip.active` 同步；切视图后 `viewport.offset == 0`。

### T5 回放、registry、文档

- `script()`：追加——切到 `/workspace` → 点第二个标签（用真实屏幕坐标，参照现有点击脚本的写法）→
  再 `tab` + `right`；保持既有回放不动。
- `registry.py`：新页描述一句话（"a chat beside an inspector -- tabs on the right, one view at a time"）。
- `README.md`：`## The demo` 的页表加 `/workspace` 行；"playing"段补一句"这一页自带右窗格，
  `/split` 在它上面让位"；`examples/demo.py` docstring 同步页名。
- 导航条实测：13 个短标签 `tabs.render(110)` 的文本与 `visible_width`（**不含 `…`**）；
  banner 提示行最坏页 `visible_width`（≤101）。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → **948 passed, 1 skipped**（一字不变）。
2. `demo.py < /dev/null; echo exit=$?` → exit 0；dump 里 `/workspace` 的**两栏并排可见**（贴原文片段：
   左栏一行对话 + 右栏标签条一行）。
3. `demo.py --pages` → exit 0、**13** 个页头（贴清单）与总行数；`/workspace` 段能看到
   标签条与当前视图的行。
4. 探针（逐条贴输出）：进入后 2 个窗格 / 离开后 1 个；`/workspace` 上 `/split` 不叠窗格且有 toast；
   `/chat` 上 `/split` 仍开预览；点 `reads` 换视图；`tab`+`←→` 换视图且 `active` 同步；
   点分隔符不换视图；切完 `offset == 0`。
5. `framebench` hash 逐字符一致；`test_readme_examples.py` 6 passed；`import mocode_tui` exit 0；
   `git diff --stat <base>..HEAD -- src/` 空；导航条无 `…`。
6. 真机项（分屏观感、点击标签、`c-o` 滚右栏、`/split` 的 toast）**无法执行** → "lead 终验项"。

## 禁触清单

- `src/`（任何文件）
- 前组已定稿的展品实现：`examples/showcase/{components,styles,features,keys,chat,interaction,streaming}.py`
  （本波只允许改 `page.py`/`session.py`/`registry.py`/`script.py` 四个装配点 + 新增 `workspace.py`）
- `specs/`（不改 spec/ref；数值只写报告）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + 页头数/行数）/ 探针输出（第 4 条逐项）/
行为变化 A/B（`show()` 顺序与 `/split` 规则的 dump 片段、新增页的两栏 dump 片段）/
导航条与提示行宽度实测 / 偏差与取舍 / 未决问题 / 真机手测：未执行（lead 终验）。

遇到阻塞（`sync` 时序不稳、切视图后窗格不刷新、`remove`/`add` 的 id 复用引发问题）：
**停下上报，不越界自救**。
