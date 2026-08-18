# -*- coding: utf-8 -*-
"""语义相似度匹配 — 主流水线。

用法：
  python scripts/main.py                     # 全流程（预筛 → LLM → 归属 → 报告）
  python scripts/main.py --stage embed       # 只做预筛
  python scripts/main.py --stage llm         # 只做 LLM 打分（断点续跑）
  python scripts/main.py --limit 20          # 小批量调试（只打 20 对）
  python scripts/main.py --theta 0.5         # 归属阈值覆盖
"""
import argparse
import json
import logging

import pandas as pd

from sem_config import DEEPSEEK_API_KEY, OUTPUT_DIR, SCORE_THETA

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["embed", "llm", "assign", "report", "all"])
    ap.add_argument("--limit", type=int, default=None, help="LLM 打分对数上限（调试用）")
    ap.add_argument("--theta", type=float, default=None, help="归属阈值覆盖")
    args = ap.parse_args()

    if not DEEPSEEK_API_KEY:
        raise SystemExit("未设置 DEEPSEEK_API_KEY（PowerShell: $env:DEEPSEEK_API_KEY = \"sk-xxx\"）")

    from data_prep import load_candidates, load_main_path_pubs, load_path_patents
    candidates = load_candidates()
    logging.info("候选专利: %d", len(candidates))

    # ---- 预筛 ----
    if args.stage in ("embed", "all"):
        from embed import build_candidates
        path_pats = load_path_patents()
        logging.info("路径专利: %d（%d 时期×3 路径的 internal 节点）", len(path_pats),
                     len(path_pats["period"].unique()))
        main_pubs = load_main_path_pubs()
        cands = build_candidates(candidates["pub"].tolist(), candidates["text"].tolist(),
                                 path_pats, exclude_pubs=main_pubs)
        cands = cands.merge(path_pats[["period", "path_id", "pub", "text"]]
                            .rename(columns={"pub": "path_pub", "text": "path_text"}),
                            on=["period", "path_id", "path_pub"], how="left")
        cands = cands.merge(candidates[["pub", "text"]].rename(columns={"text": "cand_text"}),
                            on="pub", how="left")
        cands = cands.dropna(subset=["path_text", "cand_text"])
        cands.to_csv(OUTPUT_DIR / "prefilter_candidates.csv", index=False, encoding="utf-8-sig")
        logging.info("预筛候选对: %d（每路径平均 %.0f）", len(cands),
                     len(cands) / cands["path_id"].nunique() if len(cands) else 0)

    # ---- LLM 打分 ----
    if args.stage in ("llm", "all"):
        from llm_score import score_all
        cands = pd.read_csv(OUTPUT_DIR / "prefilter_candidates.csv")
        n = score_all(cands, limit=args.limit)
        logging.info("本次新打分: %d", n)

    # ---- 归属 ----
    if args.stage in ("assign", "report", "all"):
        from llm_score import load_scores
        from assign import greedy_assign
        scores_df = pd.DataFrame(load_scores()) \
            .drop_duplicates(subset=["period", "path_id", "path_pub", "pub"], keep="first")
        if scores_df.empty:
            raise SystemExit("semantic_scores.jsonl 为空：请先运行 LLM 打分阶段")
        theta = args.theta if args.theta is not None else SCORE_THETA
        assign = greedy_assign(scores_df, theta=theta)
        logging.info("归属专利: %d（阈值 %.2f）", len(assign), theta)

    # ---- 报告 ----
    if args.stage in ("report", "all"):
        from report import write_report
        from llm_score import load_scores, SCORES_FILE
        scores_df = pd.DataFrame(load_scores()) \
            .drop_duplicates(subset=["period", "path_id", "path_pub", "pub"], keep="first")
        assign = greedy_assign(scores_df, theta=args.theta if args.theta is not None else SCORE_THETA)
        write_report(scores_df, assign, candidates, SCORES_FILE)
        logging.info("完成。输出目录: %s", OUTPUT_DIR)


if __name__ == "__main__":
    main()
