# Task 3 实施简报

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

keyword_match.py — 两段式关键词匹配引擎（Step 3）

**Files:**
- Create: `路径概括与拓展/scripts/keyword_match.py`
- Test: `路径概括与拓展/tests/test_keyword_match.py`

**Interfaces:**
- Consumes: `config.WEIGHTS`、`config.OVERALL_DIM_MAP`、`config.PATH_DIM_MAP`
- Produces:
  - `count_hits(text: str, keywords: list[str]) -> int` — 中文子串/英文词边界（允许复数 s），封顶调用方控制
  - `score_dim_groups(text: str, dims: dict, dim_map: dict, weights: dict) -> float` — 归一化 0-1；每维度命中数封顶 3；缺失维度权重计 0
  - `score_overall(text: str, summary: dict) -> float` — 时期整体得分 S_period
  - `score_path_diff(text: str, path_summary: dict) -> float` — 路径差异化得分 S_path

- [ ] **Step 1: 写失败测试**

`tests/test_keyword_match.py`:

```python
# -*- coding: utf-8 -*-
from keyword_match import count_hits, score_overall, score_path_diff

# ---- count_hits ----
def test_chinese_substring():
    text = "一种用于癫痫检测的脑电信号处理装置"
    assert count_hits(text, ["癫痫检测", "脑电信号", "不存在的词"]) == 2


def test_english_boundary_and_plural():
    text = "electrode array for neural signals, electrode placement"
    assert count_hits(text, ["electrode"]) == 2      # 两处
    assert count_hits(text, ["signal"]) == 1         # signals 命中（复数容忍）
    assert count_hits(text, ["electrod"]) == 0       # 非完整词不命中


def test_english_in_chinese_text():
    # 翻译列常保留英文术语
    text = "一种包含 electrode array 的神经电极阵列"
    assert count_hits(text, ["electrode array"]) == 1
    assert count_hits(text, ["神经电极"]) == 1


def test_empty_keywords():
    assert count_hits("任意文本", []) == 0

# ---- score_overall ----
SUMMARY = {
    "overall": {
        "功能主线": {"关键词_中": ["信号采集"], "关键词_英": ["signal acquisition"]},
        "解决问题": {"关键词_中": ["癫痫检测"], "关键词_英": []},
        "应用场景": {"关键词_中": [], "关键词_英": []},
        "技术原理": {"关键词_中": [], "关键词_英": []},
    },
    "paths": [],
}

def test_score_overall_single_dim():
    # 只命中"功能"1 词 → 0.35/1.0 = 0.35（权重 0.35）
    s = score_overall("本发明涉及 signal acquisition 信号采集方法", SUMMARY)
    assert abs(s - 0.35) < 1e-9


def test_score_overall_cap3():
    # 功能命中 5 次 → 封顶 3 → 0.35*3/1.0
    s = score_overall("信号采集 信号采集 信号采集 信号采集 信号采集", SUMMARY)
    assert abs(s - 1.05) < 1e-9  # 单维封顶 3 后超过 1 是允许的（路径对比用相对值）


def test_score_overall_no_hit():
    assert score_overall("完全不相关的内容", SUMMARY) == 0.0

# ---- score_path_diff ----
PATH_SUM = {
    "path_id": 1,
    "差异化特征": {
        "功能侧重": {"关键词_中": ["深部电极"], "关键词_英": ["deep electrode"]},
        "问题侧重": {"关键词_中": [], "关键词_英": []},
        "场景侧重": {"关键词_中": [], "关键词_英": []},
        "原理差异": {"关键词_中": [], "关键词_英": []},
    },
}

def test_score_path_hit():
    assert abs(score_path_diff("深部电极植入", PATH_SUM) - 0.35) < 1e-9
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_keyword_match.py -v`
Expected: FAIL，ModuleNotFoundError: No module named 'keyword_match'

- [ ] **Step 3: 写实现**

`scripts/keyword_match.py`:

```python
# -*- coding: utf-8 -*-
"""Step 3: 两段式关键词匹配引擎（纯函数）。"""
import re

from config import WEIGHTS, OVERALL_DIM_MAP, PATH_DIM_MAP

_HIT_CAP = 3  # 每维度命中关键词数封顶，防一词多命中爆分


def _kw_regex(kw: str) -> re.Pattern:
    """中文：子串；英文：词边界 + 允许复数 s。"""
    if re.search(r"[一-鿿]", kw):
        return re.compile(re.escape(kw))
    return re.compile(r"(?<![A-Za-z])" + re.escape(kw) + r"s?(?![A-Za-z])", re.IGNORECASE)


def count_hits(text: str, keywords: list[str]) -> int:
    """文本命中关键词数（同一关键词多次出现计 1，不同关键词累加）。"""
    hits = 0
    for kw in keywords or []:
        if not kw or not str(kw).strip():
            continue
        if _kw_regex(str(kw)).search(text):
            hits += 1
    return hits


def score_dim_groups(text: str, dims: dict, dim_map: dict, weights: dict) -> float:
    """按维度打分并归一化：Σ min(hit,3)*w / Σ w（缺失维度权重计 0）。"""
    num, den = 0.0, 0.0
    for dim_key, meta in (dims or {}).items():
        w = weights.get(dim_map.get(dim_key, ""), 0.0)
        if w == 0.0:
            continue
        den += w
        kws = (meta.get("关键词_中") or []) + (meta.get("关键词_英") or [])
        num += w * min(count_hits(text, kws), _HIT_CAP)
    return num / den if den > 0 else 0.0


def score_overall(text: str, summary: dict) -> float:
    """时期整体得分 S_period。"""
    return score_dim_groups(text, summary.get("overall", {}), OVERALL_DIM_MAP, WEIGHTS)


def score_path_diff(text: str, path_summary: dict) -> float:
    """路径差异化得分 S_path。"""
    return score_dim_groups(text, path_summary.get("差异化特征", {}), PATH_DIM_MAP, WEIGHTS)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_keyword_match.py -v`
Expected: PASS（8 个测试）

---
