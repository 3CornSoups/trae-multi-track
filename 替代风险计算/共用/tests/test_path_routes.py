# -*- coding: utf-8 -*-
import os
import sys

import pandas as pd

from path_routes import build_route_names, build_patent_routes, build_pairs_table  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTER = os.path.join(ROOT, 'outputs', 'intermediate')


class TestBuildRouteNames:
    def test_three_routes(self):
        # smoke：真实概括目录（与 TestPrepareSmoke 同风格）
        names = build_route_names(
            os.path.join(ROOT, '..', '路径概括与拓展', 'outputs'))
        assert set(names) == {'P1', 'P2', 'P3'}
        assert all(names[k] for k in names)  # 非空

    def test_route_names_fallback_chain(self, tmp_path):
        import json
        summary = {
            'paths': [
                {'path_id': 1, '差异化特征': {'功能侧重': {'描述': '侧重A' * 25}, '问题侧重': {'描述': '问题A'}}},
                {'path_id': 2, '差异化特征': {'问题侧重': {'描述': '问题B'}}},
                {'path_id': 3, '差异化特征': '纯文本C'},
            ]
        }
        with open(os.path.join(str(tmp_path), 'period_2000_2026_summary.json'),
                  'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False)
        names = build_route_names(str(tmp_path))
        assert names['P1'].startswith('侧重A侧重A')
        assert names['P1'].endswith('…') and len(names['P1']) == 61  # 60 字 + 省略号
        assert names['P2'] == '问题B'
        assert names['P3'] == '纯文本C'


class TestBuildPatentRoutes:
    def test_dedup_and_join(self, tmp_path):
        # 构造 ds：PUBX 在 P1 有 2 行、P2 有 1 行 → 归 P1（行数多者优先）
        ds = pd.DataFrame([
            {'period': '2000_2005', 'path_id': '1', 'pub': 'PUBX'},
            {'period': '2000_2010', 'path_id': '1', 'pub': 'PUBX'},
            {'period': '2000_2015', 'path_id': '2', 'pub': 'PUBX'},
            {'period': '2000_2005', 'path_id': '2', 'pub': 'PUBY'},
            {'period': '2000_2005', 'path_id': '3', 'pub': 'PUBZ'},
            {'period': '2000_2026', 'path_id': '3', 'pub': 'PUBZ'},
        ])
        ds_path = os.path.join(str(tmp_path), 'ds.csv')
        ds.to_csv(ds_path, index=False, encoding='utf-8-sig')
        route = pd.DataFrame([
            {'pub': 'PUBX', 'topic_code': 'A61B5', 'topic_name': 'x',
             'country': '美国', 'is_cn': 0, 'year': 2003, 'in_degree': 5.0,
             'func': 'a|b', 'scene': 'x', 'princ': 'p'},
            {'pub': 'PUBY', 'topic_code': 'A61N1', 'topic_name': 'y',
             'country': '中国', 'is_cn': 1, 'year': 2010, 'in_degree': 1.0,
             'func': 'c', 'scene': 'y', 'princ': 'q'},
            {'pub': 'PUBZ', 'topic_code': '', 'topic_name': '',
             'country': '中国', 'is_cn': 1, 'year': 2022, 'in_degree': 0.0,
             'func': '', 'scene': '', 'princ': ''},
        ])
        route_path = os.path.join(str(tmp_path), 'route.csv')
        route.to_csv(route_path, index=False, encoding='utf-8-sig')
        out = build_patent_routes(ds_path, route_path)
        assert len(out) == 3                       # 三条 pub 都 join 成功
        got = out.set_index('pub')
        assert got.loc['PUBX', 'topic_code'] == 'P1'   # 行数多者优先
        assert got.loc['PUBY', 'topic_code'] == 'P2'
        assert got.loc['PUBZ', 'topic_code'] == 'P3'
        assert got.loc['PUBX', 'is_cn'] == 0       # 原始列保留
        assert got.loc['PUBX', 'func'] == 'a|b'

    def test_tie_break_smaller_path_id(self, tmp_path):
        # 平局用例：PUBT 在 P1/P2 各 1 行 → 平局取较小 path_id（P1）
        ds = pd.DataFrame([
            {'period': '2000_2005', 'path_id': '1', 'pub': 'PUBT'},
            {'period': '2000_2010', 'path_id': '2', 'pub': 'PUBT'},
        ])
        ds_path = os.path.join(str(tmp_path), 'ds.csv')
        ds.to_csv(ds_path, index=False, encoding='utf-8-sig')
        route = pd.DataFrame([
            {'pub': 'PUBT', 'topic_code': 'A61B5', 'topic_name': 't',
             'country': '美国', 'is_cn': 0, 'year': 2005, 'in_degree': 2.0,
             'func': 'a', 'scene': 't', 'princ': 'r'},
        ])
        route_path = os.path.join(str(tmp_path), 'route.csv')
        route.to_csv(route_path, index=False, encoding='utf-8-sig')
        out = build_patent_routes(ds_path, route_path)
        assert len(out) == 1
        got = out.set_index('pub')
        assert got.loc['PUBT', 'topic_code'] == 'P1'   # 平局取较小 path_id


class TestBuildPairsTable:
    def test_six_pairs(self):
        routes = pd.DataFrame([
            {'pub': 'CNX', 'topic_code': 'P1', 'topic_name': 'x', 'country': '中国',
             'is_cn': 1, 'year': 2010, 'in_degree': 1.0,
             'func': 'a', 'scene': 'x', 'princ': 'p'},
            {'pub': 'USX', 'topic_code': 'P1', 'topic_name': 'x', 'country': '美国',
             'is_cn': 0, 'year': 2011, 'in_degree': 2.0,
             'func': 'b', 'scene': 'y', 'princ': 'q'},
            {'pub': 'USY', 'topic_code': 'P2', 'topic_name': 'y', 'country': '美国',
             'is_cn': 0, 'year': 2012, 'in_degree': 3.0,
             'func': 'c', 'scene': 'z', 'princ': 'r'},
            {'pub': 'CNY', 'topic_code': 'P2', 'topic_name': 'y', 'country': '中国',
             'is_cn': 1, 'year': 2009, 'in_degree': 4.0,
             'func': 'd', 'scene': 'w', 'princ': 's'},
        ])
        pairs = build_pairs_table(routes)
        assert set(pairs['topic_code']) == {'P1→P2', 'P1→P3', 'P2→P1',
                                            'P2→P3', 'P3→P1', 'P3→P2'}
        # P1→P2：dom=P1 的 CN(CNX)、for=P2 的国外(USY)；USX(P1 国外) 不进 P1→P2
        sub = pairs[pairs['topic_code'] == 'P1→P2']
        assert set(sub['pub']) == {'CNX', 'USY'}
        assert sub[sub['pub'] == 'CNX'].iloc[0]['topic_name'] == '国外P2（数据平台）替代国内P1（推送+测量）'
        # 行数 = Σ_{对} (X 的 CN 数 + Y 的国外数) = CNX*2 + CNY*2 + USX*2 + USY*2 = 8
        assert len(pairs) == 8
