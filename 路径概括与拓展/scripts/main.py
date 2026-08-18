# -*- coding: utf-8 -*-
"""路径概括与拓展 — 主流水线。

用法：
  python scripts/main.py                # 全 5 时期
  python scripts/main.py --period 2000_2005   # 单时期（调试）
  python scripts/main.py --force        # 强制重新调用 LLM（忽略断点缓存）
"""
import argparse
import logging
import time

from config import OUTPUT_DIR, PERIODS, DEEPSEEK_API_KEY
from data_loader import load_top_paths, load_patent_texts, path_abstracts
from llm_summarize import summarize_period
from assign import build_candidates, greedy_assign
from report import write_report, write_summary_md


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default=None, help="单时期，如 2000_2005")
    ap.add_argument("--force", action="store_true", help="强制重新调用 LLM")
    args = ap.parse_args()

    periods = [args.period] if args.period else PERIODS
    for p in periods:
        if p not in PERIODS:
            raise SystemExit(f"无效时期: {p}，可选 {PERIODS}")

    if not DEEPSEEK_API_KEY:
        raise SystemExit("未设置 DEEPSEEK_API_KEY。请先执行（PowerShell）：\n"
                         "  $env:DEEPSEEK_API_KEY = \"sk-你的key\"\n"
                         "或在系统环境变量中永久设置后重开终端。")

    # Step 1: 数据
    patents = load_patent_texts()
    logging.info("全量专利含中文摘要文本: %d", len(patents))

    # Step 2: 各时期 LLM 概括（断点续跑）
    periods_data = {}
    for period in periods:
        paths = load_top_paths(period)
        pa = path_abstracts(period, paths, patents)
        logging.info("[%s] 路径 %d 条，可查摘要: %s",
                     period, len(pa), [len(x["items"]) for x in pa])
        summary = summarize_period(period, pa, force=args.force)
        periods_data[period] = {"summary": summary, "paths": pa}
        write_summary_md(period, summary)
        time.sleep(1)  # 温和调用间隔

    # Step 3+4: 匹配 + 贪心归属
    candidates = build_candidates(patents, periods_data)
    logging.info("候选数: %d", len(candidates))
    assignments = greedy_assign(candidates)
    logging.info("归属专利: %d（每时期每路径并入数: %s）",
                 len(assignments),
                 assignments.groupby(["period", "path_id"]).size().to_dict())

    # Step 5: 报告
    write_report(assignments, candidates, periods_data, patents)
    logging.info("完成。输出目录: %s", OUTPUT_DIR)


if __name__ == "__main__":
    main()
