#!/usr/bin/env python3
"""
时间窗口引文网络构建脚本
========================

基于全量引文网络 (citation_network_full/) 按累积时间窗口切分，
输出各窗口的子网络文件和跨窗口对比报告。

时间窗口 (累积, 以申请年为准):
  - pre-2000    : app_year < 2000     (BCI 技术萌芽期)
  - 2000-2005   : app_year <= 2005    (第一波专利浪潮)
  - 2000-2010   : app_year <= 2010    (技术成长期)
  - 2000-2015   : app_year <= 2015    (信号处理+电极爆发期)
  - 2000-2020   : app_year <= 2020    (商业化加速期)
  - 2000-2026   : app_year <= 2026    (当前全貌)

处理策略:
  1. 窗口内专利 = app_year 在范围内的内部专利 ∪ 所有外部专利 (保持连通性)
  2. 删除孤立节点 (入度=0 且 出度=0)
  3. 取最大弱连通分量 (WCC) 作为核心网络
  4. 每个窗口输出节点表/边表/统计报告/GraphML

依赖: pandas, networkx, numpy
"""

import os
import re
import datetime
import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path
from collections import Counter

# ============================================================
# 0. 路径配置
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "citation_network_full"
NODES_FILE = INPUT_DIR / "nodes.csv"
EDGES_FILE = INPUT_DIR / "edges.csv"
OUTPUT_DIR = BASE_DIR / "citation_network_windows"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 窗口定义
WINDOWS = [
    ("pre2000", None, 1999),       # < 2000
    ("2000_2005", 2000, 2005),
    ("2000_2010", 2000, 2010),
    ("2000_2015", 2000, 2015),
    ("2000_2020", 2000, 2020),
    ("2000_2026", 2000, 2026),
]

# ============================================================
# 1. 加载数据
# ============================================================
print("=" * 70)
print("时间窗口引文网络构建")
print("=" * 70)

print("\n[1/5] 加载全量引文网络数据...")
nodes_df = pd.read_csv(NODES_FILE, dtype=str, low_memory=False)
edges_df = pd.read_csv(EDGES_FILE, dtype=str, low_memory=False)

print(f"  节点: {len(nodes_df):,}")
print(f"  边: {len(edges_df):,}")

# 解析节点属性
# is_internal 是字符串 "True"/"False"
nodes_df["is_internal_bool"] = nodes_df["is_internal"].map({"True": True, "False": False})

# 解析 app_year (可能为 None/NaN)
def safe_year(val):
    try:
        if pd.isna(val) or str(val).strip() in ("", "None", "nan", "<NA>", "NaT"):
            return None
        y = int(float(val))
        if 1900 <= y <= 2030:
            return y
        return None
    except (ValueError, TypeError):
        return None

nodes_df["app_year_int"] = nodes_df["app_year"].apply(safe_year)

n_internal = nodes_df["is_internal_bool"].sum()
n_external = (~nodes_df["is_internal_bool"]).sum()
n_with_year = nodes_df["app_year_int"].notna().sum()
print(f"  内部节点: {n_internal:,}")
print(f"  外部节点: {n_external:,}")
print(f"  有申请年份的节点: {n_with_year:,}")

# 构建 node_id → attributes 快速查找
node_attr = {}
for _, row in nodes_df.iterrows():
    nid = row["node_id"]
    node_attr[nid] = {
        "is_internal": row["is_internal_bool"],
        "app_year": row["app_year_int"],
        "country": row.get("country", ""),
        "in_degree": row.get("in_degree", 0),
        "out_degree": row.get("out_degree", 0),
    }

# 构建 node_id 集合 (快速查找)
all_node_ids = set(nodes_df["node_id"])


# ============================================================
# 2. 逐窗口构建子网络
# ============================================================
print("\n[2/5] 逐窗口构建子网络...")

window_stats = []

for label, yr_start, yr_end in WINDOWS:
    print(f"\n{'─'*60}")
    print(f"  窗口: {label}")
    if yr_start is None:
        print(f"    条件: app_year < {yr_end + 1}")
    else:
        print(f"    条件: {yr_start} <= app_year <= {yr_end}")

    # 2a. 确定该窗口的节点集合
    if yr_start is None:
        # pre-2000: app_year < 2000
        eligible_internal = {
            nid for nid, attr in node_attr.items()
            if attr["is_internal"] and attr["app_year"] is not None
            and attr["app_year"] < 2000
        }
    else:
        eligible_internal = {
            nid for nid, attr in node_attr.items()
            if attr["is_internal"] and attr["app_year"] is not None
            and yr_start <= attr["app_year"] <= yr_end
        }

    # 外部节点全部保留（无年份，维持连通性）
    external_set = {
        nid for nid, attr in node_attr.items()
        if not attr["is_internal"]
    }

    # 无年份的内部节点也保留
    no_year_internal = {
        nid for nid, attr in node_attr.items()
        if attr["is_internal"] and attr["app_year"] is None
    }

    window_nodes = eligible_internal | external_set | no_year_internal
    print(f"    窗口内节点: {len(window_nodes):,}")
    print(f"      符合条件的内部专利: {len(eligible_internal):,}")
    print(f"      外部节点 (保持连通): {len(external_set):,}")
    print(f"      无年份内部节点: {len(no_year_internal):,}")

    # 2b. 过滤边 (source 和 target 都在窗口节点中)
    # 使用 pandas 高效过滤
    edges_window = edges_df[
        edges_df["source"].isin(window_nodes) &
        edges_df["target"].isin(window_nodes)
    ]
    print(f"    窗口内边: {len(edges_window):,}")

    # 2c. 构建有向图
    print(f"    构建有向图...")
    G_w = nx.DiGraph()
    G_w.add_nodes_from(window_nodes)
    for _, row in edges_window.iterrows():
        G_w.add_edge(row["source"], row["target"],
                     via_backward=row.get("via_backward", "True"),
                     via_forward=row.get("via_forward", "False"))

    # 2d. 挂属性
    for n in G_w.nodes:
        if n in node_attr:
            attr = node_attr[n]
            G_w.nodes[n]["is_internal"] = attr["is_internal"]
            G_w.nodes[n]["app_year"] = attr["app_year"] if attr["app_year"] is not None else ""
            G_w.nodes[n]["country"] = attr.get("country", "")
        else:
            G_w.nodes[n]["is_internal"] = False
            G_w.nodes[n]["app_year"] = ""
            G_w.nodes[n]["country"] = ""

    # 计算度
    in_d = dict(G_w.in_degree())
    out_d = dict(G_w.out_degree())
    nx.set_node_attributes(G_w, in_d, "in_degree_w")
    nx.set_node_attributes(G_w, out_d, "out_degree_w")

    raw_n = G_w.number_of_nodes()
    raw_e = G_w.number_of_edges()
    print(f"    原始图: {raw_n:,} 节点, {raw_e:,} 边")

    # 2e. 删除孤立节点
    isolated = [n for n in G_w.nodes if in_d[n] == 0 and out_d[n] == 0]
    G_w.remove_nodes_from(isolated)
    n_removed = len(isolated)
    if n_removed > 0:
        print(f"    移除孤立节点: {n_removed:,}")

    # 2f. 取最大弱连通分量
    if G_w.number_of_nodes() > 0:
        wcc_list = list(nx.weakly_connected_components(G_w))
        wcc_sorted = sorted(wcc_list, key=len, reverse=True)
        giant = wcc_sorted[0]
        if len(wcc_sorted) > 1:
            G_w = G_w.subgraph(giant).copy()
            print(f"    保留最大 WCC: {len(giant):,} 节点 "
                  f"({len(giant) / raw_n * 100:.1f}%), "
                  f"丢弃 {len(wcc_sorted) - 1} 个小分量")

    # 2g. 网络统计
    n_nodes = G_w.number_of_nodes()
    n_edges = G_w.number_of_edges()
    density = n_edges / (n_nodes * (n_nodes - 1)) if n_nodes > 1 else 0

    in_vals = [d for _, d in G_w.in_degree()]
    out_vals = [d for _, d in G_w.out_degree()]
    avg_in = np.mean(in_vals) if in_vals else 0
    avg_out = np.mean(out_vals) if out_vals else 0
    max_in = max(in_vals) if in_vals else 0
    max_out = max(out_vals) if out_vals else 0
    median_in = np.median(in_vals) if in_vals else 0
    median_out = np.median(out_vals) if out_vals else 0

    # WCC 统计
    sub_wcc = list(nx.weakly_connected_components(G_w))
    n_sub_wcc = len(sub_wcc)
    largest_wcc = max(len(c) for c in sub_wcc) if sub_wcc else 0

    # 内部/外部分布
    internal_in_w = sum(1 for n in G_w.nodes if G_w.nodes[n].get("is_internal"))
    external_in_w = n_nodes - internal_in_w

    # 国别分布
    country_in_w = Counter()
    for n in G_w.nodes:
        c = G_w.nodes[n].get("country", "")
        if c and G_w.nodes[n].get("is_internal"):
            country_in_w[c] += 1

    stats = {
        "window": label,
        "year_range": f"{'<' + str(yr_end + 1) if yr_start is None else str(yr_start) + '-' + str(yr_end)}",
        "raw_nodes": raw_n,
        "raw_edges": raw_e,
        "isolated_removed": n_removed,
        "final_nodes": n_nodes,
        "final_edges": n_edges,
        "density": density,
        "internal_nodes": internal_in_w,
        "external_nodes": external_in_w,
        "external_ratio": external_in_w / n_nodes if n_nodes > 0 else 0,
        "avg_in_degree": avg_in,
        "avg_out_degree": avg_out,
        "median_in_degree": median_in,
        "median_out_degree": median_out,
        "max_in_degree": max_in,
        "max_out_degree": max_out,
        "wcc_count": n_sub_wcc,
        "largest_wcc_size": largest_wcc,
        "largest_wcc_ratio": largest_wcc / n_nodes if n_nodes > 0 else 0,
        "top_countries": dict(country_in_w.most_common(5)),
    }
    window_stats.append(stats)

    # 2h. 导出窗口文件
    print(f"    导出窗口文件...")

    # 节点表
    node_rows_win = []
    for n in G_w.nodes:
        attr = G_w.nodes[n]
        # 从原始节点表获取更多元数据
        orig = node_attr.get(n, {})
        node_rows_win.append({
            "node_id": n,
            "is_internal": attr.get("is_internal", False),
            "app_year": attr.get("app_year", ""),
            "country": attr.get("country", ""),
            "in_degree_window": attr.get("in_degree_w", 0),
            "out_degree_window": attr.get("out_degree_w", 0),
            "in_degree_global": orig.get("in_degree", ""),
            "out_degree_global": orig.get("out_degree", ""),
        })
    pd.DataFrame(node_rows_win).to_csv(
        os.path.join(OUTPUT_DIR, f"nodes_window_{label}.csv"),
        index=False, encoding="utf-8-sig")

    # 边表
    edge_rows_win = []
    for u, v, d in G_w.edges(data=True):
        edge_rows_win.append({
            "source": u,
            "target": v,
            "via_backward": d.get("via_backward", ""),
            "via_forward": d.get("via_forward", ""),
        })
    pd.DataFrame(edge_rows_win).to_csv(
        os.path.join(OUTPUT_DIR, f"edges_window_{label}.csv"),
        index=False, encoding="utf-8-sig")

    # 统计报告
    report = f"""
{'='*60}
时间窗口引文网络: {label}
{'='*60}

窗口范围: {stats['year_range']}

--- 节点统计 ---
原始节点数:              {stats['raw_nodes']:>12,}
移除孤立节点:            {stats['isolated_removed']:>12,}
最终节点数:              {stats['final_nodes']:>12,}
  内部专利:              {stats['internal_nodes']:>12,}  ({stats['internal_nodes']/n_nodes*100:5.1f}%)
  外部专利:              {stats['external_nodes']:>12,}  ({stats['external_ratio']*100:5.1f}%)

--- 边统计 ---
最终边数:                {stats['final_edges']:>12,}

--- 网络结构 ---
密度:                    {stats['density']:>12.8f}
弱连通分量数:            {stats['wcc_count']:>12,}
最大 WCC:                {stats['largest_wcc_size']:>12,} ({stats['largest_wcc_ratio']*100:.1f}%)

--- 度分布 ---
平均入度:                {stats['avg_in_degree']:>12.2f}
平均出度:                {stats['avg_out_degree']:>12.2f}
中位入度:                {stats['median_in_degree']:>12.0f}
中位出度:                {stats['median_out_degree']:>12.0f}
最大入度:                {stats['max_in_degree']:>12,}
最大出度:                {stats['max_out_degree']:>12,}

--- 内部专利国别 Top 5 ---
"""
    for c, cnt in stats["top_countries"].items():
        report += f"  {c}: {cnt:,}\n"

    report += f"""
--- 被引最多 Top 10 (in_degree_window) ---
"""
    top_cited_w = sorted(in_d.items(), key=lambda kv: kv[1], reverse=True)[:10]
    for n, d in top_cited_w:
        ext_flag = " [E]" if not G_w.nodes[n].get("is_internal") else ""
        report += f"  {d:5d}  {n}{ext_flag}\n"

    report += f"""
--- 引用最多 Top 10 (out_degree_window) ---
"""
    top_citing_w = sorted(out_d.items(), key=lambda kv: kv[1], reverse=True)[:10]
    for n, d in top_citing_w:
        ext_flag = " [E]" if not G_w.nodes[n].get("is_internal") else ""
        report += f"  {d:5d}  {n}{ext_flag}\n"

    with open(os.path.join(OUTPUT_DIR, f"window_{label}_stats.txt"),
              "w", encoding="utf-8") as f:
        f.write(report)

    # GraphML (清洗后)
    print(f"    导出 GraphML ({G_w.number_of_nodes():,} 节点)...")
    G_clean = G_w.copy()
    for _, d in G_clean.nodes(data=True):
        for k, v in list(d.items()):
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                d[k] = ""
            elif str(v) in ("nan", "<NA>", "NaT", "None"):
                d[k] = ""
            else:
                try:
                    d[k] = str(v)
                except Exception:
                    d[k] = ""
    for _, _, d in G_clean.edges(data=True):
        for k, v in list(d.items()):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                d[k] = ""
            else:
                try:
                    d[k] = str(v)
                except Exception:
                    d[k] = ""

    graphml_path = os.path.join(OUTPUT_DIR, f"window_{label}.graphml")
    nx.write_graphml(G_clean, graphml_path)
    graphml_mb = os.path.getsize(graphml_path) / 1024 / 1024
    print(f"      window_{label}.graphml ({graphml_mb:.1f} MB)")

    print(f"    完成: {n_nodes:,} 节点, {n_edges:,} 边")


# ============================================================
# 3. 跨窗口对比报告
# ============================================================
print(f"\n[3/5] 生成跨窗口对比报告...")

comparison = pd.DataFrame(window_stats)
comparison_csv = os.path.join(OUTPUT_DIR, "windows_comparison.csv")
comparison.to_csv(comparison_csv, index=False, encoding="utf-8-sig")
print(f"  [OK] windows_comparison.csv")

# 打印对比表
print(f"\n{'='*100}")
print("跨窗口对比摘要")
print(f"{'='*100}")
header = f"{'窗口':<15s} {'内部专利':>10s} {'外部专利':>10s} {'总节点':>10s} {'总边':>12s} {'密度':>12s} {'最大入度':>8s}"
print(header)
print("-" * 100)
for s in window_stats:
    print(f"{s['window']:<15s} {s['internal_nodes']:>10,} {s['external_nodes']:>10,} "
          f"{s['final_nodes']:>10,} {s['final_edges']:>12,} "
          f"{s['density']:>12.8f} {s['max_in_degree']:>8,}")

# 增长分析
print(f"\n--- 增长分析 ---")
prev_nodes = 0
prev_edges = 0
for s in window_stats:
    delta_n = s["final_nodes"] - prev_nodes
    delta_e = s["final_edges"] - prev_edges
    print(f"  {s['window']:<15s}: +{delta_n:>10,} 节点, +{delta_e:>12,} 边 "
          f"(增长率 {delta_n/prev_nodes*100:5.1f}% 节点)" if prev_nodes > 0 else
          f"  {s['window']:<15s}: {delta_n:>10,} 节点, {delta_e:>12,} 边 (初始窗口)")
    prev_nodes = s["final_nodes"]
    prev_edges = s["final_edges"]


# ============================================================
# 4. 窗口增长分解 (新增节点+边)
# ============================================================
print(f"\n[4/5] 计算窗口间增长分解...")

# 用全量图的 app_year 做窗口边界过滤，计算每个窗口"新增"的内部专利
year_col = nodes_df["app_year_int"]
nodes_with_year = nodes_df[nodes_df["is_internal_bool"] & year_col.notna()].copy()

for i, (label, yr_start, yr_end) in enumerate(WINDOWS):
    if yr_start is None:
        in_window = nodes_with_year[nodes_with_year["app_year_int"] < 2000]
        desc = "year < 2000"
    else:
        in_window = nodes_with_year[
            (nodes_with_year["app_year_int"] >= yr_start) &
            (nodes_with_year["app_year_int"] <= yr_end)
        ]
        desc = f"{yr_start} <= year <= {yr_end}"

    # 如果是累积窗口，报告"到该窗口为止累计"的专利数
    cumulative = nodes_with_year[nodes_with_year["app_year_int"] <= yr_end]
    print(f"  {label} ({desc}): {len(in_window):,} 内部专利在该区间申请, "
          f"累计 {len(cumulative):,}")


# ============================================================
# 5. 文件汇总
# ============================================================
print(f"\n[5/5] 输出文件汇总")
print(f"  输出目录: {os.path.abspath(OUTPUT_DIR)}")
total_size = 0
for f in sorted(os.listdir(OUTPUT_DIR)):
    fpath = os.path.join(OUTPUT_DIR, f)
    size_mb = os.path.getsize(fpath) / 1024 / 1024
    total_size += size_mb
    print(f"    {f}  ({size_mb:.1f} MB)")
print(f"  总大小: {total_size:.1f} MB")

print("\n" + "=" * 70)
print("时间窗口引文网络构建完成!")
print("=" * 70)
