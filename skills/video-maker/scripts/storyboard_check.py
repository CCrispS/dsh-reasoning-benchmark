#!/usr/bin/env python3
"""检查 Markdown 文件里的分镜表：核算时长、检查旁白语速、统计插图引用，并可导出 CSV。

用法：
    python3 storyboard_check.py <分镜.md> [--speed 4.5] [--group-level 3]
                                [--images 50] [--csv <输出目录>]

  --speed        旁白语速，单位“字/秒”（默认 4.5）
  --group-level  按这一级标题分组合计时长（例如 3 表示每个 ### 集合计一次）
  --images       原稿插图总数；会列出从未被引用的“图N”
  --csv          把每张表导出为 <输出目录>/<序号>-<标题>.csv（带 BOM 的 UTF-8，Excel 可直接打开）

分镜表的判定：表头既有“时长”列，又有“镜号”“画面内容”“旁白”中的任意一列。
只用 Python 标准库，macOS、Windows、Linux 通用。
"""
import argparse
import csv
import re
import sys
from pathlib import Path

CJK = re.compile(r"[㐀-鿿豈-﫿]")
WORD = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:[.,]\d+)*")
IMG = re.compile(r"图\s*(\d+)")
IMAGE_TYPES = ("截图", "素材图", "照片", "档案", "图片")


def spoken_units(text):
    """要念出来的单位数：汉字 + 英文单词 + 数字，标点不计。"""
    return len(CJK.findall(text)) + len(WORD.findall(CJK.sub(" ", text)))


def parse_seconds(cell):
    cell = cell.strip()
    m = re.fullmatch(r"(\d+):(\d{1,2}(?:\.\d+)?)", cell)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.search(r"\d+(?:\.\d+)?", cell)
    return float(m.group()) if m else None


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def find_col(header, *keys):
    for i, h in enumerate(header):
        if any(k in h for k in keys):
            return i
    return None


def read_tables(text):
    """逐张产出分镜表：(所在各级标题, 表头, 数据行)。代码块里的内容会跳过。"""
    headings = {}
    lines = text.splitlines()
    i = 0
    fenced = False
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if fenced or line.lstrip().startswith("```"):
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            headings = {k: v for k, v in headings.items() if k < level}
            headings[level] = m.group(2).strip()
        if line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            header = split_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            if rows and find_col(header, "时长") is not None and find_col(header, "镜号", "画面内容", "旁白", "台词") is not None:
                yield dict(headings), header, rows
            continue
        i += 1


def fmt(sec):
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="分镜 Markdown 文件")
    ap.add_argument("--speed", type=float, default=4.5, help="旁白语速，字/秒，默认 4.5")
    ap.add_argument("--group-level", type=int, help="按这一级标题分组合计时长")
    ap.add_argument("--images", type=int, help="原稿插图总数，用于列出未引用的插图")
    ap.add_argument("--csv", help="把每张表导出为 CSV 到这个目录")
    a = ap.parse_args()

    text = Path(a.file).read_text(encoding="utf-8")
    grand, n_shots, issues, used = 0.0, 0, [], set()
    groups = {}
    out_dir = Path(a.csv) if a.csv else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for t_no, (heads, header, rows) in enumerate(read_tables(text), 1):
        c_id, c_dur = find_col(header, "镜号"), find_col(header, "时长")
        c_type, c_vis = find_col(header, "画面类型", "景别"), find_col(header, "画面内容")
        c_nar, c_cap = find_col(header, "旁白", "台词"), find_col(header, "字幕", "花字")
        name = heads[max(heads)] if heads else f"表{t_no}"
        total = 0.0
        for r in rows:
            r += [""] * (len(header) - len(r))
            sid = r[c_id] if c_id is not None else "?"
            dur = parse_seconds(r[c_dur])
            if dur is None:
                issues.append(f"{sid}: 时长无法识别 “{r[c_dur]}”")
                continue
            total += dur
            n_shots += 1
            for col in (c_vis, c_cap):
                if col is not None:
                    used.update(int(x) for x in IMG.findall(r[col]))
            nar = r[c_nar] if c_nar is not None else ""
            units = spoken_units(nar)
            if units and units / max(dur - 0.3, 0.1) > a.speed * 1.1:
                need = units / a.speed + 0.5
                issues.append(f"{sid}: 旁白 {units} 字 / {dur:g} 秒，超速；按 {a.speed} 字/秒至少需要 {need:.1f} 秒")
            kind = r[c_type] if c_type is not None else ""
            cap = spoken_units(r[c_cap]) if c_cap is not None else 0
            if not units and any(k in kind for k in IMAGE_TYPES) and dur < 4:
                issues.append(f"{sid}: 无旁白的素材图只停 {dur:g} 秒，观众读不完（建议 ≥4 秒）")
            if not units and "卡" in kind and cap and cap / dur > 8:
                issues.append(f"{sid}: 卡片 {cap} 字 / {dur:g} 秒，读不完（建议每秒 ≤8 字）")
        grand += total
        print(f"{t_no:>2}. {name}  —  {len(rows)} 镜，{fmt(total)}")
        if a.group_level and a.group_level in heads:
            g = heads[a.group_level]
            groups[g] = groups.get(g, 0.0) + total
        if out_dir:
            safe = re.sub(r'[\\/:*?"<>|\s]+', "_", name)[:40]
            with open(out_dir / f"{t_no:02d}-{safe}.csv", "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(r[: len(header)] for r in rows)

    if not n_shots:
        print("没有找到带“时长”列的分镜表。")
        sys.exit(1)
    if groups:
        print("\n分组合计：")
        for g, s in groups.items():
            print(f"  {g}: {fmt(s)}")
    print(f"\n总计 {n_shots} 镜，{fmt(grand)}（{grand:.0f} 秒）")
    if a.images:
        unused = [f"图{i}" for i in range(1, a.images + 1) if i not in used]
        print("未引用的插图：" + ("、".join(unused) if unused else "无"))
    if issues:
        print(f"\n需要处理的问题（{len(issues)}）：")
        for s in issues:
            print("  - " + s)
    else:
        print("\n未发现超速或停留过短的镜头。")
    if out_dir:
        print(f"\nCSV -> {out_dir}")


if __name__ == "__main__":
    main()
