# -*- coding: utf-8 -*-
"""LLM 批量打分：每 prompt 评估 LLM_BATCH 个候选，多线程并发，断点续跑（jsonl）。"""
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from sem_config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_URL, LLM_BATCH, OUTPUT_DIR

_WRITE_LOCK = threading.Lock()

SCORES_FILE = OUTPUT_DIR / "semantic_scores.jsonl"

BATCH_PROMPT_TMPL = """【路径专利】{path_pub}：{path_text}

以下是 {n} 个候选专利，请分别独立判断每个候选与路径专利的技术语义相似度：
{items}

输出严格 JSON 数组（与候选顺序一一对应，不要输出其他内容）：
[{{"score": 0.0-1.0, "verdict": "相似/不相似", "reason": "不超过50字，说明相似的技术点"}}, ...]
评分标准：技术功能、技术原理、应用场景、解决的问题越重合分越高；
仅属于同一大领域（如都做脑电）但具体技术手段不同，score 应 ≤ 0.5。
注意：每个候选独立评估，给出与路径专利的绝对相似度，不要互相比较。"""


def _norm_score(obj: dict) -> dict:
    """规范化单个评估结果。"""
    score = float(obj.get("score", 0.0))
    score = max(0.0, min(1.0, score))
    verdict = obj.get("verdict", "")
    if verdict not in ("相似", "不相似"):
        verdict = "相似" if score >= 0.55 else "不相似"
    return {"score": score, "verdict": verdict,
            "reason": str(obj.get("reason", ""))[:100]}


def parse_llm_json(text: str) -> list[dict]:
    """容忍 ```json 代码块包裹；返回规范化后的列表。"""
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    raw = m.group(1) if m else text.strip()
    obj = json.loads(raw)
    if not isinstance(obj, list):
        raise ValueError(f"LLM 输出不是数组: {str(obj)[:200]}")
    return [_norm_score(x) if isinstance(x, dict) else {"score": 0.0, "verdict": "不相似", "reason": "解析失败"}
            for x in obj]


def call_llm_batch(path_pub: str, path_text: str, chunk, retries: int = 3) -> list[dict]:
    """批量打分一个 chunk（<=LLM_BATCH 个候选）；重试指数退避。"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY")
    items = "\n".join(f"{i}.【候选】{r['pub']}：{str(r['cand_text'])[:800]}"
                      for i, (_, r) in enumerate(chunk.iterrows(), 1))
    prompt = BATCH_PROMPT_TMPL.format(path_pub=path_pub, path_text=path_text[:1500],
                                      n=len(chunk), items=items)
    # deepseek-v4-flash 默认带推理：reasoning 消耗 token 且拖慢响应。
    # 实测 thinking.disabled 后 10 对/批从 20s 降到 5.5s（3.6 倍提速），
    # max_tokens 仍需 4000（推理 + 批量输出的余量）。
    payload = {"model": DEEPSEEK_MODEL, "messages": [
        {"role": "system", "content": "你是专利语义相似度评估专家，只输出合法 JSON。"},
        {"role": "user", "content": prompt}], "temperature": 0.1,
        "max_tokens": 4000, "thinking": {"type": "disabled"}}
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=180)
            if resp.status_code == 429:  # 限流：长退避后重试
                last_err = RuntimeError("HTTP 429 限流")
                time.sleep(5 + 2 ** attempt)
                continue
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = parse_llm_json(content)
            if len(parsed) != len(chunk):
                raise ValueError(f"数组长度不符: 期望 {len(chunk)} 实际 {len(parsed)}")
            return parsed
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM 批量调用失败（重试 {retries} 次后）: {last_err}")


def load_scores() -> list[dict]:
    """读取全部打分记录（容错：跳过空行与进程被杀遗留的半行）。"""
    recs = []
    if SCORES_FILE.exists():
        for line in SCORES_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # 半行（进程中断残留），跳过
    return recs


def load_done_keys() -> set[tuple]:
    """已打分对的键集合（断点续跑）。"""
    return {(r["period"], r["path_id"], r["path_pub"], r["pub"]) for r in load_scores()}


def score_all(candidates_df, limit: int | None = None, sleep: float = 0.0,
              workers: int = 8, retry_failures: int = 3) -> int:
    """按 (时期,路径,路径专利) 分组批量打分，多线程并发，追加 jsonl；返回新打分数。

    - 断点续跑：已打分的对跳过
    - 并发：ThreadPoolExecutor(workers)，写 jsonl 加锁
    - 失败重试：失败的 chunk 在 retry_failures 轮内重试；耗尽后打印警告（不再静默丢弃）
    """
    done = load_done_keys()
    tasks = []
    for (period, path_id, path_pub), g in candidates_df.groupby(
            ["period", "path_id", "path_pub"], sort=False):
        path_text = g["path_text"].iloc[0]
        todo = g[~g.apply(lambda r: (r["period"], r["path_id"], r["path_pub"], r["pub"]) in done,
                          axis=1)]
        for i in range(0, len(todo), LLM_BATCH):
            tasks.append((path_pub, path_text, todo.iloc[i:i + LLM_BATCH]))
    if limit:
        tasks = tasks[:limit]  # limit 在提交前截断（executor 退出会等待全部任务，无法中途停）

    new_count = 0
    pending = tasks
    for round_no in range(retry_failures + 1):
        if not pending:
            break
        if round_no > 0:
            time.sleep(5)  # 失败轮之间喘息
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(call_llm_batch, pp, pt, chunk): chunk
                       for pp, pt, chunk in pending}
            failed = []
            for fut in as_completed(futures):
                chunk = futures[fut]
                try:
                    results = fut.result()
                    with _WRITE_LOCK:
                        with open(SCORES_FILE, "a", encoding="utf-8") as f:
                            for (_, row), res in zip(chunk.iterrows(), results):
                                rec = {"period": row["period"], "path_id": int(row["path_id"]),
                                       "path_pub": row["path_pub"], "pub": row["pub"],
                                       "cos": float(row["cos"]), **res}
                                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            f.flush()
                        new_count += len(chunk)
                    time.sleep(sleep)
                except Exception:
                    failed.append(chunk)  # 下一轮重试
        pending = failed
    if pending:
        n_pairs = sum(len(ch) for _, _, ch in pending)
        print(f"[WARN] {len(pending)} 个 chunk（{n_pairs} 对）重试耗尽仍失败，"
              f"本轮未写入；下次运行会自动重试", flush=True)
    return new_count
