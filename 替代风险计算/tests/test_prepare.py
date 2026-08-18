# -*- coding: utf-8 -*-
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from prepare import normalize_pub  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTER = os.path.join(ROOT, 'outputs', 'intermediate')


class TestNormalizePub:
    def test_strip_hyphen_and_case(self):
        assert normalize_pub('us-2004-0102828-a1') == 'US20040102828A1'

    def test_whitespace(self):
        assert normalize_pub(' CN115281682B ') == 'CN115281682B'


class TestPrepareSmoke:
    def test_patent_route_shape(self):
        df = pd.read_csv(os.path.join(INTER, 'patent_route.csv'), dtype=str)
        assert len(df) == 2863                       # KG Patent 节点数
        assert df['is_cn'].astype(int).sum() == 705  # KG 公开国家=中国 的专利数
        assert (df['topic_code'].fillna('') != '').sum() == 2823  # 40 个无有效主IPC 无主题边（pandas 3.0 read_csv 将空单元格读为 NaN，需先 fillna('')）

    def test_patent_route_spot_check(self):
        df = pd.read_csv(os.path.join(INTER, 'patent_route.csv'), dtype=str)
        row = df.loc[df['pub'] == 'US20040102828A1'].iloc[0]
        assert row['topic_code'] == 'A61N1'   # 主IPC A61N1/05 → 大组 A61N1
        assert row['country'] == '美国'
        assert row['year'] == '2003'          # 申请年
        assert row['in_degree'] != ''         # 引文网络有记录

    def test_mainpath_counts(self):
        df = pd.read_csv(os.path.join(INTER, 'mainpath_nodes_by_window.csv'), dtype=str)
        counts = df.groupby('window')['pub'].nunique().to_dict()
        # 预期值为 2026-08-17 实测（边表 source/target 去重并集）；若不一致先核对窗口文件再改
        assert counts == {
            'pre2000': 182, '2000_2005': 21, '2000_2010': 40,
            '2000_2015': 43, '2000_2020': 34, '2000_2026': 38,
        }
