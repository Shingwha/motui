# motui 2.0 收口重构 · 干净版 + 互动 Showcase

> 启动：2026-10-25 18:56（UTC+8）
> 基线：`main` @ `9d60730`（motui 2.0.0，1592 passed / 57 byte + 57 semantic golden）
> 上一组：`specs/2026-10-25-0900-motui-2-0-architecture/`（架构重构的完整记录）

## 1. 目标

把 2.0.0 从「已可用但保留兼容层」收成「一个干净的 2.0」：

1. 删除所有公开兼容层与旧 API（App/Runtime 旧构造参数、`split("vertical")`、`dock(edge=)`、`pin`、`Section.component`、`open_palette(list)`、Scrollbar 旧参数、`TUI`/`EveryHandle`/`take_result` 残留）；
2. 完成深层模型收口：`Revisioned`→`touch()`、`ScrollState`→`Scroll`、`RowRange`→`RowSpan`、`Themed`→`Widget.style()`、`group()`→`style()`、`Router`/`DEFAULT_HANDLERS`；
3. 把 `Runtime`/`Workspace`/`App` 真正拆开（文件行数向 Runtime/Workspace ≤450、App ≤250 靠拢）；
4. 重做 demo 为**单页互动秀**：开屏动画 → 主菜单（Breakout / Dashboard / Component Gallery）→ 可玩场景；`examples/` 只留精简 API 示例（quickstart / code / wide_table）；
5. 删除 57 个 topic tour 字节 golden，改为 4–5 个新场景的语义 golden；更新文档/CHANGELOG/MIGRATION；
6. 终验全绿，版本保持 2.0.0（未发布）。

## 2. 非目标

- 不新增功能（图片/动图、文档流横向滚动、网格布局等仍是 2.x/非目标）。
- 不 push / 不 tag / 不发 PyPI。
- 不为了行数拆而破坏行为；行数是结果，不是目的。

## 3. 用户已定方向（2026-10-25）

- Demo：**单页互动秀**；`examples/` 只留 quickstart / code / wide_table。
- 清理：**彻底清理**，包括 Revisioned→touch、ScrollState→Scroll、RowRange→RowSpan、Themed→style、Router 拆分、删旧字节 golden。
- 游戏：**Breakout 打砖块**。
- Golden：删除 57 topic tour 字节 golden 与 topic tour，录 4–5 个新场景语义 golden。

## 4. 波次表

| 波 | 主题 | 分支 | 关键产出 | 门禁 |
|---|---|---|---|---|
| C1 | 公开兼容层删除 | `2.0-clean/c1-surface` | 新构造面、Axis/Placement、Section.widget/placement、registry-only palette、ScrollbarStyles | 1592 passed / 字节不变 |
| C2 | 深层模型收口 | `2.0-clean/c2-model` | Revisioned→touch、Themed→style、RowSpan、Scroll/ScrollAxis、删除旧协议 | 全绿 / 缓存测试 / 字节不变 |
| C3 | Runtime/Workspace/Router 实拆 | `2.0-clean/c3-runtime` | `app/router.py`、Workspace 真状态、Runtime≤450、App≤250 | 全绿 / 定时器 / 大小 |
| C4 | 互动 Showcase | `2.0-clean/c4-showcase` | splash + menu + Breakout + dashboard + gallery；examples 精简；新语义 golden | 场景可跑 / golden |
| C5 | 文档与终验 | `2.0-clean/c5-close` | README/ARCHITECTURE/MIGRATION/CHANGELOG、终验、清理 | 五组全绿 |

依赖：C1 → C2 → C4 → C3 → C5（C3 是内部拆分，放 C4 后避免与 showcase 并行冲突；如时间紧可先 C4 再 C3）。

## 5. 全局不变量

1. 每波结束 `pytest` 全绿；行为/字节变化必须显式分类（C4 的 showcase 变化除外）。
2. 删除名字不保留 alias/shim；旧名只允许出现在 `MIGRATION.md` 的历史表。
3. 不改渲染/交互/定时器语义，除非该波明确要求。
4. 双平台 CI 配置保持；本地以 `uv run` 命令为准。
5. 不 push / 不 tag / 不发版。

## 6. 门禁命令

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/semantic.py --check      # C4 后为新场景
uv run python tools/golden.py --check        # C4 后删除
uv run python tools/framebench.py
uv run python -m motui --pages
uv run ruff check .
uv run pyright
uv run lint-imports
uv run python tools/api.py --check
uv run python tools/growth.py
```

## 7. 状态

| 波 | 状态 |
|---|---|
| C1 | ⏳ |
| C2 | ⏳ |
| C3 | ⏳ |
| C4 | ⏳ |
| C5 | ⏳ |
