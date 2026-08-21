# -*- coding: utf-8 -*-
"""主题对构建与文档口径门槛（研究方案 3.3）。

产出 patent_route_theme.csv（主题版专利表：topic_code=theme_id、
topic_name=theme_name、problem 列=KG 边表"解决"实体按 pub 聚合的 | 连接）
与 mainpath_nodes_by_window_theme.csv（拷贝过滤版）。配对结构不预建——
run_all theme 模式按 45 个主题的有序对动态计算。
"""
import io
import os
import shutil
import zipfile

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 脚本在 X/scripts/ → 上三级=项目根
INTER_DIR = os.path.join(ROOT, 'outputs', 'intermediate')
KG_ZIP = os.path.join(ROOT, '..', '实体抽取，知识图谱构建', 'bci知识图谱数据包.zip')

PREMISE_PROBLEM_SIM = 0.5   # 前提①：解决同一类技术问题（问题实体集合相似度）
PREMISE_H = 0.3             # 前提②：技术原理存在明显差异
# 硬阈值（仅达标对计算综合得分）；F 按导师建议由 0.6 放宽为 0.5
TH_F, TH_C, TH_H = 0.5, 0.5, 0.3
# 最终风险加权幂：R = S^α × ((M+V)/2)^β（导师给定 α=0.6, β=0.4）
RISK_S_POWER, RISK_MV_POWER = 0.6, 0.4


def premise_pass(problem_sim: float, H: float) -> bool:
    """替代候选双前提：解决同一类问题 且 原理存在明显差异。"""
    return problem_sim >= PREMISE_PROBLEM_SIM and H >= PREMISE_H


def threshold_pass(F: float, C: float, H: float) -> bool:
    """硬阈值：仅满足阈值条件的技术路线对才计算综合得分。"""
    return F >= TH_F and C >= TH_C and H >= TH_H


def load_problem_map() -> dict:
    """KG 边表"解决"关系 → {pub: set(问题实体)}（实体取 target 冒号后缀）。"""
    problem_map = {}
    with zipfile.ZipFile(KG_ZIP) as zf:
        with zf.open('graph_edges.csv') as f:
            edges = pd.read_csv(io.TextIOWrapper(f, encoding='utf-8-sig'), dtype=str)
    for _, r in edges.loc[edges['relation'] == '解决'].iterrows():
        suffix = r['target'].split(':', 1)[1] if ':' in r['target'] else r['target']
        problem_map.setdefault(r['patent_pub'], set()).add(suffix)
    return problem_map


def main() -> None:
    # 输入：过滤后研究数据集的路由表 + Task 14 主题表（每专利一行）
    patent = pd.read_csv(os.path.join(INTER_DIR, 'patent_route_filtered.csv'),
                         dtype={'pub': str, 'topic_code': str})
    theme = pd.read_csv(os.path.join(INTER_DIR, 'patent_theme.csv'), dtype=str)

    # 问题实体：从 KG 边表补"解决"实体（无问题实体则空集合，前提①按空集相似度 0 处理）
    problem_map = load_problem_map()
    patent['problem'] = patent['pub'].map(
        lambda p: '|'.join(sorted(problem_map.get(p, set()))))

    # 主题归并：左连接保留全部 2493 条专利；主题表内个别 LLM 回显的乱码公开号
    # （Task 14 数据质量发现，13 条）与路由表 pub 无法精确匹配 → 该专利主题码留空
    # （沿用 run_all 对无主题专利的既有约定：不参与任何主题分组）。
    merged = patent.merge(theme[['pub', 'theme_id', 'theme_name']],
                          on='pub', how='left')
    merged['topic_code'] = merged['theme_id']
    merged['topic_name'] = merged['theme_name']

    out = merged[['pub', 'topic_code', 'topic_name', 'country', 'is_cn', 'year',
                  'func', 'scene', 'princ', 'in_degree', 'problem']]
    out.to_csv(os.path.join(INTER_DIR, 'patent_route_theme.csv'),
               index=False, encoding='utf-8-sig')

    # 主路径节点长表（主题版沿用过滤版口径）
    shutil.copy(os.path.join(INTER_DIR, 'mainpath_nodes_by_window_filtered.csv'),
                os.path.join(INTER_DIR, 'mainpath_nodes_by_window_theme.csv'))

    n_themed = (out['topic_code'].notna() & (out['topic_code'] != '')).sum()
    print(f'patent_route_theme: {len(out)} 行（主题 {out["topic_code"].nunique()} 个，'
          f'带主题 {n_themed} 条，无主题 {len(out) - n_themed} 条）；'
          f'mainpath_nodes_by_window_theme 已拷贝')


if __name__ == '__main__':
    main()
