# 踩坑清单

全部是这套流水线真跑过之后撞出来的，按"症状 → 原因 → 修法"记。

## 渲染

**动效片段重渲了，成片没变**
渲染器按镜头内容做 sha1 缓存（`clips/NNN_<hash>.mkv`）。改了 `scenes3.py` 但没删 `build/clips/SXX.mp4`，装配就会用旧的。
→ 删对应片段，或 `VMP_FORCE=1`。

**`TypeError: can only concatenate str (not "tuple") to str`**
`StampScene` 的 `color` 传了 `"#E5432D"` 字符串，内部却按 RGB 元组拼 `(r,g,b,a)`。
→ 用 `scenes.col()` 把 hex 转元组（`scenes3` 里已统一走 `col()`）。

**`AttributeError: 'str' object has no attribute 'resize'`**
`QuestionScene` 的 `emoji` 传进来是 png 路径，代码直接 `put()` 贴图。
→ `anim.emoji_img(v, size)`：传路径读文件，传字符查 emoji 目录，缺失时返回 2×2 空白。

**`TypeError: 'float' object cannot be interpreted as an integer`**
`shot_card()` 收到按宽高比算出的 float 高度。
→ `hh = clamp(int(cw / asp), 200, cmax)`，函数入口 `w, h = int(w), int(h)`。

**emoji 位置是空圈**
`story` 里写了 `e("1f4fa")`，但 `assets/emoji/1f4fa.png` 没下载，`emoji_img` 静默返回空白。
→ 跑 `test_stills.py` 找空圈；`tools/fetch_emoji.mjs` 补文件（见下）。

**✅ / ✕ 变成豆腐块**
微软雅黑没有 U+2715 等符号字形。
→ `anim.mark_icon("check"/"cross", size, color)` 用线段矢量画。

**文字被画面裁掉**
`chain` 的首尾节点标签以节点为中心居中，宽文字溢出画布；`network` 底部节点 y=0.84 会把标签压到字幕上。
→ chain 首尾用左/右锚点（已在 `scenes.py` 修）；network 的 `py` 钳到 `0.735H`，`px` 钳到 `[150, W-150]`。

**`Pattern type 'glob' was selected but globbing is not supported`**
某些 ffmpeg 构建的 image2 不解 glob。
→ 不要用 glob 输入拼图，用 PIL 拼。

## 声音

**True Peak 超过 0 dBTP**
44 个音效里最响的 RMS −9.4，loudnorm 之后仍溢出。
→ `loudnorm=TP=-4` + `alimiter=limit=0.63:level=false`；`level=false` 是关键，默认 true 会把电平抬回来。

**BGM 听不见 / 抢戏**
0.15 太轻（间隙 −35 dB），0.26 开始和音效打架。
→ 0.18 起调，用 `sidechaincompress` 而不是单纯拉低。

**生成的 wav 结尾"咔"一声**
方波状包络在切点有台阶。
→ 每个音效加 3 ms 淡入 / 35 ms 淡出；铺底加 50 ms / 300 ms。

**两个音效叠在一起爆音**
同一帧多个 `adelay` 叠加。
→ cue 之间至少隔 0.3 秒；不可避时把 `--sfx-volume` 降到 0.45。

## 环境

**`UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'`**
Windows 控制台默认 GBK，脚本打印 ✓。
→ `$env:PYTHONIOENCODING="utf-8"; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8`。

**PATH 上的 `python` 是微软商店占位符**（"Python was not found"）
→ 用真实解释器绝对路径，例如 `C:\Users\<you>\.dsh\dsh-runtimes\...\python.exe`。

**`shutil.which("edge-tts")` 返回 None**
pip 的控制台脚本不在 PATH。
→ 本流水线用 `python -m edge_tts`，绕开这个问题。

**中文源码被写成乱码，`SyntaxError: unterminated triple-quoted string literal`**
用 PowerShell `Get-Content` / `Set-Content` 改 UTF-8 中文脚本，编码在往返中被破坏。
→ 用能保持 UTF-8 的写文件工具整篇重写；不要用 shell 文本重定向改中文源码。

## 网络（本机特定，可跳过）

- `raw.githubusercontent.com` 的 DNS 会被解析到 0.0.0.0 → 用 `gcore.jsdelivr.net` / `testingcf.jsdelivr.net` 镜像。
- `curl.exe` / `Invoke-WebRequest` 在该沙箱下 TLS 失败（`SEC_E_NO_CREDENTIALS`）→ 用 node 的 `fetch`（OpenSSL）。
  补 emoji：
  ```bash
  node tools/fetch_emoji.mjs 1f4fa 2753     # 从 gcore.jsdelivr.net 拉到 assets/emoji/
  ```
