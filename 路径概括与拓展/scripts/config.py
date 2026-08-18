# -*- coding: utf-8 -*-
"""全局配置：路径、参数、DeepSeek 接入。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根（TRAE/多轨道）
SCRIPTS_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "路径概括与拓展" / "outputs"
PROMPT_DIR = BASE_DIR / "路径概括与拓展" / "prompts"
LOG_DIR = BASE_DIR / "路径概括与拓展" / "logs"
for d in (OUTPUT_DIR, PROMPT_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- 时期与路径 ----
PERIODS = ["2000_2005", "2000_2010", "2000_2015", "2000_2020", "2000_2026"]
PATHS_DIR = BASE_DIR / "主路径识别" / "outputs"
PATENTS_FILE = BASE_DIR / "03_合并专利信息_精简.csv"
TOP_N_PATHS = 3

# ---- 匹配参数（对齐论文三大指标 + 问题维度）----
WEIGHTS = {"功能": 0.35, "解决问题": 0.30, "应用场景": 0.20, "技术原理": 0.15}
THETA1 = 0.6   # 时期整体门槛（得分尺度 0-3，取 s_period 中位档）
THETA2 = 1.0   # 路径差异化门槛（至少命中一个强维度）
K = 100        # 每路径并入上限

# LLM JSON 键名 → 内部维度键名（LLM 输出为中文键，此处做映射容错）
OVERALL_DIM_MAP = {"功能主线": "功能", "解决问题": "解决问题",
                   "应用场景": "应用场景", "技术原理": "技术原理"}
PATH_DIM_MAP = {"功能侧重": "功能", "问题侧重": "解决问题",
                "场景侧重": "应用场景", "原理差异": "技术原理"}

# ---- DeepSeek ----
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def deepseek_headers() -> dict:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("环境变量 DEEPSEEK_API_KEY 未设置：请执行 `$env:DEEPSEEK_API_KEY=\"sk-xxx\"`")
    return {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
