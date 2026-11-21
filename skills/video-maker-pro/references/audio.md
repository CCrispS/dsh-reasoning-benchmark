# 声音：合成、混音、响度

这里没有一首下载来的音乐。所有声音都是 numpy 现算出来的，好处是**没有版权问题**、可以按情绪改参数、可以精确对齐画面。

## 两段铺底

| | `bed-a`（平静） | `bed-b`（压迫） |
| --- | --- | --- |
| 脚本 | `tools/make_audio_calm.py` | `tools/make_audio_tension.py` |
| 调性 | A 小调 | D 小调 |
| 速度 | 60 BPM | 92 BPM |
| 时长 | 224 s（循环无缝） | 320.87 s（123 个整小节） |
| 电平 | peak −4.4 dBFS / mean −18.2 | peak −3.2 / RMS −17.9 |
| 构成 | 低频持续音 + 稀疏点缀 | 低 D 长音（7 分音）+ 每拍脉冲 + 每 8 小节铜管重音 + 半音爬行 + 4 条 riser + Schroeder 混响 |

`bed-b` 的关键取舍：**300–4k（人声频段）刻意留空**，能量压在 120 Hz 以下，这样压到旁白下面 −6~−8 dB 也不会糊住人声。

`score.py` 把两段接起来：前段平静，从指定镜（默认 `S41`，第四章开头）起切到压迫，5 秒交叉淡化。

## 音效（44 处 cue）

| 文件 | 时长 | RMS | 用在哪 |
| --- | --- | --- | --- |
| `impact-low` | 1.65 s | −18 | 章节落点 |
| `impact-hit` | 1.05 s | −20 | 结论砸下、矛盾被点破 |
| `whoosh-soft` / `whoosh-hard` | 0.82 / 0.64 s | −26 / −22 | 转场 |
| `stamp` | 0.44 s | −19 | 盖章式定论 |
| `pop` / `tick` / `tick-fast` | 0.16 / 0.06 / 1.0 s | −24 / −32 | 小节点出现 |
| `riser-up` / `riser-long` | 2.2 / 4.5 s | −24 | 推向揭示；`riser-long` 前 0.3 秒是静的，尾端对切点 |
| `thunder` | 2.6 s | −23.6 | 揭示帧，峰值在 t=0 |
| `heartbeat` | 2.0 s | −16.4 | 逼近感 |
| `question-ding` | 0.9 s | −17.5 | 提问卡 |
| `typewriter` | 1.4 s | −25.8 | 文字逐字出现 |
| `glitch-burst` | 0.8 s | **−9.4** | 矛盾揭露；最响，混音里要压到 −12 dB 以下 |
| `sub-drop` | 1.3 s | −21 | 下沉转场 |

音效在 story 里标记：`sfx=["impact-low"]`，`build.py plan()` 会把它们挂在镜头起点 +0.05 秒，写进 `cues.json`。

## 混音链（`tools/mix.py`）

```
[旁白] ──asplit──┬─→ sidechain 参考
                 └─→ 保留
[BGM ] volume=0.18 → afade in 2s / out 3s → atrim → sidechaincompress(threshold=0.02, ratio=6,
        attack=30, release=500) → amix(normalize=0) → 逐个 SFX  adelay → amix
→ loudnorm=I=-16:TP=-4:LRA=11 → alimiter=limit=0.63:level=false:attack=5:release=80
→ aac 192k / 48 kHz → -c:v copy -movflags +faststart
```

实测参数：`--bgm-volume 0.18 --sfx-volume 0.5`。0.15 太轻（旁白间隙只剩 −35 dB），0.26 在 44 个音效的场景里会开始抢戏。

## 响度：为什么必须两级

目标 **−16 LUFS / ≤ −1 dBTP**（视频平台通用）。第一版直接 `loudnorm` 得到 **+1.9 dBTP**——因为 44 个音效里有 RMS −9.4 的 `glitch-burst`，瞬时峰值把整条链推爆。

正确的做法是 **loudnorm 之后再限幅**：

- `loudnorm=I=-16:TP=-4.0` —— 目标峰值留 4 dB 余量；
- `alimiter=limit=0.63:level=false` —— 0.63 ≈ −4 dBFS，`level=false` 是关键的：默认 `level=true` 会把整体电平又抬回去，等于没限；
- aac 编码还会产生 0.5–1.3 dB 的 ISP 过冲，所以采样峰值要按 −3 dBFS 附近设限。

最终实测：**−16.1 LUFS / −0.9 dBTP / LRA 2.9**。

## 校验命令

```bash
# 响度（三项都在目标内才发片）
ffmpeg -hide_banner -i out/story_v3_final.mp4 -af loudnorm=print_format=summary -f null -
# 流参数
ffmpeg -hide_banner -i out/story_v3_final.mp4 2>&1 | grep -E "Duration|Stream #"
# 某段是不是真有声音（例如 BGM 切换点前后）
ffmpeg -hide_banner -ss 500 -t 6 -i out/story_v3_final.mp4 -af volumedetect -f null -
```

`check_audio.py` 会把每个 wav 读回来，打印时长 / 峰值 / RMS / 频段占比，改了合成参数后跑一遍。
