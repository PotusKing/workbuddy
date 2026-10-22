# -*- coding: utf-8 -*-
"""
打包 nmpa-regulatory 技能，产出可分发的 zip。

默认排除 references/source-docs/（法规、标准、官方答复、指导原则正文，约 8.5MB）——
索引层与口径层完整，缺原文库不影响作答，收包方可按 SKILL.md 的 bootstrap 自建。
需要连原文库一起打包时加 --with-source-docs。

用法：
  python scripts/pack_skill.py                       # 瘦身包 → dist/
  python scripts/pack_skill.py --with-source-docs    # 全量包
  python scripts/pack_skill.py --out /tmp/xx.zip
"""
import argparse
import datetime
import os
import zipfile

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_NAME = os.path.basename(SKILL_ROOT)
VERSION = "1.0.0"

TOP_FILES = ["SKILL.md", "README.md"]
TOP_DIRS = ["references", "assets", "scripts"]
EXCLUDE_NAMES = {".DS_Store", "__pycache__", ".git"}


def collect(with_source_docs):
    out = []
    for f in TOP_FILES:
        p = os.path.join(SKILL_ROOT, f)
        if os.path.isfile(p):
            out.append(p)
    for d in TOP_DIRS:
        base = os.path.join(SKILL_ROOT, d)
        for root, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in EXCLUDE_NAMES]
            rel = os.path.relpath(root, SKILL_ROOT)
            if not with_source_docs and rel.startswith("references/source-docs"):
                dirs[:] = []
                continue
            for fn in files:
                if fn in EXCLUDE_NAMES:
                    continue
                out.append(os.path.join(root, fn))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--with-source-docs", action="store_true")
    args = ap.parse_args()

    suffix = "full" if args.with_source_docs else "slim"
    out = args.out or os.path.join(
        SKILL_ROOT, "..", "..", "dist",
        "%s-v%s-%s.zip" % (SKILL_NAME, VERSION, suffix))
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    files = collect(args.with_source_docs)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            arc = os.path.join(SKILL_NAME, os.path.relpath(p, SKILL_ROOT))
            z.write(p, arc)

    # 汇总
    size = os.path.getsize(out)
    md = [p for p in files if p.endswith(".md")]
    by = {}
    for p in files:
        rel = os.path.relpath(p, SKILL_ROOT)
        key = rel.split(os.sep)[0]
        by[key] = by.get(key, 0) + os.path.getsize(p)
    print("打包完成：%s" % out)
    print("文件 %d 个（其中 md %d 篇）｜zip %.2f MB" % (len(files), len(md), size / 1048576.0))
    for k in sorted(by):
        print("  %-12s %7.1f KB" % (k, by[k] / 1024.0))
    if not args.with_source_docs:
        print("注：已排除 references/source-docs/（原文库），收包方按 SKILL.md bootstrap 自建。")
    print("打包时间：%s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()
