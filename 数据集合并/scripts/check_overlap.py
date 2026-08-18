# -*- coding: utf-8 -*-
"""合并前检查：两方法重叠专利的归属冲突情况。输出 UTF-8 文件避免控制台乱码。"""
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]  # 多轨道/
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

rule = pd.read_csv(BASE / "路径概括与拓展/outputs/path_extension_combined.csv", encoding="utf-8-sig")
sem = pd.read_csv(BASE / "语义相似度匹配/outputs/semantic_assignments.csv", encoding="utf-8-sig")

rule_main = rule[rule["类型"] == "原始主路径"]
rule_ext = rule[rule["类型"] == "拓展并入"]
sem_pubs = set(sem["pub"])
rule_ext_pubs = set(rule_ext["pub"])
main_pubs = set(rule_main["pub"])

lines = []
lines.append(f"规则拓展: {len(rule_ext)} | 语义拓展: {len(sem)} | 主路径(有摘要): {len(rule_main)}")
lines.append(f"语义含主路径: {len(sem_pubs & main_pubs)} | 规则拓展含主路径: {len(rule_ext_pubs & main_pubs)}")

both = sem_pubs & rule_ext_pubs
lines.append(f"两方法重叠(拓展): {len(both)}")
lines.append(f"并集拓展: {len(sem_pubs | rule_ext_pubs)}")

# 归属冲突：同 pub 在两边是否归入同一 (period, path_id)
sem_assign = set(zip(sem["pub"], sem["period"], sem["path_id"]))
rule_assign = set(zip(rule_ext["pub"], rule_ext["period"], rule_ext["path_id"]))
conflict = [p for p in both if (p, sem.loc[sem["pub"] == p, "period"].iloc[0],
                                sem.loc[sem["pub"] == p, "path_id"].iloc[0]) not in rule_assign]
agree = len(both) - len(conflict)
lines.append(f"重叠中归属一致: {agree} | 归属冲突: {len(conflict)}")

# 冲突样例（前 20）
samples = []
for p in conflict[:20]:
    s = sem[sem["pub"] == p].iloc[0]
    r = rule_ext[rule_ext["pub"] == p].iloc[0]
    samples.append(f"{p} | 语义→{s['period']}/路径{s['path_id']} (score={s['score']:.2f}) "
                   f"| 规则→{r['period']}/路径{r['path_id']} (规则score={r['备注']})")
lines.append("--- 冲突样例 ---")
lines += samples

(OUT / "overlap_check.txt").write_text("\n".join(lines), encoding="utf-8")
print("written:", OUT / "overlap_check.txt")
