# -*- coding: utf-8 -*-
"""把两段 BGM 拼成一条 score：前段平静（bed-a），第四幕起转紧张（bed-b），交叉淡化。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)

import build  # noqa: E402

SF = os.environ.get("FFMPEG") or "ffmpeg"
BGM = os.path.join(ROOT, "audio", "bgm")
OUT = os.path.join(ROOT, "audio", "score.wav")
SWITCH_AT_SHOT = "S41"
XF = 5.0


def main():
    rows = json.load(open(os.path.join(ROOT, "build", "narration.json"), encoding="utf-8"))
    plans, cues, total = build.plan(rows)
    switch = None
    for p in plans:
        if p["shot"]["id"] == SWITCH_AT_SHOT:
            switch = p["start"]
            break
    if switch is None:
        raise SystemExit("找不到切换点 %s" % SWITCH_AT_SHOT)
    a, b = os.path.join(BGM, "bed-a.wav"), os.path.join(BGM, "bed-b.wav")
    a_end = switch + XF / 2.0
    b_len = total - switch + XF / 2.0 + 2.0
    fc = ("[0:a]atrim=0:%.2f,asetpts=N/SR/TB,afade=t=in:st=0:d=1.5[a];"
          "[1:a]atrim=0:%.2f,asetpts=N/SR/TB[b];"
          "[a][b]acrossfade=d=%.1f:c1=tri:c2=tri[o]" % (a_end, b_len, XF))
    cmd = [SF, "-y", "-hide_banner", "-loglevel", "error",
           "-stream_loop", "-1", "-i", a, "-stream_loop", "-1", "-i", b,
           "-filter_complex", fc, "-map", "[o]", "-ar", "48000", "-ac", "2",
           "-c:a", "pcm_s16le", OUT]
    subprocess.run(cmd, check=True)
    dur = os.path.getsize(OUT) / (48000 * 2 * 2)
    print("score: %.2fs (switch %.2fs of %.2fs) -> %s" % (dur, switch, total, OUT))


if __name__ == "__main__":
    main()
