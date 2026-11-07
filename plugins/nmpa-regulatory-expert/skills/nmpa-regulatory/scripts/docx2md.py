#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用 docx → Markdown 转换（法规/附录原文入库用）。

特性：
  - 按段落顺序遍历，表格插在它实际出现的位置（不会全堆到文末）
  - 自动识别「第X部分 / 一、 / 2.1」层级做 Markdown 标题
  - 不改写任何文字，只补版式

用法：
  python docx2md.py <in.docx> <out.md> --title "标题" --meta "文号=xxx" --meta "施行=xxx"
"""
import argparse
import os
import re

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

# 「第一部分 范围和原则」「一、总则」「2.1 人员」
RE_PART = re.compile(r"^(第[一二三四五六七八九十]+部分)[\s　]*(.*)$")
RE_NUM1 = re.compile(r"^([一二三四五六七八九十]+、)\s*(.*)$")
RE_NUM2 = re.compile(r"^(\d+(?:\.\d+){0,2})\s+(\S.*)$")


def iter_block(doc):
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            yield Paragraph(child, doc)
        elif tag == "tbl":
            yield Table(child, doc)


def clean(s):
    return re.sub(r"[ \t\u3000]+", " ", (s or "").replace("\xa0", " ")).strip()


def table_md(t):
    rows = []
    for r in t.rows:
        cells = [clean(c.text).replace("|", "｜").replace("\n", " ") for c in r.cells]
        rows.append(cells)
    if not rows:
        return []
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "---|" * len(rows[0])]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--meta", action="append", default=[])
    a = ap.parse_args()

    doc = docx.Document(a.docx)
    out = ["# %s" % a.title, ""]
    for m in a.meta:
        out.append("> %s" % m)
    out += ["> **入库方式**：NMPA 官网公告附件 .docx 逐段解析，文字未经删改，仅做层级分行与表格还原",
            ""]

    seen_title = False
    for blk in iter_block(doc):
        if isinstance(blk, Table):
            out += [""] + table_md(blk) + [""]
            continue
        txt = clean(blk.text)
        if not txt:
            continue
        if not seen_title and txt in ("附件", a.title):
            seen_title = True
            continue
        style = (blk.style.name or "")
        if style.startswith("Heading"):
            lvl = style.replace("Heading ", "").strip()
            lvl = int(lvl) if lvl.isdigit() else 2
            out += ["", "#" * min(lvl + 1, 6) + " " + txt, ""]
            continue
        m = RE_PART.match(txt)
        if m and len(txt) < 30:
            out += ["", ("## %s %s" % (m.group(1), m.group(2))).strip(), ""]
            continue
        m = RE_NUM1.match(txt)
        if m and len(txt) < 40:
            out += ["", ("### %s %s" % (m.group(1), m.group(2))).strip(), ""]
            continue
        m = RE_NUM2.match(txt)
        if m:
            num, rest = m.group(1), m.group(2)
            # 「2.1 人员」这类小节标题：编号只有一段、整行短且不是完整句子
            if num.count(".") == 1 and len(rest) <= 12 and not rest.endswith("。"):
                out += ["", "### %s %s" % (num, rest), ""]
            elif len(rest) > 6:
                out += ["", "**%s** %s" % (num, rest), ""]
            else:
                out += [txt, ""]
            continue
        out += [txt, ""]

    # 收掉连续空行
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
    print("%s → %s（%.1f KB）" % (os.path.basename(a.docx), os.path.basename(a.out),
                                os.path.getsize(a.out) / 1024))


if __name__ == "__main__":
    main()
