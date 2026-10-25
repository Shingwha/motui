# W2 · 渲染契约：Constraints + Surface + Canvas

> 上级：`README.md`　依赖：`W1-kernel-split.md`　下一波：`W2.5-wrapmode.md`
> 状态：ready

## 1. 目标

把 38 处 `render(width)` 迁到 `render(Constraints) -> Surface`，并交付：

- `Surface` 的裁剪不变量（超宽行不再破坏整屏）；
- `Sizing.FILL` / `Fill`（填满窗格）；
- `Canvas` + `Marker` + `Sparkline`（画布）；
- `ScrollPanel` 统一到 `Viewport`；
- 语义 golden 重录。

## 2. 为什么

- 1.x 只有宽度；`ScrollView(height=)` 由宿主塞。
- 单 pane 全宽透传不裁剪：实测 20 列屏写 40 个 `A`。
- 画布/游戏/图表需要 height + 裁剪 + cell 栅格。

## 3. 契约（见 `02`）

```python
def render(self, c: Constraints) -> Surface: ...
# Surface: width（内容宽度）+ rows；每行 ≤ width
# c.max_height: None = 自然高度；int = 上限
```

三种形态：

| 组件 | Constraints | 返回 |
|---|---|---|
| 流式（Text/Markdown/Table） | `width=w` | 自然高度 |
| 固定窗口（List） | `width=w, max_height=h` | 恰好 h |
| 填满（Canvas/仪表盘） | `width=w, max_height=remaining` | 恰好 remaining |

容器单趟分配（`Column`）：

```python
y = 0
for child in self.children:
    c = Constraints(width=width, max_height=None if child.sizing is NATURAL
                    else max(0, bound - y))
    s = child.render(c)
    out.extend(s.rows); y += s.height
    if bound is not None and y >= bound: break
```

## 4. 任务

### 4.1 Surface 裁剪

- `Surface.of(rows, width)`：每行 `fit(width)`，短行 `fill(width)`；
- `Painter` 收到的一定是合法行；
- 删除 1.x 的“单 pane 透传不裁剪”路径；
- 测试：20 列屏 + 40 列内容 → 不换行、不破坏邻行。

### 4.2 38 处 render 迁移

按模块顺序：

1. `widgets/text.py`（原 `core/lines.py:Text`）
2. `widgets/decor.py`（Divider/Panel/Collapsible/Notice/StatusLine）
3. `widgets/layout.py`（Column/Row/Padding/Spacer/Grid）
4. `widgets/rows.py` / `strip.py` / `tabs.py` / `menubar.py` / `navlist.py`
5. `widgets/list.py` / `tree.py` / `table.py` / `choice.py`
6. `widgets/textfield.py`（Input/Editor）
7. `widgets/diff.py` / `markdown/*` / `syntax.py`
8. `widgets/indicators.py`
9. `app/*`（Find/Palette/Modal/overlays）

每迁一个：加 `Constraints` 测试（自然高度 + 固定高度 + 超宽裁剪）。

### 4.3 Section sizing / Fill

- `Section.sizing = NATURAL | FILL`；`Document.add` 校验“至多一个 FILL、在所有 FLOW 之后”；
- `Fill(widget)` 作为 `PaneContent`；`pane.fill(component)`；
- `Viewport` 对 FILL 内容跳过滚动索引，直接 `layout(rect)`；
- `TUI.fill`/`App.fill` 代理。

### 4.4 Canvas

```python
Canvas(w, h): put/text/hline/vline/box/blit/plot/surface/render
```

- `Marker`: cell/half/braille；
- 内部 dirty rows；`Surface` 只重建变化的行；
- 不写 escape；不 import painter/screen；
- `Sparkline` 薄封装；
- 测试：80×24 全异色 ≤2.0ms；单色 ≤0.4ms；braille 点位。

### 4.5 ScrollPanel 统一

- `ScrollPanel(child, height=None, axis="y")` 基于 `Viewport`；
- 1.x `ScrollView` 删除；
- 本波只跑 y（x 在 W2.6）。

### 4.6 golden

- 语义 golden（emulator）替换字节 hash；
- 差异分类报告：每 topic 只允许“裁剪/尺寸/新 fill 行为”；
- 旧字节 golden 标记 expected-change，W5 删除。

## 5. 门禁

- `pytest` 全绿；
- 语义 golden 重录 + 差异报告；
- `framebench` 不劣化 >10%；
- Canvas 阈值；
- 20 列屏 40 列内容回归测试；
- `examples/snake.py` headless 跑完一局。

## 6. 退出条件

- [ ] 所有组件 `render(Constraints)`；
- [ ] 超宽行被裁剪（无整屏破坏）；
- [ ] `Fill` 可填满 pane；
- [ ] `Canvas` 可用；
- [ ] `ScrollPanel` 基于 `Viewport`；
- [ ] golden 语义化完成。

## 7. 回滚

- 本波改动面最大；按子任务（4.1–4.6）各自可回退；
- 建议拆 3 个 PR：Surface+裁剪 / Canvas / golden 重录。

## 8. 交接

`W2-handoff.md`：

- 38 处迁移清单（完成/例外）；
- `Surface` 裁剪的边界测试；
- `Fill` 的校验规则；
- Canvas 性能数据；
- golden 差异分类表。
