# W0 · 契约与护栏（不改变行为）

> 上级：`README.md`　依赖：无　下一波：`W1-kernel-split.md`
> 状态：ready

## 1. 目标

在不改变任何生产行为的前提下，建立：

1. 新 kernel 的值类型（`geom` / `cell` / `Surface` / `Constraints` / `WrapMode` / `Scroll`）；
2. VT 模拟器与 headless harness；
3. 静态护栏（ruff / pyright / import-linter）；
4. API 快照与可增长性演练；
5. CI 阶梯。

**本波结束：旧测试全绿、字节 golden 不变、`render-hash` 不变。**

## 2. 为什么先做这一波

- 重构 33k 行没有护栏等于盲改；pyright/import-linter 必须在第一波就位。
- `Surface`/`Constraints`/`WrapMode`/`Scroll` 是后面每一波的地基；先把它们作为**未被使用的纯值**引入，可以用单元测试锁死，不影响旧代码。
- golden 现在是字节 hash；先建模拟器，W2 才能语义化重录。

## 3. 范围（文件）

新增：

```
src/motui/kernel/__init__.py
src/motui/kernel/geom.py          # Size/Rect/Pos/Axis
src/motui/kernel/cell.py          # Cell/Line/Surface（最小）
src/motui/kernel/text.py          # WrapMode（先只加枚举）
src/motui/kernel/layout.py        # Constraints/Scroll/Axis 值（先不接 Viewport）
tools/api.py
tools/growth.py
tests/kernel/test_geom.py
tests/kernel/test_surface.py
tests/kernel/test_wrapmode_values.py
tests/kernel/test_scroll_values.py
```

修改：

```
pyproject.toml        # ruff/pyright/import-linter 配置
.github/workflows/ci.yml  # 追加 ruff/pyright/import-linter/api/growth
```

**不修改**：`core/`、`widgets/`、`app/` 的任何运行时路径。

## 4. 任务

### 4.1 几何

- 从 `core/frame.py` 抽出 `Rect` 的语义（不删旧文件，先复制到 `kernel/geom.py` 并加测试）；
- `Size`/`Pos`/`Axis` 新增；
- `Rect` 方法：`right`/`bottom`/`area`/`contains`/`intersect`/`split(axis, weights, min_size)`。

**验证**：随机化不变量测试（intersect 交换律、contains 传递、split 面积守恒）。

### 4.2 Cell / Line / Surface（最小）

- `Cell(char/style/link/action)` + 内容门（C0/DEL/C1、tab→空格）；
- `Line` 先包一层 `tuple[Segment, ...]`，提供 `text/width/segments/styled`；
- `Surface(width, rows)` + `blank`/`of` + 裁剪（每行 `fit`，短行 `fill`）；
- 不接入 `render`/`painter`。

**验证**：宽度 0/1/2/emoji/CJK、超宽裁剪、控制字符、等值/哈希。

### 4.3 Constraints / WrapMode / Scroll 值

- `Constraints(width, max_height=None)`；
- `WrapMode` 5 值（`WORD/CHAR/ELLIPSIS/CLIP/OVERFLOW`）；
- `Axis`/`Scroll` 值 + `clamp`/`max_offset`/`reveal`/`thumb` 的纯函数实现（先独立于 `ScrollState`）。

**验证**：两轴 clamp、sticky 只 y、thumb 公式与 1.x 一致（用 1.x 测试数据对照）。

### 4.4 VT 模拟器

- `testing/emulator.py`：cell 网格 + CUP/EL/ED/SGR/换行/裁剪；
- 输入：`Painter` 的一帧字节；输出：`grid`/`text`/`cell`/`sgr_at`；
- 不解析图片/鼠标。

**验证**：1.x 的一个固定帧 → 模拟器文本与 `snapshot` 一致；20 列写 40 列会被模拟器识别为换行。

### 4.5 Tooling

- `tools/api.py`：导出公开名字 + 签名快照；`--check`/`--update`；
- `tools/growth.py`：给 `Surface`/`Constraints`/`Scroll` 模拟追加默认字段，跑 `pytest` + golden + api check，断言零变化；
- `pyproject.toml`：ruff（E/F/I/UP/B/SIM/RUF）、pyright（strict 先只对 `kernel/`）、import-linter（分层 + kernel 无 I/O）；
- CI 阶梯追加。

**验证**：故意加一个反向 import，import-linter 必须失败；故意改 API 快照，`api.py --check` 必须失败。

### 4.6 CI

```
ruff → pyright(kernel) → lint-imports → pytest → framebench → golden → api → growth
```

双平台（ubuntu/windows）全绿。

## 5. 门禁

- `pytest` 全绿（旧 65 文件 + 新 kernel 测试）；
- 57 golden 字节不变；`render-hash` 不变；
- `ruff` 0；`pyright`（kernel）0；
- `lint-imports` 通过；
- `api.py --check` 通过；
- `growth.py` 通过。

## 6. 退出条件

- [ ] `kernel/` 的值类型有独立测试且**未被生产代码使用**；
- [ ] 模拟器能对 1.x 的一帧做语义断言；
- [ ] 静态护栏在 CI 生效，反向依赖会红；
- [ ] API 快照 + growth 演练可重复；
- [ ] 旧行为零变化（字节级）。

## 7. 回滚

- 整波是新增文件 + 配置，回退只需删除 `kernel/`/`tools/` 新文件与 CI 步骤；
- 不影响 1.x 运行时。

## 8. 交接

`10-waves/W0-handoff.md` 记录：

- 实际新增/修改文件；
- `pyright`/`import-linter` 的配置片段；
- 模拟器支持的 escape 列表；
- API 快照文件路径；
- 未决项（例如 `text` 度量的命名是否已定）。
