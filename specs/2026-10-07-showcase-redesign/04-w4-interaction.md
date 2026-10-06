# Spec showcase-redesign · W4 交互展品（波次 W4）
> 分支 `sr4-interaction`；前置：**W3 已合并**；深读：`00-overview.md`（设计定稿 A/C/E 节、决策 D1/D3）、
> `ref/capabilities.md` 第 1 节（交互模型是本次第一主角）。
> **最高约束：这一页必须让观众"看见"交互模型——焦点在谁身上、激活拿走了什么、点击落到了哪里，
> 三件事都要有画面。** 讲解文字只做提示，证据必须来自真实的组件状态。
> ✅ **2026-10-07 已合并** @ `sr4-interaction`（`interaction` 展品 + `Showcase.log` 唯一反馈出口，页表 12；

## 目标

新增 `interaction` 展品（三件套 + 实时 last-action 行），并把 W2 的反馈通道收口成
**全展台唯一的一条**：ring 的键盘激活、ring 的点击激活、导航条点击，全部经 `_report` 产生
toast/日志（`chosen` 读一次清一次）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| ring 的 handle 路由表与 click 策略 | `src/mocode_tui/focus.py` 类 docstring |
| 失焦渲染 `merge(theme.dim)` | `widgets/{choice,tree,tabs}.py` |
| 字段落点 | `widgets/field.py` 的 `click`、`widgets/textbuf.py` 的 `place` |
| `PageBody.note` 反馈通道 | `examples/showcase/page.py`（W2 落地） |
| `playing` 规则（composer 空 + 非打印键才给 ring） | `session.py` 的 `run()` |
| 导航条与 `c-n`/`c-p` | `session.py`（W1 落地） |

## 工单（按序执行，每项一个 commit）

### T1 反馈通道收口

- `session.py`：`_report(text, *, toast=True)` 成为唯一出口；本波把它接到**所有**路径：
  - `enter` 激活（key 路径）：读 `chosen` → `chosen: <repr>`；
  - `ring.click` 的"二点激活"：同读一次；
  - `tab` 换焦点：`toast=False`，只写日志（`focus → <name>`，避免刷屏）；
  - 导航条点击/`c-n`/`c-p`：`toast=False`，写日志（`→ <page>`）。
- **日志本体**：`Showcase.log: list[str]`（最近 3 条，新的在前）——它就是 `interaction` 页的
  last-action 行数据源；页面用 `PageBody.note` 把它画出来。
- 判据：任何一次"激活"（键盘或鼠标）在日志里恰好留下**一条**记录，且 `chosen` 事后为 `None`
  （读一次清一次，headless 探针钉住）。

### T2 `interaction` 展品（新模块）

- 新 `examples/showcase/interaction.py`，页名 `interaction`，注册进 `PAGES`（页表 → **12** 页，
  插在 `features` 之后、`streaming` 之前）。
- 页面内容（顺序即叙事）：
  1. `header("interaction", "焦点、点击、激活、落点 —— 这一页就是交互模型本身")`。
  2. `try_line("tab 换焦点（看光标行变暗）· ↑↓ 移动 · enter 激活 · 点一次聚焦、再点激活 · 在 Editor 文本里点一格落光标")`。
  3. 三个展品各自挂块、同属一个 `FocusRing([menu, tree, editor])`：
     - `Select`（5 个 Option，带 description）；
     - `Tree`（两层，含叶子与可折叠节点）；
     - `Editor`（三行文本，`focused` 由环管理）。
     每个展品上方一行 dim 小标题说明"它是什么"，下方一行 `api_note`。
  4. **last-action 行**：一个页面自有的 `Text`（初始 `--`），经 `PageBody.note` 显示
     `Showcase.log` 的最近 3 条（`\n` 连接，dim；最新一条 accent）。
- `api_note` 内容必须真实：`ring.handle(event) -> bool`、`ring.click(hit) -> bool`、
  `field.click(row, col)`、`component.chosen`。
- 验证：headless 探针依次做——`tab` → 日志出现 `focus → tree`；`enter` 折叠/展开树 →
  日志出现 `activate → tree`（Tree 是 `Activable`（激活即折叠），但它**没有 `chosen` 载荷**，
  所以按"这次激活产出了什么"记一条无载荷的记录，而不是报 `chosen: None` 那种像失败的话）；
  切到 Select 后 `enter` → 日志出现 `chosen: 'row 01'`；在 Editor 上点一格 →
  `cursor_position` 落在所点格子。

### T3 页面接入与回放

- `registry.py`：新页描述一句话（"焦点环、点击策略、落点 —— 交互模型现场"）。
- `script.py`：追加——切到 `/interaction` → `tab` 两次 → `enter` → 在 Editor 上点一次；
  保持既有回放不动。
- `README.md`：`## The demo` 段的页表加 `/interaction` 行，玩法段落改写为"这一页把交互模型演给你看"。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → **一字不变** `948 passed, 1 skipped`。
2. `demo.py < /dev/null` → exit 0，dump 含 `interaction` 页的 `TRY ▸` 与 last-action 行；
   `--pages` → exit 0、**12** 个页头（贴清单）。
3. T1/T2 的探针输出（逐条贴）：激活恰好一条日志、`chosen` 事后为 None、落点格与 `render` 对照一致。
4. `framebench` hash 逐字符一致；`test_readme_examples.py` 6 passed；`src/` 零 diff。
5. 真机项（失焦变暗的肉眼效果、点一次/二点的观感）**无法执行** → "lead 终验项"，由探针替代。

## 禁触清单

- `src/`（任何文件）
- `examples/showcase/{components,styles,features,chat}.py`（前几波定稿；本波只在 registry 加一页）
- `examples/showcase/markdown`/streaming 相关（W5）
- `specs/`

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + 页头清单）/ 探针输出（按 T2 的四步）/
行为变化 A/B（新增页与日志行的 dump 片段）/ 偏差与取舍 / 未决问题 / 真机手测：未执行（lead 终验）。

遇到阻塞（例如"Tree 的 activate 让日志读出 None 会显得像失败"这类语义问题）：**停下上报，不越界自救**——
把观察写清楚，由 lead 决定措辞。
