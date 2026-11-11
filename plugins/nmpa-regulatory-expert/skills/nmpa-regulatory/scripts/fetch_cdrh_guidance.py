#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 CDRH guidance：全量清单 + 核心文件全文

数据源
------
1. 清单：https://www.fda.gov/files/api/datatables/static/cdrh-guidance-documents.json
   共 600 条，含标题、发布日期、状态（Final/Draft）、主题、PDF 直链。
   注意：该 URL 用 curl 直连会被 CDN 返回假 404，必须用真实 Chrome 的
   request 上下文（共享 cookie/UA）才能取到。
2. 全文：https://www.fda.gov/media/{id}/download ，同样只能走 Chrome 上下文。

策略
----
- 清单全收：600 条全部进 00-清单.md。这是「有没有相关 guidance」的检索入口，
  成本很低（约 300KB），价值极高。
- 全文只抓骨架级：600 份 PDF 全量约 400MB，转文本后上百 MB，塞进 skill 没有意义。
  按 8 个主题挑通用性、程序性最强的 30 余份 —— 判断标准是「跨产品类型适用」，
  具体产品类（如某类骨科螺钉的性能标准）只留清单链接。
"""
import json
import os
import re
import subprocess
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SKILL, "references", "source-docs", "us-fda", "guidance")
CACHE = "/tmp/cdrh_pdf"
LIST_JSON = "/tmp/cdrh_g.json"
PDFTEXT = os.path.join(SKILL, "scripts", "pdf_text.swift")
BASE = "https://www.fda.gov"

# 组别 | 标题唯一片段 | 中文名 | 为什么值得全文入库
PICKS = [
    # ---- 1 审评路径 ----
    ("1-审评路径", "The 510(k) Program: Evaluating Substantial Equivalence",
     "510(k) 项目：实质等同的判定",
     "510(k) 的判据总纲。predicate 选择、intended use 比对、"
     "技术特征差异与性能数据要求，全部在这一份里定义。"),
    ("1-审评路径", "Deciding When to Submit a 510(k) for a Change to an Existing Device",
     "器械变更何时需要提交新 510(k)",
     "变更管理的核心判据：以「可能显著影响安全性或有效性」为界，"
     "给出标签、技术、材料、工艺四类变更的判断流程图。"),
    ("1-审评路径", "Deciding When to Submit a 510(k) for a Software Change",
     "软件变更何时需要提交新 510(k)",
     "软件变更的专门判据，比上一份更细。与 PCCP 配合使用。"),
    ("1-审评路径", "De Novo Classification Process",
     "De Novo 分类流程",
     "无同类已上市器械时的路径：如何从零建立 Class I/II 分类与特殊控制。"
     "中国创新器械走美国市场常走这条。"),
    ("1-审评路径", "Acceptance Review for De Novo Classification Requests",
     "De Novo 申请的受理审查",
     "受理门槛（acceptance review）与拒收理由，避免递交前踩空。"),
    ("1-审评路径", "Breakthrough Devices Program",
     "突破性器械项目",
     "突破性认定的门槛（更有效治疗/诊断生命威胁疾病）与审评优待内容。"),
    ("1-审评路径", "Safety and Performance Based Pathway",
     "安全与性能基准路径（510(k) 简化版）",
     "用「性能基准」代替 predicate 比对的简化路径，2020 年后逐步铺开。"),
    ("1-审评路径", "510(k) Third Party Review Program",
     "510(k) 第三方审评",
     "哪些 510(k) 可由认可第三方审，审评时限与 FDA 复核方式。"),

    # ---- 2 PMA ----
    ("2-PMA", "Modifications to Devices Subject to Premarket Approval",
     "PMA 器械的变更：补充申请判定",
     "PMA 变更的判据（与 510(k) 变更判据平行）。决定走 30 天通知、"
     "实时补充、panel-track 还是新 PMA。"),
    ("2-PMA", "30-Day Notices, 135-Day Premarket Approval (PMA) Supplements",
     "30 天通知与 135 天补充申请",
     "PMA 变更的具体递交类型与时限，含 HDE 的 75 天补充。"),
    ("2-PMA", "Acceptance and Filing Reviews for Premarket Approval Applications",
     "PMA 的受理与立卷审查",
     "acceptance（是否收）与 filing（是否立卷）两关的标准，"
     "对应中国「受理审查」与「技术审评」的分界。"),
    ("2-PMA", "Factors to Consider When Making Benefit-Risk Determinations in Medical Device Premarket Approval",
     "PMA 获益-风险评估的考虑因素",
     "FDA 怎么权衡获益与风险。中国「获益大于风险」原则的对照物。"),
    ("2-PMA", "FDA and Industry Actions on Premarket Approval Applications",
     "PMA 审评时钟与双方动作",
     "审评计时规则：哪些情形停表、哪些不停。对照中国的「发补」时限。"),

    # ---- 3 临床评价 ----
    ("3-临床评价", "Design Considerations for Pivotal Clinical Investigations",
     "关键性临床研究的设计考虑",
     "确证性临床的终点选择、对照设置、样本量、统计假设。"
     "是中国「临床试验方案设计指导原则」的主要参照。"),
    ("3-临床评价", "Investigational Device Exemptions (IDEs) for Early Feasibility",
     "早期可行性研究（EFS）的 IDE",
     "EFS 的适用条件与伦理/safety 要求，对应中国「早期临床试验」。"),
    ("3-临床评价", "FDA Categorization of Investigational Device Exemption",
     "IDE 器械的显著/非显著风险分级",
     "NSR/SR 分级决定是否需要 IRB 之外加 FDA 批准，"
     "对应中国「临床试验审批目录」。"),
    ("3-临床评价", "Use of Real-World Evidence to Support Regulatory Decision-Making for Medical Devices",
     "真实世界证据（RWE）用于监管决策",
     "RWE 的可接受性判据。中国 2020 年后也在推真实世界数据。"),
    ("3-临床评价", "The Content of Investigational Device Exemption (IDE) and Premarket Approval",
     "IDE 与 PMA 申请的内容要求",
     "IDE/PMA 递交资料的目录结构，可直接对照中国 ToC 格式。"),
    ("3-临床评价", "Patient-Reported Outcome Measures",
     "患者报告结局（PRO）",
     "PRO 量表的选择、开发与验证要求，用于支持标签声称。"),

    # ---- 4 软件 / AI / 网络安全 ----
    ("4-软件与AI", "Content of Premarket Submissions for Device Software Functions",
     "器械软件功能：上市前递交内容",
     "软件类器械递交资料的必备项（软件描述、SBOM、风险分析、验证）。"
     "中国《医疗器械软件注册审查指导原则》的主要参照。"),
    ("4-软件与AI", "Cybersecurity in Medical Devices: Quality Management System Considerations",
     "器械网络安全：体系要求与上市前内容",
     "2026 年 2 月最新版。网络安全从「文档要求」升级为「体系要求」，"
     "含 SBOM、漏洞管理、上市后修补。"),
    ("4-软件与AI", "Postmarket Management of Cybersecurity in Medical Devices",
     "上市后网络安全管理",
     "漏洞分级（可控/不可控）、修补是否算需报批的变更 —— "
     "与 510(k) 软件变更判据的衔接点。"),
    ("4-软件与AI", "Policy for Device Software Functions and Mobile Medical Applications",
     "器械软件功能与移动医疗应用的政策边界",
     "哪些 App 算器械、哪些不管。中国「移动医疗器械」定义的对照物。"),
    ("4-软件与AI", "Clinical Decision Support Software",
     "临床决策支持软件（CDS）",
     "2026 年 1 月最新版。CDS 何时被排除在器械定义外 —— 四条判据。"),
    ("4-软件与AI", "Marketing Submission Recommendations for a Predetermined Change Control Plan for Artificial Intelligence",
     "AI 器械的预定变更控制计划（PCCP）",
     "AI 模型迭代怎么合法改：在批准时预先约定变更范围。"
     "这是中美差异最大的一块，中国目前仍以变更注册为主。"),
    ("4-软件与AI", "Off-The-Shelf Software Use in Medical Devices",
     "医疗器械中的现成软件（OTS）",
     "用商用现成软件（含开源）时的验证深度与文档要求。"),
    ("4-软件与AI", "Computer Software Assurance for Production and Quality Management System Software",
     "生产与质量体系软件的计算机软件保证（CSA）",
     "2026 年 2 月版。用 CSA 取代传统 CSV 验证，"
     "基于风险而非逐条脚本。与中国 GMP 附录「计算机软件」要求差异明显。"),

    # ---- 5 质量体系与检查 ----
    ("5-体系与检查", "Quality System Information for Certain Premarket Application Reviews",
     "上市前审评中的质量体系资料",
     "上市前递交时体系资料要交到什么程度，"
     "与中国「体系核查」时点不同的地方。"),
    ("5-体系与检查", "Review and Update of Device Establishment Inspection Processes",
     "器械生产企业检查流程与标准",
     "FDA 工厂检查（含飞行检查）的流程、分级、后续动作。"),
    ("5-体系与检查", "Circumstances that Constitute Delaying, Denying, Limiting, or Refusing",
     "拒绝/拖延/限制检查的认定",
     "什么行为算「拒绝检查」，后果是什么。"
     "对应中国《医疗器械监督管理条例》第 74 条的对抗性条款。"),
    ("5-体系与检查", "Quality Management System Information for Certain Premarket Submission Reviews",
     "上市前递交中的 QMS 资料（草案）",
     "2025 年 10 月草案，QMSR 生效后的配套要求。"),

    # ---- 6 标签 / UDI / 人因 ----
    ("6-标签与UDI", "Applying Human Factors and Usability Engineering to Medical Devices",
     "人因与可用性工程",
     "2026 年 8 月最新版。形成性/总结性可用性测试的要求，"
     "中国《可用性工程指导原则》的主要参照。"),
    ("6-标签与UDI", "Global Unique Device Identification Database (GUDID)",
     "GUDID 数据库提交",
     "UDI 数据要录什么、怎么录。对应中国 UDI 数据库。"),
    ("6-标签与UDI", "Unique Device Identification: Direct Marking of Devices",
     "UDI 直接标识",
     "什么情况下必须把 UDI 刻在器械本体上，以及例外。"),
    ("6-标签与UDI", "Unique Device Identification System: Form and Content",
     "UDI 的形式与内容",
     "UDI 编码结构（DI+PI）、人机可读格式要求。"),
    ("6-标签与UDI", "Submission and Review of Sterility Information in Premarket Notification",
     "灭菌信息的递交与审评",
     "灭菌方式、灭菌确认、无菌保证水平（SAL）在 510(k) 里怎么交。"),

    # ---- 7 上市后 ----
    ("7-上市后", "Distinguishing Medical Device Recalls from Medical Device Enhancements",
     "召回与「产品改进」的界限",
     "同样是改产品，什么算召回（需报告）、什么算改进（不需）。"
     "中国「召回 vs 变更」的争议可直接对照这份。"),
    ("7-上市后", "Postmarket Surveillance Under Section 522",
     "522 条上市后监督",
     "FDA 可强制要求特定器械做上市后监督的条件与程序（对应中国「重点监测」）。"),
    ("7-上市后", "Initiation of Voluntary Recalls Under 21 CFR Part 7",
     "主动召回的启动",
     "召回分级（I/II/III）、召回策略、效度检查、终止条件。"),
    ("7-上市后", "Public Notification of Emerging Postmarket Medical Device Signals",
     "新兴上市后信号的公开",
     "FDA 在证据尚不充分时如何公开信号 —— 对应中国「警示信息」。"),

    # ---- 8 生物学 / 特殊路径 ----
    ("8-生物学与特殊路径", "Use of International Standard ISO 10993-1",
     "ISO 10993-1 生物学评价的应用",
     "FDA 对 ISO 10993-1 的立场：评价范围、试验选择矩阵、"
     "何时可免动物试验。与中国 GB/T 16886.1 的差异点。"),
    ("8-生物学与特殊路径", "Chemical Analysis for Biocompatibility Assessment",
     "生物学评价的化学表征（草案）",
     "用化学表征替代部分动物试验的路径（毒理学风险评估 TRA）。"),
    ("8-生物学与特殊路径", "Reprocessing Medical Devices in Health Care Settings",
     "医疗机构中的器械再处理",
     "复用器械的再处理验证与标签要求。"),
    ("8-生物学与特殊路径", "Humanitarian Device Exemption (HDE) Program",
     "人道主义器械豁免（HDE）",
     "罕见病器械的 HDE 路径：免有效性证据、限 8000 人/年。"),
    ("8-生物学与特殊路径", "Requesting FDA Feedback on Combination Products",
     "组合产品的 FDA 反馈机制",
     "组合产品归属哪个中心、如何取得书面反馈（Pre-RFD/RFD）。"),
]


def plain(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def unesc(s):
    import html
    return html.unescape(s or "")


def rec_pdf(r):
    m = re.search(r'href="(/media/\d+/download)"', r.get("field_associated_media_2") or "")
    return m.group(1) if m else None


def load_list():
    d = json.load(open(LIST_JSON, encoding="utf-8"))
    return d if isinstance(d, list) else (d.get("data") or [])


def write_index(recs, picks, targets=None):
    """全量清单 -> 00-清单.md

    targets 是 [(组, 中文名, 理由, rec)]，用它填「已抓全文」表的日期与 ★ 标记。
    """
    rows = []
    for r in recs:
        t = plain(unesc(r.get("title")))
        dt = plain(r.get("field_issue_datetime"))
        st = plain(r.get("field_final_guidance_1"))
        tp = plain(r.get("topics-product"))
        dk = plain(unesc(r.get("field_docket_number")))
        p = rec_pdf(r)
        rows.append((dt, st, t, tp, dk, p))

    # 按发布日期倒序（MM/DD/YYYY）
    def key(x):
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", x[0] or "")
        return (m.group(3), m.group(1), m.group(2)) if m else ("0000", "00", "00")
    rows.sort(key=key, reverse=True)

    # 已抓全文的原題集合（用于 ★ 标记）
    full_titles = set()
    if targets:
        for _, _, _, r in targets:
            full_titles.add(plain(unesc(r.get("title"))).lower())

    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    out = [
        "# CDRH 器械 guidance 全量清单",
        "",
        "> 来源：FDA 官网 datatables 接口 `cdrh-guidance-documents.json`",
        "> 抓取时点：%s" % now,
        "> 共 %d 条（Final %d / Draft %d）。" % (
            len(rows),
            sum(1 for x in rows if x[1] == "Final"),
            sum(1 for x in rows if x[1] == "Draft")),
        "> 说明：本清单是「有没有相关 guidance」的检索入口。"
        "标 ★ 的是已抓全文入库的骨架级文件，正文见同目录。",
        "",
        "## 已抓全文的 %d 份" % (len(targets) if targets else len(picks)),
        "",
        "| 组 | guidance | 发布日 | 状态 |",
        "|---|---|---|---|",
    ]
    if targets:
        for grp, cn, why, r in targets:
            out.append("| %s | %s | %s | %s |" % (
                grp, cn,
                plain(r.get("field_issue_datetime")),
                plain(r.get("field_final_guidance_1"))))
    else:
        for grp, frag, cn, why in picks:
            out.append("| %s | %s | — | — |" % (grp, cn))
    out += ["", "## 全量清单（按发布日倒序）", ""]

    for dt, st, t, tp, dk, p in rows:
        star = " ★" if t.lower() in full_titles else ""
        link = "[PDF](%s%s)" % (BASE, p) if p else "—"
        out.append("- `%s` **%s**%s · %s · %s · %s · %s" % (
            dt or "—", st or "—", star, t, tp or "—", dk or "—", link))
    out += ["", "---", "", "生成脚本：`scripts/fetch_cdrh_guidance.py`，抓取时点 %s" % now, ""]
    p = os.path.join(OUT, "00-清单.md")
    open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("清单写入:", p, len("\n".join(out)), "字符")


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)
    recs = load_list()
    print("清单条数:", len(recs))

    # 精确匹配目标
    targets, miss = [], []
    for grp, frag, cn, why in PICKS:
        hit = [r for r in recs if frag.lower() in plain(unesc(r.get("title"))).lower()]
        if not hit:
            miss.append(frag)
            continue
        # 多条命中时取最新
        def k(r):
            m = re.match(r"(\d{2})/(\d{2})/(\d{4})", plain(r.get("field_issue_datetime")))
            return (m.group(3), m.group(1), m.group(2)) if m else ("0", "0", "0")
        r = max(hit, key=k)
        targets.append((grp, cn, why, r))
    print("命中 %d / 目标 %d，未命中: %s" % (len(targets), len(PICKS), miss))

    write_index(recs, PICKS, targets)
    json.dump([{"grp": g, "cn": c, "why": w,
                "title": plain(unesc(r.get("title"))),
                "date": plain(r.get("field_issue_datetime")),
                "status": plain(r.get("field_final_guidance_1")),
                "pdf": rec_pdf(r)} for g, c, w, r in targets],
              open("/tmp/guidance_targets.json", "w"), ensure_ascii=False, indent=1)
    print("目标清单 -> /tmp/guidance_targets.json")


if __name__ == "__main__":
    main()
