# W2c2b 交接 · 语义 golden（emulator 网格 + 属性）

> 分支 `2.0/w2c2-semantic`；起点 `2b2c8c6`（W2c2a 合并 `672a134` + 工单排序 commit）。前置：`ref/interfaces.md`、`handoff/W2c1-canvas.md`、`handoff/W2c2-signatures.md`、本波工单。
> 结论：T1–T4 全部完成；**1119 passed**；语义 57 match；旧 57 字节 golden 与 `a82f7968…` 不变；两次 `--update` 后快照零 diff。

## A. 交付面与门禁

### 工具（`tools/semantic.py`，206 行）
- 复用 `golden.py` 的 `ROOT/src` sys.path 约定；默认目录 `tests/golden/semantic`。
- `frame(topic)` 复刻 `render_topic` 的字节路径：`Session(screen=HeadlessScreen(110,70), interactive=False)` → `show_topic(key, toast=False)` → `tui.paint()`；把 `screen.output`（首屏 + 第二帧 diff 的完整累积流）喂给 `Emulator(110,70)`。
- `snapshot(topic)` 生成文本；`check/update(directory=None)`；`main` 支持 `--check`（默认）/`--update` 与 `--snapshot DIR`（可出现在任一侧），退出码 0/1，用法错 2。
- `Session` 构造时已 `show_topic(TOPICS[0])` + `paint()`，之后工单路径再 `show_topic(topic)` + `paint()`；`HeadlessScreen.output` 是累积流，整段喂给 emulator 得到的就是第二帧（Painter 行 diff）之后的最终网格。以 `render_topic` 的纯文本做对照：56/57 逐行相等，唯一差异见 B6。

### 快照格式（`<section>--<key>.txt`，57 个，1.3 MB）
```
# <section>/<key> 110x70 cursor=<x>,<y>
<row text>\t<runs>
```
- 70 行网格全写；`row text = "".join(cell.char for cell in row).rstrip()`（宽字符占位 `""` 不贡献字符）。
- `runs` 只覆盖非默认 `Style` 的列，**闭区间**零基 `start-end:<sgrhex>[:L<link>]`，`|` 连接；整行默认写 `-`。
- `sgrhex = style.prefix().encode("utf-8").hex()`；`link` 用 `repr`（含引号），link 变化即断 run；默认样式按 `Style()` 相等判断。
- header 光标取 `Emulator.cursor`（0 基，当前 57 个全部 `109,69`）；LF、末尾恰好一个换行。
- `matches` 只额外接受整文件精确的 `LF -> CRLF`（本机 `core.autocrlf=true`，windows-latest CI 也如此）；混合换行/其他字节都算差异。

### 门禁实测（2026-10-25，本 worktree）
- `uv run python tools/semantic.py --check`：`semantic: 57 topics match`。
- `uv run pytest -q -p no:cacheprovider`：**1119 passed**（基线 1113 + 6 个新用例，14.66s）。
- `tools/golden.py --check`：`golden: 57 topics match`；`framebench`：`a82f7968ed98…f379` 不变。
- `python -m motui < /dev/null`：exit 0 / 70 行；`--pages`：exit 0 / 4059 行。
- 确定性：连续两次 `--update` 后 `git status`/`git diff` 对 `tests/golden/semantic` 均为空（跨进程）。
- `ruff check .` 通过；`pyright` 0 errors；`lint-imports` 4 kept / 0 broken；`api.py --check` 181 names match；`growth.py --quick` pass/pass/OK。
- CI：`golden frames` 后新增 `semantic frames -- grid, attributes and cursor`（6 空格缩进，`uv run python tools/semantic.py --check`）。
- 复现：`uv run python tools/semantic.py --check`；`uv run pytest -q tests/test_semantic_golden.py`（6 passed，0.65s）。

## B. 取舍、差异分类与坑

1. **闭区间列号**：工单只写 `start-end`，选闭区间（`0-4` 含第 4 列）；README 与工具 docstring 都写死，避免半开歧义。快照同时保留 row text 与网格列号，宽字符不靠字符下标推断列。
2. **样式 key 用 SGR 字节**：`prefix()` 正是 Painter 写出的那段字节，hex 后稳定且与终端语义一一对应；不用 `repr(Color)`。link 参与 run key，换 URL 会红。
3. **link 现状**：57 个 topic 里只有 `components/markdown` 有 OSC 8（第 10 行、列 43–46 一个 run、4 个 cell，`https://example.invalid`）；其余无 link。
4. **默认样式的 `-`**：真实 57 个 topic 每行都至少有一个非默认 cell（shell chrome/滚动条），所以当前没有 `\t-` 行；格式与代码仍支持，属未被数据覆盖的路径。
5. **宽字符/组合字符**：emulator 的宽字符第二格 `char=""`，row text 自然跳过；组合字符附加到前一格。run 列号按网格列。
6. **唯一文本差异（预期外，已分类）**：`patterns/streaming-markdown` 第 9 行。旧字节 golden 是 `…👨\u200d💻` + 66 列空格 + `│░`（109 字符 / 110 列）；语义 row text 以该 emoji 结尾（43 字符）。原因：kernel `visible_width` 按 grapheme cluster 把 ZWJ 序列 👨‍💻 记 2 列，`Emulator._print` 按单码点 `wcwidth` 累加为 4 列（👨=2、ZWJ=0、💻=2），该行变 112 列；emulator 的立即换行把末尾 `│░` 写到下一行，随后被下一行 CUP 覆盖。属**量测工具（emulator）宽字符模型差异**，不是渲染变化；结果确定，旧字节 golden 未动。其余 56 个 topic 文本零差异。
7. **未改生产代码**：`src/motui/**`、旧 `tests/golden/topics/**`、`tools/golden.py`/`framebench.py` 零 diff；emulator 的 cluster 修正留给 W5/后续波次，届时该行快照会移动一次。
8. **测试策略**：`tests/test_semantic_golden.py` 用 `monkeypatch` 把工具的 `TOPICS` 缩成 1 个 topic，`--update`/`--check` 往返共 0.65s；另用文件集断言 57 个真实快照齐全、header 与 71 行结构正确。篡改行、缺文件分别断言 `differs`/`missing` 与退出码 1。
9. **pyright 细节**：`Session.tui.screen` 的静态类型是 `Screen`，没有 `output`；工具保留 `HeadlessScreen` 局部变量再取 `.output`，0 errors。
10. **光标语义**：header 记录 emulator 的最终光标（Painter 的 anchor）；当前 57 个都是 `109,69`。它不含时间戳/对象地址，只随布局/焦点/anchor 变化。
11. **快照确定性**：输出只由 Topic registry、Painter 字节与 Style 值决定；`Style.prefix()` 的缓存不改变字节；两次独立进程 `--update` 结果一致。
12. **`--snapshot` 的定位**：只是目录覆盖，不改 registry；测试用它把 1 个 topic 的往返放进临时目录，`main` 的打印/退出码与正式门禁同路。
13. **既有问题（非本波）**：`tools/growth.py` 全量探针不复制 `examples/`，而 W2c1 的 `tests/test_examples.py` 要跑 `examples/snake.py`，故 full probe 自 `d15bc1b` 起即 `pytest: FAIL`；`--quick` 通过。本波未改该工具（不在写入范围），交由 W5/工具波修。

## C. 位置与 commit

- 工具：`tools/semantic.py`（新，206 行）；数据：`tests/golden/semantic/*.txt`（57 个）；文档：`tests/golden/README.md`（新增 “Semantic frames” 一节）；测试：`tests/test_semantic_golden.py`（6 用例）；CI：`.github/workflows/ci.yml`（golden 后新增 semantic 步骤）。
- 禁触清单核对：`git diff 672a134..HEAD -- src/motui tests/golden/topics tools/golden.py tools/framebench.py pyproject.toml uv.lock README.md docs CHANGELOG.md` 为空；本波只新增 `tools/semantic.py`、`tests/golden/semantic/`、`tests/test_semantic_golden.py`、改 README 与 CI。
- commit：
  - `f007cd5` tools: pin semantic frames from the emulator grid
  - `c8f2c85` test: record a semantic golden frame for every topic
  - `af8d468` ci: gate the semantic snapshots and test their round trip
  - 本文件（最后一个 commit）
- 验收汇总：semantic 57 / pytest 1119 / 旧 golden 57 / hash `a82f7968…` / demo 70·4059 / 两次 update 零 diff / ruff·pyright·lint-imports·api 全绿 / CI 含 semantic 步骤。
- 四个 commit（含本文件）都在 `2.0/w2c2-semantic`；未 merge/push/tag，未碰主检出与其他 worktree。
