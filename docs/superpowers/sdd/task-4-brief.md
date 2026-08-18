# Task 4 实施简报

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

assign.py — 全局贪心唯一归属（Step 4）

**Files:**
- Create: `路径概括与拓展/scripts/assign.py`
- Test: `路径概括与拓展/tests/test_assign.py`

**Interfaces:**
- Consumes: `config.THETA1`、`config.THETA2`、`config.K`
- Produces:
  - `build_candidates(df_patents: pd.DataFrame, periods_data: dict) -> pd.DataFrame`
    - `periods_data`: `{period: {summary: dict, paths: [path_summary dicts]}}`
    - 返回列：`pub`、`text`、`period`、`path_id`、`s_period`、`s_path`；仅保留 `s_period >= THETA1` 的候选
  - `greedy_assign(candidates: pd.DataFrame, theta2: float = THETA2, k: int = K) -> pd.DataFrame`
    - 每个 pub 取 `s_path` 最高且 `s_path >= theta2` 的一行；每 (period,path_id) 组内取 top-k（按 s_path 降序）
    - 返回列：`pub`、`text`、`period`、`path_id`、`s_period`、`s_path`；每 pub 唯一
    - 用 `s_path * 0.5 + s_period * 0.5` 作为同分平局时的次排序键（保证确定性）

- [ ] **Step 1: 写失败测试**

`tests/test_assign.py`:

```python
# -*- coding: utf-8 -*-
import pandas as pd
from assign import greedy_assign

CAND = pd.DataFrame([
    # pub 1：两个时期都过门槛，取 s_path 更高的
    {"pub": "P1", "text": "t", "period": "2000_2005", "path_id": 1, "s_period": 0.5, "s_path": 0.6},
    {"pub": "P1", "text": "t", "period": "2000_2010", "path_id": 2, "s_period": 0.6, "s_path": 0.8},
    # pub 2：只有一个过路径门槛
    {"pub": "P2", "text": "t", "period": "2000_2005", "path_id": 1, "s_period": 0.5, "s_path": 0.1},
    {"pub": "P2", "text": "t", "period": "2000_2010", "path_id": 2, "s_period": 0.7, "s_path": 0.4},
    # pub 3：全部低于路径门槛 → 不归属
    {"pub": "P3", "text": "t", "period": "2000_2005", "path_id": 1, "s_period": 0.5, "s_path": 0.05},
    {"pub": "P3", "text": "t", "period": "2000_2010", "path_id": 2, "s_period": 0.5, "s_path": 0.05},
])


def test_unique_per_pub():
    out = greedy_assign(CAND)
    assert out["pub"].is_unique


def test_best_path_wins():
    out = greedy_assign(CAND)
    row = out[out["pub"] == "P1"].iloc[0]
    assert row["period"] == "2000_2010" and row["path_id"] == 2 and row["s_path"] == 0.8


def test_threshold2_filters():
    out = greedy_assign(CAND)
    assert "P3" not in out["pub"].values          # 0.05 < 0.3 不归属
    row = out[out["pub"] == "P2"].iloc[0]
    assert row["period"] == "2000_2010" and row["path_id"] == 2  # 0.4 ≥ 0.3 归属


def test_topk_cap():
    many = pd.DataFrame([
        {"pub": f"P{i}", "text": "t", "period": "2000_2005", "path_id": 1,
         "s_period": 0.5, "s_path": 0.3 + i * 0.01} for i in range(150)
    ])
    out = greedy_assign(many)
    assert len(out) == 100  # K=100 上限


def test_empty_input():
    out = greedy_assign(pd.DataFrame(columns=["pub", "text", "period", "path_id", "s_period", "s_path"]))
    assert len(out) == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_assign.py -v`
Expected: FAIL，ModuleNotFoundError: No module named 'assign'

- [ ] **Step 3: 写实现**

`scripts/assign.py`:

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_assign.py -v`
Expected: PASS（4 个测试）

---
