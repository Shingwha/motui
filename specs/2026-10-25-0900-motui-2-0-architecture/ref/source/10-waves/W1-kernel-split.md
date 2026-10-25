# W1 · 内核拆分（机械迁移）

> 上级：`README.md`　依赖：`W0-harness.md`　下一波：`W2-render-contract.md`
> 状态：ready

## 1. 目标

把 1.x 的 `core/` 拆成 **kernel（纯值）+ terminal（I/O）**，并把 `frame.py` 拆成 geom/frame/hit/overlay，`viewport+scroll` 合成 layout。

**本波结束：demo 输出逐字节不变；kernel 不 import 任何 I/O。**

## 2. 为什么

- `core/` 里混着 2,150 行终端 I/O（ansi/screen/decoder/sources/console）。
- `frame.py` 1,677 行同时做 Rect、split、docks、compositor、overlay、hit、memo。
- `driver.py` 1,333 行，W4 才拆运行时；W1 只做“文件与边界”的机械迁移，风险最低。

## 3. 文件迁移表

| 1.x | 2.0 | 备注 |
|---|---|---|
| `core/ansi.py` | `terminal/ansi.py` | 私有；不导出 |
| `core/screen.py` | `terminal/screen.py` | `Screen` → ABC；加 `TerminalOptions`/`MouseMode` 占位（W4 接） |
| `core/decoder.py` | `terminal/decoder.py` | 纯状态机 |
| `core/sources.py` | `terminal/keys.py` | `RawTerminalKeys` |
| `core/console.py` | `terminal/win32.py` | ctypes |
| `core/clipboard.py` | `terminal/clipboard.py` | 内存替身 → `testing` |
| `core/frame.py` | `kernel/geom.py` + `kernel/frame.py` + `kernel/hit.py` + `kernel/overlay.py` | Rect/split → geom；compositor → frame；Hit → hit；layers → overlay |
| `core/viewport.py` + `core/scroll.py` | `kernel/layout.py` | `Viewport` + `Scroll`/`RowSpan` |
| `core/block.py` | `kernel/document.py` | `Block` → `Section` |
| `core/painter.py` | `kernel/paint.py` | |
| `core/selection.py` | `kernel/selection.py` | 仍保持自由函数（W3 改方法） |
| `core/lines.py` | `kernel/cell.py` + `widgets/text.py` | `Text` 组件归 widgets |
| `core/text.py` | `kernel/text.py` | |
| `core/style.py` + `theme.py` + `glyphs.py` | `kernel/cell.py` + `kernel/theme.py` | 删 `Themed`（W3 前先保留兼容？不，2.0 直接删） |
| `core/mark.py` | `widgets/base.py` | 随 W3 |
| `core/cursor.py` | `widgets/base.py` | 随 W3 |
| `core/chrome.py` | `kernel/frame.py` | `Separator` 并入 |
| `core/hit.py` | `kernel/hit.py` | `EveryHandle` → `runtime`（W4），`RowRange` → layout |

## 4. Screen 改 ABC

```python
class Screen(ABC):
    # 稳定成员；可选成员带默认实现
```

- `TerminalScreen` / `HeadlessScreen` 继承；
- `runtime_checkable Protocol` 删除；
- 2.0 不新增必须实现的方法；
- `cell_metrics`/`graphics` 等属性留到 2.x（带默认值）。

**验证**：`isinstance(screen, Screen)` 仍可用；第三方子类不需改。

## 5. 任务顺序

1. 建 `terminal/` 与 `kernel/` 包；移动文件（`git mv` 保留历史）。
2. 修 import：`core.*` → `kernel.*`/`terminal.*`；先保留 `core/__init__.py` 作为转发？**不**——直接改所有 import，删除 `core/` 包。
3. `frame.py` 拆分：
   - Rect/split 代数 → `geom.py`；
   - `splice_row` → frame 私有；
   - `Hit`/`HitPath` → `hit.py`；
   - `LAYERS`/`Overlay`/`apply_overlays` → `overlay.py`。
4. `viewport+scroll` 合并 → `layout.py`；`RowSpan` 新增；`Scroll` 2D 值先保留 1.x 行为（x 恒等）。
5. `block` → `document`：`Block` → `Section`；`Document.add` 返回 `Section`。
6. 删除 `core/` 包与 `core.__all__`；建 `kernel/__init__` + `terminal/__init__`。
7. 测试同步移动；`tests/core/*` → `tests/kernel/*` / `tests/terminal/*`。
8. import-linter 规则收紧；`kernel` 不得 import terminal/widgets/app。

## 6. 门禁

- `pytest` 全绿；
- 57 golden **逐字节不变**；`render-hash` 不变；
- demo 两条命令输出不变；
- `ruff`/`pyright`（kernel）/`lint-imports` 通过；
- `grep -r "from .*core" src/motui` 为空；
- `python -c "import motui.kernel"` 不触发 `os/sys/io/ctypes`（`sys.modules` 断言测试）。

## 7. 退出条件

- [ ] `kernel/` 纯值，`terminal/` 唯一 I/O；
- [ ] `core/` 目录消失；
- [ ] `frame.py` ≤500 行，`geom`/`hit`/`overlay` 独立；
- [ ] demo 字节不变（这是“机械迁移”的证明）；
- [ ] 测试目录跟随模块移动。

## 8. 回滚

- 本波是文件移动 + import 修复；回滚到 `2.0/w0` 即可；
- 由于删除 `core/`，回滚前先确认 W0 分支可构建。

## 9. 交接

`W1-handoff.md`：

- 文件迁移清单（实际路径）；
- `Screen` ABC 的成员表；
- `kernel/__init__` 与 `terminal/__init__` 的导出列表；
- 仍然保留的 1.x 行为（例如 `Scroll` 的 x 恒等）；
- 下一波 W2 需要改的 38 处 `render` 清单。
