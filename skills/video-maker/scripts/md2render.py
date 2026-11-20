#!/usr/bin/env python3
"""把 Markdown 分镜表转成渲染 JSON（供 render_video.py 使用）。只用标准库。

用法：
  python3 scripts/md2render.py 分镜.md --assets <素材目录> -o video.json
  python3 scripts/md2render.py 系列.md --assets <素材目录> --section E1 -o e1.json
  python3 scripts/md2render.py 分镜.md --assets <素材目录> --style-meta theme=light,width=1080,height=1920 -o v.json
  python3 scripts/md2render.py 分镜.md --list-sections          # 列出文件里的标题，方便选 --section

表头按关键字识别：镜号、时长、画面类型（或景别）、运镜（或动效）、画面内容、旁白（或台词）、
字幕（花字）、声音/备注。约定详见 references/rendering.md。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

TYPE_KEYS = [
    ("image", ["长截图", "截图", "素材图", "照片", "档案", "图片", "网页"]),
    ("text", ["字卡", "文字卡", "要点卡", "列表卡"]),
    ("chapter", ["章节卡", "章节"]),
    ("quote", ["引文卡", "引用卡", "声明卡", "引文"]),
    ("data", ["数据卡", "数字卡"]),
    ("split", ["分屏", "对比卡", "对比"]),
    ("timeline", ["时间线", "时间轴"]),
    ("title", ["标题卡", "片头", "封面"]),
    ("end", ["片尾", "结尾卡"]),
    ("placeholder", ["实拍", "录屏", "动画", "出镜", "历史影像", "影像", "空镜", "地图", "示意图", "图解",
                     "视频", "采访", "航拍", "特写", "近景", "中景", "全景", "远景"]),
]
MOTION_KEYS = [
    ("static", ["固定", "静止", "定格", "不动"]),
    ("push", ["缓推", "推近", "推进", "推"]),
    ("pull", ["缓拉", "拉远", "拉出", "拉"]),
    ("left", ["左移", "左摇", "向左"]),
    ("right", ["右移", "右摇", "向右"]),
    ("down", ["下移", "下滚", "向下滚动", "滚动", "下摇", "向下"]),
    ("up", ["上移", "上滚", "上摇", "向上"]),
]
COLS = {
    "id": ["镜号", "编号", "序号"],
    "dur": ["时长", "秒"],
    "type": ["画面类型", "景别", "类型"],
    "motion": ["运镜", "动效", "镜头运动"],
    "content": ["画面内容", "画面描述", "画面"],
    "narr": ["旁白", "台词", "配音", "解说", "口播"],
    "text": ["字幕", "花字", "屏幕文字"],
    "note": ["声音", "备注", "音乐", "音效"],
}
MEDIA_EXT = r"(?:mp4|mov|mkv|webm|m4v|png|jpe?g|webp|gif|bmp)"


def first_hit(text, table):
    """返回 text 中最早出现的关键字所属类别；同位置取更长的关键字。"""
    best = None
    for name, keys in table:
        for k in keys:
            i = text.find(k)
            if i >= 0 and (best is None or i < best[0] or (i == best[0] and len(k) > best[1])):
                best = (i, len(k), name)
    return best[2] if best else None


def clean(s):
    s = s.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = s.replace("\\|", "|")
    return s.strip()


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells, cur, i = [], "", 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur += "\\|"
            i += 2
            continue
        if c == "|":
            cells.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    cells.append(cur)
    return [clean(c) for c in cells]


def map_cols(header):
    out = {}
    for idx, h in enumerate(header):
        hh = h.replace(" ", "")
        for key in ["id", "dur", "type", "motion", "narr", "text", "content", "note"]:
            if key in out:
                continue
            if any(k in hh for k in COLS[key]):
                # "画面类型/景别" 不能被当成 "画面内容"
                if key == "content" and any(k in hh for k in COLS["type"]):
                    continue
                if key == "dur" and "镜号" in hh:
                    continue
                out[key] = idx
                break
    return out


def parse_md(text):
    """返回 [(heading_path, table_rows_as_dicts)]，heading_path 为 [(level, title), ...]"""
    lines = text.splitlines()
    heads = []
    tables = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1))
            heads = [h for h in heads if h[0] < lvl] + [(lvl, m.group(2).strip())]
            i += 1
            continue
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            header = split_row(ln)
            cols = map_cols(header)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                rows.append({k: (cells[j] if j < len(cells) else "") for k, j in cols.items()})
                i += 1
            if "narr" in cols or "content" in cols:
                tables.append((list(heads), rows, i))
            continue
        i += 1
    return tables


def section_filter(text, key):
    """取标题含 key 的那一节（到下一个同级或更高级标题为止）"""
    lines = text.splitlines()
    out, on, lvl = [], False, 0
    for ln in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            l = len(m.group(1))
            if on and l <= lvl:
                break
            if not on and key in m.group(2):
                on, lvl = True, l
        if on:
            out.append(ln)
    return "\n".join(out), (lvl if on else 0)


def parse_dur(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|秒|″)?", s or "")
    if not m:
        m2 = re.search(r"(\d+):(\d{2})", s or "")
        if m2:
            return int(m2.group(1)) * 60 + int(m2.group(2))
        return None
    if re.search(r"(\d+):(\d{2})", s):
        m2 = re.search(r"(\d+):(\d{2})", s)
        return int(m2.group(1)) * 60 + int(m2.group(2))
    return float(m.group(1))


def image_refs(content):
    refs = []
    for m in re.finditer(r"(?:原稿)?图\s*(\d+)(?:\s*[、,，和与及/~\-–至]\s*(\d+))*", content):
        nums = re.findall(r"\d+", m.group(0))
        span = m.group(0)
        if re.search(r"\d+\s*[~\-–至]\s*\d+", span) and len(nums) == 2:
            a, b = int(nums[0]), int(nums[1])
            if 0 < b - a < 12:
                nums = [str(n) for n in range(a, b + 1)]
        for n in nums:
            r = "图%d" % int(n)
            if r not in refs:
                refs.append(r)
    return refs


def media_ref(content, md_dir):
    for m in re.finditer(r"([^\s：:，,（）()「」\"'`]+\.%s)\b" % MEDIA_EXT, content, re.I):
        p = m.group(1)
        cand = Path(p) if Path(p).is_absolute() else md_dir / p
        if cand.is_file():
            return p
    return None


def split_card(text):
    t = text.strip()
    parts = re.split(r"\s*[／]\s*|\s+/\s+", t, maxsplit=1)
    title = parts[0].strip()
    sub = parts[1].strip() if len(parts) > 1 else ""
    return title, sub


def items_of(text):
    return [x.strip() for x in re.split(r"[；;\n]", text) if x.strip()]


def build_shot(row, idx, md_dir):
    content = row.get("content", "")
    tcell = row.get("type", "")
    typ = first_hit(tcell, TYPE_KEYS) or first_hit(content[:12], TYPE_KEYS)
    refs = image_refs(content)
    media = media_ref(content, md_dir)
    if not typ:
        typ = "image" if refs else "placeholder"
    if typ == "placeholder" and media:
        typ = "media"
    elif typ == "placeholder" and refs:
        # 例如「特写：原稿图5」——有原稿图就当图片镜头
        typ = "image"
    motion = first_hit(row.get("motion", ""), MOTION_KEYS)
    txt = row.get("text", "")
    shot = {"id": row.get("id") or str(idx + 1), "type": typ}
    d = parse_dur(row.get("dur", ""))
    if d:
        shot["duration"] = d
    if refs:
        shot["images"] = refs
    if media:
        shot["media"] = media
    if motion:
        shot["motion"] = motion
    card = {}
    if typ in ("text", "chapter", "quote", "data", "title", "end"):
        src = txt or re.sub(r"^[^：:]{0,6}[：:]", "", content).strip()
        if typ == "text" and ("；" in src or ";" in src):
            head, rest = (src.split("：", 1) + [""])[:2] if re.match(r"^[^；;]{1,16}：", src) else ("", src)
            card["title"] = head.strip()
            card["items"] = items_of(rest)
        else:
            title, sub = split_card(src)
            if typ == "chapter":
                m = re.match(r"^((?:第[一二三四五六七八九十\d]+[章节集部篇])|(?:E\d+)|(?:Part\s*\d+))[\s·:：]*(.+)$", title)
                if m:
                    card["kicker"], title = m.group(1), m.group(2)
            card["title"] = title
            if sub:
                if typ == "data" and ("；" in sub):
                    its = items_of(sub)
                    card["sub"], card["items"] = its[0], its[1:]
                else:
                    card["sub"] = sub
    elif typ == "timeline":
        src = txt or content
        head = ""
        m = re.match(r"^([^；;：:]{1,20})[／]\s*(.+)$", src)
        if m:
            head, src = m.group(1), m.group(2)
        card["title"] = head.strip()
        card["items"] = items_of(src)
    elif typ == "split":
        src = txt or ""
        title = ""
        if "／" in src:
            title, src = src.split("／", 1)
        if "｜" in src or "|" in src:
            l, r = re.split(r"[｜|]", src, maxsplit=1)
            card["left"], card["right"] = l.strip(), r.strip()
        elif src.strip():
            title = (title + " " + src).strip()
        if title.strip():
            card["title"] = title.strip()
    elif typ == "placeholder":
        card["title"] = "待补素材"
        card["sub"] = content
    else:  # 图片 / 外部媒体
        if txt:
            shot["caption"] = txt
        if typ == "media" and not media:
            shot["type"] = "placeholder"
            shot["card"] = {"title": "待补素材", "sub": content}
    if card:
        shot["card"] = card
    narr = row.get("narr", "").strip()
    narr = re.sub(r"[（(](?:停顿|停|音乐|无旁白|静音)[^）)]*[）)]", "", narr).strip()
    if narr in ("—", "-", "无", "（无）", "/"):
        narr = ""
    if narr:
        shot["narration"] = narr
    if content:
        shot["content"] = content
    if row.get("note"):
        shot["note"] = row["note"]
    return shot


def main():
    ap = argparse.ArgumentParser(description="Markdown 分镜表 → 渲染 JSON")
    ap.add_argument("md")
    ap.add_argument("--assets", help="素材目录（内含 assets.json 时自动作为素材清单）")
    ap.add_argument("-o", "--out", help="输出 JSON，默认与 md 同名 .json")
    ap.add_argument("--section", help="只取标题含该关键字的一节，例如 E1 或 完整版")
    ap.add_argument("--title", help="视频标题（默认取节标题或文件名）")
    ap.add_argument("--style-meta", action="append", default=[],
                    help="写入 meta 的键值：JSON 对象，或 key=value[,key=value]，可重复")
    ap.add_argument("--list-sections", action="store_true", help="列出标题及其下的镜头数")
    args = ap.parse_args()

    md_path = Path(args.md).resolve()
    text = md_path.read_text(encoding="utf-8")
    if args.list_sections:
        for heads, rows, _ in parse_md(text):
            print("%-60s %3d 镜" % (" > ".join(h[1] for h in heads) or "(无标题)", len(rows)))
        return
    title = args.title
    if args.section:
        sub, lvl = section_filter(text, args.section)
        if not sub:
            sys.exit("错误：找不到标题含「%s」的小节；用 --list-sections 查看" % args.section)
        text = sub
        if not title:
            m = re.match(r"^#{1,6}\s+(.*)$", sub.splitlines()[0])
            title = m.group(1).strip() if m else args.section
    tables = parse_md(text)
    if not tables:
        sys.exit("错误：没有找到分镜表（需要含「镜号/时长/画面内容/旁白」等列的 Markdown 表格）")
    shots = []
    for heads, rows, _ in tables:
        for r in rows:
            if not any(v.strip() for v in r.values()):
                continue
            shots.append(build_shot(r, len(shots), md_path.parent))
    out = Path(args.out).resolve() if args.out else md_path.with_suffix(".json")
    meta = {"title": title or md_path.stem, "width": 1920, "height": 1080, "fps": 30, "theme": "dark", "tts": "auto"}
    if args.assets:
        ad = Path(args.assets).resolve()
        if not ad.is_dir():
            sys.exit("错误：素材目录不存在：%s" % ad)
        meta["assets_dir"] = os.path.relpath(ad, out.parent).replace("\\", "/")
        if (ad / "assets.json").is_file():
            meta["assets_manifest"] = os.path.relpath(ad / "assets.json", out.parent).replace("\\", "/")
    for sm in args.style_meta:
        sm = sm.strip()
        if sm.startswith("{"):
            meta.update(json.loads(sm))
        else:
            for kv in sm.split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    v = v.strip()
                    try:
                        v = json.loads(v)
                    except ValueError:
                        pass
                    meta[k.strip()] = v
    out.write_text(json.dumps({"meta": meta, "shots": shots}, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(s.get("duration") or 0 for s in shots)
    kinds = {}
    for s in shots:
        kinds[s["type"]] = kinds.get(s["type"], 0) + 1
    print("已写出 %s：%d 镜，分镜标注时长合计 %.0f 秒；类型 %s" % (out, len(shots), total,
          "、".join("%s×%d" % kv for kv in kinds.items())))
    miss = [s["id"] for s in shots if s["type"] == "placeholder"]
    if miss:
        print("占位镜头（待补素材）：%s" % "、".join(miss))


if __name__ == "__main__":
    main()
