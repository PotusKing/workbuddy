#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 guidance PDF -> Markdown

依赖 fetch_cdrh_guidance.py 产出的 /tmp/guidance_targets.json。
PDF 直链必须用真实 Chrome 的 request 上下文取；curl 直连会被 CDN 返回假 404。
文本层用 scripts/pdf_text.swift 抽（不 OCR，因为 CDRH guidance 都是文本型 PDF）。
"""
import json
import os
import re
import subprocess
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SKILL, "references", "source-docs", "us-fda", "guidance")
CACHE = "/tmp/cdrh_pdf"
PDFTEXT = os.path.join(SKILL, "scripts", "pdf_text.swift")
BASE = "https://www.fda.gov"


def safe(s):
    return re.sub(r"[／/\\:*?\"<>|]", "-", s)


def main():
    tg = json.load(open("/tmp/guidance_targets.json", encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            "/tmp/fda_profile", channel="chrome", headless=True,
            args=["--disable-blink-features=AutomationControlled"])
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(BASE + "/medical-devices", timeout=90000, wait_until="domcontentloaded")

        # 组内计数
        cnt = {}
        ok, bad = 0, []
        for i, t in enumerate(tg):
            grp = t["grp"]
            cnt[grp] = cnt.get(grp, 0) + 1
            gno = grp.split("-")[0]
            fn_base = "%s.%02d-%s" % (gno, cnt[grp], safe(t["cn"]))
            pdf_p = os.path.join(CACHE, fn_base + ".pdf")
            md_p = os.path.join(OUT, fn_base + ".md")
            if os.path.exists(md_p) and os.path.getsize(md_p) > 2000:
                print("  [skip] 已存在", fn_base)
                ok += 1
                continue
            if not t.get("pdf"):
                bad.append((fn_base, "无 PDF 链接"))
                continue
            # 1. 下载
            if not (os.path.exists(pdf_p) and os.path.getsize(pdf_p) > 5000):
                try:
                    r = ctx.request.get(BASE + t["pdf"], timeout=180000)
                    if r.status != 200 or len(r.body()) < 5000:
                        bad.append((fn_base, "HTTP %s len %s" % (r.status, len(r.body()))))
                        continue
                    open(pdf_p, "wb").write(r.body())
                except Exception as e:
                    bad.append((fn_base, "下载异常 %s" % type(e).__name__))
                    continue
            # 2. 抽文本
            tmp_md = pdf_p + ".md"
            try:
                rr = subprocess.run(["swift", PDFTEXT, pdf_p, tmp_md],
                                    capture_output=True, text=True, timeout=300)
            except subprocess.TimeoutExpired:
                bad.append((fn_base, "转换超时"))
                continue
            if not os.path.exists(tmp_md) or os.path.getsize(tmp_md) < 1000:
                bad.append((fn_base, "文本层为空 rc=%s %s" % (rr.returncode, rr.stdout.strip()[:60])))
                continue
            body = open(tmp_md, encoding="utf-8").read()
            head = [
                "<!-- 来源：%s%s -->" % (BASE, t["pdf"]),
                "<!-- 原题：%s -->" % t["title"],
                "<!-- 发布：%s（%s） -->" % (t["date"], t["status"]),
                "",
                "# %s" % t["cn"],
                "",
                "**原文标题**：%s" % t["title"],
                "",
                "**发布**：%s ｜ **状态**：%s" % (t["date"], t["status"]),
                "",
                "> 【为什么收这份】%s" % t["why"],
                "",
                "> 【阅读提示】以下是 PDF 原文的文本层抽取，保留了页序标记 `<!-- p.N -->`。"
                "FDA guidance 的法律效力是「非约束性建议」（nonbinding recommendations），"
                "表述为 *should / recommend / FDA believes*，不是 *must*。"
                "引用时请按「FDA 建议」而非「法规要求」处理 —— 这一点与中国的指导原则一致。",
                "",
                "---",
                "",
            ]
            open(md_p, "w", encoding="utf-8").write("\n".join(head) + body)
            ok += 1
            print("  [ok] %-58s %7d 字符" % (fn_base[:58], len(body)))
        ctx.close()
    print("\n完成 %d，失败 %d" % (ok, len(bad)))
    for f, w in bad:
        print("  FAIL", f, w)


if __name__ == "__main__":
    main()
