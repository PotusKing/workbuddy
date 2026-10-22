#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 _index.json 生成 references/cmde-guidelines-index.md（供 skill 检索用）。"""
import json, os, re, io, time
from collections import defaultdict

SKILL = os.path.expanduser("~/.workbuddy/skills/nmpa-regulatory")
WORK = os.path.join(SKILL, "references", "source-docs", "cmde")
IDX = os.path.join(WORK, "_index.json")
OUT = os.path.join(SKILL, "references", "cmde-guidelines-index.md")
FE = os.path.join(WORK, "_fetched.txt")

# 标题关键词 -> 域（用于分组，一个条目可命中多个域，取第一个）
DOMAINS = [
    ("软件/AI", ["软件", "人工智能", "网络", "网络安全", "算法", "深度学习", "大模型", "数据集"]),
    ("IVD", ["试剂", "体外诊断", "校准品", "质控品", "检测", "测定", "诊断"]),
    ("无源/材料", ["敷料", "导管", "支架", "缝合", "植入", "陶瓷", "高分子", "胶原", "无源", "口腔", "义齿", "缝线", "膜"]),
    ("有源/电气", ["有源", "电气", "激光", "超声", "监护", "除颤", "输注", "影像", "磁共振", "CT", "射线", "内窥镜", "能量"]),
    ("临床评价", ["临床评价", "临床试验", "同品种"]),
    ("生物相容/生物学", ["生物学评价", "生物相容"]),
    ("灭菌/包装", ["灭菌", "无菌", "包装", "微生物", "洁净"]),
    ("通用/方法学", ["通用", "技术审查", "申报资料", "研究资料", "稳定性", "可用性", "风险管理", "受益", "人因", "货架"]),
]


def domain_of(title):
    for name, kws in DOMAINS:
        if any(k in title for k in kws):
            return name
    return "其他产品类"


def main():
    items = json.load(open(IDX))
    fetched = set()
    if os.path.exists(FE):
        fetched = set(x.strip() for x in open(FE) if x.strip())

    by_sec = defaultdict(list)
    for it in items:
        by_sec[it["section"]].append(it)

    out = ["# CMDE 注册审查指导原则索引（自动维护）\n"]
    out.append("> **来源**：国家药监局医疗器械技术审评中心 cmde.org.cn「法规文件 > 指导原则」栏目")
    out.append("> **抓取时间**：%s　|　**条目数**：%d（正式 %d、征求意见 %d）"
               % (time.strftime("%Y-%m-%d"),
                  len(items),
                  len(by_sec.get("指导原则文本库", [])),
                  len(by_sec.get("征求意见稿", []))))
    out.append("> **用法**：先在本索引里按关键词找条目 → 标 ✅ 的正文已在库（`source-docs/cmde/F-*.md`，Grep 检索）；"
               "未标 ✅ 的多为产品专用稿，已移出技能目录（归档在 `~/.workbuddy/nmpa-cmde-archive/`），"
               "一条命令即可抓回：`python scripts/cmde_crawl.py docs --only 关键词`")
    out.append("> **增量更新**：`python scripts/cmde_sync.py` 只抓新增正式稿（约 3–5 分钟）；已配定时任务每周自动跑。")
    out.append("> **注意**：指导原则写「不作为法规强制执行」，但**实操中就是强制标准**——审评拿它当尺子，偏离即发补。"
               "答题时不要暗示「可以简化」；替代方法须先沟通交流、再举证等效（见 `qa-playbook.md`）。\n")

    # 域视图
    out.append("## 一、按域速查（正式发布稿）\n")
    dom = defaultdict(list)
    for it in by_sec.get("指导原则文本库", []):
        dom[domain_of(it["title"])].append(it)
    out.append("| 域 | 条目数 |")
    out.append("|---|---|")
    for k in sorted(dom, key=lambda x: -len(dom[x])):
        out.append("| %s | %d |" % (k, len(dom[k])))
    out.append("")

    # 按通告号分组（同一通告一次发布多项，检索时很有用）
    formal = by_sec.get("指导原则文本库", [])
    by_notice = defaultdict(list)
    for it in formal:
        m = re.search(r"[(（](20\d{2})年第\s*(\d+)号[)）]", it["title"])
        key = ("%s年第%s号" % (m.group(1), m.group(2))) if m else "未标号（早期）"
        by_notice[key].append(it)

    def _k(x):
        m = re.match(r"(\d{4})年第(\d+)号", x)
        return (0, -int(m.group(1)), -int(m.group(2))) if m else (1, 0, 0)

    out.append("\n## 二、按发布通告分组（同一通告一次发布多项）\n")
    out.append("| 通告 | 项数 | 代表条目 |")
    out.append("|---|---|---|")
    for k in sorted(by_notice, key=_k):
        v = by_notice[k]
        out.append("| %s | %d | %s |" % (k, len(v), v[0]["title"][:36]))
    out.append("")

    # 全量清单
    for sec in ["指导原则文本库", "征求意见稿"]:
        lst = by_sec.get(sec, [])
        out.append("\n## %s（%d 条）\n" % (sec, len(lst)))
        cur = None
        for it in lst:
            d = domain_of(it["title"])
            if d != cur:
                out.append("\n### %s\n" % d)
                cur = d
            mark = "✅" if it["url"] in fetched else ""
            out.append("- %s [%s](%s)" % (mark, it["title"], it["url"]))

    io.open(OUT, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("-> %s  (%d 条)" % (OUT, len(items)))


if __name__ == "__main__":
    main()
