# -*- coding: utf-8 -*-
"""预筛：embedding 编码（缓存）+ 余弦矩阵 + 每路径候选池（top-N ∪ cos 阈值）。"""
from pathlib import Path

import numpy as np
import pandas as pd

from sem_config import CACHE_DIR, COS_TH, EMBED_BATCH, EMBED_MODEL, TOP_N, OUTPUT_DIR


def encode_texts(texts: list[str], cache_file: Path) -> np.ndarray:
    """编码并缓存 .npy；缓存存在则直接加载（重跑秒级）。"""
    if cache_file.exists():
        return np.load(cache_file)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBED_MODEL)
    vecs = model.encode(texts, batch_size=EMBED_BATCH, show_progress_bar=True,
                        normalize_embeddings=True)
    np.save(cache_file, vecs)
    return vecs


def build_candidates(cand_pubs: list[str], cand_texts: list[str],
                     path_pats: pd.DataFrame, exclude_pubs: set[str]) -> pd.DataFrame:
    """每路径候选：余弦 top-TOP_N ∪ cos > COS_TH；排除主路径自身成员与路径专利本身。

    返回列: period, path_id, path_pub, pub, cos（按路径分组的候选对）。
    """
    cand_vecs = encode_texts(cand_texts, CACHE_DIR / "cand_vecs.npy")
    path_vecs = encode_texts(path_pats["text"].tolist(), CACHE_DIR / "path_vecs.npy")
    cos = cand_vecs @ path_vecs.T  # 31650 × 179（归一化向量点积 = 余弦）

    rows = []
    path_pats = path_pats.reset_index(drop=True)
    for j in range(len(path_pats)):
        pp = path_pats.iloc[j]
        scores = cos[:, j]
        top_idx = np.argpartition(scores, -TOP_N)[-TOP_N:]          # top-200
        above = np.where(scores > COS_TH)[0]                        # cos > 0.4
        idx = np.unique(np.concatenate([top_idx, above]))
        for i in idx:
            pub = cand_pubs[i]
            if pub in exclude_pubs or pub == pp["pub"]:
                continue
            rows.append({"period": pp["period"], "path_id": pp["path_id"],
                         "path_pub": pp["pub"], "pub": pub, "cos": float(scores[i])})
    return pd.DataFrame(rows, columns=["period", "path_id", "path_pub", "pub", "cos"])
