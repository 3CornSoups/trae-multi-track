# -*- coding: utf-8 -*-
"""归属：LLM 分数贪心唯一归属 + 每路径上限。"""
import pandas as pd

from sem_config import K, SCORE_THETA


def greedy_assign(scores: pd.DataFrame, theta: float = SCORE_THETA, k: int = K) -> pd.DataFrame:
    """每专利只保留 LLM score 最高的一行；过 theta 才归属；每(时期,路径)取 top-k。"""
    if scores.empty:
        return scores
    df = scores[scores["score"] >= theta].copy()
    if df.empty:
        return df
    df = df.sort_values("score", ascending=False)
    df = df.drop_duplicates(subset="pub", keep="first")   # 全局贪心唯一
    df["_rnk"] = df.groupby(["period", "path_id"]).cumcount()
    return df[df["_rnk"] < k].drop(columns="_rnk").reset_index(drop=True)
