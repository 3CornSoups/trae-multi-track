# -*- coding: utf-8 -*-
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_MD = os.path.join(ROOT, '实验二_主路径配对', 'outputs', '主路径全景概况.md')


class TestPathsOverviewSmoke:
    def test_overview_file(self):
        assert os.path.exists(OUT_MD)
        with open(OUT_MD, encoding='utf-8') as f:
            md = f.read()
        # 6 个窗口节 + 3 条路线节
        for w in ['2000 前', '2000-2005', '2000-2010', '2000-2015',
                  '2000-2020', '2000-2026']:
            assert w in md, f'缺少窗口 {w}'
        for p in ['### P1', '### P2', '### P3']:
            assert p in md, f'缺少 {p}'
        # 总行数 sanity：163 条路径明细行（表格行，含表头与分隔行后）
        assert md.count('→') >= 163
