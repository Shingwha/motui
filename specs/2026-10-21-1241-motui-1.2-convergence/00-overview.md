# motui 1.2.0 — convergence refactor

> 启动：2026-10-21 12:41（UTC+8）
> 基线：`cbebdf9 demo: call the command palette by its 2.0 name`
> 目标版本：1.2.0（把当前 main 上的 2.0 工作并入 1.2 发布线；发布动作不在本组内）

## 目标

把 motui 从“分层但公共表面积过大、同一状态多个所有者”收敛成一套**简洁、清晰、可自定义**的 1.2.0 API：

1. **三层包结构**：`motui.core`（值、事件、输入、文档、渲染）、`motui.widgets`（组件、Markdown、语法高亮）、`motui.app`（App/TUI、控制器）。删除 `kernel`、`keys`、`interaction`、`commands` 四个旧命名空间。
2. **双档 API**：`App` 负责默认编排（焦点、指针、手势、滚轮路由、overlay、快捷键），`TUI` 保留完全显式的底层驱动。`TUI.read_event()` 恢复为纯事件读取，不再隐式消费 wheel/page 或执行焦点策略。
3. **一个状态一个所有者**：`ScrollState` 统一 Viewport / ScrollView / Scrollbar 的 offset、clamp、reveal 和 thumb 公式；`Cursor` 统一 list-like 控件的 disabled 跳过、clamp/wrap 和窗口计算。
4. **Widget 基类 + 样式组覆盖**：`Widget` 提供可选的交互动词默认实现；`Component` 仍只要求 `render(width)`。控件的 4-6 个 `*_style` 参数收进一个 `Styles` 值（复用 `TextStyles`/`RowStyles`/`ControlStyles`/`BorderStyles` 等主题组），主题在 render 时解析，换主题不重建控件。
5. **修掉两个可见缺陷**：`ScrollView(bar=True)` 的 bar 可拖动、可滚轮；Markdown/独立 `Table` 支持单元格自动换行并保留 inline style。
6. **删除意外抽象/兼容残留**：`Host`、`QueryInput`/`FilterList`/`OptionLike`、`make_input`/`make_autocomplete`、`Delegate`、`BlockState`/`seal`、`DEFAULT_HEADER_STYLE`、`COLORBGBG`、`CommandPalette` 的纯转发、`Text` 的双出口。

## 非目标

- 不改成 Textual 式 retained widget tree / 消息冒泡。
- 不改成 Elm-style immediate mode。
- 不新增与本次收敛无关的组件或功能。
- 不写兼容 shim、别名、转发模块、`DeprecationWarning` 桥。
- 不主动 push、打 tag、发版。

## 已拍板决策

| # | 决策 | 依据 |
|---|---|---|
| D1 | 版本号定为 **1.2.0**，当前 `pyproject.toml` 的 2.0.0 在 W6 改为 1.2.0 | 用户明确指定；当前没有 v2 tag，`dist/` 只有 1.1.0 |
| D2 | 保留文档模型（Document/Component/Line），不引入父子事件树 | 这是 motui 的可测试性与 headless 能力的来源 |
| D3 | `App`（默认编排）+ `TUI`（显式底层）双档 | 简单场景少写代码，高级场景不丢控制 |
| D4 | 控件统一用 `Widget` 基类 + `Styles` 组覆盖；保留全部主题旋钮 | 降低构造器参数，同时保持可自定义性 |
| D5 | 删除旧命名空间与兼容代码，不做过渡层 | 用户明确要求 1.2.0 API 无兼容负担 |
| D6 | 测试“必要才加”：现有 889 测试 + golden 作为回归红线；只为新行为/缺陷修补充最小用例 | 用户明确要求非必要不加测试 |

## 波次表

| 波 | 名称 | 依赖 | 写入范围（文件级） | 门禁 |
|---|---|---|---|---|
| W1 | 核心状态收敛 | 无 | `kernel/viewport.py`、`kernel/scroll.py`(新)、`kernel/cursor.py`、`kernel/block.py`、`kernel/theme.py`、`widgets/{scroll,list,choice,table,tree,navlist,tabs,menubar,strip,autocomplete,combobox,form,collapsible,delegate}.py`、`interaction/scrollbar.py`、`app.py`、对应 tests/demo | 全量 pytest + golden + framebench + 两个 demo 入口 |
| W2 | 包与运行时合并 | W1 | `src/motui/**`（移动/导入）、`tests/**` 导入、`tools/**`、docs 中的路径 | 全量 pytest + golden + framebench + demo |
| W3 | Widget API 收敛 | W2 | `core/widget.py`(新)、`core/theme.py`、`widgets/**`、`demo/topics/**`、`demo/shell.py`、tests 中控件构造 | 全量 pytest + golden + demo |
| W4 | App 编排 + demo 重写 | W3 | `app/**`、`demo/**`、`testing.py`、`tests/app/**` | 全量 pytest + 新 App 冒烟 + demo |
| W5a | Table 换行 | W4 | `widgets/table.py`、`widgets/markdown/tables.py`、`widgets/markdown/context.py`、对应 tests/demo | 全量 pytest + golden（必要处重录） |
| W5b | ScrollView bar 输入 + wheel 路由 | W4 | `widgets/scroll.py`、`app/**` 的 wheel 路由、`demo/topics/interactions.py`、对应 tests | 全量 pytest + headless 拖动/滚轮用例 |
| W6 | 文档、API、版本 | W5 | `README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`src/motui/__init__.py`、`tests/test_api.py` | 全量 pytest + golden + framebench + demo + API 快照 |

W5a / W5b 可并行，其余串行。W1-W4 是紧耦合链，允许同一 worker 连做，但每波单独 commit、单独 handoff、单独门禁。

- W1 ✅ 2026-10-21 @ merge `5444cb2`（885 tests / 57 golden / hash 不变）
- W2 ✅ 2026-10-21 @ merge `0c25bc2`（879 tests / 57 golden / hash 不变）
- W3a 进行中（Widget/Styles 基础 + action 家族）

## 全局不变量

1. 依赖单向：`core` 不 import 上层；`widgets` 只 import `core`；`app` 可以 import `core` + `widgets`；`testing` import `core` + `app`。删除 `kernel`/`keys`/`interaction`/`commands` 命名空间后，任何 `motui.kernel` / `motui.keys` / `motui.interaction` / `motui.commands` import 都是失败。
2. 一个状态一个所有者：不得出现第二套 offset/clamp/thumb 公式；不得出现第二套 disabled-cursor 步进循环。
3. `TUI.read_event()` 从 W4 起只读取事件：不消费 wheel/page，不执行 `focus_policy`，不调用 `scroll_keys`。
4. 主题是活输入：`Widget.theme` 变更后，下一次 render 必须反映新主题；不得要求宿主重建控件。显式 `theme=` 的控件保持本地覆盖。
5. 无兼容代码：删除的名字直接删除；不保留 alias、转发模块、`__getattr__` 桥、旧参数。
6. 渲染红线：除 W1 的 ScrollView thumb 长度变化 / `Delegate` topic 删除、W5a 的换行、W3/W4 明确允许的视觉变化外，golden 帧必须逐字节不变。任何 golden 变化必须在 commit message 中逐帧解释。
7. demo 是验收面：`python -m motui` 的 headless replay、`--pages`、golden 必须继续工作；W4 后 `Session` 行数应显著下降（目标 ≤ 250 行）。
8. 测试红线：不为内部实现细节新增测试；优先扩展现有 test 文件；新行为没有现有覆盖时才加最小用例。删除功能时同步删除对应测试，不保留“以防万一”的测试。

## 共享文件所有者

| 文件 | 所有者 | 说明 |
|---|---|---|
| `src/motui/__init__.py` | lead/W6 | 最终 curated root |
| `src/motui/core/__init__.py` | W2 | 合并 kernel+keys 的导出面 |
| `src/motui/widgets/__init__.py` | W3 | 组件库导出面 |
| `src/motui/app/__init__.py` | W2/W4 | 驱动 + 控制器 + App 导出面 |
| `docs/**`、`README.md`、`CHANGELOG.md`、`pyproject.toml` | lead/W6 | 最后一波统一更新 |
| `specs/**` | lead | worker 只写自己名下的 handoff |

## 回归红线（每波必须真实跑）

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

Windows/Git Bash 环境下若 `uv` 不可用，用 `./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` 等价执行，并在 handoff 中写明实际命令。

## 接口索引

- 当前契约草案：`ref/interfaces.md`
- 仓库地图：`ref/repo-map.md`
- W1 详单：`01-W1-core-state.md`
- W2-W6 占位：`02-W2-runtime.md` ... `06-W6-release.md`（JIT 补全）
