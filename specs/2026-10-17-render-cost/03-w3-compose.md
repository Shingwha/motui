# Spec render-cost · W3：合成路径（波次 W3）

> 分支 `rc-w3-compose`（worktree `C:\Users\shifu\.worktrees\mocode-tui\rc-w3-compose`）；
> 前置：无（与 W1 并行，文件级不相交）；深读：`00-overview.md`（D11/D12）、`ref/facts.md`、`ref/probe.py`。
> 本波只碰 `kernel/frame.py` + `chrome.py` 的每帧路径，**输出字节必须逐字节不变**。

## 目标

挂一个滚动条就把整屏每行推上 splice 路径（实测 0.075 → 0.987 ms/帧，13.1×）：让未变的行
在合成时不重建对象，让 splice 在平凡的窗口上有早退，让 chrome 的绘制结果可缓存。

## 工单（按序执行，每项一个 commit，每个 commit 独立跑一遍 `uv run pytest -q`）

### T1 `frame.compose`：未变的行复用上一帧（D11）

- pass-through 判定从"单 region + 整帧 + 无 chrome"放宽到**逐行**：一行的矩形、内容来源、
  窗口位置都没变时，直接复用上一帧为它构造的 `Line`/FrameSpan，不新建对象。
- 判据必须是"**能不能证明没变**"（矩形 + 来源块 + 窗口内偏移 + 宽度），不许靠"看起来没变"。
  拿不准的行按老路重建——正确性优先，收益靠能证明的那些行拿。
- 与已完成的 painter 行级 diff 配合：静止帧写屏 0 字节这条不许破坏。

### T2 `splice_row` 的平凡早退

- 窗口等于整行（`base` 为空或窗口覆盖全宽）时直接返回原行，不走 `index_bounds_at_columns` +
  `slice_line` + `pad_to` 三件套；裁剪结果为空时同样早退。
- 逐字节等价：早退路径返回的行必须与慢路径**同值**（用既有测试 + 你自己的等价性核对）。

### T3 `Chrome.paint` 的结果缓存（D11）

- 滚动条/分隔条这类"只由布局决定"的 chrome：绘制结果按 `(offset, total_rows, height, 宽度)`
  缓存，命中直接复用；布局参数变了就重建。`Stats`/`Tooltip`/`Toasts` 不在本波范围。
- 注意 `chrome.py` 里既有 `invalidate()` 的调用点（`:484/:512/:750/:828/:835/:1136`）——
  缓存要跟着这些失效信号走，别让缓存比状态活得久。

### T4 测试与产物

- 更新被内部结构逼着改的既有用例（预计：`tests/test_frame.py`、`tests/test_chrome.py`、
  `tests/test_painter.py` 里与 `compose`/splice 内部行为有关的少数几条）；新增 ≤ 3 条：
  带滚动条的帧复用（调用计数或对象计数）、`splice_row` 早退与慢路径等值、chrome 缓存失效。
- 若发现"零字节变化"做不到（例如必须改输出才能省算）：**停下报告**，不要自行改契约。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q`（基线 1407 passed / 1 skipped）
2. `uv run python tools/golden.py --check`（**不许** `--update`）× 与 `tools/apidoc.py --check`
3. `uv run python tools/framebench.py`：`scroll` 与 `scroll-long` 两行必须动（目标：
   `scroll` ≤ 1.0 ms/notch，改前 2.7）；`render-hash` 必须**逐字不变**（`de48e747…`）；
   `stream-*`/`replay` 如实
4. `%TEMP%\rc_probe.py`：A 行 `+scrollbar` ≤ 0.2 ms（改前 0.987）；B–I 与 hover 四条不因本波改变
   （F1–F4 仍按各自波次的进度）
5. `uv run python -m motui < /dev/null` exit 0 与 `uv run python -m motui --pages` 11 页有内容
6. `git status --porcelain` 干净 + `git log --oneline main..HEAD`

## 禁触清单

- 只改：`src/motui/kernel/frame.py`、`src/motui/chrome.py`、`docs/API.md`（仅 `--write` 生成，如签名动了）、
  `tests/{test_frame,test_chrome,test_painter}.py`。
- 禁触：`src/motui/kernel/{block,viewport,lines,selection}.py`、`src/motui/app.py`、
  `src/motui/interaction/**`、`src/motui/widgets/**`（W1/W2/W4 的）、`tools/framebench.py`
  （行由 W1/W2/W4 加，本波不动它）、`docs/`（W5 的）、`specs/**`、`pyproject.toml`、其它测试文件。
- 不 merge / 不 push / 不打 tag / 不 checkout main；不碰主检出与其它 worktree（尤其 `rc-w1-row-cache`）。

## 报告格式（最终消息，中文）

工单状态表（T1–T4）/ commit 清单 / 自测真实结论 / 探针 A 行改前 vs 改后 / framebench 全行
（标明哪两行动了）/ 既有用例搬迁清单 / 等价性核对方式（早退 vs 慢路径）与结论 / 偏差与取舍 /
未决问题 / 真机手测：未执行。
