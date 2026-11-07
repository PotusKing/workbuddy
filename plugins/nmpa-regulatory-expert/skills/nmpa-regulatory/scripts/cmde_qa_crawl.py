#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMDE「共性问题」全量抓取器（口径层数据源）。

为什么用它而不是微信公众号：
  各地药监局 / 第三方公众号里的「问题解答」，原始出处几乎都是
  器审中心官网「审评科学 > 共性问题」栏目。抓原件的好处是可溯源、
  有发布日期与供稿部门、不重复转载、不触发公众号的验证码风控。

技术要点（2026-11 实测）：
  cmde.org.cn 全站挂瑞数 WAF，纯 curl 返回 202 空壳。
  可行方案 = 真实 Chrome + 持久 profile + 先访首页拿挑战 cookie；
  headless 会被判死，必须 headless=False。

用法：
  python cmde_qa_crawl.py list              # 只抓目录 -> _index.json
  python cmde_qa_crawl.py all               # 目录 + 正文（增量，跳过已抓）
  python cmde_qa_crawl.py rebuild           # 只按已有 JSONL 重新生成 Markdown

产物：
  references/source-docs/cmde-qa/_index.json   目录（标题/链接/日期）
  references/source-docs/cmde-qa/_items.jsonl  正文逐条（增量追加）
  references/source-docs/cmde-qa/20XX.md       按年分组的问答正文
"""
import json
import os
import re
import time

BASE = "https://www.cmde.org.cn"
LIST = BASE + "/splt/ltgxwt/index.html"
SKILL = os.path.expanduser("~/.workbuddy/skills/nmpa-regulatory")
WORK = os.path.join(SKILL, "references", "source-docs", "cmde-qa")
PROFILE = "/tmp/cmde_profile"
IDX = os.path.join(WORK, "_index.json")
JSONL = os.path.join(WORK, "_items.jsonl")
MAX_PAGES = 200

# 正文区域前后固定噪声，按「发布时间：」到「供稿」裁切
RE_DATE = re.compile(r"发布时间：\s*(\d{4}-\d{2}-\d{2})")
RE_PROV = re.compile(r"\n\s*([\u4e00-\u9fa5]{2,10}(?:部|处|中心))\s*(?:供稿)?\s*$")


def clean_ws(s):
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_article(body_text, title):
    """从 inner_text 抽 发布日期 / 正文 / 供稿部门。"""
    t = clean_ws(body_text)
    m = RE_DATE.search(t)
    date = m.group(1) if m else ""
    if m:
        t = t[m.end():]
    # 尾部版式噪声从「地址：北京经济技术开发区」起截断
    cut = t.find("地址：北京经济技术开发区")
    if cut > 0:
        t = t[:cut]
    prov = ""
    mp = RE_PROV.search(t)
    if mp:
        prov = mp.group(1)
        t = t[: mp.start()]
    # 去掉重复的标题行
    lines = [ln.strip() for ln in t.split("\n")]
    lines = [ln for ln in lines if ln and ln != title]
    return date, prov, "\n".join(lines).strip()


def start(p):
    ctx = p.chromium.launch_persistent_context(
        PROFILE, headless=False, channel="chrome",
        args=["--disable-blink-features=AutomationControlled",
              "--window-position=2600,2600", "--window-size=1280,900"])
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, pg


def warmup(pg):
    try:
        pg.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(3500)
    except Exception:
        pass


def crawl_list(pg):
    items, seen = [], set()
    empty = 0
    for n in range(MAX_PAGES):
        url = LIST if n == 0 else LIST.replace("index.html", "index_%d.html" % n)
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(1200)
        except Exception as e:
            print("  ! 列表页失败", url, e)
            break
        rows = pg.eval_on_selector_all(
            "a", "els => els.map(e => [e.innerText.trim(), e.href])")
        page_items = []
        for title, href in rows:
            if not title or len(title) < 6:
                continue
            if not re.search(r"/splt/ltgxwt/\d{10,}\.html$", href):
                continue
            if href in seen:
                continue
            seen.add(href)
            page_items.append({"title": title, "url": href})
        print("  - 第 %d 页 %d 条" % (n, len(page_items)))
        if not page_items:
            empty += 1
            if empty >= 2:
                break
            continue
        empty = 0
        items.extend(page_items)
    return items


def html_to_text(frag):
    """HTML 片段 → 纯文本：段落保留换行，去掉标签与实体。"""
    frag = re.sub(r"(?i)<br\s*/?>", "\n", frag)
    frag = re.sub(r"(?i)</(p|div|h\d|li|tr)>", "\n", frag)
    frag = re.sub(r"<[^>]+>", "", frag)
    frag = (frag.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    return clean_ws(frag)


RE_TITLE = re.compile(r'<h2 class="title">(.*?)</h2>', re.S)
RE_DATEH = re.compile(r'<div class="date">\s*(.*?)</div>', re.S)
RE_CONTENT = re.compile(r'<meta name="ContentStart"/>(.*?)<meta name="ContentEnd"/>', re.S)
RE_TEXTDIV = re.compile(r'<div class="text">(.*?)</div>\s*$', re.S)


def parse_html(html, fallback_title):
    m = RE_TITLE.search(html)
    title = html_to_text(m.group(1)).strip() if m else fallback_title
    date = ""
    md = RE_DATEH.search(html)
    if md:
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", html_to_text(md.group(1)))
        date = dm.group(1) if dm else ""
    m = RE_CONTENT.search(html)
    frag = m.group(1) if m else ""
    mt = RE_TEXTDIV.search(frag)
    if mt:
        frag = mt.group(1)
    text = html_to_text(frag)
    prov = ""
    mp = RE_PROV.search("\n" + text)
    if mp:
        prov = mp.group(1)
        text = ("\n" + text)[: mp.start()].strip()
    return title, date, prov, text


def crawl_body(pg, it):
    """用浏览器上下文发请求（共享 WAF cookie），直接解析 HTML。约 0.1 s/篇。"""
    try:
        r = pg.context.request.get(it["url"], timeout=30000)
        if r.status != 200:
            print("  ! HTTP %d %s" % (r.status, it["url"]))
            return None
        html = r.text()
    except Exception as e:
        print("  ! 正文失败", it["url"], e)
        return None
    title, date, prov, ans = parse_html(html, it["title"])
    if not ans.strip():
        return None
    return {"title": title or it["title"], "url": it["url"], "date": date,
            "dept": prov, "answer": ans}


def load_done():
    done = set()
    if os.path.exists(JSONL):
        with open(JSONL, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(json.loads(line)["url"])
                except Exception:
                    pass
    return done


def rebuild():
    """按 JSONL 生成按年分组的 Markdown。"""
    rows = []
    if os.path.exists(JSONL):
        with open(JSONL, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    rows.sort(key=lambda r: (r.get("date") or "", r.get("url") or ""), reverse=True)
    years = {}
    for r in rows:
        y = (r.get("date") or "0000")[:4]
        years.setdefault(y, []).append(r)
    os.makedirs(WORK, exist_ok=True)
    for y, rs in sorted(years.items(), reverse=True):
        out = ["# CMDE 共性问题解答 · %s 年（%d 条）" % (y, len(rs)), "",
               "> 来源：国家药监局医疗器械技术审评中心官网「审评科学 > 共性问题」",
               "> 抓取方式：原始页面逐条解析，问=页面标题，答=正文原文，未改写未删节",
               "> 效力定位：**审评机构的公开答复口径**，不是法规、不是指导原则；",
               "> 可作审评预期与技术要求的参考，但不可表述为「法规要求必须」。",
               "> 同题若已有正式指导原则，指导原则优先。", ""]
        for r in rs:
            out.append("## %s" % r["title"])
            meta = "　".join(x for x in [r.get("date", ""),
                                        (r.get("dept", "") + " 供稿") if r.get("dept") else ""] if x)
            out.append("")
            out.append("> %s" % meta)
            out.append("")
            out.append("**问**：%s" % r["title"])
            out.append("")
            out.append("**答**：%s" % r["answer"].replace("\n", "\n> "))
            out.append("")
        path = os.path.join(WORK, "%s.md" % y)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        print("  -> %s（%d 条，%.1f KB）" % (os.path.basename(path), len(rs),
                                          os.path.getsize(path) / 1024))


def main():
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(WORK, exist_ok=True)

    if mode == "rebuild":
        rebuild()
        return

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx, pg = start(p)
        warmup(pg)
        items = crawl_list(pg)
        json.dump(items, open(IDX, "w"), ensure_ascii=False, indent=1)
        print("目录 %d 条 -> %s" % (len(items), IDX))
        if mode == "list":
            ctx.close()
            return
        done = load_done()
        todo = [x for x in items if x["url"] not in done]
        print("待抓正文 %d 条（已完成 %d）" % (len(todo), len(done)))
        with open(JSONL, "a", encoding="utf-8") as f:
            for i, it in enumerate(todo, 1):
                r = crawl_body(pg, it)
                if r:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    f.flush()
                if i % 50 == 0:
                    print("  ... %d/%d" % (i, len(todo)))
        ctx.close()
    rebuild()


if __name__ == "__main__":
    main()
