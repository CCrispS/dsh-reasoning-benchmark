# -*- coding: utf-8 -*-
"""出片流水线：旁白 → 动效片段 → render.json → 装配（→ 混音）。

用法：python tools/build.py {narration|clips|json|video|all}
环境变量：VIDEO_MAKER_SKILL（渲染器技能目录）、VMP_STORY（分镜模块名）、
          VMP_OUT（输出目录）、VMP_FORCE=1（强制重渲全部动效片段）、FFMPEG。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.dirname(HERE)
STORY_DIR = os.path.join(ROOT, "story")
sys.path.insert(0, STORY_DIR)
VIDEO_MAKER = os.environ.get("VIDEO_MAKER_SKILL") or os.path.join(os.path.dirname(ROOT), "video-maker")
STORY_MODULE = os.environ.get("VMP_STORY", "story_v3")
BUILD = os.path.join(ROOT, "build")
CLIPS = os.path.join(BUILD, "clips")
NAR = os.path.join(ROOT, "audio", "nar")
AUDIO = os.path.join(ROOT, "audio")
OUT = os.environ.get("VMP_OUT") or os.path.join(ROOT, "out")

PY = sys.executable
FFMPEG = os.environ.get("FFMPEG") or "ffmpeg"
VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "+14%"

MIN_DUR = {"title": 3.6, "network": 6.0, "versus": 6.4, "chain": 5.6,
           "stamp": 3.8, "quote": 5.2, "end": 4.6,
           "question": 7.0, "bigq": 6.6, "contradiction": 8.6, "wall": 7.6,
           "flow": 6.6, "web": 8.2, "guess": 7.2}
FORCE = os.environ.get("VMP_FORCE", "0") == "1"


def load_story():
    import importlib
    mod = importlib.import_module(STORY_MODULE)
    importlib.reload(mod)
    return mod.SHOTS


def ensure_dirs():
    for d in (CLIPS, NAR, os.path.join(AUDIO, "bgm"), os.path.join(AUDIO, "sfx"), OUT,
              os.path.join(BUILD, "work")):
        os.makedirs(d, exist_ok=True)


def sh(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if p.returncode != 0:
        raise RuntimeError("命令失败 %s\n%s\n%s" % (cmd[:3], p.stdout[-2000:], p.stderr[-3000:]))
    return p


def wav_dur(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def narration(skip_existing=True):
    shots = load_story()
    rows = []
    for i, s in enumerate(shots):
        sid = s["id"]
        mp3 = os.path.join(NAR, sid + ".mp3")
        wav = os.path.join(NAR, sid + ".wav")
        if not (skip_existing and os.path.exists(wav)):
            sh([PY, "-m", "edge_tts", "--voice", VOICE, "--rate", RATE,
                "--text", s["narration"], "--write-media", mp3])
            sh([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", mp3,
                "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav])
        dur = wav_dur(wav)
        rows.append(dict(id=sid, kind=s["kind"], ndur=round(dur, 3)))
        print("%-4s %-6s %5.2fs  %s" % (sid, s["kind"], dur, s["narration"][:34]))
    with open(os.path.join(BUILD, "narration.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    total = sum(r["ndur"] for r in rows)
    print("旁白合计 %.1f 秒 / %d 镜" % (total, len(rows)))
    return rows


def plan(rows):
    shots = load_story()
    cues = []
    t = 0.0
    out = []
    for s, r in zip(shots, rows):
        ndur = r["ndur"]
        if s["kind"] == "media":
            want = MIN_DUR.get(s["scene"]["type"], 5.0)
        else:
            want = 3.4
        dur = max(ndur + 0.55, want)
        out.append(dict(shot=s, ndur=ndur, dur=round(dur, 3), start=round(t, 3)))
        for fx in s.get("sfx", []):
            cues.append(dict(file=fx, at=round(t + 0.05, 3)))
        t += dur
    return out, cues, t


def clips(only=None):
    import anim
    import scenes3 as scenes
    rows = json.load(open(os.path.join(BUILD, "narration.json"), encoding="utf-8"))
    plans, _, _ = plan(rows)
    for p in plans:
        s = p["shot"]
        if s["kind"] != "media":
            continue
        if only and s["id"] not in only:
            continue
        spec = dict(s["scene"])
        spec["dur"] = p["dur"] + 0.12
        path = os.path.join(CLIPS, s["id"] + ".mp4")
        if os.path.exists(path) and not FORCE:
            print("%-4s 已存在，跳过" % s["id"])
            continue
        scene = scenes.TYPES[spec.pop("type")](**spec)
        anim.render_scene(scene, path, crf=18, preset="fast")
        sz = os.path.getsize(path) / 1e6
        print("%-4s %.2fs  %5.1f MB" % (s["id"], spec.get("dur", 0), sz))


def image_id(fname):
    m = re.match(r"img(\d+)\.png$", fname)
    return "图%d" % int(m.group(1)) if m else fname


def render_json():
    import importlib
    story = importlib.import_module(STORY_MODULE)
    rows = json.load(open(os.path.join(BUILD, "narration.json"), encoding="utf-8"))
    plans, cues, total = plan(rows)
    shots = []
    for p in plans:
        s = p["shot"]
        if s["kind"] == "media":
            shots.append(dict(id=s["id"], type="media", duration=p["dur"],
                              media=os.path.join(CLIPS, s["id"] + ".mp4"),
                              narration=s["narration"],
                              audio=os.path.join(NAR, s["id"] + ".wav")))
        else:
            shots.append(dict(id=s["id"], type="image", duration=p["dur"],
                              images=[image_id(f) for f in s["images"]],
                              motion=s.get("motion", "push"),
                              caption=s.get("caption", ""),
                              narration=s["narration"],
                              audio=os.path.join(NAR, s["id"] + ".wav")))
    doc = dict(
        meta=dict(title=getattr(story, "TITLE", STORY_MODULE), width=1920, height=1080, fps=30, theme="dark",
                  tts="none", speed=1.0, subtitles=True,
                  assets_dir=os.path.join(VIDEO_MAKER, "assets"),
                  assets_manifest=os.path.join(VIDEO_MAKER, "assets", "assets.json")),
        shots=shots)
    path = os.path.join(BUILD, "render.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BUILD, "cues.json"), "w", encoding="utf-8") as f:
        json.dump(dict(cues=cues, total=round(total, 3)), f, ensure_ascii=False, indent=1)
    print("render.json %d 镜 总时长 %d:%04.1f" % (len(shots), total // 60, total % 60))
    return path


def build_video(only=None, sheet=True):
    spec = os.path.join(BUILD, "render.json")
    cmd = [PY, os.path.join(VIDEO_MAKER, "scripts", "render_video.py"), spec,
           "--tts", "none", "--quality", "2",
           "--work", os.path.join(BUILD, "work"),
           "-o", os.path.join(OUT, STORY_MODULE + "_full.mp4")]
    if only:
        cmd += ["--only", only]
    if sheet:
        cmd += ["--sheet"]
    print(" ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    for line in p.stdout:
        print(line.rstrip())
    if p.wait() != 0:
        raise SystemExit("渲染失败")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["narration", "clips", "json", "video", "all"])
    ap.add_argument("--only", default=None)
    ap.add_argument("--no-sheet", action="store_true")
    a = ap.parse_args()
    ensure_dirs()
    if a.step in ("narration", "all"):
        narration()
    if a.step in ("clips", "all"):
        clips(only=a.only.split(",") if a.only else None)
    if a.step in ("json", "all"):
        render_json()
    if a.step in ("video", "all"):
        build_video(only=a.only, sheet=not a.no_sheet)
