# Task 7 实施简报

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

main.py 流水线 + 2000-2005 端到端集成

**Files:**
- Create: `路径概括与拓展/scripts/main.py`

**Interfaces:**
- Consumes: 全部模块
- Produces: 完整输出产物（见 Task 6）

- [ ] **Step 1: 写 main.py**

`scripts/main.py`:

```python
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
```

（说明：main.py 中匹配循环直接内联，不重复 import assign.build_candidates，保持逻辑单点——greedy_assign 与阈值常量由 config 控制。）

- [ ] **Step 2: 无 API 环境下验证参数解析与数据流（--help 与 Step 1-2 前段）**

Run: `cd "D:/论文和代码项目/论文/TRAE/多轨道/路径概括与拓展" && python scripts/main.py --help`
Expected: usage 信息正常输出

- [ ] **Step 3: 设置 API key 并跑 2000-2005 端到端**

Run（PowerShell，用户交互步骤）:
```powershell
$env:DEEPSEEK_API_KEY = "sk-你的key"
python scripts/main.py --period 2000_2005
```
Expected:
- logs 显示路径摘要条数（2000-2005 内部节点 9/7/7 左右）
- 一次 LLM 调用成功，`outputs/period_2000_2005_summary.json` 生成
- 匹配完成，`outputs/assignments.csv` 生成，归属数合理（路径并入 ≤ K=100）
- `outputs/period_2000_2005_summary.md` 人工检查：维度齐全、关键词确实能在摘要中检索到

- [ ] **Step 4: 人工验证并入专利合理性**

Run: `python -c "from scripts import data_loader as dl; import pandas as pd; a=pd.read_csv('outputs/assignments.csv'); print(a.groupby(['period','path_id']).size()); print(a.head(10)[['pub','period','path_id','s_path']].to_string())"`
检查：抽查 5-10 条并入专利，打开 `extension_report.md` 查看抽查摘要片段，确认相似性合理、无大量"无关专利"误入。

- [ ] **Step 5: 全量运行 5 时期**

Run: `python scripts/main.py`
Expected: 5 次 LLM 调用（每次间隔 1s）+ 全量匹配 + 报告；`extension_report.md` 阈值敏感性表呈现各档并入量，若并入总量明显过高（>1 万）或过低（<500），与用户确认调整 θ₁/θ₂ 后重跑（断点续跑只重算匹配，不重复调用 LLM）。

---

## Self-Review（已执行）

1. **Spec 覆盖**：Step1→Task2、Step2→Task5、Step3→Task3、Step4→Task4、Step5→Task6、断点续跑→Task5、敏感性表→Task6、防重复（贪心唯一）→Task4、防膨胀（θ₁θ₂+K）→Task4/6、申请日标注→Task6、prompt 存档→Task5、错误处理（重试/JSON 解析）→Task5。均覆盖。
2. **占位符扫描**：无 TBD/TODO；所有测试与实现代码完整给出。
3. **类型一致性**：`count_hits(text, list[str])->int`、`score_overall(text, summary)->float`、`greedy_assign(candidates)->DataFrame(唯一pub)`、`summarize_period(period, path_abstracts, force=False)->dict` 在 Task3/4/5/6/7 中签名一致；LLM JSON 键名（功能主线/解决问题/应用场景/技术原理；功能侧重/问题侧重/场景侧重/原理差异）在 Task3 映射、Task5 prompt、Task6 报告中一致。
