# handoff · W3-b Motion 双画板 + Splash 2.0

分支 `dm-w3b-motion-splash`（基于 main `6de43d1`，W2-a + W2-b 均已合并），
worktree `C:\Users\shifu\.worktrees\mocode-tui\dm-w3b-motion-splash`。
环境实测 `uv run python --version` = **3.13.16**（`.python-version` 钉生效）。
波末全量 `uv run pytest -q` = **1657 passed**（基线 1653 + 本波恰 4 条
`tests/test_demo_motion.py`），`uv run ruff check .` 零告警，
`tools/semantic.py --check` 10 场景 match，`tools/api.py --check` 198 名零变化
（kernel/widgets 本波零 diff）。

## A · 交付清单（自动事实）

### A.1 文件与接线

- `src/motui/demo/sections/motion.py`（新，507 行）：`MotionScene` + `RINGS_SEED`
  （=20261028，导出）。默认 `mode == "rings"`（PixelCanvas 判定游戏）；`tab`
  切到 `"snake"` 模式（组合自己的 `SnakeScene` 实例，`demo/snake.py` 未迁移）。
- `src/motui/demo/sections/splash.py`（重写，530 行）：`SplashScene` 全部契约名保留
  ——`SPLASH_ROTATE_TICKS(120)/SPLASH_STYLES/LOGO_START/LOGO_END` 真实使用，
  `SPLASH_GLYPHS/SPLASH_GLYPH_TICKS` 保留为 `motui.demo.showcase` re-export 契约名
  （showcase.py 禁触，导入面不能断），并获得新工作：pulse 呼吸点按包吃 glyph。
- `src/motui/demo/sections/__init__.py`：`"motion"` 换成 `MotionScene(theme)`；
  `"snake"` 仍是独立 `SnakeScene(theme)` 对象（契约名不动，
  `tests/test_demo_scenes.py` 零修改通过）。`__all__` +`MotionScene`。
- golden 重录恰 2 个：`tests/golden/semantic/motion.txt`、`splash.txt`；其余 8 个
  `--update` 的 LF 假 modified 已 `git checkout` 还原，逐字未变（W1-b B.3 的坑，
  再次应验）。
- 新测试恰 4 条：`tests/test_demo_motion.py`（判定窗口逐值、帧确定性+阶梯标签、
  tab 换板、splash 像素 wordmark+退出契约）。

### A.2 rings 行为契约落点（判定数值逐条照抄工单，未改）

时间源 = `phase / 60`（模块常量 `_TICK_HZ`）；首生 +0.4s、间隔 1.2s；approach 1.0s
26→8 线性；目标盘 r=8，出生 ease_out_back 0.15s 弹入；space 判最近未判圈
`|now−(born+1.0)|`：≤0.06 Perfect +300、≤0.12 Good +100、≤0.20 强行命中（combo
清零、0 分）、无圈入窗则 no-op；超窗自动 Miss（combo 清零、attempts+1、原地 r=8
冷色 0.4s 淡出）；Perfect/Good 计 hits，强行命中与 Miss 计 attempts（HUD
`hits/attempts` 口径=准确率分母）；入 Good 窗缩圈环白色 ~10Hz 闪烁；命中爆散 0.35s
ease_out_back 8→28（+20 过冲），色 Perfect 白/Good 粉/强行冷。出生位置：
`random.Random(20261028)`，margin = `min(34, 子格宽高的一半)`，均匀取点；槽位色
1..4 按并发序轮换。**board resize → RNG 重置**（照工单）；已活环保持原位。

### A.3 Splash 2.0 结构

wordmark = 152x96 设计网格上的手绘子格笔画（笔画宽 3，T/I 竖笔 4；M 双竖+对角 V、
O 参数椭圆、U 半椭圆底、I 上下衬线），`_WORDMARK` import 期一次构建，按 canvas
尺寸缓存（`_GEOM_CACHE`：band 索引 / 列索引 / 点集）。fill 层承载字（不衰减），
art 层承载动效：neon 白扫光 = 头列 + 12 列衰减拖尾（**显式逐像素 heat**，同一
decay 曲线 255−k·10，保证 render 是 phase 的纯函数，头less 重放不依赖衰减步数）；
plasma 12 槽色相轮 `+phase//2` 步进；retro 琥珀/绿按 SPLASH_ROTATE_TICKS 周期翻转
+ 隔 cell 行暗槽扫描线；starfield 三层视差星（速度 1/12、1/6、1/3 子格每 tick，
近层双点亮星+闪烁、永不落在笔画上）+ 红青 glitch 带（仅 starfield）。四包配色
身份与旧版一致（neon 用 LOGO_START→END 渐变）。契约原样：tick 永不转场、
任意键/点击 → `"menu"`、restart() 重洗包序、`"press any key"` 提示行。

### A.4 性能实测（写入两模块 docstring）

协议：CPython 3.13.16 / Windows，7 轮 × 200 帧，取各轮中位数（本 VM 轮间漂移
±20%，med-of-med 口径）：

| 场景 | best | med-of-med |
|---|---|---|
| motion rings（3 活环）@100x30 | 4.95 | **5.00 ms** |
| motion rings @80x24 | 4.52 | 4.59 ms |
| motion snake 模式 @100x30 | 8.03 | 8.09 ms |
| splash neon/plasma/retro/starfield @100x30 | 5.86–6.19 | **5.89–6.32 ms** |

同会话参照（shipped 场景同协议）：dashboard 6.25、components 5.87、layout 4.22、
**snake 独立场景 7.41 ms**（snake 模式的 8.1 ≈ 原板 7.4 + 阶梯 chrome 0.7，
非本波回归）。校准结论：≤8ms 达标；余量来自下述两处尺寸帽。

### A.5 确定性验收实录

- `scene_output`（真 painter 字节）两场景 × 7 相位（0/20/40/90/155/300/909）两次
  逐字节一致；
- wipe 重放 menu→motion→splash 40 帧（20+20 tick）两次逐帧一致；
- `render_scene("motion", …)` 两次逐字一致（tests 钉死）。

## B · 偏差与坑（接手必读）

1. **画布尺寸帽（对"约 152×96"的有意偏差）**：quantize 成本 ∝ 格数 × 墨密度，
   kernel/widgets 只读不能优化，唯一合法杠杆是尺寸。实测 76x23 满规格 wordmark
   ~9ms med-of-med **超预算**，落 60x17（120x68 子格，≈0.8×）；rings 板同理落
   68x20（136x80 子格）。两处均在 render 里帽 + docstring 声明。若后续 kernel
   优化了 quantize（如空层快路径），先恢复 76x24 / 80x24。
2. **衰减拖尾的确定性实现**：`decay()` 是有状态 API（每 tick 调一次），而 headless
   的 render_scene 只 render 一次、不 tick——依赖 decay 状态的帧无法逐字重放。
   落法：拖尾 heat 逐像素显式写（`art.heat[idx] = 255−k·步长`，与 decay 同曲线），
   `canvas.clear()` 后整帧重画。**结论：像素场景要确定性，就别把 decay 当状态
   机用；它适合"活体流沙"，不适合快照回放。**
3. **`_fading_ring` 直写公开栅格**：`Raster.set` 恒置 heat=255，无法表达"指定
   heat 的墨"（爆散烧尽/MISS 淡出需要）。按 `PixelCanvas.unset` 的先例直写
   `art.slot/heat` 公开 bytearray——这是画图动词不是量化逻辑，红线不犯；
   kernel 若将来收编 `Raster.set(..., heat=)` 或 `plot(x, y, slot, heat)`，
   此处一行转发即可（最小补丁建议，非缺陷）。
4. **rings 的 on_click = 判定**（space 的鼠标门）：工单叙事提到原 pixel.py 有
   "鼠标踢球"，但誊写契约里没有 kick 语义，遂把点击落成与 space 等价的判定，
   交互上完整、语义上不新增数值。若 lead 另有拍板（例如点击 no-op），改
   `MotionScene.on_click` 一行。
5. **rings 记分口径**：契约只写 Miss "attempts+1"。强行命中消费了圈（爆散），
   计 attempts 不计 hits——即 attempts=全部已判圈数，hits=Perfect+Good，
   HUD `hits N/M` 是准确率。combo 仅 Perfect/Good 增。
6. **空按不罚**：无未判圈时按 space 是 no-op（契约只定义"对最近未判圈"的判定，
   未定义空按惩罚）。
7. **`SPLASH_GLYPHS/SPLASH_GLYPH_TICKS` 是活契约名**：showcase.py re-export
   （禁触）从 `sections.splash` 导入它们，删了就断公共面。给的新工作：pulse
   呼吸点的亮点按包吃 glyph（老 glyph 循环的唯一幸存）。别删。
8. **`Line.clip` 即使行宽合适也走全程 cut_line**：本波帧路径里把"必然放得下"的
   拼行改成 `pad + row`（不 clip），chrome 行用 `_fit()`（先比 `.width` 再决定
   是否 clip）。这一处改动约省 4-5ms/帧（profile 实证 clip/cut_line 占 41%）。
   写像素节 chrome 的后来者注意。
9. **本 VM 噪声**：轮间漂移 ±20%，性能结论必须多轮中位数、最好附带同会话
   shipped 场景参照（A.4 表），单轮数字不可信。
10. **menu 瓷砖 blurb 未动**：瓷砖仍写 "the snake, live"（menu.py 稳定区禁触）。
    motion 现在是 rings+snake 双板，blurb 略过时；改不改由 lead 定（改则连
    menu golden 重录，一行事）。
11. **octant 标签**：工单写"未探测"，UI 语言全英文，落 `"unprobed"`；octant 槽
    无 canvas，纯文字（kernel 词表无 octant，探测不存在——照 W2-a 拍板口径）。

## C · 指针

- 实现：`src/motui/demo/sections/motion.py`（rings/双板/阶梯）、
  `src/motui/demo/sections/splash.py`（wordmark/四包）
- 测试：`tests/test_demo_motion.py`；golden：`tests/golden/semantic/{motion,splash}.txt`
- 上游契约：`handoff/W2-a-canvas.md` A 节（PixelCanvas 全签名，未变）、
  `handoff/W1-b-shell.md` B 节（wipe/60Hz）
- 建议后续（非本波）：kernel `Raster` 增 `unset`/带 heat 写入动词 →
  `_fading_ring` 转发；quantize 空层快路径 → 两处尺寸帽恢复满规格。
