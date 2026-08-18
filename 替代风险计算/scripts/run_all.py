# -*- coding: utf-8 -*-
"""编排：读中间表 + config，计算 147 主题全部指标，输出指标总表。
input_suffix 机制：config.json 的 input_suffix 非空时读写带后缀的文件
（如 _paths 路线版，patent_route_paths.csv → 替代风险指标总表_paths.csv）。"""
import json
import os

import numpy as np
import pandas as pd

from indicators import THRESHOLD_FLAG, per_topic_indicators

# 注（相对 brief 的一处修正）：BASE_DIR 为 scripts/ 的父目录（替代风险计算），
# 使 ROOT 解析为 替代风险计算 而非 多轨道（多轨道 下无 outputs/ 与 config.json）。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
PROJECT_ROOT = os.path.dirname(ROOT)
INTER_DIR = os.path.join(ROOT, 'outputs', 'intermediate')
OUT_DIR = os.path.join(ROOT, 'outputs')

COLUMN_MAP = {
    'topic_code': '主题码', 'topic_name': '主题名',
    'n_dom': 'n_国内', 'n_for': 'n_国外',
    'F': 'F_AB', 'C': 'C_AB', 'H': 'H_AB', 'S': 'S_AB',
    'F_J': 'F_J', 'C_J': 'C_J', 'H_J': 'H_J',
    'gA': 'g_A', 'gB': 'g_B', 'G': 'G_AB',
    'pA_init': 'p_A初期', 'pA_final': 'p_A末期',
    'pB_init': 'p_B初期', 'pB_final': 'p_B末期',
    'dPA': 'Δp_A', 'dPB': 'Δp_B', 'T': 'T_AB', 'M': 'M_AB',
    'K': 'K_B', 'A': 'A_B', 'V': 'V_B', 'R': 'R_AB',
    'flags': '标记', 'risk_rank': '风险排名',
}
COLUMN_ORDER = list(COLUMN_MAP.values())

# 高价值判定数据源（设计文档 §2）：引文网络全量节点表
NODES_CSV = os.path.join(PROJECT_ROOT, '专利数据合并与引文网络构建',
                         'citation_network_full', 'nodes.csv')


def load_config() -> dict:
    with open(os.path.join(ROOT, 'config.json'), encoding='utf-8') as f:
        return json.load(f)


def parse_sets(s) -> set:
    if pd.isna(s) or s == '':
        return set()
    return set(str(s).split('|'))


def exp_suffix_of(suffix: str) -> str:
    """K/A/V 数据源后缀推导：'_paths'→''、'_paths_filtered'→'_filtered'。"""
    return suffix.replace('_paths', '')


def main() -> None:
    cfg = load_config()
    suffix = cfg.get('input_suffix', '')
    patent = pd.read_csv(os.path.join(INTER_DIR, f'patent_route{suffix}.csv'),
                         dtype={'pub': str, 'topic_code': str, 'year': 'Int64'})
    patent['topic_code'] = patent['topic_code'].fillna('')
    mainpath = pd.read_csv(os.path.join(INTER_DIR, f'mainpath_nodes_by_window{suffix}.csv'),
                           dtype=str)

    sim = pd.read_csv(os.path.join(INTER_DIR, f'entity_sim_by_topic{suffix}.csv'),
                      dtype={'topic_code': str})
    sim_map = {r.topic_code: r for r in sim.itertuples(index=False)}

    mp_nodes = {}
    for win in cfg['windows']:
        mp_nodes[win] = set(mainpath.loc[mainpath['window'] == win, 'pub'])

    # 配对模式（_paths / _paths_filtered 版）：K/A/V 按配对中的 B 路线（Y）全集计算（文档口径）
    exposure_map = {}
    if suffix == '_paths' or suffix == '_paths_filtered':
        exp_suffix = exp_suffix_of(suffix)   # '_paths'→''、'_paths_filtered'→'_filtered'
        routes = pd.read_csv(
            os.path.join(INTER_DIR, f'patent_route_routes{exp_suffix}.csv'),
            dtype={'pub': str, 'topic_code': str, 'year': 'Int64'})
        for code in ('P1', 'P2', 'P3'):
            lst = []
            for r in routes.loc[routes['topic_code'] == code].itertuples(index=False):
                lst.append({
                    'pub': r.pub,
                    'year': r.year if pd.notna(r.year) else None,
                    'in_degree': float(r.in_degree),
                    'func': parse_sets(r.func),
                    'scene': parse_sets(r.scene),
                    'princ': parse_sets(r.princ),
                    'is_cn': int(r.is_cn),
                })
            exposure_map[code] = lst

    # 高价值阈值：研究数据集（引文网络内部节点，即全量专利库）被引次数 top10% 分位
    # 注（相对 brief 的一处修正）：brief 原文对 patent_route.csv 的 in_degree 求分位
    # 得 102.0，与预期 ≈44.0 不符；设计文档 §2 规定高价值判定数据源为 nodes.csv，
    # 其内部节点（is_internal=True，31,899 个）in_degree 的 q90 恰为 44.0。
    cite = pd.read_csv(NODES_CSV, usecols=['is_internal', 'in_degree'])
    threshold = float(np.quantile(
        cite.loc[cite['is_internal'], 'in_degree'], cfg['high_value_quantile']))

    rows = []
    for code, grp in patent.loc[patent['topic_code'] != ''].groupby('topic_code'):
        dom, for_ = [], []
        for r in grp.itertuples(index=False):
            item = {
                'pub': r.pub,
                'year': r.year if pd.notna(r.year) else None,
                'in_degree': float(r.in_degree),
                'func': parse_sets(r.func),
                'scene': parse_sets(r.scene),
                'princ': parse_sets(r.princ),
            }
            (dom if r.is_cn == 1 else for_).append(item)
        rows.append(per_topic_indicators(
            topic_code=code,
            topic_name=grp['topic_name'].iloc[0],
            dom=dom, for_=for_,
            mainpath_nodes=mp_nodes,
            window_ends=cfg['window_ends'],
            high_value_threshold=threshold,
            weights=(cfg['weights']['w1'], cfg['weights']['w2'], cfg['weights']['w3']),
            thresholds=cfg['thresholds'],
            sigmoid_k=cfg['sigmoid_k'],
            min_patents=cfg['min_patents'],
            exposure=exposure_map[code.split('→')[1]] if suffix in ('_paths', '_paths_filtered') else None,
            fch={'F': float(sim_map[code].F_sim),
                 'C': float(sim_map[code].C_sim),
                 'H': 1.0 - float(sim_map[code].P_sim)},
        ))

    df = pd.DataFrame(rows)
    df['flags'] = df['flags'].map(lambda f: ';'.join(f) if f else '')
    df['risk_rank'] = np.nan
    # 软阈值+全量排名：有 R 即参与排名（标记不再排除排名）
    eligible = df['R'].notna()
    ranked = df.loc[eligible].sort_values('R', ascending=False)
    df.loc[ranked.index, 'risk_rank'] = np.arange(1, len(ranked) + 1)

    df = df.rename(columns=COLUMN_MAP)[COLUMN_ORDER]
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f'替代风险指标总表{suffix}.csv')
    df.to_csv(out, index=False, encoding='utf-8-sig')
    qualified = (~df['标记'].str.contains(THRESHOLD_FLAG, na=False)).sum()
    print(f'主题数 {len(df)}，参与排名 {eligible.sum()}，达标主题数 {qualified}，'
          f'高价值阈值(被引) {threshold:.1f}')
    print(f'已写 {out}')


if __name__ == '__main__':
    main()
