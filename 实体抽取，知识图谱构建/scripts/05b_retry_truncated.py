# -*- coding: utf-8 -*-
"""05b_retry_truncated.py — 找出输出截断(completion_tokens 达上限)的聚类批, 拆半重跑。

流程:
1. 扫描 llm_results.jsonl, 找 completion_tokens == max 的任务 (截断)
2. 从 llm_tasks.jsonl 抽取对应任务, 每个拆成两半 (每批 25 个实体名)
3. 写 retry_tasks.jsonl, 调用 batch_llm 重跑, 结果写 retry_results.jsonl
4. 解析重跑结果 (按 retry_tasks 重建成员集合校验), 合并进 canonical_map.csv

用法: 先跑 batch_llm 处理 retry_tasks.jsonl, 再跑本脚本的解析段 (--parse)。
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "实体抽取，知识图谱构建" / "outputs"
FIELDS = ["技术问题", "应用场景", "技术方法", "生物信号类型", "技术原理", "核心部件"]
MAX_TOKENS = 8000


def task_items_from_prompt(prompt):
    """从 prompt 的实体列表重建名字集合 (每行 'N. name')。"""
    names = set()
    for line in prompt.splitlines():
        m = re.match(r"^\d+\.\s(.+)$", line.strip())
        if m:
            names.add(m.group(1).strip())
    return names


# ---------- 1. 找截断批 ----------
recs = [json.loads(l) for l in open(OUT / "llm_results.jsonl", encoding="utf-8")
        if l.strip()]
truncated = [r for r in recs if r.get("ok") and r.get("completion_tokens") == MAX_TOKENS]
if not truncated:
    print("[ok] 无截断批, 无需重试")
    sys.exit(0)
print(f"截断批 {len(truncated)} 个: {[r['id'] for r in truncated]}")

# ---------- 2. 从任务文件抽取并拆半 ----------
task_by_id = {}
for line in open(OUT / "llm_tasks.jsonl", encoding="utf-8"):
    t = json.loads(line)
    task_by_id[t["id"]] = t

retry_tasks = []
item_sets = {}
for r in truncated:
    t = task_by_id.get(r["id"])
    if not t:
        continue
    known = sorted(task_items_from_prompt(t["prompt"]))
    n = len(known) // 2
    for i, chunk in enumerate((known[:n], known[n:]), 1):
        if not chunk:
            continue
        tid = f"{r['id']}_r{i}"
        items = "\n".join(f"{j}. {name}" for j, name in enumerate(chunk, 1))
        prompt = t["prompt"]
        # 替换实体列表部分: 保留模板, 仅替换编号列表
        parts = prompt.split("实体列表：")
        prompt = parts[0] + "实体列表：\n" + items
        retry_tasks.append({"id": tid, "prompt": prompt})
        item_sets[tid] = set(chunk)

with open(OUT / "retry_tasks.jsonl", "w", encoding="utf-8") as f:
    for t in retry_tasks:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")
print(f"生成重试任务 {len(retry_tasks)} 个 -> retry_tasks.jsonl (跑 batch_llm 后加 --parse 合并)")

# ---------- 3. 解析段 (--parse) ----------
if "--parse" not in sys.argv:
    sys.exit(0)

retry_recs = [json.loads(l) for l in open(OUT / "retry_results.jsonl", encoding="utf-8")
              if l.strip()]
map_df = pd.read_csv(OUT / "canonical_map.csv", encoding="utf-8-sig")
canon = {(row["entity_type"], row["alias"]): row["canonical"]
         for _, row in map_df.iterrows()}
freq_of = {}
for _, row in map_df.iterrows():
    freq_of[(row["entity_type"], row["alias"])] = row["freq"]

n_merged = 0
for r in retry_recs:
    if not r.get("ok") or r["id"] not in item_sets:
        continue
    known = item_sets[r["id"]]
    fld = r["id"].split("_")[1] if r["id"].startswith("dedup_") else ""
    # id 形如 dedup_技术方法_123_r1, 类型是第 2 段
    m = re.match(r"dedup_(.+)_\d+_r\d+", r["id"])
    if not m:
        continue
    fld = m.group(1)
    if fld not in FIELDS:
        continue
    resp = r["response"]
    mj = re.search(r"\{.*\}", resp, re.S)
    if not mj:
        continue
    try:
        d = json.loads(mj.group(0))
    except Exception:
        continue
    for g in (d.get("groups") or []):
        if not isinstance(g, dict):
            continue
        canon_name = str(g.get("canonical") or "").strip()
        for mem in (g.get("members") or []):
            mem = str(mem).strip()
            if mem not in known:
                continue
            if (fld, mem) in canon and canon[(fld, mem)] != mem:
                continue  # 已有合并映射, 保持原映射
            canon[(fld, mem)] = canon_name
            n_merged += 1
        canon[(fld, canon_name)] = canon_name

rows = [(f, a, c, freq_of.get((f, a), 1))
        for (f, a), c in sorted(canon.items(), key=lambda kv: (kv[0][0], kv[0][1]))]
pd.DataFrame(rows, columns=["entity_type", "alias", "canonical", "freq"]).to_csv(
    OUT / "canonical_map.csv", index=False, encoding="utf-8-sig")
print(f"合并重试映射 {n_merged} 条, canonical_map.csv 已更新")
