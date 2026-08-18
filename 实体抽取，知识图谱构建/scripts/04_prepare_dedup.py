# -*- coding: utf-8 -*-
"""04_prepare_dedup.py — 实体消歧阶段1: 规则归一化 + 构造 LLM 语义聚类任务。

输入: outputs/entity_results.jsonl (LLM 抽取结果)
输出: outputs/entity_terms.csv        — 全部语义实体名(归一化后)及频次
      outputs/dedup_tasks.jsonl       — LLM 聚类任务 (每批 ~400 实体名, 按频次降序)
      outputs/dedup_prepare_stats.txt — 统计

归一化只做机械层面(安全, 不改变语义):
  全半角统一 / 英文小写 / 去首尾空白与引号 / 括号半角化 / 多空白合并。
语义级同义(EEG vs 脑电信号)交给阶段2 LLM 聚类。
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "实体抽取，知识图谱构建" / "outputs"

FIELDS = ["技术问题", "应用场景", "技术方法", "生物信号类型", "技术原理", "核心部件"]
BATCH_SIZE = 50  # 每批实体名数量。实测 400/150/100 均有批因长实体名(20+字)分组 JSON 超输出上限,
                 # 50 配合 --max-tokens 8000 全量通过; prompt 只输出同义组

# ---------- 归一化 ----------
FULL2HALF = {chr(c): chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F)}
FULL2HALF["　"] = " "  # 全角空格


def normalize(name):
    s = str(name).strip()
    s = "".join(FULL2HALF.get(ch, ch) for ch in s)
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", " ", s)
    # 英文/数字统一小写 (中文不受影响)
    s = re.sub(r"[A-Za-z0-9]+", lambda m: m.group(0).lower(), s)
    s = s.strip(" \t\"'“”‘’")
    return s


# ---------- 1. 收集全部实体名 (按类型) ----------
recs = [json.loads(l) for l in open(OUT / "entity_results.jsonl", encoding="utf-8")
        if l.strip()]

terms = defaultdict(Counter)   # field -> Counter(name: freq)
pair_terms = Counter()         # 方法-信号 中的方法/信号也计入各自类型频次
for r in recs:
    if not r.get("ok"):
        continue
    try:
        d = json.loads(re.search(r"\{.*\}", r["response"], re.S).group(0))
    except Exception:
        continue
    for f in FIELDS:
        for v in (d.get(f) or []):
            if isinstance(v, str):
                n = normalize(v)
                if n:
                    terms[f][n] += 1
    for pair in (d.get("方法-信号") or []):
        if isinstance(pair, dict) and pair.get("方法") and pair.get("信号"):
            mn, sn = normalize(pair["方法"]), normalize(pair["信号"])
            if mn:
                terms["技术方法"][mn] += 1
            if sn:
                terms["生物信号类型"][sn] += 1

n_raw = sum(sum(c.values()) for c in terms.values())
n_uniq = sum(len(c) for c in terms.values())
print(f"原始出现 {n_raw} 次, 归一化后唯一 {n_uniq} 个")

# ---------- 2. 导出实体表 (pandas 引号引用, 实体名可能含逗号) ----------
import pandas as pd
rows = [(fld, name, cnt) for fld in FIELDS
        for name, cnt in terms[fld].most_common()]
pd.DataFrame(rows, columns=["entity_type", "name", "freq"]).to_csv(
    OUT / "entity_terms.csv", index=False, encoding="utf-8-sig")

# ---------- 3. 构造 LLM 聚类任务 (按频次降序分批) ----------
PROMPT_TMPL = """你是一名生物医学领域术语专家。以下是{n}个从 BCI（脑机接口）专利摘要中自动抽取的【{field}】实体名（带编号）。请将语义相同的实体归为同一组。

判定标准：
- 语义完全相同视为一组，如 "EEG"、"脑电图"、"脑电信号"、"脑电图(EEG)" 归为一组
- 中文与英文同一概念视为同义（如 "肌电信号" 与 "EMG"）
- 仅语序/虚词不同视为同义（如 "信号采集" 与 "采集信号"）
- 不要合并粒度或具体性明显不同的概念（如 "电极" 与 "柔性电极" 不合并；"信号处理" 与 "脑电信号处理" 不合并）
- 语义独特、无同义的实体单独成组

要求：
1. 每组指定一个规范名 canonical：选择最标准、最通用的术语（中文标准术语优先，其次英文标准术语），不要使用带编号的名称
2. 每个实体必须且只能出现在一个组的 members 中；members 里的名称必须是上面列表中的原始名称（保留原样，不要改写）
3. 只输出同义组：members 至少有 2 个实体名的组才需要输出；没有同义实体的独一实体不要出现在输出中
4. 只输出 JSON，不要任何其他文字：
{{"groups": [{{"canonical": "规范名", "members": ["原名称1", "原名称2"]}}]}}

实体列表：
{items}"""

tasks = []
task_count = 0
for fld in FIELDS:
    names = [n for n, _ in terms[fld].most_common()]
    for i in range(0, len(names), BATCH_SIZE):
        chunk = names[i:i + BATCH_SIZE]
        items = "\n".join(f"{j}. {name}" for j, name in enumerate(chunk, 1))
        task_count += 1
        tasks.append({
            "id": f"dedup_{fld}_{task_count:03d}",
            "prompt": PROMPT_TMPL.format(n=len(chunk), field=fld, items=items),
        })

with open(OUT / "dedup_tasks.jsonl", "w", encoding="utf-8") as f:
    for t in tasks:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")

n_batch = sum(1 for t in tasks)
print(f"LLM 聚类任务: {n_batch} 批 ({n_uniq} 个实体名)")

# ---------- 4. IPC 子类中文主题名任务 (单任务) ----------
import pandas as pd
meta = pd.read_csv(OUT / "patent_metadata.csv", encoding="utf-8-sig")
meta["主IPC分类号"] = meta["主IPC分类号"].fillna("")

def subcode(s):
    # IPC 大组码: 小类(如 A61M) + 大组号(1~3 位数字), 如 A61B5 / G06F3 / A61M21
    m = re.match(r"([A-Z]{1,2}\d{2}[A-Z]\d{1,3})", str(s).strip())
    return m.group(1) if m else ""

subs = sorted({subcode(s) for s in meta["主IPC分类号"] if subcode(s)})
subs_items = "\n".join(f"{i}. {code}" for i, code in enumerate(subs, 1))
ipc_prompt = f"""你是一名知识产权领域专家。以下是 BCI（脑机接口）专利数据中出现的 {len(subs)} 个 IPC 子类分类号（如 A61B5）。请为每个分类号给出简洁准确的中文主题名（参考 IPC 官方子类标题，如 A61B5=身体诊断测量）。

要求：
1. 只输出 JSON：{{"topics": [{{"code": "A61B5", "topic": "身体诊断测量"}}]}}
2. 主题名 4~12 个字，覆盖该子类核心技术含义
3. 不要输出任何其他文字

子类列表：
{subs_items}"""

with open(OUT / "ipc_tasks.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps({"id": "ipc_subtopics",
                        "prompt": ipc_prompt}, ensure_ascii=False) + "\n")
print(f"IPC 子类: {len(subs)} 个 -> ipc_tasks.jsonl")

(OUT / "dedup_prepare_stats.txt").write_text(
    f"原始出现 {n_raw} 次\n归一化后唯一 {n_uniq} 个\nLLM 聚类任务 {n_batch} 批\n"
    f"IPC 子类 {len(subs)} 个\n", encoding="utf-8")
