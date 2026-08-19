# -*- coding: utf-8 -*-
"""路径路线版：3 条主路径作为技术路线 → patent_route_routes.csv；
6 个跨路线有序配对 → patent_route_paths.csv（schema 同 patent_route）。
input_suffix 机制：config.json 的 input_suffix 非空时读写带该后缀的文件
（patent_route{suffix}.csv → patent_route_routes{suffix}.csv 等，如 _filtered 过滤版）。"""
import json
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 脚本在 X/scripts/ → 上三级=项目根
INTER_DIR = os.path.join(ROOT, 'outputs', 'intermediate')
DS_PATH = os.path.join(ROOT, '..', '数据集合并', 'outputs', '05_合并数据集.csv')
SUMMARY_DIR = os.path.join(ROOT, '..', '路径概括与拓展', 'outputs')


def load_config() -> dict:
    with open(os.path.join(ROOT, 'config.json'), encoding='utf-8') as f:
        return json.load(f)


def build_route_names(summary_dir: str) -> dict:
    """3 条路线名：取 2000_2026 概括的 差异化特征.功能侧重.描述（截 60 字）。"""
    names = {}
    with open(os.path.join(summary_dir, 'period_2000_2026_summary.json'),
              encoding='utf-8') as f:
        d = json.load(f)
    for p in d['paths']:
        pid = int(p['path_id'])
        feat = p.get('差异化特征') or {}
        text = ''
        if isinstance(feat, dict):
            for key in ('功能侧重', '问题侧重'):
                sub = feat.get(key) or {}
                if isinstance(sub, dict) and sub.get('描述'):
                    text = str(sub['描述']).strip()
                    break
        if not text:
            text = str(feat).strip()
        label = text[:60] + ('…' if len(text) > 60 else '')
        names[f'P{pid}'] = label or f'路线{pid}'
    return names


ROUTE_SHORT = {'P1': '推送+测量', 'P2': '数据平台', 'P3': '投放优化'}


def build_pairs_table(routes: pd.DataFrame) -> pd.DataFrame:
    """6 个有序路线对 (X→Y, X≠Y)：dom 行 = X 的 CN 专利，for 行 = Y 的国外专利。"""
    cols = ['pub', 'topic_code', 'topic_name', 'country', 'is_cn',
            'year', 'in_degree', 'func', 'scene', 'princ']
    rows = []
    for x in ('P1', 'P2', 'P3'):
        for y in ('P1', 'P2', 'P3'):
            if x == y:
                continue
            code = f'{x}→{y}'
            name = f'国外{y}（{ROUTE_SHORT[y]}）替代国内{x}（{ROUTE_SHORT[x]}）'
            for _, r in routes.loc[routes['topic_code'] == x].iterrows():
                if int(r['is_cn']) == 1:
                    row = dict(r)
                    row['topic_code'], row['topic_name'] = code, name
                    rows.append(row)
            for _, r in routes.loc[routes['topic_code'] == y].iterrows():
                if int(r['is_cn']) == 0:
                    row = dict(r)
                    row['topic_code'], row['topic_name'] = code, name
                    rows.append(row)
    return pd.DataFrame(rows)[cols]


def build_patent_routes(ds_path: str, patent_route_path: str,
                        summary_dir: str = SUMMARY_DIR) -> pd.DataFrame:
    """05 按 pub 去重归属 path_id（行数多者优先，平局取小号），join patent_route。

    summary_dir：路线名来源目录（period_2000_2026_summary.json 所在目录）。
    """
    ds = pd.read_csv(ds_path, dtype=str)
    ds['path_id'] = ds['path_id'].astype(int)
    cnt = ds.groupby(['pub', 'path_id']).size().reset_index(name='n')
    # 行数多者优先；平局取较小 path_id
    best = (cnt.sort_values(['pub', 'n', 'path_id'], ascending=[True, False, True])
            .groupby('pub', as_index=False).first()[['pub', 'path_id']])
    route = pd.read_csv(patent_route_path, dtype={'pub': str, 'topic_code': str})
    out = best.merge(route, on='pub', how='inner')
    out['topic_code'] = 'P' + out['path_id'].astype(str)
    names = build_route_names(summary_dir)
    out['topic_name'] = out['topic_code'].map(names)
    cols = ['pub', 'topic_code', 'topic_name', 'country', 'is_cn',
            'year', 'in_degree', 'func', 'scene', 'princ']
    return out[cols]


def main() -> None:
    suffix = load_config().get('input_suffix', '')
    patent_route = os.path.join(INTER_DIR, f'patent_route{suffix}.csv')
    out = build_patent_routes(DS_PATH, patent_route)
    out.to_csv(os.path.join(INTER_DIR, f'patent_route_routes{suffix}.csv'),
               index=False, encoding='utf-8-sig')
    pairs = build_pairs_table(out)
    pairs.to_csv(os.path.join(INTER_DIR, f'patent_route_paths{suffix}.csv'),
                 index=False, encoding='utf-8-sig')
    # 主路径分母口径不变：对应版本长表拷贝（suffix='_filtered' 时读过滤版长表）
    mp = pd.read_csv(os.path.join(INTER_DIR, f'mainpath_nodes_by_window{suffix}.csv'),
                     dtype=str)
    mp.to_csv(os.path.join(INTER_DIR, f'mainpath_nodes_by_window_paths{suffix}.csv'),
              index=False, encoding='utf-8-sig')
    print(f'patent_route_routes{suffix}: {len(out)} 行')
    for code, grp in out.groupby('topic_code'):
        print(f'  {code}: {len(grp)} 条（CN {(grp["is_cn"].astype(int) == 1).sum()}）')
    print(f'patent_route_paths{suffix}（配对表）: {len(pairs)} 行')


if __name__ == '__main__':
    main()
