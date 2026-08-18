# Task 6 实施简报

## 项目全局约束（必须遵守）

- 时期（PERIODS）：`["2000_2005", "2000_2010", "2000_2015", "2000_2020", "2000_2026"]`（不含 pre2000）
- 每时期取 `rank_by_spc` ≤ 3 的路径（按 total_spc 降序，见 paths_all.csv）
- 数据文件：`主路径识别/outputs/window_{period}_paths_all.csv` 与 `专利数据合并与引文网络构建/merged_all_patents.xlsx`（相对 `D:\论文和代码项目\论文\TRAE\多轨道` 解析为绝对路径）
- 维度权重（对齐论文指标）：功能 0.35、解决问题 0.30、应用场景 0.20、技术原理 0.15
- 阈值默认：θ₁ = 0.3（时期门槛）、θ₂ = 0.3（路径门槛）、每路径上限 K = 100
- 中文摘要文本规则：优先"摘要——翻译"列 → 否则"摘要"列含 CJK 用原文 → 否则跳过该专利
- LLM：DeepSeek `deepseek-chat`，base_url `https://api.deepseek.com`，key 从环境变量 `DEEPSEEK_API_KEY` 读取
- 公开号规范化：去连字符、大写（US A 类补零沿用项目规范）
- 输出目录：`路径概括与拓展/`（prompts/、outputs/、logs/ 子目录）
- 所有输出文件 UTF-8 编码
- API 失败重试 3 次 + 指数退避（1s/2s/4s）；JSON 解析失败重试并要求"仅输出 JSON 代码块"
- 断点续跑：`outputs/period_{period}_summary.json` 已存在则跳过该时期 LLM 调用

## 任务正文（需求与完整代码）

report.py — 报告与成果表（Step 5）

**Files:**
- Create: `路径概括与拓展/scripts/report.py`
- Test: `路径概括与拓展/tests/test_report.py`

**Interfaces:**
- Consumes: `config.OUTPUT_DIR`；`assign.greedy_assign` 输出；`llm_summarize` 的 summary json
- Produces:
  - `build_sensitivity_table(candidates: pd.DataFrame) -> str` — θ₂ ∈ {0.20,0.25,0.30,0.35,0.40} 各阈值下的并入总量 markdown 表格（对固定 θ₁=0.3、K=100）
  - `write_report(assignments: pd.DataFrame, candidates: pd.DataFrame, periods_summaries: dict, df_patents: pd.DataFrame) -> None` — 写 `outputs/extension_report.md`、`outputs/assignments.csv`、`outputs/matching_scores.csv`（候选集）、`outputs/extension_results.xlsx`（归属+摘要+元数据）
  - `write_summary_md(period, summary: dict) -> None` — 每时期可读版 `outputs/period_{period}_summary.md`

- [ ] **Step 1: 写失败测试**

`tests/test_report.py`:

```python
# -*- coding: utf-8 -*-
import pandas as pd
from report import build_sensitivity_table

CAND = pd.DataFrame([
    {"pub": "P1", "period": "2000_2005", "path_id": 1, "s_period": 0.5, "s_path": 0.42},
    {"pub": "P2", "period": "2000_2005", "path_id": 1, "s_period": 0.5, "s_path": 0.31},
    {"pub": "P3", "period": "2000_2005", "path_id": 1, "s_period": 0.5, "s_path": 0.12},
])


def test_sensitivity_table_counts():
    t = build_sensitivity_table(CAND)
    assert "0.30" in t
    # θ=0.25 → 2 条（0.42, 0.31）；θ=0.35 → 1 条；θ=0.40 → 1 条
    assert "2" in t.split("0.25")[1][:10]
    assert "1" in t.split("0.35")[1][:10]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL，ModuleNotFoundError: No module named 'report'

- [ ] **Step 3: 写实现**

`scripts/report.py`:

```python
# -*- coding: utf-8 -*-
"""Step 5: 报告生成（markdown 报告 + csv + xlsx）。"""
import json
from datetime import datetime

import pandas as pd

from config import OUTPUT_DIR, THETA1, THETA2, K, PERIODS

SENSITIVE_THETAS = [0.20, 0.25, 0.30, 0.35, 0.40]


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
    # 1. 归属表 csv（合并元数据）
    if not assignments.empty:
        meta = df_patents[["pub", "text", "title", "apply_date", "pub_date", "source"]].copy()
        out = assignments.merge(meta, on="pub", how="left")
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
        for path_id in sorted(assignments[assignments["period"] == period]["path_id"].unique()):
            sub = assignments[(assignments["period"] == period) & (assignments["path_id"] == path_id)]
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
    for _, r in assignments.sort_values("s_path", ascending=False).groupby(["period", "path_id"]).head(1).iterrows():
        lines.append(f"- [{r['period']} 路径{r['path_id']}] {r['pub']} (S={r['s_path']:.3f})：{str(r.get('text', ''))[:120]}")
    (OUTPUT_DIR / "extension_report.md").write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS（1 个测试）

---
