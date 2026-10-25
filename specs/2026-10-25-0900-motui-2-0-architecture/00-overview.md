# motui 2.0 · 架构重构（Epic）

> 启动：2026-10-25 09:00（UTC+8）
> 权威规格：`ref/source/`（用户提供的 `motui-2.0-specs`，冲突时以其为准）
> 基线：`main` @ `400773b`（motui 1.2.3）

## 1. 目标

把 motui 从「文档流 + 行 diff 的 TUI 工具箱」升级为「有几何、有画布、有节拍、可验证的终端 UI 内核」，并发布 **2.0.0**（不向后兼容）。

验收以 `ref/source/12-acceptance.md` 的五组（结构 / 质量 / 能力 / 性能 / 文档）为准。

## 2. 非目标

- 不保留 1.x shim / alias（ADR-009；迁移表是一等交付）。
- 不做图片/动图协议、文档流横向滚动、CSS/网格、消息总线、多窗口、SSH。
- 不 tag / 不 push / 不发 PyPI，除非用户明确要求。

## 3. 基线（开工实测，2026-10-25 09:00）

| 门禁 | 基线 |
|---|---|
| `uv run pytest -q -p no:cacheprovider` | **921 passed** |
| `uv run python tools/golden.py --check` | **57 topics match** |
| `uv run python tools/framebench.py` | render-hash `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379` |
| `uv run python -m motui < /dev/null` | exit 0 |
| `uv run python -m motui --pages` | exit 0，4059 行 |
| `ruff` / `pyright` / `lint-imports` | **尚未安装**（W0 引入） |

实测计数（与规格的对应）：`def render(` 48（规格 38 处 `render(width)` 指组件实现，含重载/协议，W2 逐个清点）；`.fit(` 59；`revision(` 79；`Revisioned` 44；`take_result` 119；`isinstance` 125；`def handle(` 22；`_CHILD_ATTRS` 3；`from .*core` 222。

## 4. 波次表

| 波 | 主题 | 分支 | 写入范围（文件级） | 依赖 | 门禁关键词 |
|---|---|---|---|---|---|
| W0a | 值类型 | `2.0/w0a-values` | `kernel/{geom,cell,text,layout}.py` + `tests/kernel/` | 无 | 旧测试全绿、字节不变 |
| W0b | 模拟器 + 工具 + 护栏 | `2.0/w0b-harness` | `testing/emulator.py`、`tools/{api,growth}.py`、`pyproject.toml`、CI | W0a | 工具可失败演练 |
| W1 | 内核拆分 | `2.0/w1-kernel` | 全仓 import + `kernel/*` + `terminal/*`，删 `core/` | W0 | demo 字节不变、kernel 零 I/O |
| W2a | Surface/Constraints 基础 | `2.0/w2a-surface` | `kernel/{cell,layout,paint,document}.py`、`kernel/frame.py`、`widgets/{text,layout,decor}.py` | W1 | 裁剪不变量 + 语义 golden |
| W2b | 数据/编辑组件迁移 | `2.0/w2b-widgets` | `widgets/{list,tree,table,choice,navlist,tabs,menubar,rows,strip,textfield,textbuf,combobox,autocomplete,dialog,form,action,indicators,diff,syntax}.py`、`widgets/markdown/*` | W2a | 全部 `render(Constraints)` |
| W2c | Canvas + Fill + app/overlays | `2.0/w2c-canvas` | `widgets/canvas.py`、`app/*`、`kernel/document.py`（Fill） | W2a | 80×24 ≤2.0ms、Fill 校验 |
| W2.5 | WrapMode | `2.0/w2.5-wrap` | `kernel/text.py`、`kernel/cell.py`、59 处 `.fit` 的组件 | W2 | 代码块/Input 差异分类 |
| W2.6 | 横向滚动 L1 | `2.0/w2.6-scrollx` | `kernel/layout.py`、`widgets/scroll.py`、`app/scrollbar.py`、hit | W2.5 | 宽表最右列可达 |
| W3a | Widget 基座 | `2.0/w3a-base` | `widgets/base.py`、`kernel/events.py`、删除反射/协议 | W1 | 树/hooks/keymap/focus |
| W3b | 组件族迁移 | `2.0/w3b-widgets` | 全部 `widgets/*` + `app/focus.py` | W3a | 行为 1:1、`handle` ≤3 |
| W4a | 运行时拆分 | `2.0/w4a-runtime` | `app/{terminal,runtime,workspace,router}.py`、`app/driver.py`、`app/application.py` | W3 | 定时器 ≤5%、`TUI` 删除 |
| W4b | 调用面收敛 | `2.0/w4b-api` | `app/{commands,workspace}.py`、`kernel/document.py`、`app/*` tiers | W4a | `Section`/`Axis`/`Placement`/`take`/`walk` |
| W5 | 文档与发布 | `2.0/w5-docs` | `README.md`、`docs/`、`examples/`、`CHANGELOG.md`、`pyproject.toml` | 全部 | 五组全绿、版本 2.0.0 |

### 并行与串行

- W0a → W0b 串行（工具要用值类型）。
- W1 单 worker（机械迁移，全仓 import 相交，不可并行）。
- W2a → W2b / W2c 串行起点；W2b 与 W2c 文件级不相交，可并行。
- W2.5 依赖 W2b（组件已迁移到 `Surface`）。
- W2.6 依赖 W2.5 的 `OVERFLOW`。
- W3a → W3b（基座先行；族迁移可在 W3b 内按文件分区并行）。
- W4a → W4b；W5 最后。
- 强耦合串行链允许同一 agent 连做多波（同一 worktree/分支），但每波单独 commit、单独跑门禁、单独写 handoff。

## 5. 全局不变量（每波都验）

1. `kernel` 不 import `os/sys/io/ctypes/termios/tty/select/asyncio`，也不 import `terminal/widgets/app`。
2. 只有 `terminal/ansi.py` 构造 escape；内容走 `Segment`/`Cell` 门。
3. 所有组件只有一个渲染签名：`render(Constraints) -> Surface`（W2 完成后）。
4. 进入 painter 的每一行都合法（`len ≤ Surface.width`）；超宽必须被裁剪。
5. 定时器只经 `Runtime`；pane 只经 `Workspace`；事件只经 `Router`；主题只经 `Widget.style()`。
6. `render()` 不读时钟；动画写状态再 `touch()`。
7. 不保留 shim；被替代的名字直接删除。
8. 测试随代码走：删模块同时删/迁测试。
9. 双平台（ubuntu/windows）+ Python 3.12 CI 必须绿；本地 3.13 只作快速反馈。
10. 不 tag / 不 push / 不发版。

## 6. 波次级门禁

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages > /tmp/pages.txt
# W0b 起追加：
uv run ruff check .
uv run pyright
uv run lint-imports
uv run python tools/api.py --check
uv run python tools/growth.py
```

- W0/W1：golden 必须逐字节不变；render-hash 必须等于基线 `a82f7968…`。
- W2 起：语义 golden 重录，差异必须附分类（裁剪 / 尺寸 / 换行 / 新行为）；旧字节 golden 标记 expected-change，W5 删除。
- 性能：framebench 任一指标劣化 >10% 阻断。

## 7. 共享文件所有者（并行波）

| 文件 | 所有者 |
|---|---|
| `src/motui/kernel/__init__.py` | W0a 建；W1 扩；后续波只由 lead 改 |
| `src/motui/kernel/text.py` | W2.5 |
| `src/motui/kernel/cell.py` | W2a（构造/裁剪）；W2.5（reflow） |
| `src/motui/kernel/layout.py` | W1（合并 viewport/scroll）；W2a（Constraints）；W2.6（2D） |
| `src/motui/kernel/document.py` | W1（Block→Section）；W2c（Fill） |
| `src/motui/widgets/__init__.py` | lead 统一改（每波合并后） |
| `src/motui/__init__.py` | W5（最终面） |
| `pyproject.toml` | W0b；W5 版本号 |
| `tests/golden/topics/*` | W2a 统一重录；后续波只增分类说明 |
| `docs/*`、`README.md`、`CHANGELOG.md` | W5 |

## 8. 接口索引

- `ref/interfaces.md`：本操作最终要落地的公开接口（每波合并后由 lead 回写现实）。
- `ref/repo-map.md`：仓库地图、真实命令、环境陷阱。

## 9. 诚实出口

- 规格中的 `38 处 render` 与实测 48 个 `def render(` 有口径差（含协议/重载/控制器）；以 `grep` 清单为准逐个迁移，不为了凑数字改签名。
- 若 `pyright --strict` 在 kernel 上无法在单波内达标：W0b 先以 `basic` + 明确 `# type: ignore` 清单交付，W2 前清零；必须在 handoff 记录剩余项。
- 若 Windows 本地无法安装 `pyright`（Node 依赖）：本地以 `ruff` + `lint-imports` + pytest 为主，CI 双平台仍必须配置；handoff 记录本地未跑项。
- 若某波门禁无法全绿：停止并上报，不在波内越界自救。

## 10. 状态

| 波 | 状态 |
|---|---|
| W0a | ⏳ |
| W0b | ⏳ |
| W1 | ⏳ |
| W2a | ⏳ |
| W2b | ⏳ |
| W2c | ⏳ |
| W2.5 | ⏳ |
| W2.6 | ⏳ |
| W3a | ⏳ |
| W3b | ⏳ |
| W4a | ⏳ |
| W4b | ⏳ |
| W5 | ⏳ |
