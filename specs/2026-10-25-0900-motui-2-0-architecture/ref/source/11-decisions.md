# 11 · 决策记录（ADR-001 … ADR-023）

> 状态：accepted（随 2.0 冻结）
> 格式：Context / Decision / Why / Consequences / Alternatives

## ADR-001 · Surface 是唯一帧类型

- **Context**：1.x 的帧是 `list[Line]`，没有几何；画布/媒体无处安放。
- **Decision**：所有组件 `render(Constraints) -> Surface`；`Surface` 是唯一帧类型；`Canvas` 是它的可变构造器。
- **Why**：选择/hit/golden/overlay 只有一条路径；未来能力可在 `Surface` 内部增长。
- **Consequences**：`Surface` 必须有裁剪不变量；禁止 Canvas 直写字节。
- **Alternatives**：`list[Line]`（1.x，已否决）；第二通道（rows + media 并列，已否决）。

## ADR-002 · 不做 measure/render 两阶段

- **Context**：需要“填满窗格”，但不想让每个组件写两份逻辑。
- **Decision**：单趟 `render(Constraints)` + `Sizing.FILL`；容器按顺序分配剩余高度。
- **Why**：覆盖游戏（单 fill）、IDE（固定侧栏 + fill）、聊天（list fill + 输入固定）。
- **Consequences**：FILL 必须在 FLOW 之后；`Document.add` 校验。
- **Alternatives**：measure/render 两阶段（成本高、API 翻倍）。

## ADR-003 · 能力是属性，交互是 hooks

- **Context**：1.x 用 `isinstance` + 反射判定能力；`handle` 里手写按键。
- **Decision**：`focusable/clickable/hoverable/activatable` 属性；`on_key/on_mouse/on_paste/on_resize/on_focus/on_click/on_hover/on_drag/on_action` hooks。
- **Why**：删除 18 处能力 `isinstance` 与 `_looks_interactive`；行为可按 action 测试。
- **Consequences**：`handle()` 只保留特殊控制器（≤3）。
- **Alternatives**：继续用 `runtime_checkable` 协议；消息总线。

## ADR-004 · 删除 Revisioned

- **Context**：37 个 `revision()`、44 处提及、3 页“快照必须是值语义”的陷阱文档。
- **Decision**：状态变更自动 `touch()`（`__setattr__` + 祖先传播）；`Section` 缓存 key `(width, height, generation)`；`MOTUI_NO_CACHE=1` 关闭缓存。
- **Why**：默认缓存、零快照陷阱；容器不再实现 `_child_key`。
- **Consequences**：就地修改需 `touch()`；每个可变 widget 有一个“变更即失效”测试。
- **Alternatives**：继续 `Revisioned`；全局 dirty flag（漏得更隐蔽）。

## ADR-005 · kernel 零 I/O

- **Context**：`core/` 里 2,150 行终端 I/O；内核不能脱离终端使用。
- **Decision**：`ansi/screen/decoder/keys/win32/capability/clipboard` 全进 `terminal/`；kernel 不 import `os/sys/io/ctypes/termios/tty/select/asyncio`。
- **Why**：内核纯值；可服务端渲染/录制/测试；import-linter 可机器化。
- **Consequences**：`Screen` 在 terminal；kernel 只能用值。
- **Alternatives**：保留在 core（已否决）。

## ADR-006 · 定时器按截止时间调度

- **Context**：`next_run = now + period` 累积漂移（50ms → 58–65ms）。
- **Decision**：`next_run += period`；`catch_up="skip"|"coalesce"`；`advance(dt)` 虚拟时钟；`fps`/`frame_budget` 丢帧。
- **Why**：固定频率；测试确定性；动画不漂移。
- **Consequences**：落后太多时按策略丢弃；不补帧。
- **Alternatives**：继续 `now + period`；真实 sleep。

## ADR-007 · 派发顺序是数据

- **Context**：`App.dispatch` 10 层 if 链，不可组合。
- **Decision**：`DEFAULT_HANDLERS` 元组；`auto=False` = `handlers=()`；每个 tier 只回答“是否消费”。
- **Why**：顺序可见、可测、可替换；新 tier 不改 App。
- **Consequences**：顺序是公开契约，改顺序需评审。
- **Alternatives**：继承 + `super().dispatch`（1.x）。

## ADR-008 · golden 语义化

- **Context**：57 个字节 hash golden；SGR 顺序变化误报，换行/裁剪 bug 抓不到。
- **Decision**：VT 模拟器的 cell 网格 + 属性为主断言；少量字节级测试保留。
- **Why**：稳定的语义；能抓换行/裁剪。
- **Consequences**：W2 重录 + 差异分类；旧字节 golden W5 删除。
- **Alternatives**：继续字节 hash。

## ADR-009 · 2.0 不兼容

- **Context**：大量 API 改名（`take`/`Section`/`TUI` 等）。
- **Decision**：不保留 shim/alias；提供迁移表与示例。
- **Why**：断代版本；避免双门与长期债务。
- **Consequences**：用户必须迁移；`MIGRATION.md` 是一等交付。
- **Alternatives**：兼容层（已否决）。

## ADR-010 · 性能边界 ≤30fps

- **Context**：Python 对象 + 终端带宽限制。
- **Decision**：目标 ≤30fps；不做 60fps 全屏逐格；文档写明。
- **Why**：避免为不可达目标牺牲架构。
- **Consequences**：`throttle`/`fps` 可调，但不承诺 60。
- **Alternatives**：追逐 60fps。

## ADR-011 · 可增长性，不预置字段

- **Context**：曾考虑预留 `Cell.media`/`Surface.placements`。
- **Decision**：不预置未实现字段；引擎值类型 `kw_only + 默认 + 类方法`；能力用注入/默认属性。
- **Why**：未验证语义会变成承诺；所有权与构造方式决定兼容性。
- **Consequences**：`tools/growth.py` 演练；2.x 加字段是 minor。
- **Alternatives**：预留空字段。

## ADR-012 · 换行是内容策略

- **Context**：59 处 `fit`；代码块/Diff/宽表丢内容。
- **Decision**：`WrapMode` + `Line.reflow`；按内容类型设默认；2.0 只改代码块（截断→换行）与 Input（多行→单行）。
- **Why**：行业按内容类型分；统一词表；不丢内容。
- **Consequences**：`fit` 私有；`Table(wrap=bool)` 删除。
- **Alternatives**：全局 `App(wrap=)`（已否决）。

## ADR-013 · Scroll 是 2D 值，L1 进 2.0

- **Context**：1.x `ScrollState` 只有 `offset: int`；宽表不可读。
- **Decision**：`Scroll(x: Axis, y: Axis)`；2.0 横向只给不换行内容（`ScrollPanel(axis)` + `OVERFLOW`）；文档流横向留 2.x。
- **Why**：形状现在对；横向能力有明确边界。
- **Consequences**：pane 仍 y-only；`thumb` 只写一遍。
- **Alternatives**：1D 以后改（牵动所有公式）；全文档横向（复杂）。

## ADR-014 · Screen 是 ABC

- **Context**：1.x `Screen` 是 `runtime_checkable Protocol`；加方法破坏实现者。
- **Decision**：窄 ABC + 默认实现；能力用默认属性/注入；消费者仍用 Protocol。
- **Why**：宿主/测试可继承；2.x 加方法不破坏子类。
- **Consequences**：`TerminalScreen`/`HeadlessScreen` 继承。
- **Alternatives**：Protocol（已否决）。

## ADR-015 · 终端度量不进 Constraints

- **Context**：图片/像素尺寸需要 cell metrics。
- **Decision**：不进 `Constraints`；作为能力值/组件状态注入；第三个消费者出现才考虑 `RenderEnv`。
- **Why**：kernel 纯度；组件测试不需要假终端。
- **Consequences**：2.0 不做 `RenderEnv`。
- **Alternatives**：`Constraints.env` 现在加（投机）。

## ADR-016 · 值拥有行为

- **Context**：行/选择/标记操作是自由函数；同一概念多个入口。
- **Decision**：`Line.*`、`Selection.*`、`Scroll.*`、`MarkSet.*`、`HitPath.*`；模块级函数只做构造/度量。
- **Why**：可发现、可链式、可测试；减少散落函数。
- **Consequences**：`text.*` 保留（只吃字符串）；`fit` 等私有。
- **Alternatives**：继续自由函数。

## ADR-017 · 一个概念一个门

- **Context**：`ansi.*` + `Screen.*`；`App.add` + `TUI.add`；`EveryHandle` + `Timer`。
- **Decision**：终端只经 `Screen`，定时器只经 `Runtime`，pane 只经 `Workspace`，事件只经 `Router`，主题只经 `Widget`。
- **Why**：减少双门与“改一处忘另一处”。
- **Consequences**：删重复门；`api.py` 检查。
- **Alternatives**：保留双门。

## ADR-018 · TerminalOptions + MouseMode

- **Context**：App/TUI/Screen 三份开关；`hover` 不是独立布尔。
- **Decision**：`TerminalOptions` 一份配置；`MouseMode.OFF/BUTTON/DRAG/MOVE`。
- **Why**：新增开关只改一处；1000/1002/1003 语义清楚。
- **Consequences**：`App` 参数减少；`interactive` 推导。
- **Alternatives**：继续 `mouse=True, hover=True`。

## ADR-019 · 返回 Section，位置用枚举

- **Context**：`add -> str`、`get -> Component`、`Document.add -> Block`；`split("vertical")` 反直觉。
- **Decision**：`add/get/remove -> Section`；`split(Axis.X)`、`dock(placement=...)`；`ratios` → `weights`。
- **Why**：一个返回类型；方向语义明确。
- **Consequences**：字符串入口删除。
- **Alternatives**：保留 `str` id / 字符串方向。

## ADR-020 · Command 声明即接线

- **Context**：`Command` 无 `group`（demo 把 group 当 description）；`keys` 没接 App；`open_palette` 类型空。
- **Decision**：`Command` 加 `group` 且 `kw_only`；`CommandRegistry.bind(app)`；`open_palette(registry)`。
- **Why**：声明与接线一处；类型明确；不再误用位置参数。
- **Consequences**：`by_key` 被 App 使用；palette 可按组渲染。
- **Alternatives**：继续手动 bind。

## ADR-021 · Focus 从树推导

- **Context**：`set_focus_targets` + `FocusManager.add/remove` + `owns_focus`。
- **Decision**：`focusable` + `children` 决定环；`Workspace.focus*` 唯一入口；`FocusManager` 内部化；`owns_focus` → `focus_scope`。
- **Why**：加控件即可聚焦；删注册 API。
- **Consequences**：焦点顺序 = 前序遍历。
- **Alternatives**：继续注册。

## ADR-022 · 一次性结果用 take()

- **Context**：`take_result()` 不是标准 UI 命名；`bool | None` 易混淆。
- **Decision**：`take()`；`Resultful` → `HasResult`；`None` = 无事件，状态仍由 `selected/checked/text/open` 提供。
- **Why**：Rust `Option::take` 的消费语义；短、语境清楚；一门。
- **Consequences**：`bool | None` 组件用 `is not None`；旧名删除。
- **Alternatives**：`take_result`（保留旧名）；`result()` getter（会清空，误导）。

## ADR-023 · 结果做拉取，不做 per-widget 推送

- **Context**：demo 每轮 walk 整棵树；是否加 `on_result`。
- **Decision**：不加回调；公开 `Widget.walk()`，用 `walk()` + `take()` 收集。
- **Why**：避免 dispatch 中重入/顺序副作用；避免滑向消息总线；保持单门。
- **Consequences**：宿主需要遍历或持引用；`walk()` 成为公共 API。
- **Alternatives**：per-widget `on_result`（已否决）；App 级单钩子/`Modal.on_close`（若将来需要）。
