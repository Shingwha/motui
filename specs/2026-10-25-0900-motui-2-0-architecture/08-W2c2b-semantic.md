# W2c2b · 语义 golden（emulator 网格 + 属性）

> 分支 `2.0/w2c2-semantic`；前置：W2c2a 已合并（`672a134`）；写入范围：`tools/semantic.py`、`tests/golden/semantic/**`、`tests/golden/README.md`、`.github/workflows/ci.yml`、`tests/test_semantic_golden.py`
> 权威：`ref/source/09-testing-tooling.md` §3–5、`10-waves/W2-render-contract.md` §4.6

## 目标

给 57 个 demo topic 建**语义 golden**：用 `motui.testing.Emulator` 消费真实 Painter 字节，快照 cell 网格 + 每格 SGR 属性 + 光标锚点；`--check` 进 CI。旧的字节 `.txt` golden 本波保留（W5 删除）。

**本波结束：`semantic --check` 通过；57 个语义快照落盘；CI 增加该步；字节 golden 与 hash 不变。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2c1-canvas.md` → `handoff/W2c2-signatures.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1113 passed）；`golden --check`（57）；`framebench`（hash a82f7968…）。
- 已知事实：
  - `motui.demo.render_topic(topic)` 返回纯文本；要拿真实字节需复刻它的路径：
    ```python
    from motui.demo import BY_KEY, Session
    from motui.demo.script import HEADLESS_W, HEADLESS_H
    from motui.terminal import HeadlessScreen
    session = Session(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H), interactive=False)
    session.show_topic(topic.key, toast=False)
    session.tui.paint()
    output = session.screen.output
    ```
  - `Emulator(HEADLESS_W, HEADLESS_H).feed(output)` 维护 `grid: list[list[Cell]]`、`cursor: Pos`、`text()`、`cell(x,y)`、`sgr_at(x,y)`。
  - `Emulator.Cell` 有 `char/style/link`；宽字符第二格 `char=""`；组合字符附加到前一格。
  - `Style` 是 `motui.kernel.style.Style`，`style.prefix()` 给出 SGR 字节（默认样式为 `""`），可用于稳定 key。
  - `TOPICS` 在 `motui.demo.registry`；`topic.section` / `topic.key` 是文件名。
  - 旧 golden 文件在 `tests/golden/topics/<section>--<key>.txt`；不要改它们。
- 已知坑：
  - 快照必须是确定性文本（LF、无时间戳、无对象地址）；`Color`/`Style` 的 `repr` 可能稳定，但更稳的是 `style.prefix()` 的 UTF-8 hex。
  - 宽字符：`text()` 里宽字符后的占位 `char=""` 不产生字符；样式 run 的列索引按网格列算，两套坐标都保留在快照里，不要互相推断。
  - OSC 8 link 可能出现在 Markdown 页面；把 link 写进 style key（`repr`），否则换链接不会红。
  - `Session.show_topic` 可能产生 toast；用 `toast=False` 与 `render_topic` 一致。
  - `session.tui.paint()` 可能不是 live？`HeadlessScreen.live=True`，会写字节。
  - CI 在 3.12 双平台跑；不要用 3.13-only 语法。
- 不要改 `tools/golden.py`、`tools/framebench.py`、`tests/golden/topics/**`。

## 工单（按序执行，每项一个 commit）

### T1 `tools/semantic.py`

- 新建 `tools/semantic.py`，沿用 `golden.py` 的 `ROOT/src` sys.path 约定。
- 快照格式（每个 topic 一个文件 `tests/golden/semantic/<section>--<key>.txt`）：
  ```
  # <section>/<key> <width>x<height> cursor=<x>,<y>
  <row text>\t<runs>
  ...
  ```
  - `row text`：`"".join(cell.char for cell in row).rstrip()`；
  - `runs`：对该行**非默认样式**的连续列区间做 RLE，格式 `start-end:<sgrhex>[:L<link>]`，多个用 `|` 分隔；没有则 `-`；
    - `sgrhex` = `style.prefix().encode("utf-8").hex()`（默认样式 = 空字符串，不写）；
    - `link` = `repr(cell.link)`（含引号，避免分隔符歧义），同一 run 内 link 不同则断开；
  - 行尾无多余空白；文件 LF；末尾一个换行。
  - 光标：取 `Emulator.cursor`（0-based）写进 header。
- `--update`：生成 57 个文件；`--check`：逐字节比较，缺/多/不同都失败；`--snapshot DIR` 便于测试临时目录。
- 打印 `semantic: N topics match` / 差异清单；退出码 0/1。
- 只允许改：`tools/semantic.py`、`tests/test_semantic_golden.py`。
- 验证：`uv run python tools/semantic.py --update` 生成文件；`--check` 通过。

### T2 落盘 57 个快照 + README

- 提交 `tests/golden/semantic/*.txt`（57 个）。
- 在 `tests/golden/README.md` 增加一节：语义快照的格式、与字节 golden 的关系（W5 删字节）、如何 `--update`、差异分类要求。
- 只允许改：`tests/golden/semantic/**`、`tests/golden/README.md`。
- 验证：`uv run python tools/semantic.py --check`。

### T3 测试与 CI

- `tests/test_semantic_golden.py`：
  - 用临时目录 + `--snapshot`/`--update` 生成一份小快照，`--check` 通过；
  - 篡改一行后 `--check` 失败；
  - 删除一个文件后失败；
  - 断言 57 个 topic 都有快照。
- `.github/workflows/ci.yml` 在 `golden frames` 之后加：
  ```yaml
  - name: semantic frames -- grid, attributes and cursor
    run: uv run python tools/semantic.py --check
  ```
- 只允许改：`tests/test_semantic_golden.py`、`.github/workflows/ci.yml`。
- 验证：`uv run pytest -q tests/test_semantic_golden.py`；`uv run python tools/semantic.py --check`。

### T4 差异分类报告 + 收口

- 对比语义快照的 `row text` 与旧字节 golden 的文本（去掉 header/尾空行）：逐 topic 记录是否有文本差异。
- 预期为零差异（W2 的组件迁移保持字节不变）；若有差异，按“裁剪/尺寸/换行/新行为”分类并在 handoff 写清原因。
- 只允许改：`handoff/W2c2b-semantic.md`。
- 验证：全量验收。

## 验收

1. `uv run python tools/semantic.py --check` → `57 topics match`。
2. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
3. 旧 `golden --check` → 57 match；hash `a82f7968…` 不变。
4. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
5. 快照确定性：连续两次 `--update` 后 `git diff` 为空；跨进程（两次运行）一致。
6. `ruff` / `pyright` / `lint-imports` 全 0；`api --check` 通过（本波无公开面变化）。
7. CI YAML 含 semantic 步骤（人工检查缩进）。

## 禁触清单

`src/motui/**`（本波不改生产代码）、`tests/golden/topics/**`、`tools/golden.py`、`tools/framebench.py`、`pyproject.toml`、`uv.lock`、`README.md`、`docs/**`、`CHANGELOG.md`。

## 交接包

最后 commit 写 `handoff/W2c2b-semantic.md`：A 节给快照格式/文件数/门禁；B 节给格式取舍（SGR hex、link、宽字符、光标）、差异分类；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W2c2a 事实）/ 探索审计 / 未决问题。
