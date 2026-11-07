#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eCFR XML → Markdown 转换器（美国 21 CFR 原文入库用）。

数据源：eCFR versioner API
  https://www.ecfr.gov/api/versioner/v1/full/{date}/title-21.xml?part={part}
  （必须带 --compressed，否则返回 406）

结构映射：
  DIV5/PART  → 文档标题
  DIV6/SUBPART → ##  Subpart X—...
  DIV8/SECTION → ### § 820.1 Scope
  P          → 段落正文（保留法规的 (a)(b)(1) 层级）

用法：
  python ecfr2md.py <in.xml> <out.md> --title "..." --meta "..." --meta "..."
"""
import argparse
import os
import re
import xml.etree.ElementTree as ET

TAG_DIV5, TAG_DIV6, TAG_DIV8 = "DIV5", "DIV6", "DIV8"


def txt(el):
    """取元素全部文本，去标签，收空白。"""
    s = "".join(el.itertext())
    s = (s.replace("\u2014", "—").replace("\u2019", "'").replace("\u201c", '"')
          .replace("\u201d", '"').replace("\u00a7", "§").replace("\u00a0", " "))
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def head_of(el):
    for ch in el:
        if ch.tag == "HEAD":
            return txt(ch)
    return ""


def walk(el, out, depth=0):
    for ch in el:
        if ch.tag == TAG_DIV6:
            h = head_of(ch)
            if h:
                out += ["", "## %s" % h, ""]
            walk(ch, out, depth + 1)
        elif ch.tag == TAG_DIV8:
            h = head_of(ch)
            if h:
                out += ["", "### %s" % h, ""]
            for p in ch:
                if p.tag in ("HEAD",):
                    continue
                if p.tag in ("P", "FP"):
                    t = txt(p)
                    if t:
                        out += [t, ""]
                elif p.tag == "EXTRACT":
                    t = txt(p)
                    if t:
                        out += ["> %s" % t, ""]
                else:
                    walk(p, out, depth + 1)
        elif ch.tag in ("AUTH", "SOURCE", "CITA"):
            t = txt(ch)
            if t:
                out.append("> %s" % t)
        else:
            walk(ch, out, depth + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml")
    ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--meta", action="append", default=[])
    a = ap.parse_args()

    tree = ET.parse(a.xml)
    root = tree.getroot()
    out = ["# %s" % a.title, ""]
    for m in a.meta:
        out.append("> %s" % m)
    out += ["> **入库方式**：eCFR（ecfr.gov）官方 XML 逐节点解析，条文文字未改写，仅做层级分行",
            ""]
    walk(root, out)

    # 收连续空行
    md, blank = [], 0
    for ln in out:
        if ln.strip() == "":
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        md.append(ln)

    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("%s → %s（%.1f KB）" % (os.path.basename(a.xml), os.path.basename(a.out),
                                os.path.getsize(a.out) / 1024))


if __name__ == "__main__":
    main()
