# -*- coding: utf-8 -*-
"""Step 5: 报告生成（markdown 报告 + csv + xlsx）。"""
import json
from datetime import datetime

import pandas as pd

from config import OUTPUT_DIR, THETA1, THETA2, K, PERIODS

SENSITIVE_THETAS = [0.50, 0.75, 1.00, 1.25, 1.50]  # 对齐 0-3 得分尺度


def build_sensitivity_table(candidates: pd.DataFrame) -> str:
    """θ₂ 敏感性表：各阈值下真实并入总量（调用 greedy_assign，θ₁ 固定为 config.THETA1）。"""
    from assign import greedy_assign
    lines = ["| θ₂ 阈值 | 并入专利数 | 归属专利比例 |", "|---|---|---|"]
    total_pub = candidates["pub"].nunique()
    for t in SENSITIVE_THETAS:
        n = len(greedy_assign(candidates, theta2=t))
        ratio = n / total_pub if total_pub else 0
        lines.append(f"| {t:.2f} | {n} | {ratio:.1%} |")
    return "\n".join(lines)


def write_summary_md(period: str, summary: dict) -> None:
    """每时期可读版概括文档。"""
    label = period.replace("_", "-")
    lines = [f"# {label} 时期技术路径特征概括（LLM 生成）", ""]
    lines.append("## 时期整体特征")
    for k, v in summary.get("overall", {}).items():
        lines.append(f"- **{k}**：{v.get('描述', '')}")
        kws = (v.get("关键词_中") or []) + [f"*{e}*" for e in (v.get("关键词_英") or [])]
        lines.append(f"  - 关键词：{'、'.join(kws)}")
    lines.append("")
    for p in summary.get("paths", []):
        lines.append(f"## 路径 {p['path_id']} 差异化特征")
        for k, v in p.get("差异化特征", {}).items():
            lines.append(f"- **{k}**：{v.get('描述', '')}")
            kws = (v.get("关键词_中") or []) + [f"*{e}*" for e in (v.get("关键词_英") or [])]
            lines.append(f"  - 关键词：{'、'.join(kws)}")
        lines.append("")
    (OUTPUT_DIR / f"period_{period}_summary.md").write_text("\n".join(lines), encoding="utf-8")


def _is_late_apply(apply_date, end: str) -> bool:
    """申请日晚于时期终点（end='2005' 表示 ≤2005-12-31 不算晚；缺失日期不算晚）。"""
    if pd.isna(apply_date):
        return False
    return str(apply_date)[:10] > f"{end}-12-31"


def write_report(assignments: pd.DataFrame, candidates: pd.DataFrame,
                 periods_summaries: dict, df_patents: pd.DataFrame) -> None:
    """写全部输出产物。"""
    # 1. 归属表 csv（合并元数据；已含元数据列则跳过，避免 _x/_y 重复列污染）
    # 清理上游 naive merge 遗留的 _x/_y 重复列（如 text_x/text_y → 保留左表 text）
    dup_cols = [c for c in assignments.columns
                if c.endswith("_x") and c[:-2] + "_y" in assignments.columns]
    if dup_cols:
        assignments = assignments.drop(columns=[c[:-2] + "_y" for c in dup_cols]) \
                                 .rename(columns={c: c[:-2] for c in dup_cols})
    meta_cols = ["text", "title", "apply_date", "pub_date", "source"]
    if not assignments.empty and not all(c in assignments.columns for c in meta_cols):
        add_cols = [c for c in meta_cols if c not in assignments.columns]
        meta = df_patents[["pub"] + add_cols].copy()
        out = assignments.merge(meta.drop_duplicates(subset="pub"), on="pub", how="left")
    else:
        out = assignments.copy()
    out.to_csv(OUTPUT_DIR / "assignments.csv", index=False, encoding="utf-8-sig")
    # 2. 候选得分矩阵
    candidates.to_csv(OUTPUT_DIR / "matching_scores.csv", index=False, encoding="utf-8-sig")
    # 3. 成果 xlsx
    with pd.ExcelWriter(OUTPUT_DIR / "extension_results.xlsx") as writer:
        out.to_excel(writer, sheet_name="归属", index=False)
        candidates.to_excel(writer, sheet_name="候选得分", index=False)
    # 4. markdown 报告
    lines = ["# 路径概括与拓展报告", f"生成时间：{datetime.now().isoformat(timespec='seconds')}", ""]
    lines.append(f"参数：θ₁={THETA1}，θ₂={THETA2}，每路径上限 K={K}")
    lines.append(f"全量专利：{len(df_patents)} 条有摘要文本；候选数：{len(candidates)}；归属专利：{len(out)}")
    lines.append("")
    lines.append("## 每时期每路径并入统计")
    lines.append("| 时期 | 路径 | 并入数 | 中位 S_path | 申请日晚于时期终点 | 抽查示例 |")
    lines.append("|---|---|---|---|---|---|")
    period_end = {"2000_2005": "2005", "2000_2010": "2010", "2000_2015": "2015",
                  "2000_2020": "2020", "2000_2026": "2026"}
    for period in PERIODS:
        for path_id in sorted(out[out["period"] == period]["path_id"].unique()):
            sub = out[(out["period"] == period) & (out["path_id"] == path_id)]
            if sub.empty:
                continue
            med = sub["s_path"].median()
            late = sub["apply_date"].apply(lambda d: _is_late_apply(d, period_end[period])).sum()
            sample = sub["pub"].iloc[0]
            lines.append(f"| {period} | {path_id} | {len(sub)} | {med:.3f} | {late} | {sample} |")
    lines.append("")
    lines.append("## 阈值敏感性（θ₂ 变化）")
    lines.append(build_sensitivity_table(candidates))
    lines.append("")
    lines.append("## 抽查：每条路径最高分并入专利")
    for _, r in out.sort_values("s_path", ascending=False).groupby(["period", "path_id"]).head(1).iterrows():
        lines.append(f"- [{r['period']} 路径{r['path_id']}] {r['pub']} (S={r['s_path']:.3f})：{str(r.get('text', ''))[:120]}")
    (OUTPUT_DIR / "extension_report.md").write_text("\n".join(lines), encoding="utf-8")
