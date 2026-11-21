# 流水线细节

## 目录与环境变量

```
video-maker-pro/
├── story/story_v3.py        分镜数据（SHOTS 列表）
├── tools/                   流水线脚本
├── assets/emoji/            twemoji（文件名 = codepoint）
├── audio/{bgm,sfx,nar}/     生成物（不入库）
├── build/{clips,stills}/    生成物（不入库）
└── out/                     成片（不入库）
```

| 变量 | 默认 | 用途 |
| --- | --- | --- |
| `VIDEO_MAKER_SKILL` | 同级 `../video-maker` | 渲染器与截图素材所在技能 |
| `VMP_STORY` | `story_v3` | 用哪份分镜（可写多份 story 切换） |
| `VMP_OUT` | `<技能>/out` | 成片输出目录 |
| `VMP_FORCE` | `0` | `1` = 忽略已有片段全部重渲 |
| `FFMPEG` | `ffmpeg` | 指向 ffmpeg 可执行文件 |

Windows 上建议每次运行前：

```powershell
$env:PYTHONIOENCODING="utf-8"; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$env:FFMPEG="C:\Users\<you>\AppData\Roaming\Python\Python312\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe"
```

否则 `setup_env` 类脚本和任何打印 ✓ 的程序会报 `UnicodeEncodeError: 'gbk' codec`。

## 五步各自做什么

### 1. `build.py narration`

逐镜调用 `python -m edge_tts --voice zh-CN-XiaoxiaoNeural --rate +14% --text <旁白> --write-media SXX.mp3`，再用 ffmpeg 转 `48 kHz / 立体声 / pcm_s16le`，用 `wave` 量时长写入 `build/narration.json`。

- 已有 `audio/nar/SXX.wav` 就跳过 → **补一镜只要删掉它的 wav 再跑一遍**。
- 单镜 3–15 秒；93 镜合计 940 秒（≈15:40），加每镜 0.55 秒呼吸后正片 16:42。
- 中文语音可选：`XiaoxiaoNeural`（旁白，默认）、`YunxiNeural`（更年轻）、`YunjianNeural`（更硬）、`YunyangNeural`（新闻腔）。

### 2. `build.py clips`

对每个 `kind == "media"` 的镜头：

```
dur = max(ndur + 0.55, MIN_DUR[场景类型])
spec["dur"] = dur + 0.12          # 多给 0.12 秒，防止装配时 loop 接缝
scene = scenes3.TYPES[type](**spec)
anim.render_scene(scene, build/clips/SXX.mp4, crf=18, preset="fast")
```

- `MIN_DUR`：`title 3.6 / network 6.0 / versus 6.4 / chain 5.6 / stamp 3.8 / quote 5.2 / end 4.6 / question 7.0 / bigq 6.6 / contradiction 8.6 / wall 7.6 / flow 6.6 / web 8.2 / guess 7.2`。
- 尺寸 1920×1080@30fps；crf 18 + preset fast 是画质/体积/速度的平衡点（crf 16 时某镜 58 MB，18 时 15 MB）。
- 60 个片段约 150 MB，耗时约 45 分钟（单核 PIL 逐帧）。

### 3. `build.py json`

写两个文件：

- `build/render.json`：`meta`（title/width/height/fps/theme/tts=none/assets_dir/assets_manifest）+ `shots`。
  - media 镜：`{id, type:"media", duration, media:<片段绝对路径>, narration, audio:<wav 绝对路径>}`
  - image 镜：`{id, type:"image", duration, images:["图13"], motion, caption, narration, audio}`
- `build/cues.json`：`{cues:[{file, at}], total}`，`at` 是该镜起点 + 0.05 秒。

### 4. `build.py video`

调 `<video-maker>/scripts/render_video.py render.json --tts none --quality 2 --work build/work -o out/<story>_full.mp4 --sheet`。

渲染器要点（决定你怎么写分镜）：

- `plan_shot`：`D = max(base, ndur+lead+0.4, est+0.5, 1.0)`，`lead = 0.15`。我们传的 `duration` 已算好，但因为镜头自带 `audio`，渲染器还会用音频时长兜底。
- 字幕由渲染器按 `narration` 切块烧成 ASS；`--no-subs` 可关。花字用 `caption`（`主标题／补充说明` 用全角斜杠分隔）。
- 缓存键 = 镜头内容 sha1 → **改了 story 但没删片段，装配会用旧画面**。
- 片段首尾自动 0.5 秒淡入 / 0.6 秒淡出；我们自己的场景也应处理首尾，否则接缝硬。

### 5. `score.py` + `mix.py`

`score.py`：读 `narration.json` 算出切换镜（默认 `S41`）的起点，把 `bed-a`（前）与 `bed-b`（后）用 `acrossfade=d=5` 接成 `audio/score.wav`，`-stream_loop -1` 保证够长。

`mix.py`：一条滤镜链完成全部混音（见 `audio.md`）。

## 只改一镜的最短路径

```bash
rm audio/nar/S46.wav build/clips/S46.mp4
python tools/build.py narration        # 只补 S46
python tools/build.py clips --only S46
python tools/build.py json
python tools/build.py video            # 装配（会重渲染？不会，命中缓存）
python tools/mix.py
```

约 3 分钟。若改了场景代码（`scenes3.py`），要删掉所有用到该场景的片段，或者 `VMP_FORCE=1`。

## 预览与检查

- `python tools/test_stills.py`：每种场景渲染一张静帧到 `build/stills/`，改场景后**必跑**。
- 只要一段预览：`build.py video --only S61` → `out/story_v3_full_preview.mp4`（只含该镜）。
- 装配完成后先看 `out/*_sheet.png`（2 列缩略拼图）判断整体节奏，再抽关键帧看细节——**缩略图看不清字，涉及排版必须抽原尺寸帧**。

## 跨平台

- 字体：`anim.font()` 默认 `C:\Windows\Fonts\msyh*.ttc`；Linux 改 `NOTO_SANS_CJK` 路径即可（只改 `anim.py` 顶部三行）。
- edge-tts：`pip install edge-tts`；如果 `shutil.which("edge-tts")` 找不到（脚本不在 PATH），`build.py` 用的是 `python -m edge_tts`，不受影响。
