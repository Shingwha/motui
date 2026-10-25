# motui 2.0 重构 Specs

> 状态：Draft（可直接开工）
> 目标版本：**2.0**（不承诺向后兼容）
> 基线：`motui 1.2.3`（`src/` 33,233 行）
> 长文背景：`archive/motui-2.0-架构重构方案.md`（1,828 行，含完整论证与实测数据）
> 代码根：仓库 `src/motui/`

## 1. 这是什么

这是一组**多级、可执行的 spec**，不是设计散文。每一级回答不同的问题：

| 级别 | 目录 | 回答的问题 |
|---|---|---|
| L0 总纲 | `00-overview.md` | 为什么重构、做到什么算成功 |
| L1 架构 | `01-architecture.md` | 目标分层、模块、依赖、扩展点 |
| L1 契约 | `02-core-contracts.md` … `09-testing-tooling.md` | 每个领域的契约、理由、做法 |
| L2 波次 | `10-waves/W*.md` | 这一波具体改哪些文件、按什么顺序、怎么验 |
| L3 收口 | `11-decisions.md` `12-acceptance.md` `13-risks-migration.md` | 决策记录、验收、风险与迁移 |

## 2. 怎么用

1. 先读 `00-overview.md`，确认目标与边界；
2. 再读 `01-architecture.md` 与 `05-api-surface.md`，建立全局图；
3. 开工时**只读当前波次 + 它引用的 L1 spec**，不要一次读完全部；
4. 每一波结束必须过 `12-acceptance.md` 里对应的门禁；
5. 任何与 spec 不一致的实现，先改 spec 再改代码（spec 是唯一事实来源）。

## 3. 状态板

| Spec | 内容 | 状态 |
|---|---|---|
| `00-overview.md` | 目标/非目标/原则/指标 | ✅ ready |
| `01-architecture.md` | 分层/模块/依赖/所有权 | ✅ ready |
| `02-core-contracts.md` | 几何/行/帧/文档/滚动/绘制 | ✅ ready |
| `03-interaction.md` | Widget 树/hooks/keymap/focus/router | ✅ ready |
| `04-runtime.md` | Terminal/Runtime/Workspace/定时器 | ✅ ready |
| `05-api-surface.md` | 公开面/命名/返回类型/扩展规则 | ✅ ready |
| `06-widgets.md` | 组件族重构与合并 | ✅ ready |
| `07-theme-style.md` | Theme/Styles/Glyphs 单一解析 | ✅ ready |
| `08-terminal-io.md` | 终端 I/O、输入、剪贴板 | ✅ ready |
| `09-testing-tooling.md` | 模拟器/护栏/金标 | ✅ ready |
| `10-waves/W0-harness.md` | 契约与护栏 | ✅ ready |
| `10-waves/W1-kernel-split.md` | 内核拆分 | ✅ ready |
| `10-waves/W2-render-contract.md` | 渲染契约 + Canvas | ✅ ready |
| `10-waves/W2.5-wrapmode.md` | 换行策略 | ✅ ready |
| `10-waves/W2.6-horizontal-scroll.md` | 横向滚动 L1 | ✅ ready |
| `10-waves/W3-tree-interaction.md` | 树与交互 | ✅ ready |
| `10-waves/W4-runtime-api.md` | 运行时与调用面 | ✅ ready |
| `10-waves/W5-docs-release.md` | 文档与 2.0 | ✅ ready |
| `11-decisions.md` | ADR-001…023 | ✅ ready |
| `12-acceptance.md` | 定义完成/门禁/基准 | ✅ ready |
| `13-risks-migration.md` | 风险 + 1.x→2.0 迁移 | ✅ ready |

## 4. 执行协议

- **一波一分支**：`2.0/w0-harness`、`2.0/w1-kernel` …；合并前 rebase 到上一波。
- **每波必须可独立合并**：不要求全部波次完成才可用。
- **不留 shim**：被替代的名字直接删除；迁移表见 `13-risks-migration.md`。
- **字节级门禁**：W0/W1 必须 golden 逐字节不变；W2 起允许变化但必须附差异分类报告。
- **测试随代码走**：删除一个模块，同时删除/迁移它的测试，不允许“暂时跳过”。
- **文档同步**：公开 API 变化必须同时更新 `docs/CONTRACT.md` 与 `docs/COMPONENTS.md`（W5 统一重写）。

## 5. 门禁命令

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/framebench.py
uv run python tools/golden.py --check
uv run python tools/api.py --check          # W0 新增
uv run python tools/growth.py               # W0 新增
uv run python -m motui < /dev/null
uv run python -m motui --pages
# W0 起追加：
ruff check .
pyright
lint-imports
```

> 平台：CI 同时跑 `ubuntu-latest` 与 `windows-latest`；所有门禁必须在两个平台通过。

## 6. 目录

```
motui-2.0-specs/
├── README.md
├── 00-overview.md
├── 01-architecture.md
├── 02-core-contracts.md
├── 03-interaction.md
├── 04-runtime.md
├── 05-api-surface.md
├── 06-widgets.md
├── 07-theme-style.md
├── 08-terminal-io.md
├── 09-testing-tooling.md
├── 10-waves/
│   ├── README.md
│   ├── W0-harness.md
│   ├── W1-kernel-split.md
│   ├── W2-render-contract.md
│   ├── W2.5-wrapmode.md
│   ├── W2.6-horizontal-scroll.md
│   ├── W3-tree-interaction.md
│   ├── W4-runtime-api.md
│   └── W5-docs-release.md
├── 11-decisions.md
├── 12-acceptance.md
├── 13-risks-migration.md
└── archive/
    └── motui-2.0-架构重构方案.md
```

## 7. 不可协商的七条

1. `kernel` 不 import `os/sys/io/ctypes`，也不 import `terminal/widgets/app`。
2. 所有组件只有一个渲染签名：`render(Constraints) -> Surface`。
3. 进入 painter 的每一行都合法（宽度 ≤ `Surface.width`），超宽内容必须被裁剪。
4. 内容永远不能携带 escape；只有 `terminal/` 构造字节。
5. 终端输出只经 `Screen`；定时器只经 `Runtime`；pane 只经 `Workspace`。
6. `render()` 不读时钟；动画只能写状态再 `touch()`。
7. 不为未实现的功能预置字段；可增长性靠所有权与构造方式（见 `02`）。

## 8. 与旧文档的关系

`archive/motui-2.0-架构重构方案.md` 是这次重构的**论证长文**（包含全部实测数字、被否决方案、历史细节）。本目录是它的**执行化拆解**：

- 冲突时以本目录为准；
- 需要“为什么”的完整推导时回查 archive；
- archive 不再更新，只作为背景资料保留。
