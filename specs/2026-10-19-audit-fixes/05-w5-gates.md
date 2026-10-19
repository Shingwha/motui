# Spec audit-fixes · W5：总门禁与 CHANGELOG（收口）
> ⏳ 待执行；前置：**W1–W4 全部完成**。深读：`00-overview.md`（总验收清单是权威）。
> 本波基本只读；唯一写的是 `CHANGELOG.md` 追加条目。不修任何代码——发现问题回去找对应波次。

## 目标

按 CONTRIBUTING 的门禁逐项验靶，记录本包**有意**造成的渲染移动，落破坏性变更记录。

## 工单（按序；本波不 commit）

### T1 套件

`uv run pytest -q -p no:cacheprovider`：贴总数（预期 > 1539 passed / 1 skipped，新增来自 W2/W3/W4）。
任何失败：定位到波次，报告，不回退别人的活。

### T2 golden

`uv run python tools/golden.py --check` 必须绿。若不绿：说明 W1 的重录不完整或有第二处渲染移动——
报告差异页与差异行，**不**自己 `--update`（重录归 W1 范围；若确需补录，先报告差异证据）。

### T3 framebench（记录有意移动）

`uv run python tools/framebench.py`：贴全表。render-hash **预期已变**（标记删除改变了
滚动后的末行渲染——这就是修复的证据，CONTRIBUTING："the frame diff is the evidence of the fix"）。
贴改前 `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122` 与改后值；
其余时序行与改前同量级即可，异常量变 = 报告。

### T4 两条 demo 路

`uv run python -m motui < /dev/null` 与 `uv run python -m motui --pages`：均 exit 0，贴退出码。

### T5 探针四连（`ref/` 里的脚本，直接跑，贴输出）

- `ref/probe_marker.py`：标记不存在；滚动后末行 owner 是真实 block（F1 关闭的行为证据）。
- `ref/probe_dialog_matrix.py`：五突变全 fresh（F2 关闭）。
- `ref/probe_hover_click.py`：全交互组件 hover 命中域 ≡ click 命中域（回归护栏，1740 格 0 分歧）。
- `ref/scan_layers.py`：层依赖零向上（架构护栏）。

### T6 diff 总审

`git diff main --stat`：范围 = W1–W4 写范围并集（overview 的波次表），无范围外文件。
`git status --porcelain`：无散落文件（探针、缓存、临时脚本一律不许留仓——探针在 `specs/.../ref/`）。

### T7 CHANGELOG（本波唯一写入）

按仓库现有格式在 `CHANGELOG.md` 顶部追加条目（版本号待 lead 定，条目内容照实写）：
- **Breaking**：`motui.kernel.MORE_BELOW` 移除（内核不再绘制 "─ more below ─" 标记行；
  滚动反馈由 host 的 chrome——如 `Scrollbar`——负责；顺带消除标记行的命中测试错配）。
- Fixed：`Dialog` 框参数原地变更在块缓存下的陈旧行；`Diff` 及 Tabs/NavList/Slider/
  ProgressBar/Collapsible 的 sealed 块 hover/focus 不落屏。
- Fixed：`Palette` 挂载后无法卸载；`Find` 卸载后仍消费键盘；gesture 复制路径的冗余重绘。
- Fixed：`__version__` 源码检出兜底号与发行版不一致；文档若干（34 名字清单、悬空引用、
  三处决策编号）。

## 验收

1. T1–T6 全绿，输出全部贴真实值
2. CHANGELOG 条目含 Breaking 段且描述与 diff 事实一致
3. `git diff main --stat` 干净收口

## 禁触清单

- 只写 `CHANGELOG.md`（仅追加）；其它一切只读。
- 禁触：任何源码、测试、golden、`specs/**`。
- 不 commit / 不建分支 / 不 push / 不 `--update` golden。

## 报告格式（最终消息，中文）

门禁逐项结果表（命令 + 真实输出摘要）/ render-hash 改前改后 / 四探针输出 / diff --stat /
CHANGELOG 条目全文 / 遗留与未决（若有，指名波次）。
