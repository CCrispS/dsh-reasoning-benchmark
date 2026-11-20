#!/usr/bin/env python3
"""分镜渲染 JSON -> mp4。

只依赖 Python 3.8+ 标准库和 ffmpeg（需要 libass，用于 subtitles 过滤器）。
环境检查与安装：python3 scripts/setup_env.py [--install]
JSON 规范与用法：references/rendering.md

常用：
  python3 scripts/render_video.py video.json                 # 出整片
  python3 scripts/render_video.py video.json --sheet         # 同时输出每镜中间帧拼图
  python3 scripts/render_video.py video.json --only 2-01,2-03  # 只渲这几镜，输出预览片
  python3 scripts/render_video.py video.json --dry-run       # 只检查素材与时长，不渲染
  python3 scripts/render_video.py --list-voices              # 列出可用中文配音
"""
import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

VERSION = "7"
SKILL_DIR = Path(__file__).resolve().parent.parent
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

# ---------------------------------------------------------------- 主题

THEMES = {
    # 颜色均为 RRGGBB
    "dark": {
        "bg": "10131A", "vignette": "PI/3.2", "text": "FFFFFF", "sub": "C9D1DC",
        "accent": "E5432D", "accent2": "FFD38A", "panel": "1C2330", "line": "5A6478",
        "img_brightness": -0.28,
    },
    "light": {
        "bg": "F3EFE6", "vignette": "PI/7", "text": "1E1E1E", "sub": "5C5C5C",
        "accent": "C0392B", "accent2": "8A5A00", "panel": "FFFFFF", "line": "B8B0A0",
        "img_brightness": -0.12,
    },
}

CARD_TYPES = {"text", "chapter", "quote", "data", "timeline", "title", "end", "placeholder"}
ALL_TYPES = CARD_TYPES | {"image", "split", "media"}
MOTIONS = {"static", "push", "pull", "left", "right", "down", "up"}

INSTALL_HINT = (
    "请先运行环境检查：python3 scripts/setup_env.py（Windows：python scripts\\setup_env.py），\n"
    "按提示安装；或任选其一：\n"
    "  1) python3 -m pip install --user imageio-ffmpeg   （自带完整版 ffmpeg，含 libass）\n"
    "  2) macOS: brew install ffmpeg   Windows: 下载 gyan.dev 的 ffmpeg full build   Linux: apt install ffmpeg\n"
    "  3) 已有 ffmpeg 时设置环境变量 FFMPEG=/path/to/ffmpeg"
)


def die(msg, code=2):
    print("错误：" + msg, file=sys.stderr)
    sys.exit(code)


def warn(msg):
    print("提示：" + msg, file=sys.stderr)


# ---------------------------------------------------------------- ffmpeg

def ffmpeg_candidates():
    """查找顺序：环境变量 FFMPEG → PATH → imageio-ffmpeg（当前 Python）→ 技能内 .venv 里的 imageio-ffmpeg。"""
    cands = []
    if os.environ.get("FFMPEG"):
        cands.append(("环境变量 FFMPEG", os.environ["FFMPEG"]))
    w = shutil.which("ffmpeg")
    if w:
        cands.append(("PATH", w))
    try:
        import imageio_ffmpeg  # type: ignore
        cands.append(("imageio-ffmpeg", imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        pass
    venv = SKILL_DIR / ".venv"
    if venv.is_dir():
        for p in sorted(venv.glob("**/imageio_ffmpeg/binaries/ffmpeg*")):
            if p.is_file() and not p.name.endswith((".txt", ".md")):
                cands.append(("技能 .venv 中的 imageio-ffmpeg", str(p)))
    return [(src, c) for src, c in cands if c and Path(c).is_file()]


def locate_ffmpeg():
    c = ffmpeg_candidates()
    return c[0][1] if c else None


def find_ffmpeg():
    ff = locate_ffmpeg()
    if not ff:
        die("找不到 ffmpeg。\n" + INSTALL_HINT)
    return ff


def ffmpeg_caps(ff):
    r = subprocess.run([ff, "-hide_banner", "-filters"], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    filters = r.stdout
    r = subprocess.run([ff, "-hide_banner", "-encoders"], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    enc = r.stdout
    has = lambda name, text: re.search(r"\s%s\s" % re.escape(name), text) is not None
    return {
        "subtitles": has("subtitles", filters),
        "zoompan": has("zoompan", filters),
        "gblur": has("gblur", filters),
        "sidechaincompress": has("sidechaincompress", filters),
        "libx264": has("libx264", enc),
        "libopenh264": has("libopenh264", enc),
        "h264_videotoolbox": has("h264_videotoolbox", enc),
        "aac": has("aac", enc),
    }


def run(cmd, cwd=None):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tail = "\n".join(r.stderr.strip().splitlines()[-25:])
        raise RuntimeError("ffmpeg 失败（cwd=%s）：\n%s\n---\n%s" % (cwd, " ".join(map(str, cmd))[:1500], tail))
    return r


def probe(ff, path):
    r = subprocess.run([ff, "-hide_banner", "-i", str(path)], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    s = r.stderr
    dur = None
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", s)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    size = None
    m = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", s)
    if m:
        size = (int(m.group(1)), int(m.group(2)))
    return dur, size


# ---------------------------------------------------------------- 字体

FONT_CANDIDATES = {
    "Darwin": [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ],
    "Windows": [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\Deng.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ],
    "Linux": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc",
    ],
}
FONT_GLOBS = ["**/NotoSansCJK*.ttc", "**/NotoSansSC*.ttf", "**/NotoSansSC*.otf",
              "**/SourceHanSans*.ttc", "**/SourceHanSans*.otf", "**/wqy-*.ttc"]


def font_family_names(path):
    """读 TTF/OTF/TTC 的 name 表，返回英文家族名列表（第一个字体优先）。"""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    offsets = [0]
    if data[:4] == b"ttcf":
        n = struct.unpack(">I", data[8:12])[0]
        offsets = list(struct.unpack(">%dI" % n, data[12:12 + 4 * n]))
    names = []
    for off in offsets:
        try:
            num = struct.unpack(">H", data[off + 4:off + 6])[0]
            for i in range(num):
                rec = off + 12 + 16 * i
                if data[rec:rec + 4] != b"name":
                    continue
                toff, _ = struct.unpack(">II", data[rec + 8:rec + 16])
                _, count, soff = struct.unpack(">HHH", data[toff:toff + 6])
                found = {}
                for j in range(count):
                    r = toff + 6 + 12 * j
                    pid, eid, lid, nid, ln, so = struct.unpack(">HHHHHH", data[r:r + 12])
                    if nid not in (1, 16):
                        continue
                    raw = data[toff + soff + so: toff + soff + so + ln]
                    if pid == 3 and lid == 0x409:
                        found.setdefault(nid, raw.decode("utf-16-be", "ignore"))
                    elif pid == 1 and lid == 0:
                        found.setdefault(nid + 100, raw.decode("mac_roman", "ignore"))
                for key in (16, 1, 116, 101):
                    if key in found and found[key] and found[key] not in names:
                        names.append(found[key])
                        break
        except struct.error:
            continue
    return names


def locate_font(explicit=None):
    """查找顺序：--font → 环境变量 VS_FONT → 技能内 fonts/ → 系统常见中文字体。返回 (路径, 家族名) 或 None。"""
    cands = []
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            die("--font 指定的字体文件不存在：%s" % explicit)
        cands.append(p)
    if os.environ.get("VS_FONT"):
        cands.append(Path(os.environ["VS_FONT"]))
    local = SKILL_DIR / "fonts"
    if local.is_dir():
        cands += sorted([p for p in local.iterdir() if p.suffix.lower() in (".ttf", ".otf", ".ttc")])
    cands += [Path(p) for p in FONT_CANDIDATES.get(platform.system(), [])]
    if platform.system() == "Linux":
        for base in ("/usr/share/fonts", "/usr/local/share/fonts", str(Path.home() / ".local/share/fonts")):
            b = Path(base)
            if b.is_dir():
                for g in FONT_GLOBS:
                    cands += sorted(b.glob(g))
    for p in cands:
        if p.is_file():
            fams = font_family_names(p)
            if fams:
                pick = fams[0]
                for f in fams:  # 简体优先
                    if re.search(r"\bSC\b|GB|YaHei|Hei SC|CN", f):
                        pick = f
                        break
                return p, pick
    return None


def find_font(explicit=None):
    r = locate_font(explicit)
    if not r:
        die("找不到中文字体。请运行 python3 scripts/setup_env.py --install（会把开源字体 Noto Sans SC 下载到技能的 fonts/ 目录），或用 --font 指定字体文件。")
    return r


# ---------------------------------------------------------------- TTS

def list_say_voices():
    if not shutil.which("say"):
        return []
    r = subprocess.run(["say", "-v", "?"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace")
    out = []
    for line in r.stdout.splitlines():
        m = re.match(r"^(.+?)\s{2,}([a-z]{2,3}_[A-Za-z0-9]+)\s+#", line)
        if m:
            out.append((m.group(1).strip(), m.group(2)))
    return out


SAY_PREF = ["Tingting", "Ting-Ting", "Lili", "Lilian", "Yu-shu", "Reed", "Eddy", "Flo", "Rocko", "Sandy", "Shelley"]


def pick_say_voice(voice=None):
    vs = list_say_voices()
    if voice:
        for name, loc in vs:
            if name == voice or name.split(" (")[0] == voice:
                return name
        warn("say 中没有语音 %s，改用自动选择" % voice)
    zh = [(n, l) for n, l in vs if l.lower().startswith("zh_cn")]
    for pref in SAY_PREF:
        for n, l in zh:
            if n.split(" (")[0] == pref:
                return n
    if zh:
        return zh[0][0]
    anyzh = [n for n, l in vs if l.lower().startswith("zh")]
    return anyzh[0] if anyzh else None


SAPI_PS1 = r"""
param([string]$TextFile, [string]$OutFile, [string]$Voice, [int]$Rate)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($Voice) { $s.SelectVoice($Voice) } else {
  $v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'zh-*' } | Select-Object -First 1
  if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }
}
$s.Rate = $Rate
$s.SetOutputToWaveFile($OutFile)
$s.Speak([IO.File]::ReadAllText($TextFile, [Text.Encoding]::UTF8))
$s.Dispose()
"""


def resolve_tts_engine(engine):
    if engine != "auto":
        return engine
    if IS_MAC and shutil.which("say"):
        return "say"
    if IS_WIN and (shutil.which("powershell") or shutil.which("pwsh")):
        return "sapi"
    if shutil.which("espeak-ng"):
        return "espeak"
    warn("没有可用的本地 TTS，改为无配音（只出字幕）。可运行 setup_env.py 查看安装方法。")
    return "none"


def tts(ctx, text):
    """返回 (wav 路径, 时长)。按 引擎+语音+语速+文本 缓存。"""
    eng = ctx["tts"]
    key = hashlib.sha1(json.dumps([eng, ctx["voice"], ctx["rate"], text], ensure_ascii=False).encode()).hexdigest()[:16]
    d = ctx["work"] / "cache" / "tts"
    d.mkdir(parents=True, exist_ok=True)
    wav = d / (key + ".wav")
    if not wav.exists():
        txt = d / (key + ".txt")
        txt.write_text(text, encoding="utf-8")
        raw = None
        if eng == "say":
            raw = d / (key + ".aiff")
            cmd = ["say", "-f", str(txt), "-o", str(raw)]
            if ctx["voice"]:
                cmd[1:1] = ["-v", ctx["voice"]]
            if ctx["rate"]:
                cmd[1:1] = ["-r", str(int(ctx["rate"]))]
            subprocess.run(cmd, check=True)
        elif eng == "sapi":
            ps1 = d / "sapi_tts.ps1"
            ps1.write_text(SAPI_PS1, encoding="utf-8-sig")
            raw = d / (key + ".sapi.wav")
            exe = shutil.which("powershell") or shutil.which("pwsh")
            rate = int(ctx["rate"]) if ctx["rate"] is not None else 0
            subprocess.run([exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1),
                            "-TextFile", str(txt), "-OutFile", str(raw), "-Voice", ctx["voice"] or "",
                            "-Rate", str(rate)], check=True)
        elif eng == "espeak":
            raw = d / (key + ".espeak.wav")
            cmd = ["espeak-ng", "-v", ctx["voice"] or "cmn", "-w", str(raw), "-f", str(txt)]
            if ctx["rate"]:
                cmd[1:1] = ["-s", str(int(ctx["rate"]))]
            subprocess.run(cmd, check=True)
        elif eng == "edge":
            exe = shutil.which("edge-tts")
            if not exe:
                die("指定了 --tts edge，但没装 edge-tts：python3 -m pip install --user edge-tts（注意：文本会发送到微软在线服务）")
            raw = d / (key + ".mp3")
            cmd = [exe, "--voice", ctx["voice"] or "zh-CN-YunxiNeural", "--file", str(txt), "--write-media", str(raw)]
            if ctx["rate"]:
                cmd += ["--rate", "%+d%%" % int(ctx["rate"])]
            subprocess.run(cmd, check=True)
        else:
            raise ValueError(eng)
        run([ctx["ff"], "-y", "-hide_banner", "-loglevel", "error", "-i", raw,
             "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav])
    dur, _ = probe(ctx["ff"], wav)
    return wav, dur or 0.0



def spoken_units(text):
    """要念出来的单位数：汉字 + 英文单词 + 数字（与 storyboard_check.py 的口径一致，标点不计）。"""
    cjk = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
    words = re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:[.,]\d+)*", cjk.sub(" ", text))
    return len(cjk.findall(text)) + len(words)

def fit_tempo(ctx, wav, dur, target):
    """配音比镜头可用时长长时，用 atempo 保调加速（不超过 max_tempo 倍），尽量不改分镜节奏。
    系统 TTS 的语速参数与实际字速不成线性关系，按实测时长变速比调引擎参数更可靠，也适用于外部配音文件。"""
    if not dur or target <= 0 or dur <= target:
        return wav, dur
    factor = min(ctx["max_tempo"], dur / target)
    if factor < 1.02:
        return wav, dur
    d = ctx["work"] / "cache" / "tts"
    d.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(("%s|%.3f" % (Path(wav).resolve(), factor)).encode()).hexdigest()[:16]
    out = d / ("fit_" + key + ".wav")
    if not out.exists():
        run([ctx["ff"], "-y", "-hide_banner", "-loglevel", "error", "-i", wav,
             "-af", "atempo=%.4f" % factor, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", out])
    nd, _ = probe(ctx["ff"], out)
    return out, nd or dur / factor


# ---------------------------------------------------------------- 文本与 ASS

PUNCT_FULL = "，。！？；：、“”‘’（）【】《》—…·「」『』〈〉"


def char_w(c):
    o = ord(c)
    if c in PUNCT_FULL or o >= 0x2E80 or 0xFF00 <= o <= 0xFFEF:
        return 1.0
    if c == " ":
        return 0.3
    return 0.56


def text_w(s, fs):
    return sum(char_w(c) for c in s) * fs


def wrap(s, max_w, fs):
    lines = []
    for para in str(s).split("\n"):
        cur = ""
        for ch in para:
            if cur and text_w(cur + ch, fs) > max_w:
                if ch in "，。！？；：、”’）》」』…,.!?;:)":  # 避免行首标点
                    cur += ch
                    continue
                # 英文单词不拆
                m = re.search(r"[A-Za-z0-9_.\-/]+$", cur)
                if m and re.match(r"[A-Za-z0-9_.\-/]", ch) and len(m.group(0)) < len(cur):
                    lines.append(cur[:m.start()])
                    cur = m.group(0) + ch
                else:
                    lines.append(cur)
                    cur = ch
            else:
                cur += ch
        lines.append(cur)
    return [l for l in lines if l.strip()] or [""]


def fit_fs(s, max_w, fs, min_fs):
    while fs > min_fs and text_w(s, fs) > max_w:
        fs -= 2
    return fs


def ass_c(hex6, alpha=0):
    return "&H%02X%s%s%s&" % (alpha, hex6[4:6], hex6[2:4], hex6[0:2])


def ass_esc(s):
    return str(s).replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", "\\N")


def ass_t(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return "%d:%02d:%02d.%02d" % (h, m, s, cs)


def sub_chunks(text, maxc):
    """按标点切字幕块；英文单词、网址、数字不拆开；超长块按宽度均分。"""
    text = re.sub(r"\s+", " ", text).strip()
    parts = [p.strip() for p in re.split(r"(?<=[，。！？；：、…])|(?<=[,.!?;:])(?=\s)", text) if p.strip()]
    merged = []
    for p in parts:
        if merged and len(merged[-1]) + len(p) <= maxc and len(merged[-1]) < 6:
            merged[-1] += p
        else:
            merged.append(p)
    out = []
    for p in merged:
        if text_w(p, 1) <= maxc:
            out.append(p)
        else:
            n = math.ceil(text_w(p, 1) / maxc)
            out += wrap(p, text_w(p, 1) / n + 1.2, 1)
    return [o.strip() for o in out if o.strip()]


def clean_sub(s):
    return s.rstrip("，。；：、,.;:").strip("“”\"") if len(s) > 1 else s


class Ass:
    def __init__(self, W, H, fam, theme):
        self.W, self.H, self.fam, self.th = W, H, fam, theme
        self.u = min(W, H) / 1080.0
        self.ev = []

    def header(self):
        u, th = self.u, self.th
        styles = [
            # 样式字段：名称、字号、主色、描边色、背景色、粗体、边框样式、描边、阴影、对齐、边距
            ("Sub", 50 * u, ass_c("FFFFFF"), ass_c("000000"), ass_c("000000", 0x80), -1, 1, 3.2 * u, 0, 2, 44 * u),
            ("Text", 50 * u, ass_c(th["text"]), ass_c("000000"), ass_c("000000", 0x80), 0, 1, 0, 0, 5, 0),
            ("Box", 56 * u, ass_c("FFFFFF"), ass_c("0B0D12", 0x38), ass_c("000000", 0xFF), -1, 3, 16 * u, 0, 1, 0),
            ("Shape", 20, ass_c("FFFFFF"), ass_c("000000"), ass_c("000000", 0xFF), 0, 1, 0, 0, 7, 0),
        ]
        lines = [
            "[Script Info]", "ScriptType: v4.00+", "PlayResX: %d" % self.W, "PlayResY: %d" % self.H,
            "WrapStyle: 2", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        ]
        for n, fs, pc, oc, bc, b, bs, o, sh, al, mv in styles:
            lines.append("Style: %s,%s,%d,%s,&H000000FF&,%s,%s,%d,0,0,0,100,100,0,0,%d,%.1f,%.1f,%d,%d,%d,%d,1"
                         % (n, self.fam, round(fs), pc, oc, bc, b, bs, o, sh, al, round(60 * self.u), round(60 * self.u), round(mv)))
        lines += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
        return "\n".join(lines) + "\n"

    def add(self, layer, t0, t1, style, text):
        self.ev.append("Dialogue: %d,%s,%s,%s,,0,0,0,,%s" % (layer, ass_t(t0), ass_t(t1), style, text))

    def txt(self, t0, t1, x, y, an, fs, color, text, bold=False, extra="", layer=2, fade=(150, 150), alpha=0):
        f = "\\fad(%d,%d)" % fade if fade else ""
        tag = "{\\an%d\\pos(%d,%d)\\fs%d\\c%s\\1a&H%02X&\\b%d%s%s}" % (
            an, round(x), round(y), round(fs), ass_c(color), alpha, 1 if bold else 0, f, extra)
        self.add(layer, t0, t1, "Text", tag + ass_esc(text))

    def shape(self, t0, t1, path, color, alpha=0, bord=0, bcolor=None, layer=0, fade=(150, 150)):
        f = "\\fad(%d,%d)" % fade if fade else ""
        tag = "{\\an7\\pos(0,0)\\p1\\bord%.1f\\shad0\\1c%s\\1a&H%02X&\\3c%s%s}" % (
            bord, ass_c(color), alpha, ass_c(bcolor or color), f)
        self.add(layer, t0, t1, "Shape", tag + path + "{\\p0}")

    def rect(self, t0, t1, x1, y1, x2, y2, color, alpha=0, **kw):
        p = "m %d %d l %d %d l %d %d l %d %d" % (x1, y1, x2, y1, x2, y2, x1, y2)
        self.shape(t0, t1, p, color, alpha, **kw)

    def circle(self, t0, t1, cx, cy, r, color, **kw):
        k = 0.5523 * r
        p = ("m %d %d b %d %d %d %d %d %d b %d %d %d %d %d %d b %d %d %d %d %d %d b %d %d %d %d %d %d" % (
            cx - r, cy,
            cx - r, cy - k, cx - k, cy - r, cx, cy - r,
            cx + k, cy - r, cx + r, cy - k, cx + r, cy,
            cx + r, cy + k, cx + k, cy + r, cx, cy + r,
            cx - k, cy + r, cx - r, cy + k, cx - r, cy))
        self.shape(t0, t1, p, color, **kw)

    def text(self):
        return self.header() + "\n".join(self.ev) + "\n"


def add_subtitles(a, narration, start, dur, D):
    if not narration or dur <= 0:
        return
    u = a.u
    maxc = min(22, int(a.W * 0.9 / (50 * u)))
    chunks = sub_chunks(narration, maxc)
    total = sum(len(c) for c in chunks) or 1
    t = start
    for c in chunks:
        d = dur * len(c) / total
        a.add(5, t, min(D, t + d), "Sub", ass_esc(clean_sub(c)))
        t += d


def add_caption(a, caption, D, theme):
    if not caption:
        return
    u, W, H = a.u, a.W, a.H
    fs = 56 * u
    # “主标题／补充”：补充信息另起一行、字号小一号，不把分隔符显示出来
    main, _, extra = caption.partition("／")
    main, extra = main.strip(), extra.strip()
    lines = wrap(main or extra, W * 0.78, fs)[:2]
    y = H - 150 * u if W >= H else H - 300 * u
    tag = "{\\an1\\pos(%d,%d)\\fad(250,120)}" % (round(70 * u), round(y))
    body = "{\\c%s}▍{\\c%s}" % (ass_c(theme["accent"]), ass_c("FFFFFF")) + "\\N".join(ass_esc(l) for l in lines)
    if main and extra:
        sfs = 40 * u
        sub = wrap(extra, W * 0.78, sfs)[0]
        body += "\\N{\\fs%d\\c%s}%s" % (round(sfs), ass_c("C9D1DC"), ass_esc(sub))
    a.add(3, 0.15, D, "Box", tag + body)


def split_title(card):
    t = (card.get("title") or "").strip()
    return t


def card_events(a, typ, card, D, th):
    """各类卡片的版式。所有坐标用画幅比例，适配横竖屏。"""
    W, H, u = a.W, a.H, a.u
    portrait = H > W
    title = (card.get("title") or "").strip()
    sub = (card.get("sub") or "").strip()
    items = [i for i in (card.get("items") or []) if str(i).strip()]
    kicker = (card.get("kicker") or "").strip()
    T, S, A, A2 = th["text"], th["sub"], th["accent"], th["accent2"]

    def block(lines, x, y, an, fs, color, bold=False, lh=1.35):
        n = len(lines)
        for i, l in enumerate(lines):
            if an in (4, 5, 6):
                yy = y + (i - (n - 1) / 2) * fs * lh
            elif an in (7, 8, 9):
                yy = y + i * fs * lh
            else:
                yy = y - (n - 1 - i) * fs * lh
            a.txt(0, D, x, yy, an, fs, color, l, bold)
        return n * fs * lh

    if typ == "chapter" and sub and not kicker and len(title) <= 10 and len(sub) > len(title):
        # “第二章／命名：把原作写成派生”：短的序号做眉标，真正的章节名做大标题
        kicker, title, sub = title, sub, ""
    if typ in ("title", "chapter", "end"):
        big = (120 if typ == "title" else 100) * u
        if typ == "end" and not title:
            title = "感谢观看"
        big = fit_fs(title, W * 0.86, big, 56 * u)
        tl = wrap(title, W * 0.86, big)
        cy = H * (0.44 if not portrait else 0.42)
        if kicker:
            a.txt(0, D, W / 2, cy - big * (len(tl) / 2 + 0.95), 5, 44 * u, A, kicker, True, extra="\\fsp%d" % round(8 * u))
        hgt = block(tl, W / 2, cy, 5, big, T, True)
        bar_y = cy + hgt / 2 + 26 * u
        a.rect(0, D, W / 2 - 70 * u, bar_y, W / 2 + 70 * u, bar_y + 8 * u, A)
        if sub:
            sl = wrap(sub, W * 0.8, 46 * u)
            block(sl, W / 2, bar_y + 40 * u, 8, 46 * u, S)
        if items:
            y0 = bar_y + (120 if sub else 50) * u
            for i, it in enumerate(items[:4]):
                a.txt(0, D, W / 2, y0 + i * 56 * u, 8, 40 * u, S, it)
        return

    if typ == "text":
        if items:
            x0 = W * (0.14 if not portrait else 0.08)
            maxw = W - 2 * x0
            y = H * (0.22 if not portrait else 0.25)
            if title:
                tl = wrap(title, maxw, 72 * u)
                y += block(tl, x0, y, 7, 72 * u, T, True) + 50 * u
            fs = 52 * u
            for it in items[:7]:
                lines = wrap(it, maxw - 60 * u, fs)
                a.txt(0, D, x0, y + 4 * u, 7, fs, A, "▍", True)
                for j, l in enumerate(lines):
                    a.txt(0, D, x0 + 56 * u, y + j * fs * 1.3, 7, fs, T, l)
                y += len(lines) * fs * 1.3 + 30 * u
        else:
            fs = fit_fs(title, W * 0.8 * 2, 84 * u, 56 * u)
            tl = wrap(title, W * 0.8, fs)
            hgt = block(tl, W / 2, H * 0.45, 5, fs, T, True)
            if sub:
                block(wrap(sub, W * 0.76, 46 * u), W / 2, H * 0.45 + hgt / 2 + 40 * u, 8, 46 * u, S)
        return

    if typ == "quote":
        x0 = W * (0.15 if not portrait else 0.09)
        maxw = W * (0.70 if not portrait else 0.82)
        a.txt(0, D, x0 - 30 * u, H * 0.20, 7, 240 * u, A, "“", True)
        fs = 60 * u if len(title) < 60 else 50 * u
        tl = wrap(title, maxw, fs)
        y0 = H * 0.30
        hgt = block(tl, x0 + 40 * u, y0, 7, fs, T, False, lh=1.45)
        if sub:
            a.txt(0, D, x0 + 40 * u + maxw, y0 + hgt + 50 * u, 9, 42 * u, S, "—— " + sub)
        return

    if typ == "data":
        fs = fit_fs(title, W * 0.9, 190 * u, 80 * u)
        a.txt(0, D, W / 2, H * 0.44, 5, fs, A, title, True)
        if sub:
            block(wrap(sub, W * 0.8, 52 * u), W / 2, H * 0.44 + fs * 0.62 + 30 * u, 8, 52 * u, T)
        for i, it in enumerate(items[:3]):
            a.txt(0, D, W / 2, H * 0.74 + i * 52 * u, 8, 40 * u, S, it)
        return

    if typ == "timeline":
        pts = []
        for it in items[:8]:
            m = re.match(r"^\s*([^：:｜|\s]+(?:\s*年)?(?:\s*\d+\s*月)?(?:\s*\d+\s*日)?)\s*[：:｜|\s]\s*(.+)$", it)
            pts.append((m.group(1), m.group(2)) if m else ("", it))
        n = max(1, len(pts))
        if title:
            a.txt(0, D, W / 2, H * (0.16 if not portrait else 0.10), 5, 64 * u, T, title, True)
        if not portrait:
            y = H * 0.54
            x1, x2 = W * 0.08, W * 0.92
            a.rect(0, D, x1, y - 3 * u, x2, y + 3 * u, th["line"])
            seg = (x2 - x1) / n
            for i, (d_, lab) in enumerate(pts):
                cx = x1 + seg * (i + 0.5)
                a.circle(0, D, cx, y, 14 * u, A, layer=1)
                fsd = fit_fs(d_, seg * 0.95, 46 * u, 28 * u)
                a.txt(0, D, cx, y - 36 * u, 2, fsd, A, d_, True)
                fsl = 36 * u if n > 4 else 40 * u
                ll = wrap(lab, seg * 0.88, fsl)[:4]
                for j, l in enumerate(ll):
                    a.txt(0, D, cx, y + 40 * u + j * fsl * 1.3, 8, fsl, T, l)
        else:
            x = W * 0.16
            y1, y2 = H * 0.18, H * 0.86
            a.rect(0, D, x - 3 * u, y1, x + 3 * u, y2, th["line"])
            seg = (y2 - y1) / n
            for i, (d_, lab) in enumerate(pts):
                cy = y1 + seg * (i + 0.5)
                a.circle(0, D, x, cy, 14 * u, A, layer=1)
                a.txt(0, D, x + 40 * u, cy - 30 * u, 4, 44 * u, A, d_, True)
                ll = wrap(lab, W * 0.7, 38 * u)[:3]
                for j, l in enumerate(ll):
                    a.txt(0, D, x + 40 * u, cy + 18 * u + j * 48 * u, 4, 38 * u, T, l)
        return

    if typ == "placeholder":
        x1, y1, x2, y2 = W * 0.1, H * 0.2, W * 0.9, H * 0.76
        dash, gap, t = 30 * u, 18 * u, 4 * u
        xx = x1
        while xx < x2:
            e = min(xx + dash, x2)
            a.rect(0, D, xx, y1, e, y1 + t, th["line"])
            a.rect(0, D, xx, y2 - t, e, y2, th["line"])
            xx += dash + gap
        yy = y1
        while yy < y2:
            e = min(yy + dash, y2)
            a.rect(0, D, x1, yy, x1 + t, e, th["line"])
            a.rect(0, D, x2 - t, yy, x2, e, th["line"])
            yy += dash + gap
        a.txt(0, D, W / 2, y1 + 90 * u, 5, 60 * u, A, title or "待补素材", True)
        if sub:
            block(wrap(sub, (x2 - x1) * 0.86, 40 * u)[:6], W / 2, y1 + 170 * u, 8, 40 * u, T)
        return


def split_events(a, card, D, th, with_images):
    W, H, u = a.W, a.H, a.u
    portrait = H > W
    T, S, A = th["text"], th["sub"], th["accent"]
    title = (card.get("title") or "").strip()
    left, right = (card.get("left") or "").strip(), (card.get("right") or "").strip()
    if title:
        a.txt(0, D, W / 2, H * (0.12 if not portrait else 0.08), 5, 58 * u, T, title, True)
    panels = split_panels(W, H)
    for (px1, py1, px2, py2), txt_ in zip(panels, (left, right)):
        head, body = "", txt_
        m = re.match(r"^([^：:]{1,8})[：:](.+)$", txt_)
        if m:
            head, body = m.group(1).strip(), m.group(2).strip()
        cx = (px1 + px2) / 2
        if with_images:
            if txt_:
                lab = (head + "：" + body) if head else body
                fs = fit_fs(lab, (px2 - px1) * 0.95, 44 * u, 28 * u)
                a.txt(0, D, cx, py1 - 26 * u, 2, fs, A, lab, True)
        else:
            a.rect(0, D, px1, py1, px2, py2, th["panel"], alpha=0x30)
            a.rect(0, D, px1, py1, px2, py1 + 8 * u, A)
            if head:
                a.txt(0, D, cx, py1 + 80 * u, 5, 46 * u, A, head, True)
            fs = 72 * u if len(body) <= 8 else 56 * u
            bl = wrap(body, (px2 - px1) * 0.84, fs)[:5]
            n = len(bl)
            cy = (py1 + py2) / 2 + 30 * u
            for i, l in enumerate(bl):
                a.txt(0, D, cx, cy + (i - (n - 1) / 2) * fs * 1.35, 5, fs, T, l, True)


def split_panels(W, H):
    if H > W:
        return [(W * 0.07, H * 0.14, W * 0.93, H * 0.47), (W * 0.07, H * 0.52, W * 0.93, H * 0.85)]
    return [(W * 0.05, H * 0.22, W * 0.49, H * 0.80), (W * 0.51, H * 0.22, W * 0.95, H * 0.80)]


# ---------------------------------------------------------------- 素材

def load_manifest(spec_dir, meta):
    """返回 (assets_dir, {id 或 文件名: entry})"""
    ad = meta.get("assets_dir")
    adir = (spec_dir / ad).resolve() if ad else None
    mf = meta.get("assets_manifest")
    mpath = (spec_dir / mf).resolve() if mf else (adir / "assets.json" if adir else None)
    table = {}
    if mpath and mpath.is_file():
        data = json.loads(mpath.read_text(encoding="utf-8"))
        items = data.get("images", data) if isinstance(data, dict) else data
        base = mpath.parent
        for e in items:
            e = dict(e)
            e["_path"] = (base / e["file"]).resolve()
            for k in {e.get("id"), e.get("file"), Path(e["file"]).stem}:
                if k:
                    table[str(k)] = e
            m = re.match(r"^图(\d+)$", str(e.get("id", "")))
            if m:
                table["原稿图" + m.group(1)] = e
        if not adir:
            adir = base
    return adir, table


def resolve_image(ref, spec_dir, adir, table):
    """ref 可以是 '图3' / 'img03' / 文件路径。返回 (path, redact 列表) 或 (None, [])"""
    r = str(ref).strip()
    if r in table:
        e = table[r]
        return e["_path"], e.get("redact") or []
    m = re.match(r"^(?:原稿)?图\s*(\d+)$", r)
    if m and ("图%s" % int(m.group(1))) in table:
        e = table["图%s" % int(m.group(1))]
        return e["_path"], e.get("redact") or []
    if m and adir:  # 没有 assets.json 时：图N → imgNN.*（extract_docx.py 的命名）
        n = int(m.group(1))
        for stem in ("img%02d" % n, "img%d" % n):
            for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
                p = adir / (stem + ext)
                if p.is_file():
                    return p.resolve(), []
    for base in [p for p in (spec_dir, adir) if p]:
        p = (base / r)
        if p.is_file():
            return p.resolve(), []
    p = Path(r)
    if p.is_file():
        return p.resolve(), []
    return None, []


# ---------------------------------------------------------------- 画面合成

def even(x):
    x = int(round(x))
    return x - (x % 2)


def fg_geometry(iw, ih, maxw, maxh, cap=3.0):
    s = min(maxw / iw, maxh / ih, cap)
    return max(2, even(iw * s)), max(2, even(ih * s))


def redact_chain(label, boxes, iw, ih, prefix):
    """在原图分辨率上模糊若干区域。返回 (filter 片段列表, 输出标签)"""
    parts, cur = [], label
    for i, b in enumerate(boxes):
        x, y, w, h = [float(v) for v in b[:4]]
        px, py = int(x * iw), int(y * ih)
        pw, ph = max(4, int(w * iw)), max(4, int(h * ih))
        pw, ph = min(pw, iw - px), min(ph, ih - py)
        sw, sh = max(1, pw // 10), max(1, ph // 10)
        a, c, bl, nx = "%sm%d" % (prefix, i), "%sc%d" % (prefix, i), "%sb%d" % (prefix, i), "%sr%d" % (prefix, i)
        parts.append("[%s]split=2[%s][%s]" % (cur, a, c))
        parts.append("[%s]crop=%d:%d:%d:%d,scale=%d:%d:flags=area,scale=%d:%d:flags=bilinear,gblur=sigma=%.1f[%s]"
                     % (c, pw, ph, px, py, sw, sh, pw, ph, max(2.0, min(pw, ph) / 6), bl))
        parts.append("[%s][%s]overlay=%d:%d[%s]" % (a, bl, px, py, nx))
        cur = nx
    return parts, cur


def highlight_chain(boxes, fw, fh, color, thick):
    out = []
    for b in boxes or []:
        x, y, w, h = [float(v) for v in b[:4]]
        out.append("drawbox=x=%d:y=%d:w=%d:h=%d:color=0x%s@0.95:t=%d" % (
            int(x * fw), int(y * fh), max(4, int(w * fw)), max(4, int(h * fh)), color, thick))
    return out


def bg_cover_chain(src, out, W, H, brightness):
    return ("[%s]scale=%d:%d:force_original_aspect_ratio=increase:flags=area,crop=%d:%d,gblur=sigma=6,"
            "scale=%d:%d:flags=bicubic,eq=brightness=%.2f:saturation=0.65[%s]"
            % (src, max(16, W // 8), max(16, H // 8), max(16, W // 8), max(16, H // 8), W, H, brightness, out))


def card_bg(ctx):
    th, W, H = ctx["theme"], ctx["W"], ctx["H"]
    p = ctx["work"] / "cache" / ("cardbg_%s_%dx%d.png" % (ctx["theme_name"], W, H))
    if not p.exists():
        run([ctx["ff"], "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             "color=c=0x%s:s=%dx%d" % (th["bg"], W, H), "-vf", "vignette=angle=%s,format=rgb24" % th["vignette"],
             "-frames:v", "1", p])
    return p


def compose_fit_still(ctx, img, redacts, highlights, out_png, k):
    """图片等比适配画幅，空白处用同图模糊铺底；输出 k 倍分辨率静帧（供 zoompan）。"""
    W, H = ctx["W"] * k, ctx["H"] * k
    _, size = probe(ctx["ff"], img)
    if not size:
        raise RuntimeError("读不出图片尺寸：%s" % img)
    iw, ih = size
    portrait = ctx["H"] > ctx["W"]
    maxw, maxh = (W * 0.88, H * 0.76) if not portrait else (W * 0.92, H * 0.58)
    fw, fh = fg_geometry(iw, ih, maxw, maxh)
    bord = max(2, int(3 * k * ctx["u"]))
    ox = (W - fw) // 2 - bord
    oy = int((H - fh) / 2 - H * (0.045 if not portrait else 0.08)) - bord
    parts, cur = redact_chain("0:v", redacts, iw, ih, "r")
    inputs = ["-i", img]
    if max(iw / ih, ih / iw) > 3.2:  # 细长条截图：模糊铺底会出现巨大的糊字，改用主题底色
        inputs += ["-i", card_bg(ctx)]
        parts.append("[%s]format=rgba[fa]" % cur)
        parts.append("[1:v]scale=%d:%d[bg]" % (W, H))
    else:
        parts.append("[%s]format=rgba,split=2[fa][fb]" % cur)
        parts.append(bg_cover_chain("fb", "bg", W, H, ctx["theme"]["img_brightness"]))
    fgf = ["scale=%d:%d:flags=lanczos" % (fw, fh)] + highlight_chain(highlights, fw, fh, ctx["theme"]["accent"], max(3, int(5 * k * ctx["u"])))
    fgf.append("pad=%d:%d:%d:%d:color=0x000000@0.6" % (fw + 2 * bord, fh + 2 * bord, bord, bord))
    parts.append("[fa]" + ",".join(fgf) + "[fg]")
    parts.append("[bg][fg]overlay=%d:%d,format=rgb24[out]" % (ox, oy))
    run([ctx["ff"], "-y", "-hide_banner", "-loglevel", "error"] + inputs + ["-filter_complex", ";".join(parts),
         "-map", "[out]", "-frames:v", "1", out_png])


def compose_scroll_stills(ctx, img, redacts, highlights, bg_png, fg_png):
    """长图滚动：输出静态背景 + 竖长前景，返回 (前景宽, 前景高, 视窗高, x, y)。"""
    W, H = ctx["W"], ctx["H"]
    _, (iw, ih) = probe(ctx["ff"], img)
    portrait = H > W
    fw = even(min(W * (0.62 if not portrait else 0.9), iw * 3))
    fh = even(fw * ih / iw)
    vh = even(min(fh, H * (0.84 if not portrait else 0.74)))
    parts, cur = redact_chain("0:v", redacts, iw, ih, "r")
    parts.append("[%s]format=rgba,split=2[fa][fb]" % cur)
    parts.append(bg_cover_chain("fb", "bg", W, H, ctx["theme"]["img_brightness"]))
    fgf = ["scale=%d:%d:flags=lanczos" % (fw, fh)] + highlight_chain(highlights, fw, fh, ctx["theme"]["accent"], max(3, int(5 * ctx["u"])))
    parts.append("[fa]" + ",".join(fgf) + ",format=rgb24[fg]")
    run([ctx["ff"], "-y", "-hide_banner", "-loglevel", "error", "-i", img, "-filter_complex", ";".join(parts),
         "-map", "[bg]", "-frames:v", "1", bg_png, "-map", "[fg]", "-frames:v", "1", fg_png])
    x = (W - fw) // 2
    y = int((H - vh) / 2 - H * (0.03 if not portrait else 0.06))
    return fw, fh, vh, x, y


def compose_split_still(ctx, imgs, out_png, k):
    W, H = ctx["W"] * k, ctx["H"] * k
    bg = card_bg(ctx)
    inputs = ["-i", bg]
    parts = ["[0:v]scale=%d:%d[c0]" % (W, H)]
    cur = "c0"
    for i, ((img, red), (px1, py1, px2, py2)) in enumerate(zip(imgs[:2], split_panels(W, H))):
        _, (iw, ih) = probe(ctx["ff"], img)
        inputs += ["-i", img]
        pr, rc = redact_chain("%d:v" % (i + 1), red, iw, ih, "s%d" % i)
        parts += pr
        fw, fh = fg_geometry(iw, ih, (px2 - px1), (py2 - py1) * 0.92)
        parts.append("[%s]scale=%d:%d:flags=lanczos,pad=%d:%d:3:3:color=0x000000@0.6[f%d]" % (rc, fw, fh, fw + 6, fh + 6, i))
        x = int((px1 + px2) / 2 - fw / 2)
        y = int((py1 + py2) / 2 - fh / 2)
        parts.append("[%s][f%d]overlay=%d:%d[c%d]" % (cur, i, x, y, i + 1))
        cur = "c%d" % (i + 1)
    parts.append("[%s]format=rgb24[out]" % cur)
    run([ctx["ff"], "-y", "-hide_banner", "-loglevel", "error"] + inputs +
        ["-filter_complex", ";".join(parts), "-map", "[out]", "-frames:v", "1", out_png])


def zoompan_expr(motion, frames, amount):
    n1 = max(1, frames - 1)
    p = "(on/%d)" % n1
    c_x, c_y = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    z1 = 1 + amount
    if motion == "push":
        return "1+%.4f*%s" % (amount, p), c_x, c_y
    if motion == "pull":
        return "%.4f-%.4f*%s" % (z1, amount, p), c_x, c_y
    if motion == "right":
        return "%.4f" % z1, "(iw-iw/zoom)*%s" % p, c_y
    if motion == "left":
        return "%.4f" % z1, "(iw-iw/zoom)*(1-%s)" % p, c_y
    if motion == "down":
        return "%.4f" % z1, c_x, "(ih-ih/zoom)*%s" % p
    if motion == "up":
        return "%.4f" % z1, c_x, "(ih-ih/zoom)*(1-%s)" % p
    return "1", "0", "0"


# ---------------------------------------------------------------- 单镜渲染

def file_sig(p):
    try:
        st = Path(p).stat()
        return [str(p), st.st_size, int(st.st_mtime)]
    except OSError:
        return [str(p), None]


def choose_vcodec(caps):
    if caps["libx264"]:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    if caps["libopenh264"]:
        return ["-c:v", "libopenh264", "-b:v", "6M", "-pix_fmt", "yuv420p"]
    if caps["h264_videotoolbox"]:
        return ["-c:v", "h264_videotoolbox", "-b:v", "8M", "-pix_fmt", "yuv420p"]
    return ["-c:v", "mpeg4", "-q:v", "3", "-pix_fmt", "yuv420p"]


def plan_shot(ctx, idx, shot):
    """确定类型、素材、配音和最终时长（不渲染画面）。"""
    sd, adir, table = ctx["spec_dir"], ctx["adir"], ctx["table"]
    typ = (shot.get("type") or "image").strip()
    if typ not in ALL_TYPES:
        warn("镜头 %s 类型 %s 未知，按 placeholder 处理" % (shot.get("id"), typ))
        typ = "placeholder"
    imgs, missing = [], []
    for ref in shot.get("images") or []:
        p, red = resolve_image(ref, sd, adir, table)
        if p:
            imgs.append((p, red))
        else:
            missing.append(str(ref))
    media = None
    if shot.get("media"):
        mp = Path(shot["media"])
        mp = mp if mp.is_absolute() else (sd / mp)
        if mp.is_file():
            media = mp.resolve()
        else:
            missing.append(str(shot["media"]))
    if media and media.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
        imgs.insert(0, (media, []))
        media = None
        if typ in ("placeholder", "media"):
            typ = "image"
    if media and typ in ("placeholder", "image", "media"):
        typ = "media"
    if typ in ("image",) and not imgs:
        typ = "placeholder"
    if typ == "media" and not media:
        typ = "placeholder"
    card = dict(shot.get("card") or {})
    if typ == "placeholder":
        card.setdefault("title", "待补素材")
        desc = card.get("sub") or shot.get("note") or shot.get("content") or ""
        if missing:
            desc = ("缺少素材：%s。" % "、".join(missing)) + desc
        card["sub"] = desc
    if typ in CARD_TYPES - {"placeholder"} and not card.get("title") and not card.get("items"):
        card["title"] = shot.get("caption") or ""
    narr = (shot.get("narration") or "").strip()
    audio, ndur = None, 0.0
    if shot.get("audio"):
        ap = Path(shot["audio"])
        ap = ap if ap.is_absolute() else sd / ap
        if ap.is_file():
            audio = ap.resolve()
            ndur = probe(ctx["ff"], audio)[0] or 0.0
        else:
            warn("镜头 %s 的 audio 文件不存在：%s" % (shot.get("id"), shot["audio"]))
    elif narr and ctx["tts"] != "none" and not ctx.get("dry"):
        audio, ndur = tts(ctx, narr)
    est = spoken_units(narr) / ctx["speed"] if narr else 0.0
    base = float(shot.get("duration") or 0)
    lead = 0.15
    if audio and base and ctx.get("max_tempo", 1.0) > 1.0:
        audio, ndur = fit_tempo(ctx, audio, ndur, base - lead - 0.4)
    D = max(base, (ndur + lead + 0.4) if ndur else 0, (est + 0.5) if (not ndur and narr) else 0, 1.0)
    fps = ctx["fps"]
    frames = int(round(D * fps))
    D = frames / fps
    sub_dur = ndur if ndur else min(est, D - lead - 0.2)
    motion = (shot.get("motion") or "").strip() or None
    if motion and motion not in MOTIONS:
        warn("镜头 %s 运镜 %s 未知，改为 push" % (shot.get("id"), motion))
        motion = "push"
    return {
        "idx": idx, "id": str(shot.get("id") or idx + 1), "type": typ, "imgs": imgs, "media": media,
        "card": card, "caption": (shot.get("caption") or "").strip(), "narr": narr, "audio": audio,
        "ndur": ndur, "sub_dur": max(0.0, sub_dur), "lead": lead, "D": D, "frames": frames,
        "motion": motion, "highlight": shot.get("highlight") or [], "missing": missing,
        "base": base, "raw": shot,
    }


def render_shot(ctx, P, first, last):
    ff, W, H, fps, th = ctx["ff"], ctx["W"], ctx["H"], ctx["fps"], ctx["theme"]
    work = ctx["work"]
    key_obj = {
        "v": VERSION, "shot": P["raw"], "type": P["type"], "D": P["D"], "W": W, "H": H, "fps": fps,
        "theme": ctx["theme_name"], "font": str(ctx["font"]), "fam": ctx["fam"], "subs": ctx["subs"],
        "imgs": [file_sig(p) + [r] for p, r in P["imgs"]], "media": file_sig(P["media"]) if P["media"] else None,
        "audio": file_sig(P["audio"]) if P["audio"] else None, "first": first, "last": last,
        "zoom": ctx["zoom"], "k": ctx["k"], "card": P["card"],
    }
    key = hashlib.sha1(json.dumps(key_obj, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:12]
    safe = "%03d" % (P["idx"] + 1)
    clip = work / "clips" / ("%s_%s.mkv" % (safe, key))
    if clip.exists():
        return clip
    for old in (work / "clips").glob(safe + "_*.mkv"):
        old.unlink()
    stills = work / "cache" / "stills"
    stills.mkdir(parents=True, exist_ok=True)
    D, frames = P["D"], P["frames"]

    # ---- ASS
    a = Ass(W, H, ctx["fam"], th)
    typ = P["type"]
    if typ in CARD_TYPES:
        card_events(a, typ, P["card"], D, th)
    elif typ == "split":
        split_events(a, P["card"], D, th, with_images=len(P["imgs"]) >= 2)
    if typ in ("image", "media") or (typ == "split" and P["caption"] and P["card"].get("title") != P["caption"]):
        add_caption(a, P["caption"], D, th)
    if ctx["subs"]:
        add_subtitles(a, P["narr"], P["lead"], P["sub_dur"], D)
    ass_rel = "ass/%s.ass" % safe
    (work / "ass").mkdir(exist_ok=True)
    (work / ass_rel).write_text(a.text(), encoding="utf-8")

    # ---- 画面
    inputs, parts, vlabels = [], [], []
    nin = 0
    if typ == "image":
        n = len(P["imgs"])
        seg_frames = [frames // n + (1 if i < frames % n else 0) for i in range(n)]
        for i, ((img, red), fr) in enumerate(zip(P["imgs"], seg_frames)):
            hl = P["highlight"]
            if isinstance(hl, dict):
                hl = hl.get(str(P["raw"].get("images", [])[i]) if i < len(P["raw"].get("images", [])) else "", [])
            elif i > 0:
                hl = []
            _, size = probe(ff, img)
            iw, ih = size or (1, 1)
            motion = P["motion"]
            tall = (ih / iw > 1.5) and H <= W * 1.2
            if motion is None:
                motion = "down" if tall else "push"
            sk = hashlib.sha1(json.dumps([file_sig(img), red, hl, W, H, ctx["theme_name"], ctx["k"], VERSION], default=str).encode()).hexdigest()[:12]
            use_scroll = motion in ("down", "up") and tall
            if use_scroll:
                bgp, fgp = stills / ("%s_bg.png" % sk), stills / ("%s_fg.png" % sk)
                geo_p = stills / ("%s_geo.json" % sk)
                if not (bgp.exists() and fgp.exists() and geo_p.exists()):
                    geo = compose_scroll_stills(ctx, img, red, hl, bgp, fgp)
                    geo_p.write_text(json.dumps(geo))
                fw, fh, vh, x, y = json.loads(geo_p.read_text())
                dseg = fr / fps
                inputs += ["-loop", "1", "-framerate", str(fps), "-t", "%.3f" % dseg, "-i", bgp,
                           "-loop", "1", "-framerate", str(fps), "-t", "%.3f" % dseg, "-i", fgp]
                q = "min(1,max(0,(t-0.5)/%.3f))" % max(0.1, dseg - 1.0)
                pe = "(0.5-0.5*cos(PI*%s))" % q
                if motion == "up":
                    pe = "(1-%s)" % pe
                parts.append("[%d:v]crop=%d:%d:0:'(ih-oh)*%s'[w%d]" % (nin + 1, fw, vh, pe, i))
                parts.append("[%d:v][w%d]overlay=%d:%d,setsar=1,format=yuv420p[v%d]" % (nin, i, x, y, i))
                nin += 2
            else:
                if motion in ("down", "up") and not tall:
                    pass  # 普通图的上下移动用 zoompan 平移
                sp = stills / ("%s_fit.png" % sk)
                if not sp.exists():
                    compose_fit_still(ctx, img, red, hl, sp, ctx["k"])
                z, x, y = zoompan_expr(motion, fr, ctx["zoom"])
                inputs += ["-i", sp]
                parts.append("[%d:v]zoompan=z='%s':x='%s':y='%s':d=%d:s=%dx%d:fps=%d,setsar=1,format=yuv420p[v%d]"
                             % (nin, z, x, y, fr, W, H, fps, i))
                nin += 1
            vlabels.append("v%d" % i)
    elif typ == "split" and len(P["imgs"]) >= 2:
        sk = hashlib.sha1(json.dumps([[file_sig(p), r] for p, r in P["imgs"][:2]] + [W, H, ctx["theme_name"], ctx["k"], VERSION], default=str).encode()).hexdigest()[:12]
        sp = stills / ("%s_split.png" % sk)
        if not sp.exists():
            compose_split_still(ctx, P["imgs"], sp, ctx["k"])
        z, x, y = zoompan_expr(P["motion"] or "static", frames, ctx["zoom"] * 0.4)
        inputs += ["-i", sp]
        parts.append("[0:v]zoompan=z='%s':x='%s':y='%s':d=%d:s=%dx%d:fps=%d,setsar=1,format=yuv420p[v0]" % (z, x, y, frames, W, H, fps))
        vlabels.append("v0")
        nin = 1
    elif typ == "media":
        inputs += ["-stream_loop", "-1", "-t", "%.3f" % D, "-i", P["media"]]
        parts.append("[0:v]scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=0x%s,fps=%d,setsar=1,format=yuv420p[v0]"
                     % (W, H, W, H, th["bg"], fps))
        vlabels.append("v0")
        nin = 1
    else:  # 卡片、文字分屏、占位
        bg = card_bg(ctx)
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", "%.3f" % D, "-i", bg]
        parts.append("[0:v]setsar=1,format=yuv420p[v0]")
        vlabels.append("v0")
        nin = 1
    if len(vlabels) > 1:
        parts.append("".join("[%s]" % l for l in vlabels) + "concat=n=%d:v=1:a=0[vc]" % len(vlabels))
        vc = "vc"
    else:
        vc = vlabels[0]
    post = ["subtitles=%s:fontsdir=fonts" % ass_rel]
    if first:
        post.append("fade=t=in:st=0:d=0.5")
    if last:
        post.append("fade=t=out:st=%.3f:d=0.6" % max(0, D - 0.6))
    parts.append("[%s]%s,trim=end_frame=%d,setpts=PTS-STARTPTS[vout]" % (vc, ",".join(post), frames))

    # ---- 声音
    if P["audio"]:
        inputs += ["-i", P["audio"]]
        parts.append("[%d:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo,adelay=%d|%d,apad,atrim=0:%.3f[aout]"
                     % (nin, int(P["lead"] * 1000), int(P["lead"] * 1000), D))
    else:
        inputs += ["-f", "lavfi", "-t", "%.3f" % D, "-i", "anullsrc=r=48000:cl=stereo"]
        parts.append("[%d:a]atrim=0:%.3f[aout]" % (nin, D))
    (work / "clips").mkdir(exist_ok=True)
    tmp = clip.with_suffix(".tmp.mkv")
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"] + inputs + [
        "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
        "-r", str(fps)] + ctx["vcodec"] + ["-c:a", "pcm_s16le", "-t", "%.3f" % D, tmp]
    run(cmd, cwd=work)
    tmp.replace(clip)
    return clip


# ---------------------------------------------------------------- 拼接与混音

def concat_and_mix(ctx, clips, total, out):
    work, ff = ctx["work"], ctx["ff"]
    lst = work / "concat.txt"
    lst.write_text("".join("file '%s'\n" % c.relative_to(work).as_posix() for c in clips), encoding="utf-8")
    joined = work / "joined.mkv"
    run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt",
         "-c", "copy", joined.name], cwd=work)
    bgm = ctx["bgm"]
    out.parent.mkdir(parents=True, exist_ok=True)
    acodec = (["-c:a", "aac", "-b:a", "192k"] if ctx["caps"]["aac"] else ["-c:a", "libmp3lame", "-b:a", "192k"]) + ["-ar", "48000"]
    if bgm:
        vol = ctx["bgm_volume"]
        fo = max(0, total - 3)
        if ctx["caps"]["sidechaincompress"]:
            fc = ("[0:a]asplit=2[n1][n2];"
                  "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=%.3f,afade=t=in:d=2,afade=t=out:st=%.2f:d=3,atrim=0:%.3f[b];"
                  "[b][n1]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=500[bd];"
                  "[n2][bd]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]" % (vol, fo, total))
        else:
            fc = ("[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=%.3f,afade=t=in:d=2,afade=t=out:st=%.2f:d=3,atrim=0:%.3f[b];"
                  "[0:a][b]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]" % (vol * 0.6, fo, total))
        run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", joined, "-stream_loop", "-1", "-i", bgm,
             "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy"] + acodec +
            ["-movflags", "+faststart", "-t", "%.3f" % total, out])
    else:
        af = "loudnorm=I=-16:TP=-1.5:LRA=11" if ctx["has_voice"] else "anull"
        run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", joined, "-map", "0:v", "-map", "0:a",
             "-c:v", "copy", "-af", af] + acodec + ["-movflags", "+faststart", out])
    return out


def make_sheet(ctx, plans, clips, out_png):
    ff, work = ctx["ff"], ctx["work"]
    th_dir = work / "sheet"
    if th_dir.exists():
        shutil.rmtree(th_dir)
    th_dir.mkdir()
    portrait = ctx["H"] > ctx["W"]
    tw, tht = (480, 270) if not portrait else (270, 480)
    for i, (P, c) in enumerate(zip(plans, clips)):
        label = th_dir / ("%04d.txt" % i)
        label.write_text("%s  %s  %.1fs" % (P["id"], P["type"], P["D"]), encoding="utf-8")
        run([ff, "-y", "-hide_banner", "-loglevel", "error", "-ss", "%.2f" % (P["D"] * 0.55), "-i", c,
             "-frames:v", "1", "-vf",
             "scale=%d:%d,drawbox=x=0:y=0:w=iw:h=26:color=black@0.7:t=fill,drawtext=fontfile=fonts/%s:textfile=sheet/%04d.txt:fontsize=18:fontcolor=white:x=6:y=4"
             % (tw, tht, ctx["font_local"], i),
             "sheet/%04d.png" % i], cwd=work)
    cols = 5 if not portrait else 8
    rows = math.ceil(len(clips) / cols)
    run([ff, "-y", "-hide_banner", "-loglevel", "error", "-framerate", "1", "-i", "sheet/%04d.png",
         "-vf", "tile=%dx%d:padding=6:margin=6:color=0x202020" % (cols, rows), "-frames:v", "1", str(out_png.resolve())], cwd=work)
    return out_png


# ---------------------------------------------------------------- 主流程

def parse_size(s):
    s = str(s).lower()
    if s in ("vertical", "portrait", "9:16", "竖屏"):
        return 1080, 1920
    if s in ("horizontal", "landscape", "16:9", "横屏"):
        return 1920, 1080
    if s in ("square", "1:1"):
        return 1080, 1080
    m = re.match(r"^(\d+)x(\d+)$", s)
    if not m:
        die("--size 格式应为 1920x1080 / vertical")
    return int(m.group(1)), int(m.group(2))


def fmt_t(sec):
    m, s = divmod(int(round(sec)), 60)
    return "%d:%02d" % (m, s)


def main():
    ap = argparse.ArgumentParser(description="分镜渲染 JSON → mp4（ffmpeg + libass）")
    ap.add_argument("spec", nargs="?", help="渲染 JSON（由 md2render.py 生成或手写）")
    ap.add_argument("-o", "--out", help="输出 mp4，默认与 JSON 同名")
    ap.add_argument("--work", help="工作/缓存目录，默认 <JSON 名>_build/")
    ap.add_argument("--tts", choices=["auto", "say", "sapi", "espeak", "edge", "none"])
    ap.add_argument("--voice", help="配音语音名（say/SAPI/espeak/edge 各自的名字）")
    ap.add_argument("--rate", type=float, help="语速：say/espeak 为每分钟词数，SAPI 为 -10..10，edge 为百分比")
    ap.add_argument("--speed", type=float, help="无配音时估算字幕时长用的语速（字/秒），默认 4.5")
    ap.add_argument("--bgm", help="背景音乐文件")
    ap.add_argument("--bgm-volume", type=float)
    ap.add_argument("--font", help="中文字体文件（ttf/otf/ttc）")
    ap.add_argument("--theme", choices=sorted(THEMES))
    ap.add_argument("--size", help="1920x1080 / 1080x1920 / vertical / square")
    ap.add_argument("--fps", type=int)
    ap.add_argument("--only", help="只渲染这些镜号（逗号分隔），输出 <名>_preview.mp4")
    ap.add_argument("--sheet", action="store_true", help="输出每镜中间帧拼图 <名>_sheet.png")
    ap.add_argument("--no-subs", action="store_true", help="不烧录旁白字幕")
    ap.add_argument("--max-tempo", type=float,
                    help="配音超出镜头时长时最多加速到几倍去贴合分镜（保持音调），默认 1.35；设为 1 则只延长镜头")
    ap.add_argument("--dry-run", action="store_true", help="只检查素材和时长，不渲染")
    ap.add_argument("--list-voices", action="store_true", help="列出本机可用的中文配音并退出")
    ap.add_argument("--quality", type=int, choices=[1, 2, 3], default=2, help="运镜防抖倍数，越大越平滑越慢（默认 2）")
    args = ap.parse_args()

    if args.list_voices:
        vs = list_say_voices()
        if vs:
            print("macOS say 中文语音：")
            for n, l in vs:
                if l.lower().startswith("zh"):
                    print("  %-28s %s" % (n, l))
            print("自动选择：", pick_say_voice())
        elif IS_WIN:
            print("Windows 用 SAPI：设置 → 时间和语言 → 语音 中添加中文语音；--voice 填语音全名，如 'Microsoft Huihui Desktop'")
        else:
            print("Linux 用 espeak-ng（--voice cmn），或 --tts edge（需 pip install edge-tts，联网）")
        return
    if not args.spec:
        ap.error("需要渲染 JSON 文件")

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    meta = dict(spec.get("meta") or {})
    shots = spec.get("shots") or []
    if not shots:
        die("JSON 中没有 shots")
    sd = spec_path.parent

    W, H = parse_size(args.size) if args.size else (int(meta.get("width", 1920)), int(meta.get("height", 1080)))
    theme_name = args.theme or meta.get("theme") or "dark"
    if theme_name not in THEMES:
        warn("主题 %s 不存在，改用 dark" % theme_name)
        theme_name = "dark"
    ff = find_ffmpeg()
    caps = ffmpeg_caps(ff)
    if not caps["subtitles"]:
        die("当前 ffmpeg（%s）没有 libass（缺 subtitles 过滤器），无法渲染文字。\n%s" % (ff, INSTALL_HINT))
    if not caps["zoompan"]:
        die("当前 ffmpeg 缺 zoompan 过滤器，请换完整版 ffmpeg。\n" + INSTALL_HINT)
    font, fam = find_font(args.font or meta.get("font"))
    work = Path(args.work).resolve() if args.work else sd / (spec_path.stem + "_build")
    work.mkdir(parents=True, exist_ok=True)
    # 字体放进工作目录 fonts/，用简单文件名，ffmpeg 以 cwd=工作目录 + 相对路径引用（Windows 路径转义安全）
    fdir = work / "fonts"
    fdir.mkdir(exist_ok=True)
    sheet_font = "main" + font.suffix.lower()
    lf = fdir / sheet_font
    marker = work / "font_source.txt"
    if not lf.exists() or not marker.exists() or marker.read_text(encoding="utf-8") != str(font):
        for old in fdir.iterdir():
            old.unlink()
        try:
            if IS_WIN:
                raise OSError
            lf.symlink_to(font)
        except OSError:
            shutil.copy2(font, lf)
        marker.write_text(str(font), encoding="utf-8")

    tts_engine = resolve_tts_engine(args.tts or meta.get("tts") or "auto")
    voice = args.voice or meta.get("voice")
    if tts_engine == "say":
        voice = pick_say_voice(voice)
        if not voice:
            warn("say 没有中文语音，改为无配音")
            tts_engine = "none"
    adir, table = load_manifest(sd, meta)
    bgm = args.bgm or meta.get("bgm")
    if bgm:
        bp = Path(bgm)
        bp = bp if bp.is_absolute() else sd / bp
        if not bp.is_file():
            warn("背景音乐不存在：%s，忽略" % bgm)
            bgm = None
        else:
            bgm = bp.resolve()
    ctx = {
        "ff": ff, "caps": caps, "W": W, "H": H, "u": min(W, H) / 1080.0, "fps": int(args.fps or meta.get("fps", 30)),
        "theme_name": theme_name, "theme": THEMES[theme_name], "font": font, "fam": fam,
        "font_local": sheet_font, "work": work, "spec_dir": sd, "adir": adir, "table": table,
        "tts": tts_engine, "voice": voice, "rate": args.rate if args.rate is not None else meta.get("rate"),
        "speed": float(args.speed or meta.get("speed", 4.5)), "subs": not (args.no_subs or meta.get("subtitles") is False),
        "max_tempo": float(args.max_tempo if args.max_tempo is not None else meta.get("max_tempo", 1.35)),
        "bgm": bgm, "bgm_volume": float(args.bgm_volume if args.bgm_volume is not None else meta.get("bgm_volume", 0.18)),
        "zoom": float(meta.get("zoom", 0.08)), "k": args.quality, "vcodec": choose_vcodec(caps),
        "dry": args.dry_run, "has_voice": False,
    }
    print("ffmpeg：%s\n字体：%s（%s）\n配音：%s %s\n画幅：%dx%d @%dfps  主题：%s"
          % (ff, font, fam, tts_engine, voice or "", W, H, ctx["fps"], theme_name))

    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    sel = [(i, s) for i, s in enumerate(shots) if not only or str(s.get("id")) in only]
    if only and not sel:
        die("--only 没有匹配到任何镜号")
    plans = []
    for i, s in sel:
        P = plan_shot(ctx, i, s)
        plans.append(P)
        if P["ndur"]:
            ctx["has_voice"] = True
    total = sum(P["D"] for P in plans)
    n_ph = sum(1 for P in plans if P["type"] == "placeholder")
    for P in plans:
        flag = ""
        if P["base"] and P["D"] > P["base"] + 0.5:
            flag = "  ← 配音比分镜时长长，已延长"
        if P["missing"]:
            flag += "  ← 缺素材：" + "、".join(P["missing"])
        print("  %-8s %-11s %5.1fs%s" % (P["id"], P["type"], P["D"], flag))
    print("共 %d 镜，总时长 %s（%.1f 秒），占位镜头 %d 个" % (len(plans), fmt_t(total), total, n_ph))
    if args.dry_run:
        return

    clips = []
    for j, P in enumerate(plans):
        first = (j == 0) and not only
        last = (j == len(plans) - 1) and not only
        sys.stdout.write("\r渲染 %d/%d  %s        " % (j + 1, len(plans), P["id"]))
        sys.stdout.flush()
        clips.append(render_shot(ctx, P, first, last))
    print()
    stem = spec_path.stem
    out = Path(args.out).resolve() if args.out else sd / (stem + ("_preview.mp4" if only else ".mp4"))
    if only and args.out:
        out = out.with_name(out.stem + "_preview.mp4")
    concat_and_mix(ctx, clips, total, out)
    dur, _ = probe(ff, out)
    print("成片：%s  时长 %s（%.1f 秒）" % (out, fmt_t(dur or total), dur or total))
    if args.sheet:
        sp = out.with_name(out.stem + "_sheet.png")
        make_sheet(ctx, plans, clips, sp)
        print("拼图：%s" % sp)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        die(str(e), 1)
    except KeyboardInterrupt:
        die("已中断", 130)
