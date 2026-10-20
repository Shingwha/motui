# W8 · 1.2.0 发版（阻塞，等用户指令）
> 状态：**不执行**。按用户 2026-10-21 指示：发版前用户先做测试重构；版本 bump、release notes、
> tag、push 全部等用户明确指令。

## 发版前条件

1. 用户的测试重构完成并合并。
2. W7a demo 与 W7b docs 已合并，全量门禁绿。
3. 用户确认可以发 1.2.0。

## 发版清单（届时执行）

- `pyproject.toml` version → 1.2.0；`uv lock`；`src/motui/__init__.py` fallback 对齐。
- `CHANGELOG.md` 的 `[Unreleased]` 整理为 `[1.2.0] — <date>`，加 `**Breaking**` 说明
  （事件模型、driver API、FocusManager、take_result、组件改名、删除的旧名）。
- `docs/releases/1.2.0.md`：面向读者的 release notes。
- 全量门禁：pytest / golden / framebench / demo 两入口 / import graph。
- 用户确认后 commit、push、tag（`v1.2.0`）、GitHub release。

## 禁触

- 本波未开始前，不改 `pyproject.toml`、`uv.lock`、`CHANGELOG.md`、`docs/releases/**`。
- 不主动 push / tag / 发版。
