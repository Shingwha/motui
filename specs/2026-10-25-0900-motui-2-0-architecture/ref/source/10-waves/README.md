# 10 · 波次总览

> 上级：`README.md`　下级：`W0` … `W5`
> 状态：ready

## 1. 执行规则

- 一波一分支：`2.0/w0-harness` … `2.0/w5-docs`；
- 每波必须**可独立合并**（不要求全部完成才可用）；
- 每波结束删除被替代的旧代码与旧测试，不留 shim；
- 每波结束更新 `docs/CONTRACT.md` / `docs/COMPONENTS.md` 中受影响的部分（W5 统一重写）；
- 任何与 spec 不一致的实现，先改 spec 再改代码。

## 2. 依赖图

```
W0 ──▶ W1 ──▶ W2 ──▶ W2.5 ──▶ W2.6
                │
                └──▶ W3 ──▶ W4 ──▶ W5
```

- W2.5/W2.6 可与 W3 并行（文件级不相交：W2.5/W2.6 动 kernel/text + widgets 的 wrap，W3 动 widgets/base + 交互）。
- W4 依赖 W3 的树与 hooks；W5 依赖全部。

## 3. 波次表

| 波 | 主题 | 关键产出 | 门禁关键词 |
|---|---|---|---|
| W0 | 契约与护栏 | 值类型 + emulator + 工具 | golden 字节不变 |
| W1 | 内核拆分 | kernel 零 I/O、Screen ABC | demo 字节不变 |
| W2 | 渲染契约 | Surface/Constraints/Canvas/Fill | 语义 golden 重录 |
| W2.5 | 换行 | WrapMode、59 fit | 只允许代码块/Input 变化 |
| W2.6 | 横向滚动 | ScrollPanel(axis)、OVERFLOW | 宽表可达最右列 |
| W3 | 树与交互 | Widget 树/hooks/keymap/focus | 行为 1:1 |
| W4 | 运行时/API | TerminalOptions、Runtime/Workspace/Router、Section | 定时器 ≤5% 误差 |
| W5 | 文档/2.0 | 文档、迁移、示例 | 全绿 |

## 4. 每波交付物

- 代码 + 测试；
- `HANDOFF.md`（在本目录下按波命名，例如 `W1-handoff.md`）：
  - 实际改动文件清单；
  - 与 spec 的偏差（必须为零或已回写 spec）；
  - 门禁输出摘要；
  - 未决项/下一波注意。
- golden 差异报告（W2 起）。

## 5. 回滚

- 每波一个合并点；失败只回退该波；
- 因为接口在同一波内成对引入/删除，回退不会留下半成品；
- W0/W1 的字节级门禁让回退有确定基线。

## 6. 完成定义

见 `../12-acceptance.md`。最低线：结构/质量/能力/性能/文档五组全绿。
