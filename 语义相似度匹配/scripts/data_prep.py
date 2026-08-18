# -*- coding: utf-8 -*-
"""数据准备：候选专利 + 路径专利（复用规则匹配项目的 data_loader）。"""
import sys
from pathlib import Path

import pandas as pd

from sem_config import PATHS_DIR, PERIODS, RULE_SCRIPTS

# append 而非 insert(0)：不抢占 sys.path 首位，避免本项目的 assign/report 被规则项目的同名模块遮蔽
sys.path.append(str(RULE_SCRIPTS))
from data_loader import load_patent_texts, load_top_paths  # noqa: E402


def load_candidates() -> pd.DataFrame:
    """全部候选专利（有中文摘要），列 pub/text/title/apply_date/pub_date/source。"""
    return load_patent_texts()


def load_main_path_pubs(periods: list[str] | None = None) -> set[str]:
    """全部时期 top3 路径的全部节点（internal+external），用于排除主路径自身成员。"""
    pubs = set()
    for period in periods or PERIODS:
        for p in load_top_paths(period):
            pubs.update(p["nodes"])
    return pubs


def load_path_patents() -> pd.DataFrame:
    """路径专利（有摘要的 internal 节点），列 period/path_id/pub/text。"""
    patents = load_candidates()
    by_pub = {p: row for p, row in zip(patents["pub"], patents.to_dict("records"))}
    rows = []
    for period in PERIODS:
        for p in load_top_paths(period):
            for node in p["nodes"]:
                info = by_pub.get(node)
                if info:
                    rows.append({"period": period, "path_id": p["path_id"],
                                 "pub": node, "text": info["text"]})
    return pd.DataFrame(rows)
