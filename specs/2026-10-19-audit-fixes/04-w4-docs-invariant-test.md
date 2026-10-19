# Spec audit-fixes · W4：文档准确性与未测不变式（D4；F9/F10）
> ⏳ 待执行；前置：**W1 完成**（同改 `docs/DESIGN.md`，避免并发写冲突）。
> 深读：`00-overview.md`（D4）。本波只动文档、纯注释与一个测试文件，不碰任何行为代码。

## 目标

1. **F9a**：`docs/DESIGN.md:87` 的 motui 行补全 `headless_tui` / `snapshot`，凑齐文档自称的 34。
2. **F9b**：`docs/COMPONENTS.md:79` 的 "listed in `README.md`" 改指真实位置。
3. **F9c**：三处失解析的决策引用修正（`kernel/text.py:372`、`app.py:539`、`interaction/pointer.py:187`）。
4. **F10**：新增测试钉住 "styles resolve once at construction"。

## 工单（按序；每项完成跑 `uv run pytest -q -p no:cacheprovider`；本波不 commit）

### T1 DESIGN.md:87 补全 34 名字

- motui 行当前枚举 32 个，缺 `headless_tui` / `snapshot`（散文 :77-78 其实提到了）。
- 改法：把这两个名字加进行内枚举，位置与 `src/motui/__init__.py` 的 `__all__` 顺序/分组一致；
  改完与 `__all__` 逐个 diff，必须一一对应（共 34）。

### T2 COMPONENTS.md:79 修悬空引用

- "the 34 are listed in `README.md`" 是假的（README 从没列过）。
- 改指实际位置：`src/motui/__init__.py` 的 `__all__`（权威面）与
  `tests/test_api_root.py:14-19`（被测试钉住的清单）。二选一或都指，措辞自定，事实要对。

### T3 三处决策引用修正（先读 spec 原文再改，只修错号，不发明新格式）

- `src/motui/kernel/text.py:372` 的 "(D2)"：cluster-scanner 规则（"one home for the cluster
  rules"）在 `specs/2026-10-06-split-row-truth/00-overview.md` 里是 **D1**（:119 附近），
  该包的 D2 是 `styled()` 的 RESET 规则。把编号改对，或把引用改成"该 spec 的决策"字样。
- `src/motui/app.py:539` 的 "(D10)"：pin 规则（top/bottom 固定区）在
  `specs/2026-10-04-mocode-tui-fullscreen/00-overview.md` 里是 **D3**（:19 附近）。改对编号。
- `src/motui/interaction/pointer.py:187` 的 "(D10)"：`clear()` 的 best-effort 语义在任何 spec 的
  决策表里都找不到对应 D10——删掉裸编号，保留文字描述（或引到真正描述它的位置，以你读到的为准）。
- 只改注释文字，一行行为代码都不动。改完在报告里列：文件:行、旧引用、新引用、依据的 spec 文件:行。

### T4 F10：styles-resolve-once 测试

- 位置：`tests/test_theme.py`（或仓库现有的主题测试文件，先 `ls tests/` 确认）。
- 形状：对一批**构造时解析**样式的 `Themed` 组件，monkeypatch `Themed._pick` 计数，
  `render(width)` 期间断言计数为 0。名单逐个核实后再定——已知合法的 render 期读者：
  `Divider` 的 label 原地换肤（theme.py docstring 明文）、`Tabs`/`NavList` 的 unfocused
  focus 规则（直读 `self._theme.muted`，不走 `_pick`，计数法天然兼容）、
  `Find`/`Tooltip`/`Stats` 等 overlay（直读 theme 字段）。把"为什么这些组件不在名单里"
  写成测试里的注释。
- 断言语义：构造后改任何能改的（主题是 frozen，改不了——所以这条测试钉的是"render 不回头
  找主题"这一实现纪律），docstring 写清楚它保护什么。

### T5 全量回归

`uv run pytest -q -p no:cacheprovider` 贴总数（基线 1539/1 + 前面各波新增 + 本波新增）。

## 验收

1. pytest 贴总数/失败数/新增
2. DESIGN.md:87 的枚举与 `motui.__all__` 逐一对应（贴比对结果：34 = 34）
3. COMPONENTS.md:79 指向的位置真实存在且列全 34 个名字（贴证据）
4. 三处引用改动的依据表（文件:行 → spec 文件:行）
5. 新测试存在且贴输出；名单例外的理由写在测试注释里
6. `git diff` 确认本波零行为代码改动（`git diff --stat` + 逐文件看过）

## 禁触清单

- 只改：`docs/DESIGN.md`（仅 :87 一行区域）、`docs/COMPONENTS.md`（仅 :79 附近）、
  `src/motui/kernel/text.py`、`src/motui/app.py`、`src/motui/interaction/pointer.py`
  （这三个仅限注释文字）、`tests/test_theme.py`（或经确认的主题测试文件）。
- 禁触：任何行为逻辑、任何其它测试、golden、`CHANGELOG.md`、`specs/`、widget 源码。
- 不 commit / 不建分支 / 不 push。

## 报告格式（最终消息，中文）

工单状态表（T1–T5）/ 34 名字比对结果 / 三处引用修正的依据表 / 新测试的名字、名单与例外理由 /
`git diff --stat`（证明零行为改动）/ 自测真实输出 / 未决。
