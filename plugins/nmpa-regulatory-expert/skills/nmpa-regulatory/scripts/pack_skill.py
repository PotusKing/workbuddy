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
import re
import zipfile

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_NAME = os.path.basename(SKILL_ROOT)
VERSION = "1.3.1"

TOP_FILES = ["SKILL.md", "README.md"]
TOP_DIRS = ["references", "assets", "scripts"]
EXCLUDE_NAMES = {".DS_Store", "__pycache__", ".git"}
# 口径层例外：这些属于「作答能力」而非「原文库」，瘦身包也要带上。
#   - cmde-qa / official-qa：官方向答口径（605 条共性问题 + 168 问百问百答）
#   - qms 24–33：现行 GMP 体系（2025 版规范、2026 版总则+附录篇检查指导原则、
#     IVD/义齿附录、禁止委托目录）——判定与分级是答「查多少项、哪几项关键」的依据
#   - us-fda：美国参照层三层原文（法案 48 条 + 21 CFR 14 份 + guidance 600 份
#     清单与 45 份全文）。中美对照要能落到原文，否则只能凭印象。
KEEP_IN_SLIM = ["references/source-docs/cmde-qa",
                "references/source-docs/official-qa",
                "references/source-docs/us-fda"]
KEEP_FILE_RE = re.compile(r"^references/source-docs/qms/(2[4-9]|3[0-3])-")


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
            keep = any(rel == k or rel.startswith(k + os.sep) for k in KEEP_IN_SLIM)
            # 当前目录是保留路径的祖先（含按文件名保留的目录）时不能剪枝
            ancestor = any(k.startswith(rel + os.sep) for k in KEEP_IN_SLIM)
            has_file_rule = rel == "references/source-docs/qms"
            if (not with_source_docs and rel.startswith("references/source-docs")
                    and not keep and not ancestor and not has_file_rule):
                dirs[:] = []
                continue
            for fn in files:
                if fn in EXCLUDE_NAMES:
                    continue
                # 抓取中间产物（_index.json / _items.jsonl / _fetched.txt）不进包
                if fn.startswith("_") and fn.endswith((".json", ".jsonl", ".txt")):
                    continue
                rel_file = os.path.join(rel, fn)
                # source-docs 下只放行保留目录与预留文件名规则命中的文件
                if (not with_source_docs and rel_file.startswith("references/source-docs")
                        and not keep and not KEEP_FILE_RE.match(rel_file)):
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
        print("注：已排除 references/source-docs/ 原文库（保留 cmde-qa / official-qa 口径目录、"
              "qms/24-33 现行 GMP 体系、us-fda 三层原文：法案 48 条 + CFR 14 份 + guidance 清单与 45 份全文），"
              "收包方按 SKILL.md bootstrap 自建。")
    print("打包时间：%s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()
