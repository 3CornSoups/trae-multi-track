# -*- coding: utf-8 -*-
import os
import sys

import numpy as np
import pandas as pd
import pytest

# 注：scripts 的 sys.path 由 共用/tests/conftest.py 统一注入（共用 + 实验二 + 实验三 scripts）。
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_CSV = os.path.join(ROOT, '实验一_IPC主题排查', 'outputs', '替代风险指标总表.csv')
NODES_CSV = os.path.join(ROOT, '..', '专利数据合并与引文网络构建',
                         'citation_network_full', 'nodes.csv')
PATENT_ROUTE = os.path.join(ROOT, 'outputs', 'intermediate', 'patent_route.csv')


class TestRunAllSmoke:
    def test_output_csv_exists_and_sane(self):
        assert os.path.exists(OUT_CSV)
        df = pd.read_csv(OUT_CSV, dtype={'主题码': str})
        assert len(df) == 147                       # 147 个技术主题
        assert df['主题名'].notna().all()            # 中文名全覆盖
        assert (df['风险排名'].notna()).sum() >= 1    # 至少一个主题可参与排名
        # 数值域 sanity：S/G/T/M/K/A/V/R 要么空要么在 [0,1]
        for col in ['S_AB', 'G_AB', 'T_AB', 'M_AB', 'K_B', 'A_B', 'V_B', 'R_AB',
                    'F_J', 'C_J', 'H_J']:
            vals = df[col].dropna()
            assert ((vals >= 0) & (vals <= 1)).all(), f'{col} 越界'
        # A61B5 为最大主题，n_国内+n_国外 应等于该主题专利总数
        row = df.loc[df['主题码'] == 'A61B5'].iloc[0]
        assert row['n_国内'] >= 3 and row['n_国外'] >= 3
        # 嵌入口径显著高于 Jaccard 对照（同义异形被捕捉）
        assert df['F_AB'].dropna().mean() > df['F_J'].dropna().mean()
        # 双方都有功能实体的主题（F_AB>0）语义重叠应显著（实测非零均值 0.58，留余量取 0.5）
        assert df.loc[df['F_AB'] > 0, 'F_AB'].mean() > 0.5

    def test_ranking_consistent(self):
        # 软阈值语义：有 R 即参与排名（标记不再排除排名）
        df = pd.read_csv(OUT_CSV, dtype={'主题码': str})
        ranked = df.dropna(subset=['风险排名']).sort_values('风险排名')
        assert ranked['R_AB'].is_monotonic_decreasing   # R 降序
        assert (ranked['风险排名'].tolist()
                == list(range(1, len(ranked) + 1)))     # 1..N 连续整数
        assert df.loc[df['R_AB'].isna(), '风险排名'].isna().all()  # 无 R 则无排名


class TestThresholdSource:
    def test_high_value_threshold_from_citation_nodes(self):
        # 数据冻结断言：阈值必须来自引文网络内部节点 q90（2026-08-17 实测 44.0）
        cite = pd.read_csv(NODES_CSV, usecols=['is_internal', 'in_degree'])
        q90 = float(np.quantile(cite.loc[cite['is_internal'], 'in_degree'], 0.9))
        assert q90 == pytest.approx(44.0)

    def test_a_column_matches_threshold(self):
        # 交叉验证：A61N1 的 A_B 必须等于按 44.0 阈值手工重算的 CN 高价值占比
        cite = pd.read_csv(NODES_CSV, usecols=['is_internal', 'in_degree'])
        q90 = float(np.quantile(cite.loc[cite['is_internal'], 'in_degree'], 0.9))
        route = pd.read_csv(PATENT_ROUTE, dtype={'pub': str, 'topic_code': str})
        sub = route[route['topic_code'] == 'A61N1']
        high = sub[sub['in_degree'] >= q90]
        manual_a = high['is_cn'].astype(int).mean()
        out = pd.read_csv(OUT_CSV, dtype={'主题码': str})
        csv_a = out.loc[out['主题码'] == 'A61N1', 'A_B'].iloc[0]
        assert manual_a == pytest.approx(csv_a)


class TestEmbedAssembly:
    def test_fch_assembly_matches_sim_table(self):
        sim = pd.read_csv(os.path.join(ROOT, 'outputs', 'intermediate',
                                       'entity_sim_by_topic.csv'),
                          dtype={'topic_code': str})
        out = pd.read_csv(OUT_CSV, dtype={'主题码': str})
        merged = out.merge(sim, left_on='主题码', right_on='topic_code')
        assert len(merged) == 147
        assert np.allclose(merged['F_AB'], merged['F_sim'])
        assert np.allclose(merged['H_AB'], 1.0 - merged['P_sim'])


PATHS_CSV = os.path.join(ROOT, '实验二_主路径配对', 'outputs', '替代风险指标总表_paths.csv')

PAIRS = [f'{x}→{y}' for x in ('P1', 'P2', 'P3') for y in ('P1', 'P2', 'P3') if x != y]


class TestPathsRun:
    def test_paths_outputs_exist(self):
        assert os.path.exists(PATHS_CSV)
        df = pd.read_csv(PATHS_CSV, dtype={'主题码': str})
        assert len(df) == 6
        assert set(df['主题码']) == set(PAIRS)
        assert (df['n_国内'] >= 3).all() and (df['n_国外'] >= 3).all()
        assert (df['风险排名'].notna()).sum() >= 1
        for col in ['S_AB', 'G_AB', 'T_AB', 'M_AB', 'K_B', 'A_B', 'V_B', 'R_AB']:
            vals = df[col].dropna()
            assert ((vals >= 0) & (vals <= 1)).all(), f'{col} 越界'

    def test_exposure_equivalence(self):
        # exposure 语义：同一 B 路线(Y)的两对 K/A/V 必须相等
        df = pd.read_csv(PATHS_CSV, dtype={'主题码': str})
        assert df.loc[df['主题码'] == 'P1→P2', 'K_B'].iloc[0] == \
               df.loc[df['主题码'] == 'P3→P2', 'K_B'].iloc[0]


class TestExpSuffix:
    def test_exposure_suffix_derivation(self):
        from run_all import exp_suffix_of
        assert exp_suffix_of('_paths') == ''
        assert exp_suffix_of('_paths_filtered') == '_filtered'
        assert exp_suffix_of('') == ''


class TestPathsEmbedAssembly:
    def test_paths_assembly_matches_sim_table(self):
        sim = pd.read_csv(os.path.join(ROOT, 'outputs', 'intermediate',
                                       'entity_sim_by_topic_paths.csv'),
                          dtype={'topic_code': str})
        out = pd.read_csv(PATHS_CSV, dtype={'主题码': str})
        merged = out.merge(sim, left_on='主题码', right_on='topic_code')
        assert len(merged) == 6
        assert np.allclose(merged['F_AB'], merged['F_sim'])
        assert np.allclose(merged['H_AB'], 1.0 - merged['P_sim'])


FILTERED_CSV = os.path.join(ROOT, '实验一_IPC主题排查', 'outputs', '替代风险指标总表_filtered.csv')
PATHS_FILTERED_CSV = os.path.join(ROOT, '实验二_主路径配对', 'outputs', '替代风险指标总表_paths_filtered.csv')


class TestFilteredRun:
    def test_filtered_outputs_exist(self):
        assert os.path.exists(FILTERED_CSV)
        df = pd.read_csv(FILTERED_CSV, dtype={'主题码': str})
        # 修正记录（数据驱动，2026-08-18）：brief 原断言 len==147"主题全集仍在"与实测不符——
        # run_all 只按非空主题码分组，过滤后保留 133 个主题（stats topics_kept=133，
        # 147 全集含 14 个被整体排除的主题），按 brief"以实际为准"改为 133。
        assert len(df) == 133
        assert (df['n_国内'] + df['n_国外']).sum() < 2863  # 过滤后专利数少于全量
        assert (df['风险排名'].notna()).sum() >= 1
        for col in ['S_AB', 'R_AB']:
            vals = df[col].dropna()
            assert ((vals >= 0) & (vals <= 1)).all(), f'{col} 越界'


class TestPathsFilteredRun:
    def test_paths_filtered_outputs_exist(self):
        assert os.path.exists(PATHS_FILTERED_CSV)
        df = pd.read_csv(PATHS_FILTERED_CSV, dtype={'主题码': str})
        assert len(df) == 6
        assert set(df['主题码']) == set(PAIRS)
        assert (df['风险排名'].notna()).sum() >= 1
        for col in ['S_AB', 'R_AB']:
            vals = df[col].dropna()
            assert ((vals >= 0) & (vals <= 1)).all(), f'{col} 越界'


THEME_CSV = os.path.join(ROOT, '实验三_要素凝练主题', 'outputs', '替代风险指标总表_theme.csv')


class TestThemeRun:
    def test_theme_outputs_exist(self):
        assert os.path.exists(THEME_CSV)
        df = pd.read_csv(THEME_CSV, dtype={'主题码': str})
        assert len(df) >= 10                       # 主题对数（N×(N-1) 的达标子集或全部留行）
        ranked = df.loc[df['风险排名'].notna()]
        assert len(ranked) >= 1                    # 至少一个达标对参与排名（若为 0 停下核对并报告）
        for col in ['S_AB', 'R_AB']:
            vals = df[col].dropna()
            assert ((vals >= 0) & (vals <= 1)).all(), f'{col} 越界'
        # 硬阈值语义：有排名的行 F/C/H 必须全部达标
        for _, r in ranked.iterrows():
            assert r['F_AB'] >= 0.6 and r['C_AB'] >= 0.5 and r['H_AB'] >= 0.3
        # 终审修复（M-建议-4）：计数断言（1980 对 / 30 未过前提 / 230 未达阈值 /
        # 140 无高价值 / 1580 达标排名；Top1=C31→C8 R=0.5084）
        n_premise = (df['标记'].fillna('').str.contains('未过前提')).sum()
        n_thr = (df['标记'].fillna('').str.contains('未达阈值')).sum()
        n_no_hv = (df['标记'].fillna('').str.contains('无高价值专利')).sum()
        assert len(df) == 1980
        assert n_premise == 30 and n_thr == 230 and n_no_hv == 140
        assert (df['风险排名'].notna()).sum() == 1580
        top = df.dropna(subset=['风险排名']).sort_values('风险排名').iloc[0]
        assert top['主题码'] == 'C31→C8'
        assert abs(top['R_AB'] - 0.5084) < 0.001
        # 终审修复（M-建议-5）：问题相似度（前提①）落盘——theme 版全表该列有值
        assert (df['问题相似度'].notna()).sum() == len(df)
