#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 FD&C Act 器械条款原文库

数据源：govinfo.gov 的 US Code 官方 GPO 版（USCODE-{year}-title21）
产出：references/source-docs/us-fda/fdc-act/*.md，每节一份

设计取舍
--------
1. 只收器械相关条款，不整本 Chapter V 搬。Chapter V 有 129 节，
   其中 355/356 系列是药品、360b 是兽药、360eee 是药品供应链，与器械无关。
2. 原文保留英文。法案是判据，翻译会引入歧义；中文只做导航摘要。
3. Editorial Notes 全留。注册费金额、生效日期、废止记录都在注释里，
   砍掉注释等于砍掉可核查性。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from usc2md import render, sect_key, split_sections  # noqa: E402

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SKILL, "references", "source-docs", "us-fda", "fdc-act")
BASE = "https://www.govinfo.gov/content/pkg/USCODE-2023-title21/html/USCODE-2023-title21-chap9"
EDITION = "U.S. Code 2023 年版（current through Pub. L. 118-31，2024-01-03）"

# (组, 序号, section key, 中文名, 一句话摘要)
CATALOG = [
    # ---- A 横切：定义与法律责任 ----
    ("A", 1, "321", "关键术语定义",
     "§201。器械、药品、组合产品、标签、掺假、错标等全部法定定义的总出处。"
     "「device」的三要件（识别用途／实现方式非代谢药理／不依赖代谢…)在此。"),
    ("A", 2, "331", "禁止行为（Prohibited acts）",
     "§301。全部违法行为清单，是 360 系列各项义务的罚则挂靠点。"),
    ("A", 3, "333", "处罚（Penalties）",
     "§303。罚金与刑期分档，含故意违反器械条款的加重情形。"),
    ("A", 4, "374", "检查权（Inspection）",
     "§704。FDA 进入工厂检查的法定授权、范围与拒绝检查的后果。"),
    ("A", 5, "381", "进出口（Imports and exports）",
     "§801。进口报关扣留（detention）、拒绝入境、出口豁免的法定依据。"
     "**(e)(1) 是出口豁免的四个条件，(e)(2) 列出拿不到豁免的三类器械，"
     "(e)(4) 是 CFG（对国外政府证书）的签发时限与收费**。"),
    ("A", 6, "382", "未获批产品的出口（白名单国家）",
     "§802。不符合 §360d/§360e 的器械、IDE 器械、被禁器械，"
     "出口时须依本条获授权。**(b) 列明可接受的白名单国家**"
     "（澳、加、以、日、新、南非、欧盟/EEA）——只拿 CE 未走 FDA 路径的器械，"
     "经美国转口到这些市场的法律基础在此。"),

    # ---- B Part A 器械主体 ----
    ("B", 1, "351", "掺假（Adulterated）",
     "§501。掺假的法定情形，器械部分见 (a)(2)(B)/(h)。"),
    ("B", 2, "352", "错标（Misbranded）",
     "§502。标签与标识违规的法定情形，器械部分见 (f)/(o)/(q)。"),
    ("B", 3, "356j", "器械停产或中断的报告义务",
     "§506J。疫情期间暴露的短缺条款：制造中断须提前 6 个月通知 FDA。"),
    ("B", 4, "360", "生产商注册与产品列名（含 510(k)）",
     "§510。注册与列名在 (a)–(j)；**510(k) 上市前通知在 (k)**，"
     "要求上市前至少 90 天报告（这是「510(k)」这个名字的由来，"
     "不在 §360j）；豁免在 (l)(m)；FDA 审评时限在 (n)；"
     "复用单次使用器械在 (o)；电子注册列名在 (p)。"),
    ("B", 5, "360c", "器械分类（Class I/II/III）",
     "§513。三级分类的法定定义、特殊控制（special controls）、"
     "De Novo 路径（f)(1)）、重新分类（e）全部在此。"),
    ("B", 6, "360c-1", "分类变更的年度公示",
     "§513-1。要求 FDA 每年公布上一年度降级/升级的器械数量与类型。"),
    ("B", 7, "360d", "性能标准（Performance standards）",
     "§514。Class II 特殊控制的一种法定形式，含标准制定的程序与生效方式。"),
    ("B", 8, "360e", "上市前批准（PMA）",
     "§515。Class III 的核心路径：申请内容、审评时限、"
     "补充申请（supplement）分类、生产变更的报批规则。"),
    ("B", 9, "360e-1", "器械的儿科用途",
     "§515A。儿科器械的附加审评要求与延长 exclusivity 的激励。"),
    ("B", 10, "360e-3", "突破性器械（Breakthrough Devices）",
     "§515B。突破性认定标准与审评优待，2016 年 Cures Act 引入。"),
    ("B", 11, "360e-4", "预定变更控制计划（PCCP）",
     "§515C。允许在批准时预先约定后续变更范围，变更时不再逐次报批 —— "
     "软件类器械的核心机制，2022 年 FDASLA 新增。"),
    ("B", 12, "360f", "禁用器械（Banned devices）",
     "§516。部长可直接以法规禁用某类器械的授权。"),
    ("B", 13, "360g", "司法审查（Judicial review）",
     "§517。对分类、性能标准、PMA 决定提起司法审查的途径与时限。"),
    ("B", 14, "360g-1", "重大决定的理由说明义务",
     "§517A。要求 CDRH 对 510(k)/De Novo/PMA/IDE 等重大决定出具"
     "科学与监管理由的实质摘要，含争议点及解决方式。"),
    ("B", 15, "360g-2", "第三方数据透明度",
     "§517B。FDA 引用受资助或受托第三方数据作监管决定时的披露义务。"),
    ("B", 16, "360h", "通知与其他救济（含召回）",
     "§518。器械召回（recall）、通知、修理/更换/退款的法定授权；"
     "「cease distribution」的适用条件在此。"),
    ("B", 17, "360h-1", "器械召回体系改进计划",
     "§518A。要求建立召回台账、公开召回状态、评估召回有效性。"),
    ("B", 18, "360i", "记录与报告（MDR）",
     "§519。不良事件报告（MDR）、报告保存、"
     "以及 522 上市后监督的数据来源义务。"),
    ("B", 19, "360j", "器械控制的通用授权（GMP-IDE-HDE）",
     "§520。**GMP 要求在 (f)**，是 QMSR（21 CFR 820）的法律依据；"
     "IDE 临床试验豁免在 (g)；定制器械在 (b)；追溯在 (j)；"
     "人道豁免 HDE 在 (m)；**医疗器械与临床决策支持软件的界限在 (o)**；"
     "OTC 助听器在 (q)。**注意：510(k) 不在这条，在 §360(k)。**"),
    ("B", 20, "360k", "州与地方要求的优先适用",
     "§521。联邦体系对州法要求的优先（preemption）规则与例外。"),
    ("B", 21, "360l", "上市后监督（Postmarket surveillance）",
     "§522。FDA 可命令特定 Class II/III 器械开展上市后监督的条件与程序。"),
    ("B", 22, "360m", "认可第三方（Accredited persons）",
     "§523。第三方审评 510(k) 的资质认可与适用范围。"),
    ("B", 23, "360n-2", "器械网络安全",
     "§524B。「cyber device」的定义、上市前须提交的网络安全资料、"
     "以及上市后漏洞修补与协调披露义务。2022 年 FDASLA 新增。"),

    # ---- C Part C 电子辐射产品控制 ----
    ("C", 1, "360hh", "电子辐射产品：定义",
     "§531。electronic product / radiation 的定义，涵盖 X 光、激光、"
     "超声、MRI 等辐射类器械。"),
    ("C", 2, "360ii", "电子辐射产品：控制计划",
     "§532。卫生部须建立并执行电子产品的性能标准与测试计划。"),
    ("C", 3, "360jj", "电子辐射产品：研究",
     "§533。授权开展辐射危害与控制方法的研究。"),
    ("C", 4, "360kk", "电子辐射产品：性能标准",
     "§534。制定性能标准的程序、适用产品、"
     "以及标准生效后的认证（certification）要求。"),
    ("C", 5, "360ll", "电子辐射产品：缺陷通知与修理更换",
     "§535。发现缺陷后的通知义务与修理/更换/退款责任。"),
    ("C", 6, "360mm", "电子辐射产品：进口",
     "§536。进口电子产品的合规声明与拒绝入境。"),
    ("C", 7, "360nn", "电子辐射产品：检查、记录与报告",
     "§537。FDA 对电子产品厂商的检查权与记录保存要求。"),
    ("C", 8, "360oo", "电子辐射产品：禁止行为",
     "§538。违反 Part C 的具体违法行为清单。"),
    ("C", 9, "360pp", "电子辐射产品：执法",
     "§539。禁令（injunction）、扣押（seizure）、刑事追诉的适用。"),
    ("C", 10, "360rr", "电子辐射产品：联邦与州协作",
     "§541。与州政府在辐射控制上的分工与协作。"),
    ("C", 11, "360ss", "电子辐射产品：州标准",
     "§542。州可否制定更严标准的规则。"),

    # ---- D Part E 通用条款 ----
    ("D", 1, "360bbb", "扩大可及（Expanded access）",
     "§561。未获批产品在临床试验外的可及途径与知情同意要求。"),
    ("D", 2, "360bbb-2", "产品属性分类（RFD）",
     "§563。申请人可请求 FDA 裁定产品归药品/生物制品/器械/组合产品，"
     "以及由哪个中心主管 —— 组合产品争端的法定通道。"),
    ("D", 3, "360bbb-3", "紧急使用授权（EUA）",
     "§564。公共卫生紧急状态下 EUA 的签发条件、"
     "范围、条件与终止，器械（如呼吸机、检测试剂）大规模适用。"),
    ("D", 4, "360bbb-8b", "境外临床数据的使用",
     "§569B。明确 FDA 应接受境外（含欧盟）临床试验数据，"
     "前提是证明符合美国适用标准 —— 中美双报策略的法定依据。"),

    # ---- E 费用与提交程序（Subchapter VII）----
    ("E", 1, "379i", "器械费用的定义",
     "§737。MDUFA 各项费用的术语定义（premarket application、"
     "establishment registration 等）。"),
    ("E", 2, "379j", "器械使用者费用（MDUFA）",
     "§738。收费种类、各类费用占 PMA 费用的百分比、"
     "小企业减免、以及历次授权的金额调整 —— 查具体数字看本条注释。"),
    ("E", 3, "379j-1", "MDUFA 再授权与报告义务",
     "§738A。五年授权周期、FDA 须提交的绩效报告与目标。"),
    ("E", 4, "379k-1", "电子提交格式",
     "§745A。要求以电子格式提交申报资料的法定授权 —— "
     "eCopy/eSTAR 的法律基础。"),
]

# 哪些 section 在哪个源页里：{缓存文件名: (govinfo 文件名主干, [section key])}
SOURCES = {
    "gv_subchapV.htm": ("subchapV", [
        "351", "352", "356j", "360", "360c", "360c-1", "360d", "360e",
        "360e-1", "360e-3", "360e-4", "360f", "360g", "360g-1", "360g-2",
        "360h", "360h-1", "360i", "360j", "360k", "360l", "360m", "360n-2",
        "360hh", "360ii", "360jj", "360kk", "360ll", "360mm", "360nn",
        "360oo", "360pp", "360rr", "360ss",
        "360bbb", "360bbb-2", "360bbb-3", "360bbb-8b"]),
    "gv_subchapVII.htm": ("subchapVII", ["374", "379i", "379j", "379j-1", "379k-1"]),
    "gv_321.htm": ("subchapII-sec321", ["321"]),
    "gv_331.htm": ("subchapIII-sec331", ["331"]),
    "gv_333.htm": ("subchapIII-sec333", ["333"]),
    "gv_381.htm": ("subchapVIII-sec381", ["381"]),
    "gv_382.htm": ("subchapVIII-sec382", ["382"]),
    "gv_374.htm": ("subchapVII-partA-sec374", ["374"]),
}


def load_all(cache="/tmp"):
    """从本地缓存 HTML 拆出全部 section -> {key: (head, body, src_url)}"""
    pool = {}
    for fn, (srcname, _) in SOURCES.items():
        p = os.path.join(cache, fn)
        if not os.path.exists(p):
            print("  [skip] 缓存缺失:", p)
            continue
        doc = open(p, encoding="utf-8", errors="replace").read()
        url = "%s-%s.htm" % (BASE, srcname)
        for head, body in split_sections(doc):
            k = sect_key(head)
            if k:
                pool[k] = (head, body, url)
    return pool


def main():
    pool = load_all()
    print("可用 section:", len(pool))
    os.makedirs(OUT, exist_ok=True)
    missing, written = [], []
    for grp, no, key, cn, note in CATALOG:
        if key not in pool:
            missing.append(key)
            continue
        head, body, url = pool[key]
        md = render(head, body, cn_note="【本条规定什么】" + note)
        # 文件头：来源与版本，便于日后核时效
        front = [
            "<!-- 来源：%s -->" % url,
            "<!-- 版本：%s -->" % EDITION,
            "<!-- 提示：原文为英文，中文摘要仅供导航；引用时以英文原文为准。 -->",
            "",
        ]
        fn = "%s%d-sec%s-%s.md" % (grp, no, key, cn)
        fn = re.sub(r"[／/\\:*?\"<>|]", "-", fn)
        open(os.path.join(OUT, fn), "w", encoding="utf-8").write("\n".join(front + md) + "\n")
        written.append((fn, len("\n".join(md))))
    print("写出:", len(written), "缺失:", missing)
    for fn, n in written:
        print("  %-60s %6d" % (fn, n))
    total = sum(n for _, n in written)
    print("合计字符:", total)
    json.dump({"count": len(written), "chars": total, "missing": missing},
              open("/tmp/fdc_build.json", "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
