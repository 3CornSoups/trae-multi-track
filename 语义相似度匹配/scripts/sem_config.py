# -*- coding: utf-8 -*-
"""语义相似度匹配：全局配置。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根（TRAE/多轨道）
OUTPUT_DIR = BASE_DIR / "语义相似度匹配" / "outputs"
CACHE_DIR = OUTPUT_DIR / "embedding_cache"
for d in (OUTPUT_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# 复用规则匹配项目的 data_loader/config（不复制代码）
RULE_SCRIPTS = BASE_DIR / "路径概括与拓展" / "scripts"

# ---- 数据 ----
PERIODS = ["2000_2005", "2000_2010", "2000_2015", "2000_2020", "2000_2026"]
PATHS_DIR = BASE_DIR / "主路径识别" / "outputs"
PATENTS_FILE = BASE_DIR / "03_合并专利信息_精简.csv"
RULE_ASSIGNMENTS = BASE_DIR / "路径概括与拓展" / "outputs" / "assignments.csv"

# ---- 预筛（embedding 余弦）----
# 2026-08-06 实测：bge-small 对 BCI 中文摘要余弦中位数 0.57、99% 分位 0.73；
# 每篇路径专利 top-300 ∪ cos>0.72 → 全量约 4.3 万对（LLM 批量 1.6s/对 ≈ 19 小时后台）。
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
TOP_N = 300        # 每路径专利余弦 top-N（高召回 + LLM 时间平衡）
COS_TH = 0.72      # 余弦补充阈值（与 top-N 取并集）
EMBED_BATCH = 64
LLM_BATCH = 10     # 每个 LLM prompt 评估的候选对数（吞吐 10 倍）

# ---- LLM 精判（DeepSeek）----
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
SCORE_THETA = 0.55  # 默认阈值（跑完看分布调）
K = 300             # 每路径并入上限（放宽，配合高召回）
