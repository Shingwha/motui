# Spec showcase-redesign · W2 组件展品 A（波次 W2）
> 分支 `sr2-exhibits-a`；前置：**W1 已合并**；深读：`00-overview.md`（设计定稿 B/C 节、决策 D2/D3）、
> `ref/capabilities.md`（每族"怎么玩"的清单）。
> **最高约束：每一页都要回答"这是什么 / 你该做什么 / 对应哪行 API"三件事，且激活必须有回声。**
> ✅ **2026-10-07 已合并** @ `sr2-exhibits-a`（四页套语法 + `PageBody.note` 反馈通道；提示行最坏 98 列）。

## 目标

把 `structure` / `lists` / `fields` / `feedback` 四页按展品语法重做，并落地**反馈通道**：
宿主在 ring 消费一次激活后读一次 `chosen` → toast + 页内回声（`PageBody` 新增的可选 hook）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 四页现状（widgets 与 ring 组成） | `examples/showcase/components.py` 的 `structure/lists/fields/feedback` |
| `PageBody(hint, focus, tick)`；`tick` 是"页面自主动画"的既有先例 | `examples/showcase/page.py:32-49` |
| ring 的 click 策略（点一次聚焦、二点激活、非目标也派发） | `src/mocode_tui/focus.py` docstring |
| `Select.chosen` / `Table.chosen`（读一次清一次） | `widgets/choice.py`、`widgets/table.py` |
| `Toasts.show(text)` | `src/mocode_tui/chrome.py` |
| 落点能力（W5 of interaction-model） | `widgets/textbuf.py` 的 `place`、`widgets/field.py` 的 `click` |

## 工单（按序执行，每项一个 commit）

### T1 反馈通道：`PageBody.note` + 宿主的"读一次"

- `page.py`：`PageBody` 增可选字段 `note: Callable[[str], None] | None = None`（docstring 写明：
  宿主读到一次激活的结果时调用它，页面用它更新自己的回声行；与 `tick` 同一性质的页面级 hook）。
- `session.py`：抽出 `_report(text: str)`——`self.toasts.show(text)` + 若当前页有 `body.note` 则
  `body.note(text)`。**所有**激活路径都过它：
  - `playing and ring.handle(event)` 消费后，若事件是 `Key("enter")`：从聚焦目标读 `chosen`
    （存在且有值 → 报 `f"chosen: {value!r}"`；`chosen` 读后置 `None`）；
  - `_page_click` 里 `ring.click(hit)` 之后同样读一次（二点激活的路径）。
  不许在组件侧新增回调（全局不变量 1）。
- 验证：headless 探针——`/lists` 上 `enter` 一次 → `Toasts` 的当前文本含 `option`；
  且相同目标的第二次 `enter` 不会重复同一句（chosen 已被清空）。

### T2 `structure` 页重做

- 语法三件套：`header` → `try_line("点 Tabs 的任一 tab / Tree 的任一行；tab 换焦点，失焦者的光标会变暗；enter 折叠或展开")`
  → 展品（Panel / Row / Column / Padding 的编排保持"盒子与列"的信息密度，可精简但不得删族）
  → `api_note("Tabs.click(row, col) / Tree.activate() / FocusRing.handle(event)")`。
- ring 组成保持 `[tabs, tree]`；**点破失焦变暗**：在 Tabs 或 Tree 旁加一行 dim 说明
  （如 `when it is not focused, the cursor row dims -- theme.dim`）。
- 验证：dump 里出现 `TRY ▸`/`API ·` 两行；`focused=False` 的变暗效果已有单测（interaction-model W4），
  本波只需在 dump 中确认页面正常。

### T3 `lists` 页重做（第一条可见回声）

- 顶部 `try_line("点一行把光标带过去；enter 激活；看 toast 与下面这行回声")`。
- 页内回声行：一个页面自有的 `Text`（初始 `last pick: --`），由 `PageBody.note` 更新为
  `last pick: <repr(value)>`（只保留最近一次）。
- 四个展品保持（Select 20/6、Confirm 危险/普通、Autocomplete 已过滤）；每段一行 `api_note`
  （`Select.chosen`、`Confirm` 是 Yes/No 的 `Option(value=True/False)`、`Autocomplete` 过滤后激活拿命中项）。
- 验证：headless 探针激活 Select 的第 3 行 → 回声行变 `last pick: 3`（贴输出）。

### T4 `fields` 页重做

- `try_line("在最下面两段文本里任意点一格：块光标就落在那里；点在 prompt 上落在行首")`。
- 保留四种状态（空 Input 的 hint、`focused=False` 的 Input、Editor、`max_rows` 窗口 Editor）；
  每段一行 `api_note`（`TextBuffer.place(row, col)`、`field.click(row, col)`）。
- 加一行 dim 说明粘贴语义（`a multi-line paste is one event and never submits; a single-line Input folds its newlines`）。
- 验证：headless 探针在窗口 Editor 的第 3 行中间点一下 → `cursor_position` 落在所点格子
  （与 `render` 的行对照，贴输出）。

### T5 `feedback` 页重做（toast 的展品入口）

- `try_line("激活下面这个级别选择器：它会按你选的级别弹一条 toast")`。
- 新增一个单项展品：`Select([Option("info"), Option("warn"), Option("error")])`，
  `enter`/点击激活 → 宿主读 `chosen` → `toasts.show(f"{level}: a {level} notice from the feedback exhibit")`。
  这是"用激活驱动反馈"的最小演示。
- 保留三条 ProgressBar、Spinner 帧、三条 Notice；每段 `api_note`（`Toasts.show(text)`、`ProgressBar.fraction`、`Spinner.advance()`）。
- ring 组成：`FocusRing([levels])`（级别选择器）；活条/转轮仍靠 `tick`。
- 验证：headless 探针激活 → toast 文本出现（贴输出）。

### T6 回放与文档

- `script.py`：在 `/lists` 的一次 `enter` 后保持既有回放；追加"激活 feedback 的级别选择器"一步
  （切到 feedback 页 → `enter`），使 piped 回放覆盖 toast 路径。
- `registry.py`：四页描述改成展品口吻（一句话说清"能玩什么"）。
- `README.md`：`## The demo` 段里对应四页的两行同步（页表条目 + 玩法）；其余段不动。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → **一字不变** `948 passed, 1 skipped`。
2. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；dump 里能看到四页的
   `TRY ▸` 行原文（各贴一行）与 `lists` 的回声行。
3. `uv run python examples/demo.py --pages` → exit 0；页头仍 10 个；贴四页的关键行。
4. 四条 headless 探针（T1 的 toast+回声、T3 的 last pick、T4 的落点、T5 的级别 toast）：
   探针代码与真实输出贴报告。
5. `uv run python tools/framebench.py` → hash 逐字符一致；`tests/test_readme_examples.py -q` → 6 passed；
   `git diff --stat <base>..HEAD -- src/` → **空**。
6. 真机项（点/enter 的观感、失焦变暗的肉眼效果）**无法执行** → 报告写"lead 终验项"，由探针替代。

## 禁触清单

- `src/`（任何文件）
- `examples/showcase/{styles,features,chat}.py`（W3）、`components.py` 的 `text` 页
  （W1 已定稿，除共享 helper 调用外不改）与 `markdown` 页（W5）
- `specs/`

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行）/ 四条探针输出 /
行为变化 A/B（四页的 dump 前后对比摘要）/ 偏差与取舍 / 未决问题 / 真机手测：未执行（lead 终验）。

遇到阻塞：**停下上报，不越界自救**。
