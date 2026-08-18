# -*- coding: utf-8 -*-
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from embed_similarity import symmetric_max_match  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM_CSV = os.path.join(ROOT, 'outputs', 'intermediate', 'entity_sim_by_topic.csv')


class TestSymmetricMaxMatch:
    def test_identical(self):
        a = np.array([[1.0, 0.0]])
        assert symmetric_max_match(a, a) == 1.0

    def test_orthogonal(self):
        a = np.array([[1.0, 0.0]])
        b = np.array([[0.0, 1.0]])
        assert symmetric_max_match(a, b) == 0.0

    def test_symmetric(self):
        rng = np.random.default_rng(42)
        a = rng.normal(size=(5, 8))
        b = rng.normal(size=(3, 8))
        a /= np.linalg.norm(a, axis=1, keepdims=True)
        b /= np.linalg.norm(b, axis=1, keepdims=True)
        assert symmetric_max_match(a, b) == symmetric_max_match(b, a)

    def test_two_vs_one(self):
        # 双实体对单实体：每个方向的最佳匹配都是 √2/2
        a = np.array([[1.0, 0.0], [0.0, 1.0]])
        b = np.array([[0.70710678, 0.70710678]])
        assert symmetric_max_match(a, b) == pytest.approx(np.sqrt(2) / 2)


class TestEmbedSmoke:
    def test_sim_table(self):
        df = pd.read_csv(SIM_CSV, dtype={'topic_code': str})
        assert len(df) == 147
        for col in ['F_sim', 'C_sim', 'P_sim']:
            vals = df[col]
            assert ((vals >= 0) & (vals <= 1)).all(), f'{col} 越界'
        # 147 主题中 78 个无国内专利（dom 空→恒 0）、21 个国外功能实体为空，
        # 仅 48 个双方均有功能实体——实测全部 F_sim>0（min≈0.39），即嵌入质量断言
        assert (df['F_sim'] > 0).sum() >= 48
