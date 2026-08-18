# -*- coding: utf-8 -*-
"""07_visualize.py — 知识图谱可视化 (HTML 交互式, 无外部依赖, 离线可用)。

输出 (outputs/viz/):
  01_topic_distribution.html   — 技术主题分布条形图 (147 大组主题, Top25+其他)
  02_signal_method_network.html — 生物信号类型↔技术方法共现网络 (交互 SVG)
  03_graph_full.graphml         — 全图导出 (Gephi 用: 23029 节点 / 51193 边)
  index.html                    — 三个可视化的索引页

设计遵循 dataviz 规范: 调色板取自参考 palette (light/dark 双模式),
categorical 固定色序不循环, sequential 单色阶, 悬停 tooltip, 辅助色不承载含义。
"""
import html as html_mod
import json
import re
from collections import Counter
from pathlib import Path

import networkx as nx
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "实体抽取，知识图谱构建" / "outputs"
VIZ = OUT / "viz"
VIZ.mkdir(exist_ok=True)

# ---------- 调色板 (palette.md 参考实例; 按角色使用) ----------
CAT = {"1_blue": "#2a78d6", "2_orange": "#eb6834", "3_aqua": "#1baf7a",
       "4_yellow": "#eda100", "5_magenta": "#e87ba4", "6_green": "#008300",
       "7_violet": "#4a3aa7", "8_red": "#e34948"}
CAT_DARK = {"1_blue": "#3987e5", "2_orange": "#d95926", "3_aqua": "#199e70",
            "4_yellow": "#c98500", "5_magenta": "#d55181", "6_green": "#008300",
            "7_violet": "#9085e9", "8_red": "#e66767"}
SEQ = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf",
       "#1c5cab", "#184f95", "#104281"]  # sequential blue 250→700 (light)
CHROME = """--surface-1:#fcfcfb;--page:#f9f9f7;--ink-1:#0b0b0b;--ink-2:#52514e;
--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10)"""
CHROME_DARK = """--surface-1:#1a1a19;--page:#0d0d0d;--ink-1:#ffffff;--ink-2:#c3c2b7;
--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10)"""

# ---------- 读取图数据 ----------
nodes = pd.read_csv(OUT / "graph_nodes.csv", encoding="utf-8-sig")
edges = pd.read_csv(OUT / "graph_edges.csv", encoding="utf-8-sig")

# =====================================================================
# 可视化 1: 技术主题分布 (专利-属于-技术主题)
# =====================================================================
topic_edges = edges[edges["relation"] == "属于"]
topic_cnt = Counter(edges["target"] for edges in topic_edges.to_dict("records"))
topic_rows = sorted(topic_cnt.items(), key=lambda kv: -kv[1])
# 主题名: "身体诊断测量 (A61B5)" -> 名称 + 码
topic_display = []
for target, cnt in topic_rows:
    m = re.match(r"^(.*)\s\(([A-Z]\d{2}[A-Z]\d{1,3})\)$", target)
    if m:
        topic_display.append((m.group(1), m.group(2), cnt))
    else:
        topic_display.append((target, "", cnt))

TOP_N = 25
top = topic_display[:TOP_N]
rest_cnt = sum(c for _, _, c in topic_display[TOP_N:])
if rest_cnt > 0:
    top.append(("其他 %d 个主题" % (len(topic_display) - TOP_N), "", rest_cnt))

max_cnt = max(c for _, _, c in top)
# sequential 色阶映射 (ordinal: 最浅 >= step250)
def seq_color(c):
    i = round((c / max_cnt) * (len(SEQ) - 1))
    return SEQ[max(0, min(len(SEQ) - 1, i))]

bars = []
for name, code, cnt in top:
    bars.append(f"""<div class="bar-row">
  <div class="bar-label" title="{html_mod.escape(name)}">{html_mod.escape(name)}
    {f'<span class="code">{html_mod.escape(code)}</span>' if code else ''}</div>
  <div class="bar-track"><div class="bar" style="width:{cnt / max_cnt * 100:.1f}%;background:{seq_color(cnt)}"
       data-cnt="{cnt}" data-name="{html_mod.escape(name)}"></div></div>
  <div class="bar-val">{cnt}</div>
</div>""")

topic_html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>BCI 专利技术主题分布</title>
<style>
:root{{color-scheme:light;{CHROME}}}
.viz-root{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
  max-width:860px;margin:0 auto;padding:24px 20px 48px}}
body{{margin:0;background:var(--page)}}
@media (prefers-color-scheme:dark){{
  :root:where(:not([data-theme="light"])){{color-scheme:dark;{CHROME_DARK}}}
}}
:root[data-theme="dark"]{{color-scheme:dark;{CHROME_DARK}}}
h1{{font-size:17px;color:var(--ink-1);font-weight:650;margin:0 0 4px}}
.sub{{font-size:12.5px;color:var(--ink-2);margin:0 0 20px}}
.bar-row{{display:grid;grid-template-columns:minmax(150px,34%) 1fr 46px;gap:10px;align-items:center;
  padding:2.5px 0}}
.bar-label{{font-size:12px;color:var(--ink-1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.code{{color:var(--muted);font-size:10.5px}}
.bar-track{{background:var(--grid);border-radius:3px;height:16px;position:relative}}
.bar{{height:16px;border-radius:3px;min-width:2px;transition:filter .12s}}
.bar:hover{{filter:brightness(1.08)}}
.bar-val{{font-size:11.5px;color:var(--ink-2);font-variant-numeric:tabular-nums;text-align:right}}
#tip{{position:fixed;pointer-events:none;background:var(--ink-1);color:var(--surface-1);
  font-size:12px;padding:6px 10px;border-radius:6px;opacity:0;transition:opacity .1s;z-index:9}}
.note{{margin-top:18px;font-size:11.5px;color:var(--muted)}}
</style></head><body><div class="viz-root">
<h1>BCI 专利技术主题分布（IPC 大组级，共 {len(topic_display)} 个主题）</h1>
<p class="sub">专利—属于—技术主题 · 共 {sum(c for _, _, c in topic_display)} 条归属边 ·
Top {TOP_N} + 其余折叠 · 颜色深浅表示专利数量</p>
{''.join(bars)}
<div class="note">主题归属由主IPC分类号规则提取（无 LLM 判断）；主题中文名由 LLM 生成并复核。
A61B5（身体诊断测量）与 A61N1（神经刺激器件）合计占 65%，符合 BCI 领域特征。</div>
</div>
<div id="tip"></div>
<script>
const tip=document.getElementById('tip');
document.querySelectorAll('.bar').forEach(b=>{{
  b.addEventListener('mousemove',e=>{{tip.style.opacity=1;tip.style.left=(e.clientX+12)+'px';
    tip.style.top=(e.clientY+12)+'px';tip.textContent=b.dataset.name+'：'+b.dataset.cnt+' 项专利'}});
  b.addEventListener('mouseleave',()=>{{tip.style.opacity=0}});
}});
</script></body></html>"""
(VIZ / "01_topic_distribution.html").write_text(topic_html, encoding="utf-8")
print(f"[1/3] 主题分布: {len(topic_display)} 主题 -> 01_topic_distribution.html")

# =====================================================================
# 可视化 2: 生物信号类型 ↔ 技术方法共现网络
# =====================================================================
proc = edges[edges["relation"] == "处理"]
co = Counter((r["source"], r["target"]) for r in proc.to_dict("records"))
# 节点频次
sig_cnt = Counter(r["target"] for r in proc.to_dict("records"))
meth_cnt = Counter(r["source"] for r in proc.to_dict("records"))
SIG_TOP, METH_TOP = 12, 25
sig_top = [n for n, _ in sig_cnt.most_common(SIG_TOP)]
meth_top = [n for n, _ in meth_cnt.most_common(METH_TOP)]
keep = set(sig_top) | set(meth_top)
co = {k: v for k, v in co.items() if k[0] in keep and k[1] in keep}

G = nx.Graph()
for n in meth_top:
    G.add_node(n, kind="方法")
for n in sig_top:
    G.add_node(n, kind="信号")
for (s, t), w in co.items():
    G.add_edge(s, t, weight=w)

# 布局 (kamada-kawai 确定性布局, 基于最短路径, 中等规模稳定)
pos = nx.kamada_kawai_layout(G, weight="weight", scale=300)
node_size = {n: 9 + 4.5 * (meth_cnt.get(n, sig_cnt.get(n, 0))) ** 0.5 for n in G}

xmin = min(x for x, y in pos.values())
ymin = min(y for x, y in pos.values())
xmax = max(x for x, y in pos.values())
ymax = max(y for x, y in pos.values())
def tx(x): return (x - xmin) / (xmax - xmin) * 1050 + 80
def ty(y): return (y - ymin) / (ymax - ymin) * 780 + 60
VIEW_W, VIEW_H = tx(xmax) + 190, ty(ymax) + 80

wmax = max(co.values())
edges_svg = []
for (s, t), w in sorted(co.items(), key=lambda kv: -kv[1]):
    x1, y1 = pos[s]; x2, y2 = pos[t]
    op = 0.18 + 0.62 * (w / wmax)
    edges_svg.append(
        f'<line x1="{tx(x1):.1f}" y1="{ty(y1):.1f}" x2="{tx(x2):.1f}" y2="{ty(y2):.1f}" '
        f'data-s="{html_mod.escape(s)}" data-t="{html_mod.escape(t)}" '
        f'stroke="#898781" stroke-opacity="{op:.2f}" stroke-width="{(0.6 + 2.2 * w / wmax):.2f}"/>')

def name_short(name, k=14):
    return name if len(name) <= k else name[:k] + "…"

# 标签只给高频节点 (方法 top LABEL_M, 信号 top LABEL_S), 其余悬停查看
LABEL_M, LABEL_S = 14, 8
labeled = set(meth_top[:LABEL_M]) | set(sig_top[:LABEL_S])

nodes_svg = []
for n, kind in G.nodes(data="kind"):
    x, y = pos[n]
    color = CAT["2_orange"] if kind == "方法" else CAT["1_blue"]
    r = node_size[n]
    label_dx = r + 4
    lbl = (f'<text x="{tx(x) + label_dx:.1f}" y="{ty(y) + 3.5:.1f}" class="nlabel">'
           f'{html_mod.escape(name_short(n))}</text>') if n in labeled else ""
    nodes_svg.append(f"""<g class="nd" data-name="{html_mod.escape(n)}" data-kind="{kind}"
     data-freq="{meth_cnt.get(n, sig_cnt.get(n, 0))}">
  <circle cx="{tx(x):.1f}" cy="{ty(y):.1f}" r="{r:.1f}" fill="{color}" stroke="var(--surface-1)" stroke-width="1.5"/>
  {lbl}
</g>""")

legend = f"""<div class="legend">
  <span class="lg"><span class="dot" style="background:{CAT['1_blue']}"></span>生物信号类型</span>
  <span class="lg"><span class="dot" style="background:{CAT['2_orange']}"></span>技术方法</span>
  <span class="lg note2">节点大小 ∝ 出现频次 · 连线粗细/深浅 ∝ 共现专利数</span>
</div>"""

network_html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>BCI 信号-方法共现网络</title>
<style>
:root{{color-scheme:light;{CHROME}}}
.viz-root{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
  max-width:960px;margin:0 auto;padding:24px 20px 48px}}
body{{margin:0;background:var(--page)}}
@media (prefers-color-scheme:dark){{
  :root:where(:not([data-theme="light"])){{color-scheme:dark;{CHROME_DARK}}}
}}
:root[data-theme="dark"]{{color-scheme:dark;{CHROME_DARK}}}
h1{{font-size:17px;color:var(--ink-1);font-weight:650;margin:0 0 4px}}
.sub{{font-size:12.5px;color:var(--ink-2);margin:0 0 12px}}
svg{{display:block;margin:0 auto;background:var(--surface-1);border:1px solid var(--border);
  border-radius:10px;max-width:100%;height:auto}}
.nlabel{{font-size:10px;fill:var(--ink-2);pointer-events:none;
  paint-order:stroke;stroke:var(--surface-1);stroke-width:2.5px}}
.nd circle{{cursor:pointer;transition:filter .12s}}
.nd:hover circle{{filter:brightness(1.12)}}
.nd{{opacity:.92}}
.nd.dim{{opacity:.22}}
.legend{{display:flex;gap:18px;align-items:center;margin-top:12px;flex-wrap:wrap;
  font-size:12px;color:var(--ink-1)}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}}
.note2{{color:var(--muted);font-size:11px}}
#tip{{position:fixed;pointer-events:none;background:var(--ink-1);color:var(--surface-1);
  font-size:12px;padding:6px 10px;border-radius:6px;opacity:0;transition:opacity .1s;z-index:9;
  max-width:260px}}
</style></head><body><div class="viz-root">
<h1>BCI 核心技术网络：生物信号类型 ↔ 技术方法</h1>
<p class="sub">技术方法—处理→生物信号类型 · Top {METH_TOP} 方法 × Top {SIG_TOP} 信号 · 消歧后
（如 "脑电信号" 已合并 EEG/脑电图等 25 种写法）· 悬停节点查看详情与高亮邻居</p>
<svg viewBox="0 0 {VIEW_W:.0f} {VIEW_H:.0f}" width="{VIEW_W:.0f}" height="{VIEW_H:.0f}">
{''.join(edges_svg)}
{''.join(nodes_svg)}
</svg>
{legend}
</div><div id="tip"></div>
<script>
const tip=document.getElementById('tip');
const groups=document.querySelectorAll('.nd');
const lines=document.querySelectorAll('line');
groups.forEach(g=>g.addEventListener('mousemove',e=>{{
  tip.style.opacity=1;tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px';
  tip.innerHTML='<b>'+g.dataset.name+'</b>（'+g.dataset.kind+'）<br>出现频次：'+g.dataset.freq;
  const n=g.dataset.name;
  lines.forEach(l=>{{
    l.style.strokeOpacity=(l.dataset.s===n||l.dataset.t===n)?'0.95':'0.05';
  }});
  groups.forEach(o=>o.classList.toggle('dim',o.dataset.name!==n));
}}));
groups.forEach(g=>g.addEventListener('mouseleave',()=>{{
  tip.style.opacity=0;
  lines.forEach(l=>l.style.strokeOpacity='');
  groups.forEach(o=>o.classList.remove('dim'));
}}));
</script></body></html>"""
(VIZ / "02_signal_method_network.html").write_text(network_html, encoding="utf-8")
print(f"[2/3] 共现网络: 节点 {G.number_of_nodes()} 边 {len(co)} -> 02_signal_method_network.html")

# =====================================================================
# 可视化 3: 全图 GraphML (Gephi)
# =====================================================================
Gf = nx.MultiDiGraph()  # 保留跨专利重复边 (如多专利共用同一 方法-信号 对)
for _, r in nodes.iterrows():
    Gf.add_node(r["node_id"], node_type=r["node_type"], name=r["name"],
                **{k: ("" if pd.isna(v) else str(v)) for k, v in
                   [("title", r.get("title")), ("标题_中文", r.get("标题_中文")),
                    ("是否主路径", r.get("是否主路径")), ("申请日", r.get("申请日")),
                    ("主IPC分类号", r.get("主IPC分类号")), ("ipc_code", r.get("ipc_code"))]})
for _, r in edges.iterrows():
    Gf.add_edge(r["source"], r["target"], relation=r["relation"],
                patent_pub=str(r["patent_pub"]))
nx.write_graphml(Gf, VIZ / "03_graph_full.graphml", encoding="utf-8")
print(f"[3/3] GraphML: {Gf.number_of_nodes()} 节点 {Gf.number_of_edges()} 边 -> 03_graph_full.graphml")

# =====================================================================
# 索引页
# =====================================================================
index_html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>BCI 专利知识图谱可视化</title>
<style>
body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#f9f9f7;color:#0b0b0b;
  max-width:760px;margin:0 auto;padding:48px 24px}}
@media (prefers-color-scheme:dark){{body{{background:#0d0d0d;color:#fff}}}}
h1{{font-size:20px}} p{{color:#52514e;font-size:13.5px;line-height:1.7}}
@media (prefers-color-scheme:dark){{p{{color:#c3c2b7}}}}
a.card{{display:block;border:1px solid rgba(11,11,11,.12);border-radius:12px;padding:16px 18px;
  margin:14px 0;text-decoration:none;color:inherit;background:#fcfcfb}}
@media (prefers-color-scheme:dark){{a.card{{background:#1a1a19;border-color:rgba(255,255,255,.12)}}}}
a.card b{{font-size:15px}} a.card span{{display:block;margin-top:4px;font-size:12.5px;color:#898781}}
</style></head><body>
<h1>BCI 专利知识图谱可视化</h1>
<p>数据：2863 个 BCI 专利 · 23029 节点 · 51193 关系（实体消歧 + IPC 大组级主题细化后）</p>
<a class="card" href="01_topic_distribution.html"><b>① 技术主题分布</b>
  <span>147 个 IPC 大组级主题的专利数量分布（Top 25 + 折叠）</span></a>
<a class="card" href="02_signal_method_network.html"><b>② 信号-方法共现网络</b>
  <span>生物信号类型 × 技术方法的共现结构（悬停高亮）</span></a>
<a class="card" href="03_graph_full.graphml"><b>③ 全图 GraphML</b>
  <span>23029 节点 / 51193 边完整图数据，用 Gephi 打开做网络分析</span></a>
</body></html>"""
(VIZ / "index.html").write_text(index_html, encoding="utf-8")
print("索引页 -> index.html")
