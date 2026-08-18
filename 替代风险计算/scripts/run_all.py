# -*- coding: utf-8 -*-
"""编排：读中间表 + config，计算 147 主题全部指标，输出指标总表。
input_suffix 机制：config.json 的 input_suffix 非空时读写带后缀的文件
（如 _paths 路线版，patent_route_paths.csv → 替代风险指标总表_paths.csv）。"""
import json
import os

import numpy as np
import pandas as pd

from embed_similarity import load_entity_vectors, symmetric_max_match
from indicators import THRESHOLD_FLAG, jaccard, per_topic_indicators
from theme_pairs import premise_pass, threshold_pass

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
    'problem_sim': '问题相似度',   # 终审修复（M-建议-5）：主题版前提①（问题相似度）落盘
}
COLUMN_ORDER = list(COLUMN_MAP.values())
# 终审修复（M-建议-5）：'问题相似度' 置于列序末尾（'风险排名' 之前）；
# 仅 theme 版该列有值，IPC/配对版该列全空（不影响既有按列名取值断言）。
COLUMN_ORDER.remove('问题相似度')
COLUMN_ORDER.insert(COLUMN_ORDER.index('风险排名'), '问题相似度')

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


def _union(patents: list, key: str) -> set:
    s = set()
    for p in patents:
        s |= p.get(key) or set()
    return s


def _main_theme(cfg: dict) -> None:
    """主题对版（实验三，文档口径 3.3）：45 个主题的有序对 (X→Y, X≠Y)。

    对每个有序对动态计算 6 类实体集合的嵌入对称最佳匹配：
    problem_sim（前提①，≥0.5）与 F/C/H（P_sim→H=1−P_sim）；双前提全过才进入
    硬阈值判定（F≥0.6/C≥0.5/H≥0.3），硬阈值全过才调用 per_topic_indicators
    计算 S 与后续指标（R）；未过前提/未达阈值的对留行带标记、S/R 空、不参与排名。
    dom=主题 X 的中国专利、for=主题 Y 的国外专利、exposure=主题 Y 全集（K/A/V）。
    """
    patent = pd.read_csv(os.path.join(INTER_DIR, 'patent_route_theme.csv'),
                         dtype={'pub': str, 'topic_code': str, 'year': 'Int64'})
    patent['topic_code'] = patent['topic_code'].fillna('')
    mainpath = pd.read_csv(os.path.join(INTER_DIR, 'mainpath_nodes_by_window_theme.csv'),
                           dtype=str)

    mp_nodes = {}
    for win in cfg['windows']:
        mp_nodes[win] = set(mainpath.loc[mainpath['window'] == win, 'pub'])

    cite = pd.read_csv(NODES_CSV, usecols=['is_internal', 'in_degree'])
    threshold = float(np.quantile(
        cite.loc[cite['is_internal'], 'in_degree'], cfg['high_value_quantile']))

    # 实体向量：复用 embed_similarity 缓存（func/scene/princ）；问题实体不在缓存内，
    # 用同一模型补编缺失实体后拼接到全量矩阵（每次运行都按当前 KG 增量编码，不写缓存）。
    names, vecs = load_entity_vectors()
    problem_entities = set()
    for s in patent['problem']:
        problem_entities |= parse_sets(s)
    missing = sorted(problem_entities - set(names))
    if missing:
        # 本机离线环境：仅用本地 HF 缓存加载 bge 模型（不访问 huggingface.co）
        os.environ.setdefault('HF_HUB_OFFLINE', '1')
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(cfg['embed_model'])
        extra = model.encode(missing, batch_size=256, show_progress_bar=False,
                             normalize_embeddings=True)
        names = names + missing
        vecs = np.vstack([vecs, extra])
    idx = {n: i for i, n in enumerate(names)}

    def set_vecs(es: set) -> np.ndarray:
        ids = sorted(idx[n] for n in es)
        return vecs[ids] if ids else np.zeros((0, vecs.shape[1]))

    # 每主题专利列表 + 预缓存 4 类实体集合向量（避免 1980 个有序对重复编码/取行）
    theme_patents = {}
    theme_names = {}
    for code, grp in patent.loc[patent['topic_code'] != ''].groupby('topic_code'):
        rows = []
        for r in grp.itertuples(index=False):
            rows.append({
                'pub': r.pub,
                'year': r.year if pd.notna(r.year) else None,
                'in_degree': float(r.in_degree),
                'func': parse_sets(r.func),
                'scene': parse_sets(r.scene),
                'princ': parse_sets(r.princ),
                'problem': parse_sets(r.problem),
                'is_cn': int(r.is_cn),
            })
        theme_patents[code] = rows
        theme_names[code] = grp['topic_name'].iloc[0]

    vec_cache = {code: {k: set_vecs(_union(rows, k)) for k in
                        ('problem', 'func', 'scene', 'princ')}
                 for code, rows in theme_patents.items()}

    def sim(a: np.ndarray, b: np.ndarray) -> float:
        if a.shape[0] == 0 or b.shape[0] == 0:
            return 0.0   # 空集合 → 该维相似度记 0（embed_similarity 同口径）
        return symmetric_max_match(a, b)

    def gated_row(x, y, F, C, H, problem_sim, mark):
        return {
            'topic_code': f'{x}→{y}',
            'topic_name': f'{theme_names[x]}→{theme_names[y]}',
            'n_dom': len([p for p in theme_patents[x] if p['is_cn'] == 1]),
            'n_for': len([p for p in theme_patents[y] if p['is_cn'] == 0]),
            'F': F, 'C': C, 'H': H, 'S': None,
            'F_J': jaccard(_union(theme_patents[x], 'func'),
                           _union(theme_patents[y], 'func')),
            'C_J': jaccard(_union(theme_patents[x], 'scene'),
                           _union(theme_patents[y], 'scene')),
            'H_J': 1.0 - jaccard(_union(theme_patents[x], 'princ'),
                                 _union(theme_patents[y], 'princ')),
            'gA': None, 'gB': None, 'G': None,
            'pA_init': None, 'pA_final': None,
            'pB_init': None, 'pB_final': None,
            'dPA': None, 'dPB': None, 'T': None, 'M': None,
            'K': None, 'A': None, 'V': None, 'R': None,
            'flags': [mark],
            'problem_sim': problem_sim,
        }

    rows = []
    themes = sorted(theme_patents)
    for x in themes:
        for y in themes:
            if x == y:
                continue
            problem_sim = sim(vec_cache[x]['problem'], vec_cache[y]['problem'])
            F = sim(vec_cache[x]['func'], vec_cache[y]['func'])
            C = sim(vec_cache[x]['scene'], vec_cache[y]['scene'])
            H = 1.0 - sim(vec_cache[x]['princ'], vec_cache[y]['princ'])
            if not premise_pass(problem_sim, H):
                rows.append(gated_row(x, y, F, C, H, problem_sim, '未过前提'))
                continue
            if not threshold_pass(F, C, H):
                rows.append(gated_row(x, y, F, C, H, problem_sim, '未达阈值'))
                continue
            dom = [p for p in theme_patents[x] if p['is_cn'] == 1]
            for_ = [p for p in theme_patents[y] if p['is_cn'] == 0]
            row = per_topic_indicators(
                topic_code=f'{x}→{y}',
                topic_name=f'{theme_names[x]}→{theme_names[y]}',
                dom=dom, for_=for_,
                mainpath_nodes=mp_nodes,
                window_ends=cfg['window_ends'],
                high_value_threshold=threshold,
                weights=(cfg['weights']['w1'], cfg['weights']['w2'], cfg['weights']['w3']),
                thresholds=cfg['thresholds'],
                sigmoid_k=cfg['sigmoid_k'],
                min_patents=cfg['min_patents'],
                exposure=theme_patents[y],
                fch={'F': F, 'C': C, 'H': H},
            )
            row['problem_sim'] = problem_sim   # 终审修复（M-建议-5）
            rows.append(row)

    df = pd.DataFrame(rows)
    df['flags'] = df['flags'].map(lambda f: ';'.join(f) if f else '')
    df['risk_rank'] = np.nan
    eligible = df['R'].notna()
    ranked = df.loc[eligible].sort_values('R', ascending=False)
    df.loc[ranked.index, 'risk_rank'] = np.arange(1, len(ranked) + 1)

    df = df.rename(columns=COLUMN_MAP)[COLUMN_ORDER]
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, '替代风险指标总表_theme.csv')
    df.to_csv(out, index=False, encoding='utf-8-sig')
    n_premise = int(df['标记'].str.contains('未过前提', na=False).sum())
    n_thr = int(df['标记'].str.contains('未达阈值', na=False).sum())
    print(f'主题 {len(themes)} 个，主题对 {len(df)}，未过前提 {n_premise}，'
          f'未达阈值 {n_thr}，达标候选 {eligible.sum()}，'
          f'高价值阈值(被引) {threshold:.1f}')
    print(f'已写 {out}')


def main() -> None:
    cfg = load_config()
    suffix = cfg.get('input_suffix', '')
    if suffix == '_theme':
        return _main_theme(cfg)
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
    df['problem_sim'] = np.nan   # 终审修复（M-建议-5）：IPC/配对版该列留空
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
