# -*- coding: utf-8 -*-
"""Step 4: 全局贪心唯一归属 + 每路径 top-K 上限。"""
import pandas as pd

from config import THETA1, THETA2, K


def build_candidates(df_patents: pd.DataFrame, periods_data: dict) -> pd.DataFrame:
    """对全量专利 × 所有时期路径打分，仅保留过时期门槛的候选。"""
    rows = []
    for period, pd_data in periods_data.items():
        summary = pd_data["summary"]
        for path_sum in summary.get("paths", []):
            path_id = int(path_sum["path_id"])
            for _, row in df_patents.iterrows():
                s_period = _score_overall(row["text"], summary)
                if s_period < THETA1:
                    continue
                s_path = _score_path_diff(row["text"], path_sum)
                rows.append({"pub": row["pub"], "text": row["text"],
                             "period": period, "path_id": path_id,
                             "s_period": s_period, "s_path": s_path})
    return pd.DataFrame(rows, columns=["pub", "text", "period", "path_id", "s_period", "s_path"])


def greedy_assign(candidates: pd.DataFrame, theta2: float = THETA2, k: int = K) -> pd.DataFrame:
    """每专利唯一归属：s_path 最高者；过 theta2 才归属；每(时期,路径)取 top-k。"""
    if candidates.empty:
        return candidates
    df = candidates.copy()
    df["_tie"] = df["s_path"] * 0.5 + df["s_period"] * 0.5  # 平局次排序键
    df = df.sort_values(["s_path", "_tie"], ascending=False)
    # 每 pub 只保留最高的一行
    df = df.drop_duplicates(subset="pub", keep="first")
    df = df[df["s_path"] >= theta2]
    # 每 (period, path_id) 组内 top-k
    df["_rnk"] = df.groupby(["period", "path_id"]).cumcount()
    df = df[df["_rnk"] < k].drop(columns=["_rnk", "_tie"]).reset_index(drop=True)
    return df


def _score_overall(text: str, summary: dict) -> float:
    from keyword_match import score_overall
    return score_overall(text, summary)


def _score_path_diff(text: str, path_sum: dict) -> float:
    from keyword_match import score_path_diff
    return score_path_diff(text, path_sum)
