#!/usr/bin/env python3
"""环境检查与安装：确认这台电脑能不能用 render_video.py 出片，缺什么、怎么装。只用标准库。

  python3 scripts/setup_env.py                    # 只检查，不改任何东西
  python3 scripts/setup_env.py --install          # 安装缺的：imageio-ffmpeg（pip）+ 必要时下载开源中文字体
  python3 scripts/setup_env.py --install --with-edge-tts   # 另装 edge-tts（在线配音，文本会发到微软服务）

Windows 用 `python scripts\\setup_env.py`。
"""
import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
sys.path.insert(0, str(HERE))
import render_video as rv  # noqa: E402

SYSTEM = platform.system()
NOTO_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"
NOTO_LICENSE = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/OFL.txt"
NOTO_FILE = "NotoSansSC-VF.ttf"


def sh(cmd, **kw):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace", **kw)


def check_python():
    ok = sys.version_info >= (3, 8)
    return ok, "Python %s（%s）" % (platform.python_version(), sys.executable), "" if ok else "需要 Python 3.8 以上"


def check_ffmpeg():
    cands = rv.ffmpeg_candidates()
    if not cands:
        return False, "未找到 ffmpeg", "运行 --install 安装 imageio-ffmpeg；或 macOS: brew install ffmpeg，Windows: 下载 gyan.dev 的 full build 并加入 PATH，Linux: apt/dnf install ffmpeg"
    notes = []
    for src, ff in cands:
        caps = rv.ffmpeg_caps(ff)
        ver = sh([ff, "-hide_banner", "-version"]).stdout.splitlines()[0] if Path(ff).is_file() else "?"
        missing = [k for k in ("subtitles", "zoompan", "gblur") if not caps[k]]
        if not missing:
            enc = "libx264" if caps["libx264"] else ("openh264" if caps["libopenh264"] else ("videotoolbox" if caps["h264_videotoolbox"] else "mpeg4（画质一般）"))
            return True, "%s：%s（%s；编码器 %s）" % (src, ff, ver[:60], enc), ""
        notes.append("%s 的 ffmpeg 缺少 %s" % (src, "/".join(missing)))
    return False, "；".join(notes), ("当前 ffmpeg 没有 libass（subtitles 过滤器），无法渲染中文字幕和卡片。"
                                   "请运行 --install 安装 imageio-ffmpeg，或换用完整版构建（brew install ffmpeg / gyan.dev full build），"
                                   "再用环境变量 FFMPEG 指向它")


def check_font():
    r = rv.locate_font()
    if r:
        return True, "%s（家族名 %s）" % r, ""
    return False, "未找到中文字体", "运行 --install 下载开源字体 Noto Sans SC（OFL 许可）到 %s" % (SKILL_DIR / "fonts")


def check_tts():
    found, tips = [], []
    if SYSTEM == "Darwin":
        v = rv.pick_say_voice()
        if v:
            found.append("say（自动选用 %s）" % v)
        else:
            tips.append("macOS 没有中文语音：系统设置 → 辅助功能 → 朗读内容 → 系统声音 → 管理声音，添加“中文（中国大陆）”语音")
    if SYSTEM == "Windows":
        exe = shutil.which("powershell") or shutil.which("pwsh")
        if exe:
            r = sh([exe, "-NoProfile", "-Command",
                    "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | "
                    "Where-Object { $_.VoiceInfo.Culture.Name -like 'zh-*' } | ForEach-Object { $_.VoiceInfo.Name }"])
            names = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            if names:
                found.append("SAPI（%s）" % "、".join(names[:3]))
            else:
                tips.append("Windows 没有中文 SAPI 语音：设置 → 时间和语言 → 语音 → 添加语音 → 中文（简体）")
    if shutil.which("espeak-ng"):
        found.append("espeak-ng（音质较机械）")
    elif SYSTEM == "Linux":
        tips.append("Linux 可安装 espeak-ng（apt install espeak-ng），或 --with-edge-tts 用在线配音")
    if shutil.which("edge-tts"):
        found.append("edge-tts（在线，需显式 --tts edge）")
    if found:
        return True, "；".join(found), "；".join(tips)
    return False, "没有可用的配音引擎（仍可出片：无配音，只有字幕；或自己录音后在 JSON 里用 audio 字段）", "；".join(tips)


def report():
    rows = [("Python", check_python()), ("ffmpeg + libass", check_ffmpeg()), ("中文字体", check_font()), ("配音 TTS", check_tts())]
    print("\n=== 视频创造者（video-maker）渲染环境检查（%s %s）===" % (SYSTEM, platform.machine()))
    for name, (ok, info, tip) in rows:
        print("[%s] %-14s %s" % ("✓" if ok else "✗", name, info))
        if tip:
            print("      → %s" % tip)
    ready = rows[0][1][0] and rows[1][1][0] and rows[2][1][0]
    print()
    if ready:
        print("结论：能出片。%s" % ("" if rows[3][1][0] else "（没有配音引擎，会输出只有字幕的无声版）"))
    else:
        lack = [n for n, (ok, _, _) in rows[:3] if not ok]
        print("结论：暂时不能出片，缺少：%s。运行 `%s %s --install` 自动安装。"
              % ("、".join(lack), Path(sys.executable).name, Path(__file__).as_posix().split("/")[-2] + "/setup_env.py"))
    return ready, rows


def pip_install(pkgs):
    cmd = [sys.executable, "-m", "pip", "install", "--user", "--upgrade"] + pkgs
    print("  执行：%s" % " ".join(cmd))
    r = sh(cmd)
    if r.returncode == 0:
        return True
    out = r.stdout
    if "externally-managed" in out or "externally managed" in out:
        venv = SKILL_DIR / ".venv"
        print("  当前 Python 不允许 --user 安装（PEP 668）。改为在技能目录建独立虚拟环境：%s" % venv)
        if not venv.exists():
            r2 = sh([sys.executable, "-m", "venv", str(venv)])
            if r2.returncode != 0:
                print(r2.stdout[-1500:])
                return False
        py = venv / ("Scripts/python.exe" if SYSTEM == "Windows" else "bin/python")
        cmd = [str(py), "-m", "pip", "install", "--upgrade"] + pkgs
        print("  执行：%s" % " ".join(cmd))
        r3 = sh(cmd)
        if r3.returncode == 0:
            print("  已装入 %s；render_video.py 会自动在这里找 ffmpeg。" % venv)
            if "edge-tts" in pkgs:
                print("  edge-tts 命令位于 %s，请把该目录加入 PATH 后再用 --tts edge。" % (py.parent))
            return True
        print(r3.stdout[-1500:])
        return False
    print(out[-1500:])
    return False


def download(url, dest):
    print("  下载：%s\n     → %s" % (url, dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "video-maker-setup"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            f.write(b)
            got += len(b)
            if total:
                sys.stdout.write("\r     %.1f / %.1f MB" % (got / 1e6, total / 1e6))
                sys.stdout.flush()
    print()
    tmp.replace(dest)


def install(rows, with_edge):
    plan = []
    ff_ok = rows[1][1][0]
    font_ok = rows[2][1][0]
    pkgs = []
    if not ff_ok:
        pkgs.append("imageio-ffmpeg")
    if with_edge and not shutil.which("edge-tts"):
        pkgs.append("edge-tts")
    if pkgs:
        plan.append("用 pip 安装 %s（当前解释器 %s，--user；不允许时改用技能内 .venv）" % ("、".join(pkgs), sys.executable))
    if not font_ok:
        plan.append("下载开源字体 Noto Sans SC（SIL OFL 1.1，约 18 MB）及许可证到 %s" % (SKILL_DIR / "fonts"))
    if not plan:
        print("\n无需安装：ffmpeg 和中文字体都已就绪。")
        return
    print("\n将执行以下操作：")
    for i, p in enumerate(plan, 1):
        print("  %d. %s" % (i, p))
    if with_edge:
        print("  注意：edge-tts 会把旁白文本发送到微软在线语音服务。")
    print()
    if pkgs:
        if pip_install(pkgs):
            import importlib
            import site
            try:
                site.addsitedir(site.getusersitepackages())
            except Exception:
                pass
            importlib.invalidate_caches()
        else:
            print("pip 安装失败。可改用系统包管理器安装 ffmpeg（见上方提示），再设置环境变量 FFMPEG。")
    if not font_ok:
        try:
            download(NOTO_URL, SKILL_DIR / "fonts" / NOTO_FILE)
            download(NOTO_LICENSE, SKILL_DIR / "fonts" / "OFL.txt")
        except Exception as e:  # 网络问题
            print("  字体下载失败：%s\n  可手动下载 Noto Sans SC 或思源黑体，放进 %s，或渲染时用 --font 指定。" % (e, SKILL_DIR / "fonts"))


def main():
    ap = argparse.ArgumentParser(description="检查并安装视频创造者（video-maker）的渲染环境")
    ap.add_argument("--install", action="store_true", help="安装缺少的组件（会先列出将做的事）")
    ap.add_argument("--with-edge-tts", action="store_true", help="同时安装 edge-tts（在线配音）")
    args = ap.parse_args()
    ready, rows = report()
    if args.install:
        install(rows, args.with_edge_tts)
        print("\n重新检查：")
        report()


if __name__ == "__main__":
    main()
