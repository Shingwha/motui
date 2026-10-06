# Spec interaction-model · 总纲

> 操作启动日 **2026-10-07**。本组是一次**交互模型的从根重建**：把"指针命中 / 激活 / 焦点 /
> 落点 / 粘贴"这五件事从各自为政的补丁收进一条宪法，每个波次**先立协议再改消费者**，
> 被取代的旧名与旧路径**同波删除**（不留 shim、不留 alias、不留弃用期——这是库在
> `docs/DESIGN.md` 写下的契约，本组贯彻到底）。
>
> Git / worktree 协议见 `spec-team` SKILL 一节（worktree 放仓库外、分支从合并时刻最新 main
> 切出、agent 不 merge / push / tag、lead 统一创建与销毁）。本组不重复。
>
> ✅ **2026-10-07 全组六波已合并**（W1 `im1-paste` → W6 `im6-table`，每个合并前/后各过一次全门禁）。
> 终验：`948 passed, 1 skipped`；`render-hash` 全程未动；demo 10 页 exit 0；旧名全仓零残留。
> 各波工单头部有对应 merge 状态；交付后真机手测清单见本文件末节（待用户在真终端执行）。

## 背景与问题清单

最近两轮迭代（菜单重做、展示台 demo）把交互这条线暴露成五个各自成立、合起来不成体系的问题。
每条都有可复现证据，完整锚点在 `ref/audit-interaction.md` 与 `ref/audit-paste.md`：

1. **命中协议看不见列**。`Clickable.click(row) -> bool` 是行式协议，但 `Tabs` 的点击语义是
   "第几个 tab"，组件文档自己写着"由 host 解析格子"——于是展示台只能在宿主里手写
   `_tab_at()` 走一遍渲染段宽（`examples/showcase/session.py`）。**能看见列才是常态，
   row-only 是特例**（Textual 传含 x/y 的事件、prompt_toolkit 传完整 MouseEvent、
   ratatui 把坐标交给应用）。这是协议裂缝，不是 demo 的错。
2. **"激活"没有统一动词，而且名字被占用两次**。`Tree.toggle()`、`Tabs.activate(index)`、
   `Select` 的"拿走光标项"是 host 语义（展示台里是弹 toast），
   `SlashPalette` 又自己长了一套 `chosen` 契约。同一个词 `activate` 在两处表示两件事
   （Tabs 选 tab、协议想要的"执行主操作"），正是命名宪法要禁止的。
3. **没有 widget 级焦点**。只有 pane 级焦点（`TUI.frame.focused_pane`），
   组件渲染时**不知道自己在不在焦点上**（`Input`/`Editor` 有 `focused`，列表族没有）。
   展示台只好把"每页一个可玩目标"写成一个 host 私有的 `Play` 适配器
   （`examples/showcase/page.py`）——那是焦点层的残缺替身。
4. **字段不能点**。`Input`/`Editor` 没有命中入口：点在文本上只能靠方向键挪光标。
   `TextBuffer` 已经有完整行几何（`visual_rows` / `locate` / `_VisualRow`），
   缺的只是 **cell → offset 的反向映射**。
5. **多行粘贴会触发多次提交（真 bug）**。全仓 **没有任何一处开启 bracketed paste**
   （grep `2004` 零命中），所以终端从不包裹粘贴内容：`\r\n` 的每一半都被
   `_char_key` 解码成一个 `Key("enter")`，宿主每见一个 `enter` 就提交一次。
   实测 `b"line one\r\nline two\r\nline three"` 解码出 4 个 `enter`
   （证据与探针输出见 `ref/audit-paste.md`）。decoder 侧其实**已经支持**
   `\x1b[200~`/`\x1b[201~`（`tests/test_keys.py` 有单测），只是没人让终端发它。

## 交互宪法（本组定稿，全部波次遵守）

```
1. 命中   Clickable.click(row, col) -> bool
          坐标是「块内」的 (行, 列)，与 TUI.hit_test 报的一致；组件消化自己的行/列算术。
          行式列表忽略 col —— 但必须在 docstring 里写明「忽略」，不允许静默丢弃。

2. 激活   Activable.activate() -> bool
          只属于「光标指着一个东西、回车就是拿走它」的组件：Select / Autocomplete /
          Confirm / Tree。菜单族把拿走的那一项写进 chosen（host 读一次清一次），
          SlashPalette 的选择契约上收归 Select；Tree 的「展开/折叠」就是它的 activate。

3. 焦点   FocusRing（新层 focus.py，与 gesture.py 平级）
          注册目标、循环、把事件转发给聚焦者；组件只多一个 focused: bool 与一条
          「失焦 = 光标样式 merge theme.dim」的渲染规则，不认识焦点管理器。

4. 落点   字段可点：TextBuffer.place(row, col) 做 cell → offset 的反向映射，
          Input / Editor 因此成为 Clickable；点在文本上 = 光标落在那儿。

5. 粘贴   屏幕进入时开 bracketed paste（DECSET 2004）：多行粘贴是「一个 Paste 事件」，
          永远不等于一串 enter；Paste 永不提交。单行 Input 把粘贴里的换行归一成空格。
```

**边界（防止宪法被泛化）**：不做 hover（见 D5）、不做 Button 组件（D6）、布局容器不转发点击（D7）、
不引入回调 / 事件总线 / 全局焦点单例（全局不变量 1）。

## 命名宪法（本组定稿）

| 概念 | 统一名 | 淘汰者（同波删除） |
|---|---|---|
| 指针命中一个块内格子 | `click(row: int, col: int) -> bool` | `click(row)`（row-only 签名，W2） |
| tab 条选中第 i 个 | `Tabs.select(index) -> bool` | `Tabs.activate(index)`（W2，它是"设值"不是"执行"） |
| 执行光标下的那件事 | `activate() -> bool` | `Tree.toggle()`（W3） |
| 被拿走的当前项 | `<组件>.chosen`（读一次清一次） | `SlashPalette` 自带的私有选中路径（W3 改为委托） |
| widget 焦点 | `focused: bool`（组件属性）+ `FocusRing`（层） | 展示台的 `Play` 适配器（W4，`examples/showcase/page.py`） |
| 文本落点 | `TextBuffer.place(row, col) -> bool` | —（W5 新增） |

## 决策登记（拍板，不再反复）

- **D1 命中必带 col**：`click(row, col)` 的 `col` 无默认值。理由：宿主永远两样都有
  （`Hit.row`/`Hit.col`），必填逼每个实现显式决定列要不要用；默认值会诱使实现静默忽略。
- **D2 激活动词唯一**：协议名 `activate()`；Tabs 的"选中第 i 个"改名 `select(index)`
  （它是"设值"不是"执行"）。理由：一个概念一个名字。
- **D3 `chosen` 上收**：`Select` 持有 `chosen: Option | None` 与 `activate()`；
  `SlashPalette` 退化为「键路由 + value 映射」，它公开的 `chosen: str | None` 契约不变。
- **D4 焦点在层、不在组件**：`FocusRing` 是 app 层控制器（与 `gesture.py` 同层，可 import app）；
  组件的失焦表现是渲染规则：**光标样式 `.merge(theme.dim)`**（accent/selection 保住色相，
  只降权重；不新增 theme 字段）。`Input`/`Editor` 已有的 `focused` 语义（画不画块光标）
  与之一致，直接并入。
- **D5 hover 不做**。要 hover 必须开 1003（any-motion）：指针每移一格一个事件，
  200 列的终端横穿一次 200 个事件、每个都要 hit-test + 重绘，正好打掉本库
  "无变化零字节"的卖点；还会和终端原生选择、`SelectionGesture` 的拖动抢 motion。
  行业里认真做 hover 的只有 Textual 系（全量消息泵 + CSS）。未来要做单独立项，
  形状是「组件加 `pointer_row` 状态 + host 自行开 1003」，默认关。
- **D6 不做 Button 组件**：TUI 的 button ≈ 一项菜单 + host 动作；本库的模型是
  "组件存状态、host 读状态"，没有回调总线。文档给配方（单项 `Select` +
  `activate()`/`chosen`），不新增类。
- **D7 容器不转发点击**（本次范围外）：命中粒度是 block，这是本库的设计选择
  （Textual 是 widget 树级）。替代写法已在展示台验证：**可交互组件各自挂块**。
  未来的形状写在下面"范围外"一节。
- **D8 demo 键位**：`tab` = 焦点环（widget 焦点，行业通例），`c-o` = 窗格焦点
  （`/split` 之后用）。README / banner / 展示台脚本同步改。
- **D9 粘贴**：开 2004 是唯一可靠手段，且**不做启发式猜测**。旧 console 记录路径
  （拿不到 VT 输入的老控制台）与 cooked 管道拿不到 bracketed paste，
  降级行为写进文档，不假装能修。
- **D10 Table（可选波次）光标默认**：`move(delta)` 夹取（数据表不循环，与菜单族相反，
  docstring 必须写明）；`selected_style` 默认 `theme.selection`（整行反白带，
  数据行用带比用 accent 更好读）。

## 波次表（严格串行；每波一个 agent，合并后再派下一个）

| W | 交付 | 主要写入范围 | 前置 |
|---|---|---|---|
| W1 | 粘贴语义：开 2004、Paste 永不提交、单行 Input 归一 | `core/ansi.py` `core/screen.py` `widgets/input.py` `tests/test_screen.py` `tests/test_ansi.py` `tests/test_widgets_editing.py` `examples/showcase/script.py` `docs/` | — |
| W2 | 命中协议：`click(row, col)` 全量替换 + Tabs 列算术归位 + `Tabs.activate→select` | `core/block.py` `widgets/{choice,tabs,tree}.py` `app.py`(docstring) `examples/showcase/*` `tests/*` `README.md docs/` | W1 |
| W3 | 激活协议：`Activable` + `Select.chosen` + `Tree.toggle→activate` + SlashPalette 委托 | `core/block.py` `widgets/{choice,tree}.py` `chat/slash.py` `tests/*` `docs/` | W2 |
| W4 | 焦点层：`focus.py` + 列表族 `focused` + 展示台接线 | 新 `src/mocode_tui/focus.py` `__init__.py` `widgets/{choice,tree,tabs}.py` `examples/showcase/*` `tests/test_focus.py`(新) `docs/` | W3 |
| W5 | 落点：字段可点（cell → offset） | `widgets/{textbuf,field,input,editor}.py` `tests/test_widgets_editing.py` `examples/showcase/components.py` `docs/` | W2 |
| W6 | （**可裁剪**）Table 行光标：`index`/`move`/`click`/`activate` | `widgets/table.py` `tests/test_widgets_table.py` `docs/` | W3 |

> **调度顺序 = 表序（严格串行：W1 → W2 → W3 → W4 → W5 → W6）**；「前置」列只是硬依赖的最小集
> （例如 W5 技术上只依赖 W2，但它排在 W4 之后，落工时 `examples/showcase/components.py`
> 已经带 W4 的焦点环接线，必须在其之上改，不能回退）。

## 全局不变量（每波每 commit 都不得违反）

1. **组件保持纯渲染**：`render(width) -> list[Line]`；交互 = 组件持有状态 + 控制器方法
   （`handle` / `move` / `click` / `activate` / `select`），**宿主路由事件**。
   不引入回调字段、事件总线、全局焦点单例、`async` 组件。
2. **一概念一名**（见命名宪法）；被淘汰的名字在同一 commit 里删除，全仓 grep 零残留
   （含 docstring、文档表格、示例、测试）。
3. **行为变化要登记**：任何改变渲染字节或宿主可见行为的工单，必须在工单里写明
   "改前 → 改后"与 A/B 证据；render-hash 故意变化时记录新基线并说明原因。
4. **注释与文档规范沿用现状**：代码注释/docstring 英文，spec 中文；
   commit 风格 `type(scope): 小写短句 -- 第二句`，单行、无句号。
5. **测试与文档同步**：README 里被 `tests/test_readme_examples.py` 执行的代码块、
   `docs/COMPONENTS.md` 的组件表/交互表、`docs/DESIGN.md` 的命名表，必须与代码同波更新。

## 门禁（每波合并前、合并后各跑一次，贴真实输出）

```bash
uv run pytest -q                                   # 基线：846 passed, 1 skipped（只增不减，除非工单写明删了什么）
uv run python examples/demo.py < /dev/null; echo exit=$?   # 期望 exit=0（脚本遍历全部页面）
uv run python examples/demo.py --pages | head -40   # 期望 10 页正常 dump
uv run python tools/framebench.py                   # render-hash 与基线比对（基线见 ref/）
uv run python -c "import mocode_tui"                # 根面导入不破
uv run pytest tests/test_readme_examples.py -q      # README 代码块
```

harness 事实（agent 必读）：

- OS = win32（Git Bash），Python 3.12+，`uv run` 是唯一入口；路径含非 ASCII 无影响。
- 无网络、无浏览器、无真实终端：**粘贴/鼠标这类交互只能靠 headless + `ScriptedKeys` 验**，
  真机手测项集中在下面的"交付后手测清单"，每波验收里再列自己那条。
- 测试零 sleep（库契约）；示例的交互路径允许 sleep，headless 路径不允许。

## 范围外（明确不做，附未来形状）

- **hover**（D5）：未来形状 = 组件加 `pointer_row: int | None` + `pointer_style`（默认比光标淡），
  host 自行开 1003 并转发 motion；默认关，且必须先在真机量事件风暴的代价。
- **布局容器转发点击**（D7）：未来形状 = `Row`/`Column`/`Panel`/`Padding` 实现
  `click(row, col)`：用自己的几何（固定宽度、gap、边框、内边距）把坐标翻译成
  「子组件 + 子坐标」再转发；需要在渲染时记录子矩形（每个子组件渲染的行数已知）。
  代价：容器要缓存上一次渲染的布局；收益：并排摆可交互组件不必各自挂块。
- **`Button` 组件**（D6）：配方写进 `docs/COMPONENTS.md`，不新增类。
- **鼠标拖动落点/拖选字段**：本组只做"单击落光标"；拖选字段文本需要
  `TextBuffer` 的 anchor 状态与 `SelectionGesture` 的协调，单独立项。
- **大粘贴的分块/节流**：`Paste` 一次性 `insert` + 一次重绘，够用；不做分块。

## 交付后手测清单（真机，lead 终验用）

1. Windows Terminal 里 `uv run python examples/demo.py`：粘贴 **3 行文本** →
   输入框应出现 3 行、**一个**字符都不提交；回车才提交一次。
2. 复制一段含中文/emoji 的文本粘贴 → 列宽与光标正确（`visible_width` 路径）。
3. `/lists` 页：点菜单行 → 光标跟过去；点 `Confirm` 的 Yes/No → 选中。
4. `/structure` 页：点 Tabs 的第 3 个 tab → 它变 active；点 Tree 行 → 折叠/展开；
   `tab` 在 Tree ↔ Tabs 之间切焦点，失焦者的光标变暗。
5. `/fields` 页：点在 Editor 第三行中间 → 块光标落在那一格。
6. 老控制台（无 VT 输入）粘贴多行 → 逐行提交（**已知降级**，文档已写明）。
