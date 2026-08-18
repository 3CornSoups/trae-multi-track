# -*- coding: utf-8 -*-
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from indicators import jaccard, sigmoid_norm, growth_slope, per_topic_indicators  # noqa: E402


class TestJaccard:
    def test_both_empty(self):
        assert jaccard(set(), set()) == 0.0

    def test_no_overlap(self):
        assert jaccard({'a'}, {'b'}) == 0.0

    def test_identical(self):
        assert jaccard({'a', 'b'}, {'a', 'b'}) == 1.0

    def test_partial(self):
        assert jaccard({'a', 'b'}, {'b', 'c'}) == pytest.approx(1 / 3)

    def test_one_empty(self):
        assert jaccard({'a'}, set()) == 0.0


class TestSigmoidNorm:
    def test_zero_gives_half(self):
        assert sigmoid_norm(0.0) == pytest.approx(0.5)

    def test_symmetry(self):
        assert sigmoid_norm(-1.0) == pytest.approx(1.0 - sigmoid_norm(1.0))

    def test_monotonic(self):
        assert sigmoid_norm(-1.0) < sigmoid_norm(0.0) < sigmoid_norm(1.0)

    def test_known_value(self):
        assert sigmoid_norm(1.0, k=2.0) == pytest.approx(1.0 / (1.0 + math.exp(-2.0)))


class TestGrowthSlope:
    def test_exponential_growth(self):
        # N_t = e^{0.5t} - 1 → ln(1+N_t) = 0.5t → 斜率恰为 0.5
        series = [math.exp(0.5 * t) - 1.0 for t in range(4)]
        assert growth_slope(series) == pytest.approx(0.5, abs=1e-9)

    def test_flat_series(self):
        assert growth_slope([0, 0, 0]) == pytest.approx(0.0, abs=1e-12)

    def test_short_series(self):
        assert growth_slope([5]) == 0.0

    def test_empty_series(self):
        assert growth_slope([]) == 0.0


WINDOWS = ['pre2000', '2000_2005', '2000_2010', '2000_2015', '2000_2020', '2000_2026']
WINDOW_ENDS = [1999, 2005, 2010, 2015, 2020, 2026]


def make_patents(specs):
    """specs: [(pub, year, in_degree, func_set, scene_set, princ_set), ...]"""
    return [
        {'pub': p, 'year': y, 'in_degree': d,
         'func': set(f), 'scene': set(s), 'princ': set(pr)}
        for p, y, d, f, s, pr in specs
    ]


def empty_mainpath():
    return {w: set() for w in WINDOWS}


class TestPerTopicIndicators:
    def test_min_patents_flag(self):
        dom = make_patents([('CN1', 2010, 0, {'a'}, {'x'}, {'p1'}),
                            ('CN2', 2012, 0, {'a'}, {'x'}, {'p1'})])
        for_ = make_patents([('US1', 2010, 0, {'a'}, {'x'}, {'q'}),
                             ('US2', 2011, 0, {'a'}, {'x'}, {'q'}),
                             ('US3', 2012, 0, {'a'}, {'x'}, {'q'})])
        r = per_topic_indicators('A61B5', '身体诊断测量', dom, for_,
                                 empty_mainpath(), WINDOW_ENDS, 10)
        assert '样本不足' in r['flags']
        assert r['n_dom'] == 2 and r['n_for'] == 3

    def test_full_happy_path(self):
        # 国内专利年份全部 <2000 → N_A 六窗口恒为 3 → gA=0；
        # 国外专利年份 2022-2025 → N_B 仅末窗口为 3 → gB>0 → G>0.5
        dom = make_patents([('CN1', 1999, 0, {'a', 'b'}, {'x'}, {'p1'}),
                            ('CN2', 1998, 0, {'b'}, {'x'}, {'p1'}),
                            ('CN3', 1997, 0, {'a'}, {'x'}, {'p1'})])
        for_ = make_patents([('US1', 2022, 0, {'a', 'b'}, {'x'}, {'p2'}),
                             ('US2', 2024, 0, {'b'}, {'x'}, {'p2'}),
                             ('US3', 2025, 0, {'a'}, {'x'}, {'p2'})])
        mp = empty_mainpath()
        mp['pre2000'] = {'CN1'}
        mp['2000_2026'] = {'US1'}
        r = per_topic_indicators('A61B5', '身体诊断测量', dom, for_, mp,
                                 WINDOW_ENDS, 0)
        # 功能集相同 → F=1；场景相同 → C=1；原理无交集 → H=1
        assert r['F'] == 1.0 and r['C'] == 1.0 and r['H'] == 1.0
        assert r['S'] == pytest.approx(1.0)
        # K：国外 (0+1)*3 / 全部 (0+1)*6 = 0.5；阈值 0 → 全部高价值 → A = 3/6 = 0.5
        assert r['K'] == pytest.approx(0.5)
        assert r['A'] == pytest.approx(0.5)
        assert r['V'] == pytest.approx(0.5)
        # pA_init=1/1=1, pA_final=0; pB_init=0, pB_final=1 → T=sigmoid(2*(1-(-1)))=sigmoid(4)
        assert r['pA_init'] == pytest.approx(1.0)
        assert r['pB_final'] == pytest.approx(1.0)
        assert r['T'] == pytest.approx(1.0 / (1.0 + math.exp(-4.0)))
        # 国外年份更晚 → 增长更快 → G > 0.5
        assert r['G'] > 0.5
        assert r['M'] == pytest.approx((r['G'] + r['T']) / 2.0)
        assert r['R'] == pytest.approx(r['S'] * (r['M'] + r['V']) / 2.0)
        assert r['flags'] == []

    def test_threshold_not_met(self):
        dom = make_patents([('CN1', 2001, 0, {'a'}, {'x'}, {'p1'}),
                            ('CN2', 2002, 0, {'a'}, {'x'}, {'p1'}),
                            ('CN3', 2003, 0, {'a'}, {'x'}, {'p1'})])
        for_ = make_patents([('US1', 2020, 0, {'a'}, {'x'}, {'p1'}),  # 原理相同 → H=0
                             ('US2', 2021, 0, {'a'}, {'x'}, {'p1'}),
                             ('US3', 2022, 0, {'a'}, {'x'}, {'p1'})])
        r = per_topic_indicators('A61N1', '神经刺激器件', dom, for_,
                                 empty_mainpath(), WINDOW_ENDS, 10)
        # 软阈值：S 恒计算（等权 (1+1+0)/3），'未达标' 仅作参考标记
        assert r['H'] == 0.0
        assert r['S'] == pytest.approx(2 / 3)
        assert '未达标' in r['flags']
        # in_degree 全 0 < 阈值 10 → 无高价值专利 → V/R 为 None
        assert '无高价值专利' in r['flags']
        assert r['V'] is None
        assert r['R'] is None

    def test_no_high_value_patents(self):
        dom = make_patents([('CN1', 2001, 0, {'a'}, {'x'}, {'p1'}),
                            ('CN2', 2002, 0, {'a'}, {'x'}, {'p1'}),
                            ('CN3', 2003, 0, {'a'}, {'x'}, {'p1'})])
        for_ = make_patents([('US1', 2020, 0, {'a'}, {'x'}, {'p2'}),
                             ('US2', 2021, 0, {'a'}, {'x'}, {'p2'}),
                             ('US3', 2022, 0, {'a'}, {'x'}, {'p2'})])
        r = per_topic_indicators('A61N1', '神经刺激器件', dom, for_,
                                 empty_mainpath(), WINDOW_ENDS, 100)
        # 原理无交集 → H=1 全达标 → S=(1+1+1)/3=1.0 且无 '未达标'
        assert r['S'] == pytest.approx(1.0)
        assert '未达标' not in r['flags']
        assert r['A'] is None
        assert '无高价值专利' in r['flags']
        assert r['V'] is None and r['R'] is None

    def test_a_direction_asymmetric(self):
        # 高价值全部在 CN：A 必须为 1.0（若实现误用国外占比会得到 0.0）
        dom = make_patents([('CN1', 2001, 5, {'a'}, {'x'}, {'p1'}),
                            ('CN2', 2002, 5, {'a'}, {'x'}, {'p1'}),
                            ('CN3', 2003, 5, {'a'}, {'x'}, {'p1'})])
        for_ = make_patents([('US1', 2020, 0, {'a'}, {'x'}, {'p2'}),
                             ('US2', 2021, 0, {'a'}, {'x'}, {'p2'}),
                             ('US3', 2022, 0, {'a'}, {'x'}, {'p2'})])
        r = per_topic_indicators('A61N1', '神经刺激器件', dom, for_,
                                 empty_mainpath(), WINDOW_ENDS, 4)
        assert r['A'] == pytest.approx(1.0)
        assert '无高价值专利' not in r['flags']
        # K = 3 / (3 + 3*(5+1)) = 3/21；V = (K + 1 - 1)/2 = K/2
        assert r['K'] == pytest.approx(3 / 21)
        assert r['V'] == pytest.approx(r['K'] / 2)


class TestFchOverride:
    def _fixture(self):
        dom = make_patents([('CN1', 1999, 0, {'a', 'b'}, {'x'}, {'p1'}),
                            ('CN2', 1998, 0, {'b'}, {'x'}, {'p1'}),
                            ('CN3', 1997, 0, {'a'}, {'x'}, {'p1'})])
        for_ = make_patents([('US1', 2022, 0, {'a'}, {'x'}, {'p2'}),
                             ('US2', 2024, 0, {'b'}, {'x'}, {'p2'}),
                             ('US3', 2025, 0, {'c'}, {'x'}, {'p2'})])
        return dom, for_

    def test_fch_drives_s_and_flag(self):
        dom, for_ = self._fixture()
        r = per_topic_indicators('A61B5', '身体诊断测量', dom, for_,
                                 empty_mainpath(), WINDOW_ENDS, 0,
                                 fch={'F': 1.0, 'C': 1.0, 'H': 0.0})
        assert r['F'] == 1.0 and r['C'] == 1.0 and r['H'] == 0.0
        assert r['S'] == 2 / 3  # (1+1+0)/3
        assert '未达标' in r['flags']  # H=0 < 0.3
        # Jaccard 对照值：F_J=2/3（{'a','b'} vs {'a','b','c'}）、H_J=1.0（原理零交集）
        assert r['F_J'] == 2 / 3
        assert r['H_J'] == 1.0

    def test_fch_pass_marker(self):
        dom, for_ = self._fixture()
        r = per_topic_indicators('A61B5', '身体诊断测量', dom, for_,
                                 empty_mainpath(), WINDOW_ENDS, 0,
                                 fch={'F': 0.9, 'C': 0.8, 'H': 0.6})
        assert '未达标' not in r['flags']
        assert r['F'] == 0.9 and r['C'] == 0.8 and r['H'] == 0.6


class TestExposureOverride:
    def test_exposure_drives_k_and_a(self):
        dom = make_patents([('CN1', 2001, 5, {'a'}, {'x'}, {'p1'}),
                            ('CN2', 2002, 5, {'a'}, {'x'}, {'p1'}),
                            ('CN3', 2003, 5, {'a'}, {'x'}, {'p1'})])
        for_ = make_patents([('US1', 2020, 0, {'a'}, {'x'}, {'p2'}),
                             ('US2', 2021, 0, {'a'}, {'x'}, {'p2'}),
                             ('US3', 2022, 0, {'a'}, {'x'}, {'p2'})])
        # exposure = B 路线全集：国外 3 条(in_degree 0) + 国内 2 条(in_degree 2)
        exposure = [dict(p, is_cn=0) for p in for_]
        exposure += [dict(p, is_cn=1) for p in make_patents(
            [('CN9', 2005, 2, {'a'}, {'x'}, {'p1'}),
             ('CN8', 2006, 2, {'a'}, {'x'}, {'p1'})])]
        r = per_topic_indicators('P1→P2', '国外P2替代国内P1', dom, for_,
                                 empty_mainpath(), WINDOW_ENDS, 0,
                                 exposure=exposure)
        # K：num=国外 3 条 q=1 → 3；den=3*1 + 2*3 = 9 → K=1/3
        assert r['K'] == 1 / 3
        # A：阈值 0 → exposure 全部高价值；CN 2/5 = 0.4
        assert r['A'] == 0.4
        assert r['V'] == (1 / 3 + 1 - 0.4) / 2
