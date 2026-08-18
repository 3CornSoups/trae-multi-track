# -*- coding: utf-8 -*-
"""05_parse_dedup.py — 实体消歧阶段3: 解析 LLM 聚类结果 → 映射表。

输入: outputs/dedup_tasks.jsonl    (任务: 含每批实体列表, 用于校验成员)
      outputs/llm_results.jsonl    (LLM 聚类结果, dedup_* 与 ipc_subtopics)
      outputs/entity_terms.csv     (实体名与频次)
输出: outputs/canonical_map.csv    (entity_type, alias, canonical, freq)
      outputs/ipc_subtopic_map.csv (code, topic)
      outputs/dedup_stats.txt      (合并统计)

校验规则:
- 每批任务的实体列表由 dedup_tasks.jsonl 以与 04 相同顺序重建
- LLM 输出 groups 中 members 只接受任务列表内原名称 (防改写/幻觉), 其余丢弃并警告
- 未出现在任何 members 的实体 → 自身映射 (canonical = 自身)
- canonical 若不在原列表中也接受 (LLM 构造的规范名), 并自映射
- 跨批对齐: 同一类型内 canonical 精确相同的自动归并
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "实体抽取，知识图谱构建" / "outputs"

FIELDS = ["技术问题", "应用场景", "技术方法", "生物信号类型", "技术原理", "核心部件"]
BATCH_SIZE = 50  # 必须与 04_prepare_dedup.py 一致

# ---------- 1. 重建每批任务的实体列表 (与 04 完全一致的分批顺序) ----------
import pandas as pd
terms = defaultdict(list)   # field -> [(name, freq)] 频次降序
terms_df = pd.read_csv(OUT / "entity_terms.csv", encoding="utf-8-sig")
for _, row in terms_df.iterrows():
    if row["entity_type"] in FIELDS:
        terms[row["entity_type"]].append((row["name"], int(row["freq"])))

task_items = {}   # task_id -> [name, ...]
n = 0
for fld in FIELDS:
    names = [name for name, _ in terms[fld]]
    for i in range(0, len(names), BATCH_SIZE):
        n += 1
        task_items[f"dedup_{fld}_{n:03d}"] = names[i:i + BATCH_SIZE]

# ---------- 2. 解析 LLM 结果 ----------
recs = [json.loads(l) for l in open(OUT / "llm_results.jsonl", encoding="utf-8")
        if l.strip()]

canonical_map = {}   # (type, alias) -> canonical
warn = Counter()
freq_of = {(f, name): cnt for f in FIELDS for name, cnt in terms[f]}

for r in recs:
    if not r.get("ok"):
        warn["任务失败"] += 1
        continue
    tid = r["id"]
    if tid == "ipc_subtopics":
        continue
    if tid not in task_items:
        warn["未知任务id"] += 1
        continue
    fld = tid[len("dedup_"):].rsplit("_", 1)[0]
    known = set(task_items[tid])

    m = re.search(r"\{.*\}", r["response"], re.S)
    if not m:
        warn["无JSON"] += 1
        continue
    try:
        d = json.loads(m.group(0))
    except Exception:
        warn["JSON解析失败"] += 1
        continue

    groups = d.get("groups") or []
    if not isinstance(groups, list):
        warn["groups非列表"] += 1
        continue

    seen = set()
    for g in groups:
        if not isinstance(g, dict):
            continue
        canon = str(g.get("canonical") or "").strip()
        members = g.get("members") or []
        if not isinstance(members, list) or not canon:
            warn["组格式异常"] += 1
            continue
        for mem in members:
            mem = str(mem).strip()
            if mem not in known:
                warn["成员不在列表(改写/幻觉)"] += 1
                continue
            canonical_map[(fld, mem)] = canon
            seen.add(mem)
        # canonical 自映射 (含 LLM 构造的新规范名)
        canonical_map[(fld, canon)] = canon

    # 未出现在任何组的实体 → 自身映射
    for name in known - seen:
        canonical_map[(fld, name)] = name

# 跨批对齐: 同一类型内 alias 的 canonical 若精确相同 → 归并 (天然发生)
# canonical 本身自映射已在上面完成

n_alias = len(canonical_map)
n_canon = len({(f, c) for (f, a), c in canonical_map.items()})
merged = n_alias - n_canon
print(f"alias={n_alias} canonical={n_canon} 合并减少 {merged}")

# ---------- 3. 输出 canonical_map.csv (pandas 引号引用) ----------
map_rows = [(fld, alias, canon, freq_of.get((fld, alias), 1))
            for (fld, alias), canon in sorted(
                canonical_map.items(), key=lambda kv: (kv[0][0], kv[0][1]))]
pd.DataFrame(map_rows, columns=["entity_type", "alias", "canonical", "freq"]).to_csv(
    OUT / "canonical_map.csv", index=False, encoding="utf-8-sig")

# ---------- 4. IPC 子类主题名 ----------
for r in recs:
    if r.get("id") != "ipc_subtopics" or not r.get("ok"):
        continue
    m = re.search(r"\{.*\}", r["response"], re.S)
    if not m:
        print("[warn] ipc_subtopics 无 JSON")
        break
    try:
        d = json.loads(m.group(0))
    except Exception as e:
        print(f"[warn] ipc_subtopics 解析失败: {e}")
        break
    topics = d.get("topics") or []
    topic_rows = [(t["code"], t["topic"]) for t in topics
                  if isinstance(t, dict) and t.get("code") and t.get("topic")]
    pd.DataFrame(topic_rows, columns=["code", "topic"]).to_csv(
        OUT / "ipc_subtopic_map.csv", index=False, encoding="utf-8-sig")
    print(f"ipc_subtopics: {len(topic_rows)} 条")
    break

# ---------- 5. 统计 ----------
lines = [
    "=== 05 实体消歧统计 ===",
    f"实体别名: {n_alias} | 规范名: {n_canon} | 合并减少: {merged}",
    f"警告: {dict(warn)}",
]
per_field = defaultdict(lambda: [0, 0])
for (fld, alias), canon in canonical_map.items():
    per_field[fld][0] += 1
for (fld, c) in {(f, c) for (f, a), c in canonical_map.items()}:
    per_field[fld][1] += 1
for fld in FIELDS:
    a, c = per_field[fld]
    lines.append(f"  {fld}: {a} -> {c} (减少 {a - c})")
(OUT / "dedup_stats.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
