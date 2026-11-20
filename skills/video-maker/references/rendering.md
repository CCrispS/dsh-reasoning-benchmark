# 分镜稿 → 视频：渲染说明

把 Markdown 分镜表直接渲染成 mp4：图片镜头自动运镜和打码，卡片（标题、章节、字卡、引文、数据、分屏、时间线、片尾）自动排版，旁白自动配音并烧录字幕，可选背景音乐。只依赖 Python 3.8+ 标准库和 ffmpeg，macOS、Windows、Linux 通用。

## 目录

1. 安装与环境检查
2. 三步出片
3. Markdown 分镜表约定
4. 渲染 JSON 规范
5. 素材包、打码与高亮框
6. 配音、字幕与音乐
7. 命令参考
8. 排错
9. 已知限制

---

## 1. 安装与环境检查

任何系统，第一次使用前先运行环境检查（在技能根目录下）：

```bash
python3 scripts/setup_env.py
```

Windows 用 `python scripts\setup_env.py`。它会逐项检查并给出结论“能出片 / 缺什么 / 怎么装”：

| 检查项 | 要求 | 缺了会怎样 |
| --- | --- | --- |
| Python | 3.8 以上 | 无法运行 |
| ffmpeg | 必须带 libass（`subtitles` 过滤器）和 `zoompan` | 无法渲染文字，直接报错 |
| 中文字体 | 任一中文字体文件 | 无法渲染，直接报错 |
| 配音 TTS | macOS `say` / Windows SAPI / Linux `espeak-ng` / 可选 `edge-tts` | 仍可出片，只是没有配音、只有字幕 |

缺东西时运行：

```bash
python3 scripts/setup_env.py --install
```

它会先列出要做的事，再执行：

- 用当前 Python 执行 `python -m pip install --user imageio-ffmpeg`（自带完整版 ffmpeg，含 libass）。如果当前 Python 不允许 `--user` 安装（PEP 668，常见于 Homebrew / Debian 的 Python），改为在技能目录建 `.venv` 并装在里面，渲染脚本会自动找到。
- 找不到任何中文字体时，下载开源字体 Noto Sans SC（SIL OFL 1.1，约 18 MB）和许可证到技能内 `fonts/` 目录。
- 加 `--with-edge-tts` 会再装 edge-tts（在线配音，旁白文本会发送到微软服务）。

**ffmpeg 查找顺序**：环境变量 `FFMPEG` → `PATH` 中的 `ffmpeg` → 当前 Python 的 `imageio-ffmpeg` → 技能内 `.venv` 中的 `imageio-ffmpeg`。已有完整版 ffmpeg 时，设置 `FFMPEG=/path/to/ffmpeg` 即可。

**字体查找顺序**：`--font` 参数 → 环境变量 `VS_FONT` → 技能内 `fonts/` → 系统常见中文字体（macOS：PingFang、Hiragino Sans GB、黑体；Windows：微软雅黑、黑体；Linux：Noto Sans CJK、文泉驿）。

手动安装 ffmpeg 的办法（任选其一）：

| 系统 | 命令 |
| --- | --- |
| 任意 | `python3 -m pip install --user imageio-ffmpeg` |
| macOS | `brew install ffmpeg` |
| Windows | 下载 gyan.dev 的 ffmpeg *full* build，把 `bin` 加入 PATH，或设置 `FFMPEG` |
| Linux | `sudo apt install ffmpeg`（Debian/Ubuntu）或 `sudo dnf install ffmpeg` |

## 2. 三步出片

```bash
# 0) 输出目录放在技能目录之外，并先建好（md2render.py 不会自动创建目录）
mkdir -p ~/video-maker-out

# 1) Markdown 分镜 → 渲染 JSON（一个文件里有多节时，可用 --section 只取一节）
python3 scripts/md2render.py storyboards/full.md --assets assets -o ~/video-maker-out/full.json

# 2) 先空跑：检查素材是否齐、每镜时长、哪些镜头是占位（空跑也会在 JSON 旁边建缓存目录）
python3 scripts/render_video.py ~/video-maker-out/full.json --dry-run

# 3) 出片 + 拼图（每镜中间帧拼成一张图，便于检查）
python3 scripts/render_video.py ~/video-maker-out/full.json --sheet
```

成片默认写在 JSON 旁边（`full.mp4`、`full_sheet.png`），中间文件和缓存在 `full_build/`。技能自带的 `render/*.json` 可以直接渲染，但要用 `-o` 和 `--work` 把成片和缓存放到技能目录之外。只改了几镜时，用 `--only 2-03,2-07` 重渲这几镜并输出 `full_preview.mp4`；之后再全量渲染时，未改动的镜头直接用缓存。

**交付前务必看拼图**：检查字幕是否压住关键信息、打码是否到位、占位镜头是否已补素材。拼图只能看构图，节奏和配音要实际播放确认。

## 3. Markdown 分镜表约定

`md2render.py` 读取文件中所有含“镜号/时长/画面内容/旁白”等列的 Markdown 表格。表头按关键字识别，列顺序随意：

| 列（表头关键字） | 用途 |
| --- | --- |
| 镜号 | 镜头编号，例如 `2-05`、`S-12` |
| 时长 | `6`、`6s`、`6秒`、`6.5`、`0:06` |
| 画面类型（或 景别） | 决定镜头类型，见下表 |
| 运镜（或 动效） | 决定运动方式，见下表 |
| 画面内容 | 用 `图N` / `原稿图N` 引用素材；也可写本地媒体路径，如 `素材: footage/demo.mp4` |
| 旁白（或 台词、配音） | 配音文本，同时生成逐句字幕；空则无配音 |
| 字幕/花字 | 卡片镜头＝卡片文字；图片/视频镜头＝左下角花字 |
| 声音/备注 | 只记录，不参与渲染 |

**画面类型关键字**（取单元格里最先出现的一个）：

| 关键字 | 类型 | 字幕/花字列的写法 |
| --- | --- | --- |
| 截图、长截图、素材图、照片、档案、图片、网页 | `image` | 左下角花字，如 `原作者声明 2026-10-29` |
| 字卡、文字卡、要点卡 | `text` | `标题：要点1；要点2；要点3`，或 `一句话／补充说明` |
| 章节卡 | `chapter` | `第二章 镜像授权／许可从哪来`（`第X章` 会自动成为小标题） |
| 引文卡、声明卡 | `quote` | `引文内容／出处` |
| 数据卡 | `data` | `1.25 万元／瑞得哈希注册资本` |
| 分屏、对比 | `split` | 有两张图：`左标签｜右标签`；无图：`标题／原作者：未授权｜网页红警方：代为维权` |
| 时间线 | `timeline` | `标题／2023：镜像上线；2025-10：注册域名；2026-05：申请商标` |
| 标题卡、片头 | `title` | `主标题／副标题` |
| 片尾 | `end` | `感谢观看／认准官方：xxx.com` |
| 实拍、录屏、动画、出镜、历史影像、空镜、地图、示意图 等 | `placeholder` / `media` | 画面内容里有存在的媒体文件路径 → 用该素材；否则生成“待补素材”占位卡 |

`／` 是全角斜杠，`｜` 是全角竖线（不会和表格分隔符冲突），`；` 分隔列表项。景别词（特写、近景）+ `图N` 会按图片镜头处理。

**运镜关键字**：固定 → `static`；缓推 → `push`；缓拉 → `pull`；左移 → `left`（视野从右向左）；右移 → `right`；下移/滚动 → `down`（长截图自上而下滚动）；上移 → `up`。不写时：图片默认缓推，横屏下的竖长截图（高宽比大于 1.5）默认向下滚动，卡片固定。

一张图片镜头引用多张图（`图13、图14`）时，按时长平均切成连续幻灯。

## 4. 渲染 JSON 规范

`md2render.py` 生成的 JSON 可以直接手改（例如补高亮框、改主题、换配音），也可以由 AI 直接手写。路径一律相对于 JSON 文件所在目录。

```json
{
  "meta": {
    "title": "两份声明之后（完整版）",
    "width": 1920, "height": 1080, "fps": 30,
    "theme": "dark",
    "tts": "auto", "voice": null, "rate": null, "speed": 4.5,
    "bgm": "music/bed.mp3", "bgm_volume": 0.18,
    "assets_dir": "../assets",
    "assets_manifest": "../assets/assets.json",
    "zoom": 0.08, "subtitles": true
  },
  "shots": [
    {"id": "1-02", "type": "image", "duration": 8, "images": ["图1"], "motion": "push",
     "highlight": [[0.585, 0.095, 0.105, 0.06]],
     "caption": "原作者声明 2026-10-29",
     "narration": "原作者在声明里写得很清楚：官方网站只有 chronodivide.com。"},
    {"id": "1-05", "type": "quote", "duration": 6,
     "card": {"title": "What can I say, obviously not true.", "sub": "use-strict，Discord"},
     "narration": "原作者的回答只有一句：显然不是真的。"}
  ]
}
```

**meta 字段**

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `width` / `height` | 1920 / 1080 | 竖屏用 1080 / 1920；也可渲染时 `--size vertical` |
| `fps` | 30 | |
| `theme` | `dark` | `dark`（深色证据向）或 `light`（浅色） |
| `tts` | `auto` | `auto` / `say` / `sapi` / `espeak` / `edge` / `none` |
| `voice` | 自动 | 语音名，见 `render_video.py --list-voices` |
| `rate` | 系统默认 | say / espeak：每分钟词数；SAPI：-10 到 10；edge：百分比 |
| `speed` | 4.5 | 无配音时按“字/秒”估算字幕时长 |
| `bgm` / `bgm_volume` | 无 / 0.18 | 背景音乐文件与音量；有旁白时自动压低 |
| `assets_dir` / `assets_manifest` | — | 素材目录与 `assets.json` |
| `zoom` | 0.08 | 缓推/缓拉的缩放幅度 |
| `subtitles` | true | false 则不烧录旁白字幕 |
| `font` | 自动 | 字体文件路径 |

**shot 字段**

| 字段 | 说明 |
| --- | --- |
| `id` | 镜号 |
| `type` | `image` `text` `chapter` `quote` `data` `split` `timeline` `title` `end` `placeholder` `media` |
| `duration` | 分镜时长（秒）。实际时长 = max(分镜时长, 配音时长 + 0.55 秒) |
| `images` | 素材引用列表：`"图3"`、清单里的文件名，或相对路径 |
| `media` | 外部视频或图片路径（录屏、实拍素材）；视频会静音并循环到镜头结束 |
| `motion` | `static` `push` `pull` `left` `right` `down` `up` |
| `highlight` | 红框，`[[x, y, w, h], ...]`，0–1 比例坐标、相对于图片本身；多图镜头可写成 `{"图13": [[...]]}` |
| `caption` | 图片/视频镜头左下角花字 |
| `card` | 卡片内容：`title`、`sub`、`items`（列表）、`kicker`（章节小标题）、`left`/`right`（分屏） |
| `narration` | 旁白文本 |
| `audio` | 外部配音文件（自己录的旁白），优先于 TTS |
| `content` / `note` | 画面描述与备注；占位卡会显示 `content` |

## 5. 素材包、打码与高亮框

本案素材在技能根目录的 `assets/`，清单是 `assets/assets.json`：

```json
{
  "images": [
    {"id": "图11", "file": "img11.png", "width": 571, "height": 450,
     "desc": "CNNIC whois chronodivide.cn ……",
     "redact": [], "baked_redact": [[0.47, 0.69, 0.30, 0.06]],
     "recommended": true, "note": "打包副本已模糊邮箱"}
  ]
}
```

- `redact`：渲染时自动模糊的区域（比例坐标），素材文件本身不改。适合“视频里要遮、但原图要留档”的内容，如粗口昵称、手势。
- `baked_redact`：已经直接模糊在素材文件里的区域（手机号、邮箱、年龄等个人信息），仅作记录。
- `recommended: false`：不建议使用的素材（与主题无关、版权或伦理风险）。写分镜时应避开。

**新项目**：`scripts/extract_docx.py` 会把 docx 里的插图按顺序导出到 `assets/imgNN.<扩展名>`。没有 `assets.json` 时，`图N` 会直接对应 `imgNN` 文件，可以马上渲染；需要描述、打码或标记不推荐素材时，再按上面的格式建 `assets.json`（至少 `id` 和 `file`）。

**定坐标的方法**：坐标是图片宽高的比例，左上角为原点。先目测估算，再用 `--only <镜号> --sheet` 渲一镜看效果，必要时微调。高亮框同理，写在镜头的 `highlight` 里。

## 6. 配音、字幕与音乐

- `--tts auto` 在 macOS 用 `say` 的中文（中国大陆）语音（优先 Tingting），Windows 用 SAPI 的中文语音，Linux 用 `espeak-ng`。`edge` 音质最好，但要联网，且只在显式指定时使用。
- 配音按“引擎 + 语音 + 语速 + 文本”缓存，改了一镜的旁白只重配这一镜。
- 配音比镜头可用时长长时，先用 ffmpeg `atempo` 保持音调加速去贴合分镜（最多 1.35 倍，`--max-tempo` 可调，设为 1 则不加速）；加速到上限仍不够，才延长镜头，并在输出里标出“配音比分镜时长长，已延长”。系统 TTS 的语速参数和实际字速不成线性关系，所以按实测时长变速，而不是猜 `--rate`。这一步对外部配音文件同样生效。
- 字幕按标点切成每条不超过 22 字（竖屏约 19 字），按字数比例分配时间；英文单词和网址不拆开。
- 有人声的成片做响度标准化（-16 LUFS）；背景音乐循环、淡入淡出，并按旁白自动压低。

## 7. 命令参考

`render_video.py <json>`

| 参数 | 说明 |
| --- | --- |
| `-o out.mp4` | 输出路径 |
| `--sheet` | 同时输出每镜中间帧拼图 |
| `--only 2-01,2-03` | 只渲这些镜头，输出 `_preview.mp4` |
| `--dry-run` | 只检查素材和时长 |
| `--size vertical` | 改画幅：`1920x1080`、`1080x1920`、`vertical`、`square` |
| `--theme light` | 改主题 |
| `--tts none` | 无配音（只出字幕） |
| `--voice` / `--rate` | 指定语音与语速 |
| `--max-tempo 1.35` | 配音超长时最多加速几倍去贴合分镜；1 表示只延长镜头 |
| `--bgm file --bgm-volume 0.15` | 背景音乐 |
| `--font file` | 指定字体 |
| `--no-subs` | 不烧录字幕 |
| `--quality 1/2/3` | 运镜防抖倍数，默认 2；3 更平滑但更慢 |
| `--work dir` | 工作/缓存目录 |
| `--list-voices` | 列出本机中文语音 |

`md2render.py <md>`：`--assets 目录`、`-o 输出.json`、`--section 关键字`、`--title`、`--style-meta theme=light,width=1080,height=1920`（也接受 JSON）、`--list-sections`。

## 8. 排错

| 现象 | 处理 |
| --- | --- |
| “没有 libass（缺 subtitles 过滤器）” | 运行 `setup_env.py --install`，或换完整版 ffmpeg 并设置 `FFMPEG` |
| 文字显示成方框 | 字体缺中文字形：`--font` 指定中文字体，或 `setup_env.py --install` 下载 Noto Sans SC |
| pip 报 externally-managed-environment | `setup_env.py --install` 会自动改用技能内 `.venv`；也可自建虚拟环境 |
| macOS 没有中文语音 | 系统设置 → 辅助功能 → 朗读内容 → 系统声音 → 管理声音，添加中文（中国大陆） |
| Windows 没有中文语音 | 设置 → 时间和语言 → 语音 → 添加语音 → 中文（简体） |
| 运镜有轻微抖动 | `--quality 3`，或把该镜改为 `static` |
| 渲染慢 | `--quality 1`；先 `--only` 调好个别镜头再全量渲染 |
| 长截图被缩得太小 | 运镜写“下移”，让它滚动展示；或把截图裁成几段分镜 |
| 字幕压住截图关键处 | 缩短旁白，或把关键处放在画面上半部（加高亮框），或改用引文卡 |
| 某镜出错 | 报错会列出 ffmpeg 命令和最后几行输出；用 `--only <镜号>` 单独重试 |
| 改了 `render_video.py` 的排版代码，画面却没变 | 镜头缓存按 `VERSION` 常量区分：改排版后把脚本顶部的 `VERSION` 加一，或删掉工作目录下的 `clips/` |

## 9. 已知限制

- 卡片是静态排版，只有淡入淡出，没有逐字动画；需要复杂动画时，把该镜写成占位，在剪辑软件里替换。
- 镜头之间是硬切（首尾有淡入淡出）；需要转场效果请在剪辑软件里加。
- 视频素材会静音；需要保留现场声时，导出后在剪辑软件里处理。
- 系统 TTS 音质有限，正式发布建议真人配音：把录音按镜头切好，写进每镜的 `audio` 字段。
- `highlight` 和 `redact` 坐标需要人工确认，脚本不会自动识别文字位置。
