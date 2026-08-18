# -*- coding: utf-8 -*-
"""Step 1: 主路径节点解析 + 全量专利中文摘要提取。"""
import re
import unicodedata
import pandas as pd

from config import PATHS_DIR, PATENTS_FILE, TOP_N_PATHS

_CJK_RE = re.compile(r"[一-鿿㐀-䶿]")
_ARROW_RE = re.compile(r"\s*→\s*")


def normalize_pubnum(pub: str) -> str:
    """规范化公开号：去连字符、大写。"""
    if not isinstance(pub, str):
        return ""
    return unicodedata.normalize("NFKC", pub).replace("-", "").upper()


def parse_node_sequence(seq: str) -> list[str]:
    """'A → B → C' → ['A','B','C']（已规范化）"""
    if not isinstance(seq, str) or not seq.strip():
        return []
    return [normalize_pubnum(n) for n in _ARROW_RE.split(seq.strip())]


def resolve_abstract(abstract, translated) -> str | None:
    """统一为中文摘要文本；无法获得则返回 None。
    规则：翻译列非空用它；否则摘要含 CJK 用原文；否则 None。"""
    if translated and isinstance(translated, str) and translated.strip():
        return translated.strip()
    if abstract and isinstance(abstract, str) and _CJK_RE.search(abstract):
        return abstract.strip()
    return None


def load_top_paths(period: str) -> list[dict]:
    """该时期 rank_by_spc ≤ TOP_N_PATHS 的路径。"""
    df = pd.read_csv(PATHS_DIR / f"窗口_{period}_全部路径.csv", encoding="utf-8-sig")
    top = df.sort_values("rank_by_spc").head(TOP_N_PATHS)
    return [{"path_id": int(r["path_id"]), "nodes": parse_node_sequence(r["node_sequence"])}
            for _, r in top.iterrows()]


def load_patent_texts() -> pd.DataFrame:
    """全量专利（03_合并专利信息_精简.csv），统一中文摘要文本；text 为空的排除。"""
    df = pd.read_csv(PATENTS_FILE, encoding="utf-8-sig",
                     usecols=["公开号", "专利标题", "摘要", "摘要_中文",
                              "申请日", "公开日", "数据来源"])
    df["pub"] = df["公开号"].astype(str).map(normalize_pubnum)
    df["text"] = [resolve_abstract(a, t) for a, t in zip(df["摘要"], df["摘要_中文"])]
    df = df.dropna(subset=["text"]).rename(columns={
        "专利标题": "title", "申请日": "apply_date", "公开日": "pub_date", "数据来源": "source"})
    return df[["pub", "text", "title", "apply_date", "pub_date", "source"]].copy()


def path_abstracts(period: str, paths: list[dict], patents_df: pd.DataFrame) -> list[dict]:
    """每路径内部节点（能命中全量表的）及其摘要文本。"""
    pub_set = set(patents_df["pub"])
    by_pub = {p: row for p, row in zip(patents_df["pub"], patents_df.to_dict("records"))}
    result = []
    for p in paths:
        items = []
        for node in p["nodes"]:
            if node in pub_set:
                row = by_pub[node]
                items.append({"node": node, "title": row["title"], "text": row["text"]})
        result.append({"path_id": p["path_id"], "nodes": p["nodes"], "items": items})
    return result
