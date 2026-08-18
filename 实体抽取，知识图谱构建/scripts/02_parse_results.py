# -*- coding: utf-8 -*-
"""02_parse_results.py — 解析 LLM 实体抽取结果, 构建知识图谱文件。

输入: outputs/entity_results.jsonl (batch_llm.py 输出, 含 provider 字段)
      outputs/patent_metadata.csv (01 生成的原始元数据: country/app_year/主IPC)
输出: outputs/graph_nodes.csv — 节点表 (node_id, node_type, name, ...)
      outputs/graph_edges.csv — 关系表 (source, relation, target, patent_pub)
      outputs/entity_stats.csv — 各类实体/关系统计
      outputs/parse_failures.csv — LLM 输出无法解析的专利清单
      outputs/parse_stats.txt   — 汇总

关系模式 (9 类):
  专利-解决-技术问题 | 专利-应用于-应用场景 | 专利-采用-技术方法
  技术方法-处理-生物信号类型 | 专利-基于-技术原理 | 专利-包括-核心部件
  专利-属于-技术主题(IPC 映射) | 专利-公开国家-国家 | 专利-公开年-年份
技术主题/公开国家/公开年份 来自原始信息 (IPC 大类映射 / country / app_year)。
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]  # 多轨道/
OUT = BASE / "实体抽取，知识图谱构建" / "outputs"

# ---------- IPC 大类 -> 技术主题 (覆盖 BCI/神经技术常见领域) ----------
IPC_TOPIC = {
    "A61B": "诊断与检测装置", "A61N": "电疗磁疗放射疗", "A61M": "介质输入器械",
    "A61H": "理疗装置", "A61F": "假体与植入装置", "A61K": "医用制剂",
    "G06F": "电数字数据处理", "G06K": "数据识别与表示", "G06T": "图像数据处理",
    "G06N": "机器学习计算系统", "G06Q": "管理数据处理系统", "G06V": "图像识别",
    "G16H": "医疗保健信息学", "G16B": "生物信息学", "G10L": "语音分析与合成",
    "G09B": "教育演示用具", "H04N": "图像通信", "H04B": "传输系统",
    "H04W": "无线通信网络", "G01N": "材料检测分析", "G01R": "电变量测量",
    "G01S": "无线电定位导航", "G02B": "光学元件", "G05B": "控制系统",
    "G05D": "非电变量控制", "A63B": "体育锻炼器械", "A63F": "游戏娱乐",
    "A01N": "生物化学药剂", "A42B": "帽子头饰", "B60K": "车辆动力装置",
    "G08B": "信号报警装置", "G09G": "显示控制", "H01L": "半导体器件",
    "H03K": "脉冲技术", "G16C": "化学信息学",
}


def ipc_topic(main_ipc):
    """主IPC分类号 -> 技术主题。空/未知回退到代码本身。"""
    s = str(main_ipc or "").strip()
    if not s:
        return "未分类"
    code = s[:4]
    return IPC_TOPIC.get(code, f"其他({code})")


# ---------- 1. 读取 LLM 结果 ----------
recs = [json.loads(l) for l in open(OUT / "entity_results.jsonl", encoding="utf-8") if l.strip()]
ok_recs = [r for r in recs if r.get("ok")]
fail_recs = [r for r in recs if not r.get("ok")]
print(f"records={len(recs)} ok={len(ok_recs)} fail={len(fail_recs)}")

FIELDS = ["技术问题", "应用场景", "技术方法", "生物信号类型", "技术原理", "核心部件"]
parsed = {}   # pub -> {field: [ents], "方法-信号": [(m, s)]}
parse_fail = []

for r in ok_recs:
    resp = r["response"]
    m = re.search(r"\{.*\}", resp, re.S)  # 容忍 ```json 围栏与前后杂文
    if not m:
        parse_fail.append({"pub": r["id"], "原因": "响应中无 JSON 对象", "响应": resp[:200]})
        continue
    try:
        d = json.loads(m.group(0))
    except Exception as e:
        parse_fail.append({"pub": r["id"], "原因": f"JSON 解析失败: {e}", "响应": resp[:200]})
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

n_parsed = len(parsed)
print(f"parsed={n_parsed} parse_fail={len(parse_fail)}")

# ---------- 2. 专利元数据 ----------
meta = pd.read_csv(OUT / "patent_metadata.csv", encoding="utf-8-sig")
meta["pub"] = meta["pub"].astype(str)
meta["country"] = meta["country"].fillna("")
meta["app_year"] = pd.to_numeric(meta["app_year"], errors="coerce")

# ---------- 3. 节点与边 ----------
nodes = {}   # node_id -> {node_type, name, ...}
edges = []   # {source, relation, target, patent_pub}


def node(node_type, name):
    """按 (类型, 名称) 去重的节点登记, 返回 node_id。"""
    name = str(name).strip()
    key = f"{node_type}:{name}"
    if key not in nodes:
        nodes[key] = {"node_id": key, "node_type": node_type, "name": name}
    return key


country_zh = {"US": "美国", "WO": "世界知识产权组织", "EP": "欧洲专利局", "CN": "中国",
              "JP": "日本", "KR": "韩国", "DE": "德国", "FR": "法国", "GB": "英国",
              "CA": "加拿大", "AU": "澳大利亚", "IN": "印度", "IL": "以色列",
              "BR": "巴西", "RU": "俄罗斯", "OTHER": "其他"}

for _, p in meta.iterrows():
    pub = p["pub"]
    if pub not in parsed:
        continue
    n_patent = node("Patent", pub)
    nodes[n_patent].setdefault("title", str(p.get("title") or ""))
    nodes[n_patent].setdefault("标题_中文", str(p.get("title_zh") or ""))
    nodes[n_patent].setdefault("是否主路径", "是" if p.get("是否主路径") else "否")
    nodes[n_patent].setdefault("申请日", str(p.get("申请日") or ""))
    nodes[n_patent].setdefault("主IPC分类号", str(p.get("主IPC分类号") or ""))

    ent = parsed[pub]
    # 6 类专利->实体关系
    rel_map = [("技术问题", "解决"), ("应用场景", "应用于"), ("技术方法", "采用"),
               ("技术原理", "基于"), ("核心部件", "包括")]
    for field, rel in rel_map:
        for name in ent[field]:
            t = node(field, name)
            edges.append({"source": n_patent, "relation": rel, "target": t,
                          "patent_pub": pub})
    # 技术方法-处理-生物信号类型
    for meth, sig in ent["方法-信号"]:
        n_m = node("技术方法", meth)
        n_s = node("生物信号类型", sig)
        edges.append({"source": n_m, "relation": "处理", "target": n_s,
                      "patent_pub": pub})
    # 专利-属于-技术主题 (IPC 映射)
    topic = ipc_topic(p.get("主IPC分类号"))
    if topic != "未分类":
        n_t = node("技术主题", topic)
        edges.append({"source": n_patent, "relation": "属于", "target": n_t,
                      "patent_pub": pub})
    # 专利-公开国家-国家 (原始信息)
    if p["country"]:
        n_c = node("国家", country_zh.get(p["country"], p["country"]))
        edges.append({"source": n_patent, "relation": "公开国家", "target": n_c,
                      "patent_pub": pub})
    # 专利-公开年-年份 (原始信息)
    if pd.notna(p["app_year"]):
        n_y = node("年份", str(int(p["app_year"])))
        edges.append({"source": n_patent, "relation": "公开年", "target": n_y,
                      "patent_pub": pub})

node_df = pd.DataFrame(nodes.values())
edge_df = pd.DataFrame(edges)
node_df.to_csv(OUT / "graph_nodes.csv", index=False, encoding="utf-8-sig")
edge_df.to_csv(OUT / "graph_edges.csv", index=False, encoding="utf-8-sig")

# ---------- 4. 统计 ----------
stats = []
for t in ["Patent", "技术问题", "应用场景", "技术方法", "生物信号类型",
          "技术原理", "核心部件", "技术主题", "国家", "年份"]:
    n = (node_df["node_type"] == t).sum()
    stats.append({"节点类型": t, "数量": n})
rel_stats = edge_df["relation"].value_counts().reset_index()
rel_stats.columns = ["关系", "数量"]
pd.DataFrame(stats).to_csv(OUT / "entity_stats.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(parse_fail).to_csv(OUT / "parse_failures.csv", index=False, encoding="utf-8-sig")

lines = [
    "=== 02 解析与图谱构建统计 ===",
    f"LLM 记录: {len(recs)} (ok {len(ok_recs)} / fail {len(fail_recs)})",
    f"成功解析: {n_parsed} | 解析失败: {len(parse_fail)}",
    f"节点总数: {len(node_df)} | 关系总数: {len(edge_df)}",
]
for _, s in pd.DataFrame(stats).iterrows():
    lines.append(f"  节点 {s['节点类型']}: {s['数量']}")
for _, r in rel_stats.iterrows():
    lines.append(f"  关系 {r['关系']}: {r['数量']}")
(OUT / "parse_stats.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"nodes={len(node_df)} edges={len(edge_df)}")
