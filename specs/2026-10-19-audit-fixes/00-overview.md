# Spec audit-fixes · 审计缺陷修复包（波次 W1–W5）
> ⏳ 待执行 2026-10-19；基线 `main` @ `e77858c`（motui 1.1.6）。
> 门禁基线（改前）：`uv run pytest -q` = **1539 passed / 1 skipped**；`tools/golden.py --check` = **11 页全 match**；
> `tools/framebench.py` render-hash = `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`。
>
> 协议：subagent 在**主检出**直接作业（本机无 worktree 需求）；**不 commit、不建分支、不 push**——写范围按波次隔离
> （见各 W 禁触清单），lead 审完整 diff 后统一提交。spec 归 lead，agent 不更新任何 spec。
> 并发约束：并行波次跑 pytest 一律加 `-p no:cacheprovider`（避免 `.pytest_cache` 竞争）。
> 探针在 `ref/`，验收时直接运行，输出贴报告。

## 目标与范围

2026-10-19 对 1.1.6 全树做了分层审计（kernel / widgets / interaction+driver / docs+specs+tests），
每条头部结论都用独立探针复现过。总评：API / 命名 / 逻辑 MOSTLY UNIFORM，架构 UNIFORM；
3 个 HIGH + 7 个 MEDIUM。本包修掉它们，并记录唯一需要的决策撤销。

**做**：F1–F10 全部关闭（见下表）。F1 随 D1 的标记删除自然消灭，不需要单独修 ownership。

**不做**（D5，遗留清单）：`handle()` 返回值的两义（改它是 API 破坏，各 tier docstring 已自述语义）；
`Tabs`/`NavList` `move`/`select` 逐字重复（纯内部搅动）；`ScreenLayout.row_blocks` 与 `FrameTable`
双所有权机制（驱动内部重构，值得独立包）；`ComboBox` 不向内层 `Input` 转发协议（新 API 面）；
MORE_ABOVE（不存在，D1 删掉它唯一的同伴）。

**破坏性变更一项**：D1 从发布面移除 `motui.kernel.MORE_BELOW`。按 CONTRIBUTING 版本政策
（年轻库、干净切除、不设 shim；变更必须记录在案），W5 落 CHANGELOG 条目并打 `**Breaking**` 标签。
渲染字节**有意**移动：framebench 的 render-hash 与 3 页 golden 必须变，diff 即修复的证据
（CONTRIBUTING："A rendering fix that moves the golden frames is still a PATCH"）。

## Findings（本包关闭项）

| # | 级 | 问题 | 证据 |
|---|---|---|---|
| F1 | high | MORE_BELOW 覆盖末行但所有权表仍声称归属被挤掉的 block——点标记行派发给不可见 block，选择高亮画在标记上 | `kernel/viewport.py:194-195` vs `:200-205`；复现：`scroll_up(2)` 后 `hit_test` 标记行答 `('b27', 0, 0)` |
| F2 | high | `Dialog.revision()` 漏掉 render 读取的 5 个可变行输入，热缓存后服务陈旧行 | `widgets/dialog.py:433-448`；复现：title/width/frame/shade/align 五突变全 stale |
| F3 | high | `Palette` 无 `detach()`，其 Modal 注册的 frame overlay 永不可注销 | `interaction/palette.py:142-236`；八个兄弟全有 |
| F4 | med | `Diff` 非 `Revisioned`，sealed 块按宽度冻结，"never a stale frame" 承诺落空 | `widgets/diff.py:357-371` |
| F5 | med | revision()  rollout 未达 Tabs/NavList/Slider/ProgressBar/Collapsible——sealed 块 hover/focus 不落屏 | `specs/2026-10-17-render-cost/00-overview.md` D4 |
| F6 | med | `Find.detach()` 无失效标志，卸载后仍吃键盘 | `interaction/find.py:161-169` |
| F7 | med | gesture 直接 invalidate，与自家 docstring 委托的 facade 冗余双重 | `interaction/gesture.py:572` vs `app.py:856` |
| F8 | med | `__version__` 兜底硬编码 `"1.1.0"`，发行版是 1.1.6，无测试钉住 | `src/motui/__init__.py:82` |
| F9 | med | 文档不准：DESIGN.md:87 只列 32/34；COMPONENTS.md:79 指向不存在的 README 列表；text.py:372 的 (D2) 引错决策；app.py:539 / pointer.py:187 的 "D10" 无此决策 | docs 域 |
| F10 | med | "styles resolve once at construction" 无任何测试 | `docs/DESIGN.md:175-182` |

## 拍板决策（照抄执行，不现场猜）

| # | 决策 | 取值 |
|---|---|---|
| D1 | 标记去留 | **整体删除**（撤销 `specs/2026-10-06-frame-chrome/00-overview.md` 的 D8）。理由：内核唯一绕过 Theme 系统的视觉（裸 `MUTED` 常量、无 theme 字段）、零 API（不可配置/替换/本地化/按 pane 关闭）、静默偷占一行内容、挂 Scrollbar 处即冗余（demo 就挂着）、且是 F1 的唯一来源。全屏 TUI 框架（Textual/Bubble Tea/ratatui）把滚动指示放 chrome 组件而非渲染核心；分页器（less）是另一物种。滚动反馈交还 host 的 chrome，符合 "ships parts, not an application" 宪章。删除写入即删除 F1，不需修 ownership |
| D2 | Revisioned 家族 | 从根上修：Dialog 快照补全全部可变行输入并稳定 body 快照；Diff 实现 `revision()`；五个组件补齐 rollout（落实 render-cost D4 的剩余部分）。每个修复先落"sealed 块突变"复现测试再动手；docstring 承诺与快照必须一致 |
| D3 | 生命周期/版本 | `Palette.detach()` 委托其 modal；`Find.detach()`  inert 化；gesture 只经 facade invalidate 一次；版本兜底对齐发行版并有测试钉住 |
| D4 | 文档与未测不变式 | 文档描述现实；存活的 (Dn) 引用都能解析到本 spec 组的正确决策；补一条测试钉住"构造时解析一次" |
| D5 | 不做 | 见「目标与范围·不做」 |

## 波次、依赖与写范围

| 波次 | 内容 | 依赖 | 写范围 |
|---|---|---|---|
| W1 | 标记删除（D1/F1） | 无 | `src/motui/kernel/{viewport,__init__}.py`、`tests/{test_viewport,test_painter,test_app,test_api_root}.py`、`tests/golden/pages/{themes,streaming,notes}.txt`（仅经 golden.py）、`docs/DESIGN.md`（仅标记相关行） |
| W2 | Revisioned 正确性（D2/F2/F4/F5） | 无 | `src/motui/widgets/{dialog,diff,tabs,navlist,indicators,collapsible}.py` + 对应测试文件 |
| W3 | 生命周期与版本（D3/F3/F6/F7/F8） | 无 | `src/motui/interaction/{palette,find,gesture}.py`、`src/motui/__init__.py` + 对应测试文件 |
| W4 | 文档与不变式测试（D4/F9/F10） | **W1 后**（同改 DESIGN.md） | `docs/{DESIGN,COMPONENTS}.md`、三处纯注释 docstring、`tests/test_theme.py` |
| W5 | 总门禁 + CHANGELOG | W1–W4 后 | `CHANGELOG.md`（仅追加条目）；其余只读 |

W1–W3 并行（写范围两两不交）；W4 等 W1；W5 收口。

## 总验收（W5 逐项贴真实输出）

1. `uv run pytest -q`：总数 > 1539，0 failed；新增测试覆盖 F1–F10 每个修复
2. `uv run python tools/golden.py --check` 绿；改动的只有 themes/streaming/notes 三页的窗口末行
3. `uv run python tools/framebench.py`：render-hash **已变**（贴新旧两值），其余时序行无异常量变
4. `uv run python -m motui < /dev/null` 与 `--pages` 均 exit 0
5. `ref/probe_hover_click.py`：1740 格 0 分歧；`ref/scan_layers.py`：零向上依赖
6. `ref/probe_marker.py`：标记不存在、滚动后末行 owner 是真实 block
7. `ref/probe_dialog_matrix.py`：五突变全 fresh
8. `git diff main --stat` 范围 = 各波写范围并集，无蠕变；探针不留仓（在 `specs/.../ref/` 或 `%TEMP%`）
