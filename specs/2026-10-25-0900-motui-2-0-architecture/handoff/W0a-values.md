# W0a 交接 · 值类型（不改变行为）

> 分支 `2.0/w0a-values`；起点 `4defdd0`（main @ `400773b`）。前置 handoff：无。
> 结论：T1–T5 全部完成；921 旧用例 + 81 新用例全绿；golden/render-hash 不变；生产代码零真实 import。
## A. 交付面与门禁

### diff（`git diff --stat main...HEAD`）
```
 src/motui/kernel/__init__.py         |  28 +
 src/motui/kernel/cell.py             | 322 +
 src/motui/kernel/geom.py             | 145 +
 src/motui/kernel/layout.py           | 139 +
 src/motui/kernel/text.py             |  29 +
 tests/kernel/__init__.py             |   0
 tests/kernel/test_geom.py            | 198 +
 tests/kernel/test_kernel_imports.py  |  90 +
 tests/kernel/test_scroll_values.py   | 171 +
 tests/kernel/test_surface.py         | 223 +
 tests/kernel/test_wrapmode_values.py |  27 +
 11 files changed, 1372 insertions(+)
```
### 新公开签名（`motui.kernel` 恰好 12 名）

```python
Axis(X, Y); Size(width=0, height=0); Pos(x=0, y=0)
Rect(x=0, y=0, width=0, height=0)   # frozen/slots/kw_only
    right/bottom/area; contains(Pos); intersect(Rect); split(Axis, weights, min_size=0)
Cell(char=" ", style=Style(), link=None, action=None)
Segment(text, style=Style(), link=None, action=None)
Line(segments=())                    # text/width/segments/from_text/clip(width)/pad(width)
Surface(width=0, rows=())            # height/blank(Size)/of(rows, width)
WrapMode(WORD, CHAR, ELLIPSIS, CLIP, OVERFLOW)
Constraints(width=0, max_height=None)
ScrollAxis(offset=0, content=0, viewport=0, sticky=False)
    max_offset; clamp(); reveal(row); thumb(track, min_length=1)
Scroll(x=ScrollAxis(), y=ScrollAxis(sticky=True)); with_x(axis); with_y(axis)
```
### 门禁实测
- `uv sync --locked` OK；`import motui` 指向本 worktree 的 `src/motui/__init__.py`。
- `pytest -q -p no:cacheprovider`：**1002 passed**（921 旧 + 81 新），0 failed。
- `tools/golden.py --check`：**57 topics match**。
- `tools/framebench.py`：`render-hash a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（不变）。
- `python -m motui < /dev/null`：exit 0，70 行；`--pages`：exit 0，4059 行。
- import 隔离：真实 import 语句 0 处。工单 grep 的 3 处命中全是 `demo/topics/*` 既有展示字符串（main 已存在，禁触）。

## B. 偏差与取舍

1. **`Line.styled` 未实现**（按工单）：kernel 不构造 terminal 字节；`Segment` 只保留 text/style/link/action 与宽度。
2. **`Style` 过渡占位**（`cell.py:87`）：8 字段、无 SGR 的冻结值，不从包根导出；W1 用真实 `core.style.Style` 替换，`Cell.style` 默认仍是 `Style()`。
3. **`Line.clip(width: int)`** 仅整数硬裁（W2.5 换 `reflow(mode, width)`）；双宽字符跨边界时整字丢弃，故结果可窄于上限；`pad` 负责补齐。
4. **`Surface.blank(size)`** 按工单“height 行空行”返回 `Line()`（宽 0），不预填空格；只有 `Surface.of` 保证每行恰为 `width`。
5. **命名**：滚动轴值用 `ScrollAxis`，避免与 `geom.Axis` 冲突；包根同时导出 `Axis`（几何）与 `ScrollAxis`。最终公开名待 lead 在 W2.6 决定。
6. **sticky clamp 近似**：值内没有“旧 extent”，按工单以自身 `max_offset` 等价判断；贴底/夹取两分支对可达状态同值，但无法复刻 1.x“内容增长后跟随到底”。W2.6 需恢复 previous-extent。
7. **`reveal` 不改 `sticky`**：1.x `scroll_to` 会在移动时 attach/detach；本实现的 offset 与 1.x 逐值一致（已对照测试），flag 留给 W2.6。
8. **内容门**：`Cell` 的 `action` 也过门（source-02 §10）；复制的 `Segment` 保持 1.x 语义（action 不洗、`compare=False`）。W1 合并时统一。
9. **导入隔离测试**：裸 `import motui.kernel` 必先执行 1.x facade（eager import core/widgets/app），字面“sys.modules 无 core”不可能成立且 facade 禁触；测试在子进程用 stub `motui` 根包加载 kernel，断言只有 `motui.kernel*` 6 个模块。
10. **split 语义**：复刻 1.x `_ratio_sizes`（floor、最后吃余数、`min_size` 抬升后再裁剪）；浮点 floor 转 `int` 保持 Rect 整型。随机断言只要求“剩余跨度允许时 >= min_size”（前序大权重可裁剪后续，1.x 同）。

## C. 位置与 commit

关键文件：

- `src/motui/kernel/geom.py:22` Axis，`:51` Rect，`:103` split
- `src/motui/kernel/cell.py:106` Cell，`:129` Segment，`:164` Line，`:236` clip，`:281` Surface
- `src/motui/kernel/text.py:16` WrapMode
- `src/motui/kernel/layout.py:27` Constraints，`:47` ScrollAxis，`:66` clamp，`:79` reveal，`:101` thumb，`:127` Scroll
- 测试：`tests/kernel/test_{geom,surface,wrapmode_values,scroll_values,kernel_imports}.py`
commit：

- `d3b9c11` kernel: add geometry values and the split algebra
- `66af66b` kernel: add cells, segments, lines and surfaces behind the content door
- `e59d8ed` kernel: add the wrap mode vocabulary
- `6ae4b1e` kernel: add constraints and two-axis scroll values
- `e645e84` test: lock the kernel surface and its import isolation
- 本文件（最后一个 commit）
## 未决

- sticky 的 previous-extent 复刻（W2.6）；`ScrollAxis` 最终公开名（lead）；`Style` 占位替换（W1）。
