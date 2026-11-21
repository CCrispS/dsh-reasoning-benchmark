---
name: video-maker-pro
description: 证据叙事视频的动效流水线：把截图、聊天记录、网页原文做成有动效、有配乐、有音效的说明片（mp4）。自带 7 类自制动效场景（关系网、矛盾对撞、证据墙、流程链、网页摘录、提问卡、巨型质问、猜测卡）、自写场景引擎、程序化配乐与音效生成、混音与响度控制，以及一套 93 镜的完成分镜（Chrono Divide · vera20k · 网页红警 授权与署名争议）。用户要把一堆证据做成"讲得清、看得下去"的视频，或要给已有分镜加关系网、矛盾对照、连发质问、自制 BGM、音效与响度校准，或提到 video-maker 进阶版、动效、关系网、矛盾对照、证据视频时使用。
---

# 视频创造者 · 进阶版（动效 + 声音）

本技能解决一个具体问题：**手里有一堆截图、聊天记录、网页原文，要做成一支让人看得下去、又经得起核对的说明片。**

`video-maker` 技能给的是分镜规范 + 一个通用渲染器（evidence 图卡、运镜、字幕）。本技能在它上面补三样东西：

1. **一套自制动效场景引擎**（`tools/anim.py` + `tools/scenes.py` + `tools/scenes3.py`）——关系网、矛盾对撞、证据墙、流程链、网页摘录、提问卡、巨型质问、猜测卡。这些是逐帧用 PIL 画出来的，不受渲染器卡片样式限制。
2. **一条完整流水线**（`tools/build.py`）——旁白合成 → 动效片段 → 装配 JSON → 渲染 → 混音，每步可单独重跑，改一镜只重渲一镜。
3. **一套程序化声音**（`tools/make_audio_*.py` + `tools/mix.py`）——不下载任何音乐，用 numpy 合成铺底与音效，再按旁白做侧链闪避、统一到 −16 LUFS。

外加一支**成品分镜**（`story/story_v3.py`，93 镜 / 16 分 42 秒）当作范例：它把「一个运营方、五个名字、九处矛盾」讲成一条问题链。要新做一支片子，改它比从零写快得多。

## 依赖

- 同仓库的 **`video-maker` 技能**：提供渲染器 `scripts/render_video.py`、48 张证据截图与 `assets/assets.json`。两个技能放在同一个 `skills/` 目录下即可，路径是同级推导的；不在同级就设 `VIDEO_MAKER_SKILL=<video-maker 绝对路径>`。
- Python 3.8+，`Pillow`、`numpy`；`ffmpeg`（本机用 imageio-ffmpeg 的静态包，设环境变量 `FFMPEG` 指向它）；`edge-tts`（中文配音）。
- 中文字体：`C:\Windows\Fonts\msyh.ttc`（微软雅黑）；macOS/Linux 见 `references/pipeline.md`。

## 三条命令跑通

```bash
python tools/build.py narration     # 93 段旁白，约 6–10 分钟
python tools/build.py all           # 动效片段 + 装配 + 渲染（首次约 45 分钟）
python tools/score.py && python tools/mix.py   # 配乐拼条 + 混音
```

产物在 `out/`：`story_v3_full.mp4`（无配乐）与 `story_v3_final.mp4`（含配乐音效）。

## 目录

| 路径 | 内容 | 什么时候看 |
| --- | --- | --- |
| `story/story_v3.py` | 93 镜成品分镜：每条旁白 + 场景参数 + 音效标记 | **改内容先看这个** |
| `tools/build.py` | 流水线总控：`narration / clips / json / video / all` | 每次出片 |
| `tools/anim.py` | 逐帧绘制原语：字体、圆角、模糊、光晕、粒子、箭头、写 mp4 | 加新场景时查 |
| `tools/scenes.py` | 8 类基础场景：标题、关系网、左右对照、时间链、冲击卡、引言、片尾 | 直接用 |
| `tools/scenes3.py` | 7 类证据场景：矛盾对撞、证据墙、流程链、网页摘录、提问卡、巨型质问、猜测卡 | **本技能的主力** |
| `tools/mix.py` | 混音：BGM 侧链 + 音效 + 两次定点限幅 + loudnorm | 出片最后一步 |
| `tools/score.py` | 把两段铺底按章节切换点拼成一条 score | 第一次配乐 |
| `tools/make_audio_calm.py` | 合成「平静」铺底 `bed-a` + 10 个音效 | 换风格时改参数重生成 |
| `tools/make_audio_tension.py` | 合成「压迫」铺底 `bed-b` + 8 个音效 | 同上 |
| `tools/test_stills.py` | 每种场景出一张静帧，检查排版 | **改场景后必跑** |
| `assets/emoji/` | twemoji 72×72 PNG（文件名即 codepoint） | 场景里要表情时 |
| `web-evidence.md` | 6 个公开网页的原文摘录与抓取日期 | 写旁白引用网页时 |
| `references/` | 流水线细节、场景参数、声音、写法、踩坑 | 按需 |

## 流水线五步（细节见 `references/pipeline.md`）

1. **narration**：逐镜合成旁白 → 48 kHz 双声道 wav，量出 `ndur`，写 `build/narration.json`。
2. **clips**：按 `ndur` 定每镜时长 → 逐镜渲染无声 mp4 到 `build/clips/`。
3. **json**：写 `build/render.json`（media 镜引用片段、image 镜引用「图N」）+ `build/cues.json`（音效时间点）。
4. **video**：调 `video-maker` 的渲染器装配 93 镜，烧字幕、加转场，出 `*_full.mp4`。
5. **mix**：拼 score → BGM 侧链闪避 → 叠音效 → 限幅 → loudnorm，出 `*_final.mp4`。

**改一镜只做两步**：改 `story_v3.py` → `build.py narration --only` 不行（narration 是全量），实际做法是删掉该镜的 `build/clips/SXX.mp4` 与 `audio/nar/SXX.wav`，再跑 `build.py narration`（有则跳过，只补缺的）→ `build.py clips --only SXX` → `build.py json` → `build.py video` → `mix.py`。

## 写分镜：一镜长什么样

```python
A(pic("S03", ["img01.png"], "原作者声明一／2026-10-29 · 图1",
      "旁白一句话，15–40 字最好读。", motion="up"))

A(media("S46", "contradiction",
      "同一份材料，两种自我介绍……",
      left=dict(img="图10", who="「关于红色井界™」", quote="全面自研，完全知识产权"),
      right=dict(img="图24", who="ts-redalert2 README", quote="基于《红色井界》RA2WEB 的分析而开发"),
      heading="同一个 RA2WEB，两种自我介绍",
      verdict="那么，它到底是「镜像」，还是「全面自研」？",
      sfx=["impact-hit"]))
```

两条约定：

- **时长由旁白决定**：`dur = max(ndur + 0.55, MIN_DUR[type])`。`MIN_DUR` 在 `build.py` 里按场景类型给下限（`contradiction 8.6`、`web 8.2`、`question 7.0`…），因为观众需要时间读画面。旁白写到 20 字左右，画面才有呼吸。
- **语速**：`RATE = "+14%"`（edge-tts 的百分比）。实测 1.14× 是"紧凑但听得清"的上限；再快，术语和数字会糊。

## 场景怎么选

| 想表达 | 用哪个 | 关键参数 |
| --- | --- | --- |
| 两个说法直接冲突 | `contradiction` | 左右各一张截图 + 一句原话，下方一句带问号的结论 |
| 一批证据压过来 | `wall` | 10 张缩略图飞入，每张带编号标签 |
| 谁是谁、谁连谁 | `network` | 节点 kind 决定颜色，冲突边红色虚线 + 沿线脉冲 |
| 环节怎么走 | `flow` | 3–6 个框 + 虚线箭头，`kind` 标出 start/bad/good/end |
| 网页原话要站得住 | `web` | 浏览器窗口样式 + URL + 「抓取日期」角标，**不许伪造** |
| 连发质问 | `bigq` | 左侧巨型编号水印 + 大号问句 + 证据角标 |
| 先抛问题再回答 | `question` | 巨型 🤔 + 三到五条问题逐条浮现 |
| 只能猜、不能定性 | `guess` | 猜测卡 + 巨型问号水印 + 「依据：」一行 |

参数、动画时序、实现要点在 `references/scenes.md`。

## 声音（细节见 `references/audio.md`）

- 两段铺底：`bed-a`（A 小调 60 BPM，铺垫）/ `bed-b`（D 小调 92 BPM，压迫），`score.py` 在指定镜（默认 S41）用 5 秒交叉淡化切换。
- 音效 44 处，全部程序化合成：`impact-low`（章节落点）、`whoosh-soft/hard`（转场）、`stamp`（结论砸下）、`question-ding`（提问）、`heartbeat`（逼近）、`glitch-burst`（矛盾揭露，最响）。
- 混音参数：`--bgm-volume 0.18 --sfx-volume 0.5`；BGM 走 `sidechaincompress` 让旁白一开口就压下去。
- 响度目标：**−16 LUFS / ≤ −1 dBTP**。三处限幅写成一条链：`loudnorm=I=-16:TP=-4:LRA=11` → `alimiter=limit=0.63:level=false` → 输出 aac（ISP 会再冲 0.5–1.3 dB）。

## 口径（这是硬约束，不是风格建议）

做证据类视频最容易翻车的地方不是技术，是**替观众下结论**。这套流水线默认遵守下面五条，`story_v3.py` 里每一镜都按它写：

1. **只陈述记录**：截图、原文、登记信息、时间。形容词留给当事人自己说。
2. **指控一律写成问句**：「那么，为什么……？」「如果……，那……算什么？」——问句让观众自己接上，陈述句就是你在定性。
3. **猜测必须带问号 + 依据**：每张猜测卡下方写「依据：<图号/网页>」，没有依据的猜测删掉。
4. **每条都挂来源**：图号、日期、URL、抓取日；网页摘录画成浏览器窗口并标注抓取日期，**绝不伪造截图**。
5. **不点名真人、不汇总个人账号**：用当事人公开使用的账号名/产品名；个人信息按 `assets.json` 的 `redact` 打码（自制场景必须自己打，渲染器只对 image 镜自动打）。

## 排错清单（完整版见 `references/pitfalls.md`）

- **emoji 变成空圈**：`anim.emoji_img()` 只在文件存在时返回图，缺文件就静默返回 2×2 空白。跑 `test_stills.py` 看，缺哪个 codepoint 补哪个。
- **✅/✕ 变豆腐块**：微软雅黑没有 U+2715，用 `anim.mark_icon("check"/"cross")` 矢量画。
- **文字被画面裁掉**：`chain` 首尾标签要用左/右锚点，`network` 底部节点 y 要钳到 0.735H 以下，否则压字幕。
- **动效片段重渲了但成片没变**：渲染器按内容 sha1 缓存，改场景后要删对应 `build/clips/SXX.mp4`（或 `VMP_FORCE=1`）。
- **True Peak 超 0**：`alimiter` 必须 `level=false`，否则它会把整体电平抬回来。
- **中文源码变乱码**：不要用 PowerShell 的 `Set-Content` 改含中文的脚本，用写文件工具整篇重写。

## 一次真实出片的成本

93 镜 / 16 分 42 秒：旁白 6 分钟，动效渲染 45 分钟（60 个片段、约 150 MB），装配 6 分钟，混音 3 分钟。成片 156 MB，1043 kb/s。**改一镜约 3 分钟**（重渲 1 个片段 + 装配 + 混音）。
