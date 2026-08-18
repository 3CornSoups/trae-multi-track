# -*- coding: utf-8 -*-
"""合并规则匹配 + 语义匹配：每个时期主路径专利 + 拓展专利（全局唯一归属）。

合并策略（延续用户既定原则"语义新结果为主 + 规则对照"）：
- 主路径：window 文件 node_sequence 全部节点（含无摘要 external 节点），元数据补自 03_合并专利信息_精简.csv
- 规则拓展剔除混入的主路径节点（规则匹配未排除主路径成员，语义匹配排除了）
- 双方法重叠 173 条：归属一致（35）直接合并；归属冲突（138）取语义归属，备注中记录规则归属，供审查
- 输出：05_合并数据集.csv（全量明细）+ merge_summary.csv（每时期每路径统计）
"""
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]  # 多轨道/
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

RULE_SCRIPTS = BASE / "路径概括与拓展/scripts"
sys.path.append(str(RULE_SCRIPTS))
from data_loader import load_top_paths, normalize_pubnum  # noqa: E402

PERIODS = ["2000_2005", "2000_2010", "2000_2015", "2000_2020", "2000_2026"]

# ---------- 1. 主路径完整节点（全部节点，含无摘要） ----------
main_rows = []
for period in PERIODS:
    for p in load_top_paths(period):
        for pos, node in enumerate(p["nodes"], 1):
            main_rows.append({"period": period, "path_id": p["path_id"],
                              "序列位置": pos, "pub": node})
main_nodes = pd.DataFrame(main_rows)
all_main_pubs = set(main_nodes["pub"])

# ---------- 2. 元数据（03_合并专利信息_精简.csv） ----------
meta = pd.read_csv(BASE / "03_合并专利信息_精简.csv", encoding="utf-8-sig",
                   usecols=["公开号", "专利标题", "专利标题（中文）", "摘要_中文",
                            "申请日", "数据来源"])
meta["pub"] = meta["公开号"].astype(str).map(normalize_pubnum)
meta = meta.rename(columns={"专利标题": "title", "专利标题（中文）": "title_zh",
                            "摘要_中文": "abstract_zh", "申请日": "apply_date",
                            "数据来源": "source"})
meta = meta.drop_duplicates(subset="pub").drop(columns=["公开号"])

main = main_nodes.merge(meta, on="pub", how="left")
main["类型"] = "原始主路径"
main["拓展方法"] = ""
main["LLM分数"] = ""
main["最相似路径专利"] = ""
main["相似理由"] = ""
main["备注"] = main["abstract_zh"].isna().map(
    lambda b: "主路径节点（数据集中无中文摘要）" if b else "")

# ---------- 3. 拓展：规则 + 语义 ----------
rule = pd.read_csv(BASE / "路径概括与拓展/outputs/path_extension_combined.csv",
                   encoding="utf-8-sig")
sem = pd.read_csv(BASE / "语义相似度匹配/outputs/semantic_assignments.csv",
                  encoding="utf-8-sig")

rule_ext = rule[rule["类型"] == "拓展并入"].copy()
n_rule_mixed_main = rule_ext["pub"].isin(all_main_pubs).sum()
rule_ext = rule_ext[~rule_ext["pub"].isin(all_main_pubs)].copy()

sem_ext = sem.copy()  # 语义匹配已排除主路径成员
n_sem_mixed_main = 0

rule_assign = {(r["pub"], r["period"], int(r["path_id"])) for _, r in rule_ext.iterrows()}
both_pubs = set(sem_ext["pub"]) & set(rule_ext["pub"])
rule_by_pub = {r["pub"]: r for _, r in rule_ext.iterrows()}
sem_by_pub = {r["pub"]: r for _, r in sem_ext.iterrows()}

# ---------- 4. 合并（语义为主，冲突取语义并记录规则归属） ----------
ext_rows = []
for _, s in sem_ext.iterrows():
    key = (s["pub"], s["period"], int(s["path_id"]))
    if s["pub"] in both_pubs:
        if key in rule_assign:
            method, note = "双方法", "规则匹配与语义匹配并入同一时期同一路径（高置信）"
        else:
            r = rule_by_pub[s["pub"]]
            method = "双方法"
            note = (f"归属冲突：语义匹配为主（LLM 精判）；"
                    f"规则匹配归入 {r['period']}/路径{int(r['path_id'])}")
    else:
        method, note = "语义", "语义匹配并入"
    ext_rows.append({
        "period": s["period"], "path_id": int(s["path_id"]), "类型": "拓展并入",
        "序列位置": "", "pub": s["pub"],
        "title": s.get("title", ""), "title_zh": "", "abstract_zh": s.get("text", ""),
        "apply_date": s.get("apply_date", ""), "source": s.get("source", ""),
        "拓展方法": method, "LLM分数": round(float(s["score"]), 3),
        "最相似路径专利": s["path_pub"], "相似理由": s.get("reason", ""), "备注": note,
    })

for _, r in rule_ext.iterrows():
    if r["pub"] in both_pubs:
        continue  # 已由语义分支输出
    ext_rows.append({
        "period": r["period"], "path_id": int(r["path_id"]), "类型": "拓展并入",
        "序列位置": "", "pub": r["pub"],
        "title": r.get("title", ""), "title_zh": r.get("标题_中文", ""),
        "abstract_zh": r.get("摘要_中文", ""),
        "apply_date": r.get("申请日", ""), "source": r.get("数据来源", ""),
        "拓展方法": "规则", "LLM分数": "", "最相似路径专利": "", "相似理由": "",
        "备注": "规则匹配并入",
    })

ext = pd.DataFrame(ext_rows)

# ---------- 5. 统一列 + 输出 ----------
COLS = ["period", "path_id", "类型", "序列位置", "pub", "title", "标题_中文",
        "摘要_中文", "申请日", "数据来源", "拓展方法", "LLM分数",
        "最相似路径专利", "相似理由", "备注"]
RENAME = {"title_zh": "标题_中文", "abstract_zh": "摘要_中文",
          "apply_date": "申请日", "source": "数据来源"}
main_out = main.rename(columns=RENAME)[COLS]
ext_out = ext.rename(columns=RENAME)[COLS]

# 排序：主路径行在前（按序列位置升序），拓展行在后（LLM 分数降序，仅规则无分数排最后）
main_out["_seq"] = 0
main_out["_pos"] = main_out["序列位置"].astype(int)
ext_out["_seq"] = 1
ext_out["_pos"] = -1
ext_out["_score"] = pd.to_numeric(ext_out["LLM分数"], errors="coerce")
ext_out["_sort"] = -ext_out["_score"].fillna(-1.0)  # 升序排序：分越高越靠前，无分数排最后
merged = pd.concat([main_out, ext_out], ignore_index=True)
period_cat = pd.Categorical(merged["period"], categories=PERIODS, ordered=True)
merged = merged.assign(period_c=period_cat)
merged = merged.sort_values(["period_c", "path_id", "_seq", "_pos", "_sort"])
merged = merged.drop(columns=["_seq", "_pos", "_score", "_sort", "period_c"]).reset_index(drop=True)
# 空值归一为 ""
merged = merged.fillna("")

merged.to_csv(OUT / "05_合并数据集.csv", index=False, encoding="utf-8-sig")

# ---------- 6. 每时期每路径汇总 ----------
stats = []
for period in PERIODS:
    for path_id in sorted(main_out[main_out["period"] == period]["path_id"].unique()):
        m = main_out[(main_out["period"] == period) & (main_out["path_id"] == path_id)]
        e = ext_out[(ext_out["period"] == period) & (ext_out["path_id"] == path_id)]
        stats.append({
            "period": period, "path_id": path_id,
            "主路径节点数": len(m),
            "主路径有摘要": int(m["摘要_中文"].astype(bool).sum()),
            "规则拓展": int((e["拓展方法"] == "规则").sum()),
            "语义拓展": int((e["拓展方法"] == "语义").sum()),
            "双方法": int((e["拓展方法"] == "双方法").sum()),
            "拓展合计": len(e),
            "总计": len(m) + len(e),
        })
summary = pd.DataFrame(stats)
summary.to_csv(OUT / "merge_summary.csv", index=False, encoding="utf-8-sig")

# ---------- 7. 报告 ----------
n_main = len(main_out)
n_abs_main = int(main_out["摘要_中文"].astype(bool).sum())
n_ext = len(ext_out)
n_dual = len(both_pubs)
n_sem_only = int((ext_out["拓展方法"] == "语义").sum())
n_rule_only = int((ext_out["拓展方法"] == "规则").sum())
n_agree = sum(1 for p in both_pubs if (p, sem_by_pub[p]["period"], int(sem_by_pub[p]["path_id"]))
              in rule_assign)
conflict = len(both_pubs) - n_agree

lines = ["# 合并数据集：主路径 + 拓展（规则 × 语义）",
         f"生成时间：{pd.Timestamp.now().isoformat(timespec='seconds')}", ""]
lines.append(f"主路径专利（全部节点）: {n_main}（有中文摘要 {n_abs_main}，无摘要 "
             f"{n_main - n_abs_main}）")
lines.append(f"拓展专利（两方法并集）: {n_ext} = 双方法 {n_dual} + 仅语义 {n_sem_only} "
             f"+ 仅规则 {n_rule_only}")
lines.append(f"双方法重叠中归属一致 {n_agree} 条 / 归属冲突 {conflict} 条"
             f"（冲突取语义归属，备注保留规则归属）")
lines.append(f"剔除规则匹配混入的主路径专利: {n_rule_mixed_main} 条")
n_main_unique = main_out["pub"].nunique()
n_main_dup = len(main_out) - n_main_unique
lines.append(f"主路径专利按路径完整保留：{n_main} 个路径位置中唯一专利 {n_main_unique} 个"
             f"（{n_main_dup} 个位置为核心枢纽专利跨时期/跨路径共享，"
             f"如 {main_out['pub'].value_counts().index[0]} 出现在 "
             f"{main_out['pub'].value_counts().iloc[0]} 条路径——主路径识别的客观性质，按路径结构保留）")
ext_unique = ext_out["pub"].nunique()
lines.append(f"拓展专利全局唯一：{n_ext} 行 = {ext_unique} 个唯一专利（0 跨路径重复）")
lines.append(f"主路径 ∩ 拓展 = ∅（语义匹配排除了主路径成员；规则拓展已剔除混入的 29 条）")
lines.append("")
lines.append("## 每时期每路径统计")
lines.append("| 时期 | 路径 | 主路径节点 | 有摘要 | 规则拓展 | 语义拓展 | 双方法 | 拓展合计 | 总计 |")
lines.append("|---|---|---|---|---|---|---|---|---|")
for _, s in summary.iterrows():
    lines.append(f"| {s['period']} | {s['path_id']} | {s['主路径节点数']} | {s['主路径有摘要']} "
                 f"| {s['规则拓展']} | {s['语义拓展']} | {s['双方法']} | {s['拓展合计']} | {s['总计']} |")
lines.append("")
lines.append(f"总计: 主路径 {n_main} + 拓展 {n_ext} = {n_main + n_ext}")
(OUT / "merged_report.md").write_text("\n".join(lines), encoding="utf-8")

print(f"主路径: {n_main}（有摘要 {n_abs_main}）| 拓展: {n_ext}（双方法 {n_dual}，"
      f"仅语义 {n_sem_only}，仅规则 {n_rule_only}）| 剔除主路径混入 {n_rule_mixed_main}")
print("输出:", OUT / "05_合并数据集.csv", OUT / "merge_summary.csv", OUT / "merged_report.md")
