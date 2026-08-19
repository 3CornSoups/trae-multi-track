# -*- coding: utf-8 -*-
"""读指标总表生成 Markdown 报告。"""
import json
import os
from itertools import chain

import pandas as pd

from indicators import THRESHOLD_FLAG
from paths_overview import render_paths_overview

# 注（控制器修正记录①）：BASE_DIR 为 scripts/ 本身、ROOT 为其父目录（替代风险计算），
# 使报表/配置读取落在 替代风险计算/outputs 与 替代风险计算/config.json。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)


def _fmt(v):
    return '—' if pd.isna(v) else f'{v:.4f}'


def _theme_summary(df: pd.DataFrame) -> str:
    ranked = df.loc[df['风险排名'].notna()].sort_values('风险排名')
    n_all = len(df)
    n_premise = int((df['标记'].fillna('').str.contains('未过前提')).sum())
    n_thr = int((df['标记'].fillna('').str.contains('未达阈值')).sum())
    n_ranked = len(ranked)
    # 终审修复（I-1）：主题码为 "X→Y" 有序对——真实主题数 = 拆对两半的并集去重
    # （如 1980 行 → 45 个主题），替代字面占位 "N 个主题"。
    n_themes = len(set(chain.from_iterable(code.split('→') for code in df['主题码'])))
    lines = ['## 实验三：文档要求版（要素凝练主题 + 替代候选双前提 + 硬阈值）\n']
    lines.append('- 口径：按《替代风险计算研究方案.md》第三步——从知识要素凝练技术主题'
                 f'（LLM 逐条标签 + 归并，{n_themes} 个主题）；主题码 "X→Y" 表示'
                 '"国外 Y 替代 国内 X"（X=被替代侧/国内，Y=替代侧/国外）；替代候选须同时满足'
                 '"解决同一类问题（问题相似度≥0.5）"与"原理明显不同（H≥0.3）"两个前提；'
                 f'仅 F≥0.6/C≥0.5/H≥0.3 全过的路线对才计算综合得分（硬阈值）。')
    lines.append(f'- 结果：{n_all} 个主题对中，{n_premise} 对未过双前提、'
                 f'{n_thr} 对未达阈值、{n_ranked} 对为达标替代候选并参与风险排名。')
    if n_ranked:
        top3 = '、'.join(f'国外{code.split("→")[1]}→国内{code.split("→")[0]}(R={r["R_AB"]:.3f})'
                         for _, r in ranked.head(3).iterrows()
                         for code in [r['主题码']])
        lines.append(f'- 达标候选 Top-3：{top3}。')
    else:
        lines.append('- 无达标候选：硬阈值下没有路线对同时满足三条件（详见报告解读与附录）。')
    return '\n'.join(lines)


def _paths_summary(df: pd.DataFrame, filtered: bool = False) -> str:
    """路线版（6 个跨路线配对）结论摘要：先给结论，再说方法。

    filtered=True（_paths_filtered 版）：对照句指向过滤版细粒度报告（133 主题）。
    """
    ranked = df.loc[df['风险排名'].notna()].sort_values('风险排名')
    top_row = ranked.iloc[0]
    n_qualified = (~df['标记'].astype(str).str.contains(THRESHOLD_FLAG, na=False)).sum()
    qualified_rows = (df.loc[~df['标记'].astype(str).str.contains(THRESHOLD_FLAG, na=False)]
                      .sort_values('风险排名', na_position='last'))
    k_min, k_max = df['K_B'].min(), df['K_B'].max()
    a_min, a_max = df['A_B'].min(), df['A_B'].max()
    s_min, s_max = df['S_AB'].min(), df['S_AB'].max()
    m_min, m_max = df['M_AB'].min(), df['M_AB'].max()

    lines = ['## 结论摘要（先读这里）\n']
    if n_qualified > 0 and str(top_row['标记']) and THRESHOLD_FLAG in str(top_row['标记']):
        q_top = qualified_rows.iloc[0]
        extra = (f'；注意：风险最高的这一对本身不构成"替代候选"（原理差异未达阈值），'
                 f'唯一达标的是"{q_top["主题名"]}"（R={q_top["R_AB"]:.3f}，'
                 f'原理差异 {q_top["H_AB"]:.3f} 恰过 0.3 线）')
    else:
        extra = ''
    lines.append(
        f'- **一句话结论**：在国外三条路线替代国内三条路线的全部 6 个配对中，'
        f'**"{top_row["主题名"]}"的风险最高（R={top_row["R_AB"]:.3f}）**{extra}；'
        f'其中 {n_qualified} 个配对满足文档"替代候选"三条件——跨路线配对让"达标"判定恢复意义。\n')
    lines.append(
        '- **我们在算什么**：把"国外技术替代国内技术"拆成三个问题打分（0~1）：'
        '①能不能替代——国外路线 Y 与国内路线 X 做的事像不像（功能、场景越像分越高，'
        '原理差异越大分越高）；②正在发生吗——Y 的专利增长是否快于 X、'
        'Y 在技术主干道（主路径）上的地位是否上升；③被替代了疼不疼——Y 路线'
        '核心技术多少握在国外、中国自己有多少高价值专利。风险 = 能替代 ×'
        '（正在发生 + 疼不疼）÷ 2。\n')
    lines.append('- **三条路线是谁**：P1=根据位置向用户推送刺激内容并用脑电测反应'
                 '（推送+测量）；P2=把测到的脑反应数据收集、存储、分析、可视化'
                 '（数据平台）；P3=根据脑反应决定刺激内容放在哪里、何时放'
                 '（投放优化）。替代配对即"国外某路线替代国内某路线"共 6 对。\n')
    lines.append('- **结果怎么读**（风险从高到低）：')
    for _, r in ranked.iterrows():
        tag = '　← 风险最高' if r['风险排名'] == 1 else ''
        qual = '，达标' if THRESHOLD_FLAG not in str(r['标记']) else ''
        lines.append(f'  - {r["主题名"]}：风险分 {r["R_AB"]:.3f}{qual}{tag}')
    lines.append(
        f'- **三个要点**：①"能不能替代"各对非常接近（S≈{s_min:.3f}~{s_max:.3f}）、'
        f'"正在发生"拉开差距（M≈{m_min:.2f}~{m_max:.2f}）——排序主要由增长与'
        '主路径地位决定，看 Top 表可逐项归因；②真正的警报仍是"国内缺位"——B 路线的核心技术 '
        f'{k_min*100:.0f}%~{k_max*100:.0f}% 被国外专利掌控，中国高价值专利仅占 '
        f'{a_min*100:.1f}%~{a_max*100:.1f}%，风险性质是"国外强势、国内空白"；'
        '③同路线内部的"原理差异"恒低、无法构成替代（旧口径 3 行结果已归档于'
        '过程记录），跨路线配对才能回答"哪条国外路线在替代哪条国内路线"。\n')
    if filtered:
        lines.append('- **与细粒度版对照**：按 133 个 IPC 主题计算的过滤版'
                     '（`替代风险报告_filtered.md`）同样指向"国外主导、国内缺位"，'
                     '两种口径结论一致。\n')
    else:
        lines.append('- **与细粒度版对照**：按 147 个 IPC 主题计算的细粒度版'
                     '（`替代风险报告.md`）同样指向"国外主导、国内缺位"，'
                     '两种口径结论一致。\n')
    lines.append('---\n')
    return '\n'.join(lines)


def render_report(df: pd.DataFrame, params: dict, top_n: int = 20,
                  caliber: str = 'ipc',
                  domain_stats: dict | None = None,
                  patent_n: int | None = None,
                  filtered: bool = False) -> str:
    """由指标 DataFrame 与参数 dict 生成报告正文。

    caliber='ipc'：IPC 大组主题口径（原文）；caliber='paths'：3 条主路径路线口径。
    domain_stats：BCI 相关性过滤统计 dict（relevance_filter_stats.csv 单行）；
    caliber=='ipc' 且非 None 时在「三、总体结果」前插入「研究域界定」节。
    patent_n：局限节尾注的研究数据集专利数（过滤版传 patent_kept，如 2493；
    None 时输出 2863——未过滤版输出与现状逐字节一致）。
    filtered=True（suffix 以 '_filtered' 开头）：路径版对照句/运行参数显式标注
    按过滤版口径输出。
    """
    ranked = df.loc[df['风险排名'].notna()].sort_values('风险排名')
    top = ranked.head(top_n)
    total_topics = len(df)
    ranked_n = len(ranked)
    sample_short = df['标记'].astype(str).str.contains('样本不足', na=False).sum()
    thr_fail = df['标记'].astype(str).str.contains(THRESHOLD_FLAG, na=False).sum()
    no_hv = df['标记'].astype(str).str.contains('无高价值专利', na=False).sum()
    qualified = (~df['标记'].astype(str).str.contains(THRESHOLD_FLAG, na=False)).sum()
    n_premise = df['标记'].astype(str).str.contains('未过前提', na=False).sum()
    n_thr = df['标记'].astype(str).str.contains('未达阈值', na=False).sum()

    w = params['weights']
    wsum = w['w1'] + w['w2'] + w['w3']

    lines = []
    lines.append('# 技术替代风险计算报告\n')
    lines.append('> 依据：`替代风险计算(1).doc` 思路；设计文档：'
                 '`docs/superpowers/specs/2026-08-17-替代风险计算-design.md`；'
                 '相似度口径升级：`docs/superpowers/specs/2026-08-18-嵌入相似度升级-design.md`\n')
    if caliber == 'paths':
        lines.append(_paths_summary(df, filtered=filtered))
        lines.append(render_paths_overview(
            level=2, title='技术路线全景：全部主路径的技术主线'))
    elif caliber == 'theme':
        lines.append(_theme_summary(df))
    lines.append('## 一、方法与公式\n')
    if caliber == 'paths':
        lines.append('- 配对口径：跨路线替代候选——国内路线 X 与国外路线 Y（X≠Y，共 6 个有序'
                     '配对 X→Y）；3 条路线（P1/P2/P3）由每窗口 15-30 条原生主路径'
                     'LLM 概括合并而来；K/A/V 按 B 路线（Y）全集计算（文档口径）。')
    elif caliber == 'theme':
        n_themes = len({c for code in df['主题码'] for c in str(code).split('→')})
        lines.append('- 配对口径：知识要素凝练技术主题（LLM 逐条标签 + 归并聚类）的国内'
                     f'（公开国家=中国）与国外专利子集；{n_themes} 个主题的有序主题对'
                     f'（X→Y，X≠Y，共 {n_themes}×{n_themes - 1} 对），dom=主题 X 的中国专利、'
                     'for=主题 Y 的国外专利、K/A/V 按主题 Y 全集计算（文档口径）。')
    else:
        lines.append('- 配对口径：同一 IPC 大组级技术主题的国内（公开国家=中国）与国外专利子集；'
                     '147 个主题逐一计算。')
    lines.append('- 可替代性：S_AB = w1·F_AB + w2·C_AB + w3·H_AB，F=功能相似度、C=场景相似度、'
                 'H=原理差异度；F/C 与原理相似度 P 采用 bge-small-zh-v1.5 嵌入的对称最佳匹配'
                 '余弦（½[mean_a max_b cos + mean_b max_a cos]；任一侧实体集为空则该维'
                 '相似度记 0；H=1−P）；F_J/C_J/H_J 为 Jaccard 字符串口径对照列。')
    lines.append(f'- 权重 w1:w2:w3 = {w["w1"]}:{w["w2"]}:{w["w3"]}（归一化后 '
                 f'{w["w1"]/wsum:.3f}:{w["w2"]/wsum:.3f}:{w["w3"]/wsum:.3f}）；'
                 '替代候选双前提：问题实体集合相似度≥0.5（解决同一类技术问题）且 '
                 'H≥0.3（原理明显不同）；硬阈值 F≥0.6、C≥0.5、H≥0.3 全过才计算'
                 '综合得分与风险（文档口径）；未过前提/未达阈值的对留表带标记、'
                 'S/R 空、不参与排名。' if caliber == 'theme' else
                 '阈值 F≥0.6、C≥0.5、H≥0.3 为"达标"参考标记（软阈值口径，'
                 '用户 2026-08-17 拍板）；S 对全部主题计算，未达标主题照常参与排名。')
    lines.append('- 增长优势：g = slope[ln(1+N_t)]（6 时点等间隔线性回归）；'
                 'G_AB = sigmoid(2·(g_B−g_A))。')
    lines.append('- 地位转移：T_AB = sigmoid(2·(Δp_B−Δp_A))，Δp = p_末期−p_初期'
                 '（初期=pre2000，末期=2000-2026）。')
    lines.append('- 替代成熟度：M_AB = (G_AB+T_AB)/2。')
    lines.append('- 安全暴露度：V_B = (K_B+1−A_B)/2；K_B=Σq·Foreign/Σq（q=被引次数+1，'
                 'Foreign=公开国家≠中国）；A_B=主题内高价值专利（引文网络内部节点被引次数前 '
                 f'{100 - int(params["high_value_quantile"]*100)}%'
                 f'（分位 {params["high_value_quantile"]}））的中国专利占比。')
    lines.append('- 最终风险：R_AB = S_AB × (M_AB+V_B)/2。\n')
    lines.append('## 二、运行参数\n')
    lines.append(f'- 高价值分位：{params["high_value_quantile"]}；'
                 f'sigmoid k={params.get("sigmoid_k", 2.0)}；'
                 f'最少专利数（单侧）：{params.get("min_patents", 3)}')
    lines.append(f'- 窗口：{params.get("windows", "见 config.json")}，'
                 f'累计末端年份 {params.get("window_ends", "见 config.json")}'
                 f'（公开年取自 KG `公开年` 边，即申请年字段）。\n')
    if caliber == 'paths' and filtered:
        lines.append('- 本版基于 BCI 相关性过滤后的数据（研究数据集 2493 条）。\n')
    if caliber == 'ipc' and domain_stats:
        lines.append('## 研究域界定（BCI 相关性过滤）\n')
        lines.append('- 判定方法：LLM 逐条判定（deepseek-v4-flash 批量，batch-glm-llm skill）'
                     '"是否属于脑机接口领域或其直接应用"；边界含 BCI 边缘应用'
                     '（神经营销、BCI 教育、神经反馈媒体），排除与脑信号无关的专利'
                     '（位置广告、一般医疗、纯算法工具等）。')
        lines.append(f'- 过滤结果：研究数据集 {domain_stats["patent_total"]} → '
                     f'保留 {domain_stats["patent_kept"]}（排除 {domain_stats["patent_dropped"]}）；'
                     f'主路径节点 {domain_stats["mainpath_total"]} → '
                     f'保留 {domain_stats["mainpath_kept"]}；'
                     f'保留专利中 CN {domain_stats.get("cn_kept", "—")}。')
        lines.append(f'- 判定规模：LLM 逐条判定 {int(domain_stats.get("judged", 2969))} 条'
                     f'（相关 {int(domain_stats.get("relevant", 2582))} / 无关 '
                     f'{int(domain_stats.get("irrelevant", 387))}；类别分布 核心/边缘应用/无关）；'
                     f'其中约 61% 仅凭摘要判定（源数据缺中文标题）。')
        lines.append(f'- 主路径节点：{int(domain_stats.get("mainpath_no_text", 74))} 个无任何文本的'
                     '节点无法判定、默认排除（清单见 '
                     '`outputs/intermediate/no_text_mainpath_nodes.csv`）。')
        lines.append(f'- 主题变化：14 个主题因专利全部被排除而整体退出；另有 8 个主题'
                     '留在表中但风险不可计算（详见任务报告 task-13-report.md 台账）。')
        lines.append('- 被排除专利清单见 `outputs/intermediate/excluded_patents.csv`'
                     '（含判定类别与理由，可复核）。\n')
    lines.append('## 三、总体结果\n')
    if caliber == 'theme':
        lines.append(f'- 技术主题数：{n_themes}；有序主题对数（X→Y，X≠Y）：{total_topics}')
        lines.append(f'- 未过双前提（问题相似度<0.5 或 H<0.3）：{n_premise}')
        lines.append(f'- 未达硬阈值（F<0.6 或 C<0.5 或 H<0.3）：{n_thr}')
        lines.append(f'- 达标替代候选并参与排名（R 可计算）：{ranked_n}')
        lines.append(f'- 标记统计（可叠加）：样本不足 {sample_short}、'
                     f'无高价值专利 {no_hv}\n')
    else:
        lines.append(f'- 技术主题总数：{total_topics}；参与排名（R 可计算）：{ranked_n}')
        lines.append(f'- 达标主题（F≥0.6 且 C≥0.5 且 H≥0.3）：{qualified}')
        lines.append(f'- 未参与排名（R 不可计算，均因无高价值专利）：{no_hv}')
        lines.append(f'- 标记统计（可叠加；"未达标"与"样本不足"不排除排名）：'
                     f'样本不足 {sample_short}、未达标 {thr_fail}、无高价值专利 {no_hv}\n')
    if caliber == 'paths':
        lines.append(f'## 四、Top-{top_n} 风险技术主题（本版全部 6 个路线对）\n')
    elif caliber == 'theme':
        lines.append(f'## 四、Top-{top_n} 风险技术主题对（达标替代候选）\n')
    else:
        lines.append(f'## 四、Top-{top_n} 风险技术主题\n')
    if len(top):
        lines.append('| 风险排名 | 主题码 | 主题名 | n_国内 | n_国外 | S_AB | M_AB | '
                     'K_B | A_B | V_B | R_AB | 标记 |')
        lines.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
        for _, r in top.iterrows():
            lines.append(f'| {int(r["风险排名"])} | {r["主题码"]} | {r["主题名"]} | '
                         f'{int(r["n_国内"])} | {int(r["n_国外"])} | {_fmt(r["S_AB"])} '
                         f'| {_fmt(r["M_AB"])} | {_fmt(r["K_B"])} | {_fmt(r["A_B"])} '
                         f'| {_fmt(r["V_B"])} | {_fmt(r["R_AB"])} | '
                         f'{"" if pd.isna(r["标记"]) else r["标记"]} |')
    else:
        empty_msg = '（无达标替代候选；见文末软阈值参考排名附录）' if caliber == 'theme' \
            else '（无主题满足排名条件）'
        lines.append(empty_msg)
    lines.append('')
    if caliber == 'theme':
        lines.append('## 达标替代候选清单（硬阈值全过；最多 10 行）')
        qual = ranked.head(10)   # 硬阈值口径：达标清单=参与排名的替代候选
    else:
        lines.append('## 达标主题清单（标记不含"未达标"；最多 10 行）')
        qual = (df.loc[~df['标记'].astype(str).str.contains(THRESHOLD_FLAG, na=False)]
                .sort_values('风险排名', na_position='last').head(10))
    if len(qual):
        lines.append('| 主题码 | 主题名 | F_AB | C_AB | H_AB | F_J | R_AB | 风险排名 |')
        lines.append('|---|---|---|---|---|---|---|---|')
        for _, r in qual.iterrows():
            lines.append(f'| {r["主题码"]} | {r["主题名"]} | {_fmt(r["F_AB"])} '
                         f'| {_fmt(r["C_AB"])} | {_fmt(r["H_AB"])} | {_fmt(r["F_J"])} '
                         f'| {_fmt(r["R_AB"])} | '
                         f'{("—" if pd.isna(r["风险排名"]) else int(r["风险排名"]))} |')
    else:
        lines.append('（无）')
    lines.append('')
    lines.append('## 解读\n')
    unit = '主题对' if caliber == 'theme' else '主题'
    n_dom_zero = int((top['n_国内'] == 0).sum())
    n_small = int(top['标记'].astype(str).str.contains('样本不足', na=False).sum())
    lines.append(f'- Top-{top_n} 中 {n_dom_zero} 个{unit}国内专利数为 0、{n_small} 个带"样本不足"标记：'
                 '靠前名次主要反映国外专利主导（V_B 趋近 1、A_B≈0）下的国内缺位风险，'
                 '而非对既有国内技术路线的替代动态。')
    f_j_pos = int((df['F_J'] > 0).sum())
    lines.append(f'- 嵌入口径下 F_AB 均值 {df["F_AB"].dropna().mean():.3f}、'
                 f'C_AB 均值 {df["C_AB"].dropna().mean():.3f}；Jaccard 对照 F_J>0 仅 '
                 f'{f_j_pos} 个{unit}——字符串相等对同义异形（"RF信号传输能量" vs "RF能量传输"）'
                 '零容错，两种口径的差异为方法学发现。')
    if caliber == 'ipc':
        lines.append('- Top 主题中 G06F17（数据处理）、G06Q30（商业交易系统）等非典型 BCI 主题'
                     '源于知识图谱的 147 个主IPC 大组映射（研究数据集 IPC 分布的真实反映），'
                     '并非管道错误；A66N1 等主题名为"未知分类"者同属 IPC 映射原始名称。')
        if domain_stats:
            lines.append('- 过滤后仍居首的 G06Q30（商业交易系统）的保留专利均为脑电广告/神经营销类'
                         '边缘应用（属纳入口径），并非管道错误。')
    elif caliber == 'theme':
        n_f_fail = int((df['F_AB'] < params['thresholds']['F']).sum())
        n_c_fail = int((df['C_AB'] < params['thresholds']['C']).sum())
        n_h_fail = int((df['H_AB'] < params['thresholds']['H']).sum())
        lines.append(f'- 硬阈值三条件的全表统计：F<0.6 的 {n_f_fail} 对、C<0.5 的 '
                     f'{n_c_fail} 对、H<0.3 的 {n_h_fail} 对（含未过前提的对，'
                     '其 F/C/H 亦照填）；与"未过双前提/未达阈值"两个标记合计对照，'
                     '可定位主要门槛。')
        # 终审修复（I-3）：达标率高系主题粒度领域特性归因（与实验二 H 临界窄带对照）
        if len(ranked):
            lines.append(f'- 达标率高达 {len(ranked)/total_topics*100:.0f}% 的原因：'
                         f'{n_themes} 个主题由同一 BCI 领域凝练而来，功能/场景普遍相似'
                         f'（F/C 均值≈{df["F_AB"].dropna().mean():.2f}），原理差异普遍'
                         f'满足 H≥0.3（仅 {n_h_fail} 对不足）——F 是实际主要门槛；'
                         '这是主题粒度的领域特性，与实验二 6 对挤在 H 临界窄带'
                         '（0.288~0.303）形成对照，说明文档硬阈值在主题粒度下是稳健筛选器。')
        n_no_r = int((df['风险排名'].isna()
                      & ~df['标记'].astype(str).str.contains(
                          '未过前提|未达阈值', na=False)).sum())
        if n_no_r:
            lines.append(f'- 另有 {n_no_r} 对通过双前提与硬阈值但 R 不可计算'
                         '（Y 主题无高价值专利），留表不参与排名——'
                         '与实验一/二"无高价值专利"的处理一致。')
        if len(ranked):
            s_min, s_max = ranked['S_AB'].min(), ranked['S_AB'].max()
            m_min, m_max = ranked['M_AB'].min(), ranked['M_AB'].max()
            lines.append(f'- 达标候选的 S 落在 {s_min:.3f}~{s_max:.3f}、'
                         f'M 落在 {m_min:.3f}~{m_max:.3f}：风险排序由可替代性'
                         '（能不能替代）与替代成熟度（正在发生）共同决定，'
                         '看 Top 表可逐项归因。')
        else:
            lines.append('- 无达标替代候选：硬阈值与双前提联合判定下没有路线对同时满足'
                         '三条件——这是文档口径的如实结果，不代表各对之间没有风险差异'
                         '（见文末"软阈值参考排名"附录，非主口径）。')
    else:
        n_qual = (~df['标记'].astype(str).str.contains(THRESHOLD_FLAG, na=False)).sum()
        # 修正记录（数据驱动，2026-08-18）：实测 6 对 F/C 全部达阈值，未达标
        # 均因原理差异仍不足（P_sim>0.7 → H<0.3），故原因句按真实数据表述。
        n_f_fail = int((df['F_AB'] < params['thresholds']['F']).sum())
        n_c_fail = int((df['C_AB'] < params['thresholds']['C']).sum())
        n_h_fail = int((df['H_AB'] < params['thresholds']['H']).sum())
        lines.append(f'- 达标 {n_qual}/6：未达标全部源于原理差异不足（H 未达阈 {n_h_fail} 对）；'
                     f'功能/场景相似度仅 {n_f_fail}/{n_c_fail} 对未达各自阈值——'
                     '跨路线配对的"原理差异"天然较高，"替代候选"判定有意义。')
        h_min, h_max = df['H_AB'].min(), df['H_AB'].max()
        q_h = df.loc[~df['标记'].astype(str).str.contains(THRESHOLD_FLAG, na=False), 'H_AB']
        h_exc = q_h.max() - params['thresholds']['H'] if len(q_h) else float('nan')
        lines.append(f'- 临界提示：6 对的 H_AB 全部落在 {h_min:.3f}~{h_max:.3f} 的窄带内，'
                     f'"达标"与否对 H≥0.3 阈值极敏感（唯一达标对仅超阈值 {h_exc:.3f}），'
                     '"达标 1/6"应读作"唯一相对达标"而非稳健分类。')
        lines.append('- 配对风险的构成看 Top 表：S_AB（能不能替代）与 M_AB（正在发生）'
                     '逐项可归因，V_B 三条 B 路线均接近上限（国外掌控、国内缺位）。')
        lines.append('- 6 个配对上的 S×M 中位数分级粒度粗，仅供示意，不宜作统计结论。')
    lines.append('')
    lines.append('## 五、S×M 态势分级\n')
    if len(ranked) == 0:
        lines.append('（无达标替代候选参与排名，分级不可用；见文末软阈值参考排名附录）\n')
    else:
        s_med = ranked['S_AB'].median()
        m_med = ranked['M_AB'].median()
        s_hi = ranked['S_AB'] > s_med
        m_hi = ranked['M_AB'] > m_med
        lines.append(f'- 分级阈值（中位数）：S={s_med:.4f}，M={m_med:.4f}')
        lines.append(f'- S 高 M 低（有替代能力、尚未成势）：{(s_hi & ~m_hi).sum()} 个主题')
        lines.append(f'- S 高 M 高（替代具有现实可能性）：{(s_hi & m_hi).sum()} 个主题')
        lines.append(f'- S 低 M 高（仅国外新路线扩张）：{(~s_hi & m_hi).sum()} 个主题')
        lines.append(f'- S 低 M 低：{(~s_hi & ~m_hi).sum()} 个主题\n')
    lines.append('## 六、数据质量与局限\n')
    lines.append('1. 主路径各窗口节点仅 21~43 个（pre2000 为 182），p_A,t 稀疏，'
                 'T_AB 对少量节点的增减敏感，解读需谨慎。')
    lines.append('2. 公开国家 ≠ 最终控制权（申请人国籍覆盖仅 57%，未采用）；'
                 'WO/EP 等国际公开按国外处理。')
    if caliber == 'paths':
        kb_note = '（路线版按 B 路线全集计算）'
    elif caliber == 'theme':
        kb_note = '（主题对版按 Y 主题全集计算，文档口径）'
    else:
        kb_note = ''
    lines.append('3. K_B 按主题全集（国内+国外）计算——严格按文档"i∈B"只取国外子集则 '
                 f'K_B 恒为 1，无信息量{kb_note}。')
    n_zero_fj = int((df['F_J'] == 0).sum())
    lines.append(f'4. Jaccard 对照列（F_J/C_J/H_J）显著低于嵌入口径：字符串口径对同义异形'
                 f'零容错，导致 {n_zero_fj} 个{unit}零交集（占总{unit} '
                 f'{n_zero_fj/total_topics:.0%}）；嵌入对称最佳匹配对长尾噪声短语较宽容，'
                 '个别主题的相似度可能被少数通用词（如"信号处理"）抬高。')
    n_zero_fcp = int((df['F_AB'] == 0).sum())
    floor_n = int((ranked['S_AB'] == 1/3).sum())
    lines.append('5. S_AB 存在缺失数据地板：任一侧实体集为空则该维相似度记 0（空集合→0 '
                 f'的约定）；真实数据下 {n_zero_fcp} 个{unit} F=C=P=0、H=1，S_AB 恰为 1/3；'
                 f'参与排名的 {ranked_n} 个{unit}中 {floor_n} 个 S_AB 位于该地板——S×M 分级的'
                 f'"S 低"档对这 {floor_n} 个{unit}是"相似度不可测"而非"测得低"，解读时不可当作'
                 '有实义的替代能力比较。')
    if caliber == 'ipc':
        lines.append('6. 40 个无有效主IPC 的专利未进任何主题；13 个无摘要专利不在 KG 中，'
                     '仅可能出现在主路径节点（计入主路径分母、无主题归属）。')
    elif caliber == 'theme':
        # 终审修复（I-2）：披露 13 条 LLM 标签回显乱码公开号未入主题（与局限#7 的
        # 13 个无摘要专利是不同批次；theme_in=实际入主题数，patent_n 即 2480）
        theme_in = patent_n if patent_n is not None else 2480
        lines.append(f'6. 另有 {2493 - theme_in} 条专利因 LLM 标签回显的公开号乱码'
                     f'（如 US11132625B1→US111326325B1）无法与路由表匹配，未进任何主题'
                     f'（研究数据集实际入主题 {theme_in}/2493）。')
        lines.append('7. 13 个无摘要专利不在 KG 中，仅可能出现在主路径节点'
                     '（计入主路径分母、无主题归属）（指主路径分母节点，'
                     '与上述乱码 13 条是不同批次）。')
    else:
        lines.append('6. 13 个无摘要专利不在 KG 中，仅可能出现在主路径节点'
                     '（计入主路径分母、无主题归属）。')
    hi_idx = 8 if caliber == 'theme' else 7
    lines.append(f'{hi_idx}. 高价值阈值取引文网络内部节点（31899 个）被引次数 top10% 分位'
                 '（约 44 次），对阈值敏感；可在 config.json 调整 high_value_quantile。')
    if caliber == 'paths':
        lines.append(f'8. 原理差异阈值 H≥0.3 在路线版中高度敏感：6 对 H 值全部落在 '
                     f'{h_min:.3f}~{h_max:.3f} 窄带内，达标判定随数据刷新可能翻转；'
                     '解读"达标/未达标"时应结合具体 H 值。')
        patent_note = (f'（研究数据集 {patent_n} 专利、' if patent_n is not None
                       else '（研究数据集 2863 专利、')
        lines.append(f'9. 本报告全部数字基于 2026-08-18 运行数据'
                     f'{patent_note}引文网络内部节点 31899 个）；数据更新后请重跑 '
                     'prepare→embed_similarity→run_all→generate_report。')
    else:
        patent_note = (f'（研究数据集 {patent_n} 专利、' if patent_n is not None
                       else '（研究数据集 2863 专利、')
        note_idx = 9 if caliber == 'theme' else 8
        lines.append(f'{note_idx}. 本报告全部数字基于 2026-08-18 运行数据'
                     f'{patent_note}引文网络内部节点 31899 个）；数据更新后请重跑 '
                     'prepare→embed_similarity→run_all→generate_report。')
    # 主口径无达标候选时：软阈值参考排名附录（非主口径，仅供相对比较）
    if caliber == 'theme' and len(ranked) == 0:
        lines.append('')
        lines.append('## 附录：软阈值参考排名（非主口径）\n')
        lines.append('- 主口径（硬阈值）下无达标替代候选。以下把未过双前提/未达阈值的'
                     f'全部主题对按 S 参考值降序列表——S 参考 = w1·F + w2·C + w3·H '
                     f'（权重 {w["w1"]}:{w["w2"]}:{w["w3"]}，F/C/H 照常计算）——'
                     '仅供相对比较与解读，不构成主口径风险排名。\n')
        soft = df.loc[df['风险排名'].isna()].copy()
        soft['S_ref'] = (w['w1'] * soft['F_AB'] + w['w2'] * soft['C_AB']
                         + w['w3'] * soft['H_AB']) / wsum
        soft = soft.sort_values('S_ref', ascending=False)
        lines.append('| 参考序 | 主题码 | S_ref | F_AB | C_AB | H_AB | 标记 |')
        lines.append('|---|---|---|---|---|---|---|')
        for i, (_, r) in enumerate(soft.head(20).iterrows(), 1):
            lines.append(f'| {i} | {r["主题码"]} | {r["S_ref"]:.4f} | '
                         f'{_fmt(r["F_AB"])} | {_fmt(r["C_AB"])} | {_fmt(r["H_AB"])} | '
                         f'{"" if pd.isna(r["标记"]) else r["标记"]} |')
    return '\n'.join(lines)


def main() -> None:
    with open(os.path.join(ROOT, 'config.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    suffix = cfg.get('input_suffix', '')
    df = pd.read_csv(os.path.join(ROOT, 'outputs', f'替代风险指标总表{suffix}.csv'),
                     dtype={'主题码': str})
    caliber = ('theme' if suffix == '_theme'
               else 'paths' if suffix in ('_paths', '_paths_filtered') else 'ipc')
    # 过滤版（suffix 以 '_filtered' 结尾，即 '_filtered' 与 '_paths_filtered'）：
    # 读相关性过滤统计，供研究域界定节（ipc 版）与尾注专利数参数化
    # （patent_n=保留数，未过滤版 None→2863）
    filtered = suffix.endswith('_filtered')
    domain_stats = None
    if filtered:
        stats = pd.read_csv(os.path.join(ROOT, 'outputs', 'intermediate',
                                         'relevance_filter_stats.csv'))
        domain_stats = stats.iloc[0].to_dict()
    if suffix == '_theme':
        # 主题版尾注：实际进入主题分组的研究数据集专利数（13 条无主题专利除外）
        pt = pd.read_csv(os.path.join(ROOT, 'outputs', 'intermediate',
                                      'patent_route_theme.csv'),
                         usecols=['topic_code'], dtype=str)
        patent_n = int((pt['topic_code'].notna() & (pt['topic_code'] != '')).sum())
    else:
        patent_n = domain_stats.get('patent_kept') if domain_stats else None
    md = render_report(df, cfg, caliber=caliber, domain_stats=domain_stats,
                       patent_n=patent_n, filtered=filtered)
    out = os.path.join(ROOT, 'outputs', f'替代风险报告{suffix}.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'已写 {out}')


if __name__ == '__main__':
    main()
