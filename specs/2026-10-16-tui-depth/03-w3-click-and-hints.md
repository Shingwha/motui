# Spec tui-depth · W3 点击策略与提示（波次 W3）
> 分支 `td3-clicks`；前置：W2；深读：`00-overview.md`（D7/D8/D9）。
> **最高约束：双击/三击只在 `SelectionGesture` 内计数（无新 tier）；Pointer 的消歧只动它的 motion
> 分支；Tooltip 是 chrome tier 的 overlay 控制器，读叶子的 `hint` 属性，无回调。**

## 目标

1. 三击选行转正（双击已有词选）；计数用 `clock()`，窗口沿用 `double_click_seconds`。
2. `Pointer` 用 `name` 消歧：按键名 motion = 拖拽；否则 hover（解 W5b 未决 #1）。
3. `chrome.Tooltip`：指针附近单行提示，叶子 `hint` 属性驱动。
4. gallery 演示 + 文档同步。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| `_last_press` 与 `_word_select`；`double_click_seconds=0.35` | `gesture.py:149-161,240-260,292,318-359` |
| 三击现状「out of scope」的测试 | `tests/test_gesture.py:657` |
| console 忽略 double-click flag（保持） | `keys/console.py:86-87`；`tests/test_keys_sources.py:185` |
| Pointer motion 分支只看 `button != 0` | `pointer.py:150-157` |
| Toasts overlay 形态（`paint(frame)->layout` + 注册/注销） | `chrome.py:672-698,828-856`；`frame.py:124-144` |
| 选择高亮是纯函数 overlay（Tooltip 的定位可借 `hit_test`/`hit_component`） | `core/selection.py:198-251`；`app.py:839-854` |

## 工单（按序执行，每项一个 commit）

### T1 `gesture.py`：三击选行（D7）

- 在 `_last_press` 基础上加点击计数：同格、`double_click_seconds` 窗口内连按 → 2 = 词选（现状）、
  3 = **行选**（该显示行整段）；第 4 次起回到 1（重新计数）。行选的「行」= 命中的块行的可见整行
  （用 `_word_run` 同层的行度量，跨块不延伸）。
- 更新 `tests/test_gesture.py:657` 的 out-of-scope 断言为新行为；新增三击/回落测试。
- docstring 与 `docs/DESIGN.md` 的 Selection 段：词选/行选与计数窗口。

### T2 `pointer.py`：拖拽与悬停消歧（D8）

- motion 分支改为：`event.name in ("left","middle","right")` **或** `event.button != 0` → 拖拽分支
  （清待定、不动 hover）；否则 → hover 分支。
- 更新 pointer docstring 的「report 规则」段与 `docs/COMPONENTS.md` 的 Pointer 行；
  `tests/test_pointer.py` 增两条：真机 32 报文（`name="left", button=0`）不再动 hover；
  `name="none", button=0` 走 hover。
- **验收含**：`git grep` 确认 W5b 未决 #1 的措辞（“message 32/35 同名”）从 spec 之外无残留。

### T3 `chrome.py`：`Tooltip`（D9）

- 新类 `Tooltip(Themed)`：`Tooltip(tui, pointer, *, theme=None)`；挂载时 `frame.add_overlay(self)`、
  `detach()` 注销（身份比较，沿用 Toasts 形态）。
- `paint(frame) -> ScreenLayout`：读 `pointer.position` 与 `pointer.hovered`；叶子有 `hint` 属性
  （getattr，非空 str）→ 在指针下方（越界则上方）画一个单行盒（`Padding`/`Panel`-风格边框可省，
  用 `theme.toast` 底 + 一行文本，宽度 clamp 进 frame）；无 hint/无指针 → 原样返回 layout。
- 测试：有/无 hint 两态、越界翻转、`detach` 后零绘制；`hint` 变化后下一帧更新。

### T4 gallery + 文档

- gallery：`Pointer` 之后挂 `Tooltip`；`action` 页给三个原语设 `hint`（构造后赋 `label` 含提示或
  直接设 `btn.hint = "..."`——由页面决定）；`features` 页文字更新（拖拽 hover 不再跟随）。
- `docs/COMPONENTS.md`：新条目 `Tooltip`（协议：叶子 `hint`）；`focus`/`overlay` 段补一行。
- `README.md`：驱动/组件表补 Tooltip 一行；`docs/DESIGN.md` 命名表加 `Tooltip`。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 只增不减；贴被更新的既有断言（`test_gesture.py:657` 一带）。
2. 探针：连按三次的 `selection` 区间（词/行/回落）；`name="left"` 拖拽三态 `hover` 不动、
   `name="none"` 悬停三态；Tooltip 两态 + 越界翻转的 overlay 行。
3. `demo.py < /dev/null` exit 0；`--pages` 12 页头；dump 与改前逐字符一致（Tooltip 未触发时零字节）。
4. framebench hash 不变（本波不碰渲染字节；Tooltip 默认不挂）。
5. import 干净；README 块全绿。

## 禁触清单

- `Text`/`Markdown` 的行内命中（W2 已定）；`selection.extract`/`copy_on_select` 的契约
- `console.py` 的双击 flag 现状（继续忽略）；`specs/**`；`examples/` 除 T4 两处

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论 / 三击与消歧探针 / Tooltip 探针 / framebench hash /
被更新的既有断言 / 偏差与取舍 / 未决问题 / 真机手测：未执行（提示观感、拖拽无重叠）。
