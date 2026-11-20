#!/usr/bin/env python3
"""从 Word 稿件（.docx）中抽取正文和插图，放进分镜项目目录。

用法：
    python3 extract_docx.py <稿件.docx> <项目目录>

输出：
    <项目目录>/manuscript.md          正文，每段一行；插图位置标成 [图N]
    <项目目录>/assets/imgNN.<扩展名>   插图，按在文中出现的顺序编号
    <项目目录>/assets/image_index.md  插图索引表，每张图一行，附前文便于定位，其余列待人工填写

只用 Python 标准库，macOS、Windows、Linux 通用。
"""
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
W = "{%s}" % NS["w"]
R_EMBED = "{%s}embed" % NS["r"]
R_ID = "{%s}id" % NS["r"]


def load_rels(z):
    rels = {}
    try:
        root = ET.fromstring(z.read("word/_rels/document.xml.rels"))
    except KeyError:
        return rels
    for rel in root.findall("rel:Relationship", NS):
        target = rel.get("Target", "")
        if rel.get("TargetMode") == "External":
            continue
        rels[rel.get("Id")] = posixpath.normpath(posixpath.join("word", target))
    return rels


def paragraph_items(p):
    """按文档顺序逐个产出段落里的文字 ('text', 文本) 和图片 ('image', 关系编号)。"""
    for el in p.iter():
        tag = el.tag
        if tag == W + "t" and el.text:
            yield "text", el.text
        elif tag == W + "tab":
            yield "text", "\t"
        elif tag in (W + "br", W + "cr"):
            yield "text", "\n"
        elif tag == "{%s}blip" % NS["a"] and el.get(R_EMBED):
            yield "image", el.get(R_EMBED)
        elif tag == "{%s}imagedata" % NS["v"] and el.get(R_ID):
            yield "image", el.get(R_ID)


def heading_level(p):
    lvl = p.find("w:pPr/w:outlineLvl", NS)
    if lvl is not None and lvl.get(W + "val", "").isdigit() and int(lvl.get(W + "val")) < 6:
        return int(lvl.get(W + "val")) + 1
    st = p.find("w:pPr/w:pStyle", NS)
    style = (st.get(W + "val", "") if st is not None else "").lower().replace(" ", "")
    m = re.fullmatch(r"(?:heading|标题)?([1-6])", style)
    return int(m.group(1)) if m else 0


def paragraphs(el):
    """按阅读顺序产出段落；不进入段落内部，文本框里的文字随所在段落一起处理。"""
    for child in el:
        if child.tag == W + "p":
            yield child
        else:
            yield from paragraphs(child)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(src) as z:
        rels = load_rels(z)
        body = ET.fromstring(z.read("word/document.xml")).find("w:body", NS)
        lines, index_rows = [], []
        seen = {}
        n = 0
        prev_text = ""
        for p in paragraphs(body):
            parts = []
            for kind, val in paragraph_items(p):
                if kind == "text":
                    parts.append(val)
                    continue
                target = rels.get(val)
                if not target:
                    continue
                if target in seen:  # 同一张图重复出现：沿用第一次的编号
                    parts.append(f"[图{seen[target]}]")
                    continue
                n += 1
                seen[target] = n
                ext = Path(target).suffix.lower() or ".png"
                name = f"img{n:02d}{ext}"
                (assets / name).write_bytes(z.read(target))
                parts.append(f"[图{n}]")
                ctx = "".join(parts[:-1]).strip() or prev_text
                index_rows.append((n, name, ctx[-40:].replace("|", "｜")))
            text = "".join(parts).strip()
            if not text:
                continue
            level = heading_level(p)
            lines.append(("#" * level + " " if level else "") + text)
            if not re.fullmatch(r"(\[图\d+\])+", text):
                prev_text = text

    (out / "manuscript.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    rows = ["| 图 | 文件 | 前文（定位用） | 类型 | 内容要点 | 日期/来源 | 需打码 |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    rows += [f"| 图{i} | {f} | {c} | | | | |" for i, f, c in index_rows]
    (assets / "image_index.md").write_text(
        "# 插图索引\n\n逐张查看图片后填写后四列。\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    chars = sum(len(re.sub(r"\s|\[图\d+\]", "", l)) for l in lines)
    print(f"段落：{len(lines)}  字数：{chars}  插图：{n}")
    print(f"正文 -> {out / 'manuscript.md'}\n插图 -> {assets}")


if __name__ == "__main__":
    main()
