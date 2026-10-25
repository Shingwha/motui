# C6 · Snake replaces Breakout; the gallery Tree folds on click

> 日期：2026-10-25（main @ `eba4c55` 之后）
> 变更：demo 游戏替换 + Gallery 点击路由修复

## A. 交付

- `src/motui/demo/snake.py`：`SnakeScene`，Canvas 绘制，确定性（本地 `random.Random(20261025)`），HUD/暂停/撞墙/自撞/重开，`tick` 每 4 tick 走一格。
- `src/motui/demo/showcase.py`：
  - `SCENES = ("splash","menu","snake","dashboard","gallery")`；Menu 选项 `Snake`；
  - `GalleryScene.on_click` 现在把局部坐标传给被点中的组件：`target.on_click(Pos(x=c,y=r))`；当目标是 Tree 且点击落在分支行上，再 `on_action("activate")` 折叠/展开。
- 删除 `breakout.py`、`tests/golden/semantic/breakout.txt`；新增 `snake.txt`。
- 更新 `tests/test_demo_scenes.py`（snake 机制 + Gallery 点击）、`tests/test_smoke.py`、README、`docs/releases/2.0.0.md`、`tests/golden/README.md`、`tools/semantic.py`。

## B. 测试/门禁

```
pytest -q -p no:cacheprovider          -> 1637 passed
semantic --check                       -> 5 scenes match
python -m motui --pages                -> 5 scenes
python -m motui < /dev/null            -> exit 0
--scene snake --frames 30 --headless   -> exit 0
--scene dashboard --frames 30          -> exit 0
examples quickstart/code/wide_table    -> exit 0 x3
ruff / pyright / lint-imports          -> 0 / 0 / 4 kept
api --check                            -> 188 names
growth.py (full)                       -> OK
framebench                             -> hash unchanged, replay ~685ms
```

## C. 行为说明

- 点击 Tree 的分支行（`app` / `workspace`）会立即折叠/展开；点击叶子只移动光标。
- Gallery 的点击仍先切换内部焦点（`_targets`），然后才把点击交给该组件；表/滑块/输入同理。
- Snake 的方向键/WASD 不允许 180° 反向；空格暂停/继续，死亡后空格重开；`q`/`esc` 回菜单。

## D. 位置

- `src/motui/demo/snake.py`
- `src/motui/demo/showcase.py:638`（Gallery click）
- `tests/test_demo_scenes.py`（snake + tree click）
- `tests/golden/semantic/snake.txt`
