# -*- coding: utf-8 -*-
"""数据准备：从 KG zip / 主路径窗口 / 引文网络 生成中间表。

输出:
  outputs/intermediate/patent_route.csv            每专利一行
  outputs/intermediate/mainpath_nodes_by_window.csv 窗口×主路径节点（长表）
"""
import io
import os
import re
import zipfile
from collections import defaultdict

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

KG_ZIP = os.path.join(PROJECT_ROOT, '实体抽取，知识图谱构建', 'bci知识图谱数据包.zip')
MAINPATH_DIR = os.path.join(PROJECT_ROOT, '主路径识别', 'outputs')
CITATION_NODES = os.path.join(PROJECT_ROOT, '专利数据合并与引文网络构建',
                              'citation_network_full', 'nodes.csv')
OUT_DIR = os.path.join(BASE_DIR, 'outputs', 'intermediate')

WINDOWS = ['pre2000', '2000_2005', '2000_2010', '2000_2015', '2000_2020', '2000_2026']


def normalize_pub(pub: str) -> str:
    """规范化公开号：去连字符、大写、去首尾空白。"""
    return str(pub).replace('-', '').strip().upper()


def _read_zip_csv(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    with zf.open(name) as f:
        return pd.read_csv(io.TextIOWrapper(f, encoding='utf-8-sig'), dtype=str)


def build_patent_table() -> pd.DataFrame:
    """从 KG 边表构建每专利一行：主题/国家/年份/三类实体集合/被引次数。"""
    with zipfile.ZipFile(KG_ZIP) as zf:
        edges = _read_zip_csv(zf, 'graph_edges.csv')
        topic_map = _read_zip_csv(zf, 'ipc_subtopic_map.csv')

    topic_name = dict(zip(topic_map['code'], topic_map['topic']))

    # 每个专利：关系 -> 目标后缀集合（目标形如 "技术方法:植入颅内电极"）
    rel_targets = defaultdict(lambda: defaultdict(set))
    for row in edges.itertuples(index=False):
        pub = normalize_pub(row.patent_pub)
        suffix = row.target.split(':', 1)[1] if ':' in row.target else row.target
        # 属于 的目标形如 "技术主题:电疗器械 (A61N1)"：提取括号内 IPC 大组代码
        if row.relation == '属于':
            m = re.search(r'\(([^()]+)\)$', suffix)
            suffix = m.group(1) if m else suffix
        rel_targets[pub][row.relation].add(suffix)

    rows = []
    for pub, rels in rel_targets.items():
        codes = sorted(rels.get('属于', set()))
        countries = rels.get('公开国家', set())
        years = rels.get('公开年', set())
        year_str = next(iter(years)) if len(years) == 1 else ''
        rows.append({
            'pub': pub,
            'topic_code': codes[0] if len(codes) == 1 else '',
            'topic_name': topic_name.get(codes[0], '') if len(codes) == 1 else '',
            'country': next(iter(countries)) if len(countries) == 1 else '',
            'is_cn': 1 if countries == {'中国'} else 0,
            'year': int(year_str) if year_str.isdigit() else None,
            'func': '|'.join(sorted(rels.get('采用', set()))),
            'scene': '|'.join(sorted(rels.get('应用于', set()))),
            'princ': '|'.join(sorted(rels.get('基于', set()))),
        })

    df = pd.DataFrame(rows)

    # 引文网络入度（被引次数）；查不到的专利按 0
    cite = pd.read_csv(CITATION_NODES, usecols=['node_id', 'in_degree'],
                       dtype={'node_id': str})
    cite['node_id'] = cite['node_id'].map(normalize_pub)
    deg = cite.groupby('node_id')['in_degree'].max()
    df['in_degree'] = df['pub'].map(deg).fillna(0.0)
    return df


def build_mainpath_table() -> pd.DataFrame:
    """各窗口主路径边表的 source/target 去重并集（长表 window, pub）。"""
    rows = []
    for w in WINDOWS:
        path = os.path.join(MAINPATH_DIR, f'window_{w}_edges.csv')
        edges = pd.read_csv(path, usecols=['source', 'target'], dtype=str)
        nodes = set()
        for s, t in zip(edges['source'], edges['target']):
            nodes.add(normalize_pub(s))
            nodes.add(normalize_pub(t))
        rows.extend({'window': w, 'pub': p} for p in sorted(nodes))
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    patent = build_patent_table()
    patent.to_csv(os.path.join(OUT_DIR, 'patent_route.csv'),
                  index=False, encoding='utf-8-sig')
    mainpath = build_mainpath_table()
    mainpath.to_csv(os.path.join(OUT_DIR, 'mainpath_nodes_by_window.csv'),
                    index=False, encoding='utf-8-sig')
    print(f'patent_route: {len(patent)} 行，有主题 '
          f'{(patent["topic_code"] != "").sum()}，CN {patent["is_cn"].sum()}')
    print(f'mainpath 长表: {len(mainpath)} 行')


if __name__ == '__main__':
    main()
