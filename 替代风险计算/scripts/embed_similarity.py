# -*- coding: utf-8 -*-
"""实体嵌入语义相似度：bge-small-zh-v1.5 编码三类实体集合，
每主题×关系计算对称最佳匹配均值 → entity_sim_by_topic.csv。
input_suffix 机制：config.json 的 input_suffix 非空时读写带该后缀的文件
（patent_route{suffix}.csv → entity_sim_by_topic{suffix}.csv，如 _paths 路线版）。"""
import json
import os

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
INTER_DIR = os.path.join(ROOT, 'outputs', 'intermediate')
VEC_CACHE = os.path.join(INTER_DIR, 'entity_vecs.npy')   # 纯浮点 npy，无 pickle
NAME_CACHE = os.path.join(INTER_DIR, 'entity_names.csv')  # 实体名一行一个

REL_COLS = {'采用': 'func', '应用于': 'scene', '基于': 'princ'}


def parse_sets(s) -> set:
    if pd.isna(s) or s == '':
        return set()
    return set(str(s).split('|'))


def symmetric_max_match(a_vecs: np.ndarray, b_vecs: np.ndarray) -> float:
    """对称最佳匹配均值：½[mean_a max_b cos + mean_b max_a cos]，值域 [0,1]。

    输入为已归一化的向量矩阵（每行一个实体）；空矩阵由调用方处理。
    """
    cos = a_vecs @ b_vecs.T
    ab = cos.max(axis=1).mean()
    ba = cos.max(axis=0).mean()
    return float((ab + ba) / 2.0)


def load_entity_vectors() -> tuple:
    """编码全部唯一实体（三类并集），npy+names.csv 缓存；返回 (实体名列表, 归一化向量)。

    注意：patent_route.csv 或 embed_model 变更后须手动删除 entity_vecs.npy 与
    entity_names.csv，否则会静默使用旧缓存。
    """
    if os.path.exists(VEC_CACHE) and os.path.exists(NAME_CACHE):
        names = (pd.read_csv(NAME_CACHE, header=None, dtype=str)[0]
                   .tolist())
        return names, np.load(VEC_CACHE)

    with open(os.path.join(ROOT, 'config.json'), encoding='utf-8') as f:
        cfg = json.load(f)

    patent = pd.read_csv(os.path.join(INTER_DIR, 'patent_route.csv'), dtype=str)
    entities = set()
    for col in REL_COLS.values():
        for s in patent[col]:
            entities |= parse_sets(s)
    names = sorted(entities)

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(cfg['embed_model'])
    vecs = model.encode(names, batch_size=256, show_progress_bar=False,
                        normalize_embeddings=True)
    np.save(VEC_CACHE, vecs)
    pd.Series(names).to_csv(NAME_CACHE, index=False, header=False,
                            encoding='utf-8-sig')
    return names, vecs


def main() -> None:
    with open(os.path.join(ROOT, 'config.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    suffix = cfg.get('input_suffix', '')
    patent = pd.read_csv(os.path.join(INTER_DIR, f'patent_route{suffix}.csv'),
                         dtype=str)
    patent['topic_code'] = patent['topic_code'].fillna('')
    names, vecs = load_entity_vectors()
    idx = {n: i for i, n in enumerate(names)}

    def set_vecs(es: set) -> np.ndarray:
        ids = sorted(idx[n] for n in es)
        return vecs[ids] if ids else np.zeros((0, vecs.shape[1]))

    rows = []
    for code, grp in patent.loc[patent['topic_code'] != ''].groupby('topic_code'):
        dom = grp.loc[grp['is_cn'].astype(int) == 1]
        for_ = grp.loc[grp['is_cn'].astype(int) == 0]
        row = {'topic_code': code}
        for col in REL_COLS.values():
            a = set()
            for s in dom[col]:
                a |= parse_sets(s)
            b = set()
            for s in for_[col]:
                b |= parse_sets(s)
            row[col] = symmetric_max_match(set_vecs(a), set_vecs(b)) if a and b else 0.0
        rows.append(row)

    out = (pd.DataFrame(rows)
           .rename(columns={'func': 'F_sim', 'scene': 'C_sim', 'princ': 'P_sim'}))
    out.to_csv(os.path.join(INTER_DIR, f'entity_sim_by_topic{suffix}.csv'),
               index=False, encoding='utf-8-sig')
    print(f'entity_sim_by_topic{suffix}: {len(out)} 行; F_sim>0.6: {(out["F_sim"] > 0.6).sum()}, '
          f'C_sim>0.5: {(out["C_sim"] > 0.5).sum()}, P_sim>0.7: {(out["P_sim"] > 0.7).sum()}')


if __name__ == '__main__':
    main()
