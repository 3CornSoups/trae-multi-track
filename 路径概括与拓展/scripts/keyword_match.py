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
    """文本命中关键词的总出现次数（同一关键词多次出现累加，不同关键词累加）。"""
    hits = 0
    for kw in keywords or []:
        if not kw or not str(kw).strip():
            continue
        hits += len(_kw_regex(str(kw)).findall(text))
    return hits


def score_dim_groups(text: str, dims: dict, dim_map: dict, weights: dict) -> float:
    """按维度打分并归一化：Σ min(hit,3)*w / Σ w（缺失维度权重计 0）。

    中/英关键词视为同一概念的不同表述：概念出现次数取 max(中频, 英频)，
    避免翻译对照文本（原文+译文同现）被双计。
    """
    num, den = 0.0, 0.0
    for dim_key, meta in (dims or {}).items():
        if not isinstance(meta, dict):
            continue  # LLM 输出不合规（维度为 null/非对象）时跳过该维度
        w = weights.get(dim_map.get(dim_key, ""), 0.0)
        if w == 0.0:
            continue
        den += w
        zh_kws = meta.get("关键词_中") or []
        en_kws = meta.get("关键词_英") or []
        if isinstance(zh_kws, str):
            zh_kws = [zh_kws]  # 容错：LLM 输出可能为字符串而非列表
        if isinstance(en_kws, str):
            en_kws = [en_kws]
        num += w * min(max(count_hits(text, zh_kws), count_hits(text, en_kws)), _HIT_CAP)
    return num / den if den > 0 else 0.0


def score_overall(text: str, summary: dict) -> float:
    """时期整体得分 S_period。"""
    return score_dim_groups(text, summary.get("overall", {}), OVERALL_DIM_MAP, WEIGHTS)


def score_path_diff(text: str, path_summary: dict) -> float:
    """路径差异化得分 S_path。"""
    return score_dim_groups(text, path_summary.get("差异化特征", {}), PATH_DIM_MAP, WEIGHTS)
