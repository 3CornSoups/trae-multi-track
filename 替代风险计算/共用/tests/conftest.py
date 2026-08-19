# -*- coding: utf-8 -*-
"""统一 sys.path 注入：共用 scripts + 实验二/实验三 专属 scripts。

各测试文件不再自行 sys.path.insert；本 conftest 在 pytest 收集前
把三层 scripts 目录注入，保证 `python -m pytest 共用/tests -q`
（从项目根）与 `cd 共用/tests; python -m pytest -q` 两种跑法均可导入。"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 共用/
for _rel in ('scripts', os.path.join('..', '实验二_主路径配对', 'scripts'),
             os.path.join('..', '实验三_要素凝练主题', 'scripts')):
    _p = os.path.normpath(os.path.join(_ROOT, _rel))
    if _p not in sys.path:
        sys.path.insert(0, _p)
