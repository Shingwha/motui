# 12 · 验收：定义完成（DoD）

> 上级：`README.md`　相关：`10-waves/*`
> 状态：ready

2.0 完成 = 下面五组全绿 + 每个波次门禁通过。

## 1. 结构

- [ ] `kernel` 不 import `os/sys/io/ctypes/termios/tty/select/asyncio`（import-linter）。
- [ ] 依赖图无环；`kernel ← widgets ← app`，`kernel ← terminal`。
- [ ] 每个组件只有一个渲染签名：`render(Constraints) -> Surface`。
- [ ] 没有 `Revisioned` / `_CHILD_ATTRS` / `_looks_interactive` / 能力协议 `isinstance`。
- [ ] `Scroll` 只有一套实现（Pane / ScrollPanel 共用 `Axis`/`thumb`）。
- [ ] `Cursor` 只有一套实现（`ClampedCursor` 删除）。
- [ ] 无单文件 >900 行（`markdown/component.py` 例外需注释）。
- [ ] `core/` 目录不存在；`terminal/` 只有 I/O。
- [ ] `App` ≤250 行；`Runtime`/`Workspace`/`Terminal` ≤450 行。

## 2. 质量

- [ ] `ruff` 0。
- [ ] `pyright --strict`（kernel）0；`pyright`（widgets/app）0 error。
- [ ] `lint-imports` 0。
- [ ] `tools/api.py --check` 通过；公开面计数：root ≤30、kernel ≤40、terminal ≤20。
- [ ] `tools/growth.py` 通过（给帧类型加默认字段后零失败/零字节变化）。
- [ ] 每个公开 API 有 docstring + 一个可执行示例。

## 3. 能力

- [ ] `examples/snake.py` ≤120 行，headless 跑完一局。
- [ ] `examples/dashboard.py` 实时 sparkline，resize 后仍正确。
- [ ] `examples/wide_table.py` 200 列在 80 列 pane 可滚到最右列。
- [ ] 20 列屏返回 40 列内容：不换行、不破坏邻行。
- [ ] `every(0.05)` 跑 1s：19–20 次（误差 ≤5%）。
- [ ] `Canvas.plot` 支持 cell/half/braille，各有快照。
- [ ] 鼠标点击画布 → `on_click(Pos)` 坐标正确（含滚动偏移）。
- [ ] 代码块长行完整可读；`Diff` 默认截断但可选 OVERFLOW。
- [ ] `Input` 恒一行，游标水平跟随。
- [ ] `take()` 的 `None`/`False` 两态有测试；`walk()` 覆盖整棵树。

## 4. 性能

- [ ] 80×24 全异色 Canvas ≤2.0 ms/帧（1.2.3 无 Canvas；参考 1.65ms 原型）。
- [ ] 单色 Canvas ≤0.4 ms/帧（参考 0.23ms）。
- [ ] 普通页面帧字节数不增加（允许因裁剪修正而减少）。
- [ ] snake 每步线上字节 ≤150（1.2.3 实测 115）。
- [ ] `framebench` 不劣化 >10%。

## 5. 文档

- [ ] `docs/ARCHITECTURE.md` 有分层图与依赖规则。
- [ ] `docs/CONTRACT.md` 只描述 2.0，无历史包袱。
- [ ] `docs/WIDGETS.md` 组件目录 + `take/walk` 用法。
- [ ] `docs/MIGRATION.md` 一页表 + 配方。
- [ ] `docs/adr/` 至少 23 条。
- [ ] README quickstart / snake / dashboard 可执行。
- [ ] 版本 2.0.0；CHANGELOG 2.0 段完整。
- [ ] 无 “1.x 兼容/迁移中” 残留。

## 6. 波次门禁摘要

| 波 | 必须 |
|---|---|
| W0 | 旧测试全绿 + 字节 golden 不变 + 工具生效 |
| W1 | demo 字节不变 + kernel 零 I/O + `core/` 删除 |
| W2 | 38 render 迁移 + 裁剪 + Canvas + 语义 golden |
| W2.5 | WrapMode + 59 fit + 代码块/Input 变化分类 |
| W2.6 | 宽表可达 + x/y 独立 + hit 映射 |
| W3 | 树/hooks/keymap/focus + 行为 1:1 |
| W4 | TerminalOptions + Section/Axis + 定时器 ≤5% |
| W5 | 文档/示例/版本 |

## 7. 评审清单（每个 PR）

- [ ] 是否新增了第二扇门？（`ansi`/`take_result`/`TUI`/`App.add`…）
- [ ] 是否给未实现功能预置了字段？
- [ ] 是否在 `render` 里读了时钟？
- [ ] 是否让内容携带了 escape？
- [ ] 是否新增了公开自由函数（首参是内核值）？
- [ ] 是否更新了 spec/契约/API 快照？
- [ ] 是否有对应的失败测试（先红后绿）？
- [ ] 是否在双平台 CI 通过？

## 8. 发布检查

- [ ] `uv run pytest` 全绿；
- [ ] `framebench` / `golden --check` / `api --check` / `growth` 全绿；
- [ ] `python -m motui < /dev/null` 与 `--pages` 通过；
- [ ] 三个示例在 CI 通过；
- [ ] 不 tag / 不 push / 不发 PyPI（除非用户明确要求）。
