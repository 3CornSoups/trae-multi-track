# -*- coding: utf-8 -*-
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from theme_pairs import premise_pass, threshold_pass  # noqa: E402


class TestGates:
    def test_premise_pass(self):
        assert premise_pass(problem_sim=0.6, H=0.4) is True
        assert premise_pass(problem_sim=0.4, H=0.4) is False   # 不同类问题
        assert premise_pass(problem_sim=0.6, H=0.2) is False   # 原理无明显差异

    def test_threshold_pass(self):
        assert threshold_pass(F=0.6, C=0.5, H=0.3) is True
        assert threshold_pass(F=0.59, C=0.9, H=0.9) is False
