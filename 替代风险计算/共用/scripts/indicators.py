# -*- coding: utf-8 -*-
"""替代风险计算的纯函数指标模块（无 IO，便于单测）。"""
import math

import numpy as np

# 软阈值参考标记的统一魔法字符串（run_all.py / generate_report.py 共用）
THRESHOLD_FLAG = '未达标'


def jaccard(a: set, b: set) -> float:
    """Jaccard 相似度；双方均为空集时定义为 0。"""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def sigmoid_norm(x: float, k: float = 2.0) -> float:
    """sigmoid 归一化 Norm(x)=1/(1+e^(-kx))，x=0 时为 0.5。"""
    return 1.0 / (1.0 + math.exp(-k * x))


def growth_slope(n_series: list) -> float:
    """ln(1+N_t) 对等间隔时点 x=0..len-1 的线性回归斜率（N_t 为累计专利数，恒 ≥0；负输入会产生 NaN）。"""
    y = np.log1p(np.asarray(n_series, dtype=float))
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y), dtype=float)
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


def _cumulative_counts(pubs_by_year: dict, window_ends: list) -> list:
    """按窗口末端年份累计专利数（缺年份的专利不计入）。"""
    counts = []
    for end in window_ends:
        counts.append(sum(n for y, n in pubs_by_year.items()
                          if y is not None and y <= end))
    return counts


def per_topic_indicators(topic_code, topic_name, dom, for_, mainpath_nodes,
                         window_ends, high_value_threshold,
                         weights=(1, 1, 1), thresholds=None,
                         sigmoid_k=2.0, min_patents=3, fch=None,
                         exposure=None, risk_s_power=1.0, risk_mv_power=1.0):
    """计算一个技术主题的全部替代风险指标。

    参数:
      dom / for_: 国内/国外专利列表，每项 {'pub','year','in_degree',
                  'func','scene','princ'}（后三者是 set）
      mainpath_nodes: {window: set(pub)}，按 config.windows 顺序
      window_ends: 各窗口累计末端年份，与 mainpath_nodes 顺序一致
      high_value_threshold: 高价值专利被引次数下限（>= 该值即高价值）
      weights: (w1, w2, w3) 原始权重，内部归一化
      fch: {'F','C','H'} 嵌入相似度覆盖值（None 时用 Jaccard，即旧行为）
      exposure: K/A/V 按此专利列表（含 is_cn）计算；None 时用 dom+for（旧行为）
      risk_s_power / risk_mv_power: 最终风险指数；默认 1/1 即
                  R = S × (M+V)/2；实验三用 0.6/0.4 即
                  R = S^0.6 × ((M+V)/2)^0.4
    返回: dict（见 Task 3 Interfaces 说明），未定义指标为 None。
    """
    if thresholds is None:
        thresholds = {'F': 0.6, 'C': 0.5, 'H': 0.3}
    w = np.asarray(weights, dtype=float)
    w = w / w.sum()

    flags = []
    n_dom, n_for = len(dom), len(for_)
    if n_dom < min_patents or n_for < min_patents:
        flags.append('样本不足')

    def entity_union(patents, key):
        s = set()
        for p in patents:
            s.update(p.get(key) or set())
        return s

    F_j = jaccard(entity_union(dom, 'func'), entity_union(for_, 'func'))
    C_j = jaccard(entity_union(dom, 'scene'), entity_union(for_, 'scene'))
    H_j = 1.0 - jaccard(entity_union(dom, 'princ'), entity_union(for_, 'princ'))

    if fch is not None:
        F, C, H = float(fch['F']), float(fch['C']), float(fch['H'])
    else:
        F, C, H = F_j, C_j, H_j

    # 软阈值：S 恒计算（全量排名），阈值未满足时仅追加参考标记 '未达标'
    S = float(w[0] * F + w[1] * C + w[2] * H)
    if F < thresholds['F'] or C < thresholds['C'] or H < thresholds['H']:
        flags.append(THRESHOLD_FLAG)

    # 相对增长优势：各窗口累计专利数的 ln(1+N) 斜率
    def cumulative(patents):
        by_year = {}
        for p in patents:
            y = p.get('year')
            if y is not None:
                by_year[y] = by_year.get(y, 0) + 1
        return _cumulative_counts(by_year, window_ends)

    N_A = cumulative(dom)
    N_B = cumulative(for_)
    gA = growth_slope(N_A)
    gB = growth_slope(N_B)
    G = sigmoid_norm(gB - gA, sigmoid_k)

    # 主路径地位转移：窗口首(初期)尾(末期)占比差
    dom_pubs = {p['pub'] for p in dom}
    for_pubs = {p['pub'] for p in for_}
    pA, pB = [], []
    for win in mainpath_nodes:
        nodes = mainpath_nodes[win]
        total = len(nodes)
        pA.append(len(nodes & dom_pubs) / total if total else 0.0)
        pB.append(len(nodes & for_pubs) / total if total else 0.0)
    dPA = pA[-1] - pA[0]
    dPB = pB[-1] - pB[0]
    T = sigmoid_norm(dPB - dPA, sigmoid_k)
    M = (G + T) / 2.0

    # 安全暴露度
    all_p = exposure if exposure is not None else dom + for_
    num = sum(p['in_degree'] + 1.0 for p in for_)
    den = sum(p['in_degree'] + 1.0 for p in all_p)
    K = num / den if den > 0 else None

    high = [p for p in all_p if p['in_degree'] >= high_value_threshold]
    if high:
        if exposure is not None:
            A = sum(1 for p in high if p['is_cn'] == 1) / len(high)
        else:
            A = sum(1 for p in high if p['pub'] in dom_pubs) / len(high)
        V = (K + 1.0 - A) / 2.0
    else:
        A = None
        V = None
        flags.append('无高价值专利')

    if S is not None and V is not None:
        mv = (M + V) / 2.0
        # 默认 power=1,1 → 线性乘积；实验三 0.6/0.4 → 加权幂乘
        R = float(S ** risk_s_power * mv ** risk_mv_power)
    else:
        R = None

    return {
        'topic_code': topic_code, 'topic_name': topic_name,
        'n_dom': n_dom, 'n_for': n_for,
        'F': F, 'C': C, 'H': H, 'S': S,
        'F_J': F_j, 'C_J': C_j, 'H_J': H_j,
        'gA': gA, 'gB': gB, 'G': G,
        'pA_init': pA[0], 'pA_final': pA[-1],
        'pB_init': pB[0], 'pB_final': pB[-1],
        'dPA': dPA, 'dPB': dPB, 'T': T, 'M': M,
        'K': K, 'A': A, 'V': V, 'R': R,
        'flags': flags,
    }
