# -*- coding: utf-8 -*-
"""为新场景出静帧，检查排版。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "story"))

import anim
import scenes3
import story_v3 as story

OUT = os.path.join(ROOT, "build", "stills")
os.makedirs(OUT, exist_ok=True)

wanted = ["question", "bigq", "contradiction", "wall", "flow", "web", "guess", "network"]
picked = {}
for s in story.SHOTS:
    if s["kind"] != "media":
        continue
    t = s["scene"]["type"]
    if t in wanted and t not in picked:
        picked[t] = s

print("shots:", len(story.SHOTS), "types picked:", sorted(picked))
for t, s in picked.items():
    spec = dict(s["scene"])
    spec["dur"] = 8.0
    cls = scenes3.TYPES[spec.pop("type")]
    sc = cls(**spec)
    for frac in (0.5, 0.9):
        img = sc.frame(sc.dur * frac)
        p = os.path.join(OUT, "%s_%d.png" % (t, int(frac * 100)))
        img.convert("RGB").save(p)
        print("  ", p)
print("done")
