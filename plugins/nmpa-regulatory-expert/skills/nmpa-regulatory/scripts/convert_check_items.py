# -*- coding: utf-8 -*-
"""
把《医疗器械生产质量管理规范×××检查指导原则》docx（NMPA 附件）转成结构化 Markdown。

适用格式：单个大表格，列 = 章节 | 序号 | 条款 | 内容 | 风险等级 | 规范条款/附录条款
输出：按章分组的条目列表 + 统计 + 关键项速查

用法：
  python convert_check_items.py <in.docx> <out.md> --title "..." --meta "文号=国药监械管〔2026〕16号" ...
"""
import argparse
import os
import re
from collections import Counter, OrderedDict

import docx


def norm(s):
    return re.sub(r"[ \t]+", " ", (s or "").replace("\u3000", " ")).strip()


def load_rows(path):
    d = docx.Document(path)
    if not d.tables:
        raise SystemExit("未找到表格")
    t = d.tables[0]
    header = [norm(c.text) for c in t.rows[0].cells]
    idx = {}
    for i, h in enumerate(header):
        if "章节" in h:
            idx["chapter"] = i
        elif "序号" in h:
            idx["no"] = i
        elif "条款" in h:
            idx["clause"] = i
        elif "内容" in h:
            idx["content"] = i
        elif "风险" in h:
            idx["risk"] = i
        elif "依据" in h or "规范条款" in h:
            idx["ref"] = i
    need = {"chapter", "clause", "content", "risk"}
    if not need.issubset(idx):
        raise SystemExit("表头不匹配：%s" % header)
    rows = []
    for r in t.rows[1:]:
        cells = [norm(c.text) for c in r.cells]
        if not any(cells):
            continue
        rows.append({k: cells[i] for k, i in idx.items()})
    return rows


def risk_label(risk):
    """*** = 关键项，** = 主要项，* = 一般项。无法识别时原样返回。"""
    n = (risk or "").count("*")
    return {3: "关键", 2: "主要", 1: "一般"}.get(n, risk or "未标注")


def ch_name(s):
    """统一章节标题：'第一章总则' → '第一章 总则'"""
    s = (s or "").replace("\n", "").strip()
    return re.sub(r"^(第[一二三四五六七八九十百]+章)\s*", r"\1 ", s).strip()


def multiline(s, indent="  "):
    """表格单元格内的软换行 → Markdown 列表续行缩进，避免打断列表。"""
    parts = [p.strip() for p in (s or "").split("\n")]
    parts = [p for p in parts if p]
    return ("\n" + indent).join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--meta", action="append", default=[])
    args = ap.parse_args()

    rows = load_rows(args.docx)
    cnt = Counter(risk_label(r["risk"]) for r in rows)

    chapters = OrderedDict()
    for r in rows:
        ch = ch_name(r["chapter"])
        chapters.setdefault(ch, []).append(r)

    out = ["# %s" % args.title, ""]
    for m in args.meta:
        out.append("> %s" % m)
    out += [
        "> **入库方式**：NMPA 官网附件 .docx 原始表格逐行解析，列结构与原文一致"
        "（章节｜序号｜条款｜内容｜风险等级｜规范条款/附录条款），文字未删改",
        "",
        "## 检查项目统计",
        "",
        "| 合计 | 关键（***） | 主要（**） | 一般（*） |",
        "|---|---|---|---|",
        "| %d | %d | %d | %d |" % (len(rows), cnt["关键"], cnt["主要"], cnt["一般"]),
        "",
        "> 结果判定不在这份文件里——检查类型与判定遵循《医疗器械生产质量管理规范检查指导原则》"
        "（2026 年，总则篇），本文件只提供项目与分级。",
        "",
    ]

    for ch, items in chapters.items():
        out += ["## %s" % ch, ""]
        for r in items:
            ref = r.get("ref", "")
            line = "- **%s**（%s）%s" % (r["clause"], risk_label(r["risk"]), multiline(r["content"]))
            if ref:
                line += "　—《%s》" % ref.strip("《》")
            out.append(line)
        out.append("")

    out += ["## 关键项速查（%d 项）" % cnt["关键"], "",
            "| 条款 | 内容摘要 | 依据 |", "|---|---|---|"]
    for r in rows:
        if risk_label(r["risk"]) == "关键":
            c = multiline(r["content"]).replace("|", "｜").replace("\n", " ")
            out.append("| %s | %s | %s |" % (r["clause"], c, r.get("ref", "").replace("|", "｜")))
    out.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("%s → %d 项（关键 %d / 主要 %d / 一般 %d）｜%s"
          % (os.path.basename(args.docx), len(rows), cnt["关键"], cnt["主要"], cnt["一般"],
             round(os.path.getsize(args.out) / 1024, 1)))


if __name__ == "__main__":
    main()
