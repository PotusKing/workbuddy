#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""US Code (FD&C Act) HTML -> Markdown

数据源：govinfo.gov 的 USCODE-{year}-title21 官方 GPO 版 HTML。
结构约定：
  <h3 class="section-head">§360c. Title</h3>
  <h4 class="subsection-head">(a) Sub</h4>
  <p class="statutory-body-…">正文</p>
  <p class="statutory-source">(...) 来源引注</p>
  <h4 class="note-head">注释标题</h4>
  <p class="note-body">注释正文</p>

段落 class 的 -1em / -2em / -3em 表示缩进层级，映射为 2 空格/级。
"""
import html as H
import os
import re
import sys

RE_HEAD = re.compile(r'<h3 class="section-head">(.*?)</h3>', re.S)
RE_PARTH = re.compile(r'<h3 class="part-head"[^>]*>(.*?)</h3>', re.S)
RE_SUBH = re.compile(r'<h4 class="subsection-head">(.*?)</h4>', re.S)
RE_NOTEH = re.compile(r'<h4 class="note-head">(.*?)</h4>', re.S)
RE_P = re.compile(r'<p class="([^"]+)">(.*?)</p>', re.S)

# 原生 HTML 实体在 <cap-smallcap> 里被拆开，先处理掉
RE_CAP = re.compile(r"<cap-smallcap>(.*?)</cap-smallcap>", re.S)
RE_TAG = re.compile(r"<[^>]+>")

DROP_CLASS = {"usc-social-medias", "img", "uscline"}


def _cap(m):
    """<cap-smallcap> 只把文字转大写，实体引用的名字不能跟着变。"""
    v = m.group(1).upper()
    for a, b in (("&MDASH;", "&mdash;"), ("&NDASH;", "&ndash;"),
                 ("&AMP;", "&amp;"), ("&SECT;", "&sect;"), ("&NBSP;", "&nbsp;")):
        v = v.replace(a, b)
    return v


def txt(s):
    """HTML 片段 -> 纯文本，只保留必要的空白语义。"""
    s = RE_CAP.sub(_cap, s)
    s = s.replace("<br/>", "\n").replace("<br />", "\n").replace("<br>", "\n")
    s = RE_TAG.sub("", s)
    s = H.unescape(s)
    s = s.replace("\u00a0", " ").replace("\u2002", " ").replace("\u2003", " ")
    s = s.replace("\u2014", "—").replace("\u2013", "–")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def indent_of(cls):
    """statutory-body-2em -> 4 空格"""
    m = re.search(r"-(\d)em$", cls)
    if m:
        return "  " * int(m.group(1))
    return ""


def para_md(cls, body):
    t = txt(body)
    if not t:
        return None
    t = t.replace("\n", " ").strip()
    if not t:
        return None
    ind = indent_of(cls)
    if ind:
        # 缩进层级用「无标记缩进行」，Grep 仍能命中，阅读上也能看出层级
        return ind + t
    return t


def split_sections(doc):
    """按 section-head 切块，返回 [(head_html, body_html), ...]"""
    ms = list(RE_HEAD.finditer(doc))
    out = []
    for i, m in enumerate(ms):
        ed = ms[i + 1].start() if i + 1 < len(ms) else len(doc)
        out.append((m.group(1), doc[m.end():ed]))
    return out


def sect_key(head):
    """'§360c–1. Reporting' -> '360c-1'；'§360bbb–3a.' -> '360bbb-3a'

    注意后缀字母：360bbb–0a / 360bbb–3c 这类如果只抓数字会把 a/c 丢掉，
    导致 360bbb–0、360bbb–0a 撞成同一个文件名。
    """
    s = txt(head)
    m = re.match(r"§+\s*([0-9]+[a-z]*(?:–[0-9]+[a-z]*)?)", s)
    if not m:
        return None
    return m.group(1).replace("–", "-")


def render(head, body, cn_note=None):
    """单节 -> Markdown 行列表"""
    h = txt(head).replace("§§", "§§ ")
    h = re.sub(r"^§\s*", "§ ", h)
    out = ["## %s" % h, ""]
    if cn_note:
        out += ["> %s" % cn_note, ""]

    # 依序扫描 h4 / p，保持原顺序
    # 条款层级：subsection (a) → paragraph (1) → subparagraph (A)
    #           → clause (i) → subclause (I)
    LEVEL = {
        "subsection-head":   "###",
        "paragraph-head":    "####",
        "subparagraph-head": "#####",
        "clause-head":       "**",
        "subclause-head":    "**",
    }
    parts = []
    rest = body
    last = 0
    pat = (r'<h4 class="(subsection-head|paragraph-head|subparagraph-head|'
           r'clause-head|subclause-head|note-head)">(.*?)</h4>')
    for m in re.finditer(pat, rest, re.S):
        parts.append(("p", rest[last:m.start()]))
        parts.append((m.group(1), m.group(2)))
        last = m.end()
    parts.append(("p", rest[last:]))

    in_notes = False
    for kind, chunk in parts:
        if kind in LEVEL:
            t = txt(chunk).replace("\n", " ").strip()
            if not t:
                continue
            if kind in ("clause-head", "subclause-head"):
                out += ["", "%s%s%s" % (LEVEL[kind], t, "**"), ""]
            else:
                out += ["", "%s %s" % (LEVEL[kind], t), ""]
        elif kind == "note-head":
            t = txt(chunk).replace("\n", " ").strip()
            if not in_notes:
                out += ["", "---", "", "**编纂与修订注释（Editorial Notes）**", ""]
                in_notes = True
            if t:
                out += ["#### %s" % t, ""]
        else:
            for pm in RE_P.finditer(chunk):
                cls, pb = pm.group(1), pm.group(2)
                base = cls.split()[0]
                if base in DROP_CLASS:
                    continue
                if base.startswith("statutory-source"):
                    v = txt(pb).replace("\n", " ").strip()
                    if v:
                        out += ["> 来源引注：%s" % v, ""]
                    continue
                if base.startswith("note-body") or base.startswith("footnote"):
                    v = txt(pb).replace("\n", " ").strip()
                    if v:
                        out += [v, ""]
                    continue
                v = para_md(base, pb)
                if v:
                    out += [v, ""]

    # 收连续空行
    md, blank = [], 0
    for ln in out:
        if not ln.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        md.append(ln.rstrip())
    return md


def main():
    src = sys.argv[1]
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    doc = open(src, encoding="utf-8", errors="replace").read()
    n = 0
    for head, body in split_sections(doc):
        k = sect_key(head) or ("x%d" % n)
        md = render(head, body)
        p = os.path.join(outdir, "sec%s.md" % k)
        open(p, "w", encoding="utf-8").write("\n".join(md) + "\n")
        n += 1
    print("sections written:", n, "->", outdir)


if __name__ == "__main__":
    main()
