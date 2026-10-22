#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMDE（国家药监局医疗器械技术审评中心）指导原则抓取器。

背景（2026-10 实测）：
  cmde.org.cn 全站挂瑞数 WAF。纯 curl/requests 一律 202 空壳；
  无痕模式 Playwright 也被判为自动化（返回空文档）。
  **可行方案 = 真实 Chrome + 持久化 profile + 先访首页拿挑战 cookie**，
  且正文不在 HTML 里，而在文章页挂的 .doc/.pdf 附件（附件路径不过 WAF，可 curl 直下）。

用法：
  python cmde_crawl.py list            # 抓全量目录 -> _index.json
  python cmde_crawl.py docs [--limit N] [--only 关键词]
  python cmde_crawl.py one <文章url>

产物：
  references/source-docs/cmde/_index.json   目录（标题/链接/栏目/日期）
  references/source-docs/cmde/F-*.md        正式发布稿正文
  references/source-docs/cmde/D-*.md        征求意见稿正文
"""
import json
import os
import re
import subprocess
import sys
import time
import zipfile

BASE = "https://www.cmde.org.cn"
SECTIONS = [
    ("/flfg/zdyz/zdyzwbk/", "指导原则文本库"),
    ("/flfg/zdyz/zqyjg/", "征求意见稿"),
]
SKILL = os.path.expanduser("~/.workbuddy/skills/nmpa-regulatory")
WORK = os.path.join(SKILL, "references", "source-docs", "cmde")
TMP = "/tmp/cmde_dl"
INDEX_JSON = os.path.join(WORK, "_index.json")
FETCHED = os.path.join(WORK, "_fetched.txt")
PROFILE = "/tmp/cmde_profile"


def start(p):
    """真实 Chrome + 持久 profile。无头模式会被 WAF 判死，必须 headless=False。"""
    ctx = p.chromium.launch_persistent_context(
        PROFILE, headless=False, channel="chrome",
        args=["--disable-blink-features=AutomationControlled",
              "--window-position=3000,3000", "--window-size=1200,800"])
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, pg


def warmup(pg):
    try:
        pg.goto(BASE + "/", wait_until="load", timeout=60000)
        pg.wait_for_timeout(3500)
    except Exception:
        pass


def open_page(pg, url, tries=3):
    """打开页面。正文/附件链接出现即返回，不固定 sleep，节省时间。"""
    for i in range(tries):
        try:
            pg.goto(url, wait_until="commit", timeout=45000)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5)
            continue
        try:
            pg.wait_for_selector(
                "a[href*='/directory/web/cmde/images/'], .content, #content",
                timeout=12000, state="attached")
        except Exception:
            pg.wait_for_timeout(1500)
        t = pg.inner_text("body")
        if len(t) > 200:
            return t
        time.sleep(1.5)
    return pg.inner_text("body")


def crawl_list():
    from playwright.sync_api import sync_playwright
    items = []
    with sync_playwright() as p:
        ctx, pg = start(p)
        warmup(pg)
        for path, label in SECTIONS:
            page_no = 0
            empty_streak = 0
            while page_no < 120:
                url = BASE + path + ("index.html" if page_no == 0 else "index_%d.html" % page_no)
                try:
                    # 列表页用轻量加载：等目录链接出现即可，不要用 open_page（它在等附件链接，会空等超时）
                    pg.goto(url, wait_until="commit", timeout=45000)
                    pg.wait_for_selector("a[href*='/flfg/zdyz/']", timeout=15000, state="attached")
                    pg.wait_for_timeout(400)
                except Exception as e:
                    print("  ! fail", url, e)
                    break
                rows = pg.eval_on_selector_all(
                    "a[href*='/flfg/zdyz/']",
                    "els => els.map(e => [e.innerText.trim(), e.href])")
                got, seen = [], set()
                for title, href in rows:
                    if not title or len(title) < 6:
                        continue
                    if re.search(r"index(_\d+)?\.html$", href):
                        continue
                    if not re.search(r"/zdyz/[a-z]+/\d{10,}\.html$", href):
                        continue
                    if href in seen:
                        continue
                    seen.add(href)
                    got.append({"title": title, "url": href, "section": label})
                print("  - %s p%d: %d 条" % (label, page_no, len(got)))
                if not got:
                    empty_streak += 1
                    if empty_streak >= 2:
                        break
                else:
                    empty_streak = 0
                    items.extend(got)
                page_no += 1
                time.sleep(0.6)
        ctx.close()
    seen, uniq = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    os.makedirs(WORK, exist_ok=True)
    json.dump(uniq, open(INDEX_JSON, "w"), ensure_ascii=False, indent=1)
    print("总计 %d 条 -> %s" % (len(uniq), INDEX_JSON))


def doc_links(pg):
    return pg.eval_on_selector_all(
        "a[href*='/directory/web/cmde/images/']",
        "els => els.map(e => e.href)")


def to_text(path):
    """doc/docx/pdf -> 纯文本"""
    p = path.lower()
    if p.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
        except Exception:
            return ""
    if p.endswith(".docx"):
        try:
            z = zipfile.ZipFile(path)
            from xml.etree import ElementTree as ET
            W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            root = ET.fromstring(z.read("word/document.xml"))
            out = []
            for para in root.iter(W + "p"):
                t = "".join(n.text or "" for n in para.iter(W + "t"))
                if t.strip():
                    out.append(t.strip())
            return "\n".join(out)
        except Exception:
            return ""
    # doc
    try:
        r = subprocess.run(["textutil", "-convert", "txt", "-encoding", "UTF-8",
                            "-stdout", path], capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "ignore")
    except Exception:
        return ""


def clean(txt):
    txt = txt.replace("\u3000", " ").replace("\ufeff", "")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    lines = [x.strip() for x in txt.split("\n")]
    return "\n".join(x for x in lines if x).strip()


def safe(s, n=70):
    s = re.sub(r"[/\\:*?\"<>|\n\r\t]", "", s)
    return re.sub(r"\s+", "", s)[:n]


def fetch_docs(limit=None, only=None):
    from playwright.sync_api import sync_playwright
    items = json.load(open(INDEX_JSON))
    done = set()
    if os.path.exists(FETCHED):
        done = set(x.strip() for x in open(FETCHED) if x.strip())
    todo = [x for x in items if x["url"] not in done and (not only or only in x["title"])]
    if not only and "--all" not in sys.argv:
        todo = [x for x in todo if x["section"] == "指导原则文本库"]
    # 被瘦身移出的产品专用稿不自动抓回（除非明确 --only 指定或 --restore）
    arch = os.path.join(WORK, "_archived.json")
    if (not only) and os.path.exists(arch) and "--restore" not in sys.argv:
        try:
            skipped = set(r["url"] for r in json.load(open(arch)))
            before = len(todo)
            todo = [x for x in todo if x["url"] not in skipped]
            if before != len(todo):
                print("跳过已归档的 %d 篇（需要时用 --only 关键词 单独抓）" % (before - len(todo)))
        except Exception:
            pass
    if limit:
        todo = todo[:limit]
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    print("待抓 %d 篇" % len(todo))
    ok = fail = 0
    with sync_playwright() as p:
        ctx, pg = start(p)
        warmup(pg)
        for i, it in enumerate(todo, 1):
            try:
                open_page(pg, it["url"])
                links = doc_links(pg)
                if not links:
                    print("  ! 无附件：", it["title"][:40])
                    fail += 1
                    continue
                url = links[0]
                ext = os.path.splitext(url)[1].lower() or ".doc"
                tmp = os.path.join(TMP, "x" + ext)
                r = subprocess.run(["curl", "-sL", "-m", "180", "-A", "Mozilla/5.0",
                                    "-o", tmp, url], capture_output=True)
                txt = clean(to_text(tmp))
                if len(txt) < 200:
                    print("  ! 正文过短：", it["title"][:40], len(txt))
                    fail += 1
                    continue
                pre = "F" if it["section"] == "指导原则文本库" else "D"
                fn = "%s-%s.md" % (pre, safe(it["title"]))
                head = ("> **来源**：%s\n> **附件**：%s\n> **栏目**：%s\n> **抓取**：%s\n\n---\n\n"
                        % (it["url"], url, it["section"], time.strftime("%Y-%m-%d")))
                open(os.path.join(WORK, fn), "w", encoding="utf-8").write(
                    "# " + it["title"] + "\n\n" + head + txt + "\n")
                open(FETCHED, "a").write(it["url"] + "\n")
                ok += 1
            except Exception as e:
                print("  ! err", it["title"][:30], e)
                fail += 1
            if i % 10 == 0:
                print("  ... %d/%d (ok=%d fail=%d)" % (i, len(todo), ok, fail))
            time.sleep(0.5)
        ctx.close()
    print("完成 ok=%d fail=%d -> %s" % (ok, fail, WORK))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    args = sys.argv[2:]
    if cmd == "list":
        crawl_list()
    elif cmd == "docs":
        limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
        only = args[args.index("--only") + 1] if "--only" in args else None
        fetch_docs(limit, only)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
