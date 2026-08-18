# Task 5 实施简报

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

llm_summarize.py — DeepSeek 时期级概括（Step 2）

**Files:**
- Create: `路径概括与拓展/scripts/llm_summarize.py`
- Test: `路径概括与拓展/tests/test_llm_summarize.py`

**Interfaces:**
- Consumes: `config.DEEPSEEK_URL`、`config.DEEPSEEK_MODEL`、`config.deepseek_headers()`、`config.PROMPT_DIR`、`config.OUTPUT_DIR`、`config.PERIODS`
- Produces:
  - `build_prompt(period: str, path_abstracts: list[dict]) -> str` — 时期 3 路径全部摘要的概括 prompt（严格 JSON 要求）
  - `parse_llm_json(text: str) -> dict` — 提取 ```json 代码块或裸 JSON，json.loads 校验
  - `call_deepseek(prompt: str, retries: int = 3) -> dict` — POST /chat/completions，指数退避，返回 parsed JSON
  - `summarize_period(period: str, path_abstracts: list[dict], force: bool = False) -> dict` — 断点续跑：summary json 已存在则读文件返回；否则调用并写 `outputs/period_{period}_summary.json`、`prompts/period_{period}_prompt.txt`、`logs/period_{period}_api.log`

- [ ] **Step 1: 写失败测试**

`tests/test_llm_summarize.py`:

```python
# -*- coding: utf-8 -*-
import json
import pytest
from llm_summarize import parse_llm_json, build_prompt, call_deepseek

SAMPLE_JSON = {
    "period": "2000_2005",
    "overall": {"功能主线": {"描述": "x", "关键词_中": ["a"], "关键词_英": ["b"]}},
    "paths": [{"path_id": 1, "差异化特征": {"功能侧重": {"关键词_中": ["c"]}}}],
}


def test_parse_codeblock():
    raw = "好的，结果如下：\n```json\n" + json.dumps(SAMPLE_JSON, ensure_ascii=False) + "\n```\n完毕"
    assert parse_llm_json(raw) == SAMPLE_JSON


def test_parse_bare_json():
    assert parse_llm_json(json.dumps(SAMPLE_JSON, ensure_ascii=False)) == SAMPLE_JSON


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        parse_llm_json("这不是 JSON")


def test_build_prompt_contains_paths():
    pa = [{"path_id": 1, "nodes": ["A"], "items": [{"node": "A", "title": "t1", "text": "摘要一"}]},
          {"path_id": 2, "nodes": ["B"], "items": [{"node": "B", "title": "t2", "text": "摘要二"}]},
          {"path_id": 3, "nodes": [], "items": []}]
    p = build_prompt("2000_2005", pa)
    assert "2000-2005" in p and "摘要一" in p and "摘要二" in p
    assert "path_id" in p and "差异化特征" in p


@pytest.mark.parametrize("status,should_retry", [
    (500, True), (200, False),
])
def test_call_deepseek_retry(monkeypatch, status, should_retry):
    calls = {"n": 0}
    import requests

    class FakeResp:
        status_code = status
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "```json\n" + json.dumps(SAMPLE_JSON) + "\n```"}}]}

    def fake_post(url, headers, json, timeout):
        calls["n"] += 1
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)
    if should_retry:
        with pytest.raises(RuntimeError):
            call_deepseek("p", retries=1)
        assert calls["n"] == 2  # 1 次失败 + 1 次重试
    else:
        out = call_deepseek("p", retries=1)
        assert out["period"] == "2000_2005"
```

（注：`call_deepseek` 需支持 `retries` 参数；200 且 JSON 合法才返回。）

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_llm_summarize.py -v`
Expected: FAIL，ModuleNotFoundError: No module named 'llm_summarize'

- [ ] **Step 3: 写实现**

`scripts/llm_summarize.py`:

```python
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
```

- [ ] **Step 4: 运行确认通过（mock 不消耗 API）**

Run: `python -m pytest tests/test_llm_summarize.py -v`
Expected: PASS（5 个测试，含参数化 2 个）

---
