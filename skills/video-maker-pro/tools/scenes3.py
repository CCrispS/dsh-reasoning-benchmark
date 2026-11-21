# -*- coding: utf-8 -*-
"""v3 专用场景：证据图卡、矛盾对照、证据墙、流程图、公开网页摘录、提问卡、逐问冲击卡。

规则：
- 任何带 redact 的截图，合成时必须自己打码（技能渲染器只对 image 镜头自动打码）。
- 页面摘录用「浏览器窗口」样式，必须写明 URL 与抓取日期，绝不伪造截图。
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFilter

import anim
import scenes
from anim import (W, H, BG, PANEL, PANEL2, TEXT, SUB, DIM, ACC, ACC2, LINE, GREEN, BLUE,
                  clamp, lerp, seg, ease_out, ease_in_out, ease_out_back, ease_out_quint, mix)
from scenes import Scene, glow_blob, radial

def _renderer_assets():
    """素材来自同仓库的 video-maker 技能；可用 VIDEO_MAKER_SKILL 覆盖。"""
    env = os.environ.get("VIDEO_MAKER_SKILL")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(env or os.path.join(os.path.dirname(root), "video-maker"), "assets")


ASSETS = _renderer_assets()
if not os.path.isdir(ASSETS):
    raise SystemExit("找不到素材目录 %s —— 请把 video-maker 与 video-maker-pro 放在同一个 skills 目录下，或设置 VIDEO_MAKER_SKILL。" % ASSETS)
_MANIFEST = json.load(open(os.path.join(ASSETS, "assets.json"), encoding="utf-8"))
_BY_ID = {e["id"]: e for e in _MANIFEST["images"]}
_CACHE = {}


def load_asset(img_id, max_w=None, max_h=None):
    """读截图并按 assets.json 的 redact 打码（模糊），可选缩小。"""
    key = (img_id, max_w, max_h)
    if key in _CACHE:
        return _CACHE[key]
    e = _BY_ID[img_id]
    im = Image.open(os.path.join(ASSETS, e["file"])).convert("RGBA")
    for box in e.get("redact", []):
        x, y, w, h = box
        x0, y0 = int(x * im.width), int(y * im.height)
        x1, y1 = int((x + w) * im.width), int((y + h) * im.height)
        if x1 <= x0 or y1 <= y0:
            continue
        pad = 6
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        x1, y1 = min(im.width, x1 + pad), min(im.height, y1 + pad)
        reg = im.crop((x0, y0, x1, y1))
        r = max(10, int(min(reg.width, reg.height) * 0.5))
        reg = reg.filter(ImageFilter.GaussianBlur(r))
        im.paste(reg, (x0, y0))
    if max_w or max_h:
        sw = (max_w or im.width) / im.width
        sh = (max_h or im.height) / im.height
        s = min(sw, sh)
        if s < 1:
            im = im.resize((max(2, int(im.width * s)), max(2, int(im.height * s))), Image.LANCZOS)
    _CACHE[key] = im
    return im


def contain(im, w, h):
    """等比缩放到 (w,h) 内，返回新图（透明底）。"""
    s = min(w / im.width, h / im.height, 1.0 if im.width <= w and im.height <= h else max(w / im.width, h / im.height))
    s = min(w / im.width, h / im.height)
    nw, nh = max(2, int(im.width * s)), max(2, int(im.height * s))
    return im.resize((nw, nh), Image.LANCZOS)


def shot_card(img_id, w, h, accent=None, alpha=1.0, label=None, pad=10):
    """把一张截图做成带边框的证据卡（面板 + 内嵌图 + 可选角标）。"""
    w, h = int(w), int(h)
    accent = accent or LINE
    card = anim.new_layer((w, h))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=16, fill=PANEL2 + (245,), outline=accent + (200,), width=2)
    src = load_asset(img_id)
    inner = contain(src, w - pad * 2, h - pad * 2)
    card.alpha_composite(inner, ((w - inner.width) // 2, (h - inner.height) // 2))
    if label:
        p = anim.pill(label, 20, TEXT, bg=(0, 0, 0), padx=12, pady=5)
        card.alpha_composite(p, (10, 10))
    return card


def _frame_dots(img, cx, cy, t, color=ACC):
    lay = anim.new_layer()
    d = ImageDraw.Draw(lay)
    for k in range(3):
        ph = (t * 0.7 + k / 3.0) % 1.0
        r = 40 + 150 * ph
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (int(70 * (1 - ph)),), width=3)
    img.alpha_composite(lay)


def _heading(img, heading, sub="", color=ACC2):
    if heading:
        put_shadow(img, heading, 34, color, 96, 74)
    if sub:
        img.alpha_composite if False else None
        anim.put(img, anim.text_img(sub, 24, DIM, "regular"), 96, 122)


def put_shadow(base, text, size, color, x, y, weight="bold", alpha=1.0):
    gl = anim.text_img(text, size, color, weight, alpha=int(255 * alpha))
    for dx, dy in ((0, 4), (0, 8)):
        sh = anim.text_img(text, size, (0, 0, 0), weight, alpha=int(90 * alpha))
        base.alpha_composite(sh, (x + dx, y + dy))
    base.alpha_composite(gl, (x, y))
    return gl


# ------------------------------------------------------------------ 提问卡（大 🤔）


class QuestionScene(Scene):
    """大号疑问 emoji + 逐条问题。questions: [str, ...]"""

    def __init__(self, dur, kicker="", title="那么，问题来了。", questions=None,
                 foot="", seed=11, emoji=None, warm=0.06):
        super().__init__(dur, seed, True, warm)
        self.kicker, self.title = kicker, title
        self.questions = questions or []
        self.foot = foot
        self.emoji = anim.emoji_img(emoji, 300) if emoji else anim.emoji_img("\U0001F914", 300)

    def frame(self, t):
        img = self.bg.copy()
        img = glow_blob(img, ACC, W * 0.5, H * 0.30, 700, 0.12 + 0.05 * math.sin(t * 1.2))
        img = anim.draw_particles(img, t, seed=21, alpha_gain=0.5)
        cx, cy = W / 2, 236
        _frame_dots(img, cx, cy, t)
        # emoji 呼吸 + 轻摆
        p = ease_out_back(seg(t, 0.1, 0.75), 2.2)
        bob = math.sin(t * 1.6) * 8
        s = (0.82 + 0.18 * p) * (1 + 0.015 * math.sin(t * 2.2))
        anim.put(img, self.emoji, cx, cy + bob, "mm", clamp(p * 1.4), s)
        # 标题
        p = seg(t, 0.45, 1.0)
        if p > 0:
            anim.put(img, anim.text_img(self.title, 54, TEXT), cx, 468, "mm", ease_out(p))
        p = seg(t, 0.55, 1.0)
        if p > 0 and self.kicker:
            anim.put(img, anim.pill(self.kicker, 24, ACC2, bg=None, border=ACC), cx, 412, "mm", ease_out(p))
        # 问题逐条
        n = len(self.questions)
        top = 552
        gap = 92 if n <= 3 else 80
        for i, q in enumerate(self.questions):
            p = seg(t, 1.0 + i * 0.35, 1.5 + i * 0.35)
            if p <= 0:
                continue
            a = ease_out(p)
            y = top + i * gap + (1 - a) * 24
            qm = anim.text_img("？", 44, ACC)
            anim.put(img, qm, 250, y - 6, "lt", a)
            lines = anim.wrap_text(q, 40, W - 700)
            anim.para(img, lines, 330, y, 40, TEXT, "bold", 1.3, alpha=a)
        if self.foot:
            p = seg(t, 1.2, 1.8)
            if p > 0:
                anim.put(img, anim.text_img(self.foot, 24, DIM, "regular"), cx, H - 90, "mm", ease_out(p))
        return anim.vignette(img, 100)


# ------------------------------------------------------------------ 单问冲击卡


class BigQuestion(Scene):
    """一个编号 + 一句质问 + 一条证据。"""

    def __init__(self, dur, num="Q01", text="", sub="", ev="", tag="", seed=12, accent=None):
        super().__init__(dur, seed, True, 0.10)
        self.num, self.text, self.sub, self.ev, self.tag = num, text, sub, ev, tag
        self.accent = accent or ACC

    def frame(self, t):
        img = self.bg.copy()
        img = glow_blob(img, self.accent, W * 0.12, H * 0.5, 620, 0.14 + 0.05 * math.sin(t * 1.3))
        img = anim.draw_particles(img, t, seed=31, alpha_gain=0.4)
        # 左侧编号（水印）
        p = ease_out(seg(t, 0.0, 0.6))
        gl = anim.text_img(self.num, 250, TEXT, "bold")
        gl.putalpha(gl.split()[3].point(lambda v: int(v * 0.10 * p)))
        img.alpha_composite(gl, (70, 66))
        # 竖线
        lay = anim.new_layer()
        d = ImageDraw.Draw(lay)
        hh = 520 * ease_out(seg(t, 0.1, 0.9))
        d.rounded_rectangle([96, 300, 102, 300 + hh], radius=3, fill=self.accent + (255,))
        img.alpha_composite(lay)
        # 正文
        lines = anim.wrap_text(self.text, 56, W - 420)
        y = 300
        for i, ln in enumerate(lines):
            p = seg(t, 0.35 + i * 0.18, 0.85 + i * 0.18)
            if p <= 0:
                break
            anim.put(img, anim.text_img(ln, 56, TEXT), 170, y, "lt", ease_out(p), 1.0)
            y += 56 * 1.36
        if self.sub:
            p = seg(t, 1.1, 1.6)
            if p > 0:
                for i, ln in enumerate(anim.wrap_text(self.sub, 30, W - 460)):
                    anim.put(img, anim.text_img(ln, 30, SUB, "regular"), 172, y + 18 + i * 42, "lt", ease_out(p))
        # 证据角标
        if self.ev:
            p = ease_out(seg(t, 1.3, 1.9))
            if p > 0:
                tag = self.tag or "证据"
                bgp = anim.pill("%s · %s" % (tag, self.ev), 24, ACC2, bg=PANEL, border=LINE, padx=18)
                anim.put(img, bgp, 172, H - 170, "lt", p)
        return anim.vignette(img, 105)


# ------------------------------------------------------------------ 矛盾对照（双截图）


class Contradiction(Scene):
    """左「此前的说法」/ 右「另一处的说法」，两边都是截图。"""

    def __init__(self, dur, left, right, heading="", verdict="", seed=13, warm=0.05):
        super().__init__(dur, seed, True, warm)
        self.left, self.right = left, right
        self.heading, self.verdict = heading, verdict

    def _side(self, img, spec, x, y, w, h, side, t):
        p = ease_out_quint(seg(t, 0.15 + side * 0.1, 0.85 + side * 0.1))
        if p <= 0:
            return
        col = ACC if side == 0 else BLUE
        card = shot_card(spec["img"], w, h, accent=col)
        anim.put(img, card, x - (1 - p) * 120 * (1 if side == 0 else -1), y, "lt", p)
        # 标签
        lab = spec.get("who", "")
        if lab:
            lp = ease_out(seg(t, 0.5 + side * 0.1, 1.0 + side * 0.1))
            if lp > 0:
                anim.put(img, anim.text_img(lab, 26, col), x, y - 46, "lt", lp)
        # 引文
        q = spec.get("quote", "")
        if q:
            qp = seg(t, 0.9 + side * 0.12, 1.4 + side * 0.12)
            if qp > 0:
                yy = y + h + 22
                for i, ln in enumerate(anim.wrap_text(q, 30, w - 10)):
                    anim.put(img, anim.text_img(ln, 30, TEXT, "bold"), x, yy + i * 42, "lt", ease_out(qp))
        # 日期
        d = spec.get("date", "")
        if d:
            dp = seg(t, 1.1 + side * 0.1, 1.5 + side * 0.1)
            if dp > 0:
                anim.put(img, anim.text_img(d, 22, DIM, "regular"), x + w, y - 44, "rt", ease_out(dp))

    def frame(self, t):
        img = self.bg.copy()
        img = glow_blob(img, ACC, W * 0.5, H * 0.5, 700, 0.06)
        img = anim.draw_particles(img, t, seed=41, alpha_gain=0.35)
        if self.heading:
            anim.put(img, anim.text_img(self.heading, 30, ACC2), 96, 70, "lt", ease_out(seg(t, 0, 0.5)))
        cw, cmax = 800, 430
        cy = 410
        for side, spec in ((0, self.left), (1, self.right)):
            e = _BY_ID.get(spec["img"])
            asp = (e["width"] / float(e["height"])) if e else 1.8
            hh = clamp(int(cw / asp), 200, cmax)
            x = 110 if side == 0 else W - 110 - cw
            self._side(img, spec, x, cy - hh / 2, cw, hh, side, t)
        # 中间 VS
        p = seg(t, 1.0, 1.5)
        if p > 0:
            e = ease_out_back(p, 2.2)
            cx, ccy = W / 2, cy - 30
            lay = anim.new_layer()
            d = ImageDraw.Draw(lay)
            d.ellipse([cx - 44 * e, ccy - 44 * e, cx + 44 * e, ccy + 44 * e], fill=ACC + (255,))
            anim.put(lay, anim.text_img("VS", 34, TEXT), cx, ccy, "mm")
            img.alpha_composite(lay)
        # 结论式提问
        if self.verdict:
            p = seg(t, 1.6, 2.2)
            if p > 0:
                yy = cy + cmax / 2 + 92
                for i, ln in enumerate(anim.wrap_text(self.verdict, 40, W - 560)):
                    anim.put(img, anim.text_img(ln, 40, ACC2, "bold"), W / 2, yy + i * 54, "mt", ease_out(p))
        return anim.vignette(img, 100)


# ------------------------------------------------------------------ 证据墙


class EvidenceWall(Scene):
    def __init__(self, dur, items, heading="", sub="", cols=4, seed=14, note=""):
        super().__init__(dur, seed, True, 0.05)
        self.items, self.heading, self.sub, self.cols, self.note = items, heading, sub, cols, note

    def frame(self, t):
        img = self.bg.copy()
        img = anim.draw_particles(img, t, seed=51, alpha_gain=0.35)
        if self.heading:
            anim.put(img, anim.text_img(self.heading, 32, ACC2), 96, 62, "lt", ease_out(seg(t, 0, 0.5)))
        if self.sub:
            anim.put(img, anim.text_img(self.sub, 24, DIM, "regular"), 96, 108, "lt", ease_out(seg(t, 0.1, 0.6)))
        n = len(self.items)
        cols = self.cols
        rows = int(math.ceil(n / float(cols)))
        margin = 96
        gapx, gapy = 30, 54
        cw = (W - margin * 2 - gapx * (cols - 1)) / float(cols)
        ch = cw * 0.60
        total_h = rows * (ch + gapy)
        top = 160 + max(0, (H - 260 - total_h) / 2)
        for i, it in enumerate(self.items):
            r, c = divmod(i, cols)
            x = margin + c * (cw + gapx)
            y = top + r * (ch + gapy)
            p = seg(t, 0.25 + i * 0.09, 0.75 + i * 0.09)
            if p <= 0:
                continue
            e = ease_out_back(p, 1.6)
            card = shot_card(it["img"], int(cw), int(ch), accent=LINE)
            anim.put(img, card, x, y, "lt", clamp(p * 1.3), 1.0)
            if it.get("label"):
                anim.put(img, anim.text_img(it["label"], 22, SUB, "regular"), x + cw / 2, y + ch + 12, "mt",
                         ease_out(seg(t, 0.5 + i * 0.09, 0.9 + i * 0.09)))
        if self.note:
            anim.put(img, anim.text_img(self.note, 22, DIM, "regular"), W / 2, H - 52, "mm",
                     ease_out(seg(t, 1.2, 1.7)))
        return anim.vignette(img, 100)


# ------------------------------------------------------------------ 流程图


class Flow(Scene):
    def __init__(self, dur, steps, heading="", note="", seed=15, vertical=False):
        super().__init__(dur, seed, True, 0.03)
        self.steps, self.heading, self.note, self.vertical = steps, heading, note, vertical

    def frame(self, t):
        img = self.bg.copy()
        img = glow_blob(img, (0x2E, 0x5A, 0x8A), W * 0.5, H * 0.5, 760, 0.08)
        if self.heading:
            anim.put(img, anim.text_img(self.heading, 32, ACC2), 96, 66, "lt", ease_out(seg(t, 0, 0.5)))
        n = len(self.steps)
        if self.vertical:
            bw, bh = 1100, 96
            gap = 42
            total = n * bh + (n - 1) * gap
            x = (W - bw) / 2
            y0 = (H - total) / 2 + 30
            for i, s in enumerate(self.steps):
                p = seg(t, 0.2 + i * 0.3, 0.7 + i * 0.3)
                if p > 0:
                    y = y0 + i * (bh + gap)
                    self._box(img, x, y, bw, bh, s, p)
                    if i < n - 1:
                        self._vline(img, x + bw / 2, y + bh, gap, seg(t, 0.6 + i * 0.3, 0.9 + i * 0.3))
        else:
            gap = 92 if n <= 4 else 60
            bw = min(400, (W - 180 - gap * (n - 1)) / float(n))
            bh = 200
            total = n * bw + (n - 1) * gap
            x0 = (W - total) / 2
            y = H / 2 - bh / 2 + 20
            for i, s in enumerate(self.steps):
                p = seg(t, 0.2 + i * 0.28, 0.7 + i * 0.28)
                if p <= 0:
                    continue
                x = x0 + i * (bw + gap)
                self._box(img, x, y, bw, bh, s, p)
                if i < n - 1:
                    self._harrow(img, x + bw, y + bh / 2, gap, seg(t, 0.55 + i * 0.28, 0.9 + i * 0.28))
        if self.note:
            anim.put(img, anim.text_img(self.note, 26, ACC2), W / 2, H - 84, "mm", ease_out(seg(t, 1.4, 2.0)))
        return anim.vignette(img, 100)

    def _box(self, img, x, y, w, h, s, p):
        e = ease_out_back(p, 1.5)
        kind = s.get("kind", "step")
        col = {"start": ACC2, "end": ACC, "step": BLUE, "bad": ACC, "good": GREEN}.get(kind, BLUE)
        lay = anim.new_layer((int(w), int(h)))
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=18, fill=PANEL + (240,), outline=col + (200,), width=3)
        img.alpha_composite(lay, (int(x), int(y)))
        anim.put(img, anim.text_img(s["label"], 32 if len(s["label"]) <= 12 else 26, TEXT),
                 x + w / 2, y + h / 2 - (14 if s.get("sub") else 0), "mm", clamp(p * 1.4))
        if s.get("sub"):
            anim.put(img, anim.text_img(s["sub"], 20, DIM, "regular"), x + w / 2, y + h / 2 + 26, "mm",
                     clamp((p - 0.3) * 1.6))

    def _harrow(self, img, x, y, gap, p):
        if p <= 0:
            return
        lay = anim.new_layer()
        d = ImageDraw.Draw(lay)
        x1 = x + gap * ease_out(p)
        anim.dashed_line(d, (x + 6, y), (x1, y), ACC2 + (230,), 3, 12, 9)
        if p > 0.95:
            anim.arrow(d, (x1 - 20, y), (x1 + 8, y), ACC2 + (240,), 3, 12)
        img.alpha_composite(lay)

    def _vline(self, img, x, y, gap, p):
        if p <= 0:
            return
        lay = anim.new_layer()
        d = ImageDraw.Draw(lay)
        y1 = y + gap * ease_out(p)
        anim.dashed_line(d, (x, y + 6), (x, y1), ACC2 + (230,), 3, 10, 8)
        img.alpha_composite(lay)


# ------------------------------------------------------------------ 公开网页摘录


class WebCard(Scene):
    """浏览器窗口样式的公开网页摘录。绝不伪造截图：只呈现可复制的原文与 URL。"""

    def __init__(self, dur, url="", title="", lines=None, tag="公开网页摘录", seed=16, foot=""):
        super().__init__(dur, seed, True, 0.04)
        self.url, self.title, self.lines, self.tag, self.foot = url, title, lines or [], tag, foot

    def frame(self, t):
        img = self.bg.copy()
        img = glow_blob(img, (0x2E, 0x5A, 0x8A), W * 0.5, H * 0.42, 780, 0.10)
        img = anim.draw_particles(img, t, seed=61, alpha_gain=0.25)
        w = 1500
        wrapped = [anim.wrap_text((ln[1:] if ln.startswith("*") else ln), 30, w - 140) for ln in self.lines]
        body = sum(len(wr) * 44 + 12 for wr in wrapped)
        h = int(96 + (66 if self.title else 0) + body + 84)
        h = max(360, min(800, h))
        x, y = (W - w) / 2, (H - h) / 2
        p = ease_out_quint(seg(t, 0.05, 0.7))
        card = anim.new_layer((w, h))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=18, fill=(0x12, 0x17, 0x20) + (250,),
                            outline=LINE + (200,), width=2)
        # 顶栏
        d.rounded_rectangle([0, 0, w - 1, 62], radius=18, fill=(0x1A, 0x21, 0x2C) + (255,))
        d.rectangle([0, 40, w - 1, 62], fill=(0x1A, 0x21, 0x2C) + (255,))
        for i, c in enumerate(((0xE5, 0x43, 0x2D), (0xFF, 0xD3, 0x8A), (0x3D, 0xDC, 0x97))):
            d.ellipse([18 + i * 26, 22, 34 + i * 26, 38], fill=c + (255,))
        urlbar = anim.new_layer((w - 260, 34))
        dd = ImageDraw.Draw(urlbar)
        dd.rounded_rectangle([0, 0, w - 261, 33], radius=10, fill=(0x0C, 0x10, 0x16) + (255,))
        card.alpha_composite(urlbar, (120, 14))
        card.alpha_composite(anim.text_img(self.url, 20, SUB, "regular"), (136, 21))
        anim.put(img, card, x, y + (1 - p) * 40, "lt", clamp(p * 1.5))
        # 内容
        cy = y + 96
        if self.title:
            anim.put(img, anim.text_img(self.title, 40, TEXT), x + 56, cy, "lt", ease_out(seg(t, 0.5, 1.0)))
            cy += 68
        for i, ln in enumerate(self.lines):
            pp = seg(t, 0.7 + i * 0.16, 1.15 + i * 0.16)
            if pp <= 0:
                break
            hl = ln.startswith("*")
            txt = ln[1:] if hl else ln
            for j, sub in enumerate(anim.wrap_text(txt, 30, w - 140)):
                anim.put(img, anim.text_img(sub, 30, ACC2 if hl else SUB, "bold" if hl else "regular"),
                         x + 56, cy, "lt", ease_out(pp))
                cy += 44
            cy += 10
        # 角标
        p = ease_out(seg(t, 0.9, 1.5))
        if p > 0:
            anim.put(img, anim.pill(self.tag + " · 抓取 2026-11-21", 22, ACC2, bg=(0, 0, 0), padx=16),
                     x + 56, y + h - 56, "lt", p)
        if self.foot:
            anim.put(img, anim.text_img(self.foot, 22, DIM, "regular"), x + w, y + h - 48, "rt",
                     ease_out(seg(t, 1.2, 1.7)))
        return anim.vignette(img, 100)


# ------------------------------------------------------------------ 猜测卡（大问号）


class GuessScene(Scene):
    """「以下为带问号的猜测」：一句猜测 + 依据 + 巨大问号水印。"""

    def __init__(self, dur, index="01", guess="", basis="", seed=17):
        super().__init__(dur, seed, True, 0.08)
        self.index, self.guess, self.basis = index, guess, basis

    def frame(self, t):
        img = self.bg.copy()
        img = glow_blob(img, ACC, W * 0.78, H * 0.5, 620, 0.10 + 0.04 * math.sin(t))
        p = ease_out(seg(t, 0.1, 0.8))
        gl = anim.text_img("？", 620, TEXT)
        gl.putalpha(gl.split()[3].point(lambda v: int(v * 0.07 * p)))
        img.alpha_composite(gl, (int(W - 300 - gl.width / 2), int(H * 0.5 - gl.height / 2)))
        anim.put(img, anim.pill("猜测 " + self.index, 24, ACC2, bg=None, border=ACC), 110, 150, "lt", p)
        yy = 240
        for i, ln in enumerate(anim.wrap_text(self.guess, 54, 1180)):
            pp = seg(t, 0.35 + i * 0.16, 0.85 + i * 0.16)
            if pp <= 0:
                break
            anim.put(img, anim.text_img(ln, 54, TEXT), 110, yy, "lt", ease_out(pp))
            yy += 74
        if self.basis:
            pp = seg(t, 1.0, 1.5)
            if pp > 0:
                anim.put(img, anim.text_img("依据：", 26, DIM, "regular"), 110, yy + 34, "lt", ease_out(pp))
                for i, ln in enumerate(anim.wrap_text(self.basis, 26, 1080)):
                    anim.put(img, anim.text_img(ln, 26, SUB, "regular"), 190, yy + 34 + i * 38, "lt", ease_out(pp))
        return anim.vignette(img, 105)


TYPES = {}
TYPES.update(scenes.TYPES)
TYPES.update({
    "question": QuestionScene,
    "bigq": BigQuestion,
    "contradiction": Contradiction,
    "wall": EvidenceWall,
    "flow": Flow,
    "web": WebCard,
    "guess": GuessScene,
})
