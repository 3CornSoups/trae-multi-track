# -*- coding: utf-8 -*-
import os
import sys

import pandas as pd

from generate_report import render_report  # noqa: E402


def test_render_report():
    df = pd.DataFrame([{
        '主题码': 'A61B5', '主题名': '身体诊断测量',
        'n_国内': 220, 'n_国外': 900, 'F_AB': 0.8, 'C_AB': 0.7, 'H_AB': 0.6,
        'S_AB': 0.7, 'F_J': 0.3, 'C_J': 0.2, 'H_J': 0.4,
        'G_AB': 0.6, 'T_AB': 0.9, 'M_AB': 0.75,
        'K_B': 0.8, 'A_B': 0.2, 'V_B': 0.8, 'R_AB': 0.5425,
        '标记': '', '风险排名': 1.0,
    }])
    md = render_report(df, {'weights': {'w1': 1, 'w2': 1, 'w3': 1},
                            'thresholds': {'F': 0.6, 'C': 0.5, 'H': 0.3},
                            'high_value_quantile': 0.9}, top_n=20)
    assert '替代风险计算报告' in md
    assert 'Top-20' in md
    assert 'A61B5' in md
    assert '身体诊断测量' in md
    assert 'S_AB = w1·F_AB + w2·C_AB + w3·H_AB' in md  # 方法段存在
    assert '结论摘要' not in md  # ipc 口径无路线版摘要


def test_domain_stats_section():
    df = pd.DataFrame([{  # 与 test_render_report 相同的单行 fixture
        '主题码': 'A61B5', '主题名': '身体诊断测量',
        'n_国内': 220, 'n_国外': 900, 'F_AB': 0.8, 'C_AB': 0.7, 'H_AB': 0.6,
        'S_AB': 0.7, 'F_J': 0.3, 'C_J': 0.2, 'H_J': 0.4,
        'G_AB': 0.6, 'T_AB': 0.9, 'M_AB': 0.75,
        'K_B': 0.8, 'A_B': 0.2, 'V_B': 0.8, 'R_AB': 0.5425,
        '标记': '', '风险排名': 1.0,
    }])
    stats = {'patent_total': 2863, 'patent_kept': 2493, 'patent_dropped': 370,
             'mainpath_total': 358, 'mainpath_kept': 231, 'mainpath_dropped': 127,
             'topics_total': 147, 'topics_kept': 133, 'cn_kept': 660,
             'judged': 2969, 'relevant': 2582, 'irrelevant': 387,
             'mainpath_no_text': 74}
    md = render_report(df, {'weights': {'w1': 1, 'w2': 1, 'w3': 1},
                            'thresholds': {'F': 0.6, 'C': 0.5, 'H': 0.3},
                            'high_value_quantile': 0.9},
                       domain_stats=stats)
    assert '研究域界定（BCI 相关性过滤）' in md
    assert '2863 → 保留 2493' in md
    assert '2969' in md and '2582' in md
    assert 'G06Q30' in md


def test_paths_summary():
    df = pd.DataFrame([{
        '主题码': 'P1→P2', '主题名': '国外P2（数据平台）替代国内P1（推送+测量）',
        'n_国内': 212, 'n_国外': 634, 'F_AB': 0.6, 'C_AB': 0.6, 'H_AB': 0.3,
        'S_AB': 0.6034, 'F_J': 0.01, 'C_J': 0.01, 'H_J': 1.0,
        'G_AB': 0.5, 'T_AB': 0.4, 'M_AB': 0.4509,
        'K_B': 0.96, 'A_B': 0.01, 'V_B': 0.97, 'R_AB': 0.43,
        '标记': '未达标', '风险排名': 1.0,
    }])
    params = {'weights': {'w1': 1, 'w2': 1, 'w3': 1},
              'thresholds': {'F': 0.6, 'C': 0.5, 'H': 0.3},
              'high_value_quantile': 0.9}
    md = render_report(df, params, caliber='paths')
    assert '结论摘要（先读这里）' in md
    assert '一句话结论' in md
    assert '技术路线全景：全部主路径的技术主线' in md
    assert '各窗口主路径总览' in md          # 全景嵌入（163 条路径明细随真实数据生成）
    assert '国外P2（数据平台）替代国内P1（推送+测量）' in md
    assert '跨路线' in md
    assert '96%~96% 被国外专利掌控' in md   # 动态数字来自表
    md_ipc = render_report(df, params)
    assert '结论摘要' not in md_ipc
