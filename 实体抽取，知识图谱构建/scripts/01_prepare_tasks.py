# -*- coding: utf-8 -*-
"""01_prepare_tasks.py — 实体抽取任务准备。

输入: 数据集合并/outputs/05_合并数据集.csv（2876 唯一专利）
      03_合并专利信息_精简.csv（元数据: country/app_year/主IPC分类号等）
输出: outputs/tasks.jsonl            — GLM 实体抽取任务（每条含摘要）
      outputs/patent_metadata.csv   — 专利原始元数据（国家/年份/IPC）
      outputs/no_abstract_list.csv  — 无摘要专利清单（不做 LLM 抽取）

实体抽取范围: 有摘要的唯一专利（LLM 抽取 6 类实体 + 方法-信号对应）。
技术主题/公开国家/公开年份 由原始信息提供（IPC 映射 + country + app_year），
不依赖 LLM。
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]  # 多轨道/
OUT = BASE / "实体抽取，知识图谱构建" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
DATASET = BASE / "数据集合并" / "outputs" / "05_合并数据集.csv"
INFO = BASE / "03_合并专利信息_精简.csv"


def norm(p):
    return re.sub(r"[\s-]", "", str(p)).upper()


# ---------- 1. 05_合并数据集 唯一专利 ----------
m = pd.read_csv(DATASET, encoding="utf-8-sig")
m["pub"] = m["pub"].map(norm)
m["摘要_中文"] = m["摘要_中文"].fillna("")
unq = m.drop_duplicates(subset="pub").copy()

# 主路径标记（该专利是否出现在任何时期主路径上）
main_pubs = set(m[m["类型"] == "原始主路径"]["pub"])
unq["是否主路径"] = unq["pub"].isin(main_pubs)

# ---------- 2. 元数据合并 ----------
info = pd.read_csv(INFO, encoding="utf-8-sig")
info["pub"] = info["公开号"].map(norm)
info = info.drop_duplicates(subset="pub")
meta = info[["pub", "专利标题", "专利标题（中文）", "公开日", "app_year", "country",
             "主IPC分类号", "IPC分类号"]].rename(
    columns={"专利标题": "title", "专利标题（中文）": "title_zh", "公开日": "pub_date"})

# unq 的 title/标题_中文 与 info 冲突, 去掉以 info 为权威
unq = unq.drop(columns=[c for c in ["title", "title_zh", "专利标题", "专利标题（中文）"]
                        if c in unq.columns])
df = unq.merge(meta, on="pub", how="left")

# ---------- 3. 摘要: 优先 05_合并数据集, 空则查 info 中文/英文摘要 ----------
df["摘要_中文"] = df["摘要_中文"].fillna("")
missing = set(df[df["摘要_中文"].eq("")]["pub"])
if missing:
    sup = info[info["pub"].isin(missing)][["pub", "摘要_中文", "摘要"]].set_index("pub")
    for i in df.index:
        if df.at[i, "摘要_中文"] != "":
            continue
        if df.at[i, "pub"] not in sup.index:
            continue
        s = sup.loc[df.at[i, "pub"]]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[0]
        cn = str(s.get("摘要_中文") or "").strip()
        en = str(s.get("摘要") or "").strip()
        df.at[i, "摘要_中文"] = cn or en

# 无摘要清单（13 个主路径外部节点，元数据库中无记录）
noabs = df[df["摘要_中文"].eq("")].copy()
noabs["摘要缺失原因"] = "主路径 window 节点，03_合并专利信息_精简.csv 中无任何记录（无中文/英文摘要）"
noabs["公开国家_推断"] = noabs["pub"].str.extract(r"^([A-Z]{2})")[0].map(
    lambda c: {"US": "美国", "WO": "世界知识产权组织", "EP": "欧洲专利局", "CN": "中国",
               "JP": "日本", "KR": "韩国", "DE": "德国", "FR": "法国", "GB": "英国",
               "CA": "加拿大", "AU": "澳大利亚", "IN": "印度", "IL": "以色列",
               "BR": "巴西", "RU": "俄罗斯"}.get(c, c))

# ---------- 4. 生成实体抽取任务 ----------
PROMPT_TMPL = """你是专利文本挖掘专家。从给定专利的标题和摘要中抽取实体，用于构建专利知识图谱。

【待抽取专利】
公开号：{pub}
标题：{title}
摘要：
{abstract}

【抽取任务】严格按下列 6 类实体抽取，每类 1~5 个，优先使用摘要中的原词或标准技术术语；摘要未提及的类输出空数组：
1. 技术问题：该专利要解决的技术问题、缺陷或需求
2. 应用场景：该专利适用的应用场景或应用领域
3. 技术方法：采用的技术方法、手段、算法或流程
4. 生物信号类型：处理、采集或分析的生物信号（如 EEG、fMRI、心率等）
5. 技术原理：依据的技术原理或作用机制
6. 核心部件：系统或装置包含的核心组件、模块

另外给出 方法-信号 对应关系：每条"技术方法 处理 生物信号类型"的配对。

【输出】只输出一个 JSON 对象，不要输出任何其他文字：
{{"技术问题": [], "应用场景": [], "技术方法": [], "生物信号类型": [], "技术原理": [], "核心部件": [], "方法-信号": [{{"方法": "", "信号": ""}}]}}"""

tasks = []
for _, r in df[df["摘要_中文"].ne("")].iterrows():
    title = str(r.get("title_zh") or r.get("title") or r["pub"])
    prompt = PROMPT_TMPL.format(pub=r["pub"], title=title, abstract=r["摘要_中文"])
    tasks.append({"id": r["pub"], "prompt": prompt})

with open(OUT / "tasks.jsonl", "w", encoding="utf-8") as f:
    for t in tasks:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")

# ---------- 5. 元数据表 + 无摘要清单 ----------
meta_cols = ["pub", "title", "title_zh", "摘要_中文", "申请日", "app_year", "country",
             "pub_date", "主IPC分类号", "IPC分类号", "数据来源", "是否主路径"]
df["数据来源"] = df["数据来源"].fillna("")
df[meta_cols].to_csv(OUT / "patent_metadata.csv", index=False, encoding="utf-8-sig")
noabs[["pub", "title", "title_zh", "摘要缺失原因", "公开国家_推断"]].to_csv(
    OUT / "no_abstract_list.csv", index=False, encoding="utf-8-sig")

# ---------- 6. 统计 ----------
n_total = len(df)
n_abs = len(df[df["摘要_中文"].ne("")])
n_main_abs = len(df[(df["是否主路径"]) & (df["摘要_中文"].ne(""))])
n_main_all = int(df["是否主路径"].sum())
lines = [
    "=== 01_prepare_tasks 统计 ===",
    f"唯一专利总数: {n_total}",
    f"有摘要(LLM抽取): {n_abs} | 无摘要: {n_total - n_abs}",
    f"主路径唯一专利: {n_main_all} (有摘要 {n_main_abs} / 无摘要 {n_main_all - n_main_abs})",
    f"country 覆盖: {df['country'].fillna('').ne('').sum()}/{n_total}",
    f"app_year 覆盖: {df['app_year'].fillna('').ne('').sum()}/{n_total}",
    f"主IPC 覆盖: {df['主IPC分类号'].fillna('').ne('').sum()}/{n_total}",
    f"tasks.jsonl: {len(tasks)} 条",
]
(OUT / "prepare_stats.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"tasks={len(tasks)} no_abstract={n_total - n_abs} "
      f"country_ok={df['country'].fillna('').ne('').sum()}")
