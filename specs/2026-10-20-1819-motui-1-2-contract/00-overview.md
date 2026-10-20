# Spec motui 1.2 contract · 全面重构（W0–W7）
> 启动：2026-10-20 18:19（UTC+8）；基线 `main` @ `d279fb2`；motui 1.1.8。
> 门禁基线（改前）：`uv run pytest -q` = **1699 passed / 1 skipped**（6.28s）；
> `uv run python tools/golden.py --check` = **11 页全 match**；
> `uv run python tools/framebench.py` render-hash = `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`
> （2026-10-20 复核；`framebench.py` 文档里的 `de48...` 是更早的基线，已过期）。
>
> W1 合并后（2026-10-20，`a84bcf7`）：`uv run pytest -q -p no:cacheprovider` = **1719 passed / 2 skipped**；
> golden 11 页 match；render-hash 仍为 `f872...`。
> W2 合并后（2026-10-20，`041e270`）：**1733 passed / 2 skipped**；golden 11 页；render-hash 仍为 `f872...`。
> W3 合并后（2026-10-20）：**1742 passed / 2 skipped**；golden 11 页；render-hash 仍为 `f872...`。
> W4a 合并后（2026-10-20）：**1777 passed / 2 skipped**；golden 11 页；render-hash 仍为 `f872...`。
> W4b 合并后（2026-10-20）：**1811 passed / 2 skipped**；golden 11 页；render-hash 仍为 `f872...`。
> W5a 合并后（2026-10-20）：**1900 passed / 2 skipped**；golden 11 页；render-hash 仍为 `f872...`。
> W6 合并后（2026-10-20）：**1926 passed / 2 skipped**；golden 11 页；render-hash 仍为 `f872...`。
> W5b 合并后（2026-10-20）：**1942 passed / 2 skipped**；golden 11 页；render-hash 仍为 `f872...`。
>
> 协议：lead 在 `main` 写 spec / 契约 / 门禁；worker 在**仓库外 worktree**作业，分支从前一刻 main 创建，
> 每波一个分支、一个 handoff、一次 `--no-ff` 合并。worker 不 merge / push / tag / 碰主检出。
> spec 归 lead，worker 只写自己名下的 `handoff/W<N>-<agent>.md`。
>
> **门禁粒度（用户 2026-10-20 指示）**：不要求每个 commit 独立可绿；只要求每个波次的 HEAD、以及合并前后
> 的全量门禁可执行。波内 commit 允许是重构中间态。

## 目标与范围

1.2.0 是一次 **契约重置 + 机制收敛 + 能力补齐**，不是推倒重写。保留 document-of-blocks +
viewport scrollback + frame/pane + diffed painter + interaction tiers 的骨架；清掉同一概念的多套实现、
分层环和会伤到用户的契约级 bug；补齐“完整 TUI 库”缺的组合层。

**做**：事件模型与终端解码；driver 生命周期与坐标/作用域；值语义与缓存所有权；组件契约与共享基类；
`ScrollView` / `Form` / `Menu` / `FocusManager` / `CommandRegistry` / `Clipboard`；交互层解耦；文档、测试、
打包收口。

**不做**：Textual 式 widget tree；图表/日期选择器/可拖拽分隔条/跨 pane 选择/水平滚轮；
向后兼容 shim；在 1.2.0 内重写 Markdown 引擎或布局引擎。

## 拍板决策（照抄执行，不在工单里现场猜）

| # | 决策 | 取值 |
|---|---|---|
| D1 | 架构身份 | 保留 document-of-blocks；新增能力用组合层，不改渲染核心模型 |
| D2 | 事件模型 | `Event` 基类；`KeyEvent` / `MouseEvent` / `PasteEvent` / `ResizeEvent` / `FocusEvent`；`MouseEvent` **不再继承** `KeyEvent`；`KeySource` → `EventSource`；`read_key` → `read_event` |
| D3 | 键名语法 | 可打印键 `key` = 字符本身；特殊键 `enter`/`escape`/`tab`/`backspace`/`insert`/`delete`/`home`/`end`/`page_up`/`page_down`/`up`/`down`/`left`/`right`/`space`/`f1`..`f24`；和弦前缀顺序 `c-` → `a-` → `s-`（如 `c-s-left`、`a-s-up`）；`\r` → `enter`，`\n` → `c-j`（修 `EDITOR_SUBMIT_KEYMAP`） |
| D4 | 鼠标模型 | `MouseEvent.button` 是字符串（`left`/`middle`/`right`/`none`/`wheel_up`/`wheel_down`/`wheel_left`/`wheel_right`）；`kind` 是 `press`/`release`/`motion`/`wheel`；带 `modifiers` |
| D5 | 结果模型 | 公开的一次性 `chosen` 改为 `take_result() -> T \| None`（读取并清空）；可选 `on_activate` 回调；组件不再各自定义“读一次”规则 |
| D6 | 驱动契约 | `run()` / `run_async()` / `run_session(body)`；`exit()`；`refresh()`；`read_event()`；`hit()` / `hit_leaf()` / `pane_at()`；`dock()` / `undock()`；document 操作统一 pane 作用域 |
| D7 | 值语义 | `Pane` 改普通可变类（删除 `frozen=True` + `object.__setattr__`）；`ScreenLayout` / `Theme` 表 / `Style`/`Segment` 真正不可变；一个 row-cache 所有者（`Block.rows`） |
| D8 | 分层 | `interaction` 只依赖 `kernel` 的 `Host` protocol，不依赖 `app`；`interaction` 不直接 import `widgets`（输入控件由构造注入或移到组合层） |
| D9 | 组件范围 | 新增 `ScrollView`、`Form`/`Field`、`MenuBar`/`ContextMenu`、`FocusManager`、`CommandRegistry`、`Clipboard`、`Disableable`/`ReadOnly`；不新增图表/日期/网格/拖拽分隔条 |
| D10 | 版本与兼容 | 1.2.0 是年度 MAJOR；删除的公开名不留 alias/shim；文档与代码同 commit；发版由用户指令触发 |
| D11 | demo | 保留随 wheel 发布的 showcase；1.2.0 不改名、不拆包，只跟随 API 迁移 |

## 全局不变量

1. 所有坐标 0-based；越界统一 `None`，不 clamp。
2. 依赖方向：`kernel` → `keys` → `widgets` → `interaction` → `app`；`interaction` 不反向依赖 `app`/`widgets`。
3. `render(width)` 除文档化缓存外无副作用；`Revisioned.revision()` 覆盖 render 读取的全部可变输入。
4. 公共 facade 一个名字一个家；`tests/test_api_root.py` 精确 pin。
5. 不引入兼容 shim；删除即删除。
6. 库与测试不 sleep；时间只经 `tui.clock()`。
7. 渲染字节变化必须由 golden 重录 + commit message 解释。
8. 文档与代码同 commit；层数/导出表/组件目录不得漂移。

## 波次、依赖与写范围

| 波次 | 内容 | 依赖 | 写范围（主） |
|---|---|---|---|
| **W0** | 契约、repo-map、API 对照、spec 落盘 | 无 | `specs/<group>/**`、`docs/CONTRACT.md`（lead 在 main 完成） |
| **W1** | 事件模型 + 终端解码 + source 生命周期 | W0 | `kernel/events.py`、`keys/**`、`app.py`（仅事件命名/read_event）、`interaction/**`、`widgets/**`、`demo/**`、`testing.py`、`tests/**`、事件相关文档 |
| **W2** | driver 生命周期 + 坐标/作用域 + dock/frame 修复 | W1 | `app.py`、`kernel/frame.py`、`kernel/viewport.py`、`kernel/screen.py`、`tests/{test_app,test_frame,test_viewport,test_painter,test_screen}.py` |
| **W3** | 值语义 + 缓存所有权 + selection 主题 | W2 | `kernel/{frame,viewport,theme,style,lines,block,selection}.py`、`interaction/find.py`、相关测试 |
| **W4a** | 组件结果契约 + action/choice/input/modal + P0 | W3 | `widgets/{action,choice,autocomplete,combobox,textfield,textbuf,dialog,collapsible,indicators}.py`、`widgets/markdown/component.py`、`kernel/{block,lines}.py`（仅协议/Text 结果）、相关测试、demo |
| **W4b** | row views + RowBands + rows/decor revision | W4a | `widgets/{list,table,tree,tabs,navlist,bands,decor,rows,layout,delegate}.py`、相关测试、demo |
| **W5a** | 组合层核心：`ScrollView` / `Form`+`Field` / `CommandRegistry` / `Clipboard` | W4b | 新文件为主；`widgets/__init__.py`、`kernel/__init__.py`、`motui/commands.py`、`tests/**` |
| **W5b** | 菜单层：`MenuBar`/`ContextMenu`（demo exhibits 与 golden 归 W7） | W6 | `widgets/menubar.py`（新）、`widgets/__init__.py`、`tests/**`、docs |
| **W6** | 交互层解耦 + Host protocol + FocusManager + overlay/focus/modal 栈 | W2, W4b | `interaction/**`、`app.py`（Host 实现）、`kernel/host.py`（新）、`kernel/clipboard.py` 调用点、相关测试 |
| **W7** | 文档、demo、版本、发布门禁 | W1–W6 | `docs/**`、`README.md`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`、`tests/golden/**`（仅经工具） |

W1 与 W3 可并行（写范围需重新核对）；W2 依赖 W1；W4 依赖 W3；W5/W6 在 W4 后；W7 收口。

## 两级门禁

**commit 级**（每个 commit）：`uv run pytest -q -p no:cacheprovider`（相关文件/全量，仓库小，直接全量）。

**波次级**（合并前 + 合并后各一次）：
1. `uv run pytest -q -p no:cacheprovider`：0 failed，贴总数
2. `uv run python tools/golden.py --check`：11 页全 match；有意变化须列页与行
3. `uv run python tools/framebench.py`：exit 0，贴 render-hash 与关键时序
4. `uv run python -m motui < /dev/null`：exit 0
5. `uv run python -m motui --pages`：exit 0
6. `uv run python -c "import motui, motui.kernel, motui.keys, motui.widgets, motui.interaction"`：无导入错误/环
7. `git diff --stat main...HEAD`：范围 = 工单写范围并集，无蠕变

W2 起追加：
8. `uv run python -c "from motui.kernel import Event, KeyEvent, MouseEvent, PasteEvent, ResizeEvent, FocusEvent"`（事件契约）
9. `uv run python -c "from motui import TUI; assert hasattr(TUI, 'read_event') and hasattr(TUI, 'exit') and hasattr(TUI, 'refresh')"`（driver 契约）

## 共享文件所有者

| 文件 | 所有者 | 规则 |
|---|---|---|
| `src/motui/kernel/events.py` | W1 | 其他波只读 |
| `src/motui/app.py` | W1（事件命名）→ W2（driver） | 串行；W2 读 W1 handoff |
| `src/motui/kernel/frame.py` | W2 | W6 只读；W6 的 Host/overlay 改动先申请 |
| `src/motui/widgets/**` | W4/W5 | W6 不直接改；需要时由 lead 追加例外 |
| `src/motui/interaction/**` | W6 | W4 只改 `find.py` 的 selection 主题 |
| `docs/CONTRACT.md` | lead | worker 只读 |
| `pyproject.toml` / `uv.lock` | lead | worker 禁触；W7 由 lead 执行 |
| `tests/golden/**` | lead/工具 | 只能经 `tools/golden.py --update` |

## 接口索引

- 事件/键名/鼠标/来源：`ref/interfaces.md` §1
- driver/坐标/pane/dock：`ref/interfaces.md` §2（W2 冻结）
- 组件/结果/行带/focus：`ref/interfaces.md` §3（W4 冻结）
- 分层/Host：`ref/interfaces.md` §4（W6 冻结）
- 命名对照：`ref/interfaces.md` §5
- 规范正文：`docs/CONTRACT.md`

## 状态

| 波次 | 状态 | 分支 | 合并 commit |
|---|---|---|---|
| W0 | ✅ 2026-10-20 | main | `3d8878f` / `bb2a6e9` |
| W1 | ✅ 2026-10-20 | `w1-events` | `a84bcf7` |
| W2 | ✅ 2026-10-20 | `w2-driver` | `041e270` |
| W3 | ✅ 2026-10-20 | `w3-values` | `1c7069f` |
| W4a | ✅ 2026-10-20 | `w4a-components` | `aa362e4` |
| W4b | ✅ 2026-10-20 | `w4b-rowviews` | `d819f74` |
| W5a | ✅ 2026-10-20 | `w5a-composition` | `2dad1f5` |
| W6 | ✅ 2026-10-20 | `w6-interaction` | `33ad1a3` |
| W5b | ✅ 2026-10-20 | `w5b-menus` | `14f224f` |
| W7a | 进行中 | `w7a-demo` | — |
| W7b | 待执行 | — | — |
