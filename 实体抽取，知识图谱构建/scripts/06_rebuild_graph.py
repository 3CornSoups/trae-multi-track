# -*- coding: utf-8 -*-
"""06_rebuild_graph.py — 应用实体消歧 + IPC 大组级主题, 重建知识图谱。

输入: outputs/entity_results.jsonl  (LLM 抽取原始结果)
      outputs/canonical_map.csv     (alias -> canonical, 05 生成)
      outputs/ipc_subtopic_map.csv  (IPC 大组码 -> 中文主题名, LLM 生成)
      outputs/patent_metadata.csv   (专利元数据)
输出: outputs/graph_nodes.csv  (覆盖 02 版本 — 消歧后节点)
      outputs/graph_edges.csv  (覆盖 02 版本 — 边重指 canonical)
      outputs/entity_stats.csv / parse_stats.txt (更新统计)

与原 02 版的差异:
1. 语义实体节点合并: 同义实体映射到 canonical 名 (node_id = 类型:canonical)
2. 技术主题细化: IPC 大类(58) -> IPC 大组(147) 级, 如 A61B -> A61B5 身体诊断测量
3. 其余关系(国家/年份/方法-信号)结构不变, 但实体名应用映射
"""
import json
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "实体抽取，知识图谱构建" / "outputs"

FIELDS = ["技术问题", "应用场景", "技术方法", "生物信号类型", "技术原理", "核心部件"]

# ---------- 1. 读取映射 ----------
canon = {}   # (field, alias) -> canonical
cm_df = pd.read_csv(OUT / "canonical_map.csv", encoding="utf-8-sig")
for _, row in cm_df.iterrows():
    if row["entity_type"] in FIELDS and row["alias"] and row["canonical"]:
        canon[(row["entity_type"], row["alias"])] = row["canonical"]

ipc_topic = {}   # 大组码 -> 中文主题名
if (OUT / "ipc_subtopic_map.csv").exists():
    ipc_df = pd.read_csv(OUT / "ipc_subtopic_map.csv", encoding="utf-8-sig")
    for _, row in ipc_df.iterrows():
        if row["code"] and row["topic"]:
            ipc_topic[row["code"]] = row["topic"]
print(f"canonical 映射 {len(canon)} 条 | IPC 大组主题 {len(ipc_topic)} 条")


def canonical_of(field, name):
    return canon.get((field, name), name)


def ipc_main_group(main_ipc):
    """主IPC分类号 -> 大组码 (如 A61B5/0476 -> A61B5), 无则返回空。"""
    m = re.match(r"([A-Z]{1,2}\d{2}[A-Z]\d{1,3})", str(main_ipc or "").strip())
    return m.group(1) if m else ""


# ---------- 2. 读取 LLM 结果 ----------
recs = [json.loads(l) for l in open(OUT / "entity_results.jsonl", encoding="utf-8")
        if l.strip()]
ok_recs = [r for r in recs if r.get("ok")]
print(f"records={len(recs)} ok={len(ok_recs)}")

parsed = {}
for r in ok_recs:
    m = re.search(r"\{.*\}", r["response"], re.S)
    if not m:
        continue
    try:
        d = json.loads(m.group(0))
    except Exception:
        continue
    ent = {f: [] for f in FIELDS}
    for f in FIELDS:
        v = d.get(f, []) or []
        if isinstance(v, str):
            v = [v]
        ent[f] = [str(x).strip() for x in v if str(x).strip()]
    ms = []
    for pair in (d.get("方法-信号") or []):
        if isinstance(pair, dict) and pair.get("方法") and pair.get("信号"):
            ms.append((str(pair["方法"]).strip(), str(pair["信号"]).strip()))
    parsed[r["id"]] = {**ent, "方法-信号": ms}

meta = pd.read_csv(OUT / "patent_metadata.csv", encoding="utf-8-sig")
meta["pub"] = meta["pub"].astype(str)
meta["country"] = meta["country"].fillna("")
meta["app_year"] = pd.to_numeric(meta["app_year"], errors="coerce")

# ---------- 3. 节点与边 ----------
nodes = {}
edges = []


def node(node_type, name, **attrs):
    key = f"{node_type}:{name}"
    if key not in nodes:
        nodes[key] = {"node_id": key, "node_type": node_type, "name": name}
    nodes[key].update({k: v for k, v in attrs.items()
                       if k not in nodes[key] and v != ""})
    return key


country_zh = {"US": "美国", "WO": "世界知识产权组织", "EP": "欧洲专利局", "CN": "中国",
              "JP": "日本", "KR": "韩国", "DE": "德国", "FR": "法国", "GB": "英国",
              "CA": "加拿大", "AU": "澳大利亚", "IN": "印度", "IL": "以色列",
              "BR": "巴西", "RU": "俄罗斯", "OTHER": "其他"}

n_patent_skip = 0
n_topic_fallback = 0
for _, p in meta.iterrows():
    pub = p["pub"]
    if pub not in parsed:
        continue
    n_patent = node("Patent", pub,
                    title=str(p.get("title") or ""),
                    标题_中文=str(p.get("title_zh") or ""),
                    是否主路径="是" if p.get("是否主路径") else "否",
                    申请日=str(p.get("申请日") or ""),
                    主IPC分类号=str(p.get("主IPC分类号") or ""))
    ent = parsed[pub]
    rel_map = [("技术问题", "解决"), ("应用场景", "应用于"), ("技术方法", "采用"),
               ("技术原理", "基于"), ("核心部件", "包括")]
    for field, rel in rel_map:
        for name in ent[field]:
            cname = canonical_of(field, name)
            t = node(field, cname)
            edges.append({"source": n_patent, "relation": rel, "target": t,
                          "patent_pub": pub})
    for meth, sig in ent["方法-信号"]:
        c_meth = canonical_of("技术方法", meth)
        c_sig = canonical_of("生物信号类型", sig)
        n_m = node("技术方法", c_meth)
        n_s = node("生物信号类型", c_sig)
        edges.append({"source": n_m, "relation": "处理", "target": n_s,
                      "patent_pub": pub})
    # 技术主题: IPC 大组级
    code = ipc_main_group(p.get("主IPC分类号"))
    if code in ipc_topic:
        topic = ipc_topic[code]
        n_t = node("技术主题", f"{topic} ({code})", ipc_code=code)
        edges.append({"source": n_patent, "relation": "属于", "target": n_t,
                      "patent_pub": pub})
    elif code:
        n_topic_fallback += 1  # 大组码无主题名 (LLM 未覆盖) -> 用码本身
        n_t = node("技术主题", code, ipc_code=code)
        edges.append({"source": n_patent, "relation": "属于", "target": n_t,
                      "patent_pub": pub})
    else:
        n_patent_skip += 1  # 无有效大组码
    if p["country"]:
        n_c = node("国家", country_zh.get(p["country"], p["country"]))
        edges.append({"source": n_patent, "relation": "公开国家", "target": n_c,
                      "patent_pub": pub})
    if pd.notna(p["app_year"]):
        n_y = node("年份", str(int(p["app_year"])))
        edges.append({"source": n_patent, "relation": "公开年", "target": n_y,
                      "patent_pub": pub})

node_df = pd.DataFrame(nodes.values())
edge_df = pd.DataFrame(edges)
node_df.to_csv(OUT / "graph_nodes.csv", index=False, encoding="utf-8-sig")
edge_df.to_csv(OUT / "graph_edges.csv", index=False, encoding="utf-8-sig")
print(f"nodes={len(node_df)} edges={len(edge_df)} "
      f"| 无大组码专利 {n_patent_skip} | 大组无主题名 {n_topic_fallback}")

# ---------- 4. 统计 ----------
stats = []
for t in ["Patent", "技术问题", "应用场景", "技术方法", "生物信号类型",
          "技术原理", "核心部件", "技术主题", "国家", "年份"]:
    stats.append({"节点类型": t, "数量": (node_df["node_type"] == t).sum()})
rel_stats = edge_df["relation"].value_counts().reset_index()
rel_stats.columns = ["关系", "数量"]
pd.DataFrame(stats).to_csv(OUT / "entity_stats.csv", index=False, encoding="utf-8-sig")

lines = [
    "=== 06 消歧后图谱统计 ===",
    f"LLM 记录: {len(recs)} (ok {len(ok_recs)})",
    f"节点总数: {len(node_df)} | 关系总数: {len(edge_df)}",
    f"技术主题大组码: {len(ipc_topic)} | 无大组码专利: {n_patent_skip} | 大组无主题名: {n_topic_fallback}",
]
for _, s in pd.DataFrame(stats).iterrows():
    lines.append(f"  节点 {s['节点类型']}: {s['数量']}")
for _, r in rel_stats.iterrows():
    lines.append(f"  关系 {r['关系']}: {r['数量']}")
(OUT / "parse_stats.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
