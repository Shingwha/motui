# 09 · 测试与工程护栏

> 上级：`01-architecture.md`　相关：`10-waves/W0` `W5`
> 状态：ready

## 1. 目标

把“重构不跑偏”变成机器可验证：

1. VT 模拟器（语义断言，不再只看字节 hash）；
2. headless harness（虚拟时钟 + 脚本输入 + cell 查询）；
3. golden 语义化 + 差异分类；
4. framebench（ms/字节阈值）；
5. growth.py（可增长性演练）；
6. api.py（公开面快照）；
7. import-linter / ruff / pyright（依赖与类型）。

## 2. 为什么

1.x 有 65 个测试文件 / 12,037 行 + 57 个 golden + framebench，这是最强的资产；但：

- golden 是**字节 hash**，SGR 缓存顺序变化就误报，换行/裁剪 bug 反而抓不到；
- 没有静态检查（ruff/mypy/pyright/import-linter 全零）；
- 没有“给帧类型加字段不破坏”的演练；
- 没有“公开面漂移”检查；
- 测试驱动动画只能替换 `clock()`，没有统一的 `advance()`。

## 3. VT 模拟器

`testing/emulator.py`：最小终端模拟器，维护 cell 网格。

支持：CUP、EL、ED、SGR（含 truecolor/256/16）、换行、裁剪、光标、alt screen 标记；不解析图片。

```python
class Emulator:
    grid: list[list[Cell]]
    cursor: Pos
    def text(self) -> str: ...
    def cell(self, x: int, y: int) -> Cell: ...
    def sgr_at(self, x: int, y: int) -> Style: ...
```

用途：

- golden 主断言：`grid` + 属性；
- 发现换行/裁剪 bug（1.x 的 20 列写 40 列会在这里现形）；
- 测试截屏/导出。

## 4. headless harness

```python
from motui.testing import headless

tui = headless(Snake)          # 接管 screen + clock + input
tui.advance(0.1)               # 虚拟时钟，不 sleep
tui.press("down")
assert tui.cell(21, 10) == "#"
assert "game over" in tui.text()
```

- `advance(dt)`：推进虚拟时钟并跑 tick/paint；
- `press(key)` / `click(x,y)` / `resize(w,h)`；
- `cell(x,y)` / `text()` / `snapshot()`；
- `headless()` 默认 `TerminalOptions(stream=HeadlessScreen, ...)`，非 live；
- 不再需要 `interactive=False` 开关。

## 5. golden：语义化

- 57 个 topic 从“字节文件”改为“cell 网格 + 属性”快照；
- 可选保留少量字节级测试（escape 顺序、sync 包裹）；
- 重录必须附**差异分类报告**：每个 topic 属于哪类变化（裁剪/尺寸/换行/新行为）；
- CI 的 `golden --check` 对语义快照做 diff。

**迁移策略**

1. W0：新增 emulator 与 `snapshot(media=...)`，旧字节 golden 暂留；
2. W1：字节级不变（旧 golden 继续跑）；
3. W2：语义 golden 重录 + 旧字节 golden 标记 expected-change；
4. W5：删除旧字节 golden。

## 6. framebench

- 输出每 topic 的 `ms` 与线上字节数；
- 阈值：普通页面帧字节不增加；80×24 全异色 Canvas ≤2.0ms；单色 ≤0.4ms；snake 每步 ≤150 字节；
- 每波跑；超过阈值 10% 阻断。

## 7. growth.py（可增长性演练）

```python
# 模拟：给 Surface/Constraints/FrameDelta 追加一个默认字段
# 跑全量 pytest + 57 golden + api.py --check
# 断言：零失败、零字节变化
```

- 证明帧类型没有被锁死；
- 若有人把 `Surface` 改成“必须传全部位置参数”，这条会失败。

## 8. api.py（公开面快照）

- 导出每个命名空间的公开名字 + 签名；
- `--check` 对比仓库中的 `tools/api-2.0.txt`；
- 任何公开面变化必须显式更新快照并评审。

## 9. 静态护栏

```ini
# pyproject.toml
[tool.ruff]
line-length = 100
select = ["E","F","I","UP","B","SIM","RUF"]

[tool.pyright]
typeCheckingMode = "strict"   # kernel 先达标，逐波扩大
```

- import-linter：分层 + kernel 零 I/O（见 `01` 第 4 节）；
- CI 阶梯：`ruff → pyright → lint-imports → pytest → framebench → golden → examples → api`。

## 10. 测试迁移

- 删除一个模块，同时删除/迁移它的测试；
- 交互测试 1:1 平移（同一按键 → 同一状态变化）；
- widget 测试用 `CellMetrics`/`headless`，不碰真终端；
- 解码器 fuzz：随机字节 10k 轮不崩；
- Rect/Surface/Scroll 随机不变量测试。

## 11. 门禁矩阵

| 波 | pytest | golden | framebench | ruff/pyright | import-linter | api/growth |
|---|---|---|---|---|---|---|
| W0 | ✅ | 字节不变 | ✅ | 配置就位 | ✅ | ✅ 新建 |
| W1 | ✅ | 字节不变 | ✅ | kernel strict | ✅ | ✅ |
| W2 | ✅ | 语义重录 | 阈值 | ✅ | ✅ | ✅ |
| W2.5 | ✅ | 分类 | ✅ | ✅ | ✅ | ✅ |
| W2.6 | ✅ | 分类 | ✅ | ✅ | ✅ | ✅ |
| W3 | ✅ | 分类 | ✅ | ✅ | ✅ | ✅ |
| W4 | ✅ | 分类 | ✅ | ✅ | ✅ | ✅ |
| W5 | ✅ | 冻结 | ✅ | ✅ | ✅ | ✅ |

## 12. 不做的

- ❌ 真终端截图对比（CI 不稳定）。
- ❌ 引入 hypothesis（用简单随机化即可，避免新依赖）。
- ❌ 为测试改生产 API（测试用 `headless`/值类型）。
