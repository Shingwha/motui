# W6 · 文档、API 清理、版本 1.2.0（lead）

> 占位；W5 合并后由 lead 执行。
> 分支：直接在 main 上做收尾提交（或短分支 `refactor/1.2-release`）。

## 目标

完成 1.2.0 的公共面与文档收尾：更新 README/DESIGN/CONTRACT/COMPONENTS、重写 Quickstart、更新 CHANGELOG、把 `pyproject.toml` 版本改为 `1.2.0`、更新 `tests/test_api.py` 的 facade 列表（不新增无意义断言）、删除所有旧名字残留、重录必要 golden、跑完整门禁和 demo 抽验。

## 依赖

W5a/W5b 已合并。

## 验收

- 全量 pytest、golden、framebench、两个 demo 入口全绿。
- root 公共名单收敛；`motui.core` / `motui.widgets` / `motui.app` / `motui.testing` 是唯一命名空间。
- README Quickstart 使用 `App`，≤ 20 行。
- `CHANGELOG.md` 有 1.2.0 段；`pyproject.toml` 版本为 1.2.0。
- `rg "motui\.(kernel|keys|interaction|commands)|Host|Delegate|BlockState|DEFAULT_HEADER_STYLE|COLORBGBG"` 无残留（specs 除外）。
- 不 push / 不 tag / 不发版。
