# -*- coding: utf-8 -*-
"""05c_audit_big_groups.py — 二次审核大合并组 (n>=5), 拆出误并成员。

背景: LLM 语义聚类存在两类误并 (见 05 产物):
  A. 粒度误并 — 子类型并入泛称 (参考电极 -> 电极, 阿尔法波 -> 脑电波)
  B. 组合误并 — 组合/复合描述并入单概念 (eeg, eog -> 脑电信号)
误并集中在大组 (成员数多=合并激进), 故仅审核 n>=5 的组。

流程:
1. 生成 audit_tasks.jsonl — 每大组一个审核任务 (canonical + 成员列表)
2. 跑 batch_llm 处理, 输出 audit_results.jsonl
3. --parse 模式: 应用审核结果 (split 成员改回自身映射), 更新 canonical_map.csv

用法:
  python 05c_audit_big_groups.py                     # 生成任务
  python batch_llm.py --input audit_tasks.jsonl --output audit_results.jsonl ...
  python 05c_audit_big_groups.py --parse             # 应用审核
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "实体抽取，知识图谱构建" / "outputs"
MIN_MEMBERS = 5  # 审核阈值: 成员 >= 5 的合并组

PROMPT_TMPL = """你是生物医学领域术语专家。以下是实体消歧时被自动合并到同一组的实体名。请逐个判断：每个成员与规范名是【同义】(可合并) 还是【子类型/组合/不同概念】(应拆分)。

判定规则：
- 同义：两者可在文中互换使用而不改变含义（如 "脑电图" 与 "EEG"）
- 子类型：成员是规范名的具体化/限定（如 "柔性电极" 是 "电极" 的子类型；"阿尔法波" 是脑电波的频段）→ 拆分
- 组合：成员是多个概念的组合（如 "eeg, eog" 相对 "脑电信号"）→ 拆分
- 不同概念：含义不同 → 拆分
- 含糊时可参考：判断成员名中是否有修饰词（柔性/参考/刺激/阵列/通道/原始/目标/基于 等）使其实指不同于规范名

规范名: {canonical}
成员列表:
{items}

只输出 JSON，不要任何其他文字：
{{"keep": ["与规范名同义的成员", ...], "split": ["应拆分的成员", ...]}}
每个成员必须且只能出现在 keep 或 split 之一。"""


def main():
    if "--parse" in sys.argv:
        apply_audit()
        return
    build_tasks()


def build_tasks():
    df = pd.read_csv(OUT / "canonical_map.csv", encoding="utf-8-sig")
    merged = df[df["alias"] != df["canonical"]]
    g = merged.groupby(["entity_type", "canonical"])["alias"].agg(list).reset_index()
    big = g[g["alias"].apply(len) >= MIN_MEMBERS]
    print(f"合并组总数 {len(g)}, n>={MIN_MEMBERS} 的大组 {len(big)} 个")

    tasks = []
    for _, row in big.iterrows():
        items = "\n".join(f"{j}. {m}" for j, m in enumerate(row["alias"], 1))
        tasks.append({
            "id": f"audit_{row['entity_type']}_{row['canonical']}",
            "prompt": PROMPT_TMPL.format(canonical=row["canonical"], items=items),
        })
    with open(OUT / "audit_tasks.jsonl", "w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"审核任务 {len(tasks)} 个 -> audit_tasks.jsonl (跑 batch_llm 后 --parse)")


def apply_audit():
    map_df = pd.read_csv(OUT / "canonical_map.csv", encoding="utf-8-sig")
    canon = {(row["entity_type"], row["alias"]): row["canonical"]
             for _, row in map_df.iterrows()}
    freq_of = {(row["entity_type"], row["alias"]): row["freq"] for _, row in map_df.iterrows()}

    recs = [json.loads(l) for l in open(OUT / "audit_results.jsonl", encoding="utf-8")
            if l.strip()]
    n_split = n_keep = 0
    for r in recs:
        if not r.get("ok"):
            print(f"[warn] 任务失败: {r['id']} {r.get('error')}")
            continue
        m = re.search(r"\{.*\}", r["response"], re.S)
        if not m:
            continue
        try:
            d = json.loads(m.group(0))
        except Exception:
            continue
        tid = r["id"]
        m2 = re.match(r"audit_(.+)_(.+)$", tid, re.S)
        if not m2:
            continue
        fld, canon_name = m2.group(1), m2.group(2)
        for mem in (d.get("split") or []):
            mem = str(mem).strip()
            if (fld, mem) in canon:
                canon[(fld, mem)] = mem  # 拆出: 映射回自身
                n_split += 1
        n_keep += len([m for m in (d.get("keep") or []) if (fld, str(m).strip()) in canon])

    rows = [(f, a, c, freq_of.get((f, a), 1))
            for (f, a), c in sorted(canon.items(), key=lambda kv: (kv[0][0], kv[0][1]))]
    pd.DataFrame(rows, columns=["entity_type", "alias", "canonical", "freq"]).to_csv(
        OUT / "canonical_map.csv", index=False, encoding="utf-8-sig")
    print(f"审核应用: 拆分 {n_split} 个, 保留 {n_keep} 个 -> canonical_map.csv 已更新")


if __name__ == "__main__":
    main()
