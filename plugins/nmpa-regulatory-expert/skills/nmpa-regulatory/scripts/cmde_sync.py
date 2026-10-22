#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMDE 指导原则增量同步：只抓新增的正式发布稿，其余不动。

流程：全量刷一遍目录 -> 与 _index.json 比对 -> 只对新增条目抓正文 -> 重建索引 md。
耗时约 3–5 分钟（主要花在 37 页目录翻页上），日常每周跑一次足够。

用法：
  python cmde_sync.py            # 同步正式稿（默认）
  python cmde_sync.py --all      # 连征求意见稿一起同步
  python cmde_sync.py --dry-run  # 只报告新增，不下载
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cmde_crawl as C          # noqa: E402
import build_cmde_index as B    # noqa: E402


def load_old():
    if os.path.exists(C.INDEX_JSON):
        try:
            return json.load(open(C.INDEX_JSON))
        except Exception:
            return []
    return []


def main():
    dry = "--dry-run" in sys.argv
    every = "--all" in sys.argv

    old = load_old()
    old_urls = set(x["url"] for x in old)
    print("同步前目录 %d 条" % len(old))

    C.crawl_list()                      # 全量刷新目录（覆盖 _index.json）
    new = load_old()
    added = [x for x in new if x["url"] not in old_urls]
    formal_new = [x for x in added if x["section"] == "指导原则文本库"]
    print("发现新增：合计 %d（正式 %d、征求意见 %d）"
          % (len(added), len(formal_new), len(added) - len(formal_new)))

    if not added:
        B.main()
        return
    for x in (formal_new if not every else added)[:20]:
        print("  + %s" % x["title"])
    if len(formal_new) > 20:
        print("  ... 其余 %d 条" % (len(formal_new) - 20))

    if dry:
        print("（dry-run，不下载）")
        return

    if every:
        C.fetch_docs()
    else:
        # 只抓正式稿：临时按 section 过滤
        sys.argv = [sys.argv[0], "docs"]
        C.fetch_docs()
    B.main()
    print("同步完成。索引已更新。")


if __name__ == "__main__":
    main()
