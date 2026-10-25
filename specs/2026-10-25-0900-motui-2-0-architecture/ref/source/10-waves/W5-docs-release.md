# W5 · 文档与 2.0 收口

> 上级：`README.md`　依赖：全部前序波次
> 状态：ready

## 1. 目标

把 2.0 变成可发布、可学习、可迁移的版本：

- 重写 README / ARCHITECTURE / CONTRACT / WIDGETS；
- 迁移指南（1.x → 2.0）；
- ADR 固化；
- 示例（quickstart / snake / dashboard）；
- 版本 2.0、CHANGELOG、CI 全绿。

## 2. 为什么

- 1.x 有 40 个历史 spec、3 份契约文档、大量“1.x 兼容”叙述；2.0 断代后必须收口。
- 用户需要一页迁移表，而不是读 10 份 spec。
- 三个可执行示例比任何营销文案更能证明能力。

## 3. 任务

### 3.1 文档结构

```
docs/
  ARCHITECTURE.md    # 分层、模块、依赖、所有权、扩展点
  CONTRACT.md        # 2.0 契约（值/协议/不变量）
  WIDGETS.md         # 组件目录 + 构造参数 + take/walk
  MIGRATION.md       # 1.x -> 2.0 一页表 + 配方
  adr/               # ADR-001..023（从 11-decisions 拆出）
```

- 删除 1.x 的过时段落（`Themed`/`Revisioned`/`TUI`/`take_result`）；
- 每个公开 API 至少一个可执行示例；
- 文档中的代码块由 CI 执行（至少 quickstart/snake/dashboard）。

### 3.2 README

- 新 quickstart（`App` + `Input` + `Text`）；
- 能力矩阵（游戏/图表/仪表盘/宽表）；
- 三行安装 + 一个示例；
- 链接到 ARCHITECTURE/MIGRATION。

### 3.3 示例

- `examples/quickstart.py`（≤30 行）；
- `examples/snake.py`（≤120 行，Canvas + Fill + every）；
- `examples/dashboard.py`（实时 sparkline + resize）；
- `examples/wide_table.py`（ScrollPanel x）；
- 全部 headless 可跑，CI 执行。

### 3.4 迁移

- `MIGRATION.md`：旧名 → 新名（引用 `05-api-surface.md` 表）；
- 配方：App、widget、controller、Screen、theme、test；
- 删除名单（`take_result`/`Resultful`/`TUI`/`Revisioned`/`Themed`/`set_focus_targets`/`EveryHandle`/`RowRange`/`ClampedCursor`/`ansi.*` 公开导出）；
- 不提供 codemod（一次性改写，人工评审）。

### 3.5 发布

- `pyproject.toml` 版本 2.0.0；
- `CHANGELOG.md` 2.0 段（Breaking / Added / Changed / Removed / Performance）；
- `CONTRIBUTING.md` 更新目录与门禁；
- 不 tag / 不 push / 不发 PyPI，除非用户明确要求。

### 3.6 清理

- `docs/specs/` 历史 spec 归档到 `docs/adr/` 或删除；
- 删除死代码、旧测试、旧 golden（W2 语义化后）；
- `tools/api-2.0.txt` 冻结。

## 4. 门禁

- 全量 `pytest` + 57 语义 golden；
- `framebench` 阈值；
- `ruff` / `pyright` / `lint-imports` 0；
- `api.py --check` 通过；
- 三个示例在双平台 CI 跑通；
- `python -m motui < /dev/null` / `--pages` 通过；
- 文档链接检查（无死链）。

## 5. 退出条件

- [ ] README/ARCHITECTURE/CONTRACT/WIDGETS/MIGRATION 全部 2.0；
- [ ] ADR-001..023 完整；
- [ ] 三个示例可执行；
- [ ] 旧名全部消失；
- [ ] 版本 2.0.0；
- [ ] 无 “1.x 兼容/迁移中” 叙述。

## 6. 回滚

- 文档波不改运行时；回滚只影响发布。
- 发布前必须过全部前序波次门禁。

## 7. 交接

`W5-handoff.md`：文档清单、示例路径、发布检查表、未决项（例如 `DocPos` 是否 2.1）。
