# -*- coding: utf-8 -*-
"""Step 2: 时期级 LLM 概括（DeepSeek chat completions，断点续跑）。"""
import json
import logging
import re
import time
from pathlib import Path

import requests

from config import (DEEPSEEK_URL, DEEPSEEK_MODEL, deepseek_headers,
                    PROMPT_DIR, OUTPUT_DIR, LOG_DIR, PERIODS)

logger = logging.getLogger("llm_summarize")

PERIOD_LABELS = {"2000_2005": "2000-2005", "2000_2010": "2000-2010",
                 "2000_2015": "2000-2015", "2000_2020": "2000-2020", "2000_2026": "2000-2026"}


def build_prompt(period: str, path_abstracts: list[dict]) -> str:
    """构造时期级概括 prompt：3 条路径全部内部节点摘要 + 严格 JSON 输出要求。"""
    label = PERIOD_LABELS.get(period, period)
    lines = [f"你是专利技术路线分析专家。以下是脑机接口(BCI)领域 {label} 时期引文网络识别出的 3 条技术主路径"
             f"（Key-Route 算法提取，按时间顺序构成技术演化链）。请概括该时期整体技术特征，"
             f"并给出每条路径区别于其他两条路径的差异化特征。"]
    for pa in path_abstracts:
        lines.append(f"\n### 路径 {pa['path_id']}（节点 {len(pa['nodes'])} 个，其中本数据集可查 {len(pa['items'])} 个）")
        for it in pa["items"]:
            lines.append(f"专利 {it['node']}《{it['title']}》：{it['text']}")
    lines.append("""
### 输出要求
输出严格 JSON（不要输出任何其他文字），结构如下：
{
  "period": "时期标签",
  "overall": {
    "功能主线": {"描述": "一句话", "关键词_中": ["短语1", ...8-15个], "关键词_英": ["term1", ...]},
    "解决问题": {"描述": "一句话", "关键词_中": [...], "关键词_英": [...]},
    "应用场景": {"描述": "一句话", "关键词_中": [...], "关键词_英": [...]},
    "技术原理": {"描述": "一句话", "关键词_中": [...], "关键词_英": [...]}
  },
  "paths": [
    {"path_id": 1, "差异化特征": {
      "功能侧重": {"描述": "一句话", "关键词_中": [...], "关键词_英": [...]},
      "问题侧重": {"描述": "一句话", "关键词_中": [...], "关键词_英": [...]},
      "场景侧重": {"描述": "一句话", "关键词_中": [...], "关键词_英": [...]},
      "原理差异": {"描述": "一句话", "关键词_中": [...], "关键词_英": [...]}
    }},
    {"path_id": 2, "差异化特征": {...}},
    {"path_id": 3, "差异化特征": {...}}
  ]
}
关键词要求：
1. 每维度 8-15 个关键词，中英对照；中文为技术短语（2-10 字），英文为对应术语
2. 关键词必须是摘要中能直接找到的文本片段（宁缺毋滥，不要自造）
3. 差异化特征的关键词必须与另两条路径明显不同（你已看到全部路径摘要，请互相比较）
4. 键名必须与上述结构完全一致（功能主线/解决问题/应用场景/技术原理；功能侧重/问题侧重/场景侧重/原理差异）
""")
    return "\n".join(lines)


def parse_llm_json(text: str) -> dict:
    """从 LLM 响应提取 JSON（容忍 ```json 代码块包裹）。"""
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    raw = m.group(1) if m else text.strip()
    return json.loads(raw)


def call_deepseek(prompt: str, retries: int = 3) -> dict:
    """调用 DeepSeek chat completions，指数退避重试，返回解析后的 JSON。"""
    payload = {"model": DEEPSEEK_MODEL, "messages": [
        {"role": "system", "content": "你是严谨的专利技术分析助手，只输出合法 JSON。"},
        {"role": "user", "content": prompt}], "temperature": 0.3}
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(DEEPSEEK_URL, headers=deepseek_headers(),
                                 json=payload, timeout=300)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = parse_llm_json(content)
            if not isinstance(parsed, dict) or "overall" not in parsed:
                raise ValueError("响应缺少 overall 字段")
            return parsed
        except Exception as e:
            last_err = e
            logger.warning("第 %d 次调用失败: %s", attempt + 1, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"DeepSeek 调用失败（重试 {retries} 次后）: {last_err}")


def summarize_period(period: str, path_abstracts: list[dict], force: bool = False) -> dict:
    """断点续跑：已存在 summary json 则直接读取；否则调用并落盘。"""
    out_file = OUTPUT_DIR / f"period_{period}_summary.json"
    if out_file.exists() and not force:
        logger.info("跳过 %s：已存在 %s", period, out_file.name)
        return json.loads(out_file.read_text(encoding="utf-8"))
    prompt = build_prompt(period, path_abstracts)
    (PROMPT_DIR / f"period_{period}_prompt.txt").write_text(prompt, encoding="utf-8")
    summary = call_deepseek(prompt)
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (LOG_DIR / f"period_{period}_api.log").write_text(
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} OK paths={len(summary.get('paths', []))}\n",
        encoding="utf-8")
    logger.info("已生成 %s 概括（%d 路径）", period, len(summary.get("paths", [])))
    return summary
