#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMDE 正文库瘦身：把「产品专用」指导原则移出技能目录，只保留通用/方法学类。
索引（cmde-guidelines-index.md）保持全量 736 条不变，移走的条目仍可一条命令抓回。

保留范围：
  域 ∈ {通用/方法学, 临床评价, 软件/AI, 灭菌/包装, 生物相容/生物学}
  或 标题命中通用关键词（使用期限、稳定性、可用性、风险管理、生物学评价…）

移出目标：~/.workbuddy/nmpa-cmde-archive/   （技能目录之外，不影响打包体积）
清单：    _archived.json（标题 + 原文链接 + 文件名，可据此恢复）

用法：
  python cmde_slim.py --dry-run   # 只统计，不动文件
  python cmde_slim.py             # 执行移动
  python cmde_slim.py --restore   # 全部移回
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_cmde_index import domain_of  # noqa: E402

SKILL = os.path.expanduser("~/.workbuddy/skills/nmpa-regulatory")
WORK = os.path.join(SKILL, "references", "source-docs", "cmde")
ARCH = os.path.expanduser("~/.workbuddy/nmpa-cmde-archive")
MANIFEST = os.path.join(WORK, "_archived.json")

KEEP_DOMAINS = {"通用/方法学", "临床评价", "软件/AI", "灭菌/包装", "生物相容/生物学"}
KEEP_WORDS = [
    "使用期限", "有效期", "货架", "稳定性", "可用性", "人因", "风险管理",
    "受益", "生物学评价", "生物相容", "灭菌", "无菌", "包装确认", "包装",
    "软件", "网络安全", "人工智能", "临床评价", "同品种", "技术审查",
    "申报资料", "注册单元", "分类界定", "命名", "说明书", "标签", "通用",
]


def safe(s, n=70):
    import re
    s = re.sub(r"[/\\:*?\"<>|\n\r\t]", "", s)
    return re.sub(r"\s+", "", s)[:n]


def keep(title):
    if domain_of(title) in KEEP_DOMAINS:
        return True
    return any(w in title for w in KEEP_WORDS)


def main():
    items = json.load(open(os.path.join(WORK, "_index.json")))
    formal = [x for x in items if x["section"] == "指导原则文本库"]
    keep_items = [x for x in formal if keep(x["title"])]
    move_items = [x for x in formal if not keep(x["title"])]
    print("正式稿 %d：保留 %d，移出 %d" % (len(formal), len(keep_items), len(move_items)))

    if "--restore" in sys.argv:
        mf = json.load(open(MANIFEST))
        n = 0
        for rec in mf:
            src = os.path.join(ARCH, rec["file"])
            dst = os.path.join(WORK, rec["file"])
            if os.path.exists(src):
                shutil.move(src, dst)
                n += 1
        os.remove(MANIFEST)
        # 恢复 _fetched.txt
        with open(os.path.join(WORK, "_fetched.txt"), "a") as f:
            for rec in mf:
                f.write(rec["url"] + "\n")
        print("已移回 %d 份" % n)
        return

    if "--dry-run" in sys.argv:
        for x in move_items[:15]:
            print("  - %s" % x["title"])
        print("  ...")
        total = 0
        kept = 0
        for x in formal:
            fn = "F-%s.md" % safe(x["title"])
            p = os.path.join(WORK, fn)
            if os.path.exists(p):
                if keep(x["title"]):
                    kept += os.path.getsize(p)
                else:
                    total += os.path.getsize(p)
        print("预计释放 %.1f MB，保留 %.1f MB" % (total / 1e6, kept / 1e6))
        return

    os.makedirs(ARCH, exist_ok=True)
    moved = []
    for x in move_items:
        fn = "F-%s.md" % safe(x["title"])
        src = os.path.join(WORK, fn)
        if not os.path.exists(src):
            continue
        shutil.move(src, os.path.join(ARCH, fn))
        moved.append({"title": x["title"], "url": x["url"], "file": fn})
    json.dump(moved, open(MANIFEST, "w"), ensure_ascii=False, indent=1)

    # _fetched.txt 只保留仍在库内的，移走的以后可 --only 重新抓
    keep_urls = set(x["url"] for x in keep_items)
    fe = os.path.join(WORK, "_fetched.txt")
    if os.path.exists(fe):
        lines = [l.strip() for l in open(fe) if l.strip()]
        open(fe, "w").write("\n".join(l for l in lines if l in keep_urls) + "\n")
    print("已移出 %d 份 -> %s" % (len(moved), ARCH))
    print("恢复：python cmde_slim.py --restore　或　cmde_crawl.py docs --only 关键词")


if __name__ == "__main__":
    main()
