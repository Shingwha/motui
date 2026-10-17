# Spec diff-view · Diff 组件：性能与样式（波次 W1–W2）

> 日期 2026-10-17；基线 main `6dd2948`；分支 `diff-w1-core`、`diff-w2-docs`。
> 协议：见 spec-team SKILL 的「Git / worktree 协议」——worktree 在
> `C:\Users\shifu\.worktrees\mocode-tui\<分支>`，agent 不 merge / 不 push / 不 tag /
> 不 checkout main、不碰主检出与其他 worktree；spec 归 lead，agent 不更新任何 spec。
> commit 风格：英文一行祈使句（本仓既有惯例）。

## 目标与范围

最高约束：**`Diff` 仍是 display-only 的行级统一 diff；`render(width)` 的三条不变量
（幂等 / 有界 `width` / 换宽度无漂移，见 `tests/test_render_invariants.py` 的模块 docstring）
一条不改；除本 spec 列明的最小集合外，零行为变化。**

**做**（lead 已拍板，agent 不现场改主意）：

1. **算法**：公共前后缀裁剪 + 唯一共同行锚点。真文件（几百行、集中改动）从"整文替换"
   回到真 hunk，不再是「每边 141 行」的天花板。
2. **缓存**：`render(width)` 按宽度缓存行（对齐 `Markdown` 的既有惯例）。
3. **API**：`before` / `after` / `context` / `numbers` / `theme` 变成「赋值即重建」的
   property——今天是可写 slot 但改了不重建，静默过期（实测：`d.before = "x"` 后
   `render()` 仍返回老行）。
4. **样式**：删除行去掉 weight（bold 归 `**…**` 的仓规，见 `kernel/style.py` 的
   markdown 调色注释）；省略行带跳过行数。
5. **新选项**：`numbers=False` 行号栏（默认关，demo 展台开）。
6. **产物**：`docs/API.md` 生成、golden 帧重录（W1）；`COMPONENTS` / `DESIGN` /
   `README` / `CHANGELOG` 的语言文档（W2）。

**不做**（遗留清单，写进报告即可）：词级行内高亮；长行折行；文件头 `--- a/x` / `+++ b/x`；
并排视图；`LCS_LIMIT` 的数值调整（20 000 不变，含义改写）；任何对 `kernel/` 的改动。

## 波次表

| 波 | 分支 | 写者 | 写入范围（文件级） | 前置 |
|---|---|---|---|---|
| W1 | `diff-w1-core` | agent A | `src/motui/widgets/diff.py`、`tests/test_widgets_diff.py`、`tests/test_render_invariants.py`（仅组件矩阵 +1 行）、`src/motui/demo/pages/content.py`（仅 Diff 展台与它的 `api_note`）、`tests/golden/pages/*.txt`（仅 `--update` 重录）、`docs/API.md`（仅 `tools/apidoc.py --write` 生成） | 无 |
| W2 | `diff-w2-docs` | agent B | `docs/COMPONENTS.md`、`docs/DESIGN.md`、`README.md`、`CHANGELOG.md` | W1 合并后由 lead 验真 |

合并顺序：W1 先、W2 后（W2 的散文描述 W1 的行为，lead 合 W2 前逐条对合并后的代码验真）。
并行安全：两份写入范围文件级不相交；W2 不跑 `pytest` 之外的东西，W1 独占 golden / apidoc 产物。

## 拍板决策（照抄执行，不再现场猜）

| # | 决策 | 取值 |
|---|---|---|
| D1 | `LCS_LIMIT` 的语义 | 值不变（20 000），含义改为「**一次 DP 比较的区间**行对上限」（裁剪/锚点之后的段），不再是整份文本 |
| D2 | 裁剪规则 | 公共头、公共尾按行严格相等剥离；两侧完全相同 → 中段为空 → 零行（今天的「大文本相同 → 4002 行」不一致就此消失） |
| D3 | 中段优先级 | 任一侧为空 → 全 del/ins；`len(b)*len(a) <= LCS_LIMIT` → 走既有 `_lcs_ops`；否则锚点；无锚点 → 整段 del+ins（诚实退化） |
| D4 | 锚点定义 | **段内**两侧各出现恰好一次的行（段局部唯一，不看全文件）；配对后按 before 索引递增做一次单调走查（保留 j 严格递增者），跨越的锚点丢弃 |
| D5 | 锚点递归 | 每段递归调用同一规则（段是严格更短区间，必然终止）；每段内的整段替换保证**结果编辑代价 ≤ n+m**（即永不比今天的整文替换更差） |
| D6 | 退化形状 | 整段替换现在是**一个 hunk**（`@@ -1,n +1,m @@`，先全部 `-` 再全部 `+`），不再是今天的两个 hunk（`+0,0` / `-n,0`）——单 hunk 是统一 diff 对"整文重写"的规范形状 |
| D7 | 缓存 | `render(width)` 同宽度命中返回 `list(缓存)`（调用方拥有）；宽度变化即重建并替换缓存；不引入 LRU（单一宽度足够） |
| D8 | 赋值语义 | `before` / `after` / `context` / `numbers` / `theme` 都是 property + setter：读不变，写即重建 `_rows` 并清空洞缓存；`context` 的 setter 先校验（`< 0` → `ValueError` 且**状态不变**）；`theme` 的 setter 重新解析三个色带 |
| D9 | 样式：weight | 删除行 = `error` 的**色相**去掉 weight（`dataclasses.replace(resolved, bold=False)`；只剥 bold，italic/underline 等宿主注入的属性保留）；`+` 行、`@@`、`…`、上下文行样式不变 |
| D10 | 省略行文本 | `f"\u2026 {n} line"` / `f"\u2026 {n} lines"`（n = 两 hunk 之间的 `same` op 数，恒 ≥ 1）；`ELISION` 常量仍是 `"\u2026"`（标记字符，外部与测试用它）；单 segment，`muted`，不加行号栏 |
| D11 | 行号栏（`numbers=True`） | content 行 = 两个 segment：`f"{n:>{w}} "`（`muted`）+ 既有文本（各自 band）；`same`/`del` 取 before 侧行号，`ins` 取 after 侧行号；`w = len(str(max(len(before_lines), len(after_lines), 1)))`（构造时按整份文本定宽，不在 hunk 内变宽）；`@@` 与 `…` 行**不加**栏；`numbers=False`（默认）逐字节同今天 |
| D12 | demo 展台 | `Diff(BEFORE, AFTER, numbers=True)`；`BEFORE`/`AFTER` 扩到能产生**一条省略行**（两处改动相隔 > 2×context 行）；页面 `api_note` 文案同步 |
| D13 | 测试预算（用户指令：非必要不加测试） | 只允许：更新 3 条既有用例（D6 退化形状 1 条、D9/D10 的字节与省略行 2 条）+ 新增 ≤ 5 条（T1 大文件集中改动、T2 大文件散布改动、T4 赋值重建、D9 的 `-` 行无 bold 字节、D11 行号栏）+ `tests/test_render_invariants.py` 矩阵 +1 行（`Diff numbers`）。**不新建测试文件、不做参数矩阵、不给缓存单独写用例**（幂等已由既有矩阵覆盖） |

## 回归红线

- 基线（改前实测）：`uv run pytest -q` → **1395 passed, 1 skipped**。
- `tests/golden/pages/*.txt` 只允许用 `uv run python tools/golden.py --update` **整组**重录；
  手改单页 = 违规。D12 会让 `content.txt` 真实移动——这是预期内的，报告里写明。
- `docs/API.md` 只允许 `uv run python tools/apidoc.py --write` 生成。
- `tests/test_render_invariants.py` 除矩阵 +1 行外零改动。
- `render(width)` 的三条不变量、`fit` 的截断语义、`Diff` 无交互协议（无 `chosen`/`click`/
  `hover`/`handle`）—— 一条不动。
- 主检出（`C:\Users\shifu\Desktop\mocode-tui`）不许出现任何未提交改动；探针脚本一律写到
  `%TEMP%`，不进 worktree、不进提交。

## 探针：预期值（lead 已实测，W1 必须复现并贴真实输出）

`ref/probe.py` 是期望值生成器（对着**当前分支**的 `motui.widgets.Diff` 跑）。用例与预期行数：

| 用例 | 今天（main） | 改后（预期） |
|---|---|---|
| 2000 行，改中间 1 行 | 4002 行 | **9 行**（1 hunk） |
| 2000 行，顶部插 1 行 | 4003 行 | **5 行**（1 hunk） |
| 500 行，3 处散布改动（第 10/250/490 行） | 1002 行 | **29 行**（3 hunk，省略行计数 233 / 233） |
| 300 行，改 1 行 | 602 行 | **9 行**（1 hunk） |
| 1000 行，隔行改 | 2002 行 | 1501 行（1 hunk；此处"整文都变了"是诚实结果） |
| 2000 vs 2000，毫无共同行 | 4002 行（2 hunk） | **4001 行（1 hunk，`@@ -1,2000 +1,2000 @@`）** |

行数允许 ±0；不吻合即报告为偏差（不许回改预期值）。

两个差分臂（探针自带独立 oracle：本文件自己的滚动 DP，LCS 长度 → 最优代价 `n+m-2·LCS`）：

| 臂 | 今天（lead 实测） | 改后（lead 原型实测） |
|---|---|---|
| 小输入 20 000 组（含重复行，两侧 ≤ 14 行） | `same_as_optimal=20000, worse=0` | 同左（裁剪只减不增；形状可变，代价不升） |
| 锚点臂 300 组（300×300 行、行内含唯一序号、每组 1–6 处改动） | `same_as_optimal=0, worse=300, max_delta=598`（今天整段替换，代价 ~n+m） | **`same_as_optimal=300, worse=0, max_delta=0`**、`over_ceiling(n+m)=0` |

## 验收命令（每条都要贴真实输出）

1. `uv run pytest -q`（报告改前 1395 passed / 1 skipped 与改后总数）
2. `uv run python tools/golden.py --check`
3. `uv run python tools/apidoc.py --check`
4. `uv run python tools/framebench.py`（六行；预期 `render-hash` 不变——Diff 不在负载路径；
   时间行如实报告）
5. `uv run python -m motui --pages`（页数 + content 页有内容）与 `uv run python -m motui < /dev/null`（exit 0）
6. `%TEMP%\probe.py`（ref/probe.py 的拷贝，`sys.path` 指到本 worktree 的 `src`）——探针表

## 诚实出口

- 锚点（T2）若在预算内做不绿：**停下来报告**，保留 T1 的裁剪即可合并；不许为了绿而放宽
  `LCS_LIMIT` 或改探针预期。
- 任何既有用例的期望值若要改而本 spec 没列：停下来报告，lead 裁决。
- 越出写入范围（哪怕一行）→ 停下来报告，不越界自救。

## 报告格式（最终消息，中文）

工单状态表 / commit 清单（hash + message）/ 自测真实结论（贴输出）/ 探针表（改前 vs 改后）/
golden 与 apidoc 的重录说明 / framebench 六行 / 偏差与取舍 / 未决问题 / 真机手测：未执行。
