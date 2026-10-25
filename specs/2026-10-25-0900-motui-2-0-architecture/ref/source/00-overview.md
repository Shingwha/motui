# 00 · 总纲（Epic）

> 上级：`README.md`　下级：`01-architecture.md`
> 状态：ready

## 1. 一句话

把 motui 从“文档流 + 行 diff 的 TUI 工具箱”升级为“**有几何、有画布、有节拍、可验证的终端 UI 内核**”，同时不丢掉它已经正确的东西：值语义、行 diff、内容安全、可测试性。

## 2. 为什么重构

1.2.3 在“应用型 TUI”上已经很好，但有五个结构性问题，导致画布/实时类需求无法表达：

| # | 问题 | 证据 | 后果 |
|---|---|---|---|
| P1 | 渲染契约只有宽度 | 38 处 `render(self, width)`；`ScrollView(height=)` 由宿主提供 | 组件不知道可用高度，“填满窗格”不存在 |
| P2 | 超宽行不裁剪 | 单 pane 全宽透传（`core/frame.py:842`）；实测 20 列屏写出 40 个 `A` | 真终端换行，整屏错位 |
| P3 | 交互靠反射与 isinstance | `_CHILD_ATTRS` 属性名遍历、`_looks_interactive`、116 处 `isinstance`（18 处能力协议） | 新容器改个子节点名，主题/焦点静默失效 |
| P4 | 失效模型认知负担重 | 37 个 `revision()`、44 处 `Revisioned` 提及、3 页陷阱文档 | 每加一个组件都要想“快照是不是值语义” |
| P5 | 运行时是上帝对象 | `app/driver.py` 1,333 行；`App.dispatch` 是 10 层 if 链 | 策略不可组合、不可检查 |
| P6 | 内核混入终端 I/O + 零静态检查 | `core/` 里 2,150 行 escape/decoder/win32；无 ruff/pyright/import-linter | 内核无法脱离终端使用；重构没有护栏 |

另外两个实测缺口：

- **定时器漂移**：`every(0.05)` 实际间隔 58–65ms，1 秒 17 次（应 20）；5ms 只到 ~84Hz。
- **内容丢字**：Markdown 代码块、`Diff`、`Table(wrap=False)` 都被 `…` 截断，无横向滚动。

## 3. 目标（可验收）

1. **一个渲染契约**：`render(Constraints) -> Surface`，`Surface` 自带裁剪不变量。
2. **一个绘制面**：`Canvas`（可变 cell 栅格）→ `Surface`；不引入第二条渲染路径。
3. **一个内容模型**：`PaneContent = Document | Fill`；流式文档与满窗格画布都是一等公民。
4. **一个交互模型**：显式 Widget 树 + 类型化 hooks + `keymap → action`；零能力 `isinstance`。
5. **一个失效模型**：状态变更自动向上冒泡 generation；删除 `Revisioned`。
6. **一个运行时拆分**：`Terminal / Runtime / Workspace / Router / App`，每个 ≤450 行。
7. **内核零 I/O**：`motui.kernel` 不 import `os/sys/io/ctypes`。
8. **可测性升级**：VT 模拟器 + 可注入时钟 + 语义化 golden + API 快照 + 可增长性演练。
9. **静态护栏**：pyright（内核 strict）、ruff、import-linter、API diff。
10. **调用面收敛**：常见路径更短；一个概念一个门；不为未实现功能预置字段。

## 4. 非目标

- ❌ Textual 式 retained tree + CSS + 消息总线。
- ❌ 两阶段 measure/render（单趟 + `Sizing.FILL` 足够）。
- ❌ 线上协议逐 cell diff（行 diff 已实测 115 字节/步）。
- ❌ 60fps 全屏逐格重绘（目标 ≤30fps）。
- ❌ 图片/动图协议（2.0 不预置字段；2.x 作为 codec 加法）。
- ❌ 自动换行的文档流横向滚动（2.0 只做不换行内容的 L1）。
- ❌ 向后兼容 shim。
- ❌ per-widget `on_result` 回调（见 ADR-023；用 `walk()` + `take()`）。

## 5. 原则

1. **值优先**：跨层的几何、事件、行、Surface 都是不可变值。
2. **单一路径**：所有组件最终产出 `Surface`；选择/hit/golden 只有一条路。
3. **能力显式**：能力是属性/hooks，不是运行时协议探测。
4. **策略可组合**：派发顺序是数据（handler 列表），不是方法里的 if 链。
5. **I/O 在边缘**：字节只在 `terminal/` 构造。
6. **不猜**：不变量在构造时校验并给出明确错误。
7. **值拥有行为，函数只做构造/度量**（ADR-016）。
8. **一个概念一个门**（ADR-017）。

## 6. 成功指标

| 维度 | 指标 | 当前 | 2.0 |
|---|---|---|---|
| 结构 | `core.__all__` | 75 | kernel ~35 + terminal ~15 |
| 结构 | 最大单文件 | 1,677（frame） | ≤900（markdown 例外需注释） |
| 结构 | `driver.py` | 1,333 | Runtime ~300 + Workspace ~450 |
| 交互 | 能力 `isinstance` | 18 | 0 |
| 交互 | `handle()` 实现 | 22 | ≤3（仅保留特殊控制器） |
| 失效 | `revision()` / `Revisioned` | 37 / 44 | 0 |
| 渲染 | 超宽行 | 会换行破坏整屏 | 裁剪保证 |
| 动画 | 50ms 定时器 1s 次数 | 17 | 19–20（误差 ≤5%） |
| 画布 | 80×24 全异色 | 不可用（无 Canvas） | ≤2.0 ms/帧 |
| 能力 | 代码块长行 | `…` 截断 | 完整可读 |
| 能力 | 宽表 | 只能被裁掉 | `ScrollPanel(axis="x")` 可滚 |
| 质量 | 类型/依赖 | 无 | pyright + import-linter 0 error |

## 7. 范围边界

**做**：内核拆分、渲染契约、画布、换行、横向滚动、Widget 树、运行时拆分、API 收敛、Tooling、文档 2.0。

**不做**：图片协议、文档流横向滚动、CSS/网格布局、消息总线、多窗口、远程/SSH 协议、i18n。

## 8. 术语

| 术语 | 含义 |
|---|---|
| **Value** | 不可变值：`Size` `Rect` `Pos` `Axis` `Cell` `Line` `Surface` `Scroll` `Section` |
| **Component** | 有 `render(Constraints) -> Surface` 的对象 |
| **Widget** | 有树、hooks、失效的组件基类 |
| **Section** | 文档中的一节：id + widget + placement + sizing |
| **Document** | 有序 Section 集合，地址化，可滚动 |
| **Fill** | 一个组件占满整个 pane 的 `PaneContent` |
| **Pane** | 一个矩形 + 一个 `PaneContent` + chrome |
| **Frame** | pane 分割树 + docks + overlays + focus |
| **Terminal** | 终端适配器：screen / input / resize / capability |
| **Runtime** | 时钟、定时器、失效、绘制、会话生命周期 |
| **Workspace** | frame / panes / content / overlays / focus 的门面 |
| **Router** | 有序 handler 链；派发顺序即数据 |
| **Host** | 控制器依赖的对象（Workspace 或 Runtime） |

## 9. 波次地图

| 波 | 主题 | 关键产出 | 依赖 |
|---|---|---|---|
| W0 | 契约与护栏 | 值类型 + 模拟器 + 工具 | 无 |
| W1 | 内核拆分 | kernel 零 I/O、Screen ABC | W0 |
| W2 | 渲染契约 | Surface/Constraints/Canvas/Fill | W1 |
| W2.5 | 换行策略 | WrapMode、59 处 fit 迁移 | W2 |
| W2.6 | 横向滚动 L1 | ScrollPanel(axis)、OVERFLOW | W2.5 |
| W3 | 树与交互 | Widget 树、hooks、keymap、focus | W1 |
| W4 | 运行时与调用面 | TerminalOptions、Runtime/Workspace/Router、API 收敛 | W3 |
| W5 | 文档与 2.0 | 文档重写、迁移表、发布 | 全部 |

> W2.5/W2.6 可与 W3 并行；W4 依赖 W3 的树与 hooks。

## 10. 决策索引

完整 ADR 见 `11-decisions.md`。要点：

- ADR-001 Surface 是唯一帧类型
- ADR-002 不做 measure/render 两阶段
- ADR-003 能力是属性，交互是 hooks
- ADR-004 删除 Revisioned
- ADR-005 kernel 零 I/O
- ADR-006 定时器按截止时间
- ADR-007 派发顺序是数据
- ADR-008 golden 语义化
- ADR-009 2.0 不兼容
- ADR-010 性能边界 ≤30fps
- ADR-011 可增长性不预置字段
- ADR-012 换行是内容策略
- ADR-013 Scroll 2D + L1
- ADR-014 Screen 是 ABC
- ADR-015 终端度量不进 Constraints
- ADR-016 值拥有行为
- ADR-017 一个概念一个门
- ADR-018 TerminalOptions + MouseMode
- ADR-019 返回 Section，位置用枚举
- ADR-020 Command 声明即接线
- ADR-021 Focus 从树推导
- ADR-022 一次性结果用 take()
- ADR-023 结果做拉取，不做 per-widget 推送

## 11. 风险摘要

- 自动失效漏掉就地修改 → `touch()` + `MOTUI_NO_CACHE=1` 对照。
- 单趟 sizing 的 fill 顺序 → 构造校验（至多一个 FILL、且在 FLOW 之后）。
- 一次性改 33k 行 → 分波 + 字节级门禁 + 每波可独立合并。
- golden 全变 → 换成语义网格，重录附差异分类。
- 性能回退 → framebench 阈值 + 每波跑。

详情见 `13-risks-migration.md`。

## 12. 验收

见 `12-acceptance.md`。最低线：

- 结构、质量、能力、性能、文档五组全绿；
- `examples/` 三个示例可执行（quickstart / snake / dashboard）；
- `take()` / `walk()` / `TerminalOptions` / `Section` / `Axis` / `Placement` 全部落地；
- 旧名（`take_result` / `Resultful` / `TUI` / `Revisioned` / `Themed` / `set_focus_targets`）不再存在。
