# Spec tui-depth · W5 开发者基建（波次 W5）
> 分支 `td5-tools`；前置：W4；深读：`00-overview.md`（D11–D14、门禁）。
> **最高约束：录制/回放是 `KeySource` 装饰器（事件级、stdlib only、零 sleep 可测）；黄金帧与 DevStats
> 都读既有字段，不引入新计时/存储机制；`devtools` 页是 gallery 的第 13 页。**

## 目标

1. `RecordingKeys` / `ReplayKeys`：真机事件流 → JSONL → 仓库回归（D11）。
2. 解码器 fuzz 与渲染不变量测试（D12）。
3. `tools/golden.py` + `tests/test_golden_frames.py`：gallery 全部页面的黄金帧（D13）。
4. `chrome.Stats` DevStats overlay + gallery `c-g` + `devtools` 页（D14）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| `KeySource` 协议与 `ScriptedKeys`（`None`=一次性 EOF） | `core/events.py:90-121` |
| keys facade 与 down-list pin | `keys/__init__.py:37-53`；`tests/test_api_root.py:42-45,78` |
| 事件三型（Key/Paste/MouseEvent）字段 | `core/events.py:45-80` |
| `painter.frames` 帧计数、`tui.clock()`、`every()` | `core/painter.py:54,86`；`app.py:718-729,858-865` |
| gallery 页注册一行一处；`script.py` 的 `/page` 驱动与坐标常量 | `examples/gallery/registry.py:55-80`；`script.py:80-101` |
| 无 hypothesis、dev 依赖只有 pytest 三件套 | `pyproject.toml:14-19` |
| 测试零 sleep 契约；`tests/_doubles.py` 现有 double | `docs/DESIGN.md:907-908`；`tests/_doubles.py` |

## 工单（按序执行，每项一个 commit）

### T1 `keys/recorder.py`：`RecordingKeys` / `ReplayKeys`（D11）

- `RecordingKeys(source: KeySource, path: str | Path)`：包装真源；`read()` 把每个事件的 JSON 行
  （`{"ms": <相对毫秒>, "event": {"kind": "key|paste|mouse", ...}}`）追加进文件；EOF(`None`)
  不记录（文件到此结束）。副本字段：`Key.name/char`、`Paste.text`、`MouseEvent.name/button/x/y/kind`。
- `ReplayKeys(path, *, speed: float = 1.0)`：`read()` 按 `ms * speed` 的间隔产出事件
  （`speed=0` → 全部零延迟，测试/CI 用；实现用 `asyncio.sleep`，惰性读文件）；事件序列耗尽 → `None`。
- 序列化/反序列化是模块内的纯函数（测试直接测 round-trip，不碰 IO）；文件 IO 只在两个类里。
- 加进 `keys/__init__.py` 的 `__all__`（分组顺序）与 `test_api_root.py`（keys 段 + `DOWN_LISTED`；
  **不进 root**——它们是测试/诊断工具，root 保持策展面）。
- 测试：round-trip（三型事件）、`speed=0` 零延迟顺序、坏行报错（ValueError 带行号）、EOF 语义。
- 文档：`docs/COMPONENTS.md` 的 Testing 段 + `README.md` 的「Testing without a terminal」加
  「录一段真机、当回归跑」的三步 recipe（`RecordingKeys` 包 `RawTerminalKeys` → JSONL →
  `ReplayKeys(speed=0)` 进 pytest）。

### T2 不变量与 fuzz（D12）

- `tests/test_decoder_fuzz.py`：`random.Random(seed)` 生成字节流（含 `\x1b`、CSI 片段、UTF-8 破碎
  序列，长度覆盖 0..512），喂 `KeyDecoder`：断言不抛、`pending` 有界、`finish()` 后状态清空；
  固定种子矩阵（≥20 例）+ 一条「逐字节喂 == 整块喂」的等价性（对全部用例）。
- `tests/test_render_invariants.py`：对公开组件矩阵（Text/Markdown/Table/Tree/Tabs/Select/Input/
  Editor/Radio/Slider/Collapsible…**以当波已有者为准**）渲染宽度 `1,2,3,7,20,80`：断言
  `render(w)` 幂等（两次调用相等）、每行 `width == w`、`[len(line.text) <= w 的显示宽]`、
  重复调用无状态漂移（前后再 render 相等）。
- 零 sleep、零新依赖。

### T3 `tools/golden.py` + `tests/test_golden_frames.py`（D13）

- `tools/golden.py`：`--update` 渲染 gallery 全部页面（`HeadlessScreen(HEADLESS_W/H)`，
  与 `demo.py --pages` 同路径）写入 `tests/golden/pages/<page>.txt`（含页头行，行尾规范化 LF）；
  `--check` 逐字节比对并列出差异页；无参 = `--check`。
- `tests/test_golden_frames.py`：对每个页面文件做逐字节断言（缺文件/多文件都红）；页数 == PAGES 长度。
- 生成 13 页基线（本波含 W5 的 `devtools` 页）并在 `tests/golden/README.md` 写「何时重录」的一句。
- 测试不许 sleep；golden 文件进仓库（`tests/golden/pages/*.txt`）。

### T4 `chrome.Stats` + gallery `c-g` + `devtools` 页（D14）

- `chrome.Stats(Themed)`：`Stats(tui, *, pointer=None, theme=None)`；overlay 形态（挂载注册/`detach`
  注销）；`paint(frame)` 在右上角画小盒：`frames`、最近 1s 帧率（用 `tui.clock()` 采样，照 `session.py`
  的 fps 先例）、事件计数（Stats 自己 `handle(event)` 累计，宿主喂）、最近键名、`pointer.hovered`
  的类名与 cell。
- gallery：`c-g` 切 Stats 挂/卸（`HOST_KEYS`/dispatch order 更新）；`devtools` 页（第 13 页）
  用文字 + 现成组件演示：帧率行、事件计数行、hit-test 探针（页面里放几个可 hover 的块并显示
  `hit_component` 结果）、黄金帧与回放工具的使用说明（静态文字 + `api_note`）。
- `registry.py` 加页；`script.py` 的 `/page` 列表补 `devtools`（回放游 13 页）。
- `tests/test_api_root.py`：`Stats` 进 root（或 DOWN_LISTED——**decision：进 root**，与 `Tooltip`/`Find`
  同级，供宿主直接挂）；同步 pin 与顺序。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 只增不减（贴 before/after 与新增文件）。
2. 探针：录制→回放 round-trip 的 JSONL 原文与事件序列（`speed=0` 零 sleep，`time` 如实）；fuzz 种子
   矩阵输出摘要；`golden --check` 全过（13 页，贴页数）。
3. `demo.py < /dev/null` exit 0；`--pages` → **13** 页头且新页有内容；回放脚本含 `c-g` 与 `/devtools`。
4. `tools/framebench.py`：hash 如实报告（gallery/工具不碰 hash 工作负载 → 预期不变）。
5. `python -c "import mocode_tui"` 干净；README 块全绿。
6. 真机项（DevStats 可读性、录制的真机事件质量）→ 未执行，列 lead 终验。

## 禁触清单

- `RawTerminalKeys`/`decode` 的既有行为（装饰器只包不改）
- `framebench.hash_workload` 的工作负载与输出格式
- `specs/**`；gallery 既有 12 页的内容（只加页与宿主键）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + pytest 数）/ 录制回放探针 /
fuzz 与不变量摘要 / golden 页数 / framebench hash / 偏差与取舍 / 未决问题 / 真机手测：未执行。
