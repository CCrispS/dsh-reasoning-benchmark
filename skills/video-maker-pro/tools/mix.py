# -*- coding: utf-8 -*-
"""给装配好的成片加 BGM 与音效，并统一响度。视频流直接 copy。

python tools/mix.py --video out/<story>_full.mp4 --bgm audio/score.wav
"""
import argparse
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
AUDIO = os.path.join(ROOT, "audio")
OUT = os.environ.get("VMP_OUT") or os.path.join(ROOT, "out")
STORY_MODULE = os.environ.get("VMP_STORY", "story_v3")
FFMPEG = os.environ.get("FFMPEG") or "ffmpeg"


def dur_of(path):
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not m:
        raise RuntimeError("read duration failed: " + path)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=os.path.join(OUT, STORY_MODULE + "_full.mp4"))
    ap.add_argument("--bgm", default=os.path.join(AUDIO, "score.wav"))
    ap.add_argument("--bgm-volume", type=float, default=0.18)
    ap.add_argument("--sfx-volume", type=float, default=0.5)
    ap.add_argument("--out", default=os.path.join(OUT, STORY_MODULE + "_final.mp4"))
    ap.add_argument("--no-bgm", action="store_true")
    a = ap.parse_args()

    total = dur_of(a.video)
    cues = []
    cue_path = os.path.join(BUILD, "cues.json")
    if os.path.exists(cue_path):
        cues = json.load(open(cue_path, encoding="utf-8"))["cues"]
    cues = [c for c in cues if os.path.exists(os.path.join(AUDIO, "sfx", c["file"] + ".wav"))]
    use_bgm = (not a.no_bgm) and os.path.exists(a.bgm)

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", a.video]
    if use_bgm:
        cmd += ["-stream_loop", "-1", "-i", a.bgm]
    for c in cues:
        cmd += ["-i", os.path.join(AUDIO, "sfx", c["file"] + ".wav")]

    parts = ["[0:a]asplit=2[n1][n2]"]
    idx = 1
    mix_labels = []
    if use_bgm:
        parts.append("[1:a]volume=%.3f,afade=t=in:st=0:d=2.0,"
                     "afade=t=out:st=%.2f:d=3.0,atrim=0:%.2f,asetpts=N/SR/TB[bg]"
                     % (a.bgm_volume, max(0.0, total - 3.0), total))
        parts.append("[bg][n2]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=500[bgc]")
        parts.append("[n1][bgc]amix=inputs=2:duration=first:normalize=0[bed]")
        mix_labels.append("[bed]")
        idx = 2
    else:
        mix_labels.append("[n1]")
    for i, c in enumerate(cues):
        lab = "fx%d" % i
        ms = int(round(c["at"] * 1000))
        parts.append("[%d:a]volume=%.3f,adelay=%d|%d[%s]" % (idx + i, a.sfx_volume, ms, ms, lab))
        mix_labels.append("[%s]" % lab)
    if len(mix_labels) > 1:
        parts.append("%samix=inputs=%d:duration=first:normalize=0[mixed]"
                     % ("".join(mix_labels), len(mix_labels)))
        last = "[mixed]"
    else:
        last = mix_labels[0]
    parts.append("%sloudnorm=I=-16:TP=-4.0:LRA=11,"
                 "alimiter=limit=0.63:level=false:attack=5:release=80,"
                 "aresample=48000[aout]" % last)

    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-shortest", a.out]
    print("BGM:", ("on %.2f" % a.bgm_volume) if use_bgm else "off",
          "| SFX:", len(cues), "| dur %.1fs" % total)
    subprocess.run(cmd, check=True)
    print("done:", a.out, "%.1f MB" % (os.path.getsize(a.out) / 1e6))


if __name__ == "__main__":
    main()
