# -*- coding: utf-8 -*-
"""报告：并入统计 + 阈值敏感性 + 规则匹配重叠对照 + 抽查。"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from sem_config import K, OUTPUT_DIR, PERIODS, RULE_ASSIGNMENTS, SCORE_THETA

THETA_GRID = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


def sensitivity_table(scores: pd.DataFrame) -> str:
    """各阈值下并入总量（贪心唯一 + 每路径上限 K）。"""
    from assign import greedy_assign
    lines = ["| 阈值 | 并入专利数 | 每路径中位数 |", "|---|---|---|"]
    for t in THETA_GRID:
        out = greedy_assign(scores, theta=t)
        n_per_path = out.groupby(["period", "path_id"]).size()
        med = n_per_path.median() if len(n_per_path) else 0
        lines.append(f"| {t:.2f} | {len(out)} | {med:.0f} |")
    return "\n".join(lines)


def overlap_with_rule(assign: pd.DataFrame) -> str:
    """与规则匹配结果的重叠对照。"""
    try:
        rule = pd.read_csv(RULE_ASSIGNMENTS)
    except FileNotFoundError:
        return "规则匹配结果不存在（路径概括与拓展/outputs/assignments.csv），跳过对照。"
    rule_pubs = set(rule["pub"])
    sem_pubs = set(assign["pub"])
    both = rule_pubs & sem_pubs
    return (f"- 语义相似度并入: {len(sem_pubs)} ｜ 规则匹配并入: {len(rule_pubs)}\n"
            f"- 两方法都并入（高置信）: {len(both)}"
            f"（占语义 {len(both)/len(sem_pubs):.1%} / 占规则 {len(both)/len(rule_pubs):.1%}）\n"
            f"- 仅语义并入: {len(sem_pubs - rule_pubs)} ｜ 仅规则并入: {len(rule_pubs - sem_pubs)}")


def write_report(scores: pd.DataFrame, assign: pd.DataFrame,
                 cand_meta: pd.DataFrame, scores_jsonl: Path) -> None:
    """写全部输出产物。"""
    # 1. 归属表（合并元数据）
    meta = cand_meta[["pub", "text", "title", "apply_date", "source"]].copy()
    out = assign.merge(meta.drop_duplicates(subset="pub"), on="pub", how="left")
    out.to_csv(OUTPUT_DIR / "semantic_assignments.csv", index=False, encoding="utf-8-sig")
    scores.to_csv(OUTPUT_DIR / "semantic_candidates.csv", index=False, encoding="utf-8-sig")

    # 2. markdown 报告
    lines = ["# 语义相似度匹配报告（LLM 精判）",
             f"生成时间：{datetime.now().isoformat(timespec='seconds')}", ""]
    lines.append(f"参数：预筛 top-{config_top_n()} ∪ cos>{config_cos_th()}；LLM {config_model()}；"
                 f"阈值 {SCORE_THETA}（默认，可调）；每路径上限 K={K}")
    lines.append(f"LLM 精判对数：{len(scores)}；并入专利：{len(out)}")
    lines.append("")
    lines.append("## 每时期每路径并入统计")
    lines.append("| 时期 | 路径 | 并入数 | 中位 LLM score | 最高分专利(score) |")
    lines.append("|---|---|---|---|---|")
    for period in PERIODS:
        for path_id in sorted(out[out["period"] == period]["path_id"].unique()):
            sub = out[(out["period"] == period) & (out["path_id"] == path_id)]
            if sub.empty:
                continue
            best = sub.sort_values("score", ascending=False).iloc[0]
            lines.append(f"| {period} | {path_id} | {len(sub)} | {sub['score'].median():.3f} "
                         f"| {best['pub']} ({best['score']:.2f}) |")
    lines.append("")
    lines.append("## 阈值敏感性")
    lines.append(sensitivity_table(scores))
    lines.append("")
    lines.append("## 与规则匹配结果对照")
    lines.append(overlap_with_rule(out))
    lines.append("")
    lines.append("## 抽查：每路径最高分（含 LLM 相似理由）")
    for _, r in out.sort_values("score", ascending=False).groupby(["period", "path_id"]).head(1).iterrows():
        lines.append(f"- [{r['period']} 路径{r['path_id']}] {r['pub']} ← 最相似路径专利 "
                     f"{r['path_pub']} (LLM={r['score']:.2f}, cos={r['cos']:.3f})：{r['reason']}")
    (OUTPUT_DIR / "semantic_report.md").write_text("\n".join(lines), encoding="utf-8")


def config_top_n() -> int:
    from sem_config import TOP_N
    return TOP_N


def config_cos_th() -> float:
    from sem_config import COS_TH
    return COS_TH


def config_model() -> str:
    from sem_config import DEEPSEEK_MODEL
    return DEEPSEEK_MODEL
