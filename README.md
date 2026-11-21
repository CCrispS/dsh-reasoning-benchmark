# dsh-reasoning-benchmark

测试大肥鱼的视频合成能力和针对事件的说理能力：给它一份背景知识文档和一批素材，看它能不能合成出足以说明事实的视频材料。

## 项目目标

- **输入**：背景知识文档 [`facts.md`](skills/video-maker/facts.md)（Chrono Divide / vera20k 授权与署名争议的中立事实表，每条事实都标明来源和对应的证据图）、50 张证据截图（48 张可用于成片），以及配套的技能“视频创造者”（`video-maker`）。
- **考察两种能力**：
  1. **视频合成**：能不能把分镜真正渲染成可以播放的成片，画面、字幕、配音、运镜、打码都到位。
  2. **说理**：能不能从文档和素材里理清事实：每个论断都对上证据图；分清公开记录、原作者的说法、网页红警方的说法和未证实的内容；每个争议点都把双方说法讲完整。
- **及格线**：只看视频，观众就能弄明白发生了什么、证据在哪里、双方各自怎么说。

## 使用约定

- 本仓库是公开的评测集。题材是一起真实的开源社区争议，涉及的项目、账号和公司都真实存在。
- 评测中生成的分镜和成片只用于评估模型能力，不发布到任何视频平台。
- 证据截图里的个人信息已经打码；不要往仓库里加入任何人的真实姓名、联系方式等个人信息。
- 视频只陈述公开记录和双方说法，不替观众下结论。具体口径见[制作简报](skills/video-maker/references/case-brief.md)第 3 节。

## 视频创造者技能

本仓库的核心是一个 AI 技能（Agent Skill）——“视频创造者”（`video-maker`）。技能里备齐了中立事实表、50 张已打码的证据图、制作简报与口径、一套完整版说明视频分镜和渲染脚本。你可以让 AI 按指定风格改编或新写分镜，也可以用自带脚本把分镜直接合成 mp4。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| [`skills/video-maker/`](skills/video-maker/) | 技能本体，自包含，可以整个文件夹单独拷走使用 |
| ├ [`SKILL.md`](skills/video-maker/SKILL.md) | 技能入口：用途、工作流程、分镜表格式（AI 读这个） |
| ├ [`facts.md`](skills/video-maker/facts.md) | 背景知识文档：当事方、时间线、每个争议点双方的说法、未证实事项 |
| ├ `assets/` | 50 张证据图和清单 `assets.json`（描述、打码区域、是否可用于成片） |
| ├ `references/` | [制作简报](skills/video-maker/references/case-brief.md)、[风格预设](skills/video-maker/references/styles.md)、[镜头语言](skills/video-maker/references/shot-language.md)、[交付模板](skills/video-maker/references/templates.md)、[渲染说明](skills/video-maker/references/rendering.md) |
| ├ `storyboards/` | 现成分镜：`full.md` 完整版说明视频 |
| ├ `render/` | 上面分镜的渲染规格 `full.json`，可直接出片 |
| └ `scripts/` | `setup_env.py` 环境检查、`storyboard_check.py` 分镜检查、`md2render.py` 分镜转渲染规格、`render_video.py` 渲染 mp4、`extract_docx.py` 从 docx 抽取正文和插图 |

**环境要求**：只写分镜什么都不用装。出片需要 Python 3.8+（脚本只用标准库，不用 pip 装依赖）、带 libass 的 ffmpeg 和一款中文字体；配音可选（macOS `say`、Windows SAPI、Linux `espeak-ng`，或在线的 `edge-tts`）。macOS、Windows、Linux 通用。

## 安装技能

先克隆仓库：

```bash
git clone https://github.com/webra2/dsh-reasoning-benchmark.git
cd dsh-reasoning-benchmark
```

### Claude Code

把 `skills/video-maker` 文件夹放进技能目录，三种方式任选其一：

```bash
# 方式一：拷贝到个人技能目录，所有项目都能用
mkdir -p ~/.claude/skills
cp -R skills/video-maker ~/.claude/skills/

# 方式二：软链接到个人技能目录，之后 git pull 更新仓库，技能跟着更新
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/video-maker" ~/.claude/skills/video-maker

# 方式三：只在某个项目里用，放进该项目的 .claude/skills/
mkdir -p /path/to/your-project/.claude/skills
cp -R skills/video-maker /path/to/your-project/.claude/skills/
```

装好后新开一个 Claude Code 会话，直接用中文提需求即可。技能的描述里写了触发场景：为这个事件做视频、分镜或换风格，或提到网页红警、vera20k、chronodivide 等关键词时，Claude 会调用它；想确保用上，就在请求里直接说“用 video-maker 技能……”。

### claude.ai

把技能文件夹打成 zip（zip 里的顶层是 `video-maker/` 文件夹，`SKILL.md` 在其中）：

```bash
cd skills
zip -r video-maker.zip video-maker -x '*.DS_Store' '*/__pycache__/*' 'video-maker/.venv/*'
```

然后在 claude.ai 设置里的技能（Skills）页面上传这个 zip（约 13 MB，主要是 50 张图），具体入口以当前界面为准。云端能不能出片取决于它的运行环境里有没有 ffmpeg 和中文字体，可以先让 Claude 运行 `setup_env.py` 检查；不行就在 claude.ai 上写分镜，回本机出片。

### 其他 AI 工具

不支持技能目录的工具，直接把文件交给它：先给 `SKILL.md`、`references/case-brief.md` 和 `facts.md`，再按任务补上需要的文件（换风格给 `references/styles.md`，改编给 `storyboards/` 里的分镜，组织交付物给 `references/templates.md`）。文档里的路径都相对于技能根目录 `skills/video-maker/`。出片脚本按下文在本机运行。

## 快速上手：直接对 AI 说

下面这些请求可以直接发给装好技能的 AI：

1. **“把 Chrono Divide / vera20k 事件改编成纪录片风格的分镜，10 分钟左右。”**
   得到一份 Markdown 分镜稿：项目概要与风格卡、章节时长表、每章的 8 列分镜表、素材清单与制作备注。新分镜会存进 `storyboards/`，例如 `documentary.md`。
2. **“直接用现成的完整版分镜渲染成 mp4。”**
   不写新分镜，直接用 `render/full.json` 出片：得到 `full.mp4` 和逐镜拼图 `full_sheet.png`，AI 会先看拼图检查顺序、文字和打码，再提醒你实际播放确认节奏和声音。
3. **“做一条 3 分钟的事件速览，新闻播报风格。”**
   按时间线新写分镜，挑 3–4 个争议点，每个都给出双方说法。
4. **“只讲 PR #3087 这一个争议点，做一条专题分镜。”**
   围绕 PR 的改动、网页红警方的解释和 vera20k 作者的声明讲透。
5. **“做一版面向海外观众的英文分镜。”**
   以原作者的英文声明为主，中文截图配英文说明。

没说清的参数，AI 会用默认值并写进交付物的“项目概要”：风格默认解说，画幅默认横屏 16:9（指定竖屏时用 9:16），只说“分镜”时只交分镜，说“出片”“生成视频”才渲染。对风格只有模糊描述（“高级感”“节奏快一点”“像纪录片”）也可以，AI 会按 [`styles.md`](skills/video-maker/references/styles.md) 末尾的对照表落成具体参数。

## 自己动手出片

以下命令都在**技能根目录**下执行。Windows 见本节末尾。

### 0. 准备

```bash
cd skills/video-maker          # 已装到 Claude Code 的话：cd ~/.claude/skills/video-maker
mkdir -p ~/video-maker-out     # 成片和缓存都放这里，不要放进技能目录
```

### 1. 检查环境

```bash
python3 scripts/setup_env.py
```

它只检查、不改动任何东西，逐项列出 Python、ffmpeg + libass、中文字体、配音 TTS 是否就绪，并给出“能不能出片、缺什么”的结论。缺 ffmpeg 或中文字体时：

```bash
python3 scripts/setup_env.py --install
```

`--install` 会先列出要做的事，然后直接执行（不再二次确认），需要联网：

- 用 pip 安装 `imageio-ffmpeg`（自带完整版 ffmpeg）；当前 Python 不允许 `--user` 安装时，改装到技能目录下的 `.venv/`，渲染脚本会自动找到。
- 系统里找不到中文字体时，下载开源字体 Noto Sans SC（约 18 MB）到技能目录下的 `fonts/`。
- 加 `--with-edge-tts` 会另装在线配音 edge-tts，旁白文本会发送到微软的在线语音服务。

也可以自己装 ffmpeg（macOS `brew install ffmpeg`；Linux `sudo apt install ffmpeg`；Windows 下载 gyan.dev 的 ffmpeg full build 并把 `bin` 加入 PATH），已有 ffmpeg 时设置环境变量 `FFMPEG=/path/to/ffmpeg` 即可。

### 2a. 直接渲染现成分镜

`render/full.json` 是完整版分镜的渲染规格，不用改分镜就能出片：

```bash
# 先空跑：只检查素材、每镜时长和占位镜头，不出视频
python3 scripts/render_video.py render/full.json -o ~/video-maker-out/full.mp4 --work ~/video-maker-out/full_build --dry-run

# 出片，同时输出逐镜拼图 full_sheet.png
python3 scripts/render_video.py render/full.json -o ~/video-maker-out/full.mp4 --work ~/video-maker-out/full_build --sheet
```

一定要带 `-o` 和 `--work`：不带的话成片会写在 `render/` 里，缓存目录也会建在那里（空跑也会建）。

### 2b. 从自己的分镜出片

分镜是 Markdown 表格，8 列：`镜号 | 时长 | 画面类型 | 运镜 | 画面内容 | 旁白/台词 | 字幕/花字 | 声音/备注`，写法见 [`SKILL.md`](skills/video-maker/SKILL.md) 第 6 步和 [`rendering.md`](skills/video-maker/references/rendering.md) 第 3 节。

```bash
# 检查分镜：各表时长合计、旁白超速的镜头、没用到的图
python3 scripts/storyboard_check.py storyboards/你的分镜.md --speed 4.5 --images 50

# 分镜 → 渲染 JSON；--assets 指向技能自带素材，缺了会找不到图、也不会按清单自动打码
python3 scripts/md2render.py storyboards/你的分镜.md --assets assets -o ~/video-maker-out/mine.json

# 空跑，再出片 + 拼图
python3 scripts/render_video.py ~/video-maker-out/mine.json --dry-run
python3 scripts/render_video.py ~/video-maker-out/mine.json --sheet
```

成片 `mine.mp4`、拼图 `mine_sheet.png` 和缓存目录 `mine_build/` 都在 JSON 旁边。`md2render.py` 不会自动创建输出目录，请先 `mkdir`。

其他常用写法：

```bash
# 按章合计时长；导出 CSV（Excel 可直接打开）
python3 scripts/storyboard_check.py storyboards/full.md --group-level 3 --csv ~/video-maker-out/csv

# 竖屏 + 浅色主题：转换时写进 meta
python3 scripts/md2render.py storyboards/你的分镜.md --assets assets -o ~/video-maker-out/short.json --style-meta theme=light,width=1080,height=1920

# 或渲染时临时改画幅 / 主题（--size 可取 vertical、square、1920x1080 这类宽x高）
python3 scripts/render_video.py ~/video-maker-out/mine.json --size vertical --theme light

# 只重渲改过的几镜，输出 mine_preview.mp4；之后全量渲染时未改动的镜头直接用缓存
python3 scripts/render_video.py ~/video-maker-out/mine.json --only 2-03,2-07 --sheet

# 列出本机可用的中文配音
python3 scripts/render_video.py --list-voices
```

`render_video.py` 的常用参数：

| 参数 | 作用 |
| --- | --- |
| `--tts none` | 不配音，只烧录字幕；也可选 `auto` `say` `sapi` `espeak` `edge` |
| `--voice 名称` / `--rate 数值` | 指定配音语音和语速 |
| `--bgm 文件 --bgm-volume 0.15` | 背景音乐，有旁白时自动压低 |
| `--font 字体文件` | 指定中文字体（ttf/otf/ttc） |
| `--no-subs` | 不烧录旁白字幕 |
| `--quality 1/2/3` | 运镜防抖倍数，默认 2；1 更快，3 更平滑 |
| `--max-tempo 1.35` | 配音比镜头长时最多保调加速几倍，设为 1 则只延长镜头 |
| `--fps 30` | 帧率 |

补高亮框、换外部素材（录屏、实拍）、用自己录的配音，都在渲染 JSON 里改，见 [`rendering.md`](skills/video-maker/references/rendering.md) 第 4–6 节。

### Windows

把命令里的 `python3` 换成 `python`，路径用反斜杠，输出目录写完整路径（Python 不会展开 `~`），例如：

```powershell
cd skills\video-maker
python scripts\setup_env.py
mkdir D:\video-maker-out
python scripts\render_video.py render\full.json -o D:\video-maker-out\full.mp4 --work D:\video-maker-out\full_build --sheet
```

### 素材更新时

正常使用用不到这一步。只有拿到新的证据截图或 docx 文档、需要更新技能内容时，才用它抽取正文和插图，再对照更新 `assets/`、`facts.md` 和制作简报的证据图索引（做法见 `SKILL.md` 末节）：

```bash
python3 scripts/extract_docx.py 新文档.docx ~/video-maker-out/新文档抽取
```

## 常见问题与注意事项

| 现象 | 处理 |
| --- | --- |
| 环境检查显示找不到 ffmpeg，或渲染报“没有 libass（缺 subtitles 过滤器）” | 运行 `setup_env.py --install`，或换完整版 ffmpeg 并设置 `FFMPEG` |
| 画面里的中文显示成方框 | 字体缺中文字形：渲染时 `--font` 指定中文字体（或设环境变量 `VS_FONT`），或用 `setup_env.py --install` 下载 Noto Sans SC |
| pip 报 externally-managed-environment | `setup_env.py --install` 会自动改用技能内 `.venv`；也可以自建虚拟环境 |
| 成片没有配音、只有字幕 | 系统缺中文语音。macOS：系统设置 → 辅助功能 → 朗读内容 → 系统声音 → 管理声音，添加中文（中国大陆）；Windows：设置 → 时间和语言 → 语音 → 添加语音 → 中文（简体）；Linux 装 `espeak-ng` |
| `md2render.py` 报 FileNotFoundError | 输出目录不存在，先 `mkdir -p` |
| 渲染慢 | `--quality 1`；先用 `--only` 调好个别镜头再全量渲染 |
| 运镜有轻微抖动 | `--quality 3`，或把该镜运镜改成“固定” |
| 字幕压住截图关键处 | 缩短旁白，或把关键处放在画面上半部（加高亮框），或改用引文卡 |
| 某一镜报错 | 报错会列出 ffmpeg 命令和最后几行输出，用 `--only <镜号>` 单独重试 |

- **成片和缓存放在技能目录之外。** 用 `-o` 和 `--work` 指到别处，尤其是软链接安装时，免得把 mp4 和缓存带进仓库。
- **`--install` 会在技能目录生成 `.venv/` 或 `fonts/`**，属于本机环境，不要提交，也不要打进上传用的 zip。
- **交付前看拼图，再实际播放。** 拼图只能检查构图、文字和打码；节奏和配音要播放确认。
- **系统 TTS 音质有限。** 正式发布建议真人配音：按镜头切好录音，写进渲染 JSON 每镜的 `audio` 字段。
- **高亮框和打码坐标要人工确认**，脚本不会自动识别文字位置；`assets.json` 里标了渲染时自动模糊的区域。
- **自己写分镜时先读制作简报和事实表。** [`case-brief.md`](skills/video-maker/references/case-brief.md) 第 3 节是必须遵守的口径；[`facts.md`](skills/video-maker/facts.md) 第 4 节列了没有公开证据、不能说成事实的内容；图33、图38 只存档，不用于成片。

## 进阶版技能：video-maker-pro（动效与声音）

skills/video-maker-pro/ 是在 ideo-maker 之上蒸馏出来的进阶流水线：同样做这个题材，但补上了**关系网、矛盾对撞、证据墙、流程链、网页摘录、提问卡、巨型质问、猜测卡**这八类自制动效场景，以及一套**程序化配乐与音效**（numpy 合成，无版权素材）、混音与响度校准、可逐镜重跑的构建流水线。

- 它不重复造渲染器：装配仍用 ideo-maker/scripts/render_video.py，两个技能放在同一个 skills/ 目录即可（也支持 VIDEO_MAKER_SKILL 指定路径）。
- 自带一支 93 镜 / 16 分 42 秒的成品分镜 [story/story_v3.py](skills/video-maker-pro/story/story_v3.py)，并附带 [公开网页摘录](skills/video-maker-pro/web-evidence.md)（6 个网页的原文与抓取日期）。
- 进入方式看 [skills/video-maker-pro/SKILL.md](skills/video-maker-pro/SKILL.md)；流水线细节、场景参数、声音做法、写法与踩坑在 
eferences/ 下。

两条命令试跑：

`ash
cd skills/video-maker-pro
python tools/build.py narration && python tools/build.py all
`

更多细节：工作流程看 [`SKILL.md`](skills/video-maker/SKILL.md)，出片、JSON 规范和排错看 [`rendering.md`](skills/video-maker/references/rendering.md)。
