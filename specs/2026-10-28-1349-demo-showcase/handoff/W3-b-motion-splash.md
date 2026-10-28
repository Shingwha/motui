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

## D · fix round（真机验收后，基于 main `4e62978`）

真机两组问题（rings 板不可见、starfield 笔画过暗）+ kernel 两连改
（`1662d9e` 空格透明、`fd35c38`/`0d625e6` bg 可选化默认 None）引发的修订，
全部落在 `sections/motion.py`、`sections/splash.py` 与两个 golden 内。
波末 `uv run pytest -q` = **1659 passed**，ruff 零告警（demo 目录已被 ratchet
纳入 lint），golden 10 场景 match，api 198 名不变。

### D.1 改动清单

1. **rings 真机可见性（最高优先）**：目标盘从 art 层改画 **fill 层**
   （`canvas.fill_disc(...)`，half 实心块，真机任何字体都清晰——盲文字体里
   braille 盘曾是稀疏点块）；缩圈环 `thickness 1→2`；爆散/MISS 淡出环
   （`_fading_ring` 直写路径）同改两个半径（r∓0.5）达到等效 thickness 2；
   入窗白闪逻辑不变。阶梯对比条**故意保持 thickness 1**——它的职责就是展示
   marker 差距。
2. **starfield 笔画提亮**：wordmark 冰蓝 ramp `#7896e6→#ebf2ff` 改为
   `#a9c6ff→#ffffff`（旧低端深蓝在真机黑底上 M/O 几乎不可见）；星野三层槽位与
   红青 glitch 槽位原样保留（身份不变）。
3. **六个调色板全部删 `bg=(...)`**（_RING/_LADDER + splash 四包）：kernel 默认
   None = 半格未亮半行透终端背景。retro CRT 观感验证：扫描线靠明/暗双槽位色
   （绿 period 实测 (51,255,153)+(30,150,90) 同帧并存），与 bg 无关，不保留
   任何包的 bg。头less 字节断言两场景均无 `48;2`/`49m` SGR。
4. **两处尺寸帽恢复满规格**：上一轮因 8ms 预算落的 splash 60x17 / rings 68x20
   帽**撤销**，恢复 splash 76x23（≈工单"约152×96"）与 rings 板 80 宽×pane 高。
   依据：空格透明后 quantize 省掉全部空格 bg 涂色 + 空格 styled run，实测帧时
   降为原来的 ~1/3，帽的存在理由消失。
5. **golden 重录**：motion（阶梯半格 SGR 去 bg 尾）、splash（满规格画布 + 无
   bg + 提亮 ramp）；其余 8 个 LF 假 modified 已 `git checkout --` 还原。
   注意：phase 20 的 rings 板为空（首生 0.4s 未到），motion golden 的变化
   **只来自阶梯**；rings 新画法在 golden 相位不可见，真机/测试相位可见。
6. 顺带：`_mix` 的 `zip` 补 `strict=False`（demo 目录已被 ratchet 纳入 lint，
   B905 新上榜）。

### D.2 fix-round 性能复测（协议同 A.4：7 轮 × 200 帧 med-of-med，100x30）

| 场景 | best | med-of-med |
|---|---|---|
| motion rings（3 活环，满规格板）@100x30 | 2.73 | **2.84 ms** |
| motion rings @80x24 | 1.99 | 2.03 ms |
| splash 四包（满规格 76x23，无 bg）@100x30 | 3.79–3.89 | **3.88–4.02 ms** |

较 A.4（5.0/5.9-6.3ms）全面下降：kernel 空格透明是主因。8ms 预算满规格下
余量 ~2-3 倍。snake 模式未复测（板与 chrome 未变，参照 A.4 的 8.1ms 上界仍有效）。

### D.3 fix-round 偏差与坑

1. **seed=0 轮转里 amber retro 永不出现**：包序 [retro,neon,plasma,starfield]
   使 retro 只落在偶数 style period（0,4,8…），而包内琥珀/绿翻转按奇偶周期，
   偶数 period 恒绿。琥珀槽位/扫描线路径存在且与绿完全对称（live 随机包序会
   展示），快照与 golden 里看不到——非缺陷，但看 golden 别误以为琥珀丢了。
2. **`bg` 现在是"要不要底色"的显式选择**：任何想让半格图形自带底色的调用方
   必须显式传（demo 六板全不传）。若将来想要"画布自带暗底"的观感，正路是
   `fill_rect` 显式垫底，不是 palette.bg。
3. **满规格恢复后 motion golden 的盲区**：golden 相位（20）早于首圈出生
   （24），rings 画法的回归保护靠 `tests/test_demo_motion.py` 的判定链 +
   本轮 headless 帧目检，不靠 golden。若想 golden 也覆盖 rings，需要 lead
   调 PAGE_PHASE（牵动全部场景 golden，本波不动）。
4. demo 目录 ruff 排除已被 ratchet 摘除：`sections/*` 现在**逐文件 lint**，
   新写 demo 代码注意 B905（zip strict）/行长 100。

## E · splash 重构轮 + motion 进入修复补全（真机三项不满后）

用户真机验收：① 字母"不符合字母的构造"（自由手绘读不出字）；② 星星落在字母上
"空白背景很丑"；③（动画层次要求）入场/循环/呼吸三层。另有 lead 已修的 motion
"二次进入无响应"——本轮发现该修法在真实路径上不可达，已补全（见 E.3，**超出
本轮红线的唯一 motion.py 改动**，理由与复现见 E.2）。
波末 `uv run pytest -q` = **1660 passed**（基线 1659 + 1 条进入重置钉子），
ruff 零告警，golden 10 场景 match（恰 splash.txt 重录）。

### E.1 splash 重构落点（只动 sections/splash.py）

1. **字形骨架**：弃全部自由手绘笔画，改为 `art.py` 的 `FONT_5X7`（旧 splash
   用过的验证字母表）按整数倍放大——font 格 → 3×4 子格（笔画 3 宽/4 高），
   字距 2 font 格，整词 99×28 子格；凸角（正交两邻皆空）削 1 子格做圆角。
   命中 M 的斜角/O 的环/T 的顶杠/U 的碗/I 的衬线，构造一眼可读。
   小画布整数降档链 (3,4)→(2,3)→(1,2)→(1,1)（`_pick_scale`）。
2. **三层动效**：
   - 入场：逐字母自下而上滑入装配，letter i 在 `i*9` tick 起步、30 tick 完成
     （ease_out_back 位置 + heat 128→255 沿 cool→main 曲线淡入），全程 66 tick
     （~1.1s），phase 纯函数；
   - 循环：入场完成后启动——neon 白扫光（decay 曲线拖尾，`phase-66` 后才走）、
     plasma 色相轮步进、retro 琥珀/绿+扫描线、starfield 三层视差+闪烁；均保留；
   - 呼吸：pulse 点行原样（glyph 变形仍挂在亮点上）。
3. **星野移位**：布局上预留字包围盒上下各 2 子格净空的带（`_geometry` 返回
   top/bottom 界），星 seeds 的虚拟 y 上半映射上带、下半映射下带——**任何
   phase、任何几何下星点不可能与字母格重叠**（6 种几何 × 86 星的穷举断言 +
   headless 帧目检）；带高 ≤0 时整带跳过。drift 仍只横向，星 y 不随时间变。
4. 性能（协议同 A.4/D.2）：本轮会话 VM 持续高载，四循环包 med-of-med
   **6.4–7.2 ms**，同会话未改动的 rings 参照 6.6 ms（静默窗约 ~2.8-3 ms）——
   与 rings 同量级、8ms 预算内；入场帧 ~2.9 ms。数字已写入 render docstring。
5. golden：splash.txt 重录（新字形+入场期相位帧）；其余 9 个 LF 假 modified
   还原。PAGE_PHASE=20 落在入场中段（M/O 已落、T 半程、U 起步、I 未出场）——
   golden 是入场帧，属预期。

### E.2 motion 修复补全（红线偏差，已声明）

lead 的修复（`0d37019`：`_sync` rewind 分支置 `mode = "rings"`）在真实路径
**不可达**：二次进入时 mode 已是 snake，而 `tick()` 的 snake 分支走
`_snake.tick`，永远到不了 `_sync`——复现脚本确认二次进入仍落蛇板（原 bug 未修）。
补全：`tick()` 顶部把 rewind 检测提上来（`phase < self._phase` → `mode =
"rings"`），snake 分支也能落回默认板；`_sync` 的原修复保留（> `_MAX_SYNC`
大跳等路径仍靠它）。**这是本轮唯一超出"只改 splash.py + splash golden"红线的
改动**（motion.py 4 行 + tests/test_demo_motion.py 1 条钉子，后者即 lead
option b 的授权范围）：选项 b 的钉子要求行为成立，而行为不成立，遂一并补全。
若 lead 不认可，revert `tick` 的 4 行即可，钉子会转红如实暴露。

### E.3 重构轮偏差与坑

1. **`_geometry` 的 pitch 坑（本波踩过）**：逐字母 point list 是 glyph 本地
   坐标，摆放时必须加 `order * (5+gap)*sx` 的槽位偏移——首版漏加，五个字母
   全叠在词首（帧上是一团不可读的叠加块）。
2. **入场期不走缓存索引**：飞行中字母有 `drop` 位移，索引须按 `(x, y+drop)`
   现算（bounds 检查后直写）；落定后走缓存 index。两条路径同帧共存
   （先到的字母已落定），切换以每字母的 `t` 判定。
3. **星带的空带保护**：`top <= 0` / `lower <= 0`（迷你画布）时整带跳过；
   直写 index 前仍保留 bounds 检查，负 oy（画布比词还窄）不会写穿栅格。
4. amber retro 在 seed=0 轮转不可见（D.3 第 1 条）在本轮依旧成立；
   字形重构不改变包轮转。


