#!/usr/bin/env python3
"""v2 动效场景的绘图基础库（Pillow）。只负责画，不管时间线编排。"""
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
U = min(W, H) / 1080.0

# 与技能 dark 主题一致的配色
BG = (0x10, 0x13, 0x1A)
PANEL = (0x1C, 0x23, 0x30)
PANEL2 = (0x16, 0x1C, 0x26)
TEXT = (0xFF, 0xFF, 0xFF)
SUB = (0xC9, 0xD1, 0xDC)
DIM = (0x8A, 0x96, 0xAB)
ACC = (0xE5, 0x43, 0x2D)
ACC2 = (0xFF, 0xD3, 0x8A)
LINE = (0x5A, 0x64, 0x78)
GREEN = (0x3D, 0xDC, 0x97)
BLUE = (0x58, 0xA6, 0xFF)

FONT_DIR = r"C:\Windows\Fonts"
FONT_FILES = {
    "bold": os.path.join(FONT_DIR, "msyhbd.ttc"),
    "regular": os.path.join(FONT_DIR, "msyh.ttc"),
    "light": os.path.join(FONT_DIR, "msyhl.ttc"),
}
_fonts = {}


def font(size, weight="bold"):
    key = (size, weight)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_FILES[weight], int(size))
    return _fonts[key]


# ---------------------------------------------------------------- 数学

def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def lerp(a, b, t):
    return a + (b - a) * t


def seg(t, t0, t1):
    """把绝对时间映射到 0..1 的进度。"""
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return clamp((t - t0) / (t1 - t0))


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return 3 * t * t - 2 * t * t * t


def ease_out_back(t, k=1.7):
    t = clamp(t)
    return 1 + (k + 1) * (t - 1) ** 3 + k * (t - 1) ** 2


def ease_out_quint(t):
    return 1 - (1 - t) ** 5


def rgba(c, a=255):
    if len(c) == 4:
        return c
    return (c[0], c[1], c[2], int(clamp(a, 0, 255)))


def mix(c1, c2, t):
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


# ---------------------------------------------------------------- 图层工具

def new_layer(size=(W, H)):
    return Image.new("RGBA", size, (0, 0, 0, 0))


def blur(img, r):
    return img.filter(ImageFilter.GaussianBlur(r))


def glow(shape_img, radius=24, gain=1.0, passes=2):
    """把一张形状图层变成发光层。"""
    out = Image.new("RGBA", shape_img.size, (0, 0, 0, 0))
    for i in range(passes):
        g = shape_img.filter(ImageFilter.GaussianBlur(radius * (1 + i * 1.6)))
        out = ImageChops.add(out, g)
    if gain != 1.0:
        r, gg, b, a = out.split()
        r = r.point(lambda v: min(255, int(v * gain)))
        gg = gg.point(lambda v: min(255, int(v * gain)))
        b = b.point(lambda v: min(255, int(v * gain)))
        out = Image.merge("RGBA", (r, gg, b, a))
    return out


_bg_cache = {}
_noise_cache = {}


def backdrop(seed=0, grid=True, warm=0.0):
    """深色底：径向渐变 + 极细网格 + 颗粒。同参数缓存。"""
    key = (seed, grid, round(warm, 2))
    if key in _bg_cache:
        return _bg_cache[key].copy()
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * (0.5 + 0.05 * ((seed % 3) - 1)), H * 0.46
    d = np.sqrt(((xx - cx) / (W * 0.75)) ** 2 + ((yy - cy) / (H * 0.75)) ** 2)
    v = np.clip(1.25 - d * 1.15, 0, 1) ** 1.6
    base = np.array(BG, dtype=np.float32)
    top = np.array(mix(BG, (0x24, 0x2C, 0x3C), 1.0), dtype=np.float32)
    if warm:
        top = np.array(mix((0x24, 0x2C, 0x3C), (0x3A, 0x22, 0x1C), warm), dtype=np.float32)
    arr = base[None, None, :] + (top - base)[None, None, :] * v[:, :, None]
    rng = np.random.default_rng(1234 + seed)
    grain = rng.normal(0, 2.1, (H, W, 1)).astype(np.float32)
    arr = np.clip(arr + grain, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB").convert("RGBA")
    if grid:
        g = new_layer()
        d2 = ImageDraw.Draw(g)
        step = 96
        for x in range(0, W, step):
            d2.line([(x, 0), (x, H)], fill=(255, 255, 255, 8), width=1)
        for y in range(0, H, step):
            d2.line([(0, y), (W, y)], fill=(255, 255, 255, 8), width=1)
        img = Image.alpha_composite(img, g)
    _bg_cache[key] = img
    return img.copy()


def noise_tile(alpha=10, seed=7):
    key = (alpha, seed)
    if key in _noise_cache:
        return _noise_cache[key]
    rng = np.random.default_rng(seed)
    n = rng.integers(0, 255, (256, 256), dtype=np.uint8)
    a = np.full((256, 256), alpha, dtype=np.uint8)
    tile = Image.fromarray(np.dstack([n, n, n, a]), "RGBA")
    _noise_cache[key] = tile
    return tile


def grain(img, alpha=12, seed=0, frame=0):
    tile = noise_tile(alpha, seed)
    rng = random.Random(seed * 100003 + frame)
    ox, oy = rng.randrange(256), rng.randrange(256)
    layer = Image.new("RGBA", (W, H))
    for y in range(-oy, H, 256):
        for x in range(-ox, W, 256):
            layer.paste(tile, (x, y))
    return Image.alpha_composite(img, layer)


def vignette(img, strength=110):
    if "vig" not in _noise_cache:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W * .62)) ** 2 + ((yy - H / 2) / (H * .62)) ** 2)
        a = np.clip((d - 0.55) * strength * 1.9, 0, strength).astype(np.uint8)
        _noise_cache["vig"] = Image.fromarray(
            np.dstack([np.zeros_like(a), np.zeros_like(a), np.zeros_like(a), a]), "RGBA")
    return Image.alpha_composite(img, _noise_cache["vig"])


# ---------------------------------------------------------------- 绘图

def rrect(size, radius, fill=None, outline=None, width=2):
    img = new_layer(size)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=fill, outline=outline, width=width)
    return img


def paste_center(base, layer, cx, cy, alpha=1.0, scale=1.0, rot=0):
    if scale != 1.0:
        w = max(1, int(layer.width * scale)); h = max(1, int(layer.height * scale))
        layer = layer.resize((w, h), Image.LANCZOS)
    if rot:
        layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer = layer.copy(); layer.putalpha(a)
    base.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))
    return base


def text_img(s, size, color=TEXT, weight="bold", stroke=0, stroke_color=(0, 0, 0), spacing=0, alpha=255):
    f = font(size, weight)
    if spacing:
        # 手动字距
        widths = [f.getbbox(ch)[2] - f.getbbox(ch)[0] for ch in s]
        w = int(sum(widths) + spacing * (len(s) - 1)) + 8
        img = new_layer((max(1, w), int(size * 1.7)))
        d = ImageDraw.Draw(img)
        x = 4
        for ch, cw in zip(s, widths):
            d.text((x, img.height * 0.32), ch, font=f, fill=rgba(color, alpha), anchor="lm",
                   stroke_width=stroke, stroke_fill=rgba(stroke_color, alpha))
            x += cw + spacing
        return img.crop(img.getbbox() or (0, 0, 1, 1))
    bbox = f.getbbox(s, stroke_width=stroke)
    pad = stroke + 6
    img = new_layer((bbox[2] - bbox[0] + pad * 2, bbox[3] - bbox[1] + pad * 2))
    d = ImageDraw.Draw(img)
    d.text((pad - bbox[0], pad - bbox[1]), s, font=f, fill=rgba(color, alpha),
           stroke_width=stroke, stroke_fill=rgba(stroke_color, alpha))
    return img


def emoji_img(value, size):
    """value 可以是 png 路径，也可以是 emoji 字符。"""
    if value and isinstance(value, str) and ("\\" in value or "/" in value):
        if value.lower().endswith(".png") and os.path.exists(value):
            im = Image.open(value).convert("RGBA")
            return im.resize((int(size), int(size)), Image.LANCZOS)
        return new_layer((2, 2))  # 路径没找到就留空，绝不把路径当文字画出来
    return text_img(value or "", int(size * 0.92), TEXT, "regular")


def mark_icon(kind, size, color):
    """矢量画 ✓ / ✕ / · ，避免字体缺字变豆腐块。"""
    img = new_layer((int(size), int(size)))
    d = ImageDraw.Draw(img)
    w = max(2, int(size * 0.13))
    if kind in ("✓", "v", "check"):
        d.line([(size * 0.12, size * 0.55), (size * 0.40, size * 0.82), (size * 0.90, size * 0.20)],
               fill=color + (255,), width=w, joint="curve")
    elif kind in ("✕", "x", "cross"):
        d.line([(size * 0.16, size * 0.16), (size * 0.84, size * 0.84)], fill=color + (255,), width=w)
        d.line([(size * 0.84, size * 0.16), (size * 0.16, size * 0.84)], fill=color + (255,), width=w)
    else:
        r = size * 0.16
        d.ellipse([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r], fill=color + (255,))
    return img


_particle_cache = {}


def particles(seed=0, n=46):
    key = (seed, n)
    if key not in _particle_cache:
        rng = random.Random(seed * 7919 + 3)
        _particle_cache[key] = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1.2, 3.4),
                                 rng.uniform(0, 6.28), rng.uniform(0.06, 0.2)) for _ in range(n)]
    return _particle_cache[key]


def draw_particles(img, t, seed=0, color=(0xBF, 0xD2, 0xEA), n=46, alpha_gain=1.0):
    for (x0, y0, r, ph, sp) in particles(seed, n):
        x = (x0 + t * 12 * sp * 10) % (W + 40) - 20
        y = y0 + math.sin(t * 0.5 + ph) * 14
        a = (0.35 + 0.65 * abs(math.sin(t * 0.7 + ph))) * sp * alpha_gain
        g = radial_local(r * 4, color, 2.0)
        g = g.copy()
        g.putalpha(g.split()[3].point(lambda v: int(v * min(1.0, a))))
        img.alpha_composite(g, (int(x - g.width / 2), int(y - g.height / 2)))
    return img


def radial_local(r, color, power=2.0):
    key = ("pl", round(r, 1), color)
    if key in _noise_cache:
        return _noise_cache[key]
    size = int(max(4, r * 2))
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    a = np.clip(1 - d, 0, 1) ** power
    arr = np.dstack([np.full_like(a, color[0]), np.full_like(a, color[1]),
                     np.full_like(a, color[2]), a * 255]).astype(np.uint8)
    img = Image.fromarray(arr, "RGBA")
    _noise_cache[key] = img
    return img


def put(base, layer, x, y, anchor="lt", alpha=1.0, scale=1.0):
    """把 layer 按锚点放到 base 上。anchor: l/m/r + t/m/b。"""
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.LANCZOS)
    if alpha < 1.0:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer = layer.copy(); layer.putalpha(a)
    ax = {"l": 0, "m": 0.5, "r": 1}[anchor[0]]
    ay = {"t": 0, "m": 0.5, "b": 1}[anchor[1]]
    base.alpha_composite(layer, (int(x - layer.width * ax), int(y - layer.height * ay)))
    return base


def fit_line(s, size, max_w, weight="bold"):
    f = font(size, weight)
    while size > 12 and f.getbbox(s)[2] - f.getbbox(s)[0] > max_w:
        size -= 2
        f = font(size, weight)
    return size


def wrap_text(s, size, max_w, weight="bold"):
    f = font(size, weight)
    lines, cur = [], ""
    for ch in s:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        trial = cur + ch
        if f.getbbox(trial)[2] - f.getbbox(trial)[0] > max_w and cur:
            lines.append(cur)
            cur = ch if ch not in "，。！？、：；）》”" else ""
            if ch in "，。！？、：；）》”" and lines:
                lines[-1] += ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def para(base, lines, x, y, size, color=TEXT, weight="bold", lh=1.42, anchor="lt", alpha=1.0):
    yy = y
    for i, ln in enumerate(lines):
        img = text_img(ln, size, color, weight, alpha=int(255 * alpha))
        put(base, img, x, yy, anchor[0] + "t")
        yy += size * lh
    return yy


def pill(text, size=26, fg=TEXT, bg=None, padx=22, pady=9, border=None, weight="bold"):
    t = text_img(text, size, fg, weight)
    w, h = t.width + padx * 2, t.height + pady * 2
    img = new_layer((w, h))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=rgba(bg, 210) if bg else None,
                        outline=rgba(border) if border else None, width=2)
    img.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2))
    return img


def dashed_line(draw, p0, p1, color, width=3, dash=14, gap=10):
    x0, y0 = p0; x1, y1 = p1
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 1:
        return
    n = max(1, int(dist // (dash + gap)) + 1)
    ux, uy = (x1 - x0) / dist, (y1 - y0) / dist
    pos = 0.0
    while pos < dist:
        a = pos / dist; b = min(1.0, (pos + dash) / dist)
        draw.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
                   (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill=color, width=width)
        pos += dash + gap


def arrow(draw, p0, p1, color, width=3, head=16):
    draw.line([p0, p1], fill=color, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        a2 = ang + s * 0.42
        draw.line([p1, (p1[0] - head * math.cos(a2), p1[1] - head * math.sin(a2))], fill=color, width=width)


# ---------------------------------------------------------------- 编码

def open_writer(path, crf=16, preset="medium"):
    cmd = [os.environ.get("FFMPEG") or "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS),
           "-i", "-", "-an", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def write_frame(p, img):
    if img.mode != "RGB":
        img = img.convert("RGB")
    p.stdin.write(img.tobytes())


def render_scene(scene, path, crf=16, preset="medium", on_frame=None):
    dur = scene.dur
    n = int(round(dur * FPS))
    proc = open_writer(path, crf=crf, preset=preset)
    try:
        for i in range(n):
            t = i / FPS
            img = scene.frame(t)
            if on_frame:
                img = on_frame(img, i, n)
            write_frame(proc, img)
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg 编码失败 rc=%s: %s" % (rc, path))
    return path
