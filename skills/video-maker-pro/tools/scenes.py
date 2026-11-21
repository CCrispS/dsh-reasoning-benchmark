#!/usr/bin/env python3
"""v2 动效场景。每个场景是一段无声动画，由 build_all.py 渲染成 mp4。"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import anim
from anim import (ACC, ACC2, BG, BLUE, DIM, GREEN, H, LINE, PANEL, PANEL2, SUB,
                  TEXT, U, W, clamp, ease_in_out, ease_out, ease_out_back,
                  ease_out_quint, lerp, mix, para, pill, put, rrect, seg,
                  text_img, wrap_text)

_radial_cache = {}


def radial(r, color, power=2.2):
    key = (r, color, power)
    if key in _radial_cache:
        return _radial_cache[key]
    size = int(r * 2)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - r) ** 2 + (yy - r) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** power
    arr = np.dstack([np.full_like(a, color[0]), np.full_like(a, color[1]),
                     np.full_like(a, color[2]), a * 255]).astype(np.uint8)
    img = Image.fromarray(arr, "RGBA")
    _radial_cache[key] = img
    return img


def glow_blob(base, color, cx, cy, r, alpha, power=2.2):
    if alpha <= 0.002:
        return base
    g = radial(r, color, power)
    a = g.split()[3].point(lambda v: int(v * min(1.0, alpha)))
    g = g.copy(); g.putalpha(a)
    base.alpha_composite(g, (int(cx - r), int(cy - r)))
    return base


class Scene:
    def __init__(self, dur, seed=0, grid=True, warm=0.0):
        self.dur = float(dur)
        self.bg = anim.backdrop(seed, grid, warm)

    def frame(self, t):
        return self.bg.copy()


# ---------------------------------------------------------------- 标题

class TitleScene(Scene):
    def __init__(self, dur, kicker="", title="", sub="", foot="", seed=1, warm=0.0, num=None, total=5):
        super().__init__(dur, seed, True, warm)
        self.kicker, self.title, self.sub, self.foot = kicker, title, sub, foot
        self.num, self.total = num, total

    def frame(self, t):
        img = self.bg.copy()
        cx, cy = W / 2, H / 2
        # 呼吸的暖色光
        img = glow_blob(img, ACC, cx - 380, cy + 120, 620, 0.16 + 0.05 * math.sin(t * 1.1))
        img = glow_blob(img, (0x2E, 0x5A, 0x8A), cx + 520, cy - 260, 560, 0.13)
        # 章节大号水印
        if self.num:
            p = seg(t, 0.1, 0.9)
            g = text_img("%02d" % self.num, 420, TEXT, "bold")
            g = g.copy()
            g.putalpha(g.split()[3].point(lambda v: int(v * 0.06 * ease_out(p))))
            img.alpha_composite(g, (int(W - 70 - g.width), int(cy + 60 - g.height / 2)))
        # 章节进度条
        if self.num:
            p = seg(t, 0.6, 1.4)
            step, r = 34, 5
            span = (self.total - 1) * step
            x0 = cx - span / 2
            y0 = H - 118
            for i in range(1, self.total + 1):
                on = i == self.num
                col = ACC if on else LINE
                rad = r + (3 if on else 0)
                d = ImageDraw.Draw(img)
                a = int(255 * ease_out(p))
                d.ellipse([x0 + (i - 1) * step - rad, y0 - rad, x0 + (i - 1) * step + rad, y0 + rad],
                          fill=col + (a if not on else 255,))
                if on:
                    img = glow_blob(img, ACC, x0 + (i - 1) * step, y0, 26, 0.5 * ease_out(p))

        n = len(self.title)
        # 逐字浮起
        size = 108
        total_w = 0
        widths = []
        for ch in self.title:
            w = text_img(ch, size).width
            widths.append(w)
            total_w += w + 6
        x = cx - total_w / 2
        revealed = 0
        for i, ch in enumerate(self.title):
            p = seg(t, 0.25 + i * 0.07, 0.75 + i * 0.07)
            if p <= 0:
                x += widths[i] + 6
                continue
            revealed += 1
            e = ease_out_quint(p)
            a = clamp(p * 1.4)
            dy = (1 - e) * 46
            s = 0.9 + 0.1 * e
            put(img, text_img(ch, size), x + widths[i] / 2, cy - 30 + dy, "mm", a, s)
            x += widths[i] + 6
        # 下划线从左扫出
        p = seg(t, 0.9, 1.5)
        if p > 0:
            lw = total_w * ease_out(p)
            ln = anim.new_layer((int(max(2, lw)), 8))
            ImageDraw.Draw(ln).rounded_rectangle([0, 0, max(2, int(lw)) - 1, 7], radius=4, fill=ACC + (255,))
            img.alpha_composite(ln, (int(cx - lw / 2), int(cy + 42)))
        # kicker
        p = seg(t, 0.05, 0.6)
        if p > 0:
            k = pill(self.kicker, 26, ACC2, bg=None, border=ACC) if self.kicker else None
            if k:
                put(img, k, cx, cy - 150, "mm", ease_out(p), 1.0)
        # sub
        p = seg(t, 1.0, 1.6)
        if p > 0:
            put(img, text_img(self.sub, 40, SUB, "regular"), cx, cy + 92 + (1 - ease_out(p)) * 18, "mm", ease_out(p))
        p = seg(t, 1.5, 2.1)
        if self.foot and p > 0:
            put(img, text_img(self.foot, 28, DIM, "regular"), cx, cy + 158, "mm", ease_out(p))
        return anim.vignette(img, 90)


# ---------------------------------------------------------------- 关系网

KIND_COLORS = {
    "party": ACC2,
    "doc": BLUE,
    "event": GREEN,
    "conflict": ACC,
    "neutral": DIM,
}


class NetworkScene(Scene):
    """节点关系网。nodes: [{id,label,sub,kind,x,y,emoji,r}]，edges: [{a,b,style,label,conflict}]"""

    def __init__(self, dur, nodes, edges, heading="", sub="", seed=2, top=0.92, warm=0.0):
        super().__init__(dur, seed, False, warm)
        self.nodes = []
        for n in nodes:
            d = dict(n)
            d["px"] = min(max(n["x"] * W, 150), W - 150)
            d["py"] = min(n["y"] * H, H * 0.735)
            d["r"] = n.get("r", 34)
            self.nodes.append(d)
        self.index = {n["id"]: n for n in self.nodes}
        self.edges = edges
        self.heading, self.sub = heading, sub
        self.appear0 = 0.15
        self.step = 0.16
        self.edge0 = self.appear0 + self.step * len(self.nodes) * 0.62
        self.edge_step = 0.13

    def _node_xy(self, n):
        return (n["px"], n["py"])

    def frame(self, t):
        img = self.bg.copy()
        # 背景呼吸光
        img = glow_blob(img, ACC, W * 0.22, H * 0.30, 480, 0.10 + 0.03 * math.sin(t * 0.9))
        img = glow_blob(img, (0x2E, 0x5A, 0x8A), W * 0.82, H * 0.78, 520, 0.10)
        img = anim.draw_particles(img, t, seed=12, alpha_gain=0.55)

        # 边
        el = anim.new_layer()
        d = ImageDraw.Draw(el)
        for j, e in enumerate(self.edges):
            a, b = self.index[e["a"]], self.index[e["b"]]
            p = seg(t, self.edge0 + j * self.edge_step, self.edge0 + j * self.edge_step + 0.55)
            if p <= 0:
                continue
            p = ease_out(p)
            (x0, y0), (x1, y1) = self._node_xy(a), self._node_xy(b)
            # 连线缩到圆边
            dx, dy = x1 - x0, y1 - y0
            dist = math.hypot(dx, dy) or 1
            ux, uy = dx / dist, dy / dist
            sx, sy = x0 + ux * (a["r"] + 6), y0 + uy * (a["r"] + 6)
            ex, ey = x1 - ux * (b["r"] + 6), y1 - uy * (b["r"] + 6)
            mx, my = sx + (ex - sx) * p, sy + (ey - sy) * p
            col = ACC if e.get("conflict") else (LINE if e.get("style") != "dim" else (0x34, 0x3B, 0x48))
            if e.get("style") == "dashed":
                anim.dashed_line(d, (sx, sy), (mx, my), col + (235,), 3, 13, 9)
            else:
                d.line([(sx, sy), (mx, my)], fill=col + (210,), width=3)
            # 箭头
            if p > 0.985 and e.get("arrow", True):
                anim.arrow(d, ((sx + mx) / 2 - ux * 8, (sy + my) / 2 - uy * 8),
                           (mx, my), col + (235,), 3, 15)
            # 沿线脉冲
            if p >= 1 and e.get("conflict"):
                for k in range(2):
                    q = ((t * 0.55 + k * 0.5 + j * 0.17) % 1.0)
                    q = ease_in_out(q)
                    px, py = sx + (ex - sx) * q, sy + (ey - sy) * q
                    g = radial(16, ACC, 1.8)
                    el.alpha_composite(g, (int(px - 16), int(py - 16)))
            # 边标签（沿法线偏移，避免压住节点文字）
            if e.get("label") and p > 0.9:
                bgp = pill(e["label"], 22, ACC2 if not e.get("conflict") else ACC, bg=PANEL, padx=12, pady=4)
                bx, by = (sx + ex) / 2 - uy * 24, (sy + ey) / 2 + ux * 24
                put(el, bgp, bx, by, "mm", 0.94)
        img.alpha_composite(el)

        # 节点
        for i, n in enumerate(self.nodes):
            p = seg(t, self.appear0 + i * self.step, self.appear0 + i * self.step + 0.5)
            if p <= 0:
                continue
            e = ease_out_back(p, 2.0)
            a = clamp(p * 1.5)
            col = KIND_COLORS.get(n.get("kind", "neutral"), DIM)
            cx, cy = n["px"], n["py"]
            R = n["r"] * (0.6 + 0.4 * e)
            lay = anim.new_layer()
            dl = ImageDraw.Draw(lay)
            if n.get("kind") == "conflict":
                dl.ellipse([cx - R, cy - R, cx + R, cy + R], outline=col + (255,), width=4)
                for k in range(2):
                    ph = (t * 0.8 + k * 0.5) % 1.0
                    rr = R * (1.0 + 1.4 * ph)
                    dl.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=col + (int(120 * (1 - ph)),), width=3)
            dl.ellipse([cx - R, cy - R, cx + R, cy + R], fill=PANEL + (255,), outline=col + (255,), width=3)
            # 内容：emoji 或首字
            val = n.get("emoji_path") or n.get("emoji")
            if val:
                em = anim.emoji_img(val, R * 1.25)
            else:
                em = text_img(n.get("icon", "◆"), int(R * 0.9), col)
            put(lay, em, cx, cy, "mm")
            img = glow_blob(img, col, cx, cy, R * 2.2, 0.16 * a)
            img.alpha_composite(lay)
            # 标签
            la = clamp((p - 0.35) * 3)
            if la > 0:
                lab = text_img(n["label"], n.get("lsize", 30), TEXT if n.get("kind") != "conflict" else ACC, "bold")
                ly = cy + R + 22
                put(img, lab, cx, ly, "mt", la)
                if n.get("sub"):
                    put(img, text_img(n["sub"], 22, DIM, "regular"), cx, ly + n.get("lsize", 30) * 1.16 + 6, "mt", la)

        # 标题
        if self.heading:
            p = ease_out(seg(t, 0.0, 0.45))
            put(img, text_img(self.heading, 34, ACC2, "bold"), 84, 74 + (1 - p) * -14, "lt", p)
            if self.sub:
                q = ease_out(seg(t, 0.2, 0.8))
                put(img, text_img(self.sub, 24, SUB, "regular"), 84, 126, "lt", q)
        return anim.grain(anim.vignette(img, 100), 7, 3, int(t * 30))


# ---------------------------------------------------------------- 对照板

def col(v):
    """支持 "#RRGGBB" 或 (r,g,b)。"""
    if isinstance(v, str):
        v = v.lstrip("#")
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    return v


class VersusScene(Scene):
    def __init__(self, dur, left, right, center="VS", center_emoji=None, heading="", seed=3):
        super().__init__(dur, seed, False, 0.15)
        self.left, self.right = left, right
        self.center, self.center_emoji = center, center_emoji
        self.heading = heading

    def _panel(self, img, x0, y0, w, h, spec, side, t):
        c = col(spec.get("color", LINE))
        bg = rrect((w, h), 22, fill=PANEL + (238,), outline=c + (200,), width=2)
        img.alpha_composite(bg, (int(x0), int(y0)))
        lay = anim.new_layer()
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle([x0, y0, x0 + w - 1, y0 + 8], radius=4, fill=c + (255,))
        img.alpha_composite(lay)
        # 表头
        head = text_img(spec["title"], 34, c, "bold")
        put(img, head, x0 + 34, y0 + 34)
        if spec.get("who"):
            put(img, text_img(spec["who"], 22, DIM, "regular"), x0 + 34, y0 + 34 + 46)
        yy = y0 + 34 + (100 if spec.get("who") else 86)
        for i, it in enumerate(spec.get("items", [])):
            p = seg(t, 0.55 + side * 0.12 + i * 0.16, 0.55 + side * 0.12 + i * 0.16 + 0.45)
            if p <= 0:
                continue
            a = ease_out(p)
            mark = it.get("mark", "·")
            mcol = GREEN if mark == "✓" else (ACC if mark == "✕" else c)
            put(img, anim.mark_icon(mark, 30, mcol), x0 + 36, yy + 2, "lt", a)
            lines = wrap_text(it["t"], 30, w - 130)
            yy2 = para(img, lines, x0 + 78, yy + (1 - a) * 12, 30, TEXT, "regular", 1.34, alpha=a)
            if it.get("note"):
                yy2 = para(img, wrap_text(it["note"], 22, w - 130), x0 + 78, yy2 + 4, 22, DIM, "regular", 1.3,
                           alpha=clamp((p - 0.4) * 2.5))
            yy = yy2 + 20
        return img

    def _measure(self, spec, w):
        yy = 34 + (100 if spec.get("who") else 86)
        for it in spec.get("items", []):
            yy += len(wrap_text(it["t"], 30, w - 130)) * 30 * 1.34
            if it.get("note"):
                yy += 4 + len(wrap_text(it["note"], 22, w - 130)) * 22 * 1.3
            yy += 20
        return yy + 28

    def frame(self, t):
        img = self.bg.copy()
        pw, gap = 800, 60
        ph = max(self._measure(self.left, pw), self._measure(self.right, pw))
        ph = min(max(ph, 380), 700)
        y0 = (H - ph) / 2 + 10
        total = pw * 2 + gap
        x_left = W / 2 - total / 2
        x_right = x_left + pw + gap
        pl = ease_out_quint(seg(t, 0.05, 0.75))
        pr = ease_out_quint(seg(t, 0.15, 0.85))
        if pl > 0:
            lay = anim.new_layer()
            self._panel(lay, 0, 0, pw, ph, self.left, -1, t)
            put(img, lay, x_left - (1 - pl) * 260, y0, "lt", pl)
        if pr > 0:
            lay = anim.new_layer()
            self._panel(lay, 0, 0, pw, ph, self.right, 1, t)
            put(img, lay, x_right + (1 - pr) * 260, y0, "lt", pr)
        # 中间 VS
        p = seg(t, 0.7, 1.25)
        if p > 0:
            e = ease_out_back(p, 2.4)
            cx, cy = W / 2, y0 + ph / 2 - 10
            if self.center_emoji:
                put(img, anim.emoji_img(self.center_emoji, 70), cx, cy - 62, "mm", clamp(p * 1.6), e)
            lay = anim.new_layer()
            d = ImageDraw.Draw(lay)
            d.ellipse([cx - 42 * e, cy + 18 - 42 * e, cx + 42 * e, cy + 18 + 42 * e], fill=ACC + (255,))
            put(lay, text_img(self.center, 34, TEXT, "bold"), cx, cy + 18, "mm")
            img.alpha_composite(lay)
        if self.heading:
            p = ease_out(seg(t, 0.0, 0.4))
            put(img, text_img(self.heading, 30, ACC2, "bold"), W / 2, 92, "mt", p)
        put(img, text_img("说法", 22, DIM, "regular"), x_left + pw / 2, y0 + ph + 26, "mt", pl)
        put(img, text_img("记录", 22, DIM, "regular"), x_right + pw / 2, y0 + ph + 26, "mt", pr)
        return anim.vignette(img, 95)


# ---------------------------------------------------------------- 时间链

class ChainScene(Scene):
    def __init__(self, dur, items, heading="", sub="", seed=4, focus=None):
        super().__init__(dur, seed, False)
        self.items, self.heading, self.sub, self.focus = items, heading, sub, focus

    def frame(self, t):
        img = self.bg.copy()
        n = len(self.items)
        y = H * 0.55
        x0, x1 = 170, W - 170
        span = x1 - x0
        # 主线
        p = ease_in_out(seg(t, 0.1, 0.9))
        lay = anim.new_layer()
        d = ImageDraw.Draw(lay)
        d.line([(x0, y), (x0 + span * p, y)], fill=(0x3A, 0x43, 0x54, 255), width=5)
        img.alpha_composite(lay)
        for i, it in enumerate(self.items):
            idx = i / max(1, n - 1)
            cx = x0 + span * idx
            q = seg(t, 0.35 + i * 0.13, 0.75 + i * 0.13)
            if q <= 0:
                continue
            e = ease_out_back(q, 2.2)
            hot = (self.focus == i) or it.get("hot")
            col = ACC if hot else (it.get("color") or ACC2)
            lay = anim.new_layer()
            dl = ImageDraw.Draw(lay)
            r = 17 * e * (1.45 if hot else 1.0)
            dl.ellipse([cx - r - 6, y - r - 6, cx + r + 6, y + r + 6], fill=(0, 0, 0, 0), outline=col + (80,), width=3)
            dl.ellipse([cx - r, y - r, cx + r, y + r], fill=col + (255,))
            img.alpha_composite(lay)
            if hot:
                img = glow_blob(img, col, cx, y, 120, 0.22 * q)
            a = clamp((q - 0.3) * 2.2)
            up = i % 2 == 0
            ax = "l" if i == 0 else ("r" if i == n - 1 else "m")
            if up:
                put(img, text_img(it["date"], 28, col, "bold"), cx, y - 62, ax + "b", a)
                put(img, text_img(it["label"], 30, TEXT, "bold"), cx, y - 132, ax + "b", a)
                if it.get("sub"):
                    put(img, text_img(it["sub"], 21, DIM, "regular"), cx, y - 108, ax + "b", a)
            else:
                put(img, text_img(it["date"], 28, col, "bold"), cx, y + 62, ax + "t", a)
                put(img, text_img(it["label"], 30, TEXT, "bold"), cx, y + 108, ax + "t", a)
                if it.get("sub"):
                    put(img, text_img(it["sub"], 21, DIM, "regular"), cx, y + 152, ax + "t", a)
        if self.heading:
            p = ease_out(seg(t, 0.0, 0.45))
            put(img, text_img(self.heading, 46, TEXT, "bold"), W / 2, 120, "mt", p)
            if self.sub:
                put(img, text_img(self.sub, 24, SUB, "regular"), W / 2, 186, "mt", ease_out(seg(t, 0.2, 0.8)))
        return anim.vignette(img, 100)


# ---------------------------------------------------------------- 冲击

class StampScene(Scene):
    def __init__(self, dur, emoji_path=None, emoji=None, text="", sub="", color=ACC, seed=5):
        super().__init__(dur, seed, False, 0.3)
        self.emoji_path, self.emoji, self.text, self.sub = emoji_path, emoji, text, sub
        self.color = col(color)

    def frame(self, t):
        img = self.bg.copy()
        cx, cy = W / 2, H * 0.44
        p = seg(t, 0.0, 0.42)
        if p > 0:
            e = ease_out_back(p, 2.6)
            if self.emoji_path and os.path.exists(self.emoji_path):
                em = Image.open(self.emoji_path).convert("RGBA")
                s = int(300 * (0.4 + 0.6 * e))
                em = em.resize((s, s), Image.LANCZOS)
                img = glow_blob(img, self.color, cx, cy - 60, 400, 0.20 * p)
                put(img, em, cx, cy - 60, "mm", clamp(p * 2), 1.0)
            elif self.emoji:
                put(img, text_img(self.emoji, int(230 * e), TEXT, "regular"), cx, cy - 60, "mm", clamp(p * 2))
        # 文字砸下
        p2 = seg(t, 0.18, 0.62)
        if p2 > 0:
            e = ease_out_back(p2, 2.2)
            shake = 0
            if p2 < 0.9 and p2 > 0.4:
                shake = math.sin(t * 90) * 6 * (1 - p2)
            size = 84
            put(img, text_img(self.text, size, TEXT, "bold"), cx + shake, H * 0.60 + (1 - e) * -60, "mm", clamp(p2 * 1.8))
            # 强调条
            lw = 260 * ease_out(seg(t, 0.5, 0.9))
            if lw > 2:
                lay = anim.new_layer((int(lw), 6))
                ImageDraw.Draw(lay).rounded_rectangle([0, 0, int(lw) - 1, 5], radius=3, fill=self.color + (255,))
                img.alpha_composite(lay, (int(cx - lw / 2), int(H * 0.60 + 54)))
        p3 = seg(t, 0.55, 1.0)
        if self.sub and p3 > 0:
            put(img, text_img(self.sub, 34, SUB, "regular"), cx, H * 0.70, "mm", ease_out(p3))
        return anim.vignette(img, 105)


# ---------------------------------------------------------------- 引言

class QuoteScene(Scene):
    def __init__(self, dur, text="", source="", who="", emoji_path=None, seed=6):
        super().__init__(dur, seed, False, 0.1)
        self.text, self.source, self.who, self.emoji_path = text, source, who, emoji_path

    def frame(self, t):
        img = self.bg.copy()
        if self.emoji_path and os.path.exists(self.emoji_path):
            em = Image.open(self.emoji_path).convert("RGBA").resize((96, 96), Image.LANCZOS)
            put(img, em, 150, 210, "lt", ease_out(seg(t, 0.0, 0.5)))
        put(img, text_img("“", 150, ACC, "bold"), 130, 250, "lt", ease_out(seg(t, 0.05, 0.5)))
        lines = wrap_text(self.text, 60, W - 380)
        yy = 380
        for i, ln in enumerate(lines):
            p = seg(t, 0.25 + i * 0.16, 0.75 + i * 0.16)
            if p <= 0:
                continue
            put(img, text_img(ln, 60, TEXT, "bold"), 190 + (1 - ease_out(p)) * 30, yy, "lt", ease_out(p))
            yy += 60 * 1.55
        p = seg(t, 0.8, 1.3)
        if p > 0:
            if self.who:
                put(img, pill(self.who, 26, ACC2, bg=PANEL, border=ACC2), 190, yy + 20, "lt", ease_out(p))
            if self.source:
                put(img, text_img(self.source, 24, DIM, "regular"), 190, yy + 88, "lt", ease_out(seg(t, 1.0, 1.5)))
        return anim.vignette(img, 100)


# ---------------------------------------------------------------- 片尾

class EndScene(Scene):
    def __init__(self, dur, title="", lines=(), foot="", seed=7):
        super().__init__(dur, seed, True, 0.05)
        self.title, self.lines, self.foot = title, list(lines), foot

    def frame(self, t):
        img = self.bg.copy()
        img = glow_blob(img, ACC, W / 2, H * 0.35, 700, 0.10)
        p = seg(t, 0.1, 0.8)
        if p > 0:
            put(img, text_img(self.title, 76, TEXT, "bold"), W / 2, H * 0.36, "mm", ease_out(p))
        yy = H * 0.47
        for i, ln in enumerate(self.lines):
            q = seg(t, 0.45 + i * 0.18, 0.95 + i * 0.18)
            if q <= 0:
                continue
            put(img, text_img(ln, 34, SUB, "regular"), W / 2, yy, "mt", ease_out(q))
            yy += 30 * 1.9
        if self.foot:
            q = seg(t, 0.9, 1.4)
            if q > 0:
                put(img, text_img(self.foot, 24, DIM, "regular"), W / 2, H - 120, "mb", ease_out(q))
        return anim.vignette(img, 95)


TYPES = {
    "title": TitleScene,
    "network": NetworkScene,
    "versus": VersusScene,
    "chain": ChainScene,
    "stamp": StampScene,
    "quote": QuoteScene,
    "end": EndScene,
}


def build(spec):
    kind = spec.pop("type")
    return TYPES[kind](**spec)
